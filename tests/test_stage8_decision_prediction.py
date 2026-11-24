"""
Stage 8 Verification & Stress-Test Suite — Predictive Decision Intelligence ("Decision Lab"):
1. Anti-leakage purity guard & out-of-sample ML calibration on V2 Indian Retail Mall.
2. Good vs Backfire (Loss) vs Scoped Discount Cap vs Pause Trade-Off counterfactual math & Hinglish parsing.
3. Zero fake currency on non-monetary clinical/ops datasets + honest LOW-confidence guard on pure noise.
4. FastAPI /api/v1/predict/overview/{run_id} & /api/v1/predict/simulate/{run_id} E2E + Tenant Isolation + UI markers.
"""
import json
import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from autonomous_engine import api_server
from autonomous_engine.decision_prediction_engine import PredictiveDecisionEngine

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
V2_MALL_OUTPUT = WORKSPACE_ROOT / "enterprise_showcase_data" / "v2_indian_retail_mall" / "output"
DIABETES_OUTPUT = WORKSPACE_ROOT / "kaggle_benchmarks" / "diabetes_clinical_endocrinology" / "output"


def _build_synthetic_retail_dir(tmp_path: Path) -> Path:
    """Fallback realistic Indian retail Parquet dir if showcase folder is absent in CI."""
    out = tmp_path / "syn_retail_out"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    n = 1200
    vendors = rng.choice(["Surat Textile Mills", "Tirupur Knitwear Co", "Ludhiana Woolens"], size=n, p=[0.30, 0.40, 0.30])
    stores = rng.choice(["V2 Kanpur Kakadeo", "V2 Lucknow Gomti", "V2 Gorakhpur"], size=n)
    stock_age = rng.integers(10, 180, size=n)
    disc = np.where(stores == "V2 Kanpur Kakadeo", rng.uniform(12, 32, size=n), rng.uniform(0, 15, size=n))
    mrp = rng.uniform(400, 1800, size=n)
    net_sale = mrp * (1.0 - disc / 100.0)
    margin = net_sale * 0.28 - (disc * 2.5)
    prob = 0.08 + np.where(vendors == "Surat Textile Mills", 0.35, 0.0) + np.where(stock_age > 120, 0.25, 0.0)
    is_ret = (rng.random(n) < np.clip(prob, 0.02, 0.90)).astype(int)
    df = pd.DataFrame({
        "bill_id": [f"B{i:05d}" for i in range(n)],
        "store_name": stores,
        "vendor_name": vendors,
        "stock_age_days": stock_age,
        "discount_pct": np.round(disc, 1),
        "mrp_inr": np.round(mrp, 2),
        "net_sale_inr": np.round(net_sale, 2),
        "net_margin_inr": np.round(margin, 2),
        "bill_status": np.where(is_ret == 1, "Returned", "Completed"),
        "return_reason": np.where(is_ret == 1, "Fabric Defect", "None"),
    })
    df.to_parquet(out / "bi_ready_fact.parquet", index=False)
    (out / "executive_pulse.json").write_text(
        json.dumps({
            "target_col": "bill_status",
            "monetary_col": "net_sale_inr",
            "is_financial": True,
            "unit_symbol": "₹",
        }),
        encoding="utf-8",
    )
    (out / "semantic_metrics_manifest.json").write_text(
        json.dumps({"target_column": "bill_status", "monetary_column": "net_sale_inr"}),
        encoding="utf-8",
    )
    return out


def _get_v2_or_synthetic_dir(tmp_path: Path) -> Path:
    if (V2_MALL_OUTPUT / "bi_ready_fact.parquet").exists():
        return V2_MALL_OUTPUT
    return _build_synthetic_retail_dir(tmp_path)


# -----------------------------------------------------------------------------
# TEST 1: Anti-Leakage Purity Guard & Out-of-Sample Calibration on V2 Retail Mall
# -----------------------------------------------------------------------------
def test_stage8_v2_mall_leakage_guard_and_calibration(tmp_path: Path):
    out_dir = _get_v2_or_synthetic_dir(tmp_path)
    eng = PredictiveDecisionEngine(str(out_dir))
    overview = eng.get_model_overview_and_presets()

    assert overview["status"] == "ready"
    m = overview["model_metrics"]

    # 1. Post-event target leakage column 'return_reason' MUST be blocked automatically!
    assert "return_reason" in m["blocked_leakage_columns"], f"Leakage column not blocked: {m}"
    assert "return_reason" not in eng.categorical_features
    assert "return_reason" not in eng.numeric_features

    # 2. Raw business levers MUST stay available for simulation (not stripped as synthetic!)
    assert "discount_pct" in eng.numeric_features
    assert "stock_age_days" in eng.numeric_features
    assert "vendor_name" in eng.categorical_features

    # 3. Realistic, honest out-of-sample ROC-AUC & calibration (not fake 1.0!)
    assert 0.65 <= m["roc_auc"] < 0.99, f"Unexpected AUC: {m['roc_auc']}"
    assert m["calibration_gap_pct"] < 5.0
    assert m["brier_score"] < 0.25

    # 4. Top drivers recover the true business causes
    top_feats = [d["feature"] for d in overview["top_drivers"][:4]]
    assert "stock_age_days" in top_feats
    assert "vendor_name" in top_feats

    # 5. Business common sense on 1-click presets: never suggest swapping physical store locations
    for p in overview["presets"]:
        dec = p["decision"]
        if dec.get("action_type") == "replace_category":
            assert dec.get("column") not in ("store_name", "city", "region", "branch")


