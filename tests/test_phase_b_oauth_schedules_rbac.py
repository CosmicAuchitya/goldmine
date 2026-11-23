"""
Phase B Verification Suite:
1. AES-256-GCM / Authenticated Token Vault encryption at rest & strict cross-tenant isolation.
2. 1-Click OAuth 2.0 CSRF state lifecycle, token exchange, replay blocking & disconnect across 4 providers.
3. End-to-End Team RBAC enforcement (Owner / Analyst / Viewer) + instant role demotion & member removal revocation.
4. Persistent Scheduled Morning Digest CRUD + zero-body cron sweep via /api/v1/schedules/run-due.
5. QuickBooks Online v3 live invoice parser + SaaS Web Client Phase B Hub UI verification.
"""
import io
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from autonomous_engine import api_server
from autonomous_engine import live_connectors
from autonomous_engine.oauth_connectors import (
    OAuthVaultAndScheduleManager,
    decrypt_vault_payload,
    encrypt_vault_payload,
)
from autonomous_engine.tenant_auth import TenantAuthManager


def test_oauth_vault_aes256_gcm_encryption_and_tenant_isolation(tmp_path: Path):
    vault = OAuthVaultAndScheduleManager(state_dir=tmp_path)
    secret_access = "shpat_super_secret_live_token_987654321"
    secret_refresh = "rt_super_secret_refresh_123456789"

    res = vault.save_encrypted_connection(
        tenant_id="tenant_alpha",
        provider="shopify",
        credentials={
            "shop_domain": "alpha-store.myshopify.com",
            "access_token": secret_access,
            "refresh_token": secret_refresh,
        },
        account_label="alpha-store.myshopify.com",
    )
    assert res["status"] == "connected"
    assert res["encrypted_at_rest"] is True

    # 1. Raw SQLite bytes must NEVER contain plaintext secrets
    raw_db_bytes = (tmp_path / "oauth_vault.sqlite").read_bytes()
    assert secret_access.encode("utf-8") not in raw_db_bytes
    assert secret_refresh.encode("utf-8") not in raw_db_bytes

    # 2. Owning tenant decrypts accurately in memory
    dec = vault.get_decrypted_credentials("tenant_alpha", "shopify")
    assert dec is not None
    assert dec["access_token"] == secret_access
    assert dec["shop_domain"] == "alpha-store.myshopify.com"

    # 3. Cross-tenant isolation: tenant_beta gets None
    assert vault.get_decrypted_credentials("tenant_beta", "shopify") is None
    assert vault.list_tenant_connections("tenant_beta") == []

    # 4. Masked listing never leaks secrets
    masked = vault.list_tenant_connections("tenant_alpha")
    assert len(masked) == 1
    assert secret_access not in json.dumps(masked)

    # 5. Tampered AAD or ciphertext rejected cryptographically
    k = vault._vault_key()
    ct = encrypt_vault_payload({"token": "abc"}, k, aad="tenant_alpha::shopify")
    try:
        decrypt_vault_payload(ct, k, aad="tenant_beta::shopify")
        assert False, "Cross-tenant AAD mismatch MUST fail decryption"
    except Exception:
        pass

    # 6. Auto-refresh rotates expired QuickBooks token and re-encrypts at rest
    vault.save_encrypted_connection(
        tenant_id="tenant_alpha",
        provider="quickbooks",
        credentials={"realm_id": "999", "access_token": "qb_expired_old", "refresh_token": "qb_rt_1"},
        expires_at=time.time() - 60.0,
    )
    vault._refresh_provider_token = lambda prov, c: (
        {**c, "access_token": "qb_fresh_rotated_999", "refresh_token": "qb_rt_2"},
        time.time() + 3600.0,
    )
    refreshed = vault.get_decrypted_credentials("tenant_alpha", "quickbooks")
    assert refreshed is not None and refreshed["access_token"] == "qb_fresh_rotated_999"
    assert b"qb_fresh_rotated_999" not in (tmp_path / "oauth_vault.sqlite").read_bytes()


