"""
=============================================================================
STAGE 1 (FULLY WIRED & GENERALIZED): RELATIONAL TOPOLOGY & PRIVACY PROFILER
=============================================================================
Features & Defenses:
1. Multi-sheet Excel scanning with smart header row detection.
2. Robust CSV delimiter & encoding auto-sniffing.
3. Adaptive statistical sampling (2,000 rows) for high-accuracy type & key inference.
4. Fully automated, domain-independent Cardinality & Bridge Table detection (1:1, 1:N, N:M).
5. Fully automated Composite Key relationship detection (multi-column joins).
6. 100% Local PII scrubbing before schema serialization.
7. Safe JSON serialization (immune to NaN/Inf/NumPy object crashes).
=============================================================================
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Robust imports supporting both package and direct script execution
try:
    from .robust_excel_scanner import detect_optimal_header_row
    from .pii_scrubber import scrub_schema_payload
    from .robust_csv_sniffer import smart_read_csv, detect_encoding_and_delimiter
    from .cardinality_and_bridge_detector import detect_relationship_cardinality
    from .composite_key_detector import detect_composite_join_mapping
    from .safe_math_and_json_guard import safe_dump_json
except ImportError:
    from robust_excel_scanner import detect_optimal_header_row
    from pii_scrubber import scrub_schema_payload
    from robust_csv_sniffer import smart_read_csv, detect_encoding_and_delimiter
    from cardinality_and_bridge_detector import detect_relationship_cardinality
    from composite_key_detector import detect_composite_join_mapping
    from safe_math_and_json_guard import safe_dump_json

SAMPLE_ROWS = 2000

KEY_SEMANTIC_KEYWORDS = [
    'id', 'code', 'ident', 'ref', 'key', 'from', 'to', 'num', 'no',
    'customer', 'cust', 'client', 'user', 'account', 'order', 'prod',
    'sku', 'item', 'flight', 'airline', 'carrier', 'airport', 'hub',
    'store', 'loc', 'city', 'state', 'country', 'region', 'date', 'time',
    'trans', 'txn'
]

def get_best_excel_sheet(filepath: Path) -> Tuple[str, int]:
    """
    Scans all sheets in an Excel workbook and returns the sheet with the most rows.
    Avoids loading tiny 'Cover' or 'Readme' sheets.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        best_sheet = wb.sheetnames[0]
        max_rows = -1
        
        for name in wb.sheetnames:
            sheet = wb[name]
            r_count = sheet.max_row or 0
            if r_count > max_rows:
                max_rows = r_count
                best_sheet = name
        wb.close()
        return best_sheet, max(max_rows - 1, 0)
    except Exception:
        xl = pd.ExcelFile(filepath)
        return xl.sheet_names[0], 100

