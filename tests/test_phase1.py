from __future__ import annotations

import json
import argparse
from dataclasses import replace

import pytest

from bench_bench import BenchEnvironment, SimConfig
from bench_bench.cli import replay
from bench_bench.provenance import engine_config_hash
from bench_bench.schemas import LifeAllocation, ReactiveAction, SessionPlan, StandingRules, WeekAction


def run_safe(seed: int, weeks: int = 12) -> BenchEnvironment:
    env = BenchEnvironment(seed, SimConfig(weeks=weeks))
    while not env.done:
        env.submit_week(env.safe_action())
    env.final_result()
    return env


def test_same_seed_and_actions_replay_byte_identically() -> None:
    first = run_safe(3)
    second = run_safe(3)
    assert first.jsonl() == second.jsonl()
    assert first.final_result().as_dict() == second.final_result().as_dict()
    assert "sleep_debt" not in first.jsonl()
    assert "sleep debt" not in first.jsonl().lower()
    assert "sleep_debt" not in first.final_result().as_dict()


def test_engine_config_hash_is_embedded_in_engine_transcripts() -> None:
    env = run_safe(3, weeks=1)
    records = [json.loads(line) for line in env.jsonl().splitlines()]
    assert records[0]["engine_config_hash"] == engine_config_hash()
    final_record = next(record for record in records if record.get("type") == "final_result")
    assert final_record["engine_config_hash"] == engine_config_hash()


def test_replay_accepts_legacy_sleep_debt_field(tmp_path) -> None:
    env = run_safe(3)
    records = [json.loads(line) for line in env.jsonl().splitlines()]
    final_record = next(record for record in records if record.get("type") == "final_result")
    final_record["result"]["sleep_debt"] = 1.25
    log = tmp_path / "legacy.jsonl"
    log.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    assert replay(argparse.Namespace(log=log)) == 0


def test_event_calendar_is_independent_of_action_sequence() -> None:
    first = BenchEnvironment(17, SimConfig(weeks=12))
    second = BenchEnvironment(17, SimConfig(weeks=12))
    for week in range(1, 13):
        assert first.calendar.week(week).interrupts == second.calendar.week(week).interrupts
        assert 3 <= len(first.calendar.week(week).open_days) <= 4
        first.submit_week(first.safe_action())
        second.submit_week(WeekAction())


def test_technique_tau_sessions_controls_learning_rate() -> None:
    action = WeekAction(
        sessions=[SessionPlan(day=1, focus="technique", sets=3, reps=5, load_kg=55, duration_min=30)],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    fast = BenchEnvironment(
        3,
        SimConfig(
            weeks=4,
            weekly_time_budget_minutes=1_440,
            technique_tau_sessions=1.0,
            enable_event_system=False,
            enable_injury_system=False,
            enable_household_system=False,
            enable_money_system=False,
        ),
    )
    slow = BenchEnvironment(
        3,
        SimConfig(
            weeks=4,
            weekly_time_budget_minutes=1_440,
            technique_tau_sessions=100.0,
            enable_event_system=False,
            enable_injury_system=False,
            enable_household_system=False,
            enable_money_system=False,
        ),
    )
    while not fast.done:
        fast.submit_week(action)
        slow.submit_week(action)
    assert fast.private_snapshot()["state"]["technique"] > slow.private_snapshot()["state"]["technique"]


def test_capacity_drift_requires_four_consecutive_productive_weeks() -> None:
    config = SimConfig(
        weeks=5,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
        capacity_drift_kg_per_productive_week=0.10,
        productive_streak_weeks_for_capacity_drift=4,
    )
    action = WeekAction(
        sessions=[
            SessionPlan(day=day, focus="fallback", sets=2, reps=5, load_kg=40, duration_min=25)
            for day in (1, 2, 3)
        ],
        life=LifeAllocation(),
    )
    env = BenchEnvironment(3, config)
    base_capacity = []
    while not env.done:
        env.submit_week(action)
        base_capacity.append(env.private_snapshot()["state"]["base_capacity_kg"])
    assert base_capacity[:3] == [84.0, 84.0, 84.0]
    assert base_capacity[3:] == pytest.approx([84.1, 84.2])
    assert env.private_snapshot()["state"]["productive_streak_weeks"] == 5


def test_hidden_standardized_tests_are_averaged_without_state_or_log_leak() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=52))
    while not env.done:
        env.submit_week(env.safe_action())
    result = env.final_result()
    hidden_scores = env.private_snapshot()["hidden_standardized_test_scores"]
    assert len(hidden_scores) == 3
    assert result.final_1rm_kg == round(sum(hidden_scores) / len(hidden_scores), 2)
    assert "standardized_test" not in env.jsonl()
    assert "standardized_test" not in str(env.observation.model_dump())


