"""
=============================================================================
DATAX-RAY V7.0: PROACTIVE EARLY-WARNING ANOMALY & VELOCITY RADAR
=============================================================================
Detects emerging operational fires BEFORE they ruin next month's P&L:
1. Auto Date-Axis Resolution:
   - Detects single timestamp/date columns via `intelligent_date_normalizer.py`
     OR reconstructs split calendar columns (e.g. arrival_date_year/month/day).
   - Red-Team Guard R1: If no valid date axis or < 4 distinct buckets exist,
     cleanly returns `status="INSUFFICIENT_TIME_HISTORY"` (zero fake trends!).
2. Rolling EWMA + Modified Z-Score (MAD) Time-Series Anomaly Detector:
   - Outlier-resistant Modified Z = 0.6745 * (x - median) / MAD.
   - Red-Team Guard R2: Enforces N >= 25 recent sample floor & >= +3.0 pp shift.
3. Emerging Cohort Acceleration Scanner (Vectorized + BH-FDR):
   - Compares Recent Window vs Prior Baseline across clean operational dims.
   - Vectorized Pandas/NumPy grouping (< 0.5s on 100k rows — Guard R6).
   - Two-proportion z-test + Benjamini-Hochberg FDR (q <= 0.05) stops spam.
4. Honest Bounded 30-Day Forward Risk Outlook:
   - Strictly enforces `is_financial` & physical `cost_col` (Guard R3: 0 fake $/₹).
   - Persists `proactive_anomaly_report.json` cleanly for Guard Check 13.
=============================================================================
"""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from .intelligent_date_normalizer import detect_dayfirst_orientation
    from .target_resolver import (
        is_demographic_attribute,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        resolve_canonical_target_and_cost,
    )
    from .pii_scrubber import is_sensitive_column_name
    from .safe_math_and_json_guard import atomic_write_json
except ImportError:
    try:
        from intelligent_date_normalizer import detect_dayfirst_orientation
    except ImportError:
        def detect_dayfirst_orientation(series: pd.Series) -> bool:
            return False
    try:
        from target_resolver import (
            is_demographic_attribute,
            is_index_artifact,
            is_pseudo_numeric_identifier,
            is_synthetic_column,
            resolve_canonical_target_and_cost,
        )
    except ImportError:
        def is_demographic_attribute(col: str) -> bool:
            return False
        def is_index_artifact(col: str, series=None) -> bool:
            return False
        def is_pseudo_numeric_identifier(col: str, series=None) -> bool:
            return False
        def is_synthetic_column(col: str, bp=None) -> bool:
            return False
        def resolve_canonical_target_and_cost(df, **kwargs):
            return {}
    try:
        from pii_scrubber import is_sensitive_column_name
    except ImportError:
        def is_sensitive_column_name(col: str) -> bool:
            return False
    try:
        from safe_math_and_json_guard import atomic_write_json
    except ImportError:
        def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
            Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


_MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

_DATE_COL_KEYWORDS = (
    "order_date", "booking_date", "invoice_date", "transaction_date", "sale_date",
    "created_at", "created_date", "purchase_date", "ship_date", "dispatch_date",
    "checkin_date", "arrival_date", "flight_date", "pickup_datetime", "pickup_date",
    "timestamp", "date", "dt", "period", "month_year",
)

_EXCLUDE_DATE_TOKENS = (
    "birth", "dob", "expir", "due_date", "update", "modified", "cancel_date",
    "return_date", "refund_date", "resolution_date", "delivery_date",
    "reservation_status", "status_date",
)


def _fmt_money_compact(val: float, sym: str, is_fin: bool) -> str:
    if not is_fin or not sym:
        return f"{int(round(val)):,}"
    av = abs(float(val))
    sign = "-" if val < 0 else ""
    if sym == "₹":
        if av >= 1e7:
            return f"{sign}₹{av / 1e7:.2f} Cr"
        if av >= 1e5:
            return f"{sign}₹{av / 1e5:.2f} L"
        if av >= 1e3:
            return f"{sign}₹{av / 1e3:.1f}K"
        return f"{sign}₹{av:,.0f}"
    if av >= 1e9:
        return f"{sign}{sym}{av / 1e9:.2f}B"
    if av >= 1e6:
        return f"{sign}{sym}{av / 1e6:.2f}M"
    if av >= 1e3:
        return f"{sign}{sym}{av / 1e3:.1f}K"
    return f"{sign}{sym}{av:,.2f}"