# -----------------------------------------------------------------------------
# TEST 2: Good vs Backfire vs Discount Cap vs Pause Trade-Off Counterfactual Math
# -----------------------------------------------------------------------------
def test_stage8_counterfactual_good_vs_backfire_vs_discount_vs_pause(tmp_path: Path):
    out_dir = _get_v2_or_synthetic_dir(tmp_path)
    eng = PredictiveDecisionEngine(str(out_dir))

    # A. Good Decision in Natural Hinglish: Surat Textile Mills -> Tirupur Knitwear Co
    good = eng.simulate_decision(
        decision_text="Agar hum Surat Textile Mills ko Tirupur Knitwear Co se badal dein?"
    )
    assert good["status"] == "simulated"
    gp = good["prediction"]
    assert gp["verdict_code"] == "STRONG_GO"
    assert gp["expected_net_impact"] > 0
    assert gp["before_risk_rate_pct"] > gp["after_risk_rate_pct"] + 15.0
    # Never claims fake 100% certainty — bounded by out-of-sample AUC honesty ceiling!
    assert 80.0 <= gp["chance_of_benefit_pct"] <= 95.0
    assert abs((gp["chance_of_benefit_pct"] + gp["chance_of_loss_pct"]) - 100.0) < 0.2
    assert len(good["where_it_helps"]) >= 1
    assert len(good["why_loss_could_happen"]["en"]) >= 1
    assert len(good["why_loss_could_happen"]["hi"]) >= 1

    # B. Bad / Backfire Decision: Swapping good vendor INTO bad vendor -> LIKELY_LOSS!
    bad = eng.simulate_decision(
        decision_text="Agar hum Tirupur Knitwear Co ko Surat Textile Mills se badal dein?"
    )
    assert bad["status"] == "simulated"
    bp = bad["prediction"]
    assert bp["verdict_code"] == "LIKELY_LOSS"
    assert bp["expected_net_impact"] < 0
    assert bp["after_risk_rate_pct"] > bp["before_risk_rate_pct"] + 10.0
    assert bp["chance_of_loss_pct"] >= 80.0
    # Negative empirical signal MUST be listed FIRST in downside explanation!
    assert bad["why_loss_could_happen"]["en"][0].startswith("Negative Empirical Signal")

    # C. Scoped Discount Cap in V2 Kanpur Kakadeo
    disc = eng.simulate_decision(
        decision_text="Cap discount_pct at 15 in V2 Kanpur Kakadeo"
    )
    assert disc["status"] == "simulated"
    assert disc["decision_applied"]["spec"]["scope_value"] == "V2 Kanpur Kakadeo"
    assert disc["prediction"]["breakdown_components"]["direct_margin_recovery"] > 0
    assert disc["prediction"]["expected_net_impact"] > 0
    assert any("Walk-Away" in r for r in disc["why_loss_could_happen"]["en"])

    # D. Pause / Stop Worst Vendor -> MUST deduct collateral healthy-order margin trade-off!
    pause = eng.simulate_decision(
        decision={
            "action_type": "pause_segment",
            "column": "vendor_name",
            "from_value": "Surat Textile Mills",
        }
    )
    assert pause["status"] == "simulated"
    assert pause["prediction"]["breakdown_components"]["collateral_tradeoff_cost"] > 0
    assert any("Collateral Volume Loss" in r for r in pause["why_loss_could_happen"]["en"])


