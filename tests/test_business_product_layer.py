"""
=============================================================================
COMPREHENSIVE TEST SUITE: BUSINESS PRODUCT LAYER & NON-CODER DEPLOYMENT
=============================================================================
Validates:
1. Strict Read-Only DuckDB SQL Sandbox Security Gate.
2. Conversational Business Q&A Engine (English & Hinglish Physical Ground Truth).
3. Actionable Priority Worklist (Two-Queue Separation, 100% Physical Lineage, No Fake $).
4. Temporal Trend Engine (Excludes Age/Tenure, Detects True Dates, Stage 6 Chart).
5. Plain Business Summary (Bilingual Brief, $0 Circuit-Breaker Honesty).
6. Anti-Hallucination Guard Check 10 (Detects Tampered Worklists & Fabricated Currency).
7. FastAPI REST Server & Container Endpoints (Health, Ask, Upload Pipeline, Security).
=============================================================================
"""

import io
import os
import json
import zipfile
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from autonomous_engine.common_utils import resolve_safe_workspace_path, quote_sql_ident
from autonomous_engine.conversational_qa_engine import (
    validate_readonly_duckdb_sql,
    enforce_sql_row_limit,
    detect_language_preference,
    ConversationalBusinessQAEngine
)
from autonomous_engine.business_action_exporter import (
    generate_actionable_priority_worklist,
    analyze_temporal_trends,
    generate_plain_business_summary,
    detect_primary_key_column
)
from autonomous_engine.stage6_semantic_viz_synthesizer import synthesize_semantic_and_viz
from autonomous_engine.anti_hallucination_guard import run_anti_hallucination_audit
from autonomous_engine.api_server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def telecom_output_dir():
    p = Path("kaggle_benchmarks/telecom_users/output").resolve()
    if not (p / "bi_ready_fact.parquet").exists():
        pytest.skip("Benchmark telecom_users output not available for integration tests")
    return p


# =============================================================================
# 1. READ-ONLY DUCKDB SQL SANDBOX SECURITY
# =============================================================================
def test_readonly_duckdb_sql_sandbox_blocks_dangerous_operations():
    malicious_queries = [
        "COPY (SELECT * FROM fact) TO 'leak.csv'",
        "SELECT * FROM read_csv_auto('.env')",
        "SELECT * FROM read_text('.env')",
        "SELECT * FROM read_parquet('secret.parquet')",
        "ATTACH 'other.db'",
        "DETACH other",
        "INSTALL httpfs",
        "LOAD httpfs",
        "DROP TABLE fact",
        "CREATE TABLE exploit AS SELECT 1",
        "INSERT INTO fact VALUES (1)",
        "UPDATE fact SET Churn = 1",
        "DELETE FROM fact WHERE 1=1",
        "ALTER TABLE fact DROP COLUMN Churn",
        "PRAGMA version",
        "SET memory_limit = '10GB'",
        "SELECT 1; SELECT 2",
        "SELECT * FROM duckdb_tables()",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM glob('../*')",
        "SELECT getenv('GEMINI_API_KEY')",
    ]

    for q in malicious_queries:
        violations = validate_readonly_duckdb_sql(q)
        assert len(violations) > 0, f"Expected security violation for query: {q}"

    # Verify legitimate queries pass
    clean_queries = [
        "SELECT * FROM fact",
        "SELECT COUNT(*), AVG(_is_target_event) FROM fact",
        "WITH cte AS (SELECT * FROM fact) SELECT * FROM cte LIMIT 10",
        "SELECT TipoContrato, COUNT(*) FROM fact GROUP BY TipoContrato ORDER BY COUNT(*) DESC;",
    ]
    for q in clean_queries:
        violations = validate_readonly_duckdb_sql(q)
        assert violations == [], f"Legitimate query triggered false violation: {q} -> {violations}"


def test_readonly_duckdb_sql_blocks_file_replacement_scans():
    replacement_scan_queries = [
        "SELECT * FROM 'secret.csv'",
        "SELECT * FROM 'secret.parquet'",
        'SELECT * FROM "kaggle_benchmarks/telecom_users/raw_data/telecom_users.csv"',
        "SELECT * FROM 'data/users.json'",
        "SELECT a.* FROM 'test.tsv' a",
    ]
    for q in replacement_scan_queries:
        violations = validate_readonly_duckdb_sql(q)
        assert len(violations) > 0, f"Expected file replacement scan violation for: {q}"