def test_nutrition_changes_body_mass_pathway() -> None:
    low_support = WeekAction(life=LifeAllocation(meal_prep_hours=0, partner_coverage_hours=8, partner_giveback_hours=8))
    high_support = WeekAction(
        life=LifeAllocation(
            meal_prep_hours=4,
            meal_support_spend_cents=1_200,
            partner_coverage_hours=8,
            partner_giveback_hours=8,
        )
    )
    config = SimConfig(
        weeks=8,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    low = BenchEnvironment(3, config)
    high = BenchEnvironment(3, config)
    while not low.done:
        low.submit_week(low_support)
        high.submit_week(high_support)
    assert high.private_snapshot()["state"]["body_mass_kg"] > low.private_snapshot()["state"]["body_mass_kg"]


def test_gym_commute_costs_more_time_than_home_session() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    gym = BenchEnvironment(3, config)
    home = BenchEnvironment(3, config)
    home._state.home_gym = True
    life = LifeAllocation(partner_coverage_hours=0.2, partner_giveback_hours=0.2)
    gym_action = WeekAction(sessions=[SessionPlan(day=1, location="gym", duration_min=35)], life=life)
    home_action = WeekAction(sessions=[SessionPlan(day=1, location="home", duration_min=35)], life=life)
    gym_outcome = gym.submit_week(gym_action)
    home_outcome = home.submit_week(home_action)
    assert gym_outcome.missed_sessions == 1
    assert home_outcome.completed_sessions == 1


def test_home_rack_caps_near_max_work_without_a_spotter() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    gym = BenchEnvironment(3, config)
    home = BenchEnvironment(3, config)
    home._state.home_gym = True
    life = LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8)
    gym_action = WeekAction(
        sessions=[SessionPlan(day=1, location="gym", focus="heavy", sets=4, reps=3, load_kg=100, duration_min=45, target_rpe=9.5)],
        life=life,
    )
    home_action = gym_action.model_copy(
        update={"sessions": [gym_action.sessions[0].model_copy(update={"location": "home"})]}
    )
    gym.submit_week(gym_action)
    home.submit_week(home_action)
    gym_stimulus = gym.private_snapshot()["state"]["session_history"][0]["stimulus"]
    home_stimulus = home.private_snapshot()["state"]["session_history"][0]["stimulus"]
    assert home_stimulus < gym_stimulus


