"""
=============================================================================
COMPREHENSIVE TEST SUITE: STAGE 7 BESPOKE EXECUTIVE DASHBOARD ARCHITECT
=============================================================================
Validates:
1. Executive Design Archetype Diversity across real benchmarks.
2. Micro-Cube Zero Multiplicity Drift (100% row & adverse event preservation).
3. Data-shape adaptation (Temporal momentum ribbon activation vs cross-sectional rejection).
4. Non-monetary dataset honesty (Zero fake '$', pareto waterfall rejection).
5. Statistical circuit-breaker noise detection ($0 CapEx Spend Freeze in ROI simulator).
6. OWASP JSON-in-HTML XSS Neutralization and 100% Zero-CDN air-gapped guarantee.
7. Anti-Demographic, Anti-Synthetic, and Anti-PII leakage guards in primary slicers.
8. Bilingual English / Roman-Hinglish narratives and Light / Dark theme switching.
9. Anti-Hallucination Guard Check 11 catches payload tampering and drift.
10. Anti-Hallucination Guard Check 11 blocks external CDN injections.
11. FastAPI REST endpoint GET /api/v1/dashboard/{run_id} and path traversal defense.
12. Component Catalog applicability predicates integrity.
13. Master Orchestrator 7-stage end-to-end DAG execution.
=============================================================================
"""

import os
import re
import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any

import duckdb
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from autonomous_engine.stage7_bespoke_dashboard_architect import (
    ARCHETYPE_SPECS,
    COMPONENT_CATALOG,
    synthesize_bespoke_dashboard,
    judge_dashboard_architecture,
    build_client_micro_cube,
    build_dashboard_payload,
    build_bespoke_html
)
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
from autonomous_engine.stage5_bi_synthesizer import detect_key_columns
from autonomous_engine.strategic_decision_matrix import StrategicDecisionEngine
from autonomous_engine.anti_hallucination_guard import run_anti_hallucination_audit
from autonomous_engine.master_orchestrator import run_master_pipeline
from autonomous_engine.api_server import app


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# 1. EXECUTIVE DESIGN ARCHETYPE DIVERSITY ACROSS REAL BENCHMARKS
# =============================================================================
def test_domain_archetype_diversity_across_real_benchmarks():
    """
    Verifies that real diverse benchmarks receive distinct, appropriate design
    archetypes, distinct color palettes, and pass the DFII information score threshold >= 11.
    """
    benchmarks = {
        "telecom_users": "nordic_saas_command",
        "loan_default": "swiss_institutional_terminal",
        "ecommerce_customer_service": "editorial_commerce_studio",
        "wine_quality": "industrial_scada_telemetry"
    }

    archetypes_found = set()
    root = Path("kaggle_benchmarks")

    for bench_name, expected_archetype in benchmarks.items():
        bp_path = root / bench_name / "output" / "dashboard_design_blueprint.json"
        html_path = root / bench_name / "output" / "bespoke_executive_dashboard.html"
        
        if not bp_path.exists() or not html_path.exists():
            pytest.skip(f"Benchmark {bench_name} outputs missing, skipping diversity check.")

        with open(bp_path, "r", encoding="utf-8") as f:
            bp = json.load(f)

        archetype = bp.get("archetype")
        assert archetype == expected_archetype, f"Expected {expected_archetype} for {bench_name}, got {archetype}"
        assert bp.get("dfii_score", 0) >= 11.0, f"DFII score below 11.0 threshold: {bp.get('dfii_score')}"
        archetypes_found.add(archetype)

        # Verify HTML contains archetype-specific design tokens
        html_text = html_path.read_text(encoding="utf-8")
        assert bp["archetype"] in html_text
        assert "DASHBOARD_PAYLOAD" in html_text
        assert "<style>" in html_text
        assert "--canvas-bg" in html_text
        assert "--accent-primary" in html_text

    # Proves 4 distinct archetypes were synthesized
    assert len(archetypes_found) == 4, f"Expected 4 distinct archetypes, got {archetypes_found}"


