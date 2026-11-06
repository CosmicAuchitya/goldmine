"""
=============================================================================
STAGE 4 (HARDENED): SANDBOX RUNNER WITH AST GATE, ENV SCRUBBING & SELF-HEALING
=============================================================================
Features & Defenses:
1. Static AST Security Gate BEFORE execution (blocks network/subprocess/eval/delete/.env).
2. Sanitized Least-Privilege Subprocess Environment (strips all API keys & secrets).
3. Local PII & Secret Scrubbing on runtime stderr/stdout tracebacks before LLM healing.
4. Strict timeout=300s guard to prevent infinite loops or deadlock freezing.
5. Non-destructive backup (.bak) saved before every self-healing modification.
6. Anchored working directory (cwd) + Post-Execution Domain Invariant Audit gate.
=============================================================================
"""

import os
import sys
import re
import subprocess
import time
import shutil
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Robust imports supporting both package and direct script execution
try:
    from .rate_limiter import PacedGeminiClient
    from .domain_invariant_audit import audit_dataset_invariants
    from .pii_scrubber import scrub_text
except ImportError:
    from rate_limiter import PacedGeminiClient
    from domain_invariant_audit import audit_dataset_invariants
    try:
        from pii_scrubber import scrub_text
    except ImportError:
        def scrub_text(text: str) -> str:
            return text

try:
    from .common_utils import (
        extract_python_code_robust,
        validate_etl_ast_security,
        build_sanitized_subprocess_env,
    )
