import re
from typing import Optional, Dict, Any, Tuple, Set
import numpy as np
import pandas as pd

def is_index_artifact(col_name: str, series: Optional[pd.Series] = None) -> bool:
    """
    Detects CSV row index artifacts (e.g. Unnamed: 0, index, level_0, row_id)
    which must never be treated as primary business features, keys, or targets.
    """
    c = str(col_name).strip().lower()
    if re.match(r'^(?:unnamed\s*:?\s*\d*|index|level_\d+|row[\s_]?(?:id|num|number)|_surrogate_id_key)$', c):
        return True
    if series is not None and len(series) > 10:
        # Check monotonic sequence 0, 1, 2, ...
        try:
            s_clean = pd.to_numeric(series.dropna(), errors='coerce')
            if s_clean.notna().mean() > 0.95:
                diffs = s_clean.diff().dropna()
                if (diffs == 1).mean() > 0.95 and s_clean.min() in [0, 1]:
                    if any(k in c for k in ['unnamed', 'index', 'row', 'id']):
                        return True
        except Exception:
            pass
    return False

def is_synthetic_column(col_name: str, blueprint: Optional[Dict[str, Any]] = None) -> bool:
    """
    Identifies stage 3 synthesized feature engineering columns.
    These must not be used as real financial ledgers, primary dimensions, or primary confounders.
    """
    c = str(col_name).strip().lower()
    c_norm = re.sub(r'[\s\-]+', '_', c)
    if blueprint and isinstance(blueprint, dict):
        for f in blueprint.get("forensic_enrichment_columns", []):
            f_name = f.split("=")[0].strip().lower() if "=" in str(f) else str(f).strip().lower()
            if c == f_name or c_norm == re.sub(r'[\s\-]+', '_', f_name):
                return True
    synthetic_suffixes = (
        '_velocity', '_ratio', '_diff', '_log', '_scaled', '_pct', '_tier',
        '_bin', '_bucket', '_norm', '_normed', '_sq', '_zscore', '_score_',
        '_score', '_flag', '_surrogate', '_index', '_impurity', '_is_target', '_penalty',
        '_penalty_index', '_spend_velocity', '_risk_index', '_friction_index'
    )
    if any(c_norm.endswith(s) for s in synthetic_suffixes):
        return True
    if any(k in c_norm for k in [
        'friction_penalty', 'market_friction', 'service_friction',
        'penalty_index', 'spend_velocity', 'penalty_score', 'composite_risk', 'synthetic_'
    ]):
        return True
    if c_norm.startswith(('fact_', '_', 'surrogate_')):
        return True
    return False


def is_demographic_attribute(col_name: str) -> bool:
    """
    Detects protected/demographic attributes across English, Portuguese, Spanish, French, and German
    (e.g., Sex, Gender, Genero, Race, Ethnicity, Marital Status, Religion, Nationality)
    so operational business dimensions are prioritized over protected personal attributes.
    """
    c = str(col_name).strip().lower()
    c_norm = re.sub(r'[\s\-]+', '_', c)
    exact_demo = {
        'sex', 'gender', 'genero', 'género', 'gênero', 'sexe', 'geschlecht', 'sesso',
        'race', 'ethnicity', 'marital_status', 'maritalstatus', 'estado_civil', 'estadocivil',
        'casado', 'married', 'partner', 'dependentes', 'dependents',
        'religion', 'nationality', 'age_group', 'seniorcitizen', 'aposentado'
    }
    if c in exact_demo or c_norm in exact_demo:
        return True
    if re.search(r'\b(?:sex|gender|genero|género|gênero|race|ethnicity|marital_status|estado_civil|religion|nationality)\b', c_norm):
        return True
    return False