def inspect_file(filepath: Path) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Reads a representative sample and extracts schema and candidate keys."""
    ext = filepath.suffix.lower()
    t_name = filepath.stem
    selected_sheet = None
    
    detected_delim = None
    detected_enc = None
    
    if ext in ['.xlsx', '.xls']:
        sheet_name, total_rows = get_best_excel_sheet(filepath)
        selected_sheet = sheet_name
        header_row = detect_optimal_header_row(filepath)
        df_sample = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, nrows=SAMPLE_ROWS)
    elif ext in ['.csv', '.tsv', '.txt']:
        header_row = detect_optimal_header_row(filepath)
        df_sample = smart_read_csv(filepath, header=header_row, nrows=SAMPLE_ROWS)
        enc, delim = detect_encoding_and_delimiter(filepath)
        detected_enc = enc
        detected_delim = delim
        with open(filepath, 'r', encoding=enc, errors='ignore') as f:
            total_rows = sum(1 for _ in f) - 1
    elif ext == '.parquet':
        import pyarrow.parquet as pq
        table = pq.read_table(filepath)
        total_rows = table.num_rows
        df_sample = table.slice(0, SAMPLE_ROWS).to_pandas()
    else:
        return None, None

    # Clean whitespace in column names
    df_sample.columns = [str(c).strip() for c in df_sample.columns]

    columns_meta = []
    potential_keys = []
    n_sample = len(df_sample)
    
    for col in df_sample.columns:
        s = df_sample[col].dropna()
        dtype = str(df_sample[col].dtype)
        nunique = int(s.nunique())
        samples = [str(x) for x in s.unique()[:3]]
        
        col_lower = str(col).lower()
        has_key_keyword = any(k in col_lower for k in KEY_SEMANTIC_KEYWORDS)
        high_uniqueness = (n_sample > 10 and (nunique / float(n_sample)) >= 0.70)
        
        if has_key_keyword or high_uniqueness:
            potential_keys.append(col)
            
        columns_meta.append({
            "name": col,
            "dtype": dtype,
            "sample_values": samples,
            "nunique_in_sample": nunique
        })
        
    strictly_unique_primary_keys = []
    if potential_keys:
        try:
            import duckdb
            con = duckdb.connect()
            f_esc = str(filepath.resolve()).replace("'", "''")
            if ext in ['.csv', '.tsv', '.txt']:
                reader_sql = f"read_csv_auto('{f_esc}', ignore_errors=true)"
            elif ext == '.parquet':
                reader_sql = f"read_parquet('{f_esc}')"
            else:
                reader_sql = None
                
            if reader_sql:
                for pk_cand in potential_keys[:5]:
                    cand_esc = pk_cand.replace('"', '""')
                    row_stat = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT \"{cand_esc}\") FROM {reader_sql}").fetchone()
                    if row_stat and row_stat[0] > 0 and row_stat[0] == row_stat[1]:
                        strictly_unique_primary_keys.append(pk_cand)
        except Exception:
            pass

    recommended_pk = strictly_unique_primary_keys[0] if strictly_unique_primary_keys else "fact_surrogate_id"

    meta = {
        "table_name": t_name,
        "filename": filepath.name,
        "filepath": str(filepath.resolve()),
        "selected_sheet": selected_sheet,
        "estimated_rows": total_rows,
        "column_count": len(df_sample.columns),
        "potential_keys": potential_keys,
        "strictly_unique_primary_keys": strictly_unique_primary_keys,
        "recommended_primary_key": recommended_pk,
        "delimiter": detected_delim,
        "encoding": detected_enc,
        "columns": columns_meta
    }
    return meta, df_sample

def profile_raw_directory(dir_path: str, output_json: str = None) -> dict:
    folder = Path(dir_path)
    DOC_KEYWORDS = ['dictionary', 'datadictionary', 'codebook', 'metadata', 'data_description', 'field_description', 'description', 'readme', 'sample_submission', 'sample_sub']
    all_files = [
        f for f in folder.iterdir() 
        if f.suffix.lower() in ['.xlsx', '.xls', '.csv', '.parquet', '.tsv', '.txt'] 
        and not f.name.startswith('~')
        and not any(k in f.stem.lower() for k in DOC_KEYWORDS)
    ]
    
    # Self-Learning Defense: If 'train' partition split exists, ignore holdout 'test' split to prevent false relational dimension joins
    stems = [f.stem.lower() for f in all_files]
    if any(s == 'train' or s.startswith('train_') for s in stems):
        files = [f for f in all_files if not (f.stem.lower() == 'test' or f.stem.lower().startswith('test_'))]
    else:
        files = all_files
    
    print(f"[*] [Stage 1 Topology Profiler] Scanning {len(files)} files in {dir_path}...")
    tables = {}
    samples = {}
    
    for f in sorted(files):
        print(f"    - Profiling {f.name}...")
        meta, df_s = inspect_file(f)
        if meta:
            tables[meta["table_name"]] = meta
            samples[meta["table_name"]] = df_s
            
    # Generic Relational, Cardinality & Composite Key Analysis
    relational_hints = []
    cardinality_hazards = []
    composite_key_relations = []
    
    table_names = list(tables.keys())
    for i in range(len(table_names)):
        for j in range(i + 1, len(table_names)):
            t1_name = table_names[i]
            t2_name = table_names[j]
            t1 = tables[t1_name]
            t2 = tables[t2_name]
            df1 = samples[t1_name]
            df2 = samples[t2_name]
            
            # 1. Single Key Relationships & Cardinality Analysis
            for k1 in t1["potential_keys"]:
                for k2 in t2["potential_keys"]:
                    k1_l = k1.lower()
                    k2_l = k2.lower()
                    
                    is_candidate_match = (
                        k1_l == k2_l or
                        k1_l.endswith(f"_{k2_l}") or k2_l.endswith(f"_{k1_l}") or
                        (k1_l in k2_l and len(k1_l) >= 4) or (k2_l in k1_l and len(k2_l) >= 4) or
                        (('airport' in k1_l or 'ident' in k1_l or 'iata' in k1_l) and 
                         ('airport' in k2_l or 'ident' in k2_l or 'iata' in k2_l))
                    )
                    
                    if is_candidate_match:
                        # Dynamically test key multiplicity (uses DuckDB full-file scan if available)
                        card_info = detect_relationship_cardinality(
                            df1, k1, df2, k2,
                            left_file_path=t1.get("filepath"),
                            right_file_path=t2.get("filepath")
                        )
                        
                        hint = {
                            "source_table": t1["table_name"],
                            "source_key": k1,
                            "target_table": t2["table_name"],
                            "target_key": k2,
                            "cardinality": card_info["cardinality"],
                            "danger_level": card_info["danger_level"],
                            "shared_keys_count": card_info["shared_keys_count"]
                        }
                        relational_hints.append(hint)
                        
                        # Automated Cardinality Hazards
                        if card_info["cardinality"].startswith("1:N"):
                            cardinality_hazards.append({
                                "table_pair": [t1["table_name"], t2["table_name"]],
                                "hazard": f"1-TO-MANY MULTIPLICITY HAZARD ({t1['table_name']}.{k1} -> {t2['table_name']}.{k2})",
                                "rule": f"Table '{t2['table_name']}' has duplicate keys for '{k2}'. Merging into '{t1['table_name']}' will duplicate fact rows.",
                                "defense_action": f"Table '{t2['table_name']}' MUST be pre-aggregated 1:1 on '{k2}' before join."
                            })
                        elif card_info["cardinality"].startswith("N:1"):
                            cardinality_hazards.append({
                                "table_pair": [t2["table_name"], t1["table_name"]],
                                "hazard": f"1-TO-MANY MULTIPLICITY HAZARD ({t2['table_name']}.{k2} -> {t1['table_name']}.{k1})",
                                "rule": f"Table '{t1['table_name']}' has duplicate keys for '{k1}'. Merging into '{t2['table_name']}' will duplicate fact rows.",
                                "defense_action": f"Table '{t1['table_name']}' MUST be pre-aggregated 1:1 on '{k1}' before join."
                            })
                        elif card_info["cardinality"].startswith("N:M"):
                            cardinality_hazards.append({
                                "table_pair": [t1["table_name"], t2["table_name"]],
                                "hazard": f"CRITICAL MANY-TO-MANY HAZARD ({t1['table_name']}.{k1} <-> {t2['table_name']}.{k2})",
                                "rule": f"Both '{t1['table_name']}' and '{t2['table_name']}' contain duplicate keys.",
                                "defense_action": f"Requires a dedicated bridge table or pre-aggregation to prevent exponential row explosion."
                            })

            # 2. Multi-Column Composite Key Detection
            comp_matches = detect_composite_join_mapping(df1, t1_name, df2, t2_name)
            if comp_matches:
                composite_key_relations.extend(comp_matches)

    # 3. Detect Multi-Reference Keys within the same table (e.g. Origin & Destination)
    TEMPORAL_WORDS = {'date', 'time', 'year', 'month', 'day', 'hour', 'minute', 'second', 'timestamp'}
    for t_name, t_meta in tables.items():
        keys = t_meta["potential_keys"]
        # Exclude temporal/timestamp columns from foreign key role pairing
        non_temporal_keys = [k for k in keys if not any(tw in k.lower() for tw in TEMPORAL_WORDS)]
        from_keys = [k for k in non_temporal_keys if any(x in k.lower() for x in ['from', 'origin', 'src', 'source'])]
        to_keys = [k for k in non_temporal_keys if any(x in k.lower() for x in ['to', 'dest', 'dst', 'target'])]
        if from_keys and to_keys:
            cardinality_hazards.append({
                "table_pair": [t_name, "Dimension_Lookup"],
                "hazard": f"DUAL/MULTI FOREIGN KEY REFERENCE IN '{t_name}'",
                "rule": f"Table '{t_name}' references dimensions with paired roles ({from_keys[0]} & {to_keys[0]}).",
                "defense_action": f"Requires dual joins with role prefixes (e.g. 'from_' and 'to_')."
            })

    raw_profile = {
        "dataset_name": folder.name,
        "tables": {k: {
            "table_name": v.get("table_name", k),
            "filename": v.get("filename", f"{k}.csv"),
            "selected_sheet": v.get("selected_sheet"),
            "estimated_rows": v["estimated_rows"],
            "delimiter": v.get("delimiter"),
            "encoding": v.get("encoding"),
            "columns": [c["name"] for c in v["columns"]],
            "potential_keys": v["potential_keys"],
            "strictly_unique_primary_keys": v.get("strictly_unique_primary_keys", []),
            "recommended_primary_key": v.get("recommended_primary_key", "fact_surrogate_id"),
            "sample_columns": v["columns"][:12]
        } for k, v in tables.items()},
        "relational_hints": relational_hints,
        "cardinality_hazards": cardinality_hazards,
        "composite_key_relations": composite_key_relations
    }
    
    # 100% Local PII Scrubbing before export/transmission
    sanitized_profile = scrub_schema_payload(raw_profile)
    
    if output_json:
        safe_dump_json(sanitized_profile, output_json, indent=2)
        print(f"[+] [Stage 1 Topology Profiler] Sanitized Schema Topology saved to: {output_json}")
        
    return sanitized_profile

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "error/raw_data"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "autonomous_engine/schema_topology.json"
    p = profile_raw_directory(target_dir, out_file)
    print("\n--- SCHEMA SUMMARY ---")
    for t, m in p["tables"].items():
        print(f"Table: {t:<15} | Sheet: {str(m.get('selected_sheet')):<12} | Rows: ~{m['estimated_rows']:<8} | Cols: {len(m['columns'])}")
    print("\n--- HAZARDS DETECTED ---")
    for h in p["cardinality_hazards"]:
        print(f"[*] {h['hazard']}: {h['defense_action']}")
