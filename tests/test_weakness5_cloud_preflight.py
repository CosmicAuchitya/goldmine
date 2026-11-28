import time
from types import SimpleNamespace

from autonomous_engine.cloud_preflight_verifier import run_cloud_preflight
from autonomous_engine.api_server import JobManager, JobRecord


def test_w5_cloud_preflight_suite_passes_all_contracts():
    res = run_cloud_preflight(include_live_probes=True)
    assert res["overall_status"] == "PASSED", res
    assert res["checks"]["postgres_sql_dialect_parity"]["passed"] is True
    assert res["checks"]["postgres_sql_dialect_parity"]["total_queries_audited"] >= 50
    assert res["checks"]["postgres_unified_ddl"]["passed"] is True
    assert res["checks"]["razorpay_webhook_contract"]["passed"] is True
    assert res["checks"]["stateless_worker_dry_run"]["passed"] is True
    assert res["checks"]["stateless_worker_dry_run"]["has_executive_pulse_in_db"] is True


def test_w5_multipod_job_manager_never_serves_stale_ram_cache_in_redis_mode(tmp_path, monkeypatch):
    """Verifies the multi-pod stale-cache fix in JobManager.get_job() when REDIS_URL is active."""
    import autonomous_engine.api_server as api_mod

    jm = JobManager(max_workers=1, state_dir=tmp_path)
    job = JobRecord(
        job_id="job_multipod_sync_1",
        tenant_id="tenant_a",
        run_root=tmp_path / "run1",
        mode="templated",
    )
    jm.register_job(job)

    # Simulate external RQ worker updating the shared DB row to COMPLETED while Pod A has QUEUED in RAM
    with jm._connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, current_stage = ?, progress_pct = ? WHERE job_id = ?",
            ("COMPLETED", "CERTIFIED_AND_READY", 100, "job_multipod_sync_1"),
        )

    # Enable simulated Redis/multi-pod mode on queue_backend
    monkeypatch.setattr(api_mod, "queue_backend", SimpleNamespace(is_redis=True))
    fresh = jm.get_job("job_multipod_sync_1")
    assert fresh is not None
    assert fresh.status == "COMPLETED", f"Expected fresh DB status COMPLETED, got stale {fresh.status}"
    assert fresh.progress_pct == 100
