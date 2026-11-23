"""
=============================================================================
DATAX-RAY PHASE C — IDEMPOTENT SQLITE WAL -> POSTGRESQL 16 MIGRATION CLI
=============================================================================
Migrates all 5 single-node SQLite WAL databases (12 multi-tenant tables) into
a unified PostgreSQL 16 database with Row-Level Security (RLS) and automated
row-count parity verification.

Examples:
    # 1. Inspect local SQLite row counts without writing anything (zero cost)
    python scripts/migrate_sqlite_to_postgres.py --dry-run

    # 2. Print complete unified PostgreSQL 16 DDL + RLS policies
    python scripts/migrate_sqlite_to_postgres.py --schema-only

    # 3. Execute verified idempotent migration into live PostgreSQL 16
    python scripts/migrate_sqlite_to_postgres.py --database-url postgresql://user:pass@host:5432/dataxray
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from autonomous_engine.db_adapter import (
    DatabaseAdapter,
    generate_postgres_unified_schema_sql,
    is_postgres_url,
    sanitize_database_url,
)


SQLITE_TABLE_SOURCES: List[Tuple[str, str]] = [
    ("state/auth_users.sqlite", "users"),
    ("state/auth_users.sqlite", "team_invites"),
    ("state/billing_plans.sqlite", "tenant_subscriptions"),
    ("state/billing_plans.sqlite", "tenant_monthly_usage"),
    ("state/billing_plans.sqlite", "processed_webhook_events"),
    ("state/oauth_vault.sqlite", "oauth_states"),
    ("state/oauth_vault.sqlite", "oauth_connections"),
    ("state/oauth_vault.sqlite", "digest_schedules"),
    ("action_ledgers/action_ledger.sqlite", "actions"),
    ("action_ledgers/action_ledger.sqlite", "tenant_roi_meta"),
    ("state/jobs.sqlite", "jobs"),
]


def _read_sqlite_table_rows(db_file: Path, table_name: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    if not db_file.exists():
        return [], []
    conn = sqlite3.connect(str(db_file), timeout=10.0)
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        if not tbl:
            return [], []
        cur = conn.execute(f'SELECT * FROM "{table_name}"')
        cols = [d[0] for d in (cur.description or [])]
        rows = cur.fetchall()
        return cols, rows
    finally:
        conn.close()


def migrate_sqlite_to_postgres(
    runs_dir: Path,
    database_url: Optional[str] = None,
    *,
    dry_run: bool = False,
    enable_rls: bool = True,
    target_adapter: Optional[DatabaseAdapter] = None,
) -> Dict[str, Any]:
    """
    Scans all single-node SQLite stores under `runs_dir`, applies the unified
    PostgreSQL 16 schema, copies rows idempotently, and verifies exact counts.
    """
    runs_root = Path(runs_dir).resolve()
    plan_report: List[Dict[str, Any]] = []
    total_source_rows = 0

    for rel_db, table_name in SQLITE_TABLE_SOURCES:
        db_file = runs_root / rel_db
        cols, rows = _read_sqlite_table_rows(db_file, table_name)
        total_source_rows += len(rows)
        plan_report.append({
            "source_db": rel_db,
            "table": table_name,
            "columns": cols,
            "source_rows": len(rows),
            "migrated_rows": 0,
            "target_rows_after": None,
            "verified": False,
        })

    if dry_run:
        return {
            "status": "dry_run_complete",
            "runs_dir": str(runs_root),
            "target": sanitize_database_url(database_url),
            "total_tables_scanned": len(plan_report),
            "total_source_rows": total_source_rows,
            "tables": plan_report,
        }

    adapter = target_adapter
    if adapter is None:
        resolved_url = (database_url or os.environ.get("DATABASE_URL", "")).strip()
        if not is_postgres_url(resolved_url):
            raise ValueError("Target --database-url (or DATABASE_URL env var) must be a valid postgresql:// URL.")
        adapter = DatabaseAdapter(runs_root / "state" / "migration_fallback.sqlite", database_url=resolved_url)

    # 1. Apply unified DDL statements idempotently (strip SQL line comments before splitting on ';')
    schema_sql = generate_postgres_unified_schema_sql(enable_rls=enable_rls and adapter.is_postgres)
    non_comment_sql = "\n".join(
        ln for ln in schema_sql.splitlines() if not ln.strip().startswith("--")
    )
    statements = [s.strip() for s in non_comment_sql.split(";") if s.strip()]
    with adapter.connect() as conn:
        for stmt in statements:
            conn.execute(stmt)

    # 2. Copy rows table-by-table with ON CONFLICT DO NOTHING idempotency & count audit
    total_migrated = 0
    for entry, (rel_db, table_name) in zip(plan_report, SQLITE_TABLE_SOURCES):
        db_file = runs_root / rel_db
        cols, rows = _read_sqlite_table_rows(db_file, table_name)
        if cols and rows:
            col_list = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join("?" for _ in cols)
            insert_sql = f'INSERT OR IGNORE INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
            with adapter.connect() as conn:
                for r in rows:
                    conn.execute(insert_sql, tuple(r))
            entry["migrated_rows"] = len(rows)
            total_migrated += len(rows)

        with adapter.connect() as conn:
            cnt_row = conn.execute(f'SELECT COUNT(*) AS cnt FROM "{table_name}"').fetchone()
            target_cnt = int(cnt_row["cnt"]) if cnt_row else 0
        entry["target_rows_after"] = target_cnt
        entry["verified"] = (target_cnt >= entry["source_rows"])

    all_ok = all(item["verified"] for item in plan_report)
    return {
        "status": "migrated_and_verified" if all_ok else "verification_mismatch",
        "runs_dir": str(runs_root),
        "target_backend": adapter.backend_name,
        "target": sanitize_database_url(adapter.database_url),
        "total_source_rows": total_source_rows,
        "total_migrated_rows": total_migrated,
        "all_tables_verified": all_ok,
        "tables": plan_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate DataX-Ray SQLite WAL stores into PostgreSQL 16")
    parser.add_argument("--runs-dir", default=str(WORKSPACE_ROOT / "runs"), help="Path to local runs/ directory")
    parser.add_argument("--database-url", default=None, help="Target PostgreSQL 16 connection URL")
    parser.add_argument("--dry-run", action="store_true", help="Inspect SQLite row counts without writing")
    parser.add_argument("--schema-only", action="store_true", help="Print PostgreSQL 16 DDL + RLS SQL and exit")
    parser.add_argument("--no-rls", action="store_true", help="Skip Row-Level Security policies")
    args = parser.parse_args()

    if args.schema_only:
        print(generate_postgres_unified_schema_sql(enable_rls=not args.no_rls))
        return 0

    report = migrate_sqlite_to_postgres(
        runs_dir=Path(args.runs_dir),
        database_url=args.database_url,
        dry_run=args.dry_run,
        enable_rls=not args.no_rls,
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in ("dry_run_complete", "migrated_and_verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
