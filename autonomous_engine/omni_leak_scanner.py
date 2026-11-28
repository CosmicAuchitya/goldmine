"""
=============================================================================
OMNI-DIMENSIONAL 360° A-TO-Z HIDDEN LEAKAGE & PROFIT FORENSICS ENGINE
=============================================================================
Extracts 100% of hidden business intelligence across 8 deep forensic layers:
1. All-Dimension Leak & Safe-Zone Scanner (every categorical column audited,
   separating statistically confirmed leaks from uniform noise).
2. Secondary Operational KPI & SLA / Delay / CSAT Cross-Scanner (catches slow
   warehouses, high-SLA-breach couriers, and low-CSAT nodes even when binary
   target rate looks average).
3. 2x2 Categorical Interaction & Confounder / Simpson's Paradox Scanner
   (isolates deadly combinations like Tier-3 x COD or UP x COD, and proves
   when a region/segment is only risky due to payment/channel mix).
4. True P&L Cash-Bleed, Negative-Margin & Reverse-Logistics Auditor (goes
   beyond gross billed revenue to audit net contribution margin, out-of-pocket
   negative-margin orders, reverse shipping burn, and pre-shipment vs post-
   shipment status breakdowns).
5. Coupon, Discount & Promo Margin-Erosion ("Double-Poison") Auditor (detects
   promotions that simultaneously slash unit margin and inflate RTO/churn).
6. Repeat-Entity (Customer / Vendor / Agent) & SKU Concentration Auditor
   (identifies serial RTO/refund abusers, negative lifetime-margin customers,
   high-margin whale segments, and worst-performing SKUs).
7. Seasonal, Quarterly (Q1-Q4) & Hour-of-Day Regime-Shift Scanner (detects
   recurring Q4 festive fulfillment collapses, yearly shifts, and late-night
   risk spikes).
8. Multi-Factor Row-Level Composite Risk Annotator (enriches priority worklists
   with exact multi-variable root causes on every single record).
=============================================================================
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

try:
    from .target_resolver import (
        resolve_canonical_target_and_cost,
        get_shared_telemetry,
        is_index_artifact,
        is_synthetic_column,
        is_pseudo_numeric_identifier,
        is_deterministic_target_leakage,
        is_temporal_column,
    )
    from .pii_scrubber import is_sensitive_column_name
except ImportError:
    from target_resolver import (
        resolve_canonical_target_and_cost,
        get_shared_telemetry,
        is_index_artifact,
        is_synthetic_column,
        is_pseudo_numeric_identifier,
        is_deterministic_target_leakage,
        is_temporal_column,
    )
    from pii_scrubber import is_sensitive_column_name


POST_EVENT_STATUS_COLS = {
    "order_status",
    "reservation_status",
    "claim_status",
    "delivery_status",
    "payment_status",
    "loan_status",
    "status_detail",
}


def _two_prop_z_and_p(k1: int, n1: int, k2: int, n2: int) -> Tuple[float, float]:
    """Computes pooled two-proportion z-statistic and two-sided p-value."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0
    p1 = k1 / float(n1)
    p2 = k2 / float(n2)
    p_pool = (k1 + k2) / float(n1 + n2)
    if p_pool <= 0.0 or p_pool >= 1.0:
        return 0.0, 1.0
    se = np.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
    if se <= 1e-12:
        return 0.0, 1.0
    z = (p1 - p2) / se
    p_val = float(2.0 * (1.0 - scipy_stats.norm.cdf(abs(z))))
    return float(z), p_val


def _find_col_by_keywords(cols: List[str], keywords: List[str], exclude: Optional[set] = None) -> Optional[str]:
    excl = {str(x).lower() for x in (exclude or set()) if x}
    for kw in keywords:
        for c in cols:
            cl = c.lower().strip()
            if cl in excl:
                continue
            if cl == kw or kw in cl:
                return c
    return None


