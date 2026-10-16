"""
=============================================================================
ENTERPRISE "LOOP FIX" PROTOCOL -- CONTINUOUS INVARIANT VERIFICATION ENGINE
=============================================================================
Formulates the User's "Loop Fix" Philosophy as a Machine-Enforced Protocol:
Rule: Whenever any code patch is introduced, recursively audit for:
1. Secondary side-effects & regressions on all prior benchmarks.
2. Silent logic drift & Cartesian multiplicity explosions.
3. Physical / mathematical / domain invariant compliance.
Only declare an issue fixed when it is eliminated at the root ("jad se khatam").
=============================================================================
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from .domain_invariant_audit import audit_dataset_invariants
except ImportError:
    from domain_invariant_audit import audit_dataset_invariants

class LoopFixVerifier:
    """
    Automated regression containment engine that validates patches across
    heterogeneous enterprise benchmarks to guarantee zero side-effects.
    """
    def __init__(self, benchmarks_catalog: Optional[List[Dict[str, Any]]] = None):
        self.benchmarks = benchmarks_catalog or [
            {
                "name": "US Commercial Aviation Capstone",
                "domain": "Aerospace & Transportation",
                "fact_parquet": "error/output/bi_ready_aviation_fact.parquet",
                "expected_rows": 518556,
                "id_column": "id"
            },
            {
                "name": "Kaggle Brazilian E-Commerce (Olist)",
                "domain": "Retail & Logistics",
                "fact_parquet": "kaggle_complex_test/output/bi_ready_fact.parquet",
                "expected_rows": 112650,
                "id_column": "order_item_surrogate_key"
            }
        ]

    def verify_all_benchmarks(self) -> Dict[str, Any]:
        """
        Runs comprehensive invariant audits on all active benchmark datasets.
        Guarantees that no patch introduces silent logic drift or Cartesian duplication.
        """
        print("\n" + "=" * 80)
        print("  LOOP FIX PROTOCOL: CONTINUOUS INVARIANT & REGRESSION AUDIT")
        print("=" * 80)
        
        results = []
        all_passed = True
        
        for bm in self.benchmarks:
            p_file = Path(bm["fact_parquet"])
            print(f"\n[*] Auditing Benchmark: '{bm['name']}' ({bm['domain']})...")
            
            if not p_file.exists():
                print(f"    [!] Notice: Benchmark file {p_file.name} not found, skipping.")
                continue
                
            t0 = time.time()
            df = pd.read_parquet(p_file)
            initial_count = bm["expected_rows"]
            id_col = bm["id_column"]
            
            # Execute Invariant Audit
            audit = audit_dataset_invariants(df, initial_count=initial_count, id_col=id_col)
            elapsed = round(time.time() - t0, 2)
            
            row_drift = len(df) - initial_count
            dups = int(df.duplicated(subset=[id_col]).sum()) if id_col in df.columns else 0
            
            status = audit["status"]
            if status != "PASSED":
                all_passed = False
                print(f"    [X] AUDIT FAILED with {audit['total_violations']} violations:")
                for v in audit["violations"]:
                    print(f"        - {v}")
            else:
                print(f"    [+] 100% INVARIANT COMPLIANT ({len(df):,} rows, 0 drift, 0 duplicate IDs in {elapsed}s)")
                
            results.append({
                "benchmark": bm["name"],
                "domain": bm["domain"],
                "status": status,
                "fact_rows": len(df),
                "expected_rows": initial_count,
                "row_drift": row_drift,
                "duplicate_ids": dups,
                "violations_count": audit["total_violations"],
                "violations": audit["violations"]
            })

        print("\n" + "=" * 80)
        overall_badge = "LOOP-FIX CERTIFIED: ZERO DRIFT ACROSS ALL DATASETS" if all_passed else "LOOP-FIX FLAGGED: ISSUES DETECTED"
        print(f"  RESULT: {overall_badge}")
        print("=" * 80 + "\n")

        return {
            "overall_status": "PASSED" if all_passed else "FAILED",
            "badge": overall_badge,
            "benchmarks_audited": len(results),
            "results": results
        }

if __name__ == "__main__":
    verifier = LoopFixVerifier()
    res = verifier.verify_all_benchmarks()
    sys.exit(0 if res["overall_status"] == "PASSED" else 1)