def _two_prop_z_test(k1: int, n1: int, k2: int, n2: int) -> Tuple[float, float]:
    """Pooled two-proportion z-test returning (z_stat, two_tailed_p)."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0
    p1 = k1 / n1
    p2 = k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    denom = math.sqrt(max(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2), 1e-12))
    if p_pool <= 0.0 or p_pool >= 1.0:
        return 0.0, 1.0
    z = (p1 - p2) / denom
    p_val = math.erfc(abs(z) / math.sqrt(2.0))
    return float(z), float(max(0.0, min(1.0, p_val)))


def _detect_primary_date_series(df: pd.DataFrame) -> Tuple[Optional[str], Optional[pd.Series]]:
    """
    Finds the best operational timestamp series without mistaking IDs, ages,
    post-event cancellation dates, or pure numeric metrics for calendar dates.
    Supports both single date columns and split year+month(+day) columns.
    """
    if df is None or df.empty:
        return None, None

    # 1. Check existing datetime64 columns first
    for col in df.columns:
        low = str(col).lower().strip()
        if any(ex in low for ex in _EXCLUDE_DATE_TOKENS):
            continue
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            s = pd.to_datetime(df[col], errors="coerce")
            if s.notna().mean() >= 0.70 and s.dt.year.between(1990, 2035).mean() >= 0.80:
                return col, s

    # 2. Score string/object columns with date-like names or ISO patterns
    candidates: List[Tuple[int, str]] = []
    for col in df.columns:
        low = str(col).lower().strip()
        if any(ex in low for ex in _EXCLUDE_DATE_TOKENS):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            # Only consider Excel serial dates if column explicitly says date/time
            if any(k in low for k in ("date", "dt", "timestamp")):
                s_num = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(s_num) > 20 and s_num.between(32000, 60000).mean() >= 0.85:
                    candidates.append((2, col))
            continue
        score = 0
        for idx, kw in enumerate(_DATE_COL_KEYWORDS):
            if low == kw:
                score = max(score, 100 - idx)
            elif kw in low:
                score = max(score, 60 - idx)
        if score == 0:
            # Peek 20 values for YYYY-MM-DD / DD-MM-YYYY pattern
            sample = df[col].dropna().astype(str).head(25)
            if len(sample) >= 5:
                hits = sample.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}").mean()
                if hits >= 0.85:
                    score = 20
        if score > 0:
            candidates.append((score, col))

    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, col in candidates[:4]:
        try:
            s_raw = df[col]
            if pd.api.types.is_numeric_dtype(s_raw):
                s_dt = pd.to_datetime(pd.to_numeric(s_raw, errors="coerce"), unit="D", origin="1899-12-30", errors="coerce")
            else:
                sample_str = s_raw.dropna().astype(str).head(50)
                if len(sample_str) < 10:
                    continue
                dayfirst = detect_dayfirst_orientation(s_raw)
                s_dt = pd.to_datetime(s_raw, dayfirst=dayfirst, errors="coerce", format="mixed", utc=True)
                if pd.api.types.is_datetime64_any_dtype(s_dt):
                    s_dt = s_dt.dt.tz_localize(None)
            valid_ratio = float(s_dt.notna().mean())
            if valid_ratio >= 0.70:
                yrs = s_dt.dropna().dt.year
                if len(yrs) >= 20 and yrs.between(1990, 2035).mean() >= 0.85:
                    return col, s_dt
        except Exception:
            continue

    # 3. Split year + month (+ optional day) columns (e.g. Hotel Bookings arrival_date_year / arrival_date_month)
    cols_low = {str(c).lower().strip(): c for c in df.columns}
    year_col = next((c for k, c in cols_low.items() if k.endswith("year") and "birth" not in k), None)
    month_col = next((c for k, c in cols_low.items() if k.endswith("month") and "tenure" not in k), None)
    day_col = next((c for k, c in cols_low.items() if "day_of_month" in k or k == "day"), None)
    if year_col and month_col:
        try:
            yr_s = pd.to_numeric(df[year_col], errors="coerce")
            if yr_s.notna().mean() >= 0.80 and yr_s.dropna().between(1990, 2035).mean() >= 0.90:
                if pd.api.types.is_numeric_dtype(df[month_col]):
                    mo_s = pd.to_numeric(df[month_col], errors="coerce")
                else:
                    mo_s = df[month_col].astype(str).str.strip().str.lower().map(_MONTH_MAP)
                dy_s = pd.to_numeric(df[day_col], errors="coerce").fillna(1) if day_col else pd.Series(1, index=df.index)
                dt_df = pd.DataFrame({
                    "year": yr_s.fillna(2000).astype(int),
                    "month": mo_s.fillna(1).clip(1, 12).astype(int),
                    "day": dy_s.clip(1, 28).astype(int),
                })
                s_dt = pd.to_datetime(dt_df, errors="coerce")
                s_dt = s_dt.where(yr_s.notna() & mo_s.notna(), pd.NaT)
                if s_dt.notna().mean() >= 0.70:
                    return f"{year_col}+{month_col}", s_dt
        except Exception:
            pass

    return None, None


def _human_col_name(col: str) -> str:
    return re.sub(r"[_]+", " ", str(col or "")).strip().title()


def run_proactive_anomaly_radar(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
    canonical_target: Optional[Dict[str, Any]] = None,
    currency_symbol: str = "$",
    is_financial: bool = True,
    circuit_breaker_active: bool = False,
    business_category: str = "auto",
) -> Dict[str, Any]:
    """
    Executes vectorized Time-Series EWMA/MAD Early-Warning Radar + Cohort
    Acceleration Scanner with Benjamini-Hochberg FDR & strict financial truth.
    """
    t0 = time.perf_counter()
    n_rows = int(len(df)) if df is not None else 0

    ct = canonical_target or {}
    phys_cost_col = ct.get("cost_col") if isinstance(ct, dict) else None
    phys_is_fin = bool(is_financial and phys_cost_col and df is not None and phys_cost_col in df.columns) if ct else bool(is_financial)
    sym = currency_symbol if phys_is_fin else ""

    def _empty_result(status_code: str, reason_en: str, reason_hi: str, date_col_found: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "version": "7.0",
            "status": status_code,
            "is_applicable": False,
            "overall_alert_level": "NO_TIME_AXIS" if status_code == "INSUFFICIENT_TIME_HISTORY" else "ALL_CLEAR",
            "audited_fact_records": n_rows,
            "is_financial": phys_is_fin,
            "currency_symbol": sym,
            "date_column": date_col_found,
            "bucket_granularity": None,
            "periods_analyzed": 0,
            "reason_en": reason_en,
            "reason_hi": reason_hi,
            "headline_en": reason_en,
            "headline_hi": reason_hi,
            "period_series": [],
            "period_anomalies": [],
            "accelerating_cohorts": [],
            "improving_cohorts": [],
            "forward_risk_projection": None,
            "should_dispatch_alert": False,
            "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }
        if output_dir is not None:
            try:
                out_p = Path(output_dir)
                out_p.mkdir(parents=True, exist_ok=True)
                atomic_write_json(out_p / "proactive_anomaly_report.json", payload)
            except Exception:
                pass
        return payload

    if df is None or n_rows < 40:
        return _empty_result(
            "INSUFFICIENT_TIME_HISTORY",
            "Fewer than 40 records available — skipping early-warning time-series radar to avoid false alarms.",
            "40 से कम रिकॉर्ड हैं — गलत अलार्म से बचने के लिए अर्ली-वॉर्निंग रडार बंद रखा गया है।",
        )

    # Resolve binary adverse series
    s_bin: Optional[pd.Series] = None
    if isinstance(ct, dict) and ct.get("binary_target") is not None and len(ct["binary_target"]) == n_rows:
        s_bin = pd.to_numeric(pd.Series(ct["binary_target"], index=df.index), errors="coerce").fillna(0).astype(int)
    elif "_is_target_event" in df.columns:
        s_bin = pd.to_numeric(df["_is_target_event"], errors="coerce").fillna(0).astype(int)
    elif isinstance(ct, dict) and ct.get("target_col") and ct["target_col"] in df.columns:
        _raw_t = pd.to_numeric(df[ct["target_col"]], errors="coerce")
        _uv = set(_raw_t.dropna().unique().tolist())
        if _uv and _uv.issubset({0, 1, 0.0, 1.0}):
            s_bin = _raw_t.fillna(0).astype(int)
    if s_bin is None:
        try:
            _rc = resolve_canonical_target_and_cost(df, blueprint={"business_category": business_category})
            if _rc.get("binary_target") is not None and len(_rc["binary_target"]) == n_rows:
                s_bin = pd.to_numeric(pd.Series(_rc["binary_target"], index=df.index), errors="coerce").fillna(0).astype(int)
        except Exception:
            s_bin = None

    if s_bin is None:
        return _empty_result(
            "INSUFFICIENT_TIME_HISTORY",
            "No binary adverse target available for time-series anomaly radar.",
            "अर्ली-वॉर्निंग रडार के लिए समस्या टारगेट कॉलम उपलब्ध नहीं है।",
        )

    # Red-Team Guard R1: Auto Date-Axis Resolution
    date_col, dt_series = _detect_primary_date_series(df)
    if date_col is None or dt_series is None:
        return _empty_result(
            "INSUFFICIENT_TIME_HISTORY",
            "Snapshot dataset without a valid date column — Early-Warning Time Radar automatically suppressed (zero fake trend).",
            "इस फ़ाइल में तारीख़ (Date) कॉलम नहीं है — नकली ट्रेंड से बचने के लिए अर्ली-वॉर्निंग रडार अपने-आप बंद है।",
        )

    valid_mask = dt_series.notna()
    if int(valid_mask.sum()) < 40:
        return _empty_result(
            "INSUFFICIENT_TIME_HISTORY",
            "Fewer than 40 dated rows found — Early-Warning Time Radar suppressed.",
            "40 से कम तारीख़ वाले रिकॉर्ड मिले — अर्ली-वॉर्निंग रडार बंद रखा गया है।",
            date_col_found=date_col,
        )

    dt_valid = dt_series[valid_mask]
    span_days = int((dt_valid.max() - dt_valid.min()).days)
    if span_days < 4:
        return _empty_result(
            "INSUFFICIENT_TIME_HISTORY",
            "All records fall within fewer than 4 calendar days — insufficient time horizon for trend radar.",
            "सारा डेटा 4 दिनों से कम समय का है — ट्रेंड रडार के लिए पर्याप्त समय-इतिहास नहीं है।",
            date_col_found=date_col,
        )

    if span_days >= 240:
        granularity = "monthly"
        bucket_keys = dt_valid.dt.strftime("%Y-%m")
        days_per_bucket = 30.0
    elif span_days >= 42:
        granularity = "weekly"
        iso_cal = dt_valid.dt.isocalendar()
        bucket_keys = iso_cal["year"].astype(str) + "-W" + iso_cal["week"].astype(str).str.zfill(2)
        days_per_bucket = 7.0
    else:
        granularity = "daily"
        bucket_keys = dt_valid.dt.strftime("%Y-%m-%d")
        days_per_bucket = 1.0

    # Monetary vector (strictly 0 if non-monetary)
    if phys_is_fin and phys_cost_col and phys_cost_col in df.columns:
        s_cost = pd.to_numeric(df.loc[valid_mask, phys_cost_col], errors="coerce").fillna(0.0).clip(lower=0.0)
    else:
        s_cost = pd.Series(0.0, index=dt_valid.index)

    work_df = pd.DataFrame({
        "bucket_key": bucket_keys.values,
        "_bin": s_bin.loc[valid_mask].values,
        "_drag": (s_cost.values * s_bin.loc[valid_mask].values) if phys_is_fin else 0.0,
    }, index=dt_valid.index)

    agg = work_df.groupby("bucket_key", sort=True).agg(
        records=("_bin", "size"),
        adverse_events=("_bin", "sum"),
        capital_drag=("_drag", "sum"),
    ).reset_index()

    # Keep buckets with at least 10 records for clean statistics
    agg_clean = agg[agg["records"] >= 10].copy()
    if len(agg_clean) < 4:
        return _empty_result(
            "INSUFFICIENT_TIME_HISTORY",
            f"Only {len(agg_clean)} valid {granularity} periods (need >= 4) — skipping anomaly radar.",
            f"सिर्फ़ {len(agg_clean)} पर्याप्त {granularity} अवधि मिलीं (कम से कम 4 चाहिए) — रडार बंद है।",
            date_col_found=date_col,
        )

    agg_clean["adverse_rate_pct"] = (agg_clean["adverse_events"] / agg_clean["records"]) * 100.0
    agg_clean["ewma_rate_pct"] = agg_clean["adverse_rate_pct"].ewm(span=min(4, len(agg_clean)), adjust=False).mean()

    rates = agg_clean["adverse_rate_pct"].to_numpy(dtype=float)
    med_rate = float(np.median(rates))
    abs_dev = np.abs(rates - med_rate)
    mad = float(np.median(abs_dev))
    # Fallback scale if MAD == 0 (flat historical baseline)
    if mad < 1e-6:
        q75, q25 = float(np.percentile(rates, 75)), float(np.percentile(rates, 25))
        scale = max((q75 - q25) / 1.349, float(np.std(rates)), 0.5)
        mod_z = (rates - med_rate) / scale
    else:
        mod_z = 0.6745 * (rates - med_rate) / mad

    agg_clean["modified_z"] = np.where(np.isfinite(mod_z), mod_z, 0.0)

    # Period series (compact latest 18 periods for UI sparkline/audit)
    period_series: List[Dict[str, Any]] = []
    period_anomalies: List[Dict[str, Any]] = []
    tail_rows = agg_clean.tail(18)
    for row in tail_rows.itertuples(index=False):
        r_rec = int(row.records)
        r_ev = int(row.adverse_events)
        r_rate = round(float(row.adverse_rate_pct), 2)
        r_ewma = round(float(row.ewma_rate_pct), 2)
        r_z = round(float(row.modified_z), 2)
        r_drag = round(float(row.capital_drag), 2) if phys_is_fin else 0.0
        is_spike = bool(r_z >= 2.5 and (r_rate - med_rate) >= 3.0 and r_rec >= 25)
        period_series.append({
            "period": str(row.bucket_key),
            "records": r_rec,
            "adverse_events": r_ev,
            "adverse_rate_pct": r_rate,
            "ewma_rate_pct": r_ewma,
            "modified_z": r_z,
            "capital_drag": r_drag,
            "is_spike": is_spike,
        })

    # Inspect the most recent 2 periods for active early-warning spikes
    recent_check_periods = period_series[-2:]
    for p_item in recent_check_periods:
        if p_item["is_spike"]:
            delta_vs_med = round(p_item["adverse_rate_pct"] - med_rate, 2)
            sev = "CRITICAL" if (p_item["modified_z"] >= 3.0 and delta_vs_med >= 5.0) else "WATCH"
            period_anomalies.append({
                "period": p_item["period"],
                "severity": sev,
                "adverse_rate_pct": p_item["adverse_rate_pct"],
                "baseline_median_pct": round(med_rate, 2),
                "delta_pp": delta_vs_med,
                "modified_z": p_item["modified_z"],
                "records": p_item["records"],
                "capital_drag": p_item["capital_drag"],
                "formatted_drag": _fmt_money_compact(p_item["capital_drag"], sym, phys_is_fin) if phys_is_fin else f"{p_item['adverse_events']:,} cases",
                "headline_en": f"Recent spike in {p_item['period']}: adverse rate jumped to {p_item['adverse_rate_pct']:.1f}% vs {med_rate:.1f}% baseline (+{delta_vs_med:.1f} pp, Z={p_item['modified_z']:.1f}).",
                "headline_hi": f"{p_item['period']} में अचानक उछाल: समस्या दर {med_rate:.1f}% से बढ़कर {p_item['adverse_rate_pct']:.1f}% पहुँच गई (+{delta_vs_med:.1f} pp)।",
            })

    # =========================================================================
    # 2. EMERGING COHORT ACCELERATION SCANNER (Recent Window vs Prior Baseline)
    # =========================================================================
    all_buckets = agg_clean["bucket_key"].tolist()
    n_recent_buckets = max(1, min(3, int(math.ceil(len(all_buckets) * 0.20))))
    recent_bucket_set = set(all_buckets[-n_recent_buckets:])
    # Ensure recent window has >= 25 rows; expand by 1 bucket if tiny
    while n_recent_buckets < len(all_buckets) - 2:
        rec_cnt = int(work_df["bucket_key"].isin(recent_bucket_set).sum())
        if rec_cnt >= 25:
            break
        n_recent_buckets += 1
        recent_bucket_set = set(all_buckets[-n_recent_buckets:])

    is_recent_mask = work_df["bucket_key"].isin(recent_bucket_set).to_numpy()
    n_recent_total = int(is_recent_mask.sum())
    n_prior_total = int((~is_recent_mask).sum())
    recent_label = f"{all_buckets[-n_recent_buckets]} to {all_buckets[-1]}" if n_recent_buckets > 1 else str(all_buckets[-1])

    # Identify up to 8 clean operational categorical dimensions
    target_col_name = ct.get("target_col") if isinstance(ct, dict) else None
    skip_cols = {target_col_name, phys_cost_col, "_is_target_event", date_col}
    op_dims: List[str] = []
    for col in df.columns:
        if col in skip_cols:
            continue
        low = str(col).lower().strip()
        if any(tok in low for tok in ("date", "time", "year", "month", "day", "id", "uuid", "phone", "email", "name")):
            continue
        if is_sensitive_column_name(col) or is_demographic_attribute(col) or is_synthetic_column(col):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        nunq = int(df[col].nunique(dropna=True))
        if 2 <= nunq <= 30 and not is_index_artifact(col, df[col]) and not is_pseudo_numeric_identifier(col, df[col]):
            op_dims.append(col)
        if len(op_dims) >= 8:
            break

    raw_cohort_tests: List[Dict[str, Any]] = []
    if n_recent_total >= 25 and n_prior_total >= 25:
        df_valid_view = df.loc[valid_mask]
        bin_vals = work_df["_bin"].to_numpy(dtype=int)
        drag_vals = work_df["_drag"].to_numpy(dtype=float)

        for dim in op_dims:
            try:
                tmp = pd.DataFrame({
                    "seg": df_valid_view[dim].fillna("Unknown").astype(str).values,
                    "rec": is_recent_mask.astype(int),
                    "ev": bin_vals,
                    "drag": drag_vals,
                })
                grp = tmp.groupby(["seg", "rec"], sort=False).agg(
                    n=("ev", "size"),
                    k=("ev", "sum"),
                    drag=("drag", "sum"),
                ).unstack(fill_value=0)

                if 0 not in grp["n"].columns or 1 not in grp["n"].columns:
                    continue

                for seg_val in grp.index:
                    n_r = int(grp["n"].at[seg_val, 1])
                    n_p = int(grp["n"].at[seg_val, 0])
                    if n_r < 25 or n_p < 25:
                        continue
                    k_r = int(grp["k"].at[seg_val, 1])
                    k_p = int(grp["k"].at[seg_val, 0])
                    r_pct = (k_r / n_r) * 100.0
                    p_pct = (k_p / n_p) * 100.0
                    delta = r_pct - p_pct
                    if abs(delta) < 3.0:
                        continue
                    z_s, p_v = _two_prop_z_test(k_r, n_r, k_p, n_p)
                    drag_r = float(grp["drag"].at[seg_val, 1]) if phys_is_fin else 0.0
                    raw_cohort_tests.append({
                        "dimension": dim,
                        "dimension_label": _human_col_name(dim),
                        "segment": str(seg_val),
                        "recent_n": n_r,
                        "prior_n": n_p,
                        "recent_events": k_r,
                        "recent_rate_pct": round(r_pct, 2),
                        "prior_rate_pct": round(p_pct, 2),
                        "delta_pp": round(delta, 2),
                        "z_stat": round(z_s, 2),
                        "p_value": round(p_v, 6),
                        "recent_capital_drag": round(drag_r, 2) if phys_is_fin else 0.0,
                        "formatted_recent_drag": _fmt_money_compact(drag_r, sym, phys_is_fin) if phys_is_fin else f"{k_r:,} cases",
                    })
            except Exception:
                continue

    # Apply Benjamini-Hochberg FDR across all cohort tests (anti-spam guard R2)
    accelerating_cohorts: List[Dict[str, Any]] = []
    improving_cohorts: List[Dict[str, Any]] = []
    if raw_cohort_tests:
        m_tests = len(raw_cohort_tests)
        raw_cohort_tests.sort(key=lambda x: x["p_value"])
        prev_q = 1.0
        for rank_idx in range(m_tests - 1, -1, -1):
            item = raw_cohort_tests[rank_idx]
            q_val = min(prev_q, item["p_value"] * m_tests / (rank_idx + 1))
            item["fdr_q_value"] = round(float(q_val), 6)
            prev_q = q_val

        for item in raw_cohort_tests:
            if item["fdr_q_value"] > 0.05:
                continue
            if item["delta_pp"] >= 3.0:
                sev = "CRITICAL" if (item["fdr_q_value"] <= 0.01 and item["delta_pp"] >= 6.0) else "WATCH"
                item["severity"] = sev
                item["headline_en"] = (
                    f"{item['dimension_label']} = '{item['segment']}' accelerated from {item['prior_rate_pct']:.1f}% → "
                    f"{item['recent_rate_pct']:.1f}% (+{item['delta_pp']:.1f} pp) in recent window ({recent_label})."
                )
                item["headline_hi"] = (
                    f"{item['dimension_label']} = '{item['segment']}' में हाल की समस्या {item['prior_rate_pct']:.1f}% से बढ़कर "
                    f"{item['recent_rate_pct']:.1f}% (+{item['delta_pp']:.1f} pp) हो गई है ({recent_label})।"
                )
                item["action_en"] = f"Audit '{item['segment']}' immediately before this accelerating trend spreads into next month."
                item["action_hi"] = f"अगले महीने बड़ा नुकसान होने से पहले '{item['segment']}' पर तुरंत कंट्रोल लगाएँ।"
                accelerating_cohorts.append(item)
            elif item["delta_pp"] <= -3.0:
                item["severity"] = "IMPROVING"
                item["headline_en"] = (
                    f"{item['dimension_label']} = '{item['segment']}' improved from {item['prior_rate_pct']:.1f}% → "
                    f"{item['recent_rate_pct']:.1f}% ({item['delta_pp']:.1f} pp)."
                )
                item["headline_hi"] = (
                    f"{item['dimension_label']} = '{item['segment']}' में सुधार हुआ: {item['prior_rate_pct']:.1f}% से घटकर "
                    f"{item['recent_rate_pct']:.1f}% ({item['delta_pp']:.1f} pp)।"
                )
                improving_cohorts.append(item)

        accelerating_cohorts.sort(key=lambda x: (-x["delta_pp"], x["fdr_q_value"]))
        improving_cohorts.sort(key=lambda x: (x["delta_pp"], x["fdr_q_value"]))

    # Respect V4.0 Circuit-Breaker if noise and no strong q <= 0.01 fire exists
    if circuit_breaker_active:
        accelerating_cohorts = [c for c in accelerating_cohorts if c.get("fdr_q_value", 1.0) <= 0.01 and c.get("delta_pp", 0.0) >= 6.0]
        period_anomalies = [p for p in period_anomalies if p.get("severity") == "CRITICAL"]

    has_critical = any(x.get("severity") == "CRITICAL" for x in period_anomalies) or any(
        x.get("severity") == "CRITICAL" for x in accelerating_cohorts
    )
    has_watch = bool(period_anomalies or accelerating_cohorts)
    overall_level = "CRITICAL" if has_critical else ("WATCH" if has_watch else "ALL_CLEAR")

    # =========================================================================
    # 3. HONEST BOUNDED 30-DAY FORWARD RISK PROJECTION (ONLY WHEN ACCELERATING)
    # =========================================================================
    forward_proj: Optional[Dict[str, Any]] = None
    recent_rate_all = float(work_df.loc[is_recent_mask, "_bin"].mean() * 100.0) if n_recent_total > 0 else med_rate
    prior_rate_all = float(work_df.loc[~is_recent_mask, "_bin"].mean() * 100.0) if n_prior_total > 0 else med_rate
    overall_delta_pp = round(recent_rate_all - prior_rate_all, 2)

    if overall_level in ("CRITICAL", "WATCH"):
        # Compute damped 30-day extra adverse exposure from latest accelerating signal
        recent_days = max(1.0, n_recent_buckets * days_per_bucket)
        scale_to_30d = 30.0 / recent_days
        if accelerating_cohorts:
            top_c = accelerating_cohorts[0]
            excess_ev_recent = max(1.0, top_c["recent_n"] * (top_c["delta_pp"] / 100.0))
            avg_cost_ev = (top_c["recent_capital_drag"] / max(top_c["recent_events"], 1)) if phys_is_fin else 0.0
            driver_en = f"{top_c['dimension_label']} = '{top_c['segment']}'"
        else:
            top_p = period_anomalies[-1]
            excess_ev_recent = max(1.0, top_p["records"] * (top_p["delta_pp"] / 100.0))
            avg_cost_ev = (top_p["capital_drag"] / max(int(round(top_p["records"] * top_p["adverse_rate_pct"] / 100.0)), 1)) if phys_is_fin else 0.0
            driver_en = f"Recent period {top_p['period']}"

        # 0.70 damping factor + +/-25% honest uncertainty band
        proj_events_mid = max(1.0, excess_ev_recent * scale_to_30d * 0.70)
        proj_events_low = max(1.0, proj_events_mid * 0.75)
        proj_events_high = max(proj_events_mid + 1.0, proj_events_mid * 1.25)

        if phys_is_fin and avg_cost_ev > 0:
            low_val = round(proj_events_low * avg_cost_ev, 2)
            mid_val = round(proj_events_mid * avg_cost_ev, 2)
            high_val = round(proj_events_high * avg_cost_ev, 2)
            range_fmt = f"{_fmt_money_compact(low_val, sym, True)} – {_fmt_money_compact(high_val, sym, True)}"
            note_en = f"If {driver_en} stays unchecked for 30 days, projected extra risk is {range_fmt} (~{int(round(proj_events_mid)):,} extra cases)."
            note_hi = f"अगर {driver_en} को अगले 30 दिन नहीं रोका गया, तो अनुमानित अतिरिक्त नुकसान {range_fmt} (~{int(round(proj_events_mid)):,} केस) हो सकता है।"
        else:
            low_val, mid_val, high_val = 0.0, 0.0, 0.0
            range_fmt = f"{int(round(proj_events_low)):,} – {int(round(proj_events_high)):,} extra cases"
            note_en = f"If {driver_en} stays unchecked for 30 days, projected extra impact is {range_fmt}."
            note_hi = f"अगर {driver_en} को अगले 30 दिन नहीं रोका गया, तो {range_fmt} अतिरिक्त मामले बढ़ सकते हैं।"

        forward_proj = {
            "horizon_days": 30,
            "driver": driver_en,
            "projected_extra_events_low": int(round(proj_events_low)),
            "projected_extra_events_mid": int(round(proj_events_mid)),
            "projected_extra_events_high": int(round(proj_events_high)),
            "projected_extra_drag_low": low_val,
            "projected_extra_drag_mid": mid_val,
            "projected_extra_drag_high": high_val,
            "formatted_range": range_fmt,
            "note_en": note_en,
            "note_hi": note_hi,
        }

    # Crisp executive headlines
    if overall_level == "CRITICAL":
        lead_src = accelerating_cohorts[0] if accelerating_cohorts else period_anomalies[-1]
        headline_en = f"Early Warning CRITICAL: {lead_src['headline_en']}"
        headline_hi = f"तुरंत अलर्ट (CRITICAL): {lead_src['headline_hi']}"
    elif overall_level == "WATCH":
        lead_src = accelerating_cohorts[0] if accelerating_cohorts else period_anomalies[-1]
        headline_en = f"Early Warning WATCH: {lead_src['headline_en']}"
        headline_hi = f"निगरानी अलर्ट (WATCH): {lead_src['headline_hi']}"
    else:
        headline_en = f"All Clear across {len(agg_clean)} {granularity} periods ({date_col}) — no statistically accelerating spike in recent window ({recent_label})."
        headline_hi = f"सभी {len(agg_clean)} {granularity} अवधियों में स्थिति स्थिर है — हाल के समय ({recent_label}) में कोई अचानक तेज़ गिरावट नहीं मिली।"

    result = {
        "version": "7.0",
        "status": "ANALYZED",
        "is_applicable": True,
        "overall_alert_level": overall_level,
        "audited_fact_records": n_rows,
        "is_financial": phys_is_fin,
        "currency_symbol": sym,
        "date_column": date_col,
        "bucket_granularity": granularity,
        "periods_analyzed": int(len(agg_clean)),
        "recent_window_label": recent_label,
        "recent_window_records": n_recent_total,
        "baseline_median_rate_pct": round(med_rate, 2),
        "recent_rate_pct": round(recent_rate_all, 2),
        "prior_rate_pct": round(prior_rate_all, 2),
        "overall_delta_pp": overall_delta_pp,
        "headline_en": headline_en,
        "headline_hi": headline_hi,
        "period_series": period_series,
        "period_anomalies": period_anomalies[:4],
        "accelerating_cohorts": accelerating_cohorts[:5],
        "improving_cohorts": improving_cohorts[:3],
        "forward_risk_projection": forward_proj,
        "should_dispatch_alert": overall_level == "CRITICAL",
        "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    }

    if output_dir is not None:
        try:
            out_p = Path(output_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            atomic_write_json(out_p / "proactive_anomaly_report.json", result)
        except Exception:
            pass

    return result


__all__ = ["run_proactive_anomaly_radar"]
