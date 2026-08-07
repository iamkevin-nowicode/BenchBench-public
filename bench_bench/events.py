"""The seeded year arc and the visible/hidden boundary for events."""

from dataclasses import dataclass
import random

from .rng import _rng, choose_unique


@dataclass(frozen=True)
class InterruptEvent:
    day: int
    kind: str
    severity: str
    title: str
    detail: str
    duration_days: int
    sleep_delta: float
    time_loss_min: int


@dataclass(frozen=True)
class WeekEvent:
    week: int
    sleep_pressure: float
    time_pressure_min: int
    illness_exposure: float
    gym_crowding: float
    open_days: tuple[int, ...]
    known_events: tuple[dict[str, object], ...]
    interrupts: tuple[InterruptEvent, ...]


class EventCalendar:
    """Pre-roll every event consequence before any agent action is observed."""

    def __init__(self, seed: int, weeks: int = 52, enabled: bool = True) -> None:
        self.seed = seed
        self.weeks = weeks
        self._weeks = self._build(seed, weeks, enabled)

    def week(self, week: int) -> WeekEvent:
        return self._weeks[week - 1]

    def _build(self, seed: int, weeks: int, enabled: bool) -> tuple[WeekEvent, ...]:
        availability_rng = _rng(seed, 33)

        def default_open_days() -> tuple[int, ...]:
            count = availability_rng.choice((3, 4))
            return tuple(sorted(availability_rng.sample(range(7), count)))

        if not enabled:
            return tuple(
                WeekEvent(
                    week=week,
                    sleep_pressure=0.18,
                    time_pressure_min=0,
                    illness_exposure=0.08,
                    gym_crowding=0.0,
                    open_days=default_open_days(),
                    known_events=(),
                    interrupts=(),
                )
                for week in range(1, weeks + 1)
            )
        rng = _rng(seed, 31)
        shock_rng = _rng(seed, 32)
        shock_weeks = choose_unique(shock_rng, range(3, min(51, weeks + 1)), min(5, max(2, weeks // 12)))
        shock_kinds = ["car repair", "household repair", "toddler ankle scare", "friend weekend", "jury-duty-style time loss"]
        shocks = {week: shock_kinds[i % len(shock_kinds)] for i, week in enumerate(shock_weeks)}

        built: list[WeekEvent] = []
        for week in range(1, weeks + 1):
            month = (week - 1) / 4.345
            sleep_pressure = 0.18
            time_pressure = 0
            illness_exposure = 0.08
            gym_crowding = 0.0
            known: list[dict[str, object]] = []
            interrupts: list[InterruptEvent] = []

            # The baby arc is deterministic and announced only where a family
            # could reasonably anticipate it.
            if 5 <= week <= 8:
                sleep_pressure += 0.62
                known.append({"title": "sleep regression window", "detail": "Nights may be less predictable as the baby learns to crawl.", "lead_weeks": 0})
            if 9 <= week <= 18:
                illness_exposure += 0.30
                if week == 9:
                    known.append({"title": "daycare begins", "detail": "The first daycare month usually costs extra flexibility.", "lead_weeks": 0})
            if 29 <= week <= 35:
                sleep_pressure += 0.55
                known.append({"title": "second sleep trough", "detail": "Molars and a second sleep regression may compete with recovery.", "lead_weeks": 0})
            if 36 <= week <= 52:
                illness_exposure += 0.12
            if 42 <= week <= 48:
                gym_crowding = 0.28
                known.append({"title": "winter gym crowding", "detail": "Commercial gym sessions may take longer through the New Year rush.", "lead_weeks": 1})

            # Predictable obligations are visible before the week begins.
            fixed_known: dict[int, tuple[str, str, int]] = {
                6: ("work crunch", "A fiscal-quarter deadline is announced two weeks ahead.", 2),
                14: ("grandparents visit", "A week of family help creates a temporary childcare window.", 1),
                19: ("business trip", "Hotel-gym access only; travel time is protected but tight.", 2),
                24: ("promotion fork", "A stretch-project offer trades money for time this quarter.", 3),
                26: ("first birthday", "A family obligation spike is coming this week.", 2),
                32: ("work crunch", "A performance-review period is announced two weeks ahead.", 2),
                39: ("family vacation", "Travel is predictable; pre-positioning matters.", 3),
                44: ("work crunch", "Year-end delivery pressure is announced two weeks ahead.", 2),
                47: ("holiday travel", "Gym access is unreliable for part of the holiday week.", 2),
            }
            if week in fixed_known:
                title, detail, lead = fixed_known[week]
                known.append({"title": title, "detail": detail, "lead_weeks": lead})
                if title == "work crunch":
                    time_pressure += 20
                elif title == "first birthday":
                    # The family obligation is visible in advance and also
                    # consumes flexible time when it arrives.
                    time_pressure += 18
            if week in (19, 39, 47):
                time_pressure += 28

            if week in shocks:
                kind = shocks[week]
                known.append({"title": "unplanned household pressure", "detail": "A one-off cost or time shock may arrive during the week.", "lead_weeks": 0})
                day = rng.randrange(1, 6)
                interrupts.append(
                    InterruptEvent(
                        day=day,
                        kind="household_shock",
                        severity="medium",
                        title=kind,
                        detail="A one-off household problem needs attention and competes with the plan.",
                        duration_days=1,
                        sleep_delta=0.15,
                        time_loss_min=55,
                    )
                )

            # Illness and closure triggers are pre-rolled.  Their existence is
            # hidden until the trigger day; alternate reactions never consume
            # another random draw.
            if 9 <= week <= 18 or week >= 36:
                if rng.random() < min(0.52, illness_exposure):
                    day = rng.randrange(0, 6)
                    severity = "high" if rng.random() < 0.26 else "medium"
                    interrupts.append(
                        InterruptEvent(
                            day=day,
                            kind="illness_onset",
                            severity=severity,
                            title="daycare illness enters the house",
                            detail="Someone in the household is ill. Protecting recovery now may prevent a longer washout.",
                            duration_days=5 if severity == "high" else 3,
                            sleep_delta=0.55 if severity == "high" else 0.32,
                            time_loss_min=45 if severity == "high" else 25,
                        )
                    )
            if rng.random() < (0.08 if week >= 20 else 0.04):
                day = rng.randrange(0, 6)
                interrupts.append(
                    InterruptEvent(
                        day=day,
                        kind="daycare_closure",
                        severity="medium",
                        title="daycare closure",
                        detail="Childcare disappears for a day. Reallocate coverage or use a short fallback.",
                        duration_days=1,
                        sleep_delta=0.10,
                        time_loss_min=75,
                    )
                )
            if rng.random() < (0.17 if week in (42, 43, 44, 47, 48) else 0.035):
                day = rng.randrange(0, 6)
                interrupts.append(
                    InterruptEvent(
                        day=day,
                        kind="gym_closed",
                        severity="low",
                        title="commercial gym is unexpectedly closed",
                        detail="The planned gym slot is unavailable today. A home session or fallback may preserve continuity.",
                        duration_days=1,
                        sleep_delta=0.0,
                        time_loss_min=15,
                    )
                )
            if rng.random() < 0.035:
                day = rng.randrange(0, 6)
                interrupts.append(
                    InterruptEvent(
                        day=day,
                        kind="partner_illness",
                        severity="high",
                        title="partner is ill",
                        detail="The partner needs care, so repeatedly claiming the usual training window raises household strain.",
                        duration_days=4,
                        sleep_delta=0.35,
                        time_loss_min=70,
                    )
                )

            built.append(
                WeekEvent(
                    week=week,
                    sleep_pressure=round(sleep_pressure, 6),
                    time_pressure_min=time_pressure,
                    illness_exposure=round(illness_exposure, 6),
                    gym_crowding=round(gym_crowding, 6),
                    open_days=default_open_days(),
                    known_events=tuple(known),
                    interrupts=tuple(sorted(interrupts, key=lambda event: event.day)),
                )
            )
        return tuple(built)
