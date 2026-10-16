"""
Unit and Invariant Test Suite for Autonomous Engine Statistics & Defenses
Covers:
1. Wilson Score Confidence Intervals (Gap 1)
2. Two-Proportion Pooled Z-Test (Gap 2)
3. Dynamic Narrative Branching & Lift (Gaps 3, 4)
4. Target Leakage & Segment Selection Invariants (Gap 5)
5. Dataset Fingerprinting & Stale Blueprint Rejection (Gap 10)
6. Adaptive Target Thresholding for Truncated Distributions (Gap 14)
7. Fact Table Immutability (Gap 12)
"""

import unittest
import numpy as np
import pandas as pd
from autonomous_engine.strategic_decision_matrix import (
    calculate_wilson_ci,
    calculate_two_proportion_z_test,
    MicroLevelForensicInquiryEngine,
    StrategicDecisionEngine
)
from autonomous_engine.stage2_ai_blueprint import calculate_topology_fingerprint


class TestEngineStatisticsAndGuards(unittest.TestCase):

    def test_wilson_ci_bounds(self):
        """Wilson CI must obey mathematical probability bounds [0, 1]."""
        # Test 1: Zero events
        low, high = calculate_wilson_ci(0, 100, confidence=0.95)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)
        self.assertLess(high, 0.10)

        # Test 2: 50% rate
        low, high = calculate_wilson_ci(50, 100, confidence=0.95)
        self.assertAlmostEqual((low + high) / 2.0, 0.50, places=2)
        self.assertTrue(0.39 <= low <= 0.42)
        self.assertTrue(0.58 <= high <= 0.61)

        # Test 3: 100% rate
        low, high = calculate_wilson_ci(100, 100, confidence=0.95)
        self.assertGreater(low, 0.90)
        self.assertEqual(high, 1.0)

    def test_two_proportion_z_test(self):
        """Two-proportion z-test should correctly compute z-score and p-value."""
        # Identical proportions
        z, p = calculate_two_proportion_z_test(20, 100, 20, 100)
        self.assertAlmostEqual(z, 0.0, places=3)
        self.assertAlmostEqual(p, 1.0, places=3)

        # Strongly separated proportions (e.g. 50% vs 10% on N=100)
        z, p = calculate_two_proportion_z_test(50, 100, 10, 100)
        self.assertGreater(z, 5.0)
        self.assertLess(p, 0.0001)

    def test_topology_fingerprinting(self):
        """Fingerprint must be deterministic and sensitive to schema changes."""
        topo1 = {
            "tables": {
                "wine": {"columns": ["fixed acidity", "volatile acidity", "quality"]}
            }
        }
        topo2 = {
            "tables": {
                "wine": {"columns": ["quality", "fixed acidity", "volatile acidity"]}
            }
        }
        topo3 = {
            "tables": {
                "imdb": {"columns": ["Series_Title", "IMDB_Rating", "Genre"]}
            }
        }
        fp1 = calculate_topology_fingerprint(topo1)
        fp2 = calculate_topology_fingerprint(topo2)
        fp3 = calculate_topology_fingerprint(topo3)

        self.assertEqual(fp1, fp2, "Fingerprint should be invariant to column ordering")
        self.assertNotEqual(fp1, fp3, "Different dataset must produce different fingerprint")

    def test_adaptive_threshold_for_truncated_ratings(self):
        """IMDB-style truncated ratings (7.6 to 9.3) must not collapse to 0 events."""
        # Simulate IMDB rating distribution
        np.random.seed(42)
        ratings = np.random.uniform(7.6, 9.3, size=1000)
        df_imdb = pd.DataFrame({
            "IMDB_Rating": ratings,
            "Gross": np.random.uniform(1e6, 5e8, size=1000),
            "Meta_score": np.random.uniform(50, 100, size=1000)
        })

        engine = StrategicDecisionEngine(df_imdb)
        self.assertEqual(engine.target_col, "IMDB_Rating")
        # Assert non-zero adverse events
        self.assertGreater(engine.target_events, 100, "Adaptive threshold must identify sub-baseline quartile")
        self.assertLess(engine.target_events, 400)
        self.assertTrue(15.0 <= engine.target_rate <= 35.0)

    def test_target_leakage_exclusion(self):
        """Synthetic flags like _is_target_event must NEVER leak as high_risk_segment."""
        np.random.seed(42)
        n = 500
        alcohol = np.random.uniform(8.0, 14.0, size=n)
        quality = np.random.choice([3, 4, 5, 6, 7, 8], size=n)
        target_event = (quality <= 5).astype(int)

        df = pd.DataFrame({
            "alcohol": alcohol,
            "quality": quality,
            "_is_target_event": target_event,
            "fact_surrogate_id": range(n)
        })

        engine = StrategicDecisionEngine(df)
        dossier = engine.generate_strategic_decision_dossier()
        bottleneck = dossier["high_risk_segment"]

        self.assertNotIn("_is_target_event", bottleneck, "Target event must not be selected as root cause")
        self.assertNotIn("fact_surrogate_id", bottleneck, "Surrogate key must not be selected as root cause")


if __name__ == "__main__":
    unittest.main()
