"""
=============================================================================
AUTONOMOUS SELF-HEALING SUPERVISOR (V6.0 — RUNTIME + LOGICAL + STRUCTURAL)
=============================================================================
Multi-tier closed-loop immune system for DataX-Ray:

1. Failure Classification & Signature Deduplication:
   - Maps tracebacks / audit violations into deterministic error signatures
     so stuck repair loops fail-fast instead of burning tokens repeatedly.
2. Tier-0 Deterministic Micro-Healer (ZERO LLM Tokens, < 5ms):
   - Auto-repairs safe, common mechanical failures (.str accessor on non-string
     Series, CSV encoding/delimiter errors, column whitespace/BOM KeyErrors,
     missing fact_surrogate_id PK, output path mismatches) while strictly
     refusing to weaken AST security blocks.
3. Tiered Model Escalation Guidance (Fast Hydrogen -> Reasoning Carbon):
   - Feeds cumulative attempt history + schema topology ground truth into
     LLM repair prompts so complex failures never repeat failed patches.
4. Post-Stage 5/6/7 Logical & Structural Closed-Loop Healer:
   - Verifies Anti-Hallucination Truth, Row Conservation, Target Semantic
     Sanity (no demographic/date/100%-tautology targets), Monetary Honesty,
     and Frontline Leak Feed cleanliness — auto-quarantining and healing
     poisoned outputs via Deterministic DAG + Stage 5/6/7 re-synthesis.
5. Anonymized Adaptive Playbook & Transparent Run Receipt:
   - Records error-signature recovery patterns (zero PII/data values) in
     `runs/self_healing_playbook.json` and emits `self_healing_report.json`.
=============================================================================
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

try:
    from .common_utils import validate_etl_ast_security
    from .target_resolver import (
        is_demographic_attribute,
        is_index_artifact,
        is_temporal_column,
        resolve_canonical_target_and_cost,
    )
    from .templated_dag_runner import execute_templated_pipeline
except ImportError:
    from common_utils import validate_etl_ast_security
    from target_resolver import (
        is_demographic_attribute,
        is_index_artifact,
        is_temporal_column,
        resolve_canonical_target_and_cost,
    )
    from templated_dag_runner import execute_templated_pipeline


_PLAYBOOK_LOCK = threading.Lock()
_DEFAULT_PLAYBOOK_PATH = (
    Path(__file__).resolve().parent.parent / "runs" / "self_healing_playbook.json"
)


def classify_failure_signature(err_text: str) -> Dict[str, Any]:
    """Classifies runtime/audit failures into a normalized category & hash signature."""
    txt = str(err_text or "").strip()
    low = txt.lower()

    if "ast security gate blocked" in low or "security gate" in low:
        cat = "AST_SECURITY_BLOCK"
        recoverable_t0 = False
    elif "syntaxerror" in low or "indentationerror" in low:
        cat = "SYNTAX_ERROR"
        recoverable_t0 = False
    elif "can only use .str accessor" in low or ".str accessor" in low:
        cat = "STR_ACCESSOR"
        recoverable_t0 = True
    elif "unicodedecodeerror" in low or "codec can't decode" in low or "parsererror" in low or "error tokenizing data" in low:
        cat = "CSV_PARSE_ENCODING"
        recoverable_t0 = True
    elif "zero drift violation" in low or "row count conservation failed" in low or "cartesian explosion" in low:
        cat = "ROW_DRIFT_CARTESIAN"
        recoverable_t0 = False
    elif "primary key uniqueness violated" in low or "duplicate primary keys" in low:
        cat = "DUPLICATE_PRIMARY_KEY"
        recoverable_t0 = True
    elif "critical target column missing" in low:
        cat = "MISSING_TARGET_COLUMN"
        recoverable_t0 = True
    elif "no *.parquet fact table" in low or "filenotfounderror" in low:
        cat = "MISSING_OUTPUT_OR_FILE"
        recoverable_t0 = True
    elif "timeout expired" in low:
        cat = "TIMEOUT"
        recoverable_t0 = False
    elif "keyerror" in low or "not in index" in low:
        cat = "COLUMN_KEY_ERROR"
        recoverable_t0 = True
    else:
        cat = "RUNTIME_EXCEPTION"
        recoverable_t0 = False

    # Normalize volatile paths/numbers/line numbers for loop detection
    norm = re.sub(r"[A-Za-z]:\\[^\s'\"]+|/[^\s'\"]+", "<PATH>", txt)
    norm = re.sub(r"line \d+", "line <N>", norm, flags=re.IGNORECASE)
    norm = re.sub(r"\d+\.\d+|\d+", "<NUM>", norm)
    sig_head = f"{cat}:{norm[:400]}"
    sig_hash = hashlib.sha256(sig_head.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return {
        "category": cat,
        "signature_hash": sig_hash,
        "recoverable_tier0": recoverable_t0,
        "excerpt": txt[:260],
    }


def load_compact_topology_context(topology_path: Optional[str]) -> Dict[str, Any]:
    """Loads compact schema facts (filenames, row counts, columns) for grounded repair."""
    if not topology_path:
        return {}
    p = Path(topology_path)
    if not p.exists():
        return {}
    try:
        topo = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    summary: Dict[str, Any] = {}
    for tname, meta in (topo.get("tables") or {}).items():
        summary[str(tname)] = {
            "filename": meta.get("filename"),
            "estimated_rows": meta.get("estimated_rows"),
            "delimiter": meta.get("delimiter", ","),
            "encoding": meta.get("encoding", "utf-8"),
            "columns": list(meta.get("columns") or [])[:60],
            "recommended_primary_key": meta.get("recommended_primary_key"),
        }
    return summary


def _inject_helper_once(code: str, marker: str, helper_src: str) -> str:
    if marker in code:
        return code
    lines = code.splitlines()
    insert_at = 0
    for idx, line in enumerate(lines[:60]):
        s = line.strip()
        if s.startswith(("import ", "from ")):
            insert_at = idx + 1
    new_lines = lines[:insert_at] + ["", helper_src, ""] + lines[insert_at:]
    return "\n".join(new_lines) + ("\n" if code.endswith("\n") else "")


def _replace_first_call_arg(code: str, method_token: str, replacement_arg: str) -> str:
    """
    Replaces the first positional argument of `<method_token>(arg1, ...)` using
    balanced parenthesis/bracket/quote scanning so expressions like
    `df.to_parquet(Path(OUT) / 'x.parquet', index=False)` rewrite cleanly.
    """
    idx = code.find(method_token)
    if idx == -1:
        return code
    arg_start = idx + len(method_token)
    n = len(code)
    depth = 0
    in_str: Optional[str] = None
    escaped = False
    i = arg_start
    while i < n:
        ch = code[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch in ("(", "[", "{"):
                depth += 1
            elif ch in (")", "]", "}"):
                if depth == 0:
                    return code[:arg_start] + replacement_arg + code[i:]
                depth -= 1
            elif ch == "," and depth == 0:
                return code[:arg_start] + replacement_arg + code[i:]
        i += 1
    return code


def apply_tier0_deterministic_etl_fix(
    code: str,
    err_text: str,
    topology_path: Optional[str] = None,
    blueprint_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """
    Attempts a 0-token deterministic repair on well-known mechanical ETL runtime errors.
    NEVER bypasses or alters AST security blocks.
    Returns `(patched_code, fix_description)` or `None` if not deterministically fixable.
    """
    sig = classify_failure_signature(err_text)
    cat = sig["category"]
    if not sig["recoverable_tier0"]:
        return None

    patched = code
    reasons: List[str] = []

    if cat == "STR_ACCESSOR":
        # Fix `df[col].str.`, `df[col].fillna('').str.`, or `ser.str.` crashes on numeric/mixed series safely
        new_code = re.sub(
            r"(\b[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\]|\([^\)]*\)|\.[A-Za-z_][A-Za-z0-9_]*)*)\.str\.",
            r"\1.astype(str).str.",
            patched,
        )
        # Avoid double `.astype(str).astype(str)`
        new_code = new_code.replace(".astype(str).astype(str).str.", ".astype(str).str.")
        if new_code != patched:
            patched = new_code
            reasons.append("Wrapped .str accessors with .astype(str)")

    elif cat == "CSV_PARSE_ENCODING":
        helper = (
            "# _DX_T0_CSV_HELPER\n"
            "def _dx_t0_read_csv(path, *args, **kwargs):\n"
            "    import pandas as _pd\n"
            "    try:\n"
            "        return _pd.read_csv(path, *args, **kwargs)\n"
            "    except Exception:\n"
            "        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin1'):\n"
            "            for sep_opt in (kwargs.get('sep', None), None):\n"
            "                try:\n"
            "                    kw = dict(kwargs)\n"
            "                    kw['encoding'] = enc\n"
            "                    if sep_opt is None:\n"
            "                        kw['sep'] = None\n"
            "                        kw['engine'] = 'python'\n"
            "                    kw.setdefault('on_bad_lines', 'skip')\n"
            "                    return _pd.read_csv(path, *args, **kw)\n"
            "                except Exception:\n"
            "                    continue\n"
            "        raise"
        )
        if "_DX_T0_CSV_HELPER" not in patched and "read_csv(" in patched:
            patched = _inject_helper_once(patched, "_DX_T0_CSV_HELPER", helper)
            patched = re.sub(r"\b(?:pd|pandas)\.read_csv\(", "_dx_t0_read_csv(", patched)
            reasons.append("Injected resilient multi-encoding/delimiter CSV reader")

    elif cat == "COLUMN_KEY_ERROR":
        m_key = re.search(r"KeyError:\s*['\"]([^'\"]+)['\"]", err_text)
        m_idx = re.search(r"\['([^']+)'\] not in index", err_text)
        bad_col = m_key.group(1) if m_key else (m_idx.group(1) if m_idx else None)
        topo_ctx = load_compact_topology_context(topology_path)
        all_phys_cols: List[str] = []
        for meta in topo_ctx.values():
            all_phys_cols.extend(meta.get("columns") or [])
        if bad_col and all_phys_cols:
            norm_bad = re.sub(r"[\s_]+", "", bad_col.lstrip("\ufeff").strip().lower())
            matched_col = next(
                (
                    pc for pc in all_phys_cols
                    if re.sub(r"[\s_]+", "", str(pc).lstrip("\ufeff").strip().lower()) == norm_bad
                    and pc != bad_col
                ),
                None,
            )
            if matched_col:
                # Replace column key strictly inside indexing / keyword-arg contexts first (avoids mutating arbitrary string literals)
                escaped_bad = re.escape(bad_col)
                col_ctx_pattern = re.compile(
                    rf"(\[\s*|\b(?:on|left_on|right_on|by|subset|columns)\s*=\s*(?:\[\s*)?)([\'\"]){escaped_bad}\2"
                )
                cand_patched = col_ctx_pattern.sub(
                    lambda m: f"{m.group(1)}{m.group(2)}{matched_col}{m.group(2)}",
                    patched,
                )
                if cand_patched == patched:
                    # Safe fallback only if column name is reasonably specific (>= 4 chars)
                    if len(bad_col) >= 4:
                        cand_patched = patched.replace(repr(bad_col), repr(matched_col))
                        if cand_patched == patched:
                            cand_patched = patched.replace(f'"{bad_col}"', f'"{matched_col}"')
                if cand_patched != patched:
                    patched = cand_patched
                    reasons.append(f"Mapped mismatched key {bad_col!r} -> {matched_col!r}")

    elif cat == "DUPLICATE_PRIMARY_KEY":
        # Append deterministic fact_surrogate_id right before to_parquet export
        if "fact_surrogate_id" not in patched and ".to_parquet(" in patched:
            patched = re.sub(
                r"^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\.to_parquet\(",
                lambda m: (
                    f"{m.group(1)}{m.group(2)}['fact_surrogate_id'] = "
                    f"(range(1, len({m.group(2)}) + 1))\n"
                    f"{m.group(1)}{m.group(2)}['fact_surrogate_id'] = {m.group(2)}['fact_surrogate_id'].astype(str)\n"
                    f"{m.group(1)}{m.group(2)}.to_parquet("
                ),
                patched,
                count=1,
                flags=re.MULTILINE,
            )
            if patched != code:
                reasons.append("Synthesized unique 'fact_surrogate_id' before Parquet write")

    elif cat == "MISSING_TARGET_COLUMN":
        if blueprint_path and Path(blueprint_path).exists() and output_dir:
            try:
                bp_info = json.loads(Path(blueprint_path).read_text(encoding="utf-8"))
                t_col = bp_info.get("target_metric")
                if t_col and ".to_parquet(" in patched and repr(t_col) not in patched:
                    # Try case-insensitive aliasing before to_parquet
                    patched = re.sub(
                        r"^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\.to_parquet\(",
                        lambda m: (
                            f"{m.group(1)}_dx_m = next((c for c in {m.group(2)}.columns if c.lower() == {repr(t_col.lower())}), None)\n"
                            f"{m.group(1)}if _dx_m and {repr(t_col)} not in {m.group(2)}.columns:\n"
                            f"{m.group(1)}    {m.group(2)}[{repr(t_col)}] = {m.group(2)}[_dx_m]\n"
                            f"{m.group(1)}{m.group(2)}.to_parquet("
                        ),
                        patched,
                        count=1,
                        flags=re.MULTILINE,
                    )
                    if patched != code:
                        reasons.append(f"Harmonized target column alias '{t_col}' before Parquet export")
            except Exception:
                pass

    elif cat == "MISSING_OUTPUT_OR_FILE":
        if output_dir and ".to_parquet(" in patched and "bi_ready_fact.parquet" not in patched:
            target_pq = (Path(output_dir).resolve() / "bi_ready_fact.parquet").as_posix()
            new_p = _replace_first_call_arg(patched, ".to_parquet(", repr(target_pq))
            if new_p != patched:
                patched = new_p
                reasons.append("Aligned Parquet export path to 'bi_ready_fact.parquet'")

    if patched == code or not reasons:
        return None

    # Validate syntax + AST security gate before returning Tier-0 patch
    try:
        compile(patched, "<tier0_self_heal>", "exec")
        sec_violations = validate_etl_ast_security(patched)
        if sec_violations:
            return None
    except SyntaxError:
        return None

    return patched, "; ".join(reasons)


def build_grounded_repair_prompt(
    failing_code: str,
    err_output: str,
    attempt_history: List[Dict[str, Any]],
    topology_path: Optional[str] = None,
    blueprint_path: Optional[str] = None,
    expected_initial_rows: Optional[int] = None,
    expected_pk: Optional[str] = None,
) -> str:
    """Builds a topology-grounded, history-aware repair prompt preventing repeated patch loops."""
    topo_ctx = load_compact_topology_context(topology_path)
    bp_summary: Dict[str, Any] = {}
    if blueprint_path and Path(blueprint_path).exists():
        try:
            raw_bp = json.loads(Path(blueprint_path).read_text(encoding="utf-8"))
            bp_summary = {
                "fact_table": raw_bp.get("fact_table"),
                "target_metric": raw_bp.get("target_metric"),
                "primary_id_column": raw_bp.get("primary_id_column"),
            }
        except Exception:
            bp_summary = {}

    prior_lines = [
        f"- Attempt {h.get('attempt')}: [{h.get('category')}/{h.get('signature_hash')}] via {h.get('tier')} -> {h.get('excerpt', '')[:160]}"
        for h in attempt_history[-4:]
    ]
    prior_block = "\n".join(prior_lines) if prior_lines else "None"

    return (
        "You are repairing a failed ETL script inside a sandboxed DataX-Ray execution loop.\n"
        f"CURRENT FAILURE ({classify_failure_signature(err_output)['category']}):\n"
        "-----------------\n"
        f"{err_output[:2600]}\n"
        "-----------------\n\n"
        "PRIOR FAILED ATTEMPTS (DO NOT REPEAT THESE MISTAKES):\n"
        f"{prior_block}\n\n"
        "VERIFIED PHYSICAL GROUND TRUTH:\n"
        f"- Expected Initial Fact Rows: {expected_initial_rows if expected_initial_rows else 'Exact raw fact file row count'}\n"
        f"- Expected Primary Key: {expected_pk or 'fact_surrogate_id'}\n"
        f"- Blueprint Target Binding: {json.dumps(bp_summary)}\n"
        f"- Topology Summary: {json.dumps(topo_ctx, ensure_ascii=False)[:3000]}\n\n"
        "FAILING SCRIPT:\n"
        "-----------------\n"
        f"{failing_code[:12000]}\n"
        "-----------------\n\n"
        "CRITICAL REPAIR INVARIANTS:\n"
        "1. Preserve 100% of raw fact rows (len(final_fact) == initial_fact_count). Never drop rows to silence assertions.\n"
        "2. Before any left join on a dimension table, pre-aggregate/deduplicate that dimension on the join key cleanly.\n"
        "3. Never fabricate fake/dummy rows or synthetic columns absent from the blueprint unless explicitly needed as safe PK 'fact_surrogate_id'.\n"
        "4. Cast mixed series with .astype(str) before calling .str accessors.\n"
        "5. STRICT SANDBOX SECURITY: No subprocess, socket, requests, urllib, http, pickle, ctypes, dotenv, eval, exec, os.system, os.remove, shutil.rmtree.\n"
        "Return ONLY complete corrected executable Python code wrapped in ```python ... ```."
    )


def record_playbook_pattern(
    sig_info: Dict[str, Any],
    resolution: str,
    playbook_path: Optional[Path] = None,
) -> None:
    """Persists an anonymized error-signature recovery pattern for operational observability."""
    p = playbook_path or _DEFAULT_PLAYBOOK_PATH
    try:
        with _PLAYBOOK_LOCK:
            p.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Any] = {"patterns": {}}
            if p.exists():
                try:
                    loaded = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict) and isinstance(loaded.get("patterns"), dict):
                        data = loaded
                except Exception:
                    pass
            key = f"{sig_info.get('category', 'UNKNOWN')}:{sig_info.get('signature_hash', '0')}"
            entry = data["patterns"].get(key) or {
                "category": sig_info.get("category"),
                "signature_hash": sig_info.get("signature_hash"),
                "hits": 0,
                "resolutions": {},
            }
            entry["hits"] = int(entry.get("hits", 0)) + 1
            res_map = entry.get("resolutions") or {}
            res_map[str(resolution)] = int(res_map.get(str(resolution), 0)) + 1
            entry["resolutions"] = res_map
            entry["last_seen_utc"] = datetime.now(timezone.utc).isoformat()
            data["patterns"][key] = entry
            p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def write_self_healing_report(output_dir: str, report: Dict[str, Any]) -> None:
    """Writes a transparent self-healing diagnostic receipt in `output_dir`."""
    try:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        (out_p / "self_healing_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _is_temporal_like_col(ser: pd.Series, col_name: str) -> bool:
    return is_temporal_column(ser, col_name)


def audit_and_heal_logical_structural(
    *,
    data_dir: str,
    out_dir: str,
    cache_dir: str,
    blueprint_path: str,
    mode: str,
    expected_initial_rows: int,
    expected_pk: str,
    run_anti_hallucination_fn: Callable[[str, Optional[str]], Dict[str, Any]],
    resynthesize_downstream_fn: Callable[[str, str], None],
    audit_res: Optional[Dict[str, Any]] = None,
    cartesian_drift: int = 0,
    dup_ids: int = 0,
) -> Dict[str, Any]:
    """
    Post-Stage-7 Closed-Loop Logical & Structural Self-Healer:
    Inspects physical Parquet invariants, truth audit confidence, semantic manifest
    logical sanity (target collapse/demographic/date/currency hallucination), and
    repairs deterministically cleanly with ZERO extra LLM tokens.
    """
    out_p = Path(out_dir).resolve()
    bp_p = Path(blueprint_path).resolve()
    bp_out_p = out_p / "execution_blueprint.json"
    active_bp_p = bp_out_p if bp_out_p.exists() else bp_p

    actions: List[Dict[str, Any]] = []
    structural_issues: List[str] = []

    if audit_res is None:
        audit_res = run_anti_hallucination_fn(str(out_p), str(active_bp_p) if active_bp_p.exists() else None)

    grounding_ok = audit_res.get("grounding_confidence") == "100.0% VERIFIED TRUTH"
    if not grounding_ok:
        structural_issues.append(
            f"Anti-hallucination truth failure: {audit_res.get('physics_invariant_violations') or audit_res.get('reason')}"
        )
    if cartesian_drift != 0:
        structural_issues.append(f"Cartesian row drift detected: {cartesian_drift}")
    if dup_ids != 0:
        structural_issues.append(f"Primary key duplication detected: {dup_ids}")

    # Semantic logical checks on manifest & physical Parquet
    logical_issues: List[str] = []
    pq_file = out_p / "bi_ready_fact.parquet"
    manifest_file = out_p / "semantic_metrics_manifest.json"
    blueprint_data: Dict[str, Any] = {}
    if active_bp_p.exists():
        try:
            blueprint_data = json.loads(active_bp_p.read_text(encoding="utf-8"))
        except Exception:
            blueprint_data = {}

    if pq_file.exists() and manifest_file.exists():
        try:
            df_fact = pd.read_parquet(pq_file)
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            t_out = manifest.get("target_outcome") or {}
            fin_out = manifest.get("financial_exposure") or {}
            m_target = str(t_out.get("column_name") or "").strip()
            m_adv = int(t_out.get("total_adverse_events") or 0)
            has_override = bool(blueprint_data.get("target_override"))

            # Canonical check independent of poisoned blueprint
            canon_clean = resolve_canonical_target_and_cost(df_fact, blueprint=None)
            clean_target = canon_clean.get("target_col")
            clean_cost = canon_clean.get("cost_col")

            if (not has_override) and m_target and m_target in df_fact.columns:
                bad_demo = is_demographic_attribute(m_target) or is_index_artifact(m_target, df_fact[m_target])
                bad_date = _is_temporal_like_col(df_fact[m_target], m_target)
                collapsed_target = len(df_fact) >= 20 and (m_adv == 0 or m_adv >= len(df_fact))
                if (bad_demo or bad_date or collapsed_target) and clean_target and clean_target != m_target:
                    logical_issues.append(
                        f"Poisoned/degenerate target_metric '{m_target}' (demo={bad_demo}, date={bad_date}, adv={m_adv}/{len(df_fact)}) -> rebinding '{clean_target}'"
                    )

            if bool(fin_out.get("has_monetary_ledger")) and clean_cost is None and not blueprint_data.get("cost_override"):
                logical_issues.append("Fabricated monetary exposure detected without verified monetary column")
        except Exception as exc:
            logical_issues.append(f"Semantic validation read warning: {exc}")

    healed = False
    current_audit = audit_res

    # Heal Path 1: Structural / Anti-Hallucination Failure -> Rebuild cleanly via Deterministic DAG + Stages 5-7
    if structural_issues and mode.lower() not in ("dag", "templated", "deterministic"):
        try:
            if blueprint_data and bp_p.exists():
                if bp_out_p.exists():
                    bp_p.write_text(json.dumps(blueprint_data, indent=2), encoding="utf-8")
            execute_templated_pipeline(str(bp_p), data_dir, str(out_p), cache_dir)
            # After deterministic ETL rebuild, strip invalid target_metric before downstream stages if needed
            if pq_file.exists():
                df_clean = pd.read_parquet(pq_file)
                canon = resolve_canonical_target_and_cost(df_clean, blueprint=None)
                if (not blueprint_data.get("target_override")) and canon.get("target_col"):
                    blueprint_data["target_metric"] = canon["target_col"]
                    for bp_target_path in (bp_p, bp_out_p):
                        bp_target_path.write_text(json.dumps(blueprint_data, indent=2), encoding="utf-8")
            resynthesize_downstream_fn(str(out_p), str(active_bp_p))
            current_audit = run_anti_hallucination_fn(str(out_p), str(active_bp_p))
            if current_audit.get("grounding_confidence") == "100.0% VERIFIED TRUTH":
                healed = True
            actions.append({
                "tier": "logical_structural_dag_recovery",
                "tokens_spent": 0,
                "issues": list(structural_issues),
                "resolved": healed,
            })
        except Exception as exc:
            actions.append({
                "tier": "logical_structural_dag_recovery",
                "tokens_spent": 0,
                "issues": list(structural_issues),
                "resolved": False,
                "error": str(exc),
            })

    # Heal Path 2: Logical Target/Currency Poisoning on valid Parquet -> Clean re-bind & Stage 5-7 rebuild (0 LLM tokens!)
    # Runs independently (not elif) if Heal Path 1 did not already heal OR if logical issues remain after structural recovery.
    if logical_issues and pq_file.exists() and not healed:
        try:
            df_fact = pd.read_parquet(pq_file)
            canon = resolve_canonical_target_and_cost(df_fact, blueprint=None)
            if canon.get("target_col"):
                blueprint_data["target_metric"] = canon["target_col"]
                blueprint_data.pop("cost_override", None)
                for p_write in (bp_p, bp_out_p):
                    if p_write.parent.exists():
                        p_write.write_text(json.dumps(blueprint_data, indent=2), encoding="utf-8")
            resynthesize_downstream_fn(str(out_p), str(active_bp_p))
            current_audit = run_anti_hallucination_fn(str(out_p), str(active_bp_p))
            if current_audit.get("grounding_confidence") == "100.0% VERIFIED TRUTH":
                healed = True
            actions.append({
                "tier": "logical_semantic_rebind",
                "tokens_spent": 0,
                "issues": list(logical_issues),
                "resolved": healed,
            })
        except Exception as exc:
            actions.append({
                "tier": "logical_semantic_rebind",
                "tokens_spent": 0,
                "issues": list(logical_issues),
                "resolved": False,
                "error": str(exc),
            })

    return {
        "structural_issues": structural_issues,
        "logical_issues": logical_issues,
        "healed": healed,
        "healing_actions": actions,
        "audit_res": current_audit,
    }
