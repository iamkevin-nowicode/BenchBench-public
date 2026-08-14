"""Score-validity rules shared by the evaluator and transcript analyzer."""

from __future__ import annotations

from typing import Any


# Pain is the only behavioral constraint on the headline score. Household
# strain and sleep debt remain visible diagnostics and are deliberately not
# included here.
PAIN_DAYS_LIMIT = 14
MAX_EPISODE_DAYS = 364

# A counted aggregate must cover the complete expected seed set.  Reporting a
# mean over only the surviving episodes creates a score-correlated selection
# effect: a policy can sacrifice most seeds and rank on its easiest survivors.
# The raw per-seed result remains available for diagnostics when this gate is
# not met.
MIN_COUNTED_SEED_FRACTION = 1.0


def constraint_violations(*, pain_days: int | float | None) -> tuple[str, ...]:
    """Return the hard-score violations for an episode."""
    if (
        not isinstance(pain_days, int)
        or isinstance(pain_days, bool)
        or not 0 <= pain_days <= MAX_EPISODE_DAYS
    ):
        if pain_days is None:
            return ("missing_pain_days",)
        return ("invalid_pain_days",)
    if pain_days > PAIN_DAYS_LIMIT:
        return (f"pain_days>{PAIN_DAYS_LIMIT}",)
    return ()


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
) -> dict[str, Any]:
    """Build the stable raw/counted/violations representation used in reports."""
    violations = constraint_violations(pain_days=pain_days)
    return {
        "raw_final_1rm_kg": float(raw_score) if raw_score is not None else None,
        "counted_final_1rm_kg": counted_score(
            raw_score,
            invalid_reason=invalid_reason,
            violations=violations,
        ),
        "constraint_violations": list(violations),
    }