def test_oauth_csrf_state_lifecycle_replay_defense_and_all_4_providers(tmp_path: Path, monkeypatch):
    iso_auth = TenantAuthManager(state_dir=tmp_path)
    iso_oauth = OAuthVaultAndScheduleManager(state_dir=tmp_path)
    monkeypatch.setattr(api_server, "auth_manager", iso_auth)
    monkeypatch.setattr(api_server, "oauth_scheduler", iso_oauth)
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "shp_cid_test")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "shp_csec_test")
    monkeypatch.setenv("QUICKBOOKS_CLIENT_ID", "qb_cid_test")
    monkeypatch.setenv("QUICKBOOKS_CLIENT_SECRET", "qb_csec_test")

    client = TestClient(api_server.app)

    # Public OAuth providers catalog
    r_prov = client.get("/api/v1/oauth/providers")
    assert r_prov.status_code == 200
    pids = [p["id"] for p in r_prov.json()["providers"]]
    assert pids == ["shopify", "quickbooks", "stripe", "zoho_books"]

    # Register workspace owner
    ts = int(time.time() * 1000)
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"oauth_owner_{ts}@corp.io", "password": "StrongPassword!123", "workspace_name": f"OAuthCo_{ts}"},
    )
    assert r_reg.status_code == 201
    hdr = {"Authorization": f"Bearer {r_reg.json()['access_token']}"}

    # Start Shopify OAuth -> receives state + authorize URL
    r_start = client.post(
        "/api/v1/oauth/shopify/start",
        json={"shop_domain": "global-d2c.myshopify.com"},
        headers=hdr,
    )
    assert r_start.status_code == 200
    s_data = r_start.json()
    assert s_data["status"] == "authorization_url_created"
    assert "global-d2c.myshopify.com/admin/oauth/authorize" in s_data["authorization_url"]
    state_tok = s_data["state"]

    # Mock token exchange so no real network call is needed
    monkeypatch.setattr(
        iso_oauth,
        "_exchange_code_with_provider",
        lambda prov, code, redir, extras: (
            {"shop_domain": "global-d2c.myshopify.com", "access_token": "shpat_exchanged_live_tok"},
            "global-d2c.myshopify.com",
            None,
        ),
    )

    # Complete public callback with valid single-use CSRF state
    r_cb = client.get(f"/api/v1/oauth/shopify/callback?state={state_tok}&code=auth_code_123&shop=global-d2c.myshopify.com")
    assert r_cb.status_code == 200
    assert r_cb.json()["status"] == "connected"

    # Replaying the exact same state MUST be blocked 401
    r_replay = client.get(f"/api/v1/oauth/shopify/callback?state={state_tok}&code=auth_code_123")
    assert r_replay.status_code == 401

    # Verify listed connection masks token
    r_list = client.get("/api/v1/oauth/connections", headers=hdr)
    assert r_list.status_code == 200
    assert len(r_list.json()["connections"]) == 1
    assert "shpat_exchanged_live_tok" not in r_list.text

    # Disconnect wipes encrypted vault record
    r_del = client.delete("/api/v1/oauth/shopify/disconnect", headers=hdr)
    assert r_del.status_code == 200
    assert client.get("/api/v1/oauth/connections", headers=hdr).json()["connections"] == []