# -----------------------------------------------------------------------------
# TEST 3: Non-Monetary Dataset (Zero Fake $) & Pure-Noise Honesty Guard
# -----------------------------------------------------------------------------
def test_stage8_non_monetary_and_pure_noise_honesty(tmp_path: Path):
    # Part A: Non-monetary clinical dataset — strictly ZERO fake currency symbols!
    if (DIABETES_OUTPUT / "bi_ready_fact.parquet").exists():
        clin_dir = DIABETES_OUTPUT
    else:
        clin_dir = tmp_path / "syn_clinical"
        clin_dir.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(7)
        n = 500
        glucose = rng.normal(125, 32, size=n).clip(60, 220)
        bmi = rng.normal(31, 6, size=n).clip(18, 52)
        outcome = (rng.random(n) < np.clip((glucose - 90) / 140.0, 0.05, 0.90)).astype(int)
        pd.DataFrame({
            "Glucose": np.round(glucose, 1),
            "BMI": np.round(bmi, 1),
            "Age": rng.integers(21, 70, size=n),
            "Outcome": outcome,
        }).to_parquet(clin_dir / "bi_ready_fact.parquet", index=False)

    clin_eng = PredictiveDecisionEngine(str(clin_dir))
    assert clin_eng.is_monetary is False
    ov = clin_eng.get_model_overview_and_presets()
    assert len(ov["presets"]) >= 1
    sim = clin_eng.simulate_decision(decision=ov["presets"][0]["decision"])
    assert sim["status"] == "simulated"
    assert sim["prediction"]["is_monetary"] is False
    for s in (sim["prediction"]["formatted_net_impact"], sim["prediction"]["formatted_ci_95"]):
        assert "$" not in s and "₹" not in s and "€" not in s
        assert "events" in s

    # Part B: Pure Random Noise Dataset -> Model MUST be honest (LOW confidence, never 95%!)
    noise_dir = tmp_path / "pure_noise"
    noise_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(999)
    n = 600
    pd.DataFrame({
        "region": rng.choice(["North", "South", "East", "West"], size=n),
        "plan": rng.choice(["Basic", "Standard", "Plus"], size=n),
        "score": rng.uniform(0, 100, size=n),
        "amount": rng.uniform(100, 500, size=n),
        "churn": rng.integers(0, 2, size=n),
    }).to_parquet(noise_dir / "bi_ready_fact.parquet", index=False)

    noise_eng = PredictiveDecisionEngine(str(noise_dir))
    nm = noise_eng.model_metrics
    assert nm["roc_auc"] < 0.62, f"Noise AUC unexpectedly high: {nm['roc_auc']}"
    assert nm["confidence_tier"] == "LOW"
    noise_sim = noise_eng.simulate_decision(
        decision={"action_type": "replace_category", "column": "plan", "from_value": "Basic", "to_value": "Plus"}
    )
    assert noise_sim["status"] == "simulated"
    # On pure noise, honesty ceiling prevents fake 90%+ certainty!
    assert noise_sim["prediction"]["chance_of_benefit_pct"] <= 75.0
    assert any("Predictability" in r or "ROC-AUC" in r for r in noise_sim["why_loss_could_happen"]["en"])


