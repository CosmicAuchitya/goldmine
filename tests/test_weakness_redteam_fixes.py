import io
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine.api_server import app
from autonomous_engine.templated_dag_runner import load_entity_dataframe
from autonomous_engine.growth_inventory_engine import analyze_growth_and_inventory
from autonomous_engine.conversational_qa_engine import (
    ConversationalBusinessQAEngine,
    clear_qa_response_cache,
)
from tests.test_weakness1_sales_stock_engine import _make_indian_shopkeeper_sales_df
from tests.test_weakness2_tally_and_pdf import _build_sample_invoice_pdf


def test_rt1_no_pd_na_string_pollution_after_vectorized_sanitization(tmp_path):
    """Bug #1: Vectorized string sanitization must NEVER produce literal '<NA>' strings or pd.NA bool crashes."""
    csv_p = tmp_path / "null_strings.csv"
    pd.DataFrame({
        "order_id": [1, 2, 3, 4],
        "region": ["North", None, "", "South"],
        "amount": [100.0, 200.0, 300.0, 400.0],
    }).to_csv(csv_p, index=False)

    df = load_entity_dataframe(csv_p)
    assert df["region"].dtype == object
    assert "<NA>" not in df["region"].astype(str).tolist()
    # Must evaluate cleanly in scalar boolean context without TypeError
    assert bool((df["region"] == "North").iloc[1]) is False


def test_rt2_duckdb_streaming_honors_title_banner_skip_rows_above_10mb(tmp_path):
    """Bug #2: >10 MB CSV with top metadata title banner must skip banner rows in DuckDB streaming."""
    csv_big = tmp_path / "big_with_banner.csv"
    with open(csv_big, "w", encoding="utf-8") as fh:
        fh.write("COMPANY SALES REPORT - FY 2026,,,,\n")
        fh.write("id,region,category,amount,flag\n")
        fh.write("1,North,Electronics,1250.50,0\n" * 380_000)
    assert csv_big.stat().st_size > 10 * 1024 * 1024

    df = load_entity_dataframe(csv_big)
    assert list(df.columns) == ["id", "region", "category", "amount", "flag"]
    assert len(df) == 380_000


def test_rt3_shopkeeper_fastpath_does_not_hijack_return_rate_or_region_sales(tmp_path):
    """Bug #3: Return-rate party queries must compute adverse rate, and sales-by-region must sum Sales_Amount."""
    clear_qa_response_cache()
    df = _make_indian_shopkeeper_sales_df()
    df["Region"] = ["North", "South", "East", "West", "North"] * (len(df) // 5) + ["North"] * (len(df) % 5)
    df["is_returned"] = [1 if i % 5 == 0 else 0 for i in range(len(df))]
    df.to_parquet(tmp_path / "bi_ready_fact.parquet", index=False)

    with ConversationalBusinessQAEngine(tmp_path) as qa:
        r_ret = qa.ask("Which party has the highest return rate?", language="en", use_llm=False)
        assert r_ret["status"] == "success"
        assert "adverse_events" in r_ret["sql_executed"] or "_is_target_event" in r_ret["sql_executed"]

        r_reg = qa.ask("sabse zyada bikri kis region mein hui?", language="auto", use_llm=False)
        assert r_reg["status"] == "success"
        assert "total_sales" in r_reg["sql_executed"]
        assert '"Region"' in r_reg["sql_executed"]


def test_rt5_growth_engine_ignores_synthetic_unit_margin_column():
    """Bug #5: Synthetic net_contribution_margin must not override physical Sales_Amount - Cost_Price * Qty."""
    df = _make_indian_shopkeeper_sales_df()
    # Inject unit-only synthetic margin column as templated_dag_runner previously could
    df["net_contribution_margin"] = df["Selling_Price"] - df["Cost_Price"]
    rep = analyze_growth_and_inventory(df)
    expected_profit = float(df["Sales_Amount"].sum() - (df["Cost_Price"] * df["Qty"]).sum())
    assert abs(rep["kpis"]["gross_profit"] - expected_profit) < 1.0


def test_rt6_frontend_language_switch_re_renders_growth_panel():
    """Bug #6: switchBriefLanguage() in compiled web_client.html must re-render growthInventorySection."""
    html_txt = Path("autonomous_engine/web_client.html").read_text(encoding="utf-8")
    idx = html_txt.find("function switchBriefLanguage(")
    assert idx != -1
    fn_block = html_txt[idx : idx + 1000]
    assert "renderGrowthInventoryPanel(" in fn_block


def test_rt7_zip_archive_containing_pdf_preview_intent_succeeds(tmp_path):
    """Bug #7: /api/v1/preview-intent must accept .pdf files packaged inside a .zip archive."""
    pdf_p = tmp_path / "monthly_tally.pdf"
    _build_sample_invoice_pdf(pdf_p)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(pdf_p, arcname="monthly_tally.pdf")
    buf.seek(0)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/preview-intent",
        files={"file": ("tally_pdfs.zip", buf.read(), "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json().get("columns", [])) >= 5


def test_rt4_worker_entry_reads_grounding_confidence_not_missing_status_key(tmp_path):
    """Bug #4: worker_entry.py must read grounding_confidence from run_anti_hallucination_audit."""
    from unittest.mock import patch
    from autonomous_engine.worker_entry import execute_pipeline_job_task
    from autonomous_engine.db_adapter import DatabaseAdapter
    from autonomous_engine.storage_backend import LocalStorageBackend
    from autonomous_engine.queue_backend import DistributedQueueBackend

    db = DatabaseAdapter(tmp_path / "jobs.sqlite")
    with db.connect() as conn:
        conn.execute(
            "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, tenant_id TEXT, run_root TEXT, mode TEXT, "
            "region_profile TEXT, language TEXT, target_override TEXT, cost_override TEXT, "
            "status TEXT, current_stage TEXT, progress_pct INTEGER, created_at REAL, "
            "started_at REAL, completed_at REAL, error TEXT, result_json TEXT)"
        )
        conn.execute(
            "INSERT INTO jobs (job_id, tenant_id, run_root, mode, region_profile, language, status, current_stage, progress_pct, created_at) "
            "VALUES ('j_rt4', 't1', '.', 'templated', 'IN', 'en', 'QUEUED', 'QUEUED', 0, 1.0)"
        )
    store = LocalStorageBackend(tmp_path / "obj")
    raw_d = tmp_path / "raw"
    raw_d.mkdir()
    (raw_d / "a.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    store.sync_dir_up(raw_d, "tenants/t1/runs/j_rt4/raw_data")
    q_bus = DistributedQueueBackend(redis_url="", max_local_workers=1)

    with patch(
        "autonomous_engine.anti_hallucination_guard.run_anti_hallucination_audit",
        return_value={"grounding_confidence": "100.0% VERIFIED TRUTH"},
    ):
        res = execute_pipeline_job_task(
            {"job_id": "j_rt4", "tenant_id": "t1", "remote_prefix": "tenants/t1/runs/j_rt4"},
            db_adapter=db,
            storage=store,
            queue_backend=q_bus,
            pipeline_runner=lambda **_kw: True,
        )
    assert res["audit_confidence"] == "100.0% VERIFIED TRUTH"
