"""
Phase A Verification Suite:
1. Stage 6 Power BI TMDL & Semantic Metrics Manifest dynamic global currency formatting (₹, €, ¥).
2. Stripe HMAC-SHA256 webhook verification (valid signature, invalid signature, replay attack, idempotency, cancellation).
3. Razorpay HMAC-SHA256 webhook verification (valid signature, tampered body, cancellation downgrade).
4. FastAPI Billing Endpoints & Quota Gate (HTTP 402 Payment Required on Free limit -> instant unblock on webhook upgrade).
5. Production Deployment Kit presence & validity (docker-compose.prod.yml, Caddyfile, .env.production.example, runbook).
"""
import hashlib
import hmac
import json
import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine.billing_manager import (
    TenantBillingManager,
    verify_stripe_webhook_signature,
    verify_razorpay_webhook_signature,
)
from autonomous_engine.stage6_semantic_viz_synthesizer import (
    generate_tmdl_semantic_model,
    generate_semantic_metrics_manifest,
)
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
from autonomous_engine import api_server


def test_stage6_tmdl_and_manifest_dynamic_currency_formatting(tmp_path: Path):
    for col_name, region_prof, expected_sym, expected_fmt in [
        ("invoiced_amount_inr", "IN", "₹", "₹#,0.00"),
        ("mrr_eur", "EU", "€", "€#,0.00"),
        ("importe_jpy", "JP", "¥", "¥#,0"),
    ]:
        out_dir = tmp_path / region_prof
        out_dir.mkdir(parents=True)
        df = pd.DataFrame({
            "order_id": [f"O-{i}" for i in range(40)],
            "region": ["North", "South"] * 20,
            col_name: [1500.0 + i * 25.0 for i in range(40)],
            "order_status": ["Returned" if i % 4 == 0 else "Delivered" for i in range(40)],
        })
        canon = resolve_canonical_target_and_cost(df, region_profile=region_prof)
        assert canon["unit_symbol"] == expected_sym

        tmdl_dir = generate_tmdl_semantic_model(
            out_dir, df, canon["target_col"], canon["cost_col"], "region", [], canon
        )
        fact_tmdl = (tmdl_dir / "tables" / "bi_ready_fact.tmdl").read_text(encoding="utf-8")
        assert f"formatString: {expected_fmt}" in fact_tmdl
        assert f"Total Portfolio Volume ({expected_sym})" in fact_tmdl

        manifest = generate_semantic_metrics_manifest(
            out_dir, df, canon["target_col"], canon["cost_col"], "region", None, canon
        )
        fin_metrics = [m for m in manifest["certified_metrics"] if m["id"] in ("m_adverse_capital_drag", "m_portfolio_volume")]
        assert len(fin_metrics) == 2
        assert all(m["format"] == expected_fmt for m in fin_metrics)
        assert all(expected_sym in m["name"] for m in fin_metrics)


def test_stripe_and_razorpay_hmac_webhook_security_and_idempotency(tmp_path: Path, monkeypatch):
    mgr = TenantBillingManager(state_dir=tmp_path)
    stripe_sec = "whsec_test_stripe_secret_999"
    rzp_sec = "rzp_test_webhook_secret_888"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", stripe_sec)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", rzp_sec)

    # 1. Valid Stripe checkout.session.completed upgrades tenant -> pro
    ev_stripe = {
        "id": "evt_stripe_001",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "status": "complete",
                "customer": "cus_abc",
                "subscription": "sub_xyz",
                "client_reference_id": "acme_global",
                "metadata": {"tenant_id": "acme_global", "plan_id": "pro"},
            }
        },
    }
    raw_s = json.dumps(ev_stripe).encode("utf-8")
    now_ts = int(time.time())
    sig_v1 = hmac.new(stripe_sec.encode("utf-8"), f"{now_ts}.".encode("utf-8") + raw_s, hashlib.sha256).hexdigest()
    sig_hdr = f"t={now_ts},v1={sig_v1}"

    # Tampered signature rejected
    ok_bad, _ = verify_stripe_webhook_signature(raw_s, f"t={now_ts},v1=deadbeef", stripe_sec)
    assert not ok_bad
    # Stale replay timestamp (> 300s) rejected
    old_ts = now_ts - 600
    old_sig = hmac.new(stripe_sec.encode("utf-8"), f"{old_ts}.".encode("utf-8") + raw_s, hashlib.sha256).hexdigest()
    ok_old, _ = verify_stripe_webhook_signature(raw_s, f"t={old_ts},v1={old_sig}", stripe_sec)
    assert not ok_old

    # Process valid Stripe webhook -> Pro active
    res1 = mgr.handle_stripe_webhook(raw_s, sig_hdr)
    assert res1["status"] == "processed"
    assert mgr.get_tenant_billing_status("acme_global")["plan_id"] == "pro"

    # Duplicate event_id must be idempotently ignored
    res_dup = mgr.handle_stripe_webhook(raw_s, sig_hdr)
    assert res_dup["status"] == "duplicate_ignored"

    # 2. Valid Razorpay subscription.activated upgrades India tenant -> starter
    ev_rzp = {
        "id": "evt_rzp_001",
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_rzp_777",
                    "customer_id": "cust_in_1",
                    "notes": {"tenant_id": "agarwal_fmcg", "plan_id": "starter"},
                }
            }
        },
    }
    raw_r = json.dumps(ev_rzp).encode("utf-8")
    rzp_sig = hmac.new(rzp_sec.encode("utf-8"), raw_r, hashlib.sha256).hexdigest()
    ok_rzp_bad, _ = verify_razorpay_webhook_signature(raw_r + b" ", rzp_sig, rzp_sec)
    assert not ok_rzp_bad

    res_r = mgr.handle_razorpay_webhook(raw_r, rzp_sig)
    assert res_r["status"] == "processed"
    assert mgr.get_tenant_billing_status("agarwal_fmcg")["plan_id"] == "starter"

    # 3. Razorpay subscription.cancelled cleanly downgrades to free
    ev_cancel = {
        "id": "evt_rzp_002",
        "event": "subscription.cancelled",
        "payload": {"subscription": {"entity": {"id": "sub_rzp_777", "notes": {"tenant_id": "agarwal_fmcg"}}}},
    }
    raw_c = json.dumps(ev_cancel).encode("utf-8")
    sig_c = hmac.new(rzp_sec.encode("utf-8"), raw_c, hashlib.sha256).hexdigest()
    mgr.handle_razorpay_webhook(raw_c, sig_c)
    assert mgr.get_tenant_billing_status("agarwal_fmcg")["plan_id"] == "free"


