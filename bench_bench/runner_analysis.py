"""Transcript-derived mini-leaderboard and exploit observations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import fields as dataclass_fields
import json
from pathlib import Path
import re
from statistics import fmean, stdev
from typing import Any, Iterable

from .engine import FinalResult, WeekOutcome, _State
from .provenance import current_prompt_hash, engine_config_hash
from .runner import retry_metrics_from_records
from .scoring import (
    HOUSEHOLD_STRAIN_HIGH_WEEK_LIMIT,
    HOUSEHOLD_STRAIN_LIMIT,
    MAX_EPISODE_DAYS,
    MIN_COUNTED_SEED_FRACTION,
    PAIN_DAYS_LIMIT,
    counted_score,
    constraint_violations,
    score_fields,
)
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


def analyze_transcript(
    path: str | Path,
    *,
    historical_pilot: bool = False,
    exclude_transport_failures: bool = True,
) -> dict[str, Any]:
    path = Path(path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = next(record for record in records if record.get("type") == "run_start")
    turns = [record for record in records if record.get("type") == "turn"]
    end = next((record for record in records if record.get("type") == "run_end"), {})
    private_fields = sorted(_private_field_hits(records))
    transport_errors = _transport_error_counts(records)
    retry_metrics = retry_metrics_from_records(records)
    successful_model_decisions = 0
    for record in records:
        if record.get("type") != "turn":
            continue
        attempt_groups = [record.get("attempts", [])]
        attempt_groups.extend(
            reactive.get("attempts", []) for reactive in record.get("reactive_turns", []) or []
        )
        for attempts in attempt_groups:
            if any(
                attempt.get("is_model_call", True)
                and not attempt.get("error")
                and not attempt.get("fallback")
                for attempt in attempts
            ):
                successful_model_decisions += 1
    configured_weeks = int(start.get("config", {}).get("weeks", 0) or 0)
    recorded_hash = start.get("engine_config_hash")
    current_hash = engine_config_hash()
    recorded_prompt_hash = start.get("prompt_hash")
    current_prompt = current_prompt_hash()
    replayed_under_current_engine = bool(start.get("replayed_under_current_engine", False))
    observed_weeks = [int(record["week"]) for record in turns]
    transcript_violations: list[str] = []
    if configured_weeks and len(turns) != configured_weeks:
        transcript_violations.append(f"expected_{configured_weeks}_turns_got_{len(turns)}")
    if configured_weeks and sorted(observed_weeks) != list(range(1, configured_weeks + 1)):
        transcript_violations.append("week_sequence_not_unique_and_complete")
    if recorded_hash != current_hash and not historical_pilot:
        transcript_violations.append("engine_config_hash_mismatch")
    if recorded_prompt_hash != current_prompt and not historical_pilot:
        transcript_violations.append("prompt_hash_mismatch")
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
    required_final_fields = (
        ("final_1rm_kg", "pain_days", "invalid_reason")
        if historical_pilot
        else (
            "final_1rm_kg",
            "pain_days",
            "household_strain_peak",
            "mean_household_strain",
            "household_strain_high_weeks",
            "final_third_mean_household_strain",
            "invalid_reason",
        )
    )
    for field_name in required_final_fields:
        if field_name not in final_result:
            transcript_violations.append(f"missing_final_result_field:{field_name}")
    invalid_reason = final_result.get("invalid_reason")
    config_data = start.get("config", {})
    if historical_pilot:
        historical_violations = tuple(
            violation
            for violation in constraint_violations(pain_days=final_result.get("pain_days"))
            if violation in {"missing_pain_days", "invalid_pain_days"}
            or violation.startswith("pain_days>")
        )
        score = {
            "raw_final_1rm_kg": (
                float(final_result["final_1rm_kg"])
                if final_result.get("final_1rm_kg") is not None
                else None
            ),
            "counted_final_1rm_kg": counted_score(
                final_result.get("final_1rm_kg"),
                invalid_reason=invalid_reason,
                violations=historical_violations,
            ),
            "constraint_violations": list(historical_violations),
        }
    else:
        score = score_fields(
            final_result.get("final_1rm_kg"),
            invalid_reason=invalid_reason,
            pain_days=final_result.get("pain_days"),
            household_strain_high_weeks=final_result.get("household_strain_high_weeks"),
            final_third_mean_household_strain=final_result.get("final_third_mean_household_strain"),
            household_strain_limit=float(
                config_data.get("household_strain_limit", HOUSEHOLD_STRAIN_LIMIT)
            ),
            household_strain_high_week_limit=int(
                config_data.get("household_strain_high_week_limit", HOUSEHOLD_STRAIN_HIGH_WEEK_LIMIT)
            ),
        )
    exclusion_reasons: list[str] = []
    if invalid_reason is not None:
        exclusion_reasons.append(f"invalid: {invalid_reason}")
    exclusion_reasons.extend(f"constraint: {violation}" for violation in score["constraint_violations"])
    transport_excluded = bool(exclude_transport_failures and retry_metrics["transport_failures"])
    if transport_excluded:
        exclusion_reasons.append(
            f"transport: {retry_metrics['transport_failures']} provider failure(s)"
        )
    if transcript_violations:
        exclusion_reasons.extend(f"transcript: {violation}" for violation in transcript_violations)
    final_pain_days = final_result.get("pain_days")
    valid_pain_days = (
        final_pain_days
        if isinstance(final_pain_days, int)
        and not isinstance(final_pain_days, bool)
        and 0 <= final_pain_days <= MAX_EPISODE_DAYS
        else None
    )
    usage_totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "visible_output_tokens": 0,
        "thinking_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
    }
    for turn in turns:
        attempt_groups = [turn.get("attempts", [])]
        attempt_groups.extend(reactive.get("attempts", []) for reactive in turn.get("reactive_turns", []))
        for attempts in attempt_groups:
            for attempt in attempts:
                usage = attempt.get("usage", {}) or {}
                usage_totals["input_tokens"] += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
                usage_totals["cached_input_tokens"] += int(usage.get("cached_prompt_tokens", 0) or 0)
                usage_totals["cache_creation_input_tokens"] += int(usage.get("cache_creation_input_tokens", 0) or 0)
                usage_totals["visible_output_tokens"] += int(usage.get("visible_output_tokens", 0) or 0)
                usage_totals["thinking_tokens"] += int(usage.get("thinking_tokens", 0) or 0)
                usage_totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
                usage_totals["cost_usd"] += float(usage.get("cost_usd", 0.0) or 0.0)
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
        "transport_excluded": transport_excluded,
        "historical_pilot": historical_pilot,
        "invalid_reason": invalid_reason,
        "exclusion_reasons": exclusion_reasons,
        # Keep the legacy field as the raw engine result for compatibility;
        # leaderboard aggregates use counted_final_1rm_kg below.
        "final_1rm_kg": score["raw_final_1rm_kg"],
        "raw_final_1rm_kg": score["raw_final_1rm_kg"],
        "counted_final_1rm_kg": score["counted_final_1rm_kg"] if not exclusion_reasons else None,
        "constraint_violations": score["constraint_violations"],
        "violations": score["constraint_violations"],
        "pain_days": valid_pain_days,
        "household_strain": final_result.get("household_strain"),
        "household_strain_peak": final_result.get("household_strain_peak"),
        "mean_household_strain": final_result.get("mean_household_strain"),
        "household_strain_high_weeks": final_result.get("household_strain_high_weeks"),
        "final_third_mean_household_strain": final_result.get("final_third_mean_household_strain"),
        "planned_sessions": int(final_result.get("planned_sessions", 0)),
        "transformed_sessions": int(final_result.get("transformed_sessions", 0)),
        "attempted_sessions": int(final_result.get("attempted_sessions", 0)),
        "completed_sessions": int(final_result.get("completed_sessions", 0)),
        "missed_sessions": int(final_result.get("missed_sessions", 0)),
        "fallback_sessions": int(final_result.get("fallback_sessions", 0)),
        "model_calls": int(end.get("model_calls", 0)),
        "successful_model_decisions": successful_model_decisions,
        # ``repair_calls`` is retained as the number of repair prompts sent.
        # The release repair rate uses rejected_output_decisions instead.
        "repair_calls": retry_metrics["repair_attempts"],
        "rejected_model_outputs": retry_metrics["rejected_model_outputs"],
        "rejected_output_decisions": retry_metrics["rejected_output_decisions"],
        "repair_attempts": retry_metrics["repair_attempts"],
        "successful_repairs": retry_metrics["successful_repairs"],
        "automatic_fallbacks": retry_metrics["automatic_fallbacks"],
        "transport_failures": retry_metrics["transport_failures"],
        "decision_count": retry_metrics["decisions"],
        "repair_rate": round(
            retry_metrics["rejected_output_decisions"] / retry_metrics["decisions"], 6
        ) if retry_metrics["decisions"] else 0.0,
        "total_tokens": int(end.get("total_tokens", usage_totals["total_tokens"])),
        "input_tokens": int(end.get("input_tokens", usage_totals["input_tokens"])),
        "cached_input_tokens": int(end.get("cached_input_tokens", usage_totals["cached_input_tokens"])),
        "cache_creation_input_tokens": int(end.get("cache_creation_input_tokens", usage_totals["cache_creation_input_tokens"])),
        "visible_output_tokens": int(end.get("visible_output_tokens", usage_totals["visible_output_tokens"])),
        "thinking_tokens": int(end.get("thinking_tokens", usage_totals["thinking_tokens"])),
        "output_tokens": int(end.get("visible_output_tokens", usage_totals["visible_output_tokens"])) + int(end.get("thinking_tokens", usage_totals["thinking_tokens"])),
        "total_cost_usd": float(end.get("total_cost_usd", usage_totals["cost_usd"])),
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
        "prompt_hash": recorded_prompt_hash,
        "current_prompt_hash": current_prompt,
        "prompt_hash_matches": recorded_prompt_hash == current_prompt,
        "replayed_under_current_engine": replayed_under_current_engine,
    }


def analyze_paths(
    paths: Iterable[str | Path],
    *,
    historical_pilot: bool = False,
    exclude_transport_failures: bool = True,
) -> list[dict[str, Any]]:
    """Analyze an explicit transcript set without importing stale neighbors."""
    return [
        analyze_transcript(
            path,
            historical_pilot=historical_pilot,
            exclude_transport_failures=exclude_transport_failures,
        )
        for path in sorted((Path(path) for path in paths), key=str)
    ]


def analyze_directory(
    directory: str | Path,
    *,
    historical_pilot: bool = False,
    exclude_transport_failures: bool = True,
) -> list[dict[str, Any]]:
    """Analyze every transcript below a directory, in stable relative order."""
    root = Path(directory).resolve()
    paths = sorted(
        (
            path
            for path in root.rglob("*.jsonl")
            if "archive" not in path.relative_to(root).parts
            and not path.name.endswith(".current-engine.jsonl")
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    records = analyze_paths(
        paths,
        historical_pilot=historical_pilot,
        exclude_transport_failures=exclude_transport_failures,
    )
    for record, path in zip(records, paths):
        record["path"] = path.relative_to(root).as_posix()
    return records


def leaderboard_aggregates(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build score aggregates without dropping excluded seeds from the denominator."""
    records = list(records)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["model"])].append(record)
    seed_values = {
        record.get("seed")
        for record in records
        if record.get("seed") is not None
    }
    expected_seed_count = max(
        len(seed_values),
        max((len(model_records) for model_records in grouped.values()), default=0),
    )
    aggregates: dict[str, dict[str, Any]] = {}
    for model, model_records in sorted(grouped.items()):
        counted_scores = [
            float(record["counted_final_1rm_kg"])
            for record in model_records
            if record.get("valid", record.get("invalid_reason") is None)
            and record.get("counted_final_1rm_kg") is not None
        ]
        raw_scores = [
            float(record["raw_final_1rm_kg"])
            for record in model_records
            if record.get("raw_final_1rm_kg") is not None
        ]
        counted_fraction = len(counted_scores) / expected_seed_count if expected_seed_count else 0.0
        reportable = counted_fraction >= MIN_COUNTED_SEED_FRACTION
        counted_mean = fmean(counted_scores) if counted_scores and reportable else None
        counted_std = stdev(counted_scores) if len(counted_scores) > 1 and reportable else (0.0 if counted_scores and reportable else None)
        aggregates[model] = {
            "total_seeds": expected_seed_count,
            "counted_seeds": len(counted_scores),
            "excluded_seeds": expected_seed_count - len(counted_scores),
            "counted_seed_fraction": round(counted_fraction, 4),
            "counted_mean_final_1rm_kg": round(counted_mean, 4) if counted_mean is not None else None,
            "counted_seed_std_kg": round(counted_std, 4) if counted_std is not None else None,
            "raw_mean_final_1rm_kg": round(fmean(raw_scores), 4) if raw_scores else None,
            "counted_aggregate_reportable": reportable,
        }
    return aggregates


