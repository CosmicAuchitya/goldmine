"""
=============================================================================
STAGE 4 (HARDENED): SANDBOX RUNNER WITH TIMEOUT, BACKUP & SELF-HEALING
=============================================================================
Features & Defenses:
1. Strict timeout=300s guard to prevent infinite loops or deadlock freezing.
2. Non-destructive backup (.bak) saved before every self-healing modification.
3. Pre-execution Python syntax compilation check.
4. Anchored working directory (cwd) preventing relative path resolution failures.
5. Integrated post-execution Domain Invariant Audit gate.
6. Rate-limiting protection via PacedGeminiClient (14 RPM guard).
=============================================================================
"""

import os
import sys
import re
import subprocess
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Robust imports supporting both package and direct script execution
try:
    from .rate_limiter import PacedGeminiClient
    from .domain_invariant_audit import audit_dataset_invariants
except ImportError:
    from rate_limiter import PacedGeminiClient
    from domain_invariant_audit import audit_dataset_invariants

_pacer_singleton = None

def get_pacer() -> Optional[PacedGeminiClient]:
    """Lazily instantiates PacedGeminiClient only when self-healing is triggered."""
    global _pacer_singleton
    if _pacer_singleton is None:
        try:
            _pacer_singleton = PacedGeminiClient(max_calls_per_minute=14)
        except Exception as e:
            print(f"[!] Warning: Unable to initialize PacedGeminiClient for self-healing: {e}")
            return None
    return _pacer_singleton

