"""
=============================================================================
STAGE 7: AUTONOMOUS BESPOKE EXECUTIVE DASHBOARD ARCHITECT (ENTERPRISE V5.0)
=============================================================================
Grand Finale of the Autonomous Enterprise Pipeline:
1. Domain Intelligence & Persona Judgment:
   Matches dataset to 1 of 12 business ontologies (business_ontology.py) and
   selects 1 of 5 high-craft Executive Design Archetypes:
     - swiss_institutional_terminal (FinTech, Banking, Lending, Actuarial)
     - nordic_saas_command (Telecom, Subscription SaaS, B2B Enterprise, B2D APIs)
     - editorial_commerce_studio (E-Commerce, D2C, Marketplaces, Retail, F&B)
     - industrial_scada_telemetry (Manufacturing, Supply Chain, Logistics, Quality)
     - clinical_diagnostic_clarity (Healthcare, Hospitals, Clinical, HR Analytics)
2. Data-Shape Adaptive Panel Selection (10-Widget Component Catalog):
   Dynamically selects 6-8 optimal panels based on dataset properties (temporal,
   monetary ledger, continuous cliffs, 2x2 interactions, triage yield curve).
3. Zero-CDN Standalone Interactive HTML Application (bespoke_executive_dashboard.html):
   Zero external dependencies (pure inline CSS3 + native interactive SVG charts).
   Features client-side DuckDB cross-filter micro-cube, live English/Hinglish toggle,
   light/dark theme switcher, What-If ROI simulator, and searchable worklist explorer.
4. Mathematical Invariants:
   Zero multiplicity drift in client-side micro-cube (sum(volume) == total_records).
   No fake '$' on non-monetary datasets (* 1000 ban).
   Statistical circuit-breaker honesty (Amber $0 CapEx Freeze in noise mode).
=============================================================================
"""

import os
import re
import sys
import copy
import json
import html
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# Support both package and direct script execution
try:
    from .common_utils import quote_sql_ident, sanitize_untrusted_metadata_token
    from .target_resolver import (
        resolve_canonical_target_and_cost,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        is_demographic_attribute
    )
    from .pii_scrubber import is_sensitive_column_name, scrub_text
    from .strategic_decision_matrix import StrategicDecisionEngine, calculate_wilson_ci
    from .stage5_bi_synthesizer import detect_key_columns
    from .rate_limiter import PacedGeminiClient
except ImportError:
    from common_utils import quote_sql_ident, sanitize_untrusted_metadata_token
    from target_resolver import (
        resolve_canonical_target_and_cost,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        is_demographic_attribute
    )
    from pii_scrubber import is_sensitive_column_name, scrub_text
    from strategic_decision_matrix import StrategicDecisionEngine, calculate_wilson_ci
    from stage5_bi_synthesizer import detect_key_columns
    try:
        from rate_limiter import PacedGeminiClient
    except ImportError:
        PacedGeminiClient = None


# -----------------------------------------------------------------------------
# 1. LOAD MASTER BUSINESS ONTOLOGY
# -----------------------------------------------------------------------------
def load_master_ontology() -> Dict[str, Any]:
    """Loads master business ontology safely from 02_domain_intelligence/business_ontology.py."""
    candidates = [
        Path(__file__).resolve().parent.parent / "02_domain_intelligence" / "business_ontology.py",
        Path.cwd() / "02_domain_intelligence" / "business_ontology.py",
        Path.cwd().parent / "02_domain_intelligence" / "business_ontology.py"
    ]
    for c in candidates:
        if c.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("business_ontology_mod", str(c))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    return getattr(mod, "MASTER_BUSINESS_ONTOLOGY", {})
            except Exception:
                pass
    return {}


# -----------------------------------------------------------------------------
# 2. DESIGN ARCHETYPES SPECIFICATION
# -----------------------------------------------------------------------------
ARCHETYPE_SPECS = {
    "swiss_institutional_terminal": {
        "id": "swiss_institutional_terminal",
        "name": "Swiss Institutional Risk Terminal",
        "default_persona": "Chief Risk Officer (CRO) & Credit Committee",
        "layout_concept": "3-column asymmetric risk cockpit with compact tabular command bar",
        "default_theme": "dark",
        "font_display": "'Cascadia Mono', 'JetBrains Mono', 'Consolas', monospace",
        "font_body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "dark": {
            "canvas": "#090D16",
            "card": "#111827",
            "border": "#1F2937",
            "accent": "#D4AF37",
            "accent_alt": "#F43F5E",
            "text": "#F9FAFB",
            "muted": "#9CA3AF",
            "badge_border": "#D4AF37",
            "badge_text": "#D4AF37"
        },
        "light": {
            "canvas": "#F3F4F6",
            "card": "#FFFFFF",
            "border": "#E5E7EB",
            "accent": "#B45309",
            "accent_alt": "#E11D48",
            "text": "#111827",
            "muted": "#6B7280",
            "badge_border": "#B45309",
            "badge_text": "#B45309"
        }
    },
    "nordic_saas_command": {
        "id": "nordic_saas_command",
        "name": "Nordic SaaS Command Center",
        "default_persona": "Chief Revenue Officer (CRO) & VP Customer Success",
        "layout_concept": "8-col / 4-col executive bento layout with prominent MRR leakage focus",
        "default_theme": "dark",
        "font_display": "'Trebuchet MS', 'Segoe UI Variable Display', system-ui, sans-serif",
        "font_body": "'Trebuchet MS', 'Segoe UI', -apple-system, sans-serif",
        "dark": {
            "canvas": "#0B1120",
            "card": "#151F32",
            "border": "#1E293B",
            "accent": "#06B6D4",
            "accent_alt": "#6366F1",
            "text": "#F8FAFC",
            "muted": "#94A3B8",
            "badge_border": "#06B6D4",
            "badge_text": "#06B6D4"
        },
        "light": {
            "canvas": "#F8FAFC",
            "card": "#FFFFFF",
            "border": "#E2E8F0",
            "accent": "#0891B2",
            "accent_alt": "#4F46E5",
            "text": "#0F172A",
            "muted": "#64748B",
            "badge_border": "#0891B2",
            "badge_text": "#0891B2"
        }
    },
    "editorial_commerce_studio": {
        "id": "editorial_commerce_studio",
        "name": "Editorial Commerce & CX Studio",
        "default_persona": "Chief Operating Officer (COO) & VP Growth / CX",
        "layout_concept": "Magazine-style asymmetric story header with CX and margin friction layout",
        "default_theme": "light",
        "font_display": "'Georgia', 'Cambria', 'Palatino Linotype', serif",
        "font_body": "-apple-system, 'Segoe UI', Roboto, sans-serif",
        "dark": {
            "canvas": "#141413",
            "card": "#1C1917",
            "border": "#292524",
            "accent": "#F59E0B",
            "accent_alt": "#10B981",
            "text": "#F5F5F4",
            "muted": "#A8A29E",
            "badge_border": "#F59E0B",
            "badge_text": "#F59E0B"
        },
        "light": {
            "canvas": "#FAF7F2",
            "card": "#FFFFFF",
            "border": "#E7E5E4",
            "accent": "#D97706",
            "accent_alt": "#059669",
            "text": "#1C1917",
            "muted": "#78716C",
            "badge_border": "#D97706",
            "badge_text": "#D97706"
        }
    },
    "industrial_scada_telemetry": {
        "id": "industrial_scada_telemetry",
        "name": "Industrial SCADA Process Telemetry",
        "default_persona": "VP Operations, Plant Director & Head of QA",
        "layout_concept": "Process control layout leading with parameter cliffs & tolerance frontier",
        "default_theme": "dark",
        "font_display": "'Consolas', 'Courier New', monospace",
        "font_body": "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif",
        "dark": {
            "canvas": "#101418",
            "card": "#182026",
            "border": "#253038",
            "accent": "#F59E0B",
            "accent_alt": "#14B8A6",
            "text": "#E6EDF2",
            "muted": "#8A9BA8",
            "badge_border": "#F59E0B",
            "badge_text": "#F59E0B"
        },
        "light": {
            "canvas": "#EBF1F5",
            "card": "#FFFFFF",
            "border": "#CED9E0",
            "accent": "#D97706",
            "accent_alt": "#0D9488",
            "text": "#182026",
            "muted": "#5C7080",
            "badge_border": "#D97706",
            "badge_text": "#D97706"
        }
    },
    "clinical_diagnostic_clarity": {
        "id": "clinical_diagnostic_clarity",
        "name": "Clinical Diagnostic & Operations Clarity",
        "default_persona": "Chief Medical Officer / Clinical Ops Director / CHRO",
        "layout_concept": "Clinical cohort stratification & early-intervention layout",
        "default_theme": "light",
        "font_display": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font_body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "dark": {
            "canvas": "#0B1324",
            "card": "#111E38",
            "border": "#1E2F54",
            "accent": "#3B82F6",
            "accent_alt": "#10B981",
            "text": "#F8FAFC",
            "muted": "#94A3B8",
            "badge_border": "#3B82F6",
            "badge_text": "#3B82F6"
        },
        "light": {
            "canvas": "#F4F7FB",
            "card": "#FFFFFF",
            "border": "#E2E8F0",
            "accent": "#2563EB",
            "accent_alt": "#059669",
            "text": "#0F172A",
            "muted": "#64748B",
            "badge_border": "#2563EB",
            "badge_text": "#2563EB"
        }
    }
}


# -----------------------------------------------------------------------------
# 2.1 COMPONENT WIDGET CATALOG (10-PANEL ADAPTIVE SPEC)
# -----------------------------------------------------------------------------
COMPONENT_CATALOG = [
    {
        "id": "temporal_momentum_ribbon",
        "name": "Temporal Failure Rate & Volume Momentum",
        "description": "Period-over-Period adverse momentum ribbon with dual-axis volume bars.",
        "applicability": "Requires verified calendar timestamp column and >= 2 time periods."
    },
    {
        "id": "pareto_loss_waterfall",
        "name": "Pareto Cumulative Financial Loss Waterfall",
        "description": "80/20 cumulative loss concentration waterfall.",
        "applicability": "Requires authentic physical financial cost/loss column."
    },
    {
        "id": "segment_vulnerability_lollipop",
        "name": "Primary Segment Vulnerability & Wilson 95% CIs",
        "description": "Ranked primary operational dimension with binomial confidence intervals.",
        "applicability": "Requires valid non-synthetic primary categorical dimension."
    },
    {
        "id": "secondary_cross_tab_heatmap",
        "name": "2D Cross-Tabulation Risk Concentration Heatmap",
        "description": "Bivariate categorical cross-tab exposing intersectional risk hubs.",
        "applicability": "Requires secondary operational dimension with cardinality 2-15."
    },
    {
        "id": "exposure_vs_risk_bubble",
        "name": "Exposure Volume vs Adverse Risk Bubble Dispersion",
        "description": "2D bubble scatter separating high-volume systemic risk from niche risk.",
        "applicability": "Requires primary dimension with >= 3 distinct cohorts."
    },
    {
        "id": "nonlinear_cliff_step_area",
        "name": "Non-Linear Parameter Threshold Cliff & Danger Zone",
        "description": "Discrete empirical threshold cliffs identifying acute failure tipping points.",
        "applicability": "Requires continuous numerical driver with non-linear quantile cliff."
    },
    {
        "id": "orthogonal_2x2_quadrant",
        "name": "2x2 Orthogonal Risk vs Protective Buffer Matrix",
        "description": "Four-quadrant interaction matrix testing protective buffer vs risk driver.",
        "applicability": "Requires orthogonal risk and protective drivers with 4 distinct quadrants."
    },
    {
        "id": "triage_efficiency_frontier",
        "name": "Operational Intake Screening Yield Frontier",
        "description": "Trade-off curve between intake discard/scrap rate and defect containment.",
        "applicability": "Requires simulated intake triage policies."
    },
    {
        "id": "what_if_counterfactual_simulator",
        "name": "What-If Counterfactual ROI & Excess-Risk Simulator",
        "description": "Interactive counterfactual slider modeling 0-100% intervention compression.",
        "applicability": "Always applicable across all datasets."
    },
    {
        "id": "actionable_worklist_explorer",
        "name": "Actionable Priority Worklist & Incident Triage Table",
        "description": "Searchable row-level priority worklist with one-click CSV export.",
        "applicability": "Requires generated actionable priority worklist artifact."
    }
]


