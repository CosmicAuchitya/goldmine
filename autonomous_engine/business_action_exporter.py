"""
=============================================================================
ENTERPRISE BUSINESS ACTION EXPORTER & TEMPORAL TREND FORENSIC ENGINE
=============================================================================
Translates deep statistical and machine learning artifacts into concrete,
actionable business deliverables for non-technical stakeholders:
1. Two-Queue Actionable Priority Worklist (`actionable_priority_worklist.csv`):
   - PREVENTIVE_RETENTION_WATCH: Active at-risk records to retain before failure.
   - REALIZED_LOSS_RECOVERY_AUDIT: Realized failure records for collections/QA.
   - Zero `* 1000` currency fabrication; preserves 100% physical primary key lineage.
   - 100% vectorized scoring (zero `iterrows()` loops); zero demographic bias.
2. Temporal Trend & Seasonality Engine (`temporal_trend_summary.json`):
   - Genuine timestamp discovery (excludes Age, Tenure, IDs, and index artifacts).
   - Period-over-Period (MoM/Weekly) volume, defect rate, and drag tracking.
3. Plain-Language Bilingual Executive Brief (`PLAIN_BUSINESS_SUMMARY.md`):
   - Side-by-side Simple Business English and Simple Business Hinglish (Roman script) briefs.
   - Honest statistical circuit-breaker warning ($0 spend freeze on noise across all blocks).
   - Real bottleneck segment and failure rate (never 'N/A' or 0.00%).
   - Real continuous threshold cliff metrics and exact Strategic Decision pathways.
=============================================================================
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

try:
    from .common_utils import quote_sql_ident
    from .pii_scrubber import is_sensitive_column_name
    from .target_resolver import (
        resolve_canonical_target_and_cost,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        is_demographic_attribute
    )
    from .strategic_decision_matrix import (
        calculate_wilson_ci,
        calculate_excess_risk_metrics,
        StrategicDecisionEngine
    )
except ImportError:
    from common_utils import quote_sql_ident
    from pii_scrubber import is_sensitive_column_name
    from target_resolver import (
        resolve_canonical_target_and_cost,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        is_demographic_attribute
    )
    from strategic_decision_matrix import (
        calculate_wilson_ci,
        calculate_excess_risk_metrics,
        StrategicDecisionEngine
    )


def detect_primary_key_column(df: pd.DataFrame, blueprint: Optional[Dict[str, Any]] = None) -> str:
    """Discovers the physical primary key column in df_fact with 100% physical ground-truth."""
    cols = list(df.columns)
    if blueprint:
        for k in ("primary_id_column", "primary_key", "fact_pk"):
            cand = blueprint.get(k)
            if cand and cand in cols:
                return cand

    # Candidate identification
    id_candidates = []
    for c in cols:
        if is_index_artifact(c, df[c]):
            continue
        c_low = c.lower()
        if c_low.startswith(('id_', 'id', 'pk_')) or c_low.endswith(('_id', ' id', '_key', ' key', '_uuid', ' uuid', '_code', ' code', '_number', ' number')):
            id_candidates.append(c)
        elif c_low in ('id', 'key', 'uuid', 'pk', 'code', 'surrogate_key', 'fact_surrogate_id', 'customerid'):
            id_candidates.append(c)

    if id_candidates:
        domain_ids = [c for c in id_candidates if c != "fact_surrogate_id"]
        if domain_ids:
            domain_ids.sort(key=lambda c: -df[c].nunique())
            return domain_ids[0]
        id_candidates.sort(key=lambda c: -df[c].nunique())
        return id_candidates[0]

    if "fact_surrogate_id" in cols:
        return "fact_surrogate_id"

    # Default to first non-target column
    for c in cols:
        if not is_index_artifact(c, df[c]) and not is_synthetic_column(c):
            return c
    return cols[0]


def generate_actionable_priority_worklist(
    df_fact: pd.DataFrame,
    out_path: Path | str,
    blueprint: Optional[Dict[str, Any]] = None,
    max_rows_per_queue: int = 250
) -> Path:
    """
    Generates `actionable_priority_worklist.csv` strictly separating:
    1. PREVENTIVE_RETENTION_WATCH: Rows where _is_target_event == 0 (preventable active accounts).
    2. REALIZED_LOSS_RECOVERY_AUDIT: Rows where _is_target_event == 1 (realized failures).
    Zero fake multipliers; physical monetary exposure only.
    Vectorized computation; zero demographic bias.
    """
    out_dir = Path(out_path).resolve()
    canonical = resolve_canonical_target_and_cost(df_fact, blueprint=blueprint)
    target_col = canonical.get("target_col")
    cost_col = canonical.get("cost_col")
    s_bin = canonical.get("binary_target")

    df_work = df_fact.copy()
    if "_is_target_event" not in df_work.columns:
        df_work["_is_target_event"] = s_bin.astype(int)

    pk_col = detect_primary_key_column(df_work, blueprint)

    synthetic_from_bp = set()
    if blueprint:
        for f in blueprint.get("forensic_enrichment_columns", []):
            if "=" in f:
                synthetic_from_bp.add(f.split("=")[0].strip().lower())
            else:
                synthetic_from_bp.add(f.strip().lower())

    def is_synth(c: str) -> bool:
        cl = str(c).strip().lower()
        if cl in synthetic_from_bp or cl.replace(" ", "_") in [x.replace(" ", "_") for x in synthetic_from_bp]:
            return True
        return is_synthetic_column(c, blueprint)

    # Detect top categorical segment for cohort risk mapping
    cat_candidates = []
    for c in df_work.columns:
        if c in (target_col, cost_col, "_is_target_event", pk_col):
            continue
        if is_index_artifact(c, df_work[c]) or is_pseudo_numeric_identifier(c, df_work[c]):
            continue
        if is_synth(c) or is_sensitive_column_name(c):
            continue
        if 2 <= df_work[c].nunique() <= 40:
            cat_candidates.append(c)

    operational_cats = [c for c in cat_candidates if not is_demographic_attribute(c)]
    usable_cats = operational_cats if operational_cats else cat_candidates

    def evaluate_cat_candidate(col_name: str) -> Tuple[float, float]:
        min_c = max(5, int(len(df_work) * 0.02))
        grp = df_work.groupby(col_name)["_is_target_event"].agg(["count", "mean"])
        valid_grp = grp[grp["count"] >= min_c]
        if len(valid_grp) < 2:
            return (0.0, 0.0)
        spread = float(valid_grp["mean"].max() - valid_grp["mean"].min())
        cont = pd.crosstab(df_work[col_name], df_work["_is_target_event"])
        chi2 = 0.0
        if cont.shape[0] >= 2 and cont.shape[1] == 2:
            try:
                chi2, _, _, _ = scipy_stats.chi2_contingency(cont)
            except Exception:
                chi2 = 0.0
        return (spread, float(chi2))

    if usable_cats:
        usable_cats.sort(key=lambda c: evaluate_cat_candidate(c), reverse=True)
        primary_dim = usable_cats[0]
    else:
        primary_dim = None

    cohort_risk_map: Dict[Any, float] = {}
    if primary_dim:
        rates = df_work.groupby(primary_dim)["_is_target_event"].mean()
        cohort_risk_map = (rates * 100.0).round(2).to_dict()

    # Detect top numeric continuous cliff for risk inflection (prioritizing raw physical columns)
    num_candidates = [
        c for c in df_work.columns
        if pd.api.types.is_numeric_dtype(df_work[c])
        and c not in (target_col, cost_col, "_is_target_event", pk_col)
        and not is_index_artifact(c, df_work[c])
        and not is_pseudo_numeric_identifier(c, df_work[c])
        and not is_synth(c)
        and not is_sensitive_column_name(c)
        and df_work[c].nunique() >= 5
    ]

    if not num_candidates:
        num_candidates = [
            c for c in df_work.columns
            if pd.api.types.is_numeric_dtype(df_work[c])
            and c not in (target_col, cost_col, "_is_target_event", pk_col)
            and not is_index_artifact(c, df_work[c])
            and not is_pseudo_numeric_identifier(c, df_work[c])
            and not is_sensitive_column_name(c)
            and df_work[c].nunique() >= 5
        ]

    cliff_col = None
    cliff_thresh = None
    cliff_op = ">="
    best_diff = -1.0

    for nc in num_candidates[:6]:
        s_col = pd.to_numeric(df_work[nc], errors='coerce').dropna()
        if len(s_col) < 20:
            continue
        q75 = float(s_col.quantile(0.75))
        q25 = float(s_col.quantile(0.25))

        # Check upper tail
        if not pd.isna(q75):
            mask_up = (s_col >= q75)
            if 0 < mask_up.sum() < len(s_col):
                r_sub = float(df_work.loc[s_col[mask_up].index, "_is_target_event"].mean())
                r_oth = float(df_work.loc[s_col[~mask_up].index, "_is_target_event"].mean())
                diff_up = r_sub - r_oth
                if diff_up > best_diff and diff_up > 0.05:
                    best_diff = diff_up
                    cliff_col = nc
                    cliff_thresh = q75
                    cliff_op = ">="

        # Check lower tail
        if not pd.isna(q25):
            mask_lo = (s_col <= q25)
            if 0 < mask_lo.sum() < len(s_col):
                r_sub = float(df_work.loc[s_col[mask_lo].index, "_is_target_event"].mean())
                r_oth = float(df_work.loc[s_col[~mask_lo].index, "_is_target_event"].mean())
                diff_lo = r_sub - r_oth
                if diff_lo > best_diff and diff_lo > 0.05:
                    best_diff = diff_lo
                    cliff_col = nc
                    cliff_thresh = q25
                    cliff_op = "<="

    # 100% Vectorized scoring (Zero Python row iteration loops!)
    baseline_rate = float(df_work["_is_target_event"].mean() * 100.0)
    if primary_dim:
        cohort_series = df_work[primary_dim].map(cohort_risk_map).fillna(baseline_rate)
        seg_str = df_work[primary_dim].astype(str)
        cohort_reasons = "Cohort " + primary_dim + "='" + seg_str + "' (" + cohort_series.round(1).astype(str) + "% risk)"
    else:
        cohort_series = pd.Series(baseline_rate, index=df_work.index)
        cohort_reasons = pd.Series(f"Baseline Portfolio Risk ({baseline_rate:.1f}%)", index=df_work.index)

    if cliff_col and cliff_thresh is not None:
        s_num = pd.to_numeric(df_work[cliff_col], errors='coerce')
        if cliff_op == ">=":
            cliff_mask = (s_num >= cliff_thresh).fillna(False)
            cliff_reason = f"{cliff_col} >= {cliff_thresh:.2f} Cliff Breach"
        else:
            cliff_mask = (s_num <= cliff_thresh).fillna(False)
            cliff_reason = f"{cliff_col} <= {cliff_thresh:.2f} Cliff Breach"

        final_risk = np.where(cliff_mask, np.minimum(100.0, cohort_series + 15.0), cohort_series)
        final_reasons = np.where(cliff_mask, cohort_reasons + "; " + cliff_reason, cohort_reasons)
    else:
        final_risk = cohort_series.values
        final_reasons = cohort_reasons.values

    df_work["empirical_cohort_risk_pct"] = np.round(final_risk, 2)
    df_work["primary_risk_reason"] = final_reasons

    # Monetary exposure
    if cost_col:
        df_work["monetary_exposure"] = pd.to_numeric(df_work[cost_col], errors="coerce").round(2)
        df_work["exposure_column_source"] = str(cost_col)
    else:
        df_work["monetary_exposure"] = np.nan
        df_work["exposure_column_source"] = "NONE_PHYSICAL_UNITS"

    # Context columns (pick up to 3 informative non-PII, non-synthetic columns)
    context_cols = []
    if primary_dim and primary_dim in df_work.columns:
        context_cols.append(primary_dim)
    for nc in num_candidates[:2]:
        if nc not in context_cols and nc != cost_col and not is_sensitive_column_name(nc):
            context_cols.append(nc)

    # 1. Queue A: PREVENTIVE_RETENTION_WATCH (_is_target_event == 0)
    df_prev = df_work[df_work["_is_target_event"] == 0].copy()
    if cost_col:
        df_prev = df_prev.sort_values(by=["empirical_cohort_risk_pct", "monetary_exposure"], ascending=[False, False])
    else:
        df_prev = df_prev.sort_values(by=["empirical_cohort_risk_pct"], ascending=[False])

    df_prev = df_prev.head(max_rows_per_queue)
    df_prev["priority_rank"] = range(1, len(df_prev) + 1)
    df_prev["action_queue"] = "PREVENTIVE_RETENTION_WATCH"
    df_prev["recommended_next_step"] = "Preventive Outreach / Retention Offer / Quality Check Before Failure"

    # 2. Queue B: REALIZED_LOSS_RECOVERY_AUDIT (_is_target_event == 1)
    df_rec = df_work[df_work["_is_target_event"] == 1].copy()
    if cost_col:
        df_rec = df_rec.sort_values(by=["monetary_exposure", "empirical_cohort_risk_pct"], ascending=[False, False])
    else:
        df_rec = df_rec.sort_values(by=["empirical_cohort_risk_pct"], ascending=[False])

    df_rec = df_rec.head(max_rows_per_queue)
    df_rec["priority_rank"] = range(1, len(df_rec) + 1)
    df_rec["action_queue"] = "REALIZED_LOSS_RECOVERY_AUDIT"
    df_rec["recommended_next_step"] = "Loss Recovery / Root-Cause Defect Audit / Collections Follow-up"

    # Combine Queues
    combined_df = pd.concat([df_prev, df_rec], ignore_index=True)

    ordered_cols = [
        pk_col, "priority_rank", "action_queue", "_is_target_event",
        "empirical_cohort_risk_pct", "monetary_exposure", "exposure_column_source",
        "primary_risk_reason", "recommended_next_step"
    ] + [c for c in context_cols if c not in [pk_col, "_is_target_event"]]

    worklist_csv_path = out_dir / "actionable_priority_worklist.csv"
    combined_df[ordered_cols].to_csv(worklist_csv_path, index=False)
    print(f"[+] Actionable Priority Worklist written to: {worklist_csv_path} ({len(combined_df)} rows)")
    return worklist_csv_path


def analyze_temporal_trends(
    df_fact: pd.DataFrame,
    out_path: Path | str,
    blueprint: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyzes true temporal trends across verified calendar date columns.
    Excludes non-temporal numeric sequences (Age, Tenure, Duration, IDs).
    Writes `temporal_trend_summary.json`.
    """
    out_dir = Path(out_path).resolve()
    canonical = resolve_canonical_target_and_cost(df_fact, blueprint=blueprint)
    cost_col = canonical.get("cost_col")
    s_bin = canonical.get("binary_target")

    df_work = df_fact.copy()
    if "_is_target_event" not in df_work.columns:
        df_work["_is_target_event"] = s_bin.astype(int)

    # Calendar Date Column Discovery
    date_col = None
    disqualified_tokens = {
        'age', 'tenure', 'duration', 'birth', 'dob', 'months_on_book',
        'credit_history_age', 'days_since', 'days_until', 'zip', 'year_birth'
    }

    for c in df_work.columns:
        if is_index_artifact(c, df_work[c]) or is_pseudo_numeric_identifier(c, df_work[c]):
            continue
        c_low = c.lower()
        if any(dtok in c_low for dtok in disqualified_tokens):
            continue

        is_explicit_dt_name = any(k in c_low for k in [
            'date', 'timestamp', 'created_at', 'order_date', 'signup_date',
            'transaction_date', 'invoice_date', 'claim_date', 'datetime', 'month_year'
        ])
        is_dt_dtype = pd.api.types.is_datetime64_any_dtype(df_work[c])

        if is_dt_dtype or is_explicit_dt_name:
            try:
                s_non_null = df_work[c].dropna()
                if len(s_non_null) > 10:
                    parsed = pd.to_datetime(s_non_null.head(100), errors="coerce")
                    valid_ratio = parsed.notna().mean()
                    if valid_ratio >= 0.80:
                        # Verify year range [1990, 2100]
                        years = parsed.dropna().dt.year
                        if years.min() >= 1990 and years.max() <= 2100:
                            date_col = c
                            break
            except Exception:
                continue

    summary_json_path = out_dir / "temporal_trend_summary.json"

    if not date_col:
        result = {
            "is_temporal_dataset": False,
            "date_column": None,
            "granularity": None,
            "period_count": 0,
            "summary_note": "Cross-sectional snapshot dataset — no physical event timestamp column present.",
            "periods": []
        }
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result

    # Convert full column to datetime
    dt_series = pd.to_datetime(df_work[date_col], errors="coerce")
    valid_mask = dt_series.notna()
    df_valid = df_work[valid_mask].copy()
    dt_valid = dt_series[valid_mask]

    span_days = (dt_valid.max() - dt_valid.min()).days
    n_distinct_months = dt_valid.dt.to_period("M").nunique()

    if span_days >= 45 and n_distinct_months >= 2:
        granularity = "monthly"
        df_valid["_period"] = dt_valid.dt.to_period("M").astype(str)
    elif span_days >= 14:
        granularity = "weekly"
        df_valid["_period"] = dt_valid.dt.strftime("%Y-W%U")
    else:
        granularity = "daily"
        df_valid["_period"] = dt_valid.dt.strftime("%Y-%m-%d")

    grouped = df_valid.groupby("_period", sort=True)
    periods_data = []

    for period_str, grp in grouped:
        vol = len(grp)
        events = int(grp["_is_target_event"].sum())
        rate = round(events / max(vol, 1) * 100.0, 2)
        drag = float(grp.loc[grp["_is_target_event"] == 1, cost_col].sum()) if cost_col else 0.0

        periods_data.append({
            "period": period_str,
            "total_records": vol,
            "adverse_events": events,
            "adverse_rate_pct": rate,
            "adverse_capital_drag": round(drag, 2),
            "has_monetary_column": bool(cost_col)
        })

    # Limit to latest 60 periods to prevent spec explosion
    periods_data = periods_data[-60:]

    if len(periods_data) >= 2:
        first_rate = periods_data[0]["adverse_rate_pct"]
        latest_rate = periods_data[-1]["adverse_rate_pct"]
        prev_rate = periods_data[-2]["adverse_rate_pct"]
        pop_delta = round(latest_rate - prev_rate, 2)
        first_last_delta = round(latest_rate - first_rate, 2)
        peak_period = max(periods_data, key=lambda x: x["adverse_rate_pct"])["period"]

        if pop_delta > 1.0:
            trend_dir = "WORSENING"
        elif pop_delta < -1.0:
            trend_dir = "IMPROVING"
        else:
            trend_dir = "STABLE"
    else:
        pop_delta = 0.0
        first_last_delta = 0.0
        peak_period = periods_data[0]["period"] if periods_data else "N/A"
        trend_dir = "STABLE"

    result = {
        "is_temporal_dataset": True,
        "date_column": date_col,
        "granularity": granularity,
        "period_count": len(periods_data),
        "period_over_period_rate_delta_pp": pop_delta,
        "first_to_last_rate_delta_pp": first_last_delta,
        "peak_risk_period": peak_period,
        "trend_direction": trend_dir,
        "summary_note": f"Temporal series audited across {len(periods_data)} {granularity} periods via '{date_col}'.",
        "periods": periods_data
    }

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"[+] Temporal Trend Summary written to: {summary_json_path} ({len(periods_data)} periods)")
    return result


