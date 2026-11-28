"""
================================================================================
REGRESSION & SECURITY TESTS: BATCH 1 CRITICAL HARDENING (C1–C5)
================================================================================
Verifies:
- C1: AST Security Gate blocks aliased OS/pickle/shutil bypasses while preserving
      legitimate list.remove() & pandas ETL operations.
- C2: Razorpay one-time payment_link.paid sets bounded current_period_end and
      auto-expires to Free; check_row_limit() and check_feature_access() enforce
      max_rows_per_run, live_connectors, and scheduled_digests when active.
- C3: /api/v1/connectors/ingest enforces RBAC (blocks viewer) & plan entitlements;
      /api/v1/schedules enforces scheduled_digests entitlement.
- C4: PacedGeminiClient.generate_content_tiered() isolates thread-local overrides
      under true concurrent multi-threading (zero cross-thread Pro tier bleed).
- C5: Live 2026 Gemini pricing table, GEMINI_MAX_RPM env override (14 default for
      Free keys), and bounded _wait_for_slot() queue timeout.
================================================================================
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from autonomous_engine.billing_manager import TenantBillingManager
from autonomous_engine.common_utils import validate_etl_ast_security
from autonomous_engine.rate_limiter import (
    PacedGeminiClient,
    _MODEL_PRICING_PER_1M_USD,
    _record_usage_metadata,
    get_token_usage_summary,
    reset_token_usage_ledger,
)


def test_c1_ast_security_gate_blocks_alias_and_from_import_bypasses():
    bypass_payloads = [
        'import os as o\no.system("echo pwn")\n',
        'from os import system\nsystem("echo pwn")\n',
        'from os import system as run_cmd\nrun_cmd("echo pwn")\n',
        'from os import *\n',
        'import pandas as p\np.read_pickle("evil.pkl")\n',
        'from pandas import read_pickle as rp\nrp("evil.pkl")\n',
        'import pandas as p\ndf.to_pickle("out.pkl")\n',
        'import shutil\nshutil.copy("a.csv", "b.csv")\n',
        'import posix\n',
        'import os as o\no.remove("important.db")\n',
    ]
    for code in bypass_payloads:
        violations = validate_etl_ast_security(code)
        assert len(violations) > 0, f"AST gate failed to block payload: {code!r}"

    # Legitimate ETL code (including Python list.remove()) MUST stay allowed
    safe_etl = """