# -----------------------------------------------------------------------------
# TEST 4: FastAPI Endpoints, Multi-Tenant Isolation & Web UI Markers
# -----------------------------------------------------------------------------
def test_stage8_fastapi_endpoints_tenant_isolation_and_ui_markers(tmp_path: Path, monkeypatch):
    client = TestClient(api_server.app)

    # 1. Public certified benchmark overview + empty-body validation
    ov_res = client.get("/api/v1/predict/overview/hotel_booking_cancellation")
    assert ov_res.status_code == 200, ov_res.text
    ov_data = ov_res.json()
    assert ov_data["run_id"] == "hotel_booking_cancellation"
    assert ov_data["model_metrics"]["roc_auc"] > 0.65
    assert len(ov_data["presets"]) >= 1

    bad_req = client.post("/api/v1/predict/simulate/hotel_booking_cancellation", json={})
    assert bad_req.status_code == 400

    # 2. V2 Retail Mall showcase live API simulation (if present on disk)
    if (V2_MALL_OUTPUT / "bi_ready_fact.parquet").exists():
        sim_res = client.post(
            "/api/v1/predict/simulate/v2_indian_retail_mall",
            json={"decision_text": "Agar hum Surat Textile Mills ko Tirupur Knitwear Co se badal dein?"},
        )
        assert sim_res.status_code == 200, sim_res.text
        sdata = sim_res.json()
        assert sdata["prediction"]["verdict_code"] == "STRONG_GO"
        assert sdata["prediction"]["expected_net_impact"] > 0

    # 3. Strict Multi-Tenant Isolation on private run predictions
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    suffix = uuid.uuid4().hex[:8]
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": f"pred_a_{suffix}@example.com", "password": "Password123!", "workspace_name": f"WS A {suffix}"},
    )
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": f"pred_b_{suffix}@example.com", "password": "Password123!", "workspace_name": f"WS B {suffix}"},
    )
    assert reg_a.status_code in (200, 201), reg_a.text
    assert reg_b.status_code in (200, 201), reg_b.text
    tok_a = reg_a.json()["access_token"]
    tok_b = reg_b.json()["access_token"]
    tid_a = reg_a.json()["user"]["tenant_id"]

    priv_run_id = f"priv_pred_{suffix}"
    priv_out = WORKSPACE_ROOT / "runs" / "tenants" / tid_a / "runs" / priv_run_id / "output"
    try:
        src_dir = _build_synthetic_retail_dir(tmp_path)
        shutil.copytree(src_dir, priv_out)

        # Unauthenticated -> 401
        r_unauth = client.get(f"/api/v1/predict/overview/{priv_run_id}")
        assert r_unauth.status_code == 401

        # Tenant B -> 403 Forbidden (Cross-Tenant Isolation)
        r_b_ov = client.get(
            f"/api/v1/predict/overview/{priv_run_id}",
            headers={"Authorization": f"Bearer {tok_b}"},
        )
        assert r_b_ov.status_code == 403

        r_b_sim = client.post(
            f"/api/v1/predict/simulate/{priv_run_id}",
            headers={"Authorization": f"Bearer {tok_b}"},
            json={"decision_text": "Stop Surat Textile Mills"},
        )
        assert r_b_sim.status_code == 403

        # Tenant A -> 200 OK
        r_a_ov = client.get(
            f"/api/v1/predict/overview/{priv_run_id}",
            headers={"Authorization": f"Bearer {tok_a}"},
        )
        assert r_a_ov.status_code == 200, r_a_ov.text

        r_a_sim = client.post(
            f"/api/v1/predict/simulate/{priv_run_id}",
            headers={"Authorization": f"Bearer {tok_a}"},
            json={"decision_text": "Agar hum Surat Textile Mills ko Tirupur Knitwear Co se badal dein?"},
        )
        assert r_a_sim.status_code == 200, r_a_sim.text
        assert r_a_sim.json()["prediction"]["expected_net_impact"] > 0
    finally:
        # Clean up temporary private tenant run directory
        tenant_root = WORKSPACE_ROOT / "runs" / "tenants" / tid_a
        if tenant_root.exists():
            shutil.rmtree(tenant_root, ignore_errors=True)

    # 4. Web UI Verification: Stage 8 Decision Lab tab embedded & Zero external CDN scripts
    html_res = client.get("/app")
    assert html_res.status_code == 200
    html = html_res.text
    assert 'data-tab="predict"' in html
    assert 'id="tabPanel-predict"' in html
    assert 'id="predictGaugeCircle"' in html
    assert "/api/v1/predict/overview/" in html
    assert "/api/v1/predict/simulate/" in html
    assert 'id="predictConfidenceMeterBox"' in html
    assert 'id="predictRolloutCostInput"' in html
    assert 'id="predictCompareCard"' in html
    assert 'id="btnAddToCombo"' in html
    assert 'id="predictComboQueueBox"' in html
    assert 'id="btnCommitDecision"' in html
    assert 'id="btnDecisionWhatsAppMemo"' in html
    assert 'id="btnDecisionPrintMemo"' in html
    assert 'id="predictCommitmentsCard"' in html
    assert "/api/v1/predict/commitments" in html
    assert '<script src="http' not in html.lower()


