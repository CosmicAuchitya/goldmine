"""
================================================================================
REGRESSION & HARDENING TESTS: BATCH 3 + 5 PROACTIVE PRODUCTION BUGS (P1–P5, B3)
================================================================================
Verifies:
- P1: HTTP rate-limit middleware uses rightmost X-Forwarded-For IP (anti-spoof)
      and refuses to mint fresh buckets for random invalid Bearer headers.
- P2: CORSMiddleware allows PATCH requests for Team RBAC role updates.
- P3: Failed /analyze-upload runs clean up orphaned run_root folders from disk.
- P4: clean_accounting_series() & templated_dag_runner parse Indian billing
      strings ('Rs. 4,500/-', '₹4,500/-', 'Rs 1,200') into clean floats.
- P5: strip_accounting_summary_rows() drops genuine 'Total' / 'Grand Total'
      footers while NEVER deleting real customer rows ('Total Energies',
      'Total Logistics Solutions') in the bottom 10 rows.
- B3.1: Unified target_resolver.is_temporal_column() catches English, Spanish
      ('fecha'), Turkish ('tarih'), ISO, and DD-MM-YYYY date columns.
- B3.2: Long-tail operational dimensions (81..500 unique, e.g. Ford COMPDESC)
      and excess-impact cohort ranking surface top real crash drivers (SERVICE
      BRAKES / AIR BAGS) ahead of tiny small-count noise slices.
================================================================================
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine import api_server
from autonomous_engine.omni_leak_scanner import OmniDimensionalLeakScanner
from autonomous_engine.ranked_leak_synthesizer import synthesize_ranked_leaks
from autonomous_engine.robust_excel_scanner import (
    clean_accounting_series,
    strip_accounting_summary_rows,
)
from autonomous_engine.target_resolver import is_temporal_column
from autonomous_engine.templated_dag_runner import execute_templated_pipeline


def test_p1_rate_limit_blocks_xff_spoofing_and_fake_bearer_flood(monkeypatch):
    api_server._RATE_BUCKETS.clear()
    monkeypatch.setenv("DATAXRAY_RATE_LIMIT_RPM", "3")
    monkeypatch.setenv("DATAXRAY_TRUST_PROXY_HEADERS", "true")
    client = TestClient(api_server.app)

    # Attacker spoofs leftmost X-Forwarded-For AND random invalid Bearer token on every call,
    # while rightmost proxy-appended IP stays constant (203.0.113.55) -> MUST still hit 429 on 4th call!
    try:
        statuses = []
        for i in range(4):
            r = client.get(
                "/api/v1/connectors",
                headers={
                    "X-Forwarded-For": f"198.51.100.{i + 1}, 203.0.113.55",
                    "Authorization": f"Bearer fake_random_token_{i:012d}",
                },
            )
            statuses.append(r.status_code)
        assert statuses[:3] == [200, 200, 200]
        assert statuses[3] == 429
    finally:
        api_server._RATE_BUCKETS.clear()


def test_p2_cors_allows_patch_for_team_role_updates():
    client = TestClient(api_server.app)
    r = client.options(
        "/api/v1/team/members/usr_123/role",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert r.status_code == 200
    allow_methods = r.headers.get("access-control-allow-methods", "")
    assert "PATCH" in allow_methods.upper()


def test_p3_failed_analyze_upload_cleans_up_orphaned_run_dir(monkeypatch):
    tenant_tag = "p3_cleanup_check"
    tenant_jobs_dir = api_server.WORKSPACE_ROOT / "runs" / "tenants" / tenant_tag / "jobs"
    before = set(tenant_jobs_dir.iterdir()) if tenant_jobs_dir.exists() else set()

    monkeypatch.setattr(api_server, "run_master_pipeline", lambda **kwargs: False)
    client = TestClient(api_server.app)
    csv_bytes = b"order_id,amount,status\n1,500,Failed\n2,600,Ok\n"
    r = client.post(
        "/api/v1/analyze-upload",
        files={"file": ("p3_fail.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"tenant_id": tenant_tag, "mode": "templated"},
    )
    assert r.status_code == 500
    after = set(tenant_jobs_dir.iterdir()) if tenant_jobs_dir.exists() else set()
    assert after == before, f"Orphaned run directory leaked on disk: {after - before}"


def test_p4_and_p5_indian_rs_slash_dash_parsing_and_total_customer_protection(tmp_path: Path):
    # P4: Indian Tally/Marg formats Rs. 4,500/- and ₹4,500/-
    s_in = pd.Series(["Rs. 4,500/-", "₹1,250/-", "Rs 800", "(Rs. 500/-)", "INR 12,000"])
    s_out = clean_accounting_series(s_in)
    assert pd.api.types.is_numeric_dtype(s_out)
    assert s_out.tolist() == [4500.0, 1250.0, 800.0, -500.0, 12000.0]

    # End-to-end inside templated_dag_runner even with <= 10 unique values
    raw_d = tmp_path / "raw_in"
    out_d = tmp_path / "out_in"
    raw_d.mkdir()
    out_d.mkdir()
    df_in = pd.DataFrame(
        {
            "invoice_id": [f"INV-{i}" for i in range(15)],
            "party_name": [
                "Total Energies India Pvt Ltd" if i == 12 else ("Total Logistics Solutions" if i == 13 else f"Party {i}")
                for i in range(15)
            ],
            "bill_amount": ["Rs. 4,500/-", "₹1,250/-", "(Rs. 500/-)"] * 5,
            "status": ["Overdue" if i % 3 == 0 else "Paid" for i in range(15)],
        }
    )
    # Add genuine footer row that SHOULD be stripped
    footer = pd.DataFrame(
        [{"invoice_id": "Grand Total", "party_name": "", "bill_amount": "Rs. 26,250/-", "status": ""}]
    )
    df_with_footer = pd.concat([df_in, footer], ignore_index=True)

    # P5: strip_accounting_summary_rows removes 'Grand Total' but keeps BOTH real 'Total ...' customers!
    df_stripped = strip_accounting_summary_rows(df_with_footer)
    assert len(df_stripped) == 15
    assert "Total Energies India Pvt Ltd" in df_stripped["party_name"].values
    assert "Total Logistics Solutions" in df_stripped["party_name"].values

    df_in.to_csv(raw_d / "ledger.csv", index=False)
    bp = tmp_path / "bp.json"
    bp.write_text(
        json.dumps({"fact_table": "ledger", "primary_id_column": "invoice_id", "target_metric": "status"}),
        encoding="utf-8",
    )
    execute_templated_pipeline(str(bp), str(raw_d), str(out_d))
    df_pq = pd.read_parquet(out_d / "bi_ready_fact.parquet")
    assert len(df_pq) == 15
    assert pd.api.types.is_numeric_dtype(df_pq["bill_amount"])
    assert float(df_pq["bill_amount"].iloc[0]) == 4500.0
    assert float(df_pq["bill_amount"].iloc[2]) == -500.0


def test_b3_1_unified_is_temporal_column():
    assert is_temporal_column(pd.Series(["2024-01-01"] * 10), "order_date") is True
    assert is_temporal_column(pd.Series(["15-03-2024"] * 10), "raw_col") is True
    assert is_temporal_column(pd.Series(["a", "b"] * 5), "fecha_venta") is True
    assert is_temporal_column(pd.Series(["a", "b"] * 5), "siparis_tarih") is True
    assert is_temporal_column(pd.Series(["North", "South"] * 5), "region") is False
    assert is_temporal_column(pd.Series([100, 200] * 5), "amount") is False


def test_b3_2_long_tail_dimension_and_ford_gate5_root_cause_discovery():
    ford_csv = Path("user_test_datasets/real_10yr_ford_audit/blind_anonymized_auto_middle_2016_2018.csv")
    if not ford_csv.exists():
        # Fallback synthetic long-tail dimension test (150 components, top bottleneck clearly concentrated)
        n = 2000
        comps = ["SERVICE BRAKES"] * 400 + ["ENGINE"] * 500 + ["STEERING"] * 400 + [f"COMP_{i % 147}" for i in range(700)]
        crash = ["Y" if (c == "SERVICE BRAKES" and i % 4 == 0) else ("Y" if i % 40 == 0 else "N") for i, c in enumerate(comps)]
        df = pd.DataFrame({"COMPDESC": comps, "STATE": [f"S{i % 10}" for i in range(n)], "CRASH": crash})
    else:
        df = pd.read_csv(ford_csv, low_memory=False)

    scanner = OmniDimensionalLeakScanner(df)
    omni = scanner.run_full_scan()
    rk = synthesize_ranked_leaks(df, omni_report=omni)
    top_leaks = rk.get("abnormal_deviations") or []
    assert len(top_leaks) >= 1
    headlines_blob = " | ".join(str(x.get("headline_en") or "").upper() for x in top_leaks[:5])
    assert any(k in headlines_blob for k in ("AIR BAG", "BRAKE", "SPEED CONTROL", "SEAT BELT", "COMPDESC")), (
        f"Expected top crash component in ranked leaks, got: {headlines_blob}"
    )


def test_b3_3_circuit_breaker_owner_pathway_badges_never_emit_literal_label(tmp_path):
    """Ensure Circuit-Breaker / zero-savings pathways never show 'Save ~Expected Savings' or 'Save ~₹0'."""
    from autonomous_engine.api_server import _extract_executive_pulse

    manifest = {
        "governance": {"audited_fact_records": 120},
        "target_outcome": {
            "column_name": "return_flag",
            "total_adverse_events": 24,
            "adverse_event_rate_pct": 20.0,
        },
        "financial_exposure": {
            "total_adverse_capital_drag": 466000.0,
            "total_portfolio_volume": 2000000.0,
            "currency_unit": "₹",
            "monetary_column": "order_value",
        },
    }
    plain_md = (
        "### 2. Where Is the Bottleneck?\n"
        "No Single Bottleneck — $0 Spend Advisory (uniform noise across groups).\n\n"
        "### 4. What Should You Do Next? (3 Choices)\n"
        "- **Option A (Low Risk / Small Pilot):** **Expected Savings:** Hold spend (no targeted intervention).\n"
        "- **Option B (Focused Fix):** **₹0 saved** — keep steady QA.\n"
    )
    pulse = _extract_executive_pulse(tmp_path, manifest, plain_md)
    for lang in ("en", "hi"):
        for pw in pulse["owner_friendly"][lang]["pathways"]:
            badge = pw.get("badge", "")
            assert "Expected Savings" not in badge, f"Literal label leaked into {lang} badge: {badge}"
            assert badge not in ("Save ~₹0", "बचत ~₹0", "Save ~$0", "बचत ~$0"), f"Zero-save badge leaked: {badge}"