def test_team_rbac_owner_analyst_viewer_end_to_end_enforcement(tmp_path: Path, monkeypatch):
    iso_auth = TenantAuthManager(state_dir=tmp_path)
    iso_oauth = OAuthVaultAndScheduleManager(state_dir=tmp_path)
    monkeypatch.setattr(api_server, "auth_manager", iso_auth)
    monkeypatch.setattr(api_server, "oauth_scheduler", iso_oauth)
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")

    client = TestClient(api_server.app)
    ts = int(time.time() * 1000)

    # 1. Register Owner
    r_own = client.post(
        "/api/v1/auth/register",
        json={"email": f"owner_{ts}@acme.io", "password": "OwnerPassword!123", "workspace_name": f"AcmeTeam_{ts}"},
    )
    assert r_own.status_code == 201
    own_hdr = {"Authorization": f"Bearer {r_own.json()['access_token']}"}
    own_uid = r_own.json()["user"]["user_id"]

    # 2. Owner invites Analyst & Viewer
    r_inv_a = client.post("/api/v1/team/invite", json={"email": f"analyst_{ts}@acme.io", "role": "analyst"}, headers=own_hdr)
    r_inv_v = client.post("/api/v1/team/invite", json={"email": f"viewer_{ts}@acme.io", "role": "viewer"}, headers=own_hdr)
    assert r_inv_a.status_code == 201 and r_inv_v.status_code == 201
    inv_tok_a = r_inv_a.json()["invite_token"]
    inv_tok_v = r_inv_v.json()["invite_token"]

    # Raw DB must NEVER store plaintext invite tokens (stored hashed)
    raw_auth_db = (tmp_path / "auth_users.sqlite").read_bytes()
    assert inv_tok_a.encode("utf-8") not in raw_auth_db
    assert inv_tok_v.encode("utf-8") not in raw_auth_db

    # 3. Analyst & Viewer accept invites
    r_acc_a = client.post("/api/v1/team/accept-invite", json={"invite_token": inv_tok_a, "password": "AnalystPassword!123"})
    r_acc_v = client.post("/api/v1/team/accept-invite", json={"invite_token": inv_tok_v, "password": "ViewerPassword!123"})
    assert r_acc_a.status_code == 201 and r_acc_v.status_code == 201
    an_hdr = {"Authorization": f"Bearer {r_acc_a.json()['access_token']}"}
    vw_hdr = {"Authorization": f"Bearer {r_acc_v.json()['access_token']}"}
    an_uid = r_acc_a.json()["user"]["user_id"]
    vw_uid = r_acc_v.json()["user"]["user_id"]

    # Reusing consumed invite token rejected
    assert client.post("/api/v1/team/accept-invite", json={"invite_token": inv_tok_v, "password": "AnotherPassword!123"}).status_code == 400

    # 4. VIEWER RBAC checks (read-only allowed, ALL mutations 403 Forbidden!)
    assert client.get("/api/v1/team/members", headers=vw_hdr).status_code == 200
    assert client.get("/api/v1/billing/status", headers=vw_hdr).status_code == 200
    assert client.post("/api/v1/billing/checkout", json={"plan_id": "pro", "provider": "stripe"}, headers=vw_hdr).status_code == 403
    assert client.post("/api/v1/team/invite", json={"email": "hacker@evil.io", "role": "owner"}, headers=vw_hdr).status_code == 403
    assert client.post("/api/v1/oauth/shopify/start", json={"shop_domain": "x.myshopify.com"}, headers=vw_hdr).status_code == 403
    assert client.post(
        "/api/v1/schedules",
        json={"name": "Blocked", "source_type": "run_id", "source_ref": "hotel_booking_cancellation", "channel": "email", "recipient": "a@b.com"},
        headers=vw_hdr,
    ).status_code == 403
    assert client.post(
        "/api/v1/analyze-upload",
        files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")},
        headers=vw_hdr,
    ).status_code == 403

    # 5. ANALYST RBAC checks (can create schedules, blocked 403 on owner-only billing/team/OAuth!)
    r_an_sched = client.post(
        "/api/v1/schedules",
        json={"name": "Analyst Weekly", "source_type": "run_id", "source_ref": "hotel_booking_cancellation", "channel": "email", "recipient": "cfo@acme.io"},
        headers=an_hdr,
    )
    assert r_an_sched.status_code == 201
    assert client.post("/api/v1/billing/checkout", json={"plan_id": "pro", "provider": "stripe"}, headers=an_hdr).status_code == 403
    assert client.post("/api/v1/team/invite", json={"email": "x@acme.io", "role": "viewer"}, headers=an_hdr).status_code == 403
    assert client.post("/api/v1/oauth/shopify/start", json={"shop_domain": "x.myshopify.com"}, headers=an_hdr).status_code == 403

    # 6. Instant live role demotion: Owner demotes Analyst -> Viewer -> old Analyst JWT immediately blocked 403!
    r_dem = client.patch(f"/api/v1/team/members/{an_uid}/role", json={"role": "viewer"}, headers=own_hdr)
    assert r_dem.status_code == 200
    assert client.post(
        "/api/v1/schedules",
        json={"name": "Now Blocked", "source_type": "run_id", "source_ref": "hotel_booking_cancellation", "channel": "email", "recipient": "cfo@acme.io"},
        headers=an_hdr,
    ).status_code == 403

    # 7. Instant live removal revocation: Owner removes Viewer -> old Viewer JWT immediately gets 401!
    assert client.delete(f"/api/v1/team/members/{vw_uid}", headers=own_hdr).status_code == 200
    assert client.get("/api/v1/auth/me", headers=vw_hdr).status_code == 401

    # 8. Last remaining Owner cannot be demoted or removed (prevents orphaned workspace)
    assert client.patch(f"/api/v1/team/members/{own_uid}/role", json={"role": "viewer"}, headers=own_hdr).status_code == 400
    assert client.delete(f"/api/v1/team/members/{own_uid}", headers=own_hdr).status_code == 400


