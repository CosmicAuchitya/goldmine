"""
=============================================================================
STAGE 2 (FULLY GENERALIZED & PACED): RELATIONAL & FORENSIC BLUEPRINT
=============================================================================
Features & Defenses:
1. Paced Gemini Client (14 RPM sliding window + exponential backoff).
2. Domain-Agnostic prompt generation: Adapts dynamically to Aviation, Retail,
   Healthcare, Banking, E-Commerce, Logistics, or any relational dataset.
3. Multi-strategy robust JSON extraction.
4. 100% Local PII scrubbed inputs.
5. Safe JSON persistence with SafeJSONEncoder.
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
    from .pii_scrubber import scrub_schema_payload
    from .safe_math_and_json_guard import safe_dump_json
except ImportError:
    from rate_limiter import PacedGeminiClient
    from pii_scrubber import scrub_schema_payload
    from safe_math_and_json_guard import safe_dump_json

def extract_json_robust(raw_text: str) -> dict:
    """
    Extracts valid JSON even if model includes conversational preamble or markdown tags.
    """
    text = raw_text.strip()
    
    # Strategy 1: Search for ```json ... ``` or ``` ... ```
    match_code = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match_code:
        candidate = match_code.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass
            
    # Strategy 2: Match outermost JSON object { ... }
    match_braces = re.search(r'\{[\s\S]*\}', text)
    if match_braces:
        candidate = match_braces.group(0).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass
            
    # Strategy 3: Direct parse
    return json.loads(text)

def build_deterministic_blueprint_from_topology(topology: dict) -> dict:
    """Synthesizes a 100% deterministic topological blueprint directly from schema topology."""
    tables = topology.get("tables", {})
    if not tables:
        return {}
    
    # 1. Identify Fact Table (largest table by estimated rows)
    sorted_tables = sorted(tables.items(), key=lambda x: x[1].get("estimated_rows", 0), reverse=True)
    fact_name, fact_meta = sorted_tables[0]
    
    # 2. Identify Primary Key in Fact
    cols = fact_meta.get("columns", [])
    pk = "id"
    for c in cols:
        if c.lower().endswith('_id') or c.lower() in ['id', 'ident', 'uuid', 'key']:
            pk = c
            break
            
    # 3. Identify Target Metric
    target = None
    for c in cols:
        if any(k in c.lower() for k in ['delay', 'status', 'target', 'churn', 'cancel', 'fraud', 'error']):
            target = c
            break
    if not target:
        target = cols[0] if cols else "record_status"
        
    dimensions = [t for t, _ in sorted_tables[1:]]
    
    return {
        "project_title": f"Enterprise Analytics & Dimensional Architecture for {topology.get('dataset_name', 'Dataset')}",
        "fact_table": fact_name,
        "target_metric": target,
        "primary_id_column": pk,
        "cardinality_defense_plan": {
            "dimension_aggregation_strategies": "Pre-aggregate any 1:N dimensions before merge to preserve 1:1 fact integrity",
            "entity_resolution_and_key_cleaning": "Sanitize and harmonize join keys with whitespace stripping and case folding",
            "relational_join_sequence": f"Left join {len(dimensions)} dimension tables ({', '.join(dimensions)}) onto {fact_name}"
        },
        "forensic_enrichment_columns": [
            "Fulfillment & SLA duration variance",
            "Financial and operational friction ratio"
        ],
        "assertion_gates": [
            f"assert len(final_fact) == len(initial_fact), 'Zero drift violation: Cartesian explosion detected!'",
            f"assert final_fact.duplicated(subset=['{pk}']).sum() == 0, 'Duplicate primary keys detected in {pk}!'"
        ],
        "bi_deliverables": {
            "fact_table": "bi_ready_fact.parquet",
            "dimension_tables": [f"bi_dim_{d}.csv" for d in dimensions],
            "dax_measures": [
                "Total Volume",
                "Target Events Count",
                "Target Event Rate %",
                "Total Operational Loss ($)",
                "Dimensional Risk Index"
            ]
        }
    }

def generate_relational_blueprint(topology_json_path: str, output_blueprint_path: str) -> dict:
    with open(topology_json_path, 'r', encoding='utf-8') as f:
        topology = json.load(f)
        
    # Local PII Scrub check
    clean_topology = scrub_schema_payload(topology)

    system_instruction = (
        "You are an Elite Enterprise Data Architect and Forensic Data Scientist.\n"
        "Your mission is to formulate an UNBIASED, mathematically rigorous ETL and forensic analytics blueprint.\n"
        "Rules:\n"
        "1. Never prescribe subjective operational decisions (do NOT recommend firing employees, cutting flights, changing prices without data).\n"
        "2. Focus 100% on verifiable data forensics: Economic Moats (Value Drivers), Capital Leaks (Friction/Delay Liabilities), and Operational Audit Triggers for supervisors.\n"
        "3. Protect against 1-to-Many Cartesian row explosion. Multi-row dimension tables MUST be pre-aggregated to 1:1 before joining.\n"
        "4. Enforce strict Star Schema for Power BI / Tableau.\n"
        "5. Formulate Confounder & Counterfactual defenses: Ensure forensic enrichment columns include normalized ratios (e.g. per-transaction cost, utilization velocity) to separate correlation from underlying volume scale.\n"
        "6. Output STRICT JSON format matching the requested structure.\n"
        "7. FACT INTEGRITY & PRIMARY KEY: If the fact table's 'recommended_primary_key' is 'fact_surrogate_id' or 'strictly_unique_primary_keys' is empty, set 'primary_id_column' to 'fact_surrogate_id'. You MUST NEVER instruct dropping rows or deduplicating the fact table on non-unique columns (such as non-unique event or user IDs)!"
    )

    prompt = f"""