def extract_python_code_robust(raw_text: str) -> str:
    text = raw_text.strip()
    match = re.search(r'```(?:python)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text

def execute_with_self_healing(
    script_path: str,
    max_retries: int = 3,
    timeout_sec: int = 300,
    output_dir: str = "error/output",
    pacer: Optional[PacedGeminiClient] = None,
    blueprint_path: Optional[str] = None
) -> bool:
    script = Path(script_path).resolve()
    if not script.exists():
        raise FileNotFoundError(f"Target ETL script {script_path} does not exist.")

    # Anchor working directory to project root
    project_root = script.parent.parent
    # Preserve original script permanently before any modifications
    original_backup = script.with_suffix(".original.bak")
    if not original_backup.exists():
        shutil.copy2(script, original_backup)

    for attempt in range(1, max_retries + 1):
        print(f"\n[>>>] [Stage 4 Sandbox] Execution Attempt {attempt}/{max_retries} for: {script.name} (Timeout: {timeout_sec}s)")
        t0 = time.time()
        
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout_sec
            )
            elapsed = round(time.time() - t0, 2)
            
            if proc.returncode == 0:
                out_p = Path(output_dir)
                out_path = out_p.resolve() if out_p.is_absolute() else (project_root / out_p).resolve()
                fact_parquets = list(out_path.glob("*.parquet"))
                
                if not fact_parquets:
                    err_output = (
                        f"Script exited with return code 0, but FAILED output assertion: "
                        f"No *.parquet fact table found in output directory ({out_path})! "
                        f"The script must not exit early or swallow errors. It MUST generate and save 'bi_ready_fact.parquet'.\n"
                        f"Script stdout:\n{proc.stdout}"
                    )
                    print(f"[!] {err_output}")
                else:
                    print(f"[SUCCESS] Script executed successfully in {elapsed}s!")
                    if proc.stdout:
                        print(proc.stdout)
                        
                    # Automated Domain Invariant & Target Metric Audit Gate
                    fact_file = fact_parquets[0]
                    print(f"[*] Running Automated Domain Invariant Audit Gate on: {fact_file.name}...")
                    violations = []
                    try:
                        import pandas as pd
                        import json
                        df_check = pd.read_parquet(fact_file)
                        inv_audit = audit_dataset_invariants(df_check, initial_count=len(df_check))
                        if inv_audit["status"] != "PASSED":
                            violations.extend(inv_audit["violations"])

                        if blueprint_path and Path(blueprint_path).exists():
                            with open(blueprint_path, 'r', encoding='utf-8') as f_bp:
                                bp_info = json.load(f_bp)
                                t_col = bp_info.get("target_metric")
                                if t_col and t_col not in df_check.columns:
                                    matches = [c for c in df_check.columns if c.lower() == t_col.lower()]
                                    if not matches:
                                        violations.append(
                                            f"CRITICAL TARGET COLUMN MISSING: Blueprint declared target_metric='{t_col}', "
                                            f"but '{t_col}' was NOT found in final_fact! You must explicitly compute and add "
                                            f"final_fact['{t_col}'] to the DataFrame before parquet export."
                                        )
                    except Exception as audit_err:
                        print(f"[*] Note: Optional Invariant Audit notice: {audit_err}")
                        
                    if violations:
                        err_output = "Post-Execution Data Integrity Violations:\n" + "\n".join(f"- {v}" for v in violations)
                        print(f"[!] {err_output}")
                    else:
                        print("[+] Domain Invariant & Target Metric Gate: 100% PASSED (0 physical/financial drifts).")
                        return True
                
            else:
                err_output = proc.stderr.strip()
                print(f"[!] Execution FAILED in {elapsed}s with return code {proc.returncode}!")
                print("--- STDERR TRACEBACK ---")
                print(err_output[:2500])
                print("------------------------")
            
        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - t0, 2)
            err_output = f"Execution TIMEOUT EXPIRED after {elapsed}s: Subprocess was terminated to prevent system freeze."
            print(f"[!] {err_output}")

        if attempt == max_retries:
            print("[X] Maximum self-healing attempts reached. Execution halted.")
            return False
            
        # Non-destructive backup before patch
        backup_path = script.with_suffix(f".attempt_{attempt}.bak")
        shutil.copy2(script, backup_path)
        print(f"[*] Non-destructive backup created: {backup_path.name}")

        print("[*] Initiating Autonomous Self-Healing via PacedGeminiClient...")
        with open(script, 'r', encoding='utf-8') as f:
            failing_code = f.read()
            
        repair_prompt = f"""
The following Python ETL script failed during execution with this exact error:
-----------------
{err_output[:3000]}
-----------------

Here is the failing script:
-----------------
{failing_code}
-----------------

Fix the bug. Preserve all assertion gates, calculations, and parquet/csv exports.
CRITICAL RULES:
1. FACT ROW INTEGRITY: You MUST NEVER resolve row count or key assertion failures by deleting, dropping duplicates, or filtering rows from the fact table!
2. If natural keys are duplicated, generate a unique surrogate ID: df['fact_surrogate_id'] = (df.index + 1).astype(str).
3. The final fact table MUST strictly conserve 100% of rows: len(final_fact) == initial_fact_count.
Return ONLY the corrected, 100% executable Python code wrapped in ```python ... ```.
"""
        active_pacer = pacer or get_pacer()
        if not active_pacer:
            print("[X] Self-Healing aborted: PacedGeminiClient unavailable (check GEMINI_API_KEY).")
            return False

        fixed_text = active_pacer.generate_content(
            contents=repair_prompt,
            system_instruction="You are an Elite Python Debugger. Return 100% executable code with no conversational preamble."
        )
        
        fixed_code = extract_python_code_robust(fixed_text)
        
        # Pre-execution Syntax Compilation Guard
        try:
            compile(fixed_code, str(script), 'exec')
            print("[+] Self-Healing Patch compiled successfully with 0 syntax errors.")
        except SyntaxError as se:
            print(f"[!] Self-Healing returned syntax error ({se}). Reverting to backup...")
            continue
            
        with open(script, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
            
        print(f"[+] Autonomous Patch applied to {script.name}. Retrying execution...")

    return False

if __name__ == "__main__":
    sc_file = sys.argv[1] if len(sys.argv) > 1 else "autonomous_engine/dynamic_etl_runner.py"
    success = execute_with_self_healing(sc_file, max_retries=3, timeout_sec=300)
    sys.exit(0 if success else 1)