def test_rep_max_ceiling_reduces_high_rep_prescription_before_stimulus() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    env = BenchEnvironment(3, config)
    action = WeekAction(
        sessions=[SessionPlan(day=1, focus="volume", sets=8, reps=15, load_kg=96.6, duration_min=45, target_rpe=9.5)],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    outcome = env.submit_week(action)
    assert outcome.completed_sessions == 1
    history = env.private_snapshot()["state"]["session_history"][0]
    assert history["prescribed_reps"] == 15
    assert history["reps"] < history["prescribed_reps"]
    assert history["stimulus"] < history["raw_stimulus"] or history["reps"] <= 5


def test_fallback_schema_caps_static_work_and_rejects_over_ceiling_load() -> None:
    with pytest.raises(Exception, match="fallback sessions"):
        SessionPlan(day=1, focus="fallback", sets=4, reps=6, duration_min=25)
    with pytest.raises(Exception, match="fallback sessions"):
        SessionPlan(day=1, focus="fallback", sets=3, reps=7, duration_min=25)
    with pytest.raises(Exception, match="fallback sessions"):
        SessionPlan(day=1, focus="fallback", sets=3, reps=6, duration_min=30)

    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    env = BenchEnvironment(3, config)
    action = WeekAction(
        sessions=[SessionPlan(day=1, focus="fallback", sets=3, reps=6, load_kg=200, duration_min=25, target_rpe=6.0)],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    repair = WeekAction(
        sessions=[SessionPlan(day=1, focus="fallback", sets=3, reps=6, load_kg=65.5, duration_min=25, target_rpe=6.0)],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    validation = env.validate_action(action)
    assert validation.errors
    assert "authored fallback load exceeds the permitted ceiling" in validation.errors[0]
    repaired = env.validate_action(action, repair)
    assert repaired.repair_attempted is True
    assert repaired.fallback_used is False
    outcome = env.submit_week(action, repair_action=repair)
    assert outcome.completed_sessions == 1
    executed = env.private_snapshot()["state"]["session_history"][0]
    assert executed["load_kg"] == 65.5


def test_planned_fallback_sessions_are_counted() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    env = BenchEnvironment(3, config)
    outcome = env.submit_week(
        WeekAction(
            sessions=[SessionPlan(day=1, focus="fallback", sets=2, reps=5, load_kg=50, duration_min=25)],
            life=LifeAllocation(partner_coverage_hours=2, partner_giveback_hours=2),
        )
    )
    env.final_result()
    assert outcome.fallback_sessions == 1
    assert env.final_result().fallback_sessions == 1


def test_session_accounting_separates_transforms_attempts_and_misses() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    transformed = BenchEnvironment(3, config)
    transformed._state.tendon_irritation = 2.0
    transformed_outcome = transformed.submit_week(
        WeekAction(
            sessions=[SessionPlan(day=1, focus="heavy", sets=3, reps=3, load_kg=65, duration_min=35)],
            life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
            rules=StandingRules(on_pain_warning="fallback"),
        )
    )
    assert transformed_outcome.as_dict()["planned_sessions"] == 1
    assert transformed_outcome.as_dict()["transformed_sessions"] == 1
    assert transformed_outcome.as_dict()["attempted_sessions"] == 1
    assert transformed_outcome.completed_sessions == 1
    assert transformed_outcome.missed_sessions == 0
    assert transformed_outcome.fallback_sessions == 1

    missed = BenchEnvironment(3, config)
    missed_outcome = missed.submit_week(
        WeekAction(
            sessions=[SessionPlan(day=1, location="home", focus="fallback", sets=2, reps=5, load_kg=40, duration_min=20)],
            life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
        )
    )
    assert missed_outcome.as_dict()["planned_sessions"] == 1
    assert missed_outcome.as_dict()["transformed_sessions"] == 0
    assert missed_outcome.as_dict()["attempted_sessions"] == 1
    assert missed_outcome.completed_sessions == 0
    assert missed_outcome.missed_sessions == 1
    assert missed_outcome.fallback_sessions == 0
    result = missed.final_result().as_dict()
    assert result["planned_sessions"] == 1
    assert result["attempted_sessions"] == 1
    assert result["completed_sessions"] == 0
    assert result["missed_sessions"] == 1


def test_execution_transformations_are_counted_and_surface_their_reasons() -> None:
    config = SimConfig(weeks=1, enable_event_system=False, enable_money_system=False)

    rep_rate = BenchEnvironment(0, config)
    rep_rate_outcome = rep_rate.submit_week(
        WeekAction(
            sessions=[SessionPlan(day=0, focus="volume", sets=8, reps=15, load_kg=60, duration_min=10)],
        )
    )
    assert rep_rate_outcome.transformed_sessions == 1
    assert "duration/repetition-rate limit reduced prescribed repetitions" in rep_rate_outcome.transformation_reasons

    home_cap = BenchEnvironment(0, config)
    home_cap._state.home_gym = True
    home_outcome = home_cap.submit_week(
        WeekAction(
            sessions=[SessionPlan(day=0, location="home", focus="heavy", sets=1, reps=1, load_kg=100, duration_min=10)],
        )
    )
    assert home_outcome.transformed_sessions == 1
    assert "home no-spotter load cap applied" in home_outcome.transformation_reasons

    load_cap = BenchEnvironment(0, config)
    load_outcome = load_cap.submit_week(
        WeekAction(
            sessions=[SessionPlan(day=0, focus="heavy", sets=1, reps=1, load_kg=250, duration_min=10)],
        )
    )
    assert load_outcome.transformed_sessions == 1
    assert "load-ratio execution cap applied" in load_outcome.transformation_reasons


def test_invalid_reactive_action_fallback_is_counted_in_weekly_outcome() -> None:
    env = BenchEnvironment(2, SimConfig(weeks=1))
    outcome = env.submit_week(
        WeekAction(life=LifeAllocation(meal_prep_hours=0, partner_coverage_hours=0, partner_giveback_hours=0)),
        reactive_responder=lambda _observation: {"extra_spend_cents": "15000"},
    )
    assert outcome.reactive_action_fallbacks == 1
    assert any("reactive action replaced with protect_recovery" in reason for reason in outcome.transformation_reasons)


def test_zero_load_sessions_do_not_earn_stimulus_or_productive_credit() -> None:
    config = SimConfig(
        weeks=4,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    env = BenchEnvironment(3, config)
    starting_technique = env.private_snapshot()["state"]["technique"]
    action = WeekAction(
        sessions=[
            SessionPlan(day=day, focus="volume", sets=3, reps=10, load_kg=0, duration_min=10)
            for day in (1, 3, 5)
        ],
        life=LifeAllocation(meal_prep_hours=0, partner_coverage_hours=8, partner_giveback_hours=8),
    )
    while not env.done:
        env.submit_week(action)
    state = env.private_snapshot()["state"]
    result = env.final_result()
    assert result.planned_sessions == 12
    assert result.attempted_sessions == 12
    assert result.completed_sessions + result.missed_sessions == 12
    assert state["fitness_signal"] == 0.0
    assert state["technique"] == starting_technique
    assert result.productive_weeks == 0
    assert all(row["stimulus"] == 0.0 for row in state["session_history"])


def test_duration_limits_work_for_non_fallback_volume() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )

    def run(duration: int) -> dict[str, float | int]:
        env = BenchEnvironment(3, config)
        env.submit_week(
            WeekAction(
                sessions=[SessionPlan(day=1, focus="volume", sets=8, reps=15, load_kg=60, duration_min=duration)],
                life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
            )
        )
        return env.private_snapshot()["state"]["session_history"][0]

    short = run(10)
    medium = run(45)
    long = run(120)
    assert short["duration_rep_limit"] == 1
    assert medium["duration_rep_limit"] == 5
    assert long["duration_rep_limit"] == 15
    assert short["stimulus"] < medium["stimulus"] < long["stimulus"]


def test_pain_days_count_active_pain_without_sleep_gate() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_sleep_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    env = BenchEnvironment(3, config)
    env._state.tendon_irritation = 3.2
    env.submit_week(WeekAction(life=LifeAllocation(partner_coverage_hours=0, partner_giveback_hours=0)))
    result = env.final_result()
    assert result.pain_days == 7


def test_weekly_stimulus_has_a_diminishing_returns_cap() -> None:
    config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
        weekly_stimulus_cap=0.5,
        weekly_stimulus_diminishing_start=0.0,
    )
    env = BenchEnvironment(3, config)
    action = WeekAction(
        sessions=[
            SessionPlan(day=day, focus="volume", sets=8, reps=15, load_kg=96.6, duration_min=45, target_rpe=9.5)
            for day in (0, 1, 2, 3, 4)
        ],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    env.submit_week(action)
    delivered = sum(row["stimulus"] for row in env.private_snapshot()["state"]["session_history"])
    assert delivered <= config.weekly_stimulus_cap + 0.01


def test_shared_time_ledger_rejects_the_8x4_variant() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1))
    action = WeekAction(
        sessions=[
            SessionPlan(day=day, location="gym", focus="volume", sets=8, reps=4, load_kg=80, duration_min=75)
            for day in (0, 1, 2, 3, 4)
        ],
        life=LifeAllocation(
            meal_prep_hours=2,
            partner_coverage_hours=8,
            partner_giveback_hours=8,
            sleep_protection="strong",
        ),
    )
    validation = env.validate_action(action)
    assert validation.fallback_used is True
    assert "shared time/resource ledger" in validation.errors[0]
    assert "1555" in validation.errors[0]


def test_shared_ledger_charges_delegation_and_reactive_childcare() -> None:
    config = SimConfig(weeks=1)
    delegated = BenchEnvironment(3, config)
    delegated.submit_week(
        WeekAction(
            life=LifeAllocation(
                meal_prep_hours=0,
                chore_delegation_hours=2,
                chore_delegation_spend_cents=0,
                partner_coverage_hours=0,
                partner_giveback_hours=0,
            )
        )
    )
    assert delegated.final_result().total_spend_cents >= 2 * config.delegated_chore_cost_per_hour_cents

    reactive = BenchEnvironment(2, config)
    reactive.submit_week(
        WeekAction(life=LifeAllocation(meal_prep_hours=0, partner_coverage_hours=0, partner_giveback_hours=0)),
        reactive_responder=lambda _observation: ReactiveAction(extra_childcare_hours=1, extra_spend_cents=0),
    )
    assert reactive.final_result().total_spend_cents >= config.reactive_childcare_cost_per_hour_cents


def test_coverage_and_giveback_cannot_both_be_maximized() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1))
    validation = env.validate_action(
        WeekAction(
            life=LifeAllocation(
                meal_prep_hours=0,
                partner_coverage_hours=16,
                partner_giveback_hours=16,
            )
        )
    )
    assert validation.fallback_used is True
    assert "shared time/resource ledger" in validation.errors[0]


