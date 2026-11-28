import json
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from autonomous_engine.growth_inventory_engine import (
    analyze_growth_and_inventory,
    detect_commercial_schema,
    render_growth_markdown_section,
)
from autonomous_engine.api_server import _extract_executive_pulse, ALLOWED_ARTIFACTS


def _make_indian_shopkeeper_sales_df() -> pd.DataFrame:
    """Realistic 60-day Indian kirana / hardware shopkeeper sales ledger with ZERO defect/return columns."""
    rng = np.random.default_rng(42)
    start = datetime(2026, 1, 1)
    rows = []
    items = [
        # (item, category, unit_cost, sell_price, stock_on_hand, base_qty)
        ("Basmati Rice 25kg", "Grains", 1600.0, 2100.0, 8, 6),       # Class A + CRITICAL STOCKOUT
        ("Mustard Oil 15L", "Oils", 2100.0, 2650.0, 12, 4),          # Class A + REORDER SOON
        ("Refined Sugar 50kg", "Grains", 2200.0, 2150.0, 45, 3),     # NEGATIVE MARGIN LEAK!
        ("Premium Spice Pack", "Spices", 180.0, 260.0, 500, 1),      # OVERSTOCK / DEAD CAPITAL!
        ("Detergent Powder 1kg", "FMCG", 75.0, 110.0, 60, 2),        # Healthy
    ]
    parties = ["Sharma Kirana", "Gupta Traders", "Patel Mart", "Verma Store", "Singh Wholesale"]
    for day_i in range(60):
        dt = start + timedelta(days=day_i)
        wk_boost = 1.45 if dt.weekday() == 5 else 1.0  # Saturday peak
        for item, cat, cp, sp, stk, bq in items:
            # Make Verma Store dormant in last 35 days
            avail_parties = parties if day_i < 25 else [p for p in parties if p != "Verma Store"]
            # Weight Sharma Kirana heavily (>35% concentration)
            p_weights = [0.45] + [(0.55 / (len(avail_parties) - 1))] * (len(avail_parties) - 1)
            party = str(rng.choice(avail_parties, p=p_weights))
            qty = max(1, int(round(bq * wk_boost * rng.uniform(0.75, 1.25))))
            if item == "Premium Spice Pack" and day_i % 3 != 0:
                continue
            rev = round(qty * sp, 2)
            due = round(rev * 0.25, 2) if party == "Sharma Kirana" else 0.0
            rows.append({
                "Invoice_Date": dt.strftime("%d/%m/%Y"),
                "Item_Name": item,
                "Category": cat,
                "Qty": qty,
                "Cost_Price": cp,
                "Selling_Price": sp,
                "Sales_Amount": rev,
                "Stock_On_Hand": stk,
                "Party_Name": party,
                "Balance_Due": due,
            })
    return pd.DataFrame(rows)


def test_w1_pure_indian_shopkeeper_sales_profit_forecast_and_stock(tmp_path):
    df = _make_indian_shopkeeper_sales_df()
    report = analyze_growth_and_inventory(df, out_dir=tmp_path)

    assert report["is_applicable"] is True
    assert report["is_pure_sales_ledger"] is True
    assert report["currency_unit"] == "₹"
    assert (tmp_path / "growth_inventory_report.json").exists()

    # Exact revenue & profit verification
    expected_rev = round(float(df["Sales_Amount"].sum()), 2)
    expected_cost = round(float((df["Cost_Price"] * df["Qty"]).sum()), 2)
    assert abs(report["kpis"]["total_revenue"] - expected_rev) < 1.0
    assert report["kpis"]["has_profit"] is True
    assert abs(report["kpis"]["gross_profit"] - (expected_rev - expected_cost)) < 1.0

    # Negative margin SKU must be caught
    neg_names = [x["item"] for x in report["negative_margin_items"]]
    assert "Refined Sugar 50kg" in neg_names

    # Critical stockout SKU & Dead-stock SKU must be caught
    reorder_names = [x["item"] for x in report["reorder_alerts"]]
    assert "Basmati Rice 25kg" in reorder_names
    rice_alert = next(x for x in report["reorder_alerts"] if x["item"] == "Basmati Rice 25kg")
    assert rice_alert["stock_status"] == "CRITICAL_STOCKOUT"
    assert rice_alert["recommended_30d_order_qty"] > 0

    dead_names = [x["item"] for x in report["dead_stock_items"]]
    assert "Premium Spice Pack" in dead_names

    # 30-day Holt-Winters forecast with Saturday peak & 95% bounds
    fc = report["demand_forecast"]
    assert fc["forecast_available"] is True
    assert fc["next_30d_revenue"] > 0
    assert fc["peak_weekday"] == "Saturday"
    assert fc["backtest_wape_pct"] < 50.0

    # Party concentration + dormant repeat buyer + udhaar
    ph = report["party_health"]
    assert ph["concentration_risk"] is True
    assert ph["top1_party"] == "Sharma Kirana"
    dormant_names = [x["party"] for x in ph["dormant_repeat_buyers"]]
    assert "Verma Store" in dormant_names
    assert ph["total_udhaar"] > 0

    # Bilingual EN + HI narratives & Markdown appendix
    assert len(report["narratives"]["en"]["actions"]) >= 4
    assert len(report["narratives"]["hi"]["actions"]) >= 4
    md = render_growth_markdown_section(report)
    assert "Next 30-Day Demand Forecast" in md
    assert "Basmati Rice 25kg" in md


