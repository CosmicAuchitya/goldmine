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
import re
import json
from pathlib import Path
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Robust imports supporting both package and direct script execution
try:
    from .robust_excel_scanner import detect_optimal_header_row, strip_accounting_summary_rows
    from .pii_scrubber import scrub_schema_payload
    from .robust_csv_sniffer import smart_read_csv, detect_encoding_and_delimiter
    from .cardinality_and_bridge_detector import detect_relationship_cardinality
    from .composite_key_detector import detect_composite_join_mapping
    from .safe_math_and_json_guard import safe_dump_json
    from .target_resolver import is_index_artifact
except ImportError:
    from robust_excel_scanner import detect_optimal_header_row, strip_accounting_summary_rows
    from pii_scrubber import scrub_schema_payload
    from robust_csv_sniffer import smart_read_csv, detect_encoding_and_delimiter
    from cardinality_and_bridge_detector import detect_relationship_cardinality
    from composite_key_detector import detect_composite_join_mapping
    from safe_math_and_json_guard import safe_dump_json
    try:
        from target_resolver import is_index_artifact
    except ImportError:
        def is_index_artifact(col_name: str, series=None) -> bool:
            c = str(col_name).strip().lower()
            return bool(re.match(r'^(?:unnamed\s*:?\s*\d*|index|level_\d+|row_?(?:id|num|number)|_surrogate_id_key)$', c))

SAMPLE_ROWS = 2000

KEY_SEMANTIC_KEYWORDS = [
    'id', 'code', 'ident', 'ref', 'key', 'from', 'to', 'num', 'no',
    'customer', 'cust', 'client', 'user', 'account', 'order', 'prod',
    'sku', 'item', 'flight', 'airline', 'carrier', 'airport', 'hub',
    'store', 'loc', 'city', 'state', 'country', 'region', 'date', 'time',
    'trans', 'txn', 'channel', 'source', 'utm', 'awb', 'waybill',
    'invoice', 'bill', 'voucher', 'category', 'vendor', 'supplier',
    'warehouse', 'courier', 'branch'
]


def unpack_multisheet_excel_workbooks(folder: Path) -> set:
    """
    If an .xlsx / .xls workbook contains 2 or more valid data sheets (e.g., Orders,
    Shiprocket_RTO, Meta_Ads in a single file), unpacks each sheet into its own CSV
    `<workbook_stem>__<sheet_name>.csv` (applying per-sheet optimal header detection
    and summary row stripping) and returns the set of unpacked container .xlsx Paths.
    """
    unpacked_containers = set()
    skip_sheet_words = (
        'readme', 'cover', 'instruction', 'dictionary', 'metadata', 'notes',
        'summary_only', 'exec_summary', 'executive_summary', 'pivot', 'dashboard', 'overview', 'kpi', 'totals', 'rollup', 'chart'
    )
    for f in list(folder.iterdir()):
        if f.suffix.lower() not in ('.xlsx', '.xls') or f.name.startswith('~'):
            continue
        try:
            xl = pd.ExcelFile(f)
            if len(xl.sheet_names) < 2:
                continue
            valid_sheets = []
            for sname in xl.sheet_names:
                if any(w in sname.lower() for w in skip_sheet_words):
                    continue
                h_idx = detect_optimal_header_row(f, sheet_name=sname)
                df_tab = pd.read_excel(f, sheet_name=sname, header=h_idx)
                df_tab.columns = [str(c).strip() for c in df_tab.columns]
                df_tab = strip_accounting_summary_rows(df_tab)
                # Drop completely empty rows/columns
                df_tab = df_tab.dropna(how='all').dropna(axis=1, how='all')
                if len(df_tab) >= 2 and len(df_tab.columns) >= 2:
                    valid_sheets.append((sname, df_tab))
            if len(valid_sheets) >= 2:
                for sname, df_tab in valid_sheets:
                    clean_s = re.sub(r'[^A-Za-z0-9_]+', '_', sname.strip()).strip('_')
                    out_csv = folder / f"{f.stem}__{clean_s}.csv"
                    df_tab.to_csv(out_csv, index=False, encoding='utf-8')
                unpacked_containers.add(f.resolve())
                print(f"    [+] Auto-unpacked multi-tab Excel workbook '{f.name}' into {len(valid_sheets)} relational sheets.")
        except Exception as e:
            print(f"    [!] Warning inspecting multi-tab Excel '{f.name}': {e}")
    return unpacked_containers


