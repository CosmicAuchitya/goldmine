"""
=============================================================================
OPTION 2 GLOBAL MARKET POLISH VERIFICATION TEST SUITE
=============================================================================
Verifies:
1. European semicolon (;) CSV & decimal-comma (1.250,50) parser without corrupting dot-decimals.
2. Dynamic currency (€ / ₹) propagation in StrategicDecisionEngine pathways & advisories.
3. Explicit Interactive Demo labels & global US/EU connector presets (`shopify_global_orders`,
   `quickbooks_ar_invoices`) + live `/api/v1/connectors/ingest`.
4. Web UI Account Sign-In modal, Geo-adaptive currency switcher, and zero-CDN/tag invariants.
=============================================================================
"""

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from autonomous_engine.api_server import app
from autonomous_engine.robust_csv_sniffer import (
    normalize_european_decimal_columns,
    smart_read_csv,
    smart_read_csv_bytes,
)
from autonomous_engine.strategic_decision_matrix import StrategicDecisionEngine


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_european_decimal_comma_and_semicolon_csv_parsing(tmp_path: Path, client: TestClient):
    """European semicolon CSV with `1.250,50` amounts parses accurately without mangling `52.52` floats."""
    eu_csv = (
        "invoice_id;city;lat;revenue_eur;is_overdue\n"
        "INV-1;Berlin;52.52;1.250,50;1\n"
        "INV-2;Munich;48.14;980,75;0\n"
        "INV-3;Hamburg;53.55;2.340,00;1\n"
        "INV-4;Frankfurt;50.11;415,25;0\n"
    )
    csv_path = tmp_path / "eu_invoices.csv"
    csv_path.write_text(eu_csv, encoding="utf-8")

    df = smart_read_csv(csv_path)
    assert list(df.columns) == ["invoice_id", "city", "lat", "revenue_eur", "is_overdue"]
    assert pd.api.types.is_numeric_dtype(df["revenue_eur"])
    assert pd.api.types.is_numeric_dtype(df["lat"])
    assert abs(float(df.loc[0, "revenue_eur"]) - 1250.50) < 1e-6
    assert abs(float(df.loc[1, "revenue_eur"]) - 980.75) < 1e-6
    assert abs(float(df.loc[2, "revenue_eur"]) - 2340.00) < 1e-6
    assert abs(float(df.loc[0, "lat"]) - 52.52) < 1e-6

    df_bytes = smart_read_csv_bytes(eu_csv.encode("utf-8"))
    assert abs(float(df_bytes.loc[0, "revenue_eur"]) - 1250.50) < 1e-6

    # Also test direct bytes via /api/v1/preview-intent
    resp = client.post(
        "/api/v1/preview-intent",
        files={"file": ("eu_invoices.csv", io.BytesIO(eu_csv.encode("utf-8")), "text/csv")},
        data={"region_profile": "EU"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["columns_count"] == 5
    assert "revenue_eur" in payload["columns"]
    assert abs(float(payload["preview_rows"][0]["revenue_eur"]) - 1250.50) < 1e-6
    assert abs(float(payload["preview_rows"][0]["lat"]) - 52.52) < 1e-6


def test_dynamic_currency_in_decision_matrix_pathways():
    """StrategicDecisionEngine formats decision pathways using resolved € / ₹ instead of hardcoded $."""
    rng = np.random.default_rng(42)
    n = 240
    segments = ["Berlin_Enterprise"] * 80 + ["Paris_SMB"] * 80 + ["Madrid_Mid"] * 80
    # Inject a strong, statistically significant bottleneck on Berlin_Enterprise (35% vs 6%)
    is_churn = (
        [1 if i < 28 else 0 for i in range(80)]
        + [1 if i < 5 else 0 for i in range(80)]
        + [1 if i < 5 else 0 for i in range(80)]
    )
    df = pd.DataFrame(
        {
            "account_id": [f"EU-{i:04d}" for i in range(n)],
            "region_segment": segments,
            "monthly_spend_amount": np.round(rng.uniform(400.0, 2500.0, size=n), 2),
            "is_churn": is_churn,
        }
    )

    engine = StrategicDecisionEngine(df, blueprint={"region_profile": "EU"})
    dossier = engine.generate_strategic_decision_dossier()
    assert engine.domain_profile["unit_symbol"] == "€"

    pathways = dossier.get("pathways", [])
    assert len(pathways) == 3
    joined = " ".join(
        f"{p.get('implementation_cost', '')} {p.get('projected_friction_reduction', '')} {p.get('statistical_confidence_interval', '')}"
        for p in pathways
    )
    assert "€" in joined
    assert "€5,000" in joined or "€ risk averted" in joined
    assert "$" not in joined, f"Found unexpected stray '$' in EU pathways: {joined}"

    # Verify ₹ as well
    engine_in = StrategicDecisionEngine(df, blueprint={"region_profile": "IN"})
    dossier_in = engine_in.generate_strategic_decision_dossier()
    assert engine_in.domain_profile["unit_symbol"] == "₹"
    joined_in = " ".join(
        f"{p.get('implementation_cost', '')} {p.get('projected_friction_reduction', '')}"
        for p in dossier_in.get("pathways", [])
    )
    assert "₹" in joined_in
    assert "$" not in joined_in


def test_global_connectors_demo_labels_and_ingest(client: TestClient):
    """Catalog marks synthetic ERP presets clearly as Interactive Demo and includes US/EU presets."""
    resp = client.get("/api/v1/connectors")
    assert resp.status_code == 200, resp.text
    connectors = resp.json().get("connectors", [])
    by_id = {c["id"]: c for c in connectors}

    assert "shopify_global_orders" in by_id
    assert "quickbooks_ar_invoices" in by_id
    assert by_id["shopify_global_orders"]["region_profile"] == "US"
    assert by_id["quickbooks_ar_invoices"]["region_profile"] == "EU"

    for c in connectors:
        assert c.get("is_sample_demo") is True
        assert c.get("mode_label") == "Interactive Demo"

    # Ingest quickbooks_ar_invoices EU demo preset cleanly
    ing = client.post(
        "/api/v1/connectors/ingest",
        json={"connector_id": "quickbooks_ar_invoices", "region_profile": "EU"},
    )
    assert ing.status_code == 200, ing.text
    data = ing.json()
    run_id = data.get("run_id")
    assert run_id
    assert data.get("connector_source") == "quickbooks_ar_invoices"
    assert data["executive_pulse"]["unit_symbol"] == "€"

    # Verify downloadable PLAIN_BUSINESS_SUMMARY.md & DATA_XRAY_EXECUTIVE_DOSSIER.md use € (not hardcoded $)
    dl_sum = client.get(f"/api/v1/download/{run_id}/PLAIN_BUSINESS_SUMMARY.md")
    assert dl_sum.status_code == 200
    assert "€" in dl_sum.text
    assert "**$" not in dl_sum.text

    dl_dos = client.get(f"/api/v1/download/{run_id}/DATA_XRAY_EXECUTIVE_DOSSIER.md")
    assert dl_dos.status_code == 200
    assert "Total Liability (€)" in dl_dos.text or "Monetary Exposure (€)" in dl_dos.text
    assert "Total Liability ($)" not in dl_dos.text


def test_web_ui_auth_modal_region_adaptation_and_invariants(client: TestClient):
    """Web client contains Account Sign-In modal, Geo-adaptive switcher, Demo badges, and passes structural invariants."""
    resp = client.get("/app")
    assert resp.status_code == 200
    html = resp.text

    # Option 2 Global UI markers
    assert 'id="authModal"' in html
    assert 'id="btnAuthModal"' in html
    assert "submitAuthForm" in html
    assert "applyRegionAdaptation" in html
    assert "SAMPLE DEMO" in html
    assert "LIVE SYNC" in html
    assert "shopify_global_orders" in html
    assert "quickbooks_ar_invoices" in html
    assert "eyebrowDemoConnectors" in html

    # Existing critical structural invariants preserved
    assert "fonts.googleapis.com" not in html
    assert 'id="apiKeyModal"' in html
    assert "PRE-FLIGHT SCHEMA &amp; INTENT HANDSHAKE" in html
    assert "await pollJobUntilComplete(data.job_id)" in html

    # Morning Digest modal tag balance before Proof Drawer modal
    start = html.index('id="morningDigestModal"')
    end = html.index('id="proofDrawerModal"')
    digest_block = html[start:end]
    opens = len(re.findall(r"<div\b", digest_block))
    closes = len(re.findall(r"</div>", digest_block))
    assert opens == closes, f"Unbalanced div tags in morningDigestModal: {opens} opens vs {closes} closes"


def test_public_demo_routes_work_when_require_auth_enabled(monkeypatch, client: TestClient):
    """When DATAXRAY_REQUIRE_AUTH=true, public 1-click demo benchmarks work while private APIs require auth."""
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    monkeypatch.setenv("DATAXRAY_JWT_SECRET", "test_secret_for_public_demo_check_123456")

    # Public onboarding & demo routes MUST succeed (200) without auth
    assert client.get("/api/v1/benchmarks").status_code == 200
    assert client.get("/api/v1/benchmarks/hotel_booking_cancellation").status_code == 200
    assert client.get("/api/v1/connectors").status_code == 200
    assert client.get("/api/v1/audit-proof/hotel_booking_cancellation").status_code == 200
    assert client.get("/api/v1/digest/hotel_booking_cancellation").status_code == 200
    assert client.get("/api/v1/download/hotel_booking_cancellation/PLAIN_BUSINESS_SUMMARY.md").status_code == 200

    # Private endpoints MUST remain blocked (401)
    assert client.get("/api/v1/workspaces/founder_workspace/runs").status_code == 401
    assert client.post("/api/v1/connectors/ingest", json={"connector_id": "shopify_global_orders"}).status_code == 401
    assert client.get("/api/v1/dashboard/private_run_999").status_code == 401


def test_default_tenant_wildcard_cross_tenant_leak_closed(client: TestClient):
    """Querying workspace runs or comparing runs with 'default' or '' never leaks other tenants' private runs."""
    from autonomous_engine.live_connectors import list_workspace_runs, compare_workspace_runs
    from autonomous_engine.api_server import WORKSPACE_ROOT

    ing = client.post(
        "/api/v1/connectors/ingest",
        json={"connector_id": "shopify_global_orders", "tenant_id": "isolated_secret_tenant_99", "region_profile": "US"},
    )
    assert ing.status_code == 200
    secret_run_id = ing.json()["run_id"]

    # Querying 'default' via API or empty string via helper MUST NOT include isolated_secret_tenant_99's run
    res_def = client.get("/api/v1/workspaces/default/runs")
    assert res_def.status_code == 200
    def_ids = {r["run_id"] for r in res_def.json().get("runs", [])}
    assert secret_run_id not in def_ids

    empty_runs = list_workspace_runs(WORKSPACE_ROOT, tenant_id="")
    assert secret_run_id not in {r["run_id"] for r in empty_runs}

    with pytest.raises(ValueError, match="not found"):
        compare_workspace_runs(WORKSPACE_ROOT, secret_run_id, "hotel_booking_cancellation", tenant_id="default")


def test_multi_file_eu_csv_preview_and_trailing_euro_cleaning(client: TestClient):
    """Multi-file preview parses European semicolon CSVs + trailing '€' amounts without 100x comma-strip inflation."""
    from autonomous_engine.robust_excel_scanner import clean_accounting_series

    s_eu = pd.Series(["1.250,50 €", "125,50 €", "980,75 €", "410,00 €"])
    s_cleaned = clean_accounting_series(s_eu)
    assert abs(float(s_cleaned.iloc[0]) - 1250.50) < 1e-6
    assert abs(float(s_cleaned.iloc[1]) - 125.50) < 1e-6

    orders_csv = (
        "order_id;customer_id;order_amount_eur;is_canceled\n"
        "O-1;C-1;1.250,50 €;1\n"
        "O-2;C-2;125,50 €;0\n"
        "O-3;C-1;980,75 €;1\n"
        "O-4;C-3;410,00 €;0\n"
    )
    customers_csv = (
        "customer_id;country\n"
        "C-1;Germany\n"
        "C-2;France\n"
        "C-3;Spain\n"
    )
    res = client.post(
        "/api/v1/preview-multi-intent",
        files=[
            ("files", ("orders_eu.csv", io.BytesIO(orders_csv.encode("utf-8")), "text/csv")),
            ("files", ("customers_eu.csv", io.BytesIO(customers_csv.encode("utf-8")), "text/csv")),
        ],
        data={"region_profile": "EU"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_tables"] == 2
    assert data["detected_goal"]["unit_symbol"] == "€"
    assert data["detected_goal"]["cost_col"] == "order_amount_eur"


def test_reverse_proxy_xff_rate_limiter_and_cohort_breakdown_order(monkeypatch, client: TestClient):
    """Reverse-proxy X-Forwarded-For isolates rate limits per client IP, and cohort_breakdowns liability/share are not swapped."""
    from autonomous_engine.api_server import _RATE_BUCKETS
    _RATE_BUCKETS.clear()
    monkeypatch.setenv("DATAXRAY_RATE_LIMIT_RPM", "3")

    ip1_hdr = {"X-Forwarded-For": "203.0.113.10, 10.0.0.1"}
    ip2_hdr = {"X-Forwarded-For": "198.51.100.42, 10.0.0.1"}

    for _ in range(3):
        assert client.get("/api/v1/connectors", headers=ip1_hdr).status_code == 200
    assert client.get("/api/v1/connectors", headers=ip1_hdr).status_code == 429

    # Different client IP behind same proxy MUST NOT be rate-limited
    assert client.get("/api/v1/connectors", headers=ip2_hdr).status_code == 200
    _RATE_BUCKETS.clear()
    monkeypatch.setenv("DATAXRAY_RATE_LIMIT_RPM", "120")

    # Verify cohort_breakdowns does not swap total_liability and share_of_failures_pct
    bench = client.get("/api/v1/benchmarks/hotel_booking_cancellation")
    assert bench.status_code == 200
    row0 = bench.json()["executive_pulse"]["cohort_breakdowns"][0]["rows"][0]
    assert 0.0 <= float(row0["share_of_failures_pct"]) <= 100.0
    assert "$" in str(row0["total_liability"])


def test_omni_dimensional_leak_scanner_extracts_all_12_hidden_leaks():
    """Verifies OmniDimensionalLeakScanner extracts 100% of hidden leaks across all 8 forensic layers."""
    from autonomous_engine.omni_leak_scanner import (
        OmniDimensionalLeakScanner,
        render_plain_omni_sections,
        render_dossier_omni_section,
    )

    nexura_csv = Path("enterprise_showcase_data/nexura_lifestyle_brand/raw_data/nexura_3yr_omnichannel_transactions.csv")
    if not nexura_csv.exists():
        pytest.skip("Nexura showcase CSV not present")

    df = pd.read_csv(nexura_csv)
    scanner = OmniDimensionalLeakScanner(df, blueprint={"region_profile": "IN"})
    report = scanner.run_full_scan()

    # 1. All 6 confirmed leak dimensions discovered (COD, Tier 3, Delhivery, UP, FLASH30, Kolkata-East-Depot)
    leak_dims = {x["dimension"]: x["worst_segment"] for x in report["confirmed_leak_dimensions"]}
    assert leak_dims.get("payment_gateway") == "Cash on Delivery (COD)"
    assert leak_dims.get("city_tier") == "Tier 3 Regional"
    assert leak_dims.get("courier_partner") == "Delhivery Surface Express"
    assert leak_dims.get("customer_state") == "Uttar Pradesh"
    assert leak_dims.get("coupon_code") == "FLASH30"
    assert leak_dims.get("fulfillment_warehouse") == "Kolkata-East-Depot"

    # 2. Secondary operational SLA & dispatch speed bottlenecks caught
    ops_text = " ".join(o["headline_en"] for o in report["operational_sla_and_delay_findings"])
    assert "Kolkata-East-Depot" in ops_text and "2.85 days" in ops_text
    assert "Delhivery Surface Express" in ops_text and "48.15%" in ops_text

    # 3. Confounder / Simpson's Paradox & 2x2 Hotspots isolated
    conf_text = " ".join(c["explanation_en"] for c in report["confounder_insights"])
    assert "Uttar Pradesh" in conf_text and "44.80%" in conf_text and "7.04%" in conf_text
    assert len(report["top_2d_hotspots"]) >= 3

    # 4. P&L Net Margin, Negative-Margin Orders, Reverse Shipping & Toxic FLASH30 Coupon
    pnl = report["pnl_and_coupons"]
    assert pnl["has_margin_ledger"] is True
    assert pnl["negative_margin_order_count"] == 924
    assert abs(pnl["negative_margin_cash_loss"] - (-289450.0)) < 1.0
    assert abs(pnl["reverse_shipping_burn"] - 170940.0) < 1.0
    assert any(tc["coupon_code"] == "FLASH30" for tc in pnl["toxic_coupons"])

    # 5. Repeat Customer Abusers, Negative-LTV Accounts & Corporate Wellness Whale Segment
    ent = report["entities_and_skus"]
    assert ent["has_repeat_entities"] is True
    assert ent["negative_ltv_entity_count"] == 248
    assert ent["serial_abuser_count"] == 72
    assert ent["top_serial_abusers"][0]["entity_id"] == "CUST-101943"
    assert ent["has_whale_segment"] is True
    assert ent["whale_segment"] == "Corporate Wellness Client"

    # 6. Seasonal Q4 Festive Surge
    seas = report["seasonal_regimes"]
    assert seas["has_quarterly_regime_shift"] is True
    assert seas["peak_quarter"] == "Q4"
    assert abs(seas["peak_quarter_sla_breach_pct"] - 41.81) < 0.1

    # 7. Renderers produce clean bilingual markdown with zero scientific p-value notation
    en_sec, hi_sec = render_plain_omni_sections(report)
    dos_sec = render_dossier_omni_section(report)
    assert "FLASH30" in en_sec and "FLASH30" in hi_sec and "DOUBLE-POISON" in dos_sec
    assert not re.search(r"p\s*=\s*\d+\.\d+e[+-]\d+", en_sec + hi_sec)


def test_universal_200_questions_engine_answers_all_200_questions(tmp_path):
    """Verifies Universal200QuestionsEngine answers all 200 questions across 15 pillars on Nexura, non-monetary, empty & API."""
    from autonomous_engine.universal_200_questions_engine import Universal200QuestionsEngine
    from autonomous_engine.omni_leak_scanner import OmniDimensionalLeakScanner
    from autonomous_engine.conversational_qa_engine import ConversationalBusinessQAEngine
    from fastapi.testclient import TestClient
    from autonomous_engine.api_server import app

    nexura_csv = Path("enterprise_showcase_data/nexura_lifestyle_brand/raw_data/nexura_3yr_omnichannel_transactions.csv")
    if not nexura_csv.exists():
        pytest.skip("Nexura showcase CSV not present")

    df = pd.read_csv(nexura_csv)
    omni = OmniDimensionalLeakScanner(df, blueprint={"region_profile": "IN"}).run_full_scan()
    engine = Universal200QuestionsEngine(df, blueprint={"region_profile": "IN"}, omni_report=omni)
    rep = engine.generate_all_200_questions(tmp_path)

    qs = rep["questions"]
    assert len(qs) == 200
    assert rep["summary"]["answered_count"] == 200
    assert rep["summary"]["pillars_count"] == 15
    assert [q["id"] for q in qs] == [f"Q{i:03d}" for i in range(1, 201)]

    qmap = {q["id"]: q for q in qs}
    for q in qs:
        assert q["question_en"] and q["question_hi"]
        assert q["answer_en"] and q["answer_hi"]
        assert "nan" not in q["answer_en"].lower().split()

    # Exact physical Nexura discoveries
    assert qmap["Q006"]["status"] == "DIRECT_ANSWERED" and "48.08%" in qmap["Q006"]["answer_en"]
    assert qmap["Q049"]["status"] == "DIRECT_ANSWERED" and "40.67%" in qmap["Q049"]["answer_en"]
    assert "738" in qmap["Q054"]["answer_en"]
    assert qmap["Q079"]["status"] == "DIRECT_ANSWERED" and "Champions" in qmap["Q079"]["answer_en"]
    assert "292.0" in qmap["Q080"]["answer_en"]
    assert "FlexForm High-Waisted Compressive Leggings" in qmap["Q090"]["answer_en"]
    assert "NX-PROT-RAW-UNFLAV-1KG" in qmap["Q091"]["answer_en"]
    assert "NX-NUTRI-VITD3-K2-60" in qmap["Q093"]["answer_en"]
    assert "BlueDart Express Air" in qmap["Q124"]["answer_en"]
    assert qmap["Q174"]["status"] == "DIRECT_ANSWERED" and "0.0257" in qmap["Q174"]["answer_en"]

    # Non-monetary dataset must never fabricate currency symbols
    non_mon_df = pd.DataFrame({
        "Type": ["L", "L", "M", "H", "L", "M"] * 5,
        "Rotational_speed_rpm": [1300, 1400, 1500, 1600, 1320, 1450] * 5,
        "Machine_failure": [1, 0, 0, 0, 1, 0] * 5,
    })
    rep_nm = Universal200QuestionsEngine(non_mon_df).generate_all_200_questions()
    assert len(rep_nm["questions"]) == 200
    assert rep_nm["is_financial"] is False
    for q in rep_nm["questions"]:
        assert "$" not in q["key_metric"] and "₹" not in q["key_metric"]

    # Empty dataframe must return cleanly without KeyError
    rep_empty = Universal200QuestionsEngine(pd.DataFrame()).generate_all_200_questions()
    assert len(rep_empty["questions"]) == 200

    # Q&A integration checks Q001-Q200 lookup on parquet directory
    df.to_parquet(tmp_path / "bi_ready_fact.parquet", index=False)
    with ConversationalBusinessQAEngine(tmp_path) as qa:
        res_q = qa.ask("Explain Q174 Benford scan", language="english", use_llm=False)
        assert res_q["status"] == "success"
        assert res_q["sql_generation_mode"] == "universal_200_matrix"
        assert "0.0257" in res_q["answer_markdown"]

    # FastAPI endpoint GET /api/v1/questions-200/{run_id}
    client = TestClient(app)
    resp = client.get("/api/v1/questions-200/hotel_booking_cancellation")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["answered_count"] == 200
    assert len(payload["questions"]) == 200
    assert len(payload["pillars"]) == 15


def test_43_languages_i18n_and_obsidian_editorial_ui(client: TestClient):
    """43-language i18n engine, stale-cache validator, Decision Lab ?lang, and Obsidian Editorial UI invariants."""
    from autonomous_engine.global_i18n_engine import (
        WORLD_LANGUAGES,
        RTL_CODES,
        _is_valid_translated_cache,
        _shield_tokens,
        _unshield_tokens,
    )

    # 1. All 43 languages + RTL catalog check
    langs_resp = client.get("/api/v1/i18n/languages")
    assert langs_resp.status_code == 200
    langs_payload = langs_resp.json()
    assert langs_payload["count"] == 43
    assert len(WORLD_LANGUAGES) == 43
    assert {"ar", "ur", "he", "fa"}.issubset(RTL_CODES)

    # 2. Shield/unshield preserves exact numeric & brand tokens
    src_txt = "DataX-Ray found $4.64M risk (41.73% rate) across WhatsApp orders."
    sh, toks = _shield_tokens(src_txt)
    assert "$4.64M" not in sh and "41.73%" not in sh and "DataX-Ray" not in sh
    assert _unshield_tokens(sh, toks) == src_txt

    # 3. Stale/broken English cache detector rejects untranslated non-EN caches
    src_map = {"a": "Business Health Check", "b": "Biggest Money Leak", "c": "Decision Predictor"}
    assert _is_valid_translated_cache(src_map, src_map, "es") is False
    tr_ok = {"a": "Control de Salud Empresarial", "b": "Mayor Fuga de Dinero", "c": "Predictor de Decisiones"}
    assert _is_valid_translated_cache(tr_ok, src_map, "es") is True

    # 4. Decision Lab overview supports ?lang parameter cleanly
    ov_resp = client.get("/api/v1/predict/overview/hotel_booking_cancellation?lang=en")
    assert ov_resp.status_code == 200
    assert "presets" in ov_resp.json()

    # 5. Obsidian Ink & Warm Editorial Atelier UI structural markers
    html = client.get("/app").text
    assert "top-command-bar" in html
    assert "topbar-lang-dock" in html
    assert "exec-action-strip" in html
    assert "inFlightLangKey" in html
    assert '<script src="http' not in html