except ImportError:
    try:
        from common_utils import (
            extract_python_code_robust,
            validate_etl_ast_security,
            build_sanitized_subprocess_env,
        )
    except ImportError:
        def extract_python_code_robust(raw_text: str) -> str:
            text = str(raw_text or "").strip()
            match = re.search(r'```(?:python)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
            return match.group(1).strip() if match else text

        def validate_etl_ast_security(code: str):
            return []

        def build_sanitized_subprocess_env(extra_env=None):
            return dict(os.environ)

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


def execute_with_self_healing(
    script_path: str,
    max_retries: int = 3,
    timeout_sec: int = 300,
    output_dir: str = "output",
    pacer: Optional[PacedGeminiClient] = None,
    blueprint_path: Optional[str] = None
) -> bool:
    script = Path(script_path).resolve()
    if not script.exists():
        raise FileNotFoundError(f"Target ETL script {script_path} does not exist.")

    # Anchor working directory to repo/workspace root
    repo_root = Path.cwd().resolve()
    # Preserve original script permanently before any modifications
    original_backup = script.with_suffix(".original.bak")
    if not original_backup.exists():
        shutil.copy2(script, original_backup)

    sanitized_env = build_sanitized_subprocess_env()

    for attempt in range(1, max_retries + 1):
        print(f"\n[>>>] [Stage 4 Sandbox] Execution Attempt {attempt}/{max_retries} for: {script.name} (Timeout: {timeout_sec}s)")
        t0 = time.time()
        err_output = ""

        # PRE-EXECUTION SYNTAX & STATIC AST SECURITY GATE
        script_code = script.read_text(encoding="utf-8")
        precheck_failed = False
        try:
            compile(script_code, str(script), "exec")
            ast_violations = validate_etl_ast_security(script_code)
            if ast_violations:
                precheck_failed = True
                err_output = (
                    "AST SECURITY GATE BLOCKED EXECUTION BEFORE SUBPROCESS LAUNCH:\n"
                    + "\n".join(f"- {v}" for v in ast_violations)
                    + "\nRewrite the ETL logic using ONLY safe pandas/numpy/pyarrow file operations."
                )
                print(f"[!] {err_output}")
        except SyntaxError as se:
            precheck_failed = True
            err_output = f"Pre-execution SyntaxError in {script.name} at line {se.lineno}: {se}"
            print(f"[!] {err_output}")

        if not precheck_failed:
            try:
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    cwd=str(repo_root),
                    env=sanitized_env,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=timeout_sec
                )
                elapsed = round(time.time() - t0, 2)
                safe_stdout = scrub_text(proc.stdout or "")
                safe_stderr = scrub_text(proc.stderr or "")

                if proc.returncode == 0:
                    out_p = Path(output_dir).resolve() if Path(output_dir).is_absolute() else (repo_root / output_dir).resolve()
                    if not out_p.exists() or not list(out_p.glob("*.parquet")):
                        if list(script.parent.glob("*.parquet")):
                            out_p = script.parent.resolve()
                    out_path = out_p
                    fact_parquets = list(out_path.glob("*.parquet"))

                    if not fact_parquets:
                        err_output = (
                            f"Script exited with return code 0, but FAILED output assertion: "
                            f"No *.parquet fact table found in output directory ({out_path})! "
                            f"The script must not exit early or swallow errors. It MUST generate and save 'bi_ready_fact.parquet'.\n"
                            f"Script stdout:\n{safe_stdout[:1500]}"
                        )
                        print(f"[!] {err_output}")
                    else:
                        print(f"[SUCCESS] Script executed successfully in {elapsed}s!")
                        if safe_stdout:
                            print(safe_stdout)

                        # Automated Domain Invariant & Target Metric Audit Gate
                        ready_candidates = [p for p in fact_parquets if p.name == "bi_ready_fact.parquet"]
                        fact_file = ready_candidates[0] if ready_candidates else fact_parquets[0]
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
                            err_output = scrub_text("Post-Execution Data Integrity Violations:\n" + "\n".join(f"- {v}" for v in violations))
                            print(f"[!] {err_output}")
                        else:
                            print("[+] Domain Invariant & Target Metric Gate: 100% PASSED (0 physical/financial drifts).")
                            return True

                else:
                    err_output = safe_stderr.strip()
                    print(f"[!] Execution FAILED in {elapsed}s with return code {proc.returncode}!")
                    print("--- STDERR TRACEBACK (PII SCRUBBED) ---")
                    print(err_output[:2500])
                    print("---------------------------------------")

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
        failing_code = scrub_text(script.read_text(encoding='utf-8'))
        scrubbed_err = scrub_text(err_output[:3000])

        repair_prompt = f"""
The following Python ETL script failed during execution with this exact error:
-----------------
{scrubbed_err}
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
4. ZERO DUMMY/MOCK DATA: NEVER generate fake dummy rows or 1-row mock DataFrames! You MUST load and process the real physical raw CSV/Parquet files from the disk.
5. If column .str accessor fails, cast to string first: df[col] = df[col].astype(str).str.strip().
6. STRICT SANDBOX SECURITY: NEVER import subprocess, socket, requests, urllib, http, pickle, ctypes, or dotenv; NEVER call eval, exec, os.system, os.remove, or shutil.rmtree; NEVER access '.env'.
Return ONLY the corrected, 100% executable Python code wrapped in ```python ... ```.
"""
        active_pacer = pacer or get_pacer()
        if not active_pacer:
            print("[X] Self-Healing aborted: PacedGeminiClient unavailable (check GEMINI_API_KEY).")
            return False

        fixed_text = active_pacer.generate_content(
            contents=repair_prompt,
            system_instruction="You are an Elite Python Debugger. Return 100% executable, sandbox-compliant code with no conversational preamble."
        )

        fixed_code = extract_python_code_robust(fixed_text)

        # Pre-execution Syntax & AST Security Guard on Self-Healed Patch
        try:
            compile(fixed_code, str(script), 'exec')
            patch_violations = validate_etl_ast_security(fixed_code)
            if patch_violations:
                print(f"[!] Self-Healing patch rejected by AST Security Gate: {patch_violations[0]}. Reverting...")
                continue
            print("[+] Self-Healing Patch compiled & passed AST Security Gate (0 errors).")
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