def _has_strong_value_overlap(s1: pd.Series, s2: pd.Series, min_overlap: float = 0.50) -> bool:
    """
    Detects physical join-key relationship when column names differ completely
    (e.g., `order_id` vs `client_ref_no` or `acquisition_channel` vs `utm_source`)
    by measuring normalized value containment / Jaccard overlap >= 50%.
    Strictly rejects boolean {0,1,YES,NO} and small-integer measure columns.
    """
    if s1 is None or s2 is None:
        return False
    bool_tokens = {'0', '1', '0.0', '1.0', 'TRUE', 'FALSE', 'YES', 'NO', 'Y', 'N', 'NAN', 'NONE', 'NULL', ''}
    vals1 = {str(x).strip().upper() for x in s1.dropna().unique()[:500] if str(x).strip()} - bool_tokens
    vals2 = {str(x).strip().upper() for x in s2.dropna().unique()[:500] if str(x).strip()} - bool_tokens
    if len(vals1) < 2 or len(vals2) < 2:
        return False
    shared = vals1 & vals2
    if len(shared) < 2:
        return False
    # Reject plain small numbers (< 4 digits) so quantities/days/ratings never false-match
    all_plain_num = all(bool(re.match(r'^-?\d+(?:\.\d+)?$', v)) for v in shared)
    if all_plain_num:
        min_digits = min(len(v.split('.')[0].lstrip('-')) for v in shared)
        if min_digits < 4 or len(shared) < 10:
            return False
    denom = float(min(len(vals1), len(vals2)))
    return (len(shared) / denom) >= min_overlap

