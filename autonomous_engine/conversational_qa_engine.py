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

import re
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
    el = str(explicit_lang or "auto").strip().lower()
    if el in ("english", "en"):
        return "english"
    if el in ("hinglish", "hi", "hindi"):
        return "hinglish"

    q_lower = str(question or "").lower()
    if re.search(r'[\u0900-\u097F]', q_lower):
        return "hinglish"

    # Precise Hinglish markers (English words like 'loss' removed!)
    hinglish_markers = {
        'kya', 'kaise', 'kaun', 'kis', 'sabse', 'zyada', 'jyada', 'kam', 'kitna', 'kitne',
        'kyun', 'kaha', 'kahan', 'mein', 'aur', 'hain', 'hai', 'batao', 'bataiye', 'dikhao',
        'nuksan', 'fayda', 'kharcha', 'grahak', 'paise', 'paisa', 'rokna', 'bache', 'wali',
        'wala', 'wale', 'konsa', 'konse', 'konsi', 'chahiye', 'karo', 'mujhe', 'humara',
        'hamara', 'aaj', 'dekho', 'kisme', 'kisko', 'sirf', 'usme', 'isme', 'munafa', 'kiraya', 'bijli'
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
        self.questions_200 = self._load_json("universal_200_questions_report.json")

        # Load Parquet fact table and initialize canonical targets
        self.df_fact = pd.read_parquet(self.fact_parquet)
        self.canonical = resolve_canonical_target_and_cost(self.df_fact, blueprint=self.blueprint)
        self.target_col = self.canonical.get("target_col")
        self.cost_col = self.canonical.get("cost_col")
        self.binary_target = self.canonical.get("binary_target")
        self.is_financial = bool(self.canonical.get("is_financial", False)) and bool(self.cost_col)
        self.unit_symbol = str(self.canonical.get("unit_symbol") or "") if self.is_financial else ""
        self.numbering_system = str(self.canonical.get("numbering_system") or ("indian" if self.unit_symbol == "₹" else "international"))

        # Ensure _is_target_event column exists on fact dataframe
        if "_is_target_event" not in self.df_fact.columns and self.binary_target is not None:
            self.df_fact["_is_target_event"] = self.binary_target.astype(int)
        self.overall_rate_pct = float(self.df_fact["_is_target_event"].mean() * 100.0) if len(self.df_fact) > 0 and "_is_target_event" in self.df_fact.columns else 0.0

        # Detect primary business dimension & semantic helper columns
        self.primary_dim = self._detect_primary_dimension()
        self.semantic_cols = self._detect_semantic_helper_cols()
        self._value_index = self._build_categorical_value_index()
        self.conversation_history: List[Dict[str, Any]] = []

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

    def _detect_semantic_helper_cols(self) -> Dict[str, Optional[str]]:
        cols = list(self.df_fact.columns)
        def _pick(pats: List[str], num_only: bool = True, exclude_tokens: Tuple[str, ...] = ()) -> Optional[str]:
            for pat in pats:
                for c in cols:
                    if c in (self.target_col, "_is_target_event"):
                        continue
                    if exclude_tokens and any(et in c.lower() for et in exclude_tokens):
                        continue
                    if num_only and not pd.api.types.is_numeric_dtype(self.df_fact[c]):
                        continue
                    if pat in c.lower():
                        return c
            return None
        return {
            "margin": _pick(["net_contribution_margin", "contribution_margin", "net_margin", "net_profit", "profit", "margin"], True),
            "discount": _pick(["discount_amount", "discount_inr", "discount_usd", "discount_pct", "discount"], True),
            "discount_pct": _pick(["discount_pct", "discount_percent", "discount_rate"], True),
            "ad_spend": _pick(["ad_spend", "marketing_spend", "campaign_cost", "media_spend"], True),
            "cogs": _pick(["unit_cogs", "cogs", "product_cost", "unit_cost", "cost_price"], True, ("mrp", "selling_price", "revenue")),
            "op_cost": _pick(["fuel_and_toll_cost", "fuel_cost", "operating_cost", "direct_cost", "freight_cost", "service_cost", "delivery_cost"], True, ("mrp", "revenue", "lease", "rent")),
            "penalty": _pick(["sla_penalty", "penalty_inr", "penalty_usd", "penalty_amount", "chargeback_amount", "damage_cost", "late_fee"], True),
            "lease": _pick(["monthly_lease", "annual_lease", "lease_inr", "lease_usd", "monthly_rent", "fixed_overhead"], True),
            "outstanding_due": _pick(["outstanding_due", "balance_due", "unpaid_amount", "ar_balance", "overdue_amount", "amount_due"], True),
            "dso": _pick(["days_to_pay", "dso_days", "dso", "days_overdue", "overdue_days", "payment_days"], True),
            "credit_note": _pick(["credit_note", "refund_amount", "rebate_amount"], True),
            "csat": _pick(["csat", "rating", "satisfaction"], True),
            "delay": _pick(["dispatch_delay", "total_delivery", "transit_days", "transit_hours", "delivery_days", "dep_delay", "delay"], True),
            "year": _pick(["order_year", "year"], True),
            "date": _pick(["order_date", "dispatch_date", "invoice_date", "transaction_date", "ship_date", "booking_date", "date"], False),
        }

    def _build_categorical_value_index(self) -> List[Tuple[str, str, str, str]]:
        """
        Builds a deterministic lookup of (match_phrase_lower, column_name, exact_or_like_val, match_mode)
        across low/medium-cardinality text columns so offline queries understand real data values
        like 'Uttar Pradesh', 'UP', 'FLASH30', 'Tier 3', 'COD', 'BlueDart', 'Delhivery', 'City Hotel'.
        """
        stop_words = {
            "and", "the", "for", "with", "from", "this", "that", "have", "what", "which",
            "show", "give", "find", "total", "high", "low", "top", "best", "worst", "all",
            "only", "now", "sirf", "kya", "kitna", "kitne", "kahan", "kaun", "kis", "loss",
            "risk", "rate", "cost", "order", "orders", "sale", "sales", "data", "none", "other",
            "yes", "no", "true", "false", "null", "nan", "avg", "average", "sum", "count",
            "margin", "profit", "revenue", "discount", "delay", "days", "month", "year"
        }
        alias_map = {
            "uttar pradesh": ["UP"],
            "madhya pradesh": ["MP"],
            "west bengal": ["WB"],
            "maharashtra": ["MH"],
            "tamil nadu": ["TN"],
            "rajasthan": ["RJ"],
            "gujarat": ["GJ"],
        }
        entries: List[Tuple[str, str, str, str]] = []
        seen_phrases: Set[str] = set()

        for c in self.df_fact.columns:
            if c in (self.target_col, self.cost_col, "_is_target_event"):
                continue
            if is_index_artifact(c, self.df_fact[c]) or is_sensitive_column_name(c):
                continue
            if pd.api.types.is_numeric_dtype(self.df_fact[c]):
                continue
            nunq = self.df_fact[c].nunique(dropna=True)
            if nunq < 2 or nunq > 80:
                continue
            vals = [str(v).strip() for v in self.df_fact[c].dropna().unique().tolist() if str(v).strip()]
            for val in vals:
                v_low = val.lower()
                if len(v_low) >= 3 and v_low not in stop_words and v_low not in seen_phrases:
                    entries.append((v_low, c, val, "eq"))
                    seen_phrases.add(v_low)
                # Well-known uppercase 2-letter state abbreviations (matched case-sensitively so Hinglish 'ka' / English 'up' never false-match!)
                for full_name, abbrs in alias_map.items():
                    if v_low == full_name:
                        for ab in abbrs:
                            if ab not in seen_phrases:
                                entries.append((ab, c, val, "eq_upper"))
                                seen_phrases.add(ab)
                # COD / UPI / Card / Wallet shorthand matching (e.g. "COD" -> "Cash on Delivery (COD)", "UPI" -> "UPI (Razorpay)")
                if "(cod)" in v_low or v_low == "cod" or "cash on delivery" in v_low:
                    if "cod" not in seen_phrases:
                        entries.append(("cod", c, val, "eq"))
                        seen_phrases.add("cod")
                if re.search(r"\bupi\b", v_low):
                    if "upi" not in seen_phrases:
                        entries.append(("upi", c, val, "eq"))
                        seen_phrases.add("upi")
                if "(" in v_low:
                    prefix_clean = v_low.split("(")[0].strip()
                    if len(prefix_clean) >= 3 and prefix_clean not in stop_words and prefix_clean not in seen_phrases:
                        matches_in_col = [ov for ov in vals if ov.lower().split("(")[0].strip() == prefix_clean]
                        if len(matches_in_col) == 1:
                            entries.append((prefix_clean, c, val, "eq"))
                            seen_phrases.add(prefix_clean)
                # Distinctive multi-word leading token (e.g. "Delhivery" from "Delhivery Surface Express", "Tier 3" from "Tier 3 Regional")
                toks = re.findall(r"[a-z0-9]+", v_low)
                if len(toks) >= 2:
                    two_tok = f"{toks[0]} {toks[1]}"
                    if len(two_tok) >= 5 and two_tok not in stop_words and two_tok not in seen_phrases:
                        # Ensure two_tok uniquely identifies this value inside column c
                        matches_in_col = [ov for ov in vals if two_tok in ov.lower()]
                        if len(matches_in_col) == 1:
                            entries.append((two_tok, c, val, "eq"))
                            seen_phrases.add(two_tok)
                    first_tok = toks[0]
                    col_name_tokens = {t for cn in self.df_fact.columns for t in re.findall(r"[a-z]+", str(cn).lower()) if len(t) >= 4}
                    if len(first_tok) >= 5 and first_tok not in stop_words and first_tok not in col_name_tokens and first_tok not in seen_phrases:
                        matches_in_col = [ov for ov in vals if first_tok in ov.lower()]
                        if len(matches_in_col) == 1:
                            entries.append((first_tok, c, val, "eq"))
                            seen_phrases.add(first_tok)

        # Sort longest phrases first so "Uttar Pradesh" matches before "UP" and "Tier 3 Regional" before "Tier 3"
        entries.sort(key=lambda x: len(x[0]), reverse=True)
        return entries

    def _detect_missing_domain_concept(self, question: str) -> Optional[Dict[str, str]]:
        """
        Honest Guard: Detects when a user asks about a business concept whose columns
        physically do NOT exist in `df_fact`, preventing misleading fallback summary tables.
        """
        q_low = str(question or "").lower()
        cols_joined = " ".join(c.lower() for c in self.df_fact.columns)

        unavailable_concepts = [
            (
                ["electricity", "bijli", "utility bill", "power bill", "water bill", "बिजली", "यूटिलिटी"],
                ["electric", "utility", "power", "energy", "kwh"],
                "Electricity / Utility Expense",
                "बिजली / यूटिलिटी खर्च",
                "expense_ledger (utility_bill_amount, expense_category)",
            ),
            (
                ["office rent", "shop rent", "kiraya", "fixed overhead", "break-even", "breakeven", "किराया", "ओवरहेड"],
                ["rent", "overhead", "fixed_cost", "lease"],
                "Rent & Fixed Overhead",
                "किराया व फिक्स्ड ओवरहेड खर्च",
                "monthly_overhead_ledger (rent, fixed_expenses)",
            ),
            (
                ["bank balance", "cash runway", "cash in bank", "overdraft", "बैंक बैलेंस"],
                ["bank_balance", "cash_balance", "runway"],
                "Bank Cash Balance & Runway",
                "बैंक बैलेंस व कैश रनवे",
                "bank_statement / cash_balance_ledger",
            ),
            (
                ["competitor price", "buy-box", "competitor rate"],
                ["competitor", "market_price"],
                "Competitor Pricing Benchmarks",
                "प्रतिद्वंदी (Competitor) प्राइसिंग डेटा",
                "competitor_sku_price_feed",
            ),
            (
                ["ad spend", "roas", "poas", "meta ads spend", "facebook ads cost", "google ads cost", "विज्ञापन खर्च"],
                ["ad_spend", "marketing_spend", "campaign_cost", "media_spend"],
                "Marketing / Ad Spend (ROAS & POAS)",
                "विज्ञापन खर्च (Ad Spend / ROAS / POAS)",
                "channel_ad_spend.csv (acquisition_channel, ad_spend_inr)",
            ),
            (
                ["stockout", "out of stock", "inventory expiry", "closing stock", "shrinkage", "pilferage", "गोदाम स्टॉक", "इन्वेंटरी"],
                ["stock", "inventory", "doh", "expiry", "shrinkage"],
                "Warehouse Inventory & Stockout Ledger",
                "गोदाम स्टॉक व इन्वेंटरी डेटा",
                "inventory_stock_ledger (sku_code, stock_on_hand, expiry_date)",
            ),
            (
                ["employee salary", "staff payroll", "attrition", "karmchari", "hiring channel", "कर्मचारी सैलरी"],
                ["salary", "payroll", "monthlyincome", "attrition", "employee", "jobrole"],
                "HR Payroll & Employee Attrition",
                "कर्मचारी सैलरी व HR डेटा",
                "hr_employee_roster (employee_id, salary, attrition)",
            ),
            (
                ["gstr", "gst reconciliation", "gst filing", "vat filing", "जीएसटी रिटर्न"],
                ["gstr", "gst_filed", "vat_return"],
                "GST / VAT Filing Reconciliation",
                "GST / VAT रिटर्न मिलान डेटा",
                "gstr1_export + sales_tax_register",
            ),
            (
                ["profit", "net profit", "gross profit", "munafa", "margin", "ebitda", "cogs", "kharid rate", "purchase cost", "profit kitna", "मुनाफा", "मुनाफ़ा", "शुद्ध लाभ", "कुल लाभ", "मार्जिन", "खरीद लागत"],
                ["profit", "margin", "cogs", "cost_price", "purchase_price", "buying_price", "unit_cost", "fuel_and_toll_cost", "operating_cost", "direct_cost", "sla_penalty"],
                "Net Profit / Product Cost Margin (COGS)",
                "कुल मुनाफ़ा / खरीद लागत (COGS / Net Profit)",
                "purchase_invoice_register / cogs_master (cost_price, purchase_rate)",
            ),
        ]

        def _phrase_matches(phrase: str, text: str) -> bool:
            if any(ord(ch) > 127 for ch in phrase):
                return phrase in text
            return bool(re.search(rf'\b{re.escape(phrase)}\b', text))

        for trigger_phrases, col_tokens, label_en, label_hi, needed_sheet in unavailable_concepts:
            if any(_phrase_matches(tp, q_low) for tp in trigger_phrases):
                if not any(ct in cols_joined for ct in col_tokens):
                    return {
                        "label_en": label_en,
                        "label_hi": label_hi,
                        "needed_sheet": needed_sheet,
                    }

        # Universal Unknown Explicit Metric Guard (catches explicit snake_case metrics like `carbon_emissions`, `bitcoin_price`, `nps_score` not in table)
        snake_tokens = re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', q_low)
        if snake_tokens:
            cols_lower = {c.lower() for c in self.df_fact.columns}
            val_lower = {p for p, _, _, _ in self._value_index}
            sqli_ignore = {"sqlite_master", "information_schema", "pg_catalog", "pg_tables", "sys_tables"}
            unknown_metrics = [
                tok for tok in snake_tokens
                if tok not in cols_lower
                and tok.replace("_", " ") not in val_lower
                and tok not in val_lower
                and tok not in sqli_ignore
                and not any(tok in cl or cl in tok for cl in cols_lower if len(cl) >= 4)
            ]
            # Only refuse if every explicit snake_case identifier in the prompt is completely absent from the dataset
            if unknown_metrics and len(unknown_metrics) == len([t for t in snake_tokens if t not in sqli_ignore]):
                nice_lbl = ", ".join(f"`{t}`" for t in unknown_metrics[:3])
                return {
                    "label_en": f"Requested Metric(s) {nice_lbl}",
                    "label_hi": f"पूछा गया डेटा कॉलम ({nice_lbl})",
                    "needed_sheet": f"a dataset containing {', '.join(unknown_metrics[:3])}",
                }
        return None

    def _extract_filters_from_question(self, question: str) -> Dict[str, str]:
        """Extracts exact column -> SQL predicate dict from text values, numeric comparisons, and years."""
        q_raw = str(question or "").strip()
        q_low = q_raw.lower()
        cols = list(self.df_fact.columns)
        filters: Dict[str, str] = {}

        # 1. Numeric filter conditions (e.g. "discount_pct > 20", "MonthlyCharges >= 70")
        comp_matches = re.finditer(r'([a-zA-Z0-9_]+)\s*(>=|<=|>|<|=|==)\s*(\d+(?:\.\d+)?)', q_raw)
        for comp_match in comp_matches:
            cand_col, op, num_val = comp_match.group(1), comp_match.group(2), comp_match.group(3)
            real_col = next((c for c in cols if c.lower() == cand_col.lower() or c.lower().replace("_", "") == cand_col.lower().replace("_", "")), None)
            if real_col and pd.api.types.is_numeric_dtype(self.df_fact[real_col]):
                sql_op = "=" if op == "==" else op
                filters[real_col] = f"{quote_sql_ident(real_col)} {sql_op} {num_val}"

        # 1.5 Universal Numeric Range / BETWEEN Filter (English & Hinglish: "between 48000 and 50000", "48000 se 50000 ke beech", "48k to 50k")
        range_m = re.search(
            r'(?:between\s+)?(\d+(?:,\d{3})*(?:\.\d+)?)(?:\s*(k)\b)?\s*(?:and|to|-|se)\s*(\d+(?:,\d{3})*(?:\.\d+)?)(?:\s*(k)\b)?(?:\s+ke\s+beech)?',
            q_low,
        )
        if range_m:
            v1 = float(range_m.group(1).replace(",", "")) * (1000.0 if range_m.group(2) else 1.0)
            v2 = float(range_m.group(3).replace(",", "")) * (1000.0 if range_m.group(4) else 1.0)
            # Exclude years like 2024 to 2025 or small month/quarter numbers
            if v2 > v1 and not (1990 <= v1 <= 2035 and 1990 <= v2 <= 2035):
                # Pick explicitly named numeric column in question, else credit_note / cost_col
                target_rng_col = None
                for c in cols:
                    if pd.api.types.is_numeric_dtype(self.df_fact[c]):
                        cn = c.lower().replace("_", " ")
                        if c.lower() in q_low or cn in q_low:
                            target_rng_col = c
                            break
                if not target_rng_col and any(w in q_low for w in ("credit note", "refund", "rebate")):
                    target_rng_col = self.semantic_cols.get("credit_note")
                if not target_rng_col and any(w in q_low for w in ("discount", "chhoot")):
                    target_rng_col = self.semantic_cols.get("discount_pct") or self.semantic_cols.get("discount")
                if not target_rng_col:
                    target_rng_col = self.cost_col
                if target_rng_col and target_rng_col not in filters:
                    filters[f"{target_rng_col}__rng"] = f"TRY_CAST({quote_sql_ident(target_rng_col)} AS DOUBLE) BETWEEN {v1:g} AND {v2:g}"

        # 2. Categorical text-value filters from inverted index (supports multi-value IN (...) on same column!)
        matched_spans: List[Tuple[int, int]] = []
        col_matched_vals: Dict[str, List[str]] = {}
        for phrase, col_name, exact_val, match_mode in self._value_index:
            if col_name in filters:
                continue
            # Include underscore '_' in boundary check so column names like `monthly_lease_inr` never trigger `billing_currency = 'INR'`!
            if match_mode == "eq_upper":
                m_iter = list(re.finditer(rf'(?<![A-Za-z0-9_]){re.escape(phrase)}(?![A-Za-z0-9_])', q_raw))
            else:
                m_iter = list(re.finditer(rf'(?<![a-z0-9_]){re.escape(phrase)}(?![a-z0-9_])', q_low))
            for m in m_iter:
                span = m.span()
                if any(not (span[1] <= s or span[0] >= e) for s, e in matched_spans):
                    continue
                matched_spans.append(span)
                vals_list = col_matched_vals.setdefault(col_name, [])
                if exact_val not in vals_list:
                    vals_list.append(exact_val)

        for col_name, vals_list in col_matched_vals.items():
            if len(vals_list) == 1:
                safe_val = vals_list[0].replace("'", "''")
                filters[col_name] = f"{quote_sql_ident(col_name)} = '{safe_val}'"
            elif len(vals_list) >= 2:
                in_list = ", ".join("'" + v.replace("'", "''") + "'" for v in vals_list)
                filters[col_name] = f"{quote_sql_ident(col_name)} IN ({in_list})"

        # 2.5 Explicit Status Filters on target_col (e.g., "even on Delivered shipments", "In Transit shipments")
        if self.target_col and self.target_col in cols and not pd.api.types.is_numeric_dtype(self.df_fact[self.target_col]):
            t_vals = [str(v).strip() for v in self.df_fact[self.target_col].dropna().unique().tolist()]
            t_norm_map = {re.sub(r'[_\-/]+', ' ', v.lower()).strip(): v for v in t_vals}
            if re.search(r'\b(?:in[\s_]+transit)\b', q_low) and "in transit" in t_norm_map:
                sv = t_norm_map["in transit"].replace("'", "''")
                filters[self.target_col] = f"{quote_sql_ident(self.target_col)} = '{sv}'"
            elif re.search(r'\b(?:on\s+delivered|for\s+delivered|delivered\s+(?:orders|shipments|records|only)|only\s+delivered)\b', q_low) and "delivered" in t_norm_map:
                sv = t_norm_map["delivered"].replace("'", "''")
                filters[self.target_col] = f"{quote_sql_ident(self.target_col)} = '{sv}'"

        # 2.6 Explicit Negative Amount / Credit Note Filter (e.g. "negative credit notes", "negative invoice_amount")
        if self.cost_col and re.search(r'\b(?:negative\s+(?:credit|invoice|amount|bill|value|revenue|refund)|credit\s+notes?|below\s+zero)\b', q_low):
            filters[f"{self.cost_col}__neg"] = f"TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) < 0"

        # 3. Special "Prepaid" filter when user asks about prepaid/non-COD on a payment column
        if re.search(r'\bprepaid\b', q_low):
            pay_col = next((c for c in cols if any(k in c.lower() for k in ("payment", "pay_mode", "gateway"))), None)
            if pay_col and pay_col not in filters:
                filters[pay_col] = f"LOWER(CAST({quote_sql_ident(pay_col)} AS VARCHAR)) NOT LIKE '%cod%' AND LOWER(CAST({quote_sql_ident(pay_col)} AS VARCHAR)) NOT LIKE '%cash on delivery%'"

        # 4. Year, Quarter (Q1-Q4), and Month (Jan-Dec) temporal filters
        yr_m = re.search(r'\b(20[1-3]\d)\b', q_low)
        ycol = self.semantic_cols.get("year")
        dcol = self.semantic_cols.get("date")
        if yr_m:
            yr_int = int(yr_m.group(1))
            if ycol and ycol not in filters:
                filters[ycol] = f"TRY_CAST({quote_sql_ident(ycol)} AS INTEGER) = {yr_int}"
            elif dcol and dcol not in filters:
                filters[dcol] = f"EXTRACT(YEAR FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE)) = {yr_int}"

        found_qtrs = sorted(set(int(x) for x in re.findall(r'\bq([1-4])\b', q_low)))
        if len(found_qtrs) >= 2 and dcol:
            q_list = ", ".join(str(q) for q in found_qtrs)
            q_expr = f"EXTRACT(QUARTER FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE)) IN ({q_list})"
            filters[dcol] = f"{filters[dcol]} AND {q_expr}" if dcol in filters else q_expr
        elif len(found_qtrs) == 1 and dcol:
            q_num = found_qtrs[0]
            q_expr = f"EXTRACT(QUARTER FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE)) = {q_num}"
            filters[dcol] = f"{filters[dcol]} AND {q_expr}" if dcol in filters else q_expr

        month_map = [
            (["january", "jan"], 1), (["february", "feb"], 2), (["march", "mar"], 3),
            (["april", "apr"], 4), (["may mein", "in may", "month of may"], 5), (["june", "jun"], 6),
            (["july", "jul"], 7), (["august", "aug"], 8), (["september", "sept", "sep"], 9),
            (["october", "oct"], 10), (["november", "nov"], 11), (["december", "dec"], 12),
        ]
        mcol = next((c for c in cols if c.lower() in ("order_month", "month")), None)
        found_months = []
        for m_tokens, m_num in month_map:
            if any(re.search(rf'\b{re.escape(mt)}\b', q_low) for mt in m_tokens):
                found_months.append(m_num)

        if len(found_months) >= 2:
            m_list = ", ".join(str(m) for m in found_months)
            if mcol and mcol not in filters:
                filters[mcol] = f"TRY_CAST({quote_sql_ident(mcol)} AS INTEGER) IN ({m_list})"
            elif dcol:
                m_expr = f"EXTRACT(MONTH FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE)) IN ({m_list})"
                filters[dcol] = f"{filters[dcol]} AND {m_expr}" if dcol in filters else m_expr
        elif len(found_months) == 1:
            m_num = found_months[0]
            if mcol and mcol not in filters:
                filters[mcol] = f"TRY_CAST({quote_sql_ident(mcol)} AS INTEGER) = {m_num}"
            elif dcol:
                m_expr = f"EXTRACT(MONTH FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE)) = {m_num}"
                filters[dcol] = f"{filters[dcol]} AND {m_expr}" if dcol in filters else m_expr

        return filters

    def _synthesize_deterministic_sql_with_context(
        self,
        question: str,
        prior_filters: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str, Dict[str, str]]:
        """
        Upgraded Deterministic Natural-Language-to-SQL Compiler:
        - Supports multi-filter categorical + numeric + year predicates offline
        - Supports multi-turn follow-up context inheritance & per-column override
        - Dynamically adapts SELECT metrics (Net Margin, Discount, CSAT, Delay, Capital Drag)
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

        # Extract current turn filters & merge with prior turn ONLY when explicit follow-up cue applies
        new_filters = self._extract_filters_from_question(q_raw)
        is_reset_query = any(w in q_clean for w in ["overall", "all records", "reset", "poora", "sabhi", "summary statistics"])
        is_followup_cue = any(
            re.search(rf'\b{w}\b', q_clean)
            for w in ["sirf", "only", "usme", "isme", "now", "also", "what about", "ab", "instead", "baki"]
        )
        active_filters: Dict[str, str] = {}
        if prior_filters and not is_reset_query and is_followup_cue:
            active_filters.update(prior_filters)
        active_filters.update(new_filters)  # New filter on same column cleanly overrides prior filter!
        self._last_group_col = None

        where_sql = f"WHERE {' AND '.join(active_filters.values())}" if active_filters else ""

        # Detect intent qualifiers & requested metrics
        is_count_query = any(w in q_clean for w in ['count', 'total', 'kitne', 'kitna', 'how many', 'how much', 'number of', 'volume'])
        is_adverse_query = any(w in q_clean for w in ['churn', 'default', 'risk', 'fail', 'defect', 'loss', 'losing', 'nuksan', 'bad', 'adverse', 'problem', 'rto', 'cancel', 'return', 'spoil', 'kharab', 'wapas', 'chuna'])
        is_margin_query = any(w in q_clean for w in ['margin', 'profit', 'profitability', 'munafa', 'kamai', 'net profit', 'losing money', 'losing the most', 'cogs'])
        is_losing_money = any(w in q_clean for w in ['losing', 'loss', 'bleed', 'ghata', 'nuksan'])
        is_ad_roas_query = any(w in q_clean for w in ['ad spend', 'roas', 'poas', 'marketing spend', 'campaign cost', 'ad cost'])
        is_revenue_query = bool(re.search(r'\b(?:revenue|sales|sale|turnover|gmv|bikri|selling price|invoice_amount|invoiced_amount|invoice amount|billing)\b', q_clean))
        is_op_cost_query = any(w in q_clean for w in ['fuel', 'toll', 'operating cost', 'direct cost', 'freight cost', 'fuel_and_toll_cost'])
        is_penalty_query = any(w in q_clean for w in ['penalty', 'sla penalty', 'sla_penalty', 'chargeback', 'demurrage', 'late fee'])
        is_ar_due_query = any(w in q_clean for w in ['outstanding', 'unpaid', 'udhari', 'receivable', 'overdue', 'balance due', 'paisa nahi', 'fasa hua', 'fasa hai', 'due'])
        is_dso_query = any(w in q_clean for w in ['days_to_pay', 'days to pay', 'dso', 'payment days', 'overdue days', 'kitne din mein paisa'])
        is_avg_disc_query = any(w in q_clean for w in ['average discount', 'avg discount', 'discount pct', 'discount %', 'ausat discount'])
        is_duplicate_query = any(w in q_clean for w in ['duplicate', 'double billing', 'double bill', 'double entry', 'dobara chadh', 'do baar'])
        is_ratio_pct_query = bool(re.search(r'(?:as\s+a\s+percentage\s+of|%\s+of\s+(?:total\s+)?(?:revenue|sales|billing|invoice)|percentage\s+of\s+(?:total\s+)?(?:revenue|sales))', q_clean))
        is_repeat_cust_query = any(w in q_clean for w in ['repeat customer', 'repeat buyer', 'returning customer', 'unique customer', 'repeat client', 'kitne repeat'])
        is_discount_query = any(w in q_clean for w in ['discount', 'chhoot', 'coupon'])
        is_csat_query = any(w in q_clean for w in ['csat', 'rating', 'satisfaction', 'review'])
        is_delay_query = any(w in q_clean for w in ['delay', 'transit', 'late', 'deri', 'delivery days']) and not is_penalty_query
        is_aov_query = any(w in q_clean for w in ['aov', 'average order value', 'avg order value', 'average bill', 'ticket size', 'ausat order'])
        is_top_query = any(w in q_clean for w in ['top', 'sabse zyada', 'highest', 'max', 'most', 'worst', 'sabse kharab'])
        is_bottom_query = any(w in q_clean for w in ['lowest', 'sabse kam', 'least', 'min', 'best', 'safest', 'bottom'])
        is_row_level_query = any(w in q_clean for w in ['customer', 'customers', 'client', 'clients', 'user', 'users', 'account', 'accounts', 'loan', 'loans', 'ticket', 'tickets', 'row', 'rows', 'record', 'records', 'shipment', 'shipments', 'intervene'])
        is_explicit_dispatch_top_n = bool(is_row_level_query and re.search(r'\b(?:top|give me|list|show me)\s+\d+\b', q_clean) and any(w in q_clean for w in ['intervene', 'shipments', 'orders', 'accounts', 'tickets', 'records', 'in transit']))

        # Fast-path 0: Universal Composite Duplicate / Ghost Double-Billing Audit
        if is_duplicate_query and self.cost_col:
            ent_c = next(
                (c for c in cols if any(k in c.lower() for k in ("distributor_name", "dealer_name", "party_name", "account_name", "client_name", "dealer_id", "customer_id", "account_id")) and not pd.api.types.is_numeric_dtype(self.df_fact[c])),
                None,
            )
            dt_c = self.semantic_cols.get("date")
            cat_c = next((c for c in cols if any(k in c.lower() for k in ("sku", "product_category", "category", "item")) and not pd.api.types.is_numeric_dtype(self.df_fact[c])), None)
            if ent_c and dt_c:
                grp_parts = [quote_sql_ident(ent_c), quote_sql_ident(dt_c), f"ROUND(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE), 2)"]
                if cat_c and cat_c != ent_c:
                    grp_parts.append(quote_sql_ident(cat_c))
                grp_sql = ", ".join(grp_parts)
                sql = f"""WITH dup_groups AS (
    SELECT {grp_sql}, COUNT(*) AS dup_cnt, ROUND(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE), 2) AS bill_amt
    FROM fact
    WHERE TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) > 0
    GROUP BY {grp_sql}
    HAVING COUNT(*) > 1
)
SELECT
    COUNT(*) AS duplicate_groups,
    COALESCE(SUM(dup_cnt - 1), 0) AS extra_duplicate_rows,
    ROUND(COALESCE(SUM((dup_cnt - 1) * bill_amt), 0), 2) AS duplicated_cash_exposure
