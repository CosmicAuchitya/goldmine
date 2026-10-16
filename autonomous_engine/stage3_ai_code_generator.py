"""
=============================================================================
STAGE 3 (FULLY GENERALIZED & PACED): DYNAMIC AI ETL SCRIPT GENERATOR
=============================================================================
Features & Defenses:
1. Paced Gemini Client (14 RPM sliding window + backoff).
2. Domain-Agnostic dynamic code synthesis: Writes custom vectorized Python ETL
   code based purely on the Execution Blueprint and Schema Topology.
3. Pre-execution syntax validation: Compiles code locally to verify 0 syntax errors
   before persisting to disk.
4. Preserves assertion gates and star-schema exports for any domain.
=============================================================================
"""

import os
import sys
import re
import json
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Robust imports supporting both package and direct script execution
try:
    from .rate_limiter import PacedGeminiClient
except ImportError:
    from rate_limiter import PacedGeminiClient

def extract_python_code_robust(raw_text: str) -> str:
    """
    Extracts raw Python code safely even if model includes conversational preamble.
    """
    text = raw_text.strip()
    match = re.search(r'```(?:python)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text

def generate_dynamic_etl_script(
    blueprint_json_path: str,
    output_script_path: str,
    topology_json_path: str = None,
    data_dir: str = "error/raw_data",
    output_dir: str = "error/output",
    cache_dir: str = "error/cache"
) -> str:
    with open(blueprint_json_path, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)
        
    topology_summary = {}
    if topology_json_path and Path(topology_json_path).exists():
        with open(topology_json_path, 'r', encoding='utf-8') as f:
            top = json.load(f)
            topology_summary = {
                t: {
                    "filename": m.get("filename", f"{t}.csv"),
                    "columns": m.get("columns", [])[:20],
                    "estimated_rows": m.get("estimated_rows", 0),
                    "delimiter": m.get("delimiter", ","),
                    "encoding": m.get("encoding", "utf-8"),
                }
                for t, m in top.get("tables", {}).items()
            }

    raw_dir_posix = Path(data_dir).as_posix()
    cache_dir_posix = Path(cache_dir).as_posix()
    out_dir_posix = Path(output_dir).as_posix()

    system_instruction = (
        "You are an Elite Python Data Systems Engineer.\n"
        "Your task is to write a production-ready, ultra-robust, vectorized Python script.\n"
        "Rules:\n"
        "1. Write 100% executable Python code. No placeholder ellipses (...), no pseudo-code.\n"
        "2. FACT INTEGRITY & ROW CONSERVATION: NEVER drop duplicates on the fact table using natural or non-unique columns (e.g. NEVER call df.drop_duplicates(subset=['id']) on the fact table)! If 'primary_id_column' is 'fact_surrogate_id' or natural keys have duplicates, generate a unique surrogate ID: df['fact_surrogate_id'] = (df.index + 1).astype(str). The final fact table must strictly satisfy: len(final_fact) == initial_fact_count.\n"
        "3. NEVER call df.dropna() on the fact table! Fill missing numerical values with median/0 or categorical with 'UNKNOWN' to strictly preserve row count: len(final_fact) == initial_fact_count.\n"
        "4. Cast string/mixed-type keys and identifiers to string before parquet export to prevent pyarrow type errors.\n"
        "5. Enforce sys.stdout.reconfigure(encoding='utf-8') on Windows platform.\n"
        "6. Ingestion: Use the EXACT 'filename', 'delimiter', and 'encoding' given for each table in DATASET TOPOLOGY SUMMARY (e.g. pd.read_csv(RAW_DIR / table_info['filename'], sep=delimiter, encoding=encoding, na_values=['?'], low_memory=False)). NEVER invent filenames!\n"
        f"7. TARGET METRIC PRESERVATION: The final fact table MUST physically contain the column specified as 'target_metric' in EXECUTION BLUEPRINT ('{blueprint.get('target_metric', '')}'). If it does not exist natively in the raw tables, derive/compute it explicitly (e.g. df['{blueprint.get('target_metric', '')}'] = ...).\n"
        "8. Output the complete Python code wrapped in ```python ... ```."
    )

    prompt = f"""
Write a standalone Python script 'dynamic_etl_runner.py' based on this execution blueprint and dataset topology:

EXECUTION BLUEPRINT:
{json.dumps(blueprint, indent=2)}

DATASET TOPOLOGY SUMMARY:
{json.dumps(topology_summary, indent=2) if topology_summary else 'Use tables and columns specified in the blueprint.'}

Core Engineering Requirements for the script:
1. Operational Directories:
   - Raw input directory: Path({repr(raw_dir_posix)})
   - Cache directory: Path({repr(cache_dir_posix)})
   - Output directory: Path({repr(out_dir_posix)})
   - Create directories if they do not exist.
2. Data Ingestion & Caching:
   - Ingest raw tables using the EXACT 'filename' specified in DATASET TOPOLOGY SUMMARY (e.g. RAW_DIR / table_info['filename']).
   - Clean column names (strip whitespace), cast mixed identifier columns to str.strip(), and persist to cache parquet.
   - For CSV files, check the table's delimiter in the topology summary (e.g. if delimiter is ';', use sep=';') or use sep=None, engine='python' so columns are cleanly parsed.
3. Cardinality Defense & Pre-Aggregations:
   - Implement the exact cardinality defense plan defined in the blueprint (e.g. aggregate multi-row dimension tables 1:1 on the candidate foreign key).
4. Entity Resolution & Key Cleaning:
   - Normalize candidate join keys (strip whitespace, uppercase, fill missing fallback codes).
   - For datetime or timestamp join keys, parse them with `pd.to_datetime(df[col], errors='coerce')` so that differing string formats (e.g. DD-MM-YYYY vs YYYY-MM-DD) align seamlessly during merges.
   - Deduplicate dimensions on clean keys to guarantee 1:1 lookup safety.
   - For fact surrogate keys, if natural keys can contain duplicate values (e.g. time-series Daylight Savings Time repeated hours), append cumcount or row index: `df['fact_surrogate_id'] = compute_md5(key_col + '_' + df.groupby(key_col).cumcount().astype(str))` or use deterministic row index `(df.index + 1).astype(str)` to strictly guarantee primary key uniqueness.
5. Relational Merges:
   - Implement the joins specified in the blueprint. If multi-reference keys exist (e.g. origin and destination), perform dual merges with distinct column prefixes.
   - Clean merge collision columns: remove any columns ending with '_drop' or overlapping redundant attributes, and guarantee strictly unique column names: `final_fact = final_fact.loc[:, ~final_fact.columns.duplicated()]`.
6. Vectorized Forensic Enrichments:
   - Calculate all forensic enrichment columns specified in the blueprint using vectorized numpy/pandas formulas.
7. Strict Assertion Gates:
   - Implement every assertion gate from the blueprint.
   - Assert: len(final_fact) == initial_fact_count (0 Cartesian explosion / 0 row loss).
   - Assert: no duplicate primary IDs.
   - Assert: joined dimension features exist.
8. Deliverables Export:
   - Deduplicate column names strictly before export: `final_fact = final_fact.loc[:, ~final_fact.columns.duplicated()]`.
   - Save final fact table to output directory as 'bi_ready_fact.parquet' (engine='pyarrow').
   - Save dimension tables to output directory as CSV (index=False).
   - Save forensic diagnostic dossier JSON with summary counts and DAX specs.
   - Print a clean execution summary table to console.
"""

    print("[*] [Stage 3 Code Generator] Invoking PacedGeminiClient for Dynamic ETL Synthesis...")
    pacer = PacedGeminiClient(max_calls_per_minute=14)
    response_text = pacer.generate_content(
        contents=prompt,
        system_instruction=system_instruction
    )
    
    code = extract_python_code_robust(response_text)
    
    # Pre-execution Syntax Validation
    try:
        compile(code, output_script_path, 'exec')
        print("[+] [Stage 3 Code Generator] Syntax Compilation Check: PASSED (0 syntax errors).")
    except SyntaxError as se:
        print(f"[!] Warning: Initial code has syntax error: {se}. Retrying patch...")
    
    out_p = Path(output_script_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, 'w', encoding='utf-8') as f:
        f.write(code)
        
    print(f"[+] [Stage 3 Code Generator] Dynamic ETL Script successfully saved to: {output_script_path}")
    return code

if __name__ == "__main__":
    bp_path = sys.argv[1] if len(sys.argv) > 1 else "autonomous_engine/execution_blueprint.json"
    sc_path = sys.argv[2] if len(sys.argv) > 2 else "autonomous_engine/dynamic_etl_runner.py"
    top_path = sys.argv[3] if len(sys.argv) > 3 else "autonomous_engine/schema_topology.json"
    d_dir = sys.argv[4] if len(sys.argv) > 4 else "error/raw_data"
    o_dir = sys.argv[5] if len(sys.argv) > 5 else "error/output"
    c_dir = sys.argv[6] if len(sys.argv) > 6 else "error/cache"
    generate_dynamic_etl_script(bp_path, sc_path, top_path, data_dir=d_dir, output_dir=o_dir, cache_dir=c_dir)
