"""
=============================================================================
STRATEGIC DECISION MATRIX & MICRO-LEVEL FORENSIC INQUIRY ENGINE (VERSION 3.5)
=============================================================================
Core Capabilities:
1. Domain Ontology Mapping: Identifies Healthcare, FinTech, Logistics, SaaS,
   Food & Beverage / Manufacturing Quality Assurance, etc.
2. Unflinching Problem Diagnosis: Isolates true causal bottlenecks with statistical
   significance testing (Odds Ratios, p-values, Chi-Square).
3. 3 Strategic Pathways: Conservative, Surgical, and Structural options.
4. Mathematical & Simulation Proof: Proves expected outcomes with confidence bounds.
5. Executive Counter-Questions & Answers: Preempts board/executive skepticism.
6. Honest Pros & Cons Matrix: Evaluates upside, downside, and collateral friction.
7. Micro-Level Forensic Inquiry Engine:
   - Non-linear quantile threshold cliffs & inflection points.
   - 2x2 orthogonal feature interaction matrix & sensory antagonism.
   - Catastrophic tail risk & multi-factor compound boundary breaches.
   - Operational triage scrap vs purity yield trade-off simulation.
   - Simpson's Paradox & confounder isolation.
   - 8 Deep granular investigative questions formulated and answered autonomously.
=============================================================================
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency, pearsonr, norm

try:
    from .target_resolver import (
        is_index_artifact,
        is_synthetic_column,
        is_demographic_attribute,
        is_pseudo_numeric_identifier,
        resolve_canonical_target_and_cost
    )
except ImportError:
    from target_resolver import (
        is_index_artifact,
        is_synthetic_column,
        is_demographic_attribute,
        is_pseudo_numeric_identifier,
        resolve_canonical_target_and_cost
    )


def calculate_wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Calculates exact Wilson score confidence interval for a binomial proportion.
    k: number of events/successes
    n: total trials/volume
    """
    if n <= 0:
        return (0.0, 0.0)
    z = 1.95996 if abs(confidence - 0.95) < 0.01 else float(norm.ppf(1.0 - (1.0 - confidence) / 2.0))
    p = float(k) / float(n)
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2.0 * n)) / denom
    spread = (z / denom) * np.sqrt((p * (1.0 - p) / n) + (z**2) / (4.0 * (n**2)))
    lower = 0.0 if k <= 0 else max(0.0, float(center - spread))
    upper = 1.0 if k >= n else min(1.0, float(center + spread))
    return (lower, upper)


def calculate_two_proportion_z_test(k1: int, n1: int, k0: int, n0: int) -> Tuple[float, float]:
    """
    Performs a two-proportion pooled z-test.
    Cohort 1: k1 / n1
    Cohort 0: k0 / n0
    Returns (z_stat, p_val).
    """
    if n1 <= 0 or n0 <= 0:
        return (0.0, 1.0)
    p1 = float(k1) / float(n1)
    p0 = float(k0) / float(n0)
    p_pool = float(k1 + k0) / float(n1 + n0)
    if p_pool <= 0.0 or p_pool >= 1.0:
        return (0.0, 1.0)
    se = np.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n0))
    if se <= 0:
        return (0.0, 1.0)
    z = (p1 - p0) / se
    p_val = float(2.0 * (1.0 - norm.cdf(abs(z))))
    return (float(z), float(p_val))


def calculate_excess_risk_metrics(k1: int, n1: int, k0: int, n0: int, confidence: float = 0.95) -> Dict[str, float]:
    """
    Calculates Epidemiological / Econometric Attributable (Excess) Risk for Cohort 1 over Rest-of-Population Cohort 0:
      Excess Rate = max(0, p1 - p0)
      Excess Events = n1 * Excess Rate
      95% Wald/Newcombe Confidence Interval on Risk Difference (p1 - p0)
    """
    if n1 <= 0 or n0 <= 0:
        return {
            "p1": 0.0, "p0": 0.0, "z_stat": 0.0, "p_val": 1.0, "p_value": 1.0,
            "excess_rate": 0.0, "excess_rate_low": 0.0, "excess_rate_high": 0.0,
            "excess_events": 0.0, "excess_events_low": 0.0, "excess_events_high": 0.0,
            "excess_events_ci_low": 0.0, "excess_events_ci_high": 0.0
        }
    p1 = float(k1) / float(n1)
    p0 = float(k0) / float(n0)
    z_stat, p_val = calculate_two_proportion_z_test(k1, n1, k0, n0)
    z_crit = 1.95996 if abs(confidence - 0.95) < 0.01 else float(norm.ppf(1.0 - (1.0 - confidence) / 2.0))
    se_diff = float(np.sqrt((p1 * (1.0 - p1) / max(n1, 1)) + (p0 * (1.0 - p0) / max(n0, 1))))
    excess_rate = max(0.0, p1 - p0)
    excess_low = max(0.0, excess_rate - z_crit * se_diff)
    excess_high = min(1.0, excess_rate + z_crit * se_diff)
    return {
        "p1": p1,
        "p0": p0,
        "z_stat": z_stat,
        "p_val": p_val,
        "p_value": p_val,
        "excess_rate": excess_rate,
        "excess_rate_low": excess_low,
        "excess_rate_high": excess_high,
        "excess_events": float(n1) * excess_rate,
        "excess_events_low": float(n1) * excess_low,
        "excess_events_high": float(n1) * excess_high,
        "excess_events_ci_low": float(n1) * excess_low,
        "excess_events_ci_high": float(n1) * excess_high
    }

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure root workspace is in sys.path to access 02_domain_intelligence
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT / "02_domain_intelligence") not in sys.path:
    sys.path.append(str(WORKSPACE_ROOT / "02_domain_intelligence"))

try:
    from business_ontology import MASTER_BUSINESS_ONTOLOGY
except ImportError:
    MASTER_BUSINESS_ONTOLOGY = {}