def test_api_billing_quota_402_and_webhook_upgrade_flow(tmp_path: Path, monkeypatch):
    isolated_bm = TenantBillingManager(state_dir=tmp_path)
    monkeypatch.setattr(api_server, "billing_manager", isolated_bm)
    monkeypatch.setenv("DATAXRAY_ENFORCE_BILLING_QUOTAS", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_live_test_gate")

    client = TestClient(api_server.app)

    # 1. Public plans catalog accessible without auth
    r_plans = client.get("/api/v1/billing/plans")
    assert r_plans.status_code == 200
    plan_ids = [p["plan_id"] for p in r_plans.json()["plans"]]
    assert plan_ids == ["free", "starter", "pro", "enterprise"]

    # 2. Register isolated tenant
    ts = int(time.time() * 1000)
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"bill_{ts}@corp.io", "password": "StrongPassword!123", "workspace_name": f"BillCorp_{ts}"},
    )
    assert r_reg.status_code == 201
    tok = r_reg.json()["access_token"]
    tid = r_reg.json()["user"]["tenant_id"]
    hdr = {"Authorization": f"Bearer {tok}"}

    # Simulate 3 runs already used on Free Trial (limit=3)
    for _ in range(3):
        isolated_bm.record_run_usage(tid, rows_audited=500)

    # 3. 4th run must return HTTP 402 Payment Required!
    csv_bytes = b"order_id,region,amount,status\nO-1,North,100,Delivered\nO-2,South,200,Returned\n"
    r_blocked = client.post(
        "/api/v1/analyze-upload",
        files={"file": ("quota_test.csv", csv_bytes, "text/csv")},
        headers=hdr,
    )
    assert r_blocked.status_code == 402
    assert "Monthly run limit reached" in r_blocked.text

    # 4. Checkout without live Stripe key returns honest configuration_required (never fake payment)
    r_chk = client.post("/api/v1/billing/checkout", json={"plan_id": "pro", "provider": "stripe"}, headers=hdr)
    assert r_chk.status_code == 200
    assert r_chk.json()["status"] in ("configuration_required", "checkout_created")

    # 5. Unsigned webhook rejected 401
    r_bad_wh = client.post("/api/v1/billing/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "t=1,v1=bad"})
    assert r_bad_wh.status_code == 401

    # 6. Signed Stripe webhook upgrades tenant to Pro -> status reflects 150 runs limit!
    ev = {
        "id": f"evt_api_{ts}",
        "type": "checkout.session.completed",
        "data": {"object": {"status": "complete", "client_reference_id": tid, "metadata": {"tenant_id": tid, "plan_id": "pro"}}},
    }
    raw_ev = json.dumps(ev).encode("utf-8")
    now_t = int(time.time())
    sig = hmac.new(b"whsec_live_test_gate", f"{now_t}.".encode("utf-8") + raw_ev, hashlib.sha256).hexdigest()
    r_ok_wh = client.post("/api/v1/billing/webhooks/stripe", content=raw_ev, headers={"Stripe-Signature": f"t={now_t},v1={sig}"})
    assert r_ok_wh.status_code == 200

    r_st = client.get("/api/v1/billing/status", headers=hdr)
    assert r_st.status_code == 200
    assert r_st.json()["plan_id"] == "pro"
    assert r_st.json()["usage"]["runs_limit"] == 150
    assert r_st.json()["usage"]["runs_remaining"] == 147


def test_production_deployment_kit_files_present_and_hardened():
    root = Path(__file__).resolve().parent.parent
    compose = (root / "docker-compose.prod.yml").read_text(encoding="utf-8")
    caddy = (root / "Caddyfile").read_text(encoding="utf-8")
    env_ex = (root / ".env.production.example").read_text(encoding="utf-8")
    runbook = (root / "deploy" / "DEPLOYMENT_RUNBOOK.md").read_text(encoding="utf-8")

    assert "DATAXRAY_REQUIRE_AUTH=true" in compose
    assert "DATAXRAY_ENFORCE_BILLING_QUOTAS=true" in compose
    assert "Strict-Transport-Security" in caddy
    assert "STRIPE_WEBHOOK_SECRET" in env_ex and "RAZORPAY_WEBHOOK_SECRET" in env_ex
    assert "/api/v1/schedules/run-due" in runbook