Given this dataset schema topology and detected cardinality hazards:
{json.dumps(clean_topology, indent=2)}

Analyze the table relationships, candidate keys, and cardinality hazards. Formulate an unbiased, production-ready Star Schema and Forensic Analytics blueprint.
Your output MUST be a valid JSON object with these EXACT top-level keys:
{{
  "project_title": "<Descriptive professional title reflecting the specific dataset domain>",
  "fact_table": "<Name of central event/transaction table with highest volume>",
  "target_metric": "<Primary operational target / dependent variable / status column>",
  "primary_id_column": "<Must use 'recommended_primary_key' from topology. If no natural column is 100% unique, specify 'fact_surrogate_id'>",
  "cardinality_defense_plan": {{
    "dimension_aggregation_strategies": "<Specific pre-aggregation rules for any 1:N dimension tables to prevent row multiplication>",
    "entity_resolution_and_key_cleaning": "<Key harmonization, prefixing, deduplication, and code resolution steps>",
    "relational_join_sequence": "<Step-by-step join order from fact table to dimensions with explicit join types and keys>"
  }},
  "forensic_enrichment_columns": [
    "<Derived metric 1 with exact calculation formula>",
    "<Derived metric 2 with exact calculation formula>",
    "<Domain operational friction / penalty / cost liability metric with formula>"
  ],
  "assertion_gates": [
    "assert len(final_fact) == len(initial_fact), 'Row count mismatch: Cartesian duplicate explosion or row loss occurred!'",
    "assert final_fact.duplicated(subset=[<id_col>]).sum() == 0, 'Duplicate primary IDs detected!'",
    "assert <key_dimension_column> in final_fact.columns, 'Missing expected dimension features!'"
  ],
  "bi_deliverables": {{
    "fact_table": "bi_ready_fact.parquet",
    "dimension_tables": ["bi_dim_<name>.csv"],
    "dax_measures": [
      "Total Volume / Records",
      "Target Events Count",
      "Rate / Percentage %",
      "Total Financial / Operational Friction Loss ($)",
      "Segment Performance / Congestion Index"
    ]
  }}
}}
"""

    active_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    try:
        if active_provider in ["nemotron", "openrouter"]:
            print("[*] [Stage 2 Blueprint] Invoking NVIDIA Nemotron 3 Ultra 550B MoE (OpenRouter Free Tier)...")
            try:
                from .rate_limiter import call_openrouter_model
            except ImportError:
                from rate_limiter import call_openrouter_model
            response_text = call_openrouter_model(
                prompt=prompt,
                system_instruction=system_instruction,
                model="nvidia/nemotron-3-ultra-550b-a55b:free"
            )
        else:
            print("[*] [Stage 2 Blueprint] Invoking PacedGeminiClient (14 RPM Safety Guard)...")
            pacer = PacedGeminiClient(max_calls_per_minute=14)
            response_text = pacer.generate_content(
                contents=prompt,
                system_instruction=system_instruction,
                max_retries=2
            )
        blueprint = extract_json_robust(response_text)
    except Exception as api_err:
        print(f"[!] Note: Upstream Gemini API unavailable ({api_err}).")
        if Path(output_blueprint_path).exists():
            print(f"[*] Reusing verified cached blueprint from: {output_blueprint_path}")
            try:
                with open(output_blueprint_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        print("[*] Synthesizing 100% deterministic topological blueprint from schema topology...")
        blueprint = build_deterministic_blueprint_from_topology(clean_topology)
        
    safe_dump_json(blueprint, output_blueprint_path, indent=2)
    print(f"[+] [Stage 2 Blueprint] Relational Blueprint successfully saved to: {output_blueprint_path}")
    return blueprint

if __name__ == "__main__":
    top_path = sys.argv[1] if len(sys.argv) > 1 else "autonomous_engine/schema_topology.json"
    bp_path = sys.argv[2] if len(sys.argv) > 2 else "autonomous_engine/execution_blueprint.json"
    generate_relational_blueprint(top_path, bp_path)