def test_duckdb_sandbox_c_level_lock_blocks_filesystem(telecom_output_dir):
    engine = ConversationalBusinessQAEngine(telecom_output_dir)
    try:
        # 1. Direct attempt to invoke file reader function via DuckDB connection
        with pytest.raises(Exception) as exc_info:
            engine.con.execute("SELECT * FROM read_csv('secret.csv')").df()
        err_msg = str(exc_info.value).lower()
        assert "disabled" in err_msg or "permission" in err_msg or "cannot access" in err_msg

        # 2. File scan attempt is also blocked
        with pytest.raises(Exception) as exc_info2:
            engine.con.execute("SELECT * FROM 'tests/test_business_product_layer.py'").df()
        err_msg2 = str(exc_info2.value).lower()
        assert "does not exist" in err_msg2 or "disabled" in err_msg2 or "permission" in err_msg2
    finally:
        engine.close()


def test_enforce_sql_row_limit_caps_outer_query_on_cte(telecom_output_dir):
    engine = ConversationalBusinessQAEngine(telecom_output_dir)
    try:
        cte_sql = "WITH cte AS (SELECT * FROM fact) SELECT * FROM cte"
        capped_sql = enforce_sql_row_limit(cte_sql, max_rows=200)
        assert "LIMIT 200" in capped_sql
        res_df = engine.con.execute(capped_sql).df()
        assert len(res_df) == 200, f"Expected exactly 200 rows capped on outer CTE query, got {len(res_df)}"
    finally:
        engine.close()


def test_language_detection_loss_keyword():
    # 'loss' should NOT trigger Hinglish when rest of query is English
    assert detect_language_preference("Where is our biggest revenue loss?") == "english"
    assert detect_language_preference("What is the total loss in dollar terms?") == "english"
    # Pure Hinglish query with Hinglish markers should return 'hinglish'
    assert detect_language_preference("Kis contract me sabse zyada churn nuksan ho raha hai?") == "hinglish"
    assert detect_language_preference("Kahan par sabse bada loss ho raha hai?") == "hinglish"


# =============================================================================
# 2. CONVERSATIONAL Q&A: DETERMINISTIC ENGLISH ACCURACY
# =============================================================================
def test_conversational_qa_deterministic_english_accuracy(telecom_output_dir):
    engine = ConversationalBusinessQAEngine(telecom_output_dir)
    res = engine.ask("What is our overall volume, churn count, and adverse failure rate?", language="english", use_llm=False)

    assert res["grounding_verified"] is True
    assert res["language"] == "english"
    assert res["row_count_returned"] == 1
    assert len(res["data"]) == 1

    row = res["data"][0]
    assert row["total_records"] == 5986
    assert row["total_adverse_events"] == 1587
    assert abs(float(row["overall_adverse_rate_pct"]) - 26.51) < 0.1

    assert "5,986" in res["answer_markdown"]
    assert "1,587" in res["answer_markdown"]
    assert "26.51%" in res["answer_markdown"]


# =============================================================================
# 3. CONVERSATIONAL Q&A: HINGLISH DETECTION AND ACCURACY
# =============================================================================
def test_conversational_qa_hinglish_detection_and_accuracy(telecom_output_dir):
    engine = ConversationalBusinessQAEngine(telecom_output_dir)
    try:
        res = engine.ask("Kis contract me sabse zyada churn loss ho raha hai?", language="auto", use_llm=False)

        assert res["grounding_verified"] is True
        assert res["language"] == "hinglish"
        assert res["row_count_returned"] >= 1
        assert "Pramanit" in res["answer_markdown"] or "Audited" in res["answer_markdown"] or "SQL" in res["answer_markdown"] or "DuckDB" in res["answer_markdown"]

        # Verify that numbers inside answer match physical DuckDB fact records
        assert "Month-to-month" in res["sql_executed"] or "TipoContrato" in res["sql_executed"]
        assert len(res["data"]) >= 1
    finally:
        engine.close()


