"""
=============================================================================
ENTERPRISE PIPELINE RUN MANAGER & METADATA AUDIT CATALOG
=============================================================================
Solves Autopsy Flaw #3: Ephemeral State & Race Conditions.
Guarantees:
1. Isolated Run Environments: Every execution is housed in a dedicated,
   immutable run workspace (`runs/<run_id>/`).
2. Multi-tenant Safety: Eliminates race conditions and file collisions.
3. Persistent Audit Ledger: Logs execution telemetry, assertion gate statuses,
   and operational friction metrics into an SQLite catalog + JSON manifest.
4. Comprehensive Lineage: Stores schema topology, blueprints, generated scripts,
   and deliverables per run for full compliance and auditability.
=============================================================================
"""

import os
import sys
import re
import uuid
import time
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class RunManager:
    """
    Manages run lifecycle, isolated file staging, and persistent metadata cataloging.
    """
    def __init__(self, dataset_name: str = "Dataset", base_runs_dir: str = "runs"):
        self.dataset_name = dataset_name
        self.timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_slug = re.sub(r'[^a-z0-9_]+', '_', str(dataset_name).lower()).strip('_') or "dataset"
        uniq_tag = f"{os.getpid()}_{uuid.uuid4().hex[:6]}"
        self.run_id = f"run_{self.timestamp_str}_{uniq_tag}_{safe_slug}"
        
        self.base_runs_dir = Path(base_runs_dir).resolve()
        self.run_dir = self.base_runs_dir / self.run_id
        self.artifacts_dir = self.run_dir / "artifacts"
        self.logs_dir = self.run_dir / "logs"
        
        # Create run directories
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.base_runs_dir / "execution_catalog.db"
        self._init_sqlite_catalog()
        
        self.stage_timings = {}
        self.start_time = time.time()
        
    def _init_sqlite_catalog(self):
        """Initializes SQLite catalog schema if not already present."""
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                dataset_name TEXT,
                start_timestamp TEXT,
                end_timestamp TEXT,
                total_duration_sec REAL,
                status TEXT,
                initial_rows INTEGER,
                final_fact_rows INTEGER,
                cartesian_drift INTEGER,
                duplicate_ids INTEGER,
                assertion_status TEXT,
                domain_invariants_status TEXT,
                run_directory TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stage_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                stage_number INTEGER,
                stage_name TEXT,
                duration_sec REAL,
                status TEXT,
                details TEXT,
                FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
            );
        """)
        conn.commit()
        conn.close()

    def get_artifact_path(self, filename: str) -> str:
        """Returns an absolute path inside this run's isolated artifacts directory."""
        return str((self.artifacts_dir / filename).resolve())

    def log_stage_telemetry(
        self,
        stage_num: int,
        stage_name: str,
        duration_sec: float,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None
    ):
        """Records stage performance telemetry into SQLite catalog."""
        self.stage_timings[f"stage_{stage_num}"] = duration_sec
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO stage_telemetry (run_id, stage_number, stage_name, duration_sec, status, details)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            self.run_id, stage_num, stage_name, duration_sec, status,
            json.dumps(details or {}, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

    def finalize_run(
        self,
        status: str = "COMPLETED",
        initial_rows: int = 0,
        final_fact_rows: int = 0,
        cartesian_drift: int = 0,
        duplicate_ids: int = 0,
        assertion_status: str = "PASSED",
        domain_invariants_status: str = "PASSED"
    ) -> Dict[str, Any]:
        """Finalizes run records in SQLite and writes immutable run_manifest.json."""
        total_duration = round(time.time() - self.start_time, 2)
        end_time_str = datetime.datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO pipeline_runs (
                run_id, dataset_name, start_timestamp, end_timestamp,
                total_duration_sec, status, initial_rows, final_fact_rows,
                cartesian_drift, duplicate_ids, assertion_status,
                domain_invariants_status, run_directory
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            self.run_id, self.dataset_name, self.timestamp_str, end_time_str,
            total_duration, status, initial_rows, final_fact_rows,
            cartesian_drift, duplicate_ids, assertion_status,
            domain_invariants_status, str(self.run_dir)
        ))
        conn.commit()
        conn.close()
        
        manifest = {
            "run_id": self.run_id,
            "dataset_name": self.dataset_name,
            "start_time": self.timestamp_str,
            "end_time": end_time_str,
            "total_duration_sec": total_duration,
            "status": status,
            "metrics": {
                "initial_rows": initial_rows,
                "final_fact_rows": final_fact_rows,
                "cartesian_drift": cartesian_drift,
                "duplicate_ids": duplicate_ids,
                "assertion_status": assertion_status,
                "domain_invariants_status": domain_invariants_status
            },
            "stage_timings": self.stage_timings,
            "run_directory": str(self.run_dir),
            "artifacts": [f.name for f in self.artifacts_dir.iterdir()]
        }
        
        manifest_path = self.run_dir / "run_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
            
        return manifest

if __name__ == "__main__":
    print("[*] Testing Enterprise Run Manager & Audit Catalog...")
    mgr = RunManager(dataset_name="Test_Dataset")
    print(f"[+] Initialized isolated run workspace: {mgr.run_id}")
    print(f"    - Artifacts dir: {mgr.artifacts_dir}")
    print(f"    - Database ledger: {mgr.db_path}")
    mgr.log_stage_telemetry(1, "Topology Profiler", 0.42, "SUCCESS", {"tables": 5})
    manifest = mgr.finalize_run(
        status="PASSED", initial_rows=10000, final_fact_rows=10000,
        cartesian_drift=0, duplicate_ids=0, assertion_status="PASSED",
        domain_invariants_status="PASSED"
    )
    print(f"[+] Run finalized with manifest: {manifest['run_id']} ({manifest['total_duration_sec']}s)")
