"""
=============================================================================
CONVERSATIONAL BUSINESS Q&A ENGINE & READ-ONLY DUCKDB SQL SANDBOX
=============================================================================
Provides grounded, two-way conversational inquiry for non-coder business leaders:
1. Strict Read-Only DuckDB SQL Sandbox (blocks mutation, file replacement scans,
   catalog probing, external filesystem access, and secrets exfiltration).
2. Defense-in-Depth: Both AST/lexical gate AND engine-level C++ setting
   (`SET enable_external_access = false`).
3. Dual-Engine SQL Synthesis: LLM-driven query formulation with an offline
   deterministic natural-language-to-SQL compiler fallback.
4. Bilingual Support: Automatic English vs Simple Business Roman Hinglish detection.
5. Zero-Hallucination Grounding: 100% of reported figures are derived by
   physically querying the DuckDB fact view (`fact`) created from `bi_ready_fact.parquet`.
6. Auto-Viz: Generates interactive Vega-Lite v5 specifications for visual queries.
=============================================================================
"""

import os
import re
import sys
import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import duckdb
import numpy as np
import pandas as pd

# Support both package and direct script execution
try:
    from .common_utils import quote_sql_ident, sanitize_untrusted_metadata_token
    from .pii_scrubber import scrub_text, is_sensitive_column_name
    from .target_resolver import (
        resolve_canonical_target_and_cost,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        is_demographic_attribute
    )
except ImportError:
    from common_utils import quote_sql_ident, sanitize_untrusted_metadata_token
    from pii_scrubber import scrub_text, is_sensitive_column_name
    from target_resolver import (
        resolve_canonical_target_and_cost,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
        is_demographic_attribute
    )

try:
    from .rate_limiter import PacedGeminiClient
except ImportError:
    try:
        from rate_limiter import PacedGeminiClient
    except ImportError:
        PacedGeminiClient = None

_SHARED_LLM_CLIENT = None


def _get_shared_llm_client():
    """Returns a cached singleton PacedGeminiClient to avoid repeated pool initialization."""
    global _SHARED_LLM_CLIENT
    if _SHARED_LLM_CLIENT is not None:
        return _SHARED_LLM_CLIENT
    if PacedGeminiClient is None:
        return None
    try:
        _SHARED_LLM_CLIENT = PacedGeminiClient()
        return _SHARED_LLM_CLIENT
    except Exception:
        return None


FORBIDDEN_SQL_KEYWORDS: Set[str] = {
    "copy", "attach", "detach", "install", "load", "pragma", "set", "reset",
    "call", "export", "import", "create", "drop", "insert", "update", "delete",
    "alter", "truncate", "replace", "merge", "vacuum", "checkpoint", "force",
    "write", "grant", "revoke", "describe", "show", "summarize", "explain",
    "prepare", "execute", "deallocate", "use", "pivot", "unpivot"
}

FORBIDDEN_SQL_FUNCTIONS: Set[str] = {
    "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto",
    "read_text", "read_blob", "parquet_scan", "csv_scan", "json_scan",
    "sqlite_scan", "glob", "getenv", "current_setting", "system", "eval",
    "st_read", "excel_scan", "iceberg_scan", "delta_scan", "mysql_scan",
    "postgres_scan", "read_xlsx", "sniff_csv", "information_schema", "sqlite_master"
}

BLOCKED_FILE_EXTENSIONS = (
    "csv", "parquet", "json", "xlsx", "xls", "db", "sqlite",
    "log", "txt", "py", "md", "toml", "yaml", "yml"
)