# -----------------------------------------------------------------------------
# TEST 5: Anti-Forcing Red-Team Audit Guards (Noise CB, Simpson's Paradox,
#         Healthy Pause Loss, Unrecognized Prompt Honesty, V2 Number & delta_pct)
# -----------------------------------------------------------------------------
def test_stage8_anti_forcing_noise_simpsons_pause_and_parser_guards(tmp_path: Path):
    out_dir = tmp_path / "anti_force_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1234)
    n = 3000

    hubs = rng.choice(["Mumbai Hub", "Kolkata Hub", "Delhi Hub"], size=n, p=[0.45, 0.25, 0.30])
    # Confounder: Kolkata Hub mostly uses Bad Courier; Mumbai mostly uses Good Courier
    partners = np.array([
        rng.choice(["Bad Courier", "Good Courier"], p=[0.80, 0.20]) if h == "Kolkata Hub"
        else rng.choice(["Bad Courier", "Good Courier"], p=[0.12, 0.88])
        for h in hubs
    ])
    # Pure noise column inside a HIGH-AUC dataset!
    box_color = rng.choice(["Classic Blue", "Festive Gold", "Eco Kraft"], size=n)
    delay_hrs = np.where(partners == "Bad Courier", rng.uniform(12, 55, size=n), rng.uniform(4, 30, size=n))
    mrp = rng.uniform(1000, 5000, size=n)
    disc = rng.uniform(5, 30, size=n)
    net_sale = mrp * (1.0 - disc / 100.0)
    cogs = mrp * 0.65
    margin = net_sale - cogs

    # True causal failure: ONLY partner + delay_hrs drive risk (box_color & hub have ZERO effect!)
    logit = -2.6 + np.where(partners == "Bad Courier", 1.8, 0.0) + np.where(delay_hrs > 24.0, 1.4, 0.0)
    is_fail = (rng.random(n) < (1.0 / (1.0 + np.exp(-logit)))).astype(int)

    df = pd.DataFrame({
        "order_id": [f"ORD-{i}" for i in range(n)],
        "fulfillment_hub": hubs,
        "fulfillment_partner": partners,
        "packaging_box_theme": box_color,
        "dispatch_delay_hours": np.round(delay_hrs, 1),
        "mrp_inr": np.round(mrp, 2),
        "discount_pct": np.round(disc, 1),
        "net_sale_inr": np.round(net_sale, 2),
        "cost_price_inr": np.round(cogs, 2),
        "gross_margin_inr": np.round(margin, 2),
        "order_status": np.where(is_fail == 1, "RTO_Returned", "Delivered"),
        "rto_reason": np.where(is_fail == 1, "Damage", "None"),
        "refund_amount_inr": np.where(is_fail == 1, net_sale, 0.0),
    })
    df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

    eng = PredictiveDecisionEngine(str(out_dir), region_profile="IN")
    assert "rto_reason" in eng.model_metrics["blocked_leakage_columns"]
    assert "refund_amount_inr" in eng.model_metrics["blocked_leakage_columns"]
    assert eng.model_metrics["roc_auc"] >= 0.75

    # 1. Pure noise lever inside HIGH-AUC dataset MUST trigger Noise Circuit-Breaker -> NEUTRAL (~50%)!
    res_noise = eng.simulate_decision(decision_text="Replace Classic Blue with Festive Gold")
    assert res_noise["status"] == "simulated"
    assert res_noise["prediction"]["noise_circuit_breaker_active"] is True
    assert res_noise["prediction"]["verdict_code"] == "NEUTRAL"
    assert 40.0 <= res_noise["prediction"]["chance_of_benefit_pct"] <= 60.0

    # 2. Simpson's Paradox Confounded Hub MUST trigger Confounder Alert!
    res_simp = eng.simulate_decision(decision_text="Replace Kolkata Hub with Mumbai Hub")
    assert res_simp["status"] == "simulated"
    assert res_simp["prediction"]["confounder_alert_active"] is True
    assert abs(res_simp["statistical_audit"]["ml_controlled_diff_pct"]) < abs(res_simp["statistical_audit"]["raw_rate_diff_pct"]) * 0.45

    # 3. Pausing healthy low-risk Good Courier MUST return LIKELY_LOSS (negative ₹, zero forced pause gain!)
    res_pause = eng.simulate_decision(
        decision={"action_type": "pause_segment", "column": "fulfillment_partner", "from_value": "Good Courier"}
    )
    assert res_pause["prediction"]["verdict_code"] == "LIKELY_LOSS"
    assert res_pause["prediction"]["expected_net_impact"] < 0

    # 4. Unrecognized prompt MUST return honest `parse_needed` (never silently force Preset #1!)
    res_unk = eng.simulate_decision(decision_text="Agar hum SpaceX Rocket launch kar dein?")
    assert res_unk["status"] == "parse_needed"

    # 5. Builder `delta_pct` MUST be honored accurately (never silently default to -15%)!
    res_scale = eng.simulate_decision(
        decision={"action_type": "scale_numeric", "column": "dispatch_delay_hours", "delta_pct": -30}
    )
    assert res_scale["status"] == "simulated"
    assert "-30.0%" in res_scale["decision_applied"]["label_en"]

    # 6. Word-boundary & leading digit safety ("In Tier 2 / V2..." must not steal the target number!)
    parsed_num = eng.parse_decision_text("In Mumbai Hub cap discount_pct at 15")
    assert parsed_num is not None and parsed_num["value"] == 15.0 and parsed_num["scope_value"] == "Mumbai Hub"

    # 7. 4-Pillar Simulation Confidence Score (HIGH on strong signal vs LOW on noise) + Rollout Cost ROI flip!
    res_good = eng.simulate_decision(decision_text="Replace Bad Courier with Good Courier")
    c_good = res_good["prediction"]["simulation_confidence"]
    c_noise = res_noise["prediction"]["simulation_confidence"]
    assert 75 <= c_good["score"] <= 96 and c_good["tier"] == "HIGH"
    assert c_noise["score"] <= 35 and c_noise["tier"] == "LOW"
    gross_gain = res_good["prediction"]["expected_net_impact"]
    assert gross_gain > 0

    # Rollout cost > gross_gain MUST flip STRONG_GO -> LIKELY_LOSS honestly!
    res_over = eng.simulate_decision(
        decision_text="Replace Bad Courier with Good Courier",
        implementation_cost=gross_gain * 1.6,
    )
    assert res_over["prediction"]["verdict_code"] == "LIKELY_LOSS"
    assert res_over["prediction"]["expected_net_impact"] < 0
    assert res_over["prediction"]["roi_multiple"] < 1.0
    assert res_over["why_loss_could_happen"]["en"][0].startswith("Rollout Cost Exceeds")


