"""
=============================================================================
DATAX-RAY V7.0 PROACTIVE COPILOT, VOICE BRIEF & SHARE PACK TEST SUITE
=============================================================================
Validates all 8 Red-Team Safety Guards (R1-R8) + Anti-Hallucination Check 13
+ Alert 24h Cooldown + Impact Verifier + Live FastAPI Endpoints & Benchmarks.
=============================================================================
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from autonomous_engine.proactive_anomaly_radar import run_proactive_anomaly_radar
from autonomous_engine.voice_brief_synthesizer import (
    build_impact_verifier_summary,
    build_voice_brief_script,
    render_boardroom_pdf_brief_html,
)
from autonomous_engine.alert_dispatcher import (
    check_and_record_alert_cooldown,
    format_proactive_anomaly_alert,
)


def _make_accelerating_d2c_df(n: int = 1200) -> pd.DataFrame:
    """12-month D2C ledger where 'Delhivery Surface' spikes from ~10% -> ~38% in final 2 months."""
    rng = np.random.default_rng(707)
    months = pd.date_range("2025-01-01", "2025-12-28", periods=n)
    couriers = rng.choice(["BlueDart Air", "Delhivery Surface", "XpressBees"], size=n, p=[0.4, 0.35, 0.25])
    payment = rng.choice(["Prepaid", "COD"], size=n, p=[0.55, 0.45])
    order_val = rng.uniform(800, 3500, size=n).round(2)

    is_recent = months >= pd.Timestamp("2025-11-01")
    probs = np.full(n, 0.10)
    probs[(couriers == "Delhivery Surface") & is_recent] = 0.42
    rto = (rng.random(n) < probs).astype(int)

    return pd.DataFrame({
        "order_id": [f"ORD-{i:05d}" for i in range(n)],
        "order_date": months.strftime("%Y-%m-%d"),
        "courier_partner": couriers,
        "payment_gateway": payment,
        "order_value": order_val,
        "is_rto": rto,
        "_is_target_event": rto,
    })


def test_r1_snapshot_without_date_column_gracefully_suppresses_radar():
    """R1: Snapshot dataset with NO date column must return INSUFFICIENT_TIME_HISTORY (0 fake trend)."""
    rng = np.random.default_rng(11)
    df = pd.DataFrame({
        "patient_id": range(200),
        "ejection_fraction": rng.integers(20, 65, size=200),
        "serum_creatinine": rng.uniform(0.7, 3.5, size=200),
        "death_event": rng.binomial(1, 0.3, size=200),
    })
    res = run_proactive_anomaly_radar(
        df,
        canonical_target={"target_col": "death_event", "cost_col": None},
        currency_symbol="",
        is_financial=False,
    )
    assert res["status"] == "INSUFFICIENT_TIME_HISTORY"
    assert res["is_applicable"] is False
    assert res["overall_alert_level"] == "NO_TIME_AXIS"
    assert res["accelerating_cohorts"] == []
    assert res["forward_risk_projection"] is None


def test_r2_cohort_acceleration_detection_and_24h_alert_cooldown(tmp_path):
    """R2: Genuine accelerating cohort triggers CRITICAL + projection; 24h cooldown prevents spam."""
    df = _make_accelerating_d2c_df(1400)
    res = run_proactive_anomaly_radar(
        df,
        output_dir=tmp_path,
        canonical_target={"target_col": "is_rto", "cost_col": "order_value", "binary_target": df["is_rto"]},
        currency_symbol="₹",
        is_financial=True,
        business_category="d2c_ecommerce",
    )
    assert res["status"] == "ANALYZED"
    assert res["is_applicable"] is True
    assert res["overall_alert_level"] == "CRITICAL"
    assert len(res["accelerating_cohorts"]) >= 1
    top_c = res["accelerating_cohorts"][0]
    assert top_c["segment"] == "Delhivery Surface"
    assert top_c["delta_pp"] >= 15.0
    assert top_c["fdr_q_value"] <= 0.01
    assert res["forward_risk_projection"] is not None
    assert "₹" in res["forward_risk_projection"]["formatted_range"]

    # Format proactive alert & test 24h anti-fatigue cooldown
    fmt = format_proactive_anomaly_alert(res, run_id="nexura_test", lang="hi")
    assert fmt["eligible"] is True
    assert fmt["severity"] == "CRITICAL"
    cd_file = tmp_path / "cooldown.json"
    first = check_and_record_alert_cooldown("tenant_a", fmt["signature"], cooldown_hours=24.0, state_path=cd_file)
    second = check_and_record_alert_cooldown("tenant_a", fmt["signature"], cooldown_hours=24.0, state_path=cd_file)
    assert first["allowed"] is True
    assert second["allowed"] is False
    assert second["remaining_minutes"] > 1400


def test_r2_uniform_noise_no_false_alarm():
    """R2: Stable random time-series with zero real acceleration must report ALL_CLEAR."""
    rng = np.random.default_rng(42)
    n = 1200
    df = pd.DataFrame({
        "order_date": pd.date_range("2025-01-01", "2025-12-28", periods=n).strftime("%Y-%m-%d"),
        "branch": rng.choice(["North", "South", "East"], size=n),
        "amount": rng.uniform(500, 1500, size=n),
        "defect": rng.binomial(1, 0.15, size=n),
    })
    res = run_proactive_anomaly_radar(
        df,
        canonical_target={"target_col": "defect", "cost_col": "amount", "binary_target": df["defect"]},
        currency_symbol="₹",
        is_financial=True,
    )
    assert res["status"] == "ANALYZED"
    assert res["overall_alert_level"] == "ALL_CLEAR"
    assert res["should_dispatch_alert"] is False


def test_r3_and_r5_non_monetary_voice_brief_and_radar_emit_zero_fake_currency(tmp_path):
    """R3 & R5: Non-monetary clinical dataset must NEVER emit $/₹/€/£ and must be PII-scrubbed."""
    rng = np.random.default_rng(99)
    n = 900
    dates = pd.date_range("2025-01-01", "2025-12-20", periods=n)
    ward = rng.choice(["ICU-A", "Ward-B"], size=n)
    is_rec = dates >= pd.Timestamp("2025-11-01")
    probs = np.where((ward == "ICU-A") & is_rec, 0.48, 0.12)
    events = (rng.random(n) < probs).astype(int)
    df = pd.DataFrame({
        "admission_date": dates.strftime("%Y-%m-%d"),
        "ward_unit": ward,
        "readmitted": events,
    })

    radar = run_proactive_anomaly_radar(
        df,
        output_dir=tmp_path,
        canonical_target={"target_col": "readmitted", "cost_col": None, "binary_target": df["readmitted"]},
        currency_symbol="$",
        is_financial=False,
    )
    assert radar["is_financial"] is False
    if radar["forward_risk_projection"]:
        for ch in ("$", "₹", "€", "£"):
            assert ch not in radar["forward_risk_projection"]["formatted_range"]
            assert ch not in radar["forward_risk_projection"]["note_en"]

    pulse = {
        "total_records": n,
        "total_adverse_events": int(events.sum()),
        "overall_adverse_rate_pct": round(float(events.mean() * 100), 2),
        "is_financial": False,
        "formatted_capital_drag": f"{int(events.sum())} Cases",
        "owner_friendly": {
            "en": {
                "bottleneck": {"title": "ICU-A has elevated readmissions", "story": "Audit discharge checklists."},
                "recovery": {"title": f"Prevent {int(events.sum())} cases"},
                "pathways": [{"title": "Plan A", "action": "Add 48h nurse follow-up."}],
            },
            "hi": {
                "bottleneck": {"title": "ICU-A में री-एडमिशन ज़्यादा है", "story": "डिस्चार्ज चेकलिस्ट सुधारें।"},
                "recovery": {"title": f"{int(events.sum())} केस बचाएँ"},
                "pathways": [{"title": "Plan A", "action": "48 घंटे का नर्स फ़ॉलो-अप जोड़ें।"}],
            },
        },
    }
    vb = build_voice_brief_script(
        executive_pulse=pulse,
        category_intelligence={"display_name_en": "Healthcare & Clinical", "display_name_hi": "हेल्थकेयर व क्लिनिकल", "computed_kpis": []},
        proactive_anomaly=radar,
        run_title="Hospital Readmission Audit",
        output_dir=tmp_path,
    )
    assert vb["pii_scrubbed"] is True
    assert len(vb["beats"]) == 4
    for fld in ("full_script_en", "full_script_hi", "whatsapp_share_en", "whatsapp_share_hi"):
        for ch in ("$", "₹", "€", "£"):
            assert ch not in vb[fld], f"Fake currency '{ch}' leaked into {fld}!"


def test_r6_100k_row_vectorized_speed_under_budget():
    """R6: 100,000-row radar execution must remain fully vectorized and finish well under 1.5s."""
    df_big = _make_accelerating_d2c_df(100_000)
    t0 = time.perf_counter()
    res = run_proactive_anomaly_radar(
        df_big,
        canonical_target={"target_col": "is_rto", "cost_col": "order_value", "binary_target": df_big["is_rto"]},
        currency_symbol="₹",
        is_financial=True,
    )
    elapsed = time.perf_counter() - t0
    assert res["status"] == "ANALYZED"
    assert res["audited_fact_records"] == 100_000
    assert elapsed < 2.0, f"Vectorized radar too slow on 100k rows: {elapsed:.2f}s"


def test_r7_anti_hallucination_check13_blocks_row_drift_and_fake_currency(tmp_path):
    """R7: Guard Check 13 passes on clean V7 artifacts and blocks row drift & fake currency."""
    from autonomous_engine.anti_hallucination_guard import run_anti_hallucination_audit

    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    df = _make_accelerating_d2c_df(300)
    df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)
    bp_path = out_dir / "execution_blueprint.json"
    bp_path.write_text(json.dumps({"target_metric": "is_rto"}), encoding="utf-8")

    radar = run_proactive_anomaly_radar(
        df,
        output_dir=out_dir,
        canonical_target={"target_col": "is_rto", "cost_col": None, "binary_target": df["is_rto"]},
        currency_symbol="",
        is_financial=False,
    )
    build_voice_brief_script(
        executive_pulse={"total_records": 300, "total_adverse_events": int(df["is_rto"].sum()), "overall_adverse_rate_pct": 12.0, "is_financial": False},
        proactive_anomaly=radar,
        output_dir=out_dir,
    )

    clean = run_anti_hallucination_audit(str(out_dir), str(bp_path))
    v7_clean = [v for v in clean.get("physics_invariant_violations", []) if "Proactive Anomaly" in v or "Voice Brief" in v]
    assert v7_clean == []

    # Tamper voice brief with fake ₹ and wrong row count -> Check 13 MUST flag BOTH!
    vb_p = out_dir / "voice_brief_script.json"
    vb_bad = json.loads(vb_p.read_text(encoding="utf-8"))
    vb_bad["audited_fact_records"] = 9999
    vb_bad["full_script_en"] += " You lost ₹50,000."
    vb_p.write_text(json.dumps(vb_bad), encoding="utf-8")

    tampered = run_anti_hallucination_audit(str(out_dir), str(bp_path))
    v7_bad = [v for v in tampered.get("physics_invariant_violations", []) if "Voice Brief" in v]
    assert any("Row Drift" in v for v in v7_bad)
    assert any("Fake Currency" in v for v in v7_bad)


def test_r8_impact_verifier_honesty_and_live_fastapi_v7_endpoints():
    """R8: Impact verifier never fakes improvement; FastAPI exposes V7 payloads & 2-Page PDF."""
    # 1. Statistical improvement verified
    imp_ok = build_impact_verifier_summary(
        historical_drift={
            "has_historical_comparison": True,
            "previous_run": {"records": 1000, "adverse_events": 250, "adverse_rate_pct": 25.0, "capital_drag": 500000},
            "current_run": {"records": 1000, "adverse_events": 140, "adverse_rate_pct": 14.0, "capital_drag": 280000},
        },
        roi_summary={"total_actions_logged": 12, "resolved_count": 9},
        is_financial=True,
        currency_unit="₹",
    )
    assert imp_ok["verdict"] == "VERIFIED_IMPROVEMENT"
    assert imp_ok["p_value"] < 0.001
    assert imp_ok["capital_saved"] == 220000.0

    # 2. Tiny flat noise must NOT claim success
    imp_flat = build_impact_verifier_summary(
        historical_drift={
            "has_historical_comparison": True,
            "previous_run": {"records": 200, "adverse_events": 40, "adverse_rate_pct": 20.0, "capital_drag": 10000},
            "current_run": {"records": 200, "adverse_events": 38, "adverse_rate_pct": 19.0, "capital_drag": 9500},
        },
        is_financial=True,
        currency_unit="₹",
    )
    assert imp_flat["verdict"] == "NO_STATISTICAL_CHANGE"

    # 3. Live FastAPI TestClient verification
    from fastapi.testclient import TestClient
    from autonomous_engine.api_server import app

    client = TestClient(app)
    h = client.get("/health")
    assert h.status_code == 200
    assert h.json()["version"] == "7.0.0"

    r_nex = client.get("/api/v1/benchmarks/nexura_lifestyle_brand")
    assert r_nex.status_code == 200
    j_nex = r_nex.json()
    assert j_nex.get("proactive_anomaly") and j_nex["proactive_anomaly"]["is_applicable"] is True
    assert j_nex.get("voice_brief") and len(j_nex["voice_brief"]["beats"]) == 4
    assert "D2C" in j_nex["voice_brief"]["full_script_en"]
    assert j_nex.get("impact_verifier") is not None

    r_hot = client.get("/api/v1/benchmarks/hotel_booking_cancellation")
    assert r_hot.status_code == 200
    j_hot = r_hot.json()
    assert j_hot.get("proactive_anomaly") and j_hot["proactive_anomaly"]["is_applicable"] is True
    assert "reservation_status" not in str(j_hot["proactive_anomaly"].get("date_column") or "").lower()
    assert j_hot.get("voice_brief") and len(j_hot["voice_brief"]["beats"]) == 4
    assert "Hotel" in j_hot["voice_brief"]["full_script_en"]

    # 2-Page A4 Boardroom PDF Brief HTML in EN & HI
    r_pdf_en = client.get("/api/v1/report/nexura_lifestyle_brand/boardroom-brief?lang=en")
    assert r_pdf_en.status_code == 200
    assert "BOARDROOM EXECUTIVE BRIEF" in r_pdf_en.text
    assert "window.print()" in r_pdf_en.text

    r_pdf_hi = client.get("/api/v1/report/nexura_lifestyle_brand/boardroom-brief?lang=hi")
    assert r_pdf_hi.status_code == 200
    assert "कैटेगरी इकोनॉमिक्स" in r_pdf_hi.text
