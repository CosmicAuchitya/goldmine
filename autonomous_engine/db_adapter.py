"""
=============================================================================
DATAX-RAY PHASE C — DUAL-DRIVER DATABASE ADAPTER (SQLITE WAL <-> POSTGRESQL 16)
=============================================================================
Provides zero-config offline parity with seamless horizontal cloud scaling:
- When `DATABASE_URL` is unset (or starts with `sqlite://`): uses local SQLite
  WAL mode (`PRAGMA journal_mode=WAL; synchronous=NORMAL`) — zero external DB!
- When `DATABASE_URL` starts with `postgresql://` or `postgres://`: connects
  to PostgreSQL 16 (via `psycopg` v3 pool or `psycopg2`), automatically:
  1. Translates SQLite `?` placeholders -> PostgreSQL `%s` (quote-aware).
  2. Translates `INSERT OR IGNORE INTO` -> `INSERT INTO ... ON CONFLICT DO NOTHING`.
  3. Translates `REAL` DDL types -> `DOUBLE PRECISION` and skips `PRAGMA` calls.
  4. Normalizes unique-constraint violations into `DBIntegrityError` (a subclass
     of `sqlite3.IntegrityError`) so existing callers work identically on both.
  5. Returns dict-accessible rows (`row["col"]`) identically on both drivers.
- Also provides `generate_postgres_unified_schema_sql()` emitting all 12
  multi-tenant tables, composite indexes, and Row-Level Security (RLS) policies.
=============================================================================
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


class DBIntegrityError(sqlite3.IntegrityError):
    """Unified integrity/unique-constraint exception compatible with sqlite3.IntegrityError."""


def is_postgres_url(url: Optional[str]) -> bool:
    u = str(url or "").strip().lower()
    return u.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))


def sanitize_database_url(url: Optional[str]) -> str:
    """Masks username/password before logging or exposing in cloud-status endpoints."""
    raw = str(url or "").strip()
    if not raw:
        return "sqlite_wal://local"
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.hostname or "localhost"
        port = f":{parsed.port}" if parsed.port else ""
        path = parsed.path or ""
        return f"{parsed.scheme}://***:***@{host}{port}{path}"
    except Exception:
        return "postgresql://***"


def translate_sql_for_postgres(sql: str, has_params: bool = True) -> Optional[str]:
    """
    Translates SQLite-dialect SQL into PostgreSQL 16 SQL safely (quote-aware):
    - Returns None for SQLite-only PRAGMA statements (caller treats as no-op).
    - Escapes literal `%` as `%%` when parameterized execution is used.
    - Converts unquoted `?` parameter placeholders into `%s`.
    - Rewrites `INSERT OR IGNORE INTO ...` into `INSERT INTO ... ON CONFLICT DO NOTHING`.
    - Converts standalone `REAL` column types in CREATE TABLE statements to `DOUBLE PRECISION`.
    """
    stripped = str(sql or "").strip()
    if not stripped:
        return None
    if re.match(r"^PRAGMA\b", stripped, flags=re.IGNORECASE):
        return None

    # Rewrite INSERT OR IGNORE INTO -> INSERT INTO ... ON CONFLICT DO NOTHING
    is_insert_ignore = bool(re.match(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", stripped, flags=re.IGNORECASE))
    if is_insert_ignore:
        stripped = re.sub(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", stripped, count=1, flags=re.IGNORECASE)

    # Convert REAL column type in CREATE TABLE DDL to DOUBLE PRECISION
    if re.match(r"^CREATE\s+TABLE\b", stripped, flags=re.IGNORECASE):
        stripped = re.sub(r"\bREAL\b", "DOUBLE PRECISION", stripped)

    # Quote-aware scan for `?` -> `%s` and literal `%` -> `%%`
    out_chars: List[str] = []
    in_single = False
    in_double = False
    i = 0
    n = len(stripped)
    while i < n:
        ch = stripped[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < n and stripped[i + 1] == "'":
                out_chars.append("''")
                i += 2
                continue
            in_single = not in_single
            out_chars.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out_chars.append(ch)
        elif ch == "%" and has_params:
            out_chars.append("%%")
        elif ch == "?" and not in_single and not in_double:
            out_chars.append("%s")
        else:
            out_chars.append(ch)
        i += 1

    pg_sql = "".join(out_chars)
    if is_insert_ignore and "ON CONFLICT" not in pg_sql.upper():
        pg_sql = pg_sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return pg_sql


class _NoOpCursor:
    rowcount: int = 0

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> List[Any]:
        return []


class _CompatCursor:
    """Wraps a DB-API cursor so rows always support dict-style key lookup and `dict(row)`."""

    def __init__(self, cursor: Any, is_postgres: bool = False):
        self._cur = cursor
        self._is_pg = is_postgres

    @property
    def rowcount(self) -> int:
        return int(getattr(self._cur, "rowcount", 0) or 0)

    def _wrap_row(self, row: Any) -> Any:
        if row is None:
            return None
        if isinstance(row, (dict, sqlite3.Row)):
            return row
        desc = getattr(self._cur, "description", None)
        if desc and isinstance(row, (tuple, list)):
            return {col[0]: row[idx] for idx, col in enumerate(desc)}
        return row

    def fetchone(self) -> Any:
        return self._wrap_row(self._cur.fetchone())

    def fetchall(self) -> List[Any]:
        return [self._wrap_row(r) for r in self._cur.fetchall()]


class CompatConnection:
    """Context-managed DB connection providing identical `.execute(sql, params)` on SQLite & PostgreSQL."""

    def __init__(self, raw_conn: Any, is_postgres: bool = False, release_fn: Optional[Callable[[Any], None]] = None):
        self._conn = raw_conn
        self._is_pg = is_postgres
        self._release_fn = release_fn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        if not self._is_pg:
            try:
                return self._conn.execute(sql, params)
            except sqlite3.IntegrityError as ie:
                raise DBIntegrityError(str(ie)) from ie

        pg_sql = translate_sql_for_postgres(sql, has_params=bool(params))
        if pg_sql is None:
            return _NoOpCursor()
        cur = self._conn.cursor()
        try:
            if params:
                cur.execute(pg_sql, tuple(params))
            else:
                cur.execute(pg_sql)
            return _CompatCursor(cur, is_postgres=True)
        except Exception as exc:
            cls_name = exc.__class__.__name__.lower()
            if "unique" in cls_name or "integrity" in cls_name or "duplicate key" in str(exc).lower():
                raise DBIntegrityError(str(exc)) from exc
            raise

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._release_fn is not None:
            self._release_fn(self._conn)
        else:
            self._conn.close()

    def __enter__(self) -> "CompatConnection":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self.close()
        return False


class DatabaseAdapter:
    """
    Unified Phase C Database Adapter:
    - Uses local SQLite WAL when `DATABASE_URL` is unset (zero cloud spend / zero config).
    - Switches automatically to PostgreSQL 16 when `DATABASE_URL=postgresql://...` is provided.
    - Supports injectable `pg_connect_fn` for deterministic offline PostgreSQL-dialect testing.
    """

    def __init__(
        self,
        sqlite_path: Path,
        database_url: Optional[str] = None,
        pg_connect_fn: Optional[Callable[[str], Any]] = None,
    ):
        self.sqlite_path = Path(sqlite_path).resolve()
        env_url = os.environ.get("DATABASE_URL", "").strip()
        resolved_url = (database_url if database_url is not None else env_url).strip()
        self.database_url = resolved_url
        self.is_postgres = is_postgres_url(resolved_url)
        self._pg_connect_fn = pg_connect_fn
        self._pool: Any = None
        self._pool_lock = threading.Lock()
        if not self.is_postgres:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "postgresql" if self.is_postgres else "sqlite_wal"

    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "target": sanitize_database_url(self.database_url) if self.is_postgres else str(self.sqlite_path.name),
            "rls_supported": self.is_postgres,
            "horizontal_multi_pod_ready": self.is_postgres,
        }

    def _open_pg_connection(self) -> Tuple[Any, Optional[Callable[[Any], None]]]:
        if self._pg_connect_fn is not None:
            return self._pg_connect_fn(self.database_url), None

        # Prefer psycopg v3 (with ConnectionPool if psycopg_pool is installed)
        try:
            import psycopg
            from psycopg.rows import dict_row

            try:
                from psycopg_pool import ConnectionPool

                with self._pool_lock:
                    if self._pool is None:
                        self._pool = ConnectionPool(
                            conninfo=self.database_url,
                            min_size=1,
                            max_size=int(os.environ.get("DATAXRAY_PG_POOL_MAX", "20") or 20),
                            kwargs={"row_factory": dict_row},
                        )
                conn = self._pool.getconn()
                return conn, self._pool.putconn
            except ImportError:
                return psycopg.connect(self.database_url, row_factory=dict_row), None
        except ImportError:
            pass

        # Fallback to psycopg2
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor), None
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is set to PostgreSQL, but neither 'psycopg' nor 'psycopg2' is installed. "
                "Install with: pip install 'psycopg[binary,pool]'"
            ) from exc

    def connect(self) -> CompatConnection:
        if self.is_postgres:
            raw_conn, release_fn = self._open_pg_connection()
            return CompatConnection(raw_conn, is_postgres=True, release_fn=release_fn)

        conn = sqlite3.connect(str(self.sqlite_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return CompatConnection(conn, is_postgres=False)


# =============================================================================
# UNIFIED POSTGRESQL 16 PRODUCTION SCHEMA + ROW-LEVEL SECURITY (12 TABLES)
# =============================================================================
TENANT_SCOPED_TABLES = (
    "users",
    "team_invites",
    "tenant_subscriptions",
    "tenant_monthly_usage",
    "oauth_states",
    "oauth_connections",
    "digest_schedules",
    "actions",
    "tenant_roi_meta",
    "jobs",
    "decision_commitments",
)


def generate_postgres_unified_schema_sql(enable_rls: bool = True) -> str:
    """
    Emits complete idempotent PostgreSQL 16 DDL for all 12 DataX-Ray control-plane tables,
    composite multi-tenant indexes, and optional PostgreSQL Row-Level Security (RLS) policies.
    """
    ddl = """-- =============================================================================
