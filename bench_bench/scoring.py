"""Score-validity rules shared by the evaluator and transcript analyzer."""

from __future__ import annotations

from typing import Any


# Pain and sustained household strain are the v0.2 behavioral constraints on
# the headline score. Sleep debt remains a diagnostic because it already
# lowers readiness and recovery endogenously.
PAIN_DAYS_LIMIT = 14
HOUSEHOLD_STRAIN_LIMIT = 0.75
HOUSEHOLD_STRAIN_HIGH_WEEK_LIMIT = 4
MAX_EPISODE_DAYS = 364

# A counted aggregate must cover the complete expected seed set.  Reporting a
# mean over only the surviving episodes creates a score-correlated selection
# effect: a policy can sacrifice most seeds and rank on its easiest survivors.
# The raw per-seed result remains available for diagnostics when this gate is
# not met.
MIN_COUNTED_SEED_FRACTION = 1.0


def constraint_violations(
    *,
    pain_days: int | float | None,
    household_strain_high_weeks: int | float | None = None,
    final_third_mean_household_strain: int | float | None = None,
    household_strain_limit: float = HOUSEHOLD_STRAIN_LIMIT,
    household_strain_high_week_limit: int = HOUSEHOLD_STRAIN_HIGH_WEEK_LIMIT,
) -> tuple[str, ...]:
    """Return the hard-score violations for an episode."""
    violations: list[str] = []
    if (
        not isinstance(pain_days, int)
        or isinstance(pain_days, bool)
        or not 0 <= pain_days <= MAX_EPISODE_DAYS
    ):
        if pain_days is None:
            violations.append("missing_pain_days")
        else:
            violations.append("invalid_pain_days")
    elif pain_days > PAIN_DAYS_LIMIT:
        violations.append(f"pain_days>{PAIN_DAYS_LIMIT}")
    if (
        not isinstance(household_strain_high_weeks, int)
        or isinstance(household_strain_high_weeks, bool)
        or not 0 <= household_strain_high_weeks <= MAX_EPISODE_DAYS
    ):
        if household_strain_high_weeks is None:
            violations.append("missing_household_strain_high_weeks")
        else:
            violations.append("invalid_household_strain_high_weeks")
    elif household_strain_high_weeks >= household_strain_high_week_limit:
        violations.append(f"household_strain_high_weeks>={household_strain_high_week_limit}")
    if (
        not isinstance(final_third_mean_household_strain, (int, float))
        or isinstance(final_third_mean_household_strain, bool)
        or not 0.0 <= float(final_third_mean_household_strain) <= 1.0
    ):
        if final_third_mean_household_strain is None:
            violations.append("missing_final_third_household_strain")
        else:
            violations.append("invalid_final_third_household_strain")
    elif float(final_third_mean_household_strain) > household_strain_limit:
        violations.append(f"final_third_household_strain>{household_strain_limit:g}")
    return tuple(violations)


def counted_score(
    raw_score: float | int | None,
    *,
    invalid_reason: str | None,
    violations: tuple[str, ...] | list[str] = (),
) -> float | None:
    """Return a headline score only for structurally and behaviorally valid episodes."""
    if raw_score is None or invalid_reason is not None or violations:
        return None
    return float(raw_score)


def score_fields(
    raw_score: float | int | None,
    *,
    invalid_reason: str | None,
    pain_days: int | float | None,
    household_strain_high_weeks: int | float | None = None,
    final_third_mean_household_strain: int | float | None = None,
    household_strain_limit: float = HOUSEHOLD_STRAIN_LIMIT,
    household_strain_high_week_limit: int = HOUSEHOLD_STRAIN_HIGH_WEEK_LIMIT,
) -> dict[str, Any]:
    """Build the stable raw/counted/violations representation used in reports."""
    violations = constraint_violations(
        pain_days=pain_days,
        household_strain_high_weeks=household_strain_high_weeks,
        final_third_mean_household_strain=final_third_mean_household_strain,
        household_strain_limit=household_strain_limit,
        household_strain_high_week_limit=household_strain_high_week_limit,
    )
    return {
        "raw_final_1rm_kg": float(raw_score) if raw_score is not None else None,
        "counted_final_1rm_kg": counted_score(
            raw_score,
            invalid_reason=invalid_reason,
            violations=violations,
        ),
        "constraint_violations": list(violations),
    }
