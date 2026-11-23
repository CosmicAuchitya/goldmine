"""
Stress Tests & Verification Suite for Autopsy Weakness Fixes:
1. Signal-First Ranked Leaks Synthesizer (deduplicated Top Leaks, $0 shields, opportunities, unlock packs, 0 fake $ on non-monetary).
2. Dirty Real-World Multi-Sheet Stress Test (Shopify Orders + Shiprocket RTO + Meta/Google Ad Spend):
   - Case/whitespace-mismatched primary key join (`order_id` <-> `Order_ID`)
   - Exact proportional N:1 Ad Spend allocation (0x overcounting!)
   - Exact 0 Cartesian drift + auto-unlocked Q063 CAC, Q064 POAS & Q065 Payback!
3. Real Live Read-Only API Connectors (Shopify, Stripe, Razorpay) via mocked safe_urlopen.
4. Automated Alert Dispatcher (SMTP Email, WhatsApp Cloud/Twilio, Webhook dry-run honesty) + Live FastAPI Endpoints + Signal-First Web UI checks.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient


class _MockHTTPResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._bytes = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_signal_first_ranked_leaks_on_nexura_and_non_monetary(tmp_path):
    from autonomous_engine.omni_leak_scanner import OmniDimensionalLeakScanner
    from autonomous_engine.universal_200_questions_engine import Universal200QuestionsEngine
    from autonomous_engine.ranked_leak_synthesizer import synthesize_ranked_leaks

    nexura_csv = Path("enterprise_showcase_data/nexura_lifestyle_brand/raw_data/nexura_3yr_omnichannel_transactions.csv")
    if not nexura_csv.exists():
        pytest.skip("Nexura showcase CSV missing")

    df = pd.read_csv(nexura_csv)
    omni = OmniDimensionalLeakScanner(df, blueprint={"region_profile": "IN"}).run_full_scan()
    q200 = Universal200QuestionsEngine(df, blueprint={"region_profile": "IN"}, omni_report=omni).generate_all_200_questions()
    ranked = synthesize_ranked_leaks(df, omni_report=omni, q200_report=q200, out_dir=tmp_path)

    assert (tmp_path / "ranked_leaks_report.json").exists()
    assert ranked["mode"] == "AUTONOMOUS_EXCEPTION_DETECTION"
    leaks = ranked["abnormal_deviations"]
    # NO arbitrary Top-10 cap: Nexura has >10 real deviations across P&L, Ops, SLA, CSAT, Coupon Reuse, Late Night, Benford!
    assert len(leaks) >= 11
    assert [x["rank"] for x in leaks] == list(range(1, len(leaks) + 1))

    # Critical top leaks present & deduplicated with Expected vs Actual & zero empty strings/None
    leak_ids = [x["leak_id"] for x in leaks]
    assert "LEAK_NEGATIVE_MARGIN_ORDERS" in leak_ids
    assert any("FLASH30" in lid for lid in leak_ids)
    assert "LEAK_CONFOUNDER_2D_HOTSPOT" in leak_ids
    for x in leaks:
        assert "''" not in x["headline_en"] and "None" not in x["headline_en"]
        assert x.get("expected_standard_en") and x.get("actual_observed_en") and x.get("decision_rule")
    conf_card = next(x for x in leaks if x["leak_id"] == "LEAK_CONFOUNDER_2D_HOTSPOT")
    assert "Uttar Pradesh" in conf_card["headline_en"] and "Cash on Delivery (COD)" in conf_card["headline_en"]
    flash_card = next(x for x in leaks if "FLASH30" in x["leak_id"])
    assert flash_card["estimated_cash_impact"] >= 580000.0

    # Healthy checks are autonomously suppressed (hidden from alarm feed!)
    healthy_ids = {h["check_id"] for h in ranked["healthy_checks_suppressed"]}
    assert "CHK_NO_TRAP_SKUS" in healthy_ids
    assert "CHK_PROMO_LOYALTY" in healthy_ids
    assert "CHK_ZERO_DUPLICATES" in healthy_ids
    assert "CHK_ZERO_DEAD_STOCK" in healthy_ids
    assert len(ranked["do_not_spend_shields"]) >= 1
    assert len(ranked["hidden_opportunities"]) >= 3
    assert 2 <= len(ranked["missing_data_unlock_packs"]) <= 4

    # Completely healthy / uniform business dataset -> system autonomously surfaces 0 false alarms!
    import numpy as np
    rng = np.random.default_rng(42)
    clean_rows = []
    # Exact equal 5% return rate across every region & every quarter, 0 repeat abusers, Benford-natural amounts
    benford_amts = 10.0 ** rng.uniform(2.0, 4.0, size=160)
    for i in range(160):
        reg_idx = i % 4
        q_month = (i % 6) + 1
        # Exactly 1 returned order per (region, month) bucket (uniform 0 repeat offenders!)
        is_ret = 1 if i < 24 else 0
        clean_rows.append({
            "order_id": f"ORD-{i:04d}",
            "order_date": f"2025-0{q_month}-{(i % 25) + 1:02d}",
            "customer_id": f"C-{i:04d}",
            "region": ["North", "South", "East", "West"][reg_idx],
            "net_billed_amount_inr": round(float(benford_amts[i]), 2),
            "net_contribution_margin_inr": round(float(benford_amts[i]) * 0.45, 2),
            "is_returned": is_ret,
        })
    clean_df = pd.DataFrame(clean_rows)
    omni_cl = OmniDimensionalLeakScanner(clean_df, blueprint={"region_profile": "IN"}).run_full_scan()
    q200_cl = Universal200QuestionsEngine(clean_df, blueprint={"region_profile": "IN"}, omni_report=omni_cl).generate_all_200_questions()
    ranked_cl = synthesize_ranked_leaks(clean_df, omni_report=omni_cl, q200_report=q200_cl)
    abn_ids_cl = {x["leak_id"] for x in ranked_cl["abnormal_deviations"]}
    # Zero false alarms on Margin, Duplicates, Region, or Repeat Abusers!
    assert "LEAK_NEGATIVE_MARGIN_ORDERS" not in abn_ids_cl
    assert "LEAK_DUPLICATE_KEYS" not in abn_ids_cl
    assert "LEAK_DIM_region" not in abn_ids_cl
    assert "LEAK_REPEAT_ABUSERS_NEG_LTV" not in abn_ids_cl
    assert ranked_cl["summary"]["healthy_suppressed_count"] >= 4

    # Non-monetary dataset must never fabricate currency symbols
    nm_df = pd.DataFrame({
        "Type": ["L", "L", "M", "H", "L", "M"] * 10,
        "Rotational_speed_rpm": [1200, 1300, 1500, 1600, 1250, 1550] * 10,
        "Machine_failure": [1, 1, 0, 0, 1, 0] * 10,
    })
    omni_nm = OmniDimensionalLeakScanner(nm_df).run_full_scan()
    q200_nm = Universal200QuestionsEngine(nm_df, omni_report=omni_nm).generate_all_200_questions()
    ranked_nm = synthesize_ranked_leaks(nm_df, omni_report=omni_nm, q200_report=q200_nm)
    assert ranked_nm["is_financial"] is False
    for lk in ranked_nm["top_ranked_leaks"]:
        assert lk["estimated_cash_impact"] is None
        assert "$" not in lk["formatted_impact"] and "₹" not in lk["formatted_impact"]


def test_dirty_multisheet_d2c_stress_test_zero_drift_and_poas_unlock(tmp_path):
    """Real-world dirty 3-sheet D2C test: Orders + Shiprocket RTO + Meta/Google Ad Spend."""
    from autonomous_engine.master_orchestrator import run_master_pipeline
    from autonomous_engine.anti_hallucination_guard import run_anti_hallucination_audit

    raw_dir = tmp_path / "raw_data"
    out_dir = tmp_path / "output"
    cache_dir = tmp_path / "cache"
    raw_dir.mkdir()

    # Sheet 1: Dirty Shopify Orders (120 rows, mixed lowercase/spaces on order_id, Indian ₹ formatting)
    n = 120
    orders_rows = []
    for i in range(n):
        ch = "Meta Ads" if i % 2 == 0 else "Google Search"
        gross = 2000.0 if i % 3 else 3500.0
        disc = 200.0 if i % 4 == 0 else 0.0
        net = gross - disc
        margin = net * 0.45 - (350.0 if i % 5 == 0 else 0.0)
        orders_rows.append({
            "order_id": f"  ord-{1000 + i} " if i % 2 == 0 else f"ORD-{1000 + i}",
            "order_date": f"2025-0{(i % 6) + 1}-{(i % 25) + 1:02d}",
            "customer_id": f"CUST-{100 + (i % 60)}",
            "acquisition_channel": ch,
            "payment_gateway": "Cash on Delivery (COD)" if i % 3 == 0 else "UPI Prepaid",
            "gross_order_value_inr": f"₹{gross:,.2f}",
            "discount_amount_inr": disc,
            "net_billed_amount_inr": f"₹{net:,.2f}",
            "net_contribution_margin_inr": margin,
        })
    pd.DataFrame(orders_rows).to_csv(raw_dir / "shopify_orders.csv", index=False)

    # Sheet 2: Dirty Shiprocket Logistics (mismatched case header `Order_ID` + duplicate scan row!)
    ship_rows = []
    for i in range(n):
        is_cod = (i % 3 == 0)
        is_rto = 1 if (is_cod and i % 2 == 0) else (1 if i % 19 == 0 else 0)
        ship_rows.append({
            "Order_ID": f"ORD-{1000 + i}",
            "courier_partner": "Delhivery Surface" if is_cod else "BlueDart Air",
            "dispatch_delay_days": 3.5 if is_rto else 1.0,
            "is_rto_or_cancelled": is_rto,
        })
    # Add duplicate logistics event row for ORD-1000 to verify 0 Cartesian drift!
    ship_rows.append({
        "Order_ID": "ORD-1000",
        "courier_partner": "Delhivery Surface",
        "dispatch_delay_days": 0.5,
        "is_rto_or_cancelled": 0,
    })
    pd.DataFrame(ship_rows).to_csv(raw_dir / "shiprocket_rto_logs.csv", index=False)

    # Sheet 3: Channel-level Ad Spend (multiple monthly rows per channel = exact ₹60,000 total!)
    ad_rows = [
        {"acquisition_channel": "Meta Ads", "ad_spend_inr": 25000.0},
        {"acquisition_channel": "Meta Ads", "ad_spend_inr": 15000.0},
        {"acquisition_channel": "Google Search", "ad_spend_inr": 12000.0},
        {"acquisition_channel": "Google Search", "ad_spend_inr": 8000.0},
    ]
    pd.DataFrame(ad_rows).to_csv(raw_dir / "meta_google_ad_spend.csv", index=False)

    ok = run_master_pipeline(
        data_dir=str(raw_dir),
        output_dir=str(out_dir),
        cache_dir=str(cache_dir),
        mode="templated",
        region_profile="IN",
    )
    assert ok is True

    fact_df = pd.read_parquet(out_dir / "bi_ready_fact.parquet")
    # 1. Zero Cartesian Drift across 3 messy tables!
    assert len(fact_df) == n
    # 2. Primary-key enrichment from Shiprocket joined despite `order_id` <-> `Order_ID` & whitespace!
    assert "courier_partner" in fact_df.columns
    assert "is_rto_or_cancelled" in fact_df.columns
    assert fact_df["courier_partner"].notna().all()
    # 3. Proportional Ad-Spend Allocation kept exact ₹60,000 total (0x overcounting!)
    assert "ad_spend_inr" in fact_df.columns
    assert abs(float(fact_df["ad_spend_inr"].sum()) - 60000.0) < 1.0

    # 4. Q063 CAC, Q064 POAS & Q065 CAC Payback unlocked automatically as DIRECT_ANSWERED!
    q200 = json.loads((out_dir / "universal_200_questions_report.json").read_text(encoding="utf-8"))
    qmap = {q["id"]: q for q in q200["questions"]}
    assert qmap["Q063"]["status"] == "DIRECT_ANSWERED"
    assert qmap["Q064"]["status"] == "DIRECT_ANSWERED" and "POAS" in qmap["Q064"]["key_metric"]
    assert qmap["Q065"]["status"] == "DIRECT_ANSWERED" and "payback" in qmap["Q065"]["key_metric"]

    # 5. Ranked Leaks & Anti-Hallucination Audit pass cleanly
    ranked = json.loads((out_dir / "ranked_leaks_report.json").read_text(encoding="utf-8"))
    assert len(ranked["top_ranked_leaks"]) >= 1
    audit = run_anti_hallucination_audit(str(out_dir), str(out_dir / "execution_blueprint.json"))
    assert audit.get("physics_invariant_violations") == []


def test_real_live_api_connectors_normalization_and_validation():
    from autonomous_engine.live_connectors import (
        fetch_shopify_live_orders,
        fetch_stripe_live_charges,
        fetch_razorpay_live_payments,
    )

    shopify_payload = {
        "orders": [
            {
                "id": 101, "name": "#1001", "created_at": "2026-01-10T12:00:00Z",
                "financial_status": "paid", "cancelled_at": None,
                "payment_gateway_names": ["razorpay"], "source_name": "web",
                "total_line_items_price": "1500.00", "total_discounts": "100.00", "total_price": "1400.00",
                "shipping_address": {"province": "Maharashtra"}, "customer": {"id": 9001},
                "discount_codes": [{"code": "SAVE10"}],
            },
            {
                "id": 102, "name": "#1002", "created_at": "2026-01-11T12:00:00Z",
                "financial_status": "refunded", "cancelled_at": "2026-01-12T10:00:00Z",
                "payment_gateway_names": ["Cash on Delivery (COD)"], "source_name": "web",
                "total_line_items_price": "2000.00", "total_discounts": "0.00", "total_price": "2000.00",
                "shipping_address": {"province": "Uttar Pradesh"}, "customer": {"id": 9002},
                "discount_codes": [],
            },
        ]
    }
    with patch("autonomous_engine.live_connectors.safe_urlopen", return_value=_MockHTTPResponse(shopify_payload)):
        df_sh = fetch_shopify_live_orders("demo-store.myshopify.com", "shpat_test_token")
        assert len(df_sh) == 2
        assert list(df_sh["is_rto_or_cancelled"]) == [0, 1]
        assert df_sh.loc[0, "coupon_code"] == "SAVE10"

    stripe_payload = {
        "data": [
            {"id": "ch_1", "created": 1736500000, "amount": 5000, "amount_refunded": 0, "refunded": False, "disputed": False, "status": "succeeded", "currency": "usd", "customer": "cus_1", "payment_method_details": {"type": "card"}},
            {"id": "ch_2", "created": 1736500100, "amount": 9900, "amount_refunded": 9900, "refunded": True, "disputed": False, "status": "succeeded", "currency": "usd", "customer": "cus_2", "payment_method_details": {"type": "card"}},
        ]
    }
    with patch("autonomous_engine.live_connectors.safe_urlopen", return_value=_MockHTTPResponse(stripe_payload)):
        df_st = fetch_stripe_live_charges("sk_test_123")
        assert len(df_st) == 2
        assert abs(df_st.loc[0, "net_billed_amount"] - 50.0) < 1e-6
        assert list(df_st["is_payment_failed_or_refunded"]) == [0, 1]

    rzp_payload = {
        "items": [
            {"id": "pay_1", "created_at": 1736500000, "amount": 125000, "fee": 2500, "status": "captured", "amount_refunded": 0, "method": "upi", "email": "a@b.com"},
            {"id": "pay_2", "created_at": 1736500200, "amount": 250000, "fee": 5000, "status": "failed", "amount_refunded": 0, "method": "card", "email": "c@d.com"},
        ]
    }
    with patch("autonomous_engine.live_connectors.safe_urlopen", return_value=_MockHTTPResponse(rzp_payload)):
        df_rz = fetch_razorpay_live_payments("rzp_test_key", "rzp_test_sec")
        assert len(df_rz) == 2
        assert abs(df_rz.loc[0, "net_billed_amount_inr"] - 1250.0) < 1e-6
        assert list(df_rz["is_payment_failed_or_refunded"]) == [0, 1]


def test_alert_dispatcher_endpoints_and_signal_first_ui(monkeypatch):
    from autonomous_engine.api_server import app
    from autonomous_engine.alert_dispatcher import dispatch_email_smtp, dispatch_whatsapp_alert

    monkeypatch.delenv("DATAXRAY_SMTP_HOST", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)

    # Honest dry-run checks (never fake sent=True without credentials)
    em = dispatch_email_smtp("founder@example.com", "Test", "Plain", "<p>HTML</p>")
    assert em["status"] == "dry_run" and em["delivered"] is False
    wa = dispatch_whatsapp_alert("+919999999999", "Test msg")
    assert wa["status"] == "dry_run" and wa["delivered"] is False

    client = TestClient(app)
    r_rank = client.get("/api/v1/ranked-leaks/hotel_booking_cancellation")
    assert r_rank.status_code == 200
    rdata = r_rank.json()
    assert "top_ranked_leaks" in rdata and "missing_data_unlock_packs" in rdata

    r_disp = client.post(
        "/api/v1/alerts/dispatch/hotel_booking_cancellation",
        json={"channel": "email", "recipient": "owner@hotel.com", "lang": "hi"},
    )
    assert r_disp.status_code == 200
    assert r_disp.json()["status"] == "dry_run"

    # Signal-First Web UI checks
    html_txt = Path("autonomous_engine/web_client.html").read_text(encoding="utf-8")
    assert 'id="rankedLeaksSection"' in html_txt
    assert 'id="deepAuditDrawer"' in html_txt
    assert 'value="DATA_BACKED" selected' in html_txt
    assert "resetCopilotChat()" in html_txt
    assert "fonts.googleapis.com" not in html_txt


def test_custom_qa_multiturn_text_filters_currency_and_missing_guard():
    """Verifies all 4 Custom Q&A upgrades: multi-filter offline SQL, multi-turn follow-up memory, ₹ currency, and missing-column honesty."""
    from autonomous_engine.conversational_qa_engine import ConversationalBusinessQAEngine
    from autonomous_engine.api_server import app

    nexura_out = Path("enterprise_showcase_data/nexura_lifestyle_brand/output")
    if not (nexura_out / "bi_ready_fact.parquet").exists():
        pytest.skip("Nexura output parquet missing")

    with ConversationalBusinessQAEngine(nexura_out) as qa:
        # 1. Offline multi-filter (FLASH30 + Tier 3) + Margin metric + INR ₹ currency (ZERO $) + Business-Doctor verdict
        r1 = qa.ask("FLASH30 aur Tier 3 mein kitna margin aur RTO hai?", language="hi", use_llm=False)
        assert r1["status"] == "success"
        assert "coupon_code" in r1["active_filters"] and "city_tier" in r1["active_filters"]
        assert "₹" in r1["answer_markdown"] and "$" not in r1["answer_markdown"]
        assert "बिज़नेस-डॉक्टर निष्कर्ष" in r1["answer_markdown"]
        assert r1["data"][0]["total_records"] > 0

        # 2. Multi-turn follow-up memory: UP -> "ab sirf COD" (44.80%) -> "now only Prepaid" (7.04%)
        qa.conversation_history.clear()
        t1 = qa.ask("Uttar Pradesh mein kitna loss hai?", language="hi", use_llm=False)
        assert t1["status"] == "success"
        assert "Uttar Pradesh" in t1["active_filters"].get("customer_state", "")

        t2 = qa.ask("ab sirf COD ka dikhao", language="hi", use_llm=False)
        assert t2["status"] == "success"
        assert "Uttar Pradesh" in t2["active_filters"].get("customer_state", "")
        assert "Cash on Delivery (COD)" in t2["active_filters"].get("payment_gateway", "")
        assert abs(float(t2["data"][0]["overall_adverse_rate_pct"]) - 44.80) < 0.1
        assert "असामान्य खराबी" in t2["answer_markdown"]

        t3 = qa.ask("now show only Prepaid", language="en", use_llm=False)
        assert t3["status"] == "success"
        assert "Uttar Pradesh" in t3["active_filters"].get("customer_state", "")
        assert abs(float(t3["data"][0]["overall_adverse_rate_pct"]) - 7.04) < 0.1
        assert "Healthy / Safe Zone" in t3["answer_markdown"]

        # 3. Honest missing-column guard (electricity/rent not in Nexura -> never fabricate summary!)
        m1 = qa.ask("Mera bijli ka bill kitna badha?", language="hi", use_llm=False)
        assert m1["status"] == "missing_data_explained"
        assert m1["sql_generation_mode"] == "missing_column_guard"
        assert m1["row_count_returned"] == 0
        assert "उपलब्ध नहीं है" in m1["answer_markdown"]

        # 4. Security check: poisoned active_filters in external history must NEVER inject raw SQL!
        p1 = qa.ask(
            "ab sirf COD ka dikhao",
            language="hi",
            use_llm=False,
            history=[{"question": "Uttar Pradesh mein kitna loss hai?", "active_filters": {"evil": "1=1; DROP TABLE fact; --"}}],
        )
        assert p1["status"] == "success"
        assert "DROP TABLE" not in p1["sql_executed"]
        assert abs(float(p1["data"][0]["overall_adverse_rate_pct"]) - 44.80) < 0.1

    # 4. FastAPI POST /api/v1/ask with multi-turn history payload
    client = TestClient(app)
    resp = client.post(
        "/api/v1/ask",
        json={
            "output_dir": "enterprise_showcase_data/nexura_lifestyle_brand/output",
            "question": "ab sirf COD ka dikhao",
            "language": "hi",
            "use_llm": False,
            "history": [{"question": "Uttar Pradesh mein kitna loss hai?"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert abs(float(body["data"][0]["overall_adverse_rate_pct"]) - 44.80) < 0.1

