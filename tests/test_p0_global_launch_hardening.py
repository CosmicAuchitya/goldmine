"""
=============================================================================
P0 GLOBAL LAUNCH SECURITY & STABILITY HARDENING TEST SUITE
=============================================================================
Verifies all 6 P0 production blockers are permanently closed:
1. Multi-Tenant JWT Auth & Strict Cross-Tenant IDOR Isolation
2. DNS-Resolving & Redirect-Hop SSRF Defense (Cloud Metadata Protection)
3. Zip-Bomb OOM Cap + EU Semicolon CSV Preview Sniffing
4. SQLite WAL Persistence for JobManager & ActionLedger + Complete GDPR Purge
5. Deterministic Cloud Execution Guard & Hardened Python AST Gate
6. OWASP Security Headers, Rate Limiting, and Trimmed Docker Context
=============================================================================
"""

import io
import socket
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from autonomous_engine.api_server import (
    app,
    JobManager,
    JobRecord,
    _resolve_safe_pipeline_mode,
    _RATE_BUCKETS,
)
from autonomous_engine.action_ledger import ActionLedger
from autonomous_engine.common_utils import validate_etl_ast_security
from autonomous_engine.live_connectors import validate_safe_external_url, _SafeRedirectHandler


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_p0_multitenant_auth_and_cross_tenant_idor_isolation(monkeypatch, client):
    """Proves Tenant B cannot view, query, download, or GDPR-purge Tenant A's private runs."""
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DATAXRAY_JWT_SECRET", "p0_test_super_secret_key_for_jwt_signing_123456")

    import uuid
    suffix = uuid.uuid4().hex[:8]
    reg_a = client.post(
        "/api/v1/auth/register",
        json={"email": f"alice_{suffix}@acme.com", "password": "StrongPassword!123", "workspace_name": f"Acme_{suffix}"},
    )
    assert reg_a.status_code == 201, reg_a.text
    token_a = reg_a.json()["access_token"]
    tenant_a = reg_a.json()["user"]["tenant_id"]

    reg_b = client.post(
        "/api/v1/auth/register",
        json={"email": f"bob_{suffix}@rival.com", "password": "StrongPassword!456", "workspace_name": f"Rival_{suffix}"},
    )
    assert reg_b.status_code == 201, reg_b.text
    token_b = reg_b.json()["access_token"]
    tenant_b = reg_b.json()["user"]["tenant_id"]
    assert tenant_a != tenant_b

    hdr_a = {"Authorization": f"Bearer {token_a}"}
    hdr_b = {"Authorization": f"Bearer {token_b}"}

    # Verify /auth/me works for Tenant A
    me_a = client.get("/api/v1/auth/me", headers=hdr_a)
    assert me_a.status_code == 200
    assert me_a.json()["user"]["tenant_id"] == tenant_a

    # Tenant A ingests a private connector run
    ingest_a = client.post(
        "/api/v1/connectors/ingest",
        json={"connector_id": "shopify_orders_live", "tenant_id": "spoofed_other_tenant", "region_profile": "IN"},
        headers=hdr_a,
    )
    assert ingest_a.status_code == 200, ingest_a.text
    payload_a = ingest_a.json()
    run_id_a = payload_a["run_id"]
    out_dir_a = payload_a["output_dir"]
    # Server MUST ignore spoofed_other_tenant and force Tenant A's authenticated workspace!
    assert payload_a["tenant_id"] == tenant_a

    # Tenant A logs an action in the ledger
    act_a = client.post(
        "/api/v1/worklist/action",
        json={
            "tenant_id": tenant_a,
            "entity_id": "SHP-10001",
            "run_id": run_id_a,
            "monetary_exposure": 5000.0,
            "status": "RESOLVED",
        },
        headers=hdr_a,
    )
    assert act_a.status_code == 200

    # 1. Unauthenticated caller MUST be blocked (401) from private dashboard & printable report
    assert client.get(f"/api/v1/dashboard/{run_id_a}").status_code == 401
    assert client.get(f"/api/v1/report/{run_id_a}/printable").status_code == 401
    # But public certified demo benchmark dashboard remains accessible
    assert client.get("/api/v1/dashboard/hotel_booking_cancellation").status_code == 200

    # 2. Tenant B MUST receive 403 Forbidden across ALL Tenant A resources (zero IDOR!)
    assert client.get(f"/api/v1/dashboard/{run_id_a}", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/report/{run_id_a}/printable", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/runs/{run_id_a}", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/download/{run_id_a}/PLAIN_BUSINESS_SUMMARY.md", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/digest/{run_id_a}", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/audit-proof/{run_id_a}", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/workspaces/{tenant_a}/runs", headers=hdr_b).status_code == 403
    assert client.get(f"/api/v1/roi-summary/{tenant_a}", headers=hdr_b).status_code == 403
    assert client.post(
        "/api/v1/ask",
        json={"output_dir": out_dir_a, "question": "Show total rows", "use_llm": False},
        headers=hdr_b,
    ).status_code == 403
    assert client.delete(f"/api/v1/workspaces/{run_id_a}/purge", headers=hdr_b).status_code == 403

    # 3. Tenant A CAN access their own private dashboard, Q&A, and purge (including ActionLedger erasure!)
    assert client.get(f"/api/v1/dashboard/{run_id_a}", headers=hdr_a).status_code == 200
    assert client.post(
        "/api/v1/ask",
        json={"output_dir": out_dir_a, "question": "Show total rows", "use_llm": False},
        headers=hdr_a,
    ).status_code == 200

    purge_a = client.delete(f"/api/v1/workspaces/{run_id_a}/purge", headers=hdr_a)
    assert purge_a.status_code == 200
    assert purge_a.json()["purged_ledger_actions"] >= 1
    # Verify ledger is now empty for Tenant A
    acts_after = client.get(f"/api/v1/worklist/actions/{tenant_a}", headers=hdr_a)
    assert acts_after.status_code == 200
    assert len(acts_after.json()) == 0


