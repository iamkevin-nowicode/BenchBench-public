from __future__ import annotations

import json
import re

from bench_bench import BenchEnvironment, SimConfig
from bench_bench.evaluation import run_exploit_suite, run_suite
from bench_bench.schemas import WeekAction
from bench_bench.viewer import render_replay


def test_full_year_baseline_gate_rechecks_the_same_contract() -> None:
    report = run_suite(range(20), weeks=52, ablations=False)
    assert report["gate"]["gate_pass"] is True
    assert report["gate"]["separation_ratio"] >= 3.0


def test_full_year_adversarial_gate_requires_implausibility() -> None:
    report = run_exploit_suite(range(20), weeks=52)
    assert report["comparison"]["candidates_beating_expert"] == []
    assert report["comparison"]["human_review_candidates"] == []
    assert report["comparison"]["release_blocked_candidates"] == []
    assert report["search"]["invalid_search_candidates"] > 0
    assert all(
        not report["candidates"][name]["release_blocked"]
        for name in report["exploit_policies"]
    )


def test_cap_15_winner_requires_review_and_physical_signature_blocks() -> None:
    report = run_exploit_suite(range(20), weeks=52, weekly_stimulus_cap=1.5)
    best = report["exploit_policies"][0]
    assert report["candidates"][best]["beats_expert"] is True
    assert report["candidates"][best]["requires_human_review"] is True
    assert "expert_margin_at_or_above_5kg" not in report["candidates"][best]["abuse_signatures"]
    assert report["candidates"][best]["abuse_signatures"]
    assert report["candidates"][best]["release_blocked"] is True


def test_replay_viewer_embeds_only_the_public_log(tmp_path) -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1))
    env.submit_week(env.safe_action())
    env.final_result()
    log = tmp_path / "episode.jsonl"
    viewer = tmp_path / "replay.html"
    env.write_jsonl(log)
    render_replay(log, viewer)
    source = viewer.read_text()
    embedded = re.search(r'<script id="episode-data" type="application/json">(.*?)</script>', source, re.S)
    assert embedded is not None
    records = json.loads(embedded.group(1))
    assert any(record.get("type") == "week" for record in records)
    assert "recovery_capacity" not in embedded.group(1)
    assert "true_capacity" not in embedded.group(1)
    assert "sleep_debt" not in embedded.group(1)
    assert "Open all" in source and "Close all" in source


def test_promotion_fork_changes_time_and_money_endogenously() -> None:
    def run(choice: str) -> dict:
        env = BenchEnvironment(3, SimConfig(weeks=24))
        while not env.done:
            env.submit_week(WeekAction(life={"career_choice": choice}))
        return env.private_snapshot()["state"]

    protected = run("protect_time")
    accepted = run("accept_stretch_project")
    assert accepted["cash_cents"] > protected["cash_cents"]
    assert accepted["total_spend_cents"] == protected["total_spend_cents"]
    assert accepted["work_strain"] > protected["work_strain"]
