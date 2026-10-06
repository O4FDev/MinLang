"""Describe adjacent timing pairs without discarding any observation.

The percentile interval resamples complete pairs and estimates their median
ratio. It assumes independent observed pairs; host trends and unobserved
workloads are outside that interval's model.
"""

from __future__ import annotations

import math
from numbers import Real
import random
from collections.abc import Iterable

DEFAULT_BOOTSTRAP_SEED = 20261002
DEFAULT_BOOTSTRAP_RESAMPLES = 10000


def _positive_durations(values: Iterable[Real], label: str) -> list[float]:
    durations = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{label}[{index}] must be a positive finite number")
        try:
            duration = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError(
                f"{label}[{index}] must be representable as a finite number"
            ) from error
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"{label}[{index}] must be a positive finite number")
        durations.append(duration)
    return durations


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    lower, upper = ordered[middle - 1 : middle + 1]
    # All ratios are positive; subtracting avoids overflowing their sum.
    return lower + (upper - lower) / 2


def _percentile(ordered: list[float], probability: float) -> float:
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def paired_cpu_ratio_summary(
    numerator_cpu_ns: Iterable[Real],
    denominator_cpu_ns: Iterable[Real],
    *,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
) -> dict:
    """Return numerator/denominator ratios for measurements paired by position.

    The deterministic 95% percentile bootstrap draws ``sample_count`` pairs
    with replacement for each resample. Endpoint percentiles use linear
    interpolation at ``p * (resamples - 1)``. The input order, every pair ratio,
    and its full range are preserved, with no trimming or outlier rejection.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("bootstrap seed must be an integer")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples <= 0:
        raise ValueError("bootstrap resamples must be a positive integer")
    numerator = _positive_durations(numerator_cpu_ns, "numerator_cpu_ns")
    denominator = _positive_durations(denominator_cpu_ns, "denominator_cpu_ns")
    if len(numerator) != len(denominator) or not numerator:
        raise ValueError("timing measurements need the same nonzero number of pairs")
    ratios = [a / b for a, b in zip(numerator, denominator)]
    if any(not math.isfinite(ratio) or ratio <= 0 for ratio in ratios):
        raise ValueError(
            "each pair ratio must be representable as a positive finite number"
        )

    generator = random.Random(seed)
    count = len(ratios)
    bootstrap = sorted(
        _median(generator.choices(ratios, k=count)) for _ in range(resamples)
    )
    return {
        "sample_count": count,
        "median": _median(ratios),
        "ratios": ratios,
        "range": {"minimum": min(ratios), "maximum": max(ratios)},
        "confidence_interval": {
            "level": 0.95,
            "lower": _percentile(bootstrap, 0.025),
            "upper": _percentile(bootstrap, 0.975),
            "method": "percentile bootstrap of paired-ratio medians",
            "quantile_method": "linear interpolation",
            "seed": seed,
            "resamples": resamples,
            "assumption": "Observed pairs are resampled as independent observations.",
        },
    }