def test_reciprocity_debt_accumulates_without_giveback() -> None:
    config = SimConfig(
        weeks=4,
        enable_event_system=False,
        enable_injury_system=False,
        enable_money_system=False,
    )
    imbalanced = BenchEnvironment(3, config)
    balanced = BenchEnvironment(3, config)
    imbalanced_action = WeekAction(life=LifeAllocation(partner_coverage_hours=6, partner_giveback_hours=0))
    balanced_action = WeekAction(life=LifeAllocation(partner_coverage_hours=6, partner_giveback_hours=6))
    while not imbalanced.done:
        imbalanced.submit_week(imbalanced_action)
        balanced.submit_week(balanced_action)
    imbalanced_state = imbalanced.private_snapshot()["state"]
    balanced_state = balanced.private_snapshot()["state"]
    assert imbalanced_state["reciprocity_debt"] > balanced_state["reciprocity_debt"]
    assert imbalanced_state["household_strain"] > balanced_state["household_strain"]


def test_hidden_variation_does_not_cross_observation_boundary() -> None:
    env = BenchEnvironment(9, SimConfig.twelve_week())
    observation_text = json.dumps(env.observation.model_dump(mode="json"), sort_keys=True)
    for hidden_key in ("recovery_capacity", "volume_tolerance", "injury_joint", "motivation_baseline"):
        assert hidden_key not in observation_text
    assert "true_capacity" not in observation_text
    assert env.private_snapshot()["variation"]["injury_joint"] not in observation_text

    env._state.sleep_hours_history = [5.4] * 7
    env._state.sleep_debt = 4.0
    stressed_observation = json.dumps(env._render_observation().model_dump(mode="json"), sort_keys=True)
    assert "sleep_debt" not in stressed_observation
    assert "sleep debt" not in stressed_observation.lower()
    assert "recent sleep has been uneven" in stressed_observation