# -----------------------------------------------------------------------------
# 2.5 OPERATIONAL DIMENSION SANITIZER (ZERO DEMOGRAPHIC / SYNTHETIC / PII LEAK)
# -----------------------------------------------------------------------------
def _sanitize_operational_dimensions(
    df_fact: pd.DataFrame,
    target_col: str,
    cost_col: Optional[str],
    prim_dim: Optional[str],
    sec_dim: Optional[str],
    canonical: Dict[str, Any],
    blueprint: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Guarantees both prim_dim and sec_dim exclude index artifacts, pseudo-IDs,
    Stage 3 synthetic columns, PII columns, and demographic attributes.
    """
    s_bin = canonical["binary_target"]
    excluded = {target_col, cost_col, "_is_target_event", "Id", "id", "fact_surrogate_id"}

    def is_clean_dim(col: Optional[str], max_card: int = 30, allow_demo_fallback: bool = False) -> bool:
        if not col or col not in df_fact.columns or col in excluded:
            return False
        s = df_fact[col]
        if is_index_artifact(col, s) or is_pseudo_numeric_identifier(col, s):
            return False
        if is_synthetic_column(col, blueprint) or is_sensitive_column_name(col):
            return False
        if not allow_demo_fallback and is_demographic_attribute(col):
            return False
        nunq = s.nunique(dropna=True)
        return 2 <= nunq <= max_card

    def score_dim(col: str) -> Tuple[float, float]:
        try:
            cont = pd.crosstab(df_fact[col].fillna("Missing"), s_bin)
            chi2 = 0.0
            if cont.shape[0] >= 2 and cont.shape[1] == 2:
                chi2, _, _, _ = scipy_stats.chi2_contingency(cont)
            rates = df_fact.groupby(col, dropna=False).apply(
                lambda g: float(s_bin.loc[g.index].mean()), include_groups=False
            ) if hasattr(df_fact.groupby(col, dropna=False), "apply") else pd.Series([0.0])
            spread = float(rates.max() - rates.min()) if len(rates) >= 2 else 0.0
            return (spread, float(chi2))
        except Exception:
            return (0.0, 0.0)

    op_candidates = [
        c for c in df_fact.columns
        if is_clean_dim(c, max_card=30, allow_demo_fallback=False)
        and (not pd.api.types.is_float_dtype(df_fact[c]))
    ]
    op_candidates.sort(key=score_dim, reverse=True)

    clean_prim = prim_dim if is_clean_dim(prim_dim, max_card=30, allow_demo_fallback=False) else None
    if not clean_prim and op_candidates:
        clean_prim = op_candidates[0]
    elif not clean_prim and is_clean_dim(prim_dim, max_card=30, allow_demo_fallback=True):
        clean_prim = prim_dim

    clean_sec = None
    if sec_dim and sec_dim != clean_prim and is_clean_dim(sec_dim, max_card=15, allow_demo_fallback=False):
        clean_sec = sec_dim
    else:
        sec_pool = [
            c for c in op_candidates
            if c != clean_prim and 2 <= df_fact[c].nunique(dropna=True) <= 15
        ]
        if sec_pool:
            clean_sec = sec_pool[0]

    return clean_prim, clean_sec


# -----------------------------------------------------------------------------
# 3. DOMAIN INTELLIGENCE & SHAPE JUDGMENT
# -----------------------------------------------------------------------------
ONTOLOGY_MULTILINGUAL_SIGNALS: Dict[str, List[str]] = {
    "b2d_developer_tools": ["api_key", "endpoint", "latency_ms", "tokens_prompt", "compute_units", "rate_limit", "sdk", "webhook"],
    "b2b_enterprise": [
        "telecom", "telco", "churn", "mrr", "arr", "subscription", "contract", "tipocontrato",
        "valormensal", "totalgasto", "servicodeinternet", "monthlycharges", "totalcharges",
        "acv", "tcv", "invoice_status", "renewal", "saas", "plan_type", "account_manager"
    ],
    "d2c_brands": ["roas", "ad_channel", "is_cod", "rto_flag", "unboxing", "influencer", "d2c"],
    "two_sided_marketplace": ["seller_id", "buyer_id", "listing_id", "take_rate", "surge_multiplier", "gbv", "host_id", "rider"],
    "manufacturing_industrial": [
        "manufacturing", "wine", "acidity", "sulphates", "chlorides", "sulfur", "alcohol", "ph",
        "density", "quality", "scada", "machine", "sensor", "downtime", "scrap", "oee", "defect",
        "batch", "turbine", "torque", "rpm", "tool_wear"
    ],
    "healthcare_operations": [
        "patient", "hospital", "clinical", "medical", "doctor", "diagnosis", "readmission",
        "stroke", "glucose", "bmi", "hypertension", "heart_disease", "icd", "encounter_id", "alos"
    ],
    "fintech_lending": [
        "loan", "borrower", "credit", "default", "interest_rate", "interestrate", "loanamount",
        "cibil", "fico", "dpd", "npa", "emi", "collateral", "dti", "mortgage", "actuarial",
        "policy_id", "claim", "premium", "fraud"
    ],
    "food_beverage_qsr": ["restaurant", "kitchen", "cuisine", "menu_price", "food_waste", "kot", "prep_time"],
    "real_estate_proptech": ["property", "sqft", "square_feet", "lease", "tenant", "occupancy", "rent_per_sqft"],
    "edtech_upskilling": ["student", "course", "enrollment", "learning_progress", "placement", "bootcamp", "dropout"],
    "logistics_freight": ["consignment", "freight", "origin_hub", "destination_hub", "carrier", "demurrage", "transit_delay", "shipment"],
    "ecommerce_retail": [
        "ecommerce", "customer_service", "csat", "order_id", "product_category", "cart",
        "item_price", "ticket", "issue_reported", "survey_response", "retail", "store", "return"
    ],
}

ARCHETYPE_PANEL_PRIORITY: Dict[str, Dict[str, int]] = {
    "swiss_institutional_terminal": {
        "pareto_loss_waterfall": 1,
        "segment_vulnerability_lollipop": 2,
        "nonlinear_cliff_step_area": 3,
        "temporal_momentum_ribbon": 4,
        "exposure_vs_risk_bubble": 5,
        "orthogonal_2x2_quadrant": 6,
        "secondary_cross_tab_heatmap": 7,
        "triage_efficiency_frontier": 8,
        "what_if_counterfactual_simulator": 9,
        "actionable_worklist_explorer": 10,
    },
    "nordic_saas_command": {
        "temporal_momentum_ribbon": 1,
        "segment_vulnerability_lollipop": 2,
        "pareto_loss_waterfall": 3,
        "secondary_cross_tab_heatmap": 4,
        "nonlinear_cliff_step_area": 5,
        "exposure_vs_risk_bubble": 6,
        "orthogonal_2x2_quadrant": 7,
        "triage_efficiency_frontier": 8,
        "what_if_counterfactual_simulator": 9,
        "actionable_worklist_explorer": 10,
    },
    "editorial_commerce_studio": {
        "temporal_momentum_ribbon": 1,
        "pareto_loss_waterfall": 2,
        "exposure_vs_risk_bubble": 3,
        "segment_vulnerability_lollipop": 4,
        "secondary_cross_tab_heatmap": 5,
        "nonlinear_cliff_step_area": 6,
        "orthogonal_2x2_quadrant": 7,
        "triage_efficiency_frontier": 8,
        "what_if_counterfactual_simulator": 9,
        "actionable_worklist_explorer": 10,
    },
    "industrial_scada_telemetry": {
        "nonlinear_cliff_step_area": 1,
        "orthogonal_2x2_quadrant": 2,
        "triage_efficiency_frontier": 3,
        "segment_vulnerability_lollipop": 4,
        "temporal_momentum_ribbon": 5,
        "secondary_cross_tab_heatmap": 6,
        "exposure_vs_risk_bubble": 7,
        "pareto_loss_waterfall": 8,
        "what_if_counterfactual_simulator": 9,
        "actionable_worklist_explorer": 10,
    },
    "clinical_diagnostic_clarity": {
        "segment_vulnerability_lollipop": 1,
        "nonlinear_cliff_step_area": 2,
        "orthogonal_2x2_quadrant": 3,
        "triage_efficiency_frontier": 4,
        "secondary_cross_tab_heatmap": 5,
        "temporal_momentum_ribbon": 6,
        "exposure_vs_risk_bubble": 7,
        "pareto_loss_waterfall": 8,
        "what_if_counterfactual_simulator": 9,
        "actionable_worklist_explorer": 10,
    },
}


def judge_dashboard_architecture(
    df_fact: pd.DataFrame,
    target_col: str,
    cost_col: Optional[str],
    prim_dim: Optional[str],
    sec_dim: Optional[str],
    blueprint: Optional[Dict[str, Any]],
    strat_engine: StrategicDecisionEngine,
    temporal_summary: Optional[Dict[str, Any]] = None,
    worklist_path: Optional[Path] = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Evaluates dataset schema, ontology matches, statistical distributions,
    and returns a comprehensive Dashboard Design Blueprint (dict).
    """
    total_records = len(df_fact)
    total_cols = len(df_fact.columns)
    cols_lower = [c.lower() for c in df_fact.columns]
    cols_text = " ".join(cols_lower)
    ds_name = str(df_fact.attrs.get("dataset_name", "")).lower()
    bp_title = (blueprint.get("project_title", "") if blueprint else "").lower()
    bp_domain = (blueprint.get("domain_type", "") if blueprint else "").lower()
    combined_signals = f"{ds_name} {cols_text} {bp_title} {bp_domain}"

    ontology_db = load_master_ontology()

    # 1. Match Domain Ontology (Multilingual + Schema Token Scoring)
    best_ont_key = None
    best_score = -1
    for ont_key, ont_val in ontology_db.items():
        score = 0
        typ_cols = ont_val.get("typical_columns", [])
        for tc in typ_cols:
            tc_l = tc.lower()
            if tc_l in cols_lower:
                score += 4
            elif len(tc_l) >= 4 and any(tc_l in c for c in cols_lower):
                score += 1
        for kw in ONTOLOGY_MULTILINGUAL_SIGNALS.get(ont_key, []):
            if kw in combined_signals:
                score += 3
        d_code = ont_val.get("domain_code", "").lower()
        if d_code and d_code in combined_signals:
            score += 4
        if score > best_score:
            best_score = score
            best_ont_key = ont_key

    matched_ont = ontology_db.get(best_ont_key, {})

    # 2. Select Archetype based on ontology and keyword signals
    archetype_key = "swiss_institutional_terminal"
    
    # Priority keyword heuristics
    if any(k in combined_signals for k in [
        'telecom', 'telco', 'churn', 'mrr', 'arr', 'contract', 'subscription', 'monthlycharges', 'valormensal', 'b2d', 'api_key'
    ]):
        archetype_key = "nordic_saas_command"
    elif any(k in combined_signals for k in [
        'ecommerce', 'customer_service', 'csat', 'order', 'retail', 'marketplace', 'buyer', 'seller', 'sku', 'cart', 'ticket', 'booking', 'hotel'
    ]):
        archetype_key = "editorial_commerce_studio"
    elif any(k in combined_signals for k in [
        'manufacturing', 'wine', 'quality', 'scada', 'machine', 'sensor', 'chemical', 'acidity', 'alcohol', 'power', 'turbine', 'maintenance', 'scrap', 'logistics', 'freight'
    ]):
        archetype_key = "industrial_scada_telemetry"
    elif any(k in combined_signals for k in [
        'health', 'hospital', 'patient', 'clinical', 'medical', 'stroke', 'doctor', 'readmission', 'disease', 'hr', 'attrition', 'employee'
    ]):
        archetype_key = "clinical_diagnostic_clarity"
    elif any(k in combined_signals for k in [
        'loan', 'credit', 'bank', 'default', 'interest', 'cibil', 'finance', 'financial', 'insurance', 'claim', 'fraud', 'actuarial', 'collateral'
    ]):
        archetype_key = "swiss_institutional_terminal"
    elif best_ont_key:
        # Fallback to ontology code mapping
        ont_map = {
            "b2d_developer_tools": "nordic_saas_command",
            "b2b_enterprise": "nordic_saas_command",
            "d2c_brands": "editorial_commerce_studio",
            "two_sided_marketplace": "editorial_commerce_studio",
            "ecommerce_retail": "editorial_commerce_studio",
            "food_beverage_qsr": "editorial_commerce_studio",
            "manufacturing_industrial": "industrial_scada_telemetry",
            "logistics_freight": "industrial_scada_telemetry",
            "healthcare_operations": "clinical_diagnostic_clarity",
            "fintech_lending": "swiss_institutional_terminal"
        }
        archetype_key = ont_map.get(best_ont_key, "swiss_institutional_terminal")

    # 3. Data-Shape Diagnostics
    is_temporal = bool(
        temporal_summary and
        temporal_summary.get("is_temporal_dataset") and
        len(temporal_summary.get("periods", [])) >= 2
    )
    has_monetary = bool(cost_col and cost_col in df_fact.columns)
    has_sec = bool(sec_dim and sec_dim in df_fact.columns and 2 <= df_fact[sec_dim].nunique() <= 15)
    
    cliffs_data = strat_engine.micro_engine.analyze_quantile_cliffs()
    interaction_data = strat_engine.micro_engine.analyze_bivariate_interactions()
    triage_data = strat_engine.micro_engine.simulate_operational_triage()
    strat_dossier = strat_engine.generate_strategic_decision_dossier()
    is_cb_active = bool(not strat_dossier.get("is_statistically_significant", True))
    has_worklist = bool(worklist_path and worklist_path.exists())

    # 4. Adaptive Panel Selection & Rejection
    selected_panels = []
    rejected_panels = []

    # Widget 1: temporal_momentum_ribbon
    if is_temporal:
        selected_panels.append({
            "id": "temporal_momentum_ribbon",
            "name": "Temporal Failure Rate & Volume Momentum",
            "justification": "Verified calendar timestamps detected; tracks Period-over-Period adverse momentum.",
            "priority": 1
        })
    else:
        rejected_panels.append({
            "id": "temporal_momentum_ribbon",
            "name": "Temporal Failure Rate & Volume Momentum",
            "reason": "Dataset is cross-sectional; lacks verified calendar timestamp column."
        })

    # Widget 2: pareto_loss_waterfall
    if has_monetary and prim_dim and df_fact[prim_dim].nunique() >= 2:
        selected_panels.append({
            "id": "pareto_loss_waterfall",
            "name": "Pareto Cumulative Financial Loss Waterfall",
            "justification": "Physical currency ledger verified; isolates 80/20 adverse capital concentration.",
            "priority": 2
        })
    else:
        rejected_panels.append({
            "id": "pareto_loss_waterfall",
            "name": "Pareto Cumulative Financial Loss Waterfall",
            "reason": "Dataset contains no verified monetary exposure ledger; Pareto financial loss waterfall rejected to prevent fabricated currency."
        })

    # Widget 3: segment_vulnerability_lollipop
    if prim_dim and prim_dim in df_fact.columns:
        selected_panels.append({
            "id": "segment_vulnerability_lollipop",
            "name": "Primary Segment Vulnerability & Wilson 95% CIs",
            "justification": "Primary operational dimension ranked by adverse rate with exact binomial confidence intervals.",
            "priority": 1
        })
    else:
        rejected_panels.append({
            "id": "segment_vulnerability_lollipop",
            "name": "Primary Segment Vulnerability & Wilson 95% CIs",
            "reason": "No valid non-synthetic primary dimension detected."
        })

    # Widget 4: secondary_cross_tab_heatmap
    if has_sec:
        selected_panels.append({
            "id": "secondary_cross_tab_heatmap",
            "name": "2D Cross-Tabulation Risk Concentration Heatmap",
            "justification": f"Bivariate categorical cross-tab ({prim_dim} x {sec_dim}) exposes sub-node vulnerability hubs.",
            "priority": 3
        })
    else:
        rejected_panels.append({
            "id": "secondary_cross_tab_heatmap",
            "name": "2D Cross-Tabulation Risk Concentration Heatmap",
            "reason": "Secondary dimension either not detected or cardinality outside 2-15 range."
        })

    # Widget 5: exposure_vs_risk_bubble
    if prim_dim and df_fact[prim_dim].nunique() >= 3:
        selected_panels.append({
            "id": "exposure_vs_risk_bubble",
            "name": "Exposure Volume vs Adverse Risk Bubble Dispersion",
            "justification": "Separates high-volume systemic friction from low-volume niche outliers.",
            "priority": 3
        })
    else:
        rejected_panels.append({
            "id": "exposure_vs_risk_bubble",
            "name": "Exposure Volume vs Adverse Risk Bubble Dispersion",
            "reason": "Insufficient categorical depth (< 3 cohorts) for multi-dimensional bubble dispersion."
        })

    # Widget 6: nonlinear_cliff_step_area
    if cliffs_data and len(cliffs_data) > 0:
        selected_panels.append({
            "id": "nonlinear_cliff_step_area",
            "name": "Non-Linear Parameter Threshold Cliff & Danger Zone",
            "justification": f"Isolates discrete physical inflection points across {len(cliffs_data)} continuous driver(s).",
            "priority": 2
        })
    else:
        rejected_panels.append({
            "id": "nonlinear_cliff_step_area",
            "name": "Non-Linear Parameter Threshold Cliff & Danger Zone",
            "reason": "No continuous numerical threshold cliffs detected with statistical significance."
        })

    # Widget 7: orthogonal_2x2_quadrant
    if interaction_data and "quadrants" in interaction_data and len(interaction_data["quadrants"]) == 4:
        selected_panels.append({
            "id": "orthogonal_2x2_quadrant",
            "name": "2x2 Orthogonal Risk vs Protective Buffer Matrix",
            "justification": "Tests whether protective factors successfully buffer or succumb to primary risk driver.",
            "priority": 2
        })
    else:
        rejected_panels.append({
            "id": "orthogonal_2x2_quadrant",
            "name": "2x2 Orthogonal Risk vs Protective Buffer Matrix",
            "reason": "Bivariate interaction models did not isolate distinct orthogonal risk and protective drivers."
        })

    # Widget 8: triage_efficiency_frontier
    if triage_data and len(triage_data) >= 2:
        selected_panels.append({
            "id": "triage_efficiency_frontier",
            "name": "Operational Intake Screening Yield Frontier",
            "justification": "Quantifies trade-off between intake discard/scrap % and adverse defect containment.",
            "priority": 4
        })
    else:
        rejected_panels.append({
            "id": "triage_efficiency_frontier",
            "name": "Operational Intake Screening Yield Frontier",
            "reason": "Operational intake screening simulation not applicable."
        })

    # Widget 9: what_if_counterfactual_simulator (Always Selected)
    selected_panels.append({
        "id": "what_if_counterfactual_simulator",
        "name": "What-If Counterfactual ROI & Excess-Risk Simulator",
        "justification": "Allows executive leadership to interactively model 0-100% excess-risk compression scenarios.",
        "priority": 5
    })

    # Widget 10: actionable_worklist_explorer
    if has_worklist:
        selected_panels.append({
            "id": "actionable_worklist_explorer",
            "name": "Actionable Priority Worklist & Incident Triage Table",
            "justification": "Equips frontline operations with prioritized record-level retention and recovery queues.",
            "priority": 5
        })
    else:
        rejected_panels.append({
            "id": "actionable_worklist_explorer",
            "name": "Actionable Priority Worklist & Incident Triage Table",
            "reason": "No actionable worklist generated."
        })

    # Apply archetype-specific executive panel priority ordering
    arch_prio_map = ARCHETYPE_PANEL_PRIORITY.get(archetype_key, {})
    for p in selected_panels:
        p["priority"] = arch_prio_map.get(p["id"], p["priority"])
    selected_panels.sort(key=lambda p: p["priority"])

    # Never mutate global ARCHETYPE_SPECS in place
    archetype_def = copy.deepcopy(ARCHETYPE_SPECS[archetype_key])

    # Dynamic DFII Scoring: (Aesthetic Impact + Context Fit + Feasibility + Performance) - Consistency Risk
    aesthetic_impact = 5 if len(selected_panels) >= 6 else 4
    context_fit = 5 if best_score >= 3 else 4
    impl_feasibility = 5  # 100% Zero-CDN inline CSS3 + native SVG
    perf_safety = 5 if total_records <= 100_000 else 4  # Pre-aggregated micro-cube
    consistency_risk = 1 if (not is_cb_active and len(selected_panels) >= 5) else 2
    dfii_total = (aesthetic_impact + context_fit + impl_feasibility + perf_safety) - consistency_risk

    dfii_breakdown = {
        "aesthetic_impact": aesthetic_impact,
        "context_fit": context_fit,
        "implementation_feasibility": impl_feasibility,
        "performance_safety": perf_safety,
        "consistency_risk": consistency_risk,
        "dfii": dfii_total
    }

    # Titles and Narrative
    proj_title = blueprint.get("project_title", "Enterprise Operations") if blueprint else "Enterprise Operations"
    title_en = f"{proj_title} — Executive Forensic Command Cockpit"
    title_hi = f"{proj_title} — Karyakari Business Command Cockpit"

    # Optional AI Director pass to refine persona and title (strictly validated!)
    if use_llm and PacedGeminiClient:
        try:
            client = PacedGeminiClient()
            prompt = f"""<UNTRUSTED_SCHEMA_METADATA>
Columns: {', '.join([sanitize_untrusted_metadata_token(c) for c in df_fact.columns[:30]])}
Matched Ontology: {matched_ont.get('domain_name', 'Enterprise')}
Target: {target_col}
Monetary Column: {cost_col}
Current Archetype: {archetype_key}
</UNTRUSTED_SCHEMA_METADATA>
Respond with JSON only:
{{
  "refined_persona": "Exact Job Title / Committee",
  "dashboard_title_en": "Professional English Title",
  "dashboard_title_hi": "Roman Hinglish Title"
}}"""
            res = client.generate_text(prompt=prompt, system_instruction="Output JSON only.")
            j = json.loads(re.search(r'\{.*\}', res, re.DOTALL).group(0))
            if j.get("refined_persona"):
                archetype_def["default_persona"] = scrub_text(j["refined_persona"])[:80]
            if j.get("dashboard_title_en"):
                title_en = scrub_text(j["dashboard_title_en"])[:120]
            if j.get("dashboard_title_hi"):
                title_hi = scrub_text(j["dashboard_title_hi"])[:120]
        except Exception:
            pass

    blueprint_doc = {
        "dataset_name": df_fact.attrs.get("dataset_name", "dataset"),
        "matched_ontology": {
            "ontology_key": best_ont_key or "general_enterprise",
            "domain_code": matched_ont.get("domain_code", "GEN"),
            "domain_name": matched_ont.get("domain_name", "General Enterprise Operations"),
            "key_metrics_kpis": matched_ont.get("key_metrics_kpis", [])[:4],
            "hidden_leakage_risks": matched_ont.get("loss_and_leakage_risks", [])[:4]
        },
        "archetype": archetype_key,
        "archetype_name": archetype_def["name"],
        "executive_persona": archetype_def["default_persona"],
        "dfii_score": dfii_breakdown["dfii"],
        "dfii_breakdown": dfii_breakdown,
        "design_system": {
            "layout_concept": archetype_def["layout_concept"],
            "default_theme": archetype_def.get("default_theme", "dark"),
            "font_display": archetype_def["font_display"],
            "font_body": archetype_def["font_body"]
        },
        "data_shape_diagnostics": {
            "total_records": total_records,
            "total_columns": total_cols,
            "is_temporal": is_temporal,
            "has_monetary_ledger": has_monetary,
            "has_secondary_dim": has_sec,
            "cliffs_count": len(cliffs_data),
            "has_2x2_interaction": bool(interaction_data and "quadrants" in interaction_data),
            "has_triage_policies": bool(triage_data and len(triage_data) >= 2),
            "is_imbalanced_rare_event": bool(strat_engine.target_rate <= 2.0),
            "circuit_breaker_active": is_cb_active,
            "has_worklist": has_worklist
        },
        "selected_panels": selected_panels,
        "rejected_panels": rejected_panels,
        "executive_narrative": {
            "title_en": title_en,
            "title_hi": title_hi
        }
    }

    return blueprint_doc


# -----------------------------------------------------------------------------
# 4. CLIENT-SIDE MICRO-CUBE PRE-AGGREGATION (ZERO MULTIPLICITY DRIFT)
# -----------------------------------------------------------------------------
def build_client_micro_cube(
    df_fact: pd.DataFrame,
    target_col: str,
    cost_col: Optional[str],
    prim_dim: Optional[str],
    sec_dim: Optional[str],
    canonical: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Constructs a compact, zero-drift aggregation micro-cube grouped by prim_dim and sec_dim.
    Long-tail categories (>14) are grouped into 'Other' without losing a single row.
    Guarantees: sum(volume) == len(df_fact) and sum(adverse_events) == total_target_events.
    """
    total_records = len(df_fact)
    s_bin = canonical["binary_target"]
    total_events = int(s_bin.sum())
    total_adverse_cost = float(df_fact.loc[s_bin == 1, cost_col].sum()) if cost_col else 0.0
    total_volume_cost = float(df_fact[cost_col].sum()) if cost_col else 0.0

    p_col = prim_dim if (prim_dim and prim_dim in df_fact.columns) else None
    s_col = sec_dim if (sec_dim and sec_dim in df_fact.columns and 2 <= df_fact[sec_dim].nunique() <= 15) else None

    # Handle Primary Dimension values
    if p_col:
        p_counts = df_fact[p_col].value_counts(dropna=False)
        top_p = set(p_counts.head(14).index)
        prim_series = df_fact[p_col].apply(lambda v: str(v) if v in top_p else "Other")
    else:
        prim_series = pd.Series(["Global Population"] * total_records, index=df_fact.index)

    # Handle Secondary Dimension values
    if s_col:
        s_counts = df_fact[s_col].value_counts(dropna=False)
        top_s = set(s_counts.head(10).index)
        sec_series = df_fact[s_col].apply(lambda v: str(v) if v in top_s else "Other")
    else:
        sec_series = pd.Series(["All"] * total_records, index=df_fact.index)

    temp_df = pd.DataFrame({
        "p": prim_series,
        "s": sec_series,
        "target": s_bin,
        "cost": df_fact[cost_col] if cost_col else 0.0
    })

    cube_slices: List[Dict[str, Any]] = []
    grouped = temp_df.groupby(["p", "s"], observed=False)

    for (p_val, s_val), grp in grouped:
        vol = len(grp)
        if vol == 0:
            continue
        ev = int(grp["target"].sum())
        adv_cost = float(grp.loc[grp["target"] == 1, "cost"].sum()) if cost_col else 0.0
        tot_cost = float(grp["cost"].sum()) if cost_col else 0.0
        r_pct = round((ev / max(vol, 1)) * 100.0, 2)

        cube_slices.append({
            "prim_val": str(p_val),
            "sec_val": str(s_val),
            "volume": vol,
            "adverse_events": ev,
            "adverse_rate_pct": r_pct,
            "adverse_cost": round(adv_cost, 2),
            "total_cost": round(tot_cost, 2)
        })

    # Invariant Mathematical Assertions
    sum_vol = sum(c["volume"] for c in cube_slices)
    sum_ev = sum(c["adverse_events"] for c in cube_slices)
    assert sum_vol == total_records, f"Micro-cube volume drift: {sum_vol} != {total_records}"
    assert sum_ev == total_events, f"Micro-cube event drift: {sum_ev} != {total_events}"

    if cost_col:
        sum_adv_cost = sum(c["adverse_cost"] for c in cube_slices)
        assert abs(sum_adv_cost - total_adverse_cost) <= 0.10, f"Micro-cube cost drift: {sum_adv_cost} vs {total_adverse_cost}"

    return cube_slices


# -----------------------------------------------------------------------------
# 5. DASHBOARD PAYLOAD GENERATOR
# -----------------------------------------------------------------------------
def build_dashboard_payload(
    df_fact: pd.DataFrame,
    target_col: str,
    cost_col: Optional[str],
    prim_dim: Optional[str],
    sec_dim: Optional[str],
    canonical: Dict[str, Any],
    design_bp: Dict[str, Any],
    strat_engine: StrategicDecisionEngine,
    out_dir: Path
) -> Dict[str, Any]:
    """
    Constructs the 100% physically grounded, zero-hallucination DASHBOARD_PAYLOAD dictionary.
    All chart points, tooltips, what-if parameters, and worklists are generated here.
    """
    total_records = len(df_fact)
    s_bin = canonical["binary_target"]
    target_count = int(s_bin.sum())
    target_rate_pct = round((target_count / max(total_records, 1)) * 100.0, 2)
    total_adverse_cost = float(df_fact.loc[s_bin == 1, cost_col].sum()) if cost_col else 0.0
    total_portfolio_cost = float(df_fact[cost_col].sum()) if cost_col else 0.0

    cube_slices = build_client_micro_cube(df_fact, target_col, cost_col, prim_dim, sec_dim, canonical)

    strat_dossier = strat_engine.generate_strategic_decision_dossier()
    cliffs_data = strat_engine.micro_engine.analyze_quantile_cliffs()
    interaction_data = strat_engine.micro_engine.analyze_bivariate_interactions()
    triage_data = strat_engine.micro_engine.simulate_operational_triage()

    # Discover Primary & Secondary filter chip values
    prim_segments = sorted(list(set(c["prim_val"] for c in cube_slices)))
    if "Other" in prim_segments:
        prim_segments.remove("Other")
        prim_segments.append("Other")

    sec_segments = sorted(list(set(c["sec_val"] for c in cube_slices)))
    if "All" in sec_segments:
        sec_segments.remove("All")
    if "Other" in sec_segments:
        sec_segments.remove("Other")
        sec_segments.append("Other")

    # Primary Dimension Lollipop & Pareto Data
    lollipop_data = []
    pareto_data = []
    if prim_dim and prim_dim in df_fact.columns:
        p_grp = df_fact.groupby(prim_dim, dropna=False)
        for val, grp in p_grp:
            val_str = str(val) if pd.notna(val) else "Missing"
            vol = len(grp)
            ev = int(s_bin.loc[grp.index].sum())
            r_pct = round(ev / max(vol, 1) * 100.0, 2)
            c_low, c_high = calculate_wilson_ci(ev, vol, confidence=0.95)
            drag = float(grp.loc[s_bin.loc[grp.index] == 1, cost_col].sum()) if cost_col else 0.0
            item = {
                "segment": val_str,
                "volume": vol,
                "events": ev,
                "rate_pct": r_pct,
                "ci_low": round(c_low * 100.0, 2),
                "ci_high": round(c_high * 100.0, 2),
                "adverse_cost": round(drag, 2)
            }
            lollipop_data.append(item)

        lollipop_data.sort(key=lambda x: x["rate_pct"], reverse=True)

        if cost_col:
            # Build Pareto Waterfall sorted by financial drag
            pareto_sort = sorted(lollipop_data, key=lambda x: x["adverse_cost"], reverse=True)
            cum_drag = 0.0
            tot_drag = max(total_adverse_cost, 0.01)
            for idx, p_item in enumerate(pareto_sort):
                cum_drag += p_item["adverse_cost"]
                pareto_data.append({
                    "segment": p_item["segment"],
                    "adverse_cost": p_item["adverse_cost"],
                    "cumulative_drag": round(cum_drag, 2),
                    "cumulative_pct": round((cum_drag / tot_drag) * 100.0, 1)
                })

    # Build 2D Cross-Tab Heatmap & Exposure Bubble Dispersion payloads
    heatmap_data = {
        "has_heatmap": bool(sec_dim and len(sec_segments) >= 2 and len(prim_segments) >= 2),
        "prim_dim": prim_dim or "Segment",
        "sec_dim": sec_dim or "Subsegment",
        "rows": prim_segments[:10],
        "cols": sec_segments[:8],
        "cells": [
            {
                "prim_val": c["prim_val"],
                "sec_val": c["sec_val"],
                "volume": c["volume"],
                "events": c["adverse_events"],
                "rate_pct": c["adverse_rate_pct"],
                "adverse_cost": c["adverse_cost"]
            }
            for c in cube_slices
            if c["prim_val"] in set(prim_segments[:10]) and c["sec_val"] in set(sec_segments[:8])
        ]
    }
    bubble_data = lollipop_data[:15]

    # Temporal Trend Data (compatible with both date_column and detected_date_column)
    temporal_file = out_dir / "temporal_trend_summary.json"
    temporal_periods = []
    is_temporal = False
    temp_date_col = ""
    temp_pop_delta = 0.0
    temp_trend_dir = "STABLE"
    if temporal_file.exists():
        try:
            with open(temporal_file, "r", encoding="utf-8") as tf:
                t_json = json.load(tf)
                if t_json.get("is_temporal_dataset") and len(t_json.get("periods", [])) >= 2:
                    is_temporal = True
                    temp_date_col = t_json.get("date_column") or t_json.get("detected_date_column") or "Date"
                    temp_pop_delta = float(t_json.get("period_over_period_rate_delta_pp", 0.0))
                    temp_trend_dir = str(t_json.get("trend_direction", "STABLE"))
                    temporal_periods = t_json.get("periods", [])
        except Exception:
            pass

    # Actionable Worklist Preview (column + cell-level PII scrubbed)
    worklist_file = out_dir / "actionable_priority_worklist.csv"
    worklist_rows = []
    if worklist_file.exists():
        try:
            df_wl = pd.read_csv(worklist_file)
            safe_wl_cols = [
                c for c in df_wl.columns
                if not is_sensitive_column_name(c) and not is_index_artifact(c)
            ]
            df_wl_safe = df_wl[safe_wl_cols].head(160).copy()
            for col_idx, col_n in enumerate(safe_wl_cols):
                if col_idx > 0 and pd.api.types.is_object_dtype(df_wl_safe[col_n]):
                    df_wl_safe[col_n] = df_wl_safe[col_n].apply(
                        lambda x: scrub_text(str(x)) if pd.notna(x) else ""
                    )
            raw_wl = df_wl_safe.replace([np.inf, -np.inf], np.nan).to_dict(orient="records")
            for rec in raw_wl:
                clean_rec = {}
                for k, v in rec.items():
                    clean_rec[k] = None if (isinstance(v, float) and np.isnan(v)) else v
                worklist_rows.append(clean_rec)
        except Exception:
            pass

    # Bottleneck & Statistical Circuit-Breaker Governance
    is_cb_active = not strat_dossier.get("is_statistically_significant", True)
    p_val_num = float(strat_dossier.get("p_val", 1.0))
    z_stat_num = float(strat_dossier.get("z_stat", 0.0))
    rr_mult = float(strat_dossier.get("relative_risk_multiplier", 1.0))
    best_bot_seg = str(strat_dossier.get("high_risk_segment", "Global"))
    bot_rate = float(strat_dossier.get("high_risk_rate", target_rate_pct))
    rest_rate = float(strat_dossier.get("rest_rate", target_rate_pct))
    excess_ev = float(strat_dossier.get("excess_events", 0.0))
    excess_ci_lo = float(strat_dossier.get("excess_ci_low", 0.0))
    excess_ci_hi = float(strat_dossier.get("excess_ci_high", 0.0))
    avg_cost_ev = float(strat_dossier.get("avg_cost_per_event", 0.0))
    cohort_adv_dol = float(strat_dossier.get("cohort_adverse_dollars", 0.0))

    if is_cb_active:
        narrative_en = (
            f"Statistical Circuit-Breaker Active ($0 CapEx Spend Freeze): Observed variation across `{best_bot_seg}` "
            f"({bot_rate:.2f}% vs {rest_rate:.2f}%, p = {p_val_num:.4f}) is within random sampling noise. Do NOT commit targeted CapEx."
        )
        narrative_hi = (
            f"Statistical Circuit-Breaker Chalu Hai ($0 CapEx Spend Freeze): `{best_bot_seg}` ({bot_rate:.2f}% vs {rest_rate:.2f}%, "
            f"p = {p_val_num:.4f}) sirf random noise ke andar hai. Kisi ek segment par naya paisa kharch na karein."
        )
    else:
        narrative_en = (
            f"Group `{best_bot_seg}` exhibits the highest statistically verified adverse concentration at {bot_rate:.2f}% "
            f"(vs {rest_rate:.2f}% rest-of-business baseline, {rr_mult:.2f}x lift, z = {z_stat_num:.2f}, {excess_ev:.1f} excess events)."
        )
        narrative_hi = (
            f"Group `{best_bot_seg}` mein sabse zyada parmanit nuksan dar {bot_rate:.2f}% hai "
            f"(baaki business mein {rest_rate:.2f}%, {rr_mult:.2f}x zyada jokhim, {excess_ev:.1f} roke ja sakne wale excess events)."
        )

    payload = {
        "meta": {
            "dataset_name": out_dir.parent.name,
            "engine": "DataX-Ray Bespoke Architecture V5.5",
            "archetype": design_bp["archetype"],
            "archetype_name": design_bp["archetype_name"],
            "executive_persona": design_bp["executive_persona"],
            "title_en": design_bp["executive_narrative"]["title_en"],
            "title_hi": design_bp["executive_narrative"]["title_hi"],
            "generated_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "ontology": design_bp["matched_ontology"],
        "dfii": design_bp["dfii_breakdown"],
        "design_system": design_bp["design_system"],
        "selected_panels": [p["id"] for p in design_bp["selected_panels"]],
        "selected_panels_detail": design_bp["selected_panels"],
        "rejected_panels_detail": design_bp["rejected_panels"],
        "global_kpis": {
            "total_records": total_records,
            "adverse_events": target_count,
            "adverse_rate_pct": target_rate_pct,
            "system_reliability_pct": round(100.0 - target_rate_pct, 2),
            "has_monetary_ledger": bool(cost_col),
            "currency_unit": "$" if cost_col else "events",
            "cost_column": cost_col or "None (Unit Counts)",
            "adverse_capital_drag": round(total_adverse_cost, 2),
            "total_portfolio_volume": round(total_portfolio_cost, 2)
        },
        "circuit_breaker": {
            "active": is_cb_active,
            "p_value": round(p_val_num, 6),
            "z_stat": round(z_stat_num, 2),
            "relative_risk_multiplier": round(rr_mult, 2),
            "excess_events": round(excess_ev, 1)
        },
        "bottleneck": {
            "segment": best_bot_seg,
            "volume": int(strat_dossier.get("high_risk_volume", 0)),
            "events": int(strat_dossier.get("high_risk_events", 0)),
            "rate_pct": bot_rate,
            "rest_rate_pct": rest_rate,
            "excess_events": round(excess_ev, 1),
            "narrative_en": narrative_en,
            "narrative_hi": narrative_hi
        },
        "what_if_model": {
            "excess_events": round(excess_ev, 2),
            "excess_ci_low": round(excess_ci_lo, 2),
            "excess_ci_high": round(excess_ci_hi, 2),
            "avg_cost_per_event": round(avg_cost_ev, 6),
            "cohort_adverse_dollars": round(cohort_adv_dol, 2),
            "bottleneck_segment": best_bot_seg,
            "bottleneck_rate_pct": bot_rate,
            "rest_rate_pct": rest_rate
        },
        "pathways": strat_dossier.get("pathways", []),
        "cube_slices": cube_slices,
        "prim_dim_name": prim_dim or "Segment",
        "sec_dim_name": sec_dim or "Subsegment",
        "prim_segments": prim_segments,
        "sec_segments": sec_segments,
        "widgets_data": {
            "temporal": {
                "is_temporal": is_temporal,
                "date_column": temp_date_col,
                "pop_delta_pp": temp_pop_delta,
                "trend_direction": temp_trend_dir,
                "periods": temporal_periods
            },
            "pareto": pareto_data,
            "lollipop": lollipop_data,
            "heatmap": heatmap_data,
            "bubble": bubble_data,
            "cliffs": cliffs_data,
            "interaction": interaction_data,
            "triage": triage_data,
            "worklist_rows": worklist_rows
        }
    }

    return payload


# -----------------------------------------------------------------------------
# 6. STANDALONE HTML & NATIVE SVG BUILDER (ZERO-CDN)
# -----------------------------------------------------------------------------
def build_bespoke_html(payload: Dict[str, Any], design_bp: Dict[str, Any]) -> str:
    """
    Renders 100% self-contained bespoke executive dashboard HTML.
    Features:
    - Zero external CDN links (no Google Fonts, no external JS/CSS)
    - OWASP-compliant JSON injection
    - Dual English / Roman Hinglish dynamic UI switch
    - Light / Dark dynamic theme switcher
    - Native responsive SVG visualization renderers with tooltips
    - Live client-side cross-filter micro-cube
    - Live What-If ROI simulator and Priority Worklist search/export
    """
    archetype_key = design_bp["archetype"]
    arch_spec = ARCHETYPE_SPECS.get(archetype_key, ARCHETYPE_SPECS["swiss_institutional_terminal"])
    def_theme = arch_spec.get("default_theme", "dark")

    # Safe JSON stringification neutralizing script escapes
    raw_payload_json = (
        json.dumps(payload)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )

    t_dark = arch_spec["dark"]
    t_light = arch_spec["light"]

    html_template = f"""<!DOCTYPE html>
<html lang="en" data-theme="{def_theme}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(payload["meta"]["title_en"])}</title>
    <style>
        /* =====================================================================
           BESPOKE DESIGN SYSTEM: {arch_spec["name"].upper()}
           Zero External CDNs & Dynamic CSS Variable Palettes
           ===================================================================== */
        :root {{
            --canvas-bg: {t_dark["canvas"]};
            --card-bg: {t_dark["card"]};
            --border-color: {t_dark["border"]};
            --accent-primary: {t_dark["accent"]};
            --accent-secondary: {t_dark["accent_alt"]};
            --text-main: {t_dark["text"]};
            --text-muted: {t_dark["muted"]};
            --font-display: {arch_spec["font_display"]};
            --font-body: {arch_spec["font_body"]};
            --card-radius: 8px;
            --shadow-elevation: 0 4px 12px rgba(0, 0, 0, 0.25);
        }}

        [data-theme="light"] {{
            --canvas-bg: {t_light["canvas"]};
            --card-bg: {t_light["card"]};
            --border-color: {t_light["border"]};
            --accent-primary: {t_light["accent"]};
            --accent-secondary: {t_light["accent_alt"]};
            --text-main: {t_light["text"]};
            --text-muted: {t_light["muted"]};
            --shadow-elevation: 0 2px 8px rgba(0, 0, 0, 0.06);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--canvas-bg);
            color: var(--text-main);
            font-family: var(--font-body);
            line-height: 1.5;
            padding: 24px;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}

        /* Command Bar */
        .cmd-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .brand-meta h1 {{
            font-family: var(--font-display);
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .brand-badges {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 6px;
            flex-wrap: wrap;
        }}
        .badge {{
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .badge-verified {{
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid #10b981;
            color: #10b981;
        }}
        .badge-circuit-breaker {{
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid #f59e0b;
            color: #f59e0b;
        }}
        .badge-persona {{
            background: rgba(99, 102, 241, 0.12);
            border: 1px solid var(--accent-primary);
            color: var(--accent-primary);
        }}

        /* Header Controls */
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .btn-ctrl {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            font-family: var(--font-body);
            font-size: 12px;
            font-weight: 600;
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s ease;
        }}
        .btn-ctrl:hover {{
            border-color: var(--accent-primary);
            color: var(--accent-primary);
        }}

        /* Slicer Ribbon */
        .slicer-ribbon {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--card-radius);
            padding: 14px 18px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 14px;
            flex-wrap: wrap;
            box-shadow: var(--shadow-elevation);
        }}
        .slicer-label {{
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.05em;
        }}
        .chips-container {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            flex: 1;
        }}
        .chip {{
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .chip:hover {{
            color: var(--text-main);
            border-color: var(--text-muted);
        }}
        .chip.active {{
            background: var(--accent-primary);
            color: #ffffff;
            border-color: var(--accent-primary);
            font-weight: 700;
        }}
        .slicer-select {{
            background: var(--canvas-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            outline: none;
            cursor: pointer;
        }}

        /* Executive Banner */
        .exec-banner {{
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.08), rgba(244, 63, 94, 0.04));
            border-left: 4px solid var(--accent-primary);
            border-radius: 0 var(--card-radius) var(--card-radius) 0;
            padding: 14px 20px;
            margin-bottom: 24px;
            font-size: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
        }}
        .exec-banner.cb-alert {{
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(239, 68, 68, 0.06));
            border-left-color: #f59e0b;
        }}

        /* Hero KPI Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--card-radius);
            padding: 18px 20px;
            box-shadow: var(--shadow-elevation);
            position: relative;
            overflow: hidden;
        }}
        .kpi-card::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: var(--border-color);
        }}
        .kpi-card.accent-red::after {{ background: #f43f5e; }}
        .kpi-card.accent-green::after {{ background: #10b981; }}
        .kpi-card.accent-gold::after {{ background: var(--accent-primary); }}
        .kpi-title {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-family: var(--font-display);
            font-size: 26px;
            font-weight: 800;
            color: var(--text-main);
        }}
        .kpi-sub {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Main 12-Column Responsive Bento Grid & Archetype Structural Geometry */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }}
        .panel-card {{
            grid-column: span 6;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--card-radius);
            padding: 20px;
            box-shadow: var(--shadow-elevation);
            display: flex;
            flex-direction: column;
            position: relative;
        }}
        .panel-card.span-12, .panel-card.full-width {{ grid-column: span 12; }}
        .panel-card.span-8 {{ grid-column: span 8; }}
        .panel-card.span-7 {{ grid-column: span 7; }}
        .panel-card.span-6 {{ grid-column: span 6; }}
        .panel-card.span-5 {{ grid-column: span 5; }}
        .panel-card.span-4 {{ grid-column: span 4; }}
        @media (max-width: 1100px) {{
            .panel-card, .panel-card.span-8, .panel-card.span-7, .panel-card.span-5, .panel-card.span-4 {{
                grid-column: span 12;
            }}
        }}

        /* Bespoke Structural Differentiation per Executive Archetype */
        body[data-archetype="swiss_institutional_terminal"] {{
            --card-radius: 2px;
        }}
        body[data-archetype="swiss_institutional_terminal"] .cmd-bar {{
            border-top: 3px double var(--accent-primary);
            padding-top: 16px;
        }}
        body[data-archetype="swiss_institutional_terminal"] .kpi-val {{
            font-variant-numeric: tabular-nums;
            letter-spacing: -0.03em;
        }}

        body[data-archetype="nordic_saas_command"] {{
            --card-radius: 12px;
        }}
        body[data-archetype="nordic_saas_command"] .panel-card {{
            backdrop-filter: blur(8px);
            border-top: 1px solid rgba(6, 182, 212, 0.28);
        }}

        body[data-archetype="editorial_commerce_studio"] {{
            --card-radius: 14px;
        }}
        body[data-archetype="editorial_commerce_studio"] .cmd-bar {{
            border-bottom: 3px double var(--border-color);
        }}
        body[data-archetype="editorial_commerce_studio"] .brand-meta h1 {{
            font-size: 27px;
            letter-spacing: -0.01em;
        }}

        body[data-archetype="industrial_scada_telemetry"] {{
            --card-radius: 3px;
        }}
        body[data-archetype="industrial_scada_telemetry"] .panel-card::before {{
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 14px;
            height: 14px;
            border-top: 2px solid var(--accent-primary);
            border-right: 2px solid var(--accent-primary);
            pointer-events: none;
        }}
        .scada-led {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 8px #10b981;
            margin-right: 6px;
        }}

        body[data-archetype="clinical_diagnostic_clarity"] {{
            --card-radius: 10px;
        }}
        body[data-archetype="clinical_diagnostic_clarity"] .panel-card {{
            border-left: 3px solid var(--accent-primary);
        }}

        /* Ontology & Governance Drawer */
        .ont-strip {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 18px;
            font-size: 11px;
            color: var(--text-muted);
        }}
        .ont-pill {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 3px 9px;
        }}
        details.gov-drawer {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--card-radius);
            padding: 14px 18px;
            margin-top: 12px;
        }}
        details.gov-drawer summary {{
            cursor: pointer;
            font-family: var(--font-display);
            font-size: 13px;
            font-weight: 700;
            color: var(--accent-primary);
        }}
        .pathway-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 12px;
            margin-top: 14px;
        }}
        .pathway-card {{
            background: var(--canvas-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 12px 14px;
            font-size: 12px;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .panel-title {{
            font-family: var(--font-display);
            font-size: 15px;
            font-weight: 700;
            color: var(--text-main);
        }}
        .panel-desc {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        .svg-container {{
            width: 100%;
            min-height: 280px;
            position: relative;
            flex: 1;
        }}

        /* Tooltip */
        #chart-tooltip {{
            position: fixed;
            display: none;
            background: rgba(15, 23, 42, 0.95);
            color: #ffffff;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 12px;
            pointer-events: none;
            z-index: 9999;
            box-shadow: 0 4px 14px rgba(0,0,0,0.4);
            max-width: 280px;
        }}

        /* What-If Simulator */
        .sim-box {{
            background: var(--canvas-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 16px;
            margin-top: 10px;
        }}
        .sim-slider-row {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin: 12px 0;
        }}
        .sim-slider {{
            flex: 1;
            accent-color: var(--accent-primary);
            cursor: pointer;
        }}
        .sim-buttons {{
            display: flex;
            gap: 10px;
            margin-bottom: 14px;
        }}
        .btn-preset {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
        }}
        .btn-preset:hover {{
            border-color: var(--accent-primary);
        }}
        .sim-results {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-top: 10px;
        }}
        .sim-res-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 12px;
            border-radius: 6px;
        }}

        /* Worklist Explorer */
        .worklist-ctrls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .worklist-tabs {{
            display: flex;
            gap: 8px;
        }}
        .wl-tab {{
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
        }}
        .wl-tab.active {{
            background: var(--accent-primary);
            color: #ffffff;
            border-color: var(--accent-primary);
        }}
        .wl-search {{
            background: var(--canvas-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            width: 240px;
            outline: none;
        }}
        .table-wrap {{
            max-height: 380px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
            border-radius: 6px;
        }}
        .worklist-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            text-align: left;
        }}
        .worklist-table th {{
            background: var(--canvas-bg);
            position: sticky;
            top: 0;
            padding: 8px 12px;
            border-bottom: 2px solid var(--border-color);
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 11px;
        }}
        .worklist-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        .worklist-table tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        /* Footer */
        footer {{
            margin-top: 36px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
            font-size: 11px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}

        /* Print Media */
        @media print {{
            body {{ background: #ffffff !important; color: #000000 !important; padding: 0; }}
            .cmd-bar button, .slicer-ribbon, .sim-slider-row, .sim-buttons, .worklist-ctrls {{ display: none !important; }}
            .panel-card {{ break-inside: avoid; border: 1px solid #ccc !important; box-shadow: none !important; }}
            #chart-tooltip {{ display: none !important; }}
        }}
    </style>
</head>
<body data-archetype="{html.escape(archetype_key, quote=True)}">
    <div id="chart-tooltip"></div>

    <!-- Top Command Bar -->
    <header class="cmd-bar">
        <div class="brand-meta">
            <h1 id="ui-title">{html.escape(payload["meta"]["title_en"])}</h1>
            <div class="brand-badges">
                <span class="badge badge-persona">{html.escape(design_bp["executive_persona"])}</span>
                <span class="badge badge-persona">{html.escape(design_bp["archetype_name"])}</span>
                <span class="badge badge-verified">{'<span class="scada-led"></span>' if archetype_key == 'industrial_scada_telemetry' else ''}&check; 100% DuckDB Ground Truth (0 Drift)</span>
                {f'<span class="badge badge-circuit-breaker">🛑 Circuit-Breaker Active</span>' if payload["circuit_breaker"]["active"] else ''}
            </div>
        </div>
        <div class="header-actions">
            <button class="btn-ctrl" id="lang-btn" onclick="toggleLanguage()">🇮🇳 Hinglish Switch</button>
            <button class="btn-ctrl" id="theme-btn" onclick="toggleTheme()">☀️ Light / 🌙 Dark</button>
            <button class="btn-ctrl" onclick="window.print()">🖨️ Print / PDF</button>
        </div>
    </header>

    <!-- Domain Ontology Intelligence Strip -->
    <div class="ont-strip">
        <span class="ont-pill"><strong>Ontology:</strong> {html.escape(design_bp["matched_ontology"]["domain_name"])} ({html.escape(design_bp["matched_ontology"]["domain_code"])})</span>
        <span class="ont-pill"><strong>Layout:</strong> {html.escape(design_bp["design_system"]["layout_concept"])}</span>
        <span class="ont-pill"><strong>DFII Score:</strong> {design_bp["dfii_score"]} / 19 ({len(design_bp["selected_panels"])} Adaptive Panels)</span>
    </div>

    <!-- Cross-Filter Slicer Ribbon -->
    <div class="slicer-ribbon">
        <div class="slicer-label" data-en="Filter by {html.escape(payload['prim_dim_name'], quote=True)}:" data-hi="{html.escape(payload['prim_dim_name'], quote=True)} Se Filter Karein:">
            Filter by {html.escape(payload['prim_dim_name'])}:
        </div>
        <div class="chips-container" id="prim-chips">
            <button class="chip active" onclick="setPrimaryFilter('All')">All Segments</button>
        </div>
        {f'''
        <div class="slicer-label" style="margin-left: 12px;" data-en="{html.escape(payload['sec_dim_name'], quote=True)}:" data-hi="{html.escape(payload['sec_dim_name'], quote=True)}:">
            {html.escape(payload['sec_dim_name'])}:
        </div>
        <select class="slicer-select" id="sec-select" onchange="setSecondaryFilter(this.value)">
            <option value="All">All {html.escape(payload['sec_dim_name'])}</option>
        </select>
        ''' if payload['sec_dim_name'] and payload['sec_dim_name'] != 'Subsegment' and len(payload.get('sec_segments', [])) >= 2 else ''}
        <button class="btn-ctrl" style="padding: 4px 10px; font-size: 11px;" onclick="resetFilters()">Reset</button>
    </div>

    <!-- Executive Insight Strip -->
    <div class="exec-banner { 'cb-alert' if payload['circuit_breaker']['active'] else '' }" id="exec-banner">
        <div>
            <strong id="exec-banner-tag" data-en="Executive Bottleneck Insight:" data-hi="Karyakari Bottleneck Jankari:">
                Executive Bottleneck Insight:
            </strong>
            <span id="exec-banner-text">{html.escape(payload["bottleneck"]["narrative_en"])}</span>
        </div>
        <div style="font-size: 12px; font-weight: 700; white-space: nowrap;">
            Status: { '🛑 $0 CapEx Freeze' if payload['circuit_breaker']['active'] else '🟢 Statistically Validated' }
        </div>
    </div>

    <!-- Hero KPI Cards -->
    <div class="kpi-grid">
        <div class="kpi-card accent-gold">
            <div class="kpi-title" data-en="Audited Records" data-hi="Kul Records">Audited Records</div>
            <div class="kpi-val" id="kpi-records">{payload['global_kpis']['total_records']:,}</div>
            <div class="kpi-sub" data-en="Zero Cartesian Drift" data-hi="100% Asli Records">Zero Cartesian Drift</div>
        </div>
        <div class="kpi-card accent-red">
            <div class="kpi-title" data-en="Adverse Events" data-hi="Failure / Nuksan Events">Adverse Events</div>
            <div class="kpi-val" id="kpi-events">{payload['global_kpis']['adverse_events']:,}</div>
            <div class="kpi-sub" id="kpi-rate-sub">Failure Rate: {payload['global_kpis']['adverse_rate_pct']:.2f}%</div>
        </div>
        <div class="kpi-card accent-green">
            <div class="kpi-title" data-en="System Reliability" data-hi="System Ki Suraksha">System Reliability</div>
            <div class="kpi-val" id="kpi-reliability">{payload['global_kpis']['system_reliability_pct']:.2f}%</div>
            <div class="kpi-sub" data-en="Unbreached Operating Profile" data-hi="Surakshit Operating Profile">Unbreached Operating Profile</div>
        </div>
        <div class="kpi-card accent-red">
            <div class="kpi-title" data-en="Adverse Capital Drag" data-hi="Direct Financial Nuksan">
                { 'Adverse Capital Drag' if payload['global_kpis']['has_monetary_ledger'] else 'Adverse Failure Share' }
            </div>
            <div class="kpi-val" id="kpi-drag">
                { f"${payload['global_kpis']['adverse_capital_drag']:,.2f}" if payload['global_kpis']['has_monetary_ledger'] else f"{payload['global_kpis']['adverse_events']:,} units" }
            </div>
            <div class="kpi-sub" id="kpi-drag-sub">
                { f"Out of ${payload['global_kpis']['total_portfolio_volume']:,.2f} total" if payload['global_kpis']['has_monetary_ledger'] else "Physical Adverse Units" }
            </div>
        </div>
    </div>

    <!-- Main Visual Panels Grid -->
    <div class="dashboard-grid" id="main-panels-container">
        <!-- Panels are injected and rendered via native SVG engine -->
    </div>

    <!-- Collapsible Statistical Proof, Pathways & Design Governance Drawer -->
    <details class="gov-drawer" id="gov-drawer">
        <summary data-en="🔬 Statistical Proof, Strategic Options (A/B/C) &amp; Design Governance Audit" data-hi="🔬 Statistical Saboot, 3 Raste (A/B/C) Aur Design Governance Audit">
            🔬 Statistical Proof, Strategic Options (A/B/C) &amp; Design Governance Audit
        </summary>
        <div id="gov-drawer-body" style="margin-top: 12px;"></div>
    </details>

    <!-- Footer -->
    <footer>
        <div>Generated Autonomously by DataX-Ray Stage 7 Bespoke Dashboard Architect &bull; Verified Physical Ground Truth</div>
        <div>Engine Version: V5.5 &bull; Archetype: {html.escape(archetype_key)} &bull; DFII Impact Index: {design_bp['dfii_score']}/19 &bull; Zero External CDNs</div>
    </footer>

    <!-- =====================================================================
         CLIENT-SIDE APPLICATION LOGIC & ZERO-CDN NATIVE SVG RENDERERS
         ===================================================================== -->
    <script>
        const DASHBOARD_PAYLOAD = /*__DXR_PAYLOAD_START__*/{raw_payload_json}/*__DXR_PAYLOAD_END__*/;

        let currentLang = 'en';
        let currentTheme = '{def_theme}';
        let activePrim = 'All';
        let activeSec = 'All';
        let currentSimPct = 60;
        let currentCliffIdx = 0;
        let currentWlSearch = '';
        let TOOLTIP_REGISTRY = [];

        function escHtml(s) {{
            return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }}

        function regTip(htmlContent) {{
            const id = TOOLTIP_REGISTRY.length;
            TOOLTIP_REGISTRY.push(htmlContent);
            return id;
        }}

        function wilsonCI95(events, n) {{
            if (!n || n <= 0) return [0, 0];
            const z = 1.959964;
            const p = events / n;
            const denom = 1 + (z * z) / n;
            const center = (p + (z * z) / (2 * n)) / denom;
            const half = (z * Math.sqrt((p * (1 - p) + (z * z) / (4 * n)) / n)) / denom;
            return [Math.max(0, (center - half) * 100), Math.min(100, (center + half) * 100)];
        }}

        // Theme Toggle
        function toggleTheme() {{
            currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', currentTheme);
            renderAllCharts();
        }}

        // Bilingual Toggle
        function toggleLanguage() {{
            currentLang = currentLang === 'en' ? 'hi' : 'en';
            document.getElementById('lang-btn').textContent = currentLang === 'en' ? '🇮🇳 Hinglish Switch' : '🇬🇧 English Switch';
            document.getElementById('ui-title').textContent = currentLang === 'en' ? DASHBOARD_PAYLOAD.meta.title_en : DASHBOARD_PAYLOAD.meta.title_hi;
            document.getElementById('exec-banner-text').textContent = currentLang === 'en' ? DASHBOARD_PAYLOAD.bottleneck.narrative_en : DASHBOARD_PAYLOAD.bottleneck.narrative_hi;

            document.querySelectorAll('[data-en]').forEach(el => {{
                el.textContent = currentLang === 'en' ? el.getAttribute('data-en') : el.getAttribute('data-hi');
            }});

            renderAllCharts();
            renderGovernanceDrawer();
        }}

        // Safe Delegated Tooltip & Cross-Filter Event Listeners (100% Immune to Quotes/XSS)
        const tooltip = document.getElementById('chart-tooltip');
        function showTooltip(evt, htmlContent) {{
            tooltip.innerHTML = htmlContent;
            tooltip.style.display = 'block';
            const x = Math.min(window.innerWidth - 295, evt.clientX + 14);
            const y = Math.min(window.innerHeight - 130, evt.clientY + 14);
            tooltip.style.left = Math.max(8, x) + 'px';
            tooltip.style.top = Math.max(8, y) + 'px';
        }}
        function hideTooltip() {{
            tooltip.style.display = 'none';
        }}

        function bindDelegatedPanelEvents() {{
            const panelHost = document.getElementById('main-panels-container');
            if (!panelHost || panelHost.dataset.delegated === '1') return;
            panelHost.dataset.delegated = '1';

            panelHost.addEventListener('mousemove', (evt) => {{
                const el = evt.target.closest('[data-tip-id]');
                if (!el) {{ hideTooltip(); return; }}
                const tid = Number(el.getAttribute('data-tip-id'));
                if (!Number.isNaN(tid) && TOOLTIP_REGISTRY[tid]) {{
                    showTooltip(evt, TOOLTIP_REGISTRY[tid]);
                }}
            }});
            panelHost.addEventListener('mouseleave', hideTooltip);

            panelHost.addEventListener('click', (evt) => {{
                const el = evt.target.closest('[data-prim-seg], [data-sec-seg]');
                if (!el) return;
                const pSeg = el.getAttribute('data-prim-seg');
                const sSeg = el.getAttribute('data-sec-seg');
                if (pSeg) {{
                    activePrim = (activePrim === pSeg && !sSeg) ? 'All' : pSeg;
                    document.querySelectorAll('#prim-chips .chip').forEach(c => {{
                        c.classList.toggle('active', c.dataset.segVal === activePrim);
                    }});
                }}
                if (sSeg) {{
                    activeSec = sSeg;
                    const secSel = document.getElementById('sec-select');
                    if (secSel) secSel.value = sSeg;
                }}
                recalcMicroCube();
            }});
        }}

        // Slicer Filtering & Micro-Cube Recalculation
        function initSlicers() {{
            const chipsBox = document.getElementById('prim-chips');
            chipsBox.innerHTML = '';
            const allBtn = document.createElement('button');
            allBtn.className = 'chip active';
            allBtn.dataset.segVal = 'All';
            allBtn.textContent = 'All Segments';
            allBtn.onclick = () => setPrimaryFilter('All');
            chipsBox.appendChild(allBtn);

            DASHBOARD_PAYLOAD.prim_segments.forEach(seg => {{
                const btn = document.createElement('button');
                btn.className = 'chip';
                btn.dataset.segVal = seg;
                btn.textContent = seg;
                btn.onclick = () => setPrimaryFilter(seg);
                chipsBox.appendChild(btn);
            }});

            const secSelect = document.getElementById('sec-select');
            if (secSelect) {{
                secSelect.innerHTML = '<option value="All">All ' + escHtml(DASHBOARD_PAYLOAD.sec_dim_name) + '</option>';
                DASHBOARD_PAYLOAD.sec_segments.forEach(seg => {{
                    const opt = document.createElement('option');
                    opt.value = seg;
                    opt.textContent = seg;
                    secSelect.appendChild(opt);
                }});
            }}
        }}

        function setPrimaryFilter(val) {{
            activePrim = val;
            document.querySelectorAll('#prim-chips .chip').forEach(c => {{
                c.classList.toggle('active', c.dataset.segVal === val);
            }});
            recalcMicroCube();
        }}

        function setSecondaryFilter(val) {{
            activeSec = val;
            recalcMicroCube();
        }}

        function resetFilters() {{
            activePrim = 'All';
            activeSec = 'All';
            const secSel = document.getElementById('sec-select');
            if (secSel) secSel.value = 'All';
            document.querySelectorAll('#prim-chips .chip').forEach(c => {{
                c.classList.toggle('active', c.dataset.segVal === 'All');
            }});
            recalcMicroCube();
        }}

        function getActiveSegmentBreakdown() {{
            if (activeSec === 'All') {{
                return DASHBOARD_PAYLOAD.widgets_data.lollipop || [];
            }}
            const bySeg = {{}};
            DASHBOARD_PAYLOAD.cube_slices.filter(s => s.sec_val === activeSec).forEach(s => {{
                if (!bySeg[s.prim_val]) bySeg[s.prim_val] = {{ segment: s.prim_val, volume: 0, events: 0, adverse_cost: 0 }};
                bySeg[s.prim_val].volume += s.volume;
                bySeg[s.prim_val].events += s.adverse_events;
                bySeg[s.prim_val].adverse_cost += s.adverse_cost;
            }});
            return Object.values(bySeg).map(d => {{
                const r = d.volume > 0 ? (d.events / d.volume) * 100 : 0;
                const [lo, hi] = wilsonCI95(d.events, d.volume);
                return {{ segment: d.segment, volume: d.volume, events: d.events, rate_pct: r, ci_low: lo, ci_high: hi, adverse_cost: d.adverse_cost }};
            }}).sort((a, b) => b.rate_pct - a.rate_pct);
        }}

        function recalcMicroCube() {{
            const slices = DASHBOARD_PAYLOAD.cube_slices.filter(s => {{
                const matchP = (activePrim === 'All' || s.prim_val === activePrim);
                const matchS = (activeSec === 'All' || s.sec_val === activeSec);
                return matchP && matchS;
            }});

            let totRec = 0, totEv = 0, totAdvCost = 0, totCost = 0;
            slices.forEach(s => {{
                totRec += s.volume;
                totEv += s.adverse_events;
                totAdvCost += s.adverse_cost;
                totCost += s.total_cost;
            }});

            const rPct = totRec > 0 ? (totEv / totRec) * 100.0 : 0.0;
            const relPct = 100.0 - rPct;

            document.getElementById('kpi-records').textContent = totRec.toLocaleString();
            document.getElementById('kpi-events').textContent = totEv.toLocaleString();
            document.getElementById('kpi-rate-sub').textContent = 'Failure Rate: ' + rPct.toFixed(2) + '%';
            document.getElementById('kpi-reliability').textContent = relPct.toFixed(2) + '%';

            if (DASHBOARD_PAYLOAD.global_kpis.has_monetary_ledger) {{
                document.getElementById('kpi-drag').textContent = '$' + totAdvCost.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                document.getElementById('kpi-drag-sub').textContent = 'Out of $' + totCost.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}}) + ' total';
            }} else {{
                document.getElementById('kpi-drag').textContent = totEv.toLocaleString() + ' units';
            }}

            renderAllCharts();
        }}

        // =====================================================================
        // NATIVE INTERACTIVE SVG CHART RENDERERS (ALL 10 CATALOG WIDGETS)
        // =====================================================================
        function renderLollipopChart(container) {{
            const data = getActiveSegmentBreakdown();
            if (!data.length) {{ container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">No segment data.</p>'; return; }}

            const maxRate = Math.max(...data.map(d => d.ci_high), 10);
            const baseline = DASHBOARD_PAYLOAD.global_kpis.adverse_rate_pct;
            const w = 540, h = Math.max(250, data.length * 34 + 34);
            const padL = 135, padR = 48, padT = 22, padB = 24;
            const chartW = w - padL - padR;

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;

            const bx = padL + Math.min(1, baseline / maxRate) * chartW;
            svg += `<line x1="${{bx}}" y1="${{padT}}" x2="${{bx}}" y2="${{h - padB}}" stroke="var(--text-muted)" stroke-dasharray="4,4" stroke-width="1.5" />`;
            svg += `<text x="${{bx}}" y="${{padT - 6}}" fill="var(--text-muted)" font-size="10" text-anchor="middle">Baseline ${{baseline.toFixed(1)}}%</text>`;

            data.slice(0, 14).forEach((d, i) => {{
                const y = padT + i * 34 + 16;
                const cx = padL + (d.rate_pct / maxRate) * chartW;
                const xLow = padL + (d.ci_low / maxRate) * chartW;
                const xHigh = padL + (d.ci_high / maxRate) * chartW;
                const isHighlighted = (activePrim === 'All' || activePrim === d.segment);
                const opacity = isHighlighted ? 1.0 : 0.28;
                const shortLbl = d.segment.length > 18 ? d.segment.substring(0, 17) + '…' : d.segment;

                svg += `<text x="${{padL - 10}}" y="${{y + 4}}" fill="var(--text-main)" font-size="11" font-weight="600" text-anchor="end" opacity="${{opacity}}">${{escHtml(shortLbl)}}</text>`;
                svg += `<line x1="${{xLow}}" y1="${{y}}" x2="${{xHigh}}" y2="${{y}}" stroke="var(--text-muted)" stroke-width="2" opacity="${{opacity}}" />`;
                svg += `<line x1="${{xLow}}" y1="${{y - 4}}" x2="${{xLow}}" y2="${{y + 4}}" stroke="var(--text-muted)" stroke-width="2" opacity="${{opacity}}" />`;
                svg += `<line x1="${{xHigh}}" y1="${{y - 4}}" x2="${{xHigh}}" y2="${{y + 4}}" stroke="var(--text-muted)" stroke-width="2" opacity="${{opacity}}" />`;
                svg += `<line x1="${{padL}}" y1="${{y}}" x2="${{cx}}" y2="${{y}}" stroke="var(--accent-primary)" stroke-width="2.5" opacity="${{opacity}}" />`;

                const tipId = regTip(
                    `<strong>${{escHtml(d.segment)}}</strong><br>Failure Rate: ${{d.rate_pct.toFixed(2)}}%<br>Wilson 95% CI: [${{d.ci_low.toFixed(1)}}% to ${{d.ci_high.toFixed(1)}}%]<br>Volume: ${{d.volume.toLocaleString()}}<br>Adverse Events: ${{d.events.toLocaleString()}}` +
                    (DASHBOARD_PAYLOAD.global_kpis.has_monetary_ledger ? `<br>Capital Drag: $${{d.adverse_cost.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}})}}` : '')
                );
                svg += `<circle cx="${{cx}}" cy="${{y}}" r="6.5" fill="var(--accent-primary)" stroke="var(--canvas-bg)" stroke-width="2" opacity="${{opacity}}" style="cursor:pointer;" data-tip-id="${{tipId}}" data-prim-seg="${{escHtml(d.segment)}}" />`;
                svg += `<text x="${{xHigh + 7}}" y="${{y + 4}}" fill="var(--accent-primary)" font-size="11" font-weight="700" opacity="${{opacity}}">${{d.rate_pct.toFixed(1)}}%</text>`;
            }});

            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function renderParetoChart(container) {{
            if (!DASHBOARD_PAYLOAD.global_kpis.has_monetary_ledger) {{
                container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">No monetary Pareto data.</p>';
                return;
            }}
            const segs = getActiveSegmentBreakdown().slice().sort((a, b) => b.adverse_cost - a.adverse_cost).slice(0, 12);
            const totDrag = Math.max(segs.reduce((acc, x) => acc + x.adverse_cost, 0), 0.01);
            let cum = 0;
            const data = segs.map(s => {{
                cum += s.adverse_cost;
                return {{ segment: s.segment, adverse_cost: s.adverse_cost, cumulative_pct: (cum / totDrag) * 100.0 }};
            }});
            if (!data.length) {{ container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">No monetary Pareto data.</p>'; return; }}

            const w = 520, h = 260;
            const padL = 56, padR = 38, padT = 28, padB = 42;
            const chartW = w - padL - padR, chartH = h - padT - padB;
            const maxDrag = Math.max(...data.map(d => d.adverse_cost), 1);
            const n = data.length;
            const barW = Math.max(12, (chartW / n) - 8);

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            const y80 = padT + (1 - 0.8) * chartH;
            svg += `<line x1="${{padL}}" y1="${{y80}}" x2="${{w - padR}}" y2="${{y80}}" stroke="#f43f5e" stroke-dasharray="3,3" stroke-width="1.5" />`;
            svg += `<text x="${{w - padR}}" y="${{y80 - 4}}" fill="#f43f5e" font-size="10" text-anchor="end">80% Pareto Line</text>`;

            let polyPoints = [];
            data.forEach((d, i) => {{
                const x = padL + i * (chartW / n) + 4;
                const barH = (d.adverse_cost / maxDrag) * chartH;
                const y = padT + chartH - barH;
                const isHi = (activePrim === 'All' || activePrim === d.segment);
                const tipId = regTip(`<strong>${{escHtml(d.segment)}}</strong><br>Adverse Drag: $${{d.adverse_cost.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}})}}<br>Cumulative Share: ${{d.cumulative_pct.toFixed(1)}}%`);

                svg += `<rect x="${{x}}" y="${{y}}" width="${{barW}}" height="${{barH}}" fill="var(--accent-primary)" opacity="${{isHi ? '0.88' : '0.28'}}" rx="3" style="cursor:pointer;" data-tip-id="${{tipId}}" data-prim-seg="${{escHtml(d.segment)}}" />`;
                svg += `<text x="${{x + barW/2}}" y="${{h - padB + 14}}" fill="var(--text-muted)" font-size="9.5" text-anchor="middle">${{escHtml(d.segment.substring(0, 9))}}</text>`;

                const cx = x + barW / 2;
                const cy = padT + (1 - (d.cumulative_pct / 100)) * chartH;
                polyPoints.push(`${{cx}},${{cy}}`);
            }});

            if (polyPoints.length > 1) {{
                svg += `<polyline points="${{polyPoints.join(' ')}}" fill="none" stroke="#f43f5e" stroke-width="2.5" />`;
                polyPoints.forEach((pt, i) => {{
                    const [px, py] = pt.split(',');
                    const d = data[i];
                    const tipId = regTip(`<strong>${{escHtml(d.segment)}}</strong><br>Cumulative Loss Concentration: ${{d.cumulative_pct.toFixed(1)}}%`);
                    svg += `<circle cx="${{px}}" cy="${{py}}" r="4" fill="#f43f5e" stroke="var(--card-bg)" stroke-width="1.5" data-tip-id="${{tipId}}" />`;
                }});
            }}
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function renderTemporalChart(container) {{
            const tempObj = DASHBOARD_PAYLOAD.widgets_data.temporal || {{}};
            const periods = tempObj.periods || [];
            if (!periods.length) return;

            const w = 520, h = 260;
            const padL = 48, padR = 36, padT = 28, padB = 42;
            const chartW = w - padL - padR, chartH = h - padT - padB;
            const maxRate = Math.max(...periods.map(p => Number(p.adverse_rate_pct || 0)), 5);
            const maxVol = Math.max(...periods.map(p => Number(p.total_records ?? p.total_volume ?? 1)), 1);
            const n = periods.length;
            const barW = Math.max(6, Math.min(28, (chartW / n) * 0.55));
            const stepLabel = Math.max(1, Math.ceil(n / 8));

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            let pts = [];

            periods.forEach((p, i) => {{
                const vol = Number(p.total_records ?? p.total_volume ?? 0);
                const rate = Number(p.adverse_rate_pct || 0);
                const x = padL + (i / Math.max(n - 1, 1)) * chartW;
                const y = padT + (1 - (rate / maxRate)) * chartH;
                const vH = (vol / maxVol) * (chartH * 0.65);
                pts.push(`${{x}},${{y}}`);

                svg += `<rect x="${{x - barW/2}}" y="${{padT + chartH - vH}}" width="${{barW}}" height="${{vH}}" fill="var(--accent-primary)" opacity="0.18" rx="2" />`;
                if (i % stepLabel === 0 || i === n - 1) {{
                    svg += `<text x="${{x}}" y="${{h - padB + 15}}" fill="var(--text-muted)" font-size="9.5" text-anchor="middle">${{escHtml(p.period)}}</text>`;
                }}
            }});

            if (pts.length > 1) {{
                const areaPts = `${{padL}},${{padT + chartH}} ` + pts.join(' ') + ` ${{padL + chartW}},${{padT + chartH}}`;
                svg += `<polygon points="${{areaPts}}" fill="rgba(99, 102, 241, 0.12)" />`;
                svg += `<polyline points="${{pts.join(' ')}}" fill="none" stroke="var(--accent-secondary)" stroke-width="3" />`;
                periods.forEach((p, i) => {{
                    const [px, py] = pts[i].split(',');
                    const vol = Number(p.total_records ?? p.total_volume ?? 0);
                    const ev = Number(p.adverse_events || 0);
                    const rate = Number(p.adverse_rate_pct || 0);
                    const tipId = regTip(`<strong>Period: ${{escHtml(p.period)}}</strong><br>Failure Rate: ${{rate.toFixed(2)}}%<br>Volume: ${{vol.toLocaleString()}}<br>Adverse Events: ${{ev.toLocaleString()}}`);
                    svg += `<circle cx="${{px}}" cy="${{py}}" r="4.5" fill="var(--accent-secondary)" stroke="var(--canvas-bg)" stroke-width="2" data-tip-id="${{tipId}}" />`;
                }});
            }}
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function renderCrossTabHeatmap(container) {{
            const hm = DASHBOARD_PAYLOAD.widgets_data.heatmap || {{}};
            const rows = hm.rows || [], cols = hm.cols || [], cells = hm.cells || [];
            if (!rows.length || !cols.length) {{
                container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">Insufficient secondary cross-tab dimensions.</p>';
                return;
            }}
            const cellMap = {{}};
            let maxRate = 5;
            cells.forEach(c => {{
                cellMap[c.prim_val + '|||' + c.sec_val] = c;
                if (c.rate_pct > maxRate) maxRate = c.rate_pct;
            }});

            const w = 540, h = Math.max(250, rows.length * 28 + 64);
            const padL = 128, padR = 18, padT = 44, padB = 16;
            const cellW = (w - padL - padR) / cols.length;
            const cellH = (h - padT - padB) / rows.length;

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            cols.forEach((colVal, ci) => {{
                const cx = padL + ci * cellW + cellW / 2;
                const lbl = colVal.length > 10 ? colVal.substring(0, 9) + '…' : colVal;
                svg += `<text x="${{cx}}" y="${{padT - 10}}" fill="var(--text-muted)" font-size="9.5" font-weight="600" text-anchor="middle">${{escHtml(lbl)}}</text>`;
            }});

            rows.forEach((rowVal, ri) => {{
                const ry = padT + ri * cellH;
                const rLbl = rowVal.length > 17 ? rowVal.substring(0, 16) + '…' : rowVal;
                svg += `<text x="${{padL - 8}}" y="${{ry + cellH / 2 + 4}}" fill="var(--text-main)" font-size="10" font-weight="600" text-anchor="end">${{escHtml(rLbl)}}</text>`;
                cols.forEach((colVal, ci) => {{
                    const rx = padL + ci * cellW;
                    const c = cellMap[rowVal + '|||' + colVal];
                    const vol = c ? c.volume : 0;
                    const rate = c ? c.rate_pct : 0;
                    const ev = c ? c.events : 0;
                    const alpha = vol > 0 ? Math.min(0.90, 0.14 + (rate / maxRate) * 0.76) : 0.04;
                    const fillCol = vol > 0 ? `rgba(244, 63, 94, ${{alpha.toFixed(2)}})` : 'var(--canvas-bg)';
                    const tipId = regTip(
                        `<strong>${{escHtml(rowVal)}} &times; ${{escHtml(colVal)}}</strong><br>Failure Rate: ${{rate.toFixed(2)}}%<br>Volume: ${{vol.toLocaleString()}}<br>Adverse Events: ${{ev.toLocaleString()}}` +
                        (DASHBOARD_PAYLOAD.global_kpis.has_monetary_ledger && c ? `<br>Drag: $${{c.adverse_cost.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}})}}` : '')
                    );
                    svg += `<rect x="${{rx + 1.5}}" y="${{ry + 1.5}}" width="${{Math.max(4, cellW - 3)}}" height="${{Math.max(4, cellH - 3)}}" fill="${{fillCol}}" stroke="var(--border-color)" rx="3" style="cursor:pointer;" data-tip-id="${{tipId}}" data-prim-seg="${{escHtml(rowVal)}}" data-sec-seg="${{escHtml(colVal)}}" />`;
                    if (vol > 0 && cellW >= 38) {{
                        svg += `<text x="${{rx + cellW / 2}}" y="${{ry + cellH / 2 + 4}}" fill="var(--text-main)" font-size="9.5" font-weight="700" text-anchor="middle" pointer-events="none">${{rate.toFixed(1)}}%</text>`;
                    }}
                }});
            }});
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function renderExposureBubbleChart(container) {{
            const data = getActiveSegmentBreakdown().slice(0, 14);
            if (data.length < 2) {{
                container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">Insufficient cohort dispersion for bubble plot.</p>';
                return;
            }}
            const w = 520, h = 260;
            const padL = 52, padR = 36, padT = 26, padB = 38;
            const chartW = w - padL - padR, chartH = h - padT - padB;
            const maxVol = Math.max(...data.map(d => d.volume), 1);
            const maxRate = Math.max(...data.map(d => d.rate_pct), 10) * 1.12;
            const isMon = DASHBOARD_PAYLOAD.global_kpis.has_monetary_ledger;
            const maxImpact = Math.max(...data.map(d => isMon ? d.adverse_cost : d.events), 1);
            const baseRate = DASHBOARD_PAYLOAD.global_kpis.adverse_rate_pct;

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            const by = padT + (1 - Math.min(1, baseRate / maxRate)) * chartH;
            svg += `<line x1="${{padL}}" y1="${{by}}" x2="${{w - padR}}" y2="${{by}}" stroke="var(--text-muted)" stroke-dasharray="4,4" stroke-width="1.2" />`;
            svg += `<text x="${{w - padR}}" y="${{by - 5}}" fill="var(--text-muted)" font-size="9.5" text-anchor="end">Mean Rate ${{baseRate.toFixed(1)}}%</text>`;
            svg += `<text x="${{padL + chartW / 2}}" y="${{h - 6}}" fill="var(--text-muted)" font-size="10" text-anchor="middle">Cohort Volume (Records) &rarr;</text>`;

            data.forEach(d => {{
                const cx = padL + (d.volume / maxVol) * (chartW * 0.90) + chartW * 0.04;
                const cy = padT + (1 - (d.rate_pct / maxRate)) * chartH;
                const impact = isMon ? d.adverse_cost : d.events;
                const r = 6 + Math.sqrt(Math.max(0, impact) / maxImpact) * 18;
                const isHi = (activePrim === 'All' || activePrim === d.segment);
                const fill = d.rate_pct >= baseRate ? '#f43f5e' : 'var(--accent-primary)';
                const tipId = regTip(
                    `<strong>${{escHtml(d.segment)}}</strong><br>Volume: ${{d.volume.toLocaleString()}}<br>Failure Rate: ${{d.rate_pct.toFixed(2)}}%<br>Events: ${{d.events.toLocaleString()}}` +
                    (isMon ? `<br>Capital Drag: $${{d.adverse_cost.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}})}}` : '')
                );
                svg += `<circle cx="${{cx}}" cy="${{cy}}" r="${{r.toFixed(1)}}" fill="${{fill}}" fill-opacity="${{isHi ? '0.68' : '0.20'}}" stroke="${{fill}}" stroke-width="2" style="cursor:pointer;" data-tip-id="${{tipId}}" data-prim-seg="${{escHtml(d.segment)}}" />`;
                svg += `<text x="${{cx}}" y="${{cy - r - 4}}" fill="var(--text-main)" font-size="9.5" font-weight="600" text-anchor="middle" opacity="${{isHi ? '1' : '0.35'}}" pointer-events="none">${{escHtml(d.segment.substring(0, 12))}}</text>`;
            }});
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function renderCliffChart(container, selectedIndex = 0) {{
            const cliffs = DASHBOARD_PAYLOAD.widgets_data.cliffs || [];
            if (!cliffs.length) return;
            const cliff = cliffs[selectedIndex] || cliffs[0];
            const bins = cliff.bins || [];

            const w = 520, h = 260;
            const padL = 50, padR = 40, padT = 30, padB = 42;
            const chartW = w - padL - padR, chartH = h - padT - padB;
            const maxRate = Math.max(...bins.map(b => b.rate_pct), 10) * 1.1;
            const n = bins.length;

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            const pTxt = cliff.p_value < 0.0001 ? 'p < 0.0001' : ('p = ' + Number(cliff.p_value).toFixed(4));
            svg += `<text x="${{w - padR}}" y="16" fill="#f43f5e" font-size="10" font-weight="700" text-anchor="end">${{escHtml(cliff.column)}} &bull; Max Jump +${{(cliff.max_delta * 100).toFixed(1)}}pp (${{pTxt}})</text>`;

            let pts = [];
            bins.forEach((b, i) => {{
                const x = padL + (i / Math.max(n - 1, 1)) * chartW;
                const y = padT + (1 - (b.rate_pct / maxRate)) * chartH;
                pts.push(`${{x}},${{y}}`);
                svg += `<text x="${{x}}" y="${{h - padB + 15}}" fill="var(--text-muted)" font-size="9.5" text-anchor="middle">Q${{i+1}}: ${{escHtml(String(b.range).substring(0, 13))}}</text>`;
            }});

            if (pts.length > 1) {{
                const areaPts = `${{padL}},${{padT + chartH}} ` + pts.join(' ') + ` ${{padL + chartW}},${{padT + chartH}}`;
                svg += `<polygon points="${{areaPts}}" fill="rgba(244, 63, 94, 0.16)" />`;
                svg += `<polyline points="${{pts.join(' ')}}" fill="none" stroke="#f43f5e" stroke-width="3" />`;

                bins.forEach((b, i) => {{
                    const [px, py] = pts[i].split(',');
                    const tipId = regTip(`<strong>${{escHtml(cliff.column)}} (Q${{i+1}})</strong><br>Range: ${{escHtml(b.range)}}<br>Failure Rate: ${{b.rate_pct.toFixed(2)}}%<br>Volume: ${{b.count.toLocaleString()}}<br>Events: ${{b.events.toLocaleString()}}`);
                    svg += `<circle cx="${{px}}" cy="${{py}}" r="5.5" fill="#f43f5e" stroke="var(--canvas-bg)" stroke-width="2" data-tip-id="${{tipId}}" />`;
                    svg += `<text x="${{px}}" y="${{Number(py) - 9}}" fill="var(--text-main)" font-size="10" font-weight="700" text-anchor="middle">${{b.rate_pct.toFixed(1)}}%</text>`;
                }});
            }}
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function render2x2Quadrant(container) {{
            const inter = DASHBOARD_PAYLOAD.widgets_data.interaction || {{}};
            const q = inter.quadrants;
            if (!q) return;

            const posName = inter.pos_driver || 'Risk Driver';
            const negName = inter.neg_driver || 'Buffer';
            const medPos = inter.med_pos !== undefined ? Number(inter.med_pos).toFixed(2) : '';
            const medNeg = inter.med_neg !== undefined ? Number(inter.med_neg).toFixed(2) : '';

            const w = 480, h = 260;
            const pad = 18;
            const boxW = (w - pad * 3) / 2;
            const boxH = (h - pad * 3) / 2;

            const quadBoxes = [
                {{ key: 'Q1_optimal', title: 'Q1: Optimal Zone', x: pad, y: pad, color: '#10b981', desc: `Low ${{posName}} (\u2264${{medPos}}) & High ${{negName}}` }},
                {{ key: 'Q2_unbuffered', title: 'Q2: Unbuffered Baseline', x: pad * 2 + boxW, y: pad, color: '#38bdf8', desc: `Low ${{posName}} & Low ${{negName}} (\u2264${{medNeg}})` }},
                {{ key: 'Q3_masked', title: 'Q3: Masked Risk', x: pad, y: pad * 2 + boxH, color: '#f59e0b', desc: `High ${{posName}} (>${{medPos}}) & High ${{negName}}` }},
                {{ key: 'Q4_catastrophic', title: 'Q4: Compound Catastrophe', x: pad * 2 + boxW, y: pad * 2 + boxH, color: '#f43f5e', desc: `High ${{posName}} & Low ${{negName}}` }}
            ];

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            quadBoxes.forEach(qb => {{
                const d = q[qb.key] || {{ count: 0, events: 0, rate: 0.0 }};
                const tipId = regTip(`<strong>${{escHtml(qb.title)}}</strong><br>${{escHtml(qb.desc)}}<br>Volume: ${{d.count.toLocaleString()}}<br>Events: ${{d.events.toLocaleString()}}<br>Failure Rate: ${{d.rate.toFixed(2)}}%`);
                const shortDesc = qb.desc.length > 36 ? qb.desc.substring(0, 35) + '…' : qb.desc;

                svg += `<rect x="${{qb.x}}" y="${{qb.y}}" width="${{boxW}}" height="${{boxH}}" fill="var(--card-bg)" stroke="${{qb.color}}" stroke-width="2" rx="6" data-tip-id="${{tipId}}" />`;
                svg += `<text x="${{qb.x + 12}}" y="${{qb.y + 22}}" fill="${{qb.color}}" font-size="11.5" font-weight="700" pointer-events="none">${{escHtml(qb.title)}}</text>`;
                svg += `<text x="${{qb.x + 12}}" y="${{qb.y + 40}}" fill="var(--text-muted)" font-size="9.5" pointer-events="none">${{escHtml(shortDesc)}}</text>`;
                svg += `<text x="${{qb.x + 12}}" y="${{qb.y + 72}}" fill="var(--text-main)" font-size="19" font-weight="800" pointer-events="none">${{d.rate.toFixed(2)}}%</text>`;
                svg += `<text x="${{qb.x + 12}}" y="${{qb.y + 90}}" fill="var(--text-muted)" font-size="10" pointer-events="none">${{d.count.toLocaleString()}} records (${{d.events.toLocaleString()}} events)</text>`;
            }});
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        function renderTriageYieldChart(container) {{
            const triage = DASHBOARD_PAYLOAD.widgets_data.triage || [];
            if (!triage.length) return;

            const w = 520, h = 260;
            const padL = 50, padR = 40, padT = 30, padB = 40;
            const chartW = w - padL - padR, chartH = h - padT - padB;

            let svg = `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="100%" preserveAspectRatio="xMinYMin meet">`;
            svg += `<text x="${{padL + chartW / 2}}" y="${{h - 6}}" fill="var(--text-muted)" font-size="10" text-anchor="middle">Flagged / Intake Hold % &rarr;</text>`;
            let pts = [];

            triage.forEach(t => {{
                const x = padL + (t.scrap_pct / 100) * chartW;
                const y = padT + (1 - (t.recall_pct / 100)) * chartH;
                pts.push(`${{x}},${{y}}`);
            }});

            if (pts.length > 1) {{
                svg += `<polyline points="${{pts.join(' ')}}" fill="none" stroke="var(--accent-primary)" stroke-width="3" stroke-dasharray="4,3" />`;
                triage.forEach((t, i) => {{
                    const [px, py] = pts[i].split(',');
                    const polName = t.policy_name.split('(')[0].trim();
                    const tipId = regTip(`<strong>${{escHtml(t.policy_name)}}</strong><br>Flagged/Scrap: ${{t.scrap_pct.toFixed(1)}}%<br>Defect Recall: ${{t.recall_pct.toFixed(1)}}%<br>Retained Defect Rate: ${{t.retained_defect_rate.toFixed(2)}}%<br>False Alarms: ${{t.false_discards.toLocaleString()}}`);
                    svg += `<circle cx="${{px}}" cy="${{py}}" r="6.5" fill="var(--accent-primary)" stroke="var(--canvas-bg)" stroke-width="2" data-tip-id="${{tipId}}" />`;
                    svg += `<text x="${{px}}" y="${{Number(py) - 10}}" fill="var(--text-main)" font-size="10" font-weight="700" text-anchor="middle">${{escHtml(polName)}} (${{t.recall_pct.toFixed(0)}}% recall)</text>`;
                }});
            }}
            svg += `</svg>`;
            container.innerHTML = svg;
        }}

        // =====================================================================
        // WHAT-IF COUNTERFACTUAL SIMULATOR (100% PHYSICAL EXCESS-RISK MATH)
        // =====================================================================
        function initWhatIfSimulator(container) {{
            const cbActive = DASHBOARD_PAYLOAD.circuit_breaker.active;
            const pathways = Array.isArray(DASHBOARD_PAYLOAD.pathways) ? DASHBOARD_PAYLOAD.pathways : [];

            let pathCardsHtml = '';
            if (pathways.length) {{
                pathCardsHtml = `<div class="pathway-grid">` + pathways.map(pw => `
                    <div class="pathway-card">
                        <div style="font-weight:700;color:var(--accent-primary);margin-bottom:4px;">${{escHtml(pw.path_name)}}</div>
                        <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px;">
                            <strong>Cost:</strong> ${{escHtml(pw.implementation_cost)}} &bull; <strong>Timeline:</strong> ${{escHtml(pw.time_to_impact)}}
                        </div>
                        <div style="font-size:11px;margin-bottom:4px;"><strong>Impact:</strong> ${{escHtml(pw.projected_friction_reduction)}}</div>
                        <div style="font-size:11px;color:#10b981;margin-bottom:3px;"><strong>Pros (Fayda):</strong> ${{escHtml(pw.fayda_pros)}}</div>
                        <div style="font-size:11px;color:#f59e0b;"><strong>Cons / Friction:</strong> ${{escHtml(pw.nuksan_cons)}}</div>
                    </div>
                `).join('') + `</div>`;
            }}

            let htmlStr = `
                <div class="sim-box">
                    <div style="font-size:12px;font-weight:700;margin-bottom:8px;" data-en="Simulate Excess-Risk Mitigation (% Parity with Baseline):" data-hi="Excess-Risk Bachav Ka Live Simulation Karein (% Parity):">
                        Simulate Excess-Risk Mitigation (% Parity with Baseline):
                    </div>
                    ${{cbActive ? `
                    <div style="background:rgba(245,158,11,0.15);border:1px solid #f59e0b;padding:10px;border-radius:6px;font-size:12px;color:#f59e0b;margin-bottom:12px;">
                        🛑 <strong>Statistical Circuit-Breaker Active ($0 CapEx Freeze):</strong> Observed difference is within random sampling noise (p &ge; 0.05). Targeted CapEx is frozen to protect capital.
                    </div>
                    ` : `
                    <div class="sim-buttons">
                        <button class="btn-preset" onclick="setSimValue(25)">Pathway A: 25% (Conservative)</button>
                        <button class="btn-preset" onclick="setSimValue(60)">Pathway B: 60% (Surgical)</button>
                        <button class="btn-preset" onclick="setSimValue(100)">Pathway C: 100% (Structural Parity)</button>
                    </div>
                    <div class="sim-slider-row">
                        <span style="font-size:12px;color:var(--text-muted);">0%</span>
                        <input type="range" min="0" max="100" value="${{currentSimPct}}" class="sim-slider" id="sim-slider" oninput="updateWhatIfDisplay()" />
                        <span style="font-size:12px;font-weight:700;width:45px;" id="sim-val-display">${{currentSimPct}}%</span>
                    </div>
                    `}}
                    <div class="sim-results">
                        <div class="sim-res-card">
                            <div class="kpi-title" data-en="Averted Excess Events" data-hi="Roke Gaye Excess Events">Averted Excess Events</div>
                            <div class="kpi-val" id="sim-averted-ev" style="font-size:20px;color:#10b981;">0</div>
                            <div class="kpi-sub" id="sim-ev-ci">95% CI: [0 to 0]</div>
                        </div>
                        <div class="sim-res-card">
                            <div class="kpi-title" data-en="Projected Risk Averted" data-hi="Bachaya Gaya Financial Nuksan">Projected Risk Averted</div>
                            <div class="kpi-val" id="sim-averted-drag" style="font-size:20px;color:var(--accent-primary);">$0.00</div>
                            <div class="kpi-sub" id="sim-drag-ci">Physical Ledger Grounded</div>
                        </div>
                        <div class="sim-res-card">
                            <div class="kpi-title" data-en="Post-Mitigation Bottleneck Rate" data-hi="Sudhaar Ke Baad Bottleneck Dar">Post-Mitigation Bottleneck Rate</div>
                            <div class="kpi-val" id="sim-post-rate" style="font-size:20px;color:var(--text-main);">0.00%</div>
                            <div class="kpi-sub" id="sim-post-sub">Target Cohort Compression</div>
                        </div>
                    </div>
                    ${{pathCardsHtml}}
                </div>
            `;
            container.innerHTML = htmlStr;
            updateWhatIfDisplay();
        }}

        function setSimValue(v) {{
            currentSimPct = Number(v);
            const slider = document.getElementById('sim-slider');
            if (slider) {{
                slider.value = currentSimPct;
                updateWhatIfDisplay();
            }}
        }}

        function updateWhatIfDisplay() {{
            const slider = document.getElementById('sim-slider');
            if (slider) currentSimPct = Number(slider.value);
            const pct = currentSimPct;
            const valDisp = document.getElementById('sim-val-display');
            if (valDisp) valDisp.textContent = pct + '%';

            const elEv = document.getElementById('sim-averted-ev');
            const elEvCi = document.getElementById('sim-ev-ci');
            const elDrag = document.getElementById('sim-averted-drag');
            const elDragCi = document.getElementById('sim-drag-ci');
            const elPost = document.getElementById('sim-post-rate');
            const elPostSub = document.getElementById('sim-post-sub');
            if (!elEv || !elDrag) return;

            const cbActive = DASHBOARD_PAYLOAD.circuit_breaker.active;
            const isMonetary = DASHBOARD_PAYLOAD.global_kpis.has_monetary_ledger;
            const wm = DASHBOARD_PAYLOAD.what_if_model || {{}};
            const excessEv = Number(wm.excess_events ?? DASHBOARD_PAYLOAD.bottleneck.excess_events ?? 0);
            const ciLo = Number(wm.excess_ci_low ?? 0);
            const ciHi = Number(wm.excess_ci_high ?? 0);
            const avgCost = Number(wm.avg_cost_per_event ?? 0);
            const botRate = Number(wm.bottleneck_rate_pct ?? DASHBOARD_PAYLOAD.bottleneck.rate_pct ?? 0);
            const restRate = Number(wm.rest_rate_pct ?? DASHBOARD_PAYLOAD.bottleneck.rest_rate_pct ?? 0);

            if (cbActive) {{
                elEv.textContent = '0 events';
                if (elEvCi) elEvCi.textContent = 'Noise Gate Active (p >= 0.05)';
                elDrag.textContent = isMonetary ? '$0.00 ($0 Freeze)' : '0 units ($0 Freeze)';
                if (elDragCi) elDragCi.textContent = 'CapEx Frozen — Random Variation';
                if (elPost) elPost.textContent = botRate.toFixed(2) + '%';
                if (elPostSub) elPostSub.textContent = 'No cohort intervention advised';
                return;
            }}

            const avertedEv = pct === 0 ? 0 : Math.max(1, Math.round(excessEv * (pct / 100)));
            const evLo = Math.max(0, Math.round(ciLo * (pct / 100)));
            const evHi = Math.max(evLo, Math.round(ciHi * (pct / 100)));

            elEv.textContent = avertedEv.toLocaleString() + ' events';
            if (elEvCi) elEvCi.textContent = `95% CI: [${{evLo.toLocaleString()}} to ${{evHi.toLocaleString()}} events]`;

            if (isMonetary) {{
                const avertedDol = avertedEv * avgCost;
                const dolLo = evLo * avgCost;
                const dolHi = evHi * avgCost;
                elDrag.textContent = '$' + avertedDol.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                if (elDragCi) elDragCi.textContent = `95% CI: [$${{dolLo.toLocaleString(undefined, {{maximumFractionDigits:0}})}} to $${{dolHi.toLocaleString(undefined, {{maximumFractionDigits:0}})}}]`;
            }} else {{
                elDrag.textContent = avertedEv.toLocaleString() + ' physical units';
                if (elDragCi) elDragCi.textContent = 'Zero fabricated currency (*1000 ban)';
            }}

            const newRate = Math.max(restRate, botRate - (botRate - restRate) * (pct / 100));
            if (elPost) elPost.textContent = newRate.toFixed(2) + '%';
            if (elPostSub) elPostSub.textContent = `Down from ${{botRate.toFixed(2)}}% toward ${{restRate.toFixed(2)}}% baseline`;
        }}

        // =====================================================================
        // ACTIONABLE WORKLIST EXPLORER TABLE
        // =====================================================================
        let currentWlQueue = 'PREVENTIVE_RETENTION_WATCH';
        function initWorklistExplorer(container) {{
            const rows = DASHBOARD_PAYLOAD.widgets_data.worklist_rows || [];
            if (!rows.length) {{
                container.innerHTML = '<p style="color:var(--text-muted);padding:20px;">No priority worklist rows discovered.</p>';
                return;
            }}
            const nPrev = rows.filter(r => r.action_queue === 'PREVENTIVE_RETENTION_WATCH').length;
            const nRec = rows.filter(r => r.action_queue === 'REALIZED_LOSS_RECOVERY_AUDIT').length;

            let htmlStr = `
                <div class="worklist-ctrls">
                    <div class="worklist-tabs">
                        <button class="wl-tab ${{currentWlQueue === 'PREVENTIVE_RETENTION_WATCH' ? 'active' : ''}}" id="tab-prev" onclick="switchWlQueue('PREVENTIVE_RETENTION_WATCH')">Preventive Retention Watch (${{nPrev}})</button>
                        <button class="wl-tab ${{currentWlQueue === 'REALIZED_LOSS_RECOVERY_AUDIT' ? 'active' : ''}}" id="tab-rec" onclick="switchWlQueue('REALIZED_LOSS_RECOVERY_AUDIT')">Realized Loss Recovery (${{nRec}})</button>
                    </div>
                    <div style="display:flex;gap:10px;">
                        <input type="text" class="wl-search" id="wl-search" value="${{escHtml(currentWlSearch)}}" placeholder="Search ID, cohort, reason..." oninput="filterWorklistTable()" />
                        <button class="btn-ctrl" onclick="downloadWorklistCSV()">⬇️ Export CSV</button>
                    </div>
                </div>
                <div class="table-wrap">
                    <table class="worklist-table" id="worklist-table">
                        <thead id="wl-thead"></thead>
                        <tbody id="wl-tbody"></tbody>
                    </table>
                </div>
            `;
            container.innerHTML = htmlStr;
            renderWorklistTable();
        }}

        function switchWlQueue(queueName) {{
            currentWlQueue = queueName;
            document.getElementById('tab-prev')?.classList.toggle('active', queueName === 'PREVENTIVE_RETENTION_WATCH');
            document.getElementById('tab-rec')?.classList.toggle('active', queueName === 'REALIZED_LOSS_RECOVERY_AUDIT');
            renderWorklistTable();
        }}

        function getFilteredWorklistRows() {{
            const rows = DASHBOARD_PAYLOAD.widgets_data.worklist_rows || [];
            const pCol = DASHBOARD_PAYLOAD.prim_dim_name;
            const query = currentWlSearch.toLowerCase();
            return rows.filter(r => {{
                if (r.action_queue !== currentWlQueue) return false;
                if (activePrim !== 'All' && pCol && Object.prototype.hasOwnProperty.call(r, pCol) && String(r[pCol]) !== activePrim) return false;
                if (!query) return true;
                return Object.values(r).some(v => String(v ?? '').toLowerCase().includes(query));
            }});
        }}

        function renderWorklistTable() {{
            const searchEl = document.getElementById('wl-search');
            if (searchEl) currentWlSearch = searchEl.value || '';
            const filtered = getFilteredWorklistRows();

            const thead = document.getElementById('wl-thead');
            const tbody = document.getElementById('wl-tbody');
            if (!thead || !tbody) return;

            if (!filtered.length) {{
                thead.innerHTML = '';
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px;">No matching records in this queue for active filter.</td></tr>';
                return;
            }}

            const cols = Object.keys(filtered[0]).filter(c => c !== '_is_target_event' && c !== 'action_queue').slice(0, 7);
            let thHtml = '<tr>';
            cols.forEach(c => thHtml += '<th>' + escHtml(c.replace(/_/g, ' ')) + '</th>');
            thHtml += '</tr>';
            thead.innerHTML = thHtml;

            let trHtml = '';
            filtered.slice(0, 60).forEach(r => {{
                trHtml += '<tr>';
                cols.forEach(c => {{
                    const v = r[c];
                    const disp = (v === null || v === undefined || v === '') ? '—' : v;
                    trHtml += '<td>' + escHtml(disp) + '</td>';
                }});
                trHtml += '</tr>';
            }});
            tbody.innerHTML = trHtml;
        }}

        function filterWorklistTable() {{
            renderWorklistTable();
        }}

        function downloadWorklistCSV() {{
            const rows = getFilteredWorklistRows();
            const exportRows = rows.length ? rows : (DASHBOARD_PAYLOAD.widgets_data.worklist_rows || []);
            if (!exportRows.length) return;
            const cols = Object.keys(exportRows[0]);
            let csv = cols.join(',') + '\\n';
            exportRows.forEach(r => {{
                csv += cols.map(c => '"' + String(r[c] ?? '').replace(/"/g, '""') + '"').join(',') + '\\n';
            }});
            const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'actionable_priority_worklist.csv';
            a.click();
        }}

        // =====================================================================
        // GOVERNANCE PROOF DRAWER & ARCHETYPE BENTO SPAN ENGINE
        // =====================================================================
        function getArchetypeSpanClass(pId, idx) {{
            if (pId === 'actionable_worklist_explorer' || pId === 'what_if_counterfactual_simulator') return 'span-12 full-width';
            const arch = DASHBOARD_PAYLOAD.meta.archetype;
            if (arch === 'nordic_saas_command' && idx < 2) return idx === 0 ? 'span-8' : 'span-4';
            if (arch === 'swiss_institutional_terminal' && idx < 2) return idx === 0 ? 'span-7' : 'span-5';
            if (arch === 'industrial_scada_telemetry' && idx < 2) return idx === 0 ? 'span-8' : 'span-4';
            if (arch === 'editorial_commerce_studio' && idx === 0 && pId === 'temporal_momentum_ribbon') return 'span-12';
            return 'span-6';
        }}

        function renderGovernanceDrawer() {{
            const box = document.getElementById('gov-drawer-body');
            if (!box) return;
            const cb = DASHBOARD_PAYLOAD.circuit_breaker || {{}};
            const dfii = DASHBOARD_PAYLOAD.dfii || {{}};
            const ont = DASHBOARD_PAYLOAD.ontology || {{}};
            const sel = DASHBOARD_PAYLOAD.selected_panels_detail || [];
            const rej = DASHBOARD_PAYLOAD.rejected_panels_detail || [];

            const kpiList = (ont.key_metrics_kpis || []).map(k => `<li>${{escHtml(k)}}</li>`).join('');
            const leakList = (ont.hidden_leakage_risks || []).map(k => `<li>${{escHtml(k)}}</li>`).join('');
            const selRows = sel.map(p => `<tr><td><strong>${{escHtml(p.name)}}</strong></td><td style="color:#10b981;">SELECTED (P${{p.priority}})</td><td>${{escHtml(p.justification)}}</td></tr>`).join('');
            const rejRows = rej.map(p => `<tr><td>${{escHtml(p.name)}}</td><td style="color:var(--text-muted);">REJECTED</td><td>${{escHtml(p.reason)}}</td></tr>`).join('');

            box.innerHTML = `
                <div class="pathway-grid" style="margin-bottom:14px;">
                    <div class="pathway-card">
                        <div style="font-weight:700;margin-bottom:4px;">Statistical Hypothesis Proof</div>
                        <div>Two-Proportion z-Stat: <strong>${{Number(cb.z_stat || 0).toFixed(2)}}</strong></div>
                        <div>Two-Tailed p-Value: <strong>${{Number(cb.p_value ?? 1).toExponential(3)}}</strong></div>
                        <div>Relative Risk Lift: <strong>${{Number(cb.relative_risk_multiplier || 1).toFixed(2)}}x</strong></div>
                        <div>Attributable Excess Events: <strong>${{Number(cb.excess_events || 0).toFixed(1)}}</strong></div>
                    </div>
                    <div class="pathway-card">
                        <div style="font-weight:700;margin-bottom:4px;">DFII Design Score (${{dfii.dfii || 16}} / 19)</div>
                        <div>Aesthetic Impact: ${{dfii.aesthetic_impact || 5}}/5 &bull; Context Fit: ${{dfii.context_fit || 5}}/5</div>
                        <div>Feasibility: ${{dfii.implementation_feasibility || 5}}/5 &bull; Perf Safety: ${{dfii.performance_safety || 5}}/5</div>
                        <div>Consistency Risk Penalty: -${{dfii.consistency_risk || 1}}</div>
                    </div>
                    <div class="pathway-card">
                        <div style="font-weight:700;margin-bottom:4px;">Ontology Watchpoints (${{escHtml(ont.domain_code || 'GEN')}})</div>
                        <ul style="padding-left:16px;margin-top:4px;">${{leakList || kpiList}}</ul>
                    </div>
                </div>
                <div class="table-wrap" style="max-height:240px;">
                    <table class="worklist-table">
                        <thead><tr><th>Catalog Widget</th><th>Decision</th><th>Mathematical / Shape Justification</th></tr></thead>
                        <tbody>${{selRows}}${{rejRows}}</tbody>
                    </table>
                </div>
            `;
        }}

        function onCliffFeatureChange(val) {{
            currentCliffIdx = Number(val) || 0;
            const cBox = document.getElementById('chart-cliff');
            if (cBox) renderCliffChart(cBox, currentCliffIdx);
        }}

        // =====================================================================
        // ASSEMBLE ALL 10 CATALOG PANELS & INITIALIZE
        // =====================================================================
        function renderAllCharts() {{
            const container = document.getElementById('main-panels-container');
            if (!container) return;
            TOOLTIP_REGISTRY = [];
            container.innerHTML = '';

            const panels = DASHBOARD_PAYLOAD.selected_panels || [];

            panels.forEach((pId, idx) => {{
                const card = document.createElement('div');
                card.className = 'panel-card ' + getArchetypeSpanClass(pId, idx);

                if (pId === 'segment_vulnerability_lollipop') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Primary Segment Vulnerability &amp; Wilson 95% CIs' : 'Segments Ki Kamzori Aur 95% Confidence Bounds'}}</div>
                                <div class="panel-desc">Ranked failure rate across ${{escHtml(DASHBOARD_PAYLOAD.prim_dim_name)}} cohorts (click any node to cross-filter).</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-lollipop"></div>
                    `;
                    container.appendChild(card);
                    renderLollipopChart(card.querySelector('#chart-lollipop'));
                }}
                else if (pId === 'pareto_loss_waterfall') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Pareto 80/20 Cumulative Financial Loss Waterfall' : 'Pareto 80/20 Financial Nuksan Waterfall'}}</div>
                                <div class="panel-desc">Cumulative adverse capital concentration across ${{escHtml(DASHBOARD_PAYLOAD.prim_dim_name)}}.</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-pareto"></div>
                    `;
                    container.appendChild(card);
                    renderParetoChart(card.querySelector('#chart-pareto'));
                }}
                else if (pId === 'temporal_momentum_ribbon') {{
                    const tObj = DASHBOARD_PAYLOAD.widgets_data.temporal || {{}};
                    const popStr = tObj.pop_delta_pp !== undefined ? ` (${{tObj.pop_delta_pp >= 0 ? '+' : ''}}${{Number(tObj.pop_delta_pp).toFixed(2)}}pp PoP &bull; ${{escHtml(tObj.trend_direction || 'STABLE')}})` : '';
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Temporal Failure Rate &amp; Volume Momentum' : 'Samay Ke Sath Failure Rate Aur Volume Trend'}}</div>
                                <div class="panel-desc">Dual-axis volume bars &amp; adverse rate trajectory via ${{escHtml(tObj.date_column || 'Date')}}${{popStr}}.</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-temporal"></div>
                    `;
                    container.appendChild(card);
                    renderTemporalChart(card.querySelector('#chart-temporal'));
                }}
                else if (pId === 'secondary_cross_tab_heatmap') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? '2D Cross-Tabulation Risk Concentration Heatmap' : '2D Cross-Tab Risk Concentration Heatmap'}}</div>
                                <div class="panel-desc">Intersectional hotspot matrix: ${{escHtml(DASHBOARD_PAYLOAD.prim_dim_name)}} &times; ${{escHtml(DASHBOARD_PAYLOAD.sec_dim_name)}} (click cell to filter).</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-heatmap"></div>
                    `;
                    container.appendChild(card);
                    renderCrossTabHeatmap(card.querySelector('#chart-heatmap'));
                }}
                else if (pId === 'exposure_vs_risk_bubble') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Exposure Volume vs Adverse Risk Bubble Dispersion' : 'Volume Banam Nuksan Dar Bubble Dispersion'}}</div>
                                <div class="panel-desc">Separates high-volume systemic friction from low-volume niche outliers.</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-bubble"></div>
                    `;
                    container.appendChild(card);
                    renderExposureBubbleChart(card.querySelector('#chart-bubble'));
                }}
                else if (pId === 'nonlinear_cliff_step_area') {{
                    const cliffs = DASHBOARD_PAYLOAD.widgets_data.cliffs || [];
                    let selHtml = '';
                    if (cliffs.length >= 2) {{
                        selHtml = `<select class="slicer-select" onchange="onCliffFeatureChange(this.value)">` +
                            cliffs.slice(0, 6).map((c, ci) => `<option value="${{ci}}" ${{ci === currentCliffIdx ? 'selected' : ''}}>${{escHtml(c.column)}}</option>`).join('') +
                            `</select>`;
                    }}
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Non-Linear Parameter Threshold Cliff &amp; Danger Zone' : 'Khatre Ki Laal Rekha (Parameter Threshold Cliff)'}}</div>
                                <div class="panel-desc">Empirical quartile discretization exposing acute tipping points.</div>
                            </div>
                            ${{selHtml}}
                        </div>
                        <div class="svg-container" id="chart-cliff"></div>
                    `;
                    container.appendChild(card);
                    renderCliffChart(card.querySelector('#chart-cliff'), currentCliffIdx);
                }}
                else if (pId === 'orthogonal_2x2_quadrant') {{
                    const inter = DASHBOARD_PAYLOAD.widgets_data.interaction || {{}};
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? '2x2 Orthogonal Risk vs Protective Buffer Matrix' : '2x2 Risk Banam Protective Buffer Matrix'}}</div>
                                <div class="panel-desc">${{escHtml(inter.pos_driver || 'Risk')}} vs ${{escHtml(inter.neg_driver || 'Buffer')}} interaction quadrants.</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-quadrant"></div>
                    `;
                    container.appendChild(card);
                    render2x2Quadrant(card.querySelector('#chart-quadrant'));
                }}
                else if (pId === 'triage_efficiency_frontier') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Operational Intake Screening Yield Frontier' : 'Intake Screening Aur Defect Recall Curve'}}</div>
                                <div class="panel-desc">Trade-off curve between intake hold/scrap % and defect containment recall %.</div>
                            </div>
                        </div>
                        <div class="svg-container" id="chart-triage"></div>
                    `;
                    container.appendChild(card);
                    renderTriageYieldChart(card.querySelector('#chart-triage'));
                }}
                else if (pId === 'what_if_counterfactual_simulator') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'What-If Counterfactual ROI &amp; Excess-Risk Simulator' : 'Agar Hum Faisla Badlein Toh Kitna Bachav Hoga (What-If ROI)?'}}</div>
                                <div class="panel-desc">Interactive epidemiological excess-risk compression with 95% confidence bounds &amp; 3-pathway advisory.</div>
                            </div>
                        </div>
                        <div id="sim-container"></div>
                    `;
                    container.appendChild(card);
                    initWhatIfSimulator(card.querySelector('#sim-container'));
                }}
                else if (pId === 'actionable_worklist_explorer') {{
                    card.innerHTML = `
                        <div class="panel-header">
                            <div>
                                <div class="panel-title">${{currentLang === 'en' ? 'Actionable Priority Worklist &amp; Incident Triage' : 'Aaj Subah Team Ke Liye Actionable Priority List'}}</div>
                                <div class="panel-desc">Two-Queue row-level prioritization for preventive retention and realized loss recovery.</div>
                            </div>
                        </div>
                        <div id="worklist-container"></div>
                    `;
                    container.appendChild(card);
                    initWorklistExplorer(card.querySelector('#worklist-container'));
                }}
            }});
        }}

        // Window onload
        window.addEventListener('DOMContentLoaded', () => {{
            bindDelegatedPanelEvents();
            initSlicers();
            renderAllCharts();
            renderGovernanceDrawer();
        }});
    </script>
</body>
</html>
"""
    return html_template


# -----------------------------------------------------------------------------
# 7. MASTER STAGE 7 ENTRY POINT
# -----------------------------------------------------------------------------
def synthesize_bespoke_dashboard(out_dir: str = "output", use_llm: bool = True) -> Dict[str, Any]:
    """
    Master Stage 7 Entry Point:
    1. Loads bi_ready_fact.parquet, blueprint, and downstream artifacts.
    2. Runs judge_dashboard_architecture() to determine domain archetype, DFII, and panels.
    3. Writes dashboard_design_blueprint.json.
    4. Computes zero-drift client micro-cube and builds DASHBOARD_PAYLOAD.
    5. Compiles 100% self-contained bespoke_executive_dashboard.html (Zero CDNs).
    """
    out = Path(out_dir).resolve()
    print(f"\n[*] [Stage 7 Bespoke Dashboard Architect] Synthesizing executive dashboard in: {out}...")

    # Locate bi_ready_fact.parquet
    candidates = list(out.glob("bi_ready_fact.parquet"))
    if not candidates:
        candidates = [c for c in out.glob("*.parquet") if "enriched" not in c.name]
    if not candidates:
        raise FileNotFoundError(f"No Parquet fact table found in output directory: {out}")
    fact_parquet = candidates[0]

    df_fact = pd.read_parquet(fact_parquet)
    df_fact.attrs["dataset_name"] = out.parent.name
    print(f"[*] Loaded Physical Fact Parquet: {fact_parquet.name} ({len(df_fact):,} rows, {len(df_fact.columns)} cols)")

    # Read blueprint if available
    bp_path = out / "execution_blueprint.json"
    blueprint = None
    if bp_path.exists():
        try:
            with open(bp_path, "r", encoding="utf-8") as f:
                blueprint = json.load(f)
        except Exception:
            blueprint = None

    # Resolve canonical target, cost, and strictly sanitized operational dimensions
    canonical = resolve_canonical_target_and_cost(df_fact, blueprint=blueprint)
    target_col, cost_col, raw_prim_dim, raw_sec_dim = detect_key_columns(df_fact, blueprint=blueprint)
    prim_dim, sec_dim = _sanitize_operational_dimensions(
        df_fact=df_fact,
        target_col=target_col,
        cost_col=cost_col,
        prim_dim=raw_prim_dim,
        sec_dim=raw_sec_dim,
        canonical=canonical,
        blueprint=blueprint
    )

    # Read temporal trend summary if present
    temporal_file = out / "temporal_trend_summary.json"
    temporal_summary = None
    if temporal_file.exists():
        try:
            with open(temporal_file, "r", encoding="utf-8") as tf:
                temporal_summary = json.load(tf)
        except Exception:
            temporal_summary = None

    worklist_file = out / "actionable_priority_worklist.csv"

    strat_engine = StrategicDecisionEngine(df_fact, blueprint=blueprint)

    # 1. Judge Architecture & Generate Design Blueprint
    design_bp = judge_dashboard_architecture(
        df_fact=df_fact,
        target_col=target_col,
        cost_col=cost_col,
        prim_dim=prim_dim,
        sec_dim=sec_dim,
        blueprint=blueprint,
        strat_engine=strat_engine,
        temporal_summary=temporal_summary,
        worklist_path=worklist_file if worklist_file.exists() else None,
        use_llm=use_llm
    )

    bp_out_path = out / "dashboard_design_blueprint.json"
    with open(bp_out_path, "w", encoding="utf-8") as f:
        json.dump(design_bp, f, indent=2)
    print(f"[+] Dashboard Design Blueprint written to: {bp_out_path} (Archetype: {design_bp['archetype_name']}, DFII: {design_bp['dfii_score']})")

    # 2. Build Physical Dashboard Payload
    payload = build_dashboard_payload(
        df_fact=df_fact,
        target_col=target_col,
        cost_col=cost_col,
        prim_dim=prim_dim,
        sec_dim=sec_dim,
        canonical=canonical,
        design_bp=design_bp,
        strat_engine=strat_engine,
        out_dir=out
    )

    # 3. Build Standalone Interactive HTML Application
    html_content = build_bespoke_html(payload, design_bp)
    html_out_path = out / "bespoke_executive_dashboard.html"
    with open(html_out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[+] Bespoke Executive Dashboard HTML rendered to: {html_out_path} ({len(html_content):,} bytes, 0 CDNs)")

    return {
        "status": "SUCCESS",
        "blueprint_path": str(bp_out_path),
        "html_dashboard": str(html_out_path),
        "archetype": design_bp["archetype"],
        "archetype_name": design_bp["archetype_name"],
        "dfii_score": design_bp["dfii_score"],
        "selected_panels": [p["id"] for p in design_bp["selected_panels"]]
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage 7: Bespoke Executive Dashboard Architect")
    parser.add_argument("pos_output", nargs="?", default=None, help="Output directory path (positional)")
    parser.add_argument("--output", dest="flag_output", default=None, help="Output directory path (flag)")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM persona refinement (offline deterministic)")
    args = parser.parse_args()
    out_dir_arg = args.flag_output or args.pos_output or "output"
    synthesize_bespoke_dashboard(out_dir=out_dir_arg, use_llm=(not args.no_llm))
