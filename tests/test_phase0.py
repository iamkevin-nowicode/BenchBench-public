from __future__ import annotations

from statistics import stdev

from bench_bench.cli import build_parser
from bench_bench.runner import retry_metrics_from_attempt_groups
from bench_bench.runner_analysis import analyze_directory, leaderboard_aggregates
from bench_bench.runner import DeterministicPolicyClient, ModelRunner, RunnerConfig


def test_phase0_retry_vocabulary_separates_rejection_repair_transport_and_fallback() -> None:
    metrics = retry_metrics_from_attempt_groups(
        [
            [
                {"attempt": 0, "is_model_call": True, "error": "invalid action"},
                {"attempt": 1, "is_model_call": True, "content": {"action": {}}},
            ],
            [
                {"attempt": 0, "is_model_call": True, "error": "model request failed: HTTP Error 429"},
                {"attempt": 1, "is_model_call": False, "fallback": True},
            ],
        ]
    )
    assert metrics == {
        "decisions": 2,
        "rejected_model_outputs": 1,
        "rejected_output_decisions": 1,
        "repair_attempts": 1,
        "successful_repairs": 1,
        "transport_failures": 1,
        "automatic_fallbacks": 1,
    }


def test_phase0_analyzer_walks_nested_transcript_roots_and_uses_sample_sd(tmp_path) -> None:
    paths = []
    for seed in (3, 4):
        path = tmp_path / "model" / f"seed-{seed}" / f"episode-{seed}.jsonl"
        runner = ModelRunner(DeterministicPolicyClient("recovery-aware", seed), RunnerConfig(weeks=1))
        runner.run_episode(seed, path)
        paths.append(path)

    records = analyze_directory(tmp_path)
    assert [record["path"] for record in records] == [
        "model/seed-3/episode-3.jsonl",
        "model/seed-4/episode-4.jsonl",
    ]
    aggregate = leaderboard_aggregates(records)["scripted-recovery-aware"]
    scores = [record["counted_final_1rm_kg"] for record in records]
    assert aggregate["counted_seed_std_kg"] == round(stdev(scores), 4)


def test_phase0_cli_exposes_named_leaderboard_and_current_engine_verifier() -> None:
    leaderboard = build_parser().parse_args(
        ["build-leaderboard", "--input-dir", "runs", "--json", "out.json", "--markdown", "out.md"]
    )
    verifier = build_parser().parse_args(["verify-transcript", "episode.jsonl"])
    assert leaderboard.command == "build-leaderboard"
    assert verifier.command == "verify-transcript"