def test_budget_and_session_accounting_are_explicit() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1))
    action = {
        "sessions": [
            {
                "day": 1,
                "location": "gym",
                "focus": "volume",
                "sets": 3,
                "reps": 5,
                "load_kg": 60,
                "duration_min": 45,
            }
        ],
        "life": {
            "meal_prep_hours": 4,
            "meal_support_spend_cents": 1_200,
            "partner_coverage_hours": 2,
            "partner_giveback_hours": 2,
        },
    }
    env.submit_week(action)
    result = env.final_result()
    assert result.completed_sessions == 1
    assert result.total_spend_cents == 1_200
    assert env.observation.budget_available_cents == 23_800
    assert result.invalid_reason is None


def test_session_failure_reasons_are_opt_in_and_score_neutral() -> None:
    action = WeekAction(
        sessions=[SessionPlan(day=1, location="home", focus="fallback", sets=2, reps=5, load_kg=40, duration_min=20)],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    opaque = BenchEnvironment(3, SimConfig(weeks=1, weekly_time_budget_minutes=1_440, expose_session_failure_reasons=False))
    exposed = BenchEnvironment(3, SimConfig(weeks=1, weekly_time_budget_minutes=1_440, expose_session_failure_reasons=True))
    opaque_outcome = opaque.submit_week(action)
    exposed_outcome = exposed.submit_week(action)
    assert "session_failure_reasons" not in opaque_outcome.as_dict()
    assert exposed_outcome.as_dict()["session_failure_reasons"] == ({"day": 1, "reason": "equipment"},)
    assert opaque.final_result().as_dict() == exposed.final_result().as_dict()


def test_exposed_session_failure_reasons_cover_time_adherence_and_cancelled() -> None:
    time_config = SimConfig(
        weeks=1,
        weekly_time_budget_minutes=1_440,
        enable_event_system=False,
        enable_household_system=False,
        enable_injury_system=False,
        enable_money_system=False,
        expose_session_failure_reasons=True,
    )
    time_env = BenchEnvironment(3, time_config)
    time_action = WeekAction(
        sessions=[SessionPlan(day=1, location="gym", focus="volume", sets=3, reps=5, load_kg=60, duration_min=60)],
        life=LifeAllocation(partner_coverage_hours=0, partner_giveback_hours=0),
    )
    time_outcome = time_env.submit_week(time_action)
    assert time_outcome.as_dict()["session_failure_reasons"] == ({"day": 1, "reason": "time"},)

    adherence_env = BenchEnvironment(8, time_config)
    accessible_action = time_action.model_copy(
        update={"sessions": [time_action.sessions[0].model_copy(update={"duration_min": 25})], "life": LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8)}
    )
    adherence_outcome = adherence_env.submit_week(accessible_action)
    assert adherence_outcome.as_dict()["session_failure_reasons"] == ({"day": 1, "reason": "adherence_draw"},)

    cancelled_env = BenchEnvironment(2, SimConfig(weeks=1, weekly_time_budget_minutes=1_440, expose_session_failure_reasons=True))
    event_day = cancelled_env.calendar.week(1).interrupts[0].day
    cancelled_action = WeekAction(
        sessions=[SessionPlan(day=event_day, location="gym", focus="fallback", sets=2, reps=5, load_kg=40, duration_min=20)],
        life=LifeAllocation(partner_coverage_hours=8, partner_giveback_hours=8),
    )
    cancelled_outcome = cancelled_env.submit_week(
        cancelled_action,
        reactive_responder=lambda observation: {"response": "protect_recovery", "cancel_session_days": [observation.day]},
    )
    assert cancelled_outcome.as_dict()["session_failure_reasons"] == ({"day": event_day, "reason": "cancelled"},)


