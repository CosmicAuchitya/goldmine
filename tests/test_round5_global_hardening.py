"""
Round-5 Global-Earth Hardening Regression Tests:
1. Multilingual global adverse statuses (ES/PT/FR/DE/IT/JP/CN/AR/KR) & ¥/global currency parsing.
2. OWASP CWE-1236 CSV Formula Injection defense in priority worklist export.
3. CFO Pareto 80/20 customer concentration Q&A & Universal Unknown-Metric Refusal Guard.
4. Zero dead 404 Gemini fallback models in PacedGeminiClient.
"""
import re
from pathlib import Path
import numpy as np
import pandas as pd

from autonomous_engine.robust_excel_scanner import clean_accounting_series
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
from autonomous_engine.business_action_exporter import generate_actionable_priority_worklist
from autonomous_engine.conversational_qa_engine import ConversationalBusinessQAEngine
from autonomous_engine import rate_limiter


def test_global_multilingual_adverse_statuses_and_yen_currency():
    df = pd.DataFrame({
        "id_pedido": [f"JP-{i}" for i in range(40)],
        "sucursal": ["東京支店", "大阪支店", "شركة النور", "Sucursal Madrid"] * 10,
        "importe_jpy": [f"¥{15000 + i * 1000:,}" for i in range(40)],
        "estado_pedido": (["Cancelado", "Devuelto", "Annulé", "Storniert", "キャンセル", "ملغي"] + ["Entregado"] * 14) * 2,
    })
    df["importe_jpy"] = clean_accounting_series(df["importe_jpy"])
    assert pd.api.types.is_numeric_dtype(df["importe_jpy"])
    assert float(df["importe_jpy"].iloc[0]) == 15000.0

    canon = resolve_canonical_target_and_cost(df)
    assert canon["target_col"] == "estado_pedido"
    assert int(canon["binary_target"].sum()) == 12
    assert canon["cost_col"] == "importe_jpy"
    assert canon["unit_symbol"] == "¥"
    assert canon["currency_code"] == "JPY"


def test_owasp_cwe1236_csv_formula_injection_neutralized(tmp_path: Path):
    df = pd.DataFrame({
        "order_id": ["ORD-1", "ORD-2", "ORD-3", "ORD-4", "ORD-5", "ORD-6"] * 5,
        "vendor_name": [
            "=CMD|' /C calc'!A0",
            "+SUM(A1:A5)",
            "@HYPERLINK(\"http://evil.example\")",
            "-2+3+cmd|' /C calc'!A0",
            "SafeVendorA",
            "SafeVendorB",
        ] * 5,
        "invoice_amount": [-250.0, 1200.0, 950.0, 800.0, 500.0, 450.0] * 5,
        "order_status": ["Returned", "Returned", "Returned", "Delivered", "Delivered", "Delivered"] * 5,
    })
    wl_path = generate_actionable_priority_worklist(df, tmp_path)
    raw_csv = wl_path.read_text(encoding="utf-8")
    # Dangerous formula cells must be prefixed with single quote and NEVER start raw at cell boundary
    assert not re.search(r'(?:^|,)"?(?:=CMD|\+SUM|@HYPERLINK|-2\+3)', raw_csv, flags=re.M)
    assert "'=CMD|' /C calc'!A0" in raw_csv
    # Legitimate numeric negative value (-250.0) in numeric exposure column must remain numeric
    assert "-250.0" in raw_csv


def test_cfo_pareto_80_20_and_unknown_metric_guard(tmp_path: Path):
    n = 300
    custs = [f"CUST-{i % 25:03d}" for i in range(n)]
    # Skew top 5 customers (20%) to generate massive revenue
    revs = [5000.0 if int(c.split("-")[1]) < 5 else 200.0 for c in custs]
    df = pd.DataFrame({
        "order_id": [f"O-{i}" for i in range(n)],
        "customer_id": custs,
        "revenue_usd": revs,
        "order_status": ["Returned" if i % 5 == 0 else "Delivered" for i in range(n)],
    })
    df.to_parquet(tmp_path / "bi_ready_fact.parquet", index=False)
    qa = ConversationalBusinessQAEngine(tmp_path)
    try:
        # 1. Pareto 80/20 concentration query
        res_pareto = qa.ask("What percentage of total revenue comes from top 20% customers?")
        assert res_pareto["status"] == "success"
        assert res_pareto["row_count_returned"] == 1
        row = res_pareto["data"][0]
        assert int(row["top_cohort_entities"]) == 5
        assert int(row["total_unique_entities"]) == 25
        assert float(row["top_cohort_revenue_share_pct"]) > 80.0
        assert "**5**" in res_pareto["answer_markdown"] and "5.00%" not in res_pareto["answer_markdown"]

        # 2. Universal unknown-metric refusal (zero fabricated numbers, zero blank NULL bullets)
        res_missing = qa.ask("What are our carbon_emissions and bitcoin_price?")
        assert res_missing["status"] in ("success", "missing_data_explained")
        assert res_missing["sql_generation_mode"] == "missing_column_guard"
        assert res_missing["row_count_returned"] == 0
        assert "not present" in res_missing["answer_markdown"].lower() or "not available" in res_missing["answer_markdown"].lower()
    finally:
        qa.close()


def test_dead_404_gemini_model_removed_from_fallback():
    src = Path(rate_limiter.__file__).read_text(encoding="utf-8")
    assert '"gemini-2.5-flash-lite"' not in src
    assert "_DEAD_GEMINI_MODELS" in src