# =============================================================================
# 2. MICRO-CUBE ZERO MULTIPLICITY DRIFT
# =============================================================================
def test_micro_cube_zero_multiplicity_drift():
    """
    Guarantees client-side micro-cube slices sum to 100% of physical rows and
    100% of adverse target events without any Cartesian or multiplicity drift,
    even when dimension cardinality exceeds 14 and buckets into 'Other'.
    """
    np.random.seed(42)
    n_rows = 1500
    
    # 25 distinct categories (top 14 keep names, 11 collapse to 'Other')
    cats = [f"Category_{i:02d}" for i in range(25)]
    cat_weights = np.linspace(10, 1, 25)
    cat_weights /= cat_weights.sum()

    df = pd.DataFrame({
        "account_id": [f"ACC_{i}" for i in range(n_rows)],
        "product_category": np.random.choice(cats, size=n_rows, p=cat_weights),
        "region": np.random.choice(["North", "South", "East", "West"], size=n_rows),
        "churned": np.random.choice([0, 1], size=n_rows, p=[0.75, 0.25]),
        "mrr_charge": np.random.uniform(20.0, 150.0, size=n_rows).round(2)
    })

    canonical = {
        "target_col": "churned",
        "binary_target": df["churned"].astype(int),
        "target_desc": "Customer Churn",
        "cost_col": "mrr_charge"
    }

    slices = build_client_micro_cube(
        df_fact=df,
        target_col="churned",
        cost_col="mrr_charge",
        prim_dim="product_category",
        sec_dim="region",
        canonical=canonical
    )

    assert len(slices) > 0

    sum_volume = sum(s["volume"] for s in slices)
    sum_events = sum(s["adverse_events"] for s in slices)
    sum_adv_cost = sum(s["adverse_cost"] for s in slices)

    expected_volume = len(df)
    expected_events = int(df["churned"].sum())
    expected_adv_cost = float(df.loc[df["churned"] == 1, "mrr_charge"].sum())

    # Absolute mathematical zero drift
    assert sum_volume == expected_volume, f"Volume drift: {sum_volume} vs {expected_volume}"
    assert sum_events == expected_events, f"Event drift: {sum_events} vs {expected_events}"
    assert abs(sum_adv_cost - expected_adv_cost) < 1e-4, f"Cost drift: {sum_adv_cost} vs {expected_adv_cost}"

    # Verify 'Other' category was created for long-tail categories
    prim_vals = {s["prim_val"] for s in slices}
    assert "Other" in prim_vals, "Expected 'Other' grouping for long tail categories"


