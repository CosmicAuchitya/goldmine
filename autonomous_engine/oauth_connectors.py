"""
=============================================================================
DATAX-RAY 1-CLICK OAUTH 2.0 CONNECTORS, ENCRYPTED TOKEN VAULT & SCHEDULER
=============================================================================
Provides production-grade, tenant-isolated cloud integrations for Phase B:
1. Authenticated Encryption at Rest (AES-256-GCM via `cryptography`, with a
   pure-stdlib PBKDF2 + SHA-256-CTR + HMAC-SHA256 Encrypt-then-MAC fallback).
   Plaintext OAuth tokens are NEVER written to SQLite or returned by APIs.
2. 4 Global OAuth 2.0 Providers:
   - Shopify Admin (`read_orders,read_customers,read_products`)
   - QuickBooks Online Accounting (`com.intuit.quickbooks.accounting`)
   - Stripe Connect (`read_only`)
   - Zoho Books (`ZohoBooks.invoices.READ,ZohoBooks.contacts.READ` — IN/US/EU DCs)
3. Cryptographic Single-Use CSRF `state` Tokens (10-min TTL, replay-proof).
4. Persistent Scheduled Morning Digest Store (`daily`, `weekly_monday`,
   `weekly_friday`) powering zero-touch founder WhatsApp/Email/Slack alerts.
=============================================================================
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .tenant_auth import sanitize_tenant_id
    from .db_adapter import DatabaseAdapter
except ImportError:
    from tenant_auth import sanitize_tenant_id
    from db_adapter import DatabaseAdapter

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_AESGCM = True
except Exception:
    _HAS_AESGCM = False


WORKSPACE_ROOT = Path.cwd().resolve()
OAUTH_STATE_TTL_SEC = 600  # 10 minutes


# =============================================================================
# 1. OAUTH 2.0 PROVIDER REGISTRY (GLOBAL)
# =============================================================================
OAUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "shopify": {
        "id": "shopify",
        "name": "Shopify Admin",
        "category": "E-Commerce & D2C",
        "regions": ["Global", "US", "EU", "IN"],
        "scopes": "read_orders,read_customers,read_products",
        "client_id_env": "SHOPIFY_CLIENT_ID",
        "client_secret_env": "SHOPIFY_CLIENT_SECRET",
        "extra_required": ["shop_domain"],
        "description": "1-Click OAuth sync for live Shopify orders, refunds, COD/RTO rates, and fulfillment friction.",
    },
    "quickbooks": {
        "id": "quickbooks",
        "name": "QuickBooks Online",
        "category": "Accounting & B2B Receivables",
        "regions": ["US", "UK", "CA", "AU", "Global"],
        "scopes": "com.intuit.quickbooks.accounting",
        "client_id_env": "QUICKBOOKS_CLIENT_ID",
        "client_secret_env": "QUICKBOOKS_CLIENT_SECRET",
        "extra_required": [],
        "authorize_url": "https://appcenter.intuit.com/connect/oauth2",
        "token_url": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        "description": "1-Click OAuth sync for QuickBooks Online invoices, overdue B2B receivables, and cashflow aging.",
    },
    "stripe": {
        "id": "stripe",
        "name": "Stripe Connect",
        "category": "Global Payments & SaaS",
        "regions": ["Global", "US", "EU", "UK", "SG"],
        "scopes": "read_only",
        "client_id_env": "STRIPE_CONNECT_CLIENT_ID",
        "client_secret_env": "STRIPE_SECRET_KEY",
        "extra_required": [],
        "authorize_url": "https://connect.stripe.com/oauth/authorize",
        "token_url": "https://connect.stripe.com/oauth/token",
        "description": "1-Click read-only Stripe Connect sync for failed charges, disputes, refunds, and MRR churn.",
    },
    "zoho_books": {
        "id": "zoho_books",
        "name": "Zoho Books",
        "category": "India & Global MSME Accounting",
        "regions": ["IN", "US", "EU", "AE", "AU"],
        "scopes": "ZohoBooks.invoices.READ,ZohoBooks.contacts.READ",
        "client_id_env": "ZOHO_CLIENT_ID",
        "client_secret_env": "ZOHO_CLIENT_SECRET",
        "extra_required": ["organization_id"],
        "description": "1-Click OAuth sync for Zoho Books GST/B2B invoices, overdue debtors, and credit terms.",
    },
}

ZOHO_REGION_DOMAINS: Dict[str, Tuple[str, str]] = {
    "in": ("https://accounts.zoho.in", "https://www.zohoapis.in"),
    "com": ("https://accounts.zoho.com", "https://www.zohoapis.com"),
    "eu": ("https://accounts.zoho.eu", "https://www.zohoapis.eu"),
    "au": ("https://accounts.zoho.com.au", "https://www.zohoapis.com.au"),
}


# =============================================================================
# 2. AUTHENTICATED ENCRYPTION ENGINE (AES-256-GCM + STDLIB FALLBACK)
# =============================================================================
def _load_or_create_vault_key(state_dir: Path) -> bytes:
    """Derives a 32-byte symmetric encryption key strictly for token vault at-rest encryption."""
    env_key = os.environ.get("DATAXRAY_VAULT_KEY", "").strip()
    if env_key:
        return hashlib.sha256(f"dx-vault-v1::{env_key}".encode("utf-8")).digest()

    jwt_sec = os.environ.get("DATAXRAY_JWT_SECRET", "").strip()
    if jwt_sec:
        return hashlib.sha256(f"dx-vault-from-jwt-v1::{jwt_sec}".encode("utf-8")).digest()

    state_dir.mkdir(parents=True, exist_ok=True)
    key_file = state_dir / ".vault_key"
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            return hashlib.sha256(stored.encode("utf-8")).digest()

    generated = secrets.token_hex(32)
    key_file.write_text(generated, encoding="utf-8")
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return hashlib.sha256(generated.encode("utf-8")).digest()


def encrypt_vault_payload(plaintext_obj: Dict[str, Any], key: bytes, aad: str) -> str:
    """Encrypts a credentials dictionary with authenticated encryption bound to tenant+provider AAD."""
    raw = json.dumps(plaintext_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    aad_bytes = aad.encode("utf-8")

    if _HAS_AESGCM:
        nonce = secrets.token_bytes(12)
        ct = AESGCM(key).encrypt(nonce, raw, aad_bytes)
        blob = base64.urlsafe_b64encode(nonce + ct).decode("ascii")
        return f"v1gcm:{blob}"

    # Pure-stdlib Encrypt-then-MAC fallback (SHA-256 counter keystream + HMAC-SHA256)
    nonce = secrets.token_bytes(16)
    enc_key = hmac.new(key, b"enc" + nonce, hashlib.sha256).digest()
    mac_key = hmac.new(key, b"mac" + nonce, hashlib.sha256).digest()
    out = bytearray(len(raw))
    for i in range(0, len(raw), 32):
        blk = hashlib.sha256(enc_key + nonce + (i // 32).to_bytes(4, "big")).digest()
        chunk = raw[i : i + 32]
        for j, b in enumerate(chunk):
            out[i + j] = b ^ blk[j]
    tag = hmac.new(mac_key, aad_bytes + nonce + bytes(out), hashlib.sha256).digest()
    blob = base64.urlsafe_b64encode(nonce + tag + bytes(out)).decode("ascii")
    return f"v1etm:{blob}"


def decrypt_vault_payload(token_str: str, key: bytes, aad: str) -> Dict[str, Any]:
    """Verifies authenticity tag & AAD binding, then decrypts the credentials dictionary."""
    if not token_str or ":" not in token_str:
        raise ValueError("Corrupted vault ciphertext.")
    scheme, blob = token_str.split(":", 1)
    aad_bytes = aad.encode("utf-8")
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))

    if scheme == "v1gcm":
        if not _HAS_AESGCM:
            raise RuntimeError("cryptography package required to decrypt v1gcm vault record.")
        if len(raw) < 28:
            raise ValueError("Truncated AES-GCM payload.")
        nonce, ct = raw[:12], raw[12:]
        pt = AESGCM(key).decrypt(nonce, ct, aad_bytes)
        return json.loads(pt.decode("utf-8"))

    if scheme == "v1etm":
        if len(raw) < 48:
            raise ValueError("Truncated EtM payload.")
        nonce, tag, ct = raw[:16], raw[16:48], raw[48:]
        enc_key = hmac.new(key, b"enc" + nonce, hashlib.sha256).digest()
        mac_key = hmac.new(key, b"mac" + nonce, hashlib.sha256).digest()
        expected_tag = hmac.new(mac_key, aad_bytes + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Vault integrity check failed (tampered ciphertext or wrong tenant AAD).")
        out = bytearray(len(ct))
        for i in range(0, len(ct), 32):
            blk = hashlib.sha256(enc_key + nonce + (i // 32).to_bytes(4, "big")).digest()
            chunk = ct[i : i + 32]
            for j, b in enumerate(chunk):
                out[i + j] = b ^ blk[j]
        return json.loads(bytes(out).decode("utf-8"))

    raise ValueError(f"Unsupported vault cipher scheme: {scheme}")


def _clean_shop_domain(raw_domain: str) -> str:
    dom = re.sub(r"^https?://", "", str(raw_domain or "").strip().lower()).strip("/")
    if not dom:
        return ""
    if "." not in dom:
        dom = f"{dom}.myshopify.com"
    if not re.match(r"^[a-z0-9][a-z0-9\-]*\.myshopify\.com$", dom) and not re.match(r"^[a-z0-9][a-z0-9\-\.]+\.[a-z]{2,}$", dom):
        raise ValueError("Invalid Shopify shop_domain (expected e.g. 'your-store.myshopify.com').")
    return dom


# =============================================================================
# 3. OAUTH CONNECTOR VAULT & SCHEDULED MORNING DIGEST MANAGER
# =============================================================================
class OAuthVaultAndScheduleManager:
    """Thread-safe SQLite WAL store for encrypted OAuth tokens, CSRF states, and scheduled digests."""

    def __init__(self, state_dir: Optional[Path] = None, database_url: Optional[str] = None):
        self.state_dir = (state_dir or (WORKSPACE_ROOT / "runs" / "state")).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "oauth_vault.sqlite"
        self.db = DatabaseAdapter(self.db_path, database_url=database_url)
        self._lock = threading.Lock()
        self._init_db()

    def _vault_key(self) -> bytes:
        return _load_or_create_vault_key(self.state_dir)

    def _connect(self):
        return self.db.connect()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_token TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    extra_json TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_connections (
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    account_label TEXT,
                    encrypted_credentials TEXT NOT NULL,
                    scopes TEXT,
                    connected_by TEXT,
                    status TEXT NOT NULL DEFAULT 'connected',
                    expires_at REAL,
                    last_synced_at REAL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (tenant_id, provider)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS digest_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'run_id',
                    source_ref TEXT NOT NULL,
                    frequency TEXT NOT NULL DEFAULT 'weekly_monday',
                    hour_utc INTEGER NOT NULL DEFAULT 8,
                    channel TEXT NOT NULL DEFAULT 'email',
                    recipient TEXT,
                    webhook_url TEXT,
                    lang TEXT NOT NULL DEFAULT 'en',
                    region_profile TEXT NOT NULL DEFAULT 'US',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    next_run_at REAL NOT NULL,
                    last_run_at REAL,
                    last_status TEXT,
                    created_by TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_tenant ON digest_schedules(tenant_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_due ON digest_schedules(enabled, next_run_at);")

    # -------------------------------------------------------------------------
    # OAuth Provider Catalog & Start Flow
    # -------------------------------------------------------------------------
    def list_oauth_providers(self) -> List[Dict[str, Any]]:
        out = []
        for pid, cfg in OAUTH_PROVIDERS.items():
            cid = os.environ.get(cfg["client_id_env"], "").strip()
            csec = os.environ.get(cfg["client_secret_env"], "").strip()
            out.append({
                "id": pid,
                "name": cfg["name"],
                "category": cfg["category"],
                "regions": cfg["regions"],
                "scopes": cfg["scopes"],
                "extra_required": cfg["extra_required"],
                "description": cfg["description"],
                "oauth_configured": bool(cid and (csec or pid == "stripe")),
                "required_env_vars": [cfg["client_id_env"], cfg["client_secret_env"]],
            })
        return out

    def start_oauth_flow(
        self,
        tenant_id: str,
        provider: str,
        redirect_uri: str,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prov = str(provider or "").strip().lower()
        if prov not in OAUTH_PROVIDERS:
            raise ValueError(f"Unsupported OAuth provider '{prov}'. Choose from: {', '.join(OAUTH_PROVIDERS.keys())}.")
        if not str(redirect_uri or "").startswith(("https://", "http://")):
            raise ValueError("Invalid redirect_uri: must begin with https:// or http://.")

        cfg = OAUTH_PROVIDERS[prov]
        norm_tid = sanitize_tenant_id(tenant_id)
        extras = dict(extra_params or {})

        client_id = os.environ.get(cfg["client_id_env"], "").strip()
        client_secret = os.environ.get(cfg["client_secret_env"], "").strip()
        if not client_id or not client_secret:
            return {
                "status": "configuration_required",
                "provider": prov,
                "provider_name": cfg["name"],
                "message": (
                    f"OAuth credentials for {cfg['name']} are not configured on this server yet. "
                    f"Set {cfg['client_id_env']} and {cfg['client_secret_env']} (or use Direct API Key Connect)."
                ),
                "required_env_vars": [cfg["client_id_env"], cfg["client_secret_env"]],
            }

        state_token = secrets.token_urlsafe(32)
        expires_at = time.time() + OAUTH_STATE_TTL_SEC

        if prov == "shopify":
            shop_domain = _clean_shop_domain(str(extras.get("shop_domain") or ""))
            if not shop_domain:
                raise ValueError("Shopify OAuth requires 'shop_domain' (e.g., 'your-store.myshopify.com').")
            extras["shop_domain"] = shop_domain
            params = {
                "client_id": client_id,
                "scope": cfg["scopes"],
                "redirect_uri": redirect_uri,
                "state": state_token,
            }
            auth_url = f"https://{shop_domain}/admin/oauth/authorize?{urllib.parse.urlencode(params)}"

        elif prov == "quickbooks":
            params = {
                "client_id": client_id,
                "scope": cfg["scopes"],
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "state": state_token,
            }
            auth_url = f"{cfg['authorize_url']}?{urllib.parse.urlencode(params)}"

        elif prov == "stripe":
            params = {
                "response_type": "code",
                "client_id": client_id,
                "scope": cfg["scopes"],
                "redirect_uri": redirect_uri,
                "state": state_token,
            }
            auth_url = f"{cfg['authorize_url']}?{urllib.parse.urlencode(params)}"

        elif prov == "zoho_books":
            z_reg = str(extras.get("zoho_region") or "in").strip().lower()
            if z_reg not in ZOHO_REGION_DOMAINS:
                z_reg = "in"
            accounts_base, api_base = ZOHO_REGION_DOMAINS[z_reg]
            extras["zoho_region"] = z_reg
            extras["api_domain"] = api_base
            params = {
                "scope": cfg["scopes"],
                "client_id": client_id,
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
                "redirect_uri": redirect_uri,
                "state": state_token,
            }
            auth_url = f"{accounts_base}/oauth/v2/auth?{urllib.parse.urlencode(params)}"
        else:
            raise ValueError(f"Unsupported provider '{prov}'.")

        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (time.time(),))
            conn.execute(
                """
                INSERT INTO oauth_states (state_token, tenant_id, provider, redirect_uri, extra_json, expires_at, consumed)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (state_token, norm_tid, prov, redirect_uri, json.dumps(extras), expires_at),
            )

        return {
            "status": "authorization_url_created",
            "provider": prov,
            "provider_name": cfg["name"],
            "state": state_token,
            "expires_in_seconds": OAUTH_STATE_TTL_SEC,
            "authorization_url": auth_url,
        }

    def _exchange_code_with_provider(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
        extras: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str, Optional[float]]:
        """Exchanges OAuth authorization code for access/refresh tokens via provider token endpoint."""
        cfg = OAUTH_PROVIDERS[provider]
        client_id = os.environ.get(cfg["client_id_env"], "").strip()
        client_secret = os.environ.get(cfg["client_secret_env"], "").strip()

        if provider == "shopify":
            shop_domain = _clean_shop_domain(str(extras.get("shop_domain") or ""))
            url = f"https://{shop_domain}/admin/oauth/access_token"
            body = json.dumps({"client_id": client_id, "client_secret": client_secret, "code": code}).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
            creds = {
                "shop_domain": shop_domain,
                "access_token": tok["access_token"],
                "scope": tok.get("scope", cfg["scopes"]),
            }
            return creds, shop_domain, None

        if provider == "quickbooks":
            auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
            form = urllib.parse.urlencode({
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            }).encode("utf-8")
            req = urllib.request.Request(
                cfg["token_url"],
                data=form,
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
            realm_id = str(extras.get("realmId") or extras.get("realm_id") or "")
            exp = time.time() + float(tok.get("expires_in", 3600))
            creds = {
                "realm_id": realm_id,
                "access_token": tok["access_token"],
                "refresh_token": tok.get("refresh_token", ""),
            }
            return creds, f"QB Realm {realm_id or 'connected'}", exp

        if provider == "stripe":
            form = urllib.parse.urlencode({
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            }).encode("utf-8")
            req = urllib.request.Request(
                cfg["token_url"],
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
            acct = str(tok.get("stripe_user_id") or "stripe_account")
            creds = {
                "api_key": tok["access_token"],
                "refresh_token": tok.get("refresh_token", ""),
                "stripe_user_id": acct,
            }
            return creds, acct, None

        if provider == "zoho_books":
            z_reg = str(extras.get("zoho_region") or "in").lower()
            accounts_base, api_base = ZOHO_REGION_DOMAINS.get(z_reg, ZOHO_REGION_DOMAINS["in"])
            form = urllib.parse.urlencode({
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{accounts_base}/oauth/v2/token",
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
            org_id = str(extras.get("organization_id") or "")
            exp = time.time() + float(tok.get("expires_in", 3600))
            creds = {
                "access_token": tok["access_token"],
                "refresh_token": tok.get("refresh_token", ""),
                "organization_id": org_id,
                "api_domain": tok.get("api_domain") or api_base,
                "zoho_region": z_reg,
            }
            return creds, f"Zoho Org {org_id or z_reg.upper()}", exp

        raise ValueError(f"Unsupported provider '{provider}'.")

    def complete_oauth_callback(
        self,
        provider: str,
        state: str,
        code: str,
        callback_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validates single-use CSRF state, exchanges code, encrypts tokens into tenant vault."""
        prov = str(provider or "").strip().lower()
        if not state or not code:
            raise ValueError("Missing OAuth 'state' or 'code' parameter.")

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM oauth_states WHERE state_token = ?",
                (str(state).strip(),),
            ).fetchone()
            if not row:
                raise PermissionError("Invalid or unknown OAuth CSRF state token.")
            if int(row["consumed"]) == 1:
                raise PermissionError("OAuth state token was already used (replay blocked).")
            if float(row["expires_at"]) < time.time():
                raise PermissionError("OAuth state token has expired. Please restart connection.")
            if str(row["provider"]) != prov:
                raise PermissionError("OAuth provider mismatch for state token.")
            # Atomically mark consumed BEFORE network exchange to guarantee single-use
            conn.execute("UPDATE oauth_states SET consumed = 1 WHERE state_token = ?", (str(state).strip(),))

        tenant_id = str(row["tenant_id"])
        redirect_uri = str(row["redirect_uri"])
        extras = json.loads(str(row["extra_json"] or "{}"))
        if callback_params:
            for k, v in callback_params.items():
                # Never allow callback query params to override host/domain locked in signed CSRF state
                if v and not extras.get(k):
                    extras[k] = v

        creds, label, expires_at = self._exchange_code_with_provider(prov, code, redirect_uri, extras)
        return self.save_encrypted_connection(
            tenant_id=tenant_id,
            provider=prov,
            credentials=creds,
            account_label=label,
            scopes=OAUTH_PROVIDERS[prov]["scopes"],
            connected_by="oauth2_callback",
            expires_at=expires_at,
        )

    def save_encrypted_connection(
        self,
        tenant_id: str,
        provider: str,
        credentials: Dict[str, Any],
        account_label: Optional[str] = None,
        scopes: Optional[str] = None,
        connected_by: str = "owner",
        expires_at: Optional[float] = None,
    ) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        prov = str(provider or "").strip().lower()
        if not credentials or not isinstance(credentials, dict):
            raise ValueError("Credentials dictionary cannot be empty.")

        aad = f"{norm_tid}::{prov}"
        ciphertext = encrypt_vault_payload(credentials, self._vault_key(), aad=aad)
        now = time.time()
        lbl = str(account_label or credentials.get("shop_domain") or credentials.get("organization_id") or credentials.get("realm_id") or prov)[:120]

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oauth_connections (
                    tenant_id, provider, account_label, encrypted_credentials,
                    scopes, connected_by, status, expires_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'connected', ?, ?)
                ON CONFLICT(tenant_id, provider) DO UPDATE SET
                    account_label=excluded.account_label,
                    encrypted_credentials=excluded.encrypted_credentials,
                    scopes=COALESCE(excluded.scopes, oauth_connections.scopes),
                    connected_by=excluded.connected_by,
                    status='connected',
                    expires_at=excluded.expires_at,
                    updated_at=excluded.updated_at
                """,
                (norm_tid, prov, lbl, ciphertext, scopes or "", connected_by, expires_at, now),
            )
        return {
            "status": "connected",
            "tenant_id": norm_tid,
            "provider": prov,
            "account_label": lbl,
            "encrypted_at_rest": True,
            "cipher": "AES-256-GCM" if _HAS_AESGCM else "SHA256-CTR-HMAC",
            "updated_at": now,
        }

    def list_tenant_connections(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Returns ONLY masked connection metadata for the tenant — NEVER exposes decrypted secrets."""
        norm_tid = sanitize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT tenant_id, provider, account_label, scopes, connected_by,
                       status, expires_at, last_synced_at, updated_at
                FROM oauth_connections
                WHERE tenant_id = ?
                ORDER BY updated_at DESC
                """,
                (norm_tid,),
            ).fetchall()
        return [
            {
                "tenant_id": r["tenant_id"],
                "provider": r["provider"],
                "provider_name": (OAUTH_PROVIDERS.get(r["provider"]) or {}).get("name", r["provider"]),
                "account_label": r["account_label"],
                "scopes": r["scopes"],
                "status": r["status"],
                "connected_by": r["connected_by"],
                "encrypted_at_rest": True,
                "expires_at": r["expires_at"],
                "last_synced_at": r["last_synced_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def _refresh_provider_token(self, provider: str, creds: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], float]]:
        """Refreshes expired QuickBooks Online or Zoho Books OAuth access tokens via refresh_token."""
        refresh_tok = str(creds.get("refresh_token") or "").strip()
        if not refresh_tok or provider not in ("quickbooks", "zoho_books"):
            return None
        cfg = OAUTH_PROVIDERS[provider]
        client_id = os.environ.get(cfg["client_id_env"], "").strip()
        client_secret = os.environ.get(cfg["client_secret_env"], "").strip()
        if not client_id or not client_secret:
            return None

        if provider == "quickbooks":
            auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
            form = urllib.parse.urlencode({
                "grant_type": "refresh_token",
                "refresh_token": refresh_tok,
            }).encode("utf-8")
            req = urllib.request.Request(
                cfg["token_url"],
                data=form,
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
            updated = dict(creds)
            updated["access_token"] = tok["access_token"]
            if tok.get("refresh_token"):
                updated["refresh_token"] = tok["refresh_token"]
            return updated, time.time() + float(tok.get("expires_in", 3600))

        if provider == "zoho_books":
            z_reg = str(creds.get("zoho_region") or "in").lower()
            accounts_base, _ = ZOHO_REGION_DOMAINS.get(z_reg, ZOHO_REGION_DOMAINS["in"])
            form = urllib.parse.urlencode({
                "refresh_token": refresh_tok,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{accounts_base}/oauth/v2/token",
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                tok = json.loads(resp.read().decode("utf-8"))
            updated = dict(creds)
            updated["access_token"] = tok["access_token"]
            if tok.get("api_domain"):
                updated["api_domain"] = tok["api_domain"]
            return updated, time.time() + float(tok.get("expires_in", 3600))

        return None

    def get_decrypted_credentials(self, tenant_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Decrypts credentials strictly in memory for the owning tenant (AAD-enforced) and auto-refreshes if expired."""
        norm_tid = sanitize_tenant_id(tenant_id)
        prov = str(provider or "").strip().lower()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT encrypted_credentials, status, expires_at, account_label, scopes FROM oauth_connections WHERE tenant_id = ? AND provider = ?",
                (norm_tid, prov),
            ).fetchone()
        if not row or str(row["status"]) != "connected":
            return None
        aad = f"{norm_tid}::{prov}"
        creds = decrypt_vault_payload(str(row["encrypted_credentials"]), self._vault_key(), aad=aad)

        exp = row["expires_at"]
        if exp is not None and float(exp) <= time.time() + 120.0:
            try:
                refreshed = self._refresh_provider_token(prov, creds)
                if refreshed:
                    new_creds, new_exp = refreshed
                    self.save_encrypted_connection(
                        tenant_id=norm_tid,
                        provider=prov,
                        credentials=new_creds,
                        account_label=row["account_label"],
                        scopes=row["scopes"],
                        connected_by="oauth2_auto_refresh",
                        expires_at=new_exp,
                    )
                    return new_creds
            except Exception:
                # Fall back to existing token if refresh fails transiently
                pass
        return creds

    def mark_connection_synced(self, tenant_id: str, provider: str) -> None:
        norm_tid = sanitize_tenant_id(tenant_id)
        prov = str(provider or "").strip().lower()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE oauth_connections SET last_synced_at = ? WHERE tenant_id = ? AND provider = ?",
                (time.time(), norm_tid, prov),
            )

    def disconnect_provider(self, tenant_id: str, provider: str) -> bool:
        norm_tid = sanitize_tenant_id(tenant_id)
        prov = str(provider or "").strip().lower()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM oauth_connections WHERE tenant_id = ? AND provider = ?",
                (norm_tid, prov),
            )
            return cur.rowcount > 0

    # -------------------------------------------------------------------------
    # Scheduled Morning Digest Store (Recurring Daily / Weekly Monday)
    # -------------------------------------------------------------------------
    @staticmethod
    def compute_next_run_ts(frequency: str, hour_utc: int = 8, from_ts: Optional[float] = None) -> float:
        now_dt = datetime.datetime.fromtimestamp(from_ts or time.time(), tz=datetime.timezone.utc)
        hr = max(0, min(23, int(hour_utc)))
        freq = str(frequency or "weekly_monday").strip().lower()

        candidate = now_dt.replace(hour=hr, minute=0, second=0, microsecond=0)
        if freq == "daily":
            if candidate <= now_dt:
                candidate += datetime.timedelta(days=1)
        elif freq == "weekly_friday":
            days_ahead = (4 - now_dt.weekday()) % 7
            candidate += datetime.timedelta(days=days_ahead)
            if candidate <= now_dt:
                candidate += datetime.timedelta(days=7)
        else:  # weekly_monday (default)
            days_ahead = (0 - now_dt.weekday()) % 7
            candidate += datetime.timedelta(days=days_ahead)
            if candidate <= now_dt:
                candidate += datetime.timedelta(days=7)
        return candidate.timestamp()

    def create_digest_schedule(
        self,
        tenant_id: str,
        name: str,
        source_type: str,
        source_ref: str,
        frequency: str = "weekly_monday",
        hour_utc: int = 8,
        channel: str = "email",
        recipient: Optional[str] = None,
        webhook_url: Optional[str] = None,
        lang: str = "en",
        region_profile: str = "US",
        created_by: str = "owner",
        run_immediately_due: bool = False,
    ) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        st = str(source_type or "run_id").strip().lower()
        if st not in ("run_id", "oauth_connection"):
            raise ValueError("source_type must be 'run_id' or 'oauth_connection'.")
        freq = str(frequency or "weekly_monday").strip().lower()
        if freq not in ("daily", "weekly_monday", "weekly_friday"):
            raise ValueError("frequency must be 'daily', 'weekly_monday', or 'weekly_friday'.")
        ch = str(channel or "email").strip().lower()
        if ch not in ("email", "whatsapp", "webhook"):
            raise ValueError("channel must be 'email', 'whatsapp', or 'webhook'.")
        if ch in ("email", "whatsapp") and not str(recipient or "").strip():
            raise ValueError(f"Channel '{ch}' requires a recipient (email address or phone number).")
        if ch == "webhook" and not str(webhook_url or "").startswith(("https://", "http://")):
            raise ValueError("Channel 'webhook' requires a valid https:// webhook_url.")

        sched_id = f"sch_{secrets.token_hex(6)}"
        now = time.time()
        next_run = (now - 1.0) if run_immediately_due else self.compute_next_run_ts(freq, hour_utc, from_ts=now)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO digest_schedules (
                    schedule_id, tenant_id, name, source_type, source_ref, frequency,
                    hour_utc, channel, recipient, webhook_url, lang, region_profile,
                    enabled, next_run_at, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    sched_id, norm_tid, str(name or "Morning Executive Digest").strip()[:100],
                    st, str(source_ref).strip()[:120], freq, max(0, min(23, int(hour_utc))),
                    ch, str(recipient or "").strip() or None, str(webhook_url or "").strip() or None,
                    str(lang or "en").strip().lower()[:8], str(region_profile or "US").strip().upper()[:8],
                    next_run, str(created_by or "owner")[:120], now,
                ),
            )
        return self.get_schedule(norm_tid, sched_id) or {}

    def get_schedule(self, tenant_id: str, schedule_id: str) -> Optional[Dict[str, Any]]:
        norm_tid = sanitize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            r = conn.execute(
                "SELECT * FROM digest_schedules WHERE tenant_id = ? AND schedule_id = ?",
                (norm_tid, str(schedule_id).strip()),
            ).fetchone()
        return dict(r) if r else None

    def list_tenant_schedules(self, tenant_id: str) -> List[Dict[str, Any]]:
        norm_tid = sanitize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM digest_schedules WHERE tenant_id = ? ORDER BY created_at DESC",
                (norm_tid,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_schedule(self, tenant_id: str, schedule_id: str) -> bool:
        norm_tid = sanitize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM digest_schedules WHERE tenant_id = ? AND schedule_id = ?",
                (norm_tid, str(schedule_id).strip()),
            )
            return cur.rowcount > 0

    def list_due_schedules(self, now_ts: Optional[float] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        ts = now_ts if now_ts is not None else time.time()
        with self._lock, self._connect() as conn:
            if tenant_id:
                rows = conn.execute(
                    "SELECT * FROM digest_schedules WHERE enabled = 1 AND next_run_at <= ? AND tenant_id = ? ORDER BY next_run_at ASC",
                    (ts, sanitize_tenant_id(tenant_id)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM digest_schedules WHERE enabled = 1 AND next_run_at <= ? ORDER BY next_run_at ASC",
                    (ts,),
                ).fetchall()
        return [dict(r) for r in rows]

    def mark_schedule_executed(self, schedule_id: str, status_msg: str) -> None:
        now = time.time()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT frequency, hour_utc FROM digest_schedules WHERE schedule_id = ?",
                (schedule_id,),
            ).fetchone()
            if not row:
                return
            next_run = self.compute_next_run_ts(str(row["frequency"]), int(row["hour_utc"]), from_ts=now + 60.0)
            conn.execute(
                """
                UPDATE digest_schedules
                SET last_run_at = ?, last_status = ?, next_run_at = ?
                WHERE schedule_id = ?
                """,
                (now, str(status_msg)[:200], next_run, schedule_id),
            )
