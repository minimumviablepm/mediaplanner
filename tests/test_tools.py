import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mediaplanner.tools import (
    cpm_lookup,
    deduplication_model,
    mmm_priors,
    reach_frequency_model,
    universe_lookup,
    universe_overlap,
)


class TestReachFrequency(unittest.TestCase):
    BASE = dict(
        channel="linear", demo="A25-54", geography="national",
        flight_weeks=8, universe_size=129_000, cpm_override=30.0,
    )

    def test_requires_cpm(self):
        with self.assertRaises(ValueError):
            reach_frequency_model(**{**self.BASE, "cpm_override": None}, budget=1e6)

    def test_reach_monotonic_and_bounded(self):
        reaches = [
            reach_frequency_model(**self.BASE, budget=b)["reach_pct"]
            for b in (1e6, 5e6, 20e6, 200e6)
        ]
        self.assertEqual(reaches, sorted(reaches))
        # Bounded by addressable fraction (80% for linear).
        self.assertLess(reaches[-1], 80.0)

    def test_impressions_math(self):
        r = reach_frequency_model(**self.BASE, budget=3_000_000)
        self.assertAlmostEqual(r["gross_impressions"], 3_000_000 / 30.0 * 1000)

    def test_ci_brackets_estimate(self):
        r = reach_frequency_model(**self.BASE, budget=5_000_000)
        ci = r["confidence_interval_95"]
        self.assertLessEqual(ci["reach_low"], r["reach_pct"])
        self.assertGreaterEqual(ci["reach_high"], r["reach_pct"])

    def test_marginal_curve_decreasing(self):
        r = reach_frequency_model(**self.BASE, budget=20_000_000)
        increments = [p["incremental_reach"] for p in r["marginal_reach_curve"]]
        self.assertEqual(increments, sorted(increments, reverse=True))


class TestDeduplication(unittest.TestCase):
    def test_basic_properties(self):
        r = deduplication_model("linear", "ctv", 40.0, 25.0, 60.0)
        self.assertAlmostEqual(r["overlap_pct"], 40 * 25 * 0.6 / 100, places=2)
        self.assertAlmostEqual(
            r["unduplicated_reach_pct"], 40 + 25 - r["overlap_pct"], places=2
        )
        self.assertAlmostEqual(
            r["incremental_reach_from_b"], r["unduplicated_reach_pct"] - 40, places=2
        )

    def test_capped_at_100(self):
        r = deduplication_model("a", "b", 90.0, 90.0, 0.0)
        self.assertEqual(r["unduplicated_reach_pct"], 100.0)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            deduplication_model("a", "b", 120.0, 10.0, 50.0)


class TestMmmPriors(unittest.TestCase):
    def test_known_category(self):
        r = mmm_priors("CPG - household cleaning", "linear", "roas")
        self.assertEqual(r["matched_category"], "cpg")
        self.assertAlmostEqual(r["elasticity_estimate"], 0.10 * 0.8, places=4)
        self.assertIn(r["prior_confidence"], ("high", "medium", "low"))

    def test_unknown_category_is_low_confidence(self):
        r = mmm_priors("artisanal yak wool", "youtube", "brand lift")
        self.assertEqual(r["prior_confidence"], "low")

    def test_bad_channel(self):
        with self.assertRaises(ValueError):
            mmm_priors("retail", "radio", "roas")


class TestCpmLookup(unittest.TestCase):
    def test_percentile_ordering_and_metadata(self):
        r = cpm_lookup("ctv", "A25-54", "national", "programmatic_guaranteed", "Q4 2026")
        self.assertLess(r["cpm_p25"], r["cpm_median"])
        self.assertLess(r["cpm_median"], r["cpm_p75"])
        self.assertTrue(r["data_vintage"])
        self.assertIn(r["confidence"], ("high", "medium", "low"))

    def test_q4_premium(self):
        q2 = cpm_lookup("linear", "A25-54", "national", "upfront", "Q2 2026")
        q4 = cpm_lookup("linear", "A25-54", "national", "upfront", "Q4 2026")
        self.assertGreater(q4["cpm_median"], q2["cpm_median"])

    def test_dma_low_confidence(self):
        r = cpm_lookup("linear", "A25-54", "Chicago DMA", "scatter", "Q1 2026")
        self.assertEqual(r["confidence"], "low")

    def test_invalid_buying_type(self):
        with self.assertRaises(ValueError):
            cpm_lookup("linear", "A25-54", "national", "direct", "Q1 2026")


class TestUniverse(unittest.TestCase):
    def test_national_persons(self):
        r = universe_lookup("A25-54", "national", "persons")
        # ~335M total * ~38.7% 25-54 ≈ 129-130M persons
        self.assertGreater(r["universe_000s"], 100_000)
        self.assertLess(r["universe_000s"], 160_000)
        self.assertIn("Census", r["source"])

    def test_state(self):
        r = universe_lookup("A18-49", "Texas", "persons")
        self.assertGreater(r["universe_000s"], 5_000)
        self.assertLess(r["universe_000s"], 30_503)

    def test_households_not_demo_filtered(self):
        nat = universe_lookup("A25-54", "national", "households")
        self.assertGreater(nat["universe_000s"], 100_000)

    def test_unresolvable_geography_raises(self):
        with self.assertRaises(ValueError):
            universe_lookup("A25-54", "Gotham City", "persons")


class TestOverlap(unittest.TestCase):
    def test_pairs_and_symmetry(self):
        a = universe_overlap("linear", "ctv")
        b = universe_overlap("ctv", "linear")
        self.assertEqual(a["universe_overlap_pct"], b["universe_overlap_pct"])
        self.assertEqual(a["source_class"], "modeled (open-source derived)")

    def test_household_uplift(self):
        p = universe_overlap("linear", "youtube", "persons")
        h = universe_overlap("linear", "youtube", "households")
        self.assertGreater(h["universe_overlap_pct"], p["universe_overlap_pct"])

    def test_unknown_pair(self):
        with self.assertRaises(ValueError):
            universe_overlap("linear", "radio")


if __name__ == "__main__":
    unittest.main()
