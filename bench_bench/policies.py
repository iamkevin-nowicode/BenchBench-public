"""Six transparent scripted baselines used by the Phase 2 gate."""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
import random

from .config import sleep_protection_time_cost_minutes
from .schemas import InterruptObservation, LifeAllocation, ReactiveAction, SessionPlan, StandingRules, WeekAction, WeekObservation


POLICY_NAMES = (
    "random",
    "rigid-linear",
    "reckless-maximalist",
    "skip-when-busy",
    "recovery-aware",
    "scripted-expert",
)

def _days(count: int, rng: random.Random | None = None) -> list[int]:
    values = [1, 3, 5]
    if count <= 3:
        return values[:count]
    if rng is None:
        return [0, 1, 2, 3, 4][:count]
    return sorted(rng.sample(range(7), count))


def _open_days(observation: WeekObservation, count: int) -> list[int]:
    """Choose training days from the visible flexible windows when possible."""
    available = [day for day, band in enumerate(observation.available_time_bands) if band == "open"]
    return available[:count] if len(available) >= count else _days(count)


def _life(
    *,
    meal_prep: float = 2.0,
    sleep: str = "standard",
    coverage: float = 2.0,
    giveback: float = 2.0,
    chores: float = 0.0,
    purchases: list[str] | None = None,
    meal_spend: int = 0,
    childcare_spend: int = 0,
    chore_spend: int = 0,
) -> LifeAllocation:
    return LifeAllocation(
        meal_prep_hours=meal_prep,
        meal_support_spend_cents=meal_spend,
        childcare_hours=0.0,
        childcare_spend_cents=childcare_spend,
        chore_delegation_hours=chores,
        chore_delegation_spend_cents=chore_spend,
        partner_coverage_hours=coverage,
        partner_giveback_hours=giveback,
        sleep_protection=sleep,  # type: ignore[arg-type]
        purchases=purchases or [],  # type: ignore[arg-type]
    )


def _rules(sleep: str = "fallback", pain: str = "reduce", illness: str = "protect_recovery") -> StandingRules:
    return StandingRules(
        on_sleep_below_5h=sleep,  # type: ignore[arg-type]
        on_pain_warning=pain,  # type: ignore[arg-type]
        on_illness=illness,  # type: ignore[arg-type]
    )


def _session(
    day: int,
    *,
    location: str = "gym",
    focus: str = "volume",
    sets: int = 4,
    reps: int = 5,
    load: float = 60.0,
    duration: int = 45,
    rpe: float = 7.0,
) -> SessionPlan:
    return SessionPlan(
        day=day,
        slot="evening",
        location=location,  # type: ignore[arg-type]
        focus=focus,  # type: ignore[arg-type]
        sets=sets,
        reps=reps,
        # Zero is a legal authored boundary.  The engine decides whether a
        # meaningful stimulus exists; the policy helper must not rewrite it.
        load_kg=round(max(0.0, load), 1),
        duration_min=duration,
        target_rpe=rpe,
    )


def _conservative_session_minutes(sessions: list[SessionPlan]) -> int:
    """Reserve the engine's maximum visible per-session logistics cost."""
    overhead = {"gym": 26, "home": 10, "hotel": 20}
    return sum(session.duration_min + overhead[session.location] for session in sessions)


def _conservative_sleep_minutes(life: LifeAllocation) -> int:
    return sleep_protection_time_cost_minutes(life.sleep_protection)


def _visible_external_time_reserve(observation: WeekObservation) -> int:
    """Reserve the announced week-14 childcare block for scripted policies."""
    return 240 if any(
        event.week == observation.episode_week and event.title == "grandparents visit"
        for event in observation.upcoming_known_events
    ) else 0


class ScriptedPolicy(ABC):
    name: str

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed * 1_000_003 + sum(ord(char) for char in self.name))

    @abstractmethod
    def action(self, observation: WeekObservation) -> WeekAction:
        raise NotImplementedError

    @abstractmethod
    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        raise NotImplementedError