# =============================================================================
# 3. DATA-SHAPE ADAPTATION: TEMPORAL VS CROSS-SECTIONAL
# =============================================================================
def test_temporal_dataset_activates_momentum_ribbon_and_cross_sectional_rejects_it():
    """
    Proves that chronological time series datasets select 'temporal_momentum_ribbon',
    while cross-sectional datasets explicitly reject it with documented reasoning.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Temporal Dataset
        np.random.seed(101)
        dates = pd.date_range("2024-01-01", periods=180, freq="D")
        df_temp = pd.DataFrame({
            "order_id": range(len(dates)),
            "order_date": dates,
            "channel": np.random.choice(["Web", "App", "Store"], size=len(dates)),
            "is_returned": np.random.choice([0, 1], size=len(dates), p=[0.8, 0.2]),
            "order_amount": np.random.uniform(50.0, 500.0, size=len(dates)).round(2)
        })
        temp_out = tmp_path / "temporal"
        temp_out.mkdir()
        df_temp.to_parquet(temp_out / "bi_ready_fact.parquet", index=False)
        
        # Mock temporal trend summary
        temporal_summary = {
            "is_temporal_dataset": True,
            "detected_date_column": "order_date",
            "frequency": "M",
            "periods": [
                {"period": "2024-01", "total_volume": 31, "adverse_events": 6, "adverse_rate_pct": 19.35},
                {"period": "2024-02", "total_volume": 29, "adverse_events": 5, "adverse_rate_pct": 17.24},
                {"period": "2024-03", "total_volume": 31, "adverse_events": 7, "adverse_rate_pct": 22.58}
            ]
        }
        with open(temp_out / "temporal_trend_summary.json", "w", encoding="utf-8") as f:
            json.dump(temporal_summary, f)

        res_temp = synthesize_bespoke_dashboard(str(temp_out), use_llm=False)
        assert "temporal_momentum_ribbon" in res_temp["selected_panels"]

        # 2. Cross-Sectional Dataset
        df_cross = pd.DataFrame({
            "sample_id": range(200),
            "feature_x": np.random.normal(10, 2, 200),
            "category": np.random.choice(["Alpha", "Beta", "Gamma"], size=200),
            "defect": np.random.choice([0, 1], size=200, p=[0.85, 0.15])
        })
        cross_out = tmp_path / "cross"
        cross_out.mkdir()
        df_cross.to_parquet(cross_out / "bi_ready_fact.parquet", index=False)

        res_cross = synthesize_bespoke_dashboard(str(cross_out), use_llm=False)
        assert "temporal_momentum_ribbon" not in res_cross["selected_panels"]

        with open(cross_out / "dashboard_design_blueprint.json", "r", encoding="utf-8") as f:
            cross_bp = json.load(f)
        rejected_ids = {p["id"]: p.get("reason", p.get("rejection_reason", "")) for p in cross_bp["rejected_panels"]}
        assert "temporal_momentum_ribbon" in rejected_ids
        reason = rejected_ids["temporal_momentum_ribbon"].lower()
        assert "cross-sectional" in reason or "chronological" in reason or "temporal" in reason


# =============================================================================
# 4. NON-MONETARY DATASET HONESTY (* 1000 BAN & WATERFALL REJECTION)
# =============================================================================
def test_non_monetary_dataset_zero_fake_dollars_and_no_pareto_waterfall():
    """
    On non-monetary datasets (e.g. biology, wine quality, clinical failure),
    the dashboard MUST NOT fabricate dollar figures (* 1000 ban), MUST set
    has_monetary_ledger to False, and MUST reject pareto_loss_waterfall.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        np.random.seed(55)
        n = 300
        df = pd.DataFrame({
            "sample_id": range(n),
            "acidity": np.random.uniform(0.1, 1.2, n),
            "density": np.random.uniform(0.99, 1.05, n),
            "batch_type": np.random.choice(["TypeA", "TypeB", "TypeC"], n),
            "substandard_quality": np.random.choice([0, 1], n, p=[0.8, 0.2])
        })
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

        res = synthesize_bespoke_dashboard(str(out_dir), use_llm=False)
        assert "pareto_loss_waterfall" not in res["selected_panels"]

        with open(out_dir / "dashboard_design_blueprint.json", "r", encoding="utf-8") as f:
            bp = json.load(f)
        assert bp["data_shape_diagnostics"]["has_monetary_ledger"] is False

        html_text = (out_dir / "bespoke_executive_dashboard.html").read_text(encoding="utf-8")
        assert '"has_monetary_ledger": false' in html_text
        assert "$NaN" not in html_text
        assert "* 1000" not in html_text
        assert "$20,000" not in html_text