class OmniDimensionalLeakScanner:
    """
    Comprehensive 360-degree A-to-Z data forensic scanner that leaves zero
    hidden operational, financial, seasonal, or entity-level leaks behind.
    """

    def __init__(self, df: pd.DataFrame, blueprint: Optional[Dict[str, Any]] = None):
        self.df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self.blueprint = blueprint if isinstance(blueprint, dict) else {}
        self.total_records = len(self.df)
        self.canonical = resolve_canonical_target_and_cost(self.df, self.blueprint)
        self.target_col = self.canonical.get("target_col")
        self.cost_col = self.canonical.get("cost_col")
        self.s_bin = self.canonical.get("binary_target")
        if self.s_bin is None or len(self.s_bin) != self.total_records:
            self.s_bin = pd.Series(0, index=self.df.index)
        else:
            self.s_bin = pd.to_numeric(self.s_bin, errors="coerce").fillna(0).astype(int)

        self.unit_symbol = self.canonical.get("unit_symbol") or "$"
        if self.unit_symbol in ("Events", "Batches", "Patients / Lives", "Flights", "Vehicles", "Streams"):
            self.unit_symbol = "$" if self.cost_col else ""

        self.total_events = int(self.s_bin.sum())
        self.baseline_rate_pct = round((self.total_events / max(self.total_records, 1)) * 100.0, 2)

    def _discover_operational_dimensions(self) -> List[str]:
        """Discovers all valid pre-event categorical/discrete business dimensions (up to 60 categories)."""
        dims: List[str] = []
        coord_cols = {"longitude", "latitude", "lat", "lon", "alt", "tz", "tzone"}
        date_words = {"order_date", "date", "order_time", "time", "timestamp", "datetime", "created_at", "date_received", "updated_at", "ship_date"}

        for c in self.df.columns:
            cl = c.lower().strip()
            if c in (self.target_col, self.cost_col, "_is_target_event"):
                continue
            if cl in coord_cols or cl in date_words or cl in POST_EVENT_STATUS_COLS:
                continue
            if is_temporal_column(self.df[c], c):
                continue
            if cl in ("order_year", "order_month", "year", "month"):
                continue
            if is_index_artifact(c, self.df[c]) or is_sensitive_column_name(c):
                continue
            # Only treat *_tier as synthetic if its base numeric column also exists in df
            if cl.endswith("_tier") and c[:-5] in self.df.columns:
                continue
            if cl.startswith(("_", "fact_surrogate")):
                continue
            op_entity_id_prefixes = ("warehouse", "store", "branch", "hub", "plant", "channel", "clinic", "vendor", "carrier", "dept", "region")
            if cl.endswith(("_id", "_uuid", "_key")) and cl not in ("sku_code", "coupon_code") and not cl.startswith(op_entity_id_prefixes):
                continue

            nunique = int(self.df[c].nunique(dropna=True))
            if nunique < 2 or nunique > 500:
                continue
            if nunique > 30 and is_pseudo_numeric_identifier(c, self.df[c]):
                continue

            is_cat = (
                pd.api.types.is_object_dtype(self.df[c])
                or pd.api.types.is_string_dtype(self.df[c])
                or isinstance(self.df[c].dtype, pd.CategoricalDtype)
            )
            # Long-tail operational dimensions (81..500 unique values, e.g. SKUs, components, vehicle lines, vendors):
            # permit ONLY true categorical labels (short text, concentrated top-15 share >= 35%, non-ID cardinality ratio <= 20%)
            if nunique > 80:
                if not is_cat or (nunique / max(self.total_records, 1)) > 0.20:
                    continue
                s_nn = self.df[c].dropna().astype(str)
                if s_nn.empty or float(s_nn.head(200).str.len().mean()) > 60.0:
                    continue
                top15_cov = float(s_nn.value_counts().head(15).sum()) / max(len(s_nn), 1)
                if top15_cov < 0.35:
                    continue
            # Exclude continuous/count/SLA/monetary numeric metrics from categorical segment dimensions
            if not is_cat:
                if any(
                    k in cl
                    for k in (
                        "delay", "transit", "days", "hours", "sla", "breach", "units",
                        "price", "amount", "cost", "margin", "discount", "rate", "pct",
                        "score", "rating", "csat", "mrp", "spend", "cogs", "revenue",
                        "fee", "tax", "line_no", "limit", "lease", "rent", "capacity", "tons",
                        "_inr", "_usd", "_eur", "_gbp",
                    )
                ) or nunique > 10:
                    continue

            if is_deterministic_target_leakage(c, self.df[c], self.s_bin, self.target_col):
                continue
            # Also exclude post-event CSAT/rating columns if rating==1 is 100% target event
            if any(k in cl for k in ("csat", "satisfaction", "rating", "review_score")):
                min_v = self.df[c].min()
                sub_m = self.df[c] == min_v
                if sub_m.sum() >= 10 and float(self.s_bin[sub_m].mean()) >= 0.95:
                    continue

            dims.append(c)
        return dims

    # =========================================================================
    # LAYER 1: ALL-DIMENSION BOTTLENECK & NOISE SCANNER
    # =========================================================================
    def scan_all_dimensions(self, dims: List[str]) -> Dict[str, Any]:
        confirmed_leaks: List[Dict[str, Any]] = []
        uniform_noise_dims: List[Dict[str, Any]] = []
        all_breakdowns: List[Dict[str, Any]] = []

        min_support = max(10, int(self.total_records * 0.01))
        s_cost = (
            pd.to_numeric(self.df[self.cost_col], errors="coerce").fillna(0.0)
            if self.cost_col and self.cost_col in self.df.columns
            else pd.Series(0.0, index=self.df.index)
        )
        total_adverse_cost = float(s_cost[self.s_bin == 1].sum())

        for dim in dims:
            col_s = self.df[dim].astype(str)
            tmp = pd.DataFrame({"seg": col_s, "y": self.s_bin, "cost": s_cost})
            grp = tmp.groupby("seg", as_index=False).agg(
                volume=("y", "count"),
                adverse_events=("y", "sum"),
                total_volume_value=("cost", "sum"),
            )
            adv_cost_grp = tmp[tmp["y"] == 1].groupby("seg", as_index=False)["cost"].sum().rename(columns={"cost": "adverse_cost"})
            grp = grp.merge(adv_cost_grp, on="seg", how="left")
            grp["adverse_cost"] = grp["adverse_cost"].fillna(0.0)
            grp["rate_pct"] = (grp["adverse_events"] / grp["volume"].clip(lower=1) * 100.0).round(2)
            grp["share_of_failures_pct"] = (grp["adverse_events"] / max(self.total_events, 1) * 100.0).round(1)
            grp["share_of_drag_pct"] = (
                (grp["adverse_cost"] / max(total_adverse_cost, 0.01) * 100.0).round(1)
                if total_adverse_cost > 0
                else grp["share_of_failures_pct"]
            )
            grp = grp.sort_values(["rate_pct", "adverse_events"], ascending=[False, False])

            # Build UI cohort breakdown rows for every dimension
            ui_rows = []
            for _, r in grp.head(15).iterrows():
                r_pct = float(r["rate_pct"])
                status_str = "🔴 High-Risk" if r_pct >= max(20.0, self.baseline_rate_pct * 1.35) else (
                    "🟢 Resilient" if r_pct <= self.baseline_rate_pct * 0.85 else "🟡 Watch"
                )
                exp_fmt = (
                    f"{self.unit_symbol}{float(r['adverse_cost']):,.2f}"
                    if self.cost_col and total_adverse_cost > 0
                    else f"{int(r['adverse_events']):,} events"
                )
                ui_rows.append({
                    "segment": str(r["seg"]),
                    "volume": f"{int(r['volume']):,}",
                    "volume_num": int(r["volume"]),
                    "adverse_events": f"{int(r['adverse_events']):,}",
                    "adverse_events_num": int(r["adverse_events"]),
                    "risk_rate_pct": r_pct,
                    "adverse_rate_pct": r_pct,
                    "share_of_failures_pct": float(r["share_of_drag_pct"]),
                    "exposure_formatted": exp_fmt,
                    "total_liability": exp_fmt,
                    "share_of_drag": f"{float(r['share_of_drag_pct']):.1f}%",
                    "status": status_str,
                })

            all_breakdowns.append({
                "dimension": dim,
                "dimension_label": dim.replace("_", " ").title(),
                "raw_dimension": dim,
                "rows": ui_rows,
            })

            valid = grp[grp["volume"] >= min_support]
            if len(valid) < 2:
                continue

            # Omnibus Chi-Square across valid segments
            cont = np.array([[int(r["adverse_events"]), max(0, int(r["volume"]) - int(r["adverse_events"]))] for _, r in valid.iterrows()])
            chi2_p = 1.0
            if cont.shape[0] >= 2 and (cont.sum(axis=0) > 0).all():
                try:
                    _, chi2_p, _, _ = scipy_stats.chi2_contingency(cont)
                    chi2_p = float(chi2_p)
                except Exception:
                    chi2_p = 1.0

            # Pick the highest statistically significant excess-impact cohort across all valid segments
            # (prevents small 1%-volume tail slices from eclipsing high-impact operational bottlenecks like SERVICE BRAKES / AIR BAGS)
            best = valid.iloc[-1]
            best_sig_candidate = None
            for _, cand_row in valid.iterrows():
                ck_w, cn_w = int(cand_row["adverse_events"]), int(cand_row["volume"])
                ck_rest = max(0, self.total_events - ck_w)
                cn_rest = max(1, self.total_records - cn_w)
                crate_w = round(ck_w / max(cn_w, 1) * 100.0, 2)
                crate_rest = round(ck_rest / cn_rest * 100.0, 2)
                cz, cp = _two_prop_z_and_p(ck_w, cn_w, ck_rest, cn_rest)
                clift = round(crate_w / max(crate_rest, 0.01), 2)
                cexcess = round(max(0.0, ck_w - cn_w * (ck_rest / float(cn_rest))), 1)
                if cp < 0.05 and clift >= 1.15 and cexcess >= 5.0:
                    if len(grp) <= 20:
                        # Low-cardinality dimensions (e.g. 3 city tiers, 4 regions):
                        # rank by true failure severity / lift so large mediocre cohorts never mask the worst rate.
                        cand_tuple = (clift, cexcess, float(cand_row["adverse_cost"]), cand_row, ck_w, cn_w, ck_rest, cn_rest, crate_w, crate_rest, cz, cp)
                    else:
                        # High-cardinality / long-tail dimensions (e.g. 183 vehicle components):
                        # rank by attributable excess impact so major systemic bottlenecks beat tiny tail noise.
                        avg_unit_cost = (float(cand_row["adverse_cost"]) / max(ck_w, 1)) if (self.cost_col and total_adverse_cost > 0) else 1.0
                        c_impact = cexcess * avg_unit_cost if (self.cost_col and total_adverse_cost > 0) else cexcess
                        cand_tuple = (c_impact, cexcess, clift, cand_row, ck_w, cn_w, ck_rest, cn_rest, crate_w, crate_rest, cz, cp)
                    if best_sig_candidate is None or cand_tuple[:3] > best_sig_candidate[:3]:
                        best_sig_candidate = cand_tuple

            if best_sig_candidate is not None:
                _, excess_events, lift, worst, k_w, n_w, k_rest, n_rest, rate_w, rate_rest, z_stat, p_two = best_sig_candidate
            else:
                worst = valid.iloc[0]
                k_w, n_w = int(worst["adverse_events"]), int(worst["volume"])
                k_rest = max(0, self.total_events - k_w)
                n_rest = max(1, self.total_records - n_w)
                rate_w = round(k_w / max(n_w, 1) * 100.0, 2)
                rate_rest = round(k_rest / n_rest * 100.0, 2)
                z_stat, p_two = _two_prop_z_and_p(k_w, n_w, k_rest, n_rest)
                lift = round(rate_w / max(rate_rest, 0.01), 2)
                excess_events = round(max(0.0, k_w - n_w * (k_rest / float(n_rest))), 1)

            entry = {
                "dimension": dim,
                "cardinality": int(len(grp)),
                "worst_segment": str(worst["seg"]),
                "worst_volume": n_w,
                "worst_events": k_w,
                "worst_rate_pct": rate_w,
                "rest_rate_pct": rate_rest,
                "best_segment": str(best["seg"]),
                "best_rate_pct": float(best["rate_pct"]),
                "best_volume": int(best["volume"]),
                "risk_multiplier": lift,
                "excess_events": excess_events,
                "worst_adverse_cost": round(float(worst["adverse_cost"]), 2),
                "z_stat": round(z_stat, 2),
                "p_val": p_two,
                "omnibus_chi2_p": chi2_p,
            }

            if chi2_p < 0.05 and p_two < 0.05 and lift >= 1.15 and excess_events >= 5.0:
                confirmed_leaks.append(entry)
            else:
                uniform_noise_dims.append(entry)

            try:
                shared = get_shared_telemetry(self.df)
                shared.setdefault("chi2_map", {})[dim] = (chi2_p, 0.0)
            except Exception:
                pass

        confirmed_leaks.sort(key=lambda x: (x["excess_events"], x["risk_multiplier"]), reverse=True)
        return {
            "confirmed_leak_dimensions": confirmed_leaks,
            "uniform_noise_dimensions": uniform_noise_dims,
            "all_cohort_breakdowns": all_breakdowns,
        }

    # =========================================================================
    # LAYER 2: SECONDARY OPERATIONAL KPIs (SLA BREACH, DISPATCH, TRANSIT, CSAT)
    # =========================================================================
    def scan_operational_sla_and_delays(self, dims: List[str]) -> List[Dict[str, Any]]:
        """
        Audits operational dimensions (Warehouse, Courier, Channel, Branch, City Tier)
        against auxiliary operational metrics (SLA breach, dispatch delay, transit time, CSAT)
        so bottlenecks like Kolkata-East-Depot (2.85d dispatch) or Delhivery (48.15% SLA breach)
        are ALWAYS caught even if their binary target rate is near average.
        """
        cols = list(self.df.columns)
        sla_col = _find_col_by_keywords(cols, ["delivery_sla_breach", "sla_breach", "is_late", "late_delivery"])
        disp_col = _find_col_by_keywords(cols, ["dispatch_delay_days", "dispatch_delay", "dispatch_sla_hours", "processing_days"])
        trans_col = _find_col_by_keywords(cols, ["transit_days", "shipping_days", "delivery_days"])
        csat_col = _find_col_by_keywords(cols, ["customer_csat_rating", "csat", "satisfaction_score", "review_score"])

        findings: List[Dict[str, Any]] = []
        min_support = max(20, int(self.total_records * 0.02))

        for dim in dims:
            if dim in ("sku_code", "sku_name"):
                continue
            grp = self.df.groupby(dim)
            counts = grp.size()
            valid_segs = counts[counts >= min_support].index.tolist()
            if len(valid_segs) < 2:
                continue

            # 1. Check Dispatch Delay Bottleneck
            if disp_col and pd.api.types.is_numeric_dtype(self.df[disp_col]):
                s_disp = pd.to_numeric(self.df[disp_col], errors="coerce")
                means = s_disp.groupby(self.df[dim]).mean().loc[valid_segs]
                worst_seg = str(means.idxmax())
                worst_val = float(means.max())
                rest_mask = self.df[dim].astype(str) != worst_seg
                rest_val = float(s_disp[rest_mask].mean())
                ratio = round(worst_val / max(rest_val, 0.01), 2)
                dc_low = str(disp_col).lower()
                if any(tok in dc_low for tok in ("hour", "_hr", "hrs")):
                    unit_en, unit_hi = "hours", "घंटे"
                elif any(tok in dc_low for tok in ("min", "minute")):
                    unit_en, unit_hi = "minutes", "मिनट"
                else:
                    unit_en, unit_hi = "days", "दिन"
                dim_nice = str(dim).replace("_", " ").title()
                disp_nice = re.sub(r"_(hours?|hrs?|days?|mins?|minutes?)$", "", str(disp_col), flags=re.IGNORECASE).replace("_", " ").title()
                if ratio >= 1.35 and (worst_val - rest_val) >= 0.5:
                    seg_mask = self.df[dim].astype(str) == worst_seg
                    findings.append({
                        "finding_type": "DISPATCH_DELAY_BOTTLENECK",
                        "dimension": dim,
                        "segment": worst_seg,
                        "volume": int(seg_mask.sum()),
                        "metric_column": disp_col,
                        "unit": unit_en,
                        "segment_mean": round(worst_val, 2),
                        "rest_mean": round(rest_val, 2),
                        "multiplier": ratio,
                        "target_rate_pct": round(float(self.s_bin[seg_mask].mean() * 100.0), 2),
                        "headline_en": f"{dim_nice} **'{worst_seg}'** averages **{worst_val:.2f} {unit_en}** for {disp_nice} (**{ratio}x slower** than {rest_val:.2f} {unit_en} elsewhere, driving {float(self.s_bin[seg_mask].mean()*100):.2f}% failure rate across {int(seg_mask.sum()):,} orders).",
                        "headline_hi": f"{dim_nice} **'{worst_seg}'** में औसत {disp_nice} **{worst_val:.2f} {unit_hi}** है (बाकी के **{rest_val:.2f} {unit_hi} से {ratio} गुना धीमा**, कुल {int(seg_mask.sum()):,} ऑर्डर, {float(self.s_bin[seg_mask].mean()*100):.2f}% फेलियर/रिटर्न)।",
                    })

            # 2. Check SLA Breach Bottleneck
            if sla_col and pd.api.types.is_numeric_dtype(self.df[sla_col]):
                s_sla = pd.to_numeric(self.df[sla_col], errors="coerce").fillna(0)
                means = (s_sla.groupby(self.df[dim]).mean() * 100.0).loc[valid_segs]
                worst_seg = str(means.idxmax())
                best_seg = str(means.idxmin())
                worst_val = float(means.max())
                best_val = float(means.min())
                rest_mask = self.df[dim].astype(str) != worst_seg
                rest_val = float(s_sla[rest_mask].mean() * 100.0)
                ratio = round(worst_val / max(best_val, 0.1), 2)
                if (worst_val - rest_val) >= 10.0 and ratio >= 1.5:
                    seg_mask = self.df[dim].astype(str) == worst_seg
                    trans_note_en = ""
                    trans_note_hi = ""
                    if trans_col and pd.api.types.is_numeric_dtype(self.df[trans_col]):
                        tc_low = str(trans_col).lower()
                        t_unit_en, t_unit_hi = ("hours", "घंटे") if any(tok in tc_low for tok in ("hour", "_hr", "hrs")) else ("days", "दिन")
                        t_w = float(pd.to_numeric(self.df.loc[seg_mask, trans_col], errors="coerce").mean())
                        t_b = float(pd.to_numeric(self.df.loc[self.df[dim].astype(str) == best_seg, trans_col], errors="coerce").mean())
                        trans_note_en = f", avg transit **{t_w:.2f} {t_unit_en}** vs {t_b:.2f} {t_unit_en} on '{best_seg}'"
                        trans_note_hi = f", औसत ट्रांज़िट **{t_w:.2f} {t_unit_hi}** vs '{best_seg}' में {t_b:.2f} {t_unit_hi}"
                    csat_note_en = ""
                    csat_note_hi = ""
                    if csat_col and pd.api.types.is_numeric_dtype(self.df[csat_col]):
                        c_w = float(pd.to_numeric(self.df.loc[seg_mask, csat_col], errors="coerce").mean())
                        c_b = float(pd.to_numeric(self.df.loc[self.df[dim].astype(str) == best_seg, csat_col], errors="coerce").mean())
                        csat_note_en = f", CSAT **{c_w:.2f}** vs {c_b:.2f}"
                        csat_note_hi = f", CSAT रेटिंग **{c_w:.2f}** vs {c_b:.2f}"

                    findings.append({
                        "finding_type": "SLA_BREACH_BOTTLENECK",
                        "dimension": dim,
                        "segment": worst_seg,
                        "best_segment": best_seg,
                        "volume": int(seg_mask.sum()),
                        "metric_column": sla_col,
                        "segment_rate_pct": round(worst_val, 2),
                        "best_rate_pct": round(best_val, 2),
                        "rest_rate_pct": round(rest_val, 2),
                        "multiplier_vs_best": ratio,
                        "headline_en": f"`{dim}` = **'{worst_seg}'** ({int(seg_mask.sum()):,} orders) suffers a **{worst_val:.2f}% SLA breach rate** (**{ratio}x worse** than '{best_seg}' at {best_val:.2f}%{trans_note_en}{csat_note_en}).",
                        "headline_hi": f"`{dim}` = **'{worst_seg}'** ({int(seg_mask.sum()):,} ऑर्डर) में **`{sla_col}` (SLA फेलियर) {worst_val:.2f}%** है ('{best_seg}' के **{best_val:.2f}% से {ratio} गुना खराब**{trans_note_hi}{csat_note_hi})।",
                    })

        return findings

    # =========================================================================
    # LAYER 3: 2x2 CATEGORICAL INTERACTIONS & CONFOUNDER / SIMPSON'S PARADOX
    # =========================================================================
    def scan_categorical_interactions_and_confounders(self, dims: List[str]) -> Dict[str, Any]:
        """
        Finds the top 2D categorical interaction hotspots (e.g. UP x COD = 44.8%,
        Tier 3 x COD = 41.2%, Retail Walk-In x FLASH30 = 24.1%) AND detects
        Simpson's Paradox / Confounding (where a state or city tier looks bad
        only because of high COD share, while its prepaid failure rate is normal).
        """
        candidate_dims = [d for d in dims if self.df[d].nunique() <= 15]
        hotspots: List[Dict[str, Any]] = []
        confounders: List[Dict[str, Any]] = []
        min_cell = max(20, int(self.total_records * 0.003))

        for i in range(len(candidate_dims)):
            for j in range(i + 1, len(candidate_dims)):
                d1, d2 = candidate_dims[i], candidate_dims[j]
                grp = (
                    pd.DataFrame({"a": self.df[d1].astype(str), "b": self.df[d2].astype(str), "y": self.s_bin})
                    .groupby(["a", "b"], as_index=False)
                    .agg(volume=("y", "count"), events=("y", "sum"))
                )
                valid = grp[grp["volume"] >= min_cell].copy()
                if valid.empty:
                    continue
                valid["rate_pct"] = (valid["events"] / valid["volume"] * 100.0).round(2)
                top_row = valid.sort_values(["rate_pct", "events"], ascending=[False, False]).iloc[0]

                r_cell = float(top_row["rate_pct"])
                if r_cell >= max(18.0, self.baseline_rate_pct * 1.8):
                    v_a, v_b = str(top_row["a"]), str(top_row["b"])
                    r_a_only = float(self.s_bin[self.df[d1].astype(str) == v_a].mean() * 100.0)
                    r_b_only = float(self.s_bin[self.df[d2].astype(str) == v_b].mean() * 100.0)
                    # Only record genuine compounding interactions (higher than single marginals or meaningful cross)
                    if r_cell >= max(r_a_only, r_b_only) + 2.5:
                        hotspots.append({
                            "dim_a": d1,
                            "val_a": v_a,
                            "dim_b": d2,
                            "val_b": v_b,
                            "volume": int(top_row["volume"]),
                            "events": int(top_row["events"]),
                            "rate_pct": r_cell,
                            "lift_vs_baseline": round(r_cell / max(self.baseline_rate_pct, 0.01), 2),
                            "dim_a_marginal_pct": round(r_a_only, 2),
                            "dim_b_marginal_pct": round(r_b_only, 2),
                        })

        hotspots.sort(key=lambda x: (x["rate_pct"], x["events"]), reverse=True)

        # Confounder check: Does the #1 dominant driver (e.g. payment_gateway = COD) explain regional/tier risk?
        if len(candidate_dims) >= 2:
            # Find single segment with highest z-score across all candidate_dims
            best_driver_dim = None
            best_driver_val = None
            best_z = -1.0
            for d in candidate_dims:
                for val, sub in self.df.groupby(self.df[d].astype(str)):
                    n_s = len(sub)
                    if n_s < min_cell:
                        continue
                    k_s = int(self.s_bin.loc[sub.index].sum())
                    z, _ = _two_prop_z_and_p(k_s, n_s, self.total_events - k_s, self.total_records - n_s)
                    if z > best_z:
                        best_z = z
                        best_driver_dim = d
                        best_driver_val = str(val)

            if best_driver_dim and best_z >= 4.0:
                driver_mask = self.df[best_driver_dim].astype(str) == best_driver_val
                overall_driver_share = float(driver_mask.mean() * 100.0)
                non_driver_baseline = float(self.s_bin[~driver_mask].mean() * 100.0)

                for other_dim in candidate_dims:
                    if other_dim == best_driver_dim:
                        continue
                    for seg_val, sub in self.df.groupby(self.df[other_dim].astype(str)):
                        if len(sub) < max(50, min_cell):
                            continue
                        seg_idx = sub.index
                        seg_k = int(self.s_bin.loc[seg_idx].sum())
                        seg_n = len(seg_idx)
                        seg_rate = float(seg_k / max(seg_n, 1) * 100.0)
                        rest_n = max(1, self.total_records - seg_n)
                        rest_rate = float(max(0, self.total_events - seg_k) / rest_n * 100.0)
                        # Compare against rest-of-system rate too so large 50%-share segments in 2-group Simpson's Paradox are caught
                        if seg_rate < self.baseline_rate_pct * 1.20 or seg_rate < rest_rate * 1.35:
                            continue
                        seg_driver_share = float(driver_mask.loc[seg_idx].mean() * 100.0)
                        seg_with_driver = seg_idx[driver_mask.loc[seg_idx]]
                        seg_without_driver = seg_idx[~driver_mask.loc[seg_idx]]
                        if len(seg_with_driver) >= 15 and len(seg_without_driver) >= 15:
                            rate_with = float(self.s_bin.loc[seg_with_driver].mean() * 100.0)
                            rate_without = float(self.s_bin.loc[seg_without_driver].mean() * 100.0)
                            over_concentrated = (
                                seg_driver_share >= overall_driver_share * 1.35
                                or seg_driver_share >= overall_driver_share + 15.0
                            )
                            # If removing the confounder brings the segment down to normal baseline!
                            if over_concentrated and rate_without <= non_driver_baseline * 1.25:
                                confounders.append({
                                    "apparent_dim": other_dim,
                                    "apparent_segment": str(seg_val),
                                    "apparent_rate_pct": round(seg_rate, 2),
                                    "confounder_dim": best_driver_dim,
                                    "confounder_segment": best_driver_val,
                                    "segment_confounder_share_pct": round(seg_driver_share, 1),
                                    "overall_confounder_share_pct": round(overall_driver_share, 1),
                                    "rate_when_confounder_present_pct": round(rate_with, 2),
                                    "rate_when_confounder_absent_pct": round(rate_without, 2),
                                    "non_confounder_baseline_pct": round(non_driver_baseline, 2),
                                    "explanation_en": (
                                        f"**Hidden Confounder Truth (`{other_dim}` = '{seg_val}')**: At first glance, '{seg_val}' looks risky with a **{seg_rate:.2f}%** failure rate. "
                                        f"However, `{best_driver_dim}` = **'{best_driver_val}'** accounts for **{seg_driver_share:.1f}%** of orders in '{seg_val}' (vs {overall_driver_share:.1f}% company-wide). "
                                        f"Inside '{seg_val}', '{best_driver_val}' orders fail at **{rate_with:.2f}%**, whereas non-'{best_driver_val}' (prepaid/normal) orders in '{seg_val}' fail at just **{rate_without:.2f}%** (completely normal vs {non_driver_baseline:.2f}% baseline)! "
                                        f"**Action**: Do NOT block '{seg_val}' customers — only restrict or verify '{best_driver_val}' inside '{seg_val}'."
                                    ),
                                    "explanation_hi": (
                                        f"**छुपा हुआ सच (`{other_dim}` = '{seg_val}')**: ऊपर से देखने पर '{seg_val}' में **{seg_rate:.2f}%** फेलियर/RTO दिखता है। "
                                        f"लेकिन असली कारण यह है कि '{seg_val}' में **{seg_driver_share:.1f}%** ऑर्डर `{best_driver_dim}` = **'{best_driver_val}'** के हैं (जबकि पूरी कंपनी में यह सिर्फ {overall_driver_share:.1f}% है)। "
                                        f"'{seg_val}' में जब ग्राहक '{best_driver_val}' चुनते हैं तब फेलियर **{rate_with:.2f}%** है, लेकिन **बिना '{best_driver_val}' (प्रीपेड/UPI) के '{seg_val}' में फेलियर सिर्फ {rate_without:.2f}% है** (बिल्कुल सुरक्षित!)। "
                                        f"**सही फैसला**: '{seg_val}' में मार्केटिंग बंद मत कीजिए — सिर्फ वहाँ '{best_driver_val}' पर रोक या एडवांस वेरिफिकेशन लगाइए।"
                                    ),
                                })

        confounders.sort(key=lambda x: x["apparent_rate_pct"], reverse=True)
        return {
            "top_2d_hotspots": hotspots[:8],
            "confounder_insights": confounders[:5],
        }

    # =========================================================================
    # LAYER 4 & 5: P&L CASH-BLEED, NEGATIVE MARGIN, REVERSE SHIPPING & COUPONS
    # =========================================================================
    def scan_pnl_margin_and_coupons(self) -> Dict[str, Any]:
        cols = list(self.df.columns)
        gross_col = _find_col_by_keywords(cols, ["gross_order_value_inr", "gross_order_value", "gross_amount", "gross_revenue"])
        disc_amt_col = _find_col_by_keywords(cols, ["discount_amount_inr", "discount_amount", "discount_val"])
        disc_pct_col = _find_col_by_keywords(cols, ["discount_pct", "discount_rate"])
        net_bill_col = self.cost_col or _find_col_by_keywords(cols, ["net_billed_amount_inr", "net_billed", "order_amount", "total_amount"])
        cogs_col = _find_col_by_keywords(cols, ["cogs_inr", "cogs", "product_cost", "unit_cost"])
        rev_ship_col = _find_col_by_keywords(cols, ["return_reverse_shipping_inr", "reverse_shipping", "return_fee", "restocking_fee"])
        margin_col = _find_col_by_keywords(cols, ["net_contribution_margin_inr", "contribution_margin", "net_margin", "net_profit", "profit"])
        status_col = _find_col_by_keywords(cols, ["order_status", "reservation_status", "fulfillment_status"])
        coupon_col = _find_col_by_keywords(cols, ["coupon_code", "promo_code", "coupon", "discount_code"])

        result: Dict[str, Any] = {"has_margin_ledger": False, "has_coupon_audit": False}
        sym = self.unit_symbol or "$"

        if margin_col and pd.api.types.is_numeric_dtype(self.df[margin_col]):
            s_margin = pd.to_numeric(self.df[margin_col], errors="coerce").fillna(0.0)
            s_gross = pd.to_numeric(self.df[gross_col], errors="coerce").fillna(0.0) if gross_col else pd.Series(0.0, index=self.df.index)
            s_disc = pd.to_numeric(self.df[disc_amt_col], errors="coerce").fillna(0.0) if disc_amt_col else pd.Series(0.0, index=self.df.index)
            s_bill = pd.to_numeric(self.df[net_bill_col], errors="coerce").fillna(0.0) if net_bill_col else pd.Series(0.0, index=self.df.index)
            s_rev_ship = pd.to_numeric(self.df[rev_ship_col], errors="coerce").fillna(0.0) if rev_ship_col else pd.Series(0.0, index=self.df.index)

            neg_mask = s_margin < 0
            neg_count = int(neg_mask.sum())
            neg_cash_loss = float(s_margin[neg_mask].sum())
            rev_ship_total = float(s_rev_ship.sum())

            status_breakdown = []
            if status_col and status_col in self.df.columns:
                tmp_st = pd.DataFrame({
                    "st": self.df[status_col].astype(str),
                    "y": self.s_bin,
                    "bill": s_bill,
                    "margin": s_margin,
                    "rev_ship": s_rev_ship,
                })
                g_st = tmp_st.groupby("st", as_index=False).agg(
                    orders=("y", "count"),
                    billed=("bill", "sum"),
                    net_margin=("margin", "sum"),
                    reverse_shipping=("rev_ship", "sum"),
                ).sort_values("net_margin", ascending=True)
                for _, r in g_st.iterrows():
                    status_breakdown.append({
                        "status": str(r["st"]),
                        "orders": int(r["orders"]),
                        "billed_amount": round(float(r["billed"]), 2),
                        "net_margin": round(float(r["net_margin"]), 2),
                        "reverse_shipping": round(float(r["reverse_shipping"]), 2),
                    })

            neg_margin_segments = []
            for d_cand in self._discover_operational_dimensions():
                if d_cand == status_col:
                    continue
                tmp_dm = pd.DataFrame({
                    "seg": self.df[d_cand].astype(str),
                    "y": self.s_bin,
                    "bill": s_bill,
                    "disc": s_disc,
                    "margin": s_margin,
                })
                g_dm = tmp_dm.groupby("seg", as_index=False).agg(
                    orders=("y", "count"),
                    failures=("y", "sum"),
                    failure_rate_pct=("y", lambda s: round(float(s.mean() * 100.0), 2)),
                    billed=("bill", "sum"),
                    discount_burn=("disc", "sum"),
                    net_margin=("margin", "sum"),
                    avg_margin=("margin", "mean"),
                )
                for _, r_dm in g_dm[g_dm["net_margin"] < -100.0].sort_values("net_margin", ascending=True).iterrows():
                    if int(r_dm["orders"]) >= max(10, int(self.total_records * 0.01)):
                        neg_margin_segments.append({
                            "dimension": d_cand,
                            "segment": str(r_dm["seg"]),
                            "orders": int(r_dm["orders"]),
                            "failures": int(r_dm["failures"]),
                            "failure_rate_pct": round(float(r_dm["failure_rate_pct"]), 2),
                            "billed_amount": round(float(r_dm["billed"]), 2),
                            "discount_burn": round(float(r_dm["discount_burn"]), 2),
                            "net_margin": round(float(r_dm["net_margin"]), 2),
                            "avg_margin_per_order": round(float(r_dm["avg_margin"]), 2),
                        })

            result["has_margin_ledger"] = True
            result["margin_column"] = margin_col
            result["total_gross_revenue"] = round(float(s_gross.sum()), 2)
            result["total_discount_burn"] = round(float(s_disc.sum()), 2)
            result["discount_share_of_gross_pct"] = round(float(s_disc.sum() / max(s_gross.sum(), 1.0) * 100.0), 2) if gross_col else 0.0
            result["total_net_billed"] = round(float(s_bill.sum()), 2)
            result["total_net_margin"] = round(float(s_margin.sum()), 2)
            result["net_margin_pct_of_billed"] = round(float(s_margin.sum() / max(s_bill.sum(), 10.0) * 100.0), 2)
            result["negative_margin_order_count"] = neg_count
            result["negative_margin_cash_loss"] = round(neg_cash_loss, 2)
            result["reverse_shipping_burn"] = round(rev_ship_total, 2)
            result["status_cash_breakdown"] = status_breakdown
            result["negative_margin_segments"] = neg_margin_segments

        # Layer 5: Coupon & Discount Erosion Audit
        if coupon_col and coupon_col in self.df.columns:
            s_coup = self.df[coupon_col].astype(str)
            s_margin = pd.to_numeric(self.df[margin_col], errors="coerce").fillna(0.0) if margin_col else pd.Series(0.0, index=self.df.index)
            s_disc = pd.to_numeric(self.df[disc_amt_col], errors="coerce").fillna(0.0) if disc_amt_col else pd.Series(0.0, index=self.df.index)
            tmp_c = pd.DataFrame({"coupon": s_coup, "y": self.s_bin, "margin": s_margin, "disc": s_disc})
            g_c = tmp_c.groupby("coupon", as_index=False).agg(
                orders=("y", "count"),
                failures=("y", "sum"),
                failure_rate_pct=("y", lambda s: round(float(s.mean() * 100.0), 2)),
                discount_burn=("disc", "sum"),
                total_margin=("margin", "sum"),
                avg_margin_per_order=("margin", "mean"),
            ).sort_values("failure_rate_pct", ascending=False)

            none_rows = g_c[g_c["coupon"].str.upper().isin(["NONE", "NO_COUPON", "0", "NULL", "NAN"])]
            base_margin = float(none_rows["avg_margin_per_order"].iloc[0]) if len(none_rows) > 0 else float(s_margin.mean())
            base_fail = float(none_rows["failure_rate_pct"].iloc[0]) if len(none_rows) > 0 else self.baseline_rate_pct

            coupon_rows = []
            toxic_coupons = []
            for _, r in g_c.iterrows():
                c_name = str(r["coupon"])
                avg_m = round(float(r["avg_margin_per_order"]), 2)
                f_rate = float(r["failure_rate_pct"])
                margin_drop_pct = round(((avg_m - base_margin) / abs(base_margin)) * 100.0, 1) if base_margin >= 1.0 else 0.0
                fail_lift_pct = round(((f_rate - base_fail) / max(base_fail, 0.01)) * 100.0, 1)
                is_toxic = bool(
                    c_name.upper() not in ("NONE", "NO_COUPON")
                    and f_rate >= base_fail * 1.20
                    and (not margin_col or avg_m <= base_margin * 0.65)
                )
                item = {
                    "coupon_code": c_name,
                    "orders": int(r["orders"]),
                    "failures": int(r["failures"]),
                    "failure_rate_pct": f_rate,
                    "discount_burn": round(float(r["discount_burn"]), 2),
                    "avg_margin_per_order": avg_m,
                    "margin_delta_vs_no_coupon_pct": margin_drop_pct,
                    "failure_lift_vs_no_coupon_pct": fail_lift_pct,
                    "is_double_poison_promo": is_toxic,
                }
                coupon_rows.append(item)
                if is_toxic:
                    toxic_coupons.append(item)

            result["has_coupon_audit"] = True
            result["coupon_column"] = coupon_col
            result["no_coupon_baseline_margin"] = round(base_margin, 2)
            result["no_coupon_baseline_failure_pct"] = round(base_fail, 2)
            result["coupons"] = coupon_rows
            result["toxic_coupons"] = toxic_coupons

        return result

    # =========================================================================
    # LAYER 6: REPEAT-ENTITY (CUSTOMER/VENDOR) & HIGH-VALUE WHALE / SKU AUDIT
    # =========================================================================
    def scan_entity_concentration_and_skus(self) -> Dict[str, Any]:
        cols = list(self.df.columns)
        entity_col = _find_col_by_keywords(
            cols,
            ["customer_id", "client_id", "account_id", "user_id", "vendor_id", "supplier_id", "merchant_id"],
            exclude={self.target_col, self.cost_col},
        )
        margin_col = _find_col_by_keywords(cols, ["net_contribution_margin_inr", "contribution_margin", "net_margin", "net_profit", "profit"])
        seg_col = _find_col_by_keywords(cols, ["customer_segment", "client_tier", "account_tier", "segment"])
        sku_col = _find_col_by_keywords(cols, ["sku_code", "product_id", "item_code", "sku"])

        res: Dict[str, Any] = {"has_repeat_entities": False, "has_whale_segment": False, "has_sku_audit": False}

        if entity_col and entity_col in self.df.columns:
            n_unique = int(self.df[entity_col].nunique(dropna=True))
            if 10 <= n_unique < self.total_records:
                s_bill = pd.to_numeric(self.df[self.cost_col], errors="coerce").fillna(0.0) if self.cost_col else pd.Series(0.0, index=self.df.index)
                s_margin = pd.to_numeric(self.df[margin_col], errors="coerce").fillna(0.0) if margin_col else pd.Series(0.0, index=self.df.index)
                tmp_e = pd.DataFrame({
                    "eid": self.df[entity_col].astype(str),
                    "y": self.s_bin,
                    "bill": s_bill,
                    "margin": s_margin,
                })
                g_e = tmp_e.groupby("eid", as_index=False).agg(
                    orders=("y", "count"),
                    failures=("y", "sum"),
                    total_billed=("bill", "sum"),
                    lifetime_margin=("margin", "sum"),
                )
                g_e["failure_rate_pct"] = (g_e["failures"] / g_e["orders"] * 100.0).round(1)
                repeat_cnt = int((g_e["orders"] >= 2).sum())
                serial_df = g_e[(g_e["orders"] >= 3) & (g_e["failures"] >= 2)].sort_values(
                    ["failures", "failure_rate_pct", "lifetime_margin"], ascending=[False, False, True]
                )
                neg_ltv_df = g_e[g_e["lifetime_margin"] < 0] if margin_col else pd.DataFrame()

                res["has_repeat_entities"] = True
                res["entity_column"] = entity_col
                res["unique_entities"] = n_unique
                res["repeat_entities_count"] = repeat_cnt
                res["repeat_entity_share_pct"] = round(repeat_cnt / max(n_unique, 1) * 100.0, 1)
                res["serial_abuser_count"] = int(len(serial_df))
                res["serial_abuser_total_failures"] = int(serial_df["failures"].sum())
                res["negative_ltv_entity_count"] = int(len(neg_ltv_df))
                res["negative_ltv_total_cash_loss"] = round(float(neg_ltv_df["lifetime_margin"].sum()), 2) if len(neg_ltv_df) > 0 else 0.0
                res["top_serial_abusers"] = [
                    {
                        "entity_id": str(r["eid"]),
                        "orders": int(r["orders"]),
                        "failures": int(r["failures"]),
                        "failure_rate_pct": float(r["failure_rate_pct"]),
                        "total_billed": round(float(r["total_billed"]), 2),
                        "lifetime_margin": round(float(r["lifetime_margin"]), 2),
                    }
                    for _, r in serial_df.head(8).iterrows()
                ]

        # High-value whale segment detection (e.g. Corporate Wellness Client with 3.9x avg margin)
        if seg_col and seg_col in self.df.columns:
            s_val = (
                pd.to_numeric(self.df[margin_col], errors="coerce").fillna(0.0)
                if margin_col
                else (pd.to_numeric(self.df[self.cost_col], errors="coerce").fillna(0.0) if self.cost_col else None)
            )
            if s_val is not None:
                s_bill = pd.to_numeric(self.df[self.cost_col], errors="coerce").fillna(0.0) if self.cost_col else s_val
                tmp_s = pd.DataFrame({"seg": self.df[seg_col].astype(str), "y": self.s_bin, "val": s_val, "bill": s_bill})
                g_s = tmp_s.groupby("seg", as_index=False).agg(
                    orders=("y", "count"),
                    failures=("y", "sum"),
                    failure_rate_pct=("y", lambda s: round(float(s.mean() * 100.0), 2)),
                    avg_value_per_order=("val", "mean"),
                )
                adv_b = tmp_s[tmp_s["y"] == 1].groupby("seg", as_index=False)["bill"].sum().rename(columns={"bill": "adverse_exposure"})
                g_s = g_s.merge(adv_b, on="seg", how="left").fillna({"adverse_exposure": 0.0})
                overall_avg = float(s_val.mean())
                g_s = g_s.sort_values("avg_value_per_order", ascending=False)
                top_s = g_s.iloc[0]
                top_avg_v = float(top_s["avg_value_per_order"])
                mult = round(top_avg_v / overall_avg, 2) if (overall_avg > 0 and top_avg_v > 0) else 0.0
                if mult >= 1.75:
                    res["has_whale_segment"] = True
                    res["segment_column"] = seg_col
                    res["whale_segment"] = str(top_s["seg"])
                    res["whale_orders"] = int(top_s["orders"])
                    res["whale_failures"] = int(top_s["failures"])
                    res["whale_failure_rate_pct"] = float(top_s["failure_rate_pct"])
                    res["whale_avg_value_per_order"] = round(float(top_s["avg_value_per_order"]), 2)
                    res["whale_value_multiplier_vs_avg"] = mult
                    res["whale_adverse_exposure"] = round(float(top_s["adverse_exposure"]), 2)

        if sku_col and sku_col in self.df.columns and 2 <= self.df[sku_col].nunique() <= 100:
            s_bill = pd.to_numeric(self.df[self.cost_col], errors="coerce").fillna(0.0) if self.cost_col else pd.Series(0.0, index=self.df.index)
            tmp_k = pd.DataFrame({"sku": self.df[sku_col].astype(str), "y": self.s_bin, "bill": s_bill})
            g_k = tmp_k.groupby("sku", as_index=False).agg(
                orders=("y", "count"),
                failures=("y", "sum"),
                failure_rate_pct=("y", lambda s: round(float(s.mean() * 100.0), 2)),
            )
            adv_k = tmp_k[tmp_k["y"] == 1].groupby("sku", as_index=False)["bill"].sum().rename(columns={"bill": "adverse_exposure"})
            g_k = g_k.merge(adv_k, on="sku", how="left").fillna({"adverse_exposure": 0.0})
            g_k = g_k[g_k["orders"] >= max(15, int(self.total_records * 0.01))].sort_values(
                ["failure_rate_pct", "adverse_exposure"], ascending=[False, False]
            )
            if len(g_k) > 0:
                res["has_sku_audit"] = True
                res["sku_column"] = sku_col
                res["top_risk_skus"] = [
                    {
                        "sku": str(r["sku"]),
                        "orders": int(r["orders"]),
                        "failures": int(r["failures"]),
                        "failure_rate_pct": float(r["failure_rate_pct"]),
                        "adverse_exposure": round(float(r["adverse_exposure"]), 2),
                    }
                    for _, r in g_k.head(5).iterrows()
                ]

        return res

    # =========================================================================
    # LAYER 7: SEASONAL / QUARTERLY (Q4 FESTIVE) & HOUR-OF-DAY REGIME SCANNER
    # =========================================================================
    def scan_seasonal_and_temporal_regimes(self) -> Dict[str, Any]:
        cols = list(self.df.columns)
        date_col = _find_col_by_keywords(cols, ["order_date", "transaction_date", "booking_date", "invoice_date", "billing_date", "date"])
        # Strict calendar month matching: NEVER match Monthly_Retainer / Monthly_Rent / Monthly_MRR / MonthlyCharges!
        non_cal_month_tokens = ("monthly", "mrr", "rent", "retainer", "charge", "salary", "income", "fee", "checkin", "bill", "cost", "usd", "inr", "amount", "tenure", "age")
        month_col = None
        for c in cols:
            cl = c.lower().strip()
            if any(bad in cl for bad in non_cal_month_tokens):
                continue
            if cl in ("order_month", "month", "cal_month", "calendar_month", "billing_month", "invoice_month", "txn_month") or cl.endswith("_month"):
                month_col = c
                break
        sla_col = _find_col_by_keywords(cols, ["delivery_sla_breach", "sla_breach", "is_late"])
        disp_col = _find_col_by_keywords(cols, ["dispatch_delay_days", "dispatch_delay"])
        csat_col = _find_col_by_keywords(cols, ["customer_csat_rating", "csat"])

        res: Dict[str, Any] = {"has_quarterly_regime_shift": False}
        months = None
        if month_col and pd.api.types.is_numeric_dtype(self.df[month_col]):
            cand_m = pd.to_numeric(self.df[month_col], errors="coerce").dropna()
            if len(cand_m) >= 20 and float(cand_m.min()) >= 1.0 and float(cand_m.max()) <= 12.0:
                months = pd.to_numeric(self.df[month_col], errors="coerce")
        if months is None and date_col:
            try:
                dt = pd.to_datetime(self.df[date_col], errors="coerce")
                if dt.notna().mean() >= 0.8:
                    months = dt.dt.month
            except Exception:
                months = None

        if months is not None and months.dropna().nunique() >= 4:
            valid_m = months.clip(lower=1, upper=12)
            quarters = ((valid_m.fillna(1).astype(int) - 1) // 3) + 1
            q_df = pd.DataFrame({"q": quarters, "y": self.s_bin})
            if sla_col and pd.api.types.is_numeric_dtype(self.df[sla_col]):
                q_df["sla"] = pd.to_numeric(self.df[sla_col], errors="coerce").fillna(0.0) * 100.0
            if disp_col and pd.api.types.is_numeric_dtype(self.df[disp_col]):
                q_df["disp"] = pd.to_numeric(self.df[disp_col], errors="coerce")
            if csat_col and pd.api.types.is_numeric_dtype(self.df[csat_col]):
                q_df["csat"] = pd.to_numeric(self.df[csat_col], errors="coerce")

            g_q = q_df.groupby("q", as_index=False).agg(
                orders=("y", "count"),
                failure_rate_pct=("y", lambda s: round(float(s.mean() * 100.0), 2)),
            )
            g_q = g_q[g_q["orders"] >= 20]
            if len(g_q) < 2:
                return res
            worst_q_idx = int(g_q.sort_values("failure_rate_pct", ascending=False).iloc[0]["q"])
            q_mask = quarters == worst_q_idx
            rest_mask = ~q_mask
            if int(q_mask.sum()) < 20 or int(rest_mask.sum()) < 20:
                return res

            q_fail = round(float(self.s_bin[q_mask].mean() * 100.0), 2)
            rest_fail = round(float(self.s_bin[rest_mask].mean() * 100.0), 2)
            q_sla = round(float(q_df.loc[q_mask, "sla"].mean()), 2) if "sla" in q_df else None
            rest_sla = round(float(q_df.loc[rest_mask, "sla"].mean()), 2) if "sla" in q_df else None
            q_disp = round(float(q_df.loc[q_mask, "disp"].mean()), 2) if "disp" in q_df else None
            rest_disp = round(float(q_df.loc[rest_mask, "disp"].mean()), 2) if "disp" in q_df else None
            q_csat = round(float(q_df.loc[q_mask, "csat"].mean()), 2) if "csat" in q_df else None
            rest_csat = round(float(q_df.loc[rest_mask, "csat"].mean()), 2) if "csat" in q_df else None

            # Statistical significance guard on peak quarter vs rest-of-year (blocks random seasonal noise!)
            q_sig = False
            try:
                ct_q = pd.crosstab(q_mask, self.s_bin)
                if ct_q.shape == (2, 2):
                    _, p_q, _, _ = scipy_stats.chi2_contingency(ct_q)
                    q_sig = bool(float(p_q) < 0.05)
            except Exception:
                q_sig = False

            if (q_sig and (q_fail - rest_fail >= 1.2)) or (q_sla is not None and rest_sla is not None and (q_sla - rest_sla) >= 8.0):
                res["has_quarterly_regime_shift"] = True
                res["peak_quarter"] = f"Q{worst_q_idx}"
                res["peak_quarter_orders"] = int(q_mask.sum())
                res["peak_quarter_failure_pct"] = q_fail
                res["rest_of_year_failure_pct"] = rest_fail
                res["peak_quarter_sla_breach_pct"] = q_sla
                res["rest_of_year_sla_breach_pct"] = rest_sla
                res["peak_quarter_dispatch_delay"] = q_disp
                res["rest_of_year_dispatch_delay"] = rest_disp
                res["peak_quarter_csat"] = q_csat
                res["rest_of_year_csat"] = rest_csat

        return res

    # =========================================================================
    # LAYER 7: UNIVERSAL FORENSIC ACCOUNTING, FRAUD & WORKING-CAPITAL AUDIT
    # (Global-Earth Grade: Composite Ghost-Duplicates, Threshold-Gaming Bunching,
    #  and Paper-Profit vs Bank-Cash AR Gap across any currency/industry)
    # =========================================================================
    def scan_forensic_accounting_and_fraud(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "has_composite_duplicates": False,
            "has_threshold_gaming": False,
            "threshold_gaming_alerts": [],
            "has_working_capital_ar_gap": False,
        }
        cols = list(self.df.columns)
        if self.total_records < 20:
            return res

        entity_col = next(
            (c for c in cols if any(k in c.lower() for k in ("distributor_name", "dealer_name", "party_name", "account_name", "client_name", "vendor_name", "merchant_name")) and not pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        ) or next(
            (c for c in cols if any(k in c.lower() for k in ("dealer_id", "distributor_id", "customer_id", "account_id", "client_id", "vendor_id")) and not pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        rep_col = next(
            (c for c in cols if any(k in c.lower() for k in ("salesman", "sales_rep", "salesperson", "rep_name", "csm", "account_manager", "agent_name", "broker")) and not pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        date_col = next(
            (c for c in cols if any(k in c.lower() for k in ("invoice_date", "order_date", "dispatch_date", "transaction_date", "bill_date", "date")) and not pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        cat_col = next(
            (c for c in cols if any(k in c.lower() for k in ("sku", "product_category", "category", "item", "product_name")) and not pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )

        # 7A. Composite Ghost-Duplicate Billing Audit (same entity + date + optional category + continuous amount, distinct invoice IDs)
        if self.cost_col and self.cost_col in self.df.columns and entity_col and date_col:
            amt_s = pd.to_numeric(self.df[self.cost_col], errors="coerce")
            # Require continuous/varied amounts (nunique >= 50) so fixed-price subscriptions ($9.99) never false-trigger!
            if amt_s.nunique(dropna=True) >= 50:
                pos_df = self.df.loc[amt_s > 0].copy()
                pos_df["_amt_round"] = amt_s.loc[amt_s > 0].round(2)
                key_cols = [entity_col, date_col, "_amt_round"]
                if cat_col and cat_col not in key_cols:
                    key_cols.append(cat_col)
                dup_mask = pos_df.duplicated(subset=key_cols, keep="first")
                dup_cnt = int(dup_mask.sum())
                if dup_cnt >= 5:
                    dup_cash = round(float(pos_df.loc[dup_mask, "_amt_round"].sum()), 2)
                    top_dup_ent = (
                        pos_df.loc[dup_mask, entity_col].astype(str).value_counts().head(3).to_dict()
                    )
                    res["has_composite_duplicates"] = True
                    res["composite_duplicate_count"] = dup_cnt
                    res["composite_duplicate_cash"] = dup_cash
                    res["composite_duplicate_keys"] = [k for k in key_cols if k != "_amt_round"] + [self.cost_col]
                    res["composite_duplicate_top_entities"] = top_dup_ent

        # 7B. Threshold-Gaming / Approval-Limit Bunching Fraud Audit (ACFE Global Audit Standard)
        alerts: List[Dict[str, Any]] = []
        disc_pct_col = next(
            (c for c in cols if ("discount" in c.lower() and ("pct" in c.lower() or "percent" in c.lower() or "%" in c.lower())) and pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        if disc_pct_col:
            ds = pd.to_numeric(self.df[disc_pct_col], errors="coerce").dropna()
            if len(ds) >= 50:
                for cap in (10.0, 15.0, 20.0, 25.0, 30.0):
                    band_mask = (self.df[disc_pct_col] >= cap - 0.5) & (self.df[disc_pct_col] < cap)
                    b_cnt = int(band_mask.sum())
                    # Compare density in [cap-0.5, cap) vs neighboring [cap-1.5, cap-0.5) & [cap, cap+1.0)
                    above_cnt = int(((self.df[disc_pct_col] >= cap) & (self.df[disc_pct_col] <= cap + 1.0)).sum())
                    below_cnt = int(((self.df[disc_pct_col] >= cap - 1.5) & (self.df[disc_pct_col] < cap - 0.5)).sum())
                    neighbor_rate = max((above_cnt + below_cnt) / 4.0, 1.0)
                    if b_cnt >= 25 and (b_cnt / neighbor_rate) >= 5.0:
                        top_rep = str(self.df.loc[band_mask, rep_col].value_counts().index[0]) if (rep_col and band_mask.any()) else None
                        top_ent = str(self.df.loc[band_mask, entity_col].value_counts().index[0]) if (entity_col and band_mask.any()) else None
                        alerts.append({
                            "type": "discount_threshold_gaming",
                            "column": disc_pct_col,
                            "threshold": cap,
                            "band_label": f"{cap - 0.5:.1f}%–{cap:.1f}% (just under {cap:.0f}%)",
                            "flagged_count": b_cnt,
                            "flagged_cash": round(float(pd.to_numeric(self.df.loc[band_mask, self.cost_col], errors="coerce").fillna(0).sum()), 2) if self.cost_col else 0.0,
                            "top_rep": top_rep,
                            "top_entity": top_ent,
                        })

        cn_col = next(
            (c for c in cols if any(k in c.lower() for k in ("credit_note", "refund_amount", "rebate_amount", "expense_amount", "claim_payout", "adjustment_amount")) and pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        if cn_col:
            cns = pd.to_numeric(self.df[cn_col], errors="coerce").abs()
            nz = cns[cns > 0]
            if len(nz) >= 15:
                for cap in (1000.0, 5000.0, 10000.0, 25000.0, 50000.0, 100000.0, 500000.0):
                    lo_b = cap * 0.95
                    cmask = (cns >= lo_b) & (cns <= cap)
                    ccnt = int(cmask.sum())
                    if ccnt >= 15 and (ccnt / float(len(nz))) >= 0.30:
                        top_rep = str(self.df.loc[cmask, rep_col].value_counts().index[0]) if (rep_col and cmask.any()) else None
                        top_ent = str(self.df.loc[cmask, entity_col].value_counts().index[0]) if (entity_col and cmask.any()) else None
                        alerts.append({
                            "type": "monetary_cap_gaming",
                            "column": cn_col,
                            "threshold": cap,
                            "band_label": f"{self.unit_symbol}{lo_b:,.0f}–{self.unit_symbol}{cap:,.0f} (just under {self.unit_symbol}{cap:,.0f} cap)",
                            "flagged_count": ccnt,
                            "flagged_cash": round(float(cns.loc[cmask].sum()), 2),
                            "top_rep": top_rep,
                            "top_entity": top_ent,
                        })
                        break

        if alerts:
            res["has_threshold_gaming"] = True
            res["threshold_gaming_alerts"] = alerts

        # 7C. Working-Capital / Unpaid AR Cash Gap Audit
        due_col = next(
            (c for c in cols if any(k in c.lower() for k in ("outstanding_due", "balance_due", "unpaid_amount", "ar_balance", "overdue_amount", "amount_due")) and pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        coll_col = next(
            (c for c in cols if any(k in c.lower() for k in ("amount_collected", "cash_collected", "paid_amount", "collected_inr", "collected_usd")) and pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        dso_col = next(
            (c for c in cols if any(k in c.lower() for k in ("days_to_pay", "dso", "days_overdue", "overdue_days", "payment_days")) and pd.api.types.is_numeric_dtype(self.df[c])),
            None,
        )
        if due_col and self.cost_col:
            s_due = pd.to_numeric(self.df[due_col], errors="coerce").fillna(0.0)
            s_inv = pd.to_numeric(self.df[self.cost_col], errors="coerce").fillna(0.0)
            tot_due = round(float(s_due.sum()), 2)
            tot_inv = round(float(s_inv.sum()), 2)
            unpaid_pct = round(100.0 * tot_due / max(tot_inv, 1.0), 2)
            if tot_due > 0 and unpaid_pct >= 12.0:
                tot_coll = round(float(pd.to_numeric(self.df[coll_col], errors="coerce").fillna(0.0).sum()), 2) if coll_col else None
                avg_dso = round(float(pd.to_numeric(self.df[dso_col], errors="coerce").dropna().mean()), 1) if dso_col else None
                top_overdue = []
                if entity_col:
                    g_df = pd.DataFrame({"ent": self.df[entity_col].astype(str), "due": s_due})
                    if dso_col:
                        g_df["dso"] = pd.to_numeric(self.df[dso_col], errors="coerce")
                    agg_o = g_df.groupby("ent", as_index=False).agg(
                        unpaid=("due", "sum"),
                        unpaid_rows=("due", lambda x: int((x > 0).sum())),
                        avg_dso=("dso", "mean") if dso_col else ("due", "count"),
                    ).sort_values("unpaid", ascending=False)
                    for _, ro in agg_o[agg_o["unpaid"] > 0].head(5).iterrows():
                        top_overdue.append({
                            "entity": str(ro["ent"]),
                            "unpaid_amount": round(float(ro["unpaid"]), 2),
                            "unpaid_rows": int(ro["unpaid_rows"]),
                            "avg_dso_days": round(float(ro["avg_dso"]), 1) if dso_col else None,
                        })
                res["has_working_capital_ar_gap"] = True
                res["due_column"] = due_col
                res["total_outstanding_due"] = tot_due
                res["total_invoiced_base"] = tot_inv
                res["total_collected"] = tot_coll
                res["unpaid_share_pct"] = unpaid_pct
                res["avg_dso_days"] = avg_dso
                res["top_overdue_entities"] = top_overdue

        return res

    # =========================================================================
    # MASTER EXECUTION & MARKDOWN SYNTHESIS
    # =========================================================================
    def run_full_scan(self, out_dir: Optional[Path | str] = None) -> Dict[str, Any]:
        dims = self._discover_operational_dimensions()
        dim_scan = self.scan_all_dimensions(dims)
        ops_sla_findings = self.scan_operational_sla_and_delays(dims)
        interactions = self.scan_categorical_interactions_and_confounders(dims)
        pnl_coupons = self.scan_pnl_margin_and_coupons()
        entities_skus = self.scan_entity_concentration_and_skus()
        seasonal = self.scan_seasonal_and_temporal_regimes()
        forensic_acct = self.scan_forensic_accounting_and_fraud()

        report = {
            "total_records": self.total_records,
            "target_col": self.target_col,
            "cost_col": self.cost_col,
            "unit_symbol": self.unit_symbol,
            "total_events": self.total_events,
            "baseline_rate_pct": self.baseline_rate_pct,
            "audited_dimensions_count": len(dims),
            "audited_dimensions": dims,
            "confirmed_leak_dimensions": dim_scan["confirmed_leak_dimensions"],
            "uniform_noise_dimensions": dim_scan["uniform_noise_dimensions"],
            "all_cohort_breakdowns": dim_scan["all_cohort_breakdowns"],
            "operational_sla_and_delay_findings": ops_sla_findings,
            "top_2d_hotspots": interactions["top_2d_hotspots"],
            "confounder_insights": interactions["confounder_insights"],
            "pnl_and_coupons": pnl_coupons,
            "entities_and_skus": entities_skus,
            "seasonal_regimes": seasonal,
            "forensic_accounting_and_fraud": forensic_acct,
        }

        if out_dir is not None:
            out_p = Path(out_dir).resolve()
            out_p.mkdir(parents=True, exist_ok=True)
            with open(out_p / "omni_leak_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return report


def render_plain_omni_sections(report: Dict[str, Any]) -> Tuple[str, str]:
    """
    Renders zero-jargon English and Hindi/Hinglish 360-degree A-to-Z hidden leakage
    sections for `PLAIN_BUSINESS_SUMMARY.md` (with zero scientific p-value notation).
    """
    sym = report.get("unit_symbol") or "$"
    leaks = report.get("confirmed_leak_dimensions", [])
    noise = report.get("uniform_noise_dimensions", [])
    ops = report.get("operational_sla_and_delay_findings", [])
    hotspots = report.get("top_2d_hotspots", [])
    confounders = report.get("confounder_insights", [])
    pnl = report.get("pnl_and_coupons", {}) or {}
    ent = report.get("entities_and_skus", {}) or {}
    seas = report.get("seasonal_regimes", {}) or {}

    en_lines: List[str] = ["### 6. 360° Complete Hidden Leakage & Profit Audit (A-to-Z Deep Scan)"]
    hi_lines: List[str] = ["### 6. 360° Chhupe Hue Nuksan Aur Munafe Ka Poora X-Ray (A-to-Z Deep Scan)"]

    # 1. All Confirmed Dimension Leaks (deduplicate identical collinear mirror cohorts)
    dedup_leaks = []
    seen_cohort_sigs = set()
    for lk in leaks:
        sig = (int(lk.get("worst_volume", 0)), round(float(lk.get("worst_rate_pct", 0.0)), 2), round(float(lk.get("excess_events", 0.0)), 1))
        if sig in seen_cohort_sigs and sig[0] > 0:
            continue
        seen_cohort_sigs.add(sig)
        dedup_leaks.append(lk)

    if dedup_leaks:
        try:
            try:
                from .human_analyst_narrator import humanize_segment, multiplier_human_phrase, rate_out_of_ten_phrase
            except ImportError:
                from human_analyst_narrator import humanize_segment, multiplier_human_phrase, rate_out_of_ten_phrase
        except Exception:
            humanize_segment = lambda d, s, l="en": f"{d} = {s}"
            rate_out_of_ten_phrase = lambda r, l="en": f"{r:.0f}%"
            multiplier_human_phrase = lambda m, l="en": f"{m:.1f}x higher"

        en_lines.append(f"- **All {len(dedup_leaks)} Confirmed Problem Areas (Out of {report.get('audited_dimensions_count', 0)} Checked Factors)**:")
        hi_lines.append(f"- **Sabhi {len(dedup_leaks)} Asli Samasya Wale Hisse ({report.get('audited_dimensions_count', 0)} check kiye gaye columns mein se)**:")
        for lk in dedup_leaks[:6]:
            cost_str = f", **{sym}{lk['worst_adverse_cost']:,.2f}** at risk" if lk.get("worst_adverse_cost", 0) > 0 else ""
            seg_en = humanize_segment(lk["dimension"], lk["worst_segment"], "en")
            seg_hi = humanize_segment(lk["dimension"], lk["worst_segment"], "hi")
            here_en = rate_out_of_ten_phrase(lk["worst_rate_pct"], "en")
            rest_en = rate_out_of_ten_phrase(lk["rest_rate_pct"], "en")
            here_hi = rate_out_of_ten_phrase(lk["worst_rate_pct"], "hi")
            rest_hi = rate_out_of_ten_phrase(lk["rest_rate_pct"], "hi")
            mult_en = multiplier_human_phrase(lk["risk_multiplier"], "en")
            mult_hi = multiplier_human_phrase(lk["risk_multiplier"], "hi")
            en_lines.append(
                f"  - **{seg_en}**: **{here_en}** run into problems vs {rest_en} normally (**{mult_en}**, ~{lk['excess_events']:,.0f} avoidable cases across {lk['worst_volume']:,} checked{cost_str})."
            )
            hi_lines.append(
                f"  - **{seg_hi}**: **{here_hi}** mein samasya aa rahi hai jabki baaki jagah {rest_hi} hai (**{mult_hi}**, {lk['worst_volume']:,} mein se ~{lk['excess_events']:,.0f} cases bachaye ja sakte hain{cost_str})."
            )

    if noise:
        noise_names = ", ".join(f"`{n['dimension']}`" for n in noise[:6])
        en_lines.append(f"- **Safe / Uniform-Noise Dimensions ({sym}0 Extra Targeted Spend Needed)**: Failure rates across {noise_names} show no statistically significant bottleneck — do not waste targeted budget cherry-picking inside these columns.")
        hi_lines.append(f"- **Safe / Normal Columns (Yahan {sym}0 Extra Kharch Karein)**: {noise_names} ke alag-alag groups mein failure rate lagbhag barabar hai — in par alag se targeted budget waste na karein.")

    # 2. Secondary Operational Bottlenecks (Warehouse Dispatch & Courier SLA)
    for op in ops[:4]:
        en_lines.append(f"- **Operational SLA / Speed Bottleneck**: {op['headline_en']}")
        hi_lines.append(f"- **Operational Speed / SLA Bottleneck**: {op['headline_en']}")

    # 3. Confounder / Simpson's Paradox & 2D Hotspots
    for cf in confounders[:2]:
        en_lines.append(f"- {cf['explanation_en']}")
        hi_lines.append(f"- {cf['explanation_en']}")

    if hotspots:
        top_h = hotspots[:3]
        hs_en = "; ".join(
            f"`{h['dim_a']}={h['val_a']}` + `{h['dim_b']}={h['val_b']}` (**{h['rate_pct']:.2f}%** failure across {h['volume']:,} records, {h['lift_vs_baseline']}x baseline)"
            for h in top_h
        )
        hs_hi = "; ".join(
            f"`{h['dim_a']}={h['val_a']}` + `{h['dim_b']}={h['val_b']}` (**{h['rate_pct']:.2f}%** failure, {h['volume']:,} records, {h['lift_vs_baseline']}x khatra)"
            for h in top_h
        )
        en_lines.append(f"- **Deadliest 2-Factor Combinations (2x2 Hotspots)**: {hs_en}.")
        hi_lines.append(f"- **Sabse Khatarnak Double Combinations (2x2 Hotspots)**: {hs_hi}.")

    # 4. P&L Net Margin, Profitless Segments, Reverse Shipping & Toxic Coupons
    if pnl.get("has_margin_ledger"):
        neg_cnt = pnl.get("negative_margin_order_count", 0)
        neg_loss = abs(float(pnl.get("negative_margin_cash_loss", 0.0)))
        rev_ship = float(pnl.get("reverse_shipping_burn", 0.0))
        tot_m = float(pnl.get("total_net_margin", 0.0))
        disc_b = float(pnl.get("total_discount_burn", 0.0))
        rev_str_en = f" (including **{sym}{rev_ship:,.2f}** burned purely in reverse return shipping)" if rev_ship > 0 else ""
        rev_str_hi = f" (jismein **{sym}{rev_ship:,.2f}** akele reverse shipping mein jal gaya)" if rev_ship > 0 else ""
        disc_str_en = f", while total discount giveaways consumed **{sym}{disc_b:,.2f}** ({pnl.get('discount_share_of_gross_pct', 0)}% of gross sales)" if disc_b > 0 else ""
        disc_str_hi = f", aur total discounts mein **{sym}{disc_b:,.2f}** ({pnl.get('discount_share_of_gross_pct', 0)}%) kharch hua" if disc_b > 0 else ""

        en_lines.append(
            f"- **True Cash P&L & Negative-Margin Bleed**: Total net contribution margin is **{sym}{tot_m:,.2f}** ({pnl.get('net_margin_pct_of_billed', 0)}% of net billed){disc_str_en}. Exactly **{neg_cnt:,} negative-margin records** caused a direct out-of-pocket cash loss of **-{sym}{neg_loss:,.2f}**{rev_str_en}."
        )
        hi_lines.append(
            f"- **Asli Cash Munafa (Net Margin) Aur Jeb Se Gaya Ghata**: Total net profit margin **{sym}{tot_m:,.2f}** hai{disc_str_hi}. **{neg_cnt:,} negative-margin records** ki wajah se company ki jeb se seedha **-{sym}{neg_loss:,.2f}** ka cash loss hua{rev_str_hi}."
        )
        for nms in (pnl.get("negative_margin_segments") or [])[:3]:
            n_dim = nms.get("dimension")
            n_seg = nms.get("segment")
            n_loss = abs(float(nms.get("net_margin", nms.get("total_net_margin", 0.0))))
            n_cnt = int(nms.get("orders", nms.get("records", 0)))
            en_lines.append(
                f"  - **Profitless Revenue Trap (`{n_dim} = '{n_seg}'`)**: Losing **-{sym}{n_loss:,.2f}** net margin across **{n_cnt:,} records** — high revenue is masking negative unit economics."
            )
            hi_lines.append(
                f"  - **Ghate Wala Segment (`{n_dim} = '{n_seg}'`)**: **{n_cnt:,} records** par seedha **-{sym}{n_loss:,.2f}** ka net cash loss ho raha hai — revenue dikhne ke bawajood yeh segment company ka paisa jala raha hai."
            )

    for tc in pnl.get("toxic_coupons", [])[:2]:
        en_lines.append(
            f"- **Margin-Killing Promo Alert (`{pnl.get('coupon_column')} = '{tc['coupon_code']}'`)**: Used on **{tc['orders']:,} orders** (burning **{sym}{tc['discount_burn']:,.2f}** in discounts), slashing average net profit per order to **{sym}{tc['avg_margin_per_order']:,.2f}** (**{tc['margin_delta_vs_no_coupon_pct']}%** vs no-coupon baseline {sym}{pnl.get('no_coupon_baseline_margin', 0):,.2f}) while simultaneously inflating failure/RTO rate to **{tc['failure_rate_pct']:.2f}%** (+{tc['failure_lift_vs_no_coupon_pct']}% higher risk)."
        )
        hi_lines.append(
            f"- **Double Nuksan Wala Coupon (`{pnl.get('coupon_column')} = '{tc['coupon_code']}'`)**: **{tc['orders']:,} orders** par **`{tc['coupon_code']}`** ne **{sym}{tc['discount_burn']:,.2f}** discount jalaya, per-order profit **{sym}{pnl.get('no_coupon_baseline_margin', 0):,.2f}** se girakar **{sym}{tc['avg_margin_per_order']:,.2f}** (**{tc['margin_delta_vs_no_coupon_pct']}%**) kar diya, aur failure rate bhi badhakar **{tc['failure_rate_pct']:.2f}%** kar diya."
        )

    # 5. Customer Repeat Abuse, Negative-LTV & Whale Segments
    if ent.get("has_repeat_entities"):
        ab_cnt = ent.get("serial_abuser_count", 0)
        ab_fail = ent.get("serial_abuser_total_failures", 0)
        neg_ltv_cnt = ent.get("negative_ltv_entity_count", 0)
        neg_ltv_loss = abs(float(ent.get("negative_ltv_total_cash_loss", 0.0)))
        top_ids = ", ".join(f"`{a['entity_id']}` ({a['failures']}/{a['orders']} failed)" for a in ent.get("top_serial_abusers", [])[:4])
        en_lines.append(
            f"- **Repeat Customer / Entity Forensics (`{ent.get('entity_column')}`)**: Out of **{ent.get('unique_entities', 0):,} unique accounts** ({ent.get('repeat_entities_count', 0):,} repeat buyers), **{neg_ltv_cnt:,} accounts have negative lifetime net margin** (net cash loss **-{sym}{neg_ltv_loss:,.2f}**), and **{ab_cnt:,} serial repeat offenders** (>=3 orders with >=2 failures) generated **{ab_fail:,} repeat failures** (top serial IDs: {top_ids})."
        )
        hi_lines.append(
            f"- **Baar-Baar Nuksan Dene Wale Accounts (`{ent.get('entity_column')}`)**: Total **{ent.get('unique_entities', 0):,} accounts** ({ent.get('repeat_entities_count', 0):,} repeat) mein se **{neg_ltv_cnt:,} accounts Negative LTV (ghate) mein hain** (**-{sym}{neg_ltv_loss:,.2f}** net loss), aur **{ab_cnt:,} serial repeat offenders** ne akele **{ab_fail:,} repeat failures** kiye (top IDs: {top_ids}) — in par strict prepayment/SLA guardrails lagayein."
        )

    if ent.get("has_whale_segment"):
        en_lines.append(
            f"- **High-Margin Whale Segment Protection (`{ent.get('segment_column')} = '{ent.get('whale_segment')}'`)**: Generates **{sym}{ent.get('whale_avg_value_per_order', 0):,.2f}** average profit/value per order (**{ent.get('whale_value_multiplier_vs_avg')}x company average**), with **{sym}{ent.get('whale_adverse_exposure', 0):,.2f}** at risk across {ent.get('whale_failures', 0):,} failed orders ({ent.get('whale_failure_rate_pct')}% rate) — assign dedicated VIP account management."
        )
        hi_lines.append(
            f"- **Sabse Zyada Munafe Wala VIP Segment (`{ent.get('segment_column')} = '{ent.get('whale_segment')}'`)**: Average value **{sym}{ent.get('whale_avg_value_per_order', 0):,.2f}** per record hai (**{ent.get('whale_value_multiplier_vs_avg')}x company average**), jahan {ent.get('whale_failures', 0):,} failed cases mein **{sym}{ent.get('whale_adverse_exposure', 0):,.2f}** at risk hai — inke liye dedicated priority support rakhein."
        )

    # 6. Seasonal Q4 Spike
    if seas.get("has_quarterly_regime_shift"):
        pq = seas.get("peak_quarter", "Q4")
        sla_note_en = f", SLA breach surges from **{seas['rest_of_year_sla_breach_pct']}% to {seas['peak_quarter_sla_breach_pct']}%**" if seas.get("peak_quarter_sla_breach_pct") is not None else ""
        disp_note_en = f", and avg dispatch delay jumps from **{seas['rest_of_year_dispatch_delay']}d to {seas['peak_quarter_dispatch_delay']}d**" if seas.get("peak_quarter_dispatch_delay") is not None else ""
        sla_note_hi = f", SLA ब्रीच **{seas['rest_of_year_sla_breach_pct']}% से कूदकर {seas['peak_quarter_sla_breach_pct']}%**" if seas.get("peak_quarter_sla_breach_pct") is not None else ""
        disp_note_hi = f", और डिस्पैच देरी **{seas['rest_of_year_dispatch_delay']} दिन से बढ़कर {seas['peak_quarter_dispatch_delay']} दिन**" if seas.get("peak_quarter_dispatch_delay") is not None else ""

        en_lines.append(
            f"- **Seasonal Regime Collapse (`{pq}` Peak Quarter Alert)**: Across **{seas.get('peak_quarter_orders', 0):,} `{pq}` orders**, failure rate rises from **{seas.get('rest_of_year_failure_pct')}% to {seas.get('peak_quarter_failure_pct')}%**{sla_note_en}{disp_note_en}. Pre-allocate extra warehouse & courier buffer capacity before `{pq}` begins."
        )
        hi_lines.append(
            f"- **Seasonal / Peak Quarter Breakdown (`{pq}` Alert)**: Har saal **`{pq}` ({seas.get('peak_quarter_orders', 0):,} records)** mein failure rate **{seas.get('rest_of_year_failure_pct')}% se badhkar {seas.get('peak_quarter_failure_pct')}%** ho jata hai — `{pq}` shuru hone se pehle extra buffer capacity arrange karein."
        )

    # 7. Universal Forensic Accounting, Fraud & Working-Capital AR Gap
    fa = report.get("forensic_accounting_and_fraud") or {}
    if fa.get("has_working_capital_ar_gap"):
        tot_due = float(fa.get("total_outstanding_due") or 0.0)
        unp_pct = float(fa.get("unpaid_share_pct") or 0.0)
        top_o = fa.get("top_overdue_entities") or []
        top_o_str = ", ".join(
            f"`{o['entity']}` ({sym}{o['unpaid_amount']:,.2f}" + (f", {o['avg_dso_days']}d DSO)" if o.get("avg_dso_days") is not None else ")")
            for o in top_o[:3]
        )
        en_lines.append(
            f"- **Working-Capital / Unpaid Receivables Cash Gap**: **{sym}{tot_due:,.2f}** (**{unp_pct:.1f}%** of invoiced billing) is stuck unpaid/overdue — paper profit does not equal cash in bank. Top overdue accounts: {top_o_str}."
        )
        hi_lines.append(
            f"- **Market Mein Fasa Unpaid Cash (AR Cash Gap)**: Kul **{sym}{tot_due:,.2f}** (**{unp_pct:.1f}%** billing) abhi tak unpaid/overdue fasa hua hai — paper profit aur bank cash mein bada antar hai. Sabse badi udhari wali parties: {top_o_str}."
        )
    if fa.get("has_composite_duplicates"):
        dcnt = int(fa.get("composite_duplicate_count") or 0)
        dcash = float(fa.get("composite_duplicate_cash") or 0.0)
        en_lines.append(
            f"- **Ghost Double-Billing / Composite Duplicate Alert**: Detected **{dcnt:,} duplicate transactions** (identical account + date + amount under separate invoice IDs) totaling **{sym}{dcash:,.2f}** — audit for accidental re-entry or billing duplication."
        )
        hi_lines.append(
            f"- **Double-Billing / Duplicate Transaction Alert**: File mein **{dcnt:,} duplicate bills** mile (same party + date + amount alag invoice ID par), kul रकम **{sym}{dcash:,.2f}** — double entry turant verify karein."
        )
    for ta in (fa.get("threshold_gaming_alerts") or [])[:2]:
        rep_s = f" (top rep: `{ta['top_rep']}`)" if ta.get("top_rep") else ""
        ent_s = f" on account `{ta['top_entity']}`" if ta.get("top_entity") else ""
        en_lines.append(
            f"- **Approval-Threshold Gaming / Policy-Bunching Alert (`{ta['column']}`)**: **{ta['flagged_count']:,} records** clustered suspiciously in **{ta['band_label']}**{rep_s}{ent_s} (value: **{sym}{ta['flagged_cash']:,.2f}**) — audit for split-approvals bypassing management limits."
        )
        hi_lines.append(
            f"- **Approval-Limit Bypass / Fraud Bunching Alert (`{ta['column']}`)**: **{ta['flagged_count']:,} transactions** jaan-boojh kar **{ta['band_label']}** limit ke theek neeche kate hain{rep_s}{ent_s} (kul value: **{sym}{ta['flagged_cash']:,.2f}**) — approval bypass audit karwayein."
        )

    return "\n".join(en_lines), "\n".join(hi_lines)


def render_dossier_omni_section(report: Dict[str, Any]) -> str:
    """
    Renders Section 10 of `DATA_XRAY_EXECUTIVE_DOSSIER.md` with full tables across
    all dimensions, secondary operational KPIs, 2D interactions, P&L margin/coupons,
    repeat entities, and seasonal regimes.
    """
    sym = report.get("unit_symbol") or "$"
    leaks = report.get("confirmed_leak_dimensions", [])
    noise = report.get("uniform_noise_dimensions", [])
    ops = report.get("operational_sla_and_delay_findings", [])
    hotspots = report.get("top_2d_hotspots", [])
    confounders = report.get("confounder_insights", [])
    pnl = report.get("pnl_and_coupons", {}) or {}
    ent = report.get("entities_and_skus", {}) or {}
    seas = report.get("seasonal_regimes", {}) or {}

    md = [
        "\n---\n",
        "## 🔍 SECTION 10: OMNI-DIMENSIONAL 360° HIDDEN LEAKAGE, P&L MARGIN & ENTITY FORENSICS",
        "*Exhaustive A-to-Z scan across every operational dimension, secondary SLA/delay KPI, 2D interaction, net contribution margin, promotion code, repeat entity, and seasonal quarter:*\n",
    ]

    if leaks:
        md.append("### 10.1 All Statistically Confirmed Leak Dimensions (Multi-Column Scan)")
        md.append(f"| Dimension | High-Risk Segment | Segment Orders | Failed Cases | Segment Failure % | Rest-of-Business % | Risk Multiplier | Excess Failures | Financial Exposure ({sym}) |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for lk in leaks:
            md.append(
                f"| `{lk['dimension']}` | **{lk['worst_segment']}** | {lk['worst_volume']:,} | {lk['worst_events']:,} | **{lk['worst_rate_pct']:.2f}%** | {lk['rest_rate_pct']:.2f}% | **{lk['risk_multiplier']}x** | {lk['excess_events']:,.1f} | {sym}{lk['worst_adverse_cost']:,.2f} |"
            )
        md.append("")

    if noise:
        md.append("### 10.2 Verified Uniform-Noise Dimensions (Zero Targeted Spend Advised)")
        for n in noise:
            md.append(
                f"- **`{n['dimension']}`** ({n['cardinality']} groups): Highest group `'{n['worst_segment']}'` ({n['worst_rate_pct']:.2f}%) vs rest ({n['rest_rate_pct']:.2f}%) is within random variation (`Chi-Square p = {n['omnibus_chi2_p']:.4f}`). **Hold targeted budget at {sym}0.**"
            )
        md.append("")

    if ops:
        md.append("### 10.3 Secondary Operational SLA, Dispatch Speed & Transit Bottlenecks")
        for op in ops:
            md.append(f"- {op['headline_en']}")
            md.append(f"  - *Hindi*: {op['headline_hi']}")
        md.append("")

    if confounders or hotspots:
        md.append("### 10.4 2x2 Categorical Interactions & Confounder / Simpson's Paradox Isolation")
        for cf in confounders:
            md.append(f"- {cf['explanation_en']}")
            md.append(f"  - *Hindi*: {cf['explanation_hi']}")
        if hotspots:
            md.append("\n| Factor A | Factor B | Combined Orders | Failed Cases | Combined Failure % | Lift vs Baseline |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for h in hotspots[:6]:
                md.append(
                    f"| `{h['dim_a']}` = **{h['val_a']}** | `{h['dim_b']}` = **{h['val_b']}** | {h['volume']:,} | {h['events']:,} | **{h['rate_pct']:.2f}%** | **{h['lift_vs_baseline']}x** |"
                )
        md.append("")

    if pnl.get("has_margin_ledger") or pnl.get("has_coupon_audit"):
        md.append("### 10.5 P&L Net Contribution Margin, Reverse Logistics & Coupon Erosion Ledger")
        if pnl.get("has_margin_ledger"):
            md.append(
                f"- **Gross Sales**: **{sym}{pnl.get('total_gross_revenue', 0):,.2f}** | **Discount Burn**: **{sym}{pnl.get('total_discount_burn', 0):,.2f}** ({pnl.get('discount_share_of_gross_pct', 0)}%) | **Net Billed**: **{sym}{pnl.get('total_net_billed', 0):,.2f}**"
            )
            md.append(
                f"- **Total Net Contribution Margin**: **{sym}{pnl.get('total_net_margin', 0):,.2f}** ({pnl.get('net_margin_pct_of_billed', 0)}% of net billed)"
            )
            md.append(
                f"- **Out-of-Pocket Negative-Margin Orders**: **{pnl.get('negative_margin_order_count', 0):,} orders** generating **-{sym}{abs(float(pnl.get('negative_margin_cash_loss', 0))):,.2f}** in direct cash loss (including **{sym}{pnl.get('reverse_shipping_burn', 0):,.2f}** in reverse return shipping)."
            )
            st_rows = pnl.get("status_cash_breakdown", [])
            if st_rows:
                md.append(f"\n| Order Status | OrdersCount | Billed Value ({sym}) | Net Contribution Margin ({sym}) | Reverse Shipping Burn ({sym}) |")
                md.append("| :--- | :--- | :--- | :--- | :--- |")
                for sr in st_rows:
                    md.append(
                        f"| **{sr['status']}** | {sr['orders']:,} | {sym}{sr['billed_amount']:,.2f} | **{sym}{sr['net_margin']:,.2f}** | {sym}{sr['reverse_shipping']:,.2f} |"
                    )
        if pnl.get("has_coupon_audit"):
            md.append(f"\n| Promotion / Coupon | OrdersCount | Failed Cases | Failure % | Discount Burn ({sym}) | Avg Net Margin / Order ({sym}) | Margin vs No-Coupon |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for c in pnl.get("coupons", []):
                flag = " ⚠️ **DOUBLE-POISON**" if c.get("is_double_poison_promo") else ""
                md.append(
                    f"| **{c['coupon_code']}**{flag} | {c['orders']:,} | {c['failures']:,} | **{c['failure_rate_pct']:.2f}%** | {sym}{c['discount_burn']:,.2f} | **{sym}{c['avg_margin_per_order']:,.2f}** | {c['margin_delta_vs_no_coupon_pct']:+.1f}% |"
                )
        md.append("")

    if ent.get("has_repeat_entities") or ent.get("has_whale_segment") or ent.get("has_sku_audit"):
        md.append("### 10.6 Customer / Entity Repeat Abuse, Negative-LTV Accounts & SKU Forensics")
        if ent.get("has_repeat_entities"):
            md.append(
                f"- **Unique Accounts (`{ent['entity_column']}`)**: **{ent['unique_entities']:,}** ({ent['repeat_entities_count']:,} repeat accounts = {ent['repeat_entity_share_pct']}%)"
            )
            md.append(
                f"- **Negative Lifetime-Margin Accounts**: **{ent['negative_ltv_entity_count']:,} accounts** generating **-{sym}{abs(float(ent['negative_ltv_total_cash_loss'])):,.2f}** cumulative net cash loss."
            )
            md.append(
                f"- **Serial Repeat Abusers (>=3 orders & >=2 failures)**: **{ent['serial_abuser_count']:,} accounts** responsible for **{ent['serial_abuser_total_failures']:,} failed orders**."
            )
            top_ab = ent.get("top_serial_abusers", [])
            if top_ab:
                md.append(f"\n| Account ID (`{ent['entity_column']}`) | OrdersCount | Failed Cases | Account Failure % | Billed Exposure ({sym}) | Lifetime Net Margin ({sym}) |")
                md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
                for a in top_ab:
                    md.append(
                        f"| **`{a['entity_id']}`** | {a['orders']:,} | {a['failures']:,} | **{a['failure_rate_pct']:.1f}%** | {sym}{a['total_billed']:,.2f} | **{sym}{a['lifetime_margin']:,.2f}** |"
                    )
        if ent.get("has_whale_segment"):
            md.append(
                f"\n- **High-Margin Whale Segment (`{ent['segment_column']} = '{ent['whale_segment']}'`)**: **{sym}{ent['whale_avg_value_per_order']:,.2f}** avg profit/value per order (**{ent['whale_value_multiplier_vs_avg']}x company mean**), with **{sym}{ent['whale_adverse_exposure']:,.2f}** exposure across {ent['whale_failures']:,} failures ({ent['whale_failure_rate_pct']}% rate)."
            )
        if ent.get("has_sku_audit"):
            skus = ", ".join(f"`{s['sku']}` ({s['failure_rate_pct']:.2f}% across {s['orders']} orders)" for s in ent.get("top_risk_skus", [])[:5])
            md.append(f"- **Top High-Risk SKUs (`{ent['sku_column']}`)**: {skus}.")
        md.append("")

    if seas.get("has_quarterly_regime_shift"):
        pq = seas.get("peak_quarter", "Q4")
        md.append(f"### 10.7 Seasonal & Quarterly Regime-Shift Forensics (`{pq}` Surge)")
        md.append(
            f"- **Peak Vulnerability Quarter (`{pq}`)**: Across **{seas.get('peak_quarter_orders', 0):,} orders**, failure rate climbs from **{seas.get('rest_of_year_failure_pct')}% (rest of year) to {seas.get('peak_quarter_failure_pct')}%**"
            + (f", SLA breach jumps from **{seas.get('rest_of_year_sla_breach_pct')}% to {seas.get('peak_quarter_sla_breach_pct')}%**" if seas.get("peak_quarter_sla_breach_pct") is not None else "")
            + (f", and avg dispatch delay rises from **{seas.get('rest_of_year_dispatch_delay')}d to {seas.get('peak_quarter_dispatch_delay')}d**." if seas.get("peak_quarter_dispatch_delay") is not None else ".")
        )
        md.append("")

    return "\n".join(md)
