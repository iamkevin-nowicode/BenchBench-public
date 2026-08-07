"""Public observation and action schemas.

Only these schemas cross the simulator boundary.  Hidden state is deliberately
represented by private engine dataclasses rather than an observation model.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Slot = Literal["morning", "lunch", "evening"]
Location = Literal["gym", "home", "hotel"]
Focus = Literal["volume", "heavy", "technique", "fallback", "test"]
SleepRule = Literal["fallback", "skip", "reduce"]
PainRule = Literal["reduce", "fallback", "skip"]
IllnessRule = Literal["protect_recovery", "fallback", "skip"]
CapitalPurchase = Literal["home_gym", "recurring_childcare", "meal_prep_subscription"]


class SchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SessionPlan(SchemaBase):
    day: int = Field(ge=0, le=6)
    slot: Slot = "evening"
    location: Location = "gym"
    focus: Focus = "volume"
    sets: int = Field(default=3, ge=1, le=8)
    reps: int = Field(default=5, ge=1, le=15)
    load_kg: float = Field(default=60.0, ge=0.0, le=250.0)
    duration_min: int = Field(default=45, ge=10, le=120)
    target_rpe: float = Field(default=7.0, ge=5.0, le=10.0)

    @model_validator(mode="after")
    def validate_focus(self) -> "SessionPlan":
        if self.focus == "fallback":
            if self.duration_min > 25 or self.sets > 3 or self.reps > 6:
                raise ValueError("fallback sessions must be at most 25 minutes, three sets, and six reps")
        if self.focus == "test" and self.reps != 1:
            raise ValueError("test sessions use one-rep attempts")
        return self


class LifeAllocation(SchemaBase):
    meal_prep_hours: float = Field(default=2.0, ge=0.0, le=10.0)
    meal_support_spend_cents: int = Field(default=0, ge=0, le=25_000)
    childcare_hours: float = Field(default=0.0, ge=0.0, le=24.0)
    childcare_spend_cents: int = Field(default=0, ge=0, le=25_000)
    chore_delegation_hours: float = Field(default=0.0, ge=0.0, le=12.0)
    chore_delegation_spend_cents: int = Field(default=0, ge=0, le=25_000)
    partner_coverage_hours: float = Field(default=2.0, ge=0.0, le=16.0)
    partner_giveback_hours: float = Field(default=2.0, ge=0.0, le=16.0)
    sleep_protection: Literal["none", "standard", "strong"] = "standard"
    career_choice: Literal["protect_time", "accept_stretch_project", "defer"] = "protect_time"
    purchases: list[CapitalPurchase] = Field(default_factory=list, max_length=3)

    @field_validator("purchases", mode="before")
    @classmethod
    def normalize_purchase_sentinel(cls, value: object) -> object:
        """Accept common no-purchase/string forms without changing the public type."""
        if value is None:
            return []
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "none", "no purchases", "no-purchases", "no_purchase", "[]"}:
                return []
            if normalized in {"home_gym", "recurring_childcare", "meal_prep_subscription"}:
                return [normalized]
        return value

    @model_validator(mode="after")
    def validate_purchases(self) -> "LifeAllocation":
        if len(set(self.purchases)) != len(self.purchases):
            raise ValueError("capital purchases must be unique")
        return self


class StandingRules(SchemaBase):
    on_sleep_below_5h: SleepRule = "fallback"
    on_pain_warning: PainRule = "reduce"
    on_illness: IllnessRule = "protect_recovery"
    preserve_one_fallback: bool = True


class WeekAction(SchemaBase):
    sessions: list[SessionPlan] = Field(default_factory=list, max_length=5)
    life: LifeAllocation = Field(default_factory=LifeAllocation)
    rules: StandingRules = Field(default_factory=StandingRules)
    coach_note: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def validate_days(self) -> "WeekAction":
        days = [session.day for session in self.sessions]
        if len(days) != len(set(days)):
            raise ValueError("at most one planned session may use each day")
        if len(self.sessions) > 5:
            raise ValueError("at most five sessions are allowed")
        return self


class ReactiveAction(SchemaBase):
    response: Literal["protect_recovery", "reallocate", "preserve_training", "accept_disruption"] = "protect_recovery"
    cancel_session_days: list[int] = Field(default_factory=list, max_length=5)
    fallback_session_days: list[int] = Field(default_factory=list, max_length=5)
    extra_childcare_hours: float = Field(default=0.0, ge=0.0, le=8.0)
    extra_spend_cents: int = Field(default=0, ge=0, le=15_000)
    note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def validate_days(self) -> "ReactiveAction":
        for day in [*self.cancel_session_days, *self.fallback_session_days]:
            if day < 0 or day > 6:
                raise ValueError("reactive session days must be between 0 and 6")
        if set(self.cancel_session_days) & set(self.fallback_session_days):
            raise ValueError("a day cannot be both cancelled and converted")
        return self


class PlannedEvent(SchemaBase):
    week: int = Field(ge=1, le=52)
    title: str
    detail: str
    lead_weeks: int = Field(ge=0, le=8)


class RecentWeek(SchemaBase):
    week: int = Field(ge=0, le=52)
    planned_sessions: int = Field(ge=0, le=5)
    transformed_sessions: int = Field(ge=0, le=5)
    attempted_sessions: int = Field(ge=0, le=5)
    completed_sessions: int = Field(ge=0, le=5)
    fallback_sessions: int = Field(ge=0, le=5)
    missed_sessions: int = Field(ge=0, le=5)
    average_sleep_hours: float = Field(ge=0.0, le=12.0)
    estimated_1rm_kg: float = Field(ge=0.0, le=300.0)
    headline: str


class WeekObservation(SchemaBase):
    episode_week: int = Field(ge=1, le=52)
    total_weeks: int = Field(ge=1, le=52)
    baby_age_months: float = Field(ge=6.0, le=24.0)
    estimated_1rm_kg: float = Field(ge=0.0, le=300.0)
    estimated_1rm_low_kg: float = Field(ge=0.0, le=300.0)
    estimated_1rm_high_kg: float = Field(ge=0.0, le=300.0)
    recent_sessions: int = Field(ge=0, le=5)
    sleep_band: Literal["depleted", "strained", "okay", "good"]
    energy_band: Literal["low", "medium", "high"]
    soreness_band: Literal["none", "mild", "moderate", "high"]
    pain_band: Literal["none", "warning", "limiting", "recovery"]
    illness_status: Literal["clear", "exposed", "active", "recovering"]
    nutrition_band: Literal["insufficient", "adequate", "high_support"]
    body_mass_kg: float = Field(ge=40.0, le=180.0)
    body_mass_trend: Literal["falling", "stable", "rising"]
    budget_available_cents: int = Field(ge=0)
    current_month_spend_cents: int = Field(ge=0)
    weekly_time_budget_minutes: int = Field(default=900, ge=0)
    equipment: list[str]
    household_strain_band: Literal["low", "medium", "high", "critical"]
    work_strain_band: Literal["low", "medium", "high"]
    available_time_bands: list[Literal["tight", "normal", "open"]]
    this_week_signals: list[str]
    known_obligations: list[str]
    upcoming_known_events: list[PlannedEvent]
    recent_weeks: list[RecentWeek]
    last_interrupt: str | None = None


class InterruptObservation(SchemaBase):
    episode_week: int = Field(ge=1, le=52)
    day: int = Field(ge=0, le=6)
    kind: Literal["illness_onset", "daycare_closure", "gym_closed", "partner_illness", "household_shock"]
    title: str
    detail: str
    severity: Literal["low", "medium", "high"]
    affected_session_days: list[int]
    visible_options: list[str]
    weekly_time_remaining_minutes: int = Field(default=0, ge=0)
