"""The v0.2 public constraint inventory and prompt rendering.

This module is the single prompt-facing source of truth for constraints that
cross the simulator boundary.  Each entry has a stable marker.  Rendered
prompts include those markers, which lets the conformance tests prove both
that every inventory item is disclosed and that no marked prompt constraint
has been added outside this inventory.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Literal


PromptSurface = Literal["weekly", "reactive"]


@dataclass(frozen=True)
class ConstraintEntry:
    key: str
    section: str
    text: str
    surfaces: tuple[PromptSurface, ...] = ("weekly",)
    rejection_tokens: tuple[str, ...] = ()

    @property
    def marker(self) -> str:
        return f"[constraint:{self.key}]"

    def render(self) -> str:
        return f"- {self.marker} {self.text}"


def _entries() -> tuple[ConstraintEntry, ...]:
    weekly = ("weekly",)
    reactive = ("reactive",)
    both = ("weekly", "reactive")
    return (
        ConstraintEntry("protocol.objective", "Protocol", "Objective: maximize Dave's bench press one-rep max.", both),
        ConstraintEntry(
            "protocol.scoring",
            "Protocol",
            "Scoring: the average of three standardized tests at weeks 44, 48, and 52; each test measures true capacity after a fixed three-day taper. The noisy weekly estimated 1RM is not the score.",
            weekly,
        ),
        ConstraintEntry("protocol.horizon", "Protocol", "Horizon: 52 weeks.", weekly),
        ConstraintEntry(
            "session.day",
            "Field constraints — SessionPlan",
            "SessionPlan.day is an integer from 0–6.",
            weekly,
            ("day",),
        ),
        ConstraintEntry(
            "session.slot",
            "Field constraints — SessionPlan",
            "SessionPlan.slot is one of morning, lunch, or evening.",
            weekly,
            ("slot",),
        ),
        ConstraintEntry(
            "session.location",
            "Field constraints — SessionPlan",
            "SessionPlan.location is one of gym, home, or hotel.",
            weekly,
            ("location",),
        ),
        ConstraintEntry(
            "session.focus",
            "Field constraints — SessionPlan",
            "SessionPlan.focus is one of volume, heavy, technique, fallback, or test.",
            weekly,
            ("focus",),
        ),
        ConstraintEntry(
            "session.sets",
            "Field constraints — SessionPlan",
            "SessionPlan.sets is an integer from 1–8.",
            weekly,
            ("sets",),
        ),
        ConstraintEntry(
            "session.reps",
            "Field constraints — SessionPlan",
            "SessionPlan.reps is an integer from 1–15.",
            weekly,
            ("reps",),
        ),
        ConstraintEntry(
            "session.load_kg",
            "Field constraints — SessionPlan",
            "SessionPlan.load_kg is a number from 0–250 kg.",
            weekly,
            ("load_kg",),
        ),
        ConstraintEntry(
            "session.duration_min",
            "Field constraints — SessionPlan",
            "SessionPlan.duration_min is an integer from 10–120 minutes.",
            weekly,
            ("duration_min",),
        ),
        ConstraintEntry(
            "session.target_rpe",
            "Field constraints — SessionPlan",
            "SessionPlan.target_rpe is a number from 5–10.",
            weekly,
            ("target_rpe",),
        ),
        ConstraintEntry(
            "life.meal_prep_hours",
            "Field constraints — LifeAllocation",
            "LifeAllocation.meal_prep_hours is 0–10 hours.",
            weekly,
            ("meal_prep_hours",),
        ),
        ConstraintEntry(
            "life.meal_support_spend_cents",
            "Field constraints — LifeAllocation",
            "LifeAllocation.meal_support_spend_cents is 0–25000¢.",
            weekly,
            ("meal_support_spend_cents",),
        ),
        ConstraintEntry(
            "life.childcare_hours",
            "Field constraints — LifeAllocation",
            "LifeAllocation.childcare_hours is 0–24 hours.",
            weekly,
            ("childcare_hours",),
        ),
        ConstraintEntry(
            "life.childcare_spend_cents",
            "Field constraints — LifeAllocation",
            "LifeAllocation.childcare_spend_cents is 0–25000¢.",
            weekly,
            ("childcare_spend_cents",),
        ),
        ConstraintEntry(
            "life.chore_delegation_hours",
            "Field constraints — LifeAllocation",
            "LifeAllocation.chore_delegation_hours is 0–12 hours.",
            weekly,
            ("chore_delegation_hours",),
        ),
        ConstraintEntry(
            "life.chore_delegation_spend_cents",
            "Field constraints — LifeAllocation",
            "LifeAllocation.chore_delegation_spend_cents is 0–25000¢.",
            weekly,
            ("chore_delegation_spend_cents",),
        ),
        ConstraintEntry(
            "life.partner_coverage_hours",
            "Field constraints — LifeAllocation",
            "LifeAllocation.partner_coverage_hours is 0–16 hours.",
            weekly,
            ("partner_coverage_hours",),
        ),
        ConstraintEntry(
            "life.partner_giveback_hours",
            "Field constraints — LifeAllocation",
            "LifeAllocation.partner_giveback_hours is 0–16 hours.",
            weekly,
            ("partner_giveback_hours",),
        ),
        ConstraintEntry(
            "life.sleep_protection",
            "Field constraints — LifeAllocation",
            "LifeAllocation.sleep_protection is one of none, standard, or strong.",
            weekly,
            ("sleep_protection",),
        ),
        ConstraintEntry(
            "life.career_choice",
            "Field constraints — LifeAllocation",
            "LifeAllocation.career_choice is one of protect_time, accept_stretch_project, or defer.",
            weekly,
            ("career_choice",),
        ),
        ConstraintEntry(
            "mechanic.career_week24",
            "Announced mechanics",
            "At the announced week-24 promotion fork, career_choice is resolved by the simulator: accept_stretch_project grants 12000¢ and starts an 8-week stretch-project period that reduces session availability and adds work strain; protect_time reduces work strain by 0.04; defer applies neither branch.",
            weekly,
            ("week-24", "12000", "8-week", "work strain"),
        ),
        ConstraintEntry(
            "life.purchases",
            "Field constraints — LifeAllocation",
            "LifeAllocation.purchases is a list of at most 3 values: home_gym, recurring_childcare, or meal_prep_subscription.",
            weekly,
            ("purchases",),
        ),
        ConstraintEntry(
            "rules.sleep",
            "Field constraints — StandingRules",
            "StandingRules.on_sleep_below_5h is one of fallback, skip, or reduce.",
            weekly,
            ("on_sleep_below_5h",),
        ),
        ConstraintEntry(
            "rules.pain",
            "Field constraints — StandingRules",
            "StandingRules.on_pain_warning is one of reduce, fallback, or skip.",
            weekly,
            ("on_pain_warning",),
        ),
        ConstraintEntry(
            "rules.illness",
            "Field constraints — StandingRules",
            "StandingRules.on_illness is one of protect_recovery, fallback, or skip.",
            weekly,
            ("on_illness",),
        ),
        ConstraintEntry(
            "rules.preserve_one_fallback",
            "Field constraints — StandingRules",
            "StandingRules.preserve_one_fallback is a boolean.",
            weekly,
            ("preserve_one_fallback",),
        ),
        ConstraintEntry(
            "week.sessions",
            "Field constraints — WeekAction",
            "WeekAction.sessions contains at most 5 sessions.",
            weekly,
            ("sessions",),
        ),
        ConstraintEntry(
            "week.coach_note",
            "Field constraints — WeekAction",
            "WeekAction.coach_note is at most 600 characters and is a concise coaching rationale or priority for the coming week, not a restatement of the full plan; notebook_update is the separate place for durable observations about Dave.",
            weekly,
            ("coach_note",),
        ),
        ConstraintEntry(
            "reactive.cancel_session_days",
            "Field constraints — ReactiveAction",
            "ReactiveAction.cancel_session_days is a list of at most 5 days.",
            reactive,
            ("cancel_session_days",),
        ),
        ConstraintEntry(
            "reactive.fallback_session_days",
            "Field constraints — ReactiveAction",
            "ReactiveAction.fallback_session_days is a list of at most 5 days.",
            reactive,
            ("fallback_session_days",),
        ),
        ConstraintEntry(
            "reactive.extra_childcare_hours",
            "Field constraints — ReactiveAction",
            "ReactiveAction.extra_childcare_hours is 0–8 hours, draws from the remaining weekly time/resource ledger, and must not exceed the minutes remaining in the interrupt observation.",
            reactive,
            ("extra_childcare_hours",),
        ),
        ConstraintEntry(
            "reactive.extra_spend_cents",
            "Field constraints — ReactiveAction",
            "ReactiveAction.extra_spend_cents is 0–15000¢; reactive childcare must be paid for.",
            reactive,
            ("extra_spend_cents",),
        ),
        ConstraintEntry(
            "reactive.note",
            "Field constraints — ReactiveAction",
            "ReactiveAction.note is at most 300 characters.",
            reactive,
            ("note",),
        ),
        ConstraintEntry(
            "reactive.response",
            "Field constraints — ReactiveAction",
            "ReactiveAction.response is one of protect_recovery, reallocate, preserve_training, or accept_disruption.",
            reactive,
            ("response",),
        ),
        ConstraintEntry(
            "schema.strict_types",
            "Schema-wide rules",
            "Action fields use strict types; numeric strings, string sentinels, and other implicit coercions are rejected.",
            both,
            ("valid integer", "valid number", "strict", "Input should"),
        ),
        ConstraintEntry(
            "schema.extra_fields",
            "Schema-wide rules",
            "Unknown fields are rejected; return only the documented action and notebook_update fields.",
            both,
            ("Extra inputs are not permitted",),
        ),
        ConstraintEntry(
            "turn.notebook_update",
            "Turn wrappers",
            "The notebook_update string is at most 2000 characters.",
            both,
            ("notebook_update",),
        ),
        ConstraintEntry(
            "cross.fallback_caps",
            "Cross-field rejection rules",
            "When focus is fallback, the session is capped at 25 minutes, 3 sets, and 6 reps.",
            weekly,
            ("fallback sessions", "25 minutes", "three sets", "six reps"),
        ),
        ConstraintEntry(
            "cross.test_reps",
            "Cross-field rejection rules",
            "A session whose focus is test must have reps == 1.",
            weekly,
            ("test sessions", "one-rep"),
        ),
        ConstraintEntry(
            "cross.purchase_unique",
            "Cross-field rejection rules",
            "Purchases must be unique.",
            weekly,
            ("purchases", "unique"),
        ),
        ConstraintEntry(
            "cross.one_session_per_day",
            "Cross-field rejection rules",
            "At most one planned session may use each day.",
            weekly,
            ("one planned session", "each day"),
        ),
        ConstraintEntry(
            "cross.max_sessions",
            "Cross-field rejection rules",
            "No weekly action may contain more than 5 sessions.",
            weekly,
            ("at most five sessions",),
        ),
        ConstraintEntry(
            "cross.reactive_days",
            "Cross-field rejection rules",
            "Reactive session days must be integers from 0–6.",
            reactive,
            ("reactive session days", "between 0 and 6"),
        ),
        ConstraintEntry(
            "cross.reactive_overlap",
            "Cross-field rejection rules",
            "A day cannot appear in both the cancel and fallback lists.",
            reactive,
            ("both cancelled and converted", "overlap"),
        ),
        ConstraintEntry(
            "engine.authored_fallback_load",
            "Engine rejections",
            "An authored fallback load above 0.78× the estimated 1RM is rejected; it is not silently clipped.",
            weekly,
            ("authored fallback load exceeds", "0.78", "permitted ceiling"),
        ),
        ConstraintEntry(
            "engine.weekly_ledger",
            "Engine rejections",
            "A weekly action that exceeds the shared time/resource ledger is rejected.",
            both,
            ("shared time/resource ledger", "weekly action requires"),
        ),
        ConstraintEntry(
            "engine.cash",
            "Engine rejections",
            "An action that exceeds available cash is rejected.",
            weekly,
            ("weekly action requires", "cents", "available"),
        ),
        ConstraintEntry(
            "engine.reactive_spend",
            "Engine rejections",
            "Reactive spend that exceeds available cash is rejected.",
            reactive,
            ("reactive action requires", "cents", "available"),
        ),
        ConstraintEntry(
            "engine.shock_reserve",
            "Engine rejections",
            "Scheduled household-shock reserve is unavailable for discretionary spending.",
            both,
            ("reserved for scheduled household shocks",),
        ),
        ConstraintEntry(
            "scoring.pain_days",
            "Scoring constraints",
            "A score is void if pain_days exceeds 14.",
            weekly,
            ("pain_days", "14"),
        ),
        ConstraintEntry(
            "scoring.household_strain",
            "Scoring constraints",
            "Household strain voids the score through either branch: at least 4 weeks at or above 0.75, or a final-third mean above 0.75.",
            weekly,
            ("household strain", "0.75", "final-third"),
        ),
        ConstraintEntry(
            "scoring.counted_aggregates",
            "Scoring constraints",
            "Counted aggregates require 100% of a policy's or model's seeds to be compliant; violated seeds are not silently dropped.",
            weekly,
            ("counted", "seeds", "compliant"),
        ),
        ConstraintEntry(
            "ledger.total",
            "Ledger and costs",
            "one 900-minute weekly budget is shared, including 180 fixed household minutes; 720 minutes remain usable for authored weekly allocations.",
            both,
            ("900", "180", "720"),
        ),
        ConstraintEntry(
            "ledger.observation",
            "Ledger and costs",
            "In the observation, weekly_time_budget_minutes reports 720 usable minutes and weekly_fixed_household_minutes reports the 180-minute committed reserve.",
            weekly,
            ("weekly_time_budget_minutes", "720", "weekly_fixed_household_minutes"),
        ),
        ConstraintEntry(
            "ledger.sleep_cost",
            "Ledger and costs",
            "Sleep protection costs 0 minutes for none, 30 minutes for standard, and 60 minutes for strong; severe sleep degrades execution and recovery.",
            both,
            ("sleep protection", "30", "60", "execution and recovery"),
        ),
        ConstraintEntry(
            "ledger.delegated_chores",
            "Ledger and costs",
            "Delegated chores cost 1200¢ per hour.",
            weekly,
            ("Delegated chores", "1200"),
        ),
        ConstraintEntry(
            "ledger.reactive_childcare",
            "Ledger and costs",
            "Reactive childcare costs 1400¢ per hour.",
            reactive,
            ("Reactive childcare", "1400"),
        ),
        ConstraintEntry(
            "ledger.commute",
            "Ledger and costs",
            "A gym session costs 20 commute minutes; a home session costs 10 overhead minutes.",
            weekly,
            ("gym session", "20", "home session", "10"),
        ),
        ConstraintEntry(
            "ledger.repair",
            "Ledger and costs",
            "Every invalid action receives one repair attempt; if it remains invalid, a safe fallback is substituted.",
            both,
            ("one repair", "safe fallback"),
        ),
        ConstraintEntry(
            "outcome.transformations",
            "Execution reporting",
            "The engine may transform a plan during execution. Transformations are counted and reported in the weekly outcome as transformed_sessions, transformation_reasons, reactive_action_fallbacks, and attempted_sessions.",
            weekly,
            ("transformed_sessions", "transformation_reasons", "reactive_action_fallbacks", "attempted_sessions"),
        ),
    )


ENTRIES: tuple[ConstraintEntry, ...] = _entries()
ENTRY_BY_KEY = {entry.key: entry for entry in ENTRIES}


def entries_for(surface: PromptSurface, *, include_protocol: bool = True) -> tuple[ConstraintEntry, ...]:
    return tuple(
        entry
        for entry in ENTRIES
        if surface in entry.surfaces
        and (include_protocol or entry.section != "Protocol")
    )


def render_inventory(surface: PromptSurface, *, include_protocol: bool = False) -> str:
    """Render the inventory entries relevant to one turn type."""
    lines: list[str] = ["Constraint inventory (the following rules are enforced):"]
    current_section: str | None = None
    for entry in entries_for(surface, include_protocol=include_protocol):
        if entry.section != current_section:
            current_section = entry.section
            lines.append(f"\n{current_section}:")
        lines.append(entry.render())
    return "\n".join(lines) + "\n"


def render_protocol_summary() -> str:
    """Render the protocol statements repeated at the top and bottom."""
    return "\n".join(
        ENTRY_BY_KEY[key].render()
        for key in ("protocol.objective", "protocol.scoring", "protocol.horizon")
    )


def render_objective() -> str:
    return ENTRY_BY_KEY["protocol.objective"].render()


def all_markers() -> frozenset[str]:
    return frozenset(entry.marker for entry in ENTRIES)


def prompt_hash(weekly_prompt: str, reactive_prompt: str) -> str:
    payload = json.dumps(
        {"weekly": weekly_prompt, "reactive": reactive_prompt},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def rejection_tokens() -> frozenset[str]:
    """Return all source-level error fragments represented in the inventory."""
    return frozenset(token.lower() for entry in ENTRIES for token in entry.rejection_tokens)


def prompt_markers(text: str) -> frozenset[str]:
    """Extract the stable marker vocabulary from a rendered prompt."""
    import re

    return frozenset(re.findall(r"\[constraint:[a-z0-9_.-]+\]", text))


def every_entry_rendered(*prompts: str) -> bool:
    combined = "\n".join(prompts)
    return all(entry.marker in combined for entry in ENTRIES)


def iter_uninventoried_prompt_markers(*prompts: str) -> Iterable[str]:
    known = all_markers()
    found = prompt_markers("\n".join(prompts))
    return sorted(found - known)