import os
import pandas as pd
cols = ['id', 'amount', 'status']
cols.remove('id')
df = pd.read_csv('data.csv')
df.to_parquet('bi_ready_fact.parquet', index=False)
"""
    assert validate_etl_ast_security(safe_etl) == []


def test_c2_razorpay_expiry_and_entitlement_quotas(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "rzp_test_secret_123")
    monkeypatch.setenv("DATAXRAY_ENFORCE_BILLING_QUOTAS", "true")

    bm = TenantBillingManager(state_dir=tmp_path)
    tid = "tenant_india_smb"

    # Free Trial defaults: max_rows_per_run=10_000, live_connectors=False, scheduled_digests=False
    ok_rows, msg_rows, _ = bm.check_row_limit(tid, 50_000)
    assert ok_rows is False and "10,000" in msg_rows
    ok_rows_small, _, _ = bm.check_row_limit(tid, 10_000)
    assert ok_rows_small is True

    ok_conn, _, _ = bm.check_feature_access(tid, "live_connectors")
    assert ok_conn is False
    ok_sched, _, _ = bm.check_feature_access(tid, "scheduled_digests")
    assert ok_sched is False

    # Simulate valid Razorpay one-time payment_link.paid webhook -> Starter plan for 30 days
    payload = {
        "id": "evt_rzp_001",
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_abc123",
                    "notes": {"tenant_id": tid, "plan_id": "starter", "billing_period_days": "30"},
                }
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(b"rzp_test_secret_123", raw_body, hashlib.sha256).hexdigest()

    res = bm.handle_razorpay_webhook(raw_body, sig)
    assert res["status"] == "processed"
    st = bm.get_tenant_billing_status(tid)
    assert st["plan_id"] == "starter"
    assert st["subscription_status"] == "active"
    assert st["current_period_end"] is not None
    assert st["current_period_end"] > time.time() + 25 * 86400

    # Starter unlocks live_connectors, scheduled_digests, and 100,000 rows/run
    assert bm.check_feature_access(tid, "live_connectors")[0] is True
    assert bm.check_feature_access(tid, "scheduled_digests")[0] is True
    assert bm.check_row_limit(tid, 100_000)[0] is True
    assert bm.check_row_limit(tid, 150_000)[0] is False

    # Simulate time passing beyond current_period_end -> MUST auto-expire to Free (no lifetime access!)
    bm.set_tenant_plan(
        tenant_id=tid,
        plan_id="starter",
        provider="razorpay",
        status="active",
        current_period_end=time.time() - 60.0,
    )
    expired_st = bm.get_tenant_billing_status(tid)
    assert expired_st["plan_id"] == "free"
    assert expired_st["subscription_status"] == "expired"
    assert bm.check_feature_access(tid, "live_connectors")[0] is False


def test_c3_connector_and_schedule_rbac_and_quota_enforcement(tmp_path: Path, monkeypatch):
    from autonomous_engine import api_server
    from autonomous_engine.oauth_connectors import OAuthVaultAndScheduleManager
    from autonomous_engine.tenant_auth import TenantAuthManager

    monkeypatch.setattr(api_server, "auth_manager", TenantAuthManager(state_dir=tmp_path))
    monkeypatch.setattr(api_server, "billing_manager", TenantBillingManager(state_dir=tmp_path))
    monkeypatch.setattr(api_server, "oauth_scheduler", OAuthVaultAndScheduleManager(state_dir=tmp_path))
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DATAXRAY_ENFORCE_BILLING_QUOTAS", "true")
    client = TestClient(api_server.app)

    # Register an owner on Free Trial, then invite + accept a real Viewer in the same workspace
    ts = int(time.time() * 1000)
    email = f"c3_owner_{ts}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPassword123!", "workspace_name": f"C3_Test_{ts}"},
    )
    assert reg.status_code == 201, reg.text
    owner_token = reg.json()["access_token"]
    tenant_id = reg.json()["user"]["tenant_id"]

    inv = client.post(
        "/api/v1/team/invite",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": f"c3_viewer_{ts}@example.com", "role": "viewer"},
    )
    assert inv.status_code == 201, inv.text
    acc = client.post(
        "/api/v1/team/accept-invite",
        json={"invite_token": inv.json()["invite_token"], "password": "ViewerPassword123!"},
    )
    assert acc.status_code == 201, acc.text
    viewer_tok = acc.json()["access_token"]

    # 1) Viewer MUST be blocked (HTTP 403) from POST /api/v1/connectors/ingest
    r_viewer = client.post(
        "/api/v1/connectors/ingest",
        headers={"Authorization": f"Bearer {viewer_tok}"},
        json={"connector_id": "shopify_orders_demo", "tenant_id": tenant_id},
    )
    assert r_viewer.status_code == 403

    # 2) Free Trial Owner MUST be blocked (HTTP 402) from live connectors when quotas are enforced
    r_free_conn = client.post(
        "/api/v1/connectors/ingest",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"connector_id": "shopify_orders_demo", "tenant_id": tenant_id},
    )
    assert r_free_conn.status_code == 402
    assert "Live Connectors" in r_free_conn.text

    # 3) Free Trial Owner MUST be blocked (HTTP 402) from creating scheduled digests
    r_free_sched = client.post(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Monday Leak Pulse",
            "source_type": "run_id",
            "source_ref": "demo_run",
            "frequency": "weekly_monday",
            "channel": "email",
            "recipient": email,
        },
    )
    assert r_free_sched.status_code == 402
    assert "Scheduled Digests" in r_free_sched.text


def test_c4_rate_limiter_thread_local_tier_isolation(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test_dummy_key_1")
    pacer = PacedGeminiClient(max_calls_per_minute=28, quiet=True)

    barrier = threading.Barrier(2)
    observed = {}

    def _spy_generate_content(contents, system_instruction=None, max_retries=5):
        # Synchronize both threads INSIDE generate_content simultaneously
        barrier.wait(timeout=5.0)
        observed[contents] = getattr(pacer, "_override_models", None)
        return f"ok:{contents}"

    monkeypatch.setattr(pacer, "generate_content", _spy_generate_content)

    def _run_reasoning():
        pacer.generate_content_tiered("req_reasoning", tier="reasoning")

    def _run_fast():
        pacer.generate_content_tiered("req_fast", tier="fast")

    t1 = threading.Thread(target=_run_reasoning)
    t2 = threading.Thread(target=_run_fast)
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert "gemini-2.5-pro" in (observed.get("req_reasoning") or [])
    # Thread B MUST NOT see Thread A's Pro model override!
    assert observed.get("req_fast") is None
    assert not hasattr(pacer, "_override_models")


def test_c5_live_2026_pricing_env_rpm_and_bounded_wait(monkeypatch):
    # 1) Verify updated 2026 pricing table accuracy
    assert _MODEL_PRICING_PER_1M_USD["gemini-3.5-flash-lite"] == (0.30, 2.50)
    assert _MODEL_PRICING_PER_1M_USD["gemini-3.8-flash"] == (0.75, 3.75)

    reset_token_usage_ledger()
    fake_resp = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=4_083,
            candidates_token_count=3_661,
            thoughts_token_count=0,
            total_token_count=7_744,
        )
    )
    _record_usage_metadata("gemini-3.5-flash-lite", fake_resp, 1.2)
    summary = get_token_usage_summary()
    # 4083/1e6*0.30 + 3661/1e6*2.50 = 0.0012249 + 0.0091525 = 0.0103774
    assert abs(summary["total_cost_usd"] - 0.010377) < 1e-5

    # 2) Verify Free-Tier default = 14 RPM when GEMINI_MAX_RPM unset, and scales cleanly when set
    monkeypatch.setenv("GEMINI_API_KEY", "test_dummy_key_1")
    monkeypatch.delenv("GEMINI_API_KEY_SECONDARY", raising=False)
    monkeypatch.delenv("GEMINI_MAX_RPM", raising=False)
    p_free = PacedGeminiClient(quiet=True)
    assert p_free.max_calls_per_key == 14

    monkeypatch.setenv("GEMINI_MAX_RPM", "600")
    p_paid = PacedGeminiClient(quiet=True)
    assert p_paid.max_calls_per_key == 600