def leaderboard_markdown(records: Iterable[dict[str, Any]], *, title_override: str | None = None) -> str:
    all_values = list(records)
    historical_pilot = bool(all_values) and all(record.get("historical_pilot") for record in all_values)
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
        and record["endpoint_metadata"].get("kind") in {"openai-compatible", "anthropic-messages"}
        for record in all_values
    )
    replayed = bool(all_values) and all(record.get("replayed_under_current_engine") for record in all_values)
    if title_override:
        title = title_override
    elif historical_pilot:
        title = "# Bench-bench v0.1 Pilot Analyzer Report (Historical)"
    elif replayed and configured_weeks >= 52:
        title = "# Bench-bench Generated Public Leaderboard"
    else:
        title = "# Bench-bench Generated Public Leaderboard" if live_endpoint and configured_weeks >= 52 else "# Bench-bench Phase 3 Mini-Leaderboard"
    description = (
        "Historical compatibility analysis of the archived v0.1 pilot transcripts. The transcripts retain their original engine/config hash; this report does not claim current-engine replay. Any provider transport failure excludes that transcript from counted aggregates while retaining its raw score."
        if historical_pilot
        else
        "This is an offline re-evaluation of the checked-in public model actions under the current engine/config hash; no model calls were made during regeneration."
        if replayed
        else
        "This artifact is generated from live model transcripts. Endpoint provenance and transport errors are audited below; a failed transport audit must not be presented as a model result."
        if live_endpoint
        else "This artifact is generated from runner transcripts. It is a local deterministic runner smoke test unless the input directory was produced with a live endpoint; it must not be presented as a frontier-model result without endpoint metadata."
    )
    aggregates = leaderboard_aggregates(all_values)
    lines = [
        title,
        "",
        description,
        "",
        f"- Analysis engine/config hash: `{engine_config_hash()}`",
        f"- Prompt hash: `{current_prompt_hash()}`",
        "| Model | Valid seeds | Excluded | Counted mean final 1RM (kg) | Counted seed SD (kg) | Decisions | Mean calls | Mean cost | Rejected decisions | Repair attempts | Successful repairs | Transport failures | Auto fallbacks | Violations | Raw mean final 1RM (kg) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for model in sorted(all_grouped):
        model_records = grouped.get(model, [])
        excluded_count = aggregates[model]["excluded_seeds"]
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
        aggregate = aggregates[model]
        mean = aggregate["counted_mean_final_1rm_kg"]
        variance = aggregate["counted_seed_std_kg"]
        raw_mean = fmean(raw_scores) if raw_scores else None
        rejected_decisions = sum(record.get("rejected_output_decisions", 0) for record in all_grouped[model])
        repair_attempts = sum(record.get("repair_attempts", record.get("repair_calls", 0)) for record in all_grouped[model])
        successful_repairs = sum(record.get("successful_repairs", 0) for record in all_grouped[model])
        transport_failures = sum(record.get("transport_failures", 0) for record in all_grouped[model])
        automatic_fallbacks = sum(record.get("automatic_fallbacks", 0) for record in all_grouped[model])
        decisions = sum(record.get("decision_count", 0) for record in all_grouped[model])
        if model_records:
            lines.append(
                f"| {model} | {len(scores)} | {excluded_count} | {mean:.2f} | {variance:.2f} | {decisions} | {fmean(record['model_calls'] for record in model_records):.1f} | ${fmean(record['total_cost_usd'] for record in model_records):.4f} | {rejected_decisions} | {repair_attempts} | {successful_repairs} | {transport_failures} | {automatic_fallbacks} | {violations} | {raw_mean:.2f} |"
                if mean is not None
                else
                f"| {model} | {len(scores)} | {excluded_count} | — | — | {decisions} | {fmean(record['model_calls'] for record in model_records):.1f} | ${fmean(record['total_cost_usd'] for record in model_records):.4f} | {rejected_decisions} | {repair_attempts} | {successful_repairs} | {transport_failures} | {automatic_fallbacks} | {violations} | {raw_mean:.2f} |"
            )
        else:
            lines.append(f"| {model} | 0 | {excluded_count} | — | — | {decisions} | — | — | {rejected_decisions} | {repair_attempts} | {successful_repairs} | {transport_failures} | {automatic_fallbacks} | {violations} | {raw_mean:.2f} |" if raw_mean is not None else f"| {model} | 0 | {excluded_count} | — | — | {decisions} | — | — | {rejected_decisions} | {repair_attempts} | {successful_repairs} | {transport_failures} | {automatic_fallbacks} | {violations} | — |")
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
    lines.extend(
        [
            "",
            "## Aggregation rule",
            "",
            f"A counted mean and seed standard deviation are reportable only when all expected seeds count (minimum counted-seed fraction {MIN_COUNTED_SEED_FRACTION:.0%}). Excluded seeds remain in the denominator and their raw scores remain diagnostic; no survivor mean is ranked.",
            "",
            "## Provenance and transcript audit",
            "",
        ]
    )
    hash_matches = sum(record.get("engine_config_hash_matches") is True for record in all_values)
    if historical_pilot:
        source_hashes = sorted({str(record.get("engine_config_hash")) for record in all_values})
        lines.append(
            f"- Historical transcript engine/config hash: {', '.join(f'`{value}`' for value in source_hashes)}; current-engine match is intentionally not required."
        )
    else:
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
    transport_excluded_records = [record for record in all_values if record.get("transport_excluded")]
    if transport_excluded_records:
        lines.append(
            f"- Transport exclusion: EXCLUDED {len(transport_excluded_records)}/{len(all_values)} transcripts from counted aggregates; raw scores and failure counts remain visible."
        )
    else:
        lines.append("- Transport exclusion: PASS (no transcripts excluded for provider transport failures).")
    if historical_pilot:
        zero_model_decision_counts: dict[str, int] = defaultdict(int)
        for record in all_values:
            if record.get("successful_model_decisions", 0) == 0:
                zero_model_decision_counts[str(record["model"])] += 1
        if zero_model_decision_counts:
            details = ", ".join(
                f"{model}: {count}/{sum(1 for item in all_values if item.get('model') == model)}"
                for model, count in sorted(zero_model_decision_counts.items())
            )
            lines.append(f"- Zero-successful-model-decision transcripts: {details}.")
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
        "The analyzer reads the archived v0.1 runner transcripts in historical compatibility mode. It applies the v0.1 pain-only counted rule, excludes any transcript with provider transport failures from counted aggregates, and retains raw scores and transport metrics for audit."
        if historical_pilot
        else
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
    historical_pilot = bool(records) and all(record.get("historical_pilot") for record in records)
    transport_excluded_records = [record for record in records if record.get("transport_excluded")]
    json_path.write_text(
        json.dumps(
            {
                "engine_config_hash": engine_config_hash(),
                "prompt_hash": current_prompt_hash(),
                "analysis_mode": "historical_pilot" if historical_pilot else "current",
                "records": records,
                "leaderboard": leaderboard_aggregates(records),
                "valid_record_count": len(records) - len(excluded_records),
                "excluded_invalid_count": len(invalid_records),
                "constraint_violating_count": len(constraint_records),
                "excluded_record_count": len(excluded_records),
                "transport_excluded_count": len(transport_excluded_records),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    title_override = (
        "# Bench-bench v0.2 Paid Smoke Analysis"
        if json_path.name == "current_v02_smoke_analysis.json"
        else None
    )
    markdown_path.write_text(
        leaderboard_markdown(records, title_override=title_override), encoding="utf-8"
    )
