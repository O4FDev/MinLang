#!/usr/bin/env python3
"""Paired timing summaries retain observations and reject invalid measurements."""

import math
from pathlib import Path
import random
import statistics
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments/memory"))
from measurement_stats import paired_cpu_ratio_summary


class MeasurementStats(unittest.TestCase):
    def test_adjacent_pairs_differ_from_separate_medians(self):
        numerator = [10, 20, 30]
        denominator = [1, 100, 10]
        before = (list(numerator), list(denominator))
        result = paired_cpu_ratio_summary(
            numerator, denominator, seed=7, resamples=1000
        )
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["ratios"], [10.0, 0.2, 3.0])
        self.assertEqual(result["median"], 3.0)
        self.assertEqual(
            statistics.median(numerator) / statistics.median(denominator), 2.0
        )
        self.assertEqual(result["range"], {"minimum": 0.2, "maximum": 10.0})
        self.assertEqual((numerator, denominator), before)

    def test_identical_pairs_have_exact_unit_interval(self):
        result = paired_cpu_ratio_summary([1, 10, 1000], [1, 10, 1000])
        self.assertEqual(result["median"], 1.0)
        self.assertEqual(result["ratios"], [1.0] * 3)
        self.assertEqual(result["range"], {"minimum": 1.0, "maximum": 1.0})
        self.assertEqual(result["confidence_interval"]["lower"], 1.0)
        self.assertEqual(result["confidence_interval"]["upper"], 1.0)
        self.assertEqual(result["confidence_interval"]["level"], 0.95)

    def test_known_scale_is_invariant_to_duration_units(self):
        for units in (1, 1000, 1000000):
            result = paired_cpu_ratio_summary(
                [5 * units, 10 * units, 50 * units],
                [4 * units, 8 * units, 40 * units],
                seed=31,
                resamples=200,
            )
            self.assertEqual(result["ratios"], [1.25] * 3)
            self.assertEqual(result["median"], 1.25)
            self.assertEqual(result["confidence_interval"]["lower"], 1.25)
            self.assertEqual(result["confidence_interval"]["upper"], 1.25)

    def test_bootstrap_resamples_pairs_and_reports_its_method(self):
        # For two ratios {1, 4}, the three possible bootstrap medians are
        # {1, 2.5, 4}, with probabilities {1/4, 1/2, 1/4}.
        result = paired_cpu_ratio_summary([1, 4], [1, 1], seed=7, resamples=1000)
        self.assertEqual(result["median"], 2.5)
        interval = result["confidence_interval"]
        self.assertEqual((interval["lower"], interval["upper"]), (1.0, 4.0))
        self.assertEqual(interval["seed"], 7)
        self.assertEqual(interval["resamples"], 1000)
        self.assertEqual(
            interval["method"], "percentile bootstrap of paired-ratio medians"
        )
        self.assertEqual(interval["quantile_method"], "linear interpolation")

    def test_local_seed_is_repeatable_and_does_not_change_global_rng(self):
        state = random.getstate()
        first = paired_cpu_ratio_summary(
            [3, 4, 9, 7], [1, 3, 2, 5], seed=19, resamples=211
        )
        second = paired_cpu_ratio_summary(
            [3, 4, 9, 7], [1, 3, 2, 5], seed=19, resamples=211
        )
        self.assertEqual(first, second)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(first["sample_count"], 4)
        self.assertEqual(len(first["ratios"]), 4)

    def test_one_pair_keeps_exact_observation(self):
        result = paired_cpu_ratio_summary([2], [4], seed=1, resamples=100)
        self.assertEqual(result["ratios"], [0.5])
        self.assertEqual(result["median"], 0.5)
        self.assertEqual(result["confidence_interval"]["lower"], 0.5)
        self.assertEqual(result["confidence_interval"]["upper"], 0.5)

    def test_extreme_observations_are_retained(self):
        result = paired_cpu_ratio_summary(
            [1, 1, 1, 1000000], [1, 1, 1, 1], seed=7, resamples=1000
        )
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["ratios"], [1.0, 1.0, 1.0, 1000000.0])
        self.assertEqual(result["range"]["maximum"], 1000000.0)

    def test_large_finite_ratios_do_not_overflow_their_median(self):
        result = paired_cpu_ratio_summary([1e308, 1e308], [1, 1], seed=7, resamples=100)
        self.assertEqual(result["median"], 1e308)
        self.assertEqual(result["confidence_interval"]["lower"], 1e308)
        self.assertEqual(result["confidence_interval"]["upper"], 1e308)

    def test_invalid_values_are_rejected_in_either_language(self):
        for bad in (0, -1, math.nan, math.inf, -math.inf, True, "1", None):
            for numerator, denominator in (
                ([1, bad, 2], [1, 1, 1]),
                ([1, 1, 1], [1, bad, 2]),
            ):
                with self.subTest(numerator=numerator, denominator=denominator):
                    with self.assertRaises(ValueError):
                        paired_cpu_ratio_summary(numerator, denominator)

    def test_empty_or_mismatched_pairs_are_rejected(self):
        for numerator, denominator in (([], []), ([1], []), ([], [1]), ([1, 2], [1])):
            with self.subTest(numerator=numerator, denominator=denominator):
                with self.assertRaises(ValueError):
                    paired_cpu_ratio_summary(numerator, denominator)

    def test_overflowed_or_underflowed_ratios_are_rejected(self):
        for numerator, denominator in (([1e308], [1e-308]), ([1e-308], [1e308])):
            with self.subTest(numerator=numerator, denominator=denominator):
                with self.assertRaises(ValueError):
                    paired_cpu_ratio_summary(numerator, denominator)

    def test_invalid_bootstrap_parameters_are_rejected(self):
        for parameters in (
            {"resamples": 0},
            {"resamples": -1},
            {"resamples": True},
            {"resamples": 1.5},
            {"seed": True},
            {"seed": 1.5},
            {"seed": "7"},
        ):
            with self.subTest(parameters=parameters):
                with self.assertRaises(ValueError):
                    paired_cpu_ratio_summary([1], [1], **parameters)


if __name__ == "__main__":
    unittest.main()
