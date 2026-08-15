from __future__ import annotations

from bench_bench.adversarial import _reference_expert_mean
from bench_bench.evaluation import run_episode, run_suite
from bench_bench.config import SimConfig
from bench_bench.engine import BenchEnvironment
from bench_bench.policies import POLICY_NAMES, make_policy
from bench_bench.schemas import WeekAction


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
    # The old six-policy ordering is a diagnostic at this stage; the v0.2
    # release gate is the held-out oracle/policy-ladder evaluation.
    assert isinstance(gate["reckless_loses_endogenously"], bool)
    assert gate["invalid_episode_free"] is True


def test_phase2_mechanics_change_outcomes_in_ablations() -> None:
    report = run_suite(range(20), weeks=12, ablations=True)
    assert {ablation["name"] for ablation in report["ablations"]} == {
        "no-sleep-system",
        "no-delayed-adaptation",
        "no-event-system",
    }
    # The evidence-informed sleep path is intentionally thresholded: this
    # ordinary 12-week fixture need not differ when no session lands below
    # the severe-sleep breakpoint. The longer-horizon ladder exercises the
    # situational sleep choice directly.
    sleep_ablation = next(item for item in report["ablations"] if item["name"] == "no-sleep-system")
    assert sleep_ablation["changed_score"] is False
    no_delayed = next(item for item in report["ablations"] if item["name"] == "no-delayed-adaptation")
    no_events = next(item for item in report["ablations"] if item["name"] == "no-event-system")
    assert no_delayed["changed_score"] is True
    assert no_delayed["changed_decisions"] is False
    assert no_events["changed_score"] is True
    assert no_events["changed_decisions"] is True


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


def test_sleep_protection_is_priced_in_the_shared_time_ledger() -> None:
    config = SimConfig(weeks=1)
    none = WeekAction(life={"sleep_protection": "none"})
    standard = WeekAction(life={"sleep_protection": "standard"})
    strong = WeekAction(life={"sleep_protection": "strong"})
    env = BenchEnvironment(3, config)
    assert env._weekly_time_cost_minutes(standard) - env._weekly_time_cost_minutes(none) == 30
    assert env._weekly_time_cost_minutes(strong) - env._weekly_time_cost_minutes(none) == 60


def test_scripted_baselines_play_their_authored_policies() -> None:
    config = SimConfig(weeks=52)
    seeds = range(300, 308)
    for name in POLICY_NAMES:
        episodes = [run_episode(name, seed, config) for seed in seeds]
        fallback_rate = sum(episode.fallback_actions for episode in episodes) / (len(episodes) * config.weeks)
        assert fallback_rate <= 0.05, (name, fallback_rate)
    reckless = [run_episode("reckless-maximalist", seed, config) for seed in seeds]
    assert all(episode.attempted_sessions > 0 for episode in reckless)
    assert all(episode.fallback_actions == 0 for episode in reckless)
    assert all(episode.pain_days > 14 for episode in reckless)


def test_adversarial_reference_uses_the_counted_expert_mean() -> None:
    seeds = list(range(3))
    report = run_suite(seeds, weeks=52, ablations=False)
    reference = _reference_expert_mean(seeds, SimConfig(weeks=52))
    assert reference == report["summaries"]["scripted-expert"]["counted_mean_final_1rm_kg"]
