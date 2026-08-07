"""Transcript-derived mini-leaderboard and exploit observations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import fields as dataclass_fields
import json
import math
from pathlib import Path
import re
from statistics import fmean
from typing import Any, Iterable

from .engine import FinalResult, WeekOutcome, _State
from .provenance import engine_config_hash
from .scoring import PAIN_DAYS_LIMIT, score_fields
from .schemas import (
    InterruptObservation,
    LifeAllocation,
    PlannedEvent,
    ReactiveAction,
    RecentWeek,
    SessionPlan,
    StandingRules,
    WeekAction,
    WeekObservation,
)


def _serialized_dataclass_fields(dataclass_type: type[Any]) -> set[str]:
    """Return fields emitted by a public dataclass serializer.

    The dummy object lets this derive omissions made by ``as_dict`` (notably
    evaluator-only state) without duplicating a private-field allowlist here.
    """
    value = object.__new__(dataclass_type)
    for field in dataclass_fields(dataclass_type):
        object.__setattr__(value, field.name, None)
    return set(dataclass_type.as_dict(value))  # type: ignore[attr-defined]


_STATE_FIELDS = {field.name for field in dataclass_fields(_State)}
_PUBLIC_SCHEMA_FIELDS = {
    field_name
    for schema_type in (
        InterruptObservation,
        LifeAllocation,
        PlannedEvent,
        ReactiveAction,
        RecentWeek,
        SessionPlan,
        StandingRules,
        WeekAction,
        WeekObservation,
    )
    for field_name in schema_type.model_fields
}
_PUBLIC_SCHEMA_FIELDS.update(_serialized_dataclass_fields(WeekOutcome))
_PUBLIC_SCHEMA_FIELDS.update(_serialized_dataclass_fields(FinalResult))

# The vocabulary is derived from the engine's state surface and the fields
# explicitly declared at the public boundary.  A newly added evaluator-only
# state field therefore becomes auditable without another hand-maintained set.
_PRIVATE_PUBLIC_FIELDS = _STATE_FIELDS - _PUBLIC_SCHEMA_FIELDS


def _private_field_hits(value: Any, hits: set[str] | None = None) -> set[str]:
    """Find evaluator-only field names that were serialized into a transcript."""
    hits = hits if hits is not None else set()
    if isinstance(value, dict):
        hits.update(str(key) for key in value if key in _PRIVATE_PUBLIC_FIELDS)
        for child in value.values():
            _private_field_hits(child, hits)
    elif isinstance(value, list):
        for child in value:
            _private_field_hits(child, hits)
    return hits


def _endpoint_label(record: dict[str, Any]) -> str:
    metadata = record.get("endpoint_metadata")
    if not isinstance(metadata, dict):
        return "MISSING"
    kind = str(metadata.get("kind", "unknown"))
    url = metadata.get("url")
    return f"{kind} ({url})" if url else kind


def _transport_error_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Count provider/transport failures separately from malformed model output."""
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        attempt_groups = [record.get("attempts", [])]
        if record.get("type") == "turn":
            attempt_groups.extend(reactive.get("attempts", []) for reactive in record.get("reactive_turns", []))
        for attempts in attempt_groups:
            for attempt in attempts:
                error = str(attempt.get("error", ""))
                if not error.startswith("model request failed:"):
                    continue
                match = re.search(r"HTTP Error (\d+)", error)
                counts[f"http_{match.group(1)}" if match else "model_request_failed"] += 1
    return dict(sorted(counts.items()))


