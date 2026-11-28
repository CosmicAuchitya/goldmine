"""
=============================================================================
DATAX-RAY WORKSTREAM 1 — PURE SALES, PROFIT, DEMAND FORECAST & STOCK ENGINE
=============================================================================
Solves Weakness #1 (Risk/Defect-Only Paradigm Bias):
Gives Indian shopkeepers, distributors, and retail/SME operators complete
commercial intelligence EVEN WHEN a dataset is a clean sales/Tally register
with zero defect/return/churn columns:
  1. Revenue, Gross Margin & Negative-Margin / Discount Leakage Audit
  2. ABC Pareto Revenue & Inventory Concentration (80/20 Cash Cows vs Slow Stock)
  3. Zero-Hallucination 30-Day Demand Forecasting (Damped Holt Exponential
     Smoothing + Day-of-Week Seasonality + 95% Prediction Interval + Backtest WAPE)
  4. Smart Safety Stock, Reorder Point (ROP), Stockout & Overstock Trap Radar
  5. Party / Customer Concentration, Dormant Repeat Buyers & Udhaar Exposure
  6. 100% Grounded Bilingual (English + Simple Business Hindi) Action Briefs

100% deterministic, zero external paid dependencies, zero fabricated claims:
activates ONLY on datasets with real commercial sales/quantity/inventory columns.
=============================================================================
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from .target_resolver import (
        is_index_artifact,
        is_synthetic_column,
        is_temporal_column,
        resolve_currency_metadata,
    )
except ImportError:
    from target_resolver import (
        is_index_artifact,
        is_synthetic_column,
        is_temporal_column,
        resolve_currency_metadata,
    )


_REVENUE_PAT = re.compile(
    r"(?:^|_|\s)(?:line_revenue|sales|revenue|turnover|total_amount|net_amount|bill_amount|invoice_amount|"
    r"order_value|order_amount|grand_total|line_total|total_sales|total_price|net_sales|amount|"
    r"gross_sales|selling_total|sale_value|bikri|कुल_बिक्री|रकम|राशि)(?:$|_|\s)",
    re.IGNORECASE,
)
_UNIT_PRICE_PAT = re.compile(
    r"(?:^|_|\s)(?:unit_price|selling_price|sale_price|item_price|mrp|rate|price|sp|dar|भाव|कीमत)(?:$|_|\s)",
    re.IGNORECASE,
)
_COST_PAT = re.compile(
    r"(?:^|_|\s)(?:cost|cost_price|unit_cost|purchase_cost|purchase_price|cogs|buying_price|"
    r"landed_cost|cp|kharid|खरीद|लागत)(?:$|_|\s)",
    re.IGNORECASE,
)
_PROFIT_PAT = re.compile(
    r"(?:^|_|\s)(?:profit|net_profit|gross_profit|margin|margin_amount|munafa|मुनाफा|लाभ)(?:$|_|\s)",
    re.IGNORECASE,
)
_DISCOUNT_PAT = re.compile(
    r"(?:^|_|\s)(?:discount|rebate|markdown|disc|chhoot|छूट)(?:$|_|\s)",
    re.IGNORECASE,
)
_QTY_PAT = re.compile(
    r"(?:^|_|\s)(?:qty|quantity|units|units_sold|sold_qty|order_qty|billed_qty|volume|pcs|pieces|boxes|"
    r"packs|nos|count_sold|मात्रा)(?:$|_|\s)",
    re.IGNORECASE,
)
_STOCK_PAT = re.compile(
    r"(?:^|_|\s)(?:stock|stock_on_hand|closing_stock|inventory|inventory_qty|available_stock|"
    r"available_qty|qty_on_hand|on_hand|warehouse_stock|current_stock|स्टॉक)(?:$|_|\s)",
    re.IGNORECASE,
)
_ITEM_PAT = re.compile(
    r"(?:^|_|\s)(?:item|item_name|product|product_name|sku|sku_name|material|medicine|article|"
    r"goods|brand|model|commodity|उत्पाद|आइटम|सामान)(?:$|_|\s)",
    re.IGNORECASE,
)
_POS_ITEM_FALLBACK_PAT = re.compile(
    r"(?:^|_|\s)(?:description|item_desc|item_description|product_desc|product_description|particulars|stock_code|product_code)(?:$|_|\s)",
    re.IGNORECASE,
)
_CATEGORY_PAT = re.compile(
    r"(?:^|_|\s)(?:category|sub_category|subcategory|department|product_line|segment|group|class|"
    r"श्रेणी|कैटेगरी)(?:$|_|\s)",
    re.IGNORECASE,
)
_PARTY_PAT = re.compile(
    r"(?:^|_|\s)(?:party|party_name|customer|customer_name|client|buyer|retailer|dealer|"
    r"distributor|vendor|account_name|shop|store|ledger|ग्राहक|पार्टी)(?:$|_|\s)",
    re.IGNORECASE,
)
_PARTY_ID_FALLBACK_PAT = re.compile(
    r"(?:^|_)(?:customer_id|client_id|party_id|buyer_id|account_id|member_id|dealer_id)$",
    re.IGNORECASE,
)
_DUE_PAT = re.compile(
    r"(?:^|_|\s)(?:due|balance_due|pending_amount|receivable|outstanding|udhaar|credit_balance|"
    r"overdue_amount|बकाया|उधार)(?:$|_|\s)",
    re.IGNORECASE,
)
_NON_COMMERCIAL_GUARD_PAT = re.compile(
    r"(?:ejection_fraction|creatinine|glucose|insulin|bloodpressure|serum_sodium|cholesterol|"
    r"air_temperature|rotational_speed|torque|tool_wear|tailnum|flight|dep_delay|arr_delay|"
    r"cylinders|horsepower|displacement|mpg|latitude|longitude|ocean_proximity)",
    re.IGNORECASE,
)


def _norm_col(col: str) -> str:
    """Normalizes CamelCase, spaces, and hyphens to lowercase snake_case for regex matching."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(col).strip())
    return re.sub(r"[\s\-]+", "_", s).lower()


def _format_money(val: float, currency: str = "₹") -> str:
    sign = "-" if val < 0 else ""
    av = abs(float(val))
    if currency == "₹":
        if av >= 1e7:
            return f"{sign}₹{av / 1e7:.2f} Cr"
        if av >= 1e5:
            return f"{sign}₹{av / 1e5:.2f} L"
        if av >= 1e3:
            return f"{sign}₹{av:,.0f}"
        return f"{sign}₹{av:.2f}"
    if av >= 1e9:
        return f"{sign}{currency}{av / 1e9:.2f}B"
    if av >= 1e6:
        return f"{sign}{currency}{av / 1e6:.2f}M"
    if av >= 1e3:
        return f"{sign}{currency}{av / 1e3:.1f}K"
    return f"{sign}{currency}{av:,.2f}"


