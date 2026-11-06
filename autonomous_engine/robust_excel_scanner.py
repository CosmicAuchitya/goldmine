"""
=============================================================================
INTELLIGENT EXCEL & TABULAR HEADER SCANNER
=============================================================================
Defeats Weakness #2: Multi-header, merged cells, and title-row metadata.
Algorithm:
1. Inspects the first 15 rows of an Excel sheet or CSV.
2. Computes the 'Header Signal Score' for each row based on:
   - String density (% of non-empty cells that are strings)
   - Column name distinctness (uniqueness of cell values)
   - Absence of purely numeric/date values
3. Automatically detects the optimal `skiprows` parameter.
=============================================================================
"""

import os
import sys
import re
from pathlib import Path
from typing import Any, List, Optional
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Import CSV sniffer for arbitrary delimiters and encodings
try:
    from robust_csv_sniffer import smart_read_csv
except ImportError:
    from autonomous_engine.robust_csv_sniffer import smart_read_csv


def clean_accounting_series(s: pd.Series) -> pd.Series:
    """
    Cleans accounting-formatted strings into standard floats:
    - Indian numbering with commas: '12,34,567.50' -> 1234567.50
    - Parentheses for negatives: '(1,250.00)' -> -1250.00
    - Debit/Credit suffixes: '5,000.00 Dr' -> 5000.00, '5,000.00 Cr' -> -5000.00
    - Currency symbols: '₹ 45,000.00' / '£1,200.00' / '$500'
    """
    if pd.api.types.is_numeric_dtype(s):
        return s

    if not pd.api.types.is_object_dtype(s) and not pd.api.types.is_string_dtype(s):
        return s

    def _convert_val(val):
        if pd.isna(val):
            return np.nan
        v_str = str(val).strip()
        if not v_str or v_str.lower() in ('nan', 'none', 'null', '-', '--'):
            return np.nan

        # Check debit / credit suffix
        is_cr = v_str.lower().endswith(' cr') or v_str.lower().endswith('cr')
        # Check parenthesized negative: (1,234.50)
        is_paren_neg = v_str.startswith('(') and v_str.endswith(')')

        # Remove currency symbols, commas, Dr/Cr, parens
        cleaned = re.sub(r'[₹\$£€\s,]', '', v_str)
        cleaned = re.sub(r'(?i)(dr|cr)$', '', cleaned).strip('()')

        try:
            num = float(cleaned)
            if is_cr or is_paren_neg:
                return -abs(num)
            return num
        except (ValueError, TypeError):
            return val

    # Test sample conversion rate to ensure we only convert if >=75% non-null values parse as numbers
    sample = s.dropna().head(50)
    if len(sample) == 0:
        return s

    converted_sample = [isinstance(_convert_val(x), (float, int)) for x in sample]
    if sum(converted_sample) / float(len(converted_sample)) >= 0.75:
        return s.apply(_convert_val)
    return s


def strip_accounting_summary_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects and removes summary/aggregate footer rows (Total, Grand Total, Closing Balance)
    common in Tally, Marg, SAP, and Indian accounting exports to avoid double-counting.
    """
    if len(df) <= 2:
        return df

    summary_pattern = re.compile(
        r'^(?:total|grand\s*total|sub\s*total|subtotal|closing\s*balance|balance\s*c/f|balance\s*b/f)\b',
        re.IGNORECASE
    )

    # Check bottom 10 rows
    rows_to_drop = []
    tail_len = min(10, len(df))
    tail_indices = df.index[-tail_len:]

    for idx in tail_indices:
        row_str_vals = [str(x).strip() for x in df.loc[idx] if pd.notna(x)]
        if any(summary_pattern.match(v) for v in row_str_vals[:4]):
            rows_to_drop.append(idx)

    if rows_to_drop:
        return df.drop(index=rows_to_drop)
    return df

def detect_optimal_header_row(file_path: Path, max_scan_rows: int = 15) -> int:
    """
    Returns the 0-indexed row number that most likely represents the true table header.
    """
    ext = file_path.suffix.lower()
    
    try:
        if ext in ['.xlsx', '.xls']:
            preview_df = pd.read_excel(file_path, header=None, nrows=max_scan_rows)
        elif ext == '.csv':
            preview_df = smart_read_csv(file_path, header=None, nrows=max_scan_rows)
        else:
            return 0
    except Exception:
        return 0

    best_row_idx = 0
    highest_score = -1.0

    for idx, row in preview_df.iterrows():
        non_null = row.dropna()
        if len(non_null) == 0:
            continue
            
        # Metric 1: Fill rate (what % of available columns are populated in this row)
        fill_ratio = len(non_null) / float(len(row))
        
        # Metric 2: String type ratio (headers are almost always strings, not floats/ints)
        string_count = sum(1 for v in non_null if isinstance(v, str) and not v.strip().replace('.', '', 1).isdigit())
        string_ratio = string_count / float(len(non_null))
        
        # Metric 3: Distinctness (headers must be distinct names)
        uniqueness_ratio = len(set(non_null)) / float(len(non_null))
        
        # Metric 4: Title/metadata penalty (if a row has only 1 or 2 cells filled, it's a report title)
        title_penalty = 0.2 if len(non_null) <= 2 and len(row) > 3 else 1.0
        
        score = (fill_ratio * 0.4 + string_ratio * 0.3 + uniqueness_ratio * 0.3) * title_penalty
        
        if score > highest_score:
            highest_score = score
            best_row_idx = idx

    return int(best_row_idx)

def smart_read_tabular(file_path: str, **kwargs) -> pd.DataFrame:
    p = Path(file_path)
    header_idx = detect_optimal_header_row(p)
    ext = p.suffix.lower()
    
    if ext in ['.xlsx', '.xls']:
        df = pd.read_excel(p, header=header_idx, **kwargs)
    elif ext == '.csv':
        df = smart_read_csv(p, header=header_idx, **kwargs)
    elif ext == '.parquet':
        df = pd.read_parquet(p, **kwargs)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
        
    # Clean column names (strip whitespace, normalize)
    df.columns = [str(c).strip() for c in df.columns]
    # Strip summary/total rows (e.g. from Tally/Indian accounting exports)
    df = strip_accounting_summary_rows(df)
    # Clean accounting formatted columns (Dr/Cr, currency symbols, Indian commas)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = clean_accounting_series(df[c])
    return df

if __name__ == "__main__":
    test_path = sys.argv[1] if len(sys.argv) > 1 else "raw_data/sample.xlsx"
    detected = detect_optimal_header_row(Path(test_path))
    print(f"[*] Scanned '{test_path}' -> Optimal Header Row: {detected}")
