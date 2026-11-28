from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine.conversational_qa_engine import (
    ConversationalBusinessQAEngine,
    clear_qa_response_cache,
    get_qa_cache_stats,
)
from autonomous_engine.growth_inventory_engine import analyze_growth_and_inventory
from autonomous_engine.api_server import app
from tests.test_weakness1_sales_stock_engine import _make_indian_shopkeeper_sales_df


def test_w3_zero_rpm_shopkeeper_hinglish_sql_and_response_cache(tmp_path):
    clear_qa_response_cache()
    df = _make_indian_shopkeeper_sales_df()
    df.to_parquet(tmp_path / "bi_ready_fact.parquet", index=False)
    analyze_growth_and_inventory(df, out_dir=tmp_path)

    with ConversationalBusinessQAEngine(tmp_path) as qa:
        with patch.object(qa, "translate_question_to_sql", side_effect=AssertionError("LLM must NOT be called on 0-RPM fast-path or cache hit!")):
            # 1. Hindi forecast fast-path (0 RPM)
            r_fc = qa.ask("अगले महीने कितनी बिक्री होगी?", language="auto", use_llm=True)
            assert r_fc["status"] == "success"
            assert r_fc["sql_generation_mode"] == "growth_inventory_fastpath"
            assert r_fc["cache_hit"] is False
            assert "अनुमानित बिक्री" in r_fc["answer_markdown"]

            # 2. Repeat query hits per-run cache (0 RPM, cache_hit=True)
            r_fc2 = qa.ask("अगले महीने कितनी बिक्री होगी?  ", language="auto", use_llm=True)
            assert r_fc2["status"] == "success"
            assert r_fc2["cache_hit"] is True

            # 3. Colloquial Hindi low-stock query -> exact DuckDB SQL at 0 RPM
            r_stk = qa.ask("कौन सा स्टॉक सबसे कम है?", language="auto", use_llm=True)
            assert r_stk["status"] == "success"
            assert r_stk["sql_generation_mode"] == "deterministic_shopkeeper_fastpath"
            assert r_stk["data"][0]["item"] == "Basmati Rice 25kg"
            assert float(r_stk["data"][0]["current_stock"]) == 8.0

            # 4. Colloquial Hinglish top-selling item -> exact DuckDB SQL at 0 RPM
            r_top = qa.ask("sabse zyada bikne wala item batao", language="auto", use_llm=True)
            assert r_top["status"] == "success"
            assert r_top["data"][0]["item"] == "Basmati Rice 25kg"

            # 5. Colloquial Hinglish bakaya / udhaar party -> exact DuckDB SQL at 0 RPM
            r_due = qa.ask("kis party par sabse zyada bakaya hai?", language="auto", use_llm=True)
            assert r_due["status"] == "success"
            assert r_due["data"][0]["party"] == "Sharma Kirana"
            assert float(r_due["data"][0]["total_pending_due"]) > 0

    assert get_qa_cache_stats()["entries"] >= 4


def test_w3_cloud_status_reports_rpm_capacity_and_sandbox_posture():
    client = TestClient(app)
    resp = client.get("/api/v1/system/cloud-status")
    assert resp.status_code == 200
    body = resp.json()
    assert "llm_capacity" in body
    assert body["llm_capacity"]["per_key_rpm_limit"] >= 1
    assert "ask_ai_cache" in body["llm_capacity"]
    assert body["ai_codegen_sandbox_posture"] in (
        "disabled_deterministic_only",
        "container_isolated",
        "local_dev_ast_only",
    )