def is_pseudo_numeric_identifier(col_name: str, series: Optional[pd.Series] = None) -> bool:
    """
    Detects nominal identifiers stored as numbers (e.g., Room Number, Postal Code,
    Zip Code, Phone Number, Account Number, Serial Number, ID/Code suffixes).
    Such columns have no ordinal/cardinal physical meaning and must never be
    sliced into quantile threshold cliffs or operational triage rules.
    """
    if is_index_artifact(col_name, series):
        return True
    c = str(col_name).strip().lower()
    # Explicit nominal number patterns
    nominal_patterns = (
        r'(?:\broom[\s_]*(?:number|num|no|id)\b|'
        r'\b(?:zip|postal)[\s_]*(?:code)?\b|'
        r'\b(?:phone|mobile|tel|ssn|sin|pin|fips|serial|routing|iban)[\s_]*(?:number|num|no|code|id)?\b|'
        r'\b(?:account|card|flight|ticket|invoice|order|customer|patient|doctor|hospital|employee|store|branch|emp|dept|merchant|vendor|product|item|station|ward|bed)[\s_]*(?:number|num|no|id|code|key)\b)'
    )
    if re.search(nominal_patterns, c):
        return True
    # Suffixes that denote nominal identifiers rather than cardinal quantities
    if c.endswith(('_id', ' id', '_key', ' key', '_uuid', ' uuid', '_code', ' code', ' number', '_number')):
        if not c.startswith(('number_of', 'number of', 'num_of', 'total_', 'count_')):
            return True
    return False