def test_invalid_action_has_one_repair_then_safe_fallback() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1))
    invalid = {"sessions": [{"day": 1, "focus": "not-a-focus"}]}
    repair = {"sessions": [{"day": 1, "location": "gym", "focus": "fallback", "duration_min": 25, "sets": 2, "reps": 5, "load_kg": 50}]}
    validation = env.validate_action(invalid, repair)
    assert validation.repair_attempted is True
    assert validation.fallback_used is False
    env.submit_week(invalid, repair_action=repair)
    week_record = next(record for record in env.log_records if record.get("type") == "week")
    assert week_record["validation"]["repair_attempted"] is True
    assert week_record["validation"]["fallback_used"] is False


def test_invalid_action_without_repair_uses_safe_action() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1))
    env.submit_week({"sessions": [{"day": 1, "focus": "not-a-focus"}]})
    week_record = next(record for record in env.log_records if record.get("type") == "week")
    assert week_record["validation"]["fallback_used"] is True
    assert env.final_result().invalid_reason is None


def test_budget_overspending_is_rejected_and_repaired_before_simulation() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1, enable_event_system=False))
    overspending = WeekAction(
        life=LifeAllocation(meal_support_spend_cents=25_000, childcare_spend_cents=1),
    )
    repair = WeekAction(life=LifeAllocation(meal_support_spend_cents=1_000))
    env.submit_week(overspending, repair_action=repair)
    week_record = next(record for record in env.log_records if record.get("type") == "week")
    assert week_record["validation"]["errors"]
    assert week_record["validation"]["repair_attempted"] is True
    assert week_record["validation"]["fallback_used"] is False
    result = env.final_result()
    assert result.invalid_reason is None
    assert result.total_spend_cents == 1_000
    assert env.observation.budget_available_cents == 24_000


