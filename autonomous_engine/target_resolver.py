import re
from typing import Optional, Dict, Any, Tuple, Set, List
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


def is_categorical_or_string_series(series: pd.Series) -> bool:
    """
    Compatible across Pandas 1.x, 2.x, and 3.0+ (where string columns have 'str' / StringDtype
    instead of legacy 'object' dtype).
    """
    if series is None:
        return False
    dt_str = str(series.dtype).lower()
    if dt_str == 'category' or dt_str == 'object' or dt_str.startswith('str'):
        return True
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        return True
    return False


def is_deterministic_target_leakage(
    col_name: str,
    series: pd.Series,
    binary_target: Optional[pd.Series],
    target_col: Optional[str] = None
) -> bool:
    """
    Detects tautological post-event target sub-mode flags (e.g., HDF, OSF, PWF, TWF in AI4I
    where HDF=1 deterministically implies Machine failure=1 with 100.0% certainty, or RNF
    random failure flags) that represent decompositions of the target event itself rather than
    pre-event operational dimensions or continuous physical predictors.
    """
    if series is None or binary_target is None:
        return False
    if target_col and str(col_name).strip().lower() == str(target_col).strip().lower():
        return True
    c_low = str(col_name).strip().lower()
    t_low = str(target_col).strip().lower() if target_col else ""

    # Explicit post-event status/date columns when target is an event outcome
    if any(k in c_low for k in ['reservation_status', 'cancellation_date', 'cancellation_status', 'exit_date', 'order_status', 'delivery_status']):
        return True

    # Post-event customer feedback / reverse-logistics / penalty consequences when target is operational failure/RTO/cancel/churn/status
    if any(k in t_low for k in ['rto', 'cancel', 'churn', 'default', 'fail', 'attrition', 'fraud', 'breach', 'status', 'outcome']):
        if not any(k in t_low for k in ['csat', 'rating', 'score', 'satisfaction', 'review']):
            if any(k in c_low for k in ['csat', 'review_score', 'feedback_score', 'satisfaction_rating', 'customer_rating']):
                return True
        if not any(k in t_low for k in ['margin', 'profit', 'shipping', 'refund', 'penalty']):
            if any(k in c_low for k in [
                'reverse_shipping', 'return_shipping', 'refund_amount', 'net_contribution_margin', 'realized_margin',
                'sla_penalty', 'penalty_inr', 'penalty_usd', 'penalty_amount', 'late_fee', 'demurrage',
                'chargeback_amount', 'damage_cost', 'spoilage_cost', 'writeoff_amount', 'write_off', 'claim_payout', 'compensation_amount'
            ]):
                return True

    # Post-event / backward-causality temporal leakage when target is departure delay
    if any(k in t_low for k in ['dep_delay', 'delay']):
        if c_low in ('arr_delay', 'avgdelay', 'dep_time', 'arr_time', 'air_time') or (
            any(k in c_low for k in ['arr_delay', 'avgdelay', 'air_time']) and 'sched' not in c_low
        ):
            return True

    # Post-call duration leakage when target is telemarketing conversion outcome
    if t_low in ('y', 'deposit', 'subscribed', 'response') and c_low == 'duration':
        return True

    # Post-payment meter tip leakage when target is payment method (credit card meters never log cash tips)
    if t_low in ('payment', 'payment_type') and c_low in ('tip', 'tips'):
        return True

    # Post-rating derived display labels / color bands (e.g. Zomato 'Rating text' / 'Rating color' for 'Aggregate rating')
    if any(k in t_low for k in ['rating', 'score', 'grade']):
        if any(k in c_low for k in ['rating', 'score', 'grade']) and any(
            k in c_low for k in ['text', 'color', 'colour', 'label', 'band', 'tier', 'category', 'bucket']
        ):
            return True

    if len(series) < 50:
        return False

    # 1. Check categorical / string leakage (e.g. reservation_status where Canceled/Check-Out perfectly encodes target)
    if is_categorical_or_string_series(series):
        if series.nunique() <= 30:
            try:
                grp = binary_target.groupby(series)
                counts = grp.count()
                means = grp.mean()
                valid_cats = counts[counts >= 10].index
                if len(valid_cats) >= 2:
                    if all(means[c] >= 0.995 or means[c] <= 0.005 for c in valid_cats):
                        return True
            except Exception:
                pass
        return False

    # Check numeric columns for deterministic zero-vs-positive accounting leakage (e.g. P(Target=1 | X > 0) == 0.0 or 1.0)
    s_num = pd.to_numeric(series, errors='coerce')
    if s_num.notna().mean() < 0.98:
        return False
    pos_gt_zero = (s_num > 0)
    zero_eq = (s_num == 0)
    if int(pos_gt_zero.sum()) >= 50 and int(zero_eq.sum()) >= 50 and int(binary_target.sum()) >= 20:
        p_given_pos = float(binary_target.loc[pos_gt_zero].mean())
        if p_given_pos == 0.0 or p_given_pos == 1.0:
            return True

    # Check binary 0/1 indicator columns
    u_vals = set(s_num.dropna().unique())
    if not u_vals.issubset({0, 1, 0.0, 1.0}) or len(u_vals) != 2:
        return False

    # 1. Explicit industrial failure-mode acronym indicators when target is a failure outcome
    if target_col and any(k in str(target_col).lower() for k in ['failure', 'defect', 'fault', 'breach']):
        if re.match(r'^(?:twf|hdf|pwf|osf|rnf)$', c_low):
            return True

    # 2. Empirical tautological implication check:
    # If Flag == 1 occurs >= 10 times AND P(Target == 1 | Flag == 1) >= 0.995 (near-100% deterministic subset of target)
    pos_mask = (s_num == 1)
    n_pos = int(pos_mask.sum())
    total_target = int(binary_target.sum())
    if n_pos >= 10 and total_target > 0 and n_pos <= total_target:
        cond_prob = float(binary_target.loc[pos_mask].mean())
        if cond_prob >= 0.995:
            return True

    # Also check inverse coding where Flag == 0 is a deterministic subset of Target == 1
    zero_mask = (s_num == 0)
    n_zero = int(zero_mask.sum())
    if n_zero >= 10 and total_target > 0 and n_zero <= total_target:
        cond_prob_zero = float(binary_target.loc[zero_mask].mean())
        if cond_prob_zero >= 0.995:
            return True

    return False

