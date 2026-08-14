"""Simulation configuration.

The engine is 52-week native.  A shorter configuration is only a validation
window; it does not switch the simulator to a different model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimConfig:
    weeks: int = 52
    monthly_budget_cents: int = 25_000
    starting_cash_cents: int = 25_000
    starting_body_mass_kg: float = 84.0
    starting_estimated_1rm_kg: float = 84.0
    starting_base_capacity_kg: float = 84.0
    fit_tau_days: float = 56.0
    fatigue_tau_days: float = 10.0
    technique_tau_sessions: float = 34.0
    # Brzycki-style coupling prevents a high-rep prescription from claiming
    # the same stimulus as a plausible set at the requested load.  The small
    # tolerance preserves ordinary training prescriptions while making the
    # ceiling explicit and deterministic.
    brzycki_repmax_ceiling_ratio: float = 1.30
    # Directly authored fallback actions are rejected during validation when
    # their load exceeds this visible estimated-1RM ratio. Coerced fallback
    # sessions still receive the same conservative transform in the engine.
    fallback_max_load_ratio: float = 0.78
    # The v0.2 curve has no hard weekly stimulus cap.  It has a hidden,
    # per-episode optimum and a smooth over-reaching penalty beyond it.
    weekly_stimulus_optimum: float = 0.90
    weekly_overreach_penalty_strength: float = 0.90
    # Backwards-compatible input name for old offline experiments.  It is an
    # optimum override, never a hard output cap.
    weekly_stimulus_cap: float | None = None
    # Loads below this ratio are warm-up-only: they may occupy a session, but
    # do not produce strength stimulus or technique credit.
    minimum_meaningful_load_ratio: float = 0.35
    # A session cannot claim more than this many prescribed repetitions per
    # minute. The limit applies to every focus, including fallback.
    session_reps_per_minute: float = 1.0
    productive_week_stimulus_threshold: float = 0.20
    # One shared discretionary household-time pool. It covers training plus
    # the life allocations in the weekly action.
    weekly_time_budget_minutes: int = 900
    # Unavoidable childcare, chores, and household administration are charged
    # from the same pool before an authored allocation is considered.
    weekly_fixed_household_minutes: int = 180
    delegated_chore_cost_per_hour_cents: int = 1_200
    reactive_childcare_cost_per_hour_cents: int = 1_400
    # Calibration adopted after durable-capacity drift and multi-test scoring;
    # later stimulus-curve corrections are accepted without retuning these
    # strength coefficients to restore an earlier headline score.
    fitness_to_strength_kg: float = 2.40
    fatigue_to_strength_kg: float = 0.20
    # Sustained consistency can raise the athlete's durable base capacity.
    # The engine starts applying this drift only after the configured
    # consecutive productive-week streak has been established.
    productive_streak_weeks_for_capacity_drift: int = 4
    capacity_drift_kg_per_productive_week: float = 0.10
    # A commercial-gym visit includes a modest round-trip commute.  The home
    # rack still saves setup time, but it is not meant to dominate the model.
    gym_commute_minutes: int = 20
    home_session_overhead_minutes: int = 10
    hotel_commute_minutes: int = 20
    # Saved transition time improves the amount of productive work that fits
    # in a week.  The no-spotter cap below is the countervailing limitation.
    home_training_efficiency: float = 1.10
    home_no_spotter_max_ratio: float = 0.88
    injury_load_onset_ratio: float = 0.90
    injury_volume_threshold_units: float = 1.15
    injury_exposure_scale: float = 0.18
    household_strain_limit: float = 0.75
    enable_home_rack: bool = True
    max_sessions_per_week: int = 5
    max_action_repairs: int = 1
    enable_sleep_system: bool = True
    enable_delayed_adaptation: bool = True
    enable_event_system: bool = True
    enable_injury_system: bool = True
    enable_household_system: bool = True
    enable_money_system: bool = True
    # Keep session failure causes opaque to the agent by default.  Evaluation
    # and debugging runs can opt into a per-session reason in WeekOutcome.
    expose_session_failure_reasons: bool = False

    @property
    def days(self) -> int:
        return self.weeks * 7

    @property
    def weekly_budget_cents(self) -> int:
        # A simple four-week accounting month keeps the benchmark readable.
        return self.monthly_budget_cents // 4

    @property
    def effective_weekly_stimulus_optimum(self) -> float:
        """Return the smooth-curve optimum, honoring the legacy alias."""
        if self.weekly_stimulus_cap is not None:
            return max(0.05, float(self.weekly_stimulus_cap))
        return max(0.05, float(self.weekly_stimulus_optimum))

    @classmethod
    def twelve_week(cls) -> "SimConfig":
        return cls(weeks=12)

    def as_dict(self) -> dict[str, object]:
        return {
            "weeks": self.weeks,
            "monthly_budget_cents": self.monthly_budget_cents,
            "starting_cash_cents": self.starting_cash_cents,
            "starting_body_mass_kg": self.starting_body_mass_kg,
            "starting_estimated_1rm_kg": self.starting_estimated_1rm_kg,
            "starting_base_capacity_kg": self.starting_base_capacity_kg,
            "fit_tau_days": self.fit_tau_days,
            "fatigue_tau_days": self.fatigue_tau_days,
            "technique_tau_sessions": self.technique_tau_sessions,
            "brzycki_repmax_ceiling_ratio": self.brzycki_repmax_ceiling_ratio,
            "fallback_max_load_ratio": self.fallback_max_load_ratio,
            "weekly_stimulus_cap": self.weekly_stimulus_cap,
            "weekly_stimulus_optimum": self.weekly_stimulus_optimum,
            "weekly_overreach_penalty_strength": self.weekly_overreach_penalty_strength,
            "minimum_meaningful_load_ratio": self.minimum_meaningful_load_ratio,
            "session_reps_per_minute": self.session_reps_per_minute,
            "productive_week_stimulus_threshold": self.productive_week_stimulus_threshold,
            "weekly_time_budget_minutes": self.weekly_time_budget_minutes,
            "weekly_fixed_household_minutes": self.weekly_fixed_household_minutes,
            "delegated_chore_cost_per_hour_cents": self.delegated_chore_cost_per_hour_cents,
            "reactive_childcare_cost_per_hour_cents": self.reactive_childcare_cost_per_hour_cents,
            "fitness_to_strength_kg": self.fitness_to_strength_kg,
            "fatigue_to_strength_kg": self.fatigue_to_strength_kg,
            "productive_streak_weeks_for_capacity_drift": self.productive_streak_weeks_for_capacity_drift,
            "capacity_drift_kg_per_productive_week": self.capacity_drift_kg_per_productive_week,
            "gym_commute_minutes": self.gym_commute_minutes,
            "home_session_overhead_minutes": self.home_session_overhead_minutes,
            "hotel_commute_minutes": self.hotel_commute_minutes,
            "home_training_efficiency": self.home_training_efficiency,
            "home_no_spotter_max_ratio": self.home_no_spotter_max_ratio,
            "injury_load_onset_ratio": self.injury_load_onset_ratio,
            "injury_volume_threshold_units": self.injury_volume_threshold_units,
            "injury_exposure_scale": self.injury_exposure_scale,
            "household_strain_limit": self.household_strain_limit,
            "enable_home_rack": self.enable_home_rack,
            "max_sessions_per_week": self.max_sessions_per_week,
            "max_action_repairs": self.max_action_repairs,
            "enable_sleep_system": self.enable_sleep_system,
            "enable_delayed_adaptation": self.enable_delayed_adaptation,
            "enable_event_system": self.enable_event_system,
            "enable_injury_system": self.enable_injury_system,
            "enable_household_system": self.enable_household_system,
            "enable_money_system": self.enable_money_system,
            "expose_session_failure_reasons": self.expose_session_failure_reasons,
        }