# -----------------------------------------------------------------------------
# TEST 6: Multi-Lever Combo (Zero Double-Counting) + Predicted vs Actual
#         Accountability Tracker (Executed vs Ignored Reality + Tenant Isolation)
# -----------------------------------------------------------------------------
def test_stage8_combo_zero_double_counting_and_predicted_vs_actual_tracker(tmp_path: Path, monkeypatch):
    # Build Month-1 Baseline & two Month-2 Realities (Executed vs Ignored)
    rng = np.random.default_rng(777)
    n = 2400

    def _make_month(out_dir: Path, bad_partner_share: float, seed: int) -> pd.DataFrame:
        r = np.random.default_rng(seed)
        out_dir.mkdir(parents=True, exist_ok=True)
        partners = r.choice(
            ["Regional Third-Party Van", "JioMart Fleet Direct"],
            size=n,
            p=[bad_partner_share, 1.0 - bad_partner_share],
        )
        box_a = r.choice(["Blue Box", "Gold Box"], size=n)
        box_b = r.choice(["Tape Red", "Tape White"], size=n)
        delay = np.where(partners == "Regional Third-Party Van", r.uniform(14, 52, size=n), r.uniform(4, 28, size=n))
        mrp = r.uniform(1200, 4800, size=n)
        disc = r.uniform(5, 28, size=n)
        net_sale = mrp * (1.0 - disc / 100.0)
        cogs = mrp * 0.68
        margin = net_sale - cogs
        logit = -2.55 + np.where(partners == "Regional Third-Party Van", 1.55, 0.0) + np.where(delay > 24.0, 1.35, 0.0)
        y = (r.random(n) < (1.0 / (1.0 + np.exp(-logit)))).astype(int)
        df = pd.DataFrame({
            "order_id": [f"M-{seed}-{i}" for i in range(n)],
            "fulfillment_partner": partners,
            "box_color": box_a,
            "tape_color": box_b,
            "dispatch_delay_hours": np.round(delay, 1),
            "mrp_inr": np.round(mrp, 2),
            "discount_pct": np.round(disc, 1),
            "net_sale_inr": np.round(net_sale, 2),
            "cost_price_inr": np.round(cogs, 2),
            "gross_margin_inr": np.round(margin, 2),
            "order_status": np.where(y == 1, "RTO_Returned", "Delivered"),
        })
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)
        (out_dir / "semantic_metrics_manifest.json").write_text(
            json.dumps({"target_column": "order_status", "monetary_column": "net_sale_inr"}),
            encoding="utf-8",
        )
        return df

    m1_dir = tmp_path / "m1_base"
    m2_exec_dir = tmp_path / "m2_executed"
    m2_ign_dir = tmp_path / "m2_ignored"
    _make_month(m1_dir, bad_partner_share=0.35, seed=101)
    _make_month(m2_exec_dir, bad_partner_share=0.02, seed=202)  # Operations executed 94%+!
    _make_month(m2_ign_dir, bad_partner_share=0.36, seed=303)   # Operations ignored decision!

    eng = PredictiveDecisionEngine(str(m1_dir), region_profile="IN")

    # 1. Single A + Single B vs Joint Combo(A + B) -> PROVE ZERO DOUBLE-COUNTING!
    spec_a = {"action_type": "replace_category", "column": "fulfillment_partner", "from_value": "Regional Third-Party Van", "to_value": "JioMart Fleet Direct"}
    spec_b = {"action_type": "cap_numeric", "column": "dispatch_delay_hours", "value": 20.0}

    res_a = eng.simulate_decision(decision=spec_a)
    res_b = eng.simulate_decision(decision=spec_b)
    res_combo = eng.simulate_decision(decisions=[spec_a, spec_b])

    assert res_combo["status"] == "simulated"
    assert res_combo["decision_applied"]["is_combo"] is True
    assert res_combo["decision_applied"]["combo_count"] == 2
    assert res_combo["decision_applied"]["overlap_rows_deduplicated"] > 0
    net_a = res_a["prediction"]["expected_net_impact"]
    net_b = res_b["prediction"]["expected_net_impact"]
    net_c = res_combo["prediction"]["expected_net_impact"]
    assert net_c > max(net_a, net_b), f"Expected joint combo ({net_c}) to exceed each single lever ({net_a}, {net_b})"
    assert net_c < (net_a + net_b), f"DOUBLE-COUNTING DETECTED: combo ({net_c}) >= sum ({net_a + net_b})"
    assert any("Zero Double-Counting" in r for r in res_combo["why_loss_could_happen"]["en"])

    # 2. Natural-Language Combo ("... AND ...") parses 2 levers cleanly
    res_nl_combo = eng.simulate_decision(
        decision_text="Replace Regional Third-Party Van with JioMart Fleet Direct AND cap dispatch_delay_hours at 20"
    )
    assert res_nl_combo["decision_applied"]["is_combo"] is True
    assert res_nl_combo["decision_applied"]["combo_count"] == 2

    # 3. Combo of TWO pure-noise levers STILL trips Noise Circuit-Breaker -> NEUTRAL!
    res_noise_combo = eng.simulate_decision(
        decisions=[
            {"action_type": "replace_category", "column": "box_color", "from_value": "Blue Box", "to_value": "Gold Box"},
            {"action_type": "replace_category", "column": "tape_color", "from_value": "Tape Red", "to_value": "Tape White"},
        ]
    )
    assert res_noise_combo["prediction"]["noise_circuit_breaker_active"] is True
    assert res_noise_combo["prediction"]["verdict_code"] == "NEUTRAL"

    # 4. Combo of 1 Real Lever + 1 Noise Lever calls out the weak noisy lever honestly!
    res_mixed = eng.simulate_decision(
        decisions=[
            spec_a,
            {"action_type": "replace_category", "column": "box_color", "from_value": "Blue Box", "to_value": "Gold Box"},
        ]
    )
    assert any("Weak / Noisy Lever" in r for r in res_mixed["why_loss_could_happen"]["en"])

    # 5. End-to-End FastAPI Predicted-vs-Actual Tracker + Strict Multi-Tenant Isolation!
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    client = TestClient(api_server.app)
    suffix = uuid.uuid4().hex[:8]
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": f"trk_a_{suffix}@example.com", "password": "Password123!", "workspace_name": f"Track A {suffix}"},
    )
    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": f"trk_b_{suffix}@example.com", "password": "Password123!", "workspace_name": f"Track B {suffix}"},
    )
    tok_a = reg_a.json()["access_token"]
    tok_b = reg_b.json()["access_token"]
    tid_a = reg_a.json()["user"]["tenant_id"]

    rid_m1 = f"trk_m1_{suffix}"
    rid_m2_exec = f"trk_m2_exec_{suffix}"
    rid_m2_ign = f"trk_m2_ign_{suffix}"
    t_root = WORKSPACE_ROOT / "runs" / "tenants" / tid_a
    cid_1 = None
    cid_2 = None
    try:
        shutil.copytree(m1_dir, t_root / "runs" / rid_m1 / "output")
        shutil.copytree(m2_exec_dir, t_root / "runs" / rid_m2_exec / "output")
        shutil.copytree(m2_ign_dir, t_root / "runs" / rid_m2_ign / "output")

        # Simulate via API (with combo support!) & Commit
        sim_api = client.post(
            f"/api/v1/predict/simulate/{rid_m1}",
            headers={"Authorization": f"Bearer {tok_a}"},
            json={"decision": spec_a, "implementation_cost": 150000.0},
        )
        assert sim_api.status_code == 200, sim_api.text
        sim_payload = sim_api.json()

        c1_res = client.post(
            "/api/v1/predict/commitments",
            headers={"Authorization": f"Bearer {tok_a}"},
            json={"baseline_run_id": rid_m1, "simulation": sim_payload},
        )
        assert c1_res.status_code == 201, c1_res.text
        cid_1 = c1_res.json()["commitment_id"]

        # Tenant B CANNOT see, verify, or delete Tenant A's commitment!
        b_list = client.get("/api/v1/predict/commitments", headers={"Authorization": f"Bearer {tok_b}"})
        assert b_list.status_code == 200
        assert all(c["commitment_id"] != cid_1 for c in b_list.json()["commitments"])

        b_ver = client.post(
            f"/api/v1/predict/commitments/{cid_1}/verify",
            headers={"Authorization": f"Bearer {tok_b}"},
            json={"actual_run_id": rid_m2_exec},
        )
        assert b_ver.status_code == 404

        # Verify against Month-2 EXECUTED Reality -> high compliance & positive realized ₹!
        v_exec = client.post(
            f"/api/v1/predict/commitments/{cid_1}/verify",
            headers={"Authorization": f"Bearer {tok_a}"},
            json={"actual_run_id": rid_m2_exec},
        )
        assert v_exec.status_code == 200, v_exec.text
        ve = v_exec.json()
        assert ve["status"] == "VERIFIED"
        assert ve["execution_compliance_pct"] >= 85.0
        assert ve["actual_net_impact"] > 0
        assert ve["actual_observed_rate_pct"] < ve["actual_baseline_scope_rate_pct"]

        # Commit #2 & Verify against Month-2 IGNORED Reality -> Low Execution caught honestly!
        c2_res = client.post(
            "/api/v1/predict/commitments",
            headers={"Authorization": f"Bearer {tok_a}"},
            json={"baseline_run_id": rid_m1, "simulation": sim_payload},
        )
        cid_2 = c2_res.json()["commitment_id"]
        v_ign = client.post(
            f"/api/v1/predict/commitments/{cid_2}/verify",
            headers={"Authorization": f"Bearer {tok_a}"},
            json={"actual_run_id": rid_m2_ign},
        )
        assert v_ign.status_code == 200, v_ign.text
        vi = v_ign.json()
        assert vi["execution_compliance_pct"] < 20.0
        assert "Low Execution" in vi["verification_note_en"]
        assert vi["calibration_hit_ci95"] is False
    finally:
        if cid_1:
            api_server.decision_outcome_tracker.delete_commitment(tid_a, cid_1)
        if cid_2:
            api_server.decision_outcome_tracker.delete_commitment(tid_a, cid_2)
        if t_root.exists():
            shutil.rmtree(t_root, ignore_errors=True)