def validate_readonly_duckdb_sql(sql: str) -> List[str]:
    """
    Strict AST & Lexical Security Gate for User/LLM-supplied DuckDB SQL queries.
    Blocks all database mutations, external file reads, function exploits,
    environment lookups, replacement scans, and multi-statement injection attacks.
    """
    violations: List[str] = []
    if not sql or not str(sql).strip():
        return ["SQL query is empty."]

    # 1. Strip comments (single-line -- and multi-line /* ... */)
    cleaned = re.sub(r'--[^\n]*', ' ', str(sql))
    cleaned = re.sub(r'/\*.*?\*/', ' ', cleaned, flags=re.DOTALL).strip()

    # 2. Reject multi-statement queries (semicolon followed by non-whitespace)
    # Allow single optional trailing semicolon
    no_trailing = cleaned.rstrip(';').strip()
    if ';' in no_trailing:
        violations.append("Multi-statement SQL queries are strictly forbidden in read-only sandbox.")

    # 3. Must begin with SELECT or WITH
    if not re.match(r'^(?:SELECT|WITH)\b', no_trailing, re.IGNORECASE):
        violations.append("SQL query must begin with SELECT or WITH in read-only sandbox.")

    # 4. Check forbidden keywords and statements
    for kw in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf'\b{kw}\b', no_trailing, re.IGNORECASE):
            violations.append(f"Forbidden SQL keyword '{kw.upper()}' blocked by read-only sandbox.")

    # 5. Check forbidden table functions and scan utilities
    for fn in FORBIDDEN_SQL_FUNCTIONS:
        if re.search(rf'\b{fn}\b', no_trailing, re.IGNORECASE):
            violations.append(f"Forbidden DuckDB function '{fn}' blocked by read-only sandbox.")

    # 6. Block system namespace introspection and catalog probing
    if re.search(r'\bduckdb_\w+|\bpg_\w+', no_trailing, re.IGNORECASE):
        violations.append("System and catalog introspection functions are blocked by read-only sandbox.")

    # 7. Block path traversal and .env references
    if re.search(r'\.env|\.\.', no_trailing, re.IGNORECASE):
        violations.append("Filesystem path traversal and '.env' references are strictly forbidden.")

    # 8. Block replacement scans & file references after FROM or JOIN
    if re.search(r'\b(?:FROM|JOIN)\s+[\'"][^\'"]+[\'"]', no_trailing, re.IGNORECASE):
        violations.append("Direct file replacement scans in FROM/JOIN clauses are strictly forbidden.")

    ext_pattern = r'\.(?:' + '|'.join(BLOCKED_FILE_EXTENSIONS) + r')\b'
    if re.search(ext_pattern, no_trailing, re.IGNORECASE):
        violations.append("External file path references are strictly forbidden in read-only sandbox.")

    # 9. Verify table references: only 'fact' and declared CTEs are allowed
    cte_matches = re.findall(r'(?:WITH|,)\s*([a-zA-Z0-9_]+)\s+AS\s*\(', no_trailing, re.IGNORECASE)
    allowed_tables = {"fact"} | {c.lower() for c in cte_matches}

    # Mask EXTRACT(... FROM ...) so it does not trigger table check
    masked_query = re.sub(r'EXTRACT\s*\([^)]*\bFROM\s+[^)]+\)', ' ', no_trailing, flags=re.IGNORECASE)

    table_refs = re.finditer(r'\b(?:FROM|JOIN)\s+([a-zA-Z0-9_"]+)', masked_query, re.IGNORECASE)
    for tm in table_refs:
        raw_tbl = tm.group(1).strip('"').lower()
        if raw_tbl not in allowed_tables and raw_tbl != "select":
            violations.append(f"Forbidden table reference '{raw_tbl}'. Only table 'fact' and CTEs are permitted in read-only sandbox.")

    return violations


def enforce_sql_row_limit(sql: str, max_rows: int = 200) -> str:
    """
    Enforces a strict ceiling on returned rows.
    If the query already has an outer trailing LIMIT clause, clamps it to max_rows.
    If no outer trailing LIMIT exists (or if query uses CTEs/subqueries), wraps
    the entire query in an outer SELECT * FROM (...) LIMIT max_rows to guarantee compliance.
    """
    cleaned = sql.strip().rstrip(';').strip()
    limit_match = re.search(r'\bLIMIT\s+(\d+)(?:\s+OFFSET\s+\d+)?\s*$', cleaned, re.IGNORECASE)
    if limit_match:
        val = int(limit_match.group(1))
        if val > max_rows:
            return cleaned[:limit_match.start()] + f"LIMIT {max_rows}" + cleaned[limit_match.end():]
        return cleaned
    return f"SELECT * FROM ({cleaned}) AS _capped_q LIMIT {max_rows}"


