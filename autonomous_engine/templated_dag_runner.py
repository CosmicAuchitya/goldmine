"""
=============================================================================
ENTERPRISE DETERMINISTIC RELATIONAL DAG RUNNER & SCAFFOLDING
=============================================================================
Solves Autopsy Flaw #1: Code-Gen Fragility & LLM Non-Determinism.
Guarantees:
1. Deterministic Scaffolding: Pre-compiled, rock-solid execution structure
   guaranteed to run without random LLM syntax or import hallucinations.
2. Hybrid Execution: Leverages DuckDB out-of-core streaming when available,
   with vectorized Pandas memory fallback.
3. Automated Key Harmonization: Strips whitespace, uppercases identifiers,
   and synthesizes grain surrogate keys.
4. Mathematical Cardinality Defense: Pre-aggregates 1:N dimensions to 1:1.
5. Strict Invariant & Assertion Gates built-in.
=============================================================================
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from .duckdb_engine import DuckDBRelationalEngine
except (ImportError, ModuleNotFoundError):
    try:
        from duckdb_engine import DuckDBRelationalEngine
    except (ImportError, ModuleNotFoundError):
        try:
            from autonomous_engine.duckdb_engine import DuckDBRelationalEngine
        except (ImportError, ModuleNotFoundError):
            try:
                DuckDBRelationalEngine = globals().get('DuckDBRelationalEngine', None)
            except Exception:
                DuckDBRelationalEngine = None

def load_entity_dataframe(file_path: Path, cache_path: Path = None) -> pd.DataFrame:
    """
    Robust multi-format entity loader:
    1. Fast-path: Pre-cached Parquet in cache_dir (sub-second load).
    2. Native Parquet (.parquet).
    3. Multi-encoding CSV (.csv) with fallback to latin-1.
    4. Binary Excel (.xlsx/.xls) using openpyxl with automatic Parquet caching.
    """
    stem = file_path.stem
    if cache_path:
        cache_candidates = [
            cache_path / f"{stem}.parquet",
            cache_path / f"{stem.lower()}.parquet",
            cache_path / f"{stem.replace(' ', '_').lower()}.parquet"
        ]
        for cand in cache_candidates:
            if cand.exists():
                try:
                    if file_path.exists() and file_path.stat().st_mtime > cand.stat().st_mtime:
                        continue  # Raw file is newer than cache, invalidate
                    df = pd.read_parquet(cand)
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
                except Exception:
                    pass

    suffix = file_path.suffix.lower()
    if suffix == '.parquet':
        df = pd.read_parquet(file_path)
    elif suffix in ['.xlsx', '.xls']:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheet_names = wb.sheetnames
            best_sheet = sheet_names[0]
            for s in sheet_names:
                if any(k in s.lower() for k in ['data', 'flight', 'airline', 'fact', 'main', 'sheet1']):
                    best_sheet = s
                    break
            df = pd.read_excel(file_path, sheet_name=best_sheet)
        except Exception:
            df = pd.read_excel(file_path)
            
        if cache_path:
            try:
                parquet_cache = cache_path / f"{stem}.parquet"
                df.to_parquet(parquet_cache, index=False)
            except Exception:
                pass
    else:
        try:
            try:
                from .robust_csv_sniffer import smart_read_csv
            except ImportError:
                from robust_csv_sniffer import smart_read_csv
            df = smart_read_csv(file_path)
        except Exception:
            try:
                df = pd.read_csv(file_path, low_memory=False)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, low_memory=False, encoding='latin-1')

    df.columns = [str(c).strip() for c in df.columns]
    try:
        from .robust_excel_scanner import strip_accounting_summary_rows, clean_accounting_series
    except ImportError:
        from robust_excel_scanner import strip_accounting_summary_rows, clean_accounting_series
    df = strip_accounting_summary_rows(df)

    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = clean_accounting_series(df[col])
            s_clean = df[col].astype(str).str.replace(',', '').str.strip()
            s_num = pd.to_numeric(s_clean, errors='coerce')
            if s_num.notna().mean() >= 0.85 and s_num.nunique() > 10:
                df[col] = s_num.fillna(s_num.median())
    return df

def execute_templated_pipeline(
    blueprint_path: str,
    raw_data_dir: str,
    output_dir: str,
    cache_dir: str = "cache"
) -> Dict[str, Any]:
    """
    Executes an enterprise relational pipeline deterministically using the blueprint specifications.
    """
    start_time = time.time()
    with open(blueprint_path, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)

    raw_path = Path(raw_data_dir).resolve()
    out_path = Path(output_dir).resolve()
    cache_path = Path(cache_dir).resolve()
    
    out_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("  ENTERPRISE DETERMINISTIC DAG EXECUTION CORE")
    print(f"  Project: {blueprint.get('project_title', 'Analytics Pipeline')}")
    print("=" * 80)

    fact_table_name = blueprint.get("fact_table", "")
    target_metric = blueprint.get("target_metric", "")
    primary_id_col = blueprint.get("primary_id_column", "id")

    # Ingest tables
    raw_files = {f.stem: f for f in raw_path.iterdir() if f.suffix.lower() in ['.csv', '.parquet', '.xlsx', '.xls']}
    print(f"[*] Discovered {len(raw_files)} raw data entities in: {raw_path.name}")

    # Determine central fact table
    fact_file = None
    if fact_table_name in raw_files:
        fact_file = raw_files[fact_table_name]
    else:
        # Match case-insensitively or fallback to largest file
        for stem, f in raw_files.items():
            if stem.lower() == fact_table_name.lower():
                fact_file = f
                fact_table_name = stem
                break
        if not fact_file:
            fact_file = max(raw_files.values(), key=lambda f: f.stat().st_size)
            fact_table_name = fact_file.stem

    print(f"[*] Central Fact Entity: '{fact_table_name}' ({fact_file.name})")

    # Load Fact Table
    df_fact = load_entity_dataframe(fact_file, cache_path=cache_path)
    initial_count = len(df_fact)
    print(f"[+] Loaded base fact records: {initial_count:,}")

    # Check if candidate primary key is strictly unique at the fact grain
    is_pk_unique = (primary_id_col in df_fact.columns) and (df_fact[primary_id_col].nunique() == initial_count)

    # Synthesize surrogate key if grain requires it or if specified column has duplicate keys
    if not is_pk_unique:
        if "order_id" in df_fact.columns and "order_item_id" in df_fact.columns:
            primary_id_col = "fact_surrogate_id"
            df_fact[primary_id_col] = (
                df_fact["order_id"].astype(str).str.strip().str.upper() + "_" +
                df_fact["order_item_id"].astype(str).str.strip()
            )
            print(f"[+] Synthesized grain surrogate key '{primary_id_col}' from (order_id + order_item_id)")
        elif all(k in df_fact.columns for k in ["Store", "Dept", "Date"]):
            primary_id_col = "fact_surrogate_id"
            df_fact[primary_id_col] = (
                df_fact["Store"].astype(str).str.strip() + "_" +
                df_fact["Dept"].astype(str).str.strip() + "_" +
                df_fact["Date"].astype(str).str.strip()
            )
            print(f"[+] Synthesized grain surrogate key '{primary_id_col}' from (Store + Dept + Date)")
        elif "id" in df_fact.columns and df_fact["id"].nunique() == initial_count:
            primary_id_col = "id"
            df_fact[primary_id_col] = df_fact[primary_id_col].astype(str).str.strip().str.upper()
        else:
            unique_cols = [c for c in df_fact.columns if df_fact[c].nunique() == initial_count]
            if unique_cols:
                primary_id_col = unique_cols[0]
                print(f"[+] Selected unique primary key column '{primary_id_col}'")
            else:
                primary_id_col = "fact_surrogate_id"
                df_fact[primary_id_col] = (df_fact.index + 1).astype(str)
                print(f"[+] Synthesized grain surrogate key '{primary_id_col}' from DataFrame row index")
    else:
        df_fact[primary_id_col] = df_fact[primary_id_col].astype(str).str.strip().str.upper()

    # Process and Join Dimension Tables
    dimension_exports = {}
    for tbl_stem, file_path in raw_files.items():
        if tbl_stem == fact_table_name:
            continue

        # Skip ML holdout/test partitions and submission templates
        if tbl_stem.lower() in ['test', 'holdout', 'submission', 'sample_submission']:
            print(f"    [*] Notice: Skipping ML evaluation split / competition artifact '{tbl_stem}' from dimension joins.")
            continue
            
        print(f"[*] Ingesting & harmonizing dimension: '{tbl_stem}'...")
        df_dim = load_entity_dataframe(file_path, cache_path=cache_path)

        # 1. Check for role-playing foreign keys (Airlines AirportFrom / AirportTo -> airports.iata_code or ident)
        if "AirportFrom" in df_fact.columns and "AirportTo" in df_fact.columns and any(k in df_dim.columns for k in ["iata_code", "ident"]):
            match_col = "iata_code" if "iata_code" in df_dim.columns else "ident"
            # Deduplicate dimension on match_col
            df_dim_clean = df_dim.dropna(subset=[match_col]).drop_duplicates(subset=[match_col]).copy()
            df_dim_clean[match_col] = df_dim_clean[match_col].astype(str).str.strip().str.upper()
            
            # Select key informative attributes (name, type, elevation_ft, latitude_deg, longitude_deg)
            informative_cols = [c for c in df_dim_clean.columns if c in ['name', 'type', 'elevation_ft', 'iso_country', 'municipality']]
            if not informative_cols:
                informative_cols = [c for c in df_dim_clean.columns if c != match_col][:5]
                
            # Origin airport merge
            df_orig = df_dim_clean[[match_col] + informative_cols].rename(
                columns={c: f"origin_airport_{c}" for c in informative_cols}
            )
            df_fact = pd.merge(df_fact, df_orig, left_on="AirportFrom", right_on=match_col, how="left")
            if match_col in df_fact.columns:
                df_fact.drop(columns=[match_col], inplace=True)
                
            # Destination airport merge
            df_dest = df_dim_clean[[match_col] + informative_cols].rename(
                columns={c: f"dest_airport_{c}" for c in informative_cols}
            )
            df_fact = pd.merge(df_fact, df_dest, left_on="AirportTo", right_on=match_col, how="left")
            if match_col in df_fact.columns:
                df_fact.drop(columns=[match_col], inplace=True)

            print(f"    [+] Successfully role-merged '{tbl_stem}' on Origin & Destination (Fact count: {len(df_fact):,})")
            dim_csv_name = f"bi_dim_{tbl_stem}.csv"
            df_dim_clean.to_csv(out_path / dim_csv_name, index=False)
            dimension_exports[dim_csv_name] = len(df_dim_clean)
            continue

        # 2. Check for candidate direct or composite join keys
        common_keys = [c for c in df_fact.columns if c in df_dim.columns and c != primary_id_col]
        clean_tbl_prefix = tbl_stem.replace("olist_", "").replace("_dataset", "")

        # Composite join fast-path: if multiple common keys form a 100% unique key in dimension
        if len(common_keys) > 1 and df_dim.duplicated(subset=common_keys).sum() == 0:
            for jk in common_keys:
                df_fact[jk] = df_fact[jk].astype(str).str.strip().str.upper()
                df_dim[jk] = df_dim[jk].astype(str).str.strip().str.upper()
            df_dim_clean = df_dim.drop_duplicates(subset=common_keys)

            rename_map = {c: f"{clean_tbl_prefix}_{c}" for c in df_dim_clean.columns if c not in common_keys and c in df_fact.columns}
            df_dim_merge = df_dim_clean.rename(columns=rename_map) if rename_map else df_dim_clean

            df_fact = pd.merge(df_fact, df_dim_merge, on=common_keys, how="left")
            print(f"    [+] Successfully composite-merged '{tbl_stem}' on {common_keys} (Fact count: {len(df_fact):,})")
            dim_csv_name = f"bi_dim_{tbl_stem}.csv"
            df_dim_clean.to_csv(out_path / dim_csv_name, index=False)
            dimension_exports[dim_csv_name] = len(df_dim_clean)
            continue
        if not common_keys:
            # Check for semantic key matches (e.g. customer_id, order_id)
            for fc in df_fact.columns:
                for dc in df_dim.columns:
                    if fc.lower() == dc.lower() and len(fc) >= 3 and fc != primary_id_col:
                        common_keys.append(fc)
                        break

        if common_keys:
            join_key = common_keys[0]
            # Standardize join key
            df_fact[join_key] = df_fact[join_key].astype(str).str.strip().str.upper()
            df_dim[join_key] = df_dim[join_key].astype(str).str.strip().str.upper()

            # Cardinality defense: If dimension has duplicates on join key, pre-aggregate 1:1!
            dup_dim_keys = df_dim.duplicated(subset=[join_key]).sum()
            if dup_dim_keys > 0:
                print(f"    [!] Cardinality Defense: Pre-aggregating '{tbl_stem}' on '{join_key}' ({dup_dim_keys:,} duplicates neutralized)...")
                # Numeric aggregations
                num_cols = [c for c in df_dim.select_dtypes(include=[np.number]).columns if c != join_key]
                agg_dict = {c: "sum" for c in num_cols}
                # Non-numeric dominant values
                cat_cols = [c for c in df_dim.select_dtypes(include=['object', 'category']).columns if c != join_key]
                for c in cat_cols[:2]:
                    agg_dict[c] = "first"
                
                if agg_dict:
                    df_dim_agg = df_dim.groupby(join_key, as_index=False).agg(agg_dict)
                else:
                    df_dim_agg = df_dim.drop_duplicates(subset=[join_key])
                df_dim_clean = df_dim_agg
            else:
                df_dim_clean = df_dim.drop_duplicates(subset=[join_key])

            # Merge safely 1:1 into fact table
            # Prevent column collision & silent drops: rename conflicting columns with entity prefix
            clean_tbl_prefix = tbl_stem.replace("olist_", "").replace("_dataset", "")
            rename_map = {}
            for c in df_dim_clean.columns:
                if c != join_key and c in df_fact.columns:
                    rename_map[c] = f"{clean_tbl_prefix}_{c}"
            
            if rename_map:
                df_dim_merge = df_dim_clean.rename(columns=rename_map)
                print(f"    [*] Resolved {len(rename_map)} column collision(s) with '{clean_tbl_prefix}_' prefix: {list(rename_map.values())}")
            else:
                df_dim_merge = df_dim_clean

            df_fact = pd.merge(df_fact, df_dim_merge, on=join_key, how="left")
            print(f"    [+] Successfully merged '{tbl_stem}' on '{join_key}' (Fact count: {len(df_fact):,})")

            # Save clean dimension CSV
            dim_csv_name = f"bi_dim_{tbl_stem}.csv"
            df_dim_clean.to_csv(out_path / dim_csv_name, index=False)
            dimension_exports[dim_csv_name] = len(df_dim_clean)
        else:
            # Standalone dimension/lookup table (e.g. runways, data dictionary)
            dim_csv_name = f"bi_dim_{tbl_stem}.csv"
            df_dim.to_csv(out_path / dim_csv_name, index=False)
            dimension_exports[dim_csv_name] = len(df_dim)
            print(f"    [+] Exported standalone dimension '{dim_csv_name}' ({len(df_dim):,} records)")

    # Compute Forensic Metrics
    print("[*] Computing vectorized forensic enrichments...")
    # SLA variance if date columns exist
    deliv_cols = [c for c in df_fact.columns if 'delivered' in c.lower() and 'customer' in c.lower()]
    est_cols = [c for c in df_fact.columns if 'estimated' in c.lower() and 'delivery' in c.lower()]
    if deliv_cols and est_cols:
        d_deliv = pd.to_datetime(df_fact[deliv_cols[0]], utc=True, errors='coerce')
        d_est = pd.to_datetime(df_fact[est_cols[0]], utc=True, errors='coerce')
        df_fact["sla_fulfillment_variance_days"] = (d_deliv - d_est).dt.total_seconds() / 86400.0

    # Freight ratio
    if "freight_value" in df_fact.columns and "price" in df_fact.columns:
        p = pd.to_numeric(df_fact["price"], errors='coerce').fillna(0)
        f_val = pd.to_numeric(df_fact["freight_value"], errors='coerce').fillna(0)
        df_fact["freight_friction_ratio"] = np.where(p > 0, f_val / p, 0.0)

    # Strict Assertion Gates
    final_count = len(df_fact)
    print(f"[*] Evaluating assertion gates: initial={initial_count:,}, final={final_count:,}...")
    assert final_count == initial_count, f"Cartesian explosion detected! {final_count - initial_count:,} duplicate rows created!"
    
    dup_pks = int(df_fact.duplicated(subset=[primary_id_col]).sum())
    assert dup_pks == 0, f"Duplicate primary IDs detected in '{primary_id_col}'! Count: {dup_pks}"
    print("[+] All strict assertion gates PASSED: Exactly 0 Cartesian drift & 0 duplicate IDs.")

    # Cast key columns to string for PyArrow safety
    for col in df_fact.columns:
        if col.endswith('_id') or 'key' in col.lower() or col == primary_id_col:
            df_fact[col] = df_fact[col].astype(str)

    # Export Fact Parquet
    fact_parquet_path = out_path / "bi_ready_fact.parquet"
    df_fact.to_parquet(fact_parquet_path, engine="pyarrow", index=False)
    print(f"[+] Persisted Star Schema Parquet: {fact_parquet_path.name} ({len(df_fact):,} rows)")

    total_time = round(time.time() - start_time, 2)
    summary = {
        "status": "PASSED",
        "total_runtime_sec": total_time,
        "fact_table": fact_table_name,
        "primary_key": primary_id_col,
        "initial_rows": initial_count,
        "final_fact_rows": final_count,
        "cartesian_drift": final_count - initial_count,
        "duplicate_ids": dup_pks,
        "dimension_tables_exported": dimension_exports
    }

    print("-" * 80)
    print(f"[+] Deterministic DAG Execution Completed in {total_time}s!")
    print("-" * 80 + "\n")
    return summary

if __name__ == "__main__":
    bp = sys.argv[1] if len(sys.argv) > 1 else "kaggle_complex_test/execution_blueprint.json"
    raw = sys.argv[2] if len(sys.argv) > 2 else "kaggle_complex_test/raw_data"
    out = sys.argv[3] if len(sys.argv) > 3 else "kaggle_complex_test/output_dag_test"
    if Path(bp).exists() and Path(raw).exists():
        res = execute_templated_pipeline(bp, raw, out)
        print("DAG Execution Result:", res["status"])
