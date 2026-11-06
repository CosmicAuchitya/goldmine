"""
=============================================================================
DATAX-RAY ENTERPRISE PRODUCTION REST API SERVER (FASTAPI)
=============================================================================
Enables headless, cross-platform integration for ERPs, Slack/Teams bots,
SaaS frontends, and mobile apps:
1. GET  /health -> System health and version.
2. POST /api/v1/analyze-upload -> Streaming chunked dataset upload (DoS protected),
   isolated sandbox execution, anti-hallucination audit gate, and deliverable synthesis.
3. POST /api/v1/ask -> Conversational bilingual Q&A with DuckDB verification & resource cleanup.
4. GET  /api/v1/download/{run_id}/{artifact_name} -> Secure artifact retrieval.
=============================================================================
"""

import os
import re
import sys
import time
import json
import uuid
import shutil
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Query, Header
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

# Support both package and direct script execution
try:
    from .common_utils import resolve_safe_workspace_path
    from .kaggle_harvester import safe_extract_zip
    from .master_orchestrator import run_master_pipeline
    from .anti_hallucination_guard import run_anti_hallucination_audit
    from .conversational_qa_engine import ConversationalBusinessQAEngine
except ImportError:
    from common_utils import resolve_safe_workspace_path
    from kaggle_harvester import safe_extract_zip
    from master_orchestrator import run_master_pipeline
    from anti_hallucination_guard import run_anti_hallucination_audit
    from conversational_qa_engine import ConversationalBusinessQAEngine

WORKSPACE_ROOT = Path.cwd().resolve()
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB stream chunk
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet", ".zip"}

ALLOWED_ARTIFACTS = {
    "PLAIN_BUSINESS_SUMMARY.md",
    "DATA_XRAY_EXECUTIVE_DOSSIER.md",
    "POWERBI_TABLEAU_MEASURE_GUIDE.md",
    "CERTIFICATION_AUDIT_CHECKLIST.md",
    "actionable_priority_worklist.csv",
    "enterprise_interactive_dashboard.html",
    "bespoke_executive_dashboard.html",
    "dashboard_design_blueprint.json",
    "semantic_metrics_manifest.json",
    "vega_lite_dashboard_spec.json",
    "temporal_trend_summary.json",
    "bi_ready_fact.parquet"
}

app = FastAPI(
    title="DataX-Ray Autonomous Engine API",
    description="Enterprise Autonomous AI Data Engineering, Forensic Analytics, Grounded Q&A & Bespoke Dashboard Server",
    version="5.5.0"
)


class JobRecord:
    def __init__(
        self,
        job_id: str,
        tenant_id: str,
        run_root: Path,
        mode: str = "ai",
        region_profile: str = "US",
        language: str = "english"
    ):
        self.job_id = job_id
        self.tenant_id = tenant_id
        self.run_root = run_root
        self.mode = mode
        self.region_profile = region_profile
        self.language = language
        self.status = "QUEUED"  # QUEUED, PROCESSING, COMPLETED, FAILED, PURGED
        self.current_stage = "QUEUED"
        self.progress_pct = 0
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.error: Optional[str] = None
        self.result_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        elapsed = round((self.completed_at or time.time()) - (self.started_at or self.created_at), 2)
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "progress_pct": self.progress_pct,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": elapsed,
            "error": self.error,
            "result": self.result_payload
        }