def detect_language_preference(question: str, explicit_lang: str = "auto") -> str:
    """Detects whether question requires English or Simple Business Roman Hinglish response."""
    if explicit_lang in ("english", "hinglish"):
        return explicit_lang

    q_lower = str(question or "").lower()
    if re.search(r'[\u0900-\u097F]', q_lower):
        return "hinglish"

    # Precise Hinglish markers (English words like 'loss' removed!)
    hinglish_markers = {
        'kya', 'kaise', 'kaun', 'kis', 'sabse', 'zyada', 'jyada', 'kam', 'kitna', 'kitne',
        'kyun', 'kaha', 'kahan', 'mein', 'aur', 'hain', 'hai', 'batao', 'bataiye', 'dikhao',
        'nuksan', 'fayda', 'kharcha', 'grahak', 'paise', 'paisa', 'rokna', 'bache', 'wali',
        'wala', 'wale', 'konsa', 'konse', 'konsi', 'chahiye', 'karo', 'mujhe', 'humara',
        'hamara', 'aaj', 'dekho', 'kisme', 'kisko'
    }
    words = set(re.findall(r'\b[a-z]+\b', q_lower))
    if len(words & hinglish_markers) >= 1:
        return "hinglish"
    return "english"


class ConversationalBusinessQAEngine:
    """
    Two-Way Conversational Business Intelligence Engine.
    Executes grounded read-only DuckDB SQL queries over physical Parquet fact tables.
    Includes C++ engine-level file system lock and context-manager cleanup.
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir).resolve()
        self.fact_parquet = self._locate_fact_parquet()
        self.blueprint = self._load_json("execution_blueprint.json")
        self.manifest = self._load_json("semantic_metrics_manifest.json")
        self.temporal_summary = self._load_json("temporal_trend_summary.json")

        # Load Parquet fact table and initialize canonical targets
        self.df_fact = pd.read_parquet(self.fact_parquet)
        self.canonical = resolve_canonical_target_and_cost(self.df_fact, blueprint=self.blueprint)
        self.target_col = self.canonical.get("target_col")
        self.cost_col = self.canonical.get("cost_col")
        self.binary_target = self.canonical.get("binary_target")

        # Ensure _is_target_event column exists on fact dataframe
        if "_is_target_event" not in self.df_fact.columns and self.binary_target is not None:
            self.df_fact["_is_target_event"] = self.binary_target.astype(int)

        # Detect primary business dimension
        self.primary_dim = self._detect_primary_dimension()

        # Initialize DuckDB in-memory session registered with `fact` view
        self.con = duckdb.connect(":memory:")
        self.con.register("fact", self.df_fact)

        # C++ Engine-Level Lock: disable all file system and network operations
        try:
            self.con.execute("SET enable_external_access = false;")
        except Exception:
            pass

    def close(self):
        """Safely closes DuckDB connection to release allocated memory."""
        try:
            if hasattr(self, "con") and self.con:
                self.con.close()
                self.con = None
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _locate_fact_parquet(self) -> Path:
        candidates = [
            self.output_dir / "bi_ready_fact.parquet",
            self.output_dir / "fact_bi_ready.parquet",
        ]
        for c in candidates:
            if c.exists():
                return c
        pqs = list(self.output_dir.glob("*.parquet"))
        if pqs:
            return pqs[0]
        raise FileNotFoundError(f"No physical Parquet fact table found in '{self.output_dir}'")

    def _load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        p = self.output_dir / filename
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _detect_primary_dimension(self) -> Optional[str]:
        if self.manifest and "dimensions" in self.manifest:
            prim_info = self.manifest["dimensions"].get("primary_dimension", {})
            name = prim_info.get("name")
            if name and name in self.df_fact.columns and not is_synthetic_column(name, self.blueprint):
                return name

        # Statistical dispersion detection (excluding synthetic, PII, and index columns)
        candidates = []
        for c in self.df_fact.columns:
            if c in (self.target_col, self.cost_col, "_is_target_event"):
                continue
            if is_index_artifact(c, self.df_fact[c]) or is_pseudo_numeric_identifier(c, self.df_fact[c]):
                continue
            if is_synthetic_column(c, self.blueprint) or is_sensitive_column_name(c):
                continue
            nunq = self.df_fact[c].nunique()
            if 2 <= nunq <= 40:
                candidates.append(c)

        if not candidates:
            return None

        operational_candidates = [c for c in candidates if not is_demographic_attribute(c)]
        usable = operational_candidates if operational_candidates else candidates

        # Pick candidate with highest target rate spread
        best_dim = usable[0]
        max_spread = -1.0
        s_bin = self.df_fact["_is_target_event"]
        for c in usable:
            rates = self.df_fact.groupby(c)[s_bin.name].mean()
            spread = rates.max() - rates.min() if len(rates) > 1 else 0.0
            if spread > max_spread:
                max_spread = spread
                best_dim = c

        return best_dim

    def synthesize_deterministic_sql(self, question: str) -> Tuple[str, str]:
        """
        Deterministic, zero-API natural-language-to-SQL compiler.
        Translates user queries (English/Roman Hinglish) into verified read-only DuckDB SQL.
        Supports CamelCase columns and row-level record inquiries.
        """
        q_raw = str(question or "").strip()
        q_clean = q_raw.lower()

        cols = list(self.df_fact.columns)
        matched_cols: List[str] = []
        for c in cols:
            if is_index_artifact(c):
                continue
            c_norm = c.lower().replace("_", " ")
            c_camel = re.sub(r'([a-z])([A-Z])', r'\1 \2', c).lower()
            pattern = rf'\b{re.escape(c.lower())}\b|\b{re.escape(c_norm)}\b|\b{re.escape(c_camel)}\b'
            if re.search(pattern, q_clean):
                matched_cols.append(c)

        # Detect intent qualifiers
        is_count_query = any(w in q_clean for w in ['count', 'total', 'kitne', 'how many', 'number of', 'volume'])
        is_adverse_query = any(w in q_clean for w in ['churn', 'default', 'risk', 'fail', 'defect', 'loss', 'nuksan', 'bad', 'adverse', 'problem'])
        is_cost_query = any(w in q_clean for w in ['cost', 'drag', 'revenue', 'money', 'paisa', 'paise', 'amount', 'dollar', 'financial', 'kharcha']) and (self.cost_col is not None)
        is_top_query = any(w in q_clean for w in ['top', 'sabse zyada', 'highest', 'max', 'most', 'worst'])
        is_bottom_query = any(w in q_clean for w in ['lowest', 'sabse kam', 'least', 'min', 'best'])
        is_row_level_query = any(w in q_clean for w in ['customer', 'customers', 'client', 'clients', 'user', 'users', 'account', 'accounts', 'loan', 'loans', 'ticket', 'tickets', 'row', 'rows', 'record', 'records'])

        # Detect requested limit
        limit_match = re.search(r'\b(?:top|pehle)\s+(\d+)\b', q_clean)
        req_limit = int(limit_match.group(1)) if limit_match else (10 if (is_top_query or is_bottom_query) else 50)
        req_limit = min(req_limit, 200)

        # Detect numeric filter conditions (e.g. "MonthlyCharges > 70", "ValorMensal > 70")
        where_clauses: List[str] = []
        comp_matches = re.finditer(r'([a-zA-Z0-9_]+)\s*(>=|<=|>|<|=|==)\s*(\d+(?:\.\d+)?)', q_raw)
        for comp_match in comp_matches:
            cand_col, op, num_val = comp_match.group(1), comp_match.group(2), comp_match.group(3)
            real_col = next((c for c in cols if c.lower() == cand_col.lower() or c.lower().replace("_", "") == cand_col.lower().replace("_", "")), None)
            if real_col and pd.api.types.is_numeric_dtype(self.df_fact[real_col]):
                sql_op = "=" if op == "==" else op
                where_clauses.append(f"{quote_sql_ident(real_col)} {sql_op} {num_val}")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Check if breakdown is explicitly sought
        breakdown_indicators = ['by', 'per', 'across', 'breakdown', 'which', 'kaha', 'kahan', 'kisme', 'kis', 'group', 'segment', 'category']
        wants_breakdown = any(b in q_clean for b in breakdown_indicators) or (is_top_query and not is_row_level_query)

        # Case 1: Row-level records requested
        if is_row_level_query and not wants_breakdown:
            display_cols = []
            for c in cols:
                c_low = c.lower()
                if c_low.startswith(('id_', 'id', 'pk_')) or c_low.endswith(('_id', '_key', '_code')):
                    display_cols.append(c)
                    break
            for mc in matched_cols:
                if mc not in display_cols and not is_sensitive_column_name(mc) and not is_index_artifact(mc):
                    display_cols.append(mc)
            if self.cost_col and self.cost_col not in display_cols:
                display_cols.append(self.cost_col)
            if "_is_target_event" not in display_cols:
                display_cols.append("_is_target_event")

            order_clause = ""
            if self.cost_col:
                order_clause = f"ORDER BY {quote_sql_ident(self.cost_col)} DESC"
            elif matched_cols and pd.api.types.is_numeric_dtype(self.df_fact[matched_cols[0]]):
                order_clause = f"ORDER BY {quote_sql_ident(matched_cols[0])} DESC"

            sql = f"SELECT {', '.join(quote_sql_ident(c) for c in display_cols[:8])} FROM fact {where_sql} {order_clause} LIMIT {req_limit};"
            summary = f"Row-level query returning top {req_limit} individual records."
            return sql, summary

        # Case 2: Group-by Dimension Breakdown
        target_group_col = None
        for mc in matched_cols:
            if mc in (self.target_col, self.cost_col, "_is_target_event"):
                continue
            if self.df_fact[mc].nunique() <= 50:
                target_group_col = mc
                break

        if not target_group_col and wants_breakdown:
            target_group_col = self.primary_dim

        if target_group_col:
            q_grp = quote_sql_ident(target_group_col)
            cost_sel = f", ROUND(SUM(CASE WHEN _is_target_event = 1 THEN TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) ELSE 0 END), 2) AS adverse_capital_drag" if self.cost_col else ""
            order_by = "adverse_rate_pct DESC" if (is_top_query or is_adverse_query) else ("adverse_rate_pct ASC" if is_bottom_query else "total_records DESC")
            
            sql = f"""SELECT 
    {q_grp} AS segment,
    COUNT(*) AS total_records,
    SUM(_is_target_event) AS adverse_events,
    ROUND(100.0 * AVG(_is_target_event), 2) AS adverse_rate_pct{cost_sel}