def test_w1_non_commercial_clinical_dataset_stays_clean():
    """Clinical / SCADA datasets with no sales/inventory must NEVER fabricate commercial metrics."""
    df_clin = pd.DataFrame({
        "age": [65, 72, 55, 60, 80, 48, 59, 63, 70, 52],
        "ejection_fraction": [20, 35, 50, 25, 15, 60, 40, 30, 20, 55],
        "serum_creatinine": [1.9, 1.1, 0.9, 2.3, 2.7, 0.8, 1.2, 1.5, 2.1, 1.0],
        "DEATH_EVENT": [1, 0, 0, 1, 1, 0, 0, 1, 1, 0],
    })
    res = analyze_growth_and_inventory(df_clin)
    assert res["is_applicable"] is False


def test_w1_api_pulse_exposes_growth_inventory_artifact(tmp_path):
    assert "growth_inventory_report.json" in ALLOWED_ARTIFACTS
    df = _make_indian_shopkeeper_sales_df()
    analyze_growth_and_inventory(df, out_dir=tmp_path)
    manifest = {
        "governance": {"audited_fact_records": len(df)},
        "target_outcome": {"column_name": "Sales_Amount", "total_adverse_events": 10, "adverse_event_rate_pct": 5.0},
        "financial_exposure": {"total_adverse_capital_drag": 50000.0, "total_portfolio_volume": 500000.0, "currency_unit": "₹", "monetary_column": "Sales_Amount"},
    }
    pulse = _extract_executive_pulse(tmp_path, manifest, "")
    assert pulse.get("growth_inventory") is not None
    assert pulse["growth_inventory"]["is_pure_sales_ledger"] is True
    assert pulse["growth_inventory"]["kpis"]["has_profit"] is True