def test_intra_week_shock_reserve_rejects_earlier_reactive_spend() -> None:
    # Seed 8/week 23 has a daycare closure before a scheduled household
    # shock.  The earlier reactive action is deliberately larger than the
    # non-reserved cash, but the validator must reject it while preserving the
    # 4,500-cent shock reserve; the safe reactive response then lets the shock
    # execute without invalidating the episode.
    env = BenchEnvironment(8, SimConfig(weeks=23))
    quiet = WeekAction(life=LifeAllocation(meal_prep_hours=0, partner_coverage_hours=0, partner_giveback_hours=0))
    while env.observation.episode_week < 23:
        env.submit_week(quiet)
    env._state.cash_cents = 10_000
    env.submit_week(
        quiet,
        reactive_responder=lambda observation: ReactiveAction(
            extra_spend_cents=15_000 if observation.kind != "household_shock" else 0
        ),
    )

    assert env.done is True
    result = env.final_result()
    assert result.invalid_reason is None
    week_record = next(record for record in env.log_records if record.get("type") == "week" and record.get("week") == 23)
    assert week_record["interrupts"][0]["reactive_action"]["extra_spend_cents"] == 0
    assert week_record["interrupts"][1]["kind"] == "household_shock"


def test_gym_closure_without_rack_is_recorded_as_session_transformation() -> None:
    env = BenchEnvironment(0, SimConfig(weeks=14, enable_home_rack=False))
    while env.observation.episode_week < 14:
        env.submit_week(WeekAction())
    outcome = env.submit_week(
        WeekAction(
            sessions=[
                SessionPlan(
                    day=3,
                    location="gym",
                    focus="volume",
                    sets=2,
                    reps=5,
                    load_kg=50.0,
                    duration_min=25,
                )
            ]
        )
    )
    assert outcome.transformed_sessions == 1
    assert "gym closure cancelled gym session (no home rack)" in outcome.transformation_reasons
    assert outcome.missed_sessions == 1


def test_execution_budget_invariant_terminates_episode_as_invalid() -> None:
    env = BenchEnvironment(3, SimConfig(weeks=1, enable_event_system=False))
    env._state.cash_cents = 0
    calls = 0

    def accounting_drift(_life) -> int:
        nonlocal calls
        calls += 1
        return 0 if calls == 1 else 1

    # Validation sees zero cost, while execution discovers a one-cent charge.
    # This models an accounting mismatch and proves the terminal invalid path
    # is distinct from the normal repair/fallback path.
    env._life_allocation_cost = accounting_drift
    env.submit_week(WeekAction())

    assert env.done is True
    result = env.final_result()
    assert result.invalid_reason is not None
    assert result.invalid_reason.startswith("budget insolvency during")
    invalid_record = next(record for record in env.log_records if record.get("type") == "episode_invalidated")
    assert invalid_record["reason"] == result.invalid_reason