def _execute_job_in_background(job_id: str) -> None:
    job = job_manager.get_job(job_id)
    if not job or job.status == "PURGED":
        return

    job.status = "PROCESSING"
    job.started_at = time.time()
    job.current_stage = "Stage 1: Topology Profiling & Cardinality Scan"
    job.progress_pct = 15

    staging_raw = job.run_root / "raw_data"
    staging_out = job.run_root / "output"
    staging_cache = job.run_root / "cache"

    try:
        pipeline_mode = "templated" if job.mode.lower() in ("templated", "dag", "deterministic") else "ai"
        job.current_stage = "Stages 1-4: Dynamic ETL Synthesis & Self-Healing Sandbox"
        job.progress_pct = 40

        success = run_master_pipeline(
            data_dir=str(staging_raw),
            output_dir=str(staging_out),
            cache_dir=str(staging_cache),
            mode=pipeline_mode
        )
        if not success:
            job.status = "FAILED"
            job.error = "Master autonomous pipeline execution failed."
            job.completed_at = time.time()
            return

        job.current_stage = "Stages 5-7: Semantic Modeling & Bespoke Dashboard Synthesis"
        job.progress_pct = 80

        # Anti-Hallucination Guard Audit
        job.current_stage = "Anti-Hallucination Guard: Physical DuckDB SQL Grounding Audit"
        job.progress_pct = 90
        bp_path = staging_out / "execution_blueprint.json"
        audit_res = run_anti_hallucination_audit(str(staging_out), str(bp_path))

        # Build results payload
        manifest_data = {}
        manifest_f = staging_out / "semantic_metrics_manifest.json"
        if manifest_f.exists():
            try:
                manifest_data = json.loads(manifest_f.read_text(encoding="utf-8"))
            except Exception:
                pass

        temporal_data = {}
        temp_f = staging_out / "temporal_trend_summary.json"
        if temp_f.exists():
            try:
                temporal_data = json.loads(temp_f.read_text(encoding="utf-8"))
            except Exception:
                pass

        plain_summary_text = ""
        summary_f = staging_out / "PLAIN_BUSINESS_SUMMARY.md"
        if summary_f.exists():
            try:
                plain_summary_text = summary_f.read_text(encoding="utf-8")
            except Exception:
                pass

        worklist_preview: List[Dict[str, Any]] = []
        wl_f = staging_out / "actionable_priority_worklist.csv"
        if wl_f.exists():
            try:
                df_wl = pd.read_csv(wl_f)
                cleaned_preview = df_wl.head(10).replace([np.inf, -np.inf], np.nan)
                worklist_preview = [
                    {k: (None if pd.isna(v) else v) for k, v in row.items()}
                    for row in cleaned_preview.to_dict(orient="records")
                ]
            except Exception:
                pass

        design_bp_data = {}
        bp_f = staging_out / "dashboard_design_blueprint.json"
        if bp_f.exists():
            try:
                design_bp_data = json.loads(bp_f.read_text(encoding="utf-8"))
            except Exception:
                pass

        artifact_urls = {
            name: f"/api/v1/download/{job_id}/{name}"
            for name in ALLOWED_ARTIFACTS
            if (staging_out / name).exists()
        }

        job.status = "COMPLETED"
        job.current_stage = "COMPLETED"
        job.progress_pct = 100
        job.completed_at = time.time()
        job.result_payload = {
            "run_id": job_id,
            "tenant_id": job.tenant_id,
            "status": "success",
            "execution_time_seconds": round(job.completed_at - job.started_at, 2),
            "output_dir": str(staging_out.relative_to(WORKSPACE_ROOT)),
            "audit_confidence": audit_res.get("grounding_confidence"),
            "kpis": manifest_data.get("certified_metrics", []),
            "temporal_summary": temporal_data,
            "dashboard_design_blueprint": design_bp_data,
            "plain_summary_markdown": plain_summary_text,
            "worklist_preview": worklist_preview,
            "artifact_download_urls": artifact_urls,
            "dashboard_url": f"/api/v1/dashboard/{job_id}"
        }
    except Exception as exc:
        job.status = "FAILED"
        job.error = str(exc)
        job.completed_at = time.time()


class JobManager:
    def __init__(self, max_workers: int = 4):
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dataxray_worker")

    def register_job(self, job: JobRecord) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def submit_job(self, job: JobRecord) -> None:
        self.register_job(job)
        self._executor.submit(_execute_job_in_background, job.job_id)

    def purge_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.status = "PURGED"
            job.current_stage = "PURGED"
            job.result_payload = None
            if job.run_root.exists():
                shutil.rmtree(job.run_root, ignore_errors=True)
            return True


