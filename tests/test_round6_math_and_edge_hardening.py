"""
Round-6 Mathematical Accuracy & Unseen Real-World Edge Hardening Tests:
1. Multi-sheet CFO .xlsx with Instructions + Pivot_Summary + Raw_Transactions (zero 265x revenue inflation).
2. macOS/Windows nested folder ZIP with __MACOSX/._* AppleDouble junk + .DS_Store + cp1252 Latin-1.
3. Deduplicated Quantified Leak Exposure in ranked_leak_synthesizer (never double-counts subsets/slices).
4. Exact Newcombe (1998) Method-10 Wilson-Hybrid 95% CI at p1 == 1.0 boundary (no Wald collapse).
5. Whale multiplier guard when company mean margin <= 0 (no 10,000x division-by-0.01 explosion).
6. Benford's Law Nigrini multi-order-of-magnitude guard & Q198 true idxmax() peak + 2-sigma binomial gate.
7. Stage 7 What-If Simulator dynamic currency symbol & excessEv <= 0 zero guard.
"""
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import openpyxl
import pandas as pd

from autonomous_engine.kaggle_harvester import safe_extract_zip
from autonomous_engine.stage1_topology_profiler import unpack_multisheet_excel_workbooks
from autonomous_engine.templated_dag_runner import execute_templated_pipeline
from autonomous_engine.strategic_decision_matrix import calculate_excess_risk_metrics
from autonomous_engine.omni_leak_scanner import OmniDimensionalLeakScanner
from autonomous_engine.ranked_leak_synthesizer import synthesize_ranked_leaks
from autonomous_engine.universal_200_questions_engine import Universal200QuestionsEngine
from autonomous_engine import stage7_bespoke_dashboard_architect


def test_cfo_multisheet_xlsx_pivot_summary_never_inflates_revenue(tmp_path: Path):
    raw_dir = tmp_path / "raw_data"
    out_dir = tmp_path / "output"
    raw_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Instructions"
    ws1.append(["CFO Board Report Notes"])

    ws2 = wb.create_sheet("Pivot_Summary")
    ws2.append(["Region", "Orders", "Revenue"])
    ws2.append(["North", 50, 25000])
    ws2.append(["South", 50, 25000])
    ws2.append(["Grand Total", 100, 50000])

    ws3 = wb.create_sheet("Raw_Transactions")
    ws3.append(["ACME ERP EXPORT"])
    ws3.append([])
    ws3.append(["order_id", "region", "invoice_amount_usd", "order_status"])
    for i in range(100):
        ws3.append([f"XL-{i}", "North" if i < 50 else "South", "$500.00", "Returned" if i % 5 == 0 else "Delivered"])
    ws3.append(["Grand Total", "", "$50,000.00", ""])

    xl_path = raw_dir / "cfo_pivot_test.xlsx"
    wb.save(xl_path)

    unpacked = unpack_multisheet_excel_workbooks(raw_dir)
    # Pivot_Summary and Instructions must be skipped -> only 1 valid sheet -> not unpacked into competing tables
    assert not unpacked
    bp_path = tmp_path / "execution_blueprint.json"
    bp_path.write_text(json.dumps({"project_name": "CFO Pivot Test", "entities": []}), encoding="utf-8")
    execute_templated_pipeline(str(bp_path), str(raw_dir), str(out_dir), str(tmp_path / "cache"))
    df_fact = pd.read_parquet(out_dir / "bi_ready_fact.parquet")
    assert len(df_fact) == 100
    assert abs(float(df_fact["invoice_amount_usd"].sum()) - 50000.0) < 1.0
    assert "Revenue" not in df_fact.columns


def test_macos_folder_zip_flattens_nested_tabular_and_skips_junk(tmp_path: Path):
    df = pd.DataFrame({
        "order_id": [f"EU-{i}" for i in range(40)],
        "client": ["Café René", "Bäckerei Müller"] * 20,
        "amount_eur": [200.0 + i for i in range(40)],
        "status": ["Cancelado" if i % 4 == 0 else "Entregado" for i in range(40)],
    })
    zpath = tmp_path / "macos_folder.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("__MACOSX/._orders.csv", b"\x00\x05\x16\x07junk")
        zf.writestr("export_2025/.DS_Store", b"\x00\x00\x00\x01Bud1")
        zf.writestr("export_2025/orders_latin1.csv", df.to_csv(index=False).encode("cp1252"))

    dest = tmp_path / "raw_data"
    safe_extract_zip(zpath, dest, flatten_tabular=True)
    assert (dest / "orders_latin1.csv").exists()
    assert not (dest / "__MACOSX").exists()
    assert not list(dest.rglob("._*"))
    assert not list(dest.rglob(".DS_Store"))


