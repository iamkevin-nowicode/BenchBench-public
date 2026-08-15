from __future__ import annotations

from bench_bench.constraint_inventory import (
    ENTRIES,
    all_markers,
    every_entry_rendered,
    prompt_markers,
    rejection_tokens,
)
from bench_bench.config import SimConfig
from bench_bench.engine import BenchEnvironment
from bench_bench.events import InterruptEvent
from bench_bench.runner import ModelRunner
from bench_bench.schemas import LifeAllocation, ReactiveAction, SessionPlan, WeekAction


def test_constraint_inventory_is_bidirectionally_conformant_with_prompts() -> None:
    weekly = ModelRunner.WEEK_SYSTEM_PROMPT
    reactive = ModelRunner.REACTIVE_SYSTEM_PROMPT
    assert every_entry_rendered(weekly, reactive)
    assert prompt_markers(weekly) | prompt_markers(reactive) <= all_markers()
    assert {entry.marker for entry in ENTRIES} <= prompt_markers(weekly) | prompt_markers(reactive)

    combined = f"{weekly}\n{reactive}"
    for key, required in {
        "ledger.total": ("900", "180", "720"),
        "ledger.sleep_cost": ("0 minutes", "30 minutes", "60 minutes"),
        "ledger.delegated_chores": ("1200¢",),
        "ledger.reactive_childcare": ("1400¢",),
        "ledger.commute": ("20 commute minutes", "10 overhead minutes"),
        "engine.authored_fallback_load": ("0.78",),
    }.items():
        entry = next(item for item in ENTRIES if item.key == key)
        assert entry.marker in combined
        assert all(fragment in combined for fragment in required)

    assert "Valid example:" in weekly
    assert '"sessions":[' in weekly
    assert '"life":{' in weekly
    assert '"purchases":[]' in weekly
    assert "[constraint:engine.shock_reserve]" in reactive
    assert "[constraint:mechanic.career_week24]" in weekly


def test_constraint_inventory_covers_validation_rejection_messages() -> None:
    messages: list[str] = []

    def capture(call) -> None:
        try:
            call()
        except Exception as exc:  # noqa: BLE001 - the fuzz corpus is intentionally broad.
            messages.append(str(exc))

    capture(lambda: SessionPlan(day=7))
    capture(lambda: SessionPlan(day="2"))
    capture(lambda: SessionPlan(focus="fallback", duration_min=26))
    capture(lambda: SessionPlan(focus="test", reps=2))
    capture(lambda: LifeAllocation(purchases=["home_gym", "home_gym"]))
    capture(lambda: WeekAction(sessions=[SessionPlan(day=0), SessionPlan(day=0)]))
    capture(lambda: WeekAction(sessions=[SessionPlan(day=day) for day in range(6)]))
    capture(lambda: ReactiveAction(cancel_session_days=[0], fallback_session_days=[0]))
    capture(lambda: ReactiveAction(cancel_session_days=[7]))
    capture(lambda: SessionPlan.model_validate({"day": 0, "unknown": 1}))

    env = BenchEnvironment(3, SimConfig(weeks=1))
    validation_cases = (
        WeekAction(
            sessions=[
                SessionPlan(day=0, focus="fallback", duration_min=25, sets=3, reps=6, load_kg=100.0),
            ]
        ),
        WeekAction(sessions=[SessionPlan(day=day, duration_min=120) for day in range(5)]),
        WeekAction(life=LifeAllocation(purchases=["home_gym"])),
    )
    for action in validation_cases:
        messages.extend(env.validate_action(action).errors)

    env._state.cash_cents = 0
    event = InterruptEvent(
        day=2,
        kind="daycare_closure",
        severity="medium",
        title="daycare closure",
        detail="Childcare is unavailable.",
        duration_days=1,
        sleep_delta=0.0,
        time_loss_min=0,
    )
    _, reactive_error = env.validate_reactive_action(ReactiveAction(extra_spend_cents=1), event)
    assert reactive_error is not None
    messages.append(reactive_error)

    assert messages
    tokens = rejection_tokens()
    for message in messages:
        assert any(token in message.lower() for token in tokens), message


def test_observation_reports_usable_minutes_after_fixed_reserve() -> None:
    observation = BenchEnvironment(0, SimConfig(weeks=1)).observation
    assert observation.weekly_time_budget_minutes == 720
    assert observation.weekly_fixed_household_minutes == 180
