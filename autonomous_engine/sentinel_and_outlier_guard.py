"""
=============================================================================
ENTERPRISE SENTINEL & BI-DIRECTIONAL OUTLIER DEFENSE (HARDENED)
=============================================================================
Hardened against:
1. Negative sentinels (-1, -99, -999, -9999, -99999)
2. Negative physical/financial impossible values (negative length, negative cost, negative price)
3. Extreme positive spikes (capped at 99.5th percentile)
=============================================================================
"""

import sys
from typing import List, Tuple
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

UNAMBIGUOUS_EXTREME_SENTINELS = {-999, -9999, -99999, 9999, 99999, 999999, 9999999}
CONTEXTUAL_SENTINELS = {-99, 99, 999}

def cleanse_sentinel_values(series: pd.Series, col_name: str = "") -> Tuple[pd.Series, int]:
    """
    Identifies known negative and positive sentinel placeholders and converts them to NaN.
    Distribution-aware: Protects legitimate percentages (99%), exam scores, and ages.
    """
    s = pd.to_numeric(series, errors='coerce').copy()
    initial_valid = s.dropna()
    if initial_valid.empty:
        return s, 0
        
    # Unambiguous extreme placeholders
    mask_sentinels = s.isin(UNAMBIGUOUS_EXTREME_SENTINELS)
    
    # Contextual check: only mask 99 / 999 if series is NOT a natural 0-100 distribution (e.g. percentages, rates, ages)
    col_lower = col_name.lower()
    is_bounded_pct = (initial_valid.min() >= 0 and initial_valid.max() <= 100) or any(
        k in col_lower for k in ['pct', 'percent', 'rate', 'score', 'age', 'grade', 'ratio']
    )
    
    if not is_bounded_pct:
        mask_sentinels = mask_sentinels | s.isin(CONTEXTUAL_SENTINELS)
        
    sentinel_count = int(mask_sentinels.sum())
    
    if sentinel_count > 0:
        s.loc[mask_sentinels] = np.nan
        
    return s, sentinel_count

def cap_bi_directional_outliers(
    series: pd.Series,
    allow_negatives: bool = False,
    upper_percentile: float = 99.5,
    lower_percentile: float = 0.5
) -> Tuple[pd.Series, float, float]:
    """
    Clamps both upper and lower extreme outliers.
    Enforces a strict zero floor (>= 0.0) if allow_negatives is False.
    """
    s = pd.to_numeric(series, errors='coerce').copy()
    valid = s.dropna()
    if len(valid) < 100:
        if not allow_negatives:
            s = s.clip(lower=0.0)
        return s, 0.0, float('inf')
        
    upper_cap = float(np.percentile(valid, upper_percentile))
    lower_cap = 0.0 if not allow_negatives else float(np.percentile(valid, lower_percentile))
    
    clamped = s.clip(lower=lower_cap)
    
    # Check if max value is more than 3x the 99.5th percentile
    if valid.max() > upper_cap * 3.0:
        clamped = clamped.clip(upper=upper_cap)
        
    return clamped, lower_cap, upper_cap

def sanitize_metric_series(series: pd.Series, col_name: str = "", allow_negatives: bool = False) -> pd.Series:
    """
    Full pipeline: cleanses sentinels and clamps bi-directional outliers.
    """
    s_clean, sentinels_found = cleanse_sentinel_values(series, col_name=col_name)
    s_capped, lower_cap, upper_cap = cap_bi_directional_outliers(s_clean, allow_negatives=allow_negatives)
    
    if sentinels_found > 0:
        print(f"[*] Cleansed {sentinels_found} sentinel values from '{col_name}'.")
    if not allow_negatives and (s_clean < 0).any():
        print(f"[*] Enforced zero-floor on '{col_name}' (eliminated negative physical values).")
        
    return s_capped

if __name__ == "__main__":
    # Test with negative sentinels, negative values, and extreme upper outliers
    test_data = pd.Series([-999, -1, -50, 10, 20, 30, 40, 50, 99999, 1000000] + [25]*500)
    print("[*] Testing Hardened Bi-directional Outlier Guard...")
    clean = sanitize_metric_series(test_data, "Test_Metric", allow_negatives=False)
    print(f"Original: min={test_data.min()}, max={test_data.max()}")
    print(f"Cleaned : min={clean.min()}, max={clean.max()}")
