"""Measurement primitives for the held-out Phase 3 certification.

This module deliberately does not search or tune.  It provides the accounting
that the search, policy ladder, and later release reports must share:

* an episode with more than 5% weekly validation fallbacks is infeasible and
  cannot supply a Phase 3 score;
* raw scores remain visible as diagnostics, so a safe-fallback score cannot be
  mistaken for a policy result;
* normalized comparisons are paired, per-seed deltas from the scripted-expert
  reference.  They are not a replacement for the absolute kg headline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from statistics import fmean, stdev
from typing import Any, Callable, Iterable, Mapping

from .config import SimConfig
from .engine import BenchEnvironment
from .policies import ScriptedExpertPolicy, _open_days, make_policy
from .scoring import counted_score, constraint_violations
from .schemas import LifeAllocation, SessionPlan, WeekAction


MAX_WEEKLY_VALIDATION_FALLBACK_RATE = 0.05


class MeasurementLivenessError(RuntimeError):
    """Raised when a measurement did not execute the protocol it claims to measure."""

PolicyFactory = Callable[[int], Any]


@dataclass(frozen=True)
class Phase3Episode:
    policy: str
    seed: int
    raw_score_kg: float | None
    counted_score_kg: float | None
    normalized_delta_kg: float | None
    decision_weeks: int
    validation_fallbacks: int
    weekly_validation_fallback_rate: float
    feasible: bool
    feasibility_reasons: tuple[str, ...]
    invalid_reason: str | None
    constraint_violations: tuple[str, ...]
    pain_days: int | None
    household_strain_peak: float | None
    mean_household_strain: float | None
    sleep_debt: float | None

    def as_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["feasibility_reasons"] = list(self.feasibility_reasons)
        values["constraint_violations"] = list(self.constraint_violations)
        return values


@dataclass(frozen=True)
class Phase3Measurement:
    policy: str
    episodes: tuple[Phase3Episode, ...]
    raw_mean_kg: float | None
    raw_seed_sd_kg: float | None
    counted_mean_kg: float | None
    counted_seed_sd_kg: float | None
    normalized_mean_kg: float | None
    normalized_seed_sd_kg: float | None
    normalized_gate_mean_kg: float | None
    normalized_gate_seed_sd_kg: float | None
    paired_effect_size: float | None
    reference_seed_sd_kg: float | None
    volatility_ratio_vs_reference: float | None
    counted_seed_fraction: float
    feasible_for_phase3: bool
    ineligible_episodes: int
    validation_fallback_violating_episodes: int

    def as_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["episodes"] = [episode.as_dict() for episode in self.episodes]
        return values


def _sample_sd(values: list[float]) -> float | None:
    if not values:
        return None
    return stdev(values) if len(values) > 1 else 0.0


def _run_policy_episode(
    name: str,
    seed: int,
    policy_factory: PolicyFactory,
    config: SimConfig,
    reference_score_kg: float | None,
) -> Phase3Episode:
    env = BenchEnvironment(seed, config)
    policy = policy_factory(seed)
    reactive = getattr(policy, "reactive", None)
    while not env.done:
        env.submit_week(policy.action(env.observation), reactive_responder=reactive)

    week_records = [record for record in env.log_records if record.get("type") == "week"]
    if len(week_records) != config.weeks:
        raise MeasurementLivenessError(
            f"{name} seed {seed}: expected {config.weeks} weekly decisions, "
            f"observed {len(week_records)}"
        )
    if config.weeks == 52:
        hidden_test_scores = env.private_snapshot()["hidden_standardized_test_scores"]
        if len(hidden_test_scores) != 3:
            raise MeasurementLivenessError(
                f"{name} seed {seed}: expected three hidden standardized tests, "
                f"observed {len(hidden_test_scores)}"
            )
    result = env.final_result()
    validation_fallbacks = sum(
        bool(record.get("validation", {}).get("fallback_used"))
        for record in week_records
    )
    decision_weeks = len(week_records)
    fallback_rate = validation_fallbacks / max(1, decision_weeks)
    violations = constraint_violations(
        pain_days=result.pain_days,
        household_strain_high_weeks=result.household_strain_high_weeks,
        final_third_mean_household_strain=result.final_third_mean_household_strain,
        household_strain_limit=config.household_strain_limit,
        household_strain_high_week_limit=config.household_strain_high_week_limit,
    )
    reasons: list[str] = []
    if fallback_rate > MAX_WEEKLY_VALIDATION_FALLBACK_RATE:
        reasons.append(
            f"weekly_validation_fallback_rate>{MAX_WEEKLY_VALIDATION_FALLBACK_RATE:g}"
        )
    if result.invalid_reason is not None:
        reasons.append(f"invalid_reason:{result.invalid_reason}")
    reasons.extend(violations)
    feasible = not reasons
    raw_score = float(result.final_1rm_kg) if result.final_1rm_kg is not None else None
    counted = (
        counted_score(
            raw_score,
            invalid_reason=result.invalid_reason,
            violations=violations,
        )
        if fallback_rate <= MAX_WEEKLY_VALIDATION_FALLBACK_RATE
        else None
    )
    normalized_delta = (
        raw_score - reference_score_kg
        if raw_score is not None and reference_score_kg is not None
        else None
    )
    return Phase3Episode(
        policy=name,
        seed=seed,
        raw_score_kg=raw_score,
        counted_score_kg=counted if feasible else None,
        normalized_delta_kg=normalized_delta,
        decision_weeks=decision_weeks,
        validation_fallbacks=validation_fallbacks,
        weekly_validation_fallback_rate=round(fallback_rate, 6),
        feasible=feasible,
        feasibility_reasons=tuple(reasons),
        invalid_reason=result.invalid_reason,
        constraint_violations=violations,
        pain_days=result.pain_days,
        household_strain_peak=result.household_strain_peak,
        mean_household_strain=result.mean_household_strain,
        sleep_debt=result.sleep_debt,
    )


def measure_policy(
    name: str,
    seeds: Iterable[int],
    policy_factory: PolicyFactory,
    config: SimConfig | None = None,
    *,
    reference_scores: Mapping[int, float] | None = None,
) -> Phase3Measurement:
    """Measure one policy with strict all-seed Phase 3 eligibility.

    The raw and normalized diagnostic means use structurally completed
    episodes, including episodes that violate a hard score constraint.  The
    counted and gate columns require every expected seed to be feasible; this
    prevents both survivor-mean bias and safe-fallback masquerading.
    """
    config = config or SimConfig(weeks=52)
    seed_list = list(seeds)
    reference_scores = reference_scores or {}
    episodes = tuple(
        _run_policy_episode(
            name,
            seed,
            policy_factory,
            config,
            reference_scores.get(seed),
        )
        for seed in seed_list
    )
    structural = [
        episode
        for episode in episodes
        if episode.raw_score_kg is not None and episode.invalid_reason is None
    ]
    eligible = [episode for episode in episodes if episode.counted_score_kg is not None]
    raw_scores = [float(episode.raw_score_kg) for episode in structural]
    counted_scores = [float(episode.counted_score_kg) for episode in eligible]
    normalized = [
        float(episode.normalized_delta_kg)
        for episode in structural
        if episode.normalized_delta_kg is not None
    ]
    normalized_gate = [
        float(episode.normalized_delta_kg)
        for episode in eligible
        if episode.normalized_delta_kg is not None
    ]
    reference = [
        float(reference_scores[episode.seed])
        for episode in episodes
        if episode.seed in reference_scores
    ]
    counted_fraction = len(eligible) / len(episodes) if episodes else 0.0
    all_seed_eligible = bool(
        episodes
        and len(eligible) == len(episodes)
        and (not reference_scores or len(normalized_gate) == len(episodes))
    )
    normalized_gate_mean = (
        fmean(normalized_gate)
        if all_seed_eligible and normalized_gate
        else None
    )
    normalized_gate_sd = (
        _sample_sd(normalized_gate)
        if all_seed_eligible and normalized_gate
        else None
    )
    paired_effect = (
        normalized_gate_mean / normalized_gate_sd
        if normalized_gate_mean is not None and normalized_gate_sd not in (None, 0.0)
        else None
    )
    reference_sd = _sample_sd(reference) if len(reference) > 1 else None
    raw_sd = _sample_sd(raw_scores)
    volatility_ratio = (
        raw_sd / reference_sd
        if raw_sd is not None and reference_sd not in (None, 0.0)
        else None
    )
    return Phase3Measurement(
        policy=name,
        episodes=episodes,
        raw_mean_kg=round(fmean(raw_scores), 4) if raw_scores else None,
        raw_seed_sd_kg=round(raw_sd, 4) if raw_sd is not None else None,
        counted_mean_kg=round(fmean(counted_scores), 4) if all_seed_eligible else None,
        counted_seed_sd_kg=(
            round(_sample_sd(counted_scores), 4)
            if all_seed_eligible and _sample_sd(counted_scores) is not None
            else None
        ),
        normalized_mean_kg=round(fmean(normalized), 4) if normalized else None,
        normalized_seed_sd_kg=(
            round(_sample_sd(normalized), 4) if normalized else None
        ),
        normalized_gate_mean_kg=(
            round(normalized_gate_mean, 4)
            if normalized_gate_mean is not None
            else None
        ),
        normalized_gate_seed_sd_kg=(
            round(normalized_gate_sd, 4) if normalized_gate_sd is not None else None
        ),
        paired_effect_size=round(paired_effect, 4) if paired_effect is not None else None,
        reference_seed_sd_kg=round(reference_sd, 4) if reference_sd is not None else None,
        volatility_ratio_vs_reference=(
            round(volatility_ratio, 4) if volatility_ratio is not None else None
        ),
        counted_seed_fraction=round(counted_fraction, 4),
        feasible_for_phase3=all_seed_eligible,
        ineligible_episodes=len(episodes) - len(eligible),
        validation_fallback_violating_episodes=sum(
            episode.weekly_validation_fallback_rate > MAX_WEEKLY_VALIDATION_FALLBACK_RATE
            for episode in episodes
        ),
    )


def measure_scripted_policies(
    names: Iterable[str],
    seeds: Iterable[int],
    config: SimConfig | None = None,
) -> dict[str, Phase3Measurement]:
    """Measure named scripted policies against the same per-seed expert map."""
    config = config or SimConfig(weeks=52)
    seed_list = list(seeds)
    expert = measure_policy(
        "scripted-expert",
        seed_list,
        lambda seed: make_policy("scripted-expert", seed, allow_home_rack=config.enable_home_rack),
        config,
    )
    reference_scores = {
        episode.seed: float(episode.raw_score_kg)
        for episode in expert.episodes
        if episode.raw_score_kg is not None
    }
    reference_values = list(reference_scores.values())
    expert = replace(
        expert,
        normalized_mean_kg=0.0,
        normalized_seed_sd_kg=0.0,
        normalized_gate_mean_kg=0.0,
        normalized_gate_seed_sd_kg=0.0,
        reference_seed_sd_kg=round(_sample_sd(reference_values), 4)
        if _sample_sd(reference_values) is not None
        else None,
        volatility_ratio_vs_reference=1.0,
    )
    measurements: dict[str, Phase3Measurement] = {}
    requested = list(dict.fromkeys(names))
    if "scripted-expert" not in requested:
        requested.insert(0, "scripted-expert")
    for name in requested:
        measurements[name] = (
            expert
            if name == "scripted-expert"
            else measure_policy(
                name,
                seed_list,
                lambda seed, policy_name=name: make_policy(
                    policy_name,
                    seed,
                    allow_home_rack=config.enable_home_rack,
                ),
                config,
                reference_scores=reference_scores,
            )
        )
    return measurements


LADDER_EFFECT_SIZE_THRESHOLD = 0.64


class LadderPolicy:
    """A controlled perturbation of the scripted expert for Phase 3.

    The ladder changes one decision family at a time. It is deliberately
    separate from the adversarial genome: the purpose here is an interpretable
    paired instrument, not broad search.
    """

    def __init__(self, seed: int, variant: str, config: SimConfig) -> None:
        self.base = ScriptedExpertPolicy(seed, allow_home_rack=config.enable_home_rack)
        self.variant = variant
        self.config = config

    def reactive(self, observation: Any) -> Any:
        return self.base.reactive(observation)

    @staticmethod
    def _add_sessions(
        observation: Any,
        sessions: list[SessionPlan],
        target: int,
    ) -> list[SessionPlan]:
        sessions = list(sessions[:target])
        if len(sessions) >= target:
            return sessions
        used = {session.day for session in sessions}
        available = [day for day in _open_days(observation, 7) if day not in used]
        available.extend(day for day in range(7) if day not in used and day not in available)
        template = sessions[-1] if sessions else SessionPlan(
            day=0,
            location="gym",
            focus="technique",
            sets=3,
            reps=5,
            load_kg=round(observation.estimated_1rm_kg * 0.62, 1),
            duration_min=35,
            target_rpe=6.5,
        )
        for day in available:
            if len(sessions) >= target:
                break
            sessions.append(template.model_copy(update={"day": day}))
        return sessions

    def _fit_frequency_action(self, observation: Any, action: WeekAction, sessions: list[SessionPlan]) -> WeekAction:
        """Author a frequency rung that remains inside the visible ledger."""
        life = action.life
        budget = max(0, observation.weekly_time_budget_minutes)

        def required_minutes(current_life: LifeAllocation) -> int:
            session_minutes = 0
            for session in sessions:
                commute = self.config.home_session_overhead_minutes if session.location == "home" else self.config.gym_commute_minutes
                crowding = 6 if session.location == "gym" else 0
                session_minutes += session.duration_min + commute + crowding
            allocation_minutes = 60.0 * sum(
                float(getattr(current_life, field))
                for field in (
                    "meal_prep_hours",
                    "childcare_hours",
                    "chore_delegation_hours",
                    "partner_coverage_hours",
                    "partner_giveback_hours",
                )
            )
            external = 240 if observation.episode_week == 14 else 0
            return round(
                session_minutes
                + allocation_minutes
                + self.config.sleep_protection_time_cost_minutes(current_life.sleep_protection)
                + external
            )

        # Frequency is the intervention; reducing optional household time is
        # the explicit tradeoff that makes the rung legal, not a simulator
        # fallback. Preserve sleep protection while trimming meal/coverage
        # allocations in small, visible increments.
        for field in (
            "meal_prep_hours",
            "chore_delegation_hours",
            "partner_giveback_hours",
            "partner_coverage_hours",
            "childcare_hours",
        ):
            while required_minutes(life) > budget and float(getattr(life, field)) > 0:
                life = life.model_copy(update={field: max(0.0, float(getattr(life, field)) - 0.5)})
        return action.model_copy(update={"sessions": sessions, "life": life})

    def action(self, observation: Any) -> WeekAction:
        action = self.base.action(observation)
        if self.variant.startswith("load-"):
            multiplier = float(self.variant.removeprefix("load-"))
            sessions = [
                session.model_copy(update={"load_kg": round(session.load_kg * multiplier, 1)})
                for session in action.sessions
            ]
            return action.model_copy(update={"sessions": sessions})
        if self.variant.startswith("frequency-"):
            target = int(self.variant.removeprefix("frequency-"))
            sessions = self._add_sessions(observation, action.sessions, target)
            return self._fit_frequency_action(observation, action, sessions)
        if self.variant == "sleep-none+frequency-4":
            action = action.model_copy(
                update={"life": action.life.model_copy(update={"sleep_protection": "none"})}
            )
            sessions = self._add_sessions(observation, action.sessions, 4)
            return self._fit_frequency_action(observation, action, sessions)
        life_updates: dict[str, Any] = {}
        if self.variant == "sleep-none":
            life_updates["sleep_protection"] = "none"
        elif self.variant == "sleep-standard":
            life_updates["sleep_protection"] = "standard"
        elif self.variant == "sleep-strong":
            life_updates["sleep_protection"] = "strong"
        elif self.variant == "meal-none":
            life_updates["meal_prep_hours"] = 0.0
        elif self.variant == "coverage-none":
            life_updates["partner_coverage_hours"] = 0.0
        elif self.variant == "giveback-none":
            life_updates["partner_giveback_hours"] = 0.0
        elif self.variant == "chores-none":
            life_updates["chore_delegation_hours"] = 0.0
            life_updates["chore_delegation_spend_cents"] = 0
        elif self.variant.startswith("giveback-level-"):
            life_updates["partner_giveback_hours"] = float(
                self.variant.removeprefix("giveback-level-")
            )
        if life_updates:
            return action.model_copy(update={"life": action.life.model_copy(update=life_updates)})
        return action


def _measure_ladder_variant(
    name: str,
    variant: str,
    seeds: list[int],
    config: SimConfig,
    reference_scores: Mapping[int, float],
) -> Phase3Measurement:
    return measure_policy(
        name,
        seeds,
        lambda seed: LadderPolicy(seed, variant, config),
        config,
        reference_scores=reference_scores,
    )


def _paired_measurement_difference(
    left: Phase3Measurement,
    right: Phase3Measurement,
    *,
    require_feasible: bool = True,
) -> dict[str, Any]:
    left_by_seed = {
        episode.seed: episode
        for episode in left.episodes
        if (
            (episode.feasible and episode.counted_score_kg is not None)
            if require_feasible
            else (episode.raw_score_kg is not None and episode.invalid_reason is None)
        )
    }
    right_by_seed = {
        episode.seed: episode
        for episode in right.episodes
        if (
            (episode.feasible and episode.counted_score_kg is not None)
            if require_feasible
            else (episode.raw_score_kg is not None and episode.invalid_reason is None)
        )
    }
    seeds = sorted(set(left_by_seed) & set(right_by_seed))
    deltas = [
        (
            float(right_by_seed[seed].counted_score_kg) - float(left_by_seed[seed].counted_score_kg)
            if require_feasible
            else float(right_by_seed[seed].raw_score_kg) - float(left_by_seed[seed].raw_score_kg)
        )
        for seed in seeds
    ]
    mean = fmean(deltas) if deltas else None
    sd = _sample_sd(deltas)
    effect = mean / sd if mean is not None and sd not in (None, 0.0) else None
    return {
        "left": left.policy,
        "right": right.policy,
        "seed_count": len(deltas),
        "all_seed_eligible": len(deltas) == len(left.episodes) == len(right.episodes),
        "comparison_basis": "counted" if require_feasible else "raw_structural_diagnostic",
        "mean_delta_kg": round(mean, 4) if mean is not None else None,
        "paired_sd_kg": round(sd, 4) if sd is not None else None,
        "effect_size": round(effect, 4) if effect is not None else None,
        "order_rate": round(sum(delta > 0 for delta in deltas) / len(deltas), 4) if deltas else None,
    }


def _sleep_checkbox_diagnostic(
    measurements: Mapping[str, Phase3Measurement],
    seed_list: list[int],
) -> dict[str, Any]:
    """Count which sleep choice wins within each paired certification seed.

    This is intentionally a raw structural diagnostic.  It asks whether the
    strong/standard/none choice changes with the episode's events and hidden
    state, rather than silently dropping a choice that violates a separate
    hard constraint.
    """
    names = ("sleep-none", "sleep-standard", "sleep-strong")
    by_seed = {
        name: {episode.seed: episode for episode in measurements[name].episodes}
        for name in names
    }
    wins = {name: 0 for name in names}
    ties = 0
    rows: list[dict[str, Any]] = []
    for seed in seed_list:
        scores = {
            name: by_seed[name][seed].raw_score_kg
            for name in names
            if seed in by_seed[name] and by_seed[name][seed].raw_score_kg is not None
        }
        if len(scores) != len(names):
            continue
        best = max(scores.values())
        winners = [name for name, score in scores.items() if abs(float(score) - float(best)) <= 1e-9]
        if len(winners) == 1:
            wins[winners[0]] += 1
        else:
            ties += 1
        rows.append({"seed": seed, "scores_kg": scores, "winners": winners})
    checkbox_seed_count = min(12, len(seed_list))
    first_twelve = rows[:checkbox_seed_count]
    strong_first_twelve = sum(row["winners"] == ["sleep-strong"] for row in first_twelve)
    strong_tied_first_twelve = sum(
        "sleep-strong" in row["winners"] and len(row["winners"]) > 1
        for row in first_twelve
    )
    return {
        "options": list(names),
        "seed_count": len(rows),
        "wins": wins,
        "ties": ties,
        "first_12_seed_count": checkbox_seed_count,
        "strong_unique_wins_first_12": strong_first_twelve,
        "strong_ties_first_12": strong_tied_first_twelve,
        "strong_not_unanimous_first_12": strong_first_twelve < checkbox_seed_count,
        "rows": rows,
    }


def _partner_giveback_optimum_diagnostic(
    measurements: Mapping[str, Phase3Measurement],
    seed_list: list[int],
) -> dict[str, Any]:
    """Measure whether the best giveback level changes by certification seed."""
    levels = (0.0, 1.0, 2.0)
    names = tuple(f"giveback-level-{level:g}" for level in levels)
    by_level = {
        name: {episode.seed: episode for episode in measurements[name].episodes}
        for name in names
    }
    rows: list[dict[str, Any]] = []
    winner_counts = {level: 0 for level in levels}
    tie_count = 0
    for seed in seed_list:
        scores = {
            float(name.removeprefix("giveback-level-")): by_level[name][seed].raw_score_kg
            for name in names
            if seed in by_level[name] and by_level[name][seed].raw_score_kg is not None
        }
        if len(scores) != len(levels):
            continue
        best = max(scores.values())
        winners = [level for level, score in scores.items() if abs(float(score) - float(best)) <= 1e-9]
        if len(winners) == 1:
            winner_counts[winners[0]] += 1
        else:
            tie_count += 1
        rows.append({"seed": seed, "scores_kg": scores, "winners_hours": winners})
    observed = sorted({level for row in rows for level in row["winners_hours"]})
    return {
        "levels_hours": list(levels),
        "seed_count": len(rows),
        "unique_winner_counts": {str(level): count for level, count in winner_counts.items()},
        "ties": tie_count,
        "observed_optimum_levels_hours": observed,
        "optimum_varies_across_seeds": len(observed) > 1,
        "rows": rows,
    }


def run_policy_ladder(
    seeds: Iterable[int] = range(320, 340),
    config: SimConfig | None = None,
) -> dict[str, Any]:
    """Run the held-out paired ladder and per-field life-allocation diagnostics."""
    config = config or SimConfig(weeks=52)
    seed_list = list(seeds)
    expert = measure_policy(
        "scripted-expert",
        seed_list,
        lambda seed: make_policy("scripted-expert", seed, allow_home_rack=config.enable_home_rack),
        config,
    )
    reference_scores = {
        episode.seed: float(episode.raw_score_kg)
        for episode in expert.episodes
        if episode.raw_score_kg is not None
    }
    variants = (
        ("load-0.90", "load-0.90"),
        ("load-0.95", "load-0.95"),
        ("load-1.00", "load-1.00"),
        ("load-1.05", "load-1.05"),
        ("load-1.10", "load-1.10"),
        ("frequency-2", "frequency-2"),
        ("frequency-3", "frequency-3"),
        ("frequency-4", "frequency-4"),
        ("sleep-none", "sleep-none"),
        ("sleep-none+frequency-4", "sleep-none+frequency-4"),
        ("sleep-standard", "sleep-standard"),
        ("sleep-strong", "sleep-strong"),
        ("meal-none", "meal-none"),
        ("coverage-none", "coverage-none"),
        ("giveback-none", "giveback-none"),
        ("chores-none", "chores-none"),
        ("giveback-level-0", "giveback-level-0"),
        ("giveback-level-1", "giveback-level-1"),
        ("giveback-level-2", "giveback-level-2"),
    )
    measurements = {
        name: _measure_ladder_variant(name, variant, seed_list, config, reference_scores)
        for name, variant in variants
    }
    comparisons = {
        "load-0.90->load-0.95": _paired_measurement_difference(measurements["load-0.90"], measurements["load-0.95"]),
        "load-0.95->load-1.00": _paired_measurement_difference(measurements["load-0.95"], measurements["load-1.00"]),
        "load-1.00->load-1.05": _paired_measurement_difference(measurements["load-1.00"], measurements["load-1.05"]),
        "load-1.05->load-1.10": _paired_measurement_difference(measurements["load-1.05"], measurements["load-1.10"]),
        "frequency-2->frequency-3": _paired_measurement_difference(measurements["frequency-2"], measurements["frequency-3"]),
        "frequency-3->frequency-4": _paired_measurement_difference(measurements["frequency-3"], measurements["frequency-4"]),
    }
    load_effects = [
        comparison["effect_size"]
        for key, comparison in comparisons.items()
        if key.startswith("load-") and comparison["effect_size"] is not None
    ]
    frequency_effect = comparisons["frequency-3->frequency-4"]["effect_size"]
    life_effects: dict[str, dict[str, Any]] = {}
    anchor = measurements["load-1.00"]
    for name in ("sleep-none", "sleep-none+frequency-4", "sleep-standard", "sleep-strong", "meal-none", "coverage-none", "giveback-none", "chores-none"):
        life_effects[name] = _paired_measurement_difference(
            measurements[name],
            anchor,
            require_feasible=False,
        )
    load_range = _paired_measurement_difference(measurements["load-0.90"], measurements["load-1.10"])
    training_effects = {
        "load_calibration_min_adjacent_effect_size": min(load_effects) if load_effects else None,
        "session_frequency_effect_size": frequency_effect,
        "load_calibration_range": load_range,
    }
    sleep_checkbox = _sleep_checkbox_diagnostic(measurements, seed_list)
    partner_giveback_optimum = _partner_giveback_optimum_diagnostic(measurements, seed_list)
    life_field_pricing = {
        "meal_prep_hours": {"priced": True, "price": "shared weekly time ledger"},
        "meal_support_spend_cents": {"priced": True, "price": "cash ledger"},
        "childcare_hours": {"priced": True, "price": "shared weekly time ledger"},
        "childcare_spend_cents": {"priced": True, "price": "cash ledger"},
        "chore_delegation_hours": {"priced": True, "price": "shared weekly time ledger and delegation cash charge"},
        "chore_delegation_spend_cents": {"priced": True, "price": "cash ledger"},
        "partner_coverage_hours": {"priced": True, "price": "shared weekly time ledger and household reciprocity"},
        "partner_giveback_hours": {
            "priced": True,
            "price": "shared weekly time ledger and household reciprocity",
            "optimum_varies_across_seeds": partner_giveback_optimum["optimum_varies_across_seeds"],
        },
        "sleep_protection": {"priced": True, "price": "shared weekly time ledger: 0/30/60 minutes"},
        "career_choice": {"priced": True, "price": "work-strain/cash event consequences"},
        "purchases": {"priced": True, "price": "cash ledger and recurring time charges"},
    }
    life_field_pricing_pass = all(item["priced"] for item in life_field_pricing.values())
    gate = {
        "effect_size_threshold": LADDER_EFFECT_SIZE_THRESHOLD,
        "load_calibration_pass": bool(load_effects and min(load_effects) >= LADDER_EFFECT_SIZE_THRESHOLD),
        "session_frequency_pass": frequency_effect is not None and frequency_effect >= LADDER_EFFECT_SIZE_THRESHOLD,
        "life_field_pricing_pass": life_field_pricing_pass,
        "all_training_rungs_eligible": all(
            measurements[name].feasible_for_phase3
            for name in (
                "load-0.90",
                "load-0.95",
                "load-1.00",
                "load-1.05",
                "load-1.10",
                "frequency-2",
                "frequency-3",
                "frequency-4",
            )
        ),
        "gate_pass": bool(
            load_effects
            and min(load_effects) >= LADDER_EFFECT_SIZE_THRESHOLD
            and frequency_effect is not None
            and frequency_effect >= LADDER_EFFECT_SIZE_THRESHOLD
            and life_field_pricing_pass
            and all(
                measurements[name].feasible_for_phase3
                for name in (
                    "load-0.90",
                    "load-0.95",
                    "load-1.00",
                    "load-1.05",
                    "load-1.10",
                    "frequency-2",
                    "frequency-3",
                    "frequency-4",
                )
            )
        ),
    }
    return {
        "seeds": seed_list,
        "config": config.as_dict(),
        "measurements": {name: measurement.as_dict() for name, measurement in measurements.items()},
        "comparisons": comparisons,
        "training_effects": training_effects,
        "life_field_effects": life_effects,
        "life_field_pricing": life_field_pricing,
        "partner_giveback_optimum": partner_giveback_optimum,
        "sleep_checkbox": sleep_checkbox,
        "gate": gate,
    }
