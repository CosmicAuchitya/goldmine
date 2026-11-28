"""
=============================================================================
DATAX-RAY MULTI-TENANT AUTHENTICATION & ACCESS CONTROL ENGINE (P0 HARDENED)
=============================================================================
Provides zero-dependency, production-grade tenant isolation and authentication:
1. PBKDF2-HMAC-SHA256 (200,000 iterations) password hashing with per-user salts.
2. SQLite (WAL mode) persistent user & tenant workspace store.
3. HMAC-SHA256 signed stateless Bearer tokens (dx1.<payload>.<sig>) with expiry.
4. Constant-time API key comparison (hmac.compare_digest) defeating timing attacks.
5. Strict tenant-ownership verification across dashboards, reports, Q&A, downloads,
   and GDPR purge endpoints.
=============================================================================
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .db_adapter import DatabaseAdapter
except ImportError:
    from db_adapter import DatabaseAdapter


WORKSPACE_ROOT = Path.cwd().resolve()
PBKDF2_ITERATIONS = 200_000
DEFAULT_TOKEN_TTL_SEC = 86_400  # 24 hours
INVITE_TTL_SEC = 7 * 86_400     # 7 days

ROLE_HIERARCHY: Dict[str, int] = {
    "viewer": 1,
    "analyst": 2,
    "owner": 3,
    "admin": 4,
}
VALID_WORKSPACE_ROLES = ("owner", "analyst", "viewer")


def normalize_workspace_role(role: str) -> str:
    r = str(role or "viewer").strip().lower()
    if r not in VALID_WORKSPACE_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of: owner, analyst, viewer.")
    return r


def role_satisfies(actual_role: str, required_min_role: str) -> bool:
    actual_lvl = ROLE_HIERARCHY.get(str(actual_role or "").strip().lower(), 0)
    req_lvl = ROLE_HIERARCHY.get(str(required_min_role or "owner").strip().lower(), 99)
    return actual_lvl >= req_lvl


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sanitize_tenant_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:64] if cleaned else "default_tenant"


_JWT_MULTIPOD_WARNED = False
_LOGIN_LOCK = threading.Lock()
_FAILED_LOGINS: Dict[str, List[float]] = {}
_LOGIN_LOCKOUT_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_WINDOW_SEC = 300.0
_LOGIN_LOCKOUT_DURATION_SEC = 60.0
_DUMMY_PBKDF2_SALT = "0" * 32
_DUMMY_PBKDF2_HASH = "0" * 64


def _get_signing_secret(state_dir: Path) -> bytes:
    global _JWT_MULTIPOD_WARNED
    env_secret = os.environ.get("DATAXRAY_JWT_SECRET", "").strip()
    if env_secret:
        return env_secret.encode("utf-8")
    env_api_key = os.environ.get("DATAXRAY_API_KEY", "").strip()
    if env_api_key:
        return hashlib.sha256(f"dx-jwt::{env_api_key}".encode("utf-8")).digest()

    if not _JWT_MULTIPOD_WARNED and (os.environ.get("DATABASE_URL", "").strip() or os.environ.get("REDIS_URL", "").strip()):
        _JWT_MULTIPOD_WARNED = True
        print("[!] [Security Warning] Multi-pod cloud mode detected without DATAXRAY_JWT_SECRET! Set a shared DATAXRAY_JWT_SECRET across all replicas.")

    state_dir.mkdir(parents=True, exist_ok=True)
    secret_file = state_dir / ".jwt_secret"
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored.encode("utf-8")

    generated = secrets.token_hex(32)
    secret_file.write_text(generated, encoding="utf-8")
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return generated.encode("utf-8")


def is_valid_admin_api_key(provided_key: Optional[str]) -> bool:
    expected = os.environ.get("DATAXRAY_API_KEY", "").strip()
    if not expected or not provided_key:
        return False
    return hmac.compare_digest(provided_key.encode("utf-8"), expected.encode("utf-8"))


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex(), salt.hex()


def verify_password(password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    computed_hex, _ = hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(computed_hex.encode("ascii"), stored_hash_hex.encode("ascii"))


class TenantAuthManager:
    """Thread-safe SQLite WAL user & multi-tenant JWT authentication manager."""

    def __init__(self, state_dir: Optional[Path] = None, database_url: Optional[str] = None):
        self.state_dir = (state_dir or (WORKSPACE_ROOT / "runs" / "state")).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "auth_users.sqlite"
        self.db = DatabaseAdapter(self.db_path, database_url=database_url)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return self.db.connect()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    workspace_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'owner',
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_invites (
                    invite_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    workspace_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    invited_by TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at REAL NOT NULL,
                    accepted_at REAL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_invites_tenant ON team_invites(tenant_id);")

    def create_token(self, user: Dict[str, Any], ttl_sec: int = DEFAULT_TOKEN_TTL_SEC) -> str:
        now = int(time.time())
        payload = {
            "sub": user["user_id"],
            "email": user["email"],
            "tenant_id": user["tenant_id"],
            "workspace_name": user.get("workspace_name", user["tenant_id"]),
            "role": user.get("role", "owner"),
            "iat": now,
            "exp": now + int(ttl_sec),
        }
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        secret = _get_signing_secret(self.state_dir)
        sig = hmac.new(secret, f"dx1.{payload_b64}".encode("ascii"), hashlib.sha256).digest()
        return f"dx1.{payload_b64}.{_b64url_encode(sig)}"

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token or not isinstance(token, str):
            return None
        parts = token.strip().split(".")
        if len(parts) != 3 or parts[0] != "dx1":
            return None
        _, payload_b64, sig_b64 = parts
        try:
            secret = _get_signing_secret(self.state_dir)
            expected_sig = hmac.new(secret, f"dx1.{payload_b64}".encode("ascii"), hashlib.sha256).digest()
            actual_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None
            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
            if int(payload.get("exp", 0)) < int(time.time()):
                return None
            if not payload.get("sub") or not payload.get("tenant_id"):
                return None
            return payload
        except Exception:
            return None

    def register_user(
        self,
        email: str,
        password: str,
        workspace_name: Optional[str] = None,
        role: str = "owner",
    ) -> Dict[str, Any]:
        norm_email = str(email or "").strip().lower()
        if not re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", norm_email):
            raise ValueError("Please provide a valid email address.")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        ws_label = (workspace_name or norm_email.split("@")[0]).strip()[:80]
        base_slug = sanitize_tenant_id(ws_label)
        tenant_id = f"ws_{base_slug}_{secrets.token_hex(4)}"
        user_id = f"usr_{secrets.token_hex(8)}"
        pw_hash, salt = hash_password(password)
        now = time.time()

        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO users (user_id, email, password_hash, salt, tenant_id, workspace_name, role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, norm_email, pw_hash, salt, tenant_id, ws_label, role, now),
                )
            except sqlite3.IntegrityError:
                raise ValueError("An account with this email already exists.")

        user_dict = {
            "user_id": user_id,
            "email": norm_email,
            "tenant_id": tenant_id,
            "workspace_name": ws_label,
            "role": role,
            "created_at": now,
        }
        return {
            "user": user_dict,
            "access_token": self.create_token(user_dict),
            "token_type": "bearer",
        }

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        norm_email = str(email or "").strip().lower()
        if not norm_email or not password:
            return None

        now_ts = time.time()
        with _LOGIN_LOCK:
            recent_fails = [t for t in _FAILED_LOGINS.get(norm_email, []) if (now_ts - t) <= _LOGIN_LOCKOUT_WINDOW_SEC]
            if recent_fails:
                _FAILED_LOGINS[norm_email] = recent_fails
            else:
                _FAILED_LOGINS.pop(norm_email, None)
            if len(recent_fails) >= _LOGIN_LOCKOUT_MAX_ATTEMPTS and (now_ts - recent_fails[-1]) < _LOGIN_LOCKOUT_DURATION_SEC:
                return None

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, email, password_hash, salt, tenant_id, workspace_name, role, created_at FROM users WHERE email = ?",
                (norm_email,),
            ).fetchone()

        if not row:
            # Constant-time PBKDF2 work prevents email enumeration timing oracle
            verify_password(password, _DUMMY_PBKDF2_HASH, _DUMMY_PBKDF2_SALT)
            with _LOGIN_LOCK:
                if len(_FAILED_LOGINS) > 2048:
                    _FAILED_LOGINS.clear()
                _FAILED_LOGINS.setdefault(norm_email, []).append(now_ts)
            return None
        if not verify_password(password, row["password_hash"], row["salt"]):
            with _LOGIN_LOCK:
                if len(_FAILED_LOGINS) > 2048:
                    _FAILED_LOGINS.clear()
                _FAILED_LOGINS.setdefault(norm_email, []).append(now_ts)
            return None

        with _LOGIN_LOCK:
            _FAILED_LOGINS.pop(norm_email, None)

        user_dict = {
            "user_id": row["user_id"],
            "email": row["email"],
            "tenant_id": row["tenant_id"],
            "workspace_name": row["workspace_name"],
            "role": row["role"],
            "created_at": row["created_at"],
        }
        return {
            "user": user_dict,
            "access_token": self.create_token(user_dict),
            "token_type": "bearer",
        }

    # -------------------------------------------------------------------------
    # TEAM ROLE-BASED ACCESS CONTROL (RBAC: owner / analyst / viewer)
    # -------------------------------------------------------------------------
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not user_id:
            return None
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, email, tenant_id, workspace_name, role, created_at FROM users WHERE user_id = ?",
                (str(user_id).strip(),),
            ).fetchone()
        return dict(row) if row else None

    def list_workspace_members(self, tenant_id: str) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        now = time.time()
        with self._lock, self._connect() as conn:
            m_rows = conn.execute(
                """
                SELECT user_id, email, tenant_id, workspace_name, role, created_at
                FROM users WHERE tenant_id = ? ORDER BY created_at ASC
                """,
                (norm_tid,),
            ).fetchall()
            i_rows = conn.execute(
                """
                SELECT invite_id, email, role, invited_by, expires_at, created_at
                FROM team_invites
                WHERE tenant_id = ? AND accepted_at IS NULL AND expires_at > ?
                ORDER BY created_at DESC
                """,
                (norm_tid, now),
            ).fetchall()
        return {
            "tenant_id": norm_tid,
            "members": [dict(r) for r in m_rows],
            "pending_invites": [dict(r) for r in i_rows],
        }

    def create_team_invite(
        self,
        tenant_id: str,
        workspace_name: str,
        inviter_email: str,
        target_email: str,
        role: str = "analyst",
    ) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        norm_email = str(target_email or "").strip().lower()
        if not re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", norm_email):
            raise ValueError("Please provide a valid teammate email address.")
        norm_role = normalize_workspace_role(role)

        raw_token = f"dxinv_{secrets.token_urlsafe(24)}"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        invite_id = f"inv_{secrets.token_hex(6)}"
        now = time.time()
        exp = now + INVITE_TTL_SEC

        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT tenant_id FROM users WHERE email = ?", (norm_email,)).fetchone()
            if existing:
                raise ValueError("A user account with this email already exists.")
            conn.execute(
                """
                INSERT INTO team_invites (
                    invite_id, tenant_id, workspace_name, email, role,
                    invited_by, token_hash, expires_at, accepted_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    invite_id, norm_tid, str(workspace_name or norm_tid)[:80],
                    norm_email, norm_role, str(inviter_email or "owner")[:120],
                    token_hash, exp, now,
                ),
            )
        return {
            "status": "invited",
            "invite_id": invite_id,
            "tenant_id": norm_tid,
            "email": norm_email,
            "role": norm_role,
            "invite_token": raw_token,
            "expires_at": exp,
        }

    def accept_team_invite(self, invite_token: str, password: str) -> Dict[str, Any]:
        raw_tok = str(invite_token or "").strip()
        if not raw_tok:
            raise ValueError("Invite token is required.")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        token_hash = hashlib.sha256(raw_tok.encode("utf-8")).hexdigest()
        now = time.time()
        user_id = f"usr_{secrets.token_hex(8)}"
        pw_hash, salt = hash_password(password)

        with self._lock, self._connect() as conn:
            inv = conn.execute(
                "SELECT * FROM team_invites WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            if not inv:
                raise ValueError("Invalid invite token.")
            if inv["accepted_at"] is not None:
                raise ValueError("This invite token has already been used.")
            if float(inv["expires_at"]) < now:
                raise ValueError("This invite token has expired.")

            try:
                conn.execute(
                    """
                    INSERT INTO users (user_id, email, password_hash, salt, tenant_id, workspace_name, role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id, inv["email"], pw_hash, salt,
                        inv["tenant_id"], inv["workspace_name"], inv["role"], now,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError("An account with this email already exists.")
            conn.execute("UPDATE team_invites SET accepted_at = ? WHERE invite_id = ?", (now, inv["invite_id"]))

        user_dict = {
            "user_id": user_id,
            "email": inv["email"],
            "tenant_id": inv["tenant_id"],
            "workspace_name": inv["workspace_name"],
            "role": inv["role"],
            "created_at": now,
        }
        return {
            "user": user_dict,
            "access_token": self.create_token(user_dict),
            "token_type": "bearer",
        }

    def update_member_role(self, tenant_id: str, target_user_id: str, new_role: str) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        norm_role = normalize_workspace_role(new_role)
        with self._lock, self._connect() as conn:
            target = conn.execute(
                "SELECT user_id, email, role FROM users WHERE tenant_id = ? AND user_id = ?",
                (norm_tid, str(target_user_id).strip()),
            ).fetchone()
            if not target:
                raise KeyError("Team member not found in this workspace.")
            if str(target["role"]) == "owner" and norm_role != "owner":
                owners = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM users WHERE tenant_id = ? AND role = 'owner'",
                    (norm_tid,),
                ).fetchone()
                if int(owners["cnt"]) <= 1:
                    raise ValueError("Cannot demote the last remaining workspace Owner.")
            conn.execute(
                "UPDATE users SET role = ? WHERE tenant_id = ? AND user_id = ?",
                (norm_role, norm_tid, str(target_user_id).strip()),
            )
        return {
            "status": "updated",
            "tenant_id": norm_tid,
            "user_id": str(target["user_id"]),
            "email": str(target["email"]),
            "role": norm_role,
        }

    def remove_member(self, tenant_id: str, target_user_id: str) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            target = conn.execute(
                "SELECT user_id, email, role FROM users WHERE tenant_id = ? AND user_id = ?",
                (norm_tid, str(target_user_id).strip()),
            ).fetchone()
            if not target:
                raise KeyError("Team member not found in this workspace.")
            if str(target["role"]) == "owner":
                owners = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM users WHERE tenant_id = ? AND role = 'owner'",
                    (norm_tid,),
                ).fetchone()
                if int(owners["cnt"]) <= 1:
                    raise ValueError("Cannot remove the last remaining workspace Owner.")
            conn.execute(
                "DELETE FROM users WHERE tenant_id = ? AND user_id = ?",
                (norm_tid, str(target_user_id).strip()),
            )
        return {
            "status": "removed",
            "tenant_id": norm_tid,
            "user_id": str(target["user_id"]),
            "email": str(target["email"]),
        }