def get_best_excel_sheet(filepath: Path) -> Tuple[str, int]:
    """
    Scans all sheets in an Excel workbook and returns the sheet with the most rows.
    Avoids loading tiny 'Cover' or 'Readme' sheets.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        skip_words = ('readme', 'cover', 'instruction', 'dictionary', 'metadata', 'notes', 'summary_only')
        best_sheet = wb.sheetnames[0]
        max_rows = -1
        best_score = -1
        for name in wb.sheetnames:
            sheet = wb[name]
            r_count = int(sheet.max_row or 0)
            c_count = int(sheet.max_column or 0)
            is_cover = any(w in name.lower() for w in skip_words)
            score = (r_count * max(c_count, 1)) if not is_cover else -1
            if score > best_score:
                best_score = score
                max_rows = r_count
                best_sheet = name
        if best_score <= 0:
            for name in wb.sheetnames:
                r_count = int(wb[name].max_row or 0)
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
        header_row = detect_optimal_header_row(filepath, sheet_name=sheet_name)
        df_sample = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row, nrows=SAMPLE_ROWS)
        total_rows = max(0, total_rows - header_row)
        if len(df_sample) < SAMPLE_ROWS:
            total_rows = len(df_sample)
    elif ext in ['.csv', '.tsv', '.txt']:
        header_row = detect_optimal_header_row(filepath)
        df_sample = smart_read_csv(filepath, header=header_row, nrows=SAMPLE_ROWS)
        enc, delim = detect_encoding_and_delimiter(filepath)
        detected_enc = enc
        detected_delim = delim
        with open(filepath, 'r', encoding=enc, errors='ignore') as f:
            raw_lines = sum(1 for _ in f)
        total_rows = max(0, raw_lines - 1 - header_row)
    elif ext == '.parquet':
        import pyarrow.parquet as pq
        table = pq.read_table(filepath)
        total_rows = table.num_rows
        df_sample = table.slice(0, SAMPLE_ROWS).to_pandas()
    elif ext == '.pdf':
        try:
            from .tally_pdf_ingestion import extract_table_from_pdf
        except ImportError:
            from tally_pdf_ingestion import extract_table_from_pdf
        df_full_pdf = extract_table_from_pdf(filepath)
        total_rows = len(df_full_pdf)
        df_sample = df_full_pdf.head(SAMPLE_ROWS)
    else:
        return None, None

    # Clean whitespace in column names
    df_sample.columns = [str(c).strip() for c in df_sample.columns]
    # Flatten hierarchical Tally/Marg grouped ledgers & strip mid-sheet subtotals
    try:
        try:
            from .tally_pdf_ingestion import flatten_grouped_accounting_ledger
        except ImportError:
            from tally_pdf_ingestion import flatten_grouped_accounting_ledger
        pre_flat_len = len(df_sample)
        df_sample, _flat_meta = flatten_grouped_accounting_ledger(df_sample)
        dropped_flat = pre_flat_len - len(df_sample)
        if dropped_flat > 0:
            total_rows = max(0, total_rows - dropped_flat)
    except Exception:
        pass
    # Strip summary footer rows (e.g. Tally / Grand Total rows) and reconcile total row count
    cleaned_sample = strip_accounting_summary_rows(df_sample)
    dropped_summary_count = len(df_sample) - len(cleaned_sample)
    if dropped_summary_count > 0:
        total_rows = max(0, total_rows - dropped_summary_count)
        df_sample = cleaned_sample

    columns_meta = []
    potential_keys = []
    n_sample = len(df_sample)

    for col in df_sample.columns:
        s = df_sample[col].dropna()
        dtype = str(df_sample[col].dtype)
        nunique = int(s.nunique())
        samples = [str(x) for x in s.unique()[:3]]
        
        BAD_KEY_KEYWORDS = ['link', 'url', 'poster', 'image', 'photo', 'overview', 'description', 'desc', 'summary', 'text', 'comment', 'review', 'svg', 'png', 'jpg', 'jpeg', 'body', 'content', 'path', 'href']
        col_lower = str(col).lower()
        has_bad_keyword = any(b in col_lower for b in BAD_KEY_KEYWORDS)
        is_url_or_long_text = any(str(x).startswith(('http://', 'https://', '//', 'www.')) or len(str(x)) > 60 for x in samples)
        is_idx = is_index_artifact(col)
        
        has_key_keyword = any(k in col_lower for k in KEY_SEMANTIC_KEYWORDS) and not has_bad_keyword and not is_idx
        high_uniqueness = (n_sample > 10 and (nunique / float(n_sample)) >= 0.70) and not has_bad_keyword and not is_url_or_long_text and not is_idx
        
        if has_key_keyword or high_uniqueness:
            potential_keys.append(col)
            
        columns_meta.append({
            "name": col,
            "dtype": dtype,
            "sample_values": samples,
            "nunique_in_sample": nunique,
            "is_index_artifact": is_idx
        })
        
    strictly_unique_primary_keys = []
    if potential_keys:
        con = None
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
                for pk_cand in potential_keys[:10]:
                    cand_esc = pk_cand.replace('"', '""')
                    row_stat = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT \"{cand_esc}\") FROM {reader_sql}").fetchone()
                    if row_stat and row_stat[0] > 0 and row_stat[0] == row_stat[1]:
                        strictly_unique_primary_keys.append(pk_cand)
        except Exception:
            pass
        finally:
            if con is not None:
                try:
                    con.close()
                except Exception:
                    pass

    recommended_pk = "fact_surrogate_id"
    if strictly_unique_primary_keys:
        non_idx_keys = [c for c in strictly_unique_primary_keys if not is_index_artifact(c)]
        true_ids = [c for c in non_idx_keys if c.lower() in ['id', 'ident', 'uuid', 'key'] or c.lower().endswith(('_id', '_key', '_uuid'))]
        code_ids = [c for c in non_idx_keys if c.lower().endswith(('_code', '_num', '_no'))]
        clean_keys = [c for c in non_idx_keys if not any(b in c.lower() for b in BAD_KEY_KEYWORDS)]
        if true_ids:
            recommended_pk = true_ids[0]
        elif code_ids:
            recommended_pk = code_ids[0]
        elif clean_keys:
            recommended_pk = clean_keys[0]

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
    unpacked_xlsx = unpack_multisheet_excel_workbooks(folder)
    DOC_KEYWORDS = ['dictionary', 'datadictionary', 'codebook', 'metadata', 'data_description', 'field_description', 'description', 'readme', 'sample_submission', 'sample_sub']
    all_files = [
        f for f in folder.iterdir() 
        if f.suffix.lower() in ['.xlsx', '.xls', '.csv', '.parquet', '.tsv', '.txt', '.pdf'] 
        and f.resolve() not in unpacked_xlsx
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
                         ('airport' in k2_l or 'ident' in k2_l or 'iata' in k2_l)) or
                        _has_strong_value_overlap(df1[k1], df2[k2], min_overlap=0.50)
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
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "raw_data"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "autonomous_engine/schema_topology.json"
    p = profile_raw_directory(target_dir, out_file)
    print("\n--- SCHEMA SUMMARY ---")
    for t, m in p["tables"].items():
        print(f"Table: {t:<15} | Sheet: {str(m.get('selected_sheet')):<12} | Rows: ~{m['estimated_rows']:<8} | Cols: {len(m['columns'])}")
    print("\n--- HAZARDS DETECTED ---")
    for h in p["cardinality_hazards"]:
        print(f"[*] {h['hazard']}: {h['defense_action']}")