# =============================================================================
# 4. CONVERSATIONAL Q&A: VEGA-LITE SPEC & ROW LIMIT ENFORCEMENT
# =============================================================================
def test_conversational_qa_vega_lite_spec_and_row_limit(telecom_output_dir):
    engine = ConversationalBusinessQAEngine(telecom_output_dir)
    res = engine.ask("Show failure rate by TipoContrato", language="english", use_llm=False)

    assert res["vega_lite_spec"] is not None
    assert "$schema" in res["vega_lite_spec"]
    assert res["vega_lite_spec"]["mark"]["type"] == "bar"

    # Test limit enforcement
    capped_sql = enforce_sql_row_limit("SELECT * FROM fact", max_rows=200)
    assert "LIMIT 200" in capped_sql

    capped_existing = enforce_sql_row_limit("SELECT * FROM fact LIMIT 500", max_rows=200)
    assert "LIMIT 200" in capped_existing


# =============================================================================
# 5. ACTIONABLE PRIORITY WORKLIST: TWO QUEUES & LINEAGE
# =============================================================================
def test_actionable_priority_worklist_queue_separation_and_lineage(telecom_output_dir):
    wl_path = telecom_output_dir / "actionable_priority_worklist.csv"
    assert wl_path.exists(), "Worklist CSV must exist"

    df_wl = pd.read_csv(wl_path)
    assert len(df_wl) > 0

    queues = set(df_wl["action_queue"].unique())
    assert "PREVENTIVE_RETENTION_WATCH" in queues
    assert "REALIZED_LOSS_RECOVERY_AUDIT" in queues

    # Assert 0% contamination
    prev_rows = df_wl[df_wl["action_queue"] == "PREVENTIVE_RETENTION_WATCH"]
    assert (prev_rows["_is_target_event"] == 0).all(), "PREVENTIVE_RETENTION_WATCH must strictly contain _is_target_event == 0"

    rec_rows = df_wl[df_wl["action_queue"] == "REALIZED_LOSS_RECOVERY_AUDIT"]
    assert (rec_rows["_is_target_event"] == 1).all(), "REALIZED_LOSS_RECOVERY_AUDIT must strictly contain _is_target_event == 1"

    # Lineage check against physical Parquet
    df_fact = pd.read_parquet(telecom_output_dir / "bi_ready_fact.parquet")
    pk_col = detect_primary_key_column(df_fact)
    assert pk_col in df_wl.columns

    wl_keys = set(df_wl[pk_col].astype(str))
    fact_keys = set(df_fact[pk_col].astype(str))
    assert wl_keys.issubset(fact_keys), "100% of worklist primary keys must physically exist in fact table!"


# =============================================================================
# 6. ACTIONABLE WORKLIST: ZERO FAKE CURRENCY ON NON-MONETARY DATA
# =============================================================================
def test_actionable_priority_worklist_zero_fake_currency_on_non_monetary_data(tmp_path):
    # Create non-monetary synthetic dataset (e.g. wine quality)
    n = 100
    df_wine = pd.DataFrame({
        "sample_id": [f"SMP_{i:04d}" for i in range(n)],
        "fixed_acidity": np.random.uniform(6.0, 10.0, n),
        "volatile_acidity": np.random.uniform(0.2, 0.9, n),
        "citric_acid": np.random.uniform(0.0, 0.5, n),
        "quality": np.random.choice([3, 4, 5, 6, 7], n)
    })
    out_dir = tmp_path / "wine_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    df_wine.to_parquet(out_dir / "bi_ready_fact.parquet")

    wl_path = generate_actionable_priority_worklist(df_wine, out_dir)
    df_wl = pd.read_csv(wl_path)

    assert "monetary_exposure" in df_wl.columns
    # Must have 0 non-null values (zero fake * 1000 multiplier!)
    assert df_wl["monetary_exposure"].dropna().empty
    assert (df_wl["exposure_column_source"] == "NONE_PHYSICAL_UNITS").all()


# =============================================================================
# 7. TEMPORAL TREND: CROSS-SECTIONAL DATASET REJECTION
# =============================================================================
def test_analyze_temporal_trends_cross_sectional_rejection(tmp_path):
    n = 80
    df_cross = pd.DataFrame({
        "customer_id": [f"CUST_{i}" for i in range(n)],
        "age": np.random.randint(18, 70, n),
        "tenure": np.random.randint(1, 60, n),
        "duration": np.random.randint(10, 500, n),
        "months_on_book": np.random.randint(1, 36, n),
        "churn": np.random.choice([0, 1], n)
    })
    out_dir = tmp_path / "cross_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = analyze_temporal_trends(df_cross, out_dir)
    assert result["is_temporal_dataset"] is False
    assert result["date_column"] is None
    assert result["period_count"] == 0
    assert "Cross-sectional" in result["summary_note"]