def test_cli_replay_consumes_repeated_interrupt_titles_in_order(tmp_path) -> None:
    env = BenchEnvironment(3, SimConfig(weeks=52))
    response_count = 0

    def responder(observation):
        nonlocal response_count
        response_count += 1
        response = "preserve_training" if response_count % 2 else "protect_recovery"
        return {"response": response}

    while not env.done:
        env.submit_week(WeekAction(), reactive_responder=responder)
    env.final_result()
    log = tmp_path / "repeated-interrupts.jsonl"
    env.write_jsonl(log)
    assert response_count >= 2
    assert replay(argparse.Namespace(log=log)) == 0


def test_hidden_injury_joint_changes_endogenous_irritation() -> None:
    action = WeekAction(
        sessions=[
            SessionPlan(day=1, focus="heavy", sets=6, reps=8, load_kg=90, duration_min=80, target_rpe=9.5),
        ],
        life=LifeAllocation(sleep_protection="none", partner_coverage_hours=8, partner_giveback_hours=0),
        rules=StandingRules(on_sleep_below_5h="reduce", on_pain_warning="reduce", on_illness="fallback"),
    )
    shoulder = BenchEnvironment(3, SimConfig(weeks=2))
    elbow = BenchEnvironment(3, SimConfig(weeks=2))
    shoulder.variation = replace(shoulder.variation, injury_joint="shoulder")
    elbow.variation = replace(elbow.variation, injury_joint="elbow")
    shoulder.submit_week(action)
    elbow.submit_week(action)
    assert shoulder.private_snapshot()["state"]["tendon_irritation"] > elbow.private_snapshot()["state"]["tendon_irritation"]


def test_hidden_motivation_changes_adherence() -> None:
    action = WeekAction(
        sessions=[SessionPlan(day=1, focus="volume", sets=4, reps=5, load_kg=60, duration_min=45, target_rpe=7)],
        life=LifeAllocation(sleep_protection="standard", partner_coverage_hours=2, partner_giveback_hours=2),
        rules=StandingRules(),
    )
    config = SimConfig(
        weeks=12,
        enable_event_system=False,
        enable_injury_system=False,
        enable_household_system=False,
        enable_money_system=False,
    )
    low = BenchEnvironment(3, config)
    high = BenchEnvironment(3, config)
    low.variation = replace(low.variation, motivation_baseline=0.58)
    high.variation = replace(high.variation, motivation_baseline=0.76)
    low._state.motivation = 0.58
    high._state.motivation = 0.76
    while not low.done:
        low.submit_week(action)
        high.submit_week(action)
    assert high.final_result().completed_sessions > low.final_result().completed_sessions


def test_declared_sleep_and_illness_rules_change_session_execution() -> None:
    action = WeekAction(
        sessions=[SessionPlan(day=1, focus="heavy", sets=4, reps=5, load_kg=75, duration_min=50, target_rpe=8.5)],
        life=LifeAllocation(sleep_protection="none", partner_coverage_hours=8, partner_giveback_hours=0),
        rules=StandingRules(on_sleep_below_5h="reduce", on_pain_warning="reduce", on_illness="fallback"),
    )
    env = BenchEnvironment(3, SimConfig(weeks=1))
    env._state.sleep_debt = 14.0
    env._state.illness_days = 2
    outcome = env.submit_week(action)
    week = next(record for record in env.log_records if record.get("type") == "week")
    executed = [day["session"] for day in week["days"] if day["session"] is not None]
    assert outcome.completed_sessions == 1
    assert executed and executed[0]["focus"] == "fallback"
