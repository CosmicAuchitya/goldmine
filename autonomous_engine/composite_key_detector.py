"""
=============================================================================
ENTERPRISE COMPOSITE KEY & MULTI-COLUMN RELATIONSHIP DETECTOR
=============================================================================
Defeats Weakness #1: Composite Foreign Keys Blindspot.
Solves:
- Relationships spanning 2 or 3 columns (e.g. store_id + region, flight + date)
- Accidental row duplication caused by joining on only 1 column of a composite key
Algorithm:
1. Detects minimal composite candidate keys where tuple uniqueness == 1.0.
2. Cross-evaluates multi-column pairs across tables to recommend composite joins.
=============================================================================
"""

import sys
from itertools import combinations
from typing import Dict, List, Tuple, Any
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def find_candidate_composite_keys(
    df: pd.DataFrame,
    candidate_cols: List[str] = None,
    max_k: int = 3
) -> List[Tuple[str, ...]]:
    """
    Finds combinations of 2 or 3 columns that form a strictly unique composite key.
    """
    if candidate_cols is None:
        # Filter to ID, code, category, and date columns
        candidate_cols = [
            c for c in df.columns 
            if any(k in str(c).lower() for k in ['id', 'code', 'num', 'key', 'date', 'year', 'month', 'region', 'store', 'type'])
        ]
        
    n_rows = len(df)
    if n_rows == 0 or len(candidate_cols) < 2:
        return []
        
    valid_composites = []
    # Test combinations of length 2 and 3
    for k in range(2, min(max_k + 1, len(candidate_cols) + 1)):
        for combo in combinations(candidate_cols, k):
            # Check composite uniqueness
            uniques = df.duplicated(subset=list(combo)).sum()
            if uniques == 0:
                valid_composites.append(combo)
                
    return valid_composites

def detect_composite_join_mapping(
    df_left: pd.DataFrame, left_name: str,
    df_right: pd.DataFrame, right_name: str
) -> List[Dict[str, Any]]:
    """
    Detects if Left and Right tables share composite keys that must be joined together.
    """
    shared_cols = [c for c in df_left.columns if c in df_right.columns]
    if len(shared_cols) < 2:
        return []
        
    results = []
    for k in range(2, min(4, len(shared_cols) + 1)):
        for combo in combinations(shared_cols, k):
            combo_list = list(combo)
            dups_left = int(df_left.duplicated(subset=combo_list).sum())
            dups_right = int(df_right.duplicated(subset=combo_list).sum())
            
            # If at least one side is unique on the composite key, it is a valid composite relation!
            if dups_left == 0 or dups_right == 0:
                results.append({
                    "left_table": left_name,
                    "right_table": right_name,
                    "composite_keys": combo_list,
                    "is_left_unique": (dups_left == 0),
                    "is_right_unique": (dups_right == 0),
                    "join_type": "Composite 1:N Join" if (dups_right == 0 and dups_left > 0) else "Composite 1:1 Join",
                    "recommendation": f"Must join ON {' AND '.join([f'{left_name}.{c} = {right_name}.{c}' for c in combo_list])} to prevent Cartesian row explosion."
                })
                
    return results

if __name__ == "__main__":
    # Test with retail store + region composite key scenario
    sales = pd.DataFrame({
        "store_id": [101, 101, 102, 102],
        "region_code": ["EAST", "WEST", "EAST", "WEST"],
        "sales_amount": [5000, 7000, 4500, 8000]
    })
    store_meta = pd.DataFrame({
        "store_id": [101, 101, 102, 102],
        "region_code": ["EAST", "WEST", "EAST", "WEST"],
        "manager_name": ["Alice", "Bob", "Charlie", "David"]
    })
    
    print("[*] Testing Composite Key Detector...")
    matches = detect_composite_join_mapping(sales, "Sales_Fact", store_meta, "Store_Dim")
    import json
    print(json.dumps(matches, indent=2))
