"""Pre-rolled random streams for counterfactual-safe deterministic episodes."""

from dataclasses import dataclass
import random
from typing import Iterable


def _rng(seed: int, salt: int) -> random.Random:
    # Avoid Python's process-randomized hash() and keep the stream derivation
    # stable across Python versions and alternate action sequences.
    mixed = (seed * 1_000_003 + salt * 97_409 + 0x9E3779B9) & 0xFFFFFFFF
    return random.Random(mixed)


@dataclass(frozen=True)
class HiddenVariation:
    recovery_capacity: float
    volume_tolerance: float
    injury_joint: str
    motivation_baseline: float
    technique_start: float


@dataclass(frozen=True)
class NoiseBook:
    sleep_noise: tuple[float, ...]
    adherence_noise: tuple[float, ...]
    estimate_noise: tuple[float, ...]
    pain_noise: tuple[float, ...]
    illness_noise: tuple[float, ...]


def make_hidden_variation(seed: int) -> HiddenVariation:
    rng = _rng(seed, 11)
    return HiddenVariation(
        recovery_capacity=round(rng.uniform(0.88, 1.12), 6),
        volume_tolerance=round(rng.uniform(0.84, 1.16), 6),
        injury_joint=rng.choice(("shoulder", "elbow")),
        motivation_baseline=round(rng.uniform(0.58, 0.76), 6),
        technique_start=round(rng.uniform(0.46, 0.56), 6),
    )


def make_noise_book(seed: int, days: int) -> NoiseBook:
    sleep_rng = _rng(seed, 21)
    adherence_rng = _rng(seed, 22)
    estimate_rng = _rng(seed, 23)
    pain_rng = _rng(seed, 24)
    illness_rng = _rng(seed, 25)
    return NoiseBook(
        sleep_noise=tuple(round(sleep_rng.uniform(-0.28, 0.28), 6) for _ in range(days)),
        adherence_noise=tuple(round(adherence_rng.uniform(0.0, 1.0), 6) for _ in range(days)),
        estimate_noise=tuple(round(estimate_rng.uniform(-0.045, 0.045), 6) for _ in range(days + 1)),
        pain_noise=tuple(round(pain_rng.uniform(-0.08, 0.08), 6) for _ in range(days)),
        illness_noise=tuple(round(illness_rng.uniform(0.0, 1.0), 6) for _ in range(days)),
    )


def choose_unique(rng: random.Random, values: Iterable[int], count: int) -> list[int]:
    choices = list(values)
    rng.shuffle(choices)
    return sorted(choices[:count])
