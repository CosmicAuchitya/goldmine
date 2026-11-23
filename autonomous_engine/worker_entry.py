"""
=============================================================================
DATAX-RAY PHASE C — HORIZONTAL STATELESS RQ WORKER ENTRYPOINT
=============================================================================
Runs on dedicated worker containers (`docker-compose.cloud.yml`) listening to
prioritized Redis RQ queues (`high`, `default`, `bulk`):
1. Downloads raw tenant files from S3/R2 (or local storage) into ephemeral
   `/tmp/dx_worker_<job_id>/raw_data`.
2. Executes the full 7-stage deterministic DuckDB pipeline (`run_master_pipeline`)
   plus Anti-Hallucination Guard verification.
3. Uploads all generated artifacts (`bi_ready_fact.parquet`, bespoke dashboard,
   priority worklist, semantic model, ranked leaks) back to S3/R2.
4. Persists final job status in PostgreSQL (via `DatabaseAdapter`) and broadcasts
   live stage progress via Redis Pub/Sub (`DistributedQueueBackend`).
5. Always wipes ephemeral `/tmp` scratch in `finally:` for zero PII retention.

Usage in Cloud Container:
    python -m autonomous_engine.worker_entry --queues high default bulk
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from .db_adapter import DatabaseAdapter
    from .storage_backend import StorageBackend, build_storage_backend
    from .queue_backend import DistributedQueueBackend
except ImportError:
    from db_adapter import DatabaseAdapter
    from storage_backend import StorageBackend, build_storage_backend
    from queue_backend import DistributedQueueBackend


WORKSPACE_ROOT = Path.cwd().resolve()


def _update_job_row(
    db: DatabaseAdapter,
    job_id: str,
    status: str,
    stage: str,
    progress_pct: int,
    started_at: Optional[float] = None,
    completed_at: Optional[float] = None,
    error: Optional[str] = None,
    result_obj: Optional[Dict[str, Any]] = None,
) -> None:
    res_json = json.dumps(result_obj, default=str) if result_obj is not None else None
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                current_stage = ?,
                progress_pct = ?,
                started_at = COALESCE(?, started_at),
                completed_at = COALESCE(?, completed_at),
                error = ?,
                result_json = COALESCE(?, result_json)
            WHERE job_id = ?
            """,
            (status, stage, int(progress_pct), started_at, completed_at, error, res_json, job_id),
        )


def execute_pipeline_job_task(
    job_spec: Dict[str, Any],
    *,
    db_adapter: Optional[DatabaseAdapter] = None,
    storage: Optional[StorageBackend] = None,
    queue_backend: Optional[DistributedQueueBackend] = None,
    pipeline_runner: Optional[Callable[..., bool]] = None,
) -> Dict[str, Any]:
    """
    Executes a single DataX-Ray analysis job inside a stateless worker process.
    Accepts injectable db_adapter, storage, queue_backend, and pipeline_runner for
    deterministic testing without live cloud credentials.
    """
    job_id = str(job_spec["job_id"])
    tenant_id = str(job_spec.get("tenant_id") or "default_tenant")
    mode = str(job_spec.get("mode") or "templated")
    region_profile = str(job_spec.get("region_profile") or "US")
    target_override = job_spec.get("target_override")
    cost_override = job_spec.get("cost_override")
    remote_prefix = str(job_spec.get("remote_prefix") or f"tenants/{tenant_id}/runs/{job_id}")

    db = db_adapter or DatabaseAdapter(WORKSPACE_ROOT / "runs" / "state" / "jobs.sqlite")
    store = storage or build_storage_backend(WORKSPACE_ROOT)
    q_bus = queue_backend or DistributedQueueBackend()

    if pipeline_runner is None:
        try:
            from .master_orchestrator import run_master_pipeline as _runner
        except ImportError:
            from master_orchestrator import run_master_pipeline as _runner
        pipeline_runner = _runner

    t0 = time.time()
    scratch_root = Path(tempfile.mkdtemp(prefix=f"dx_worker_{job_id}_")).resolve()
    raw_dir = scratch_root / "raw_data"
    out_dir = scratch_root / "output"
    cache_dir = scratch_root / "cache"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    def _emit(st: str, stage: str, pct: int, err: Optional[str] = None, res: Optional[Dict[str, Any]] = None) -> None:
        comp = time.time() if st in ("COMPLETED", "FAILED") else None
        try:
            _update_job_row(db, job_id, st, stage, pct, started_at=t0, completed_at=comp, error=err, result_obj=res)
        except Exception:
            pass
        q_bus.publish_job_event(
            job_id,
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "status": st,
                "current_stage": stage,
                "progress_pct": pct,
                "error": err,
                "timestamp": time.time(),
            },
        )

    try:
        _emit("PROCESSING", "DOWNLOADING_RAW_INPUTS", 10)
        downloaded = store.sync_dir_down(f"{remote_prefix}/raw_data", raw_dir)
        if downloaded == 0 and job_spec.get("local_raw_dir"):
            src_local = Path(str(job_spec["local_raw_dir"]))
            if src_local.exists():
                for f in src_local.rglob("*"):
                    if f.is_file():
                        dest = raw_dir / f.relative_to(src_local)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dest)
                        downloaded += 1
        if downloaded == 0:
            raise FileNotFoundError(f"No raw data files found in storage prefix '{remote_prefix}/raw_data'.")

        _emit("PROCESSING", "EXECUTING_7_STAGE_DUCKDB_PIPELINE", 35)
        ok = pipeline_runner(
            data_dir=str(raw_dir),
            output_dir=str(out_dir),
            cache_dir=str(cache_dir),
            mode=mode,
            region_profile=region_profile,
            target_override=target_override,
            cost_override=cost_override,
        )
        if not ok:
            raise RuntimeError("Master 7-stage pipeline returned failure status.")

        _emit("PROCESSING", "SYNCING_ARTIFACTS_TO_OBJECT_STORE", 85)
        uploaded_artifacts = store.sync_dir_up(out_dir, f"{remote_prefix}/output")
        elapsed = round(time.time() - t0, 2)

        summary = {
            "status": "COMPLETED",
            "job_id": job_id,
            "tenant_id": tenant_id,
            "remote_prefix": remote_prefix,
            "downloaded_raw_files": downloaded,
            "uploaded_output_artifacts": uploaded_artifacts,
            "storage_backend": store.backend_name,
            "elapsed_seconds": elapsed,
        }
        _emit("COMPLETED", "CERTIFIED_AND_READY", 100, res=summary)
        return summary

    except Exception as exc:
        _emit("FAILED", "WORKER_ERROR", 100, err=str(exc))
        raise
    finally:
        # Always wipe ephemeral local scratch so zero customer PII lingers on worker disk
        shutil.rmtree(scratch_root, ignore_errors=True)


def run_rq_worker(queues: Optional[list] = None) -> None:
    """Starts a live Redis/RQ worker process for horizontal cloud deployments."""
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        raise RuntimeError("REDIS_URL must be set to start a standalone DataX-Ray RQ worker.")
    import redis
    from rq import Worker

    conn = redis.Redis.from_url(redis_url)
    q_names = queues or ["high", "default", "bulk"]
    print(f"[DataX-Ray Worker] Listening on Redis queues: {q_names}")
    worker = Worker(q_names, connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DataX-Ray Phase C Horizontal RQ Worker")
    parser.add_argument("--queues", nargs="+", default=["high", "default", "bulk"], help="Ordered RQ queue names")
    args = parser.parse_args()
    run_rq_worker(args.queues)