def test_w1_real_world_camelcase_pos_returns_mdy_dates_and_line_revenue(tmp_path):
    """
    Regression test for real-world open-source POS schemas (CamelCase headers,
    Quantity * UnitPrice without pre-computed Sales, negative-quantity credit-note returns,
    MM/DD/YYYY H:MM timestamps, Description items, numeric CustomerID with NULL walk-ins).
    """
    from autonomous_engine.templated_dag_runner import execute_templated_pipeline
    from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
    from autonomous_engine.conversational_qa_engine import ConversationalBusinessQAEngine

    raw_dir = tmp_path / "raw_data"
    out_dir = tmp_path / "output"
    cache_dir = tmp_path / "cache"
    raw_dir.mkdir()
    out_dir.mkdir()
    cache_dir.mkdir()

    rng = np.random.default_rng(7)
    rows = []
    start = datetime(2024, 12, 1, 9, 15)
    skus = [("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.55), ("22423", "REGENCY CAKESTAND 3 TIER", 12.75), ("84879", "ASSORTED COLOUR BIRD ORNAMENT", 1.69)]
    for day_i in range(45):
        dt = start + timedelta(days=day_i)
        dt_str = f"{dt.month}/{dt.day}/{dt.year} {dt.hour}:{dt.minute:02d}"
        for k in range(4):
            code, desc, price = skus[(day_i + k) % len(skus)]
            is_ret = (day_i % 9 == 0 and k == 0)
            qty = -3 if is_ret else int(rng.integers(2, 12))
            inv = f"C53{day_i:03d}{k}" if is_ret else f"53{day_i:03d}{k}"
            cid = np.nan if k == 3 else float(17850 + (day_i % 5))
            country = "EIRE" if (day_i % 5 == 0) else "United Kingdom"
            rows.append({
                "InvoiceNo": inv,
                "StockCode": code,
                "Description": desc,
                "Quantity": qty,
                "InvoiceDate": dt_str,
                "UnitPrice": price,
                "CustomerID": cid,
                "Country": country,
            })
    pd.DataFrame(rows).to_csv(raw_dir / "pos_register.csv", index=False)

    bp = {
        "project_title": "POS Regression",
        "fact_table": "pos_register",
        "target_metric": "Quantity",
        "primary_id_column": "fact_surrogate_id",
        "region_profile": "UK",
    }
    bp_path = out_dir / "execution_blueprint.json"
    bp_path.write_text(json.dumps(bp), encoding="utf-8")
    res_dag = execute_templated_pipeline(str(bp_path), str(raw_dir), str(out_dir), str(cache_dir))
    assert res_dag["status"] in ("PASSED", "SUCCESS")

    df_fact = pd.read_parquet(out_dir / "bi_ready_fact.parquet")
    assert "line_revenue" in df_fact.columns
    assert "line_gross_value" in df_fact.columns

    # Verify MM/DD/YYYY was NOT scrambled to DD/MM/YYYY (Dec 1 must stay 2024-12-01, NOT 2024-01-12!)
    min_iso = str(df_fact["InvoiceDate"].min())
    assert min_iso.startswith("2024-12-01"), f"Date day/month scrambled: {min_iso}"

    # Verify exact net revenue & negative-quantity credit-note return detection
    expected_net = round(float((df_fact["Quantity"] * df_fact["UnitPrice"]).sum()), 2)
    assert abs(float(df_fact["line_revenue"].sum()) - expected_net) < 0.05

    canon = resolve_canonical_target_and_cost(df_fact, bp, raw_source_cols=set(rows[0].keys()))
    assert canon["target_col"] == "Quantity"
    assert "Quantity < 0" in canon["target_desc"]
    assert int(canon["binary_target"].sum()) == int((df_fact["Quantity"] < 0).sum())
    assert canon["cost_col"] == "line_gross_value"
    assert canon["unit_symbol"] == "£"

    # Verify Growth & Inventory activates on CamelCase POS with exact net revenue, forecast & no Walk-in VIP bug
    gi = analyze_growth_and_inventory(df_fact, out_dir=out_dir, blueprint=bp)
    assert gi["is_applicable"] is True
    assert abs(gi["kpis"]["total_revenue"] - expected_net) < 0.05
    assert gi["kpis"]["return_lines"] == int((df_fact["Quantity"] < 0).sum())
    assert gi["detected_schema"]["item_col"] == "Description"
    assert gi["detected_schema"]["party_col"] == "CustomerID"
    assert gi["party_health"]["top1_party"] != "Walk-in / Guest"
    assert gi["demand_forecast"]["forecast_available"] is True
    assert gi["demand_forecast"]["history_start"] == "2024-12-01"

    # Verify Ask-AI resolves Description items & exact line_revenue
    qa = ConversationalBusinessQAEngine(str(out_dir))
    r_item = qa.ask("sabse zyada bikne wala item batao", language="hinglish")
    assert r_item["status"] == "success"
    assert r_item["data"] and r_item["data"][0]["item"] in {s[1] for s in skus}
    r_ctry = qa.ask("What is total sales by Country?", language="english")
    assert r_ctry["status"] == "success"
    total_ctry_sales = round(sum(float(x["total_sales"]) for x in r_ctry["data"]), 2)
    assert abs(total_ctry_sales - expected_net) < 0.10