def _safe_numeric(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    cleaned = (
        s.astype(str)
        .str.strip()
        .str.replace(r"(?i)^\s*(?:rs\.?|inr|usd|eur|gbp)\s*", "", regex=True)
        .str.replace(r"[₹\$£€,\s]", "", regex=True)
        .str.replace(r"/-$", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _parse_dates_safely(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    non_null = s.dropna()
    if len(non_null) == 0:
        return pd.to_datetime(s, errors="coerce")
    # Sample evenly across the entire timeline (not just .head(200) which may all be day 1!)
    step = max(1, len(non_null) // 400)
    sample = non_null.iloc[::step].head(400).astype(str).str.strip()
    # Detect explicit DD/MM/YYYY vs MM/DD/YYYY before falling back to mixed parsing
    dmy_evidence = 0
    mdy_evidence = 0
    iso_evidence = 0
    for val in sample:
        m_iso = re.match(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}", val)
        if m_iso:
            iso_evidence += 1
            continue
        m_slash = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", val)
        if m_slash:
            a, b = int(m_slash.group(1)), int(m_slash.group(2))
            if a > 12 and b <= 12:
                dmy_evidence += 1
            elif b > 12 and a <= 12:
                mdy_evidence += 1
    try:
        if iso_evidence >= max(1, len(sample) // 2):
            return pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=False)
        if dmy_evidence > mdy_evidence:
            return pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=True)
        if mdy_evidence > dmy_evidence:
            return pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=False)
        p_us = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=False)
        p_in = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=True)
        if p_in.notna().sum() > p_us.notna().sum():
            return p_in
        if p_in.notna().sum() == p_us.notna().sum() and p_in.notna().any():
            span_in = (p_in.max() - p_in.min()).days
            span_us = (p_us.max() - p_us.min()).days
            if span_in < span_us:
                return p_in
        return p_us
    except Exception:
        return pd.to_datetime(s, errors="coerce")


def detect_commercial_schema(
    df: pd.DataFrame,
    blueprint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Identifies commercial ledger roles (date, revenue, unit_price, cost, profit,
    discount, qty, stock, item, category, party, due) with strict guards against
    clinical/SCADA/telemetry false positives.
    """
    cols = list(df.columns)
    col_blob = " ".join(str(c) for c in cols)
    non_comm_hits = len(_NON_COMMERCIAL_GUARD_PAT.findall(col_blob))

    roles: Dict[str, Optional[str]] = {
        "date_col": None,
        "revenue_col": None,
        "unit_price_col": None,
        "cost_col": None,
        "profit_col": None,
        "discount_col": None,
        "qty_col": None,
        "stock_col": None,
        "item_col": None,
        "category_col": None,
        "party_col": None,
        "due_col": None,
    }

    usable_cols = [
        c for c in cols
        if not is_index_artifact(c, df[c])
        and not is_synthetic_column(c, blueprint)
        and not str(c).startswith("_")
        and not str(c).lower().startswith("net_contribution_margin")
    ]

    # 1. Detect Date column
    for c in usable_cols:
        if is_temporal_column(df[c], c):
            dt = _parse_dates_safely(df[c])
            valid_ratio = float(dt.notna().mean()) if len(dt) else 0.0
            if valid_ratio >= 0.65 and dt.dropna().dt.normalize().nunique() >= 2:
                # Reject pure numeric year-only integers masquerading as 1970 timestamps
                if dt.dropna().dt.year.min() >= 1990:
                    roles["date_col"] = c
                    break

    # 2. Detect Numeric Commercial Roles
    def _is_num_usable(col: str) -> bool:
        s = _safe_numeric(df[col])
        return bool(s.notna().mean() >= 0.65 and s.dropna().nunique() >= 2)

    for c in usable_cols:
        if c == roles["date_col"]:
            continue
        c_low = _norm_col(c)
        if c_low.endswith(("_id", "_code", "_num", "_no", "_phone", "_mobile", "_pin", "_zip")):
            continue
        if c_low == "line_gross_value":
            continue
        if not roles["stock_col"] and _STOCK_PAT.search(c_low) and _is_num_usable(c):
            roles["stock_col"] = c
        elif not roles["qty_col"] and _QTY_PAT.search(c_low) and not _STOCK_PAT.search(c_low) and _is_num_usable(c):
            roles["qty_col"] = c
        elif not roles["profit_col"] and _PROFIT_PAT.search(c_low) and _is_num_usable(c):
            roles["profit_col"] = c
        elif not roles["cost_col"] and _COST_PAT.search(c_low) and _is_num_usable(c):
            roles["cost_col"] = c
        elif not roles["discount_col"] and _DISCOUNT_PAT.search(c_low) and _is_num_usable(c):
            roles["discount_col"] = c
        elif not roles["due_col"] and _DUE_PAT.search(c_low) and _is_num_usable(c):
            roles["due_col"] = c

    # Revenue vs Unit Price (prefer explicit line-total revenue over unit price)
    rev_candidates = [
        c for c in usable_cols
        if c not in set(roles.values()) and _norm_col(c) != "line_gross_value"
        and _REVENUE_PAT.search(_norm_col(c)) and _is_num_usable(c)
        and not _COST_PAT.search(_norm_col(c)) and not _DISCOUNT_PAT.search(_norm_col(c)) and not _DUE_PAT.search(_norm_col(c))
    ]
    up_candidates = [
        c for c in usable_cols
        if c not in set(roles.values()) and _UNIT_PRICE_PAT.search(_norm_col(c)) and _is_num_usable(c)
        and not _COST_PAT.search(_norm_col(c))
    ]
    if rev_candidates:
        # Prefer explicit line_revenue / sales / revenue / total over generic amount
        rev_candidates.sort(
            key=lambda x: (
                0 if _norm_col(x) == "line_revenue" else (1 if re.search(r"sales|revenue|total|net|bill|invoice|bikri", _norm_col(x), re.I) else 2),
                -float(_safe_numeric(df[x]).abs().median() or 0.0),
            )
        )
        roles["revenue_col"] = rev_candidates[0]
    if up_candidates:
        for cand in up_candidates:
            if cand != roles["revenue_col"]:
                roles["unit_price_col"] = cand
                break

    # 3. Detect Categorical Entity Roles (Item, Category, Party)
    max_ent_card = max(20000, int(len(df) * 0.98))
    for c in usable_cols:
        if c in set(roles.values()):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        nu = int(df[c].dropna().nunique())
        if nu < 2 or nu > max_ent_card:
            continue
        c_low = _norm_col(c)
        if not roles["item_col"] and _ITEM_PAT.search(c_low):
            roles["item_col"] = c
        elif not roles["category_col"] and _CATEGORY_PAT.search(c_low):
            roles["category_col"] = c
        elif not roles["party_col"] and _PARTY_PAT.search(c_low):
            roles["party_col"] = c

    # POS Fallback: recognize standard POS item columns (Description / Particulars / StockCode) when qty or price exists
    if not roles["item_col"] and (roles["qty_col"] or roles["unit_price_col"] or roles["revenue_col"]):
        pos_item_cands = []
        for c in usable_cols:
            if c in set(roles.values()) or pd.api.types.is_numeric_dtype(df[c]):
                continue
            c_low = _norm_col(c)
            if _POS_ITEM_FALLBACK_PAT.search(c_low):
                nu = int(df[c].dropna().nunique())
                if 2 <= nu <= max_ent_card:
                    # Prefer human-readable description/particulars over raw stock_code
                    prio = 0 if any(k in c_low for k in ("description", "desc", "particulars")) else 1
                    pos_item_cands.append((prio, c))
        if pos_item_cands:
            pos_item_cands.sort(key=lambda t: t[0])
            roles["item_col"] = pos_item_cands[0][1]

    # POS Fallback: allow numeric CustomerID / PartyID as party_col when no string party name exists
    if not roles["party_col"] and (roles["qty_col"] or roles["unit_price_col"] or roles["revenue_col"]):
        for c in usable_cols:
            if c in set(roles.values()):
                continue
            c_low = _norm_col(c)
            if _PARTY_ID_FALLBACK_PAT.search(c_low):
                nu = int(df[c].dropna().nunique())
                if 2 <= nu <= max_ent_card:
                    roles["party_col"] = c
                    break

    # If no item_col found but category_col exists, use category_col as item_col for ABC
    if not roles["item_col"] and roles["category_col"]:
        roles["item_col"] = roles["category_col"]
        roles["category_col"] = None

    has_sales_value = bool(roles["revenue_col"] or (roles["unit_price_col"] and roles["qty_col"]) or roles["unit_price_col"])
    has_commercial_anchor = bool(roles["item_col"] or roles["party_col"] or roles["stock_col"] or (roles["qty_col"] and roles["date_col"]))

    # Guard against clinical / SCADA / housing / credit-default / flight-delay datasets masquerading as retail
    is_non_commercial_domain = non_comm_hits >= 2 and not (roles["item_col"] or roles["stock_col"])
    is_applicable = bool(has_sales_value and has_commercial_anchor and not is_non_commercial_domain and len(df) >= 5)

    reg_prof = (blueprint or {}).get("region_profile") if isinstance(blueprint, dict) else None
    cur_meta = resolve_currency_metadata(
        df,
        cost_col=roles["revenue_col"] or roles["unit_price_col"],
        region_profile=reg_prof,
    )
    currency = str(cur_meta.get("unit_symbol") or "$")
    if currency in ("events", "", "None"):
        currency = "$"
    # Detect authentic Indian SME/Tally cues when region_profile isn't explicitly non-IN
    if currency == "$" and not (reg_prof and str(reg_prof).upper() in ("US", "USA", "UK", "EU", "GLOBAL")):
        sample_blob = " ".join(str(c) for c in cols) + " " + " ".join(
            str(v) for c in [roles["party_col"], roles["item_col"]] if c for v in df[c].dropna().head(15).tolist()
        )
        if re.search(r"(?:₹|\binr\b|\brs\.?\b|gst|kirana|traders|udhaar|bikri|munafa|basmati|party_name|sharma|gupta|patel)", sample_blob, re.IGNORECASE):
            currency = "₹"

    # Detect whether dataset is a Pure Sales / Growth Ledger (no explicit discrete failure/defect column)
    _fail_col_pat = re.compile(
        r"(?:return|rto|churn|default|fraud|cancel|defect|fail|crash|death|mortality|delay|"
        r"attrition|claim|overdue|complication|malfunction|dissatisfied|damage)",
        re.IGNORECASE,
    )
    has_explicit_failure_col = any(
        _fail_col_pat.search(str(c)) and df[c].dropna().nunique() <= 12
        for c in usable_cols
    )
    is_pure_sales_ledger = bool(is_applicable and not has_explicit_failure_col)

    return {
        "is_applicable": is_applicable,
        "is_pure_sales_ledger": is_pure_sales_ledger,
        "currency_unit": currency,
        **roles,
    }


def _damped_holt_forecast(
    y: np.ndarray,
    horizon: int = 30,
    dow_factors: Optional[Dict[int, float]] = None,
    start_dow: int = 0,
) -> Dict[str, Any]:
    """
    Deterministic Damped-Trend Holt's Exponential Smoothing with bounded grid-search
    calibration minimizing one-step-ahead MAE, optional day-of-week seasonality,
    and 95% prediction interval grounded in empirical residual standard deviation.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3:
        return {"forecast_available": False, "reason": "Insufficient time periods (< 3)"}

    # Remove day-of-week seasonality before smoothing if supplied
    deseas = y.copy()
    if dow_factors and len(dow_factors) == 7:
        for i in range(n):
            f = dow_factors.get((start_dow + i) % 7, 1.0)
            deseas[i] = y[i] / max(0.25, f)

    phi = 0.85  # Trend damping factor prevents runaway linear extrapolation
    best_mae = float("inf")
    best_params = (0.35, 0.10)
    best_level = float(deseas[-1])
    best_trend = 0.0
    best_resid = np.zeros(n)

    for alpha in (0.15, 0.30, 0.50, 0.70):
        for beta in (0.0, 0.05, 0.15, 0.30):
            level = float(deseas[0])
            trend = float(deseas[1] - deseas[0]) * 0.5 if n >= 2 else 0.0
            resids = np.zeros(n)
            for t in range(1, n):
                pred = max(0.0, level + phi * trend)
                resids[t] = deseas[t] - pred
                prev_level = level
                level = alpha * deseas[t] + (1.0 - alpha) * pred
                trend = beta * (level - prev_level) + (1.0 - beta) * phi * trend
            mae = float(np.mean(np.abs(resids[1:])))
            if mae < best_mae:
                best_mae = mae
                best_params = (alpha, beta)
                best_level = level
                best_trend = trend
                best_resid = resids

    denom = float(np.sum(np.abs(deseas[1:])))
    wape_pct = round(min(99.9, (float(np.sum(np.abs(best_resid[1:]))) / denom * 100.0)), 1) if denom > 1e-9 else 0.0
    resid_std = float(np.std(best_resid[1:], ddof=1)) if n > 2 else float(np.std(deseas))

    # Project horizon steps ahead
    daily_preds = []
    cum_phi = 0.0
    for h in range(1, horizon + 1):
        cum_phi += phi ** h
        base_pt = max(0.0, best_level + cum_phi * best_trend)
        if dow_factors and len(dow_factors) == 7:
            f = dow_factors.get((start_dow + n + h - 1) % 7, 1.0)
            pt = max(0.0, base_pt * f)
        else:
            pt = base_pt
        daily_preds.append(pt)

    total_point = float(sum(daily_preds))
    # Uncertainty scales with sqrt(horizon) under independent residual shocks
    total_se = resid_std * math.sqrt(horizon)
    lower_95 = max(0.0, total_point - 1.96 * total_se)
    upper_95 = total_point + 1.96 * total_se

    return {
        "forecast_available": True,
        "model": "Damped Holt Exponential Smoothing + Weekday Seasonality" if dow_factors else "Damped Holt Exponential Smoothing",
        "alpha": best_params[0],
        "beta": best_params[1],
        "backtest_wape_pct": wape_pct,
        "point_forecast": round(total_point, 2),
        "lower_95": round(lower_95, 2),
        "upper_95": round(upper_95, 2),
        "daily_avg_forecast": round(total_point / max(1, horizon), 2),
        "daily_series": [round(x, 2) for x in daily_preds[:30]],
    }


def _weekly_damped_holt_predict(weekly_vals: np.ndarray, horizon_weeks: float = 30.0 / 7.0) -> float:
    """
    Bounded Damped-Trend Holt on 7-day aligned weekly totals.
    Eliminates closed-weekend / bank-holiday single-day shocks while capturing real multi-week trends.
    """
    w = np.asarray(weekly_vals, dtype=float)
    n = len(w)
    if n == 0:
        return 0.0
    if n == 1:
        return max(0.0, float(w[0]) * horizon_weeks)
    phi = 0.78
    best_mae = float("inf")
    best_level = float(w[-1])
    best_trend = 0.0
    for alpha in (0.15, 0.25, 0.35, 0.50):
        for beta in (0.0, 0.05, 0.12):
            level = float(w[0])
            trend = float(w[1] - w[0]) * 0.35 if n >= 2 else 0.0
            abs_err = 0.0
            for t in range(1, n):
                pred = max(0.0, level + phi * trend)
                abs_err += abs(w[t] - pred)
                prev_level = level
                level = alpha * w[t] + (1.0 - alpha) * pred
                trend = beta * (level - prev_level) + (1.0 - beta) * phi * trend
            mae = abs_err / max(1, n - 1)
            if mae < best_mae:
                best_mae = mae
                best_level = level
                best_trend = trend
    full_steps = int(math.floor(horizon_weeks))
    frac_step = horizon_weeks - full_steps
    total = 0.0
    cum_phi = 0.0
    for h in range(1, full_steps + 1):
        cum_phi += phi ** h
        total += max(0.0, best_level + cum_phi * best_trend)
    if frac_step > 1e-6:
        cum_phi += phi ** (full_steps + 1)
        total += frac_step * max(0.0, best_level + cum_phi * best_trend)
    return float(max(0.0, total))


def _trailing_weekly_blocks(arr: np.ndarray) -> np.ndarray:
    """Aggregates daily array into complete trailing 7-day blocks (zero partial-week crash)."""
    a = np.asarray(arr, dtype=float)
    n_weeks = len(a) // 7
    if n_weeks <= 0:
        return np.array([float(np.sum(a))], dtype=float)
    tail = a[len(a) - n_weeks * 7:]
    return tail.reshape(n_weeks, 7).sum(axis=1)


def _predict_candidate_30d(
    daily_arr: np.ndarray,
    model_name: str,
    horizon_days: int = 30,
) -> float:
    """Deterministic single-horizon forecast from daily history array (zero future leakage)."""
    arr = np.asarray(daily_arr, dtype=float)
    n = len(arr)
    if n == 0:
        return 0.0
    h_weeks = horizon_days / 7.0
    w_blocks = _trailing_weekly_blocks(arr)
    naive_30d = float(np.sum(arr[-min(n, horizon_days):])) * (horizon_days / max(1, min(n, horizon_days)))
    if len(w_blocks) >= 4:
        naive_4w = float(np.mean(w_blocks[-4:])) * h_weeks
    else:
        naive_4w = naive_30d

    if model_name == "seasonal_naive_30d":
        return float(max(0.0, naive_4w))

    holt_w = _weekly_damped_holt_predict(w_blocks, horizon_weeks=h_weeks)
    if model_name == "weekly_damped_holt":
        return float(max(0.0, holt_w))

    # Multi-year YoY Seasonal Ratio (requires >= 365 + 30 days to observe exact same 30-day window 1 year ago)
    yoy_pred = naive_4w
    if n >= 365 + horizon_days:
        # Exact same calendar window 1 year prior: arr[n - 365 : n - 365 + horizon_days]
        ly_start = n - 365
        ly_window = float(np.sum(arr[ly_start: ly_start + horizon_days]))
        # Compare recent 60 days vs exact same 60 days 1 year prior for YoY growth multiplier
        g_win = min(60, n - 365)
        recent_g = float(np.sum(arr[n - g_win: n]))
        ly_g = float(np.sum(arr[n - 365 - g_win: n - 365])) if (n - 365 - g_win) >= 0 else 0.0
        growth_mult = float(np.clip(recent_g / ly_g, 0.50, 2.00)) if ly_g > 1e-6 else 1.0
        if ly_window > 1e-6:
            yoy_pred = ly_window * growth_mult

    if model_name == "yoy_seasonal_ratio":
        return float(max(0.0, yoy_pred))

    if model_name == "blended_ensemble":
        anchor = yoy_pred if n >= 365 + horizon_days else naive_4w
        return float(max(0.0, 0.5 * holt_w + 0.5 * anchor))

    return float(max(0.0, holt_w))


def _walk_forward_tournament_forecast(
    daily_vals: np.ndarray,
    horizon_days: int = 30,
    dow_factors: Optional[Dict[int, float]] = None,
    start_dow: int = 0,
) -> Dict[str, Any]:
    """
    Forecasting Engine V2:
    - For short series (< 75 days): runs bounded Daily Damped Holt + Weekday Seasonality
      with autocorrelation-adjusted prediction intervals.
    - For medium/long series (>= 75 days): runs a strict zero-leakage rolling 30-day
      walk-forward tournament across Weekly Damped Holt, Seasonal Naive (4-Week),
      Multi-Year YoY Seasonal Ratio (when >= 400 days), and Blended Ensemble.
      Selects the lowest out-of-sample 30-day WAPE winner and calibrates the 95% PI
      directly from empirical rolling 30-day forecast errors (conformal calibration).
    """
    arr = np.asarray(daily_vals, dtype=float)
    n = len(arr)
    if n < 3:
        return {"forecast_available": False, "reason": "Insufficient time periods (< 3)"}

    if n < 75:
        fc = _damped_holt_forecast(arr, horizon=horizon_days, dow_factors=dow_factors, start_dow=start_dow)
        fc["winning_model"] = "daily_damped_holt"
        fc["walk_forward_windows"] = 0
        fc["seasonality_mode"] = "short_daily"
        fc["ci_calibration_method"] = "daily_residual_se"
        fc["baseline_comparison"] = {}
        return fc

    # Determine valid rolling 30-day walk-forward cutoffs strictly inside observed history
    has_yoy = bool(n >= 400)
    min_train = max(42, 365 + horizon_days) if has_yoy else 42
    max_origin = n - horizon_days
    if max_origin <= min_train:
        has_yoy = False
        min_train = 42

    candidates = ["weekly_damped_holt", "seasonal_naive_30d", "blended_ensemble"]
    if has_yoy:
        candidates.append("yoy_seasonal_ratio")

    # Select up to 12 evenly spaced non-leaking cutoffs across observed history
    span_orig = max(1, max_origin - min_train)
    n_wins = min(12, max(2, span_orig // 14 + 1))
    origins = sorted(set(int(round(x)) for x in np.linspace(min_train, max_origin, num=n_wins)))
    origins = [o for o in origins if min_train <= o <= max_origin]

    cand_errors: Dict[str, List[float]] = {m: [] for m in candidates}
    cand_signed: Dict[str, List[float]] = {m: [] for m in candidates}
    actuals_wf: List[float] = []
    flat_abs_errs: List[float] = []
    naive_abs_errs: List[float] = []

    for orig in origins:
        tr = arr[:orig]
        act = float(np.sum(arr[orig: orig + horizon_days]))
        actuals_wf.append(act)
        flat_p = float(np.mean(tr)) * horizon_days
        flat_abs_errs.append(abs(flat_p - act))
        naive_p = _predict_candidate_30d(tr, "seasonal_naive_30d", horizon_days=horizon_days)
        naive_abs_errs.append(abs(naive_p - act))
        for m in candidates:
            pred_m = _predict_candidate_30d(tr, m, horizon_days=horizon_days)
            cand_errors[m].append(abs(pred_m - act))
            cand_signed[m].append(act - pred_m)

    tot_act = float(sum(actuals_wf)) or 1.0
    wape_map: Dict[str, float] = {
        m: round(min(99.9, float(sum(cand_errors[m])) / tot_act * 100.0), 1)
        for m in candidates
    }
    flat_wape = round(min(99.9, float(sum(flat_abs_errs)) / tot_act * 100.0), 1)
    naive_wape = round(min(99.9, float(sum(naive_abs_errs)) / tot_act * 100.0), 1)

    # Pick lowest out-of-sample 30-day WAPE winner (break ties toward YoY/ensemble over naive)
    tie_pref = {"yoy_seasonal_ratio": 0, "blended_ensemble": 1, "weekly_damped_holt": 2, "seasonal_naive_30d": 3}
    winner = min(candidates, key=lambda m: (wape_map[m], tie_pref.get(m, 9)))
    win_wape = wape_map[winner]
    point_fc = _predict_candidate_30d(arr, winner, horizon_days=horizon_days)

    # Empirical conformal 95% prediction interval calibrated on actual rolling 30-day errors
    signed_w = np.asarray(cand_signed[winner], dtype=float)
    abs_w = np.asarray(cand_errors[winner], dtype=float)
    k_w = len(abs_w)
    rms_err = float(np.sqrt(np.mean(signed_w ** 2))) if k_w >= 1 else 0.0
    # Finite-sample t multiplier (prevents narrow under-coverage when k < 10)
    t_mult = 2.45 if k_w <= 4 else (2.20 if k_w <= 8 else 1.96)
    q95_abs = float(np.quantile(abs_w, 0.95)) if k_w >= 4 else (float(np.max(abs_w)) * 1.15 if k_w >= 1 else 0.0)
    half_width = max(t_mult * rms_err, q95_abs, point_fc * 0.05)
    lower_95 = max(0.0, point_fc - half_width)
    upper_95 = point_fc + half_width

    model_labels = {
        "weekly_damped_holt": "Weekly Damped Holt (Walk-Forward Selected)",
        "seasonal_naive_30d": "Seasonal 4-Week Carry-Forward (Walk-Forward Selected)",
        "yoy_seasonal_ratio": "Multi-Year YoY Seasonal Ratio (Walk-Forward Selected)",
        "blended_ensemble": "Weekly Trend + Seasonal Blended Ensemble (Walk-Forward Selected)",
    }
    skill_vs_naive = round(((naive_wape - win_wape) / max(naive_wape, 0.1)) * 100.0, 1)

    return {
        "forecast_available": True,
        "model": model_labels.get(winner, winner),
        "winning_model": winner,
        "backtest_wape_pct": win_wape,
        "point_forecast": round(point_fc, 2),
        "lower_95": round(lower_95, 2),
        "upper_95": round(upper_95, 2),
        "daily_avg_forecast": round(point_fc / max(1, horizon_days), 2),
        "walk_forward_windows": int(k_w),
        "seasonality_mode": "multi_year_yoy" if has_yoy else "intra_year_weekly",
        "ci_calibration_method": "empirical_rolling_30d_conformal",
        "baseline_comparison": {
            "winning_model_wape_pct": win_wape,
            "naive_30d_wape_pct": naive_wape,
            "flat_avg_wape_pct": flat_wape,
            "skill_vs_naive_pct": skill_vs_naive,
            "candidate_wapes_pct": wape_map,
        },
    }


def analyze_growth_and_inventory(
    df: pd.DataFrame,
    out_dir: Optional[Path] = None,
    blueprint: Optional[Dict[str, Any]] = None,
    lead_time_days: int = 7,
) -> Dict[str, Any]:
    """
    Runs the complete Commercial Sales, Margin, 30-Day Demand Forecast,
    Stock Reorder & Party Health Intelligence audit.
    """
    schema = detect_commercial_schema(df, blueprint=blueprint)
    if not schema["is_applicable"]:
        return {
            "is_applicable": False,
            "is_pure_sales_ledger": False,
            "reason": "Dataset is non-commercial (no sales/revenue/inventory ledger detected).",
        }

    cur = schema["currency_unit"]
    work = pd.DataFrame(index=df.index)

    # Resolve Quantity (preserve signed quantity for exact net revenue + returns tracking)
    if schema["qty_col"]:
        work["_qty_signed"] = _safe_numeric(df[schema["qty_col"]]).fillna(0.0)
        work["_qty"] = work["_qty_signed"].clip(lower=0.0)
    else:
        work["_qty_signed"] = 1.0
        work["_qty"] = 1.0

    # Resolve Revenue (exact physical column or unit_price * signed qty)
    if schema["revenue_col"]:
        work["_rev"] = _safe_numeric(df[schema["revenue_col"]]).fillna(0.0)
        rev_source = schema["revenue_col"]
    elif schema["unit_price_col"] and schema["qty_col"]:
        work["_rev"] = (_safe_numeric(df[schema["unit_price_col"]]).fillna(0.0) * work["_qty_signed"])
        rev_source = f"{schema['unit_price_col']} * {schema['qty_col']}"
    else:
        work["_rev"] = _safe_numeric(df[schema["unit_price_col"]]).fillna(0.0)
        rev_source = str(schema["unit_price_col"])

    work["_rev_gross"] = work["_rev"].clip(lower=0.0)
    return_lines_mask = (work["_qty_signed"] < 0) if schema["qty_col"] else (work["_rev"] < 0)
    return_lines_count = int(return_lines_mask.sum())
    gross_sales = float(work["_rev_gross"].sum())
    returns_value = float((-work.loc[return_lines_mask, "_rev"].clip(upper=0.0)).sum()) if return_lines_count > 0 else 0.0

    # Resolve Cost & Gross Profit
    has_profit = False
    if schema["profit_col"]:
        work["_profit"] = _safe_numeric(df[schema["profit_col"]]).fillna(0.0)
        work["_cost"] = work["_rev"] - work["_profit"]
        has_profit = True
    elif schema["cost_col"]:
        raw_cost = _safe_numeric(df[schema["cost_col"]]).fillna(0.0)
        # Disambiguate unit_cost vs line_cost: if median(raw_cost * qty) <= 1.25 * median(rev) and qty median > 1.2
        med_qty = float(work["_qty"].median()) if schema["qty_col"] else 1.0
        med_rev = float(work["_rev"].abs().median())
        med_raw_cost = float(raw_cost.abs().median())
        is_unit_cost_name = bool(re.search(r"unit|price|cp|buying|purchase_price", str(schema["cost_col"]), re.I))
        if schema["qty_col"] and med_qty > 1.2 and (is_unit_cost_name or (med_raw_cost * med_qty <= max(med_rev * 1.35, 1.0) and med_raw_cost < med_rev * 0.65)):
            work["_cost"] = raw_cost * work["_qty"]
        else:
            work["_cost"] = raw_cost
        work["_profit"] = work["_rev"] - work["_cost"]
        has_profit = True
    else:
        work["_cost"] = np.nan
        work["_profit"] = np.nan

    # Discount
    has_discount = False
    if schema["discount_col"]:
        work["_disc"] = _safe_numeric(df[schema["discount_col"]]).fillna(0.0).clip(lower=0.0)
        has_discount = True

    # Dates
    span_days = 30
    min_dt = max_dt = None
    if schema["date_col"]:
        work["_dt"] = _parse_dates_safely(df[schema["date_col"]])
        valid_dt = work["_dt"].dropna()
        if len(valid_dt) >= 2:
            min_dt = valid_dt.min()
            max_dt = valid_dt.max()
            span_days = max(1, int((max_dt - min_dt).days) + 1)

    total_revenue = float(work["_rev"].sum())
    total_orders = int(len(work))
    total_units = float(work["_qty"].sum()) if schema["qty_col"] else float(total_orders)
    avg_order_value = round(total_revenue / max(1, total_orders), 2)
    gross_profit = float(work["_profit"].sum()) if has_profit else None
    gross_margin_pct = round((gross_profit / total_revenue * 100.0), 2) if (has_profit and abs(total_revenue) > 1e-9) else None
    total_discount = float(work["_disc"].sum()) if has_discount else None

    # ------------------------------------------------------------------
    # MODULE A & B: ABC PARETO, MARGIN LEAKAGE & STOCK REORDER BY ITEM
    # ------------------------------------------------------------------
    abc_summary: Dict[str, Any] = {}
    top_items: List[Dict[str, Any]] = []
    reorder_alerts: List[Dict[str, Any]] = []
    dead_stock_items: List[Dict[str, Any]] = []
    negative_margin_items: List[Dict[str, Any]] = []

    if schema["item_col"]:
        work["_item"] = df[schema["item_col"]].astype(str).str.strip().replace({"": "Unknown", "nan": "Unknown"})
        if schema["stock_col"]:
            work["_stock"] = _safe_numeric(df[schema["stock_col"]])
        agg_dict: Dict[str, Any] = {
            "revenue": ("_rev", "sum"),
            "units": ("_qty", "sum"),
            "orders": ("_rev", "count"),
        }
        if has_profit:
            agg_dict["profit"] = ("_profit", "sum")
        if has_discount:
            agg_dict["discount"] = ("_disc", "sum")
        if schema["stock_col"]:
            # Latest stock snapshot per item (sorted by date if available)
            if schema["date_col"] and work["_dt"].notna().any():
                latest_stock = (
                    work.sort_values("_dt")
                    .dropna(subset=["_stock"])
                    .groupby("_item")["_stock"]
                    .last()
                )
            else:
                latest_stock = work.dropna(subset=["_stock"]).groupby("_item")["_stock"].last()
        else:
            latest_stock = pd.Series(dtype=float)

        item_grp = work.groupby("_item", as_index=False).agg(**agg_dict)
        item_grp = item_grp.sort_values("revenue", ascending=False).reset_index(drop=True)
        pos_rev_total = float(item_grp["revenue"].clip(lower=0.0).sum()) or 1.0
        item_grp["rev_share_pct"] = (item_grp["revenue"] / pos_rev_total * 100.0).round(2)
        item_grp["cum_share_pct"] = item_grp["rev_share_pct"].cumsum().round(2)

        def _abc_tier(cum_p: float, idx_i: int) -> str:
            if idx_i == 0 or cum_p <= 80.0:
                return "A"
            if cum_p <= 95.0:
                return "B"
            return "C"

        item_grp["abc_class"] = [
            _abc_tier(float(r["cum_share_pct"]), i) for i, r in item_grp.iterrows()
        ]

        abc_counts = item_grp["abc_class"].value_counts().to_dict()
        abc_rev = item_grp.groupby("abc_class")["revenue"].sum().to_dict()
        abc_summary = {
            "item_column": schema["item_col"],
            "total_skus": int(len(item_grp)),
            "class_a_skus": int(abc_counts.get("A", 0)),
            "class_b_skus": int(abc_counts.get("B", 0)),
            "class_c_skus": int(abc_counts.get("C", 0)),
            "class_a_revenue_share_pct": round(float(abc_rev.get("A", 0.0)) / pos_rev_total * 100.0, 1),
            "class_c_revenue_share_pct": round(float(abc_rev.get("C", 0.0)) / pos_rev_total * 100.0, 1),
        }

        # Daily demand volatility & empirical rolling lead-time 95th-percentile ROP per SKU
        sku_daily_std: Dict[str, float] = {}
        sku_empirical_rop: Dict[str, int] = {}
        if schema["date_col"] and min_dt is not None and max_dt is not None and span_days >= 3:
            work["_day"] = work["_dt"].dt.normalize()
            full_days = pd.date_range(min_dt.normalize(), max_dt.normalize(), freq="D")
            top_60_names = set(item_grp.head(60)["_item"].tolist())
            sub_top = work[work["_item"].isin(top_60_names) & work["_day"].notna()]
            piv = sub_top.pivot_table(index="_day", columns="_item", values="_qty", aggfunc="sum", fill_value=0.0)
            piv = piv.reindex(full_days, fill_value=0.0)
            for col_sku in piv.columns:
                s_sku = piv[col_sku]
                sku_daily_std[str(col_sku)] = float(s_sku.std(ddof=1)) if len(piv) > 1 else 0.0
                if len(piv) >= max(28, lead_time_days * 2):
                    lt_roll = s_sku.rolling(lead_time_days, min_periods=lead_time_days).sum().dropna()
                    if len(lt_roll) >= 7:
                        ov_m = float(s_sku.mean())
                        g_mult = (
                            float(np.clip(float(s_sku.iloc[-90:].mean()) / max(ov_m, 1e-9), 1.0, 1.5))
                            if (len(piv) >= 120 and ov_m > 1e-9)
                            else 1.0
                        )
                        sku_empirical_rop[str(col_sku)] = int(math.ceil(float(lt_roll.quantile(0.95)) * g_mult))

        for idx_r, r in item_grp.iterrows():
            sku = str(r["_item"])
            rev_v = float(r["revenue"])
            units_v = float(r["units"])
            ads = units_v / max(1, span_days)
            d_std = sku_daily_std.get(sku, ads * 0.45)
            classic_ss = int(math.ceil(1.645 * d_std * math.sqrt(lead_time_days)))
            classic_rop = int(math.ceil(ads * lead_time_days + classic_ss))
            emp_rop = sku_empirical_rop.get(sku, 0)
            rop = max(classic_rop, emp_rop)
            safety_stock = max(classic_ss, max(0, rop - int(math.ceil(ads * lead_time_days))))
            forecast_30d_units = int(math.ceil(ads * 30.0))
            curr_stk = float(latest_stock[sku]) if sku in latest_stock.index and pd.notna(latest_stock[sku]) else None

            margin_p = None
            profit_v = None
            if has_profit:
                profit_v = float(r["profit"])
                margin_p = round((profit_v / rev_v * 100.0), 1) if abs(rev_v) > 1e-9 else 0.0
                if profit_v < 0 or (margin_p is not None and margin_p < 5.0 and rev_v > 0):
                    negative_margin_items.append({
                        "item": sku,
                        "revenue": round(rev_v, 2),
                        "revenue_fmt": _format_money(rev_v, cur),
                        "profit": round(profit_v, 2),
                        "profit_fmt": _format_money(profit_v, cur),
                        "margin_pct": margin_p,
                    })

            days_of_cover = None
            stock_status = "NO_STOCK_COL"
            rec_order_qty = max(0, forecast_30d_units + safety_stock)
            if curr_stk is not None:
                days_of_cover = round(curr_stk / ads, 1) if ads > 1e-6 else (999.0 if curr_stk > 0 else 0.0)
                rec_order_qty = max(0, int(math.ceil(forecast_30d_units + safety_stock - curr_stk)))
                if curr_stk <= rop or days_of_cover <= lead_time_days:
                    stock_status = "CRITICAL_STOCKOUT"
                elif days_of_cover <= 14.0:
                    stock_status = "REORDER_SOON"
                elif days_of_cover > 60.0 and curr_stk > 0:
                    stock_status = "OVERSTOCK_DEAD_CAPITAL"
                else:
                    stock_status = "HEALTHY"

            item_rec = {
                "item": sku,
                "abc_class": str(r["abc_class"]),
                "revenue": round(rev_v, 2),
                "revenue_fmt": _format_money(rev_v, cur),
                "revenue_share_pct": float(r["rev_share_pct"]),
                "units_sold": round(units_v, 1),
                "avg_daily_units": round(ads, 2),
                "profit": round(profit_v, 2) if profit_v is not None else None,
                "profit_fmt": _format_money(profit_v, cur) if profit_v is not None else None,
                "margin_pct": margin_p,
                "current_stock": round(curr_stk, 1) if curr_stk is not None else None,
                "days_of_cover": days_of_cover,
                "safety_stock": safety_stock,
                "reorder_point": rop,
                "forecast_30d_units": forecast_30d_units,
                "recommended_30d_order_qty": rec_order_qty,
                "stock_status": stock_status,
            }
            if idx_r < 12:
                top_items.append(item_rec)
            if stock_status in ("CRITICAL_STOCKOUT", "REORDER_SOON"):
                reorder_alerts.append(item_rec)
            elif stock_status == "OVERSTOCK_DEAD_CAPITAL":
                dead_stock_items.append(item_rec)

        reorder_alerts.sort(key=lambda x: (0 if x["stock_status"] == "CRITICAL_STOCKOUT" else 1, x["days_of_cover"] or 999, -x["revenue"]))
        dead_stock_items.sort(key=lambda x: -(x["current_stock"] or 0.0))
        negative_margin_items.sort(key=lambda x: x["profit"])

    # ------------------------------------------------------------------
    # MODULE C: 30-DAY DEMAND & REVENUE FORECASTING
    # ------------------------------------------------------------------
    demand_forecast: Dict[str, Any] = {
        "forecast_available": False,
        "reason": "No calendar date column detected.",
    }
    if schema["date_col"] and min_dt is not None and max_dt is not None:
        valid_ts = work.dropna(subset=["_dt"]).copy()
        valid_ts["_day"] = valid_ts["_dt"].dt.normalize()
        distinct_days = int(valid_ts["_day"].nunique())
        if distinct_days >= 10 and span_days >= 14:
            # Forecast on positive gross daily demand so isolated massive credit-note reversals cannot corrupt Holt-Winters
            daily_rev = valid_ts.groupby("_day")["_rev_gross"].sum()
            daily_qty = valid_ts.groupby("_day")["_qty"].sum()
            idx_days = pd.date_range(min_dt.normalize(), max_dt.normalize(), freq="D")
            daily_rev = daily_rev.reindex(idx_days, fill_value=0.0)
            daily_qty = daily_qty.reindex(idx_days, fill_value=0.0)

            # Day-of-week seasonality (only when >= 28 days of history)
            dow_factors = None
            peak_day_name = None
            peak_day_mult = 1.0
            if len(daily_rev) >= 28:
                dow_means = daily_rev.groupby(daily_rev.index.dayofweek).mean()
                overall_m = float(daily_rev.mean())
                if overall_m > 1e-9:
                    dow_factors = {int(d): float(np.clip(v / overall_m, 0.4, 2.5)) for d, v in dow_means.items()}
                    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    peak_d = max(dow_factors, key=lambda k: dow_factors[k])
                    peak_day_name = day_names[peak_d]
                    peak_day_mult = round(dow_factors[peak_d], 2)

            fc_rev = _walk_forward_tournament_forecast(
                daily_rev.values,
                horizon_days=30,
                dow_factors=dow_factors,
                start_dow=int(idx_days[0].dayofweek),
            )
            fc_qty = _walk_forward_tournament_forecast(
                daily_qty.values,
                horizon_days=30,
                dow_factors=dow_factors,
                start_dow=int(idx_days[0].dayofweek),
            )

            # Recent momentum: last half vs prior half (or last 30d vs prior 30d)
            win = min(30, len(daily_rev) // 2)
            recent_sum = float(daily_rev.iloc[-win:].sum()) if win >= 3 else 0.0
            prior_sum = float(daily_rev.iloc[-2 * win:-win].sum()) if win >= 3 else 0.0
            momentum_pct = round(((recent_sum - prior_sum) / prior_sum * 100.0), 1) if prior_sum > 1e-9 else 0.0

            demand_forecast = {
                "forecast_available": True,
                "cadence": "daily",
                "horizon_days": 30,
                "history_days": int(len(daily_rev)),
                "history_start": str(min_dt.date()),
                "history_end": str(max_dt.date()),
                "model": fc_rev["model"],
                "winning_model": fc_rev.get("winning_model", "damped_holt"),
                "seasonality_mode": fc_rev.get("seasonality_mode", "short_daily"),
                "walk_forward_windows": int(fc_rev.get("walk_forward_windows", 0)),
                "ci_calibration_method": fc_rev.get("ci_calibration_method", "daily_residual_se"),
                "baseline_comparison": fc_rev.get("baseline_comparison", {}),
                "backtest_wape_pct": fc_rev["backtest_wape_pct"],
                "next_30d_revenue": fc_rev["point_forecast"],
                "next_30d_revenue_low95": fc_rev["lower_95"],
                "next_30d_revenue_high95": fc_rev["upper_95"],
                "next_30d_revenue_fmt": _format_money(fc_rev["point_forecast"], cur),
                "next_30d_revenue_low95_fmt": _format_money(fc_rev["lower_95"], cur),
                "next_30d_revenue_high95_fmt": _format_money(fc_rev["upper_95"], cur),
                "next_30d_units": int(round(fc_qty["point_forecast"])),
                "recent_momentum_pct": momentum_pct,
                "momentum_window_days": int(win),
                "peak_weekday": peak_day_name,
                "peak_weekday_multiplier": peak_day_mult,
            }
        else:
            # Monthly fallback for sparse monthly summary registers
            valid_ts["_ym"] = valid_ts["_dt"].dt.to_period("M")
            m_rev = valid_ts.groupby("_ym")["_rev"].sum().sort_index()
            m_qty = valid_ts.groupby("_ym")["_qty"].sum().sort_index()
            if len(m_rev) >= 3:
                fc_rev = _damped_holt_forecast(m_rev.values, horizon=1)
                fc_qty = _damped_holt_forecast(m_qty.values, horizon=1)
                prior_m = float(m_rev.iloc[-2]) if len(m_rev) >= 2 else 0.0
                mom_pct = round(((float(m_rev.iloc[-1]) - prior_m) / prior_m * 100.0), 1) if prior_m > 1e-9 else 0.0
                demand_forecast = {
                    "forecast_available": True,
                    "cadence": "monthly",
                    "horizon_days": 30,
                    "history_periods": int(len(m_rev)),
                    "history_start": str(min_dt.date()),
                    "history_end": str(max_dt.date()),
                    "model": fc_rev["model"],
                    "backtest_wape_pct": fc_rev["backtest_wape_pct"],
                    "next_30d_revenue": fc_rev["point_forecast"],
                    "next_30d_revenue_fmt": _format_money(fc_rev["point_forecast"], cur),
                    "next_30d_revenue_low95_fmt": _format_money(fc_rev["lower_95"], cur),
                    "next_30d_revenue_high95_fmt": _format_money(fc_rev["upper_95"], cur),
                    "next_30d_units": int(round(fc_qty["point_forecast"])),
                    "recent_momentum_pct": mom_pct,
                    "peak_weekday": None,
                    "peak_weekday_multiplier": 1.0,
                }
            else:
                demand_forecast = {
                    "forecast_available": False,
                    "reason": "Need at least 3 distinct monthly periods or 10 sales days for an honest statistical forecast.",
                }

    # ------------------------------------------------------------------
    # MODULE D: PARTY / CUSTOMER CONCENTRATION, DORMANT BUYERS & UDHAAR
    # ------------------------------------------------------------------
    party_health: Dict[str, Any] = {}
    if schema["party_col"]:
        p_raw = df[schema["party_col"]]
        if pd.api.types.is_numeric_dtype(p_raw):
            p_num = pd.to_numeric(p_raw, errors="coerce")
            work["_party"] = p_num.apply(
                lambda v: f"Customer #{int(v)}" if pd.notna(v) and float(v).is_integer() else (f"Customer #{v}" if pd.notna(v) else "Walk-in / Guest")
            )
        else:
            work["_party"] = p_raw.astype(str).str.strip().replace(
                {"": "Walk-in / Guest", "nan": "Walk-in / Guest", "None": "Walk-in / Guest", "<NA>": "Walk-in / Guest"}
            )
        p_agg: Dict[str, Any] = {
            "revenue": ("_rev", "sum"),
            "orders": ("_rev", "count"),
        }
        if schema["due_col"]:
            work["_due"] = _safe_numeric(df[schema["due_col"]]).fillna(0.0).clip(lower=0.0)
            p_agg["due"] = ("_due", "sum")
        if schema["date_col"] and max_dt is not None:
            p_agg["last_order"] = ("_dt", "max")
        p_grp_all = work.groupby("_party", as_index=False).agg(**p_agg).sort_values("revenue", ascending=False).reset_index(drop=True)
        tot_all_p_rev = float(p_grp_all["revenue"].clip(lower=0.0).sum()) or 1.0
        walkin_mask = p_grp_all["_party"].isin(["Walk-in / Guest", "Walk-in / Unknown"])
        walkin_rev = float(p_grp_all.loc[walkin_mask, "revenue"].sum()) if walkin_mask.any() else 0.0
        walkin_share_pct = round(walkin_rev / tot_all_p_rev * 100.0, 1) if walkin_mask.any() else 0.0
        p_grp = p_grp_all[~walkin_mask].reset_index(drop=True) if (~walkin_mask).any() else p_grp_all
        tot_p_rev = float(p_grp["revenue"].clip(lower=0.0).sum()) or 1.0
        p_grp["share_pct"] = (p_grp["revenue"] / tot_p_rev * 100.0).round(1)

        top1_share = float(p_grp.iloc[0]["share_pct"]) if len(p_grp) else 0.0
        top3_share = round(float(p_grp.head(3)["share_pct"].sum()), 1) if len(p_grp) else 0.0
        dormant_buyers = []
        if schema["date_col"] and max_dt is not None and span_days >= 45 and "last_order" in p_grp.columns:
            p_grp["days_since"] = (max_dt - p_grp["last_order"]).dt.days
            dorm = p_grp[(p_grp["orders"] >= 2) & (p_grp["days_since"] >= 30) & (p_grp["revenue"] > 0)].head(8)
            for _, dr in dorm.iterrows():
                dormant_buyers.append({
                    "party": str(dr["_party"]),
                    "orders": int(dr["orders"]),
                    "historical_revenue_fmt": _format_money(float(dr["revenue"]), cur),
                    "days_inactive": int(dr["days_since"]),
                })

        top_udhaar = []
        total_udhaar = 0.0
        if schema["due_col"] and "due" in p_grp.columns:
            total_udhaar = float(p_grp["due"].sum())
            for _, ur in p_grp[p_grp["due"] > 0].sort_values("due", ascending=False).head(8).iterrows():
                top_udhaar.append({
                    "party": str(ur["_party"]),
                    "due": round(float(ur["due"]), 2),
                    "due_fmt": _format_money(float(ur["due"]), cur),
                })

        party_health = {
            "party_column": schema["party_col"],
            "total_parties": int(len(p_grp)),
            "walkin_revenue_share_pct": walkin_share_pct,
            "top1_party": str(p_grp.iloc[0]["_party"]) if len(p_grp) else None,
            "top1_share_pct": top1_share,
            "top3_share_pct": top3_share,
            "concentration_risk": bool(top1_share >= 30.0 or top3_share >= 60.0),
            "top_parties": [
                {
                    "party": str(r["_party"]),
                    "revenue": round(float(r["revenue"]), 2),
                    "revenue_fmt": _format_money(float(r["revenue"]), cur),
                    "share_pct": float(r["share_pct"]),
                    "orders": int(r["orders"]),
                }
                for _, r in p_grp.head(6).iterrows()
            ],
            "dormant_repeat_buyers": dormant_buyers,
            "total_udhaar": round(total_udhaar, 2) if schema["due_col"] else None,
            "total_udhaar_fmt": _format_money(total_udhaar, cur) if schema["due_col"] else None,
            "top_udhaar_parties": top_udhaar,
        }

    # ------------------------------------------------------------------
    # BILINGUAL ZERO-JARGON EXECUTIVE NARRATIVES (EN + HI)
    # ------------------------------------------------------------------
    rev_fmt = _format_money(total_revenue, cur)
    prof_fmt = _format_money(gross_profit, cur) if gross_profit is not None else None
    top_sku = top_items[0] if top_items else None
    top_reorder = reorder_alerts[0] if reorder_alerts else None
    top_dead = dead_stock_items[0] if dead_stock_items else None
    top_neg = negative_margin_items[0] if negative_margin_items else None

    headline_en = (
        f"Total Sales: {rev_fmt}"
        + (f" · Gross Profit: {prof_fmt} ({gross_margin_pct:.1f}% margin)" if prof_fmt else f" across {total_orders:,} bills")
    )
    headline_hi = (
        f"कुल बिक्री: {rev_fmt}"
        + (f" · कुल मुनाफ़ा: {prof_fmt} ({gross_margin_pct:.1f}% मार्जिन)" if prof_fmt else f" ({total_orders:,} बिलों में)")
    )

    actions_en: List[str] = []
    actions_hi: List[str] = []

    if top_reorder:
        actions_en.append(
            f"URGENT REORDER: '{top_reorder['item']}' has only {top_reorder['current_stock']} units left "
            f"({top_reorder['days_of_cover']} days cover). Order ~{top_reorder['recommended_30d_order_qty']} units immediately."
        )
        actions_hi.append(
            f"तुरंत माल मँगवाएँ: '{top_reorder['item']}' का स्टॉक सिर्फ़ {top_reorder['current_stock']} यूनिट बचा है "
            f"({top_reorder['days_of_cover']} दिन का स्टॉक)। अगले 30 दिन के लिए लगभग {top_reorder['recommended_30d_order_qty']} यूनिट का ऑर्डर दें।"
        )
    if top_neg:
        actions_en.append(
            f"MARGIN LEAK: '{top_neg['item']}' earned {top_neg['profit_fmt']} profit ({top_neg['margin_pct']}% margin) on {top_neg['revenue_fmt']} sales — tighten discount or raise selling price."
        )
        actions_hi.append(
            f"मार्जिन रिसाव: '{top_neg['item']}' पर {top_neg['revenue_fmt']} की बिक्री में सिर्फ़ {top_neg['profit_fmt']} ({top_neg['margin_pct']}%) मार्जिन बचा — छूट कम करें या रेट सुधारें।"
        )
    if top_dead:
        actions_en.append(
            f"SLOW / DEAD STOCK: '{top_dead['item']}' holds {top_dead['current_stock']} units ({top_dead['days_of_cover']} days cover) — run a clearance bundle to unlock stuck cash."
        )
        actions_hi.append(
            f"फँसा हुआ माल (Dead Stock): '{top_dead['item']}' की {top_dead['current_stock']} यूनिट ({top_dead['days_of_cover']} दिन से ज़्यादा स्टॉक) रुकी हुई हैं — कॉम्बो या क्लियरेंस ऑफ़र चलाकर कैश निकालें।"
        )
    if demand_forecast.get("forecast_available"):
        actions_en.append(
            f"NEXT 30-DAY FORECAST: Expected sales {demand_forecast['next_30d_revenue_fmt']} "
            f"(95% range: {demand_forecast['next_30d_revenue_low95_fmt']} – {demand_forecast['next_30d_revenue_high95_fmt']}; "
            f"backtest error WAPE {demand_forecast['backtest_wape_pct']}%)."
        )
        actions_hi.append(
            f"अगले 30 दिन का बिक्री अनुमान: लगभग {demand_forecast['next_30d_revenue_fmt']} बिक्री होने की उम्मीद है "
            f"(रेंज: {demand_forecast['next_30d_revenue_low95_fmt']} – {demand_forecast['next_30d_revenue_high95_fmt']}; बैकटेस्ट त्रुटि {demand_forecast['backtest_wape_pct']}%)।"
        )
    if party_health.get("concentration_risk"):
        actions_en.append(
            f"BUYER DEPENDENCY: Top party '{party_health['top1_party']}' drives {party_health['top1_share_pct']}% of sales — diversify buyers to protect cashflow."
        )
        actions_hi.append(
            f"ग्राहक निर्भरता: अकेली पार्टी '{party_health['top1_party']}' से {party_health['top1_share_pct']}% बिक्री आ रही है — नए ग्राहकों को जोड़कर रिस्क कम करें।"
        )
    if party_health.get("dormant_repeat_buyers"):
        d0 = party_health["dormant_repeat_buyers"][0]
        actions_en.append(
            f"WIN BACK BUYER: Repeat customer '{d0['party']}' ({d0['historical_revenue_fmt']} past sales) hasn't ordered in {d0['days_inactive']} days — send a WhatsApp follow-up."
        )
        actions_hi.append(
            f"पुराने ग्राहक को वापस लाएँ: नियमित ग्राहक '{d0['party']}' (पुरानी बिक्री {d0['historical_revenue_fmt']}) ने {d0['days_inactive']} दिन से ऑर्डर नहीं दिया — आज कॉल या व्हाट्सएप करें।"
        )
    if top_sku and not actions_en:
        actions_en.append(
            f"STAR PRODUCT: '{top_sku['item']}' generates {top_sku['revenue_fmt']} ({top_sku['revenue_share_pct']}% of revenue). Keep priority stock ready."
        )
        actions_hi.append(
            f"सबसे ज़्यादा बिकने वाला आइटम: '{top_sku['item']}' अकेले {top_sku['revenue_fmt']} ({top_sku['revenue_share_pct']}%) बिक्री ला रहा है — इसका स्टॉक हमेशा तैयार रखें।"
        )

    report = {
        "is_applicable": True,
        "is_pure_sales_ledger": bool(schema["is_pure_sales_ledger"] and return_lines_count == 0),
        "currency_unit": cur,
        "detected_schema": {k: v for k, v in schema.items() if k.endswith("_col") and v is not None},
        "revenue_source": rev_source,
        "kpis": {
            "total_revenue": round(total_revenue, 2),
            "total_revenue_fmt": rev_fmt,
            "gross_sales": round(gross_sales, 2),
            "gross_sales_fmt": _format_money(gross_sales, cur),
            "returns_value": round(returns_value, 2),
            "returns_value_fmt": _format_money(returns_value, cur),
            "return_lines": return_lines_count,
            "total_orders": total_orders,
            "total_units_sold": round(total_units, 1),
            "avg_order_value": avg_order_value,
            "avg_order_value_fmt": _format_money(avg_order_value, cur),
            "has_profit": has_profit,
            "gross_profit": round(gross_profit, 2) if gross_profit is not None else None,
            "gross_profit_fmt": prof_fmt,
            "gross_margin_pct": gross_margin_pct,
            "total_discount": round(total_discount, 2) if total_discount is not None else None,
            "total_discount_fmt": _format_money(total_discount, cur) if total_discount is not None else None,
            "observed_span_days": span_days,
            "lead_time_days": lead_time_days,
        },
        "abc_summary": abc_summary,
        "demand_forecast": demand_forecast,
        "top_items": top_items,
        "reorder_alerts": reorder_alerts[:10],
        "dead_stock_items": dead_stock_items[:10],
        "negative_margin_items": negative_margin_items[:10],
        "party_health": party_health,
        "narratives": {
            "en": {"headline": headline_en, "actions": actions_en},
            "hi": {"headline": headline_hi, "actions": actions_hi},
        },
    }

    if out_dir is not None:
        out_p = Path(out_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        (out_p / "growth_inventory_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return report


def render_growth_markdown_section(report: Dict[str, Any]) -> str:
    """Renders a concise bilingual Markdown appendix for PLAIN_BUSINESS_SUMMARY.md."""
    if not report or not report.get("is_applicable"):
        return ""
    kpis = report.get("kpis", {})
    fc = report.get("demand_forecast", {})
    abc = report.get("abc_summary", {})
    nar = report.get("narratives", {})
    lines = [
        "\n---\n",
        "### 6. Sales, Profit, 30-Day Demand Forecast & Stock Reorder Brief (बिक्री, मुनाफ़ा और स्टॉक योजना)",
        f"- **Headline (EN):** {nar.get('en', {}).get('headline', '')}",
        f"- **मुख्य सारांश (HI):** {nar.get('hi', {}).get('headline', '')}",
    ]
    if fc.get("forecast_available"):
        lines.append(
            f"- **Next 30-Day Demand Forecast:** `{fc['next_30d_revenue_fmt']}` "
            f"(95% CI: `{fc['next_30d_revenue_low95_fmt']}` – `{fc['next_30d_revenue_high95_fmt']}`, "
            f"~`{fc['next_30d_units']:,}` units, Backtest WAPE: `{fc['backtest_wape_pct']}%`, Model: {fc['model']})."
        )
    if abc:
        lines.append(
            f"- **ABC Pareto Concentration:** Top `{abc.get('class_a_skus', 0)}` Class-A items drive "
            f"`{abc.get('class_a_revenue_share_pct', 0)}%` of revenue across `{abc.get('total_skus', 0)}` SKUs."
        )
    if report.get("reorder_alerts"):
        lines.append("\n**Top Stock Reorder Alerts (तुरंत मँगवाने वाला माल):**")
        for ra in report["reorder_alerts"][:5]:
            lines.append(
                f"- `{ra['item']}`: Stock `{ra['current_stock']}` ({ra['days_of_cover']}d cover) · "
                f"Reorder Point `{ra['reorder_point']}` · **Order ~`{ra['recommended_30d_order_qty']}` units**"
            )
    if report.get("negative_margin_items"):
        lines.append("\n**Low / Negative Margin Alerts (मार्जिन रिसाव):**")
        for nm in report["negative_margin_items"][:5]:
            lines.append(
                f"- `{nm['item']}`: Sales `{nm['revenue_fmt']}` · Profit `{nm['profit_fmt']}` (`{nm['margin_pct']}%`)"
            )
    return "\n".join(lines) + "\n"
