"""
Step A + Step B Permanent Regression & Security Gate Suite:
  1. Database Fortress: PRAGMA foreign_keys=ON, idempotent schema_migrations,
     atomic WAL-safe online backup_sqlite() with rotation, check_integrity(),
     backup_all_workspace_databases(), and 10-thread concurrent write resilience.
  2. Ugly Indian MSME Data Resilience:
     - Tally/Vyapar "₹1,24,500/-" & "Rs. 45,000/-" currency string parsing with Hindi headers
     - 0-row empty CSV fast-fail at Stage 1
     - OWASP CWE-1236 CSV formula-injection neutralization harmonized with Anti-Hallucination Guard lineage
  3. Production Docker Security Config:
     - docker-compose defaults DATAXRAY_REQUIRE_AUTH:-true
     - Dockerfile bundles enterprise_showcase_data/ & required run state directories
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pytest

from autonomous_engine.db_adapter import (
    DBIntegrityError,
    DatabaseAdapter,
    backup_all_workspace_databases,
)
from autonomous_engine.master_orchestrator import run_master_pipeline
from autonomous_engine.robust_csv_sniffer import normalize_european_decimal_columns

WS = Path(__file__).resolve().parents[1]


def test_database_fortress_fk_migrations_backup_and_concurrency(tmp_path: Path):
    db_file = tmp_path / "runs" / "state" / "fortress_test.sqlite"
    adapter = DatabaseAdapter(db_file, database_url="")

    # 1. PRAGMA foreign_keys=ON enforced on every connection
    with adapter.connect() as conn:
        fk_val = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_val == 1
        conn.execute("CREATE TABLE parents (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE children (id TEXT PRIMARY KEY, parent_id TEXT NOT NULL REFERENCES parents(id))")
        conn.execute("INSERT INTO parents (id) VALUES (?)", ("p1",))
        conn.execute("INSERT INTO children (id, parent_id) VALUES (?, ?)", ("c1", "p1"))

    with pytest.raises(DBIntegrityError):
        with adapter.connect() as conn:
            conn.execute("INSERT INTO children (id, parent_id) VALUES (?, ?)", ("c_orphan", "nonexistent_parent"))

    # 2. Idempotent schema_migrations versioning
    assert adapter.ensure_schema_version("v1_init", "Initial tables") is True
    assert adapter.ensure_schema_version("v1_init", "Duplicate should no-op") is False
    assert adapter.ensure_schema_version("v2_indexes", "Added composite indexes") is True
    vers = adapter.get_schema_versions()
    assert [v["version"] for v in vers] == ["v1_init", "v2_indexes"]

    # 3. Physical integrity check + atomic online backup & rotation
    chk = adapter.check_integrity()
    assert chk["healthy"] is True
    assert chk["foreign_key_violations"] == 0

    b_dir = tmp_path / "backups"
    snaps = []
    for _ in range(4):
        snaps.append(adapter.backup_sqlite(backup_dir=b_dir, keep_last=2))
        time.sleep(0.02)
    remaining = list(b_dir.glob("fortress_test_*.sqlite.bak"))
    assert len(remaining) == 2

    # 4. Workspace-wide multi-DB backup helper
    ws_bk = backup_all_workspace_databases(tmp_path, keep_last=2)
    assert ws_bk["databases_checked"] >= 1
    assert ws_bk["all_healthy"] is True

    # 5. 10-thread concurrent write resilience (0 'database is locked' errors)
    with adapter.connect() as conn:
        conn.execute("CREATE TABLE kv_stress (k TEXT PRIMARY KEY, v INTEGER)")

    def _write_worker(i: int) -> bool:
        for j in range(5):
            with adapter.connect() as c:
                c.execute("INSERT OR REPLACE INTO kv_stress (k, v) VALUES (?, ?)", (f"t{i}_{j}", i * 10 + j))
        return True

    with ThreadPoolExecutor(max_workers=10) as pool:
        assert all(pool.map(_write_worker, range(10)))
    with adapter.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM kv_stress").fetchone()[0] == 50


def test_indian_msme_rupee_suffix_parsing_and_hindi_headers(tmp_path: Path):
    df = pd.DataFrame({
        "रकम_INR": ["₹1,24,500/-", "₹45,000/-", "Rs. 12,350.50", None, "₹8,999/-"],
        "usd_fee": ["$1,200.50", "$450.00", "$99.99", "$10.00", "$5.25"],
        "city": ["कानपुर", "लखनऊ", "जयपुर", "दिल्ली", "सूरत"],
    })
    out = normalize_european_decimal_columns(df.copy())
    assert pd.api.types.is_numeric_dtype(out["रकम_INR"])
    assert abs(float(out["रकम_INR"].iloc[0]) - 124500.0) < 1e-6
    assert abs(float(out["रकम_INR"].iloc[2]) - 12350.5) < 1e-6
    assert pd.api.types.is_numeric_dtype(out["usd_fee"])
    assert abs(float(out["usd_fee"].iloc[0]) - 1200.5) < 1e-6
    assert out.attrs.get("_detected_currency_hints", {}).get("रकम_INR") == "INR"

    # End-to-end: messy MSME Tally sheet with 33% blank amounts + ₹/- + Hindi headers MUST still detect रकम_INR as ₹ monetary ledger!
    from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
    rng = np.random.default_rng(7)
    n5 = 60
    df_msme = normalize_european_decimal_columns(pd.DataFrame({
        "बिल_नंबर": [f"INV-{i}" for i in range(n5)],
        "ग्राहक_शहर": rng.choice(["कानपुर", "लखनऊ", "जयपुर"], n5),
        "रकम_INR": [f"₹{rng.integers(1, 9)},{rng.integers(10, 99)},{rng.integers(100, 999)}/-" if i % 3 else None for i in range(n5)],
        "is_returned": rng.integers(0, 2, n5),
    }))
    resolved = resolve_canonical_target_and_cost(df_msme, region_profile="IN")
    assert resolved["cost_col"] == "रकम_INR"
    assert resolved["is_financial"] is True
    assert resolved["unit_symbol"] == "₹"


def test_empty_0_row_fast_fail_and_csv_formula_injection_lineage(tmp_path: Path):
    # 1. Empty 0-row CSV fails fast at Stage 1 without crashing
    raw0, out0, cache0 = tmp_path / "r0", tmp_path / "o0", tmp_path / "c0"
    raw0.mkdir(); out0.mkdir(); cache0.mkdir()
    pd.DataFrame(columns=["order_id", "city", "amount", "is_rto"]).to_csv(raw0 / "empty.csv", index=False)
    t0 = time.time()
    ok0 = run_master_pipeline(str(raw0), str(out0), str(cache0), mode="deterministic", region_profile="IN")
    assert ok0 is False
    assert (time.time() - t0) < 10.0

    # 2. CSV Formula Injection payload passes Anti-Hallucination Guard AND stays Excel-safe!
    rng = np.random.default_rng(11)
    raw1, out1, cache1 = tmp_path / "r1", tmp_path / "o1", tmp_path / "c1"
    raw1.mkdir(); out1.mkdir(); cache1.mkdir()
    df_inj = pd.DataFrame({
        "order_id": ["=CMD|' /C calc'!A0" if i == 0 else f"ORD-{i:04d}" for i in range(120)],
        "vendor": ["+SUM(1+1)" if i < 25 else "SafeVendor" for i in range(120)],
        "amount": rng.uniform(500, 3000, 120).round(2),
        "is_rto": [1 if i < 25 else 0 for i in range(120)],
    })
    df_inj.to_csv(raw1 / "orders.csv", index=False)
    ok1 = run_master_pipeline(str(raw1), str(out1), str(cache1), mode="deterministic", region_profile="IN")
    assert ok1 is True
    wl_csv = (out1 / "actionable_priority_worklist.csv").read_text(encoding="utf-8")
    # Ensure formula payload is safely prefixed with apostrophe in exported CSV
    assert "'=CMD|" in wl_csv or "'+SUM(" in wl_csv


def test_docker_production_security_and_assets_config():
    dockerfile = (WS / "Dockerfile").read_text(encoding="utf-8")
    compose = (WS / "docker-compose.yml").read_text(encoding="utf-8")
    assert "COPY enterprise_showcase_data/" in dockerfile
    assert "/app/runs/decision_outcomes" in dockerfile
    assert "/app/runs/i18n_cache" in dockerfile
    assert "/app/runs/backups" in dockerfile
    assert "DATAXRAY_REQUIRE_AUTH:-true" in compose