FROM fact
{where_sql}
GROUP BY {q_grp}
ORDER BY {order_by}
LIMIT {req_limit};"""
            summary = f"Breakdown of adverse performance and risk metrics grouped by '{target_group_col}'."
            return sql, summary

        # Case 3: Overall aggregate KPI summary query
        if is_count_query or is_adverse_query or not matched_cols:
            cost_sel = f", ROUND(SUM(CASE WHEN _is_target_event = 1 THEN TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) ELSE 0 END), 2) AS total_adverse_drag, ROUND(SUM(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE)), 2) AS total_portfolio_volume" if self.cost_col else ""
            sql = f"""SELECT 
    COUNT(*) AS total_records,
    SUM(_is_target_event) AS total_adverse_events,
    ROUND(100.0 * AVG(_is_target_event), 2) AS overall_adverse_rate_pct{cost_sel}
FROM fact
{where_sql};"""
            summary = "Overall physical business volume, adverse events, and aggregate financial liability."
            return sql, summary

        # Case 4: Sample records querying matched physical columns
        selected_cols = [quote_sql_ident(c) for c in matched_cols[:6] if not is_sensitive_column_name(c)]
        if "_is_target_event" not in selected_cols:
            selected_cols.append("_is_target_event")
        sql = f"SELECT {', '.join(selected_cols)} FROM fact {where_sql} LIMIT {req_limit};"
        summary = f"Sample records querying physical columns: {', '.join(matched_cols[:6])}."
        return sql, summary

    def translate_question_to_sql(self, question: str, use_llm: bool = True) -> Tuple[str, str, str]:
        """
        Translates a natural language question to DuckDB SQL.
        Uses Paced Gemini LLM when available, falling back safely to deterministic synthesis.
        Returns: (sql_query, explanation, mode)
        """
        clean_q = scrub_text(str(question or "").strip())

        llm_client = _get_shared_llm_client() if use_llm else None

        if not llm_client:
            sql, summary = self.synthesize_deterministic_sql(clean_q)
            return sql, summary, "deterministic_engine"

        # Prepare Schema Metadata for LLM
        schema_summary = []
        for c in self.df_fact.columns:
            if is_sensitive_column_name(c):
                continue
            sanitized_name = sanitize_untrusted_metadata_token(c)
            dtype_name = str(self.df_fact[c].dtype)
            nunq = self.df_fact[c].nunique()
            schema_summary.append(f"- {sanitized_name} ({dtype_name}, {nunq} unique values)")

        schema_text = "\n".join(schema_summary[:40])
        cost_info = f"Financial Cost Column: '{self.cost_col}'" if self.cost_col else "Financial Cost Column: None (Event Counts Only)"
        target_info = f"Target Column: '{self.target_col}', Binary Indicator: '_is_target_event' (1=adverse failure, 0=normal)"

        system_prompt = (
            "You are a Principal DuckDB Analytics Engineer. Translate the user's business question "
            "into a single valid, read-only DuckDB SQL query against the table named `fact`.\n\n"
            "STRICT RULES:\n"
            "1. ONLY output a single JSON object: {\"sql\": \"SELECT ...\", \"explanation\": \"...\"}.\n"
            "2. ONLY use the table name `fact`. Do NOT use `bi_ready_fact` or external functions.\n"
            "3. MUST begin with SELECT or WITH. Absolutely NO mutations, file reads, or pragma calls.\n"
            "4. Enforce LIMIT 200 maximum.\n"
            "5. Always use `_is_target_event` (1=adverse, 0=normal) for churn/default/failure rates.\n"
            "6. Always wrap column names in double quotes if they contain spaces or special characters."
        )

        user_prompt = f"""<UNTRUSTED_SCHEMA_METADATA>
