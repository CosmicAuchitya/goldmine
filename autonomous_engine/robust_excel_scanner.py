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
from pathlib import Path
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Import CSV sniffer for arbitrary delimiters and encodings
try:
    from robust_csv_sniffer import smart_read_csv
except ImportError:
    from autonomous_engine.robust_csv_sniffer import smart_read_csv

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
    return df

if __name__ == "__main__":
    test_path = sys.argv[1] if len(sys.argv) > 1 else "error/raw_data/Airlines.xlsx"
    detected = detect_optimal_header_row(Path(test_path))
    print(f"[*] Scanned '{test_path}' -> Optimal Header Row: {detected}")