def resolve_currency_metadata(
    df: pd.DataFrame,
    cost_col: Optional[str] = None,
    region_profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detects authentic currency code, unit symbol, and formatting scale across
    US (USD $), UK (GBP £), EU (EUR €), and India (INR ₹) datasets.
    """
    if not cost_col or cost_col not in df.columns:
        return {
            "currency_code": None,
            "unit_symbol": "events",
            "numbering_system": "western",
            "is_financial": False
        }

    # Inspect all column headers for explicit currency clues
    all_col_text = " ".join([str(c).lower() for c in df.columns])
    cost_col_low = str(cost_col).lower()

    # 1. Check UK indicators
    is_uk = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['gbp', '£', 'pound', 'pence', 'sterling'])
    # 2. Check India indicators
    is_in = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['inr', '₹', 'rs', 'rupee', 'rupees', 'lakh', 'crore', 'gst', 'mrp', 'tally'])
    # 3. Check Euro indicators
    is_eu = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['eur', '€', 'euro'])
    # 4. Check USD indicators
    is_us = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['usd', '$', 'dollar', 'cents'])

    reg_norm = str(region_profile).strip().upper() if region_profile else None

    if is_in or reg_norm in ("IN", "INDIA"):
        currency_code = "INR"
        unit_symbol = "₹"
        numbering_system = "indian"
    elif is_uk or reg_norm in ("UK", "GB", "GREAT_BRITAIN"):
        currency_code = "GBP"
        unit_symbol = "£"
        numbering_system = "western"
    elif is_eu or reg_norm in ("EU", "EUROPE"):
        currency_code = "EUR"
        unit_symbol = "€"
        numbering_system = "western"
    else:
        # Default financial currency is USD ($)
        currency_code = "USD"
        unit_symbol = "$"
        numbering_system = "western"

    return {
        "currency_code": currency_code,
        "unit_symbol": unit_symbol,
        "numbering_system": numbering_system,
        "is_financial": True
    }


def format_currency_value(
    amount: float,
    currency_code: str = "USD",
    numbering_system: str = "western",
    include_symbol: bool = True
) -> str:
    """
    Formats monetary values according to regional accounting standards:
    - Western: $117.70K, $4.29B, £65.00K
    - Indian: ₹9.85 Lakh, ₹1.42 Cr, ₹25.50K
    """
    if pd.isna(amount) or np.isneginf(amount) or np.isposinf(amount):
        return "N/A"

    symbol_map = {"USD": "$", "GBP": "£", "EUR": "€", "INR": "₹"}
    sym = symbol_map.get(str(currency_code).upper(), "$") if include_symbol else ""

    val = float(amount)
    abs_val = abs(val)
    sign = "-" if val < 0 else ""

    if numbering_system == "indian":
        if abs_val >= 10000000:
            return f"{sign}{sym}{abs_val / 10000000:.2f} Cr"
        elif abs_val >= 100000:
            return f"{sign}{sym}{abs_val / 100000:.2f} Lakh"
        elif abs_val >= 1000:
            return f"{sign}{sym}{abs_val / 1000:.2f}K"
        else:
            return f"{sign}{sym}{abs_val:,.2f}"
    else:
        if abs_val >= 1000000000:
            return f"{sign}{sym}{abs_val / 1000000000:.2f}B"
        elif abs_val >= 1000000:
            return f"{sign}{sym}{abs_val / 1000000:.2f}M"
        elif abs_val >= 1000:
            return f"{sign}{sym}{abs_val / 1000:.2f}K"
        else:
            return f"{sign}{sym}{abs_val:,.2f}"


def resolve_canonical_target_and_cost(
    df: pd.DataFrame,
    blueprint: Optional[Dict[str, Any]] = None,
    raw_source_cols: Optional[Set[str]] = None,
    region_profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Single Canonical Ground-Truth Resolver for Target Outcome and Financial Exposure.
    Guarantees that Stage 5, Decision Matrix, and Micro-Forensic Engine share
    the exact same binary classification target and physical monetary column.
    """
    cols = list(df.columns)
    target_col = None
    cost_col = None
    
    # -------------------------------------------------------------
    # 1. Target Column Identification
    # -------------------------------------------------------------
    # 1.2 Target Keywords search if blueprint candidate absent or invalid
    target_keywords = [
        'claim_status', 'claim', 'death', 'mortality', 'satisfaction', 'dissatisfied', 'exited', 'stroke',
        'readmit', 'attrition', 'churn', 'fraud', 'default', 'reach', 'ontime',
        'on_time', 'time_y', 'y_n', 'cancel', 'error', 'late', 'delay', 'smoker',
        'risk', 'outcome', 'status', 'target', 'label', 'class', 'quality',
        'grade', 'rating', 'score', 'test results', 'test_results', 'test result',
        'admission type', 'admission_type', 'diagnosis', 'abnormal', 'emergency'
    ]

    # 1.1 Check Blueprint hint first (excluding artifacts, URLs, free text, or pure monetary ledgers when discrete target exists)
    if blueprint and blueprint.get("target_metric") in cols:
        bp_cand = blueprint.get("target_metric")
        c_low = bp_cand.lower()
        is_bad_bp = any(b in c_low for b in ['link', 'url', 'poster', 'image', 'photo', 'overview', 'description', 'desc', 'summary', 'path', 'href', 'title'])
        is_artifact = is_index_artifact(bp_cand)
        is_monetary = any(k in c_low for k in ['amount', 'price', 'cost', 'revenue', 'sales', 'billing', 'charge', 'balance', 'salary', 'income']) and pd.api.types.is_numeric_dtype(df[bp_cand]) and df[bp_cand].nunique() > 50
        has_discrete_targets = any(
            any(k in c.lower() for k in target_keywords) and (df[c].nunique() <= 10) and not c.lower().endswith(('_id', '_key', '_code', '_num')) and not is_index_artifact(c)
            for c in cols
        )
        if not is_bad_bp and not is_artifact and not (is_monetary and has_discrete_targets):
            target_col = bp_cand
    if not target_col:
        target_candidates = []
        for c in cols:
            if is_index_artifact(c):
                continue
            c_low = c.lower()
            is_rating_scale = any(k in c_low for k in ['rating', 'quality', 'score', 'grade']) and pd.api.types.is_numeric_dtype(df[c]) and (df[c].nunique() <= 100 or (df[c].min() >= 0 and df[c].max() <= 10.5))
            if any(k in c_low for k in target_keywords) and (df[c].nunique() <= 10 or is_rating_scale) and not c_low.endswith(('_id', '_key', '_code', '_num')):
                if c_low == 'class' and any(val in ['eco', 'business', 'first'] for val in df[c].astype(str).str.lower().unique()):
                    continue
                target_candidates.append(c)
        
        priority_targets = [
            'claim_status', 'claim', 'death', 'mortality', 'churn', 'fraud', 'default', 'stroke', 'attrition',
            'readmit', 'satisfaction', 'exited', 'cancel', 'smoker', 'fail', 'delay',
            'late', 'risk', 'quality', 'grade', 'rating', 'test results', 'test_results', 'test result', 'abnormal', 'emergency'
        ]
        target_candidates.sort(key=lambda col: next((i for i, pt in enumerate(priority_targets) if pt in col.lower()), 999))
        if target_candidates:
            target_col = target_candidates[0]

    # 1.3 Binary fallback
    if not target_col:
        strictly_binary = [
            c for c in cols
            if not is_index_artifact(c)
            and not is_demographic_attribute(c)
            and not c.lower().endswith(('_id', '_key', '_code', '_num'))
            and df[c].nunique() == 2
        ]
        yes_no_cols = [
            c for c in strictly_binary
            if any(str(val).strip().lower() in ['yes', 'y', '1', 'true', 't', 'sim', 'si'] for val in df[c].dropna().unique())
            and not is_demographic_attribute(c)
        ]
        if yes_no_cols:
            target_col = yes_no_cols[0]
        elif strictly_binary:
            target_col = strictly_binary[0]

    # Fallback to last column if still none
    if not target_col:
        valid_cols = [c for c in cols if not is_index_artifact(c) and not is_demographic_attribute(c) and not c.lower().endswith(('_id', '_key'))]
        target_col = valid_cols[-1] if valid_cols else cols[-1]

    # -------------------------------------------------------------
    # 2. Canonical Binary Target Mapping (_is_target_event: 1 = adverse, 0 = normal)
    # -------------------------------------------------------------
    s_raw = df[target_col]
    is_num = pd.api.types.is_numeric_dtype(s_raw)
    target_desc = f"{target_col} Adverse Breach"

    # Define unambiguous adverse tokens
    unconditional_adverse = (
        r'\b(?:bad|default|defaulted|charged_off|delinquent|fraud|fraudulent|'
        r'churn|churned|attrition|attrited|defect|defective|fail|failed|failure|'
        r'cancel|cancelled|canceled|delayed|delay|late|anomaly|substandard|poor|'
        r'low_quality|malignant|dead|death|deceased|fatal|disease|stroke|diabetic|'
        r'return|returned|rto|undelivered|rejected|lost|disputed|'
        r'unacceptable|dissatisfied|exited|abnormal|emergency)\b'
    )
    # Conditional adverse tokens (only adverse if target column denotes risk/failure/default)
    conditional_adverse = r'\b(?:1|yes|y|true|t|sim|si|ja|oui|high|high_risk|severe|critical|positive|pos)\b'
    col_denotes_adverse = any(k in target_col.lower() for k in [
        'risk', 'default', 'churn', 'fraud', 'defect', 'fail', 'bad', 'loss', 'delay',
        'late', 'cancel', 'disease', 'stroke', 'death', 'mortality', 'complication',
        'attrition', 'anomaly', 'claim', 'target', 'label', 'class', 'outcome', 'status',
        'test results', 'test_results', 'admission'
    ])

    if not is_num:
        s_str = s_raw.astype(str).str.lower().str.strip()
        is_adv = s_str.str.contains(unconditional_adverse, regex=True)
        # Exclude sentinel missing value tokens from being considered genuine adverse or non-adverse categories
        known_missing = {'unknown', 'none', 'null', 'nan', '', 'na', 'n/a'}
        clean_mask = ~s_str.isin(known_missing)
        clean_unique = [v for v in s_str.unique() if v not in known_missing]

        if is_adv.sum() > 0:
            binary_target = is_adv.astype(int)
            target_desc = f"{target_col} Adverse State"
        elif col_denotes_adverse:
            is_cond = s_str.str.contains(conditional_adverse, regex=True) & clean_mask
            if is_cond.sum() > 0:
                binary_target = is_cond.astype(int)
                adv_name = s_raw[is_cond].iloc[0] if is_cond.sum() > 0 else 'Positive'
                target_desc = f"{target_col} == {adv_name}"
            elif len(clean_unique) == 2:
                # Minority class as adverse among clean records
                min_val = s_raw[clean_mask].value_counts().index[-1]
                binary_target = ((s_raw == min_val) & clean_mask).astype(int)
                target_desc = f"{target_col} == {min_val}"
            else:
                binary_target = pd.Series(0, index=df.index)
        elif len(clean_unique) == 2:
            # Positive column name (e.g. good/bad): look for 'good', 'success', 'pass', '0', 'no'
            is_pos = s_str.str.contains(r'\b(?:good|success|pass|approved|performing|normal|clean)\b', regex=True)
            if is_pos.sum() > 0:
                binary_target = ((~is_pos) & clean_mask).astype(int)
                target_desc = f"{target_col} Non-Good Event"
            else:
                min_val = s_raw[clean_mask].value_counts().index[-1]
                binary_target = ((s_raw == min_val) & clean_mask).astype(int)
                target_desc = f"{target_col} == {min_val}"
        else:
            binary_target = pd.Series(0, index=df.index)
    else:
        s_clean = pd.to_numeric(s_raw, errors='coerce').fillna(0)
        if s_raw.nunique() <= 2 and set(s_clean.unique()).issubset({0, 1, 0.0, 1.0}):
            binary_target = s_clean.astype(int)
            target_desc = f"{target_col} == 1"
        elif any(k in target_col.lower() for k in ['quality', 'score', 'rating', 'grade']):
            # For quality ratings (e.g. 1 to 5, or 1 to 10): lower ratings are adverse
            if s_clean.max() <= 5.5:
                # 5-star scale (e.g. Amazon, app stores, hospitality): adverse is substandard rating
                q25 = float(s_clean.quantile(0.25))
                if q25 < s_clean.max() and q25 >= s_clean.min() and (s_clean <= q25).mean() <= 0.45:
                    thresh = q25
                elif (s_clean <= 3.8).sum() > 0:
                    thresh = 3.8
                else:
                    thresh = 3.5
            elif s_clean.max() <= 10.5:
                # 10-point scale: adverse is <= 5.0 (or bottom quartile if lower)
                q25 = float(s_clean.quantile(0.25))
                if q25 < 5.0 and q25 >= s_clean.min():
                    thresh = q25
                elif s_clean.min() >= 5.0:
                    thresh = q25
                else:
                    thresh = 5.0
            else:
                thresh = float(s_clean.quantile(0.25)) if s_clean.quantile(0.25) > 0 else float(s_clean.median())
            
            # Ensure thresh never captures 100% or 0% of records if variation exists
            if (s_clean <= thresh).sum() == len(s_clean) and s_clean.nunique() > 1:
                thresh = float(s_clean.quantile(0.25))
                if (s_clean <= thresh).sum() == len(s_clean):
                    thresh = float(s_clean.min())
            binary_target = (s_clean <= thresh).astype(int)
            target_desc = f"{target_col} <= {thresh:.2f}"
        elif any(k in target_col.lower() for k in ['stream', 'streams', 'sales', 'revenue', 'view', 'views', 'profit', 'yield', 'conversion']):
            # For volume/yield metrics: bottom quartile is adverse underperformance
            thresh = float(s_clean.quantile(0.25)) if s_clean.quantile(0.25) > 0 else float(s_clean.median())
            binary_target = (s_clean <= thresh).astype(int)
            target_desc = f"{target_col} <= {thresh:.2f}"
        else:
            # Default continuous target: if name denotes adverse, upper median is bad; else lower quartile is bad
            if col_denotes_adverse:
                thresh = float(s_clean.median())
                binary_target = (s_clean > thresh).astype(int)
                target_desc = f"{target_col} > {thresh:.2f}"
            else:
                thresh = float(s_clean.quantile(0.25))
                binary_target = (s_clean <= thresh).astype(int)
                target_desc = f"{target_col} <= {thresh:.2f}"

    # -------------------------------------------------------------
    # 3. Canonical Physical Financial / Cost Column Detection
    # -------------------------------------------------------------
    # Strict financial keywords representing physical currency ledgers
    cost_keywords = [
        'loan_amount', 'loanamount', 'credit_amount', 'amount', 'credit', 'price', 'cost', 'revenue', 'mrr', 'sales', 'balance',
        'loss', 'claim', 'charge', 'charges', 'billing_amount', 'billing', 'salary', 'income', 'expense', 'payment', 'fee',
        'valormensal', 'totalgasto', 'valor', 'gasto', 'fatura'
    ]
    # Synthetic / non-financial terms to explicitly exclude
    excluded_cost_terms = [
        'penalty', 'friction', 'weighted', 'index', 'score', 'ratio', 'scaled',
        'rate', 'pct', 'percent', 'rank', 'density', 'satisfaction', 'rating', 'level',
        'hours', 'work_life', 'worklife', 'distance', 'age'
    ]
    time_units = ['year', 'years', 'month', 'months', 'day', 'days', 'date']

    candidate_cost_cols = []
    for c in cols:
        if c == target_col or is_index_artifact(c) or is_synthetic_column(c, blueprint):
            continue
        c_low = c.lower()
        if any(x in c_low for x in excluded_cost_terms):
            continue
        # Exclude count metrics (preserving 'discount')
        if bool(re.search(r'(?<!dis)count', c_low)):
            continue
        has_anchored_arr = bool(re.search(r'(?:^|_|annual|monthly|account|net|gross|total)arr(?:$|_)', c_low))
        # Exclude pure ID/key/code suffix unless column explicitly contains money words
        money_words = ['amount', 'price', 'cost', 'revenue', 'mrr', 'sales', 'billing', 'charge', 'salary', 'income', 'expense', 'fee', 'payment', 'credit', 'balance', 'claim', 'valormensal', 'totalgasto', 'valor', 'gasto', 'fatura']
        if any(c_low.endswith(('_' + sfx, sfx)) for sfx in ['id', 'key', 'code', 'number']) and not (any(m in c_low for m in money_words) or has_anchored_arr):
            continue
        # Exclude pure date/time columns that end with time units unless they contain explicit money words
        if any(c_low == t or c_low.endswith(('_' + t, ' ' + t)) for t in time_units) and not (any(m in c_low for m in money_words) or has_anchored_arr):
            continue
        if (any(k in c_low for k in cost_keywords) or has_anchored_arr) and pd.api.types.is_numeric_dtype(df[c]):
            # If raw_source_cols provided, ensure it was an authentic raw column or a clean numeric parse of one
            if raw_source_cols:
                raw_low = {r.lower() for r in raw_source_cols}
                base_c = c_low.replace('_num', '').replace('_clean', '').replace('_parsed', '').replace('_val', '')
                if c not in raw_source_cols and base_c not in raw_low:
                    continue
            s_c = pd.to_numeric(df[c], errors='coerce').fillna(0)
            if (s_c > 0).mean() > 0.85 and s_c.sum() > 0:
                candidate_cost_cols.append(c)

    if candidate_cost_cols:
        priority_cost = [
            'loan_amount', 'loanamount', 'credit_amount', 'revenue', 'mrr', 'arr', 'sales', 'billing_amount', 'billing', 'valormensal', 'totalgasto', 'salary', 'income',
            'amount', 'credit', 'price', 'cost', 'expense', 'claim', 'charges', 'balance', 'payment', 'fee', 'valor', 'gasto', 'fatura'
        ]
        candidate_cost_cols.sort(key=lambda col: next((i for i, pc in enumerate(priority_cost) if pc in col.lower()), 999))
        cost_col = candidate_cost_cols[0]

    is_financial = (cost_col is not None)
    curr_meta = resolve_currency_metadata(df, cost_col, region_profile)
    unit_symbol = curr_meta["unit_symbol"]

    return {
        "target_col": target_col,
        "binary_target": binary_target,
        "target_desc": target_desc,
        "cost_col": cost_col,
        "is_financial": is_financial,
        "unit_symbol": unit_symbol,
        "currency_code": curr_meta["currency_code"],
        "numbering_system": curr_meta["numbering_system"]
    }
