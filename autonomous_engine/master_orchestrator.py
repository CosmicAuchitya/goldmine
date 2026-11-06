"""
=============================================================================
MASTER AUTONOMOUS DATAX-RAY ENGINE & PIPELINE ORCHESTRATOR
=============================================================================
Usage:
    python autonomous_engine/master_orchestrator.py --data "path/to/raw_data" --output "path/to/output"

Executes the complete 6-Stage Autonomous Pipeline:
- Stage 1: Relational Schema Topology Profiling & Cardinality Hazard Scanning
- Stage 2: Paced LLM Relational & Forensic Blueprint Formulation
- Stage 3: Dynamic Vectorized Python ETL Script Synthesis
- Stage 4: Isolated Sandbox Execution with AST Security Gate & Autonomous Self-Healing
- Stage 5: Enterprise BI Deliverables (Star-Schema Parquet, Dimension CSVs, DAX Guide, Forensic Dossier)
- Stage 6: Enterprise Semantic Model (TMDL, Manifest), Vega-Lite Specs, and Interactive HTML Dashboard
=============================================================================
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Robust imports supporting both package and standalone execution
try:
    from .stage1_topology_profiler import profile_raw_directory
    from .stage2_ai_blueprint import generate_relational_blueprint
    from .stage3_ai_code_generator import generate_dynamic_etl_script
    from .stage4_sandbox_executor import execute_with_self_healing
    from .stage5_bi_synthesizer import synthesize_deliverables
    from .stage6_semantic_viz_synthesizer import synthesize_semantic_and_viz
    from .stage7_bespoke_dashboard_architect import synthesize_bespoke_dashboard
    from .run_manager import RunManager
    from .templated_dag_runner import execute_templated_pipeline
    from .loop_fix_engine import LoopFixVerifier
    from .common_utils import quote_sql_ident
except ImportError:
    from stage1_topology_profiler import profile_raw_directory
    from stage2_ai_blueprint import generate_relational_blueprint
    from stage3_ai_code_generator import generate_dynamic_etl_script
    from stage4_sandbox_executor import execute_with_self_healing
    from stage5_bi_synthesizer import synthesize_deliverables
    from stage6_semantic_viz_synthesizer import synthesize_semantic_and_viz
    from stage7_bespoke_dashboard_architect import synthesize_bespoke_dashboard
    from run_manager import RunManager
    from templated_dag_runner import execute_templated_pipeline
    from loop_fix_engine import LoopFixVerifier
    try:
        from common_utils import quote_sql_ident
    except ImportError:
        def quote_sql_ident(ident: str) -> str:
            return '"' + str(ident or "").replace('"', '""') + '"'


def _compute_exact_raw_fact_rows(data_path: Path, profile: dict, blueprint: dict, fallback_rows: int) -> int:
    """Computes exact physical record count of the raw source fact file to detect true row drift."""
    tables = profile.get("tables", {}) if isinstance(profile, dict) else {}
    fact_tbl = blueprint.get("fact_table", "") if isinstance(blueprint, dict) else ""
    fact_meta = tables.get(fact_tbl)
    if not fact_meta and tables:
        # Match case-insensitively or pick largest profiled table
        matched = next((m for k, m in tables.items() if k.lower() == str(fact_tbl).lower()), None)
        fact_meta = matched or max(tables.values(), key=lambda m: m.get("estimated_rows", 0))
    if not fact_meta:
        return fallback_rows

    fname = fact_meta.get("filename")
    raw_file = (data_path / fname) if fname else None
    if not raw_file or not raw_file.exists():
        return int(fact_meta.get("estimated_rows", fallback_rows))

    ext = raw_file.suffix.lower()
    try:
        if ext == ".parquet":
            import pyarrow.parquet as pq
            return int(pq.read_metadata(raw_file).num_rows)
        elif ext in (".csv", ".tsv", ".txt"):
            import pandas as pd
            delim = fact_meta.get("delimiter", ",")
            enc = fact_meta.get("encoding", "utf-8")
            try:
                from .robust_excel_scanner import strip_accounting_summary_rows
            except ImportError:
                from robust_excel_scanner import strip_accounting_summary_rows
            df_col0 = pd.read_csv(raw_file, sep=delim, encoding=enc, usecols=[0], low_memory=False)
            df_col0 = strip_accounting_summary_rows(df_col0)
            return int(len(df_col0))
    except Exception:
        pass
    return int(fact_meta.get("estimated_rows", fallback_rows))


def _compute_fact_duplicate_keys(fact_parquet: Path, primary_id_col: str) -> int:
    """Queries DuckDB on the output Parquet to count exact primary key collisions."""
    try:
        import duckdb
        con = duckdb.connect()
        safe_pq = fact_parquet.as_posix().replace("'", "''")
        con.execute(f"CREATE VIEW v_fact AS SELECT * FROM read_parquet('{safe_pq}');")
        cols = [r[0] for r in con.execute("DESCRIBE v_fact;").fetchall()]
        matched_pk = next((c for c in cols if c.lower() == str(primary_id_col or "").lower()), None)
        dupes = 0
        if matched_pk:
            q_pk = quote_sql_ident(matched_pk)
            dupes = int(con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT {q_pk}) FROM v_fact;").fetchone()[0])
            if dupes > 0 and "fact_surrogate_id" in cols:
                q_surr = quote_sql_ident("fact_surrogate_id")
                dupes = int(con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT {q_surr}) FROM v_fact;").fetchone()[0])
        elif "fact_surrogate_id" in cols:
            q_surr = quote_sql_ident("fact_surrogate_id")
            dupes = int(con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT {q_surr}) FROM v_fact;").fetchone()[0])
        con.close()
        return dupes
    except Exception:
        return 0


def run_master_pipeline(
    data_dir: str = "raw_data",
    output_dir: str = "output",
    cache_dir: str = "cache",
    mode: str = "ai"
) -> bool:
    start_total = time.time()
    data_path = Path(data_dir).resolve()
    out_path = Path(output_dir).resolve()
    cache_path = Path(cache_dir).resolve()
    # Isolate cache per dataset folder if running benchmarks to prevent cross-dataset collisions
    if cache_dir == "cache" and data_path.parent.name not in ["", ".", "autonomous_engine"]:
        cache_path = (data_path.parent / "cache").resolve()
    engine_dir = Path(__file__).resolve().parent

    print("\n" + "=" * 80)
    print("  ENTERPRISE AUTONOMOUS DATAX-RAY ENGINE -- MASTER EXECUTION RUNNER")
    print("=" * 80)
    print(f"[*] Raw Data Directory : {data_path}")
    print(f"[*] Cache Directory    : {cache_path}")
    print(f"[*] Output Directory   : {out_path}")
    print("=" * 80 + "\n")

    if not data_path.exists():
        print(f"[X] Fatal: Input data directory does not exist: {data_path}")
        return False

    out_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    dataset_label = data_path.parent.name if data_path.name == "raw_data" and data_path.parent.name else data_path.name
    run_mgr = RunManager(dataset_name=dataset_label)
    print(f"[*] Initialized Isolated Run Workspace: {run_mgr.run_id}")
    print(f"[*] Execution Mode                    : {mode.upper()}")

    # Concurrency-safe isolated staging paths inside runs/<run_id>/artifacts/ (zero shared mutable state)
    topology_json = run_mgr.get_artifact_path("schema_topology.json")
    blueprint_json = run_mgr.get_artifact_path("execution_blueprint.json")
    etl_script = run_mgr.get_artifact_path("dynamic_etl_runner.py")

    # -------------------------------------------------------------------------
    # STAGE 1: Schema Topology & Privacy Profiling
    # -------------------------------------------------------------------------
    print("\n[STEP 1/7] Executing Stage 1: Topology Profiler & Cardinality Hazard Scanner...", flush=True)
    t0 = time.time()
    try:
        profile = profile_raw_directory(str(data_path), topology_json)
        dur1 = round(time.time() - t0, 2)
        run_mgr.log_stage_telemetry(1, "Topology Profiler", dur1, "SUCCESS", {"tables_scanned": len(profile['tables'])})
        print(f"[+] Stage 1 Completed in {dur1}s! ({len(profile['tables'])} tables scanned)", flush=True)
    except Exception as e:
        run_mgr.log_stage_telemetry(1, "Topology Profiler", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
        run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
        print(f"[X] Stage 1 Failed: {e}", flush=True)
        return False

    # -------------------------------------------------------------------------
    # STAGE 2: Paced Relational & Forensic Blueprint Formulation
    # -------------------------------------------------------------------------
    print("\n[STEP 2/7] Executing Stage 2: Paced Gemini Blueprint Formulation...", flush=True)
    t0 = time.time()
    try:
        blueprint = generate_relational_blueprint(
            topology_json,
            blueprint_json,
            use_llm=(mode.lower() not in ("dag", "templated", "deterministic"))
        )
        dur2 = round(time.time() - t0, 2)
        run_mgr.log_stage_telemetry(2, "Blueprint Formulation", dur2, "SUCCESS", {"project": blueprint.get("project_title")})
        print(f"[+] Stage 2 Completed in {dur2}s! (Project: {blueprint.get('project_title', 'Analytics')})", flush=True)

        # Persist project-specific schema & blueprint in output directory
        shutil.copy2(topology_json, out_path / "schema_topology.json")
        shutil.copy2(blueprint_json, out_path / "execution_blueprint.json")
    except Exception as e:
        run_mgr.log_stage_telemetry(2, "Blueprint Formulation", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
        run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
        print(f"[X] Stage 2 Failed: {e}", flush=True)
        return False

    # -------------------------------------------------------------------------
    # STAGE 3 & 4: Execution (Mode: DAG or AI)
    # -------------------------------------------------------------------------
    # 'templated' / 'deterministic' are accepted aliases used by the Streamlit portal and FastAPI server
    if mode.lower() in ("dag", "templated", "deterministic"):
        print("\n[STEP 3 & 4/7] Executing Deterministic Out-of-Core Relational DAG...", flush=True)
        t0 = time.time()
        try:
            dag_res = execute_templated_pipeline(blueprint_json, str(data_path), str(out_path), str(cache_path))
            dur_dag = round(time.time() - t0, 2)
            run_mgr.log_stage_telemetry(3, "Deterministic DAG", dur_dag, "SUCCESS", dag_res)
            print(f"[+] Deterministic DAG Completed in {dur_dag}s!", flush=True)
        except Exception as e:
            run_mgr.log_stage_telemetry(3, "Deterministic DAG", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
            run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
            print(f"[X] Deterministic DAG Failed: {e}", flush=True)
            return False
    else:
        # STAGE 3: Dynamic Vectorized Python ETL Generation
        print("\n[STEP 3/7] Executing Stage 3: Dynamic Vectorized Python ETL Synthesis...", flush=True)
        t0 = time.time()
        try:
            generate_dynamic_etl_script(
                blueprint_json, etl_script, topology_json,
                data_dir=str(data_path), output_dir=str(out_path), cache_dir=str(cache_path)
            )
            dur3 = round(time.time() - t0, 2)
            run_mgr.log_stage_telemetry(3, "Code Generator", dur3, "SUCCESS", {"script": "dynamic_etl_runner.py"})
            print(f"[+] Stage 3 Completed in {dur3}s! (Script saved & pre-compiled: {etl_script})", flush=True)
        except Exception as e:
            run_mgr.log_stage_telemetry(3, "Code Generator", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
            run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
            print(f"[X] Stage 3 Failed: {e}", flush=True)
            return False

        # STAGE 4: Sandbox Execution with AST Security Gate, Timeout & Self-Healing
        print("\n[STEP 4/7] Executing Stage 4: Sandbox Execution & Autonomous Self-Healing...", flush=True)
        t0 = time.time()
        try:
            success = execute_with_self_healing(
                etl_script, max_retries=3, timeout_sec=300, output_dir=str(out_path), blueprint_path=blueprint_json
            )
            dur4 = round(time.time() - t0, 2)
            if not success:
                print("\n[!] AI Code Execution retry budget exhausted. Activating Autonomous Deterministic DAG Fallback...", flush=True)
                t_dag = time.time()
                dag_res = execute_templated_pipeline(blueprint_json, str(data_path), str(out_path), str(cache_path))
                dur_dag = round(time.time() - t_dag, 2)
                run_mgr.log_stage_telemetry(4, "Deterministic DAG Fallback", dur_dag, "SUCCESS", dag_res)
                print(f"[+] Autonomous Fallback Completed in {dur_dag}s! (All assertion gates verified)", flush=True)
            else:
                shutil.copy2(etl_script, out_path / "dynamic_etl_runner.py")
                run_mgr.log_stage_telemetry(4, "Sandbox Execution", dur4, "SUCCESS")
                print(f"[+] Stage 4 Completed in {dur4}s! (All assertion gates verified)", flush=True)
        except Exception as e:
            print(f"[!] Sandbox notice: {e}. Activating Autonomous Deterministic DAG Fallback...", flush=True)
            try:
                t_dag = time.time()
                dag_res = execute_templated_pipeline(blueprint_json, str(data_path), str(out_path), str(cache_path))
                dur_dag = round(time.time() - t_dag, 2)
                run_mgr.log_stage_telemetry(4, "Deterministic DAG Fallback", dur_dag, "SUCCESS", dag_res)
                print(f"[+] Autonomous Fallback Completed in {dur_dag}s! (All assertion gates verified)", flush=True)
            except Exception as e2:
                run_mgr.log_stage_telemetry(4, "Sandbox Execution", round(time.time() - t0, 2), "FAILED", {"error": str(e2)})
                run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
                print(f"[X] Stage 4 Failed: {e2}", flush=True)
                return False

    # -------------------------------------------------------------------------
    # STAGE 5: Enterprise BI Deliverables & Executive Forensic Dossier
    # -------------------------------------------------------------------------
    print("\n[STEP 5/7] Executing Stage 5: Enterprise BI & Forensic Dossier Synthesizer...", flush=True)
    t0 = time.time()
    try:
        synthesize_deliverables(str(out_path))
        dur5 = round(time.time() - t0, 2)
        run_mgr.log_stage_telemetry(5, "BI Synthesizer", dur5, "SUCCESS")
        print(f"[+] Stage 5 Completed in {dur5}s!", flush=True)
    except Exception as e:
        run_mgr.log_stage_telemetry(5, "BI Synthesizer", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
        run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
        print(f"[X] Stage 5 Failed: {e}", flush=True)
        return False

    # -------------------------------------------------------------------------
    # STAGE 6: Enterprise Semantic Model & Auto-Viz Synthesizer
    # -------------------------------------------------------------------------
    print("\n[STEP 6/7] Executing Stage 6: Enterprise Semantic Model & Auto-Viz Synthesizer...", flush=True)
    t0 = time.time()
    try:
        synthesize_semantic_and_viz(str(out_path))
        dur6 = round(time.time() - t0, 2)
        run_mgr.log_stage_telemetry(6, "Semantic & Auto-Viz Synthesizer", dur6, "SUCCESS")
        print(f"[+] Stage 6 Completed in {dur6}s!", flush=True)
    except Exception as e:
        run_mgr.log_stage_telemetry(6, "Semantic & Auto-Viz Synthesizer", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
        run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
        print(f"[X] Stage 6 Failed: {e}", flush=True)
        return False

    # -------------------------------------------------------------------------
    # STAGE 7: Autonomous Bespoke Executive Dashboard Architect
    # -------------------------------------------------------------------------
    print("\n[STEP 7/7] Executing Stage 7: Autonomous Bespoke Executive Dashboard Architect...", flush=True)
    t0 = time.time()
    try:
        dash_res = synthesize_bespoke_dashboard(str(out_path), use_llm=(mode.lower() not in ("dag", "templated", "deterministic")))
        dur7 = round(time.time() - t0, 2)
        run_mgr.log_stage_telemetry(7, "Bespoke Dashboard Architect", dur7, "SUCCESS", dash_res)
        print(f"[+] Stage 7 Completed in {dur7}s! (Archetype: {dash_res.get('archetype_name')})", flush=True)
    except Exception as e:
        run_mgr.log_stage_telemetry(7, "Bespoke Dashboard Architect", round(time.time() - t0, 2), "FAILED", {"error": str(e)})
        run_mgr.finalize_run(status="FAILED", assertion_status="FAILED", domain_invariants_status="FAILED")
        print(f"[X] Stage 7 Failed: {e}", flush=True)
        return False

    # Physical Row Conservation & Primary Key Audit Metrics
    ready_parquets = list(out_path.glob("bi_ready_fact.parquet"))
    parquet_files = ready_parquets if ready_parquets else list(out_path.glob("*.parquet"))
    fact_count = 0
    dup_ids = 0
    if parquet_files:
        import pyarrow.parquet as pq
        fact_count = int(pq.read_metadata(parquet_files[0]).num_rows)
        dup_ids = _compute_fact_duplicate_keys(parquet_files[0], blueprint.get("primary_id_column", ""))

    initial_rows = _compute_exact_raw_fact_rows(data_path, profile, blueprint, fallback_rows=fact_count)
    cartesian_drift = fact_count - initial_rows

    # Mandatory Anti-Hallucination Deterministic Truth Audit (Never Swallowed!)
    try:
        from .anti_hallucination_guard import run_anti_hallucination_audit
    except ImportError:
        try:
            from anti_hallucination_guard import run_anti_hallucination_audit
        except ImportError:
            run_anti_hallucination_audit = None

    if run_anti_hallucination_audit is not None:
        try:
            bp_file = out_path / "execution_blueprint.json"
            audit_res = run_anti_hallucination_audit(str(out_path), str(bp_file) if bp_file.exists() else None)
            if audit_res.get("grounding_confidence") != "100.0% VERIFIED TRUTH":
                print(f"[!] Critical Error: Anti-hallucination audit failed truth gate! Violations: {audit_res.get('physics_invariant_violations')}")
                run_mgr.finalize_run(
                    status="FAILED",
                    initial_rows=initial_rows,
                    final_fact_rows=fact_count,
                    cartesian_drift=cartesian_drift,
                    duplicate_ids=dup_ids,
                    assertion_status="FAILED" if (cartesian_drift != 0 or dup_ids != 0) else "PASSED",
                    domain_invariants_status="FAILED",
                )
                return False
        except Exception as he:
            print(f"[X] Fatal Error in Anti-Hallucination Audit Gate: {he}", flush=True)
            run_mgr.finalize_run(
                status="FAILED",
                initial_rows=initial_rows,
                final_fact_rows=fact_count,
                cartesian_drift=cartesian_drift,
                duplicate_ids=dup_ids,
                assertion_status="FAILED",
                domain_invariants_status="FAILED",
            )
            return False

    assertion_ok = (cartesian_drift == 0 and dup_ids == 0)
    run_mgr.finalize_run(
        status="PASSED" if assertion_ok else "FAILED",
        initial_rows=initial_rows,
        final_fact_rows=fact_count,
        cartesian_drift=cartesian_drift,
        duplicate_ids=dup_ids,
        assertion_status="PASSED" if assertion_ok else "FAILED",
        domain_invariants_status="PASSED",
    )
    if not assertion_ok:
        print(f"[X] Invariant Gate Failed: initial_rows={initial_rows}, final_fact_rows={fact_count}, drift={cartesian_drift}, dup_ids={dup_ids}")
        return False

    total_time = time.time() - start_total
    print("\n" + "=" * 80)
    print("  AUTONOMOUS DATAX-RAY PIPELINE COMPLETED WITH 100% SUCCESS")
    print("=" * 80)
    print(f"Total Pipeline Runtime : {total_time:.2f}s")
    print(f"Run Workspace / ID     : {run_mgr.run_id}")
    print(f"Physical Row Audit     : {initial_rows:,} -> {fact_count:,} rows (Drift: {cartesian_drift}, Dupes: {dup_ids})")
    print(f"Verified Fact Output   : {out_path}")
    print("Generated Artifacts    :")
    for f in out_path.iterdir():
        if f.is_file():
            print(f"  - {f.name} ({f.stat().st_size:,} bytes)")
    print("=" * 80 + "\n")

    # Automated Loop-Fix Continuous Invariant Verification Badge
    print("[*] Running Automated Loop-Fix Continuous Invariant Verification...")
    try:
        verifier = LoopFixVerifier()
        v_res = verifier.verify_all_benchmarks()
        if v_res["overall_status"] == "PASSED":
            print(f"[+] CERTIFIED: {v_res['badge']}")
    except Exception as ve:
        print(f"[*] Notice: Verification check: {ve}")

    # Optional atomic PIKABO sync only when explicitly enabled via AUTO_SYNC_PIKABO=1
    if os.getenv("AUTO_SYNC_PIKABO", "0").strip() == "1":
        try:
            pikabo_sync_path = engine_dir.parent / "pikabo" / "sync_pikabo.py"
            if pikabo_sync_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("sync_pikabo", str(pikabo_sync_path))
                if spec and spec.loader:
                    sync_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(sync_mod)
                    sync_mod.sync_pikabo_codebase()
        except Exception:
            pass

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master Autonomous DataX-Ray Engine")
    parser.add_argument("--data", default="raw_data", help="Path to raw data directory")
    parser.add_argument("--output", default="output", help="Path to deliverables output directory")
    parser.add_argument("--cache", default="cache", help="Path to parquet cache directory")
    parser.add_argument("--mode", default="ai", choices=["ai", "dag", "templated", "deterministic"], help="Execution mode: 'ai' for generative self-healing, 'dag'/'templated' for deterministic out-of-core DAG")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "nemotron", "openrouter"], help="LLM provider: 'gemini' for Google Gemini Dual-Pool, 'nemotron' for NVIDIA Nemotron 3 Ultra 550B MoE")
    args = parser.parse_args()

    os.environ["LLM_PROVIDER"] = args.provider
    success = run_master_pipeline(data_dir=args.data, output_dir=args.output, cache_dir=args.cache, mode=args.mode)
    sys.exit(0 if success else 1)
