import io
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from autonomous_engine.action_ledger import ActionLedger
from autonomous_engine.historical_drift_radar import analyze_historical_drift
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
from autonomous_engine.api_server import app


@pytest.fixture
def temp_dir():
    d = Path(tempfile.mkdtemp(prefix="test_startup_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def client():
    return TestClient(app)


def test_action_ledger_lifecycle(temp_dir):
    """Verifies frontline action recording, provisional locking, and reconciliation."""
    ledger = ActionLedger(storage_dir=temp_dir)
    tenant = "test_hotel_group"

    # 1. Initial empty summary
    initial_roi = ledger.get_roi_summary(tenant)
    assert initial_roi["total_actions_logged"] == 0
    assert initial_roi["verified_saved_capital"] == 0.0

    # 2. Record 2 interventions
    a1 = ledger.record_action(
        tenant_id=tenant,
        entity_id="CUST_1001",
        run_id="run_1",
        action_type="RETAINED",
        notes="High-touch concierge call + 10% breakfast credit.",
        monetary_exposure=450.0,
        status="RESOLVED"
    )
    assert a1["entity_id"] == "CUST_1001"
    assert a1["status"] == "RESOLVED"

    a2 = ledger.record_action(
        tenant_id=tenant,
        entity_id="CUST_1002",
        run_id="run_1",
        action_type="DISCOUNT_OFFERED",
        notes="Room upgrade incentive offered.",
        monetary_exposure=300.0,
        status="RESOLVED"
    )

    # Check updated provisional metrics
    mid_roi = ledger.get_roi_summary(tenant)
    assert mid_roi["total_actions_logged"] == 2
    assert mid_roi["total_actions_resolved"] == 2
    assert mid_roi["verified_saved_capital"] == 750.0
    assert mid_roi["roi_multiplier"] > 0

    # 3. Simulate subsequent period fact table
    # CUST_1001 was successfully retained (is_target_event = 0)
    # CUST_1002 unfortunately still canceled (is_target_event = 1)
    # CUST_1003 is a new customer
    new_data = pd.DataFrame({
        "customer_id": ["CUST_1001", "CUST_1002", "CUST_1003"],
        "is_canceled": [0, 1, 0],
        "_is_target_event": [0, 1, 0],
        "adr": [450.0, 300.0, 200.0]
    })

    recon_res = ledger.reconcile_saved_capital(
        tenant_id=tenant,
        new_fact_df=new_data,
        id_col="customer_id",
        target_col="is_canceled",
        cost_col="adr",
        currency_symbol="$"
    )

    assert recon_res["reconciled_count"] == 2
    assert recon_res["verified_retained_count"] == 1
    assert recon_res["verified_saved_capital"] == 450.0
    assert recon_res["retention_success_rate_pct"] == 50.0

    # Final ROI summary reflects audited physical verification
    final_roi = ledger.get_roi_summary(tenant)
    assert final_roi["verified_saved_capital"] == 450.0
    assert final_roi["verified_averted_events"] == 1


def test_historical_drift_radar_analysis(temp_dir):
    """Verifies baseline registration and period-over-period drift detection."""
    out_dir = temp_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_v1 = {
        "target_outcome": {
            "column_name": "is_canceled",
            "total_adverse_events": 120,
            "adverse_event_rate_pct": 24.0
        },
        "financial_exposure": {
            "cost_column": "adr",
            "currency_unit": "$",
            "total_adverse_capital_drag": 18000.0
        },
        "governance": {
            "audited_fact_records": 500
        }
    }

    drift_res = analyze_historical_drift(
        current_out_dir=out_dir,
        tenant_id="tenant_alpha",
        current_manifest=manifest_v1,
        current_plain_summary="Key bottleneck is Lead Time > 30 days."
    )

    assert drift_res["has_historical_comparison"] is False
    assert drift_res["trajectory"] == "BASELINE"
    assert "historical_drift_summary.json" in [f.name for f in out_dir.iterdir()]
    assert "english" in drift_res["executive_drift_notes"]
    assert "hinglish" in drift_res["executive_drift_notes"]


def test_preview_intent_endpoint(client):
    """Verifies the 1-Second Pre-Flight Intent Handshake API."""
    csv_content = (
        "booking_id,is_canceled,adr,lead_time,market_segment\n"
        "B001,0,120.5,14,Online TA\n"
        "B002,1,150.0,45,Offline TA\n"
        "B003,0,95.0,2,Direct\n"
        "B004,1,210.0,120,Corporate\n"
        "B005,0,110.0,7,Direct\n"
    )
    files = {"file": ("hotel_sample.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/v1/preview-intent", files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["sample_rows_count"] == 5
    assert "booking_id" in data["columns"]

    goal = data["detected_goal"]
    assert goal["target_col"] == "is_canceled"
    assert goal["cost_col"] == "adr"
    assert goal["unit_symbol"] == "$"
    assert "cancellations" in goal["business_question_en"].lower() or "is_canceled" in goal["business_question_en"].lower()
    assert len(data["preview_rows"]) == 5


def test_worklist_and_roi_api_endpoints(client):
    """Verifies FastAPI endpoints for logging frontline actions and querying ROI."""
    tenant = "api_test_tenant"

    # 1. Log an action
    payload = {
        "tenant_id": tenant,
        "entity_id": "FLIGHT_UA452",
        "run_id": "run_test_01",
        "action_type": "ROOT_CAUSE_FIXED",
        "notes": "Turnaround ground crew re-assigned to gate 14.",
        "monetary_exposure": 1250.0,
        "status": "RESOLVED"
    }
    res_act = client.post("/api/v1/worklist/action", json=payload)
    assert res_act.status_code == 200
    act_data = res_act.json()
    assert act_data["status"] == "success"
    assert act_data["action"]["entity_id"] == "FLIGHT_UA452"
    assert act_data["roi_summary"]["verified_saved_capital"] == 1250.0

    # 2. Get ROI summary
    res_roi = client.get(f"/api/v1/roi-summary/{tenant}")
    assert res_roi.status_code == 200
    roi_data = res_roi.json()
    assert roi_data["total_actions_resolved"] == 1
    assert roi_data["verified_saved_capital"] == 1250.0

    # 3. List actions
    res_list = client.get(f"/api/v1/worklist/actions/{tenant}")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data) >= 1
    assert list_data[0]["entity_id"] == "FLIGHT_UA452"


def test_web_portal_route(client):
    """Verifies that GET / serves the bespoke Vanilla CSS SaaS web portal with zero alert() popups."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text
    assert "DataX-Ray" in html
    assert "PRE-FLIGHT SCHEMA &amp; INTENT HANDSHAKE" in html
    assert "loadCertifiedBenchmark" in html
    # Quality gates from web-app-development skill audit:
    assert "window.alert(" not in html
    assert "alert(" not in html
    assert "cdn.tailwindcss.com" not in html
    assert "bg-purple-" not in html


def test_certified_benchmarks_and_executive_pulse(client):
    """Verifies 1-click benchmark playground endpoints and structured executive_pulse extraction."""
    res_list = client.get("/api/v1/benchmarks")
    assert res_list.status_code == 200
    b_list = res_list.json()
    assert b_list["status"] == "success"
    bench_ids = [b["id"] for b in b_list["benchmarks"]]
    assert "hotel_booking_cancellation" in bench_ids
    assert "supermarket_retail_operations" in bench_ids

    # Load hotel_booking_cancellation and verify exact physical numbers & pulse structure
    res_hotel = client.get("/api/v1/benchmarks/hotel_booking_cancellation")
    assert res_hotel.status_code == 200
    payload = res_hotel.json()
    assert payload["status"] == "success"
    assert payload["run_id"] == "hotel_booking_cancellation"

    pulse = payload["executive_pulse"]
    assert pulse["total_records"] == 119390
    assert pulse["total_adverse_events"] == 44224
    assert abs(pulse["overall_adverse_rate_pct"] - 37.04) < 0.1
    assert abs(pulse["total_capital_drag"] - 4641942.67) < 1.0
    assert pulse["moat"]["headline"] != ""
    assert pulse["bottleneck"]["headline"] != ""
    assert pulse["red_line"]["headline"] != ""
    assert len(pulse["pathways"]) >= 1

    # Verify bilingual briefs and worklist preview
    assert len(payload["english_summary_markdown"]) > 100
    assert len(payload["hinglish_summary_markdown"]) > 100
    assert len(payload["worklist_preview"]) > 0
    assert payload["worklist_meta"]["primary_id_column"] != ""


def test_conversational_qa_endpoint_and_nan_safety(client):
    """Verifies /api/v1/ask returns grounded markdown, plain_summary alias, and clean JSON rows."""
    res = client.post(
        "/api/v1/ask",
        json={
            "output_dir": "kaggle_benchmarks/supermarket_retail_operations/output",
            "question": "What are the top highest risk segments?",
            "language": "en",
            "use_llm": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["answer_markdown"]) > 20
    assert data["plain_summary"] == data["answer_markdown"]
    assert data["answer"] == data["answer_markdown"]
    assert isinstance(data["columns"], list)
    assert isinstance(data["data"], list)
    assert "SELECT" in data["sql_executed"].upper()


def test_cohort_breakdowns_extracted_in_executive_pulse(client):
    """Verifies Section 4 & Section 5 cohort risk breakdowns are parsed into executive_pulse."""
    res = client.get("/api/v1/benchmarks/hotel_booking_cancellation")
    assert res.status_code == 200
    pulse = res.json()["executive_pulse"]
    breakdowns = pulse.get("cohort_breakdowns", [])
    assert len(breakdowns) >= 2
    first_dim = breakdowns[0]
    assert first_dim["dimension_label"] != ""
    assert len(first_dim["rows"]) >= 2
    first_row = first_dim["rows"][0]
    assert "segment" in first_row
    assert "adverse_rate_pct" in first_row
    assert "total_liability" in first_row


def test_morning_munim_ji_digest_and_ssrf_guard(client):
    """Verifies Morning Munim-Ji Executive Digest generation (English + Hinglish + Slack blocks) and SSRF block."""
    res = client.get("/api/v1/digest/hotel_booking_cancellation?tenant_id=taj_hotels_mumbai")
    assert res.status_code == 200
    digest = res.json()
    assert digest["status"] == "success"
    assert "DataX-Ray Morning Executive Pulse" in digest["whatsapp_english"]
    assert "DataX-Ray Morning Munim-Ji Brief" in digest["whatsapp_hinglish"]
    assert "Sabse Bada Bottleneck" in digest["whatsapp_hinglish"]
    assert "blocks" in digest["slack_payload"]
    assert len(digest["top_priority_entities"]) == 3

    # Verify SSRF protection blocks localhost webhook URLs
    res_ssrf = client.post(
        "/api/v1/digest/dispatch",
        json={
            "run_id": "hotel_booking_cancellation",
            "tenant_id": "taj_hotels_mumbai",
            "language": "hi",
            "webhook_url": "http://127.0.0.1:8080/internal_admin",
        },
    )
    assert res_ssrf.status_code == 400


def test_printable_boardroom_audit_certificate(client):
    """Verifies 1-Click Printable Boardroom Audit Dossier & Cryptographic SHA-256 Certificate."""
    res = client.get("/api/v1/report/hotel_booking_cancellation/printable")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text
    assert "@media print" in html
    assert "SHA-256:" in html
    assert "100.0% DETERMINISTIC DUCKDB SQL AUDIT" in html
    assert "Print / Save as Official PDF" in html


def test_custom_target_and_cost_override_wiring():
    """Verifies cost_override='__NONE__' forces operational frequency mode and region_profile='IN' sets ₹."""
    df = pd.DataFrame({
        "order_id": [f"ORD_{i}" for i in range(50)],
        "is_rto": [1 if i % 4 == 0 else 0 for i in range(50)],
        "order_amount": [1200.0 + i * 10 for i in range(50)],
    })

    # 1. With region_profile='IN', currency should be ₹
    spec_in = resolve_canonical_target_and_cost(
        df=df,
        blueprint={"target_override": "is_rto", "cost_override": "order_amount", "region_profile": "IN"},
    )
    assert spec_in["target_col"] == "is_rto"
    assert spec_in["cost_col"] == "order_amount"
    assert spec_in["is_financial"] is True
    assert spec_in["unit_symbol"] == "₹"

    # 2. With cost_override='__NONE__', should force operational frequency mode
    spec_none = resolve_canonical_target_and_cost(
        df=df,
        blueprint={"target_override": "is_rto", "cost_override": "__NONE__", "region_profile": "IN"},
    )
    assert spec_none["target_col"] == "is_rto"
    assert spec_none["cost_col"] is None
    assert spec_none["is_financial"] is False


def test_live_erp_connectors_catalog_and_ingest(client):
    """Verifies GET /api/v1/connectors and POST /api/v1/connectors/ingest end-to-end."""
    res_cat = client.get("/api/v1/connectors")
    assert res_cat.status_code == 200
    cat_data = res_cat.json()
    assert cat_data["status"] == "success"
    conn_ids = [c["id"] for c in cat_data["connectors"]]
    assert "shopify_orders_live" in conn_ids
    assert "tally_prime_ledger_in" in conn_ids

    # Block SSRF on data_url
    res_bad_url = client.post(
        "/api/v1/connectors/ingest",
        json={"data_url": "http://169.254.169.254/latest/meta-data/", "tenant_id": "test"},
    )
    assert res_bad_url.status_code == 400

    # Ingest live connector preset and verify full 7-stage audit with ₹ INR
    res_ingest = client.post(
        "/api/v1/connectors/ingest",
        json={
            "connector_id": "shopify_orders_live",
            "tenant_id": "d2c_brand_india",
            "region_profile": "IN",
        },
    )
    assert res_ingest.status_code == 200
    payload = res_ingest.json()
    try:
        assert payload["status"] == "success"
        assert payload["connector_meta"]["connector_id"] == "shopify_orders_live"
        pulse = payload["executive_pulse"]
        assert pulse["total_records"] == 400
        assert pulse["unit_symbol"] == "₹"
        assert pulse["total_capital_drag"] > 0
        assert len(pulse["cohort_breakdowns"]) >= 1
    finally:
        # Clean up temporary connector run directory
        run_id = payload.get("run_id", "")
        if run_id.startswith("conn_"):
            shutil.rmtree(Path("runs/uploads") / run_id, ignore_errors=True)

