from __future__ import annotations

from bench_bench.adversarial import _reference_expert_mean
from bench_bench.evaluation import run_suite
from bench_bench.config import SimConfig
from bench_bench.engine import BenchEnvironment
from bench_bench.policies import POLICY_NAMES, make_policy


def test_all_phase2_policies_are_constructible() -> None:
    assert len(POLICY_NAMES) == 6
    for name in POLICY_NAMES:
        assert make_policy(name, 3).name == name


def test_phase2_short_horizon_is_diagnostic_only() -> None:
    report = run_suite(range(20), weeks=12, ablations=False)
    gate = report["gate"]
    assert gate["gate_enforced"] is False
    assert gate["gate_pass"] is None
    assert gate["separation_ratio"] >= 3.0
    # The 12-week run is intentionally diagnostic; the current calibration
    # does not claim stable aggregate ordering at this horizon.
    assert gate["ordering_pass"] is False
    assert gate["stable_ordering_pass"] is False
    assert gate["reckless_loses_endogenously"] is True
    assert gate["invalid_episode_free"] is True


def test_phase2_mechanics_change_outcomes_in_ablations() -> None:
    report = run_suite(range(20), weeks=12, ablations=True)
    assert {ablation["name"] for ablation in report["ablations"]} == {
        "no-sleep-system",
        "no-delayed-adaptation",
        "no-event-system",
    }
    assert all(ablation["changed_score"] for ablation in report["ablations"])
    assert all(ablation["changed_decisions"] for ablation in report["ablations"])


def test_scripted_expert_never_submits_an_infeasible_900_minute_plan() -> None:
    config = SimConfig(weeks=52)
    for seed in range(20):
        env = BenchEnvironment(seed, config)
        policy = make_policy("scripted-expert", seed)
        while not env.done:
            action = policy.action(env.observation)
            validation = env.validate_action(action)
            assert validation.errors == ()
            assert env._weekly_time_cost_minutes(action) <= config.weekly_time_budget_minutes
            env.submit_week(action, reactive_responder=policy.reactive)
        assert all(
            not record["validation"]["fallback_used"]
            for record in env.log_records
            if record.get("type") == "week"
        )


def test_adversarial_reference_uses_the_counted_expert_mean() -> None:
    seeds = list(range(3))
    report = run_suite(seeds, weeks=52, ablations=False)
    reference = _reference_expert_mean(seeds, SimConfig(weeks=52))
    assert reference == report["summaries"]["scripted-expert"]["counted_mean_final_1rm_kg"]