# =============================================================================
# 8. TEMPORAL TREND: TRUE CALENDAR DATES & STAGE 6 INTEGRATION
# =============================================================================
def test_analyze_temporal_trends_calendar_dates_and_stage6_chart(tmp_path):
    n = 120
    dates = pd.date_range(start="2023-01-01", periods=6, freq="MS")
    date_col = np.random.choice(dates, n)

    df_temporal = pd.DataFrame({
        "order_id": [f"ORD_{i:04d}" for i in range(n)],
        "order_date": date_col,
        "segment": np.random.choice(["Retail", "Wholesale"], n),
        "amount": np.random.uniform(50, 500, n),
        "is_defective": np.random.choice([0, 1], n)
    })
    out_dir = tmp_path / "temporal_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    df_temporal.to_parquet(out_dir / "bi_ready_fact.parquet")

    # Run temporal trend engine
    res = analyze_temporal_trends(df_temporal, out_dir)
    assert res["is_temporal_dataset"] is True
    assert res["date_column"] == "order_date"
    assert res["period_count"] >= 2

    # Run Stage 6 semantic and viz synthesizer
    synthesize_semantic_and_viz(str(out_dir))
    vega_spec_path = out_dir / "vega_lite_dashboard_spec.json"
    assert vega_spec_path.exists()

    bundle = json.loads(vega_spec_path.read_text(encoding="utf-8"))
    assert "temporal_risk_trend" in bundle["specs"], "Stage 6 must include 5th chart 'temporal_risk_trend'"
    assert bundle["specs"]["temporal_risk_trend"]["id"] == "v5_temporal_risk_trend"


# =============================================================================
# 9. PLAIN BUSINESS SUMMARY: CIRCUIT-BREAKER HONESTY & BILINGUAL
# =============================================================================
def test_plain_business_summary_circuit_breaker_honesty_and_bilingual(tmp_path):
    n = 100
    df = pd.DataFrame({
        "id": range(n),
        "department": np.random.choice(["HR", "Engineering", "Sales"], n),
        "attrition": np.random.choice([0, 1], n)
    })
    out_dir = tmp_path / "summary_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Trigger Circuit Breaker (is_prim_significant = False)
    prim_info_noise = {
        "prim_dim": "department",
        "is_prim_significant": False,
        "prim_p_val": 0.42,
        "top_leak_segment": "Sales",
        "top_leak_rate": 22.0,
        "baseline_rate": 20.0
    }
    p_path = generate_plain_business_summary(df, out_dir, prim_dim_info=prim_info_noise)
    text = p_path.read_text(encoding="utf-8")

    assert "## 🇬🇧 Executive Business Summary" in text
    assert "## 🇮🇳 Business X-Ray Summary" in text
    assert "$0 Spend Advisory" in text or "🛑 $0 Spend Advisory" in text
    assert "$0 CapEx" in text or "Paisa Bachao" in text
    # Honesty invariant: when CB is active, do NOT promise 15%/35%/65% reductions
    assert "15% reduction" not in text
    assert "35% reduction" not in text
    assert "65% failure reduction" not in text


def test_plain_business_summary_telecom_users_grounding(telecom_output_dir):
    summary_path = telecom_output_dir / "PLAIN_BUSINESS_SUMMARY.md"
    assert summary_path.exists(), "telecom_users PLAIN_BUSINESS_SUMMARY.md must exist"
    text = summary_path.read_text(encoding="utf-8")

    # Physical grounding checks
    assert "5,986" in text
    assert "1,587" in text
    assert "Mensal" in text
    assert "TipoContrato" in text
    assert "MesesComoCliente" in text
    assert "Business X-Ray Summary" in text

    # No 'N/A' 0.00% artifacts, synthetic column leaks, or scientific p-value jargon
    assert "= 'N/A'" not in text
    assert "= \"N/A\"" not in text
    assert "at **0.00%**" not in text
    assert "at 0.00%" not in text
    assert "Service Friction Penalty Index" not in text
    assert "p = " not in text

    # Exact DuckDB-grounded rest-of-business rate for TipoContrato != 'Mensal' (189 / 2717 = 6.96%)
    assert "42.77%" in text
    assert "6.96%" in text

    # Real physical $ amounts in Block 4 (FormaPagamento = BoletoEletronico) & clean Roman Hinglish
    assert "$10,913.54" in text and "$26,223.91" in text and "$43,732.68" in text
    assert "*Fayda*:" in text and "*Nuksan*:" in text


