"""
=============================================================================
ENTERPRISE INTELLIGENT DATE & TEMPORAL NORMALIZER
=============================================================================
Defeats Weakness #2: Mixed Date Chaos & US vs UK Ambiguity.
Solves:
- US format (02/05/2024 = Feb 5) vs UK/India format (02/05/2024 = May 2)
- Excel 5-digit serial dates (e.g. 45413 -> 2024-05-01)
- Mixed formats within the same column
Algorithm:
1. Unmasks numeric Excel serial dates.
2. Performs holistic column inspection to determine dayfirst orientation
   (detects whether first or second component exceeds 12).
3. Standardizes dates to ISO YYYY-MM-DD and extracts calendar dimensions.
=============================================================================
"""

import re
import sys
from typing import Tuple
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def detect_dayfirst_orientation(series: pd.Series) -> bool:
    """
    Examines slash/dash date strings across the entire column to determine
    whether day comes first (DD/MM/YYYY) or month comes first (MM/DD/YYYY).
    """
    sample = series.dropna().astype(str).head(500)
    
    first_part_gt_12 = 0
    second_part_gt_12 = 0
    
    date_regex = re.compile(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})')
    
    for val in sample:
        m = date_regex.match(val.strip())
        if m:
            p1 = int(m.group(1))
            p2 = int(m.group(2))
            if p1 > 12:
                first_part_gt_12 += 1
            if p2 > 12:
                second_part_gt_12 += 1
                
    # If first part has numbers > 12, it is definitely DD/MM (dayfirst = True)
    if first_part_gt_12 > 0:
        return True
    # If second part has numbers > 12, it is definitely MM/DD (dayfirst = False)
    if second_part_gt_12 > 0:
        return False
        
    # Default fallback: US format unless international locale hint is present
    return False

def normalize_date_series(series: pd.Series, col_name: str = "date") -> Tuple[pd.Series, pd.DataFrame]:
    """
    Standardizes a mixed date series into clean datetime and ISO string.
    Generates rich calendar dimension features (year, month, quarter, day_of_week).
    """
    s = series.copy()
    
    s_numeric = pd.to_numeric(s, errors='coerce')
    # Valid Excel serial mask: numbers between 25000 and 75000 (roughly 1968 to 2105)
    serial_mask = s_numeric.between(25000, 75000)
    
    parsed_dt = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')
    
    # Ensure serial dates are parsed only if column exhibits temporal intent or has significant serial density
    has_date_intent = any(k in col_name.lower() for k in ['date', 'time', 'dt', 'day', 'birth', 'created', 'updated', 'stamp', 'period'])
    serial_density = serial_mask.sum() / max(len(s.dropna()), 1)
    is_valid_serial = has_date_intent or (serial_density >= 0.30)
    
    # 1. Parse Excel serial numbers
    if is_valid_serial and serial_mask.any():
        parsed_dt.loc[serial_mask] = pd.to_datetime(
            s_numeric[serial_mask], unit='D', origin='1899-12-30', errors='coerce'
        )
        
    # 2. Parse text/string dates
    text_mask = ~serial_mask & s.notna()
    if text_mask.any():
        dayfirst = detect_dayfirst_orientation(s[text_mask])
        dt_parsed = pd.to_datetime(
            s[text_mask], dayfirst=dayfirst, errors='coerce', format='mixed', utc=True
        )
        parsed_dt.loc[text_mask] = dt_parsed.dt.tz_localize(None)

    clean_iso = parsed_dt.dt.strftime('%Y-%m-%d')
    
    # Calendar dimension features
    calendar_df = pd.DataFrame({
        f"{col_name}_iso": clean_iso,
        f"{col_name}_year": parsed_dt.dt.year,
        f"{col_name}_month": parsed_dt.dt.month,
        f"{col_name}_quarter": parsed_dt.dt.quarter,
        f"{col_name}_dayofweek": parsed_dt.dt.day_name()
    })
    
    return clean_iso, calendar_df

if __name__ == "__main__":
    # Test 1: Indian/UK DD/MM/YYYY with day > 12 (e.g. 15/02/2024 and 02/05/2024)
    uk_dates = pd.Series(["15/02/2024", "02/05/2024", "28/11/2024"])
    print("[*] Testing UK/India DD/MM/YYYY detection...")
    iso, cal = normalize_date_series(uk_dates, "order_date")
    print(iso.tolist()) # Should parse 02/05 as May 2, NOT Feb 5
    
    # Test 2: Excel serial dates (e.g. 45413 = 2024-05-01)
    excel_dates = pd.Series([45413, 45414, 45415])
    print("\n[*] Testing Excel Serial Date unmasking...")
    iso_ex, _ = normalize_date_series(excel_dates, "excel_date")
    print(iso_ex.tolist())
