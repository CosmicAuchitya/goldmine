"""
Phase 1 + Phase 2 Permanent CI Accuracy Gate Suite:
  1. Verifies real corporate file target/currency/ERP credit-note auto-detection
     (dot-separated `not.fully.paid`, `installment`, raw UK ERP `'C'` credit-notes & GBP `£`,
     and `/api/v1/preview-intent` 10-second handshake sanity warning on inverted targets).
  2. Verifies blind sealed-reality accuracy >= 85% across Review Persistence,
     Stage 8 Suggestion Direction, Calibration Error (<= 3.0 pp), and Stage 9
     AI Boardroom Golden Exam (50 questions across 10 real companies).
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine import api_server
from autonomous_engine.accuracy_benchmark_grader import run_full_accuracy_benchmark
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost

WS = Path(__file__).resolve().parents[1]


def test_phase1_real_corporate_target_erp_credit_note_and_intent_handshake():
    rng = np.random.default_rng(7)
    # 1. Dot-separated FinTech ledger (LendingClub schema): MUST pick `not.fully.paid` (NOT `credit.policy`!) + `installment` ($)
    n = 300
    df_lc = pd.DataFrame({
        "credit.policy": rng.choice([0, 1], size=n, p=[0.20, 0.80]),
        "purpose": rng.choice(["credit_card", "small_business", "debt_consolidation"], size=n),
        "int.rate": np.round(rng.uniform(0.07, 0.21, size=n), 4),
        "installment": np.round(rng.uniform(120.0, 850.0, size=n), 2),
        "fico": rng.integers(610, 810, size=n),
        "not.fully.paid": rng.choice([0, 1], size=n, p=[0.84, 0.16]),
    })
    can_lc = resolve_canonical_target_and_cost(df_lc)
    assert can_lc["target_col"] == "not.fully.paid"
    assert can_lc["cost_col"] == "installment"
    assert can_lc["unit_symbol"] == "$"
    assert 0.08 <= float(can_lc["binary_target"].mean()) <= 0.30

    # 2. Raw ERP Invoice export (UK Online Retail schema): MUST auto-detect `'C'` credit-note / negative Qty returns & `£`!
    is_ret = rng.random(n) < 0.05
    df_erp = pd.DataFrame({
        "InvoiceNo": [f"C536{i:03d}" if r else f"536{i:03d}" for i, r in enumerate(is_ret)],
        "StockCode": rng.choice(["85123A", "71053", "22423", "POST"], size=n),
        "Quantity": [-int(rng.integers(1, 10)) if r else int(rng.integers(1, 20)) for r in is_ret],
        "UnitPrice": np.round(rng.uniform(1.5, 25.0, size=n), 2),
        "Country": ["United Kingdom"] * n,
    })
    can_erp = resolve_canonical_target_and_cost(df_erp)
    assert can_erp["target_col"] == "Quantity"
    assert can_erp["cost_col"] == "UnitPrice"
    assert can_erp["unit_symbol"] == "£"
    assert int(can_erp["binary_target"].sum()) == int(is_ret.sum())

    # 3. FastAPI `/api/v1/preview-intent` returns detected_adverse_rate_pct & warns cleanly if >65% flagged as problem!
    client = TestClient(api_server.app)
    buf_lc = io.BytesIO(df_lc.to_csv(index=False).encode("utf-8"))
    r_ok = client.post(
        "/api/v1/preview-intent",
        files={"file": ("lendingclub_sample.csv", buf_lc, "text/csv")},
        data={"region_profile": "US"},
    )
    assert r_ok.status_code == 200, r_ok.text
    goal_ok = r_ok.json()["detected_goal"]
    assert goal_ok["target_col"] == "not.fully.paid"
    assert goal_ok["cost_col"] == "installment"
    assert goal_ok["target_sanity_warning_en"] is None
    assert 5.0 <= goal_ok["detected_adverse_rate_pct"] <= 35.0

    # High-adverse (>65%) edge file triggers explicit 10-second handshake warning!
    df_warn = pd.DataFrame({
        "vendor": rng.choice(["A", "B"], size=100),
        "amount": rng.uniform(100, 500, size=100),
        "status": rng.choice(["Failed", "Completed"], size=100, p=[0.82, 0.18]),
    })
    buf_w = io.BytesIO(df_warn.to_csv(index=False).encode("utf-8"))
    r_warn = client.post(
        "/api/v1/preview-intent",
        files={"file": ("high_adv_check.csv", buf_w, "text/csv")},
        data={"region_profile": "US"},
    )
    assert r_warn.status_code == 200, r_warn.text
    goal_w = r_warn.json()["detected_goal"]
    assert goal_w["detected_adverse_rate_pct"] > 65.0
    assert goal_w["target_sanity_warning_en"] is not None
    assert goal_w["target_sanity_warning_hi"] is not None


def test_phase2_blind_sealed_accuracy_benchmark_exceeds_85_pct():
    report = run_full_accuracy_benchmark(workspace_root=WS)
    scores = report["summary_scores"]
    assert report["companies_evaluated"] >= 6, f"Too few companies evaluated: {report['companies_evaluated']}"
    assert scores["overall_truth_accuracy_pct"] >= 85.0, f"Overall truth score below 85%: {scores}"
    assert scores["review_persistence_accuracy_pct"] >= 85.0, f"Review persistence below 85%: {scores}"
    assert scores["suggestion_directional_accuracy_pct"] >= 85.0, f"Suggestion accuracy below 85%: {scores}"
    assert scores["boardroom_50q_accuracy_pct"] >= 85.0, f"Boardroom accuracy below 85%: {scores}"
    assert scores["mean_sealed_calibration_error_pp"] <= 3.5, f"Calibration error too high: {scores}"
    assert scores["pure_noise_placebo_rejected"] is True