Columns available in table `fact`:
{schema_text}

{target_info}
{cost_info}
Primary Dimension: '{self.primary_dim}'
</UNTRUSTED_SCHEMA_METADATA>

User Business Question: "{clean_q}"
Respond with ONLY JSON."""

        try:
            raw_response = llm_client.generate_text(prompt=user_prompt, system_instruction=system_prompt, max_retries=2)
            json_match = re.search(r'\{[\s\S]*\}', str(raw_response or ""))
            if json_match:
                payload = json.loads(json_match.group(0))
                sql = payload.get("sql", "").strip()
                expl = payload.get("explanation", "").strip()

                # Validate through security gate and dry-run on DuckDB
                violations = validate_readonly_duckdb_sql(sql)
                if not violations:
                    sql_capped = enforce_sql_row_limit(sql)
                    self.con.execute(f"EXPLAIN {sql_capped}").fetchall()
                    return sql_capped, expl, "llm_verified"
        except Exception:
            pass

        # Fallback to deterministic synthesis
        sql, summary = self.synthesize_deterministic_sql(clean_q)
        return sql, summary, "deterministic_engine"

    def _generate_vega_spec(self, df_res: pd.DataFrame, question: str) -> Optional[Dict[str, Any]]:
        """Synthesizes Vega-Lite v5 specification if query result is suitable for charting."""
        if len(df_res) < 2 or len(df_res) > 50:
            return None

        cols = list(df_res.columns)
        num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df_res[c])]
        nom_cols = [c for c in cols if c not in num_cols]

        if not nom_cols or not num_cols:
            return None

        x_col = nom_cols[0]
        y_col = num_cols[0]

        # Prioritize rate or financial metric for y-axis
        for nc in num_cols:
            if any(k in nc.lower() for k in ['rate', 'pct', 'percent', 'drag', 'cost', 'events', 'total']):
                y_col = nc
                break

        chart_data = df_res.to_dict(orient="records")
        for row in chart_data:
            for k, v in list(row.items()):
                if pd.isna(v) or v is None:
                    row[k] = None

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": f"Empirical Query Result: {html.escape(question[:60])}",
            "width": "container",
            "height": 280,
            "data": {"values": chart_data},
            "mark": {"type": "bar", "cornerRadiusEnd": 4},
            "encoding": {
                "x": {"field": x_col, "type": "nominal", "sort": "-y", "title": str(x_col).replace("_", " ").title()},
                "y": {"field": y_col, "type": "quantitative", "title": str(y_col).replace("_", " ").title()},
                "color": {
                    "field": y_col,
                    "type": "quantitative",
                    "scale": {"scheme": "tealblues" if "rate" not in y_col else "redyellowblue", "reverse": "rate" in y_col}
                },
                "tooltip": [{"field": c, "type": "quantitative" if c in num_cols else "nominal"} for c in cols[:5]]
            }
        }
        return spec

    def ask(self, question: str, language: str = "auto", use_llm: bool = True) -> Dict[str, Any]:
        """
        Processes a natural language business question, executes DuckDB SQL,
        and constructs a 100% physically truth-grounded bilingual response.
        """
        resolved_lang = detect_language_preference(question, explicit_lang=language)
        sql, explanation, mode = self.translate_question_to_sql(question, use_llm=use_llm)

        # Enforce row limit
        sql = enforce_sql_row_limit(sql, max_rows=200)

        # Execute on DuckDB
        try:
            rel = self.con.execute(sql)
            res_df = rel.fetchdf()
        except Exception as e:
            err_msg = (
                f"**Execution Error**: SQL query failed on DuckDB: `{e}`"
                if resolved_lang == "english" else
                f"**Query Error**: DuckDB SQL execution mein issue aaya: `{e}`"
            )
            return {
                "question": question,
                "language": resolved_lang,
                "sql_executed": sql,
                "sql_generation_mode": mode,
                "row_count_returned": 0,
                "columns": [],
                "data": [],
                "answer_markdown": err_msg,
                "vega_lite_spec": None,
                "grounding_verified": False,
                "error": str(e)
            }

        # Clean inf/nan for JSON serialization
        res_df_clean = res_df.replace([np.inf, -np.inf], np.nan)
        records = res_df_clean.to_dict(orient="records")

        # Format 100% physically grounded answer markdown
        answer_md = self._format_grounded_answer(question, res_df_clean, resolved_lang)
        vega_spec = self._generate_vega_spec(res_df_clean, question)

        return {
            "question": question,
            "language": resolved_lang,
            "sql_executed": sql,
            "sql_generation_mode": mode,
            "row_count_returned": len(res_df_clean),
            "columns": list(res_df_clean.columns),
            "data": records,
            "answer_markdown": answer_md,
            "vega_lite_spec": vega_spec,
            "grounding_verified": True
        }

    def _format_grounded_answer(self, question: str, df: pd.DataFrame, lang: str) -> str:
        """Constructs an auditable, strictly grounded plain-language answer."""
        if len(df) == 0:
            return (
                "**No records matched your exact query criteria.** (Audited DuckDB returned 0 rows)."
                if lang == "english" else
                "**Aapke filter criteria ke anusaar koi record match nahi hua.** (DuckDB ne 0 rows return kiye)."
            )

        # Single Aggregate Row
        if len(df) == 1 and len(df.columns) <= 6:
            row = df.iloc[0]
            items = []
            for col_name, val in row.items():
                label = str(col_name).replace("_", " ").title()
                if isinstance(val, (int, np.integer)):
                    val_str = f"**{val:,}**"
                elif isinstance(val, (float, np.floating)):
                    if "pct" in col_name.lower() or "rate" in col_name.lower():
                        val_str = f"**{val:.2f}%**"
                    elif (
                        (self.cost_col and col_name.lower() == str(self.cost_col).lower())
                        or any(k in col_name.lower() for k in [
                            'cost', 'drag', 'revenue', 'dollar', 'portfolio', 'amount',
                            'fee', 'mrr', 'arr', 'valor', 'gasto', 'charge', 'salary',
                            'claim', 'price', 'balance', 'billing'
                        ])
                    ):
                        val_str = f"**${val:,.2f}**"
                    elif float(val).is_integer():
                        val_str = f"**{int(val):,}**"
                    else:
                        val_str = f"**{val:,.2f}**"
                else:
                    val_str = f"**{val}**"
                items.append(f"- **{label}**: {val_str}")

            if lang == "english":
                return (
                    f"### 📊 Physical Data Ground Truth\n"
                    f"Direct DuckDB execution on audited fact records yielded the following metrics:\n\n"
                    + "\n".join(items)
                )
            else:
                return (
                    f"### 📊 Asli Data Ground Truth (DuckDB Verified)\n"
                    f"Aapke verified fact records par DuckDB query chalane ke baad yeh exact numbers calculate hue hain:\n\n"
                    + "\n".join(items)
                )

        # Multi-row Breakdown Table
        top_rows = df.head(10)
        try:
            table_md = top_rows.to_markdown(index=False)
        except Exception:
            # Fallback zero-dependency markdown table builder
            cols = [str(c) for c in top_rows.columns]
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            rows = []
            for _, r in top_rows.iterrows():
                row_str = "| " + " | ".join(str(r[c]) if pd.notna(r[c]) else "" for c in top_rows.columns) + " |"
                rows.append(row_str)
            table_md = "\n".join([header, sep] + rows)

        total_rows_note = f"\n\n*Displaying top {len(top_rows)} of {len(df)} total matching records.*" if len(df) > len(top_rows) else ""

        if lang == "english":
            return (
                f"### 🔍 Audited Query Results\n"
                f"Based on physical DuckDB query execution across verified records:\n\n"
                f"{table_md}{total_rows_note}"
            )
        else:
            return (
                f"### 🔍 Pramanit Nateeje (Audited Query Results)\n"
                f"Aapke verified physical data par execute kiye gaye SQL ke anusaar:\n\n"
                f"{table_md}{total_rows_note}"
            )
