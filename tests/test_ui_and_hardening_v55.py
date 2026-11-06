"""
================================================================================
UNIT & HEADLESS UI TESTS: V5.5 PORTAL, DETERMINISTIC BLUEPRINT & LLM CLIENT
================================================================================
"""

import json
import re
from pathlib import Path
import pandas as pd
import pytest


def test_escape_currency_markdown_preserves_latex():
    """Currency $ signs and ($) headers must be escaped without breaking real LaTeX."""
    from autonomous_engine.app_dashboard import escape_currency_markdown

    sample = (
        "Direct liability is **$117,699.65** (out of $387,906.05) with range $5,000 - $15,000, "
        "table header Total Liability ($), while statistical test shows $\\neq$ and $p < 0.05$."
    )
    escaped = escape_currency_markdown(sample)
    assert r"\$117,699.65" in escaped
    assert r"\$387,906.05" in escaped
    assert r"\$5,000 - \$15,000" in escaped
    assert r"(\$)" in escaped
    # Genuine LaTeX math must remain untouched
    assert "$\\neq$" in escaped
    assert "$p < 0.05$" in escaped
    # Idempotency: escaping twice must not double-escape \\$ into \\\\$
    assert escape_currency_markdown(escaped) == escaped


def test_stage2_deterministic_use_llm_false(tmp_path):
    """generate_relational_blueprint(use_llm=False) must run offline with zero network calls."""
    from autonomous_engine.stage2_ai_blueprint import generate_relational_blueprint

    topo = {
        "dataset_name": "synthetic_saas",
        "tables": {
            "accounts": {
                "estimated_rows": 500,
                "columns": ["account_id", "plan_tier", "mrr", "churned"],
                "recommended_primary_key": "account_id",
            }
        },
    }
    topo_p = tmp_path / "schema_topology.json"
    bp_p = tmp_path / "execution_blueprint.json"
    topo_p.write_text(json.dumps(topo), encoding="utf-8")

    bp = generate_relational_blueprint(str(topo_p), str(bp_p), use_llm=False)
    assert bp["fact_table"] == "accounts"
    assert bp["primary_id_column"] == "account_id"
    assert bp["target_metric"] == "churned"
    assert "dataset_fingerprint" in bp
    assert bp_p.exists()


def test_rate_limiter_generate_text_alias_and_pool_status(monkeypatch):
    """PacedGeminiClient must expose generate_text() delegating to generate_content() and get_pool_status()."""
    from autonomous_engine.rate_limiter import PacedGeminiClient

    pacer = PacedGeminiClient(max_calls_per_minute=14, quiet=True)
    status = pacer.get_pool_status()
    assert status["max_calls_per_key"] == 14
    assert status["num_keys"] >= 1

    captured = {}

    def fake_generate_content(contents, system_instruction=None, max_retries=5):
        captured["contents"] = contents
        captured["system_instruction"] = system_instruction
        captured["max_retries"] = max_retries
        return '{"sql": "SELECT COUNT(*) FROM fact", "explanation": "ok"}'

    monkeypatch.setattr(pacer, "generate_content", fake_generate_content)
    out = pacer.generate_text(prompt="How many rows?", system_instruction="JSON only", max_retries=2)
    assert "SELECT COUNT(*)" in out
    assert captured["contents"] == "How many rows?"
    assert captured["max_retries"] == 2


def test_streamlit_portal_headless_render_and_legacy_kpi_fallback(tmp_path):
    """
    Headless Streamlit AppTest must render with 0 errors even on a legacy benchmark
    folder that lacks semantic_metrics_manifest.json, computing live ground-truth KPIs.
    """
    from streamlit.testing.v1 import AppTest

    out_dir = tmp_path / "legacy_bench" / "output"
    out_dir.mkdir(parents=True)

    df = pd.DataFrame({
        "customer_id": [f"C{i:03d}" for i in range(60)],
        "contract_type": ["Monthly"] * 30 + ["Annual"] * 30,
        "monthly_fee": [80.0] * 30 + [50.0] * 30,
        "tenure_months": list(range(1, 61)),
        "churn": [1] * 18 + [0] * 12 + [1] * 3 + [0] * 27,
    })
    df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)
    (out_dir / "execution_blueprint.json").write_text(
        json.dumps({
            "project_title": "Legacy SaaS Test",
            "fact_table": "customers",
            "primary_id_column": "customer_id",
            "target_metric": "churn",
        }),
        encoding="utf-8",
    )

    app_path = Path(__file__).resolve().parent.parent / "autonomous_engine" / "app_dashboard.py"
    at = AppTest.from_file(str(app_path), default_timeout=60)
    at.session_state["active_output_dir"] = str(out_dir)
    at.run()

    errs = [e.value for e in at.exception] + [e.value for e in at.error]
    assert errs == [], f"Unexpected Streamlit errors: {errs}"

    # Verify live canonical KPI fallback computed 21 adverse events (35.00%) instead of 0 (0.00%)
    cards_html = "\n".join(m.value for m in at.markdown)
    assert "ADVERSE EVENTS (35.00%)" in cards_html
    assert "$1,590.00" in cards_html  # 18*80 + 3*50 = 1440 + 150 = $1,590.00 adverse drag!

    # Verify automatic V5.5 hydration created summary, worklist, and bespoke dashboard
    assert (out_dir / "PLAIN_BUSINESS_SUMMARY.md").exists()
    assert (out_dir / "actionable_priority_worklist.csv").exists()
    assert (out_dir / "bespoke_executive_dashboard.html").exists()

    # Verify zero unescaped currency $ signs in rendered prose markdown
    prose_blocks = [
        m.value for m in at.markdown
        if "<style>" not in m.value and "metric-card-box" not in m.value and "exec-meta-card" not in m.value
    ]
    raw_leaks = re.findall(r'(?<!\\)\$-?\d[\d,.]*', "\n".join(prose_blocks))
    assert raw_leaks == [], f"Unescaped currency $ found in UI markdown: {raw_leaks}"