FROM dup_groups;"""
                return sql, "Audited composite duplicate / double-billing detection across account, date, category, and amount.", active_filters

        # Fast-path 0.5: Universal Pareto / Top-X% Revenue Concentration (e.g., "What % of total revenue comes from top 20% customers?")
        pareto_pct_m = re.search(r'\btop\s+(\d{1,2})\s*%', q_clean)
        is_pareto_query = bool(
            self.cost_col
            and (
                pareto_pct_m
                or any(w in q_clean for w in ("80/20", "80-20", "pareto", "revenue concentration", "customer concentration"))
            )
            and any(w in q_clean for w in ("customer", "client", "account", "distributor", "dealer", "party", "buyer", "vendor", "product", "sku", "revenue", "sales", "share", "percentage", "%"))
        )
        if is_pareto_query:
            pct_n = int(pareto_pct_m.group(1)) if pareto_pct_m else 20
            pct_n = max(1, min(pct_n, 50))
            frac = pct_n / 100.0
            ent_priority = (
                ("customer_id", "client_id", "account_id", "user_id", "cust_id", "distributor_name", "dealer_name", "account_name", "party_name", "vendor_name", "sku_id", "product_category")
                if not any(w in q_clean for w in ("product", "sku"))
                else ("sku_id", "product_name", "product_category", "item", "customer_id")
            )
            pareto_ent = next((c for c in cols if c.lower() in ent_priority), None) or next(
                (c for c in cols if any(k in c.lower() for k in ("customer", "client", "account", "distributor", "dealer", "vendor", "sku", "product")) and not pd.api.types.is_numeric_dtype(self.df_fact[c])),
                None,
            )
            if pareto_ent:
                q_ent = quote_sql_ident(pareto_ent)
                q_cost = quote_sql_ident(self.cost_col)
                sql = f"""WITH entity_rev AS (
    SELECT {q_ent} AS entity_id, SUM(TRY_CAST({q_cost} AS DOUBLE)) AS entity_revenue
    FROM fact
    {where_sql}
    GROUP BY {q_ent}
),
ranked AS (
    SELECT
        entity_id,
        entity_revenue,
        ROW_NUMBER() OVER (ORDER BY entity_revenue DESC) AS rn,
        COUNT(*) OVER () AS total_entities,
        SUM(entity_revenue) OVER () AS grand_total_revenue
    FROM entity_rev
)
SELECT
    COUNT(*) FILTER (WHERE rn <= GREATEST(CAST(CEIL(total_entities * {frac:.2f}) AS BIGINT), 1)) AS top_cohort_entities,
    MAX(total_entities) AS total_unique_entities,
    ROUND(SUM(entity_revenue) FILTER (WHERE rn <= GREATEST(CAST(CEIL(total_entities * {frac:.2f}) AS BIGINT), 1)), 2) AS top_cohort_revenue,
    ROUND(MAX(grand_total_revenue), 2) AS total_revenue,
    ROUND(100.0 * SUM(entity_revenue) FILTER (WHERE rn <= GREATEST(CAST(CEIL(total_entities * {frac:.2f}) AS BIGINT), 1)) / NULLIF(MAX(grand_total_revenue), 0), 2) AS top_cohort_revenue_share_pct