def test_actionable_priority_worklist_telecom_no_demographic_bias(telecom_output_dir):
    import time
    wl_path = telecom_output_dir / "actionable_priority_worklist.csv"
    assert wl_path.exists(), "Worklist CSV must exist"
    df_wl = pd.read_csv(wl_path)

    # Assert no demographic/gender bias in primary_risk_reason
    reasons = " ".join(df_wl["primary_risk_reason"].dropna().tolist()).lower()
    assert "genero" not in reasons, "Demographic column 'genero' must NOT be used in primary risk reason!"
    assert "feminino" not in reasons, "'feminino' must NOT be used in primary risk reason!"
    assert "masculino" not in reasons, "'masculino' must NOT be used in primary risk reason!"
    assert "penalty" not in reasons, "Synthetic column must NOT be used in primary risk reason!"

    # Assert operational column 'TipoContrato' is present in risk reason
    assert "tipocontrato" in reasons or "mensal" in reasons

    # Verify vectorized speed (< 1.0s for generating 6,000 rows without iterrows)
    df_fact = pd.read_parquet(telecom_output_dir / "bi_ready_fact.parquet")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        generate_actionable_priority_worklist(df_fact, Path(tmp_dir))
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"Worklist generation took {elapsed:.2f}s, expected < 1.0s vectorized execution"


# =============================================================================
# 10. ANTI-HALLUCINATION GUARD: CHECK 10 TAMPER DETECTION
# =============================================================================
def test_anti_hallucination_guard_check_10_tamper_detection(tmp_path):
    n = 50
    df = pd.DataFrame({
        "user_id": [f"U_{i}" for i in range(n)],
        "segment": ["A"] * 25 + ["B"] * 25,
        "churn": [0] * 40 + [1] * 10
    })
    out_dir = tmp_path / "tamper_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "bi_ready_fact.parquet")

    # Generate legitimate worklist first
    generate_actionable_priority_worklist(df, out_dir)

    # Tamper with worklist: inject fake ID that does not exist in fact table
    wl_file = out_dir / "actionable_priority_worklist.csv"
    df_wl = pd.read_csv(wl_file)
    df_wl.loc[0, "user_id"] = "FAKE_INVENTED_ID_9999"
    df_wl.to_csv(wl_file, index=False)

    report = run_anti_hallucination_audit(str(out_dir))
    assert report["grounding_confidence"] != "100.0% VERIFIED TRUTH"
    violations = " ".join(report.get("physics_invariant_violations", []))
    assert "Worklist Physical Lineage Breach" in violations


def test_anti_hallucination_guard_catches_cross_wired_rate_and_jargon(tmp_path):
    df = pd.DataFrame({
        "user_id": [f"U_{i}" for i in range(100)],
        "contract_type": ["Monthly"] * 50 + ["Annual"] * 50,
        "monthly_amount": [100.0] * 100,
        "churn": [1] * 25 + [0] * 25 + [1] * 5 + [0] * 45,  # Monthly=50.0%, Annual=10.0%
    })
    out_dir = tmp_path / "rate_tamper_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "bi_ready_fact.parquet")

    p_path = generate_plain_business_summary(df, out_dir)
    valid_report = run_anti_hallucination_audit(str(out_dir))
    assert valid_report["grounding_confidence"] == "100.0% VERIFIED TRUTH"

    # Tamper rest-of-business rate (10.0% -> 29.99%) and inject scientific p-value jargon
    tampered = p_path.read_text(encoding="utf-8").replace("compared to 10.0%", "compared to 29.99%").replace("compared to 10.00%", "compared to 29.99%")
    tampered += "\nJargon leak: p = 0.0000e+00\n"
    p_path.write_text(tampered, encoding="utf-8")

    bad_report = run_anti_hallucination_audit(str(out_dir))
    assert bad_report["grounding_confidence"] != "100.0% VERIFIED TRUTH"
    violations = " ".join(bad_report.get("physics_invariant_violations", []))
    assert "Plain Business Summary Cross-Wired Rate Mismatch" in violations
    assert "Plain Business Summary Jargon Leak" in violations