def analyze_transcript(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = next(record for record in records if record.get("type") == "run_start")
    turns = [record for record in records if record.get("type") == "turn"]
    end = next((record for record in records if record.get("type") == "run_end"), {})
    private_fields = sorted(_private_field_hits(records))
    transport_errors = _transport_error_counts(records)
    configured_weeks = int(start.get("config", {}).get("weeks", 0) or 0)
    recorded_hash = start.get("engine_config_hash")
    current_hash = engine_config_hash()
    replayed_under_current_engine = bool(start.get("replayed_under_current_engine", False))
    observed_weeks = [int(record["week"]) for record in turns]
    transcript_violations: list[str] = []
    if configured_weeks and len(turns) != configured_weeks:
        transcript_violations.append(f"expected_{configured_weeks}_turns_got_{len(turns)}")
    if configured_weeks and sorted(observed_weeks) != list(range(1, configured_weeks + 1)):
        transcript_violations.append("week_sequence_not_unique_and_complete")
    sessions = [session for turn in turns for session in turn["action"].get("sessions", [])]
    none_sleep_weeks = sum(turn["action"].get("life", {}).get("sleep_protection") == "none" for turn in turns)
    imbalanced_weeks = sum(
        turn["action"].get("life", {}).get("partner_coverage_hours", 0)
        > turn["action"].get("life", {}).get("partner_giveback_hours", 0) + 2
        for turn in turns
    )
    heavy_sessions = sum(session.get("focus") == "heavy" or session.get("target_rpe", 0) >= 9 for session in sessions)
    final_week = max((int(turn["week"]) for turn in turns), default=0)
    final_action = next((turn["action"] for turn in turns if int(turn["week"]) == final_week), {})
    final_heavy = any(session.get("focus") in ("heavy", "test") for session in final_action.get("sessions", []))
    purchases = [purchase for turn in turns for purchase in turn["action"].get("life", {}).get("purchases", [])]
    final_result = end.get("result", {})
    if not isinstance(final_result, dict):
        final_result = {}
    required_final_fields = ("final_1rm_kg", "pain_days", "invalid_reason")
    for field_name in required_final_fields:
        if field_name not in final_result:
            transcript_violations.append(f"missing_final_result_field:{field_name}")
    invalid_reason = final_result.get("invalid_reason")
    score = score_fields(
        final_result.get("final_1rm_kg"),
        invalid_reason=invalid_reason,
        pain_days=final_result.get("pain_days"),
    )
    exclusion_reasons: list[str] = []
    if invalid_reason is not None:
        exclusion_reasons.append(f"invalid: {invalid_reason}")
    exclusion_reasons.extend(f"constraint: {violation}" for violation in score["constraint_violations"])
    if transcript_violations:
        exclusion_reasons.extend(f"transcript: {violation}" for violation in transcript_violations)
    if transport_errors:
        exclusion_reasons.extend(f"transport: {error}" for error in transport_errors)
    observations: list[str] = []
    if sessions and heavy_sessions / len(sessions) >= 0.7:
        observations.append("weekly-maxing / high-intensity fixation")
    if none_sleep_weeks >= max(2, len(turns) // 3):
        observations.append("sleep-sacrifice policy")
    if imbalanced_weeks >= max(2, len(turns) // 3):
        observations.append("household reciprocity debt")
    if final_heavy:
        observations.append("late final-week intensity gamble")
    if len(purchases) > 1:
        observations.append("capital stacking before the budget recovered")
    if any(record.get("parse_errors") for record in turns):
        observations.append("format repair required")
    return {
        "path": str(path),
        "model": start.get("model"),
        "provider": start.get("provider"),
        "endpoint_metadata": start.get("endpoint_metadata"),
        "seed": int(start.get("seed", -1)),
        "weeks": len(turns),
        "configured_weeks": configured_weeks,
        "valid": not exclusion_reasons and all(field_name in final_result for field_name in required_final_fields),
        "invalid_reason": invalid_reason,
        "exclusion_reasons": exclusion_reasons,
        # Keep the legacy field as the raw engine result for compatibility;
        # leaderboard aggregates use counted_final_1rm_kg below.
        "final_1rm_kg": score["raw_final_1rm_kg"],
        "raw_final_1rm_kg": score["raw_final_1rm_kg"],
        "counted_final_1rm_kg": score["counted_final_1rm_kg"] if not exclusion_reasons else None,
        "constraint_violations": score["constraint_violations"],
        "violations": score["constraint_violations"],
        "pain_days": (
            int(final_result["pain_days"])
            if isinstance(final_result.get("pain_days"), (int, float))
            and not isinstance(final_result.get("pain_days"), bool)
            and math.isfinite(float(final_result["pain_days"]))
            else None
        ),
        "planned_sessions": int(final_result.get("planned_sessions", 0)),
        "transformed_sessions": int(final_result.get("transformed_sessions", 0)),
        "attempted_sessions": int(final_result.get("attempted_sessions", 0)),
        "completed_sessions": int(final_result.get("completed_sessions", 0)),
        "missed_sessions": int(final_result.get("missed_sessions", 0)),
        "fallback_sessions": int(final_result.get("fallback_sessions", 0)),
        "model_calls": int(end.get("model_calls", 0)),
        "repair_calls": int(end.get("repair_calls", 0)),
        "total_cost_usd": float(end.get("total_cost_usd", 0.0)),
        "heavy_session_fraction": round(heavy_sessions / len(sessions), 4) if sessions else 0.0,
        "none_sleep_weeks": none_sleep_weeks,
        "imbalanced_household_weeks": imbalanced_weeks,
        "purchases": purchases,
        "observations": observations,
        "privacy_violations": private_fields,
        "transport_errors": transport_errors,
        "transcript_violations": transcript_violations,
        "engine_config_hash": recorded_hash,
        "current_engine_config_hash": current_hash,
        "engine_config_hash_matches": recorded_hash == current_hash,
        "replayed_under_current_engine": replayed_under_current_engine,
    }


def analyze_paths(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Analyze an explicit transcript set without importing stale neighbors."""
    return [analyze_transcript(path) for path in sorted((Path(path) for path in paths), key=str)]


def analyze_directory(directory: str | Path) -> list[dict[str, Any]]:
    return analyze_paths(Path(directory).glob("*.jsonl"))


def leaderboard_markdown(records: Iterable[dict[str, Any]]) -> str:
    all_values = list(records)
    values = [
        record
        for record in all_values
        if record.get("valid", record.get("invalid_reason") is None)
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in all_values:
        all_grouped[str(record["model"])].append(record)
        if record.get("valid", record.get("invalid_reason") is None):
            grouped[str(record["model"])].append(record)
    configured_weeks = max((int(record.get("configured_weeks", 0)) for record in all_values), default=0)
    live_endpoint = bool(all_values) and all(
        isinstance(record.get("endpoint_metadata"), dict)
        and record["endpoint_metadata"].get("kind") == "openai-compatible"
        for record in all_values
    )
    replayed = bool(all_values) and all(record.get("replayed_under_current_engine") for record in all_values)
    if replayed and configured_weeks >= 52:
        title = "# Bench-bench Authoritative Public Leaderboard"
    else:
        title = "# Bench-bench Phase 4 Live Leaderboard" if live_endpoint and configured_weeks >= 52 else "# Bench-bench Phase 3 Mini-Leaderboard"
    description = (
        "This is an offline re-evaluation of the checked-in public model actions under the current engine/config hash; no model calls were made during regeneration."
        if replayed
        else
        "This artifact is generated from live model transcripts. Endpoint provenance and transport errors are audited below; a failed transport audit must not be presented as a model result."
        if live_endpoint
        else "This artifact is generated from runner transcripts. It is a local deterministic runner smoke test unless the input directory was produced with a live endpoint; it must not be presented as a frontier-model result without endpoint metadata."
    )
    lines = [
        title,
        "",
        description,
        "",
        f"- Engine/config hash: `{engine_config_hash()}`",
        "| Model | Valid seeds | Excluded | Counted mean final 1RM (kg) | Counted seed std (kg) | Mean calls | Mean cost | Repairs | Violations | Raw mean final 1RM (kg) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for model in sorted(all_grouped):
        model_records = grouped.get(model, [])
        excluded_count = len(all_grouped[model]) - len(model_records)
        scores = [record["counted_final_1rm_kg"] for record in model_records if record.get("counted_final_1rm_kg") is not None]
        raw_scores = [
            record["raw_final_1rm_kg"]
            for record in all_grouped[model]
            if record.get("raw_final_1rm_kg") is not None
        ]
        violation_counts: dict[str, int] = defaultdict(int)
        for record in all_grouped[model]:
            for violation in record.get("constraint_violations", record.get("violations", [])):
                violation_counts[str(violation)] += 1
        violations = ", ".join(f"{name} ({count})" for name, count in sorted(violation_counts.items())) or "—"
        mean = fmean(scores) if scores else 0.0
        variance = fmean((score - mean) ** 2 for score in scores) if scores else 0.0
        raw_mean = fmean(raw_scores) if raw_scores else None
        if model_records:
            lines.append(
                f"| {model} | {len(scores)} | {excluded_count} | {mean:.2f} | {variance ** 0.5:.2f} | {fmean(record['model_calls'] for record in model_records):.1f} | ${fmean(record['total_cost_usd'] for record in model_records):.4f} | {sum(record['repair_calls'] for record in model_records)} | {violations} | {raw_mean:.2f} |"
                if scores
                else
                f"| {model} | 0 | {excluded_count} | — | — | {fmean(record['model_calls'] for record in model_records):.1f} | ${fmean(record['total_cost_usd'] for record in model_records):.4f} | {sum(record['repair_calls'] for record in model_records)} | {violations} | {raw_mean:.2f} |"
            )
        else:
            lines.append(f"| {model} | 0 | {excluded_count} | — | — | — | — | — | {violations} | {raw_mean:.2f} |" if raw_mean is not None else f"| {model} | 0 | {excluded_count} | — | — | — | — | — | {violations} | — |")
    endpoint_values = {_endpoint_label(record) for record in all_values}
    privacy_counts: dict[str, int] = defaultdict(int)
    transcript_counts: dict[str, int] = defaultdict(int)
    transport_record_counts: dict[str, int] = defaultdict(int)
    transport_attempt_counts: dict[str, int] = defaultdict(int)
    for record in all_values:
        for field in record.get("privacy_violations", []):
            privacy_counts[field] += 1
        for violation in record.get("transcript_violations", []):
            transcript_counts[violation] += 1
        for error, count in record.get("transport_errors", {}).items():
            transport_record_counts[error] += 1
            transport_attempt_counts[error] += int(count)
    endpoint_status = "present" if all_values and all(record.get("endpoint_metadata") for record in all_values) else "INCOMPLETE"
    lines.extend(["", "## Provenance and transcript audit", ""])
    hash_matches = sum(record.get("engine_config_hash_matches") is True for record in all_values)
    lines.append(f"- Engine/config hash audit: {'PASS' if hash_matches == len(all_values) else 'FAILED'} on {hash_matches}/{len(all_values)} transcripts.")
    lines.append(f"- Endpoint metadata: {endpoint_status} on {sum(bool(record.get('endpoint_metadata')) for record in all_values)}/{len(all_values)} transcripts.")
    lines.append(f"- Endpoint identities: {', '.join(sorted(endpoint_values)) if endpoint_values else 'none'}.")
    if privacy_counts:
        details = ", ".join(f"{field} in {count}/{len(all_values)} transcripts" for field, count in sorted(privacy_counts.items()))
        lines.append(f"- Public-field audit: FAILED ({details}).")
    else:
        lines.append("- Public-field audit: PASS (no evaluator-only fields detected).")
    if transport_record_counts:
        details = ", ".join(
            f"{error} in {transport_record_counts[error]}/{len(all_values)} transcripts ({transport_attempt_counts[error]} attempts)"
            for error in sorted(transport_record_counts)
        )
        lines.append(f"- Transport-error audit: FAILED ({details}).")
    else:
        lines.append("- Transport-error audit: PASS (no provider/transport failures detected).")
    if transcript_counts:
        details = ", ".join(f"{violation} in {count}/{len(all_values)} transcripts" for violation, count in sorted(transcript_counts.items()))
        lines.append(f"- Transcript-structure audit: FAILED ({details}).")
    else:
        lines.append("- Transcript-structure audit: PASS (configured weeks are unique and complete).")
    invalid_records = [record for record in all_values if record.get("invalid_reason") is not None]
    constraint_records = [record for record in all_values if record.get("constraint_violations") or record.get("violations")]
    excluded_records = [record for record in all_values if not record.get("valid", record.get("invalid_reason") is None)]
    if invalid_records:
        invalid_counts: dict[str, int] = defaultdict(int)
        for record in invalid_records:
            invalid_counts[str(record["invalid_reason"])] += 1
        details = ", ".join(f"{reason}: {count}" for reason, count in sorted(invalid_counts.items()))
        lines.append(f"- Invalid-episode audit: EXCLUDED {len(invalid_records)}/{len(all_values)} transcripts ({details}).")
    else:
        lines.append("- Invalid-episode audit: PASS (no invalid episodes detected).")
    if constraint_records:
        violation_counts: dict[str, int] = defaultdict(int)
        for record in constraint_records:
            for violation in record.get("constraint_violations", record.get("violations", [])):
                violation_counts[str(violation)] += 1
        details = ", ".join(f"{violation}: {count}" for violation, count in sorted(violation_counts.items()))
        lines.append(f"- Hard-constraint audit: EXCLUDED {len(constraint_records)}/{len(all_values)} transcripts ({details}); raw scores retained.")
    else:
        lines.append(f"- Hard-constraint audit: PASS (pain days ≤{PAIN_DAYS_LIMIT} on all transcripts).")
    if len(excluded_records) > len(invalid_records):
        lines.append(f"- Exclusion audit: EXCLUDED {len(excluded_records)}/{len(all_values)} records after validity checks.")
    lines.extend(["", "## Observed transcript behaviors", ""])
    observations: dict[str, int] = defaultdict(int)
    for record in values:
        for observation in record["observations"]:
            observations[f"{record['model']}: {observation}"] += 1
    if observations:
        for observation, count in sorted(observations.items()):
            lines.append(f"- {observation} ({count} transcript{'s' if count != 1 else ''})")
    else:
        lines.append("- No exploit signature crossed the analyzer thresholds.")
    method = (
        "The analyzer reads public model transcripts and re-evaluated final results. Structurally invalid or pain-violating episodes remain in audit records, their raw final 1RM is retained, and only counted scores enter aggregates."
        if replayed
        else "The analyzer reads only public model transcripts and final results. Structurally invalid or pain-violating episodes remain in audit records, their raw final 1RM is retained, and only counted scores enter aggregates."
    )
    lines.extend(["", "## Method", "", method + " It flags repeated high-intensity sessions, sleep protection choices, reciprocity imbalance, final-week intensity, capital stacking, and format repairs; these are triage signals for human transcript reading, not extra score components.", ""])
    return "\n".join(lines)


def write_analysis(records: list[dict[str, Any]], json_path: str | Path, markdown_path: str | Path) -> None:
    json_path = Path(json_path)
    markdown_path = Path(markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_records = [record for record in records if record.get("invalid_reason") is not None]
    constraint_records = [record for record in records if record.get("constraint_violations") or record.get("violations")]
    excluded_records = [record for record in records if not record.get("valid", record.get("invalid_reason") is None)]
    json_path.write_text(
        json.dumps(
            {
                "engine_config_hash": engine_config_hash(),
                "records": records,
                "valid_record_count": len(records) - len(excluded_records),
                "excluded_invalid_count": len(invalid_records),
                "constraint_violating_count": len(constraint_records),
                "excluded_record_count": len(excluded_records),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(leaderboard_markdown(records), encoding="utf-8")
