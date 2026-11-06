"""
================================================================================
UNIT TESTS: FORENSIC STATISTICAL ENGINES & PROBABILITY INVARIANTS
================================================================================
"""

import pytest
import numpy as np
import pandas as pd
from autonomous_engine.strategic_decision_matrix import (
    calculate_wilson_ci,
    calculate_two_proportion_z_test,
    calculate_excess_risk_metrics
)


def test_wilson_ci_bounds():
    """Wilson Score Confidence Intervals must strictly respect probability physics [0, 1]."""
    # Case 1: 0 observed events in 100 trials
    low_0, high_0 = calculate_wilson_ci(0, 100, confidence=0.95)
    assert low_0 == 0.0
    assert 0.0 < high_0 < 0.05

    # Case 2: 50 observed events in 100 trials (balanced)
    low_50, high_50 = calculate_wilson_ci(50, 100, confidence=0.95)
    assert 0.39 <= low_50 <= 0.42
    assert 0.58 <= high_50 <= 0.61
    assert round((low_50 + high_50) / 2.0, 2) == 0.50

    # Case 3: 100 observed events in 100 trials
    low_100, high_100 = calculate_wilson_ci(100, 100, confidence=0.95)
    assert low_100 > 0.95
    assert high_100 == 1.0


def test_two_proportion_z_test():
    """Two-proportion pooled z-test must correctly assess statistical significance."""
    # Null hypothesis: Identical rates (p1 == p0)
    z_null, p_null = calculate_two_proportion_z_test(25, 100, 25, 100)
    assert round(z_null, 3) == 0.0
    assert round(p_null, 3) == 1.0

    # Significant separation: 50% vs 10%
    z_sig, p_sig = calculate_two_proportion_z_test(50, 100, 10, 100)
    assert z_sig > 5.0
    assert p_sig < 0.0001


def test_excess_risk_metrics():
    """Epidemiological attributable risk calculation must return non-negative excess rates."""
    # Cohort 1: 40/100 (40%), Cohort 0: 20/200 (10%)
    res = calculate_excess_risk_metrics(40, 100, 20, 200, confidence=0.95)
    assert res["p1"] == 0.40
    assert res["p0"] == 0.10
    assert round(res["excess_rate"], 2) == 0.30
    assert round(res["excess_events"], 1) == 30.0
    assert res["z_stat"] > 5.0
    assert res["p_val"] < 0.0001
    assert res["excess_rate_low"] > 0.15