def resolve_currency_metadata(
    df: pd.DataFrame,
    cost_col: Optional[str] = None,
    region_profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detects authentic currency code, unit symbol, formatting scale, and multi-currency
    mixing hazards across US (USD $), UK (GBP £), EU (EUR €), and India (INR ₹) datasets.
    """
    if not cost_col or cost_col not in df.columns:
        return {
            "currency_code": None,
            "unit_symbol": "events",
            "numbering_system": "western",
            "is_financial": False,
            "is_multi_currency": False,
            "currency_col": None,
            "detected_currencies": [],
            "currency_breakdown": {},
        }

    # 0. Multi-Currency Column Audit (Defends CFOs against silent 1:1 USD + INR mixing)
    KNOWN_ISO_CURRENCIES = {"INR", "USD", "EUR", "GBP", "AED", "SGD", "CAD", "AUD", "JPY", "CHF"}
    SYMBOL_MAP = {
        "INR": ("₹", "indian"),
        "USD": ("$", "western"),
        "EUR": ("€", "western"),
        "GBP": ("£", "western"),
        "AED": ("AED ", "western"),
        "SGD": ("S$", "western"),
        "CAD": ("C$", "western"),
        "AUD": ("A$", "western"),
        "JPY": ("¥", "western"),
        "CHF": ("CHF ", "western"),
    }
    is_multi_currency = False
    currency_col = None
    detected_currencies: List[str] = []
    currency_breakdown: Dict[str, Dict[str, Any]] = {}
    dominant_col_currency: Optional[str] = None

    for c in df.columns:
        cl = str(c).strip().lower()
        if any(tok in cl for tok in ("currency", "curr_code", "billing_curr", "fx_code")) and not pd.api.types.is_numeric_dtype(df[c]):
            vals = df[c].dropna().astype(str).str.strip().str.upper()
            vc = vals[vals.isin(KNOWN_ISO_CURRENCIES)].value_counts()
            if len(vc) >= 1 and int(vc.sum()) >= max(5, int(len(df) * 0.25)):
                currency_col = c
                dominant_col_currency = str(vc.index[0])
                detected_currencies = [str(k) for k in vc.index.tolist()]
                cost_num = pd.to_numeric(df[cost_col], errors="coerce").fillna(0.0)
                for code_k, cnt_v in vc.items():
                    mask_k = (df[c].astype(str).str.strip().str.upper() == code_k)
                    sym_k = SYMBOL_MAP.get(str(code_k), ("", "western"))[0]
                    currency_breakdown[str(code_k)] = {
                        "count": int(cnt_v),
                        "share_pct": round(100.0 * int(cnt_v) / max(len(df), 1), 2),
                        "total_volume": round(float(cost_num.loc[mask_k].sum()), 2),
                        "symbol": sym_k,
                    }
                if len(vc) >= 2 and int(vc.iloc[1]) >= max(5, int(len(df) * 0.005)):
                    is_multi_currency = True
                break

    # Inspect all column headers for explicit currency clues
    all_col_text = " ".join([str(c).lower() for c in df.columns])
    cost_col_low = str(cost_col).lower()

    # Inspect actual cell data for explicit currency symbols and regional entities
    # Skip free-text person/name/note columns so surnames like "Nguyen" never trigger 'yen'!
    _skip_sample_tokens = (
        "surname", "last_name", "first_name", "customer_name", "full_name",
        "emp_name", "patient_name", "email", "phone", "comment", "note", "review_text",
    )
    cell_sample_text = ""
    for col in [cost_col] + [c for c in df.columns if c != cost_col]:
        if col in df.columns:
            c_low_i = str(col).lower()
            if col != cost_col and (c_low_i == "name" or any(tok in c_low_i for tok in _skip_sample_tokens)):
                continue
            non_null_strs = df[col].dropna().astype(str).head(80)
            cell_sample_text += " " + " ".join(non_null_strs.str.lower())
            if len(cell_sample_text) > 4000:
                break

    # 1. Check UK indicators
    is_uk = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['gbp', '£', 'pound', 'pence', 'sterling'])
    is_uk = is_uk or any(k in cell_sample_text for k in ['£', ' gbp ', 'pound', 'pence'])
    if not is_uk and 'united kingdom' in cell_sample_text:
        if not any(k in cell_sample_text for k in ['$', '€', '₹', ' usd ', ' eur ', ' inr ']):
            is_uk = True

    # 2. Check India indicators (including Devanagari Hindi currency column/value clues)
    is_in = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['inr', '₹', 'rs', 'rupee', 'rupees', 'lakh', 'crore', 'gst', 'mrp', 'tally', 'रुपये', 'रुपए', 'रकम', 'राशि'])
    is_in = is_in or any(k in cell_sample_text for k in ['₹', 'â‚¹', 'rs.', ' rs ', 'inr', 'rupee', 'rupees', 'lakh', 'crore', 'रुपये', 'रुपए', 'दिल्ली', 'मुंबई', 'जयपुर'])
    indian_entities = ['uttar pradesh', ' delhi', 'maharashtra', ' bihar', 'haryana', 'punjab', 'karnataka', 'gujarat', 'tamil nadu', 'delhivery', 'ekart', 'shiprocket', 'xpressbees', ' dtdc', 'bluedart', 'shadowfax', 'cash on delivery']
    if not is_in and any(k in cell_sample_text for k in indian_entities):
        if not any(k in cell_sample_text for k in ['$', '€', '£', ' usd ', ' eur ', ' gbp ']):
            is_in = True

    # 3. Check Euro indicators
    is_eu = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['eur', '€', 'euro'])
    is_eu = is_eu or any(k in cell_sample_text for k in ['€', ' eur ', 'euro'])

    # 3.5 Check Japanese Yen / Global Asian & Regional Currency indicators
    is_jp = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['jpy', '¥', '￥', 'yen', '円'])
    is_jp = is_jp or bool(re.search(r'(?:¥|￥|円|\bjpy\b|\byen\b)', cell_sample_text))
    is_kr = any(k in cost_col_low or f"_{k}" in all_col_text for k in ['krw', '₩', 'won']) or ('₩' in cell_sample_text)
    is_br = any(k in cost_col_low or f"_{k}" in all_col_text for k in ['brl', 'r$']) or ('r$' in cell_sample_text)
    is_ae = any(k in cost_col_low or f"_{k}" in all_col_text for k in ['aed', 'dirham'])
    is_ch = any(k in cost_col_low or f"_{k}" in all_col_text for k in ['chf'])

    # 4. Check USD indicators
    is_us = any(k in cost_col_low or f"_{k}" in all_col_text or f"({k})" in all_col_text for k in ['usd', '$', 'dollar', 'cents'])
    is_us = is_us or any(k in cell_sample_text for k in ['$', ' usd ', 'dollar'])

    reg_norm = str(region_profile).strip().upper() if region_profile else None

    if dominant_col_currency and dominant_col_currency in SYMBOL_MAP:
        currency_code = dominant_col_currency
        unit_symbol, numbering_system = SYMBOL_MAP[dominant_col_currency]
    elif is_in or reg_norm in ("IN", "INDIA"):
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
    elif is_jp or reg_norm in ("JP", "JAPAN"):
        currency_code = "JPY"
        unit_symbol = "¥"
        numbering_system = "western"
    elif is_kr or reg_norm in ("KR", "KOREA"):
        currency_code = "KRW"
        unit_symbol = "₩"
        numbering_system = "western"
    elif is_br or reg_norm in ("BR", "BRAZIL"):
        currency_code = "BRL"
        unit_symbol = "R$"
        numbering_system = "western"
    elif is_ae or reg_norm in ("AE", "UAE"):
        currency_code = "AED"
        unit_symbol = "AED "
        numbering_system = "western"
    elif is_ch or reg_norm in ("CH", "SWITZERLAND"):
        currency_code = "CHF"
        unit_symbol = "CHF "
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
        "is_financial": True,
        "is_multi_currency": is_multi_currency,
        "currency_col": currency_col,
        "detected_currencies": detected_currencies,
        "currency_breakdown": currency_breakdown,
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


_CANONICAL_TARGET_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
_SHARED_TELEMETRY_STORE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def get_shared_telemetry(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns a shared per-DataFrame telemetry dictionary (storing pre-computed
    Chi-Square p-values and numeric series across Stage 5 engines) without
    attaching non-JSON-serializable pd.Series objects to `df.attrs`.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"rows": 0, "chi2_map": {}, "num_series": {}}
    key = (id(df), len(df), tuple(df.columns))
    if key not in _SHARED_TELEMETRY_STORE:
        if len(_SHARED_TELEMETRY_STORE) > 8:
            _SHARED_TELEMETRY_STORE.clear()
        _SHARED_TELEMETRY_STORE[key] = {"rows": len(df), "chi2_map": {}, "num_series": {}}
    return _SHARED_TELEMETRY_STORE[key]


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
    Uses unified telemetry caching across Stage 5 engines to eliminate redundant scans.
    """
    cols = list(df.columns)
    cache_key = (
        id(df),
        len(df),
        tuple(cols),
        str(blueprint.get("target_override")) if isinstance(blueprint, dict) else None,
        str(blueprint.get("cost_override")) if isinstance(blueprint, dict) else None,
        str(blueprint.get("target_variable_candidate")) if isinstance(blueprint, dict) else None,
        str(region_profile or (blueprint.get("region_profile") if isinstance(blueprint, dict) else None)),
        tuple(sorted(raw_source_cols)) if raw_source_cols else None,
    )
    cached = _CANONICAL_TARGET_CACHE.get(cache_key)
    if isinstance(cached, dict) and len(cached.get("binary_target", [])) == len(df):
        return cached

    target_col = None
    cost_col = None
    
    # -------------------------------------------------------------
    # 1. Target Column Identification
    # -------------------------------------------------------------
    # 1.2 Target Keywords search if blueprint candidate absent or invalid
    target_keywords = [
        'not_fully_paid', 'not.fully.paid', 'unpaid', 'charged_off', 'charge_off', 'delinquent', 'writeoff', 'write_off',
        'is_rto', 'rto_flag', 'rto_status',
        'claim_status', 'claim', 'death', 'mortality', 'satisfaction', 'dissatisfied', 'exited', 'stroke',
        'readmit', 'attrition', 'churn', 'fraud', 'default', 'failure', 'fail', 'defect', 'fault', 'reach', 'ontime',
        'on_time', 'time_y', 'y_n', 'cancel', 'is_returned', 'returned', 'refund', 'chargeback', 'error', 'late', 'delay', 'smoker', 'survived', 'survival', 'cut',
        'risk', 'outcome', 'status', 'target', 'label', 'class', 'quality',
        'grade', 'rating', 'score', 'test results', 'test_results', 'test result',
        'admission type', 'admission_type', 'diagnosis', 'abnormal', 'emergency',
        'estado', 'statut', 'stato', 'ergebnis', '状態', '状态', 'الحالة', '상태',
        'स्थिति', 'स्टेटस', 'परिणाम', 'नतीजा'
    ]

    # 1.0 Explicit User Override Gate (from 1-Second Intent Handshake)
    if blueprint and blueprint.get("target_override") in cols:
        target_col = blueprint.get("target_override")

    # 1.1 Check Blueprint hint first (excluding artifacts, URLs, free text, or pure monetary ledgers when discrete target exists)
    if not target_col and blueprint and blueprint.get("target_metric") in cols:
        bp_cand = blueprint.get("target_metric")
        c_low = bp_cand.lower()
        is_bad_bp = any(b in c_low for b in [
            'link', 'url', 'poster', 'image', 'photo', 'overview', 'description', 'desc', 'summary',
            'path', 'href', 'title', 'longitude', 'latitude', 'pickup', 'dropoff', 'datetime', 'timestamp',
            'आईडी', 'क्रमांक'
        ]) or c_low in ['lon', 'lat'] or c_low.endswith(('_id', '_key', '_code')) or (
            not pd.api.types.is_numeric_dtype(df[bp_cand]) and len(df) >= 10 and (df[bp_cand].nunique() / max(len(df), 1)) >= 0.90
        )
        is_artifact = is_index_artifact(bp_cand)
        is_spatial = c_low in ('x', 'y', 'z') and 'x' in [col.lower() for col in cols] and 'y' in [col.lower() for col in cols]
        is_monetary = any(k in c_low for k in ['amount', 'price', 'cost', 'revenue', 'sales', 'billing', 'charge', 'balance', 'salary', 'income', 'fare', 'value']) and pd.api.types.is_numeric_dtype(df[bp_cand]) and df[bp_cand].nunique() > 50
        is_continuous_delay_driver = any(k in c_low for k in ['delay_days', 'transit_days', 'delivery_days', 'dispatch_delay', 'lead_time_days', 'sla_days']) and pd.api.types.is_numeric_dtype(df[bp_cand]) and df[bp_cand].nunique() > 10
        is_demographic = is_demographic_attribute(bp_cand)
        has_discrete_targets = any(
            any(k in c.lower() for k in target_keywords) and (df[c].nunique() <= 10) and not c.lower().endswith(('_id', '_key', '_code', '_num')) and not is_index_artifact(c)
            for c in cols
        )
        if not is_bad_bp and not is_artifact and not is_spatial and not (is_monetary and has_discrete_targets) and not (is_continuous_delay_driver and has_discrete_targets) and not (is_demographic and has_discrete_targets):
            target_col = bp_cand
    if not target_col:
        has_spatial = 'x' in [col.lower() for col in cols] and 'y' in [col.lower() for col in cols]
        if has_spatial:
            canonical_targets = [
                'dep_delay', 'arr_delay', 'delay', 'mpg', 'is_canceled', 'churn', 'death_event', 'survived', 'survival', 'cut', 'outcome',
                'deposit', 'subscribed', 'smoker', 'default', 'fraud', 'customer stratification rating',
                'median_house_value', 'payment', 'target', 'response', 'label'
            ]
        else:
            canonical_targets = [
                'dep_delay', 'arr_delay', 'delay', 'mpg', 'y', 'target', 'response', 'label', 'deposit', 'subscribed', 'is_canceled', 'is_returned', 'churn',
                'death_event', 'smoker', 'survived', 'survival', 'cut', 'outcome', 'default', 'fraud',
                'customer stratification rating', 'median_house_value', 'payment'
            ]
        for cand_name in canonical_targets:
            for c in cols:
                if c.lower() == cand_name and not is_index_artifact(c):
                    s_test = pd.to_numeric(df[c], errors='coerce')
                    if s_test.notna().mean() > 0.90:
                        n_pos = int((s_test == 1).sum()) if set(s_test.dropna().unique()).issubset({0, 1}) else 0
                        if n_pos >= 10:
                            target_col = c
                            break
                        elif cand_name in ['dep_delay', 'arr_delay', 'delay', 'mpg', 'median_house_value']:
                            target_col = c
                            break
                    elif df[c].nunique() == 2 or (c.lower() == 'cut' and df[c].nunique() <= 10):
                        target_col = c
                        break
            if target_col:
                break

    if not target_col:
        target_candidates = []
        for c in cols:
            if is_index_artifact(c):
                continue
            c_low = c.lower()
            c_norm = re.sub(r'[.\-\s]+', '_', c_low)
            is_rating_scale = any(k in c_norm for k in ['rating', 'quality', 'score', 'grade']) and pd.api.types.is_numeric_dtype(df[c]) and (df[c].nunique() <= 100 or (df[c].min() >= 0 and df[c].max() <= 10.5))
            if (any(k in c_low or k in c_norm for k in target_keywords)) and (df[c].nunique() <= 10 or is_rating_scale) and not c_norm.endswith(('_id', '_key', '_code', '_num')):
                if c_low == 'class' and any(val in ['eco', 'business', 'first'] for val in df[c].astype(str).str.lower().unique()):
                    continue
                target_candidates.append(c)
        
        priority_targets = [
            'not_fully_paid', 'unpaid', 'charged_off', 'charge_off', 'delinquent', 'is_rto',
            'claim_status', 'claim', 'death', 'mortality', 'churn', 'fraud', 'default', 'stroke', 'attrition',
            'readmit', 'satisfaction', 'exited', 'cancel', 'order_status', 'delivery_status', 'fulfillment_status', 'payment_status',
            'smoker', 'survived', 'survival', 'cut', 'outcome', 'fail', 'status', 'delay',
            'late', 'risk', 'quality', 'grade', 'rating', 'test results', 'test_results', 'test result', 'abnormal', 'emergency'
        ]
        target_candidates.sort(key=lambda col: next((i for i, pt in enumerate(priority_targets) if pt in col.lower() or pt in re.sub(r'[.\-\s]+', '_', col.lower())), 999))
        if target_candidates:
            target_col = target_candidates[0]

    # 1.3 Binary fallback (avoid input policy/flag columns; prefer rightmost outcome column)
    if not target_col:
        _input_flag_tokens = ('policy', 'approved', 'eligible', 'has_', 'is_active', 'is_member', 'is_vip', 'verified', 'consent', 'opted')
        strictly_binary = [
            c for c in cols
            if not is_index_artifact(c)
            and not is_demographic_attribute(c)
            and not re.sub(r'[.\-\s]+', '_', c.lower()).endswith(('_id', '_key', '_code', '_num'))
            and df[c].nunique() == 2
        ]
        non_policy_binary = [
            c for c in strictly_binary
            if not any(tok in re.sub(r'[.\-\s]+', '_', c.lower()) for tok in _input_flag_tokens)
        ]
        cand_bin = non_policy_binary or strictly_binary
        yes_no_cols = [
            c for c in cand_bin
            if any(str(val).strip().lower() in ['yes', 'y', '1', 'true', 't', 'sim', 'si'] for val in df[c].dropna().unique())
            and not is_demographic_attribute(c)
        ]
        if yes_no_cols:
            target_col = yes_no_cols[-1]
        elif cand_bin:
            target_col = cand_bin[-1]

    # 1.4 Raw ERP Invoice Credit-Note / Negative-Quantity Return Auto-Detector (Tally/SAP/Shopify/UK Retail)
    erp_credit_note_target: Optional[pd.Series] = None
    erp_credit_note_desc: Optional[str] = None
    if not target_col:
        inv_col = next(
            (c for c in cols if any(k in c.lower() for k in ('invoiceno', 'invoice_no', 'invoice_id', 'voucherno', 'orderno', 'order_no', 'bill_no')) and not pd.api.types.is_numeric_dtype(df[c])),
            None,
        )
        qty_col = next(
            (c for c in cols if c.lower().strip() in ('quantity', 'qty', 'units', 'order_qty', 'billed_qty') and pd.api.types.is_numeric_dtype(df[c])),
            None,
        )
        if qty_col is not None:
            q_num = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
            neg_q = q_num < 0
            inv_c = df[inv_col].astype(str).str.strip().str.upper().str.match(r'^(?:C\d|CN[-_\s]?\d|CR[-_\s]?\d)') if inv_col else pd.Series(False, index=df.index)
            comb_ret = neg_q | inv_c
            ret_rate = float(comb_ret.mean()) if len(df) else 0.0
            if int(comb_ret.sum()) >= 5 and 0.002 <= ret_rate <= 0.45:
                target_col = qty_col
                erp_credit_note_target = comb_ret.astype(int)
                erp_credit_note_desc = f"ERP Return / Credit Note ({qty_col} < 0" + (f" or {inv_col} 'C' prefix)" if inv_col and inv_c.any() else ")")

    # Fallback to last column if still none
    if not target_col:
        BAD_FALLBACK_TARGETS = [
            'tz', 'timezone', 'tzone', 'dst', 'longitude', 'latitude', 'lat', 'lon', 'coord',
            'pickup', 'dropoff', 'datetime', 'timestamp', 'date', 'time', 'sched', 'arr_time', 'dep_time', 'hour', 'minute'
        ]
        valid_cols = [
            c for c in cols
            if not is_index_artifact(c)
            and not is_demographic_attribute(c)
            and not c.lower().endswith(('_id', '_key'))
            and not any(b in c.lower() for b in BAD_FALLBACK_TARGETS)
        ]
        target_col = valid_cols[-1] if valid_cols else cols[-1]

    # -------------------------------------------------------------
    # 2. Canonical Binary Target Mapping (_is_target_event: 1 = adverse, 0 = normal)
    # -------------------------------------------------------------
    s_raw = df[target_col]
    is_num = pd.api.types.is_numeric_dtype(s_raw)
    target_desc = f"{target_col} Adverse Breach"

    # Define unambiguous global adverse tokens (English, Spanish, Portuguese, French, German, Italian + ERP snake_case)
    unconditional_adverse = (
        r'\b(?:bad|default|defaulted|charged off|delinquent|fraud|fraudulent|'
        r'churn|churned|attrition|attrited|defect|defective|fail|failed|failure|'
        r'cancel|cancelled|canceled|delayed|delay|late|anomaly|substandard|poor|'
        r'low quality|malignant|dead|death|deceased|fatal|disease|stroke|diabetic|'
        r'return|returned|rto|undelivered|rejected|lost|disputed|'
        r'damaged|damage|spoiled|spoilage|corrupt|corrupted|broken|shortage|missing|stolen|'
        r'breach|breached|excursion|overdue|expired|contaminated|chargeback|writeoff|write off|'
        r'rework|scrap|scrapped|outage|downtime|unfulfilled|refused|bounced|declined|void|voided|'
        r'unacceptable|dissatisfied|exited|abnormal|emergency|'
        r'cancelado|cancelada|devuelto|devuelta|devolvido|devolvida|reembolsado|rechazado|rechazada|'
        r'fallido|fallida|fallo|impagado|moroso|vencido|retrasado|retraso|dañado|danado|perdido|anulado|fraude|'
        r'annulé|annule|retourné|retourne|remboursé|rembourse|échoué|echoue|refusé|refuse|retard|retardé|endommagé|impayé|défaut|'
        r'storniert|retourniert|zurückgegeben|fehlgeschlagen|abgelehnt|verspätet|beschädigt|verloren|überfällig|zahlungsausfall|'
        r'annullato|cancellato|reso|rimborsato|rifiutato|ritardo|danneggiato|scaduto)\b'
    )
    # Conditional adverse tokens (only adverse if target column denotes risk/failure/default)
    conditional_adverse = r'\b(?:1|yes|y|true|t|sim|si|ja|oui|high|high risk|severe|critical|positive|pos)\b'
    col_denotes_adverse = any(k in target_col.lower() for k in [
        'risk', 'default', 'churn', 'fraud', 'defect', 'fail', 'bad', 'loss', 'delay',
        'late', 'cancel', 'disease', 'stroke', 'death', 'mortality', 'complication',
        'attrition', 'anomaly', 'claim', 'target', 'label', 'class', 'outcome', 'status',
        'estado', 'statut', 'stato', 'ergebnis', '状態', '状态', 'الحالة',
        'test results', 'test_results', 'admission'
    ])

    if erp_credit_note_target is not None:
        binary_target = erp_credit_note_target
        target_desc = erp_credit_note_desc or f"{target_col} < 0 (ERP Return)"
    elif not is_num:
        s_str = s_raw.astype(str).str.lower().str.strip()
        # Normalize ERP snake_case / kebab-case / slash codes (e.g. Delayed_SLA_Breach -> delayed sla breach)
        s_str_norm = s_str.str.replace(r'[_\-/]+', ' ', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
        is_adv = s_str_norm.str.contains(unconditional_adverse, regex=True)
        # Also match non-Latin global adverse status terms (Devanagari Hindi, Japanese, Chinese, Arabic, Korean)
        non_latin_adverse_tokens = (
            'वापस', 'वापसी', 'रिटर्न', 'रद्द', 'कैंसल', 'खराब', 'फेल', 'विफल', 'नुकसान', 'देरी', 'डिफ़ॉल्ट', 'टूटा',
            'キャンセル', '取消', '返品', '返金', '失敗', '遅延', '破損', '未払', '不正',
            '退货', '退款', '失败', '延迟', '损坏', '违约', '逾期',
            'ملغي', 'مرتجع', 'مرفوض', 'فشل', 'متأخر', 'تالف', 'متعثر',
            '취소', '반품', '환불', '실패', '지연', '파손', '연체',
        )
        is_adv_nl = s_str_norm.apply(lambda v: any(ht in v for ht in non_latin_adverse_tokens))
        if is_adv_nl.any():
            is_adv = is_adv | is_adv_nl
        # Exclude sentinel missing value tokens from being considered genuine adverse or non-adverse categories
        known_missing = {'unknown', 'none', 'null', 'nan', '', 'na', 'n/a'}
        clean_mask = s_raw.notna() & ~s_str.isin(known_missing)
        clean_unique = [str(v).lower().strip() for v in s_raw.dropna().unique() if str(v).lower().strip() not in known_missing]

        if target_col.lower() == 'cut' and any(k in s_str.unique() for k in ['ideal', 'premium', 'fair']):
            is_cut_sub = s_str.isin(['fair', 'good'])
            binary_target = is_cut_sub.astype(int)
            target_desc = f"{target_col} in ['Fair', 'Good'] (Substandard Cut)"
        elif any(k in target_col.lower() for k in ['quality', 'grade', 'rating', 'condition']) and s_str_norm.str.contains(
            r'\b(?:low|poor|substandard|bad|weak|inferior|rejected|spoiled|grade\s*[cdf])\b', regex=True
        ).any():
            is_low_q = s_str_norm.str.contains(
                r'\b(?:low|poor|substandard|bad|weak|inferior|rejected|spoiled|grade\s*[cdf])\b', regex=True
            ) & clean_mask
            binary_target = is_low_q.astype(int)
            target_desc = f"{target_col} Low / Substandard Quality"
        elif is_adv.sum() > 0:
            binary_target = is_adv.astype(int)
            target_desc = f"{target_col} Adverse State"
        elif col_denotes_adverse:
            is_cond = s_str_norm.str.contains(conditional_adverse, regex=True) & clean_mask
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
            is_pos = s_str_norm.str.contains(r'\b(?:good|success|pass|approved|performing|normal|clean)\b', regex=True)
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
            tc_norm = re.sub(r'[.\-\s]+', '_', target_col.lower())
            is_neg_prefix = any(k in tc_norm for k in ('not_', 'unpaid', 'non_', 'undelivered', 'incomplete', 'failed', 'default'))
            if (not is_neg_prefix) and any(k in tc_norm for k in ['survive', 'survival', 'pass', 'retention', 'policy', 'approved', 'delivered', 'retained']):
                binary_target = (s_clean == 0).astype(int)
                target_desc = f"{target_col} == 0 (Casualty / Mortality)" if any(k in tc_norm for k in ['survive', 'survival']) else f"{target_col} == 0 (Non-Compliant / Breach)"
            else:
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
        elif any(k in target_col.lower() for k in ['dep_delay', 'arr_delay', 'delay']):
            # Aviation FAA / DOT delay threshold (15 minutes or more past scheduled time)
            if s_clean.max() >= 15:
                thresh = 15.0
            else:
                thresh = float(s_clean.quantile(0.75))
            binary_target = (s_clean > thresh).astype(int)
            target_desc = f"{target_col} > {thresh:.0f} mins (Flight Delay)"
        elif target_col.lower() in ['mpg', 'fuel_efficiency', 'mileage']:
            # Automotive fleet fuel efficiency: <= 20 mpg low fuel economy breach (fuel guzzlers)
            if (s_clean <= 20).sum() > 0 and (s_clean <= 20).mean() <= 0.60:
                thresh = 20.0
            else:
                thresh = float(s_clean.quantile(0.25))
            binary_target = (s_clean <= thresh).astype(int)
            target_desc = f"{target_col} <= {thresh:.1f} mpg (Low Fuel Efficiency)"
        elif any(k in target_col.lower() for k in ['house_value', 'property_value', 'asset_value', 'stream', 'streams', 'sales', 'revenue', 'view', 'views', 'profit', 'yield', 'conversion']):
            # For valuation/volume/yield metrics: bottom quartile is adverse underperformance / distressed valuation
            thresh = float(s_clean.quantile(0.25)) if s_clean.quantile(0.25) > 0 else float(s_clean.median())
            binary_target = (s_clean <= thresh).astype(int)
            target_desc = f"{target_col} <= ${thresh:,.0f} (Distressed Asset Valuation)" if 'value' in target_col.lower() else f"{target_col} <= {thresh:.2f}"
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
        'loan_amount', 'loanamount', 'loan', 'credit_amount', 'installment', 'instalment', 'emi', 'monthly_payment', 'amount', 'credit', 'price', 'cost', 'revenue', 'mrr', 'sales', 'balance',
        'loss', 'claim', 'charge', 'charges', 'billing_amount', 'billing', 'salary', 'income', 'expense', 'payment', 'fee',
        'valormensal', 'totalgasto', 'valor', 'gasto', 'fatura', 'adr', 'daily_rate', 'fare', 'house_value', 'property_value', 'asset_value',
        'total_bill', 'total_amount', 'total_sales', 'total_price', 'total_cost', 'total_revenue', 'gross income', 'gross_income',
        'order_value', 'contract_value', 'deal_value', 'invoice_value', 'line_value', 'line_total', 'order_bill', 'bill_inr', 'bill_usd',
        'premium', 'retainer', 'monthly_rent', 'annual_rent', 'rent_inr', 'rent_usd', 'freight', 'tariff', 'principal', 'tuition', 'commission',
        'importe', 'monto', 'montant', 'betrag', 'umsatz', 'preis', 'kosten', 'precio', 'prix', 'prezzo', '金額', '売上', '金额', 'المبلغ',
        'रकम', 'राशि', 'रुपये', 'रुपए', 'कीमत', 'मूल्य', 'बिल', 'बिक्री', 'खर्च', 'लागत', 'किराया', 'आय', 'वेतन', 'भुगतान'
    ]
    # Synthetic / non-financial terms to explicitly exclude
    excluded_cost_terms = [
        'penalty', 'friction', 'weighted', 'index', 'idx', 'euribor', 'score', 'ratio', 'scaled',
        'rate', 'pct', 'percent', 'rank', 'density', 'satisfaction', 'rating', 'level',
        'hours', 'work_life', 'worklife', 'working', 'distance', 'age', 'duration', 'pdays', 'previous', 'campaign', 'day_of_week'
    ]
    time_units = ['year', 'years', 'month', 'months', 'day', 'days', 'date']

    is_target_valuation = bool(target_col and any(k in target_col.lower() for k in ['house_value', 'property_value', 'asset_value']))
    candidate_cost_cols = []
    for c in cols:
        if (c == target_col and not is_target_valuation) or is_index_artifact(c) or is_synthetic_column(c, blueprint):
            continue
        c_low = c.lower().strip()
        c_words = re.sub(r'[^a-z0-9]+', ' ', re.sub(r'([a-z])([A-Z])', r'\1 \2', c).lower()).strip()
        # Use word-boundary matching for short/ambiguous tokens like 'age' (so 'Average Cost' / 'Package' isn't wrongly blocked)
        _word_boundary_excl = {'age', 'rate', 'rank', 'idx', 'level', 'hours', 'range', 'tier', 'bracket', 'band', 'bucket'}
        _substr_excl = [x for x in excluded_cost_terms if x not in _word_boundary_excl]
        if c_low not in ['adr', 'daily_rate', 'hourly_rate', 'fare']:
            if any(x in c_low for x in _substr_excl):
                continue
            if any(re.search(rf'\b{re.escape(w)}\b', c_words) for w in _word_boundary_excl):
                continue
        # Exclude count metrics (preserving 'discount')
        if bool(re.search(r'(?<!dis)count', c_low)):
            continue
        has_anchored_arr = bool(re.search(r'(?:^|_|annual|monthly|account|net|gross|total)arr(?:$)', c_low)) or (c_low.startswith('arr_') and not any(k in c_low for k in ['time', 'delay', 'date', 'hour', 'min', 'minute', 'airport', 'city', 'loc', 'flight', 'station']))
        has_currency_suffix = bool(re.search(r'(?:_inr|_usd|_eur|_gbp|_aed|_sgd|_jpy|_cny|_cad|_aud|_chf|_sar|_brl|_mxn|_krw|_zar|_hkd)$', c_low))
        is_exact_total = c_low in ('total', 'total_num', 'total_clean', 'total_val')
        # Exclude pure ID/key/code suffix unless column explicitly contains money words
        money_words = [
            'amount', 'price', 'cost', 'revenue', 'mrr', 'sales', 'net_sale', 'gross_sale', 'total_sale',
            'sale_amount', 'sale_value', 'net_bill', 'bill_amount', 'bill_value', 'invoice_total', 'order_total', 'mrp', 'billing', 'charge', 'salary', 'income', 'expense', 'fee', 'payment',
            'credit', 'balance', 'claim', 'valormensal', 'totalgasto', 'valor', 'gasto', 'fatura', 'adr', 'fare',
            'importe', 'monto', 'montant', 'betrag', 'umsatz', 'preis', 'kosten', 'precio', 'prix', 'prezzo', '金額', '売上', '金额', 'المبلغ',
            'house_value', 'property_value', 'asset_value', 'total_bill', 'gross income', 'gross_income',
            'order_value', 'contract_value', 'deal_value', 'invoice_value', 'order_bill', 'premium', 'retainer', 'rent', 'freight', 'tariff', 'principal'
        ]
        if any(c_low.endswith(('_' + sfx, sfx)) for sfx in ['id', 'key', 'code', 'number']) and not (any(m in c_low for m in money_words) or has_anchored_arr or has_currency_suffix or is_exact_total):
            continue
        # Exclude pure date/time/tenure columns that end with time units unless they contain explicit money words
        if any(c_low == t or c_low.endswith(t) for t in time_units) and not (any(m in c_low for m in money_words) or has_anchored_arr or has_currency_suffix):
            continue
        if (any(k in c_low for k in cost_keywords) or has_anchored_arr or has_currency_suffix or is_exact_total) and pd.api.types.is_numeric_dtype(df[c]):
            # If raw_source_cols provided, ensure it was an authentic raw column or a clean numeric parse of one
            if raw_source_cols:
                raw_low = {r.lower() for r in raw_source_cols}
                base_c = c_low.replace('_num', '').replace('_clean', '').replace('_parsed', '').replace('_val', '')
                if c not in raw_source_cols and base_c not in raw_low:
                    continue
            s_raw = pd.to_numeric(df[c], errors='coerce')
            s_nonnull = s_raw.dropna()
            if len(s_nonnull) >= max(1, int(len(df) * 0.50)) and (s_nonnull > 0).mean() > 0.85 and float(s_nonnull.sum()) > 0:
                candidate_cost_cols.append(c)

    if blueprint and str(blueprint.get("cost_override", "")).upper() in ("__NONE__", "NONE"):
        cost_col = None
    elif blueprint and blueprint.get("cost_override") in cols:
        cost_col = blueprint.get("cost_override")
    elif candidate_cost_cols:
        priority_cost = [
            'loan_amount', 'loanamount', 'loan', 'credit_amount', 'installment', 'instalment', 'emi', 'house_value', 'median_house_value', 'property_value',
            'invoiced_amount', 'net_billed', 'net_bill', 'net_revenue', 'net_sales', 'net_sale', 'selling_price', 'net_amount', 'bill_amount', 'bill_value',
            'revenue', 'mrr', 'arr', 'sales', 'gross_sale', 'total_sale', 'sale_amount', 'sale_value', 'total_bill', 'order_bill', 'order_total', 'invoice_total', 'line_value', 'line_total', 'total_amount', 'total_sales', 'exact_total',
            'order_value', 'contract_value', 'deal_value', 'invoice_value', 'invoice_amount', 'premium', 'retainer', 'monthly_rent', 'rent',
            'gross income', 'gross_income', 'billing_amount', 'gross_billing', 'billing',
            'valormensal', 'totalgasto', 'salary', 'income',
            'amount', 'credit', 'price', 'cost', 'expense', 'claim', 'charges', 'balance', 'adr', 'fare', 'daily_rate', 'payment', 'fee', 'freight', 'tariff', 'principal', 'valor', 'gasto', 'fatura'
        ]
        def _cost_priority(col: str) -> int:
            cl = col.lower().strip()
            for i, pc in enumerate(priority_cost):
                if pc == 'exact_total':
                    if cl in ('total', 'total_num', 'total_clean', 'total_val'):
                        return i
                elif pc in cl:
                    return i
            return 999
        candidate_cost_cols.sort(key=_cost_priority)
        cost_col = candidate_cost_cols[0]

    eff_region = region_profile or (blueprint.get("region_profile") if isinstance(blueprint, dict) else None)
    is_financial = (cost_col is not None)
    curr_meta = resolve_currency_metadata(df, cost_col, eff_region)
    unit_symbol = curr_meta["unit_symbol"]

    result = {
        "target_col": target_col,
        "binary_target": binary_target,
        "target_desc": target_desc,
        "cost_col": cost_col,
        "is_financial": is_financial,
        "unit_symbol": unit_symbol,
        "currency_code": curr_meta["currency_code"],
        "numbering_system": curr_meta["numbering_system"],
        "is_multi_currency": bool(curr_meta.get("is_multi_currency", False)),
        "currency_col": curr_meta.get("currency_col"),
        "detected_currencies": curr_meta.get("detected_currencies", []),
        "currency_breakdown": curr_meta.get("currency_breakdown", {}),
    }
    if len(_CANONICAL_TARGET_CACHE) > 16:
        _CANONICAL_TARGET_CACHE.clear()
    _CANONICAL_TARGET_CACHE[cache_key] = result
    return result
