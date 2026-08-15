"""Reproduce and audit the current Bench-bench release artifacts.

This is intentionally offline. It runs deterministic baselines and the legal
action search, re-analyzes the retained public action replays, and checks the
rounded values printed in BENCHMARK_CARD.md against those outputs.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import subprocess
from pathlib import Path
from statistics import fmean
from typing import Any

from bench_bench.adversarial import run_adversarial_search
from bench_bench.evaluation import run_suite
from bench_bench.provenance import current_prompt_hash, engine_config_hash
from bench_bench.runner_analysis import analyze_directory


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
HASH = engine_config_hash()
PROMPT_HASH = current_prompt_hash()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _same(left: Any, right: Any) -> bool:
    """Compare JSON-shaped values while tolerating harmless float noise."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    return left == right


def _normalize_transcript_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ignore the absolute-vs-relative path used by different invocations."""
    normalized = []
    for record in records:
        copy = dict(record)
        if "path" in copy:
            copy["path"] = Path(str(copy["path"])).name
        normalized.append(copy)
    return normalized


def _write_verification(checks: dict[str, bool], references: dict[str, Any], transcript_count: int) -> None:
    all_checks_pass = all(checks.values())
    payload = {
        "all_checks_pass": all_checks_pass,
        "benchmark": "Bench-bench",
        "card_reference_values": references,
        "checks": checks,
        "engine_config_hash": HASH,
        "prompt_hash": PROMPT_HASH,
        "public_transcript_count": transcript_count,
    }
    (REPORTS / "current_verification.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    status = "PASS" if all_checks_pass else "FAIL"
    lines = [
        "# Bench-bench Current Artifact Verification",
        "",
        f"- Engine/config hash: `{HASH}`",
        f"- Prompt hash: `{PROMPT_HASH}`",
        f"- Overall: **{status}**",
        "",
        "| Check | Result |",
        "|---|:---:|",
    ]
    for name, value in sorted(checks.items()):
        lines.append(f"| {name} | {'PASS' if value else 'FAIL'} |")
    lines.extend(
        [
            "",
            "This verification reruns the deterministic calibration gate, the 12-week diagnostic, and the adversarial search; validates either the pre-run pending state or the complete public artifact state; and checks every numeric validation value printed in BENCHMARK_CARD.md. It makes no model or network calls.",
            "",
        ]
    )
    (REPORTS / "CURRENT_VERIFICATION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not all_checks_pass:
        raise SystemExit(1)


def main() -> None:
    checks: dict[str, bool] = {}
    stored52 = _load(REPORTS / "current_baseline_gate.json")
    source52 = run_suite(range(20), weeks=52, ablations=False)
    checks["baseline_gate_reproduces"] = all(
        _same(stored52[key], source52[key]) for key in ("config", "seeds", "summaries", "gate")
    )

    stored12 = _load(REPORTS / "current_12_week_diagnostic.json")
    source12 = run_suite(range(20), weeks=12, ablations=False)
    checks["twelve_week_diagnostic_reproduces"] = all(
        _same(stored12[key], source12[key]) for key in ("config", "seeds", "summaries", "gate")
    )

    stored_adversarial = _load(REPORTS / "current_adversarial_search.json")
    source_adversarial = run_adversarial_search(range(20), weeks=52)
    checks["adversarial_search_reproduces"] = all(
        _same(stored_adversarial[key], source_adversarial[key])
        for key in ("config", "seeds", "exploit_policies", "summaries", "episodes", "candidates", "search")
    ) and all(
        _same(stored_adversarial["comparison"][key], source_adversarial["comparison"][key])
        for key in (
            "expert_mean_final_1rm_kg",
            "release_blocked_candidates",
            "human_review_candidates",
            "release_abuse_thresholds",
            "human_review_margin_kg",
            "candidate_assessments",
        )
    )

    manifest = _load(ROOT / "release_manifest.json")
    public_directory_value = manifest.get("public_transcript_directory", "runs/v0.2-public-leaderboard")
    transcript_directory = ROOT / public_directory_value
    transcripts = sorted(
        path
        for path in transcript_directory.rglob("*.jsonl")
        if not path.name.endswith(".current-engine.jsonl")
    ) if transcript_directory.exists() else []
    stored_leaderboard_path = ROOT / manifest.get(
        "authoritative_leaderboard_json", "reports/PUBLIC_LEADERBOARD.json"
    )
    stored_leaderboard = _load(stored_leaderboard_path) if stored_leaderboard_path.exists() else {}
    public_status = manifest.get("authoritative_leaderboard_status")
    expected_public_count = int(
        manifest.get("public_run_preregistration", {}).get(
            "episode_count",
            len(manifest.get("public_models", [])) * len(manifest.get("public_leaderboard_seed_values", [])),
        )
    )
    pending_public = not transcripts and not stored_leaderboard
    complete_public = (
        public_status == "public_run_complete_card_pending"
        and len(transcripts) == expected_public_count
        and bool(stored_leaderboard)
    )
    checks["public_leaderboard_pending_or_complete"] = pending_public or complete_public

    json_reports = sorted(REPORTS.glob("*.json"))
    markdown_reports = sorted(REPORTS.glob("*.md"))
    # Historical/retracted pilot reports intentionally retain the hash of the
    # engine that produced them.  Current-source verification applies only to
    # generated current reports and the active card.
    historical_report_names = {
        "PILOT_V0.1_LEADERBOARD.json",
        "final_public_leaderboard.json",
        "FINAL_PUBLIC_LEADERBOARD.md",
        "BENCH_BENCH_RESULTS_REPORT.md",
        "PILOT_V0.1_LEADERBOARD.md",
    }
    current_json_reports = [path for path in json_reports if path.name not in historical_report_names]
    current_markdown_reports = [path for path in markdown_reports if path.name.startswith("CURRENT_")]
    checks["all_json_reports_have_hash"] = all(
        _load(path).get("engine_config_hash") == HASH and _load(path).get("prompt_hash") == PROMPT_HASH
        for path in current_json_reports
    )
    checks["all_markdown_reports_have_hash"] = all(
        HASH in path.read_text(encoding="utf-8") and PROMPT_HASH in path.read_text(encoding="utf-8")
        for path in current_markdown_reports
    )
    checks["transcripts_have_current_hash"] = not transcripts or all(
        json.loads(line).get("engine_config_hash") == HASH
        for path in transcripts
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("type") in {"run_start", "turn", "run_end"}
    )
    checks["transcripts_have_current_prompt_hash"] = not transcripts or all(
        json.loads(line).get("prompt_hash") == PROMPT_HASH
        for path in transcripts
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("type") in {"run_start", "turn", "run_end"}
    )

    card = (ROOT / "BENCHMARK_CARD.md").read_text(encoding="utf-8")
    checks["card_and_manifest_have_hash"] = (
        HASH in card
        and PROMPT_HASH in card
        and manifest.get("engine_config_hash") == HASH
        and manifest.get("prompt_hash") == PROMPT_HASH
    )

    card_baselines: dict[str, tuple[float, float]] = {}
    card_counted: dict[str, float | None] = {}
    for match in re.finditer(
        r"^\| ([a-z0-9-]+) \| ([0-9]+\.[0-9]+) \| ([0-9]+\.[0-9]+|—) \| ([0-9]+\.[0-9]+) \| ([0-9]+\.[0-9]+|—) \|",
        card,
        re.M,
    ):
        if match.group(1) in stored52["summaries"]:
            card_baselines[match.group(1)] = (float(match.group(2)), float(match.group(4)))
            card_counted[match.group(1)] = None if match.group(3) == "—" else float(match.group(3))
    checks["card_baseline_numbers_match"] = len(card_baselines) == 6 and all(
        card_baselines[policy] == (round(summary["mean_final_1rm_kg"], 2), round(summary["seed_std_kg"], 2))
        for policy, summary in stored52["summaries"].items()
    )
    checks["card_counted_baseline_numbers_match"] = len(card_counted) == 6 and all(
        card_counted[policy] == (
            round(summary["counted_mean_final_1rm_kg"], 2)
            if summary.get("counted_mean_final_1rm_kg") is not None
            else None
        )
        for policy, summary in stored52["summaries"].items()
    )

    gap_match = re.search(r"expert–random gap is ([0-9]+\.[0-9]+) kg, or ([0-9]+\.[0-9]+) pooled", card)
    diagnostic_match = re.search(r"12-week diagnostic has ([0-9]+\.[0-9]+)σ", card)
    adversarial_match = re.search(
        r"best valid candidate\s+scored ([0-9]+\.[0-9]+) kg\s+against\s+the\s+([0-9]+\.[0-9]+) kg expert", card
    )
    checks["card_gate_numbers_match"] = bool(gap_match) and float(gap_match.group(1)) == round(stored52["gate"]["expert_minus_random_kg"], 3) and float(gap_match.group(2)) == round(stored52["gate"]["separation_ratio"], 3)
    checks["card_diagnostic_numbers_match"] = bool(diagnostic_match) and float(diagnostic_match.group(1)) == round(stored12["gate"]["separation_ratio"], 3)
    best_name = stored_adversarial["exploit_policies"][0]
    checks["card_adversarial_numbers_match"] = bool(adversarial_match) and float(adversarial_match.group(1)) == round(stored_adversarial["summaries"][best_name]["mean_final_1rm_kg"], 2) and float(adversarial_match.group(2)) == round(stored_adversarial["comparison"]["expert_mean_final_1rm_kg"], 2)

    manifest_public_seeds = manifest.get("public_leaderboard_seed_values", [])
    checks["card_public_status_matches"] = (
        "intentionally not generated" in card
        and manifest.get("authoritative_leaderboard_status")
        in {
            "pending_independent_review_and_live_run",
            "pending_prompt_freeze_rehearsal_and_live_run",
            "pending_full_public_run",
            "public_run_complete_card_pending",
        }
        and manifest_public_seeds == list(range(400, 410))
    )

    seed_policy_text = (ROOT / "seed_policy.json").read_text(encoding="utf-8")
    seed_policy = json.loads(seed_policy_text)
    private_scan_paths = [ROOT / "seed_policy.json", ROOT / "release_manifest.json", ROOT / "BENCHMARK_CARD.md"]
    for directory in ("bench_bench", "tests", "reports"):
        private_scan_paths.extend((ROOT / directory).glob("**/*"))
    private_scan_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in private_scan_paths
        if path.is_file() and path.suffix not in {".pyc", ".lock", ".jsonl"}
    )
    checks["private_seed_values_not_materialized"] = isinstance(seed_policy.get("private_seed_values"), str) and not re.search(r'private_seed_values"\s*:\s*\[', private_scan_text)
    revisions = subprocess.check_output(["git", "rev-list", "--all"], cwd=ROOT, text=True).split()
    history_has_private_seed_array = False
    if revisions:
        history_has_private_seed_array = subprocess.run(
            [
                "git",
                "grep",
                "-n",
                "-F",
                '"private_seed_values": [',
                *revisions,
                "--",
                ":!scripts/verify_artifacts.py",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    checks["private_seed_git_history_clear"] = bool(revisions) and not history_has_private_seed_array
    leaderboard_json_exists = (ROOT / manifest.get("authoritative_leaderboard_json", "reports/PUBLIC_LEADERBOARD.json")).exists()
    leaderboard_markdown_exists = (ROOT / manifest.get("authoritative_leaderboard_markdown", "reports/PUBLIC_LEADERBOARD.md")).exists()
    checks["authoritative_leaderboard_state_valid"] = (
        (pending_public and not leaderboard_json_exists and not leaderboard_markdown_exists)
        or (complete_public and leaderboard_json_exists and leaderboard_markdown_exists)
    )
    runs_directory = ROOT / "runs"
    allowed_run_roots = {"archive", ".DS_Store"}
    if public_status == "public_run_complete_card_pending":
        allowed_run_roots.add(transcript_directory.name)
    unexpected_run_roots = []
    if runs_directory.exists():
        unexpected_run_roots = [
            path.name
            for path in runs_directory.iterdir()
            if path.name not in allowed_run_roots
        ]
    disposable_run_roots = [runs_directory / name for name in unexpected_run_roots]
    lock_files_outside_archive = [
        lock
        for root in disposable_run_roots
        if root.exists()
        for lock in root.rglob("*.lock")
    ]
    checks["stale_run_directories_removed"] = not unexpected_run_roots and not lock_files_outside_archive
    checks["public_transcript_count"] = (
        len(transcripts) == 0
        if public_status != "public_run_complete_card_pending"
        else len(transcripts) == expected_public_count
        and manifest.get("public_transcript_count") == expected_public_count
    )

    pilot_manifest_path = ROOT / "artifacts" / "v0.1-pilot-manifest.json"
    pilot_archive_path = ROOT / "artifacts" / "v0.1-pilot-transcripts.tar.gz"
    pilot_manifest = _load(pilot_manifest_path) if pilot_manifest_path.exists() else {}
    archive_digest = hashlib.sha256(pilot_archive_path.read_bytes()).hexdigest() if pilot_archive_path.exists() else ""
    transcript_entries = pilot_manifest.get("transcripts", [])
    checks["pilot_archive_manifest_complete"] = bool(
        pilot_archive_path.exists()
        and pilot_manifest.get("archive_sha256") == f"sha256:{archive_digest}"
        and pilot_manifest.get("file_count") == 50
        and len(transcript_entries) == 50
        and all(
            {"relative_path", "sha256", "model", "seed", "weeks", "engine_config_hash", "prompt_hash"}
            <= set(entry)
            for entry in transcript_entries
        )
    )

    references = {
        "baseline_mean_final_1rm_kg": {policy: value["mean_final_1rm_kg"] for policy, value in stored52["summaries"].items()},
        "baseline_seed_std_kg": {policy: value["seed_std_kg"] for policy, value in stored52["summaries"].items()},
        "gate": stored52["gate"],
        "twelve_week_diagnostic": stored12["gate"],
        "adversarial": {
            "expert_mean_final_1rm_kg": stored_adversarial["comparison"]["expert_mean_final_1rm_kg"],
            "best_candidate": best_name,
            "best_candidate_mean_final_1rm_kg": stored_adversarial["summaries"][best_name]["mean_final_1rm_kg"],
            "candidates_beating_expert": stored_adversarial["comparison"]["candidates_beating_expert"],
            "human_review_candidates": stored_adversarial["comparison"]["human_review_candidates"],
            "release_blocked_candidates": stored_adversarial["comparison"]["release_blocked_candidates"],
        },
        "public_leaderboard_status": public_status,
        "public_leaderboard_seed_values": manifest_public_seeds,
    }
    _write_verification(checks, references, len(transcripts))


if __name__ == "__main__":
    main()
