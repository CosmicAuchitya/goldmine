"""
=============================================================================
ENTERPRISE ATOMIC WINDOWS I/O & FILE-LOCK RETRY ENGINE
=============================================================================
Defeats Weakness #4: Windows File-Locking Hazards (PermissionError: [WinError 32]).
Solves:
- 'The process cannot access the file because it is being used by another process'
- Race conditions when overwriting large Parquet and CSV files on Windows
Algorithm:
1. Writes to a process-isolated staging file (.tmp_{pid}_{ts}).
2. Invokes gc.collect() to explicitly release open file handles in current Python runtime.
3. Performs atomic os.replace() with exponential backoff retry loop.
=============================================================================
"""

import gc
import os
import sys
import time
from pathlib import Path
from typing import Callable, Any
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def atomic_file_operation(target_path: Path, write_fn: Callable[[Path], Any], max_retries: int = 5) -> None:
    """
    Executes a write operation atomically using a temp file and retries with backoff.
    """
    p = Path(target_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    
    tmp_path = p.with_name(f"{p.stem}_tmp_{os.getpid()}_{int(time.time()*1000)}{p.suffix}")
    
    # 1. Write to temporary staging file with auto-cleanup guard
    try:
        write_fn(tmp_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise e
    
    # 2. Release any Python-level lingering handles
    gc.collect()
    
    # 3. Atomically replace with backoff
    try:
        for attempt in range(1, max_retries + 1):
            try:
                os.replace(tmp_path, p)
                return
            except PermissionError as pe:
                if attempt == max_retries:
                    raise PermissionError(f"[WinError 32] Persistent file lock on {p} after {max_retries} attempts: {pe}")
                delay = 0.1 * (2 ** attempt)
                time.sleep(delay)
                gc.collect()
            except Exception as other_err:
                if attempt == max_retries:
                    raise other_err
                time.sleep(0.1 * attempt)
    finally:
        # Guarantee tmp_path is never left behind if not successfully replaced
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def atomic_to_parquet(df: pd.DataFrame, target_path: Path, **kwargs) -> None:
    """Safely writes Parquet on Windows with atomic swap and lock defense."""
    atomic_file_operation(Path(target_path), lambda tmp: df.to_parquet(tmp, index=False, **kwargs))

def atomic_to_csv(df: pd.DataFrame, target_path: Path, **kwargs) -> None:
    """Safely writes CSV on Windows with atomic swap and lock defense."""
    atomic_file_operation(Path(target_path), lambda tmp: df.to_csv(tmp, index=False, **kwargs))

def atomic_write_text(content: str, target_path: Path, encoding: str = 'utf-8') -> None:
    """Safely writes text/markdown on Windows with atomic swap and lock defense."""
    def _write(tmp):
        with open(tmp, 'w', encoding=encoding) as f:
            f.write(content)
    atomic_file_operation(Path(target_path), _write)

if __name__ == "__main__":
    test_p = Path("cache/test_data/atomic_test.parquet")
    df_test = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]})
    print(f"[*] Testing Atomic Windows I/O on: {test_p}...")
    atomic_to_parquet(df_test, test_p)
    print(f"[+] Successfully wrote {len(df_test)} rows via Atomic Windows I/O.")