class RandomPolicy(ScriptedPolicy):
    name = "random"

    def action(self, observation: WeekObservation) -> WeekAction:
        count = self.rng.choices([0, 1, 2, 3, 4], weights=[1, 2, 4, 4, 1])[0]
        sessions: list[SessionPlan] = []
        home_available = "home_rack" in observation.equipment
        for day in self.rng.sample(range(7), count):
            focus = self.rng.choices(["volume", "heavy", "technique", "fallback"], weights=[4, 2, 2, 1])[0]
            if focus == "fallback":
                sessions.append(
                    _session(day, location="home" if home_available and self.rng.random() < 0.4 else "gym", focus=focus, sets=2, reps=5, load=observation.estimated_1rm_kg * 0.58, duration=25, rpe=6.0)
                )
            else:
                reps = self.rng.randint(3, 8)
                sets = self.rng.randint(2, 5)
                multiplier = self.rng.uniform(0.55, 1.04 if focus == "heavy" else 0.88)
                sessions.append(
                    _session(
                        day,
                        location="home" if home_available and self.rng.random() < 0.25 else "gym",
                        focus=focus,
                        sets=sets,
                        reps=reps,
                        load=observation.estimated_1rm_kg * multiplier,
                        duration=self.rng.randint(25, 80),
                        rpe=round(self.rng.uniform(6.0, 9.5), 1),
                    )
                )
        # Randomness is inside the legal action space.  The old generator
        # independently sampled training and household hours, so it emitted
        # ledger-invalid weeks and measured the safe fallback instead of a
        # random policy.  Reserve the fixed household block, the announced
        # week-14 childcare block, and maximum gym crowding before sampling
        # optional life allocations.
        sleep = self.rng.choice(["none", "standard", "strong"])
        budget = max(0, observation.weekly_time_budget_minutes)
        required = (
            _conservative_session_minutes(sessions)
            + _visible_external_time_reserve(observation)
            + sleep_protection_time_cost_minutes(sleep)
        )
        while sessions and required > budget:
            sessions.pop()
            required = _conservative_session_minutes(sessions) + _visible_external_time_reserve(observation)
        remaining_hours = max(0, (budget - required) // 60)
        meal_prep = min(float(self.rng.choice([0, 1, 2, 4])), remaining_hours)
        remaining_hours -= int(meal_prep)
        coverage = min(float(self.rng.choice([0, 1, 2, 3, 4])), remaining_hours)
        remaining_hours -= int(coverage)
        giveback = min(float(self.rng.choice([0, 1, 2, 3, 4])), remaining_hours)
        return WeekAction(
            sessions=sessions,
            life=_life(meal_prep=meal_prep, sleep=sleep, coverage=coverage, giveback=giveback),
            rules=_rules(
                sleep=self.rng.choice(["fallback", "skip", "reduce"]),
                pain=self.rng.choice(["reduce", "fallback", "skip"]),
                illness=self.rng.choice(["protect_recovery", "fallback", "skip"]),
            ),
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        response = self.rng.choice(["protect_recovery", "reallocate", "preserve_training", "accept_disruption"])
        cancel: list[int] = []
        fallback: list[int] = []
        if response == "protect_recovery":
            fallback = [observation.day]
        elif response == "accept_disruption":
            cancel = [observation.day]
        return ReactiveAction(response=response, cancel_session_days=cancel, fallback_session_days=fallback)  # type: ignore[arg-type]


class RigidLinearPolicy(ScriptedPolicy):
    name = "rigid-linear"

    def action(self, observation: WeekObservation) -> WeekAction:
        week = observation.episode_week
        load = 60.0 + week * 0.55
        location = "gym"
        sessions = [
            _session(1, location=location, focus="volume", sets=4, reps=5, load=load, duration=50, rpe=7.5),
            _session(3, location=location, focus="volume", sets=4, reps=5, load=load + 1.0, duration=50, rpe=7.5),
            _session(5, location=location, focus="heavy", sets=3, reps=3, load=load + 4.0, duration=55, rpe=8.0),
        ]
        return WeekAction(
            sessions=sessions,
            life=_life(meal_prep=2.0, sleep="standard", coverage=3.0, giveback=2.0),
            rules=_rules(sleep="fallback", pain="reduce", illness="fallback"),
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        return ReactiveAction(response="accept_disruption")


class RecklessMaximalistPolicy(ScriptedPolicy):
    name = "reckless-maximalist"

    def action(self, observation: WeekObservation) -> WeekAction:
        load = observation.estimated_1rm_kg * 1.02 + 2.0
        sessions = [
            _session(day, focus="heavy", sets=4, reps=4, load=load + index * 0.8, duration=60, rpe=9.7)
            for index, day in enumerate([0, 1, 2, 3])
        ]
        return WeekAction(
            sessions=sessions,
            # Reckless behavior is now physiological and recovery-related,
            # not a disguised ledger-invalid action: four high-RPE sessions,
            # no sleep protection, two hours of coverage, and no giveback.
            # The plan remains legal even in the announced week-14 reserve.
            life=_life(meal_prep=0.0, sleep="none", coverage=2.0, giveback=0.0),
            rules=_rules(sleep="reduce", pain="reduce", illness="fallback"),
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        return ReactiveAction(response="preserve_training")


class SkipWhenBusyPolicy(ScriptedPolicy):
    name = "skip-when-busy"

    def action(self, observation: WeekObservation) -> WeekAction:
        open_day_count = sum(band == "open" for band in observation.available_time_bands)
        busy = (
            "tight" in observation.available_time_bands
            or open_day_count < 3
            or observation.sleep_band == "depleted"
            or observation.energy_band == "low"
            or observation.household_strain_band in ("high", "critical")
        )
        if busy:
            sessions: list[SessionPlan] = []
        else:
            load = observation.estimated_1rm_kg * 0.77
            days = _open_days(observation, 3)
            sessions = [
                _session(days[0], focus="volume", sets=4, reps=5, load=load, duration=45, rpe=7.0),
                _session(days[1], focus="technique", sets=3, reps=5, load=load * 0.86, duration=35, rpe=6.5),
                _session(days[2], focus="volume", sets=4, reps=4, load=load * 1.04, duration=45, rpe=7.5),
            ]
            # This baseline deliberately leaves one good training window on
            # the table; its defining behavior is protecting the calendar by
            # skipping rather than adapting the plan into that window.
            sessions = sessions[:2]
        return WeekAction(
            sessions=sessions,
            life=_life(meal_prep=2.5, sleep="strong", coverage=3.0, giveback=3.0),
            rules=_rules(sleep="fallback", pain="skip", illness="skip"),
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        if observation.severity == "high":
            return ReactiveAction(response="protect_recovery", cancel_session_days=[observation.day])
        return ReactiveAction(response="accept_disruption", cancel_session_days=[observation.day])


class RecoveryAwarePolicy(ScriptedPolicy):
    name = "recovery-aware"

    def action(self, observation: WeekObservation) -> WeekAction:
        limiting = observation.pain_band in ("limiting", "recovery")
        depleted = observation.sleep_band == "depleted" or observation.energy_band == "low"
        strained = observation.sleep_band == "strained" or observation.energy_band == "medium"
        location = "home" if "home_rack" in observation.equipment else "gym"
        if limiting:
            days = _open_days(observation, 2)
            specs = [(days[0], "fallback", 2, 5, 0.55, 25, 6.0), (days[1], "technique", 2, 5, 0.60, 30, 6.0)]
        elif depleted:
            specs = [(_open_days(observation, 1)[0], "fallback", 2, 5, 0.58, 25, 6.0)]
        elif strained:
            days = _open_days(observation, 2)
            specs = [(days[0], "volume", 3, 5, 0.68, 40, 6.8), (days[1], "technique", 3, 5, 0.60, 35, 6.5)]
        else:
            estimate = observation.estimated_1rm_kg
            days = _open_days(observation, 3)
            specs = [(days[0], "volume", 4, 5, 0.72, 45, 7.0), (days[1], "technique", 3, 5, 0.62, 35, 6.5), (days[2], "volume", 4, 4, 0.76, 45, 7.3)]
        sessions = [
            _session(day, location=location, focus=focus, sets=sets, reps=reps, load=observation.estimated_1rm_kg * multiplier, duration=duration, rpe=rpe)
            for day, focus, sets, reps, multiplier, duration, rpe in specs
        ]
        return WeekAction(
            sessions=sessions,
            # Keep the reference policy feasible under the v0.2 fixed
            # household reserve; recovery management is the behavior under
            # test, not repeated ledger rejection.
            life=_life(meal_prep=1.5, sleep="strong", coverage=1.5, giveback=1.5, chores=0.5),
            rules=_rules(sleep="fallback", pain="fallback", illness="protect_recovery"),
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        return ReactiveAction(
            response="protect_recovery",
            cancel_session_days=[observation.day] if observation.severity == "high" else [],
            fallback_session_days=[observation.day] if observation.severity != "high" else [],
        )


class ScriptedExpertPolicy(ScriptedPolicy):
    name = "scripted-expert"

    def __init__(self, seed: int, *, allow_home_rack: bool = True) -> None:
        super().__init__(seed)
        self.allow_home_rack = allow_home_rack

    @staticmethod
    def _conservative_session_minutes(sessions: list[SessionPlan]) -> int:
        """Budget a plan without depending on hidden event-calendar state.

        The engine's largest gym-crowding surcharge is six minutes per visit.
        Reserving that surcharge keeps the public reference policy valid even
        when the exact crowding draw is not observable.
        """
        return _conservative_session_minutes(sessions)

    @staticmethod
    def _visible_external_time_reserve(observation: WeekObservation) -> int:
        # The grandparents visit is the visible announcement for the engine's
        # four-hour week-14 external-childcare allocation.
        return 240 if any(
            event.week == observation.episode_week and event.title == "grandparents visit"
            for event in observation.upcoming_known_events
        ) else 0

    def _fit_to_time_ledger(
        self,
        observation: WeekObservation,
        sessions: list[SessionPlan],
        rules: StandingRules,
        purchases: list[str],
    ) -> WeekAction:
        """Choose the strongest balanced plan that fits the visible budget.

        The candidate ladder first preserves all training while reducing
        household allocations in balanced steps.  Only then does it remove
        later sessions.  Every candidate is built from schema-valid fields;
        the conservative gym reserve and visible week-14 reserve make the
        result safe against the engine's hidden crowding draw.
        """
        budget = max(0, observation.weekly_time_budget_minutes)
        external_reserve = self._visible_external_time_reserve(observation)
        life_options = [
            _life(meal_prep=3.0, sleep="strong", coverage=3.0, giveback=3.0, chores=2.0, purchases=purchases),
            _life(meal_prep=2.0, sleep="strong", coverage=2.0, giveback=2.0, chores=1.0, purchases=purchases),
            _life(meal_prep=1.0, sleep="strong", coverage=2.0, giveback=2.0, chores=0.0, purchases=purchases),
            _life(meal_prep=1.0, sleep="strong", coverage=1.0, giveback=1.0, chores=0.0, purchases=purchases),
            _life(meal_prep=0.0, sleep="strong", coverage=1.0, giveback=1.0, chores=0.0, purchases=purchases),
            _life(meal_prep=0.0, sleep="strong", coverage=0.0, giveback=0.0, chores=0.0, purchases=purchases),
        ]
        session_options = [sessions, sessions[:2], sessions[:1], []]
        # Preserve the strongest training plan first, then reduce optional
        # household allocations.  Iterating life first would accept an empty
        # training week as soon as the most generous life bundle fits.
        for candidate_sessions in session_options:
            for life in life_options:
                life_minutes = math.ceil(
                    60.0
                    * (
                        life.meal_prep_hours
                        + life.childcare_hours
                        + life.chore_delegation_hours
                        + life.partner_coverage_hours
                        + life.partner_giveback_hours
                    )
                )
                required = (
                    self._conservative_session_minutes(candidate_sessions)
                    + life_minutes
                    + external_reserve
                    + _conservative_sleep_minutes(life)
                )
                if required <= budget:
                    return WeekAction(sessions=candidate_sessions, life=life, rules=rules)

        # This is reachable only if a caller supplies a budget smaller than
        # the visible event reserve. It still avoids emitting an infeasible
        # training plan and preserves the standing safety rules.
        return WeekAction(
            sessions=[],
            life=_life(meal_prep=0.0, sleep="strong", coverage=0.0, giveback=0.0, chores=0.0, purchases=purchases),
            rules=rules,
        )

    def action(self, observation: WeekObservation) -> WeekAction:
        purchases: list[str] = []
        has_home = self.allow_home_rack and "home_rack" in observation.equipment
        if not has_home and observation.episode_week >= 8 and observation.budget_available_cents >= 60_000:
            if self.allow_home_rack:
                purchases.append("home_gym")
                has_home = True
        limiting = observation.pain_band in ("limiting", "recovery")
        depleted = observation.sleep_band == "depleted" or observation.energy_band == "low"
        location = "home" if has_home else "gym"
        if limiting:
            days = _open_days(observation, 2)
            specs = [(days[0], "fallback", 2, 5, 0.54, 25, 6.0), (days[1], "technique", 2, 5, 0.60, 30, 6.0)]
        elif depleted:
            days = _open_days(observation, 2)
            specs = [(days[0], "fallback", 2, 5, 0.58, 25, 6.0), (days[1], "technique", 2, 5, 0.62, 30, 6.2)]
        else:
            estimate = observation.estimated_1rm_kg
            days = _open_days(observation, 3)
            specs = [(days[0], "volume", 4, 5, 0.72, 45, 7.0), (days[1], "technique", 3, 5, 0.62, 35, 6.5), (days[2], "volume", 4, 4, 0.78, 45, 7.3)]
        sessions = [
            _session(day, location=location, focus=focus, sets=sets, reps=reps, load=observation.estimated_1rm_kg * multiplier, duration=duration, rpe=rpe)
            for day, focus, sets, reps, multiplier, duration, rpe in specs
        ]
        return self._fit_to_time_ledger(
            observation,
            sessions,
            _rules(sleep="fallback", pain="fallback", illness="protect_recovery"),
            purchases,
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        if observation.kind == "gym_closed":
            return ReactiveAction(response="reallocate", fallback_session_days=[observation.day])
        if observation.severity == "high":
            return ReactiveAction(response="protect_recovery", cancel_session_days=[observation.day])
        return ReactiveAction(response="protect_recovery", fallback_session_days=[observation.day])


class ReviewerVolumePolicy(ScriptedPolicy):
    """Fixed reviewer-supplied high-volume candidate.

    The weekly plan is intentionally otherwise non-adaptive: four volume
    sessions, 3x7 at 0.68x the visible estimate, strong sleep protection,
    balanced partner time, and three hours of delegated chores.  ``duration``
    is injectable so the authored 10-minute version can be compared with the
    21-minute version that permits all 21 prescribed reps under the engine's
    one-rep-per-minute execution rule.
    """

    name = "reviewer-volume"

    def __init__(self, seed: int, *, duration_min: int = 10) -> None:
        super().__init__(seed)
        self.duration_min = duration_min

    def action(self, observation: WeekObservation) -> WeekAction:
        has_home = "home_rack" in observation.equipment
        purchases = ["home_gym"] if observation.episode_week == 8 and not has_home else []
        location = "home" if has_home or purchases else "gym"
        days = _open_days(observation, 4)
        sessions = [
            _session(
                day,
                location=location,
                focus="volume",
                sets=3,
                reps=7,
                load=observation.estimated_1rm_kg * 0.68,
                duration=self.duration_min,
                rpe=6.5,
            )
            for day in days
        ]
        return WeekAction(
            sessions=sessions,
            life=_life(
                meal_prep=2.0,
                sleep="strong",
                coverage=3.0,
                giveback=3.0,
                chores=3.0,
                purchases=purchases,
            ),
            rules=_rules(),
        )

    def reactive(self, observation: InterruptObservation) -> ReactiveAction:
        if observation.severity == "high":
            return ReactiveAction(response="protect_recovery", cancel_session_days=[observation.day])
        return ReactiveAction(response="protect_recovery", fallback_session_days=[observation.day])


_POLICY_TYPES = {
    RandomPolicy.name: RandomPolicy,
    RigidLinearPolicy.name: RigidLinearPolicy,
    RecklessMaximalistPolicy.name: RecklessMaximalistPolicy,
    SkipWhenBusyPolicy.name: SkipWhenBusyPolicy,
    RecoveryAwarePolicy.name: RecoveryAwarePolicy,
    ScriptedExpertPolicy.name: ScriptedExpertPolicy,
    ReviewerVolumePolicy.name: ReviewerVolumePolicy,
}


def make_policy(name: str, seed: int, *, allow_home_rack: bool = True) -> ScriptedPolicy:
    try:
        if name == ScriptedExpertPolicy.name:
            return ScriptedExpertPolicy(seed, allow_home_rack=allow_home_rack)
        return _POLICY_TYPES[name](seed)
    except KeyError as exc:
        raise ValueError(f"unknown scripted policy: {name}") from exc
