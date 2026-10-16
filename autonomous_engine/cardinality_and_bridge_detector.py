"""
=============================================================================
ENTERPRISE CARDINALITY & BRIDGE TABLE DETECTOR
=============================================================================
Defeats Weakness #5: Many-to-Many (M:N) Relationship Traps.
Inspects key multiplicity between two tables before joining:
1. One-to-One (1:1): Safe standard dimensional join.
2. One-to-Many (1:N): Standard Fact-to-Dimension join OR requires aggregation.
3. Many-to-Many (N:M): Critical danger zone! Identifies bridge table necessity
   to prevent catastrophic Cartesian row duplication.
=============================================================================
"""

import sys
from typing import Dict, Any, Optional
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def check_full_file_uniqueness(file_path: Optional[str], key_col: str) -> Optional[bool]:
    """Uses DuckDB to evaluate exact uniqueness across the entire file in milliseconds without RAM overhead."""
    if not file_path:
        return None
    try:
        import duckdb
        p = Path(file_path)
        if not p.exists() or p.suffix.lower() not in ['.csv', '.parquet']:
            return None
            
        con = duckdb.connect(':memory:')
        file_posix = p.as_posix().replace("'", "''")
        clean_col = key_col.replace('"', '""')
        if p.suffix.lower() == '.csv':
            sql = f"SELECT count(*), count(DISTINCT \"{clean_col}\") FROM read_csv_auto('{file_posix}', header=true, normalize_names=false, ignore_errors=true)"
        else:
            sql = f"SELECT count(*), count(DISTINCT \"{clean_col}\") FROM read_parquet('{file_posix}')"
        res = con.execute(sql).fetchone()
        con.close()
        if res and res[0] is not None and res[1] is not None:
            total_rows, distinct_keys = res[0], res[1]
            return (total_rows == distinct_keys) and (total_rows > 0)
    except Exception:
        return None
    return None

def detect_relationship_cardinality(
    df_left: pd.DataFrame, left_key: str,
    df_right: pd.DataFrame, right_key: str,
    left_file_path: Optional[str] = None,
    right_file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes exact multiplicity and cardinality type between two candidate join keys.
    Utilizes DuckDB full-file scanning when available to eliminate sampling bias.
    """
    s_left = df_left[left_key].dropna()
    s_right = df_right[right_key].dropna()
    
    left_total = len(s_left)
    left_unique = s_left.nunique()
    left_is_unique = (left_total == left_unique) and (left_total > 0)
    
    right_total = len(s_right)
    right_unique = s_right.nunique()
    right_is_unique = (right_total == right_unique) and (right_total > 0)
    
    # Check full file out-of-core if path is supplied (defeats 2000-row sampling bias)
    if left_file_path:
        exact_left = check_full_file_uniqueness(left_file_path, left_key)
        if exact_left is not None:
            left_is_unique = exact_left
            
    if right_file_path:
        exact_right = check_full_file_uniqueness(right_file_path, right_key)
        if exact_right is not None:
            right_is_unique = exact_right
    
    # Check key overlap intersection
    shared_keys = set(s_left.unique()).intersection(set(s_right.unique()))
    overlap_count = len(shared_keys)
    
    if left_is_unique and right_is_unique:
        card_type = "1:1 (ONE-TO-ONE)"
        recommendation = "Safe direct relational merge. Referential integrity preserved."
        danger_level = "LOW"
    elif left_is_unique and not right_is_unique:
        card_type = "1:N (ONE-TO-MANY)"
        recommendation = "Right table has duplicate keys. If joining Right into Left, Right MUST be aggregated 1:1 first to prevent duplicate rows."
        danger_level = "MEDIUM"
    elif not left_is_unique and right_is_unique:
        card_type = "N:1 (MANY-TO-ONE)"
        recommendation = "Standard Fact-to-Dimension lookup join. Left table rows will be cleanly preserved without multiplication."
        danger_level = "LOW"
    else:
        card_type = "N:M (MANY-TO-MANY)"
        recommendation = "CRITICAL HAZARD: Both tables have duplicate keys. Direct join causes exponential Cartesian product (N x M rows). Star Schema requires a Bridge Table or Array Aggregation."
        danger_level = "HIGH"
        
    return {
        "left_key": left_key,
        "right_key": right_key,
        "cardinality": card_type,
        "danger_level": danger_level,
        "shared_keys_count": overlap_count,
        "left_unique_ratio": round(left_unique / max(left_total, 1), 4),
        "right_unique_ratio": round(right_unique / max(right_total, 1), 4),
        "architecture_recommendation": recommendation
    }

if __name__ == "__main__":
    # Test with Order to Products (Many-to-Many bridge scenario)
    orders_items = pd.DataFrame({"order_id": [1, 1, 2, 2], "prod_id": ["P1", "P2", "P1", "P3"]})
    promotions = pd.DataFrame({"order_id": [1, 1, 2], "promo_code": ["SUMMER", "SAVE10", "WELCOME"]})
    
    print("[*] Testing Cardinality & Bridge Detector...")
    analysis = detect_relationship_cardinality(orders_items, "order_id", promotions, "order_id")
    import json
    print(json.dumps(analysis, indent=2))