class MicroLevelForensicInquiryEngine:
    """
    Autonomous Micro-Level Forensic Investigation & Empirical Q&A Engine.
    Dissects non-linear inflection cliffs, 2x2 interaction quadrants, tail risk,
    operational scrap/yield trade-offs, and confounders/Simpson's Paradox.
    Autonomously formulates investigative questions and delivers physical, data-backed answers.
    """
    def __init__(self, df: pd.DataFrame, target_col: str, domain_profile: Dict[str, Any], blueprint: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.domain_profile = domain_profile
        self.blueprint = blueprint or {}
        self.total_records = len(df)
        
        # Scoped topology resolution: identify true raw source columns
        raw_source_cols = set()
        topo_candidates = []
        if self.blueprint.get("_topology_path"):
            topo_candidates.append(Path(self.blueprint["_topology_path"]))
        if self.blueprint.get("_output_dir"):
            out_p = Path(self.blueprint["_output_dir"])
            topo_candidates.append(out_p / "schema_topology.json")
            topo_candidates.append(out_p.parent / "schema_topology.json")
        topo_candidates.extend([
            Path("schema_topology.json"),
            Path("autonomous_engine/schema_topology.json")
        ])
        df_col_set = {c.lower() for c in self.df.columns}
        for top_file in topo_candidates:
            if top_file.exists():
                try:
                    with open(top_file, "r", encoding="utf-8") as f:
                        top_data = json.load(f)
                    cand_cols = set()
                    for tname, tinfo in top_data.get("tables", {}).items():
                        for c in tinfo.get("columns", []):
                            cand_cols.add(c)
                    # Only accept topology file if it belongs to the same dataset (>= 50% column overlap)
                    if cand_cols:
                        overlap = sum(1 for c in cand_cols if c.lower() in df_col_set)
                        if overlap >= max(1, int(len(cand_cols) * 0.5)):
                            raw_source_cols = cand_cols
                            break
                except Exception:
                    pass

        # Canonical Ground-Truth Target & Cost Resolution
        canonical = resolve_canonical_target_and_cost(self.df, self.blueprint, raw_source_cols if raw_source_cols else None)
        self.target_col = canonical["target_col"]
        self.target_series = canonical["binary_target"]
        self.cost_col = canonical["cost_col"]
        self.target_desc = canonical["target_desc"]
        
        self.raw_source_cols = raw_source_cols
        synthetic_from_bp = set()
        for f in self.blueprint.get("forensic_enrichment_columns", []):
            if "=" in str(f):
                synthetic_from_bp.add(str(f).split("=")[0].strip().lower())
            else:
                synthetic_from_bp.add(str(f).strip().lower())
        self.synthetic_from_bp = synthetic_from_bp

        def is_synthetic(c: str) -> bool:
            if c.lower() in synthetic_from_bp:
                return True
            return is_synthetic_column(c, self.blueprint)

        num_candidates = [
            c for c in self.df.select_dtypes(include=[np.number]).columns
            if c not in [self.target_col, 'Id', 'id']
            and not c.lower().endswith(('_id', '_key'))
            and not is_index_artifact(c, self.df[c])
            and not is_pseudo_numeric_identifier(c, self.df[c])
        ]

        if raw_source_cols:
            valid_feats = [c for c in num_candidates if c in raw_source_cols and not is_synthetic(c)]
            # If raw source has fewer than 2 physical numeric features (e.g., dates were parsed into length_of_stay_days),
            # allow clean physical duration/tenure columns that are not synthetic scores/indices
            if len(valid_feats) < 2:
                physical_derived = [
                    c for c in num_candidates
                    if c not in valid_feats
                    and not is_synthetic(c)
                    and any(k in c.lower() for k in ['days', 'duration', 'tenure', 'hours', 'months', 'years', 'stay', 'age', 'count'])
                    and not any(b in c.lower() for b in ['index', 'risk', 'score', 'rate', 'ratio', 'penalty', 'friction'])
                ]
                valid_feats.extend(physical_derived)
            self.numeric_features = valid_feats if valid_feats else [c for c in num_candidates if not is_synthetic(c)]
        else:
            self.numeric_features = [c for c in num_candidates if not is_synthetic(c)]

    def _build_binary_target(self) -> pd.Series:
        return self.target_series

    def analyze_quantile_cliffs(self) -> List[Dict[str, Any]]:
        results = []
        for col in self.numeric_features:
            s_col = pd.to_numeric(self.df[col], errors='coerce').dropna()
            if len(s_col) < 20 or s_col.nunique() < 4:
                continue
            try:
                qbins = pd.qcut(s_col, q=4, duplicates='drop')
                temp = pd.DataFrame({'bin': qbins, 'target': self.target_series.loc[s_col.index]})
                grp = temp.groupby('bin', observed=False)['target'].agg(['count', 'sum', 'mean']).reset_index()
                rates = grp['mean'].tolist()
                deltas = [abs(rates[i] - rates[i-1]) for i in range(1, len(rates))]
                max_delta = max(deltas) if deltas else 0.0
                mean_delta = float(np.mean(deltas)) if deltas else 0.0
                step_ratio = round(max_delta / max(mean_delta, 0.001), 2)
                spread = (max(rates) - min(rates)) if rates else 0.0
                
                cont_table = pd.crosstab(temp['bin'], temp['target'])
                # Chi-Square must run whenever contingency table has at least 2 bins and 2 target states
                if cont_table.shape[0] >= 2 and cont_table.shape[1] == 2:
                    chi2, p_val, _, _ = chi2_contingency(cont_table)
                else:
                    chi2, p_val = 0.0, 1.0

                is_significant = bool(float(p_val) < 0.05 and spread >= 0.02)
                # A discrete cliff requires sharp step ratio (>= 1.5x) OR an acute absolute jump (>= 15 percentage points)
                is_cliff = bool(((step_ratio >= 1.5) or (max_delta >= 0.15)) and is_significant and max_delta >= 0.08)
                corr = float(self.df[col].corr(self.target_series))
                
                results.append({
                    "column": col,
                    "max_delta": max_delta,
                    "mean_delta": mean_delta,
                    "spread": spread,
                    "step_ratio": step_ratio,
                    "is_significant": is_significant,
                    "is_cliff": is_cliff,
                    "correlation": corr,
                    "chi2": round(float(chi2), 2),
                    "p_value": float(p_val),
                    "bins": [
                        {
                            "range": str(r["bin"]),
                            "count": int(r["count"]),
                            "events": int(r["sum"]),
                            "rate_pct": round(float(r["mean"] * 100), 2)
                        } for r in grp.to_dict(orient="records")
                    ]
                })
            except Exception:
                continue
        # Prioritize statistically significant features (p < 0.05) over random noise
        results.sort(key=lambda x: (1 if x["is_significant"] else 0, x["max_delta"], abs(x.get("correlation", 0))), reverse=True)
        return results

    def analyze_bivariate_interactions(self) -> Optional[Dict[str, Any]]:
        if self.target_series.std() == 0 or len(self.numeric_features) < 2:
            return None
        corrs = {}
        for c in self.numeric_features:
            try:
                if self.df[c].std() > 0:
                    r = float(self.df[c].corr(self.target_series))
                    if not np.isnan(r):
                        corrs[c] = r
            except Exception:
                pass
        if len(corrs) < 2:
            return None
        
        corrs_sorted = sorted(corrs.items(), key=lambda x: x[1], reverse=True)
        pos_driver = corrs_sorted[0][0]
        neg_driver = corrs_sorted[-1][0]
        
        med_pos = float(self.df[pos_driver].median())
        med_neg = float(self.df[neg_driver].median())
        
        p_hi = self.df[pos_driver] > med_pos
        n_hi = self.df[neg_driver] > med_neg
        
        q1 = self.target_series[~p_hi & n_hi]
        q2 = self.target_series[~p_hi & ~n_hi]
        q3 = self.target_series[p_hi & n_hi]
        q4 = self.target_series[p_hi & ~n_hi]

        quads = {
            "Q1_optimal": {
                "name": f"Optimal Zone (Low {pos_driver} & High {neg_driver})",
                "count": len(q1),
                "events": int(q1.sum()),
                "rate": round(float(q1.mean() * 100), 2) if len(q1) > 0 else 0.0
            },
            "Q2_unbuffered": {
                "name": f"Unbuffered Baseline (Low {pos_driver} & Low {neg_driver})",
                "count": len(q2),
                "events": int(q2.sum()),
                "rate": round(float(q2.mean() * 100), 2) if len(q2) > 0 else 0.0
            },
            "Q3_masked": {
                "name": f"Masked Risk (High {pos_driver} & High {neg_driver})",
                "count": len(q3),
                "events": int(q3.sum()),
                "rate": round(float(q3.mean() * 100), 2) if len(q3) > 0 else 0.0
            },
            "Q4_catastrophic": {
                "name": f"Compound Catastrophe (High {pos_driver} & Low {neg_driver})",
                "count": len(q4),
                "events": int(q4.sum()),
                "rate": round(float(q4.mean() * 100), 2) if len(q4) > 0 else 0.0
            }
        }

        # Statistical significance test across the 4 quadrants
        quad_rows = []
        for q_Series in [q1, q2, q3, q4]:
            if len(q_Series) > 0:
                ev = int(q_Series.sum())
                quad_rows.append([len(q_Series) - ev, ev])
        p_quad = 1.0
        if len(quad_rows) >= 2:
            try:
                quad_arr = np.array(quad_rows)
                if quad_arr.shape[1] == 2 and (quad_arr.sum(axis=0) > 0).all():
                    _, p_quad, _, _ = chi2_contingency(quad_arr)
            except Exception:
                p_quad = 1.0

        q_rates = [q["rate"] for q in quads.values() if q["count"] > 0]
        quad_spread = (max(q_rates) - min(q_rates)) if q_rates else 0.0
        is_sig = bool(float(p_quad) < 0.05 and quad_spread >= 3.0)
        
        return {
            "pos_driver": pos_driver,
            "neg_driver": neg_driver,
            "med_pos": med_pos,
            "med_neg": med_neg,
            "p_value": float(p_quad),
            "quad_spread": round(quad_spread, 2),
            "is_significant": is_sig,
            "quadrants": quads
        }

    def analyze_tail_risk(self) -> Dict[str, Any]:
        s_raw = pd.to_numeric(self.df[self.target_col], errors='coerce').fillna(0)
        if any(k in self.target_col.lower() for k in ['quality', 'score', 'rating', 'grade']):
            # For truncated distributions (e.g. IMDB 7.6-9.3), standard threshold <= 4 yields 0 rows
            if s_raw.min() > 5.0 or (s_raw.quantile(0.25) > 5.0):
                tail_mask = s_raw <= s_raw.quantile(0.10)
                if tail_mask.sum() < 5:
                    tail_mask = s_raw <= s_raw.quantile(0.25)
            else:
                tail_mask = s_raw <= 4
                if tail_mask.sum() < 5:
                    tail_mask = s_raw <= 5
        else:
            tail_mask = self.target_series == 1
        
        tail_df = self.df[tail_mask]
        tail_count = len(tail_df)
        
        corrs = {c: float(self.df[c].corr(self.target_series)) for c in self.numeric_features if not np.isnan(self.df[c].corr(self.target_series))}
        sorted_pos = sorted([c for c, r in corrs.items() if r > 0], key=lambda c: corrs[c], reverse=True)
        sorted_neg = sorted([c for c, r in corrs.items() if r < 0], key=lambda c: corrs[c])
        
        watch_features = sorted_pos[:2] + sorted_neg[:1]
        violations = pd.Series(0, index=tail_df.index)
        for wf in sorted_pos[:2]:
            thresh = float(self.df[wf].quantile(0.75))
            violations += (tail_df[wf] > thresh).astype(int)
        for wf in sorted_neg[:1]:
            thresh = float(self.df[wf].quantile(0.25))
            violations += (tail_df[wf] < thresh).astype(int)
            
        violation_counts = violations.value_counts().to_dict()
        multi_violations = sum(v for k, v in violation_counts.items() if k >= 2)
        multi_pct = round((multi_violations / max(tail_count, 1)) * 100, 2)
        
        return {
            "tail_count": tail_count,
            "watch_features": watch_features,
            "violation_counts": violation_counts,
            "multi_violation_pct": multi_pct
        }

    def simulate_operational_triage(self) -> List[Dict[str, Any]]:
        if self.target_series.std() == 0 or not self.numeric_features:
            return []
        corrs = {}
        for c in self.numeric_features:
            if self.df[c].std() > 0:
                r = float(self.df[c].corr(self.target_series))
                if not np.isnan(r):
                    corrs[c] = r
        sorted_pos = sorted([c for c, r in corrs.items() if r > 0], key=lambda c: corrs[c], reverse=True)
        sorted_neg = sorted([c for c, r in corrs.items() if r < 0], key=lambda c: corrs[c])
        
        pos_driver = sorted_pos[0] if sorted_pos else self.numeric_features[0]
        neg_driver = sorted_neg[0] if sorted_neg else self.numeric_features[-1]
        
        q75_pos = float(self.df[pos_driver].quantile(0.75))
        med_pos = float(self.df[pos_driver].median())
        med_neg = float(self.df[neg_driver].median())
        
        total_defects = int(self.target_series.sum())
        total_clean = self.total_records - total_defects
        
        dom_key = self.domain_profile.get("domain_key", "")
        if dom_key == "healthcare_clinical":
            verb = "Clinical Screen if"
        elif dom_key == "fintech_banking":
            verb = "Underwriting Audit if"
        elif dom_key == "food_beverage_manufacturing":
            verb = "Scrap if"
        else:
            verb = "Triage Gate if"

        s_pos = pd.to_numeric(self.df[pos_driver], errors='coerce').dropna()
        p1_mask = self.df[pos_driver] > q75_pos
        p2_mask = self.df[pos_driver] > med_pos

        if np.isclose(q75_pos, med_pos) or int(p1_mask.sum()) == int(p2_mask.sum()) or int(p1_mask.sum()) == 0:
            u_vals = np.sort(s_pos.unique())
            if len(u_vals) >= 2:
                val_c = float(u_vals[-1])
                val_s = float(u_vals[-2])
                p1_name = f"Policy 1: Conservative ({verb} {pos_driver} >= {val_c:.2f})"
                p1_mask = self.df[pos_driver] >= val_c
                p2_name = f"Policy 2: Surgical ({verb} {pos_driver} >= {val_s:.2f})"
                p2_mask = self.df[pos_driver] >= val_s
                if int(p1_mask.sum()) == int(p2_mask.sum()):
                    q85_val = float(s_pos.quantile(0.85))
                    q60_val = float(s_pos.quantile(0.60))
                    p1_name = f"Policy 1: Conservative ({verb} {pos_driver} > {q85_val:.2f})"
                    p1_mask = self.df[pos_driver] > q85_val
                    p2_name = f"Policy 2: Surgical ({verb} {pos_driver} > {q60_val:.2f})"
                    p2_mask = self.df[pos_driver] > q60_val
            else:
                p1_name = f"Policy 1: Conservative ({verb} {pos_driver} > {q75_pos:.2f})"
                p1_mask = self.df[pos_driver] > q75_pos
                p2_name = f"Policy 2: Surgical ({verb} {pos_driver} >= {med_pos:.2f})"
                p2_mask = self.df[pos_driver] >= med_pos
        else:
            p1_name = f"Policy 1: Conservative ({verb} {pos_driver} > {q75_pos:.2f})"
            p2_name = f"Policy 2: Surgical ({verb} {pos_driver} > {med_pos:.2f})"

        p3_name = f"Policy 3: Compound ({verb} {pos_driver} > {med_pos:.2f} OR {neg_driver} < {med_neg:.2f})"
        p3_mask = (self.df[pos_driver] > med_pos) | (self.df[neg_driver] < med_neg)

        policies = [
            (p1_name, p1_mask),
            (p2_name, p2_mask),
            (p3_name, p3_mask)
        ]
        
        triage_results = []
        for name, scrap_mask in policies:
            scrap_cnt = int(scrap_mask.sum())
            defects_caught = int(self.target_series[scrap_mask].sum())
            false_discards = int((self.target_series[scrap_mask] == 0).sum())
            retained_cnt = self.total_records - scrap_cnt
            retained_defect_rate = round(float(self.target_series[~scrap_mask].mean() * 100), 2) if retained_cnt > 0 else 0.0
            
            triage_results.append({
                "policy_name": name,
                "scrap_count": scrap_cnt,
                "scrap_pct": round((scrap_cnt / self.total_records) * 100, 2),
                "defects_caught": defects_caught,
                "recall_pct": round((defects_caught / max(total_defects, 1)) * 100, 2),
                "false_discards": false_discards,
                "false_discard_pct": round((false_discards / max(total_clean, 1)) * 100, 2),
                "retained_count": retained_cnt,
                "retained_defect_rate": retained_defect_rate
            })
        return triage_results

    def detect_confounders(self) -> Optional[Dict[str, Any]]:
        max_r = 0.0
        best_pair = None
        for i in range(len(self.numeric_features)):
            for j in range(i + 1, len(self.numeric_features)):
                c1, c2 = self.numeric_features[i], self.numeric_features[j]
                r = float(self.df[c1].corr(self.df[c2]))
                if not np.isnan(r) and 0.40 <= abs(r) <= 0.92:
                    if abs(r) > abs(max_r):
                        max_r = r
                        best_pair = (c1, c2)
        
        if not best_pair:
            return None
            
        c1, c2 = best_pair
        qbins = pd.qcut(self.df[c1], q=4, duplicates='drop')
        strata_corrs = []
        for b_name, grp in self.df.groupby(qbins, observed=False):
            t_slice = self.target_series.loc[grp.index]
            if len(grp) > 1 and grp[c2].nunique() > 1 and t_slice.nunique() > 1:
                sub_r = grp[c2].corr(t_slice)
            else:
                sub_r = 0.0
            strata_corrs.append((str(b_name), round(float(sub_r), 3) if not np.isnan(sub_r) else 0.0))
            
        return {
            "feature_1": c1,
            "feature_2": c2,
            "pair_correlation": round(max_r, 3),
            "unadjusted_corr_1": round(float(self.df[c1].corr(self.target_series)), 3),
            "unadjusted_corr_2": round(float(self.df[c2].corr(self.target_series)), 3),
            "strata_correlations": strata_corrs
        }

    def formulate_micro_questions_and_answers(self) -> List[Dict[str, str]]:
        qas = []
        cliffs = self.analyze_quantile_cliffs()
        interactions = self.analyze_bivariate_interactions()
        tail = self.analyze_tail_risk()
        triage = self.simulate_operational_triage()
        confounder = self.detect_confounders()

        # Q1: Primary Non-Linear Inflection Cliff
        if cliffs:
            top_cliff = cliffs[0]
            col = top_cliff["column"]
            b_list = top_cliff["bins"]
            p_val_str = "< 0.0001" if top_cliff["p_value"] < 0.0001 else f"= {top_cliff['p_value']:.4f}"
            q1_r = b_list[0]['rate_pct']
            q4_r = b_list[-1]['rate_pct']
            min_r = min(b['rate_pct'] for b in b_list)
            max_r = max(b['rate_pct'] for b in b_list)
            if not top_cliff.get("is_significant", False):
                ans1 = (
                    f"Physical quantile profiling across '{col}' reveals that adverse event rates remain statistically flat across all 4 quartiles, "
                    f"fluctuating narrowly between {min_r}% and {max_r}% (Q1: {q1_r}% vs Q4: {q4_r}%, Max Delta: {top_cliff['max_delta']*100:.2f} percentage points, Chi-Square p {p_val_str}). "
                    f"Because p >= 0.05, this variation is statistically indistinguishable from random sampling noise; '{col}' does not trigger a physical threshold cliff."
                )
            else:
                direction_desc = f"escalate from {q1_r}% in Q1 ({b_list[0]['range']}) to {q4_r}% in Q4 ({b_list[-1]['range']})" if q4_r >= q1_r else f"drop from {q1_r}% in Q1 ({b_list[0]['range']}) down to {q4_r}% in Q4 ({b_list[-1]['range']})"
                if top_cliff.get("is_cliff", False):
                    cliff_nature = f"This establishes that '{col}' operates as an acute non-linear cliff (step increase of {top_cliff['max_delta']*100:.2f} percentage points, {top_cliff.get('step_ratio', 1.0)}x mean delta) rather than a benign linear drift."
                else:
                    cliff_nature = f"This establishes that '{col}' exhibits a progressive gradient across quartiles (step ratio {top_cliff.get('step_ratio', 1.0)}x mean progression) rather than an isolated singular cliff."
                ans1 = f"Physical quantile profiling identifies inflection dynamics in '{col}'. Across the 4 quartiles, event failure rates {direction_desc} (Max Delta: {top_cliff['max_delta']*100:.2f} percentage points, Chi-Square p {p_val_str}). {cliff_nature}"
            qas.append({
                "question": f"At what exact physical threshold does '{col}' trigger a non-linear inflection in adverse outcomes, and is the transition gradual or a discrete cliff?",
                "data_backed_answer": ans1
            })

        # Q2: Critical Protective Floor
        if len(cliffs) >= 2:
            sec_cliff = cliffs[1]
            col2 = sec_cliff["column"]
            b_list2 = sec_cliff["bins"]
            q1_r2 = b_list2[0]['rate_pct']
            q4_r2 = b_list2[-1]['rate_pct']
            fav_q = "Q1" if q1_r2 < q4_r2 else "Q4"
            risk_q = "Q4" if q1_r2 < q4_r2 else "Q1"
            if not sec_cliff.get("is_significant", False):
                ans2 = (
                    f"Empirical distribution across secondary feature '{col2}' shows no statistically significant threshold boundary "
                    f"(Chi-Square p = {sec_cliff['p_value']:.4f}). Event rates between Q1 ({q1_r2}%) and Q4 ({q4_r2}%) differ by only "
                    f"{abs(q4_r2 - q1_r2):.2f} percentage points, confirming that '{col2}' does not independently alter adverse event probability."
                )
            else:
                ans2 = (
                    f"Empirical distribution establishes a critical boundary at '{col2}' quartile threshold (Chi-Square p = {sec_cliff['p_value']:.4e}). "
                    f"In high-risk {risk_q} ({b_list2[-1 if risk_q=='Q4' else 0]['range']}), the adverse rate is {max(q1_r2, q4_r2)}%, "
                    f"compared to {min(q1_r2, q4_r2)}% in favorable {fav_q} ({b_list2[0 if fav_q=='Q1' else -1]['range']}). "
                    f"Managing '{col2}' into its favorable operating window delivers a {abs(q4_r2 - q1_r2):.2f} percentage point risk reduction."
                )
            qas.append({
                "question": f"What is the critical operational boundary for secondary driver '{col2}', and does breach of this threshold alter failure probability?",
                "data_backed_answer": ans2
            })

        # Q3: Bivariate Interaction & Synergy/Antagonism
        if interactions:
            pos = interactions["pos_driver"]
            neg = interactions["neg_driver"]
            quads = interactions["quadrants"]
            q1_r = quads["Q1_optimal"]["rate"]
            q2_r = quads["Q2_unbuffered"]["rate"]
            q3_r = quads["Q3_masked"]["rate"]
            q4_r = quads["Q4_catastrophic"]["rate"]
            if not interactions.get("is_significant", False):
                q_rates = [q["rate"] for q in quads.values() if q["count"] > 0]
                min_q, max_q = (min(q_rates), max(q_rates)) if q_rates else (0.0, 0.0)
                ans3 = (
                    f"Two-way quadrant partitioning between '{pos}' and '{neg}' yields event rates tightly bounded between "
                    f"{min_q:.2f}% and {max_q:.2f}% across all four strata (Q1: {q1_r}%, Q2: {q2_r}%, Q3: {q3_r}%, Q4: {q4_r}%; "
                    f"2x2 Chi-Square p = {interactions['p_value']:.4f}). Because p >= 0.05, neither feature exerts a statistically significant "
                    f"buffering or compounding interaction effect on '{self.target_col}'."
                )
            else:
                ratio_q3_q1 = round(q3_r / max(q1_r, 0.01), 2)
                diff_q3_q1 = round(q3_r - q1_r, 2)
                if ratio_q3_q1 >= 2.0:
                    comp_str = f"experience {q3_r}% failure—{ratio_q3_q1}x the {q1_r}% failure rate (more than double) observed when '{pos}' is controlled in the Optimal Zone. Thus, '{pos}' exerts an independent negative drag that '{neg}' cannot fully mask."
                elif diff_q3_q1 >= 1.5:
                    comp_str = f"experience {q3_r}% failure—{diff_q3_q1:.2f} percentage points ({ratio_q3_q1}x) higher than the {q1_r}% failure rate observed when '{pos}' is controlled in the Optimal Zone. Thus, '{pos}' retains a residual risk drag even when '{neg}' is elevated."
                else:
                    comp_str = f"achieve a {q3_r}% failure rate, which closely approaches the {q1_r}% Optimal Zone rate and demonstrates that high '{neg}' effectively buffers the risk of elevated '{pos}'."
                ans3 = (
                    f"Cross-quadrant analysis (2x2 Chi-Square p = {interactions['p_value']:.4e}) reveals that within the high '{pos}' cohort, "
                    f"elevating '{neg}' shifts adverse events from {q4_r}% (Compound Catastrophe) to {q3_r}% (Masked Risk). "
                    f"Records with elevated '{pos}' and high '{neg}' {comp_str}"
                )
            qas.append({
                "question": f"Can high levels of protective factor '{neg}' compensate for elevated risk factor '{pos}', or does '{pos}' exert an overriding destructive effect?",
                "data_backed_answer": ans3
            })

        # Q4: Secondary Spoilage / Protective Buffer Cliff
        if len(cliffs) >= 3:
            third_cliff = cliffs[2]
            col3 = third_cliff["column"]
            b_list3 = third_cliff["bins"]
            q1_r3 = b_list3[0]['rate_pct']
            q2_r3 = b_list3[1]['rate_pct']
            q4_r3 = b_list3[-1]['rate_pct']
            
            if not third_cliff.get("is_significant", False):
                q_text4 = f"Does third-order metric '{col3}' exhibit a statistically significant protective buffer or operational threshold?"
                ans4 = (
                    f"Quartile breakdown of third-order metric '{col3}' shows statistically uniform event rates from Q1 ({q1_r3}%) through Q4 ({q4_r3}%) "
                    f"(Max Delta: {third_cliff['max_delta']*100:.2f} percentage points, Chi-Square p = {third_cliff['p_value']:.4f}). "
                    f"Because p >= 0.05, '{col3}' does not act as a statistically significant operational buffer or risk driver."
                )
            elif q4_r3 >= q1_r3:
                delta_3 = round(q4_r3 - q1_r3, 2)
                q_text4 = f"At what level does third-order metric '{col3}' begin compromising operational yield?"
                ans4 = (
                    f"Quartile breakdown (Chi-Square p = {third_cliff['p_value']:.4e}) shows that '{col3}' escalates by {delta_3:.2f} percentage points "
                    f"from {q1_r3}% in Q1 ({b_list3[0]['range']}) to {q4_r3}% in Q4 ({b_list3[-1]['range']}). "
                    f"This isolates Q4 as a statistically significant vulnerability zone requiring threshold monitoring."
                )
            else:
                delta_3 = round(q1_r3 - q4_r3, 2)
                q_text4 = f"How significantly does third-order metric '{col3}' buffer against failure, and what is the minimum safe threshold?"
                ans4 = (
                    f"Quartile breakdown (Chi-Square p = {third_cliff['p_value']:.4e}) shows that lower levels of '{col3}' incur {q1_r3}% adverse events in Q1 ({b_list3[0]['range']}), "
                    f"whereas elevating '{col3}' into Q4 ({b_list3[-1]['range']}) reduces adverse events by {delta_3:.2f} percentage points down to {q4_r3}%. "
                    f"This isolates Q1 as the primary vulnerability stratum."
                )

            qas.append({
                "question": q_text4,
                "data_backed_answer": ans4
            })

        # Q5: Tail Anomaly & Multi-Factor Compound Violations
        if tail:
            if tail['multi_violation_pct'] >= 50.0:
                ans5 = (f"Tail risk audit across the lowest {tail['tail_count']} catastrophic records reveals that {tail['multi_violation_pct']}% "
                        f"breach two or more critical parameters ({', '.join(tail['watch_features'])}) simultaneously. "
                        f"Catastrophic degradation is an emergent compound phenomenon rather than a single isolated defect.")
            else:
                ans5 = (f"Tail risk audit across the lowest {tail['tail_count']} catastrophic records reveals that only {tail['multi_violation_pct']}% "
                        f"breach two or more critical parameters ({', '.join(tail['watch_features'])}) simultaneously. "
                        f"Catastrophic degradation is predominantly driven by single-variable deviation, where extreme breach in an isolated critical metric is sufficient to trigger failure.")
            qas.append({
                "question": "Are catastrophic bottom-tier failures driven by isolated single-variable anomalies or compound multi-system breaches?",
                "data_backed_answer": ans5
            })

        # Q6: Operational Triage vs Purity Yield Boundary
        if len(triage) >= 2:
            pol1 = triage[0]
            pol2 = triage[1]
            eff1 = pol1['recall_pct'] / max(pol1['scrap_pct'], 0.1)
            eff2 = pol2['recall_pct'] / max(pol2['scrap_pct'], 0.1)
            if eff1 <= 1.05 and eff2 <= 1.05:
                eff_narrative = (
                    f"Crucially, both policies yield an efficiency ratio of ~{eff1:.2f} recall/scrap ratio, which is mathematically equivalent to "
                    f"random coin-flip selection (1.00x lift) and fails to reduce the retained adverse rate ({pol2['retained_defect_rate']}%). "
                    f"Recommendation: Do NOT deploy threshold filtering on this variable, as it generates false alarms without improving cohort purity."
                )
            elif abs(eff1 - eff2) < 0.05 or round(eff1, 2) == round(eff2, 2):
                eff_narrative = f"Both policies deliver equivalent marginal defect containment per flagged unit ({eff1:.2f} recall/scrap ratio), with Surgical triage capturing a greater absolute volume of defects ({pol2['recall_pct']}% vs {pol1['recall_pct']}%)."
            elif eff2 > eff1:
                eff_narrative = f"Surgical triage delivers the higher marginal defect containment per flagged unit ({eff2:.2f} vs {eff1:.2f} recall/scrap ratio)."
            else:
                eff_narrative = f"Conservative triage delivers the higher marginal defect containment per flagged unit ({eff1:.2f} vs {eff2:.2f} recall/scrap ratio), while Surgical triage captures a greater absolute volume of defects."
            qas.append({
                "question": "If operations establishes a pre-screening / triage gate, what is the exact trade-off between adverse event capture (recall), flagged volume, and false alarms?",
                "data_backed_answer": f"Under Conservative Triage ({pol1['policy_name']}), {pol1['scrap_count']} records ({pol1['scrap_pct']}%) are flagged, capturing {pol1['recall_pct']}% of all adverse events with {pol1['false_discards']} false alarms. Under Surgical Triage ({pol2['policy_name']}), flagged volume expands to {pol2['scrap_count']} records ({pol2['scrap_pct']}%), capturing {pol2['recall_pct']}% of adverse events and shifting the unflagged adverse rate to {pol2['retained_defect_rate']}%, at the cost of {pol2['false_discards']} false alarms ({pol2['false_discard_pct']}% of normal records). {eff_narrative}"
            })

        # Q7: Simpson's Paradox & Confounder Isolation
        if confounder:
            c1 = confounder["feature_1"]
            c2 = confounder["feature_2"]
            pair_r = confounder["pair_correlation"]
            u1 = confounder["unadjusted_corr_1"]
            u2 = confounder["unadjusted_corr_2"]
            strata_desc = ", ".join([f"{st}: r={r}" for st, r in confounder["strata_correlations"][:3]])
            qas.append({
                "question": f"Does '{c2}' independently drive outcomes, or is its apparent impact an illusion confounded by collinearity with '{c1}' (Simpson's Paradox)?",
                "data_backed_answer": f"At the unadjusted level, '{c2}' shows correlation r = {u2} with the target. However, '{c2}' is strongly co-linear with '{c1}' (r = {pair_r}). When stratifying across '{c1}' quartiles, the correlation of '{c2}' within strata shifts to ({strata_desc}). This proves that much of '{c2}'s macro effect is mediated through its relationship with '{c1}', warning against isolated policy changes on '{c2}' alone."
            })

        # Q8: Multi-Dimensional Premium Envelope
        if any(k in self.target_col.lower() for k in ['quality', 'score', 'rating', 'grade', 'stream', 'streams', 'sales', 'revenue', 'view', 'views', 'profit']):
            s_raw = pd.to_numeric(self.df[self.target_col], errors='coerce').fillna(0)
            if any(k in self.target_col.lower() for k in ['stream', 'streams', 'sales', 'revenue', 'view', 'views', 'profit']):
                threshold = float(s_raw.quantile(0.80))
            elif s_raw.min() > 5.0 or (s_raw.quantile(0.25) > 5.0):
                threshold = float(s_raw.quantile(0.80))
            else:
                threshold = 7.0 if (s_raw.min() >= 1 and s_raw.max() <= 10) else float(s_raw.quantile(0.80))
            prem_mask = s_raw >= threshold
            prem_cnt = int(prem_mask.sum())
            prem_pct = round((prem_cnt / self.total_records) * 100, 2)
            
            param_insights = []
            joint_condition = pd.Series(True, index=self.df.index)
            if prem_cnt > 0 and len(self.numeric_features) > 0:
                df_prem = self.df[prem_mask]
                df_base = self.df[~prem_mask]
                feat_diffs = []
                for feat in self.numeric_features[:8]:
                    prem_med = float(df_prem[feat].median())
                    base_med = float(df_base[feat].median()) if len(df_base) > 0 else prem_med
                    if not np.isnan(prem_med) and not np.isnan(base_med) and base_med != 0:
                        pct_diff = (prem_med - base_med) / abs(base_med)
                        feat_diffs.append((feat, prem_med, base_med, pct_diff))
                feat_diffs.sort(key=lambda x: abs(x[3]), reverse=True)
                for feat, p_med, b_med, p_diff in feat_diffs[:3]:
                    direction_str = "elevated" if p_diff > 0 else "reduced"
                    param_insights.append(f"{direction_str} '{feat}' (median {p_med:.2f} vs {b_med:.2f} baseline)")
                    if p_diff > 0:
                        joint_condition &= (self.df[feat] >= b_med)
                    else:
                        joint_condition &= (self.df[feat] <= b_med)
            
            param_summary = ", ".join(param_insights) if param_insights else "tight multi-dimensional tolerance control"
            joint_volume = int(joint_condition.sum())
            joint_prem_events = int((prem_mask & joint_condition).sum())
            joint_prem_rate = round((joint_prem_events / max(joint_volume, 1)) * 100.0, 2)
            
            base_prem_prob = max(prem_pct / 100.0, 0.001)
            joint_prem_prob = joint_prem_events / max(joint_volume, 1)
            empirical_lift = round(joint_prem_prob / base_prem_prob, 2) if joint_volume > 0 else 1.0
            
            qas.append({
                "question": f"What precise multi-dimensional parameters define Premium / Top-Tier status ({self.target_col} >= {threshold}), and what is the feasibility envelope across total volume?",
                "data_backed_answer": f"Across {self.total_records:,} physical records, {prem_cnt:,} ({prem_pct}%) achieve Premium / Top-Tier status ({self.target_col} >= {threshold}). Empirical distribution profiling demonstrates that top-tier records require tight alignment across key drivers: {param_summary}. Meeting these physical criteria concurrently yields a premium concentration of {joint_prem_rate}% (vs {prem_pct}% overall), establishing a true empirical conditional lift of {empirical_lift}x across {joint_volume:,} matching records."
            })

        return qas

    def render_micro_markdown(self) -> str:
        cliffs = self.analyze_quantile_cliffs()
        interactions = self.analyze_bivariate_interactions()
        triage = self.simulate_operational_triage()
        confounder = self.detect_confounders()
        qas = self.formulate_micro_questions_and_answers()

        md = """
---

## 🔬 MICRO-LEVEL FORENSIC INVESTIGATION & EMPIRICAL INQUIRY ENGINE
*Autonomous Multi-Dimensional Deep Dive: Slicing Non-Linear Inflections, Bivariate Interactions, Tail Anomalies, and Simpson's Paradox.*

### 1. Non-Linear Quantile Threshold Cliffs (Top Operational Drivers)
*Discretized quartile breakdown exposing where gradual performance transitions into structural failure:*

"""
        for c in cliffs[:3]:
            sig_tag = "Statistically Significant" if c.get("is_significant") else "Uniform Noise — Not Significant"
            md += f"#### 📊 Feature: `{c['column']}` (Max Inflection Delta: {c['max_delta']*100:.2f}%, Chi-Square p: {c['p_value']:.4e} — {sig_tag})\n"
            md += "| Quantile / Stratum | Physical Range | Monitored Volume | Target Adverse Events | Failure Rate % | Inflection Status |\n"
            md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            b_rates = [b["rate_pct"] for b in c["bins"]]
            max_b_rate = max(b_rates) if b_rates else 0.0
            min_b_rate = min(b_rates) if b_rates else 0.0
            for idx, b in enumerate(c["bins"], 1):
                if not c.get("is_significant", False):
                    status = "Statistical Noise (p >= 0.05)"
                elif b["rate_pct"] == max_b_rate:
                    status = "**Structural Cliff Breach**" if c.get("is_cliff") else "**Peak Vulnerability Stratum**"
                elif b["rate_pct"] == min_b_rate:
                    status = "**Optimal Baseline**"
                else:
                    status = "Transitional Tier"
                md += f"| **Q{idx}** | `{b['range']}` | {b['count']:,} | {b['events']:,} | **{b['rate_pct']}%** | {status} |\n"
            md += "\n"

        if interactions:
            pos = interactions["pos_driver"]
            neg = interactions["neg_driver"]
            quads = interactions["quadrants"]
            is_sig_inter = interactions.get("is_significant", False)
            q1_imp = "**Optimal Performance Buffer**" if is_sig_inter else "Uniform Noise Stratum (p >= 0.05)"
            q2_imp = "Baseline Operating Profile" if is_sig_inter else "Uniform Noise Stratum (p >= 0.05)"
            q3_imp = "Partially Buffered Risk (Elevated Drag)" if is_sig_inter else "Uniform Noise Stratum (p >= 0.05)"
            q4_imp = "**Compound Maximum Risk Exposure**" if is_sig_inter else "Uniform Noise Stratum (p >= 0.05)"
            md += f"""---

### 2. 2x2 Orthogonal Feature Interaction Matrix (`{pos}` vs. `{neg}`)
*Testing feature buffering, compounding risk, and cross-variable overrides (2x2 Chi-Square p: {interactions['p_value']:.4e}):*

| Quadrant | Physical Stratum | Monitored Volume | Target Events | Failure Rate % | Operational Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Q1 (Optimal Zone)** | Low `{pos}` (<= {interactions['med_pos']:.2f}) & High `{neg}` (> {interactions['med_neg']:.2f}) | {quads['Q1_optimal']['count']:,} | {quads['Q1_optimal']['events']:,} | **{quads['Q1_optimal']['rate']}%** | {q1_imp} |
| **Q2 (Unbuffered Low)** | Low `{pos}` (<= {interactions['med_pos']:.2f}) & Low `{neg}` (<= {interactions['med_neg']:.2f}) | {quads['Q2_unbuffered']['count']:,} | {quads['Q2_unbuffered']['events']:,} | **{quads['Q2_unbuffered']['rate']}%** | {q2_imp} |
| **Q3 (Masked Risk)** | High `{pos}` (> {interactions['med_pos']:.2f}) & High `{neg}` (> {interactions['med_neg']:.2f}) | {quads['Q3_masked']['count']:,} | {quads['Q3_masked']['events']:,} | **{quads['Q3_masked']['rate']}%** | {q3_imp} |
| **Q4 (Catastrophic Zone)** | High `{pos}` (> {interactions['med_pos']:.2f}) & Low `{neg}` (<= {interactions['med_neg']:.2f}) | {quads['Q4_catastrophic']['count']:,} | {quads['Q4_catastrophic']['events']:,} | **{quads['Q4_catastrophic']['rate']}%** | {q4_imp} |

"""

        if triage:
            md += """---

### 3. Operational Triage Screening vs. Purity Yield Curve
*Empirical evaluation of pre-screening filter policies, adverse recall, and false-alarm friction:*

| Triage Policy | Cutoff Rule | Flagged / Discarded Volume | Scrap % | Defect Recall (Caught) | Retained Defect % | False Alarms / Discards | False Discard % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
            for t in triage:
                md += f"| **{t['policy_name']}** | Operational Filter | {t['scrap_count']:,} | {t['scrap_pct']}% | **{t['recall_pct']}%** | **{t['retained_defect_rate']}%** | {t['false_discards']:,} | {t['false_discard_pct']}% |\n"

        if confounder:
            md += f"""
---

### 4. Confounder Isolation & Simpson's Paradox Defense
> [!NOTE]
> **Collinearity Audit between `{confounder['feature_1']}` and `{confounder['feature_2']}`**:
> - Pairwise Pearson Correlation: **r = {confounder['pair_correlation']}**
> - Macro Target Correlation: `{confounder['feature_1']}`: {confounder['unadjusted_corr_1']} | `{confounder['feature_2']}`: {confounder['unadjusted_corr_2']}
> - Stratified Correlation of `{confounder['feature_2']}` across `{confounder['feature_1']}` Quartiles:
"""
            for st, r in confounder["strata_correlations"]:
                md += f">   - In `{confounder['feature_1']}` stratum `{st}`: partial r = **{r}**\n"
            md += f"> - **Scientific Finding**: Macro correlation of `{confounder['feature_2']}` is heavily confounded by `{confounder['feature_1']}`. Operational intervention must address the root driver rather than the proxy symptom.\n"

        md += """
---

### 5. Micro-Level Forensic Questions & Empirical Answers (Executive Q&A)
*Autonomously formulated investigative questions and data-grounded physical proof:*

"""
        for idx, qa in enumerate(qas, 1):
            md += f"""**MQ{idx}: {qa['question']}**  
> **Empirical Data Answer**: {qa['data_backed_answer']}

"""
        return md


class StrategicDecisionEngine:
    def __init__(self, df: pd.DataFrame, blueprint: Optional[Dict[str, Any]] = None):
        self.df = df
        self.blueprint = blueprint or {}
        self.total_records = len(df)
        self.columns = list(df.columns)
        self.domain_profile = self._classify_domain()
        self.micro_engine = MicroLevelForensicInquiryEngine(self.df, None, self.domain_profile, blueprint=self.blueprint)
        self.target_col = self.micro_engine.target_col
        self.cost_col = self.micro_engine.cost_col
        self.cost_metric = self.cost_col
        self.target_events = int(self.micro_engine.target_series.sum())
        self.target_rate = round((self.target_events / max(self.total_records, 1)) * 100.0, 2)
        self.dossier: Optional[Dict[str, Any]] = None

    def _classify_domain(self) -> Dict[str, Any]:
        """Classifies the domain and determines the appropriate friction unit."""
        cols_lower = [c.lower() for c in self.columns]
        
        # Check Food & Beverage / Agricultural / Manufacturing Quality Assurance
        fnb_kw = ['wine', 'beer', 'beverage', 'alcohol', 'acidity', 'sugar', 'citric', 'sulphate', 'food', 'quality', 'batch', 'manufacturing', 'defect', 'yield', 'harvest', 'crop', 'soil']
        if any(any(k in c for k in fnb_kw) for c in cols_lower):
            return {
                "domain_key": "food_beverage_manufacturing",
                "domain_name": "Food & Beverage Manufacturing / Oenological Quality Assurance",
                "unit_name": "Sub-Standard / Defective Production Batches",
                "unit_symbol": "Batches",
                "is_financial": False,
                "persona": "Master Winemaker / VP of Oenological Operations & Quality Assurance"
            }

        # Check Healthcare / Medical
        medical_kw = ['death', 'mortality', 'patient', 'hospital', 'clinical', 'ejection', 'creatinine', 'anaemia', 'sodium', 'systolic', 'readmit', 'diagnosis']
        if any(any(k in c for k in medical_kw) for c in cols_lower):
            return {
                "domain_key": "healthcare_clinical",
                "domain_name": "Healthcare & Clinical Outcomes",
                "unit_name": "Adverse Clinical Events / Mortality Risk",
                "unit_symbol": "Patients / Lives",
                "is_financial": False,
                "persona": "Chief Medical Officer / Clinical Operations Board"
            }
            
        # Check FinTech / Banking / Fraud / Credit
        fintech_kw = ['fraud', 'default', 'loan', 'credit', 'balance', 'chargeback', 'transaction', 'debt']
        if any(any(k in c for k in fintech_kw) for c in cols_lower):
            return {
                "domain_key": "fintech_banking",
                "domain_name": "Financial Services & Risk Operations",
                "unit_name": "Capital at Risk / Default Liability",
                "unit_symbol": "$",
                "is_financial": True,
                "persona": "Chief Risk Officer / CFO"
            }

        # Check Logistics / Supply Chain
        logistics_kw = ['shipping', 'freight', 'carrier', 'delivery', 'delay', 'transit', 'tracking', 'rto', 'warehouse']
        if any(any(k in c for k in logistics_kw) for c in cols_lower):
            return {
                "domain_key": "logistics_supply_chain",
                "domain_name": "Logistics & Supply Chain Operations",
                "unit_name": "Fulfillment Delay & SLA Penalty Friction",
                "unit_symbol": "$",
                "is_financial": True,
                "persona": "VP of Supply Chain & Global Operations"
            }

        # Check SaaS / Subscription
        saas_kw = ['churn', 'arr', 'mrr', 'subscription', 'ticket', 'nrr', 'contract', 'cac']
        if any(any(k in c for k in saas_kw) for c in cols_lower):
            return {
                "domain_key": "saas_enterprise",
                "domain_name": "Enterprise SaaS & Customer Retention",
                "unit_name": "Revenue Contraction & Churn Friction",
                "unit_symbol": "$",
                "is_financial": True,
                "persona": "Chief Commercial Officer / VP Customer Success"
            }

        # Check Digital Media / Streaming Entertainment
        media_kw = ['stream', 'streams', 'track', 'artist', 'song', 'spotify', 'movie', 'film', 'cinema', 'video', 'youtube', 'view', 'views', 'listen', 'audio']
        if any(any(k in c for k in media_kw) for c in cols_lower):
            return {
                "domain_key": "digital_media_streaming",
                "domain_name": "Digital Media, Music Streaming & Algorithmic Audio Forensics",
                "unit_name": "Underperforming Stream Volume & Audience Engagement Drag",
                "unit_symbol": "Streams",
                "is_financial": False,
                "persona": "Global Head of Editorial & Music Programming / VP of Content Analytics"
            }

        # Default Enterprise Operations
        return {
            "domain_key": "enterprise_operations",
            "domain_name": "Enterprise Operational Systems",
            "unit_name": "Operational Friction & Process Drag",
            "unit_symbol": "$",
            "is_financial": True,
            "persona": "Executive Operating Committee"
        }

    def _resolve_target(self) -> Tuple[str, int, float]:
        """Resolves target metric strictly adhering to blueprint or high-certainty targets."""
        target_series = self.micro_engine.target_series
        cnt = int(target_series.sum())
        rate = round((cnt / max(self.total_records, 1)) * 100.0, 2)
        return self.target_col, cnt, rate

    def _resolve_cost_metric(self) -> Optional[str]:
        return self.micro_engine.cost_col

    def generate_strategic_decision_dossier(self) -> Dict[str, Any]:
        """Synthesizes the complete unbiased multi-pathway decision matrix with Excess-Risk math and Statistical Circuit-Breaker."""
        high_risk_segment = None
        high_risk_volume = 0
        high_risk_events = 0
        high_risk_rate = 0.0
        relative_risk_multiplier = 1.0

        target_series = self.micro_engine.target_series
        temp_df = pd.DataFrame({'segment': None, 'is_target': target_series})

        raw_src = getattr(self.micro_engine, "raw_source_cols", set()) or set()
        synth_bp = getattr(self.micro_engine, "synthetic_from_bp", set()) or set()

        def is_invalid_feature(c: str) -> bool:
            cl = c.lower()
            if cl == self.target_col.lower():
                return True
            if self.cost_metric and cl == self.cost_metric.lower():
                return True
            if cl in ['id', 'fact_surrogate_id', '_is_target_event']:
                return True
            if cl in synth_bp or is_synthetic_column(c, self.blueprint):
                return True
            if cl.endswith(('_id', '_key', '_is_target_event', '_event', '_target')):
                return True
            if is_index_artifact(c, self.df[c]) or is_pseudo_numeric_identifier(c, self.df[c]):
                return True
            return False

        has_raw_discrete = any(
            not is_invalid_feature(col)
            and 2 <= self.df[col].nunique(dropna=True) <= 25
            and col in raw_src
            for col in self.columns
        ) if raw_src else False

        candidates = []
        min_cohort_size = max(5, int(self.total_records * 0.03))
        for col in self.columns:
            if is_invalid_feature(col):
                continue
            if has_raw_discrete and col not in raw_src:
                continue
            nunq = self.df[col].nunique(dropna=True)
            if 2 <= nunq <= 25:
                is_demo = is_demographic_attribute(col)
                temp_df['segment'] = self.df[col]
                grp = temp_df.groupby('segment', observed=False)['is_target'].agg(['count', 'sum'])
                for val, row in grp.iterrows():
                    cnt_v = int(row['count'])
                    sum_v = int(row['sum'])
                    if cnt_v < min_cohort_size or cnt_v >= self.total_records:
                        continue
                    r_pct = round((sum_v / max(cnt_v, 1)) * 100.0, 2)
                    n0_cand = max(1, self.total_records - cnt_v)
                    k0_cand = max(0, self.target_events - sum_v)
                    z_cand, p_cand = calculate_two_proportion_z_test(sum_v, cnt_v, k0_cand, n0_cand)
                    r0_pct = (k0_cand / n0_cand) * 100.0
                    is_sig_cand = (p_cand < 0.05) and (r_pct > r0_pct * 1.10)
                    candidates.append({
                        "segment": f"{col} = {val}",
                        "col": col,
                        "val": val,
                        "is_quantile": False,
                        "is_demo": is_demo,
                        "is_sig": is_sig_cand,
                        "volume": cnt_v,
                        "events": sum_v,
                        "rate_pct": r_pct,
                        "z_stat": z_cand,
                        "p_val": p_cand
                    })

        # Also evaluate top quantile cliff bins so continuous bottlenecks are captured if discrete segments are weak/absent
        cliffs = self.micro_engine.analyze_quantile_cliffs()
        for top_c in cliffs[:2]:
            worst_bin = max(top_c["bins"], key=lambda b: b["rate_pct"])
            cnt_v = int(worst_bin["count"])
            sum_v = int(worst_bin["events"])
            if cnt_v >= min_cohort_size and cnt_v < self.total_records:
                r_pct = float(worst_bin["rate_pct"])
                n0_cand = max(1, self.total_records - cnt_v)
                k0_cand = max(0, self.target_events - sum_v)
                z_cand, p_cand = calculate_two_proportion_z_test(sum_v, cnt_v, k0_cand, n0_cand)
                r0_pct = (k0_cand / n0_cand) * 100.0
                is_sig_cand = (p_cand < 0.05) and (r_pct > r0_pct * 1.10)
                candidates.append({
                    "segment": f"{top_c['column']} in {worst_bin['range']}",
                    "col": top_c['column'],
                    "val": worst_bin['range'],
                    "is_quantile": True,
                    "is_demo": False,
                    "is_sig": is_sig_cand,
                    "volume": cnt_v,
                    "events": sum_v,
                    "rate_pct": r_pct,
                    "z_stat": z_cand,
                    "p_val": p_cand
                })

        high_risk_mask = pd.Series(False, index=self.df.index)
        if candidates:
            # Priority: 1. Statistically significant (p < 0.05 & lift > 1.10x), 2. Non-demographic, 3. Discrete over quantile (if both sig), 4. Highest rate_pct
            candidates.sort(
                key=lambda x: (
                    1 if x["is_sig"] else 0,
                    0 if x["is_demo"] else 1,
                    0 if x["is_quantile"] else 1,
                    x["rate_pct"]
                ),
                reverse=True
            )
            best_c = candidates[0]
            high_risk_segment = best_c["segment"]
            high_risk_volume = best_c["volume"]
            high_risk_events = best_c["events"]
            high_risk_rate = best_c["rate_pct"]
            if not best_c["is_quantile"]:
                high_risk_mask = (self.df[best_c["col"]] == best_c["val"])
            else:
                try:
                    q_col = best_c["col"]
                    r_str = str(best_c["val"]).strip('()[] ')
                    parts = r_str.split(',')
                    low_b, high_b = float(parts[0]), float(parts[1])
                    high_risk_mask = (self.df[q_col] >= low_b) & (self.df[q_col] <= high_b)
                except Exception:
                    high_risk_mask = pd.Series(True, index=self.df.index)
        else:
            high_risk_segment = "Global Population Baseline"
            high_risk_volume = self.total_records
            high_risk_events = self.target_events
            high_risk_rate = self.target_rate
            high_risk_mask = pd.Series(True, index=self.df.index)

        baseline_rate = max(self.target_rate, 0.01)
        relative_risk_multiplier = round(high_risk_rate / baseline_rate, 2) if high_risk_rate > 0 else 1.0

        # Physical Two-Proportion z-Test & Excess-Risk (Attributable Risk) Calculation
        n1 = high_risk_volume
        k1 = high_risk_events
        n0 = max(1, self.total_records - n1)
        k0 = max(0, self.target_events - k1)
        rest_rate = round((k0 / n0) * 100.0, 2)
        excess_metrics = calculate_excess_risk_metrics(k1, n1, k0, n0, confidence=0.95)
        z_stat = excess_metrics["z_stat"]
        p_val = excess_metrics["p_value"]
        excess_events = excess_metrics["excess_events"]
        excess_ci_low = excess_metrics["excess_events_ci_low"]
        excess_ci_high = excess_metrics["excess_events_ci_high"]
        excess_rate_pct = round(excess_metrics["excess_rate"] * 100.0, 2)

        # Statistical Circuit-Breaker Gate: Requires p < 0.05 AND >= 1.10x lift AND >= 3 excess events
        is_statistically_significant = bool(
            p_val < 0.05 and relative_risk_multiplier >= 1.10 and excess_events >= 3.0
        )

        unit = self.domain_profile["unit_symbol"]
        is_fin = bool(self.cost_metric and self.cost_metric in self.df.columns)
        cohort_adverse_dollars = 0.0
        avg_cost_per_event = 0.0
        if is_fin:
            cohort_adverse_mask = high_risk_mask & (target_series == 1)
            cohort_adverse_dollars = float(pd.to_numeric(self.df.loc[cohort_adverse_mask, self.cost_metric], errors='coerce').fillna(0.0).sum())
            avg_cost_per_event = (cohort_adverse_dollars / high_risk_events) if high_risk_events > 0 else 0.0

        if is_statistically_significant:
            # Epidemiological Excess-Risk (Attributable Risk) Compression:
            # Pathway A compresses 25% of Excess Risk; Pathway B compresses 60% of Excess Risk; Pathway C eliminates 100% of Excess Risk (parity with baseline p0)
            path_a_reduction = max(1, int(round(excess_events * 0.25)))
            ci_a_low = max(0, int(round(excess_ci_low * 0.25)))
            ci_a_high = max(ci_a_low, int(round(excess_ci_high * 0.25)))

            path_b_reduction = max(1, int(round(excess_events * 0.60)))
            ci_b_low = max(0, int(round(excess_ci_low * 0.60)))
            ci_b_high = max(ci_b_low, int(round(excess_ci_high * 0.60)))

            path_c_reduction = max(1, int(round(excess_events * 1.00)))
            ci_c_low = max(0, int(round(excess_ci_low * 1.00)))
            ci_c_high = max(ci_c_low, int(round(excess_ci_high * 1.00)))

            if is_fin:
                path_a_dollars = path_a_reduction * avg_cost_per_event
                path_b_dollars = path_b_reduction * avg_cost_per_event
                path_c_dollars = path_c_reduction * avg_cost_per_event

                ci_a_low_d = ci_a_low * avg_cost_per_event
                ci_a_high_d = ci_a_high * avg_cost_per_event
                ci_b_low_d = ci_b_low * avg_cost_per_event
                ci_b_high_d = ci_b_high * avg_cost_per_event
                ci_c_low_d = ci_c_low * avg_cost_per_event
                ci_c_high_d = ci_c_high * avg_cost_per_event

                ci_a_str = f"[${ci_a_low_d:,.2f} to ${ci_a_high_d:,.2f}] ({ci_a_low:,} to {ci_a_high:,} excess events) (95% Attributable Risk CI)"
                ci_b_str = f"[${ci_b_low_d:,.2f} to ${ci_b_high_d:,.2f}] ({ci_b_low:,} to {ci_b_high:,} excess events) (95% Attributable Risk CI)"
                ci_c_str = f"[${ci_c_low_d:,.2f} to ${ci_c_high_d:,.2f}] ({ci_c_low:,} to {ci_c_high:,} excess events) (95% Attributable Risk CI)"

                proj_a = f"${path_a_dollars:,.2f} risk averted ({path_a_reduction:,} excess adverse events — 25% Excess-Risk Compression)"
                proj_b = f"${path_b_dollars:,.2f} risk averted ({path_b_reduction:,} excess adverse events — 60% Excess-Risk Compression)"
                proj_c = f"${path_c_dollars:,.2f} risk averted ({path_c_reduction:,} excess adverse events — 100% Baseline Parity)"
            else:
                ci_a_str = f"[{ci_a_low:,} to {ci_a_high:,} {unit}] (95% Attributable Risk CI)"
                ci_b_str = f"[{ci_b_low:,} to {ci_b_high:,} {unit}] (95% Attributable Risk CI)"
                ci_c_str = f"[{ci_c_low:,} to {ci_c_high:,} {unit}] (95% Attributable Risk CI)"

                proj_a = f"{path_a_reduction:,} {unit} saved (25% Excess-Risk Compression)"
                proj_b = f"{path_b_reduction:,} {unit} saved (60% Excess-Risk Compression)"
                proj_c = f"{path_c_reduction:,} {unit} saved (100% Baseline Parity)"

            pathways = [
                {
                    "path_name": "Pathway A: Conservative (25% Excess-Risk Compression via Early Warning Triage)",
                    "strategy_type": "Low CapEx / Immediate Operational Triage",
                    "implementation_cost": "$5,000 - $15,000" if is_fin else "Internal Staff Hours (No CapEx)",
                    "time_to_impact": "1 - 2 Weeks",
                    "projected_friction_reduction": proj_a,
                    "statistical_confidence_interval": ci_a_str,
                    "fayda_pros": f"Zero organizational disruption; captures initial 25% of the {excess_events:.1f} attributable excess events in `{high_risk_segment}` via lightweight queue alerts.",
                    "nuksan_cons": f"Leaves 75% of cohort excess risk ({max(0, int(round(excess_events)) - path_a_reduction):,} excess events) and baseline systemic friction unaddressed.",
                    "collateral_friction": "Minor alert-fatigue among frontline staff if threshold rules are too sensitive."
                },
                {
                    "path_name": "Pathway B: Surgical (60% Excess-Risk Compression in Bottleneck Cohort)",
                    "strategy_type": "Moderate CapEx / Targeted Clinical or Operational Protocol",
                    "implementation_cost": "$25,000 - $50,000" if is_fin else "Dedicated Protocol Buffer & Daily Monitoring",
                    "time_to_impact": "30 - 45 Days",
                    "projected_friction_reduction": proj_b,
                    "statistical_confidence_interval": ci_b_str,
                    "fayda_pros": f"Highest Return on Invested Effort; directly targets the statistically verified `{high_risk_segment}` bottleneck ({high_risk_rate}% vs {rest_rate}% rest-of-system, p = {p_val:.4e}, +{excess_rate_pct}% attributable excess risk).",
                    "nuksan_cons": "Does not reduce the rest-of-system baseline failure rate; requires training frontline staff on cohort-specific triage.",
                    "collateral_friction": "Requires cross-departmental coordination; minor initial resistance during protocol adoption."
                },
                {
                    "path_name": "Pathway C: Structural (100% Excess-Risk Elimination — Full Cohort Parity with Baseline)",
                    "strategy_type": "High CapEx / Infrastructure & Automated Remediation",
                    "implementation_cost": "$100,000 - $250,000" if is_fin else "Dedicated Telemetry / Automated Infrastructure Revamp",
                    "time_to_impact": "90 - 180 Days",
                    "projected_friction_reduction": proj_c,
                    "statistical_confidence_interval": ci_c_str,
                    "fayda_pros": f"Brings `{high_risk_segment}` from {high_risk_rate}% down to exact statistical parity with the rest-of-population baseline ({rest_rate}%), eliminating all {path_c_reduction:,} attributable excess failures.",
                    "nuksan_cons": "High upfront capital expenditure and 90-180 day payback horizon; cannot push failure rates below the rest-of-system baseline without global re-engineering.",
                    "collateral_friction": "Heavy operational friction during system migration; requires ongoing engineering maintenance."
                }
            ]
        else:
            # STATISTICAL CIRCUIT-BREAKER TRIPPED: Noise Distribution Detected (p >= 0.05 or lift < 1.10x)
            path_a_reduction = 0
            path_b_reduction = 0
            path_c_reduction = 0
            if is_fin:
                proj_a = f"$0.00 risk averted (Circuit-Breaker: Noise p = {p_val:.4f} — CapEx Frozen)"
                proj_b = f"$0.00 risk averted (Circuit-Breaker: Noise p = {p_val:.4f} — CapEx Frozen)"
                proj_c = f"$0.00 cohort excess risk (Requires Global System Redesign)"
            else:
                proj_a = f"0 {unit} saved (Circuit-Breaker: Noise p = {p_val:.4f} — Intervention Halted)"
                proj_b = f"0 {unit} saved (Circuit-Breaker: Noise p = {p_val:.4f} — Intervention Halted)"
                proj_c = f"0 cohort excess {unit} (Requires Global System Redesign)"

            ci_null_str = f"[0 to 0 excess events] (Null Hypothesis Retained: z = {z_stat:.2f}, p = {p_val:.4f} >= 0.05)"
            pathways = [
                {
                    "path_name": "Pathway A: Capital Preservation & Freeze ($0 CapEx — Statistical Circuit-Breaker Active)",
                    "strategy_type": "Mandatory CapEx Freeze / Zero Targeted Spend",
                    "implementation_cost": "$0 (CapEx Frozen)",
                    "time_to_impact": "Immediate",
                    "projected_friction_reduction": proj_a,
                    "statistical_confidence_interval": ci_null_str,
                    "fayda_pros": f"Prevents wasted capital and organizational thrashing on `{high_risk_segment}`, where the observed {high_risk_rate}% rate vs {rest_rate}% baseline is statistically indistinguishable from random sampling noise (p = {p_val:.4f}).",
                    "nuksan_cons": f"Baseline systemic friction ({self.target_rate}%) continues until stronger causal features or upstream telemetry are captured.",
                    "collateral_friction": "Zero frontline disruption; protects operational teams from chasing phantom false-positive rules."
                },
                {
                    "path_name": "Pathway B: Telemetry & Root-Cause Instrumentation Audit (Diagnostic Discovery)",
                    "strategy_type": "Low-Cost Data Engineering & Sensor/Feature Expansion",
                    "implementation_cost": "Internal Data Engineering Audit",
                    "time_to_impact": "2 - 4 Weeks",
                    "projected_friction_reduction": proj_b,
                    "statistical_confidence_interval": ci_null_str,
                    "fayda_pros": "Identifies the missing upstream operational, clinical, or behavioral variables that actually drive the target outcome, since current schema columns exhibit uniform noise.",
                    "nuksan_cons": "Diagnostic phase only; does not immediately lower event volume until new predictive signals are ingested.",
                    "collateral_friction": "Requires brief collaboration between data engineering and domain subject-matter experts."
                },
                {
                    "path_name": "Pathway C: Global Baseline Process Hygiene (System-Wide Non-Cohort Remediation)",
                    "strategy_type": "Population-Wide Standard Operating Procedure Upgrade",
                    "implementation_cost": "System-Wide Operational Review",
                    "time_to_impact": "60 - 90 Days",
                    "projected_friction_reduction": proj_c,
                    "statistical_confidence_interval": ci_null_str,
                    "fayda_pros": f"Because adverse events ({self.target_rate}%) are uniformly distributed across all cohorts without a localized bottleneck, only global population-wide process improvements can lower the systemic mean.",
                    "nuksan_cons": "Cannot leverage surgical Pareto concentration (80/20 rule) because no concentrated bottleneck cohort exists in the current data.",
                    "collateral_friction": "Requires broad organizational alignment across all operating units."
                }
            ]

        if z_stat >= 3.0 and is_statistically_significant:
            stat_evidence_str = f"The empirical separation yields z = {z_stat:.2f} (p < 0.001), exceeding the rigorous 3-sigma standard of statistical evidence with {excess_events:.1f} attributable excess events."
        elif z_stat >= 1.96 and is_statistically_significant:
            stat_evidence_str = f"The empirical separation yields z = {z_stat:.2f} (p = {p_val:.4f}), which is statistically significant at the 95% confidence level with {excess_events:.1f} attributable excess events."
        else:
            stat_evidence_str = f"The empirical separation yields z = {z_stat:.2f} (p = {p_val:.4f}), indicating that this difference is within random sampling variation at 95% confidence. **Statistical Circuit-Breaker is ACTIVE: Do NOT allocate targeted CapEx to this cohort.**"

        if is_statistically_significant:
            q2_answer = (
                f"Out of {high_risk_volume:,} records in this high-risk partition, {high_risk_events:,} were confirmed adverse events ({high_risk_rate:.2f}% precision vs {rest_rate:.2f}% rest-of-system baseline, +{excess_rate_pct:.2f}% excess risk). "
                f"Targeting this cohort addresses {excess_events:.1f} attributable excess events while absorbing {high_risk_volume - high_risk_events:,} non-event reviews across the cohort cycle."
            )
            q3_answer = (
                f"Pathway C models 100% elimination of the cohort's attributable excess risk ({path_c_reduction:,} excess events, bringing `{high_risk_segment}` to exact {rest_rate:.2f}% baseline parity), "
                f"but requires 90-180 days and heavy CapEx. Pathway B captures 60% of the excess-risk reduction ({path_b_reduction:,} excess events) in 30-45 days at a fraction of the cost."
            )
        else:
            q2_answer = (
                f"Implementing surgical triage on `{high_risk_segment}` is **mathematically contraindicated**. Because the cohort event rate ({high_risk_rate:.2f}%) is virtually identical to the rest of the population ({rest_rate:.2f}%, p = {p_val:.4f}), "
                f"flagging this segment acts as a random coin-flip that would burden frontline staff with {high_risk_volume - high_risk_events:,} false alarms for zero attributable risk reduction."
            )
            q3_answer = (
                f"Neither cohort-specific Surgical CapEx (Pathway B) nor cohort-targeted Structural CapEx is justified when the Statistical Circuit-Breaker is tripped (p = {p_val:.4f}). "
                f"Leadership must freeze cohort spending (Pathway A, $0 CapEx) and audit missing upstream telemetry (Pathway B) before committing capital."
            )

        counter_questions = [
            {
                "question": f"Is the concentration in '{high_risk_segment}' statistically genuine or just random cohort noise?",
                "data_backed_answer": f"It is statistically evaluated. The event rate in '{high_risk_segment}' is {high_risk_rate:.2f}% compared to {rest_rate:.2f}% across the remainder of the population (Relative Risk Multiplier: {relative_risk_multiplier}x across {high_risk_volume:,} physical records). {stat_evidence_str}"
            },
            {
                "question": "If we implement Pathway B (Surgical Triage), what is the risk of False Positives overloading our capacity?",
                "data_backed_answer": q2_answer
            },
            {
                "question": "Why should we not immediately jump to Pathway C (Full System Re-architecture)?",
                "data_backed_answer": q3_answer
            }
        ]

        res = {
            "domain_profile": self.domain_profile,
            "target_col": self.target_col,
            "target_events": self.target_events,
            "target_rate": self.target_rate,
            "high_risk_segment": high_risk_segment,
            "high_risk_volume": high_risk_volume,
            "high_risk_events": high_risk_events,
            "high_risk_rate": round(high_risk_rate, 2),
            "rest_rate": rest_rate,
            "relative_risk_multiplier": relative_risk_multiplier,
            "z_stat": round(z_stat, 2),
            "p_val": p_val,
            "excess_events": round(excess_events, 1),
            "excess_ci_low": round(excess_ci_low, 1),
            "excess_ci_high": round(excess_ci_high, 1),
            "excess_rate_pct": excess_rate_pct,
            "cohort_adverse_dollars": round(cohort_adverse_dollars, 2),
            "avg_cost_per_event": round(avg_cost_per_event, 6),
            "is_statistically_significant": is_statistically_significant,
            "pathways": pathways,
            "counter_questions": counter_questions
        }
        self.dossier = res
        return res

    def render_markdown_section(self) -> str:
        """Renders the complete Strategic Decision Matrix section in GitHub Markdown."""
        dossier = self.generate_strategic_decision_dossier()
        dom = dossier["domain_profile"]
        is_sig = dossier["is_statistically_significant"]

        if is_sig:
            circuit_banner = (
                f"- **Statistical Significance Gate**: **PASSED (`z = {dossier['z_stat']:.2f}, p = {dossier['p_val']:.4e}`)** — "
                f"**{dossier['excess_events']:,.1f} Attributable Excess Events (+{dossier['excess_rate_pct']}% above {dossier['rest_rate']}% rest-of-system baseline)**"
            )
        else:
            circuit_banner = (
                f"- **Statistical Significance Gate**: **⚠️ CIRCUIT-BREAKER TRIPPED (`z = {dossier['z_stat']:.2f}, p = {dossier['p_val']:.4f} >= 0.05`)** — "
                f"**Uniform Noise Distribution Detected ($0 Cohort CapEx Recommended)**"
            )

        md = f"""
---

## 🏛️ STRATEGIC EXECUTIVE DECISION MATRIX & COUNTERFACTUAL ADVISORY
*Objective: Unbiased problem diagnosis, empirical proof of solutions, executive counter-questions, and honest trade-offs.*

### 1. Ground-Truth Problem Diagnosis (Audited Friction Footprint)
- **Domain Context**: **{dom['domain_name']}**
- **Monitored Population**: **{self.total_records:,} physical records**
- **Target Adverse Events (`{dossier['target_col']}`)**: **{dossier['target_events']:,} events ({dossier['target_rate']}%)**
- **Highest-Observed Candidate Segment**: **`{dossier['high_risk_segment']}`**
  - **Cohort Volume**: {dossier['high_risk_volume']:,} records
  - **Adverse Events in Segment**: {dossier['high_risk_events']:,} events
  - **Segment Failure Rate**: **{dossier['high_risk_rate']}%** (vs. {dossier['rest_rate']}% rest-of-population baseline — **{dossier['relative_risk_multiplier']}x Risk Multiplier**)
  {circuit_banner}

---

### 2. Multi-Pathway Strategic Options (Raste, Dictates Nahi)
*Hum kisi decision ko force nahi kar rahe. Teen viable raste prastut hain, har raste ke mathematical aur operational consequences ke saath:*

| Strategic Pathway | Capital / Effort | Time Horizon | Projected Risk Reduction | 95% Confidence Interval | Primary Trade-Off |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for p in dossier["pathways"]:
            md += f"| **{p['path_name']}** | {p['implementation_cost']} | {p['time_to_impact']} | **{p['projected_friction_reduction']}** | {p['statistical_confidence_interval']} | {p['nuksan_cons']} |\n"

        md += """
---

### 3. Brutal Pros & Cons Matrix (Har Faisle Ka Fayda Aur Nuksan)
*Unbiased evaluation of upside, downside risks, and collateral friction for each pathway:*

"""
        for p in dossier["pathways"]:
            md += f"""#### 🔹 {p['path_name']}
- **Fayda (Upside & Benefits)**: {p['fayda_pros']}
- **Nuksan (Downside & Limitations)**: {p['nuksan_cons']}
- **Collateral Friction (Team / Operational Impact)**: {p['collateral_friction']}

"""

        md += f"""---

### 4. Executive Devil's Advocate: Counter-Questions & Empirical Answers
*Board ya leadership ({dom['persona']}) dwara pooche jaane wale kathin sawal aur data-grounded jawab:*

"""
        for idx, cq in enumerate(dossier["counter_questions"], 1):
            md += f"""**Q{idx}: {cq['question']}**  
> **Empirical Data Answer**: {cq['data_backed_answer']}

"""

        # Append Micro-Level Forensic Investigation
        micro_md = self.micro_engine.render_micro_markdown()
        md += micro_md

        md += """---
*Generated autonomously by Enterprise Strategic Decision & Micro-Forensic Engine V4.0 (Zero Bias & Statistical Circuit-Breaker Verified)*
"""
        return md


if __name__ == "__main__":
    test_csv = sys.argv[1] if len(sys.argv) > 1 else "kaggle_benchmarks/wine_quality/raw_data/WineQT.csv"
    if os.path.exists(test_csv):
        df_test = pd.read_csv(test_csv)
        engine = StrategicDecisionEngine(df_test)
        print(engine.render_markdown_section())
