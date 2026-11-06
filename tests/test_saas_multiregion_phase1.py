"""
================================================================================
UNIT TESTS: PHASE 1 MULTI-REGION SAAS UPGRADES (US + UK + INDIA)
================================================================================
"""

import pytest
import numpy as np
import pandas as pd
from autonomous_engine.target_resolver import (
    resolve_canonical_target_and_cost,
    resolve_currency_metadata,
    format_currency_value
)
from autonomous_engine.pii_scrubber import scrub_text, is_sensitive_column_name
from autonomous_engine.robust_excel_scanner import (
    clean_accounting_series,
    strip_accounting_summary_rows
)


def test_multicurrency_detection_uk_and_india():
    """Engine must detect GBP (£) and INR (₹) from column headers and region profiles."""
    # UK dataset
    df_uk = pd.DataFrame({
        "order_id": [1, 2, 3],
        "churn": [1, 0, 0],
        "revenue_gbp": [150.0, 320.0, 95.0]
    })
    res_uk = resolve_canonical_target_and_cost(df_uk)
    assert res_uk["currency_code"] == "GBP"
    assert res_uk["unit_symbol"] == "£"
    assert res_uk["numbering_system"] == "western"

    # India dataset with column header indicator
    df_in = pd.DataFrame({
        "invoice_id": [101, 102, 103],
        "default_flag": [0, 1, 0],
        "taxable_amount_inr": [45000.0, 120000.0, 35000.0]
    })
    res_in = resolve_canonical_target_and_cost(df_in)
    assert res_in["currency_code"] == "INR"
    assert res_in["unit_symbol"] == "₹"
    assert res_in["numbering_system"] == "indian"

    # Explicit region profile override
    df_neutral = pd.DataFrame({
        "client_id": [1, 2],
        "churn": [1, 0],
        "mrr": [5000.0, 8000.0]
    })
    res_override_in = resolve_canonical_target_and_cost(df_neutral, region_profile="IN")
    assert res_override_in["currency_code"] == "INR"
    assert res_override_in["unit_symbol"] == "₹"
    assert res_override_in["numbering_system"] == "indian"


def test_currency_formatting_western_vs_indian():
    """Formats monetary figures correctly into Western (K/M/B) and Indian (Lakh/Crore) scales."""
    # Western USD
    assert format_currency_value(117700, "USD", "western") == "$117.70K"
    assert format_currency_value(4290000000, "USD", "western") == "$4.29B"
    # Western GBP
    assert format_currency_value(92400, "GBP", "western") == "£92.40K"

    # Indian Lakh / Crore
    assert format_currency_value(985000, "INR", "indian") == "₹9.85 Lakh"
    assert format_currency_value(14200000, "INR", "indian") == "₹1.42 Cr"
    assert format_currency_value(25500, "INR", "indian") == "₹25.50K"


def test_tri_jurisdiction_pii_scrubbing():
    """Scrubs UK National Insurance numbers, Indian GSTIN, and UPI handles."""
    # UK NI Number
    raw_uk = "Employee NI Number is QQ123456C registered in Leeds."
    scrubbed_uk = scrub_text(raw_uk)
    assert "[REDACTED_UK_NI_NUMBER]" in scrubbed_uk
    assert "QQ123456C" not in scrubbed_uk

    # Indian GSTIN
    raw_gst = "Vendor invoice from GSTIN 27AABCS1429B1Z0 for services."
    scrubbed_gst = scrub_text(raw_gst)
    assert "[REDACTED_INDIA_GSTIN]" in scrubbed_gst
    assert "27AABCS1429B1Z0" not in scrubbed_gst

    # UPI Handle
    raw_upi = "Direct settlement to store@okhdfcbank done via QR."
    scrubbed_upi = scrub_text(raw_upi)
    assert "[REDACTED_UPI_HANDLE]" in scrubbed_upi
    assert "store@okhdfcbank" not in scrubbed_upi


def test_stage0_tally_and_accounting_normalizer():
    """Detects and strips bottom summary rows and parses Indian/accounting strings."""
    # Data with summary rows
    df_raw = pd.DataFrame({
        "Particulars": ["Invoice #1", "Invoice #2", "Invoice #3", "Grand Total"],
        "Voucher_No": ["V-01", "V-02", "V-03", ""],
        "Amount": ["15,000.00 Dr", "2,500.00 Cr", "12,34,567.00", "12,47,067.00"]
    })

    # Summary row stripping
    df_clean = strip_accounting_summary_rows(df_raw)
    assert len(df_clean) == 3
    assert "Grand Total" not in df_clean["Particulars"].values

    # Accounting string conversion
    cleaned_amt = clean_accounting_series(df_clean["Amount"])
    assert cleaned_amt.iloc[0] == 15000.0
    assert cleaned_amt.iloc[1] == -2500.0
    assert cleaned_amt.iloc[2] == 1234567.0
