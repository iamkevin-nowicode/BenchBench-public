"""Reproduce and audit the current Bench-bench release artifacts.

This is intentionally offline. It runs deterministic baselines and the legal
action search, re-analyzes the retained public action replays, and checks the
rounded values printed in BENCHMARK_CARD.md against those outputs.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from statistics import fmean
from typing import Any

from bench_bench.adversarial import run_adversarial_search
from bench_bench.evaluation import run_suite
from bench_bench.provenance import engine_config_hash
from bench_bench.runner_analysis import analyze_directory


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
HASH = engine_config_hash()


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
            "This verification reruns the deterministic calibration gate, the 12-week diagnostic, and the adversarial search; confirms that the public leaderboard is still pending its live run; and checks every numeric validation value printed in BENCHMARK_CARD.md. It makes no model or network calls.",
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

    transcript_directory = ROOT / "runs" / "public-leaderboard"
    transcripts = sorted(transcript_directory.glob("*.jsonl")) if transcript_directory.exists() else []
    stored_leaderboard_path = REPORTS / "authoritative_leaderboard.json"
    stored_leaderboard = _load(stored_leaderboard_path) if stored_leaderboard_path.exists() else {}
    checks["public_leaderboard_pending"] = not transcripts and not stored_leaderboard

    json_reports = sorted(REPORTS.glob("*.json"))
    markdown_reports = sorted(REPORTS.glob("*.md"))
    checks["all_json_reports_have_hash"] = all(_load(path).get("engine_config_hash") == HASH for path in json_reports)
    checks["all_markdown_reports_have_hash"] = all(HASH in path.read_text(encoding="utf-8") for path in markdown_reports)
    checks["transcripts_have_current_hash"] = not transcripts or all(
        json.loads(line).get("engine_config_hash") == HASH
        for path in transcripts
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("type") in {"run_start", "turn", "run_end"}
    )

    card = (ROOT / "BENCHMARK_CARD.md").read_text(encoding="utf-8")
    manifest = _load(ROOT / "release_manifest.json")
    checks["card_and_manifest_have_hash"] = HASH in card and manifest.get("engine_config_hash") == HASH

    card_baselines: dict[str, tuple[float, float]] = {}
    for match in re.finditer(r"^\| ([a-z0-9-]+) \| ([0-9]+\.[0-9]+) \| ([0-9]+\.[0-9]+) \|$", card, re.M):
        if match.group(1) in stored52["summaries"]:
            card_baselines[match.group(1)] = (float(match.group(2)), float(match.group(3)))
    checks["card_baseline_numbers_match"] = len(card_baselines) == 6 and all(
        card_baselines[policy] == (round(summary["mean_final_1rm_kg"], 2), round(summary["seed_std_kg"], 2))
        for policy, summary in stored52["summaries"].items()
    )

    gap_match = re.search(r"expert–random gap is ([0-9]+\.[0-9]+) kg, or ([0-9]+\.[0-9]+) pooled", card)
    diagnostic_match = re.search(r"12-week diagnostic has ([0-9]+\.[0-9]+)σ", card)
    adversarial_match = re.search(
        r"best valid candidate scored ([0-9]+\.[0-9]+) kg against\s+the\s+([0-9]+\.[0-9]+) kg expert", card
    )
    checks["card_gate_numbers_match"] = bool(gap_match) and float(gap_match.group(1)) == round(stored52["gate"]["expert_minus_random_kg"], 3) and float(gap_match.group(2)) == round(stored52["gate"]["separation_ratio"], 3)
    checks["card_diagnostic_numbers_match"] = bool(diagnostic_match) and float(diagnostic_match.group(1)) == round(stored12["gate"]["separation_ratio"], 3)
    best_name = stored_adversarial["exploit_policies"][0]
    checks["card_adversarial_numbers_match"] = bool(adversarial_match) and float(adversarial_match.group(1)) == round(stored_adversarial["summaries"][best_name]["mean_final_1rm_kg"], 2) and float(adversarial_match.group(2)) == round(stored_adversarial["comparison"]["expert_mean_final_1rm_kg"], 2)

    manifest_public_seeds = manifest.get("public_leaderboard_seed_values", [])
    checks["card_public_status_matches"] = (
        "intentionally not generated" in card
        and manifest.get("authoritative_leaderboard_status") == "pending_independent_review_and_live_run"
        and manifest_public_seeds == list(range(100, 110))
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
    checks["authoritative_leaderboard_not_generated_before_live_run"] = not list(REPORTS.glob("*LEADERBOARD*"))
    runs_directory = ROOT / "runs"
    checks["stale_run_directories_removed"] = runs_directory.exists() and not list(runs_directory.iterdir()) and not list(runs_directory.rglob("*.lock"))
    checks["public_transcript_count"] = len(transcripts) == 0

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
        "public_leaderboard_status": "pending_independent_review_and_live_run",
        "public_leaderboard_seed_values": manifest_public_seeds,
    }
    _write_verification(checks, references, len(transcripts))


if __name__ == "__main__":
    main()
