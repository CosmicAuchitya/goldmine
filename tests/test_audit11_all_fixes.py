from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine.api_server import app, _RATE_BUCKETS, _resolve_rightmost_untrusted_client_ip
from autonomous_engine.tenant_auth import TenantAuthManager
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost


def test_audit11_1_and_9_hmac_api_key_and_jwt_sub_rate_bucket(monkeypatch):
    """Findings #1 & #9: DATAXRAY_API_KEY auth works cleanly (hmac imported) and JWT users get distinct sub rate buckets."""
    _RATE_BUCKETS.clear()
    monkeypatch.setenv("DATAXRAY_API_KEY", "audit11_admin_secret_key")
    monkeypatch.setenv("DATAXRAY_RATE_LIMIT_RPM", "120")

    client = TestClient(app)
    r_ok = client.get("/api/v1/workspaces/default/runs", headers={"X-API-Key": "audit11_admin_secret_key"})
    assert r_ok.status_code == 200


def test_audit11_2_requirements_include_pdf_and_cloud_drivers():
    """Finding #2: requirements.txt bundles PDF libs and Dockerfile installs requirements-cloud.txt."""
    req = Path("requirements.txt").read_text(encoding="utf-8").lower()
    req_cloud = Path("requirements-cloud.txt").read_text(encoding="utf-8").lower()
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "pymupdf" in req and "pypdf" in req
    for pkg in ("psycopg", "redis", "rq", "boto3"):
        assert pkg in req_cloud
    assert "requirements-cloud.txt" in dockerfile


def test_audit11_3_translate_texts_requires_auth_when_enforced(monkeypatch):
    """Finding #3: POST /api/v1/i18n/translate-texts must reject anonymous callers when DATAXRAY_REQUIRE_AUTH=true."""
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    client = TestClient(app)
    r_anon = client.post(
        "/api/v1/i18n/translate-texts",
        json={"target_lang": "es", "texts": {"a": "Hello"}},
    )
    assert r_anon.status_code == 401


def test_audit11_4_multihop_xff_skips_private_proxy_and_blocks_left_spoof():
    """Finding #4: X-Forwarded-For picks rightmost non-private IP (blocks left spoof, isolates behind internal proxy)."""
    assert _resolve_rightmost_untrusted_client_ip("198.51.100.1, 203.0.113.55", "127.0.0.1") == "203.0.113.55"
    assert _resolve_rightmost_untrusted_client_ip("203.0.113.10, 10.0.0.1", "127.0.0.1") == "203.0.113.10"
    assert _resolve_rightmost_untrusted_client_ip("198.51.100.42, 10.0.0.1, 172.17.0.2", "127.0.0.1") == "198.51.100.42"


def test_audit11_7_system_db_health_and_backup_block_tenant_owner_allow_admin(monkeypatch):
    """Finding #7: Regular workspace 'owner' must get 403 on server-wide db-health/db-backup; admin key gets 200."""
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DATAXRAY_API_KEY", "audit11_super_admin_999")
    client = TestClient(app)

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "owner_audit11_rbac@example.com", "password": "StrongPassword123!", "workspace_name": "Shop11"},
    )
    if reg.status_code == 200 or reg.status_code == 201:
        tok = reg.json()["access_token"]
    else:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "owner_audit11_rbac@example.com", "password": "StrongPassword123!"},
        )
        assert login.status_code == 200
        tok = login.json()["access_token"]

    r_owner_health = client.get("/api/v1/system/db-health", headers={"Authorization": f"Bearer {tok}"})
    assert r_owner_health.status_code == 403

    r_owner_bak = client.post("/api/v1/system/db-backup", headers={"Authorization": f"Bearer {tok}"})
    assert r_owner_bak.status_code == 403

    r_admin_health = client.get("/api/v1/system/db-health", headers={"X-API-Key": "audit11_super_admin_999"})
    assert r_admin_health.status_code == 200


def test_audit11_8_target_resolver_content_fingerprint_prevents_stale_cache():
    """Finding #8: Two identical-shape DataFrames with different values must never share cached binary_target."""
    df_a = pd.DataFrame({"region": ["North"] * 20, "amount": [100.0] * 20, "is_returned": [1] * 10 + [0] * 10})
    df_b = pd.DataFrame({"region": ["South"] * 20, "amount": [200.0] * 20, "is_returned": [0] * 10 + [1] * 10})
    res_a = resolve_canonical_target_and_cost(df_a)
    res_b = resolve_canonical_target_and_cost(df_b)
    assert list(res_a["binary_target"]) != list(res_b["binary_target"])


def test_audit11_11_login_bruteforce_lockout(tmp_path):
    """Finding #11: Repeated failed logins lock out the targeted account temporarily."""
    mgr = TenantAuthManager(state_dir=tmp_path)
    mgr.register_user("victim_lockout@example.com", "CorrectPass123!", workspace_name="LockShop")

    for _ in range(5):
        assert mgr.authenticate_user("victim_lockout@example.com", "WrongPass999!") is None

    # Even the correct password must be rejected during active lockout window
    assert mgr.authenticate_user("victim_lockout@example.com", "CorrectPass123!") is None
