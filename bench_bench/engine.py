"""Deterministic 52-week-native simulator for Bench-bench."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import wraps
import json
import math
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import ValidationError

from . import __version__
from .config import SimConfig
from .events import EventCalendar, InterruptEvent
from .provenance import engine_config_hash
from .rng import HiddenVariation, NoiseBook, make_hidden_variation, make_noise_book
from .schemas import (
    InterruptObservation,
    LifeAllocation,
    PlannedEvent,
    ReactiveAction,
    RecentWeek,
    SessionPlan,
    WeekAction,
    WeekObservation,
)


ReactiveResponder = Callable[[InterruptObservation], ReactiveAction | dict[str, Any] | None]

# These tests are hidden from the acting model. They are hypothetical
# standardized-test reads and do not mutate the episode state.
HIDDEN_STANDARDIZED_TEST_WEEKS = (44, 48, 52)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _band(value: float, thresholds: tuple[float, ...], labels: tuple[str, ...]) -> str:
    for threshold, label in zip(thresholds, labels):
        if value < threshold:
            return label
    return labels[-1]


@dataclass
class _WeekRuntime:
    action: WeekAction
    cancelled_days: set[int] = field(default_factory=set)
    fallback_days: set[int] = field(default_factory=set)
    home_days: set[int] = field(default_factory=set)
    coverage_minutes: float = 0.0
    sleep_protection: str = "standard"
    meal_support_level: float = 0.8
    nutrition_band: str = "adequate"
    planned_sessions: int = 0
    completed_sessions: int = 0
    fallback_sessions: int = 0
    missed_sessions: int = 0
    pain_days: int = 0
    session_notes: list[str] = field(default_factory=list)
    session_failure_reasons: list[SessionFailure] = field(default_factory=list)
    sleep_hours: list[float] = field(default_factory=list)
    interrupt_records: list[dict[str, Any]] = field(default_factory=list)
    raw_stimulus: float = 0.0
    weekly_stimulus: float = 0.0
    ledger_minutes_remaining: int = 0
    ledger_minutes_committed: int = 0


@dataclass
class _State:
    week: int = 1
    day_index: int = 0
    base_capacity_kg: float = 84.0
    fitness_signal: float = 0.0
    fatigue_signal: float = 0.0
    immediate_gain: float = 0.0
    technique: float = 0.5
    tendon_irritation: float = 0.0
    injury_recovery_days: int = 0
    illness_days: int = 0
    partner_illness_days: int = 0
    sleep_debt: float = 0.0
    motivation: float = 0.65
    household_strain: float = 0.4
    reciprocity_debt: float = 0.0
    work_strain: float = 0.15
    nutrition_score: float = 0.8
    body_mass_kg: float = 84.0
    last_body_mass_kg: float = 84.0
    cash_cents: int = 25_000
    current_month_spend_cents: int = 0
    home_gym: bool = False
    recurring_childcare: bool = False
    meal_subscription: bool = False
    stretch_project_weeks: int = 0
    total_spend_cents: int = 0
    completed_sessions: int = 0
    missed_sessions: int = 0
    fallback_sessions: int = 0
    productive_weeks: int = 0
    productive_streak_weeks: int = 0
    pain_days: int = 0
    sleep_hours_history: list[float] = field(default_factory=list)
    session_history: list[dict[str, Any]] = field(default_factory=list)
    week_history: list[dict[str, Any]] = field(default_factory=list)
    last_interrupt: str | None = None
    invalid_reason: str | None = None
    one_off_shock_costs_cents: int = 0


@dataclass(frozen=True)
class ValidationResult:
    action: WeekAction
    errors: tuple[str, ...]
    repair_attempted: bool
    fallback_used: bool
    raw_action: Any


class _BudgetInsolvency(RuntimeError):
    """Raised when an execution-time charge defeats the validated ledger."""


FailureReason = Literal["time", "equipment", "adherence_draw", "cancelled"]


@dataclass(frozen=True)
class SessionFailure:
    day: int
    reason: FailureReason


@dataclass(frozen=True)
class WeekOutcome:
    week: int
    planned_sessions: int
    completed_sessions: int
    fallback_sessions: int
    missed_sessions: int
    average_sleep_hours: float
    estimated_1rm_kg: float
    household_strain_band: str
    pain_band: str
    headline: str
    interrupts: tuple[str, ...]
    session_failure_reasons: tuple[SessionFailure, ...] | None = None

    def as_dict(self) -> dict[str, Any]:
        values = asdict(self)
        # Preserve the historical opaque outcome shape unless explicitly
        # requested by SimConfig.
        if self.session_failure_reasons is None:
            values.pop("session_failure_reasons", None)
        return values

@dataclass(frozen=True)
class FinalResult:
    final_1rm_kg: float
    estimated_1rm_kg: float
    improvement_kg: float
    completed_sessions: int
    missed_sessions: int
    fallback_sessions: int
    productive_weeks: int
    pain_days: int
    household_strain: float
    sleep_debt: float
    total_spend_cents: int
    invalid_reason: str | None

    def as_dict(self) -> dict[str, Any]:
        # Sleep debt is evaluator-only state; public episode and runner logs
        # expose the coarse sleep observations instead.
        values = asdict(self)
        values.pop("sleep_debt", None)
        return values


def _capture_budget_invalidation(method: Callable[..., WeekOutcome]) -> Callable[..., WeekOutcome]:
    """Terminate and mark an episode when an execution charge cannot be paid."""

    @wraps(method)
    def wrapped(self: "BenchEnvironment", *args: Any, **kwargs: Any) -> WeekOutcome:
        try:
            return method(self, *args, **kwargs)
        except _BudgetInsolvency as exc:
            return self._terminate_invalid_episode(str(exc))

    return wrapped


class BenchEnvironment:
    """One deterministic episode.

    The public methods expose observations, validated actions, and outcomes.
    Hidden variation, true capacity, fatigue, and the future event calendar
    remain private to the environment.
    """

    PERSONA = {
        "name": "Dave",
        "age": 38,
        "role": "returning lifter and full-time working dad",
        "body_mass_kg": 84.0,
        "estimated_1rm_kg": 84.0,
        "baby_age_months": 6.0,
        "partner_work": "full-time",
        "discretionary_budget_per_month_cents": 25_000,
        "gym": "commercial gym membership",
        "home_equipment": False,
    }

    def __init__(self, seed: int, config: SimConfig | None = None) -> None:
        self.seed = int(seed)
        self.config = config or SimConfig()
        if not 1 <= self.config.weeks <= 52:
            raise ValueError("weeks must be between 1 and 52")
        # Calendar and noise are both generated completely before the first
        # observation.  Agent choices never consume these streams.
        self.calendar = EventCalendar(self.seed, 52, enabled=self.config.enable_event_system)
        self.variation: HiddenVariation = make_hidden_variation(self.seed)
        self.noise: NoiseBook = make_noise_book(self.seed, self.config.days)
        self._state = _State(
            base_capacity_kg=self.config.starting_base_capacity_kg,
            technique=self.variation.technique_start,
            motivation=self.variation.motivation_baseline,
            body_mass_kg=self.config.starting_body_mass_kg,
            last_body_mass_kg=self.config.starting_body_mass_kg,
            cash_cents=self.config.starting_cash_cents,
        )
        self._hidden_standardized_test_scores: list[float] = []
        self._done = False
        self._active_runtime: _WeekRuntime | None = None
        self._current_observation = self._render_observation()
        self._log: list[dict[str, Any]] = [
            {
                "type": "episode_start",
                "benchmark": "Bench-bench",
                "version": __version__,
                "engine_config_hash": engine_config_hash(),
                "seed": self.seed,
                "config": self.config.as_dict(),
                "persona": self.PERSONA,
            },
            {"type": "observation", "week": 1, "observation": self._current_observation.model_dump(mode="json")},
        ]

    @property
    def done(self) -> bool:
        return self._done

    @property
    def observation(self) -> WeekObservation:
        return self._current_observation

    @property
    def log_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._log)

    def jsonl(self) -> str:
        """Return the complete public episode log with stable serialization."""
        return "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
            for record in self._log
        )

    def write_jsonl(self, path: str | Path) -> None:
        Path(path).write_text(self.jsonl(), encoding="utf-8")

    def validate_action(self, raw_action: Any, repair_action: Any = None) -> ValidationResult:
        errors: list[str] = []
        action, error = self._parse_week_action_with_budget(raw_action)
        if error is None and action is not None:
            return ValidationResult(action, tuple(errors), False, False, raw_action)
        errors.append(error or "invalid action")

        if repair_action is not None:
            action, error = self._parse_week_action_with_budget(repair_action)
            if error is None and action is not None:
                return ValidationResult(action, tuple(errors), True, False, raw_action)
            errors.append(f"repair action: {error or 'invalid action'}")

        action = self.safe_action()
        return ValidationResult(action, tuple(errors), repair_action is not None, True, raw_action)

    def _parse_week_action_with_budget(self, raw_action: Any) -> tuple[WeekAction | None, str | None]:
        try:
            action = self._parse_week_action(raw_action)
        except (ValidationError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return None, self._format_validation_error(exc)
        return action, self._budget_error_for_week_action(action)

    def _life_allocation_cost(self, life: LifeAllocation) -> int:
        purchase_costs = {"home_gym": 60_000, "recurring_childcare": 7_500, "meal_prep_subscription": 3_000}
        delegated_chore_cost = life.chore_delegation_spend_cents
        if self.config.enable_money_system:
            delegated_chore_cost = max(
                delegated_chore_cost,
                math.ceil(life.chore_delegation_hours * self.config.delegated_chore_cost_per_hour_cents),
            )
        cost = life.meal_support_spend_cents + life.childcare_spend_cents + delegated_chore_cost
        for purchase in life.purchases:
            if purchase == "home_gym" and not self.config.enable_home_rack:
                continue
            already_owned = (
                (purchase == "home_gym" and self._state.home_gym)
                or (purchase == "recurring_childcare" and self._state.recurring_childcare)
                or (purchase == "meal_prep_subscription" and self._state.meal_subscription)
            )
            if not already_owned:
                cost += purchase_costs[purchase]
        if self._state.meal_subscription:
            cost += 2_800
        if self._state.recurring_childcare:
            cost += 3_500
        return cost

    def _scheduled_household_shock_cost(self) -> int:
        return sum(4_500 for event in self.calendar.week(self._state.week).interrupts if event.kind == "household_shock")

    def _session_time_minutes(self, session: SessionPlan) -> int:
        commute = {
            "gym": self.config.gym_commute_minutes,
            "home": self.config.home_session_overhead_minutes,
            "hotel": self.config.hotel_commute_minutes,
        }[session.location]
        crowding = 0
        if self.config.enable_event_system and session.location == "gym":
            week = min(52, max(1, self._state.week))
            crowding = round(self.calendar.week(week).gym_crowding * 20.0)
        return session.duration_min + commute + crowding

    def _weekly_time_cost_minutes(self, action: WeekAction) -> int:
        external_childcare_hours = 0.0
        if self.config.enable_event_system and self._state.week == 14:
            external_childcare_hours += 4.0
        if self._state.recurring_childcare or "recurring_childcare" in action.life.purchases:
            external_childcare_hours += 6.0
        allocation_hours = (
            action.life.meal_prep_hours
            + action.life.childcare_hours
            + action.life.chore_delegation_hours
            + action.life.partner_coverage_hours
            + action.life.partner_giveback_hours
            + external_childcare_hours
        )
        training_minutes = sum(self._session_time_minutes(session) for session in action.sessions)
        return math.ceil(training_minutes + allocation_hours * 60.0)

    def _fallback_load_error_for_week_action(self, action: WeekAction) -> str | None:
        ceiling = max(0.0, self._current_observation.estimated_1rm_kg * self.config.fallback_max_load_ratio)
        for session in action.sessions:
            if session.focus == "fallback" and session.load_kg > ceiling + 0.01:
                return (
                    "authored fallback load exceeds the permitted ceiling "
                    f"on day {session.day}: {session.load_kg:.1f} kg > {ceiling:.1f} kg "
                    f"({self.config.fallback_max_load_ratio:.2f}× estimated 1RM)"
                )
        return None

    def _time_error_for_week_action(self, action: WeekAction) -> str | None:
        required = self._weekly_time_cost_minutes(action)
        available = max(0, self.config.weekly_time_budget_minutes)
        if required <= available:
            return None
        return (
            f"weekly action requires {required} minutes from the shared time/resource ledger, "
            f"but only {available} minutes are available"
        )

    def _budget_error_for_week_action(self, action: WeekAction) -> str | None:
        fallback_error = self._fallback_load_error_for_week_action(action)
        if fallback_error is not None:
            return fallback_error
        time_error = self._time_error_for_week_action(action)
        if time_error is not None:
            return time_error
        if not self.config.enable_money_system:
            return None
        available = self._state.cash_cents
        if self._state.week > 1:
            available += self.config.weekly_budget_cents
        life_cost = self._life_allocation_cost(action.life)
        shock_reserve = self._scheduled_household_shock_cost()
        required = life_cost + shock_reserve
        if required <= available:
            return None
        reserve_text = f" plus {shock_reserve} cents reserved for scheduled household shocks" if shock_reserve else ""
        return (
            f"weekly action requires {required} cents ({life_cost} cents in life allocations{reserve_text}), "
            f"but only {available} cents is available"
        )

    def validate_reactive_action(self, raw_action: Any, event: InterruptEvent) -> tuple[ReactiveAction | None, str | None]:
        try:
            action = ReactiveAction.model_validate(raw_action)
        except (ValidationError, TypeError, ValueError) as exc:
            return None, self._format_validation_error(exc)
        runtime = self._active_runtime
        if runtime is not None:
            required_minutes = math.ceil(action.extra_childcare_hours * 60.0)
            if required_minutes > runtime.ledger_minutes_remaining:
                return None, (
                    f"reactive childcare requires {required_minutes} additional minutes from the shared "
                    f"time/resource ledger, but only {runtime.ledger_minutes_remaining} remain"
                )
        if not self.config.enable_money_system:
            return action, None
        required = max(
            action.extra_spend_cents,
            math.ceil(action.extra_childcare_hours * self.config.reactive_childcare_cost_per_hour_cents),
        )
        if event.kind == "household_shock":
            required += 4_500
        if required <= self._state.cash_cents:
            return action, None
        return None, (
            f"reactive action requires {required} cents including the scheduled event cost, "
            f"but only {self._state.cash_cents} cents is available"
        )

    def safe_action(self) -> WeekAction:
        equipment = set(self._current_observation.equipment)
        location = "gym" if "commercial_gym" in equipment else "home"
        load = min(60.0, max(25.0, self._current_observation.estimated_1rm_kg * 0.62))
        return WeekAction(
            sessions=[
                SessionPlan(
                    day=2,
                    slot="evening",
                    location=location,
                    focus="fallback",
                    sets=2,
                    reps=5,
                    load_kg=round(load, 1),
                    duration_min=25,
                    target_rpe=6.0,
                )
            ],
            life=LifeAllocation(
                meal_prep_hours=2.0,
                sleep_protection="strong",
                partner_coverage_hours=1.0,
                partner_giveback_hours=1.0,
            ),
        )

    @_capture_budget_invalidation
    def submit_week(
        self,
        raw_action: Any,
        *,
        repair_action: Any = None,
        reactive_responder: ReactiveResponder | None = None,
    ) -> WeekOutcome:
        if self._done:
            raise RuntimeError("episode is already complete")
        week = self._state.week
        validation = self.validate_action(raw_action, repair_action)
        action = validation.action
        self._start_week(action)
        ledger_cost = self._weekly_time_cost_minutes(action)
        runtime = _WeekRuntime(
            action=action,
            coverage_minutes=self._available_coverage_minutes(action.life),
            sleep_protection=action.life.sleep_protection,
            meal_support_level=self._meal_support_level(action.life),
            nutrition_band=self._nutrition_band(self._meal_support_level(action.life)),
            planned_sessions=len(action.sessions),
            ledger_minutes_remaining=self.config.weekly_time_budget_minutes - ledger_cost,
            ledger_minutes_committed=ledger_cost,
        )
        self._active_runtime = runtime
        self._apply_life_allocation(action.life, runtime)

        week_record: dict[str, Any] = {
            "type": "week",
            "week": week,
            "observation": self._current_observation.model_dump(mode="json"),
            "action": action.model_dump(mode="json"),
            "validation": {
                "errors": list(validation.errors),
                "repair_attempted": validation.repair_attempted,
                "fallback_used": validation.fallback_used,
            },
            "days": [],
            "interrupts": [],
        }

        event = self.calendar.week(week)
        session_by_day = {session.day: session for session in action.sessions}
        for day in range(7):
            self._state.day_index = (week - 1) * 7 + day
            self._decay_daily_signals()
            self._start_day_effects()
            pain_active_today = self._pain_stage() >= 1
            for interrupt in [item for item in event.interrupts if item.day == day]:
                reactive = self._get_reactive_action(interrupt, reactive_responder, runtime)
                self._apply_interrupt(interrupt, reactive, runtime)
                interrupt_record = {
                    "day": day,
                    "kind": interrupt.kind,
                    "title": interrupt.title,
                    "reactive_action": reactive.model_dump(mode="json"),
                }
                runtime.interrupt_records.append(interrupt_record)
                week_record["interrupts"].append(interrupt_record)

            sleep = self._daily_sleep(event, runtime)
            runtime.sleep_hours.append(sleep)
            self._state.sleep_hours_history.append(sleep)
            self._update_sleep_debt(sleep)

            planned = session_by_day.get(day)
            day_note = "rest day"
            session_result: dict[str, Any] | None = None
            if planned is not None:
                session = self._apply_rules(planned, day, sleep, runtime)
                if session is None:
                    runtime.missed_sessions += 1
                    self._state.missed_sessions += 1
                    runtime.session_failure_reasons.append(SessionFailure(day=day, reason="cancelled"))
                    day_note = "session cancelled by standing rule"
                else:
                    if session.focus == "fallback":
                        runtime.fallback_sessions += 1
                        self._state.fallback_sessions += 1
                    session_result = self._execute_session(session, sleep, event, runtime)
                    pain_active_today = pain_active_today or self._pain_stage() >= 1
                    day_note = str(session_result["note"])
            if pain_active_today:
                runtime.pain_days += 1
            self._end_day_effects()
            week_record["days"].append(
                {
                    "day": day,
                    "sleep_hours": round(sleep, 3),
                    "planned_focus": planned.focus if planned else None,
                    "session": session_result,
                    "note": day_note,
                }
            )

        self._finish_week(runtime)
        outcome = self._make_week_outcome(week, runtime)
        self._state.week_history.append(outcome.as_dict())
        self._state.week += 1
        if self._state.week > self.config.weeks:
            self._done = True
        self._current_observation = self._render_observation()
        week_record["outcome"] = outcome.as_dict()
        week_record["next_observation"] = self._current_observation.model_dump(mode="json")
        self._log.append(week_record)
        self._active_runtime = None
        return outcome

    def final_result(self) -> FinalResult:
        if not self._done:
            raise RuntimeError("final result is available only after the configured weeks")
        test_scores = self._hidden_standardized_test_scores or [self._standardized_test_capacity()]
        final_capacity = sum(test_scores) / len(test_scores)
        result = FinalResult(
            final_1rm_kg=round(final_capacity, 2),
            estimated_1rm_kg=round(self._estimate_1rm(), 2),
            improvement_kg=round(final_capacity - self.config.starting_estimated_1rm_kg, 2),
            completed_sessions=self._state.completed_sessions,
            missed_sessions=self._state.missed_sessions,
            fallback_sessions=self._state.fallback_sessions,
            productive_weeks=self._state.productive_weeks,
            pain_days=self._state.pain_days,
            household_strain=round(self._state.household_strain, 3),
            sleep_debt=round(self._state.sleep_debt, 3),
            total_spend_cents=self._state.total_spend_cents,
            invalid_reason=self._state.invalid_reason,
        )
        if not any(record.get("type") == "final_result" for record in self._log):
            self._log.append(
                {
                    "type": "final_result",
                    "engine_config_hash": engine_config_hash(),
                    "result": result.as_dict(),
                }
            )
        return result

    def private_snapshot(self) -> dict[str, Any]:
        """Test-only introspection; never included in observations or logs."""
        return {
            "state": asdict(self._state),
            "hidden_standardized_test_scores": list(self._hidden_standardized_test_scores),
            "variation": asdict(self.variation),
            "calendar": {
                "week": self._state.week,
                "interrupt_count": sum(len(self.calendar.week(i).interrupts) for i in range(1, 53)),
            },
        }

    def _parse_week_action(self, raw_action: Any) -> WeekAction:
        if isinstance(raw_action, WeekAction):
            return raw_action
        if isinstance(raw_action, str):
            raw_action = json.loads(raw_action)
        return WeekAction.model_validate(raw_action)

    @staticmethod
    def _format_validation_error(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "; ".join(error.get("msg", "invalid action") for error in exc.errors())
        return str(exc) or "invalid action"

    def _start_week(self, action: WeekAction) -> None:
        if self._state.week > 1:
            self._state.cash_cents += self.config.weekly_budget_cents
        if (self._state.week - 1) % 4 == 0:
            self._state.current_month_spend_cents = 0
        self._state.work_strain = _clamp(self._state.work_strain * 0.76, 0.0, 1.0)
        if self._state.stretch_project_weeks > 0:
            self._state.stretch_project_weeks -= 1
        if self.config.enable_household_system:
            self._state.household_strain = _clamp(self._state.household_strain * 0.92, 0.0, 1.0)
            self._state.reciprocity_debt = _clamp(self._state.reciprocity_debt * 0.82, 0.0, 1.0)

    def _available_coverage_minutes(self, life: LifeAllocation) -> float:
        free_grandparent_hours = 4.0 if self.config.enable_event_system and self._state.week == 14 else 0.0
        recurring_hours = 6.0 if self._state.recurring_childcare else 0.0
        paid_hours = min(life.childcare_hours, life.childcare_spend_cents / 1_400.0)
        return (free_grandparent_hours + recurring_hours + paid_hours + life.partner_coverage_hours) * 60.0

    def _meal_support_level(self, life: LifeAllocation) -> float:
        level = 0.58 + min(0.28, life.meal_prep_hours * 0.075)
        if life.meal_support_spend_cents >= 2_500:
            level += 0.08
        if self._state.meal_subscription:
            level += 0.20
        return _clamp(level, 0.45, 1.15)

    @staticmethod
    def _nutrition_band(level: float) -> str:
        if level < 0.72:
            return "insufficient"
        if level < 1.0:
            return "adequate"
        return "high_support"

    def _apply_life_allocation(self, life: LifeAllocation, runtime: _WeekRuntime) -> None:
        cost = self._life_allocation_cost(life)
        self._charge(cost, "weekly life allocation exceeded available budget")
        self._state.total_spend_cents += cost
        self._state.current_month_spend_cents += cost

        for purchase in life.purchases:
            if purchase == "home_gym" and not self.config.enable_home_rack:
                continue
            if purchase == "home_gym":
                self._state.home_gym = True
            elif purchase == "recurring_childcare":
                self._state.recurring_childcare = True
            elif purchase == "meal_prep_subscription":
                self._state.meal_subscription = True

        if self.config.enable_event_system and self._state.week == 24:
            if life.career_choice == "accept_stretch_project":
                self._state.stretch_project_weeks = 8
                self._state.cash_cents += 12_000
                self._state.work_strain = _clamp(self._state.work_strain + 0.12, 0.0, 1.0)
            elif life.career_choice == "protect_time":
                self._state.work_strain = _clamp(self._state.work_strain - 0.04, 0.0, 1.0)

        runtime.meal_support_level = self._meal_support_level(life)
        runtime.nutrition_band = self._nutrition_band(runtime.meal_support_level)
        self._state.nutrition_score = _clamp(self._state.nutrition_score * 0.60 + runtime.meal_support_level * 0.40, 0.35, 1.2)

        if self.config.enable_household_system:
            delegation_effect = life.chore_delegation_hours * 0.045 + min(0.15, life.chore_delegation_spend_cents / 20_000.0)
            coverage_imbalance = life.partner_coverage_hours - life.partner_giveback_hours
            reciprocity_gap = max(0.0, coverage_imbalance)
            reciprocity_repair = max(0.0, -coverage_imbalance)
            self._state.reciprocity_debt = _clamp(
                self._state.reciprocity_debt
                + reciprocity_gap * 0.065
                - reciprocity_repair * 0.045,
                0.0,
                1.0,
            )
            self._state.household_strain = _clamp(
                self._state.household_strain
                - delegation_effect
                + reciprocity_gap * 0.04
                + self._state.reciprocity_debt * 0.025
                - reciprocity_repair * 0.025,
                0.0,
                1.0,
            )
            if life.sleep_protection == "strong" and reciprocity_gap:
                self._state.household_strain = _clamp(self._state.household_strain + reciprocity_gap * 0.015, 0.0, 1.0)

    def _terminate_invalid_episode(self, reason: str) -> WeekOutcome:
        self._state.invalid_reason = reason
        self._done = True
        runtime = self._active_runtime
        self._log.append(
            {
                "type": "episode_invalidated",
                "engine_config_hash": engine_config_hash(),
                "week": self._state.week,
                "reason": reason,
            }
        )
        self._active_runtime = None
        average_sleep = (
            sum(runtime.sleep_hours) / len(runtime.sleep_hours)
            if runtime is not None and runtime.sleep_hours
            else 0.0
        )
        return WeekOutcome(
            week=self._state.week,
            planned_sessions=runtime.planned_sessions if runtime is not None else 0,
            completed_sessions=runtime.completed_sessions if runtime is not None else 0,
            fallback_sessions=runtime.fallback_sessions if runtime is not None else 0,
            missed_sessions=runtime.missed_sessions if runtime is not None else 0,
            average_sleep_hours=round(average_sleep, 2),
            estimated_1rm_kg=round(self._estimate_1rm(), 2),
            household_strain_band=self._household_band(),
            pain_band=self._pain_band(),
            headline="Episode invalidated: budget insolvency.",
            interrupts=(
                tuple(record["title"] for record in runtime.interrupt_records)
                if runtime is not None
                else ()
            ),
            session_failure_reasons=(
                tuple(runtime.session_failure_reasons)
                if runtime is not None and self.config.expose_session_failure_reasons
                else None
            ),
        )

    def _charge(self, cents: int, reason: str) -> None:
        if not self.config.enable_money_system:
            return
        amount = max(0, cents)
        if amount > self._state.cash_cents:
            raise _BudgetInsolvency(
                f"budget insolvency during {reason}: required {amount} cents but only "
                f"{self._state.cash_cents} cents is available"
            )
        self._state.cash_cents -= amount

    def _get_reactive_action(
        self,
        event: InterruptEvent,
        responder: ReactiveResponder | None,
        runtime: _WeekRuntime | None = None,
    ) -> ReactiveAction:
        active_runtime = runtime or self._active_runtime
        observation = InterruptObservation(
            episode_week=self._state.week,
            day=event.day,
            kind=event.kind,  # type: ignore[arg-type]
            title=event.title,
            detail=event.detail,
            severity=event.severity,  # type: ignore[arg-type]
            affected_session_days=[event.day],
            visible_options=["protect_recovery", "reallocate", "preserve_training", "accept_disruption"],
            weekly_time_remaining_minutes=active_runtime.ledger_minutes_remaining if active_runtime is not None else 0,
        )
        if responder is None:
            return ReactiveAction(response="protect_recovery")
        try:
            raw = responder(observation)
            if raw is None:
                return ReactiveAction(response="protect_recovery")
            action, error = self.validate_reactive_action(raw, event)
            return action if error is None and action is not None else ReactiveAction(response="protect_recovery")
        except (ValidationError, TypeError, ValueError):
            return ReactiveAction(response="protect_recovery")

    def _apply_interrupt(self, event: InterruptEvent, reactive: ReactiveAction, runtime: _WeekRuntime) -> None:
        self._state.last_interrupt = event.title
        runtime.cancelled_days.update(reactive.cancel_session_days)
        runtime.fallback_days.update(reactive.fallback_session_days)
        extra_childcare_minutes = math.ceil(reactive.extra_childcare_hours * 60.0)
        if extra_childcare_minutes > runtime.ledger_minutes_remaining:
            raise RuntimeError("reactive childcare exceeded the shared time/resource ledger")
        runtime.ledger_minutes_remaining -= extra_childcare_minutes
        runtime.coverage_minutes += extra_childcare_minutes
        reactive_cost = max(
            reactive.extra_spend_cents,
            math.ceil(reactive.extra_childcare_hours * self.config.reactive_childcare_cost_per_hour_cents),
        )
        self._charge(reactive_cost, "reactive decision exceeded available budget")
        self._state.total_spend_cents += reactive_cost
        self._state.current_month_spend_cents += reactive_cost

        if event.kind == "illness_onset":
            self._state.illness_days = max(self._state.illness_days, event.duration_days)
        elif event.kind == "partner_illness":
            self._state.partner_illness_days = max(self._state.partner_illness_days, event.duration_days)
        elif event.kind == "gym_closed":
            if self._state.home_gym and reactive.response == "reallocate":
                runtime.home_days.add(event.day)
            else:
                runtime.cancelled_days.add(event.day)
        elif event.kind == "household_shock":
            self._charge(4_500, "household shock exhausted available budget")
            self._state.total_spend_cents += 4_500
            self._state.current_month_spend_cents += 4_500
            if self.config.enable_household_system:
                self._state.household_strain = _clamp(self._state.household_strain + 0.13, 0.0, 1.0)

        if reactive.response == "protect_recovery":
            runtime.fallback_days.add(event.day)
            if self.config.enable_household_system:
                self._state.household_strain = _clamp(self._state.household_strain - 0.025, 0.0, 1.0)
        elif reactive.response == "preserve_training":
            if self.config.enable_household_system:
                self._state.household_strain = _clamp(self._state.household_strain + 0.07, 0.0, 1.0)

    def _start_day_effects(self) -> None:
        pass

    def _end_day_effects(self) -> None:
        if self._state.illness_days > 0:
            self._state.illness_days -= 1
        if self._state.partner_illness_days > 0:
            self._state.partner_illness_days -= 1

    def _daily_sleep(self, event: Any, runtime: _WeekRuntime) -> float:
        if not self.config.enable_sleep_system:
            return 7.0
        protection = {"none": 0.0, "standard": 0.18, "strong": 0.36}[runtime.sleep_protection]
        index = self._state.day_index
        noise = self.noise.sleep_noise[index]
        sleep = 6.92 - event.sleep_pressure * 0.78 + protection + noise
        sleep -= self._state.sleep_debt * 0.025
        sleep -= self._state.illness_days * 0.18 + self._state.partner_illness_days * 0.15
        sleep -= self._state.household_strain * 0.20
        return round(_clamp(sleep, 3.6, 8.5), 3)

    def _update_sleep_debt(self, sleep: float) -> None:
        if not self.config.enable_sleep_system:
            self._state.sleep_debt = 0.0
            return
        target = 6.8
        self._state.sleep_debt = _clamp(
            self._state.sleep_debt + max(0.0, target - sleep) * 0.35 - max(0.0, sleep - target) * 0.25,
            0.0,
            14.0,
        )

    def _decay_daily_signals(self) -> None:
        if self.config.enable_delayed_adaptation:
            self._state.fitness_signal *= math.exp(-1.0 / self.config.fit_tau_days)
            self._state.fatigue_signal *= math.exp(-1.0 / self.config.fatigue_tau_days)
        else:
            self._state.fitness_signal = 0.0
            self._state.fatigue_signal = 0.0
        if self.config.enable_injury_system:
            self._state.tendon_irritation = max(0.0, self._state.tendon_irritation - 0.045)
            if self._state.injury_recovery_days > 0:
                self._state.injury_recovery_days -= 1
        else:
            self._state.tendon_irritation = 0.0
            self._state.injury_recovery_days = 0

    def _apply_rules(self, planned: SessionPlan, day: int, sleep: float, runtime: _WeekRuntime) -> SessionPlan | None:
        if day in runtime.cancelled_days:
            return None
        session = planned
        if day in runtime.home_days and self._state.home_gym:
            session = session.model_copy(update={"location": "home"})
        if day in runtime.fallback_days:
            session = self._as_fallback(session)
        if sleep < 5.0:
            if runtime.action.rules.on_sleep_below_5h == "skip":
                return None
            if runtime.action.rules.on_sleep_below_5h == "fallback":
                session = self._as_fallback(session)
            elif runtime.action.rules.on_sleep_below_5h == "reduce":
                session = self._as_reduced(session)
        if self._pain_stage() >= 1:
            if runtime.action.rules.on_pain_warning == "skip":
                return None
            if runtime.action.rules.on_pain_warning == "fallback":
                session = self._as_fallback(session)
            elif runtime.action.rules.on_pain_warning == "reduce":
                session = self._as_reduced(session)
        if self._state.illness_days > 0:
            if runtime.action.rules.on_illness == "skip":
                return None
            if runtime.action.rules.on_illness in ("protect_recovery", "fallback"):
                session = self._as_fallback(session)
        return session

    @staticmethod
    def _as_fallback(session: SessionPlan) -> SessionPlan:
        location = session.location if session.location != "hotel" else "gym"
        return SessionPlan(
            day=session.day,
            slot=session.slot,
            location=location,  # type: ignore[arg-type]
            focus="fallback",
            sets=min(3, session.sets),
            reps=min(6, session.reps),
            load_kg=round(session.load_kg * 0.78, 1),
            duration_min=25,
            target_rpe=min(6.5, session.target_rpe),
        )

    @staticmethod
    def _as_reduced(session: SessionPlan) -> SessionPlan:
        return SessionPlan(
            day=session.day,
            slot=session.slot,
            location=session.location,
            focus="technique" if session.focus == "heavy" else session.focus,
            sets=max(1, min(4, session.sets - 1)),
            reps=min(8, session.reps),
            load_kg=round(session.load_kg * 0.84, 1),
            duration_min=min(45, session.duration_min),
            target_rpe=min(7.0, session.target_rpe),
        )

    def _execute_session(self, session: SessionPlan, sleep: float, event: Any, runtime: _WeekRuntime) -> dict[str, Any]:
        location_factor = {
            "gym": 1.0,
            "home": self.config.home_training_efficiency,
            "hotel": 0.34,
        }[session.location]
        accessible = True
        reason = "completed"
        if session.location == "home" and not self._state.home_gym:
            accessible = False
            reason = "home equipment is not owned"
        if self.config.enable_event_system and session.location == "gym" and self._state.week in (19, 39, 47):
            accessible = False
            reason = "travel week has no dependable commercial-gym access"

        work_pressure = self.calendar.week(self._state.week).time_pressure_min / 7.0
        day_of_week = self._state.day_index % 7
        base_minutes = 61.0 - work_pressure - self._state.household_strain * 11.0
        if day_of_week not in event.open_days:
            # A non-open day still exists, but has less flexible family time.
            base_minutes -= 18.0
        if self._state.stretch_project_weeks > 0:
            base_minutes -= 12.0
        if self._state.illness_days > 0 or self._state.partner_illness_days > 0:
            base_minutes -= 18.0
        commute = {
            "gym": self.config.gym_commute_minutes,
            "home": self.config.home_session_overhead_minutes,
            "hotel": self.config.hotel_commute_minutes,
        }[session.location]
        crowding_minutes = event.gym_crowding * 20.0 if session.location == "gym" else 0.0
        total_minutes = session.duration_min + commute + crowding_minutes
        required_coverage = max(0.0, total_minutes - base_minutes)
        if required_coverage > runtime.coverage_minutes:
            accessible = False
            reason = "the planned session did not fit the remaining family time window"
        else:
            runtime.coverage_minutes -= required_coverage

        if not accessible:
            runtime.missed_sessions += 1
            self._state.missed_sessions += 1
            runtime.session_notes.append(reason)
            reason_code: FailureReason = "equipment" if (
                (session.location == "home" and not self._state.home_gym)
                or (session.location == "gym" and self.config.enable_event_system and self._state.week in (19, 39, 47))
            ) else "time"
            runtime.session_failure_reasons.append(
                SessionFailure(day=self._state.day_index % 7, reason=reason_code)
            )
            return {"status": "missed", "note": reason}

        readiness = 0.91
        readiness -= min(0.28, self._state.sleep_debt * 0.026) if self.config.enable_sleep_system else 0.0
        readiness -= min(0.20, self._state.fatigue_signal * 0.018)
        readiness -= self._state.household_strain * 0.09 if self.config.enable_household_system else 0.0
        readiness -= self._state.work_strain * 0.045
        readiness -= 0.18 if self._state.illness_days > 0 else 0.0
        readiness -= 0.10 if self._pain_stage() >= 2 else 0.0
        if session.focus == "fallback":
            readiness += 0.10
        if session.focus == "heavy":
            readiness -= 0.045
        if session.location == "home":
            readiness += 0.035
        motivation_factor = 0.72 + self._state.motivation * 0.42
        adherence_probability = _clamp(
            readiness * motivation_factor * (0.94 + self.variation.recovery_capacity * 0.06),
            0.18,
            0.97,
        )
        adhered = self.noise.adherence_noise[self._state.day_index] <= adherence_probability
        if not adhered:
            self._state.missed_sessions += 1
            runtime.missed_sessions += 1
            self._state.motivation = _clamp(self._state.motivation - 0.025, 0.25, 0.95)
            runtime.session_failure_reasons.append(
                SessionFailure(day=self._state.day_index % 7, reason="adherence_draw")
            )
            return {"status": "silently_failed", "note": "the plan was reasonable but adherence failed"}

        true_capacity = self._true_capacity()
        # Authored fallback loads have already passed the visible validation
        # ceiling. Do not silently rewrite them here; only sessions coerced
        # by `_as_fallback` arrive pre-transformed.
        executed_load_kg = session.load_kg
        load_ratio = _clamp(executed_load_kg / max(60.0, true_capacity), 0.35, 1.20)
        if session.location == "home" and session.focus in ("heavy", "test"):
            # A home rack has no spotter.  It remains useful for ordinary
            # volume and technique work, but true near-max work is capped.
            load_ratio = min(load_ratio, self.config.home_no_spotter_max_ratio)
        # Couple reps to load with a Brzycki-style rep-max ceiling.  A
        # prescription above the ceiling is reduced to the largest plausible
        # rep count (with one rep as the minimum attempted set), so excessive
        # reps cannot turn into free stimulus.
        ceiling_load_kg = load_ratio * max(60.0, true_capacity)
        ceiling_1rm_kg = max(1.0, true_capacity * self.config.brzycki_repmax_ceiling_ratio)
        rep_max_reps = math.floor(37.0 - (36.0 * ceiling_load_kg / ceiling_1rm_kg))
        rep_max_reps = max(1, rep_max_reps)
        executed_reps = min(session.reps, rep_max_reps)
        focus_factor = {"volume": 0.92, "heavy": 1.05, "technique": 0.56, "fallback": 0.60, "test": 0.86}[session.focus]
        effort_factor = _clamp(0.68 + (session.target_rpe - 5.0) * 0.065, 0.65, 1.02)
        volume_units = (session.sets * executed_reps / 20.0) * load_ratio
        recovery_multiplier = self._recovery_multiplier(sleep, runtime)
        raw_stimulus = volume_units * focus_factor * effort_factor * location_factor * recovery_multiplier
        raw_stimulus *= self.variation.volume_tolerance
        if self._state.injury_recovery_days > 0 and self.config.enable_injury_system:
            raw_stimulus *= 0.28
        effective_stimulus = self._apply_weekly_stimulus_cap(raw_stimulus, runtime)
        fatigue_cost = volume_units * (0.72 + session.target_rpe * 0.038)
        fatigue_cost *= 1.0 + max(0.0, 6.5 - sleep) * 0.08
        if session.duration_min > 75:
            fatigue_cost *= 1.14
        if session.focus == "fallback":
            fatigue_cost *= 0.58
        if self.config.enable_delayed_adaptation:
            self._state.fitness_signal += effective_stimulus
            self._state.fatigue_signal += fatigue_cost
        else:
            # Ablation: adaptation is immediate and fatigue has no delayed
            # impulse. This removes the planning value of taper and spacing.
            self._state.immediate_gain += effective_stimulus

        irritation = (volume_units * 0.06) + max(0.0, load_ratio - 0.82) * 0.26
        irritation += max(0.0, session.target_rpe - 8.0) * 0.14
        irritation += max(0.0, 6.0 - sleep) * 0.09
        if session.focus == "fallback" or session.focus == "technique":
            irritation *= 0.55
        if session.focus == "heavy" and self._state.sleep_debt > 3.0:
            irritation += 0.11
        # The joint-proneness trait is latent, not a public label.  A
        # shoulder-prone athlete pays more for heavy/test work while an
        # elbow-prone athlete pays more for repeated volume and technique
        # work.  The pre-rolled pain stream adds small seed-specific noise
        # without allowing choices to reshuffle future randomness.
        if self.variation.injury_joint == "shoulder":
            joint_factor = 1.16 if session.focus in ("heavy", "test") else 0.94
        else:
            joint_factor = 1.16 if session.focus in ("volume", "technique") else 0.95
        pain_noise = 1.0 + self.noise.pain_noise[self._state.day_index]
        irritation *= joint_factor * pain_noise
        irritation /= self.variation.volume_tolerance
        if self.config.enable_injury_system:
            self._state.tendon_irritation = _clamp(self._state.tendon_irritation + irritation, 0.0, 5.0)
        else:
            self._state.tendon_irritation = 0.0
        stage = self._pain_stage()
        if self.config.enable_injury_system and stage >= 2 and self._state.injury_recovery_days == 0:
            self._state.injury_recovery_days = 42
        self._state.completed_sessions += 1
        runtime.completed_sessions += 1
        technique_learning = {
            "technique": 1.00,
            "volume": 0.80,
            "fallback": 0.45,
            "heavy": 0.25,
            "test": 0.18,
        }[session.focus]
        technique_rate = 1.0 - math.exp(-1.0 / max(1.0, self.config.technique_tau_sessions))
        self._state.technique = _clamp(
            self._state.technique
            + (0.96 - self._state.technique) * technique_rate * technique_learning,
            0.0,
            0.96,
        )
        self._state.motivation = _clamp(self._state.motivation + 0.012, 0.25, 0.95)
        self._state.session_history.append(
            {
                "week": self._state.week,
                "day": self._state.day_index % 7,
                "focus": session.focus,
                "load_kg": round(executed_load_kg, 2),
                "sets": session.sets,
                "reps": executed_reps,
                "prescribed_reps": session.reps,
                "rep_max_reps": rep_max_reps,
                "sleep_hours": sleep,
                "raw_stimulus": round(raw_stimulus, 5),
                "stimulus": round(effective_stimulus, 5),
            }
        )
        return {
            "status": "completed",
            "note": "completed",
            "focus": session.focus,
            "load_kg": round(executed_load_kg, 1),
            "reps": executed_reps,
            "stimulus": round(effective_stimulus, 3),
            "pain_stage": self._pain_stage(),
        }

    def _apply_weekly_stimulus_cap(self, raw_stimulus: float, runtime: _WeekRuntime) -> float:
        """Apply a deterministic diminishing-returns curve within one week."""
        raw_stimulus = max(0.0, raw_stimulus)
        cap = max(0.0, self.config.weekly_stimulus_cap)
        if cap == 0.0:
            return 0.0
        start = _clamp(self.config.weekly_stimulus_diminishing_start, 0.0, cap)

        def delivered(raw_total: float) -> float:
            if raw_total <= start:
                return raw_total
            tail = max(1e-9, cap - start)
            return start + tail * (1.0 - math.exp(-(raw_total - start) / tail))

        before = delivered(runtime.raw_stimulus)
        runtime.raw_stimulus += raw_stimulus
        after = delivered(runtime.raw_stimulus)
        runtime.weekly_stimulus = after
        return max(0.0, after - before)

    def _recovery_multiplier(self, sleep: float, runtime: _WeekRuntime) -> float:
        sleep_factor = _clamp(sleep / 7.2, 0.48, 1.10) if self.config.enable_sleep_system else 1.0
        household_penalty = self._state.household_strain * 0.18 if self.config.enable_household_system else 0.0
        stress_factor = _clamp(1.0 - household_penalty - self._state.work_strain * 0.08, 0.68, 1.0)
        illness_factor = 0.62 if self._state.illness_days > 0 else 1.0
        nutrition_factor = _clamp(self._state.nutrition_score, 0.55, 1.12)
        return _clamp(sleep_factor * stress_factor * illness_factor * nutrition_factor * self.variation.recovery_capacity, 0.35, 1.16)

    def _finish_week(self, runtime: _WeekRuntime) -> None:
        average_sleep = sum(runtime.sleep_hours) / max(1, len(runtime.sleep_hours))
        productive = runtime.completed_sessions >= 2 and average_sleep >= 5.5 and self._pain_stage() <= 1
        if productive:
            self._state.productive_weeks += 1
            self._state.productive_streak_weeks += 1
            if (
                self._state.productive_streak_weeks >= self.config.productive_streak_weeks_for_capacity_drift
                and self.config.capacity_drift_kg_per_productive_week > 0.0
            ):
                self._state.base_capacity_kg += self.config.capacity_drift_kg_per_productive_week
        else:
            self._state.productive_streak_weeks = 0
        # Pain is an executed-state metric, not a proxy for poor sleep. Count
        # each simulated day on which the pain ladder was active, including
        # days with good sleep and days where a session newly triggered pain.
        self._state.pain_days += runtime.pain_days

        # Nutrition now has a visible, bounded mass pathway.  Maintenance
        # support is centered near 0.80; sustained under-support loses mass,
        # while unusually strong support can add a small amount over time.
        level = self._state.nutrition_score
        mass_delta = (level - 0.80) * 0.22
        if level < 0.65:
            mass_delta -= 0.04
        self._state.last_body_mass_kg = self._state.body_mass_kg
        self._state.body_mass_kg = _clamp(self._state.body_mass_kg + mass_delta, 72.0, 110.0)
        if self.config.enable_household_system and self._state.body_mass_kg - 84.0 > 8.0:
            self._state.household_strain = _clamp(self._state.household_strain + 0.015, 0.0, 1.0)

        # A little household goodwill is recovered by a good week, but not by
        # a single heroic session.
        if self.config.enable_household_system:
            if runtime.completed_sessions == 0:
                self._state.household_strain = _clamp(self._state.household_strain + 0.06, 0.0, 1.0)
            elif runtime.completed_sessions >= 2 and runtime.action.life.partner_giveback_hours >= runtime.action.life.partner_coverage_hours:
                self._state.household_strain = _clamp(self._state.household_strain - 0.035, 0.0, 1.0)

        self._state.work_strain = _clamp(
            self._state.work_strain
            + self.calendar.week(self._state.week).time_pressure_min / 220.0
            + (0.045 if self._state.stretch_project_weeks > 0 else 0.0)
            - 0.025,
            0.0,
            1.0,
        )

        # Evaluate the hidden standardized-test protocol at selected weeks.
        # The test is a read-only projection: no fatigue, taper, or other
        # state is applied to the ongoing episode.
        if self._state.week in HIDDEN_STANDARDIZED_TEST_WEEKS:
            self._hidden_standardized_test_scores.append(self._standardized_test_capacity())

    def _make_week_outcome(self, week: int, runtime: _WeekRuntime) -> WeekOutcome:
        avg_sleep = round(sum(runtime.sleep_hours) / max(1, len(runtime.sleep_hours)), 2)
        completed = runtime.completed_sessions
        if completed >= 2:
            headline = f"{completed} sessions held together; the year is compounding."
        elif completed == 1:
            headline = "One session survived the week; protect the next window."
        else:
            headline = "No productive session landed; the next fallback matters."
        if self._pain_stage() >= 2:
            headline += " Pain is now limiting output."
        if self._state.invalid_reason:
            headline += " Budget insolvency has invalidated this episode."
        return WeekOutcome(
            week=week,
            planned_sessions=runtime.planned_sessions,
            completed_sessions=completed,
            fallback_sessions=runtime.fallback_sessions,
            missed_sessions=runtime.missed_sessions,
            average_sleep_hours=avg_sleep,
            estimated_1rm_kg=round(self._estimate_1rm(), 2),
            household_strain_band=self._household_band(),
            pain_band=self._pain_band(),
            headline=headline,
            interrupts=tuple(record["title"] for record in runtime.interrupt_records),
            session_failure_reasons=(
                tuple(runtime.session_failure_reasons)
                if self.config.expose_session_failure_reasons
                else None
            ),
        )

    def _true_capacity(self) -> float:
        mass_delta = self._state.body_mass_kg - 84.0
        if mass_delta <= 8.0:
            mass_effect = mass_delta * 0.34
        else:
            mass_effect = 2.72 + (mass_delta - 8.0) * 0.08
        technique_effect = (self._state.technique - self.variation.technique_start) * 9.0
        injury_effect = -1.9 if self.config.enable_injury_system and self._state.injury_recovery_days > 0 else 0.0
        stress_effect = -self._state.household_strain * 1.2 if self.config.enable_household_system else 0.0
        if self.config.enable_delayed_adaptation:
            adaptation_effect = (
                self._state.fitness_signal * self.config.fitness_to_strength_kg
                - self._state.fatigue_signal * self.config.fatigue_to_strength_kg
            )
        else:
            adaptation_effect = self._state.immediate_gain * self.config.fitness_to_strength_kg
        return max(
            55.0,
            self._state.base_capacity_kg
            + adaptation_effect
            + technique_effect
            + mass_effect
            + injury_effect
            + stress_effect,
        )

    def _estimate_1rm(self) -> float:
        if self._state.completed_sessions == 0 and self._state.week == 1:
            return self.config.starting_estimated_1rm_kg
        index = min(len(self.noise.estimate_noise) - 1, self._state.week)
        noise = self.noise.estimate_noise[index]
        return max(40.0, self._true_capacity() * (1.0 + noise))

    def _standardized_test_capacity(self) -> float:
        # The fixed protocol gives three quiet days before the test. Fitness
        # persists longer than fatigue, so planning still matters.
        base = self._true_capacity()
        if not self.config.enable_delayed_adaptation:
            return base
        fitness = self._state.fitness_signal * math.exp(-3.0 / self.config.fit_tau_days)
        fatigue = self._state.fatigue_signal * math.exp(-3.0 / self.config.fatigue_tau_days)
        current_fit = self._state.fitness_signal * self.config.fitness_to_strength_kg
        current_fatigue = self._state.fatigue_signal * self.config.fatigue_to_strength_kg
        return max(
            55.0,
            base
            - current_fit
            + current_fatigue
            + fitness * self.config.fitness_to_strength_kg
            - fatigue * self.config.fatigue_to_strength_kg,
        )

    def _pain_stage(self) -> int:
        if not self.config.enable_injury_system:
            return 0
        if self._state.injury_recovery_days > 0:
            return 4 if self._state.injury_recovery_days > 21 else 3
        if self._state.tendon_irritation >= 3.2:
            return 3
        if self._state.tendon_irritation >= 2.0:
            return 2
        if self._state.tendon_irritation >= 1.05:
            return 1
        return 0

    def _pain_band(self) -> str:
        stage = self._pain_stage()
        if stage == 0:
            return "none"
        if stage == 1:
            return "warning"
        if stage <= 3:
            return "limiting"
        return "recovery"

    def _household_band(self) -> str:
        return _band(self._state.household_strain, (0.25, 0.52, 0.78), ("low", "medium", "high", "critical"))

    def _work_band(self) -> str:
        return _band(self._state.work_strain, (0.28, 0.62), ("low", "medium", "high"))

    def _sleep_band(self) -> str:
        if not self._state.sleep_hours_history:
            return "okay"
        avg = sum(self._state.sleep_hours_history[-7:]) / min(7, len(self._state.sleep_hours_history))
        return _band(avg, (5.0, 6.0, 7.0), ("depleted", "strained", "okay", "good"))

    def _energy_band(self) -> str:
        energy = 0.76 - self._state.sleep_debt * 0.035 - self._state.fatigue_signal * 0.018 - self._state.household_strain * 0.12
        if self._state.illness_days > 0:
            energy -= 0.25
        if energy < 0.38:
            return "low"
        if energy < 0.68:
            return "medium"
        return "high"

    def _soreness_band(self) -> str:
        signal = self._state.fatigue_signal + self._state.tendon_irritation * 0.7
        return _band(signal, (1.5, 3.5, 6.0), ("none", "mild", "moderate", "high"))

    def _illness_status(self) -> str:
        if self._state.illness_days > 0:
            return "active"
        if self._state.illness_days == 0 and self._state.sleep_debt > 2.8 and self._state.week > 1:
            return "recovering"
        if self.calendar.week(min(self._state.week, 52)).illness_exposure > 0.3:
            return "exposed"
        return "clear"

    def _body_mass_trend(self) -> str:
        delta = self._state.body_mass_kg - self._state.last_body_mass_kg
        if delta < -0.025:
            return "falling"
        if delta > 0.025:
            return "rising"
        return "stable"

    def _render_observation(self) -> WeekObservation:
        week = min(self._state.week, self.config.weeks)
        event = self.calendar.week(week)
        upcoming: list[PlannedEvent] = []
        for candidate_week in range(week, min(52, week + 5) + 1):
            for known in self.calendar.week(candidate_week).known_events:
                lead = int(known["lead_weeks"])
                if candidate_week == week or candidate_week - week <= lead:
                    upcoming.append(
                        PlannedEvent(
                            week=candidate_week,
                            title=str(known["title"]),
                            detail=str(known["detail"]),
                            lead_weeks=lead,
                        )
                    )
        time_bands: list[str] = []
        for day in range(7):
            if event.time_pressure_min >= 25 or self._state.household_strain > 0.72:
                time_bands.append("tight")
            elif day in event.open_days:
                time_bands.append("open")
            else:
                time_bands.append("normal")
        recent: list[RecentWeek] = []
        for summary in self._state.week_history[-4:]:
            recent.append(
                RecentWeek(
                    week=int(summary["week"]),
                    planned_sessions=int(summary["planned_sessions"]),
                    completed_sessions=int(summary["completed_sessions"]),
                    fallback_sessions=int(summary["fallback_sessions"]),
                    average_sleep_hours=float(summary["average_sleep_hours"]),
                    estimated_1rm_kg=float(summary["estimated_1rm_kg"]),
                    headline=str(summary["headline"]),
                )
            )
        equipment = ["commercial_gym"]
        if self._state.home_gym:
            equipment.append("home_rack")
        return WeekObservation(
            episode_week=week,
            total_weeks=self.config.weeks,
            baby_age_months=round(6.0 + (week - 1) / 4.345, 2),
            estimated_1rm_kg=round(self._estimate_1rm(), 2),
            estimated_1rm_low_kg=round(self._estimate_1rm() * 0.95, 2),
            estimated_1rm_high_kg=round(self._estimate_1rm() * 1.05, 2),
            recent_sessions=min(5, len([s for s in self._state.session_history if s["week"] == max(1, week - 1)])),
            sleep_band=self._sleep_band(),  # type: ignore[arg-type]
            energy_band=self._energy_band(),  # type: ignore[arg-type]
            soreness_band=self._soreness_band(),  # type: ignore[arg-type]
            pain_band=self._pain_band(),  # type: ignore[arg-type]
            illness_status=self._illness_status(),  # type: ignore[arg-type]
            nutrition_band=self._nutrition_band(self._state.nutrition_score),  # type: ignore[arg-type]
            body_mass_kg=round(self._state.body_mass_kg, 2),
            body_mass_trend=self._body_mass_trend(),  # type: ignore[arg-type]
            budget_available_cents=max(0, self._state.cash_cents),
            current_month_spend_cents=max(0, self._state.current_month_spend_cents),
            weekly_time_budget_minutes=max(0, self.config.weekly_time_budget_minutes),
            equipment=equipment,
            household_strain_band=self._household_band(),  # type: ignore[arg-type]
            work_strain_band=self._work_band(),  # type: ignore[arg-type]
            available_time_bands=time_bands,  # type: ignore[arg-type]
            this_week_signals=self._this_week_signals(event),
            known_obligations=["full-time job", "partner's full-time work", "infant care", "household chores"],
            upcoming_known_events=upcoming,
            recent_weeks=recent,
            last_interrupt=self._state.last_interrupt,
        )

    def _this_week_signals(self, event: Any) -> list[str]:
        signals: list[str] = []
        if event.sleep_pressure >= 0.65:
            signals.append("sleep is likely to be less predictable")
        if event.illness_exposure >= 0.3:
            signals.append("daycare exposure is elevated")
        if event.gym_crowding > 0:
            signals.append("gym sessions may take longer")
        if event.time_pressure_min:
            signals.append("work or travel compresses flexible time")
        if self._state.injury_recovery_days > 0:
            signals.append("tissue recovery is still limiting output")
        if self._sleep_band() in ("depleted", "strained"):
            signals.append("recent sleep has been uneven")
        if self._state.stretch_project_weeks > 0:
            signals.append("stretch project is consuming flexible work time")
        if not signals:
            signals.append("a normal week is available if protected")
        return signals