# =============================================================================
# 11. FASTAPI: HEALTH ENDPOINT
# =============================================================================
def test_fastapi_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "DataX-Ray" in data["engine"]


# =============================================================================
# 12. FASTAPI: ASK ENDPOINT & PATH TRAVERSAL DEFENSE
# =============================================================================
def test_fastapi_ask_endpoint_grounding_and_path_traversal_defense(client, telecom_output_dir):
    # Legitimate Q&A
    req_body = {
        "output_dir": str(telecom_output_dir),
        "question": "What is our overall volume and churn count?",
        "language": "english",
        "use_llm": False
    }
    resp = client.post("/api/v1/ask", json=req_body)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["grounding_verified"] is True
    assert "5,986" in res_data["answer_markdown"]

    # Adversarial Path Traversal Attack
    traversal_body = {
        "output_dir": "../../Windows/System32",
        "question": "Show all users",
        "language": "english",
        "use_llm": False
    }
    trap_resp = client.post("/api/v1/ask", json=traversal_body)
    assert trap_resp.status_code == 403


# =============================================================================
# 13. FASTAPI: ANALYZE-UPLOAD PIPELINE & DOWNLOAD
# =============================================================================
def test_fastapi_analyze_upload_end_to_end_and_download(client):
    # Build clean synthetic CSV upload (30 rows to support clean statistical inference)
    rows = ["client_id,contract_type,monthly_fee,is_churn"]
    for i in range(30):
        c_type = "Monthly" if i % 2 == 0 else ("Annual" if i % 3 == 0 else "TwoYear")
        fee = 50.0 + (i * 2.5)
        churn = 1 if (c_type == "Monthly" and fee > 70) else 0
        rows.append(f"C{i:03d},{c_type},{fee:.1f},{churn}")
    csv_content = "\n".join(rows) + "\n"

    files = [
        ("files", ("test_clients.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv"))
    ]
    data = {
        "mode": "templated",
        "language": "hinglish"
    }

    upload_resp = client.post("/api/v1/analyze-upload", data=data, files=files)
    assert upload_resp.status_code == 200
    resp_json = upload_resp.json()

    assert resp_json["status"] == "success"
    assert "run_id" in resp_json
    assert len(resp_json.get("worklist_preview", [])) > 0
    assert len(resp_json.get("plain_summary_markdown", "")) > 100
    run_id = resp_json["run_id"]

    # Test file download endpoint
    dl_resp = client.get(f"/api/v1/download/{run_id}/actionable_priority_worklist.csv")
    assert dl_resp.status_code == 200
    assert "client_id" in dl_resp.text
    assert "PREVENTIVE_RETENTION_WATCH" in dl_resp.text or "REALIZED_LOSS_RECOVERY_AUDIT" in dl_resp.text


# =============================================================================
# 14. FASTAPI: ZIP-SLIP REJECTION & DOWNLOAD SECURITY
# =============================================================================
def test_fastapi_zip_slip_rejection_and_download_security(client):
    # Create malicious Zip-Slip archive
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("../../evil_escape.csv", "id,val\n1,2\n")

    files = [
        ("files", ("malicious.zip", io.BytesIO(zip_buf.getvalue()), "application/zip"))
    ]
    data = {"mode": "templated", "language": "english"}

    resp = client.post("/api/v1/analyze-upload", data=data, files=files)
    assert resp.status_code == 400
    assert "Security Violation" in resp.json()["detail"] or "Zip-Slip" in resp.json()["detail"]

    # Test download security: disallowed artifact
    disallowed_resp = client.get("/api/v1/download/test_run/secret_internal.key")
    assert disallowed_resp.status_code == 400

    # Test download security: traversal attempt
    traversal_dl = client.get("/api/v1/download/run_123/../../.env")
    assert traversal_dl.status_code in (400, 404, 422)