job_manager = JobManager(max_workers=4)


class AskRequest(BaseModel):
    output_dir: str = Field(..., description="Target output directory containing bi_ready_fact.parquet")
    question: str = Field(..., min_length=1, max_length=1000, description="Business inquiry in English or Hinglish")
    language: str = Field("auto", description="'auto', 'english', or 'hinglish'")
    use_llm: bool = Field(True, description="Enable LLM SQL synthesis with fallback to deterministic engine")


@app.get("/health", tags=["System"])
def get_health() -> Dict[str, str]:
    """Health check endpoint for container orchestrators and load balancers."""
    return {
        "status": "healthy",
        "engine": "DataX-Ray Autonomous Engine",
        "version": "5.5.0"
    }


@app.post("/api/v1/jobs/submit", status_code=status.HTTP_202_ACCEPTED, tags=["Job Queue"])
async def submit_job(
    files: List[UploadFile] = File(...),
    tenant_id: str = Form("default_tenant"),
    mode: str = Form("ai"),
    region_profile: str = Form("US"),
    language: str = Form("english")
) -> Dict[str, Any]:
    """
    Submits raw dataset files asynchronously for autonomous pipeline execution.
    Returns HTTP 202 Accepted immediately with polling and live SSE stream links.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided for analysis.")

    safe_tenant = re.sub(r'[^A-Za-z0-9_-]', '_', str(tenant_id).strip()) or "default_tenant"
    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_root = WORKSPACE_ROOT / "runs" / "tenants" / safe_tenant / "jobs" / job_id
    staging_raw = run_root / "raw_data"
    staging_out = run_root / "output"
    staging_cache = run_root / "cache"

    staging_raw.mkdir(parents=True, exist_ok=True)
    staging_out.mkdir(parents=True, exist_ok=True)
    staging_cache.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    try:
        for uf in files:
            raw_name = uf.filename or "upload_file"
            safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', Path(raw_name).name)
            ext = Path(safe_name).suffix.lower()

            if ext not in ALLOWED_EXTENSIONS:
                shutil.rmtree(run_root, ignore_errors=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file extension '{ext}' for file '{safe_name}'."
                )

            dest_file = staging_raw / safe_name
            with open(dest_file, "wb") as f_out:
                while True:
                    chunk = await uf.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_BYTES:
                        f_out.close()
                        shutil.rmtree(run_root, ignore_errors=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Uploaded files exceed maximum size ceiling of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                        )
                    f_out.write(chunk)

            if ext == ".zip":
                try:
                    safe_extract_zip(dest_file, staging_raw)
                except ValueError as ve:
                    shutil.rmtree(run_root, ignore_errors=True)
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Archive Security Violation: {ve}")

        job_record = JobRecord(
            job_id=job_id,
            tenant_id=safe_tenant,
            run_root=run_root,
            mode=mode,
            region_profile=region_profile,
            language=language
        )
        job_manager.submit_job(job_record)

        return {
            "status": "QUEUED",
            "job_id": job_id,
            "tenant_id": safe_tenant,
            "poll_url": f"/api/v1/jobs/{job_id}",
            "events_url": f"/api/v1/jobs/{job_id}/events",
            "message": "Dataset accepted and scheduled for autonomous processing in background worker."
        }
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(run_root, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job submission failure: {exc}"
        )


@app.get("/api/v1/jobs/{job_id}", tags=["Job Queue"])
def get_job_status(job_id: str) -> Dict[str, Any]:
    """Retrieves current execution state, stage progress, and results payload for a job."""
    if not re.match(r'^[A-Za-z0-9_-]{3,80}$', job_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id format.")

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")

    return job.to_dict()


@app.get("/api/v1/jobs/{job_id}/events", tags=["Job Queue & Events"])
async def stream_job_events(job_id: str):
    """
    Server-Sent Events (SSE) live streaming feed for frontline progress tracking.
    Enables zero-lag live progress bars on Next.js/React frontends without polling.
    """
    if not re.match(r'^[A-Za-z0-9_-]{3,80}$', job_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id format.")

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")

    async def event_generator():
        last_pct = -1
        last_stage = ""
        while True:
            cur_job = job_manager.get_job(job_id)
            if not cur_job:
                break
            if cur_job.progress_pct != last_pct or cur_job.current_stage != last_stage:
                last_pct = cur_job.progress_pct
                last_stage = cur_job.current_stage
                payload = {
                    "job_id": job_id,
                    "status": cur_job.status,
                    "stage": cur_job.current_stage,
                    "progress_pct": cur_job.progress_pct,
                    "error": cur_job.error
                }
                yield f"data: {json.dumps(payload)}\n\n"
            if cur_job.status in ("COMPLETED", "FAILED", "PURGED"):
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.delete("/api/v1/workspaces/{job_id}/purge", tags=["Privacy & Compliance"])
def purge_workspace_data(job_id: str) -> Dict[str, Any]:
    """
    1-Click GDPR Article 17 / India DPDP Act 2023 Right to Erasure Endpoint.
    Permanently wipes uploaded files, cached state, DuckDB Parquet tables, and HTML artifacts from disk.
    """
    if not re.match(r'^[A-Za-z0-9_-]{3,80}$', job_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id format.")

    purged_from_manager = job_manager.purge_job(job_id)
    purged_disk = False

    # Check upload directory
    upload_cand = WORKSPACE_ROOT / "runs" / "uploads" / job_id
    if upload_cand.exists():
        shutil.rmtree(upload_cand, ignore_errors=True)
        purged_disk = True

    # Check tenant directories
    tenant_dir = WORKSPACE_ROOT / "runs" / "tenants"
    if tenant_dir.exists():
        for cand in tenant_dir.glob(f"*/jobs/{job_id}"):
            shutil.rmtree(cand, ignore_errors=True)
            purged_disk = True

    if not purged_from_manager and not purged_disk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workspace for job_id '{job_id}' not found.")

    return {
        "status": "purged",
        "job_id": job_id,
        "message": "All customer raw data, Parquet facts, and generated deliverables permanently erased in compliance with GDPR & DPDP."
    }


@app.post("/api/v1/analyze-upload", tags=["Pipeline Execution"])
async def analyze_upload(
    files: List[UploadFile] = File(...),
    mode: str = Form("ai"),
    language: str = Form("hinglish")
) -> Dict[str, Any]:
    """
    Streams raw dataset files in chunks, extracts ZIPs safely, runs full 7-stage pipeline,
    validates via Anti-Hallucination Guard, and returns audited KPIs, plain-language brief,
    priority worklist preview, and download links.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided for analysis.")

    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_root = WORKSPACE_ROOT / "runs" / "uploads" / run_id
    staging_raw = run_root / "raw_data"
    staging_out = run_root / "output"
    staging_cache = run_root / "cache"

    staging_raw.mkdir(parents=True, exist_ok=True)
    staging_out.mkdir(parents=True, exist_ok=True)
    staging_cache.mkdir(parents=True, exist_ok=True)

    total_bytes = 0

    try:
        # Save and validate uploaded files in chunks to prevent unbounded memory consumption
        for uf in files:
            raw_name = uf.filename or "upload_file"
            safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', Path(raw_name).name)
            ext = Path(safe_name).suffix.lower()

            if ext not in ALLOWED_EXTENSIONS:
                shutil.rmtree(run_root, ignore_errors=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file extension '{ext}' for file '{safe_name}'."
                )

            dest_file = staging_raw / safe_name
            with open(dest_file, "wb") as f_out:
                while True:
                    chunk = await uf.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_BYTES:
                        f_out.close()
                        shutil.rmtree(run_root, ignore_errors=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Uploaded files exceed maximum size ceiling of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                        )
                    f_out.write(chunk)

            if ext == ".zip":
                try:
                    safe_extract_zip(dest_file, staging_raw)
                except ValueError as ve:
                    shutil.rmtree(run_root, ignore_errors=True)
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Archive Security Violation: {ve}")

        # Run Autonomous Pipeline
        t_start = time.time()
        pipeline_mode = "templated" if mode.lower() in ("templated", "dag", "deterministic") else "ai"
        success = run_master_pipeline(
            data_dir=str(staging_raw),
            output_dir=str(staging_out),
            cache_dir=str(staging_cache),
            mode=pipeline_mode
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Autonomous pipeline execution failed. Check server execution logs."
            )

        # Run Anti-Hallucination Guard
        bp_path = staging_out / "execution_blueprint.json"
        audit_res = run_anti_hallucination_audit(str(staging_out), str(bp_path))

        if audit_res.get("grounding_confidence") != "100.0% VERIFIED TRUTH":
            violations = audit_res.get("physics_invariant_violations", [])
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Anti-Hallucination Audit Gate Failed",
                    "violations": violations
                }
            )

        # Read deliverables
        manifest_data = {}
        manifest_f = staging_out / "semantic_metrics_manifest.json"
        if manifest_f.exists():
            try:
                manifest_data = json.loads(manifest_f.read_text(encoding="utf-8"))
            except Exception as me:
                print(f"[-] Manifest read warning: {me}")

        temporal_data = {}
        temp_f = staging_out / "temporal_trend_summary.json"
        if temp_f.exists():
            try:
                temporal_data = json.loads(temp_f.read_text(encoding="utf-8"))
            except Exception as te:
                print(f"[-] Temporal read warning: {te}")

        plain_summary_text = ""
        summary_f = staging_out / "PLAIN_BUSINESS_SUMMARY.md"
        if summary_f.exists():
            try:
                plain_summary_text = summary_f.read_text(encoding="utf-8")
            except Exception as se:
                print(f"[-] Summary read warning: {se}")

        worklist_preview: List[Dict[str, Any]] = []
        wl_f = staging_out / "actionable_priority_worklist.csv"
        if wl_f.exists():
            try:
                df_wl = pd.read_csv(wl_f)
                cleaned_preview = df_wl.head(10).replace([np.inf, -np.inf], np.nan)
                worklist_preview = [
                    {k: (None if pd.isna(v) else v) for k, v in row.items()}
                    for row in cleaned_preview.to_dict(orient="records")
                ]
            except Exception as wle:
                print(f"[-] Worklist preview parsing warning: {wle}")

        # Stage 7 Dashboard Design Blueprint
        design_bp_data = {}
        bp_f = staging_out / "dashboard_design_blueprint.json"
        if bp_f.exists():
            try:
                design_bp_data = json.loads(bp_f.read_text(encoding="utf-8"))
            except Exception as bpe:
                print(f"[-] Blueprint read warning: {bpe}")

        # Download URLs
        artifact_urls = {
            name: f"/api/v1/download/{run_id}/{name}"
            for name in ALLOWED_ARTIFACTS
            if (staging_out / name).exists()
        }

        rel_out_dir = str(staging_out.relative_to(WORKSPACE_ROOT))

        return {
            "status": "success",
            "run_id": run_id,
            "execution_time_seconds": round(time.time() - t_start, 2),
            "output_dir": rel_out_dir,
            "audit_confidence": audit_res.get("grounding_confidence"),
            "kpis": manifest_data.get("certified_metrics", []),
            "temporal_summary": temporal_data,
            "dashboard_design_blueprint": design_bp_data,
            "plain_summary_markdown": plain_summary_text,
            "worklist_preview": worklist_preview,
            "artifact_download_urls": artifact_urls
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unhandled internal server exception during upload analysis: {exc}"
        )


