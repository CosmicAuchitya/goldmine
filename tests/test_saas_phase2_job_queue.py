"""
================================================================================
UNIT TESTS: PHASE 2 ASYNC JOB QUEUE, SSE STREAMING & GDPR PURGE
================================================================================
"""

import io
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from autonomous_engine.api_server import app, job_manager, JobRecord


@pytest.fixture
def client():
    return TestClient(app)


def test_async_job_submit_and_status(client, tmp_path):
    """Submitting a dataset asynchronously must return 202 Accepted and pollable job_id."""
    csv_content = "user_id,plan_tier,monthly_bill,churn_risk\nU01,Basic,29.0,0\nU02,Pro,99.0,1\n"
    files = [
        ("files", ("customers.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv"))
    ]
    data = {
        "tenant_id": "test_org_42",
        "mode": "templated",
        "region_profile": "US",
        "language": "english"
    }

    resp = client.post("/api/v1/jobs/submit", data=data, files=files)
    assert resp.status_code == 202
    res_data = resp.json()

    assert res_data["status"] == "QUEUED"
    assert "job_id" in res_data
    assert res_data["tenant_id"] == "test_org_42"
    assert "/api/v1/jobs/" in res_data["poll_url"]
    assert "/events" in res_data["events_url"]

    job_id = res_data["job_id"]

    # Poll status
    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    st = status_resp.json()
    assert st["job_id"] == job_id
    assert st["status"] in ("QUEUED", "PROCESSING", "COMPLETED")


def test_sse_event_stream(client):
    """Job event stream must emit text/event-stream formatted SSE events."""
    job_id = f"test_sse_job_{int(time.time())}"
    job = JobRecord(
        job_id=job_id,
        tenant_id="tenant_sse",
        run_root=Path("./runs/test_sse"),
        mode="templated"
    )
    job_manager.register_job(job)
    job.status = "COMPLETED"
    job.progress_pct = 100
    job.current_stage = "COMPLETED"

    stream_resp = client.get(f"/api/v1/jobs/{job_id}/events")
    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]
    text = stream_resp.text
    assert "data: " in text
    assert job_id in text
    assert "COMPLETED" in text


def test_gdpr_dpdp_purge_endpoint(client, tmp_path):
    """Purge endpoint must erase tenant job workspace from disk and job manager."""
    job_id = f"test_purge_{int(time.time())}"
    tenant_dir = Path("runs/tenants/test_purge_org/jobs") / job_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    sample_file = tenant_dir / "customer_raw.csv"
    sample_file.write_text("secret_id,name\n1,Alice\n", encoding="utf-8")

    job = JobRecord(
        job_id=job_id,
        tenant_id="test_purge_org",
        run_root=tenant_dir,
        mode="templated"
    )
    job_manager.register_job(job)

    # Verify exists
    assert sample_file.exists()
    assert job_manager.get_job(job_id) is not None

    # Call 1-Click GDPR Purge
    purge_resp = client.delete(f"/api/v1/workspaces/{job_id}/purge")
    assert purge_resp.status_code == 200
    p_data = purge_resp.json()
    assert p_data["status"] == "purged"
    assert p_data["job_id"] == job_id

    # Verify physical erasure
    assert not tenant_dir.exists(), "Physical tenant workspace must be completely deleted from disk!"


def test_invalid_job_id_and_traversal_rejection(client):
    """Malicious or non-existent job IDs must be securely rejected."""
    # Non-existent job
    missing_resp = client.get("/api/v1/jobs/non_existent_job_12345")
    assert missing_resp.status_code == 404

    # Traversal attempt
    trap_resp = client.get("/api/v1/jobs/../../evil_id")
    assert trap_resp.status_code in (400, 404, 422)