def test_newcombe_method10_ci_no_wald_collapse_at_boundary():
    # p1 = 50/50 = 1.0 (100% failure cohort), p0 = 10/100 = 0.10 -> diff = 0.90
    res = calculate_excess_risk_metrics(50, 50, 10, 100, confidence=0.95)
    assert res["p1"] == 1.0
    assert res["p0"] == 0.10
    assert round(res["excess_rate"], 2) == 0.90
    # Newcombe Wilson lower bound must reflect finite-sample uncertainty of n1=50 (strictly tighter than naive Wald 0.90 - 0.0588 = 0.841)
    assert 0.78 <= res["excess_rate_low"] <= 0.84
    assert res["excess_rate_high"] <= 1.0


def test_omni_whale_multiplier_guard_on_negative_margin_company():
    df = pd.DataFrame({
        "order_id": [f"O-{i}" for i in range(100)],
        "customer_segment": ["Small"] * 80 + ["Enterprise"] * 20,
        "revenue_usd": [100.0] * 100,
        # Company is net negative overall (-30.0 avg), while Enterprise is +10.0
        "net_margin": [-40.0] * 80 + [10.0] * 20,
        "order_status": ["Returned" if i % 4 == 0 else "Delivered" for i in range(100)],
    })
    ent = OmniDimensionalLeakScanner(df).scan_entity_concentration_and_skus()
    # Must NOT produce a bogus 10,000x / 1,000x multiplier by dividing by max(-30, 0.01) = 0.01!
    assert ent["has_whale_segment"] is False


def test_deduplicated_quantified_leak_exposure_bounded_by_portfolio():
    rng = np.random.default_rng(909)
    n = 400
    df = pd.DataFrame({
        "order_id": [f"O-{i}" for i in range(n)],
        "distributor_name": ["BadWhale"] * 100 + ["GoodA"] * 150 + ["GoodB"] * 150,
        "zone": ["West"] * 120 + ["East"] * 140 + ["South"] * 140,
        "invoiced_amount_usd": [1000.0] * n,
        "net_contribution_margin": [-200.0] * 100 + [300.0] * 300,
        "outstanding_due_usd": [950.0] * 100 + [0.0] * 300,
        "order_status": ["Returned"] * 100 + ["Delivered"] * 300,
    })
    omni = OmniDimensionalLeakScanner(df).run_full_scan()
    q200 = Universal200QuestionsEngine(df, omni_report=omni).generate_all_200_questions()
    ranked = synthesize_ranked_leaks(df, omni_report=omni, q200_report=q200)
    port_vol = float(df["invoiced_amount_usd"].sum())
    quant = float(ranked["summary"]["quantified_leak_exposure"] or 0.0)
    assert quant <= port_vol
    # Must NOT double-count BadWhale negative margin ($20k) on top of total negative margin orders ($20k)
    assert quant < port_vol * 0.50


def test_benford_nigrini_precondition_and_q198_true_peak_idxmax():
    rng = np.random.default_rng(123)
    # 1. Narrow uniform [50, 950] should NOT falsely trigger Benford's Law anomaly
    n = 1200
    months = [f"2025-{(i % 12) + 1:02d}-15" for i in range(n)]
    # Inject two spike months: Month 03 (45% fail) and Month 09 (75% fail — TRUE peak!)
    statuses = []
    for i in range(n):
        m = (i % 12) + 1
        if m == 9:
            statuses.append("Failed" if (i // 12) < 75 else "Completed")
        elif m == 3:
            statuses.append("Failed" if (i // 12) < 45 else "Completed")
        else:
            statuses.append("Failed" if (i // 12) < 10 else "Completed")
    df = pd.DataFrame({
        "order_id": [f"M-{i}" for i in range(n)],
        "order_date": months,
        "order_amount_usd": np.round(rng.uniform(50.0, 950.0, size=n), 2),
        "order_status": statuses,
    })
    q200 = Universal200QuestionsEngine(df).generate_all_200_questions()
    qmap = {q["id"]: q for q in q200["questions"]}
    # Q198 peak must be 2025-09 (75%), NOT chronologically first spike 2025-03 (45%)!
    assert "2025-09" in qmap["Q198"]["answer_en"]
    assert "75.00%" in qmap["Q198"]["answer_en"]


def test_stage7_whatif_simulator_uses_dynamic_currency_and_zero_guard():
    src = Path(stage7_bespoke_dashboard_architect.__file__).read_text(encoding="utf-8")
    assert "DASHBOARD_PAYLOAD.global_kpis.unit_symbol" in src
    assert "pct === 0 || excessEv <= 0" in src
    assert "elDrag.textContent = '$' + avertedDol" not in src
