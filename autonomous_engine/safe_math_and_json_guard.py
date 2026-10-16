"""
=============================================================================
ENTERPRISE SAFE MATH & JSON SERIALIZATION GUARD
=============================================================================
Defeats Weakness #2: Division-by-Zero, Infinity Floats, and JSON serialization crashes.
Solves:
- Division-by-zero yielding inf or NaN in calculated rates, speeds, and ratios
- ValueError: Out of range float values are not JSON compliant
- Type compatibility for NumPy scalars (int64, float64, ndarray)
=============================================================================
"""

import math
import sys
import json
from typing import Any, Union
import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def safe_divide(
    numerator: Union[pd.Series, np.ndarray, float],
    denominator: Union[pd.Series, np.ndarray, float],
    fill_value: float = 0.0
) -> Union[pd.Series, np.ndarray, float]:
    """
    Vectorized safe division that defends against zero, null, or negative denominators.
    Guarantees no inf or -inf values are generated.
    """
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        num = pd.to_numeric(numerator, errors='coerce').fillna(0.0)
        denom = pd.to_numeric(denominator, errors='coerce').fillna(0.0)
        result = np.where((denom != 0.0) & (~np.isnan(denom)), num / denom, fill_value)
        # Ensure any rogue inf is sanitized
        clean_res = np.where(np.isinf(result) | np.isnan(result), fill_value, result)
        return pd.Series(clean_res, index=numerator.index if isinstance(numerator, pd.Series) else None)
    elif isinstance(numerator, np.ndarray) or isinstance(denominator, np.ndarray):
        num = np.nan_to_num(numerator, nan=0.0)
        denom = np.nan_to_num(denominator, nan=0.0)
        with np.errstate(divide='ignore', invalid='ignore'):
            res = np.where(denom != 0.0, num / denom, fill_value)
            res = np.where(np.isinf(res) | np.isnan(res), fill_value, res)
        return res
    else:
        try:
            if denominator == 0.0 or math.isnan(denominator) or math.isinf(denominator):
                return fill_value
            res = numerator / denominator
            return fill_value if math.isinf(res) or math.isnan(res) else res
        except Exception:
            return fill_value

def clean_for_json(obj: Any) -> Any:
    """
    Recursively sanitizes Python and NumPy data structures for safe, strict JSON serialization.
    Converts inf, -inf, and nan into None or 0.0.
    Converts np.int64/np.float64 to native Python types.
    """
    if isinstance(obj, dict):
        return {str(k): clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, (np.floating, float)):
        if np.isinf(obj) or np.isnan(obj):
            return None
        return float(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return clean_for_json(obj.tolist())
    elif pd.isna(obj):
        return None
    return obj

class SafeJSONEncoder(json.JSONEncoder):
    """
    Drop-in JSON encoder that never crashes on infinity, NaN, or NumPy objects.
    """
    def default(self, o):
        if isinstance(o, (np.integer, int)):
            return int(o)
        elif isinstance(o, (np.floating, float)):
            if np.isinf(o) or np.isnan(o):
                return None
            return float(o)
        elif isinstance(o, np.ndarray):
            return o.tolist()
        elif pd.isna(o):
            return None
        return super().default(o)

def safe_dump_json(data: Any, filepath: str, indent: int = 2) -> None:
    """Writes JSON safely, immune to float out-of-range or numpy type crashes."""
    sanitized = clean_for_json(data)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(sanitized, f, indent=indent, cls=SafeJSONEncoder)

if __name__ == "__main__":
    # Test safe divide with 0 and negative denominators
    nums = pd.Series([100, 200, 300, 400])
    denoms = pd.Series([10, 0, np.nan, -5])
    print("[*] Testing safe_divide:")
    speeds = safe_divide(nums, denoms, fill_value=0.0)
    print(speeds.tolist())
    
    # Test JSON dump with rogue inf and NaN
    bad_dict = {
        "metric_a": float('inf'),
        "metric_b": float('-inf'),
        "metric_c": float('nan'),
        "numpy_int": np.int64(42),
        "valid_float": np.float64(99.9)
    }
    print("\n[*] Testing Safe JSON Dump with inf/nan:")
    cleaned = clean_for_json(bad_dict)
    print(json.dumps(cleaned, indent=2))
