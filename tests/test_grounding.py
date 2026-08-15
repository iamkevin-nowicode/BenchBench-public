from __future__ import annotations

from statistics import fmean

import pytest

from bench_bench.config import SimConfig
from bench_bench.engine import BenchEnvironment
from bench_bench.phase3 import measure_policy, measure_scripted_policies, run_policy_ladder
from bench_bench.policies import make_policy
from bench_bench.schemas import WeekAction


def _expert_score_with_mid_episode_layoff(seed: int, layoff_weeks: int) -> float:
    """Run the expert, removing training from weeks 24..24+n-1 only."""
    config = SimConfig(weeks=52)
    env = BenchEnvironment(seed, config)
    policy = make_policy("scripted-expert", seed)
    while not env.done:
        week = env.observation.episode_week
        proposed = policy.action(env.observation)
        if 24 <= week < 24 + layoff_weeks:
            # Preserve the expert's household, sleep, and money decisions. The
            # fixture therefore measures loss of training exposure rather than
            # the consequences of changing the life plan at the same time.
            action = WeekAction(
                sessions=[],
                life=proposed.life,
                rules=proposed.rules,
                coach_note=proposed.coach_note,
            )
        else:
            action = proposed
        env.submit_week(action, reactive_responder=policy.reactive)
    return env.final_result().final_1rm_kg


def test_detraining_regressions_stay_inside_literature_upper_bounds() -> None:
    seeds = range(320, 328)
    uninterrupted = {
        seed: _expert_score_with_mid_episode_layoff(seed, 0)
        for seed in seeds
    }
    literature_upper_bounds = {3: 3.3, 10: 6.0, 12: 15.0}
    observed: dict[int, float] = {}
    for layoff_weeks, upper_bound in literature_upper_bounds.items():
        losses = [
            (uninterrupted[seed] - _expert_score_with_mid_episode_layoff(seed, layoff_weeks))
            / uninterrupted[seed]
            * 100.0
            for seed in seeds
        ]
        observed[layoff_weeks] = fmean(losses)
        assert 0.0 <= observed[layoff_weeks] <= upper_bound
    # Keep the observed guard visible in a failure rather than silently
    # replacing it with a tuned constant.
    assert observed[3] == pytest.approx(1.04, abs=0.35)
    assert observed[10] == pytest.approx(3.90, abs=0.75)
    assert observed[12] == pytest.approx(4.94, abs=0.75)


def test_expert_annual_gain_stays_inside_novice_grounding_range() -> None:
    config = SimConfig(weeks=52)
    scores = []
    for seed in range(320, 340):
        env = BenchEnvironment(seed, config)
        policy = make_policy("scripted-expert", seed)
        while not env.done:
            env.submit_week(policy.action(env.observation), reactive_responder=policy.reactive)
        scores.append(env.final_result().final_1rm_kg)
    annual_gain_pct = (fmean(scores) - config.starting_estimated_1rm_kg) / config.starting_estimated_1rm_kg * 100.0
    assert 10.0 <= annual_gain_pct <= 30.0


def test_phase3_feasibility_gate_discards_safe_fallback_scores() -> None:
    class InvalidPolicy:
        def action(self, observation):
            return {"coach_note": "x" * 601}

        def reactive(self, observation):
            return {"response": "protect_recovery"}

    measurement = measure_policy(
        "invalid-template",
        range(2),
        lambda seed: InvalidPolicy(),
        SimConfig(weeks=4),
    )
    assert measurement.raw_mean_kg is not None
    assert measurement.counted_mean_kg is None
    assert measurement.feasible_for_phase3 is False
    assert measurement.ineligible_episodes == 2
    assert measurement.validation_fallback_violating_episodes == 2
    assert all(
        episode.weekly_validation_fallback_rate > 0.05
        for episode in measurement.episodes
    )


def test_phase3_normalization_is_a_paired_seed_delta() -> None:
    measurements = measure_scripted_policies(
        ["scripted-expert", "recovery-aware"],
        range(320, 324),
        SimConfig(weeks=52),
    )
    recovery = measurements["recovery-aware"]
    assert recovery.feasible_for_phase3 is True
    assert recovery.normalized_gate_mean_kg is not None
    assert recovery.normalized_gate_mean_kg < 0.0
    assert recovery.normalized_gate_seed_sd_kg is not None
    assert recovery.normalized_gate_seed_sd_kg < recovery.raw_seed_sd_kg


def test_policy_ladder_reports_training_effects_and_life_dominance() -> None:
    report = run_policy_ladder(range(320, 340), SimConfig(weeks=52))
    assert report["gate"]["all_training_rungs_eligible"] is True
    assert report["gate"]["load_calibration_pass"] is True
    assert report["gate"]["session_frequency_pass"] is True
    assert report["gate"]["life_field_pricing_pass"] is True
    assert report["partner_giveback_optimum"]["seed_count"] == 20
    assert "optimum_varies_across_seeds" in report["partner_giveback_optimum"]
    assert report["sleep_checkbox"]["strong_not_unanimous_first_12"] is True