@app.post("/api/v1/ask", tags=["Conversational Q&A"])
def ask_question(req: AskRequest) -> Dict[str, Any]:
    """
    Executes grounded natural language Q&A in English or Hinglish over
    the specified audited output directory using read-only DuckDB SQL.
    Ensures safe resource closure.
    """
    q_str = req.question.strip()
    if not q_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be blank.")

    try:
        safe_out_dir = resolve_safe_workspace_path(req.output_dir, WORKSPACE_ROOT)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access Denied: {ve}")

    fact_p = safe_out_dir / "bi_ready_fact.parquet"
    if not fact_p.exists():
        pqs = list(safe_out_dir.glob("*.parquet"))
        if not pqs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No physical fact table found in output directory '{req.output_dir}'."
            )

    qa_engine = None
    try:
        qa_engine = ConversationalBusinessQAEngine(safe_out_dir)
        response_payload = qa_engine.ask(
            question=q_str,
            language=req.language,
            use_llm=req.use_llm
        )
        return response_payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversational QA Engine encountered an internal error: {e}"
        )
    finally:
        if qa_engine:
            qa_engine.close()


@app.get("/api/v1/download/{run_id}/{artifact_name}", tags=["Artifact Downloads"])
def download_artifact(run_id: str, artifact_name: str) -> FileResponse:
    """Safely retrieves a certified deliverable file, blocking path traversal."""
    if not re.match(r'^[A-Za-z0-9_-]{3,80}$', run_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_id format.")

    if artifact_name not in ALLOWED_ARTIFACTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Artifact '{artifact_name}' is not permitted for direct download."
        )

    cand_path = WORKSPACE_ROOT / "runs" / "uploads" / run_id / "output" / artifact_name
    if not cand_path.exists():
        tenant_matches = list((WORKSPACE_ROOT / "runs" / "tenants").glob(f"*/jobs/{run_id}/output/{artifact_name}"))
        if tenant_matches:
            cand_path = tenant_matches[0]
    if not cand_path.exists():
        cand_path = WORKSPACE_ROOT / "kaggle_benchmarks" / run_id / "output" / artifact_name

    try:
        safe_file_path = resolve_safe_workspace_path(str(cand_path), WORKSPACE_ROOT)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access Denied: {ve}")

    if not safe_file_path.exists() or not safe_file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_name}' not found for run_id '{run_id}'."
        )

    return FileResponse(
        path=str(safe_file_path),
        filename=artifact_name,
        media_type="application/octet-stream"
    )


@app.get("/api/v1/dashboard/{run_id}", tags=["Bespoke Dashboard"])
def get_bespoke_dashboard_html(run_id: str) -> HTMLResponse:
    """Renders the self-contained bespoke executive dashboard HTML for the run."""
    if not re.match(r'^[A-Za-z0-9_-]{3,80}$', run_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid run_id format.")

    cand_path = WORKSPACE_ROOT / "runs" / "uploads" / run_id / "output" / "bespoke_executive_dashboard.html"
    if not cand_path.exists():
        tenant_matches = list((WORKSPACE_ROOT / "runs" / "tenants").glob(f"*/jobs/{run_id}/output/bespoke_executive_dashboard.html"))
        if tenant_matches:
            cand_path = tenant_matches[0]
    if not cand_path.exists():
        cand_path = WORKSPACE_ROOT / "kaggle_benchmarks" / run_id / "output" / "bespoke_executive_dashboard.html"

    try:
        safe_html_path = resolve_safe_workspace_path(str(cand_path), WORKSPACE_ROOT)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access Denied: {ve}")

    if not safe_html_path.exists() or not safe_html_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bespoke dashboard HTML not found for run_id '{run_id}'."
        )

    content = safe_html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=content, media_type="text/html")