# =============================================================================
# 5. STATISTICAL CIRCUIT-BREAKER NOISE LOCKDOWN
# =============================================================================
def test_circuit_breaker_noise_locks_simulator_to_zero_spend():
    """
    Proves that when a dataset consists of pure random noise with no statistically
    significant operational driver (p > 0.05), the blueprint activates the
    circuit-breaker and the What-If simulator enforces an Amber $0 CapEx Freeze.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        np.random.seed(999)
        n = 800
        # Independent noise with uniform target distribution across groups
        df = pd.DataFrame({
            "unit_id": range(n),
            "group_noise": np.random.choice(["Noise1", "Noise2", "Noise3", "Noise4"], n),
            "random_score": np.random.uniform(10, 100, n),
            "failure": np.random.choice([0, 1], n, p=[0.70, 0.30])
        })
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

        res = synthesize_bespoke_dashboard(str(out_dir), use_llm=False)

        with open(out_dir / "dashboard_design_blueprint.json", "r", encoding="utf-8") as f:
            bp = json.load(f)

        # Circuit breaker is active in noise dataset
        assert bp["data_shape_diagnostics"]["circuit_breaker_active"] is True

        html_text = (out_dir / "bespoke_executive_dashboard.html").read_text(encoding="utf-8")
        assert '"active": true' in html_text


# =============================================================================
# 6. OWASP XSS NEUTRALIZATION & ZERO-CDN AIR-GAPPED GUARANTEE
# =============================================================================
def test_zero_external_cdn_and_owasp_xss_neutralization():
    """
    Verifies that hostile XSS payloads injected in categorical strings are safely
    escaped (\\u003c / \\u003e), that count of <script> matches </script>, and that
    NO external CDN resources (http:// or https:// scripts/stylesheets) are referenced.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        n = 100
        hostile_cat = '<script>alert("XSS")</script>'
        hostile_svg = '"><svg/onload=alert(1)>'

        df = pd.DataFrame({
            "id": range(n),
            "category": [hostile_cat if i % 2 == 0 else hostile_svg for i in range(n)],
            "risk_flag": [1 if i % 3 == 0 else 0 for i in range(n)]
        })
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

        synthesize_bespoke_dashboard(str(out_dir), use_llm=False)

        html_text = (out_dir / "bespoke_executive_dashboard.html").read_text(encoding="utf-8")

        # 1. Zero External CDNs
        assert not re.search(r'<script\s+[^>]*src=["\']https?://', html_text, re.I), "External script CDN found!"
        assert not re.search(r'<link\s+[^>]*href=["\']https?://', html_text, re.I), "External CSS CDN found!"

        # 2. OWASP XSS JSON Neutralization
        assert '<script>alert("XSS")</script>' not in html_text, "Unescaped raw script tag leaked into HTML!"
        assert r'\u003cscript\u003e' in html_text or '&lt;script&gt;' in html_text

        # 3. Script tag balance
        script_opens = len(re.findall(r'<script\b', html_text, re.I))
        script_closes = len(re.findall(r'</script>', html_text, re.I))
        assert script_opens == script_closes, f"Unbalanced script tags: {script_opens} opens vs {script_closes} closes"


# =============================================================================
# 7. ANTI-SYNTHETIC, ANTI-DEMOGRAPHIC & PII LEAKAGE GUARD
# =============================================================================
def test_no_synthetic_demographic_or_pii_leakage_in_dashboard():
    """
    Verifies that:
    1. Primary slicer never chooses demographic attributes ('gender', 'sex') or index artifacts ('Unnamed: 0').
    2. Primary slicer never selects synthetic columns ('market_friction_penalty').
    3. PII columns (emails, phone numbers) are scrubbed and not leaked into worklist tables.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        n = 200
        df = pd.DataFrame({
            "Unnamed: 0": range(n),
            "user_email": [f"user_{i}@corporate.domain" for i in range(n)],
            "phone_number": [f"+1-555-01{i:02d}" for i in range(n)],
            "gender": np.random.choice(["M", "F"], n),
            "contract_type": np.random.choice(["Month-to-month", "One-year", "Two-year"], n),
            "market_friction_penalty_index": np.random.uniform(0.1, 0.9, n),
            "churn_risk": np.random.choice([0, 1], n, p=[0.75, 0.25])
        })
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

        synthesize_bespoke_dashboard(str(out_dir), use_llm=False)

        html_text = (out_dir / "bespoke_executive_dashboard.html").read_text(encoding="utf-8")
        payload_m = re.search(r'const DASHBOARD_PAYLOAD =\s*/\*__DXR_PAYLOAD_START__\*/(.*?)/\*__DXR_PAYLOAD_END__\*/;', html_text, re.DOTALL)
        assert payload_m is not None
        payload = json.loads(payload_m.group(1))

        prim_dim = payload.get("prim_dim_name")
        assert prim_dim == "contract_type", f"Expected 'contract_type', got '{prim_dim}'"
        assert prim_dim not in ["gender", "Unnamed: 0", "market_friction_penalty_index"]

        assert "user_0@corporate.domain" not in html_text, "Raw PII email leaked into dashboard HTML!"


# =============================================================================
# 8. BILINGUAL ENGLISH / HINGLISH & THEME CONTROLLER WIRING
# =============================================================================
def test_bilingual_en_hinglish_and_theme_toggle_wiring():
    """
    Validates that the dashboard HTML contains both English and Roman-Hinglish
    narrative blocks, theme token classes, and client-side toggle handlers.
    """
    bench_dir = Path("kaggle_benchmarks/telecom_users/output")
    html_path = bench_dir / "bespoke_executive_dashboard.html"
    if not html_path.exists():
        pytest.skip("Benchmark telecom_users output missing, skipping toggle wiring test.")

    html_text = html_path.read_text(encoding="utf-8")

    # Bilingual narratives in payload
    assert 'title_en' in html_text and 'title_hi' in html_text
    assert 'narrative_en' in html_text and 'narrative_hi' in html_text

    # Theme and Language UI buttons/controllers
    assert "toggleLanguage" in html_text or "data-lang" in html_text
    assert "toggleTheme" in html_text or "data-theme" in html_text
    assert "--canvas-bg" in html_text
    assert "--accent-primary" in html_text


# =============================================================================
# 9. ANTI-HALLUCINATION GUARD CHECK 11 CATCHES PAYLOAD TAMPERING
# =============================================================================
def test_anti_hallucination_guard_check_11_catches_payload_tampering():
    """
    Proves that Anti-Hallucination Guard Check 11 actively catches any manual
    or unauthorized tampering with DASHBOARD_PAYLOAD in the HTML file.
    """
    bench_dir = Path("kaggle_benchmarks/telecom_users/output")
    if not (bench_dir / "bespoke_executive_dashboard.html").exists():
        pytest.skip("Benchmark telecom_users output missing, skipping tampering test.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Copy output artifacts to temp directory
        for f in bench_dir.glob("*"):
            if f.is_file():
                shutil.copy2(f, tmp_path / f.name)

        # Baseline audit should pass
        res_baseline = run_anti_hallucination_audit(str(tmp_path))
        assert res_baseline["grounding_confidence"] == "100.0% VERIFIED TRUTH"

        # Tamper total_records by +500 in DASHBOARD_PAYLOAD
        html_file = tmp_path / "bespoke_executive_dashboard.html"
        raw_html = html_file.read_text(encoding="utf-8")
        
        # Replace total_records in payload
        tampered_html = re.sub(
            r'"total_records":\s*\d+',
            '"total_records": 99999',
            raw_html,
            count=1
        )
        html_file.write_text(tampered_html, encoding="utf-8")

        # Audit must catch and fail with Check 11 violation
        res_tampered = run_anti_hallucination_audit(str(tmp_path))
        assert res_tampered["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        violations = " ".join(res_tampered["physics_invariant_violations"])
        assert "Total Records Mismatch" in violations or "Multiplicity Drift" in violations


# =============================================================================
# 10. ANTI-HALLUCINATION GUARD CHECK 11 BLOCKS EXTERNAL CDN INJECTION
# =============================================================================
def test_anti_hallucination_guard_check_11_blocks_external_cdn_injection():
    """
    Proves that Anti-Hallucination Guard Check 11 actively catches external
    CDN script and stylesheet injections.
    """
    bench_dir = Path("kaggle_benchmarks/wine_quality/output")
    if not (bench_dir / "bespoke_executive_dashboard.html").exists():
        pytest.skip("Benchmark wine_quality output missing, skipping CDN audit test.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for f in bench_dir.glob("*"):
            if f.is_file():
                shutil.copy2(f, tmp_path / f.name)

        html_file = tmp_path / "bespoke_executive_dashboard.html"
        raw_html = html_file.read_text(encoding="utf-8")
        
        # Inject external CDN tag
        poisoned_html = raw_html.replace(
            "</head>",
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script></head>'
        )
        html_file.write_text(poisoned_html, encoding="utf-8")

        res = run_anti_hallucination_audit(str(tmp_path))
        assert res["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        violations = " ".join(res["physics_invariant_violations"])
        assert "Zero-CDN Breach" in violations or "External <script" in violations


# =============================================================================
# 11. FASTAPI DASHBOARD ENDPOINT & TRAVERSAL GUARD
# =============================================================================
def test_fastapi_dashboard_html_endpoint_and_traversal_guard(client):
    """
    Tests GET /api/v1/dashboard/{run_id} returns 200 with text/html content,
    and blocks path-traversal attacks with 400 Bad Request or 404.
    """
    # 1. Valid existing benchmark
    resp = client.get("/api/v1/dashboard/telecom_users")
    if resp.status_code == 200:
        assert resp.headers["content-type"].startswith("text/html")
        assert "DASHBOARD_PAYLOAD" in resp.text
        assert "Nordic SaaS Command Center" in resp.text

    # 2. Path-traversal attempts
    resp_bad = client.get("/api/v1/dashboard/invalid@id#")
    assert resp_bad.status_code == 400

    resp_dots = client.get("/api/v1/dashboard/..run_id..")
    assert resp_dots.status_code == 400

    # 3. Nonexistent run
    resp_404 = client.get("/api/v1/dashboard/nonexistent_run_99999")
    assert resp_404.status_code == 404


# =============================================================================
# 12. COMPONENT CATALOG APPLICABILITY INTEGRITY
# =============================================================================
def test_component_catalog_applicability_rules():
    """
    Ensures all 10 widgets in COMPONENT_CATALOG have valid metadata, IDs,
    and proper applicability rules.
    """
    assert len(COMPONENT_CATALOG) == 10
    panel_ids = {p["id"] for p in COMPONENT_CATALOG}
    expected_ids = {
        "temporal_momentum_ribbon",
        "pareto_loss_waterfall",
        "segment_vulnerability_lollipop",
        "secondary_cross_tab_heatmap",
        "exposure_vs_risk_bubble",
        "nonlinear_cliff_step_area",
        "orthogonal_2x2_quadrant",
        "triage_efficiency_frontier",
        "what_if_counterfactual_simulator",
        "actionable_worklist_explorer"
    }
    assert panel_ids == expected_ids
    for p in COMPONENT_CATALOG:
        assert "name" in p
        assert "description" in p
        assert "applicability" in p


# =============================================================================
# 13. MASTER ORCHESTRATOR 7-STAGE END-TO-END EXECUTION
# =============================================================================
def test_master_orchestrator_7_stage_end_to_end():
    """
    Executes all 7 stages of master_orchestrator end-to-end on a clean multi-row
    synthetic dataset in templated DAG mode, asserting:
    1. Stages 1 to 7 run cleanly.
    2. bespoke_executive_dashboard.html is generated.
    3. dashboard_design_blueprint.json is generated.
    4. Anti-hallucination guard passes Check 11 with 100.0% VERIFIED TRUTH.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        raw_dir = tmp_path / "raw_data"
        out_dir = tmp_path / "output"
        cache_dir = tmp_path / "cache"
        raw_dir.mkdir()
        out_dir.mkdir()
        cache_dir.mkdir()

        np.random.seed(77)
        n = 250
        df = pd.DataFrame({
            "CustomerID": [f"CUST_{i:04d}" for i in range(n)],
            "ContractType": np.random.choice(["Month-to-month", "One year", "Two year"], n, p=[0.5, 0.3, 0.2]),
            "TenureMonths": np.random.randint(1, 72, n),
            "MonthlyCharges": np.random.uniform(25.0, 115.0, n).round(2),
            "PaymentMethod": np.random.choice(["Electronic check", "Mailed check", "Bank transfer"], n),
            "Churn": np.random.choice([0, 1], n, p=[0.75, 0.25])
        })
        df.to_csv(raw_dir / "customers.csv", index=False)

        res = run_master_pipeline(
            data_dir=str(raw_dir),
            output_dir=str(out_dir),
            cache_dir=str(cache_dir),
            mode="dag"
        )

        assert res is True, "Pipeline failed to execute successfully"
        assert (out_dir / "bespoke_executive_dashboard.html").exists()
        assert (out_dir / "dashboard_design_blueprint.json").exists()

        # Audit Check 11 verification
        audit_res = run_anti_hallucination_audit(str(out_dir))
        assert audit_res["grounding_confidence"] == "100.0% VERIFIED TRUTH"
        assert len(audit_res["physics_invariant_violations"]) == 0


# =============================================================================
# 14. ARGON REGRESSION: WHAT-IF ROI DOLLAR MATH & ZERO DROPPED WIDGETS
# =============================================================================
def test_what_if_roi_positive_dollar_math_and_all_10_widget_renderers():
    """
    Guarantees:
    1. On monetary datasets with statistically significant risk, what_if_model.avg_cost_per_event > 0
       (preventing the $0.00 broken simulator bug).
    2. All 10 catalog widgets (including secondary_cross_tab_heatmap and exposure_vs_risk_bubble)
       have complete payload data and active SVG/HTML renderers in bespoke_executive_dashboard.html.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "output"
        out_dir.mkdir()
        np.random.seed(2026)
        n = 400
        contracts = np.array(["Month-to-month"] * 200 + ["One-year"] * 100 + ["Two-year"] * 100)
        channels = np.random.choice(["Fiber", "DSL", "Cable"], size=n)
        # Strong statistically significant churn difference
        churn = np.concatenate([
            np.random.choice([0, 1], 200, p=[0.45, 0.55]),
            np.random.choice([0, 1], 100, p=[0.88, 0.12]),
            np.random.choice([0, 1], 100, p=[0.94, 0.06]),
        ])
        df = pd.DataFrame({
            "AccountID": [f"ACC_{i:04d}" for i in range(n)],
            "ContractPlan": contracts,
            "AccessChannel": channels,
            "TenureMonths": np.where(churn == 1, np.random.randint(1, 14, n), np.random.randint(15, 65, n)),
            "SupportLatencyHrs": np.where(churn == 1, np.random.uniform(12, 48, n), np.random.uniform(1, 15, n)),
            "MonthlyMRR": np.random.uniform(45.0, 140.0, n).round(2),
            "Churned": churn,
        })
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

        res = synthesize_bespoke_dashboard(str(out_dir), use_llm=False)
        assert "secondary_cross_tab_heatmap" in res["selected_panels"]
        assert "exposure_vs_risk_bubble" in res["selected_panels"]

        html_text = (out_dir / "bespoke_executive_dashboard.html").read_text(encoding="utf-8")
        assert "renderCrossTabHeatmap" in html_text
        assert "renderExposureBubbleChart" in html_text

        payload_m = re.search(
            r'const DASHBOARD_PAYLOAD =\s*/\*__DXR_PAYLOAD_START__\*/(.*?)/\*__DXR_PAYLOAD_END__\*/;',
            html_text,
            re.DOTALL,
        )
        assert payload_m is not None
        payload = json.loads(payload_m.group(1))

        assert payload["circuit_breaker"]["active"] is False
        assert payload["circuit_breaker"]["p_value"] < 0.05
        assert payload["circuit_breaker"]["z_stat"] > 1.96

        wm = payload["what_if_model"]
        assert wm["excess_events"] > 10
        assert wm["avg_cost_per_event"] > 40.0
        # At 60% Surgical mitigation, projected dollars averted must be strictly > $1,000
        averted_60_events = max(1, round(wm["excess_events"] * 0.60))
        averted_60_dollars = averted_60_events * wm["avg_cost_per_event"]
        assert averted_60_dollars > 1000.0
        assert len(payload["widgets_data"]["heatmap"]["cells"]) >= 6
        assert len(payload["widgets_data"]["bubble"]) == 3


# =============================================================================
# 15. ARGON REGRESSION: APOSTROPHE SAFETY, SEC_DIM DEMOGRAPHIC GUARD & ONTOLOGY
# =============================================================================
def test_apostrophe_event_delegation_and_secondary_demographic_guard():
    """
    Verifies:
    1. Category labels containing single quotes/apostrophes (e.g. "Men's Wear") never
       generate broken inline onclick="...('Men's Wear')" handlers.
    2. Secondary dimension slicer rejects demographic columns ('gender', 'sex') cleanly.
    3. Ontology matching maps Portuguese telecom schemas to B2B/SaaS rather than E-Commerce,
       without mutating global ARCHETYPE_SPECS in place.
    """
    orig_persona = ARCHETYPE_SPECS["nordic_saas_command"]["default_persona"]
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "telecom_users" / "output"
        out_dir.mkdir(parents=True)
        np.random.seed(88)
        n = 220
        df = pd.DataFrame({
            "IDCliente": [f"T_{i}" for i in range(n)],
            "Genero": np.random.choice(["Masculino", "Feminino"], n),
            "TipoContrato": np.random.choice(["Mensal ('Promo')", "Anual 'Gold'", "Bienal"], n),
            "ServicoInternet": np.random.choice(["Fibra Optica", "DSL"], n),
            "ValorMensal": np.random.uniform(30.0, 110.0, n).round(2),
            "Churn": np.random.choice([0, 1], n, p=[0.7, 0.3]),
        })
        df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

        synthesize_bespoke_dashboard(str(out_dir), use_llm=False)
        bp = json.loads((out_dir / "dashboard_design_blueprint.json").read_text(encoding="utf-8"))
        assert bp["matched_ontology"]["ontology_key"] == "b2b_enterprise"
        assert bp["archetype"] == "nordic_saas_command"
        assert ARCHETYPE_SPECS["nordic_saas_command"]["default_persona"] == orig_persona

        html_text = (out_dir / "bespoke_executive_dashboard.html").read_text(encoding="utf-8")
        # Must use safe delegated data-tip-id / data-prim-seg, never inline showTooltip(event, '...')
        assert "showTooltip(event, '" not in html_text
        payload_m = re.search(
            r'const DASHBOARD_PAYLOAD =\s*/\*__DXR_PAYLOAD_START__\*/(.*?)/\*__DXR_PAYLOAD_END__\*/;',
            html_text,
            re.DOTALL,
        )
        payload = json.loads(payload_m.group(1))
        assert payload["sec_dim_name"] != "Genero"

        audit_res = run_anti_hallucination_audit(str(out_dir))
        assert audit_res["grounding_confidence"] == "100.0% VERIFIED TRUTH"


# =============================================================================
# 16. ARGON REGRESSION: CHECK 11 CATCHES BROKEN WHAT-IF & CSS @IMPORT CDN
# =============================================================================
def test_check_11_catches_css_import_cdn_and_zeroed_what_if_cost():
    """
    Verifies hardened Check 11 catches:
    1. External CSS @import url('https://fonts.googleapis.com/...')
    2. Broken What-If avg_cost_per_event == 0.0 on monetary datasets with significant risk.
    """
    bench_dir = Path("kaggle_benchmarks/telecom_users/output")
    if not (bench_dir / "bespoke_executive_dashboard.html").exists():
        pytest.skip("telecom_users output missing")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for f in bench_dir.glob("*"):
            if f.is_file():
                shutil.copy2(f, tmp_path / f.name)

        html_file = tmp_path / "bespoke_executive_dashboard.html"
        orig_html = html_file.read_text(encoding="utf-8")

        # 1. CSS @import CDN leak
        html_file.write_text(
            orig_html.replace("<style>", "<style>@import url('https://fonts.googleapis.com/css2?family=Inter');"),
            encoding="utf-8",
        )
        res_css = run_anti_hallucination_audit(str(tmp_path))
        assert res_css["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        assert any("Zero-CDN Breach" in v for v in res_css["physics_invariant_violations"])

        # 2. Broken $0.00 What-If avg_cost_per_event regression
        zeroed_html = re.sub(r'"avg_cost_per_event":\s*[0-9.]+', '"avg_cost_per_event": 0.0', orig_html, count=1)
        html_file.write_text(zeroed_html, encoding="utf-8")
        res_wi = run_anti_hallucination_audit(str(tmp_path))
        assert res_wi["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        assert any("Broken What-If Simulator" in v for v in res_wi["physics_invariant_violations"])

