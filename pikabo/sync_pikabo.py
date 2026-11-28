"""
====================================================================================================
PIKABO SYNCHRONIZER & CODEBASE COMPILER (V2.5 ENTERPRISE GRADE)
====================================================================================================
Compiles all specialized AI agents and core modules from `autonomous_engine/` into a single,
self-contained, fully importable reference monolith (`pikabo/pikabo.py`).

Guarantees:
1. Strict Dependency-Order Compilation: Foundational utilities and stages compile BEFORE orchestrator.
2. 100% Standalone Importable: Internal sibling import shims automatically fall back to global scope,
   eliminating `ModuleNotFoundError` completely when imported outside `autonomous_engine`.
3. Active Structured Logging: Binds `print = log_print` so all messages concurrently route to
   console and rotating enterprise file log (`runs/logs/enterprise_pipeline.log`).
4. Single Master Entry Point: Guards 23 intermediate `__main__` blocks and exposes a single
   unified CLI runner at the bottom.
====================================================================================================
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

INTERNAL_MODULES = {
    'common_utils', 'logger', 'run_manager', 'safe_math_and_json_guard',
    'robust_csv_sniffer', 'robust_excel_scanner', 'domain_invariant_audit',
    'pii_scrubber', 'composite_key_detector', 'cardinality_and_bridge_detector',
    'rate_limiter', 'stage2_ai_blueprint', 'stage3_ai_code_generator',
    'stage4_sandbox_executor', 'templated_dag_runner', 'self_healing_supervisor',
    'target_resolver', 'imbalance_aware_engine', 'strategic_decision_matrix',
    'business_action_exporter', 'stage5_bi_synthesizer',
    'stage6_semantic_viz_synthesizer', 'conversational_qa_engine',
    'stage7_bespoke_dashboard_architect', 'anti_hallucination_guard',
    'loop_fix_engine', 'stage1_topology_profiler', 'master_orchestrator',
    'atomic_windows_io', 'content_hash_cache', 'duckdb_engine',
    'duckdb_streaming_engine', 'tally_pdf_ingestion', 'growth_inventory_engine',
    'business_category_registry', 'category_intelligence_engine',
    'intelligent_date_normalizer', 'proactive_anomaly_radar', 'voice_brief_synthesizer'
}

# Strict bottom-up dependency order
AGENTS_CONFIG = [
    # 1. Foundation & Utilities
    {
        "agent_id": "SHARED_COMMON_UTILS",
        "agent_name": "CORE 0.1: Enterprise Common Utilities & Code Extractors",
        "file": "autonomous_engine/common_utils.py",
        "stage": "Core Shared Infrastructure",
        "description": "Shared string extractors, AST sanitizer, and reusable helper routines."
    },
    {
        "agent_id": "SHARED_LOGGER",
        "agent_name": "CORE 0.2: Dual-Stream Structured Enterprise Logger",
        "file": "autonomous_engine/logger.py",
        "stage": "Core Shared Infrastructure",
        "description": "Rotating structured file logging + clean console output with zero subprocess disruption."
    },
    {
        "agent_id": "SHARED_SAFE_MATH",
        "agent_name": "CORE 0.3: Safe Math, Outlier & Atomic JSON Guard",
        "file": "autonomous_engine/safe_math_and_json_guard.py",
        "stage": "Core Shared Infrastructure",
        "description": "Safe division, inf/nan sanitization, and atomic temp-file JSON serialization."
    },
    {
        "agent_id": "SHARED_ATOMIC_IO",
        "agent_name": "CORE 0.4: Enterprise Atomic Windows File I/O Guard",
        "file": "autonomous_engine/atomic_windows_io.py",
        "stage": "Core Shared Infrastructure",
        "description": "Atomic file writes with exponential backoff retry defeating WinError 32 locking hazards."
    },
    {
        "agent_id": "SHARED_CONTENT_CACHE",
        "agent_name": "CORE 0.5: Content-Hash Dataset Caching Engine",
        "file": "autonomous_engine/content_hash_cache.py",
        "stage": "Core Shared Infrastructure",
        "description": "Deterministic SHA-256 fingerprinting for dataset cache isolation."
    },
    {
        "agent_id": "SHARED_DUCKDB_ENGINE",
        "agent_name": "CORE 0.6: Enterprise DuckDB Vectorized Relational Engine",
        "file": "autonomous_engine/duckdb_engine.py",
        "stage": "Core Shared Infrastructure",
        "description": "Out-of-core streaming SQL execution engine bypassing pandas memory limits."
    },
    {
        "agent_id": "SHARED_DUCKDB_STREAMING",
        "agent_name": "CORE 0.6B: DuckDB Out-of-Core Streaming & Memory Compaction Engine",
        "file": "autonomous_engine/duckdb_streaming_engine.py",
        "stage": "Core Shared Infrastructure",
        "description": "Streams 500k+ row CSVs directly to ZSTD Parquet with lossless memory downcasting."
    },
    {
        "agent_id": "SHARED_TALLY_PDF_INGESTION",
        "agent_name": "CORE 0.6C: Tally/Marg Grouped Ledger Flattener & PDF Table Extractor",
        "file": "autonomous_engine/tally_pdf_ingestion.py",
        "stage": "Core Shared Infrastructure",
        "description": "Flattens hierarchical Indian Tally ledgers, strips mid-sheet subtotals, and extracts multi-page PDF tables."
    },
    {
        "agent_id": "SHARED_CSV_SNIFFER",
        "agent_name": "CORE 0.7: Robust CSV Sniffer & Encoding Detector",
        "file": "autonomous_engine/robust_csv_sniffer.py",
        "stage": "Core Shared Infrastructure",
        "description": "Multi-encoding sniffer (utf-8-sig, utf-8, latin-1) and delimiter detector."
    },
    {
        "agent_id": "SHARED_EXCEL_SCANNER",
        "agent_name": "CORE 0.8: Robust Excel Scanner & Header Row Detector",
        "file": "autonomous_engine/robust_excel_scanner.py",
        "stage": "Core Shared Infrastructure",
        "description": "Multi-sheet Excel scanner with entropy-based header row detection."
    },
    {
        "agent_id": "SHARED_INVARIANT_AUDIT",
        "agent_name": "CORE 0.9: Domain Invariant & Row Drift Auditor",
        "file": "autonomous_engine/domain_invariant_audit.py",
        "stage": "Core Shared Infrastructure",
        "description": "Mathematical invariant assertions: zero drift, primary key uniqueness, referential integrity."
    },
    {
        "agent_id": "SHARED_RUN_MANAGER",
        "agent_name": "CORE 0.10: Pipeline Run Manager & SQLite Audit Catalog",
        "file": "autonomous_engine/run_manager.py",
        "stage": "Core Shared Infrastructure",
        "description": "Manages isolated execution runs, persistent SQLite ledger, and immutable run manifests."
    },

    # 2. Stage 1 Workers: Privacy & Topology
    {
        "agent_id": "AGENT_1_PII_SCRUBBER",
        "agent_name": "AGENT 1.1: Local Privacy & PII Scrubbing Specialist",
        "file": "autonomous_engine/pii_scrubber.py",
        "stage": "Stage 1 - Privacy & Topology",
        "description": "Detects and masks sensitive personal data locally before sending schema metadata to LLMs."
    },
    {
        "agent_id": "AGENT_1_KEY_DETECTOR",
        "agent_name": "AGENT 1.2: Composite Key & Foreign Key Discovery Agent",
        "file": "autonomous_engine/composite_key_detector.py",
        "stage": "Stage 1 - Privacy & Topology",
        "description": "Identifies composite candidate keys and foreign key links across raw tables."
    },
    {
        "agent_id": "AGENT_1_CARDINALITY_SCANNER",
        "agent_name": "AGENT 1.3: Cardinality Hazard & Multiplicity Defense Scanner",
        "file": "autonomous_engine/cardinality_and_bridge_detector.py",
        "stage": "Stage 1 - Privacy & Topology",
        "description": "Scans for 1:1, 1:N, and N:M cardinality hazards to prevent Cartesian multiplicity explosions."
    },
    {
        "agent_id": "AGENT_1_TOPOLOGY_PROFILER",
        "agent_name": "AGENT 1.4: Schema Topology Profiler & Sanitizer",
        "file": "autonomous_engine/stage1_topology_profiler.py",
        "stage": "Stage 1 - Privacy & Topology",
        "description": "Ingests raw directories (CSV/Excel/Parquet), builds topology graph, and outputs schema_topology.json."
    },

    # 3. Stage 2 Blueprint & Rate Limiting
    {
        "agent_id": "AGENT_2_RATE_LIMITER",
        "agent_name": "AGENT 2.1: Multi-Key API Pool & Rate Limiter Manager",
        "file": "autonomous_engine/rate_limiter.py",
        "stage": "Stage 2 - Blueprint Formulation",
        "description": "Manages multi-key API rate-limiting pool across Gemini endpoints (28 RPM safety guard)."
    },
    {
        "agent_id": "AGENT_2_BLUEPRINT_ARCHITECT",
        "agent_name": "AGENT 2.2: Relational & Forensic Star-Schema Blueprint Architect",
        "file": "autonomous_engine/stage2_ai_blueprint.py",
        "stage": "Stage 2 - Blueprint Formulation",
        "description": "Synthesizes star schema design, primary fact designation, and mathematical assertion gates."
    },

    # 4. Stage 3 & 4 Codegen, Self-Healing & Execution
    {
        "agent_id": "AGENT_5_TARGET_RESOLVER",
        "agent_name": "AGENT 5.1: Canonical Ground-Truth Target & Financial Ledger Resolver",
        "file": "autonomous_engine/target_resolver.py",
        "stage": "Core Semantic Truth & Resolution",
        "description": "Single source of truth resolving binary classification target, temporal columns, and authentic financial exposure."
    },
    {
        "agent_id": "AGENT_3_CODE_GENERATOR",
        "agent_name": "AGENT 3: Dynamic Vectorized Python ETL Synthesizer",
        "file": "autonomous_engine/stage3_ai_code_generator.py",
        "stage": "Stage 3 - Code Generation",
        "description": "Generates dynamic Python ETL runner scripts with strict assertion gates and 1:N pre-aggregation."
    },
    {
        "agent_id": "AGENT_4_DAG_FALLBACK",
        "agent_name": "AGENT 4.1: Deterministic Out-of-Core DAG Fallback Engine",
        "file": "autonomous_engine/templated_dag_runner.py",
        "stage": "Stage 4 - Sandbox Execution",
        "description": "Executes deterministic relational DAG if dynamic script retries are exhausted."
    },
    {
        "agent_id": "AGENT_4_SELF_HEALING_SUPERVISOR",
        "agent_name": "AGENT 4.2: V6.0 Multi-Tier Autonomous Self-Healing Supervisor",
        "file": "autonomous_engine/self_healing_supervisor.py",
        "stage": "Stage 4 - Sandbox Execution",
        "description": "Tier-0 deterministic micro-healer, stuck-loop breaker, grounded prompts, and closed-loop logical/structural healer."
    },
    {
        "agent_id": "AGENT_4_SANDBOX_EXECUTOR",
        "agent_name": "AGENT 4.3: Sandbox Executor & AST Self-Healing Compiler",
        "file": "autonomous_engine/stage4_sandbox_executor.py",
        "stage": "Stage 4 - Sandbox Execution",
        "description": "Executes dynamic ETL scripts in an isolated subprocess with AST error interception and self-healing."
    },

    # 5. Stage 5 BI & Micro-Forensics
    {
        "agent_id": "AGENT_5_IMBALANCE_AUDITOR",
        "agent_name": "AGENT 5.2: Rare-Event & Class Imbalance Auditor",
        "file": "autonomous_engine/imbalance_aware_engine.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Detects severe class imbalance (<=2%) and protects against misleading accuracy/moat claims."
    },
    {
        "agent_id": "AGENT_5_MICRO_FORENSIC_ENGINE",
        "agent_name": "AGENT 5.3: Strategic Executive Decision & Micro-Forensic Inquiry Engine",
        "file": "autonomous_engine/strategic_decision_matrix.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Performs non-linear decile cliffs, 2x2 interaction matrices, Wilson 95% CIs, and Simpson's Paradox defenses."
    },
    {
        "agent_id": "AGENT_5_ACTION_EXPORTER",
        "agent_name": "AGENT 5.4: Actionable Priority Worklist & Temporal Trend Exporter",
        "file": "autonomous_engine/business_action_exporter.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Exports two-queue operational worklists, genuine temporal trends, and plain English/Hinglish executive briefs."
    },
    {
        "agent_id": "AGENT_5_GROWTH_INVENTORY",
        "agent_name": "AGENT 5.4B: Pure Sales, Profit, 30-Day Demand Forecast & Stock Reorder Engine",
        "file": "autonomous_engine/growth_inventory_engine.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Computes ABC Pareto, negative-margin leaks, damped Holt 30-day forecasts, safety stock/ROP, and dormant buyers."
    },
    {
        "agent_id": "AGENT_5_CATEGORY_REGISTRY",
        "agent_name": "AGENT 5.4C: Canonical Business Category Registry & 3-Layer Auto-Detector (V6.0)",
        "file": "autonomous_engine/business_category_registry.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Unifies 10 canonical business categories + sub-categories with strict whitelist validation, honest abstain, and mismatch guard."
    },
    {
        "agent_id": "AGENT_5_CATEGORY_INTELLIGENCE",
        "agent_name": "AGENT 5.4D: Vectorized Category Economics & Statistics Intelligence Engine (V6.0)",
        "file": "autonomous_engine/category_intelligence_engine.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Computes column-gated, zero-hallucination category economics and statistics KPIs across all 10 business domains."
    },
    {
        "agent_id": "AGENT_5_DATE_NORMALIZER",
        "agent_name": "AGENT 5.4E: Intelligent Date & Temporal Orientation Normalizer",
        "file": "autonomous_engine/intelligent_date_normalizer.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Resolves US vs UK/India day-first dates and Excel serial dates into clean ISO timestamps."
    },
    {
        "agent_id": "AGENT_5_PROACTIVE_ANOMALY_RADAR",
        "agent_name": "AGENT 5.4F: Proactive Early-Warning Anomaly & Cohort Acceleration Radar (V7.0)",
        "file": "autonomous_engine/proactive_anomaly_radar.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Detects rolling EWMA/MAD time-series spikes and BH-FDR validated cohort acceleration before next-month P&L impact."
    },
    {
        "agent_id": "AGENT_5_VOICE_BRIEF_SYNTHESIZER",
        "agent_name": "AGENT 5.4G: Grounded Bilingual Voice Brief, Share Pack & Impact Verifier (V7.0)",
        "file": "autonomous_engine/voice_brief_synthesizer.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Generates 100% grounded 60s EN/HI CEO voice scripts, PII-free WhatsApp share packs, impact verifier, and 2-page A4 Boardroom PDF HTML."
    },
    {
        "agent_id": "AGENT_5_BI_SYNTHESIZER",
        "agent_name": "AGENT 5.5: Enterprise BI Deliverables & Star-Schema DAX Synthesizer",
        "file": "autonomous_engine/stage5_bi_synthesizer.py",
        "stage": "Stage 5 - BI & Forensics",
        "description": "Exports star-schema dimension CSVs, fact parquet, DAX measure guide, and executive forensic dossier."
    },

    # 6. Stage 6 Semantic Model & Visuals
    {
        "agent_id": "AGENT_6_SEMANTIC_VIZ_SYNTHESIZER",
        "agent_name": "AGENT 6.1: Power BI / Fabric TMDL Semantic Model & Auto-Viz Synthesizer",
        "file": "autonomous_engine/stage6_semantic_viz_synthesizer.py",
        "stage": "Stage 6 - Semantic Model & Visuals",
        "description": "Generates Power BI TMDL folder, universal semantic metrics manifest, Vega-Lite specs, HTML dashboard, and certification gate."
    },
    {
        "agent_id": "AGENT_6_CONVERSATIONAL_QA",
        "agent_name": "AGENT 6.2: Grounded Conversational Business Q&A Engine",
        "file": "autonomous_engine/conversational_qa_engine.py",
        "stage": "Stage 6 - Semantic Model & Visuals",
        "description": "Executes read-only DuckDB SQL queries over physical Parquet fact tables with English/Hinglish responses."
    },
    {
        "agent_id": "AGENT_7_BESPOKE_DASHBOARD",
        "agent_name": "AGENT 7: Autonomous Bespoke Executive Dashboard Architect",
        "file": "autonomous_engine/stage7_bespoke_dashboard_architect.py",
        "stage": "Stage 7 - Bespoke Dashboard Architecture",
        "description": "Judges domain ontology, selects executive design archetype, compiles zero-drift micro-cube and renders zero-CDN bespoke interactive HTML dashboard."
    },

    # 7. Audit & Regression Governance
    {
        "agent_id": "AGENT_AUDIT_ANTI_HALLUCINATION",
        "agent_name": "AUDIT AGENT 1: Deterministic Anti-Hallucination Truth Guard",
        "file": "autonomous_engine/anti_hallucination_guard.py",
        "stage": "Governance & Verification",
        "description": "Executes physical DuckDB SQL reflection on fact Parquet to verify 100.0% truth-grounding of LLM claims."
    },
    {
        "agent_id": "AGENT_AUDIT_LOOP_FIX",
        "agent_name": "AUDIT AGENT 2: Continuous Multi-Dataset Regression Engine",
        "file": "autonomous_engine/loop_fix_engine.py",
        "stage": "Governance & Verification",
        "description": "Continuously verifies mathematical invariants (0 drift, 0 duplicates) across historical benchmarks."
    },

    # 8. Master Orchestrator (Compiled before test suite so pipeline runner is available)
    {
        "agent_id": "MASTER_ORCHESTRATOR",
        "agent_name": "AGENT 0: Master Autonomous Pipeline Orchestrator",
        "file": "autonomous_engine/master_orchestrator.py",
        "stage": "Stage 0 - Master Orchestration",
        "description": "Coordinates all 6 stages of the autonomous enterprise pipeline from raw ingestion to Fabric TMDL."
    },

    # 9. Enterprise Automated Test Suite & Invariant Verification Gate
    {
        "agent_id": "ENTERPRISE_TEST_SUITE",
        "agent_name": "AGENT 9: Enterprise Statistical & Invariant Test Suite",
        "file": "autonomous_engine/test_engine_statistics.py",
        "stage": "Verification & Testing Gate",
        "description": "Automated unit tests validating Wilson CIs, z-tests, target scaling, and domain invariant assertions."
    }
]


def patch_internal_imports_for_monolith(code: str) -> str:
    """
    Transforms internal package/sibling imports so they never crash with ModuleNotFoundError
    when the monolithic file is imported standalone. In the monolith, all symbols are in globals().
    """
    for mod in INTERNAL_MODULES:
        # Relative import
        code = re.sub(
            rf'(?ms)^(\s*)from\s+\.{mod}\s+import\s+(\([^)]+\)|[^\n]+)',
            rf'\1try:\n\1    from .{mod} import \2\n\1except (ImportError, ModuleNotFoundError):\n\1    try:\n\1        from {mod} import \2\n\1    except (ImportError, ModuleNotFoundError):\n\1        pass',
            code
        )
        # Package import: from autonomous_engine.<mod> import
        code = re.sub(
            rf'(?ms)^(\s*)from\s+autonomous_engine\.{mod}\s+import\s+(\([^)]+\)|[^\n]+)',
            rf'\1try:\n\1    from autonomous_engine.{mod} import \2\n\1except (ImportError, ModuleNotFoundError):\n\1    try:\n\1        from {mod} import \2\n\1    except (ImportError, ModuleNotFoundError):\n\1        pass',
            code
        )
        # Sibling direct import: from <mod> import
        code = re.sub(
            rf'(?ms)^(\s*)from\s+{mod}\s+import\s+(\([^)]+\)|[^\n]+)',
            rf'\1try:\n\1    from {mod} import \2\n\1except (ImportError, ModuleNotFoundError):\n\1    pass',
            code
        )
    return code


def sync_pikabo_codebase(output_path: Optional[Path] = None) -> Path:
    if output_path is None:
        output_path = REPO_ROOT / "pikabo" / "pikabo.py"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_lines = [
        '"""',
        '====================================================================================================',
        'PIKABO -- UNIFIED ENTERPRISE AUTONOMOUS AI DATA ENGINE (MONOLITHIC CONSOLIDATION)',
        '====================================================================================================',
        f'Generated At : {timestamp_str}',
        f'Purpose      : Single-source comprehensive reference code containing all specialized AI agents.',
        'Usage Scope  : Cross-checking, auditing, and multi-AI review. Does not interfere with modular execution.',
        'Core Engine  : DataX-Ray Autonomous Enterprise Engine (V4.5)',
        '====================================================================================================',
        '',
        'INDEX OF SPECIALIZED AGENTS CONSOLIDATED IN THIS FILE:',
    ]

    for idx, agent in enumerate(AGENTS_CONFIG, 1):
        header_lines.append(f"  [{idx:02d}] {agent['agent_name']} ({agent['stage']})")
        header_lines.append(f"       Source: {agent['file']}")
        header_lines.append(f"       Role  : {agent['description']}")

    header_lines.extend([
        '',
        '====================================================================================================',
        '"""',
        '',
        '# Global warning & execution guardrail',
        '# This file is an audited monolithic compilation for review and cross-checking purposes.',
        '# Production pipelines should be executed via: python autonomous_engine/master_orchestrator.py',
        '',
        'from __future__ import annotations',
        '',
        'import sys',
        'import os',
        'import re',
        'import json',
        'import time',
        'import logging',
        '',
    ])

    compiled_content = "\n".join(header_lines) + "\n"

    for idx, agent in enumerate(AGENTS_CONFIG, 1):
        src_path = REPO_ROOT / agent["file"]
        banner = [
            "",
            "#" * 100,
            f"# SECTION {idx:02d} // {agent['agent_name'].upper()}",
            f"# STAGE      : {agent['stage']}",
            f"# SOURCE FILE: {agent['file']}",
            f"# DESCRIPTION: {agent['description']}",
            "#" * 100,
            ""
        ]
        compiled_content += "\n".join(banner) + "\n"

        if src_path.exists():
            code_text = src_path.read_text(encoding="utf-8")
            # 0. Hoist/strip embedded __future__ imports (already declared at top of monolith)
            code_text = re.sub(r'(?m)^\s*from\s+__future__\s+import\s+[^\n]+\n?', '', code_text)
            # 1. Patch internal sibling imports so monolith is 100% standalone importable
            patched_code = patch_internal_imports_for_monolith(code_text)
            # 2. Guard intermediate __main__ blocks
            guarded_code = re.sub(
                r'if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:',
                r'if False and __name__ == "__main__":  # Section CLI preserved for reference',
                patched_code
            )
            compiled_content += guarded_code + "\n"
            # 3. After logger section is defined, bind global print = log_print
            if agent["agent_id"] == "SHARED_LOGGER":
                compiled_content += "\n# Active Enterprise Logging: route all prints to structured logger\nprint = log_print\n\n"
        else:
            compiled_content += f"# [WARNING] Source file not found: {src_path}\n"

    # Add single unified Master Entry Point at the very bottom of the monolithic file
    compiled_content += """
# ====================================================================================================
# UNIFIED MASTER CLI ENTRY POINT FOR PIKABO MONOLITH
# ====================================================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PIKABO Unified Autonomous Enterprise Engine")
    parser.add_argument("--data", default="raw_data", help="Path to raw data directory")
    parser.add_argument("--output", default="output", help="Path to deliverables output directory")
    parser.add_argument("--cache", default="cache", help="Path to parquet cache directory")
    parser.add_argument("--mode", default="ai", choices=["ai", "dag"], help="Execution mode ('ai' or 'dag')")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "nemotron", "openrouter"], help="LLM provider")
    parser.add_argument("--test", action="store_true", help="Execute built-in self-contained invariant and statistical test suite")
    args = parser.parse_args()

    if args.test:
        print("[*] [PIKABO Monolith] Executing internal self-contained invariant and statistical test suite...")
        import unittest
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestEngineStatisticsAndGuards)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        if result.wasSuccessful():
            print("[+] [PIKABO Monolith] 100% ALL STATISTICAL AND INVARIANT TESTS PASSED!")
            sys.exit(0)
        else:
            print("[!] [PIKABO Monolith] Test failures detected!")
            sys.exit(1)

    os.environ["LLM_PROVIDER"] = args.provider
    print(f"[*] [PIKABO Monolith] Launching Master Autonomous Pipeline on: {args.data}...")
    success = run_master_pipeline(data_dir=args.data, output_dir=args.output, cache_dir=args.cache, mode=args.mode)
    sys.exit(0 if success else 1)
"""

    tmp_path = output_path.parent / f".{output_path.name}.tmp_{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(compiled_content)
    os.replace(tmp_path, output_path)

    line_count = len(compiled_content.splitlines())
    size_kb = len(compiled_content.encode("utf-8")) / 1024

    print(f"[+] PIKABO Monolithic File Compiled Successfully!")
    print(f"    - Destination : {output_path.resolve()}")
    print(f"    - Total Agents: {len(AGENTS_CONFIG)}")
    print(f"    - Total Lines : {line_count:,} lines")
    print(f"    - File Size   : {size_kb:.2f} KB")

    return output_path


if __name__ == "__main__":
    sync_pikabo_codebase()