# -----------------------------------------------------------------------------
# TEST 7: Stage 8.3 Multi-Model Ensemble, Calibration ECE, Out-of-Time Backtest,
#         Causal Common-Support Guard & CFO Break-Even Safety Margin
# -----------------------------------------------------------------------------
def test_stage83_multimodel_calibration_temporal_and_causal_support(tmp_path: Path):
    rng = np.random.default_rng(314)
    n = 900
    dates = pd.date_range("2025-01-01", periods=n, freq="6h")
    stores = rng.choice(["Mumbai", "Delhi", "Pune"], size=n)
    # Create clean overlapping data AND one zero-overlap extrapolation stratum ("Luxury" never used "BudgetVan")
    tier = rng.choice(["Budget", "Mid", "Luxury"], size=n, p=[0.45, 0.35, 0.20])
    carrier = np.where(
        tier == "Luxury",
        "ExpressAir",
        rng.choice(["SlowRoad", "ExpressAir"], size=n, p=[0.55, 0.45]),
    )
    order_val = np.where(tier == "Luxury", 4500.0, np.where(tier == "Mid", 1800.0, 900.0))
    prob = np.where(carrier == "SlowRoad", 0.48, 0.11) + np.where(stores == "Delhi", 0.08, 0.0)
    is_rto = (rng.random(n) < np.clip(prob, 0.02, 0.95)).astype(int)

    df = pd.DataFrame({
        "order_date": dates,
        "store": stores,
        "tier": tier,
        "carrier": carrier,
        "order_value_inr": order_val,
        "is_rto": is_rto,
    })
    out_dir = tmp_path / "stage83_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

    eng = PredictiveDecisionEngine(str(out_dir), region_profile="IN")
    m = eng.model_metrics
    assert m["trained"] is True
    assert "Multi-Model Ensemble" in m["algorithm"]
    assert "ensemble_weights" in m and sum(m["ensemble_weights"].values()) >= 0.99
    assert isinstance(m.get("ece_pct"), float)
    assert m.get("temporal_backtest_auc") is not None and m["temporal_backtest_auc"] > 0.65

    # Simulate valid switch with rollout budget -> verify high causal support & CFO Break-Even Safety Margin
    sim = eng.simulate_decision(
        decision={"action_type": "replace_category", "column": "carrier", "from_value": "SlowRoad", "to_value": "ExpressAir"},
        implementation_cost=40000.0,
    )
    assert sim["status"] == "simulated"
    pred = sim["prediction"]
    assert pred["causal_support_pct"] >= 80.0
    assert pred["extrapolation_warning"] is False
    be = pred["break_even_analysis"]
    assert be["break_even_realization_pct"] is not None and be["break_even_realization_pct"] < 100.0
    assert be["margin_of_safety_x"] is not None and be["margin_of_safety_x"] > 1.0
    assert "margin of safety" in be["summary_en"].lower()



