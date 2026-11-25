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


def test_phase3_doubly_robust_aipw_3fold_dual_gate_and_live_badge(tmp_path: Path):
    from autonomous_engine.boardroom_decision_judge import BoardroomDecisionJudge
    from autonomous_engine.decision_prediction_engine import PredictiveDecisionEngine

    rng = np.random.default_rng(303)
    n = 900
    carrier = rng.choice(["BadVan", "FastCourier"], size=n, p=[0.45, 0.55])
    delay_h = np.where(carrier == "BadVan", rng.normal(32, 6, size=n), rng.normal(14, 5, size=n)).clip(2, 72)
    bill = rng.uniform(600, 3200, size=n)
    prob = np.clip(0.06 + np.where(carrier == "BadVan", 0.36, 0.0) + np.where(delay_h > 26, 0.16, 0.0), 0.02, 0.94)
    is_rto = (rng.random(n) < prob).astype(int)

    sig_dir = tmp_path / "phase3_sig"
    sig_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "carrier": carrier,
        "dispatch_delay_hours": np.round(delay_h, 1),
        "order_bill_inr": np.round(bill, 2),
        "is_rto": is_rto,
    }).to_parquet(sig_dir / "bi_ready_fact.parquet", index=False)

    eng = PredictiveDecisionEngine(str(sig_dir), region_profile="IN")

    # 1. Live Blind Backtest Verified Badge on strong signal vs Exploration Warning on pure noise
    bb = eng.model_metrics.get("blind_backtest_badge")
    assert bb is not None and bb["verified"] is True
    assert bb["unseen_directional_accuracy_pct"] >= 75.0
    assert bb["unseen_risk_lift_x"] > 2.0
    assert "Blind Backtest Verified" in bb["label_en"]

    noise_dir = tmp_path / "phase3_noise"
    noise_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "carrier": rng.choice(["A", "B", "C"], size=400),
        "score": rng.uniform(0, 100, size=400),
        "is_rto": rng.integers(0, 2, size=400),
    }).to_parquet(noise_dir / "bi_ready_fact.parquet", index=False)
    n_eng = PredictiveDecisionEngine(str(noise_dir))
    n_bb = n_eng.model_metrics.get("blind_backtest_badge")
    assert n_bb is not None and n_bb["verified"] is False
    assert "Exploration Only" in n_bb["label_en"]

    # 2. Doubly-Robust AIPW Propensity-Weighted Causal Audit computed & agrees on genuine causal lever
    sim = eng.simulate_decision(
        decision={"action_type": "replace_category", "column": "carrier", "from_value": "BadVan", "to_value": "FastCourier"}
    )
    assert sim["status"] == "simulated"
    dr = sim["prediction"]["doubly_robust_audit"]
    assert dr["computed"] is True
    assert dr["propensity_ess"] >= 25.0
    assert dr["dr_att_rate_diff_pct"] > 10.0
    assert dr["dr_agrees_with_gcomp"] is True

    # 3. 3-Fold Out-of-Sample Stability Map + Boardroom Dual-Verification Gate
    assert "carrier" in eng.fold_stability_map
    assert eng.fold_stability_map["carrier"]["fold_total"] == 3
    assert eng.fold_stability_map["carrier"]["is_fold_stable"] is True

    judge = BoardroomDecisionJudge(str(sig_dir), region_profile="IN", engine=eng)
    r_ok = judge.discuss("Should we fix carrier or dispatch_delay_hours first?")
    assert r_ok["comparison_scorecard"][0]["fold_stability"].endswith("/3")
    assert r_ok["context_used"]["blind_backtest_badge"]["verified"] is True

    # Simulate an unstable 0/3 fold factor (<25% importance) -> Dual-Gate MUST downgrade to PILOT_FIRST!
    eng.fold_stability_map["dispatch_delay_hours"] = {
        "fold_win_count": 0,
        "fold_total": 3,
        "fold_drops": [0.0, 0.0, 0.0],
        "is_fold_stable": False,
        "is_unanimous": False,
    }
    judge.imp_map["dispatch_delay_hours"] = 15.0
    r_folded = judge.discuss("Should we focus on dispatch_delay_hours?")
    assert r_folded["verdict"]["code"] == "PILOT_FIRST"
    assert any("3-Fold" in w for w in r_folded["evidence"]["wrong_or_risky_en"])

    # 4. Web UI & Boardroom Starters API expose Phase 3 badges cleanly
    client = TestClient(api_server.app)
    r_st = client.get("/api/v1/boardroom/starters/hotel_booking_cancellation")
    assert r_st.status_code == 200
    assert r_st.json()["blind_backtest_badge"]["verified"] is True
    html = client.get("/app").text
    assert "blind_backtest_badge" in html
    assert "doubly_robust_audit" in html