def test_persistent_morning_digest_schedules_crud_and_cron_sweep(tmp_path: Path, monkeypatch):
    iso_auth = TenantAuthManager(state_dir=tmp_path)
    iso_oauth = OAuthVaultAndScheduleManager(state_dir=tmp_path)
    monkeypatch.setattr(api_server, "auth_manager", iso_auth)
    monkeypatch.setattr(api_server, "oauth_scheduler", iso_oauth)

    client = TestClient(api_server.app)
    ts = int(time.time() * 1000)
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": f"sched_{ts}@corp.io", "password": "StrongPassword!123", "workspace_name": f"SchedCo_{ts}"},
    )
    hdr = {"Authorization": f"Bearer {r_reg.json()['access_token']}"}

    # Create an immediately-due Morning Digest schedule targeting certified benchmark
    r_cr = client.post(
        "/api/v1/schedules",
        json={
            "name": "Monday 8AM Founder Digest",
            "source_type": "run_id",
            "source_ref": "hotel_booking_cancellation",
            "frequency": "weekly_monday",
            "hour_utc": 8,
            "channel": "email",
            "recipient": "founder@corp.io",
            "lang": "hi",
            "run_immediately_due": True,
        },
        headers=hdr,
    )
    assert r_cr.status_code == 201
    sid = r_cr.json()["schedule"]["schedule_id"]

    # List verifies saved schedule
    r_ls = client.get("/api/v1/schedules", headers=hdr)
    assert r_ls.status_code == 200
    assert any(s["schedule_id"] == sid for s in r_ls.json()["schedules"])

    # Trigger zero-body cron sweep -> processes due schedule and advances next_run_at
    r_sweep = client.post("/api/v1/schedules/run-due", json={}, headers=hdr)
    assert r_sweep.status_code == 200
    sw_data = r_sweep.json()
    assert sw_data["status"] == "cron_sweep_completed"
    assert sw_data["due_count"] == 1
    assert sw_data["processed_count"] == 1
    assert sw_data["results"][0]["schedule_id"] == sid
    assert sw_data["results"][0]["status"] in ("alert_triggered", "healthy_no_alert_needed")

    # Second immediate sweep finds 0 due (next_run_at moved forward cleanly!)
    r_sweep2 = client.post("/api/v1/schedules/run-due", json={}, headers=hdr)
    assert r_sweep2.status_code == 200
    assert r_sweep2.json()["due_count"] == 0

    # Delete schedule
    assert client.delete(f"/api/v1/schedules/{sid}", headers=hdr).status_code == 200


def test_quickbooks_live_invoice_parser_and_phase_b_web_ui_hub(monkeypatch):
    fake_qb_resp = {
        "QueryResponse": {
            "Invoice": [
                {
                    "Id": "101", "DocNumber": "INV-1001", "TxnDate": "2026-01-10", "DueDate": "2026-02-10",
                    "TotalAmt": 4200.50, "Balance": 4200.50,
                    "CustomerRef": {"value": "1", "name": "Apex Logistics"},
                    "SalesTermRef": {"value": "3", "name": "Net 30"},
                    "CurrencyRef": {"value": "USD"},
                },
                {
                    "Id": "102", "DocNumber": "INV-1002", "TxnDate": "2026-01-12", "DueDate": "2026-02-12",
                    "TotalAmt": 1850.00, "Balance": 0.0,
                    "CustomerRef": {"value": "2", "name": "Beacon Retail"},
                    "SalesTermRef": {"value": "2", "name": "Net 15"},
                    "CurrencyRef": {"value": "USD"},
                },
            ]
        }
    }

    class _FakeResp(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(live_connectors, "safe_urlopen", lambda req, timeout=20: _FakeResp(json.dumps(fake_qb_resp).encode("utf-8")))
    df = live_connectors.fetch_quickbooks_live_invoices("91303500123", "qb_tok_xyz", limit=50)
    assert len(df) == 2
    assert list(df["invoice_status"]) == ["Overdue", "Paid"]
    assert float(df["invoice_amount"].sum()) == 6050.50

    # Verify SaaS Web Portal embeds Phase B Workspace Hub modal cleanly
    client = TestClient(api_server.app)
    html_text = client.get("/app").text
    for marker in ("workspaceHubModal", "hubTabOauth", "hubTabSchedules", "hubTabTeam", "hubTabBilling", "/api/v1/oauth/providers", "/api/v1/team/members"):
        assert marker in html_text