-- DATAX-RAY PHASE C — UNIFIED POSTGRESQL 16 MULTI-TENANT SCHEMA (12 TABLES)
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workspace_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner',
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

CREATE TABLE IF NOT EXISTS team_invites (
    invite_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    invited_by TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    accepted_at DOUBLE PRECISION,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invites_tenant ON team_invites(tenant_id);

CREATE TABLE IF NOT EXISTS tenant_subscriptions (
    tenant_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'active',
    provider TEXT NOT NULL DEFAULT 'none',
    external_customer_id TEXT,
    external_subscription_id TEXT,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_monthly_usage (
    tenant_id TEXT NOT NULL,
    month_key TEXT NOT NULL,
    runs_used INTEGER NOT NULL DEFAULT 0,
    qa_used INTEGER NOT NULL DEFAULT 0,
    rows_audited INTEGER NOT NULL DEFAULT 0,
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (tenant_id, month_key)
);

CREATE TABLE IF NOT EXISTS processed_webhook_events (
    event_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    event_type TEXT NOT NULL,
    tenant_id TEXT,
    processed_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_states (
    state_token TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    extra_json TEXT NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS oauth_connections (
    tenant_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    account_label TEXT,
    encrypted_credentials TEXT NOT NULL,
    scopes TEXT,
    connected_by TEXT,
    status TEXT NOT NULL DEFAULT 'connected',
    expires_at DOUBLE PRECISION,
    last_synced_at DOUBLE PRECISION,
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (tenant_id, provider)
);

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
    next_run_at DOUBLE PRECISION NOT NULL,
    last_run_at DOUBLE PRECISION,
    last_status TEXT,
    created_by TEXT,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sched_tenant ON digest_schedules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sched_due ON digest_schedules(enabled, next_run_at);

CREATE TABLE IF NOT EXISTS actions (
    tenant_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    queue TEXT NOT NULL,
    risk_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    monetary_exposure DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    assigned_to TEXT NOT NULL DEFAULT 'Executive Triage Team',
    currency_symbol TEXT NOT NULL DEFAULT '$',
    created_at DOUBLE PRECISION NOT NULL,
    reconciled INTEGER NOT NULL DEFAULT 0,
    reconciled_status TEXT,
    saved_capital DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provisional_savings DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    PRIMARY KEY (tenant_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_actions_tenant_run ON actions(tenant_id, run_id);
CREATE INDEX IF NOT EXISTS idx_actions_run ON actions(run_id);

CREATE TABLE IF NOT EXISTS tenant_roi_meta (
    tenant_id TEXT PRIMARY KEY,
    currency_symbol TEXT NOT NULL DEFAULT '$',
    estimated_subscription_cost DOUBLE PRECISION NOT NULL DEFAULT 99.0,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_root TEXT NOT NULL,
    mode TEXT NOT NULL,
    region_profile TEXT NOT NULL,
    language TEXT NOT NULL,
    target_override TEXT,
    cost_override TEXT,
    status TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    progress_pct INTEGER NOT NULL DEFAULT 0,
    created_at DOUBLE PRECISION NOT NULL,
    started_at DOUBLE PRECISION,
    completed_at DOUBLE PRECISION,
    error TEXT,
    result_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default_tenant',
    dataset_name TEXT,
    status TEXT NOT NULL,
    started_at DOUBLE PRECISION NOT NULL,
    completed_at DOUBLE PRECISION,
    total_rows INTEGER DEFAULT 0,
    drift_rows INTEGER DEFAULT 0,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS decision_commitments (
    commitment_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    baseline_run_id TEXT NOT NULL,
    decision_label_en TEXT NOT NULL,
    decision_label_hi TEXT NOT NULL,
    decision_specs_json TEXT NOT NULL,
    verdict_code TEXT NOT NULL,
    predicted_before_rate_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    predicted_after_rate_pct DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    predicted_net_impact DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    predicted_ci_low DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    predicted_ci_high DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    predicted_benefit_prob_pct DOUBLE PRECISION NOT NULL DEFAULT 50.0,
    confidence_score INTEGER NOT NULL DEFAULT 50,
    implementation_cost DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    unit_symbol TEXT NOT NULL DEFAULT '$',
    is_monetary INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'COMMITTED',
    created_at DOUBLE PRECISION NOT NULL,
    verified_at DOUBLE PRECISION,
    actual_run_id TEXT,
    actual_baseline_scope_rate_pct DOUBLE PRECISION,
    actual_observed_rate_pct DOUBLE PRECISION,
    actual_net_impact DOUBLE PRECISION,
    actual_affected_records INTEGER,
    execution_compliance_pct DOUBLE PRECISION,
    calibration_hit_ci95 INTEGER,
    accuracy_score_pct DOUBLE PRECISION,
    verification_note_en TEXT,
    verification_note_hi TEXT
);
CREATE INDEX IF NOT EXISTS idx_dc_tenant_created ON decision_commitments(tenant_id, created_at DESC);
"""
    if enable_rls:
        rls_lines = [
            "",
            "-- =============================================================================",
            "-- MULTI-TENANT ROW-LEVEL SECURITY (RLS) DEFENSE-IN-DEPTH POLICIES",
            "-- Set per-session tenant context via: SET LOCAL app.current_tenant = '<tid>';",
            "-- =============================================================================",
        ]
        for tbl in TENANT_SCOPED_TABLES:
            rls_lines.append(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
            rls_lines.append(f"DROP POLICY IF EXISTS tenant_isolation_{tbl} ON {tbl};")
            rls_lines.append(
                f"CREATE POLICY tenant_isolation_{tbl} ON {tbl} "
                f"USING (current_setting('app.current_tenant', true) IN ('*', '') "
                f"OR tenant_id = current_setting('app.current_tenant', true));"
            )
        ddl += "\n".join(rls_lines) + "\n"
    return ddl