def test_p0_dns_and_redirect_ssrf_defenses():
    """Proves DNS-resolved private/cloud-metadata IPs, embedded creds, and 302 redirects are blocked."""
    # Embedded credentials blocked
    with pytest.raises(ValueError, match="SSRF Security Gate"):
        validate_safe_external_url("https://user:secret@example.com/data.csv")

    # IPv4-mapped IPv6 loopback blocked
    with pytest.raises(ValueError, match="SSRF Security Gate"):
        validate_safe_external_url("http://[::ffff:127.0.0.1]/admin")

    # Domain resolving via DNS to AWS cloud metadata IP (169.254.169.254) MUST be blocked
    fake_metadata_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
    with patch("socket.getaddrinfo", return_value=fake_metadata_dns):
        with pytest.raises(ValueError, match="SSRF Security Gate"):
            validate_safe_external_url("http://evil-rebind.example.com/latest/meta-data/")

    # Domain resolving via DNS to RFC1918 internal IP (10.0.0.5) MUST be blocked
    fake_internal_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]
    with patch("socket.getaddrinfo", return_value=fake_internal_dns):
        with pytest.raises(ValueError, match="SSRF Security Gate"):
            validate_safe_external_url("https://internal-db.example.com/export.csv")

    # Redirect hop to AWS metadata MUST be blocked by _SafeRedirectHandler
    import urllib.request
    handler = _SafeRedirectHandler()
    orig_req = urllib.request.Request("https://public.example.com/sheet.csv")
    with pytest.raises(ValueError, match="SSRF Security Gate"):
        handler.redirect_request(orig_req, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data/")


def test_p0_zip_bomb_oom_cap_and_eu_semicolon_csv_preview(client):
    """Proves zip bombs >25MB uncompressed are rejected (413) and EU semicolon CSVs parse cleanly."""
    # 1. Construct a tiny compressed ZIP (~30 KB) whose inner file expands to 30 MB
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.csv", b"a,b\n" + (b"0,1\n" * (8 * 1024 * 1024)))
    buf.seek(0)

    res_bomb = client.post(
        "/api/v1/preview-intent",
        files={"file": ("bomb.zip", buf, "application/zip")},
        data={"region_profile": "US"},
    )
    assert res_bomb.status_code == 413
    assert "zip-bomb" in res_bomb.text.lower()

    # 2. Construct a European semicolon-delimited CSV
    eu_csv = "order_id;payment_method;order_amount;is_canceled\n1;SEPA;150.50;0\n2;Card;220.00;1\n3;SEPA;95.00;0\n4;Invoice;410.00;1\n"
    res_eu = client.post(
        "/api/v1/preview-intent",
        files={"file": ("berlin_orders.csv", io.BytesIO(eu_csv.encode("utf-8")), "text/csv")},
        data={"region_profile": "EU"},
    )
    assert res_eu.status_code == 200, res_eu.text
    eu_data = res_eu.json()
    assert eu_data["columns_count"] == 4
    assert "is_canceled" in eu_data["columns"]


def test_p0_sqlite_persistence_job_manager_and_action_ledger(tmp_path):
    """Proves JobManager and ActionLedger persist across restarts in ACID SQLite WAL mode."""
    # 1. JobManager restart survival
    jm = JobManager(max_workers=1, state_dir=tmp_path / "state")
    jr = JobRecord(
        job_id="job_persist_test_001",
        tenant_id="acme_global",
        run_root=tmp_path / "run_001",
        mode="templated",
        region_profile="EU",
        language="en",
    )
    jr.status = "COMPLETED"
    jr.progress_pct = 100
    jm.register_job(jr)

    # Simulate container restart by creating a fresh JobManager reading the same SQLite DB
    jm_restarted = JobManager(max_workers=1, state_dir=tmp_path / "state")
    recovered = jm_restarted.get_job("job_persist_test_001")
    assert recovered is not None
    assert recovered.tenant_id == "acme_global"
    assert recovered.status == "COMPLETED"
    assert recovered.progress_pct == 100

    # 2. ActionLedger SQLite persistence + GDPR run purge
    al = ActionLedger(storage_dir=tmp_path / "ledgers")
    al.record_action(
        tenant_id="acme_global",
        run_id="job_persist_test_001",
        entity_id="ORD-99",
        monetary_exposure=1200.0,
        status="RESOLVED",
        currency_symbol="€",
    )
    al_restarted = ActionLedger(storage_dir=tmp_path / "ledgers")
    assert al_restarted.get_roi_summary("acme_global")["total_actions_logged"] == 1
    assert al_restarted.get_roi_summary("acme_global")["verified_saved_capital"] == 1200.0

    deleted = al_restarted.purge_run_actions("job_persist_test_001", tenant_id="acme_global")
    assert deleted == 1
    assert al_restarted.get_roi_summary("acme_global")["total_actions_logged"] == 0


def test_p0_sandbox_mode_ast_headers_ratelimit_and_dockerignore(monkeypatch, client):
    """Proves safe cloud mode default, hardened AST gate, OWASP headers, rate limiting, and trimmed .dockerignore."""
    # 1. Default cloud mode blocks arbitrary AI codegen unless DATAXRAY_ALLOW_AI_CODEGEN=true
    monkeypatch.delenv("DATAXRAY_ALLOW_AI_CODEGEN", raising=False)
    assert _resolve_safe_pipeline_mode("ai") == "templated"
    monkeypatch.setenv("DATAXRAY_ALLOW_AI_CODEGEN", "true")
    assert _resolve_safe_pipeline_mode("ai") == "ai"

    # 2. AST Gate blocks getattr/globals escape vectors
    viols = validate_etl_ast_security("import os\ngetattr(os, 'system')('whoami')\n")
    assert any("getattr" in v for v in viols)

    # 3. OWASP Security Headers present
    res_h = client.get("/api/v1/health")
    assert res_h.headers.get("X-Content-Type-Options") == "nosniff"
    assert res_h.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "Referrer-Policy" in res_h.headers

    # 4. Rate Limiter enforces 429 on burst
    _RATE_BUCKETS.clear()
    monkeypatch.setenv("DATAXRAY_RATE_LIMIT_RPM", "3")
    for _ in range(3):
        assert client.get("/api/v1/connectors").status_code == 200
    assert client.get("/api/v1/connectors").status_code == 429
    _RATE_BUCKETS.clear()

    # 5. .dockerignore trims raw Kaggle datasets while preserving demo outputs
    di_text = Path(".dockerignore").read_text(encoding="utf-8")
    assert "kaggle_benchmarks/*" in di_text
    assert "!kaggle_benchmarks/hotel_booking_cancellation/output/" in di_text
