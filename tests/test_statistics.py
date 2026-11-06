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
    assert res["p_value"] < 0.0001
    assert res["excess_rate_low"] > 0.15


def test_camelcase_hr_and_industrial_domain_classification():
    """CamelCase 'WorkLifeBalance' must classify as HR Workforce (never FinTech 'balance' substring)."""
    from autonomous_engine.strategic_decision_matrix import StrategicDecisionEngine

    df_hr = pd.DataFrame({
        "EmployeeNumber": range(1, 61),
        "JobRole": ["Sales Representative"] * 20 + ["Manager"] * 40,
        "WorkLifeBalance": [1, 2, 3] * 20,
        "DistanceFromHome": list(range(1, 31)) * 2,
        "TotalWorkingYears": [2] * 20 + [12] * 40,
        "MonthlyIncome": [2500.0] * 20 + [9000.0] * 40,
        "Attrition": ["Yes"] * 12 + ["No"] * 8 + ["Yes"] * 4 + ["No"] * 36
    })
    eng_hr = StrategicDecisionEngine(df_hr)
    dossier = eng_hr.generate_strategic_decision_dossier()
    assert eng_hr.domain_profile["domain_key"] == "hr_workforce"
    assert eng_hr.domain_profile["domain_key"] != "fintech_banking"

    # Verify Relative Risk Multiplier uses rest_rate denominator (60.0% / 10.0% = 6.0x)
    assert dossier["high_risk_rate"] == 60.0
    assert dossier["rest_rate"] == 10.0
    assert dossier["relative_risk_multiplier"] == 6.0

    # Verify Triage policies never flag 0% or 100% of population
    triage = eng_hr.micro_engine.simulate_operational_triage()
    for pol in triage:
        assert 0 < pol["scrap_count"] < len(df_hr)
        assert "Retention Review if" in pol["policy_name"]


def test_empty_2x2_quadrant_never_claims_false_buffering():
    """When Q3 (High pos & High neg) has 0 observations, MQ3 and 2x2 table must report Empty Stratum."""
    from autonomous_engine.strategic_decision_matrix import StrategicDecisionEngine

    # Construct inverse relationship where Torque > median and RPM > median never co-occur
    n = 100
    torque = np.concatenate([np.linspace(50, 75, 50), np.linspace(15, 35, 50)])
    rpm = np.concatenate([np.linspace(1200, 1400, 50), np.linspace(1600, 2200, 50)])
    failure = np.array([1] * 15 + [0] * 35 + [1] * 2 + [0] * 48)
    df_ind = pd.DataFrame({
        "UDI": range(1, n + 1),
        "Type": ["L"] * 60 + ["M"] * 40,
        "Torque [Nm]": torque,
        "Rotational speed [rpm]": rpm,
        "Machine failure": failure
    })
    eng_ind = StrategicDecisionEngine(df_ind)
    assert eng_ind.domain_profile["domain_key"] == "industrial_predictive_maintenance"
    md = eng_ind.micro_engine.render_micro_markdown()
    assert "N/A (Empty Stratum)" in md
    assert "structurally empty stratum" in md
    assert "achieve a 0.0% failure rate" not in md


def test_bivariate_interactions_robust_binary_split():
    """Discrete binary feature (median == max) must split cleanly using >= operator into populated quadrants."""
    from autonomous_engine.strategic_decision_matrix import StrategicDecisionEngine

    n = 200
    np.random.seed(42)
    age = np.random.uniform(20, 70, n)
    # Active member is binary {0, 1} with more 1s than 0s so median is 1.0
    active = np.random.choice([0, 1], p=[0.4, 0.6], size=n)
    # Target churn is higher when age is high and active is 0
    churn = ((age > 45) & (active == 0)).astype(int)
    # Add random baseline noise
    churn[np.random.choice(n, 15, replace=False)] = 1

    df_test = pd.DataFrame({
        "CustomerId": range(1, n + 1),
        "Age": age,
        "IsActiveMember": active,
        "Balance": np.linspace(1000, 50000, n),
        "Churn": churn
    })

    eng = StrategicDecisionEngine(df_test)
    interactions = eng.micro_engine.analyze_bivariate_interactions()
    assert interactions is not None
    quads = interactions["quadrants"]
    # All 4 quadrants must have positive counts (no artificial zero dropouts)
    for qk, qv in quads.items():
        assert qv["count"] > 0, f"Quadrant {qk} unexpectedly had 0 counts!"
    assert sum(qv["count"] for qv in quads.values()) == n
    assert sum(qv["events"] for qv in quads.values()) == int(churn.sum())