FROM ranked;"""
                return sql, f"Pareto concentration computed for top {pct_n}% `{pareto_ent}` share of `{self.cost_col}`.", active_filters

        # Fast-path: Customer-level Repeat / Unique Buyer metrics when customer_id exists
        if is_repeat_cust_query:
            cust_col = next((c for c in cols if c.lower() in ("customer_id", "client_id", "user_id", "account_id", "cust_id")), None)
            if cust_col:
                q_cid = quote_sql_ident(cust_col)
                sql = f"""WITH cust_orders AS (
    SELECT {q_cid} AS cid, COUNT(*) AS orders_cnt
    FROM fact
    {where_sql}
    GROUP BY {q_cid}
)
SELECT
    COUNT(*) AS unique_customers,
    SUM(CASE WHEN orders_cnt >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
    SUM(CASE WHEN orders_cnt = 1 THEN 1 ELSE 0 END) AS one_time_customers,
    ROUND(100.0 * SUM(CASE WHEN orders_cnt >= 2 THEN 1 ELSE 0 END) / GREATEST(COUNT(*), 1), 2) AS repeat_customer_rate_pct
FROM cust_orders;"""
                return sql, f"Customer repeat analysis computed on unique `{cust_col}`.", active_filters

        limit_match = re.search(r'\b(?:top|worst|bottom|best|pehle|sabse\s+(?:zyada|kharab|kam|achhe))\s+(\d+)\b', q_clean)
        req_limit = int(limit_match.group(1)) if limit_match else (10 if (is_top_query or is_bottom_query) else 50)
        req_limit = min(req_limit, 200)

        # Extra metric SQL fragments
        extra_metrics_sql = ""
        m_col = self.semantic_cols.get("margin")
        d_col = self.semantic_cols.get("discount")
        d_pct_col = self.semantic_cols.get("discount_pct")
        ad_col = self.semantic_cols.get("ad_spend")
        cogs_col = self.semantic_cols.get("cogs")
        op_cost_col = self.semantic_cols.get("op_cost")
        pen_col = self.semantic_cols.get("penalty")
        lease_col = self.semantic_cols.get("lease")
        due_col = self.semantic_cols.get("outstanding_due")
        dso_col = self.semantic_cols.get("dso")
        cn_col = self.semantic_cols.get("credit_note")
        cs_col = self.semantic_cols.get("csat")
        dl_col = self.semantic_cols.get("delay")
        has_rng_filter = any(k.endswith("__rng") for k in active_filters.keys())
        if (is_revenue_query or is_ad_roas_query or is_margin_query or is_ratio_pct_query) and self.cost_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE)), 2) AS total_revenue"
        if is_margin_query and cogs_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(cogs_col)} AS DOUBLE)), 2) AS total_cogs"
        if (is_op_cost_query or is_margin_query) and op_cost_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(op_cost_col)} AS DOUBLE)), 2) AS total_op_cost"
        if (is_penalty_query or is_margin_query) and pen_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(pen_col)} AS DOUBLE)), 2) AS total_sla_penalty"
            if is_ratio_pct_query and self.cost_col:
                extra_metrics_sql += f", ROUND(100.0 * SUM(TRY_CAST({quote_sql_ident(pen_col)} AS DOUBLE)) / NULLIF(SUM(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE)), 0), 2) AS penalty_pct_of_revenue"
        if (is_ad_roas_query or is_margin_query) and ad_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(ad_col)} AS DOUBLE)), 2) AS total_ad_spend"
            if is_ad_roas_query and self.cost_col:
                extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE)) / NULLIF(SUM(TRY_CAST({quote_sql_ident(ad_col)} AS DOUBLE)), 0), 2) AS roas_multiplier"
        if is_margin_query and m_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(m_col)} AS DOUBLE)), 2) AS total_net_margin, ROUND(AVG(TRY_CAST({quote_sql_ident(m_col)} AS DOUBLE)), 2) AS avg_margin_per_order"
        if is_ar_due_query and due_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(due_col)} AS DOUBLE)), 2) AS total_outstanding_due"
        if is_dso_query and dso_col:
            extra_metrics_sql += f", ROUND(AVG(TRY_CAST({quote_sql_ident(dso_col)} AS DOUBLE)), 1) AS avg_days_to_pay"
        if has_rng_filter and cn_col and any(k.startswith(cn_col) for k in active_filters.keys()):
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(cn_col)} AS DOUBLE)), 2) AS total_credit_note_amount"
        if is_avg_disc_query and d_pct_col:
            extra_metrics_sql += f", ROUND(AVG(TRY_CAST({quote_sql_ident(d_pct_col)} AS DOUBLE)), 2) AS avg_discount_pct"
        if is_discount_query and d_col:
            extra_metrics_sql += f", ROUND(SUM(TRY_CAST({quote_sql_ident(d_col)} AS DOUBLE)), 2) AS total_discount"
        if is_csat_query and cs_col:
            extra_metrics_sql += f", ROUND(AVG(TRY_CAST({quote_sql_ident(cs_col)} AS DOUBLE)), 2) AS avg_csat_rating"
        if is_delay_query and dl_col:
            extra_metrics_sql += f", ROUND(AVG(TRY_CAST({quote_sql_ident(dl_col)} AS DOUBLE)), 2) AS avg_delay_days"
        if is_aov_query and self.cost_col:
            extra_metrics_sql += f", ROUND(AVG(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE)), 2) AS avg_order_value_aov"

        # Direct Total Sum of an explicitly named numeric metric column (e.g. "What is our total monthly_lease_inr across all hubs?")
        explicit_num_cols = [
            mc for mc in matched_cols
            if pd.api.types.is_numeric_dtype(self.df_fact[mc])
            and mc not in (self.target_col, "_is_target_event")
            and any(k in mc.lower() for k in ("lease", "rent", "overhead", "budget", "penalty", "fuel", "cost", "spend", "fee", "salary", "payroll"))
        ]
        wants_group_by_phrase = bool(re.search(r'\b(?:by|per|breakdown|compare|vs|versus|which)\b', q_clean))
        if explicit_num_cols and is_count_query and not wants_group_by_phrase and not is_margin_query and not is_adverse_query:
            t_col = explicit_num_cols[0]
            alias_n = f"total_{re.sub(r'[^a-z0-9_]+', '_', t_col.lower()).strip('_')}"
            sql = f"""SELECT
    COUNT(*) AS total_records,
    ROUND(SUM(TRY_CAST({quote_sql_ident(t_col)} AS DOUBLE)), 2) AS {alias_n},
    ROUND(AVG(TRY_CAST({quote_sql_ident(t_col)} AS DOUBLE)), 2) AS avg_per_record
FROM fact
{where_sql};"""
            return sql, f"Audited aggregate total for `{t_col}` across physical records.", active_filters

        target_group_col: Optional[str] = None
        wants_breakdown: bool = False

        # Check if user asks what happens if they stop/switch/replace an entity ("If I stop using DTDC, how much will I save?")
        is_stop_or_save_query = any(re.search(rf'\b{w}\b', q_clean) for w in [
            'stop using', 'switch from', 'replace', 'band karu', 'hata du', 'hata dein',
            'how much will i save', 'how much can i save', 'kitna bachega', 'kitni bachat', 'save', 'savings'
        ])
        if is_stop_or_save_query and len(active_filters) == 1:
            f_col = list(active_filters.keys())[0]
            f_pred = active_filters.pop(f_col)
            m_val = re.search(r"=\s*'([^']+)'", f_pred)
            ent_label = m_val.group(1) if m_val else f_col
            target_group_col = f"CASE WHEN {f_pred} THEN '{ent_label}' ELSE 'Rest of Business' END"
            wants_breakdown = True
            where_sql = f"WHERE {' AND '.join(active_filters.values())}" if active_filters else ""

        # Check if date month or quarter IN (...) filter exists for multi-period comparison (e.g. July vs October, Q2 vs Q3 vs Q4)
        dcol = self.semantic_cols.get("date")
        is_multi_qtr_compare = bool(dcol and dcol in active_filters and "EXTRACT(QUARTER" in active_filters[dcol] and " IN (" in active_filters[dcol])
        if dcol and dcol in active_filters and "EXTRACT(MONTH" in active_filters[dcol] and " IN (" in active_filters[dcol]:
            target_group_col = f"EXTRACT(MONTH FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE))"
            wants_breakdown = True

        # Check if user asks a 2x2 Interaction / Confounder / Simpson's Paradox comparison
        is_confounder_query = any(re.search(rf'\b{w}\b', q_clean) for w in [
            'real problem', 'just up', 'confounder', 'asli wajah', 'kya sach me', 'sach mein',
            'ki wajah se', 'is it just', 'is it really', 'or is it just', 'actually because',
            'really the problem', 'just because of', 'simpson'
        ])
        if is_confounder_query and len(active_filters) == 2:
            cols_2 = list(active_filters.keys())
            pred_1 = active_filters[cols_2[0]]
            pred_2 = active_filters[cols_2[1]]
            m_val1 = re.search(r"=\s*'([^']+)'", pred_1)
            l1 = m_val1.group(1) if m_val1 else cols_2[0]
            m_val2 = re.search(r"=\s*'([^']+)'", pred_2)
            l2 = m_val2.group(1) if m_val2 else cols_2[1]
            active_filters.clear()
            target_group_col = f"CASE WHEN {pred_1} THEN '{l1}' ELSE 'Non-{l1}' END || ' + ' || CASE WHEN {pred_2} THEN '{l2}' ELSE 'Non-{l2}' END"
            wants_breakdown = True
            where_sql = ""

        # Check if breakdown is explicitly sought (or if user asked to compare 2+ values in an IN (...) filter or a BETWEEN range audit!)
        multi_val_cols = [c for c, pred in active_filters.items() if " IN (" in pred and c in self.df_fact.columns and c != dcol]
        breakdown_indicators = ['by', 'per', 'across', 'breakdown', 'which', 'kaha', 'kahan', 'kisme', 'kis', 'kiska', 'kaunsa', 'kaunsi', 'group', 'segment', 'category', 'categories', 'compare', 'vs', 'versus', 'tulna']
        wants_breakdown = (not is_explicit_dispatch_top_n) and (
            bool(multi_val_cols) or is_multi_qtr_compare or wants_breakdown or has_rng_filter
            or any(re.search(rf'\b{b}\b', q_clean) for b in breakdown_indicators)
            or (is_top_query and not is_row_level_query)
        )

        non_group_metric_cols = {self.target_col, self.cost_col, "_is_target_event", m_col, d_col, d_pct_col, ad_col, cogs_col, op_cost_col, pen_col, lease_col, due_col, dso_col, cn_col, cs_col, dl_col}
        # Pick group-by column(s): support 2-column composite GROUP BY when user names 2 categorical dimensions (e.g. client_tier and account_manager)!
        if not target_group_col:
            target_group_col = multi_val_cols[0] if multi_val_cols else None
        if not target_group_col:
            group_block_kw = ("mrp", "price", "cost", "amount", "spend", "cogs", "margin", "discount", "line_no", "lease", "rent", "penalty", "fuel", "capacity", "tons", "hours", "limit", "due", "days", "credit_note", "collected")
            valid_matched_dims = [
                mc for mc in matched_cols
                if mc not in non_group_metric_cols
                and mc not in active_filters
                and not any(k in mc.lower() for k in group_block_kw)
                and self.df_fact[mc].nunique() <= 80
            ]
            if len(valid_matched_dims) >= 2 and not is_multi_qtr_compare:
                c1, c2 = valid_matched_dims[0], valid_matched_dims[1]
                target_group_col = f"CAST({quote_sql_ident(c1)} AS VARCHAR) || ' · ' || CAST({quote_sql_ident(c2)} AS VARCHAR)"
            elif len(valid_matched_dims) == 1:
                target_group_col = valid_matched_dims[0]
        if not target_group_col and wants_breakdown:
            # Map common natural-language group words to schema columns (strictly excluding target & cost columns!)
            nl_group_map = [
                (["distributor", "distributors", "dealer", "dealers", "party", "parties", "account", "accounts"], ["distributor_name", "dealer_name", "party_name", "account_name", "distributor", "dealer"]),
                (["category", "categories", "brand", "brands"], ["category", "product_category", "brand"]),
                (["salesman", "sales rep", "salesperson", "sales team", "counselor", "account manager", "manager", "broker", "agent"], ["salesman_name", "salesman", "sales_rep", "sales_team", "account_manager", "manager", "broker", "agent"]),
                (["supplier", "vendor"], ["supplier", "vendor"]),
                (["courier", "carrier", "delivery partner", "fleet"], ["fleet_partner", "courier", "carrier"]),
                (["warehouse", "hub", "depot", "godam", "kitchen", "outlet", "branch", "store", "clinic"], ["warehouse", "hub", "depot", "kitchen", "outlet", "branch", "store", "clinic"]),
                (["truck", "vehicle", "route", "highway", "shift", "slot"], ["truck", "vehicle", "route", "shift", "slot"]),
                (["course", "plan", "membership", "policy", "property", "fabric"], ["course", "plan", "membership", "policy", "property", "fabric"]),
                (["sku", "product", "item", "menu"], ["sku_name", "sku_code", "sku", "product_name", "product_item", "product_category", "menu_item", "category"]),
                (["state", "rajya", "region", "zone", "city", "tier", "shahar", "territory", "province"], ["zone", "state", "city_tier", "city", "territory", "region", "province", "geography"]),
                (["payment", "gateway", "cod", "upi", "mode", "credit terms"], ["payment_mode", "payment_gateway", "payment_plan", "credit_terms", "payment", "gateway"]),
                (["channel", "marketing", "source", "portal"], ["sales_channel", "channel", "source", "market_segment", "portal"]),
                (["coupon", "promo"], ["coupon", "promo"]),
            ]
            for words_list, col_hints in nl_group_map:
                if any(w in q_clean for w in words_list):
                    for ch in col_hints:
                        found = next(
                            (
                                c for c in cols
                                if ch in c.lower()
                                and c not in active_filters
                                and c not in non_group_metric_cols
                                and not any(k in c.lower() for k in ("mrp", "price", "cost", "amount", "spend", "cogs", "margin", "discount", "line_no", "limit", "due", "days", "credit_note"))
                                and self.df_fact[c].nunique() <= 80
                            ),
                            None,
                        )
                        if found:
                            target_group_col = found
                            break
                if target_group_col:
                    break
            if not target_group_col and has_rng_filter:
                # For threshold/range fraud audits (e.g. 48k-50k credit notes), group by rep or distributor!
                target_group_col = next(
                    (c for c in cols if any(k in c.lower() for k in ("salesman_name", "sales_rep", "distributor_name", "dealer_name", "party_name", "account_name")) and c not in active_filters),
                    None,
                )
            if not target_group_col and not is_multi_qtr_compare and self.primary_dim and self.primary_dim not in active_filters:
                target_group_col = self.primary_dim

        if is_multi_qtr_compare and dcol:
            qtr_sql_expr = f"'Q' || CAST(EXTRACT(QUARTER FROM TRY_CAST({quote_sql_ident(dcol)} AS DATE)) AS VARCHAR)"
            if target_group_col and target_group_col != dcol and "(" not in target_group_col:
                target_group_col = f"{qtr_sql_expr} || ' · ' || CAST({quote_sql_ident(target_group_col)} AS VARCHAR)"
            else:
                target_group_col = qtr_sql_expr

        # Case 1: Row-level records requested (including explicit Top-N dispatch / intervention queries)
        if is_explicit_dispatch_top_n or (is_row_level_query and not wants_breakdown and not (is_count_query or is_margin_query or is_discount_query or is_csat_query)):
            display_cols = []
            for c in cols:
                c_low = c.lower()
                if c_low.startswith(('id_', 'id', 'pk_')) or c_low.endswith(('_id', '_key', '_code')):
                    display_cols.append(c)
                    break
            for extra_c in [self.target_col, self.primary_dim]:
                if extra_c and extra_c in cols and extra_c not in display_cols:
                    display_cols.append(extra_c)
            for mc in matched_cols:
                if mc not in display_cols and not is_sensitive_column_name(mc) and not is_index_artifact(mc):
                    display_cols.append(mc)
            if self.cost_col and self.cost_col not in display_cols:
                display_cols.append(self.cost_col)
            if "_is_target_event" not in display_cols:
                display_cols.append("_is_target_event")

            order_clause = ""
            if self.cost_col:
                order_clause = f"ORDER BY TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) DESC"
            elif matched_cols and pd.api.types.is_numeric_dtype(self.df_fact[matched_cols[0]]):
                order_clause = f"ORDER BY {quote_sql_ident(matched_cols[0])} DESC"

            sql = f"SELECT {', '.join(quote_sql_ident(c) for c in display_cols[:8])} FROM fact {where_sql} {order_clause} LIMIT {req_limit};"
            summary = f"Row-level query returning top {req_limit} individual records."
            return sql, summary, active_filters

        # Case 2: Group-by Dimension Breakdown
        if target_group_col and (wants_breakdown or (not active_filters and target_group_col in matched_cols)):
            self._last_group_col = target_group_col
            q_grp = target_group_col if ("(" in target_group_col or "CASE " in target_group_col or "||" in target_group_col) else quote_sql_ident(target_group_col)
            grp_by_clause = "1" if ("(" in target_group_col or "CASE " in target_group_col or "||" in target_group_col) else q_grp
            cost_sel = f", ROUND(SUM(CASE WHEN _is_target_event = 1 THEN TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) ELSE 0 END), 2) AS adverse_capital_drag" if self.cost_col else ""
            case2_extra_sql = extra_metrics_sql
            if target_group_col == dl_col:
                case2_extra_sql = case2_extra_sql.replace(f", ROUND(AVG(TRY_CAST({quote_sql_ident(dl_col)} AS DOUBLE)), 2) AS avg_delay_days", "")
            if "EXTRACT(MONTH" in target_group_col.upper() or "EXTRACT(QUARTER" in target_group_col.upper():
                order_by = "1 ASC"
            elif is_ar_due_query and due_col:
                order_by = "total_outstanding_due ASC" if is_bottom_query else "total_outstanding_due DESC"
            elif is_dso_query and dso_col:
                order_by = "avg_days_to_pay ASC" if is_bottom_query else "avg_days_to_pay DESC"
            elif has_rng_filter:
                order_by = "total_records DESC"
            elif is_ratio_pct_query and is_penalty_query and pen_col and self.cost_col:
                order_by = "penalty_pct_of_revenue ASC" if is_bottom_query else "penalty_pct_of_revenue DESC"
            elif is_delay_query and dl_col and target_group_col != dl_col:
                order_by = "avg_delay_days ASC" if is_bottom_query else "avg_delay_days DESC"
            elif is_margin_query and m_col:
                order_by = "total_net_margin ASC" if (is_bottom_query or is_losing_money) else "total_net_margin DESC"
            elif is_discount_query and d_col:
                order_by = "total_discount ASC" if is_bottom_query else "total_discount DESC"
            elif is_ad_roas_query and ad_col:
                order_by = "roas_multiplier ASC" if is_bottom_query else "total_ad_spend DESC"
            elif is_revenue_query and self.cost_col and not is_adverse_query:
                order_by = "total_revenue ASC" if is_bottom_query else "total_revenue DESC"
            elif is_csat_query and cs_col:
                order_by = "avg_csat_rating ASC" if (is_top_query or is_adverse_query) else "avg_csat_rating DESC"
            elif is_top_query or is_adverse_query:
                order_by = "adverse_rate_pct DESC"
            elif is_bottom_query:
                order_by = "adverse_rate_pct ASC"
            else:
                order_by = "total_records DESC"

            sql = f"""SELECT
    {q_grp} AS segment,
    COUNT(*) AS total_records,
    SUM(_is_target_event) AS adverse_events,
    ROUND(100.0 * AVG(_is_target_event), 2) AS adverse_rate_pct{cost_sel}{case2_extra_sql}
FROM fact
{where_sql}
GROUP BY {grp_by_clause}
ORDER BY {order_by}
LIMIT {req_limit};"""
            summary = f"Breakdown grouped by '{target_group_col}'" + (f" with active filters ({len(active_filters)})" if active_filters else "") + "."
            return sql, summary, active_filters

        # Case 3: Filtered or Overall Aggregate KPI Summary Query
        if active_filters or is_count_query or is_adverse_query or is_margin_query or is_discount_query or is_csat_query or is_delay_query or is_aov_query or not matched_cols:
            cost_sel = f", ROUND(SUM(CASE WHEN _is_target_event = 1 THEN TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE) ELSE 0 END), 2) AS total_adverse_drag, ROUND(SUM(TRY_CAST({quote_sql_ident(self.cost_col)} AS DOUBLE)), 2) AS total_portfolio_volume" if self.cost_col else ""
            sql = f"""SELECT
    COUNT(*) AS total_records,
    SUM(_is_target_event) AS total_adverse_events,
    ROUND(100.0 * AVG(_is_target_event), 2) AS overall_adverse_rate_pct{cost_sel}{extra_metrics_sql}
FROM fact
{where_sql};"""
            summary = "Filtered aggregate metrics on physical fact records." if active_filters else "Overall physical business volume, adverse events, and aggregate financial liability."
            return sql, summary, active_filters

        # Case 4: Sample records querying matched physical columns
        selected_cols = [quote_sql_ident(c) for c in matched_cols[:6] if not is_sensitive_column_name(c)]
        if "_is_target_event" not in selected_cols:
            selected_cols.append("_is_target_event")
        sql = f"SELECT {', '.join(selected_cols)} FROM fact {where_sql} LIMIT {req_limit};"
        summary = f"Sample records querying physical columns: {', '.join(matched_cols[:6])}."
        return sql, summary, active_filters

    def synthesize_deterministic_sql(self, question: str) -> Tuple[str, str]:
        """Backward-compatible wrapper returning (sql, summary)."""
        sql, summary, _ = self._synthesize_deterministic_sql_with_context(question, prior_filters=None)
        return sql, summary

    def translate_question_to_sql(self, question: str, use_llm: bool = True) -> Tuple[str, str, str]:
        """
        Translates a natural language question to DuckDB SQL.
        Uses Paced Gemini LLM when available, falling back safely to deterministic synthesis.
        Returns: (sql_query, explanation, mode)
        """
        clean_q = scrub_text(str(question or "").strip())
        q_low_fast = clean_q.lower()

        # High-precision deterministic bypass for complex window/CTE CFO queries (Pareto 80/20, Composite Duplicate Audit)
        is_high_prec_fast = bool(
            re.search(r'\btop\s+\d{1,2}\s*%', q_low_fast)
            or any(k in q_low_fast for k in ("80/20", "80-20", "pareto", "revenue concentration", "customer concentration", "duplicate bill", "double billing", "double bill", "duplicate"))
        )
        if is_high_prec_fast:
            sql, summary = self.synthesize_deterministic_sql(clean_q)
            return sql, summary, "deterministic_engine"

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
            "6. Always wrap column names in double quotes if they contain spaces or special characters.\n"
            "7. Group ONLY by the specific column(s) the user asked about (e.g. if the user asks about Delivery_Days, group ONLY by Delivery_Days without adding Courier_Partner or Primary Dimension unless asked).\n"
            "8. Cast integer count sums like SUM(_is_target_event) AS BIGINT so order counts are whole numbers."
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
                elif isinstance(v, np.generic):
                    row[k] = v.item()

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

    def _lookup_200_question(self, question: str) -> Optional[Dict[str, Any]]:
        """Matches explicit Q001-Q200 IDs or specialized forensic topics in Universal 200 Matrix."""
        if not isinstance(self.questions_200, dict):
            return None
        qs = self.questions_200.get("questions") or []
        if not qs:
            return None
        q_raw = str(question or "").strip()
        qid_m = re.search(r'\b(Q(?:0\d\d|1\d\d|200))\b', q_raw.upper())
        if qid_m:
            target_id = qid_m.group(1)
            for item in qs:
                if item.get("id") == target_id:
                    return item
        q_low = q_raw.lower()
        topic_map = [
            ("benford", "Q174"),
            ("rfm", "Q079"),
            ("bcg", "Q090"),
            ("market basket", "Q093"),
            ("cross-sell", "Q093"),
            ("gateway", "Q091"),
            ("pareto", "Q007"),
            ("promo-acquired", "Q049"),
            ("bargain hunter", "Q049"),
            ("unit economics waterfall", "Q025"),
            ("optimal courier allocation", "Q124"),
            ("reorder gap", "Q080"),
            ("reorder reminder", "Q080"),
        ]
        for kw, qid in topic_map:
            if kw in q_low:
                for item in qs:
                    if item.get("id") == qid:
                        return item
        return None

    def ask(
        self,
        question: str,
        language: str = "auto",
        use_llm: bool = True,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Processes a natural language business question (supporting multi-turn follow-ups),
        checks honest column availability, executes read-only DuckDB SQL, and returns a
        100% physically grounded bilingual Business-Doctor response with dynamic currency.
        """
        resolved_lang = detect_language_preference(question, explicit_lang=language)

        # 1. Honest Missing-Column Guard (never dump a misleading fallback summary for absent sheets!)
        missing_info = self._detect_missing_domain_concept(question)
        if missing_info is not None:
            avail_cols = [c for c in self.df_fact.columns if not is_sensitive_column_name(c) and c != "_is_target_event"][:12]
            cols_preview = ", ".join(f"`{c}`" for c in avail_cols)
            if resolved_lang == "english":
                md_miss = (
                    f"### ⚪ Data Not Present in Current Sheet: {missing_info['label_en']}\n"
                    f"Your uploaded file does not contain columns for **{missing_info['label_en']}** — "
                    f"so DataX-Ray refuses to guess or fabricate numbers.\n\n"
                    f"- **Sheet/Column Needed to Unlock:** `{missing_info['needed_sheet']}`\n"
                    f"- **Available Columns You Can Query Right Now:** {cols_preview}"
                )
                if "Profit" in missing_info['label_en'] and self.is_financial and self.cost_col:
                    tot_sales = float(pd.to_numeric(self.df_fact[self.cost_col], errors='coerce').sum())
                    adv_sales = float(pd.to_numeric(self.df_fact.loc[self.df_fact["_is_target_event"] == 1, self.cost_col], errors='coerce').sum())
                    deliv_sales = tot_sales - adv_sales
                    md_miss += (
                        f"\n\n#### 📊 What Your Uploaded Sales Data Shows Right Now:\n"
                        f"- **Gross Sales (Total Orders)**: {self._format_money_val(tot_sales)}\n"
                        f"- **Lost Revenue (Returns & Cancellations)**: {self._format_money_val(adv_sales)}\n"
                        f"- **Successfully Delivered Revenue**: {self._format_money_val(deliv_sales)}\n"
                        f"*To calculate Net Profit and Profit Margin %, upload your Purchase / Cost Price sheet.*"
                    )
            else:
                md_miss = (
                    f"### ⚪ मौजूदा शीट में यह डेटा उपलब्ध नहीं है: {missing_info['label_hi']}\n"
                    f"आपकी अपलोड की गई फ़ाइल में **{missing_info['label_hi']}** के कॉलम नहीं हैं — "
                    f"इसलिए DataX-Ray बिना सबूत के कोई झूठा नंबर नहीं दिखाएगा।\n\n"
                    f"- **अनलॉक करने के लिए जरूरी शीट/कॉलम:** `{missing_info['needed_sheet']}`\n"
                    f"- **अभी आपकी शीट में उपलब्ध कॉलम जिन पर आप सवाल पूछ सकते हैं:** {cols_preview}"
                )
                if "Profit" in missing_info['label_en'] and self.is_financial and self.cost_col:
                    tot_sales = float(pd.to_numeric(self.df_fact[self.cost_col], errors='coerce').sum())
                    adv_sales = float(pd.to_numeric(self.df_fact.loc[self.df_fact["_is_target_event"] == 1, self.cost_col], errors='coerce').sum())
                    deliv_sales = tot_sales - adv_sales
                    md_miss += (
                        f"\n\n#### 📊 आपकी शीट से कुल बिक्री का हिसाब (Pramanit Data):\n"
                        f"- **कुल बिक्री (Gross Sales)**: {self._format_money_val(tot_sales)}\n"
                        f"- **रिटर्न व कैंसिलेशन में डूबी रकम**: {self._format_money_val(adv_sales)}\n"
                        f"- **सफल पूरी हुई बिक्री (Delivered Revenue)**: {self._format_money_val(deliv_sales)}\n"
                        f"*शुद्ध मुनाफ़ा (Net Profit) जानने के लिए कृपया खरीद लागत (Cost Price / COGS) की शीट जोड़ें।*"
                    )
            return {
                "status": "missing_data_explained",
                "question": question,
                "language": resolved_lang,
                "sql_executed": "-- Honest Missing-Column Guard (0 fabricated figures)",
                "sql_generation_mode": "missing_column_guard",
                "active_filters": {},
                "row_count_returned": 0,
                "columns": [],
                "data": [],
                "answer_markdown": md_miss,
                "plain_summary": md_miss,
                "answer": md_miss,
                "vega_lite_spec": None,
                "grounding_verified": True,
            }

        # 2. Direct Universal 200-Question Matrix Lookup (Q001-Q200 / RFM / Benford / Market Basket / BCG)
        matched_q200 = self._lookup_200_question(question)
        if matched_q200 is not None:
            ans_txt = matched_q200.get("answer_hi") if resolved_lang == "hinglish" else matched_q200.get("answer_en")
            q_txt = matched_q200.get("question_hi") if resolved_lang == "hinglish" else matched_q200.get("question_en")
            md = (
                f"### 📌 {matched_q200.get('id')} · {matched_q200.get('pillar_name')}\n"
                f"**Question:** {q_txt}\n\n"
                f"**Key Metric:** `{matched_q200.get('key_metric')}` *({matched_q200.get('status')})*\n\n"
                f"{ans_txt}"
            )
            return {
                "status": "success",
                "question": question,
                "language": resolved_lang,
                "sql_executed": f"-- Universal 200-Question Matrix ({matched_q200.get('id')})",
                "sql_generation_mode": "universal_200_matrix",
                "active_filters": {},
                "row_count_returned": 1,
                "columns": ["question_id", "key_metric", "status"],
                "data": [{"question_id": matched_q200.get("id"), "key_metric": matched_q200.get("key_metric"), "status": matched_q200.get("status")}],
                "answer_markdown": md,
                "plain_summary": md,
                "answer": md,
                "vega_lite_spec": None,
                "grounding_verified": True,
            }

        # 2.5 Priority Worklist / Call List Handler ("Kis customer ko pehle call karu?", "Who to call today?")
        q_clean_call = str(question or "").lower()
        is_call_query = any(re.search(rf'\b{w}\b', q_clean_call) for w in [
            'call list', 'priority list', 'worklist', 'action list', 'whom to call', 'who to call',
            'who should i call', 'who should we call', 'which customer to call', 'which customer should i call',
            'whom should we contact', 'whom to contact', 'parties to call', 'accounts to contact',
            'kisko call', 'kis customer ko pehle call', 'kise call', 'pehle call', 'call karu', 'call karein', 'call karna', 'kise pehle call',
            'phone lagwana', 'phone karna', 'phone karu', 'phone lagau', 'kin 5 parties'
        ])
        if is_call_query:
            wl_file = self.output_dir / "actionable_priority_worklist.csv"
            if wl_file.exists():
                try:
                    df_wl = pd.read_csv(wl_file)
                    top_wl = df_wl.head(5).to_dict(orient="records")
                    def _pick_display_order_id(row_dict: Dict[str, Any]) -> str:
                        for cand_k in ("Order No.", "Order No", "Order_No_", "order_id", "Order_ID", "invoice_no", "Invoice No.", "bill_no", "awb_no"):
                            if cand_k in row_dict and pd.notna(row_dict[cand_k]) and str(row_dict[cand_k]).strip():
                                v = str(row_dict[cand_k]).strip()
                                return v if v.startswith("#") else f"#{v}"
                        fb = str(row_dict.get("fact_surrogate_id", "")).strip()
                        return fb if fb.startswith("#") else f"#{fb}"

                    if resolved_lang == "english":
                        md_wl = "### 📞 Today's Top Priority Action List (Immediate Customer Calls)\n"
                        md_wl += "Here are the top in-flight/active orders where customer contact is urgently recommended to prevent return/cancellation:\n\n"
                        for idx, item in enumerate(top_wl, 1):
                            rank = item.get("priority_rank", idx)
                            amt = item.get("monetary_exposure")
                            amt_val = float(amt) if amt is not None and not pd.isna(amt) else 0.0
                            amt_str = self._format_money_val(amt_val) if amt_val > 0 else "**N/A**"
                            risk = float(item.get("empirical_cohort_risk_pct") or 0.0)
                            reason = item.get("primary_risk_reason", "")
                            action = item.get("recommended_next_step", "")
                            ord_lbl = _pick_display_order_id(item)
                            md_wl += f"- **#{rank} Order {ord_lbl}** — Amount: {amt_str} | Return Risk: **{risk:.1f}%**\n"
                            md_wl += f"  - *Root Cause:* {reason}\n"
                            md_wl += f"  - *Action:* {action}\n\n"
                        md_wl += "*(Full prioritized call list is available in `actionable_priority_worklist.csv` or Dashboard Action Queue)*"
                    else:
                        md_wl = "### 📞 आज की प्राथमिकता कॉल लिस्ट (तुरंत एक्शन)\n"
                        md_wl += "यहाँ वे सबसे जोखिम भरे एक्टिव/इन-ट्रांजिट ऑर्डर हैं जिन पर कस्टमर से तुरंत बात करके रिटर्न/नुकसान रोका जा सकता है:\n\n"
                        for idx, item in enumerate(top_wl, 1):
                            rank = item.get("priority_rank", idx)
                            amt = item.get("monetary_exposure")
                            amt_val = float(amt) if amt is not None and not pd.isna(amt) else 0.0
                            amt_str = self._format_money_val(amt_val) if amt_val > 0 else "**N/A**"
                            risk = float(item.get("empirical_cohort_risk_pct") or 0.0)
                            reason = item.get("primary_risk_reason", "")
                            action = item.get("recommended_next_step", "")
                            ord_lbl = _pick_display_order_id(item)
                            md_wl += f"- **#{rank} ऑर्डर {ord_lbl}** — रकम: {amt_str} | रिटर्न का खतरा: **{risk:.1f}%**\n"
                            md_wl += f"  - *वजह:* {reason}\n"
                            md_wl += f"  - *कदम:* {action}\n\n"
                        md_wl += "*(पूरी लिस्ट डैशबोर्ड के Action Queue और `actionable_priority_worklist.csv` में उपलब्ध है)*"
                    return {
                        "status": "success",
                        "question": question,
                        "language": resolved_lang,
                        "sql_executed": "-- Priority Worklist Dispatch (actionable_priority_worklist.csv)",
                        "sql_generation_mode": "priority_worklist",
                        "active_filters": {},
                        "row_count_returned": len(top_wl),
                        "columns": list(df_wl.columns),
                        "data": top_wl,
                        "answer_markdown": md_wl,
                        "plain_summary": md_wl,
                        "answer": md_wl,
                        "vega_lite_spec": None,
                        "grounding_verified": True,
                    }
                except Exception:
                    pass

        # 3. Resolve Multi-Turn Follow-Up Context (ONLY when explicit follow-up cue applies to avoid cross-query filter poisoning!)
        q_clean_fl = str(question or "").lower()
        is_followup_cue = any(
            re.search(rf'\b{w}\b', q_clean_fl)
            for w in ["sirf", "only", "usme", "isme", "now", "also", "what about", "ab", "instead", "baki", "and in", "how about", "within that", "for those", "unka", "inka", "aur"]
        )
        prior_filters: Dict[str, str] = {}
        if is_followup_cue:
            if isinstance(history, list) and len(history) > 0:
                for turn in reversed(history[-4:]):
                    if isinstance(turn, dict):
                        prev_q = turn.get("question")
                        if prev_q:
                            extracted_prev = self._extract_filters_from_question(str(prev_q))
                            if extracted_prev:
                                prior_filters = extracted_prev
                                break
            elif self.conversation_history:
                for turn in reversed(self.conversation_history[-4:]):
                    if isinstance(turn, dict) and isinstance(turn.get("active_filters"), dict) and turn["active_filters"]:
                        prior_filters = dict(turn["active_filters"])
                        break

        # 4. Synthesize Read-Only DuckDB SQL (LLM with fallback to upgraded Multi-Filter Deterministic Compiler)
        active_filters: Dict[str, str] = {}
        if use_llm and _get_shared_llm_client() is not None:
            ctx_q = question
            if prior_filters:
                ctx_q = f"{question} (Follow-up context filters if applicable: {'; '.join(prior_filters.values())})"
            sql, explanation, mode = self.translate_question_to_sql(ctx_q, use_llm=True)
            if mode == "deterministic_engine":
                sql, explanation, active_filters = self._synthesize_deterministic_sql_with_context(question, prior_filters=prior_filters)
            else:
                active_filters = {**prior_filters, **self._extract_filters_from_question(question)}
        else:
            sql, explanation, active_filters = self._synthesize_deterministic_sql_with_context(question, prior_filters=prior_filters)
            mode = "deterministic_engine"

        # Enforce row limit & mandatory Read-Only Sandbox Security Gate on ALL paths
        sql = enforce_sql_row_limit(sql, max_rows=200)
        sec_violations = validate_readonly_duckdb_sql(sql)
        if sec_violations:
            sec_msg = f"**Security Sandbox Block**: {'; '.join(sec_violations)}"
            return {
                "status": "blocked",
                "question": question,
                "language": resolved_lang,
                "sql_executed": "-- Blocked by read-only DuckDB sandbox",
                "sql_generation_mode": mode,
                "active_filters": {},
                "row_count_returned": 0,
                "columns": [],
                "data": [],
                "answer_markdown": sec_msg,
                "plain_summary": sec_msg,
                "answer": sec_msg,
                "vega_lite_spec": None,
                "grounding_verified": False,
                "error": sec_msg,
            }

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
                "status": "error",
                "question": question,
                "language": resolved_lang,
                "sql_executed": sql,
                "sql_generation_mode": mode,
                "active_filters": active_filters,
                "row_count_returned": 0,
                "columns": [],
                "data": [],
                "answer_markdown": err_msg,
                "plain_summary": err_msg,
                "answer": err_msg,
                "vega_lite_spec": None,
                "grounding_verified": False,
                "error": str(e)
            }

        # Clean inf/nan for strict JSON serialization
        res_df_clean = res_df.replace([np.inf, -np.inf], np.nan)

        # Post-Query Honest Missing-Data Safety Net: if LLM returned a dummy NULL-only result (e.g. SELECT 'metric', NULL), refuse cleanly instead of printing blank bullets
        if len(res_df_clean) > 0 and len(res_df_clean.columns) >= 2:
            val_cols = [c for c in res_df_clean.columns if c.lower() not in ("metric", "column", "field", "name", "label", "segment")]
            if val_cols and all(res_df_clean[vc].isna().all() for vc in val_cols):
                avail_cols = ", ".join(f"`{c}`" for c in list(self.df_fact.columns)[:12] if not is_index_artifact(c))
                refusal_md = (
                    f"### ⚪ Requested Data Is Not Present in This Dataset\n"
                    f"The requested metric does not exist in your uploaded table — DataX-Ray will never fabricate placeholder numbers.\n\n"
                    f"- **Available columns you can query right now:** {avail_cols}"
                    if resolved_lang == "english" else
                    f"### ⚪ मौजूदा शीट में यह डेटा उपलब्ध नहीं है\n"
                    f"आपकी अपलोड की गई फ़ाइल में यह कॉलम मौजूद नहीं है — DataX-Ray बिना सबूत के कोई झूठा नंबर नहीं दिखाएगा।\n\n"
                    f"- **अभी आपकी शीट में उपलब्ध कॉलम जिन पर आप सवाल पूछ सकते हैं:** {avail_cols}"
                )
                return {
                    "status": "success",
                    "question": question,
                    "language": resolved_lang,
                    "sql_executed": "-- Honest Missing-Column Guard (NULL-only query intercepted; 0 fabricated figures)",
                    "sql_generation_mode": "missing_column_guard",
                    "active_filters": {},
                    "row_count_returned": 0,
                    "columns": [],
                    "data": [],
                    "answer_markdown": refusal_md,
                    "plain_summary": refusal_md,
                    "answer": refusal_md,
                    "vega_lite_spec": None,
                    "grounding_verified": True,
                }
        records = [
            {k: (None if pd.isna(v) else (v.item() if isinstance(v, np.generic) else v)) for k, v in row.items()}
            for row in res_df_clean.to_dict(orient="records")
        ]

        # Persist turn into session memory
        self.conversation_history.append({"question": question, "active_filters": dict(active_filters)})
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

        # Format 100% physically grounded Business-Doctor answer markdown
        answer_md = self._format_grounded_answer(question, res_df_clean, resolved_lang, active_filters=active_filters)
        vega_spec = self._generate_vega_spec(res_df_clean, question)

        return {
            "status": "success",
            "question": question,
            "language": resolved_lang,
            "sql_executed": sql,
            "sql_generation_mode": mode,
            "active_filters": active_filters,
            "row_count_returned": len(res_df_clean),
            "columns": list(res_df_clean.columns),
            "data": records,
            "answer_markdown": answer_md,
            "plain_summary": answer_md,
            "answer": answer_md,
            "vega_lite_spec": vega_spec,
            "grounding_verified": True
        }

    def _format_money_val(self, val: float, sym_override: Optional[str] = None, numbering_override: Optional[str] = None) -> str:
        """Formats monetary figures strictly using dataset or row-native currency symbol (zero fake $ on non-monetary or INR data)."""
        sym = sym_override if sym_override is not None else self.unit_symbol
        if not self.is_financial or not sym:
            return f"**{val:,.2f}**"
        num_sys = numbering_override if numbering_override is not None else ("indian" if sym == "₹" else self.numbering_system)
        sign = "-" if val < 0 else ""
        av = abs(val)
        if num_sys == "indian" or sym == "₹":
            if av >= 1e7:
                return f"**{sign}{sym}{av / 1e7:.2f} Cr ({sign}{sym}{av:,.2f})**"
            if av >= 1e5:
                return f"**{sign}{sym}{av / 1e5:.2f} L ({sign}{sym}{av:,.2f})**"
        return f"**{sign}{sym}{av:,.2f}**"

    def _humanize_filter_text(self, pred: str) -> str:
        """Converts raw SQL WHERE predicates like '\"State\" IN ('UP', 'Bihar')' into plain human text."""
        s = str(pred or "").strip()
        m_in = re.match(r'^"?([A-Za-z0-9_ ]+)"?\s+IN\s*\((.+)\)$', s, re.IGNORECASE)
        if m_in:
            col = m_in.group(1).replace("_", " ").title()
            vals = [v.strip().strip("'\"") for v in m_in.group(2).split(",")]
            return f"**{col}**: {', '.join(vals)}"
        m_eq = re.match(r'^(?:TRY_CAST\()?"?([A-Za-z0-9_ ]+)"?(?:\s+AS\s+[A-Z]+)?\)?\s*(=|>=|<=|>|<)\s*(.+)$', s, re.IGNORECASE)
        if m_eq:
            col = m_eq.group(1).replace("_", " ").title()
            op = m_eq.group(2)
            val = m_eq.group(3).strip().strip("'\"")
            return f"**{col}** {':' if op == '=' else op} {val}"
        if "not like '%cod%'" in s.lower():
            return "**Payment Mode**: Prepaid / Non-COD"
        return s.replace('"', '').replace("'", "")

    def _friendly_col_label(self, col_name: str, lang: str = "english") -> str:
        """Translates internal SQL column aliases into domain-accurate everyday business words."""
        low = str(col_name or "").strip().lower()
        t_low = str(self.target_col or "").lower()
        is_non_order_domain = (not self.is_financial) or any(k in t_low for k in ("readmit", "death", "mortality", "attrition", "default", "churn", "stroke", "disease", "failure"))
        en_map = {
            "total_records": "Total Records" if is_non_order_domain else "Total Orders",
            "total_orders": "Total Records" if is_non_order_domain else "Total Orders",
            "adverse_events": "Flagged / Adverse Cases" if is_non_order_domain else "Problem / Returned Orders",
            "total_adverse_events": "Flagged / Adverse Cases" if is_non_order_domain else "Problem / Returned Orders",
            "adverse_orders": "Flagged / Adverse Cases" if is_non_order_domain else "Problem / Returned Orders",
            "total_returns": "Returned Orders",
            "total_returned": "Returned Orders",
            "returned_orders": "Returned Orders",
            "adverse_rate_pct": "Adverse Rate" if is_non_order_domain else "Problem / Return Rate",
            "overall_adverse_rate_pct": "Adverse Rate" if is_non_order_domain else "Problem / Return Rate",
            "return_rate_pct": "Return Rate",
            "return_rate": "Return Rate",
            "adverse_capital_drag": "Money at Risk / Lost",
            "total_adverse_drag": "Money at Risk / Lost",
            "total_loss": "Money Lost",
            "total_portfolio_volume": "Total Sales Value",
            "total_revenue": "Total Revenue",
            "total_cogs": "Total COGS",
            "total_op_cost": "Total Operating / Fuel Cost",
            "total_sla_penalty": "Total SLA Penalty",
            "penalty_pct_of_revenue": "SLA Penalty % of Revenue",
            "total_outstanding_due": "Total Unpaid / Outstanding Due",
            "avg_days_to_pay": "Avg Days to Pay (DSO)",
            "avg_discount_pct": "Avg Discount %",
            "total_credit_note_amount": "Total Credit Note Value",
            "duplicate_groups": "Duplicate Transaction Groups",
            "extra_duplicate_rows": "Duplicate / Double-Billed Rows",
            "duplicated_cash_exposure": "Duplicated Billing Exposure",
            "total_ad_spend": "Total Ad Spend",
            "roas_multiplier": "ROAS (x)",
            "total_discount": "Total Discount Given",
            "avg_order_value_aov": "Avg Order Value (AOV)",
            "avg_delay_days": "Avg Delivery Days",
            "total_net_margin": "Total Net Profit",
            "avg_margin_per_order": "Avg Profit per Order",
            "repeat_customer_rate_pct": "Repeat Customer Rate",
            "unique_customers": "Unique Customers",
            "repeat_customers": "Repeat Customers",
            "one_time_customers": "One-Time Customers",
            "top_cohort_entities": "Top-Cohort Accounts",
            "total_unique_entities": "Total Unique Accounts",
            "top_cohort_revenue": "Top-Cohort Revenue",
            "top_cohort_revenue_share_pct": "Top-Cohort Revenue Share (%)",
        }
        hi_map = {
            "total_records": "कुल ऑर्डर (Total Orders)",
            "total_orders": "कुल ऑर्डर (Total Orders)",
            "adverse_events": "खराब/वापस आए ऑर्डर (Problem Orders)",
            "total_adverse_events": "खराब/वापस आए ऑर्डर (Problem Orders)",
            "adverse_orders": "खराब/वापस आए ऑर्डर (Problem Orders)",
            "total_returns": "वापस आए ऑर्डर (Returns)",
            "total_returned": "वापस आए ऑर्डर (Returns)",
            "returned_orders": "वापस आए ऑर्डर (Returns)",
            "adverse_rate_pct": "नुकसान/रिटर्न दर (Problem Rate)",
            "overall_adverse_rate_pct": "नुकसान/रिटर्न दर (Problem Rate)",
            "return_rate_pct": "रिटर्न दर (Return Rate)",
            "return_rate": "रिटर्न दर (Return Rate)",
            "adverse_capital_drag": "फँसी/डूबी रकम (Money at Risk)",
            "total_adverse_drag": "फँसी/डूबी रकम (Money at Risk)",
            "total_loss": "कुल नुकसान (Money Lost)",
            "total_portfolio_volume": "कुल बिक्री रकम (Total Sales)",
            "total_revenue": "कुल बिक्री (Total Revenue)",
            "total_cogs": "कुल खरीद लागत (Total COGS)",
            "total_ad_spend": "कुल विज्ञापन खर्च (Ad Spend)",
            "roas_multiplier": "ROAS (रिटर्न गुना)",
            "total_discount": "कुल डिस्काउंट (Total Discount)",
            "avg_discount_pct": "औसत डिस्काउंट % (Avg Discount)",
            "total_outstanding_due": "कुल बकाया उधारी (Total Unpaid Due)",
            "avg_days_to_pay": "औसत भुगतान दिन (Avg DSO Days)",
            "total_credit_note_amount": "कुल क्रेडिट नोट (Total Credit Note)",
            "duplicate_groups": "डुप्लिकेट बिल ग्रुप (Duplicate Groups)",
            "extra_duplicate_rows": "अतिरिक्त डुप्लिकेट एंट्री (Extra Duplicate Rows)",
            "duplicated_cash_exposure": "डुप्लिकेट बिलिंग रकम (Duplicate Exposure)",
            "avg_order_value_aov": "औसत ऑर्डर साइज (AOV)",
            "avg_delay_days": "औसत डिलीवरी दिन (Delivery Days)",
            "total_net_margin": "कुल शुद्ध मुनाफा (Net Profit)",
            "avg_margin_per_order": "प्रति ऑर्डर मुनाफा (Avg Profit)",
            "repeat_customer_rate_pct": "रिपीट ग्राहक दर (Repeat Rate)",
            "unique_customers": "कुल यूनिक ग्राहक",
            "repeat_customers": "रिपीट ग्राहक",
            "one_time_customers": "एक बार वाले ग्राहक",
        }
        if lang != "english":
            return hi_map.get(low, str(col_name).replace("_", " ").title())
        return en_map.get(low, str(col_name).replace("_", " ").title())

    def _is_money_column(self, col_name: str) -> bool:
        low = str(col_name or "").strip().lower()
        if any(k in low for k in ("rate", "pct", "percent", "count", "orders", "events", "records", "days", "rank", "roas", "multiplier")):
            if not any(m in low for m in ("amount", "value", "drag", "loss", "margin", "profit", "revenue", "cost", "aov", "discount", "inr", "usd")):
                return False
        if self.cost_col and low == str(self.cost_col).lower():
            return True
        return any(k in low for k in (
            "cost", "drag", "loss", "revenue", "dollar", "portfolio", "amount",
            "fee", "mrr", "arr", "valor", "gasto", "charge", "salary", "penalty", "lease", "due", "credit_note",
            "claim", "price", "balance", "billing", "margin", "profit", "cogs",
            "discount", "aov", "sales", "spend", "value", "inr", "usd", "exposure", "burn", "nuksan"
        ))

    def _build_doctor_takeaway(self, df: pd.DataFrame, lang: str) -> str:
        """Adds a 1-line Business-Doctor Expected-vs-Actual diagnosis comparing query risk rate to baseline."""
        if "repeat_customer_rate_pct" in df.columns and len(df) > 0:
            try:
                rep_r = float(pd.to_numeric(df["repeat_customer_rate_pct"].iloc[0], errors="coerce"))
                if np.isfinite(rep_r):
                    if rep_r >= 25.0:
                        return (
                            f"\n\n🩺 **Business-Doctor Verdict:** ✅ **Strong Customer Loyalty** — **{rep_r:.2f}%** of your customers are repeat buyers (well above the 20% healthy retention benchmark)."
                            if lang == "english" else
                            f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ✅ **मज़बूत ग्राहक वफादारी** — आपके **{rep_r:.2f}%** ग्राहक बार-बार खरीदारी (Repeat Buyers) कर रहे हैं (20% के स्वस्थ मानक से काफी बेहतर)।"
                        )
                    return (
                        f"\n\n🩺 **Business-Doctor Verdict:** ⚠️ **Low Repeat Retention** — Only **{rep_r:.2f}%** of buyers reorder (healthy benchmark is >= 25%)."
                        if lang == "english" else
                        f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ⚠️ **कम रिपीट ग्राहक दर** — केवल **{rep_r:.2f}%** ग्राहक दोबारा ऑर्डर कर रहे हैं (स्वस्थ स्तर >= 25% होना चाहिए)।"
                    )
            except Exception:
                pass

        if "total_net_margin" in df.columns and len(df) >= 1:
            try:
                s_nm = pd.to_numeric(df["total_net_margin"], errors="coerce")
                if s_nm.notna().any() and float(s_nm.min()) < 0:
                    w_pos = int(np.nanargmin(s_nm.values))
                    w_loss = float(s_nm.iloc[w_pos])
                    w_seg = str(df["segment"].iloc[w_pos]) if "segment" in df.columns else str(df.iloc[w_pos, 0])
                    loss_fmt = self._format_money_val(w_loss)
                    return (
                        f"\n\n🩺 **Business-Doctor Verdict:** ⚠️ **Profitless Revenue / Negative-Margin Alert** — **{w_seg}** is generating a net cash loss of {loss_fmt} after COGS, discounts, shipping, and ad spend!"
                        if lang == "english" else
                        f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ⚠️ **घाटे की बिक्री (Negative-Margin Alert)** — **{w_seg}** में COGS, डिस्काउंट, शिपिंग व विज्ञापन खर्च के बाद {loss_fmt} का शुद्ध नकद घाटा हो रहा है!"
                    )
            except Exception:
                pass

        positive_rate_cols = {"repeat_customer_rate_pct", "retention_rate_pct", "delivery_rate_pct", "reliability_rate_pct", "success_rate_pct", "win_rate_pct"}
        rate_col = next(
            (
                c for c in df.columns
                if c.lower() not in positive_rate_cols
                and (("rate" in c.lower() and "pct" in c.lower()) or c.lower() in ("return_rate", "failure_rate", "churn_rate", "adverse_rate", "rto_rate"))
            ),
            None,
        )
        if not rate_col or self.overall_rate_pct <= 0 or len(df) == 0:
            return ""
        try:
            s_rates = pd.to_numeric(df[rate_col], errors="coerce")
            if not s_rates.notna().any():
                return ""
            # When comparing multiple rows (e.g. Bihar vs UP), evaluate the highest-risk row so severe problems are never masked!
            row_pos = int(np.nanargmax(s_rates.values)) if len(df) >= 2 else 0
            obs_rate = float(s_rates.iloc[row_pos])
            if not np.isfinite(obs_rate):
                return ""

            cnt_col = next(
                (c for c in df.columns if any(k in c.lower() for k in ("total_records", "total_orders", "orders_cnt", "order_count", "volume", "count")) and c != rate_col),
                None,
            )
            fail_col = next(
                (c for c in df.columns if any(k in c.lower() for k in ("adverse_events", "total_adverse", "adverse_orders", "total_returns", "total_returned", "returned_orders", "failures", "returns")) and c not in (rate_col, cnt_col)),
                None,
            )
            metric_like_cols = {rate_col, cnt_col, fail_col}
            seg_col = "segment" if "segment" in df.columns else (
                df.columns[0]
                if (len(df) >= 2 and len(df.columns) >= 2 and df.columns[0] not in metric_like_cols and not self._is_money_column(df.columns[0]))
                else None
            )

            # Epidemiological rest-of-business baseline & statistical significance guard (prevents random-noise false alarms!)
            ref_baseline = self.overall_rate_pct
            ref_lbl_en = "company average"
            ref_lbl_hi = "कंपनी औसत"
            is_stat_significant = True
            if cnt_col and fail_col:
                n0 = int(pd.to_numeric(df[cnt_col].iloc[row_pos], errors="coerce") or 0)
                k0 = int(pd.to_numeric(df[fail_col].iloc[row_pos], errors="coerce") or 0)
                tot_n = len(self.df_fact)
                tot_k = int(self.df_fact["_is_target_event"].sum()) if "_is_target_event" in self.df_fact.columns else 0
                if 0 < n0 < tot_n and (tot_n - n0) >= 10:
                    n1 = tot_n - n0
                    k1 = tot_k - k0
                    rest_r = (k1 / float(n1)) * 100.0
                    if rest_r > 0:
                        ref_baseline = rest_r
                        ref_lbl_en = "rest-of-business normal rate"
                        ref_lbl_hi = "बाकी बिज़नेस के सामान्य औसत"
                    p_pool = (k0 + k1) / float(n0 + n1)
                    se = np.sqrt(max(p_pool * (1.0 - p_pool) * (1.0 / n0 + 1.0 / n1), 1e-12))
                    z_score = abs((k0 / float(n0)) - (k1 / float(n1))) / se
                    is_stat_significant = bool(z_score >= 1.96)
            mult = obs_rate / max(ref_baseline, 1e-9)
            raw_seg_val = str(df[seg_col].iloc[row_pos]) if seg_col else ""
            if raw_seg_val.endswith(".0") and raw_seg_val[:-2].isdigit():
                raw_seg_val = raw_seg_val[:-2]
            grp_prefix = getattr(self, "_last_group_col", None) or (seg_col if seg_col and seg_col != "segment" else None)
            month_names = {
                "1": "January", "2": "February", "3": "March", "4": "April", "5": "May", "6": "June",
                "7": "July", "8": "August", "9": "September", "10": "October", "11": "November", "12": "December"
            }
            if "EXTRACT(MONTH" in str(grp_prefix).upper() and len(df) >= 2 and seg_col:
                m_start_raw = str(df[seg_col].iloc[0])
                m_end_raw = str(df[seg_col].iloc[-1])
                if m_start_raw.endswith(".0") and m_start_raw[:-2].isdigit():
                    m_start_raw = m_start_raw[:-2]
                if m_end_raw.endswith(".0") and m_end_raw[:-2].isdigit():
                    m_end_raw = m_end_raw[:-2]
                m_start_lbl = month_names.get(m_start_raw, f"Month {m_start_raw}")
                m_end_lbl = month_names.get(m_end_raw, f"Month {m_end_raw}")
                r_start = float(pd.to_numeric(df[rate_col].iloc[0], errors="coerce"))
                r_end = float(pd.to_numeric(df[rate_col].iloc[-1], errors="coerce"))
                delta = r_end - r_start
                sign_s = "+" if delta > 0 else ""
                if abs(delta) < 1.0:
                    return (
                        f"\n\n🩺 **Business-Doctor Verdict:** ℹ️ **Stable Month-over-Month** — Problem/return rate stayed nearly flat from **{m_start_lbl}** (**{r_start:.2f}%**) to **{m_end_lbl}** (**{r_end:.2f}%**, change **{sign_s}{delta:.2f}%**)."
                        if lang == "english" else
                        f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ℹ️ **लगभग समान स्तर** — **{m_start_lbl}** (**{r_start:.2f}%**) से **{m_end_lbl}** (**{r_end:.2f}%**) में रिटर्न/नुकसान दर लगभग बराबर रही (**{sign_s}{delta:.2f}%** मामूली अंतर)।"
                    )
                if delta > 0:
                    return (
                        f"\n\n🩺 **Business-Doctor Verdict:** ⚠️ **Rate Increased** — Problem/return rate rose from **{m_start_lbl}** (**{r_start:.2f}%**) to **{m_end_lbl}** (**{r_end:.2f}%**, **{sign_s}{delta:.2f}%** increase)."
                        if lang == "english" else
                        f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ⚠️ **रिटर्न/नुकसान बढ़ा है** — **{m_start_lbl}** (**{r_start:.2f}%**) की तुलना में **{m_end_lbl}** में दर बढ़कर **{r_end:.2f}%** हो गई (**{sign_s}{delta:.2f}%** बढ़ोतरी)।"
                    )
                return (
                    f"\n\n🩺 **Business-Doctor Verdict:** ✅ **Rate Decreased (Improved)** — Problem/return rate dropped from **{m_start_lbl}** (**{r_start:.2f}%**) to **{m_end_lbl}** (**{r_end:.2f}%**, **{delta:.2f}%** improvement)."
                    if lang == "english" else
                    f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ✅ **रिटर्न/नुकसान घटा है (सुधार)** — **{m_start_lbl}** (**{r_start:.2f}%**) की तुलना में **{m_end_lbl}** में दर घटकर **{r_end:.2f}%** रह गई (**{delta:.2f}%** सुधार)।"
                )
            if "EXTRACT(MONTH" in str(grp_prefix).upper() and raw_seg_val in month_names:
                raw_seg_val = f"{month_names[raw_seg_val]} (Month {raw_seg_val})"
            elif raw_seg_val.isdigit() and grp_prefix:
                raw_seg_val = f"{str(grp_prefix).replace('_', ' ').title()}: {raw_seg_val}"
            seg_lbl = f"**{raw_seg_val}**" if seg_col else ("this filtered group" if lang == "english" else "इस फ़िल्टर किए गए हिस्से")
            if mult >= 1.25 and is_stat_significant:
                return (
                    f"\n\n🩺 **Business-Doctor Verdict:** ⚠️ **High Problem Alert** — {seg_lbl} has a **{obs_rate:.2f}%** problem rate vs **{ref_baseline:.2f}%** {ref_lbl_en} (**{mult:.2f}x higher** than normal)."
                    if lang == "english" else
                    f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ⚠️ **असामान्य खराबी (ध्यान दें)** — {seg_lbl} में नुकसान/रिटर्न **{obs_rate:.2f}%** है, जबकि {ref_lbl_hi} **{ref_baseline:.2f}%** है (**{mult:.2f}x गुना ज़्यादा**)।"
                )
            if mult <= 0.85:
                return (
                    f"\n\n🩺 **Business-Doctor Verdict:** ✅ **Healthy / Safe Zone** — {seg_lbl} is at just **{obs_rate:.2f}%**, better than the **{ref_baseline:.2f}%** {ref_lbl_en}."
                    if lang == "english" else
                    f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ✅ **सुरक्षित व स्वस्थ स्थिति** — {seg_lbl} में रिस्क मात्र **{obs_rate:.2f}%** है, जो {ref_lbl_hi} (**{ref_baseline:.2f}%**) से बेहतर है।"
                )
            return (
                f"\n\n🩺 **Business-Doctor Verdict:** ℹ️ **Normal Level** — {seg_lbl} ({obs_rate:.2f}%) is close to {ref_lbl_en} ({ref_baseline:.2f}%) with no real abnormal spike."
                if lang == "english" else
                f"\n\n🩺 **बिज़नेस-डॉक्टर निष्कर्ष:** ℹ️ **सामान्य स्तर** — {seg_lbl} ({obs_rate:.2f}%) {ref_lbl_hi} ({ref_baseline:.2f}%) के आसपास ही है, कोई असामान्य खराबी नहीं है।"
            )
        except Exception:
            return ""

    def _format_grounded_answer(
        self,
        question: str,
        df: pd.DataFrame,
        lang: str,
        active_filters: Optional[Dict[str, str]] = None,
    ) -> str:
        """Constructs an auditable, strictly grounded plain-language Business-Doctor answer."""
        flt_banner = ""
        if active_filters:
            flt_txt = " • ".join(self._humanize_filter_text(v) for v in active_filters.values())
            flt_banner = (
                f"*Filter Applied:* {flt_txt}\n\n"
                if lang == "english" else
                f"*लागू फ़िल्टर:* {flt_txt}\n\n"
            )

        if len(df) == 0:
            return (
                f"{flt_banner}**No matching orders/records found for this filter.** (Audited data returned 0 rows)."
                if lang == "english" else
                f"{flt_banner}**इस फ़िल्टर में कोई ऑर्डर/रिकॉर्ड नहीं मिला।** (Pramanit डेटा में 0 रिकॉर्ड मिले)।"
            )

        takeaway = self._build_doctor_takeaway(df, lang)

        # Single Aggregate Row
        if len(df) == 1 and len(df.columns) <= 10:
            row = df.iloc[0]
            items = []
            for col_name, val in row.items():
                label = self._friendly_col_label(col_name, lang)
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    val_str = "**0**"
                elif isinstance(val, (int, np.integer)):
                    val_str = f"**{val:,}**"
                elif isinstance(val, (float, np.floating)):
                    if "pct" in col_name.lower() or "rate" in col_name.lower():
                        val_str = f"**{val:.2f}%**"
                    elif self._is_money_column(col_name):
                        val_str = self._format_money_val(float(val))
                    elif float(val).is_integer():
                        val_str = f"**{int(val):,}**"
                    else:
                        val_str = f"**{val:,.2f}**"
                else:
                    val_str = f"**{val}**"
                items.append(f"- **{label}**: {val_str}")

            if lang == "english":
                return (
                    f"### 📊 Direct Business Answer (Audited Data)\n"
                    f"{flt_banner}"
                    f"Exact numbers from your business records:\n\n"
                    + "\n".join(items)
                    + takeaway
                )
            else:
                return (
                    f"### 📊 आपके बिज़नेस डेटा से सीधा जवाब (Pramanit Data)\n"
                    f"{flt_banner}"
                    f"आपके असली रिकॉर्ड्स के अनुसार सटीक हिसाब:\n\n"
                    + "\n".join(items)
                    + takeaway
                )

        # Multi-row Breakdown Summary (show up to 18 rows for multi-quarter / top-10 comparisons without cutting off Q3/Q4 or column 9!)
        max_bullet_rows = 18 if len(df) <= 18 else 10
        top_rows = df.head(max_bullet_rows)
        iso_sym_map = {
            "INR": ("₹", "indian"), "USD": ("$", "western"), "EUR": ("€", "western"),
            "GBP": ("£", "western"), "AED": ("AED ", "western"), "SGD": ("S$", "western"),
        }
        bullet_lines = []
        for idx_r, (_, r) in enumerate(top_rows.iterrows(), start=1):
            seg_v = str(r.get("segment", r.iloc[0]))
            if seg_v.endswith(".0") and seg_v[:-2].isdigit():
                seg_v = seg_v[:-2]
            grp_prefix = getattr(self, "_last_group_col", None) or (top_rows.columns[0] if top_rows.columns[0] != "segment" else None)
            row_sym_override, row_num_override = None, None
            if seg_v.strip().upper() in iso_sym_map:
                row_sym_override, row_num_override = iso_sym_map[seg_v.strip().upper()]
            month_names = {
                "1": "January", "2": "February", "3": "March", "4": "April", "5": "May", "6": "June",
                "7": "July", "8": "August", "9": "September", "10": "October", "11": "November", "12": "December"
            }
            if "EXTRACT(MONTH" in str(grp_prefix).upper() and seg_v in month_names:
                seg_v = f"{month_names[seg_v]} (Month {seg_v})"
            elif seg_v.isdigit() and grp_prefix:
                seg_v = f"{str(grp_prefix).replace('_', ' ').title()}: {seg_v}"
            parts = []
            for col_name in top_rows.columns:
                if col_name in ("segment", "_is_target_event") or (col_name == top_rows.columns[0] and "segment" not in top_rows.columns):
                    continue
                val = r[col_name]
                if pd.isna(val) or val is None:
                    continue
                lbl = self._friendly_col_label(col_name, lang)
                if isinstance(val, (int, np.integer)):
                    parts.append(f"{lbl}: **{int(val):,}**")
                elif isinstance(val, (float, np.floating)):
                    if "pct" in col_name.lower() or "rate" in col_name.lower():
                        parts.append(f"{lbl}: **{float(val):.2f}%**")
                    elif self._is_money_column(col_name):
                        parts.append(f"{lbl}: {self._format_money_val(float(val), sym_override=row_sym_override, numbering_override=row_num_override)}")
                    elif float(val).is_integer():
                        parts.append(f"{lbl}: **{int(val):,}**")
                    else:
                        parts.append(f"{lbl}: **{float(val):,.2f}**")
                else:
                    parts.append(f"{lbl}: **{val}**")
            bullet_lines.append(f"- **#{idx_r} {seg_v}** — " + " | ".join(parts[:14]))

        bullets_md = "\n".join(bullet_lines)
        total_rows_note = (
            f"\n\n*Showing top {len(top_rows)} of {len(df)} groups (full table below).*"
            if (len(df) > len(top_rows) and lang == "english")
            else (f"\n\n*ऊपर मुख्य {len(top_rows)} ग्रुप दिखाए गए हैं (पूरी {len(df)} लाइनों की टेबल नीचे है)।*" if len(df) > len(top_rows) else "")
        )

        if lang == "english":
            return (
                f"### 🔍 Direct Business Breakdown (Audited Data)\n"
                f"{flt_banner}"
                f"Here is the exact comparison from your records:\n\n"
                f"{bullets_md}{total_rows_note}{takeaway}"
            )
        else:
            return (
                f"### 🔍 आपके बिज़नेस डेटा से सीधा हिसाब (Pramanit Data)\n"
                f"{flt_banner}"
                f"आपके असली रिकॉर्ड्स के अनुसार मुख्य नतीजे:\n\n"
                f"{bullets_md}{total_rows_note}{takeaway}"
            )
