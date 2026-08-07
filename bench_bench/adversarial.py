"""Deterministic adversarial search over legal public action fields.

The search deliberately operates on WeekAction fields rather than a registry
of hand-written exploit policies.  Candidate actions are made schema-valid,
fit to the visible time budget, and then checked again by the engine before a
candidate receives a score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
import random
from statistics import fmean, stdev
from typing import Any, Iterable

from .config import SimConfig
from .engine import BenchEnvironment
from .policies import _open_days, _rules, _session
from .provenance import engine_config_hash
from .scoring import counted_score, constraint_violations
from .schemas import InterruptObservation, LifeAllocation, ReactiveAction, SessionPlan, StandingRules, WeekAction, WeekObservation


FOCUS_VALUES = ("volume", "heavy", "technique", "fallback", "test")
LOCATION_VALUES = ("gym", "home", "auto")
SLEEP_VALUES = ("none", "standard", "strong")
RULE_VALUES = ("fallback", "skip", "reduce")
ILLNESS_VALUES = ("protect_recovery", "fallback", "skip")
PURCHASE_VALUES = ("home_gym", "recurring_childcare", "meal_prep_subscription")
BOUNDARY_LOAD_RATIOS = (0.0, 0.05, 0.20, 0.34, 0.35, 0.50, 0.78, 0.80, 0.95, 1.0, 1.2)

RELEASE_ABUSE_THRESHOLDS = {
    "mean_pain_days": 14.0,
    "mean_household_strain": 0.95,
    "fallback_load_ratio": 0.78,
    "high_rep_threshold": 12,
    "high_rep_load_ratio": 0.80,
    "high_volume_reps_sets": 96,
}
HUMAN_REVIEW_MARGIN_KG = 5.0


@dataclass(frozen=True)
class WeekTemplate:
    """A repeatable per-week public action structure.

    Each tuple is a per-session pattern inside the week.  Patterns can mix
    focuses and boundary loads; the policy cycles the template across weeks so
    the search can discover structured programs rather than one scalar action
    copied 52 times.
    """

    session_count: int = 3
    focuses: tuple[str, ...] = ("volume",)
    sets: tuple[int, ...] = (4,)
    reps: tuple[int, ...] = (5,)
    load_ratios: tuple[float, ...] = (0.80,)
    durations: tuple[int, ...] = (45,)
    target_rpes: tuple[float, ...] = (7.0,)
    location: str = "auto"


def _cycle_values(values: tuple[Any, ...], length: int, default: Any) -> tuple[Any, ...]:
    values = values or (default,)
    return tuple(values[index % len(values)] for index in range(max(1, length)))


def _normalize_template(template: WeekTemplate) -> WeekTemplate:
    raw_focuses = tuple(template.focuses) or ("volume",)
    pattern_length = min(
        5,
        max(
            1,
            len(raw_focuses),
            len(tuple(template.sets)),
            len(tuple(template.reps)),
            len(tuple(template.load_ratios)),
            len(tuple(template.durations)),
            len(tuple(template.target_rpes)),
        ),
    )
    focuses = _cycle_values(raw_focuses, pattern_length, "volume")
    focuses = tuple(focus if focus in FOCUS_VALUES else "volume" for focus in focuses)
    sets_raw = _cycle_values(tuple(template.sets), pattern_length, 4)
    reps_raw = _cycle_values(tuple(template.reps), pattern_length, 5)
    ratios_raw = _cycle_values(tuple(template.load_ratios), pattern_length, 0.80)
    durations_raw = _cycle_values(tuple(template.durations), pattern_length, 45)
    rpes_raw = _cycle_values(tuple(template.target_rpes), pattern_length, 7.0)
    sets: list[int] = []
    reps: list[int] = []
    durations: list[int] = []
    for focus, raw_sets, raw_reps, raw_duration in zip(focuses, sets_raw, reps_raw, durations_raw):
        current_sets = min(8, max(1, int(raw_sets)))
        current_reps = min(15, max(1, int(raw_reps)))
        current_duration = min(120, max(10, int(raw_duration)))
        if focus == "fallback":
            current_sets = min(3, current_sets)
            current_reps = min(6, current_reps)
            current_duration = min(25, current_duration)
        elif focus == "test":
            current_sets = 1
            current_reps = 1
        sets.append(current_sets)
        reps.append(current_reps)
        durations.append(current_duration)
    return WeekTemplate(
        session_count=min(5, max(0, int(template.session_count))),
        focuses=focuses,
        sets=tuple(sets),
        reps=tuple(reps),
        load_ratios=tuple(min(1.20, max(0.0, float(value))) for value in _cycle_values(tuple(template.load_ratios), pattern_length, 0.80)),
        durations=tuple(durations),
        target_rpes=tuple(min(10.0, max(5.0, float(value))) for value in _cycle_values(tuple(template.target_rpes), pattern_length, 7.0)),
        location=template.location if template.location in LOCATION_VALUES else "auto",
    )


@dataclass(frozen=True)
class AdversarialGenome:
    """A compact policy genome whose fields map to public action fields."""

    session_count: int = 3
    focus: str = "volume"
    sets: int = 4
    reps: int = 5
    load_ratio: float = 0.80
    progression_per_week: float = 0.0
    duration_min: int = 45
    target_rpe: float = 7.0
    location: str = "auto"
    meal_prep_hours: float = 2.0
    childcare_hours: float = 0.0
    meal_support_spend_cents: int = 0
    childcare_spend_cents: int = 0
    chore_delegation_hours: float = 0.0
    partner_coverage_hours: float = 2.0
    partner_giveback_hours: float = 2.0
    sleep_protection: str = "standard"
    on_sleep_below_5h: str = "fallback"
    on_pain_warning: str = "reduce"
    on_illness: str = "protect_recovery"
    buy_home_rack: bool = False
    purchase_week: int = 8
    skip_when_strained: bool = False
    final_week_test: bool = False
    final_test_ratio: float = 1.05
    week_templates: tuple[WeekTemplate, ...] = ()
    purchase_sequence: tuple[str, ...] = ()
    purchase_spacing_weeks: int = 4

    def normalized(self) -> "AdversarialGenome":
        focus = self.focus if self.focus in FOCUS_VALUES else "volume"
        location = self.location if self.location in LOCATION_VALUES else "auto"
        if focus == "fallback":
            sets = min(3, max(1, self.sets))
            reps = min(6, max(1, self.reps))
            duration = min(25, max(10, self.duration_min))
        elif focus == "test":
            sets = 1
            reps = 1
            duration = min(120, max(10, self.duration_min))
        else:
            sets = min(8, max(1, self.sets))
            reps = min(15, max(1, self.reps))
            duration = min(120, max(10, self.duration_min))
        return replace(
            self,
            session_count=min(5, max(0, self.session_count)),
            focus=focus,
            sets=sets,
            reps=reps,
            load_ratio=min(1.20, max(0.0, self.load_ratio)),
            progression_per_week=min(0.02, max(0.0, self.progression_per_week)),
            duration_min=duration,
            target_rpe=min(10.0, max(5.0, self.target_rpe)),
            location=location,
            meal_prep_hours=min(10.0, max(0.0, self.meal_prep_hours)),
            childcare_hours=min(24.0, max(0.0, self.childcare_hours)),
            meal_support_spend_cents=min(25_000, max(0, self.meal_support_spend_cents)),
            childcare_spend_cents=min(25_000, max(0, self.childcare_spend_cents)),
            chore_delegation_hours=min(12.0, max(0.0, self.chore_delegation_hours)),
            partner_coverage_hours=min(16.0, max(0.0, self.partner_coverage_hours)),
            partner_giveback_hours=min(16.0, max(0.0, self.partner_giveback_hours)),
            sleep_protection=self.sleep_protection if self.sleep_protection in SLEEP_VALUES else "standard",
            on_sleep_below_5h=self.on_sleep_below_5h if self.on_sleep_below_5h in RULE_VALUES else "fallback",
            on_pain_warning=self.on_pain_warning if self.on_pain_warning in RULE_VALUES else "reduce",
            on_illness=self.on_illness if self.on_illness in ILLNESS_VALUES else "protect_recovery",
            purchase_week=min(52, max(1, self.purchase_week)),
            final_test_ratio=min(1.20, max(0.80, self.final_test_ratio)),
            week_templates=tuple(_normalize_template(template) for template in tuple(self.week_templates)[:8]),
            purchase_sequence=tuple(
                purchase for purchase in tuple(dict.fromkeys(self.purchase_sequence)) if purchase in PURCHASE_VALUES
            )[:3],
            purchase_spacing_weeks=min(12, max(0, int(self.purchase_spacing_weeks))),
        )

    def as_dict(self) -> dict[str, Any]:
        def jsonable(value: Any) -> Any:
            if isinstance(value, tuple):
                return [jsonable(item) for item in value]
            if isinstance(value, dict):
                return {key: jsonable(item) for key, item in value.items()}
            return value

        return jsonable(asdict(self.normalized()))


@dataclass(frozen=True)
class CandidateEpisode:
    seed: int
    final_1rm_kg: float | None
    completed_sessions: int
    pain_days: int
    household_strain: float
    fallback_actions: int
    invalid_reason: str | None
    constraint_violations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["constraint_violations"] = list(self.constraint_violations)
        values["raw_final_1rm_kg"] = self.final_1rm_kg
        values["counted_final_1rm_kg"] = counted_score(
            self.final_1rm_kg,
            invalid_reason=self.invalid_reason,
            violations=self.constraint_violations,
        )
        return values


@dataclass(frozen=True)
class CandidateEvaluation:
    name: str
    genome: AdversarialGenome
    episodes: tuple[CandidateEpisode, ...]
    search_mean_final_1rm_kg: float | None
    mean_final_1rm_kg: float | None
    seed_std_kg: float | None
    min_final_1rm_kg: float | None
    max_final_1rm_kg: float | None
    invalid_episodes: int
    mean_pain_days: float | None
    mean_household_strain: float | None
    mean_fallback_actions: float | None
    raw_mean_final_1rm_kg: float | None = None
    raw_seed_std_kg: float | None = None
    counted_episodes: int = 0
    constraint_violating_episodes: int = 0
    constraint_violation_counts: dict[str, int] | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "policy": self.name,
            "episodes": self.counted_episodes,
            "mean_final_1rm_kg": self.mean_final_1rm_kg,
            "seed_std_kg": self.seed_std_kg,
            "min_final_1rm_kg": self.min_final_1rm_kg,
            "max_final_1rm_kg": self.max_final_1rm_kg,
            "raw_mean_final_1rm_kg": self.raw_mean_final_1rm_kg,
            "raw_seed_std_kg": self.raw_seed_std_kg,
            "mean_pain_days": self.mean_pain_days,
            "mean_household_strain": self.mean_household_strain,
            "mean_fallback_actions": self.mean_fallback_actions,
            "invalid_episodes": self.invalid_episodes,
            "constraint_violating_episodes": self.constraint_violating_episodes,
            "constraint_violation_counts": self.constraint_violation_counts or {},
        }


def _random_genome(rng: random.Random) -> AdversarialGenome:
    def random_ratio() -> float:
        return round(rng.choice(BOUNDARY_LOAD_RATIOS) if rng.random() < 0.45 else rng.uniform(0.0, 1.20), 3)

    def random_template() -> WeekTemplate:
        count = rng.randrange(0, 6)
        pattern_length = rng.randrange(1, min(5, max(1, count)) + 1)
        focuses = [rng.choice(FOCUS_VALUES) for _ in range(pattern_length)]
        if pattern_length > 1 and len(set(focuses)) == 1 and rng.random() < 0.75:
            focuses[-1] = rng.choice(tuple(focus for focus in FOCUS_VALUES if focus != focuses[0]))
        return WeekTemplate(
            session_count=count,
            focuses=tuple(focuses),
            sets=tuple(rng.randrange(1, 9) for _ in range(pattern_length)),
            reps=tuple(rng.randrange(1, 16) for _ in range(pattern_length)),
            load_ratios=tuple(random_ratio() for _ in range(pattern_length)),
            durations=tuple(rng.choice((10, 20, 25, 30, 35, 45, 55, 65, 75, 90, 120)) for _ in range(pattern_length)),
            target_rpes=tuple(round(rng.uniform(5.0, 10.0), 1) for _ in range(pattern_length)),
            location=rng.choice(LOCATION_VALUES),
        )

    focus = rng.choice(FOCUS_VALUES)
    sequence = list(rng.sample(PURCHASE_VALUES, rng.randrange(0, 4)))
    templates = tuple(random_template() for _ in range(rng.choice((0, 0, 2, 3, 4))))
    return AdversarialGenome(
        session_count=rng.randrange(0, 6),
        focus=focus,
        sets=rng.randrange(1, 9),
        reps=rng.randrange(1, 16),
        load_ratio=round(rng.choice(BOUNDARY_LOAD_RATIOS) if rng.random() < 0.45 else rng.uniform(0.0, 1.20), 3),
        progression_per_week=round(rng.uniform(0.0, 0.014), 4),
        duration_min=rng.choice((10, 20, 25, 30, 35, 45, 55, 65, 75, 90, 120)),
        target_rpe=round(rng.uniform(5.0, 10.0), 1),
        location=rng.choice(LOCATION_VALUES),
        meal_prep_hours=rng.choice((0.0, 1.0, 2.0, 3.0, 4.0)),
        childcare_hours=rng.choice((0.0, 1.0, 2.0, 4.0)),
        meal_support_spend_cents=rng.choice((0, 1_200, 3_000)),
        childcare_spend_cents=rng.choice((0, 2_000, 5_000)),
        chore_delegation_hours=rng.choice((0.0, 1.0, 2.0, 4.0)),
        partner_coverage_hours=rng.choice((0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0)),
        partner_giveback_hours=rng.choice((0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0)),
        sleep_protection=rng.choice(SLEEP_VALUES),
        on_sleep_below_5h=rng.choice(RULE_VALUES),
        on_pain_warning=rng.choice(RULE_VALUES),
        on_illness=rng.choice(ILLNESS_VALUES),
        buy_home_rack="home_gym" in sequence or rng.random() < 0.20,
        purchase_week=rng.randrange(6, 21),
        skip_when_strained=rng.random() < 0.35,
        final_week_test=rng.random() < 0.35,
        final_test_ratio=round(rng.uniform(0.85, 1.18), 3),
        week_templates=templates,
        purchase_sequence=tuple(sequence),
        purchase_spacing_weeks=rng.randrange(0, 9),
    ).normalized()


def _mutate(genome: AdversarialGenome, rng: random.Random) -> AdversarialGenome:
    field = rng.choice(
        (
            "session_count", "focus", "sets", "reps", "load_ratio", "progression_per_week",
            "duration_min", "target_rpe", "location", "meal_prep_hours", "childcare_hours",
            "meal_support_spend_cents", "childcare_spend_cents", "chore_delegation_hours",
            "partner_coverage_hours", "partner_giveback_hours", "sleep_protection",
            "on_sleep_below_5h", "on_pain_warning", "on_illness", "buy_home_rack",
            "purchase_week", "skip_when_strained", "final_week_test", "final_test_ratio",
            "week_templates", "purchase_sequence", "purchase_spacing_weeks",
        )
    )
    updates: dict[str, Any] = {}
    if field == "session_count":
        updates[field] = rng.randrange(0, 6)
    elif field == "focus":
        updates[field] = rng.choice(FOCUS_VALUES)
    elif field == "sets":
        updates[field] = rng.randrange(1, 9)
    elif field == "reps":
        updates[field] = rng.randrange(1, 16)
    elif field == "load_ratio":
        updates[field] = round(rng.choice(BOUNDARY_LOAD_RATIOS) if rng.random() < 0.55 else rng.uniform(0.0, 1.20), 3)
    elif field == "progression_per_week":
        updates[field] = round(rng.uniform(0.0, 0.02), 4)
    elif field == "duration_min":
        updates[field] = rng.choice((10, 20, 25, 30, 35, 45, 55, 65, 75, 90, 120))
    elif field == "target_rpe":
        updates[field] = round(rng.uniform(5.0, 10.0), 1)
    elif field == "location":
        updates[field] = rng.choice(LOCATION_VALUES)
    elif field == "meal_prep_hours":
        updates[field] = rng.choice((0.0, 1.0, 2.0, 3.0, 4.0))
    elif field == "childcare_hours":
        updates[field] = rng.choice((0.0, 1.0, 2.0, 4.0))
    elif field == "meal_support_spend_cents":
        updates[field] = rng.choice((0, 1_200, 3_000))
    elif field == "childcare_spend_cents":
        updates[field] = rng.choice((0, 2_000, 5_000))
    elif field == "chore_delegation_hours":
        updates[field] = rng.choice((0.0, 1.0, 2.0, 4.0))
    elif field in {"partner_coverage_hours", "partner_giveback_hours"}:
        updates[field] = rng.choice((0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0))
    elif field == "sleep_protection":
        updates[field] = rng.choice(SLEEP_VALUES)
    elif field in {"on_sleep_below_5h", "on_pain_warning"}:
        updates[field] = rng.choice(RULE_VALUES)
    elif field == "on_illness":
        updates[field] = rng.choice(ILLNESS_VALUES)
    elif field == "buy_home_rack":
        updates[field] = rng.random() < 0.5
    elif field == "purchase_week":
        updates[field] = rng.randrange(6, 21)
    elif field == "week_templates":
        candidate = _random_genome(rng)
        if genome.week_templates and rng.random() < 0.65:
            templates = list(genome.week_templates)
            templates[rng.randrange(len(templates))] = candidate.week_templates[0] if candidate.week_templates else WeekTemplate()
            updates[field] = tuple(templates)
        else:
            updates[field] = tuple(candidate.week_templates)
    elif field == "purchase_sequence":
        updates[field] = tuple(rng.sample(PURCHASE_VALUES, rng.randrange(0, 4)))
    elif field == "purchase_spacing_weeks":
        updates[field] = rng.randrange(0, 13)
    elif field in {"skip_when_strained", "final_week_test"}:
        updates[field] = rng.random() < 0.5
    else:
        updates[field] = round(rng.uniform(0.80, 1.20), 3)
    return replace(genome, **updates).normalized()


class AdversarialPolicy:
    def __init__(self, genome: AdversarialGenome) -> None:
        self.genome = genome.normalized()
        self.purchased: set[str] = set()

    def _conservative_minutes(self, observation: WeekObservation, sessions: list[SessionPlan], life: LifeAllocation) -> int:
        overhead = {"gym": 26, "home": 10, "hotel": 20}
        training = sum(session.duration_min + overhead[session.location] for session in sessions)
        life_minutes = 60.0 * (
            life.meal_prep_hours
            + life.childcare_hours
            + life.chore_delegation_hours
            + life.partner_coverage_hours
            + life.partner_giveback_hours
        )
        external = 240 if any(
            event.week == observation.episode_week and event.title == "grandparents visit"
            for event in observation.upcoming_known_events
        ) else 0
        return math.ceil(training + life_minutes + external)

    def _legalize(self, observation: WeekObservation, sessions: list[SessionPlan], life: LifeAllocation, rules: StandingRules) -> WeekAction:
        budget = max(0, observation.weekly_time_budget_minutes)
        working_sessions = list(sessions)
        working_life = life
        action = WeekAction(sessions=working_sessions, life=working_life, rules=rules)
        while self._conservative_minutes(observation, working_sessions, working_life) > budget:
            reduced = False
            for field in (
                "partner_giveback_hours", "partner_coverage_hours", "chore_delegation_hours",
                "childcare_hours", "meal_prep_hours",
            ):
                value = float(getattr(working_life, field))
                if value > 0:
                    working_life = working_life.model_copy(update={field: max(0.0, value - 0.5)})
                    reduced = True
                    break
            if not reduced:
                if working_sessions:
                    working_sessions.pop()
                    reduced = True
                else:
                    break
            action = WeekAction(sessions=working_sessions, life=working_life, rules=rules)
        return action

    def action(self, observation: WeekObservation) -> WeekAction:
        genome = self.genome
        purchases: list[str] = []
        meal_spend = genome.meal_support_spend_cents
        childcare_spend = genome.childcare_spend_cents
        if observation.budget_available_cents < meal_spend + childcare_spend:
            meal_spend = 0
            childcare_spend = 0
        has_home = "home_rack" in observation.equipment or "home_gym" in self.purchased
        if has_home:
            self.purchased.add("home_gym")
        purchase_sequence = genome.purchase_sequence
        if not purchase_sequence and genome.buy_home_rack:
            purchase_sequence = ("home_gym",)
        purchase_costs = {
            "home_gym": 60_000,
            "recurring_childcare": 7_500,
            "meal_prep_subscription": 3_000,
        }
        shock_reserve = 4_500 if any(
            event.week == observation.episode_week and event.title == "unplanned household pressure"
            for event in observation.upcoming_known_events
        ) else 0
        available_for_purchase = observation.budget_available_cents - meal_spend - childcare_spend - shock_reserve
        for index, purchase in enumerate(purchase_sequence):
            if purchase in self.purchased or (purchase == "home_gym" and has_home):
                continue
            if any(previous not in self.purchased for previous in purchase_sequence[:index]):
                break
            due_week = genome.purchase_week + index * genome.purchase_spacing_weeks
            if observation.episode_week < due_week:
                break
            if available_for_purchase >= purchase_costs[purchase]:
                purchases.append(purchase)
                self.purchased.add(purchase)
                available_for_purchase -= purchase_costs[purchase]
                if purchase == "home_gym":
                    has_home = True
            break
        skip_this_week = genome.skip_when_strained and (
            observation.sleep_band == "depleted"
            or observation.energy_band == "low"
            or observation.household_strain_band in ("high", "critical")
        )
        count = 0 if skip_this_week else genome.session_count
        template = (
            genome.week_templates[(observation.episode_week - 1) % len(genome.week_templates)]
            if genome.week_templates
            else None
        )
        if template is not None and not skip_this_week:
            count = template.session_count
        focus = genome.focus
        load_ratio = genome.load_ratio + genome.progression_per_week * max(0, observation.episode_week - 1)
        duration = genome.duration_min
        location_name = genome.location
        if genome.final_week_test and observation.episode_week == observation.total_weeks:
            template = None
            count = min(1, max(0, count)) or 1
            focus = "test"
            load_ratio = genome.final_test_ratio
            duration = max(30, duration)
            location_name = "gym"
        location = "home" if location_name == "home" and has_home else "gym"
        days = _open_days(observation, count)
        sessions: list[SessionPlan] = []
        for index, day in enumerate(days):
            pattern_index = index % len(template.focuses) if template is not None else 0
            session_focus = template.focuses[pattern_index] if template is not None else focus
            reps = template.reps[pattern_index] if template is not None else genome.reps
            sets = template.sets[pattern_index] if template is not None else genome.sets
            session_duration = template.durations[pattern_index] if template is not None else duration
            session_rpe = template.target_rpes[pattern_index] if template is not None else genome.target_rpe
            session_ratio = template.load_ratios[pattern_index] if template is not None else load_ratio
            session_location_name = template.location if template is not None else location
            session_location = "home" if session_location_name == "home" and has_home else "gym"
            if session_focus == "fallback":
                sets = min(3, sets)
                reps = min(6, reps)
                session_duration = min(25, session_duration)
            elif session_focus == "test":
                sets = 1
                reps = 1
            load = min(249.0, max(0.0, observation.estimated_1rm_kg * session_ratio))
            sessions.append(
                _session(
                    day,
                    location=session_location,
                    focus=session_focus,
                    sets=sets,
                    reps=reps,
                    load=load,
                    duration=session_duration,
                    rpe=session_rpe,
                )
            )
        life = LifeAllocation(
            meal_prep_hours=genome.meal_prep_hours,
            meal_support_spend_cents=meal_spend,
            childcare_hours=genome.childcare_hours,
            childcare_spend_cents=childcare_spend,
            chore_delegation_hours=genome.chore_delegation_hours,
            chore_delegation_spend_cents=0,
            partner_coverage_hours=genome.partner_coverage_hours,
            partner_giveback_hours=genome.partner_giveback_hours,
            sleep_protection=genome.sleep_protection,
            purchases=purchases,
        )
        rules = _rules(
            sleep=genome.on_sleep_below_5h,
            pain=genome.on_pain_warning,
            illness=genome.on_illness,
        )
        return self._legalize(observation, sessions, life, rules)

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        if observation.severity == "high":
            return ReactiveAction(response="protect_recovery", cancel_session_days=[observation.day])
        return ReactiveAction(response="protect_recovery", fallback_session_days=[observation.day])


def _regression_genomes() -> tuple[tuple[str, AdversarialGenome], ...]:
    base = AdversarialGenome(
        session_count=5,
        load_ratio=0.95,
        duration_min=45,
        target_rpe=8.0,
        meal_prep_hours=0.0,
        childcare_hours=0.0,
        chore_delegation_hours=0.0,
        partner_coverage_hours=0.0,
        partner_giveback_hours=0.0,
        sleep_protection="standard",
        buy_home_rack=False,
    )
    return (
        ("regression-volume-stacking", replace(base, focus="volume", sets=8, reps=15)),
        ("regression-compressed-fallback", replace(base, focus="fallback", sets=3, reps=6, duration_min=25)),
        ("regression-volume-8x4", replace(base, focus="volume", sets=8, reps=4)),
        (
            "regression-mixed-focus-week",
            replace(
                base,
                week_templates=(
                    WeekTemplate(
                        session_count=5,
                        focuses=("technique", "volume", "heavy", "fallback", "volume"),
                        sets=(3, 8, 3, 3, 8),
                        reps=(8, 4, 3, 6, 4),
                        load_ratios=(0.55, 0.78, 0.95, 0.55, 0.78),
                        durations=(45, 75, 45, 25, 75),
                        target_rpes=(6.5, 8.0, 8.5, 6.0, 8.0),
                        location="gym",
                    ),
                ),
            ),
        ),
        (
            "regression-zero-load-boundary",
            replace(
                base,
                week_templates=(
                    WeekTemplate(
                        session_count=3,
                        focuses=("volume", "technique", "volume"),
                        sets=(3, 3, 3),
                        reps=(10, 10, 10),
                        load_ratios=(0.0, 0.0, 0.0),
                        durations=(10, 10, 10),
                        target_rpes=(7.0, 7.0, 7.0),
                        location="home",
                    ),
                ),
            ),
        ),
        (
            "regression-purchase-ordering",
            replace(
                base,
                purchase_sequence=("meal_prep_subscription", "home_gym", "recurring_childcare"),
                purchase_week=8,
                purchase_spacing_weeks=4,
            ),
        ),
    )


def _evaluate_genome(name: str, genome: AdversarialGenome, seeds: list[int], config: SimConfig) -> CandidateEvaluation:
    episodes: list[CandidateEpisode] = []
    for seed in seeds:
        env = BenchEnvironment(seed, config)
        policy = AdversarialPolicy(genome)
        invalid_reason: str | None = None
        while not env.done:
            action = policy.action(env.observation)
            validation = env.validate_action(action)
            if validation.errors:
                invalid_reason = "; ".join(validation.errors)
                break
            env.submit_week(action, reactive_responder=policy.reactive)
        if invalid_reason is not None:
            episodes.append(CandidateEpisode(seed, None, 0, 0, 0.0, 0, invalid_reason))
            continue
        result = env.final_result()
        week_records = [record for record in env.log_records if record.get("type") == "week"]
        episodes.append(
            CandidateEpisode(
                seed=seed,
                final_1rm_kg=result.final_1rm_kg,
                completed_sessions=result.completed_sessions,
                pain_days=result.pain_days,
                household_strain=result.household_strain,
                fallback_actions=sum(1 for record in week_records if record["validation"]["fallback_used"]),
                invalid_reason=result.invalid_reason,
                constraint_violations=constraint_violations(pain_days=result.pain_days),
            )
        )
    structural_valid = [
        episode for episode in episodes
        if episode.final_1rm_kg is not None and episode.invalid_reason is None
    ]
    valid = [episode for episode in structural_valid if not episode.constraint_violations]
    invalid = len(episodes) - len(structural_valid)
    violation_counts: dict[str, int] = {}
    for episode in structural_valid:
        for violation in episode.constraint_violations:
            violation_counts[violation] = violation_counts.get(violation, 0) + 1
    raw_scores = [float(episode.final_1rm_kg) for episode in structural_valid if episode.final_1rm_kg is not None]
    if not valid:
        return CandidateEvaluation(
            name=name,
            genome=genome,
            episodes=tuple(episodes),
            search_mean_final_1rm_kg=None,
            mean_final_1rm_kg=None,
            seed_std_kg=None,
            min_final_1rm_kg=None,
            max_final_1rm_kg=None,
            invalid_episodes=invalid,
            mean_pain_days=round(fmean(episode.pain_days for episode in structural_valid), 4) if structural_valid else None,
            mean_household_strain=round(fmean(episode.household_strain for episode in structural_valid), 4) if structural_valid else None,
            mean_fallback_actions=round(fmean(episode.fallback_actions for episode in structural_valid), 4) if structural_valid else None,
            raw_mean_final_1rm_kg=round(fmean(raw_scores), 4) if raw_scores else None,
            raw_seed_std_kg=round(stdev(raw_scores), 4) if len(raw_scores) > 1 else (0.0 if raw_scores else None),
            counted_episodes=0,
            constraint_violating_episodes=len(structural_valid),
            constraint_violation_counts=violation_counts,
        )
    scores = [float(episode.final_1rm_kg) for episode in valid]
    return CandidateEvaluation(
        name=name,
        genome=genome,
        episodes=tuple(episodes),
        search_mean_final_1rm_kg=None,
        mean_final_1rm_kg=round(fmean(scores), 4),
        seed_std_kg=round(stdev(scores), 4) if len(scores) > 1 else 0.0,
        min_final_1rm_kg=round(min(scores), 4),
        max_final_1rm_kg=round(max(scores), 4),
        invalid_episodes=invalid,
        mean_pain_days=round(fmean(episode.pain_days for episode in structural_valid), 4),
        mean_household_strain=round(fmean(episode.household_strain for episode in structural_valid), 4),
        mean_fallback_actions=round(fmean(episode.fallback_actions for episode in structural_valid), 4),
        raw_mean_final_1rm_kg=round(fmean(raw_scores), 4),
        raw_seed_std_kg=round(stdev(raw_scores), 4) if len(raw_scores) > 1 else 0.0,
        counted_episodes=len(valid),
        constraint_violating_episodes=len(structural_valid) - len(valid),
        constraint_violation_counts=violation_counts,
    )


def _rank(evaluation: CandidateEvaluation) -> tuple[float, float]:
    if evaluation.invalid_episodes or evaluation.constraint_violating_episodes or evaluation.mean_final_1rm_kg is None:
        return (-float("inf"), -float("inf"))
    return (evaluation.mean_final_1rm_kg, -(evaluation.mean_pain_days or 0.0))


def _physical_implausibility_reasons(genome: AdversarialGenome, config: SimConfig) -> list[str]:
    """Return public-action signatures outside the physical plausibility envelope."""
    genome = genome.normalized()
    reasons: list[str] = []
    specs: list[tuple[str, int, int, float]] = []
    if genome.week_templates:
        for template in genome.week_templates:
            for focus, sets, reps, ratio in zip(template.focuses, template.sets, template.reps, template.load_ratios):
                specs.append((focus, sets, reps, ratio))
    else:
        specs.append((genome.focus, genome.sets, genome.reps, genome.load_ratio))
    for focus, sets, reps, ratio in specs:
        peak_ratio = min(1.20, ratio + genome.progression_per_week * max(0, config.weeks - 1))
        if focus == "fallback":
            if ratio > RELEASE_ABUSE_THRESHOLDS["fallback_load_ratio"]:
                reasons.append("authored_fallback_load_above_0.78x")
            # Authored fallback execution is capped by the engine, so use the
            # executed ceiling when checking the high-volume envelope. This
            # keeps a legal low-load fallback program from being classified as
            # abuse.
            physical_ratio = min(peak_ratio, config.fallback_max_load_ratio)
            physical_reps = min(reps, 6)
        else:
            physical_ratio = peak_ratio
            physical_reps = reps
        if physical_reps >= RELEASE_ABUSE_THRESHOLDS["high_rep_threshold"] and physical_ratio >= RELEASE_ABUSE_THRESHOLDS["high_rep_load_ratio"]:
            reasons.append("high_reps_at_or_above_0.80x")
        if sets * physical_reps >= RELEASE_ABUSE_THRESHOLDS["high_volume_reps_sets"] and physical_ratio >= RELEASE_ABUSE_THRESHOLDS["high_rep_load_ratio"]:
            reasons.append("high_sets_times_reps_at_or_above_0.80x")
    return list(dict.fromkeys(reasons))


def _release_assessment(evaluation: CandidateEvaluation, expert_mean: float, config: SimConfig) -> dict[str, Any]:
    mean = evaluation.mean_final_1rm_kg
    beats_expert = mean is not None and mean > expert_mean
    margin = round(mean - expert_mean, 4) if mean is not None else None
    signatures: list[str] = []
    if evaluation.mean_pain_days is not None and evaluation.mean_pain_days >= RELEASE_ABUSE_THRESHOLDS["mean_pain_days"]:
        signatures.append("mean_pain_days_at_or_above_14")
    if evaluation.mean_household_strain is not None and evaluation.mean_household_strain >= RELEASE_ABUSE_THRESHOLDS["mean_household_strain"]:
        signatures.append("mean_household_strain_at_or_above_0.95")
    signatures.extend(f"physical:{reason}" for reason in _physical_implausibility_reasons(evaluation.genome, config))
    requires_human_review = margin is not None and margin >= HUMAN_REVIEW_MARGIN_KG
    return {
        "beats_expert": beats_expert,
        "expert_margin_kg": margin,
        "abuse_signatures": signatures,
        "requires_human_review": requires_human_review,
        "release_blocked": bool(beats_expert and signatures),
    }


def _reference_expert_mean(seeds: list[int], config: SimConfig) -> float:
    from .policies import make_policy

    scores: list[float] = []
    for seed in seeds:
        env = BenchEnvironment(seed, config)
        policy = make_policy("scripted-expert", seed)
        while not env.done:
            env.submit_week(policy.action(env.observation), reactive_responder=policy.reactive)
        scores.append(env.final_result().final_1rm_kg)
    return round(fmean(scores), 4)


def run_adversarial_search(
    seeds: Iterable[int] = range(20),
    weeks: int = 52,
    *,
    weekly_stimulus_cap: float | None = None,
    population_size: int = 48,
    generations: int = 3,
    search_seed_count: int = 6,
    top_k: int = 5,
) -> dict[str, Any]:
    """Search legal action-field policies, then re-evaluate the finalists."""
    seed_list = list(seeds)
    config = SimConfig(
        weeks=weeks,
        **({"weekly_stimulus_cap": weekly_stimulus_cap} if weekly_stimulus_cap is not None else {}),
    )
    search_seeds = seed_list[:search_seed_count]
    if not search_seeds:
        raise ValueError("adversarial search requires at least one seed")
    rng = random.Random(20260807)
    regression = _regression_genomes()
    genomes = [genome for _, genome in regression]
    while len(genomes) < population_size:
        genomes.append(_random_genome(rng))
    seen: set[AdversarialGenome] = set()
    best_by_genome: dict[AdversarialGenome, CandidateEvaluation] = {}
    for generation in range(generations):
        unique = []
        for genome in genomes:
            normalized = genome.normalized()
            if normalized not in seen:
                unique.append(normalized)
                seen.add(normalized)
        scored: list[CandidateEvaluation] = []
        for index, genome in enumerate(unique):
            evaluation = _evaluate_genome(f"search-g{generation}-{index:03d}", genome, search_seeds, config)
            evaluation = replace(evaluation, search_mean_final_1rm_kg=evaluation.mean_final_1rm_kg)
            best_by_genome[genome] = evaluation
            scored.append(evaluation)
        scored.sort(key=_rank, reverse=True)
        elites = [evaluation.genome for evaluation in scored[: max(4, population_size // 8)] if evaluation.mean_final_1rm_kg is not None]
        if not elites:
            elites = [genome for _, genome in regression]
        genomes = list(elites)
        while len(genomes) < population_size:
            genomes.append(_mutate(rng.choice(elites), rng))

    ranked = sorted(best_by_genome.values(), key=_rank, reverse=True)
    final_genomes: list[AdversarialGenome] = []
    for evaluation in ranked:
        if evaluation.genome not in final_genomes and evaluation.mean_final_1rm_kg is not None:
            final_genomes.append(evaluation.genome)
        if len(final_genomes) >= top_k:
            break
    for _, genome in regression:
        if genome not in final_genomes:
            final_genomes.append(genome)

    evaluations: list[CandidateEvaluation] = []
    for index, genome in enumerate(final_genomes):
        name = next((label for label, candidate in regression if candidate.normalized() == genome), f"adversarial-{index + 1:03d}")
        evaluation = _evaluate_genome(name, genome, seed_list, config)
        search_evaluation = best_by_genome.get(genome)
        if search_evaluation is not None:
            evaluation = replace(evaluation, search_mean_final_1rm_kg=search_evaluation.search_mean_final_1rm_kg)
        evaluations.append(evaluation)
    evaluations.sort(key=_rank, reverse=True)
    expert_mean = _reference_expert_mean(seed_list, config)
    summaries = {evaluation.name: evaluation.summary() for evaluation in evaluations}
    assessments = {
        evaluation.name: _release_assessment(evaluation, expert_mean, config)
        for evaluation in evaluations
    }
    candidates = {
        evaluation.name: {
            "genome": evaluation.genome.as_dict(),
            "search_mean_final_1rm_kg": evaluation.search_mean_final_1rm_kg,
            "final_mean_final_1rm_kg": evaluation.mean_final_1rm_kg,
            **assessments[evaluation.name],
        }
        for evaluation in evaluations
    }
    return {
        "benchmark": "Bench-bench",
        "engine_config_hash": engine_config_hash(),
        "phase": 4,
        "config": config.as_dict(),
        "seeds": seed_list,
        "exploit_policies": [evaluation.name for evaluation in evaluations],
        "summaries": summaries,
        "episodes": {
            evaluation.name: [episode.as_dict() for episode in evaluation.episodes]
            for evaluation in evaluations
        },
        "candidates": candidates,
        "search": {
            "method": "deterministic evolutionary search over legal WeekAction fields with mixed-focus weekly templates, boundary loads, and ordered purchases",
            "search_seed": 20260807,
            "search_seeds": search_seeds,
            "population_size": population_size,
            "generations": generations,
            "unique_genomes_evaluated": len(best_by_genome),
            "regression_families": [label for label, _ in regression],
            "genome_features": [
                "mixed_focus_sessions",
                "per_week_templates",
                "boundary_load_ratios_including_zero",
                "ordered_capital_purchases",
            ],
            "invalid_search_candidates": sum(
                evaluation.invalid_episodes > 0 for evaluation in best_by_genome.values()
            ),
        },
        "comparison": {
            "expert_mean_final_1rm_kg": expert_mean,
            "candidates_beating_expert": [
                evaluation.name
                for evaluation in evaluations
                if evaluation.mean_final_1rm_kg is not None and evaluation.mean_final_1rm_kg > expert_mean
            ],
            "release_blocked_candidates": [
                name for name, assessment in assessments.items() if assessment["release_blocked"]
            ],
            "human_review_candidates": [
                name for name, assessment in assessments.items() if assessment["requires_human_review"]
            ],
            "release_abuse_thresholds": RELEASE_ABUSE_THRESHOLDS,
            "human_review_margin_kg": HUMAN_REVIEW_MARGIN_KG,
            "candidate_assessments": assessments,
        },
    }