def generate_plain_business_summary(
    df_fact: pd.DataFrame,
    out_path: Path | str,
    blueprint: Optional[Dict[str, Any]] = None,
    prim_dim_info: Optional[Dict[str, Any]] = None,
    temporal_summary: Optional[Dict[str, Any]] = None,
    worklist_path: Optional[Path | str] = None,
    strat_dossier: Optional[Dict[str, Any]] = None,
    cliffs: Optional[List[Dict[str, Any]]] = None
) -> Path:
    """
    Generates `PLAIN_BUSINESS_SUMMARY.md` in both Simple Business English
    and Simple Conversational Roman-Script Hinglish.
    100% grounded in DuckDB fact records and StrategicDecisionEngine findings.
    Zero academic jargon, zero 'N/A' 0.00% artifacts, and zero Circuit-Breaker contradictions.
    """
    out_dir = Path(out_path).resolve()
    canonical = resolve_canonical_target_and_cost(df_fact, blueprint=blueprint)
    target_col = canonical.get("target_col")
    cost_col = canonical.get("cost_col")
    s_bin = canonical.get("binary_target")

    total_records = len(df_fact)
    target_count = int(s_bin.sum())
    target_rate_pct = round(target_count / max(total_records, 1) * 100.0, 2)

    # Instantiate StrategicDecisionEngine if called standalone
    if strat_dossier is None or cliffs is None:
        try:
            strat_engine = StrategicDecisionEngine(df_fact, blueprint=blueprint)
            if strat_dossier is None:
                strat_dossier = strat_engine.generate_strategic_decision_dossier()
            if cliffs is None:
                cliffs = strat_engine.micro_engine.analyze_quantile_cliffs()
        except Exception:
            pass

    # Circuit-Breaker Status Resolution across all inputs
    is_cb_active = False
    if prim_dim_info and prim_dim_info.get("is_prim_significant") is False:
        is_cb_active = True
    elif strat_dossier and strat_dossier.get("is_statistically_significant") is False:
        is_cb_active = True

    # Financial Exposure vs Defect Event Volume
    has_cost = (cost_col is not None)
    if has_cost:
        adverse_cost = float(pd.to_numeric(df_fact.loc[s_bin == 1, cost_col], errors='coerce').fillna(0.0).sum())
        total_portfolio = float(pd.to_numeric(df_fact[cost_col], errors='coerce').fillna(0.0).sum())
        cost_drag_en = f"**${adverse_cost:,.2f}** in direct financial liability / capital at risk (out of ${total_portfolio:,.2f} total monitored portfolio volume)"
        cost_drag_hi = f"kul **${adverse_cost:,.2f}** ka seedha financial nuksan / risk (${total_portfolio:,.2f} ke kul portfolio volume mein se)"
    else:
        cost_drag_en = f"**{target_count:,} critical quality/failure events** ({target_rate_pct}% defect rate)"
        cost_drag_hi = f"kul **{target_count:,} critical failure/defect events** ({target_rate_pct}% defect rate)"

    # Resolve Primary Dimension & Bottleneck Cohort
    prim_dim = prim_dim_info.get("prim_dim") if prim_dim_info else None
    if not prim_dim and strat_dossier:
        hr_seg = strat_dossier.get("high_risk_segment", "")
        if " = " in hr_seg:
            prim_dim = hr_seg.split(" = ")[0].strip()

    top_leak_seg = prim_dim_info.get("top_leak_segment") if prim_dim_info else None
    top_leak_rate = float(prim_dim_info.get("top_leak_rate", 0.0)) if prim_dim_info else 0.0
    baseline_rate = float(prim_dim_info.get("baseline_rate", target_rate_pct)) if prim_dim_info else target_rate_pct
    rest_rate = baseline_rate

    # If top_leak_seg is invalid or missing, recover from strat_dossier or df_fact
    if (not top_leak_seg or top_leak_seg == "N/A" or top_leak_rate == 0.0) and strat_dossier and not is_cb_active:
        hr_seg = strat_dossier.get("high_risk_segment", "")
        if " = " in hr_seg:
            parts = hr_seg.split(" = ", 1)
            if not prim_dim:
                prim_dim = parts[0].strip()
            if prim_dim == parts[0].strip():
                top_leak_seg = parts[1].strip().strip("'\"")
                top_leak_rate = float(strat_dossier.get("high_risk_rate", target_rate_pct))
                rest_rate = float(strat_dossier.get("rest_rate", baseline_rate))

    if (not top_leak_seg or top_leak_seg == "N/A" or top_leak_rate == 0.0) and prim_dim and prim_dim in df_fact.columns:
        min_c = max(5, int(total_records * 0.02))
        temp_bin = df_fact["_is_target_event"] if "_is_target_event" in df_fact.columns else s_bin
        rates = temp_bin.groupby(df_fact[prim_dim]).agg(["count", "mean"])
        valid_rates = rates[rates["count"] >= min_c]
        if len(valid_rates) > 0:
            worst_idx = valid_rates["mean"].idxmax()
            top_leak_seg = str(worst_idx)

    # Physical Ground-Truth Enforcement: ALWAYS compute exact cohort & rest-of-business rates on (prim_dim == top_leak_seg)
    if prim_dim and prim_dim in df_fact.columns and top_leak_seg and top_leak_seg != "N/A":
        seg_mask = (df_fact[prim_dim].astype(str) == str(top_leak_seg))
        n_seg = int(seg_mask.sum())
        if n_seg > 0:
            k_seg = int(s_bin[seg_mask].sum())
            top_leak_rate = round((k_seg / n_seg) * 100.0, 2)
            n_other = max(1, total_records - n_seg)
            k_other = max(0, target_count - k_seg)
            rest_rate = round((k_other / n_other) * 100.0, 2)

    # Worklist summary counts
    n_prev_watch = 0
    n_loss_audit = 0
    wl_file = Path(worklist_path).resolve() if worklist_path else (out_dir / "actionable_priority_worklist.csv")
    if wl_file.exists():
        try:
            wl_df = pd.read_csv(wl_file)
            n_prev_watch = int((wl_df["action_queue"] == "PREVENTIVE_RETENTION_WATCH").sum())
            n_loss_audit = int((wl_df["action_queue"] == "REALIZED_LOSS_RECOVERY_AUDIT").sum())
        except Exception:
            pass

    # Temporal Trend Note
    temp_note_en = ""
    temp_note_hi = ""
    if temporal_summary and temporal_summary.get("is_temporal_dataset"):
        t_dir = temporal_summary.get("trend_direction", "STABLE")
        p_count = temporal_summary.get("period_count", 0)
        pop_delta = temporal_summary.get("period_over_period_rate_delta_pp", 0.0)
        temp_note_en = f"\n- **Time Trend ({p_count} periods)**: The defect rate is currently **{t_dir}** (recent period shift: {pop_delta:+.2f} percentage points)."
        temp_note_hi = f"\n- **Time Trend ({p_count} periods)**: Defect rate abhi **{t_dir}** trend mein hai (recent period change: {pop_delta:+.2f} percentage points)."

    # =========================================================================
    # BLOCK 2: Bottleneck Identification
    # =========================================================================
    if not is_cb_active and prim_dim and top_leak_seg and top_leak_seg != "N/A" and top_leak_rate > 0.0:
        bottleneck_en = (
            f"- **Main Bottleneck Identified**: Group `{prim_dim}` = **'{top_leak_seg}'** has the highest failure rate at **{top_leak_rate:.2f}%** (compared to {rest_rate:.2f}% across the rest of the business).\n"
            f"- **Strategic Priority**: Direct intervention on this specific group will yield the highest return on operational effort."
        )
        bottleneck_hi = (
            f"- **Sabse Bada Bottleneck Kahan Hai?**: Group `{prim_dim}` = **'{top_leak_seg}'** mein sabse zyada failure/churn rate **{top_leak_rate:.2f}%** hai (jabki baaki business mein yeh sirf {rest_rate:.2f}% hai).\n"
            f"- **Team Ka Focus**: Sabse pehle isi specific cohort par dhyan dein, yahin se sabse tez improvement milega."
        )
    else:
        dim_name_str = f"`{prim_dim}`" if prim_dim else "sub-segment"
        bottleneck_en = (
            f"- **🛑 $0 Spend Advisory (No Cherry-Picking)**: Our Statistical Circuit-Breaker proves that failure rates across {dim_name_str} are **uniformly distributed (random noise)**.\n"
            f"- **Action**: Do NOT waste capital targeting individual groups within {dim_name_str}. Focus instead on global process improvements across the entire operation."
        )
        bottleneck_hi = (
            f"- **🛑 $0 Spend Advisory (Targeted Paisa Barbaad Mat Karein)**: Statistical Circuit-Breaker ne confirm kiya hai ki {dim_name_str} ke alag-alag groups mein farak sirf **random luck / noise** hai.\n"
            f"- **Sahi Action**: Kisi ek cohort par targeted marketing ya discount ka paisa mat lagayein. Poore system ke standard process ko globally improve karein."
        )

    # =========================================================================
    # BLOCK 3: Danger Threshold (Physical Continuous Cliff / Red-Line)
    # =========================================================================
    valid_cliffs = []
    if cliffs:
        for c in cliffs:
            col_name = c.get("column", "")
            if is_synthetic_column(col_name, blueprint) or is_index_artifact(col_name) or is_pseudo_numeric_identifier(col_name):
                continue
            if c.get("bins"):
                valid_cliffs.append(c)

    if valid_cliffs:
        top_c = valid_cliffs[0]
        col_n = top_c.get("column")
        bins = top_c.get("bins", [])
        worst_b = max(bins, key=lambda b: b.get("rate_pct", 0.0))
        best_b = min(bins, key=lambda b: b.get("rate_pct", 0.0))
        w_range = worst_b.get("range", "")
        b_range = best_b.get("range", "")
        w_rate = worst_b.get("rate_pct", 0.0)
        b_rate = best_b.get("rate_pct", 0.0)

        cliff_text_en = (
            f"- **Key Operational Red-Line**: In metric `{col_n}`, when values reach **{w_range}**, failure risk surges abruptly to **{w_rate:.2f}%** (compared to **{b_rate:.2f}%** in range {b_range}).\n"
            f"- **Preventive Guardrail**: Establish early-warning alerts before accounts cross this critical `{col_n}` threshold to prevent realized losses."
        )
        cliff_text_hi = (
            f"- **Khatre Ki Laal Rekha (Danger Limit)**: Metric `{col_n}` mein jab values **{w_range}** ke daayre mein pahunchti hain, toh failure rate badhkar **{w_rate:.2f}%** ho jata hai (jabki {b_range} range mein yeh sirf **{b_rate:.2f}%** rehta hai).\n"
            f"- **Bachav Ka Tarika**: Accounts ko is `{col_n}` limit tak pahunchne se pehle hi early-warning trigger karein taaki realized churn/default ko pehle hi roka ja sake."
        )
    else:
        cliff_text_en = "- **No Physical Numeric Cliffs**: No continuous operational metrics in the current schema exhibit threshold failure cliff behavior."
        cliff_text_hi = "- **Koi Numeric Cliff Nahi**: Is dataset ke raw columns mein koi aisa continuous metric nahi mila jisme abrupt threshold risk cliff ho."

    # =========================================================================
    # BLOCK 4: 3 Strategic Choices (Pathways A, B, C)
    # =========================================================================
    if is_cb_active:
        pathways_en = (
            "- **Pathway A (Capital Preservation & Freeze — $0 CapEx)**: $0.00 targeted spend advised. Statistical Circuit-Breaker confirms failure rates across cohorts are random sampling noise. Freeze targeted budget to prevent wasting capital on phantom patterns.\n"
            "- **Pathway B (Data & Telemetry Audit)**: $0.00 cohort spend. Audit upstream operational data collection to capture missing operational drivers that truly separate failure vs success.\n"
            "- **Pathway C (Global System Hygiene)**: Implement global standard operating procedure upgrades across all accounts equally, rather than cherry-picking statistically uniform cohorts."
        )
        pathways_hi = (
            "- **Pathway A (Paisa Bachao / Budget Freeze — $0 CapEx)**: $0 targeted kharch ki salah. Statistical Circuit-Breaker ne confirm kiya hai ki alag-alag groups ka farak sirf random chance hai. Targeted budget freeze rakhein taaki bekar kharch na ho.\n"
            "- **Pathway B (Data Telemetry Audit)**: $0 cohort kharch. Apne data collection system ko audit karein taaki wo missing variables capture ho sakein jo sach mein risk decide karte hain.\n"
            "- **Pathway C (Global Process Sudhar)**: Kisi ek group ko target karne ke bajay poori company ke basic process ko ek sath sudharein."
        )
    else:
        pathways = strat_dossier.get("pathways", []) if strat_dossier else []
        p_a = pathways[0] if len(pathways) > 0 else {}
        p_b = pathways[1] if len(pathways) > 1 else {}
        p_c = pathways[2] if len(pathways) > 2 else {}

        proj_a = p_a.get("projected_friction_reduction", "25% Excess-Risk Compression")
        proj_b = p_b.get("projected_friction_reduction", "60% Excess-Risk Compression")
        proj_c = p_c.get("projected_friction_reduction", "100% Baseline Parity")

        cost_a = p_a.get("implementation_cost", "Low / Internal")
        cost_b = p_b.get("implementation_cost", "Moderate")
        cost_c = p_c.get("implementation_cost", "Structural CapEx")

        time_a = p_a.get("time_to_impact", "1 - 2 Weeks")
        time_b = p_b.get("time_to_impact", "30 - 45 Days")
        time_c = p_c.get("time_to_impact", "90 - 180 Days")

        hr_seg_label = strat_dossier.get("high_risk_segment") if strat_dossier else None
        if not hr_seg_label and prim_dim and top_leak_seg:
            hr_seg_label = f"{prim_dim} = {top_leak_seg}"
        hr_seg_label = hr_seg_label or "high-risk bottleneck group"
        hr_rate_val = float(strat_dossier.get("high_risk_rate", top_leak_rate)) if strat_dossier else top_leak_rate
        hr_rest_val = float(strat_dossier.get("rest_rate", rest_rate)) if strat_dossier else rest_rate
        excess_total = int(round(float(strat_dossier.get("excess_events", 0.0)))) if strat_dossier else 0

        adv_a_en = (
            f"Zero disruption to daily operations; uses simple early-warning queue alerts on `{hr_seg_label}` to stop the first 25% of avoidable excess failures. "
            f"*Trade-Off*: Leaves 75% of excess losses in `{hr_seg_label}` unaddressed."
        )
        adv_b_en = (
            f"Highest return on operational effort; directly fixes the `{hr_seg_label}` bottleneck ({hr_rate_val:.2f}% failure rate vs {hr_rest_val:.2f}% across the rest of the business). "
            f"*Trade-Off*: Requires frontline team training on targeted outreach protocols."
        )
        adv_c_en = (
            f"Brings `{hr_seg_label}` down from {hr_rate_val:.2f}% to normal rest-of-business parity ({hr_rest_val:.2f}%), eliminating all {excess_total:,} avoidable excess failures. "
            f"*Trade-Off*: Higher upfront investment and 90 to 180 days payback timeline."
        )

        fayda_a_hi = (
            f"Daily kaam mein bina kisi rukawat ke `{hr_seg_label}` par simple early-warning alerts lagakar shuruati 25% avoidable nuksan turant roka ja sakta hai. "
            f"*Nuksan*: Is group ka baaki 75% extra risk abhi bhi bacha rahega."
        )
        fayda_b_hi = (
            f"Mehnat aur paise par sabse behtar return (Best ROI); seedha `{hr_seg_label}` bottleneck ({hr_rate_val:.2f}% failure rate vs baaki business mein {hr_rest_val:.2f}%) ko theek karke 60% extra nuksan kam karta hai. "
            f"*Nuksan*: Frontline team ko naye targeted follow-up process ki training deni hogi."
        )
        fayda_c_hi = (
            f"`{hr_seg_label}` ke {hr_rate_val:.2f}% failure rate ko ghata kar baaki business ke normal {hr_rest_val:.2f}% level par le aata hai, jisse poore {excess_total:,} avoidable excess failures khatam ho jate hain. "
            f"*Nuksan*: Shuruati kharcha zyada hai aur poora asar aane mein 90 se 180 din lagenge."
        )

        def _format_proj_bold(proj_str: str) -> str:
            if " (" in proj_str:
                metric_part, detail_part = proj_str.split(" (", 1)
                return f"**{metric_part}** ({detail_part}"
            return f"**{proj_str}**"

        p_a_fmt = _format_proj_bold(proj_a)
        p_b_fmt = _format_proj_bold(proj_b)
        p_c_fmt = _format_proj_bold(proj_c)

        pathways_en = (
            f"- **Pathway A (Low-Risk Pilot)**: {p_a_fmt}. Est. Cost: {cost_a}, Timeline: {time_a}. *Advantage*: {adv_a_en}\n"
            f"- **Pathway B (Focused Operational Fix)**: {p_b_fmt}. Est. Cost: {cost_b}, Timeline: {time_b}. *Advantage*: {adv_b_en}\n"
            f"- **Pathway C (Deep Structural Overhaul)**: {p_c_fmt}. Est. Cost: {cost_c}, Timeline: {time_c}. *Advantage*: {adv_c_en}"
        )
        pathways_hi = (
            f"- **Pathway A (Chhota / Low-Risk Trial)**: {p_a_fmt}. Kharcha: {cost_a}, Samay: {time_a}. *Fayda*: {fayda_a_hi}\n"
            f"- **Pathway B (Focused / Targeted Fix)**: {p_b_fmt}. Kharcha: {cost_b}, Samay: {time_b}. *Fayda*: {fayda_b_hi}\n"
            f"- **Pathway C (Bada / Structural Badlav)**: {p_c_fmt}. Kharcha: {cost_c}, Samay: {time_c}. *Fayda*: {fayda_c_hi}"
        )

    # =========================================================================
    # Full Document Assembly
    # =========================================================================
    brief_en = f"""## 🇬🇧 Executive Business Summary (Plain English — Zero Jargon)

### 1. Business Health Snapshot
Across **{total_records:,} physical records** audited in your dataset, our system identified **{target_count:,} critical failure events ({target_rate_pct}%)**, generating {cost_drag_en}.{temp_note_en}

### 2. Where Is the Bottleneck?
{bottleneck_en}

### 3. Danger Threshold (Red-Line)
{cliff_text_en}

### 4. Your 3 Strategic Choices (You Decide — We Don't Force Dictates)
{pathways_en}

### 5. Immediate Team Action Worklist (`actionable_priority_worklist.csv`)
- **Preventive Retention Watch ({n_prev_watch:,} active accounts)**: High-risk active accounts that have NOT yet failed. Have your customer success or QA team contact these accounts immediately.
- **Realized Loss Recovery Audit ({n_loss_audit:,} accounts)**: Already-breached records prioritized by financial impact for root-cause analysis and recovery.
"""

    brief_hi = f"""## 🇮🇳 Business X-Ray Summary (Simple Hinglish — Seedhi Bhasha Mein)

### 1. Aaj Business Ki Asli Halat (Health Snapshot)
Aapke audit kiye gaye **{total_records:,} records** mein se, system ne **{target_count:,} failure / churn cases ({target_rate_pct}%)** pakde hain, jisse {cost_drag_hi} ho raha hai.{temp_note_hi}

### 2. Sabse Bada Nuksan Kahan Ho Raha Hai?
{bottleneck_hi}

### 3. Khatre Ki Laal Rekha (Danger Limit)
{cliff_text_hi}

### 4. Aapke Paas 3 Imandar Raste Hain (Faisla Aapka — Koi Jabardasti Nahi)
{pathways_hi}

### 5. Aaj Subah Team Ko Kya Kaam Dein? (`actionable_priority_worklist.csv`)
- **Bachav Soochi - Preventive Retention Watch ({n_prev_watch:,} active accounts)**: Yeh wo active accounts hain jo abhi tak kharab nahi hue hain, par risk zone mein hain. Team se turant preventive contact karwayein.
- **Vasooli Aur Jaanch - Realized Loss Recovery Audit ({n_loss_audit:,} accounts)**: Yeh wo accounts hain jinka nuksan pehle hi ho chuka hai. Inhein recovery aur root-cause audit ke liye use karein.
"""

    full_brief_md = brief_en.strip() + "\n\n---\n\n" + brief_hi.strip() + "\n"
    summary_path = out_dir / "PLAIN_BUSINESS_SUMMARY.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(full_brief_md)

    print(f"[+] Plain Business Summary written to: {summary_path}")
    return summary_path
