from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from autonomous_engine.tally_pdf_ingestion import (
    extract_table_from_pdf,
    flatten_grouped_accounting_ledger,
)
from autonomous_engine.robust_excel_scanner import smart_read_tabular
from autonomous_engine.stage1_topology_profiler import profile_raw_directory
from autonomous_engine.templated_dag_runner import load_entity_dataframe
from autonomous_engine.api_server import app


def test_w2_tally_nested_grouped_ledger_flattener_and_company_preservation(tmp_path):
    """Real Indian Tally grouped ledger with party section headers, mid-sheet subtotals, and 'Total Logistics'."""
    rows = [
        ["SHREE GANESH WHOLESALE — PARTY SALES REGISTER", None, None, None, None],
        ["Period: 01-Apr-2026 to 30-Apr-2026", None, None, None, None],
        ["Date", "Voucher_No", "Item_Name", "Qty", "Amount"],
        ["M/s Sharma Traders", None, None, None, None],
        ["01/04/2026", "INV-101", "Basmati Rice 25kg", 10, "Rs. 21,000/-"],
        ["03/04/2026", "INV-102", "Mustard Oil 15L", 5, "Rs. 13,250/-"],
        ["Sub Total", None, None, 15, "Rs. 34,250/-"],
        ["Ledger: Gupta Kirana", None, None, None, None],
        ["02/04/2026", "INV-103", "Refined Sugar 50kg", 4, "Rs. 8,600/-"],
        ["05/04/2026", "INV-104", "Basmati Rice 25kg", 3, "(Rs. 1,200/-)"],
        ["Party Total", None, None, 7, "Rs. 7,400/-"],
        ["Total Logistics Pvt Ltd", None, None, None, None],
        ["06/04/2026", "INV-105", "Detergent 1kg", 20, "₹2,200/-"],
        ["Closing Balance", None, None, 42, "Rs. 43,850/-"],
        ["Grand Total", None, None, 42, "Rs. 43,850/-"],
    ]
    xlsx_path = tmp_path / "tally_party_register.xlsx"
    pd.DataFrame(rows).to_excel(xlsx_path, index=False, header=False)

    df_clean = smart_read_tabular(str(xlsx_path))
    assert "Ledger_Party" in df_clean.columns
    assert len(df_clean) == 5, f"Expected exact 5 transaction rows, got {len(df_clean)}: {df_clean}"

    parties = set(df_clean["Ledger_Party"].tolist())
    assert "M/s Sharma Traders" in parties
    assert "Gupta Kirana" in parties
    assert "Total Logistics Pvt Ltd" in parties

    # Exact monetary sum: 21000 + 13250 + 8600 - 1200 + 2200 = 43850
    assert abs(float(df_clean["Amount"].sum()) - 43850.0) < 0.01

    # Also verify load_entity_dataframe() in templated_dag_runner matches identically
    df_dag = load_entity_dataframe(xlsx_path)
    assert len(df_dag) == 5
    assert "Ledger_Party" in df_dag.columns
    assert abs(float(df_dag["Amount"].sum()) - 43850.0) < 0.01


def test_w2_normal_flat_table_not_mutated():
    df = pd.DataFrame({
        "Order_ID": [1, 2, 3, 4],
        "Customer": ["Total Energies India", "Total Logistics", "Reliance Retail", "DMart"],
        "Region": ["West", "North", "West", "South"],
        "Sales": [1500.0, 2200.0, 3100.0, 1800.0],
    })
    out, meta = flatten_grouped_accounting_ledger(df)
    assert meta["flattened"] is False
    assert "Ledger_Party" not in out.columns
    assert len(out) == 4


def _build_sample_invoice_pdf(pdf_path: Path) -> None:
    """Creates a genuine 2-page bordered PDF invoice table using PyMuPDF (`fitz`)."""
    import fitz

    doc = fitz.open()
    headers = ["Invoice_No", "Date", "Party_Name", "Item", "Qty", "Amount"]
    pages_rows = [
        [
            ["INV-001", "01/04/2026", "Sharma Kirana", "Basmati Rice", "10", "Rs. 21,000/-"],
            ["INV-002", "02/04/2026", "Gupta Traders", "Mustard Oil", "5", "Rs. 13,250/-"],
            ["INV-003", "03/04/2026", "Patel Mart", "Sugar 50kg", "4", "Rs. 8,600/-"],
        ],
        [
            ["INV-004", "04/04/2026", "Sharma Kirana", "Mustard Oil", "6", "Rs. 15,900/-"],
            ["INV-005", "05/04/2026", "Verma Store", "Basmati Rice", "8", "Rs. 16,800/-"],
            ["Grand Total", "", "", "", "33", "Rs. 75,550/-"],
        ],
    ]
    col_x = [30, 105, 185, 290, 390, 445, 555]
    for p_rows in pages_rows:
        page = doc.new_page(width=595, height=842)
        grid = [headers] + p_rows
        y0 = 60
        row_h = 26
        for r_idx, row in enumerate(grid):
            y_top = y0 + r_idx * row_h
            y_bot = y_top + row_h
            for c_idx, cell in enumerate(row):
                rect = fitz.Rect(col_x[c_idx], y_top, col_x[c_idx + 1], y_bot)
                page.draw_rect(rect, color=(0, 0, 0), width=0.6)
                page.insert_text((col_x[c_idx] + 4, y_top + 17), cell, fontsize=9)
    doc.save(str(pdf_path))
    doc.close()


def test_w2_pdf_multipage_invoice_extraction_and_api_preview(tmp_path):
    pdf_file = tmp_path / "tally_sales_statement.pdf"
    _build_sample_invoice_pdf(pdf_file)

    df_pdf = extract_table_from_pdf(pdf_file)
    assert len(df_pdf) == 5, f"Expected 5 stitched rows (Grand Total stripped), got {len(df_pdf)}: {df_pdf}"
    assert "Amount" in df_pdf.columns
    assert abs(float(df_pdf["Amount"].sum()) - 75550.0) < 0.01

    # Stage 1 Topology Profiler discovers & profiles .pdf cleanly
    topo = profile_raw_directory(str(tmp_path))
    assert "tally_sales_statement" in topo["tables"]
    assert topo["tables"]["tally_sales_statement"]["estimated_rows"] == 5

    # FastAPI /api/v1/preview-intent accepts .pdf cleanly
    client = TestClient(app)
    with open(pdf_file, "rb") as fh:
        resp = client.post(
            "/api/v1/preview-intent",
            files={"file": ("tally_sales_statement.pdf", fh.read(), "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body.get("columns", [])) >= 5


def test_w2_scanned_image_only_pdf_raises_clear_error(tmp_path):
    import fitz

    blank_pdf = tmp_path / "scanned_photo_only.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=400)
    doc.save(str(blank_pdf))
    doc.close()

    with pytest.raises(ValueError, match="scanned image"):
        extract_table_from_pdf(blank_pdf)
