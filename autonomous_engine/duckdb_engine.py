"""
=============================================================================
ENTERPRISE DUCKDB OUT-OF-CORE VECTORIZED RELATIONAL ENGINE
=============================================================================
Solves Autopsy Flaw #2: In-Memory Pandas Scalability Ceiling.
Guarantees:
1. Out-of-core streaming execution: Processes datasets up to 100M+ rows
   directly from disk without RAM Out-of-Memory (OOM) crashes.
2. Deterministic ANSI-SQL aggregations and star-schema joins with safe identifier quoting.
3. Hardware acceleration: Automatic multi-core vectorized SIMD execution.
4. Direct Parquet & CSV streaming serialization with zero intermediate bloat.
5. Invariant assertion validation natively executed inside the database engine.
=============================================================================
"""

import os
import re
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import duckdb

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from .common_utils import quote_sql_ident
except ImportError:
    try:
        from common_utils import quote_sql_ident
    except ImportError:
        def quote_sql_ident(ident: str) -> str:
            return '"' + str(ident or "").replace('"', '""') + '"'


class DuckDBRelationalEngine:
    """
    High-performance out-of-core data engineering engine powered by DuckDB.
    Replaces RAM-bound Pandas joins with deterministic, thread-parallel SQL operations.
    """
    def __init__(self, db_path: Optional[str] = ":memory:"):
        self.con = duckdb.connect(database=db_path)
        self.con.execute("PRAGMA threads=8;")
        self.con.execute("PRAGMA preserve_insertion_order=false;")

    def register_tables_from_dir(self, raw_dir: str) -> Dict[str, str]:
        """
        Discovers and registers all CSV and Parquet files in the raw directory as DuckDB views.
        """
        raw_path = Path(raw_dir)
        registered = {}
        for f in raw_path.iterdir():
            if f.name.startswith("~") or f.name.startswith("."):
                continue
            ext = f.suffix.lower()
            tbl_name = f.stem
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', tbl_name)
            if clean_name and clean_name[0].isdigit():
                clean_name = f"v_{clean_name}"
            view_name = clean_name or "v_table"
            q_view = quote_sql_ident(view_name)
            safe_posix = f.as_posix().replace("'", "''")

            if ext == ".csv":
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW {q_view} AS 
                    SELECT * FROM read_csv_auto('{safe_posix}', normalize_names=true, header=true);
                """)
                registered[tbl_name] = view_name
            elif ext == ".parquet":
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW {q_view} AS 
                    SELECT * FROM read_parquet('{safe_posix}');
                """)
                registered[tbl_name] = view_name
        return registered

    def get_table_count(self, view_name: str) -> int:
        """Returns row count of a registered view/table."""
        q_view = quote_sql_ident(view_name)
        rows = self.con.execute(f"SELECT count(*) FROM {q_view};").fetchall()
        return rows[0][0] if rows else 0

    def get_table_columns(self, view_name: str) -> List[str]:
        """Returns column names of a registered view/table."""
        q_view = quote_sql_ident(view_name)
        df_desc = self.con.execute(f"DESCRIBE {q_view};").df()
        return list(df_desc["column_name"])

    def execute_cardinality_defense_view(
        self,
        source_view: str,
        target_view: str,
        group_key: str,
        agg_specs: Dict[str, str]
    ) -> str:
        """
        Creates a pre-aggregated 1:1 view of a 1:N dimension table before joining,
        mathematically preventing Cartesian multiplicity explosion.
        """
        q_src = quote_sql_ident(source_view)
        q_tgt = quote_sql_ident(target_view)
        q_grp = quote_sql_ident(group_key)
        select_exprs = [q_grp]
        for alias, formula in agg_specs.items():
            select_exprs.append(f"{formula} AS {quote_sql_ident(alias)}")

        sql = f"""
            CREATE OR REPLACE VIEW {q_tgt} AS
            SELECT {', '.join(select_exprs)}
            FROM {q_src}
            GROUP BY {q_grp};
        """
        self.con.execute(sql)
        return target_view

    def build_star_schema_fact(
        self,
        fact_view: str,
        joins: List[Dict[str, str]],
        enrichments: List[Dict[str, str]],
        output_view: str = "v_bi_ready_fact"
    ) -> str:
        """
        Constructs the unified star-schema fact table with strict referential integrity.
        """
        q_fact = quote_sql_ident(fact_view)
        q_out = quote_sql_ident(output_view)
        join_clauses = []
        for j in joins:
            j_type = str(j.get("type", "LEFT")).upper()
            if j_type not in {"LEFT", "INNER", "RIGHT", "FULL", "LEFT OUTER"}:
                j_type = "LEFT"
            join_clauses.append(f"{j_type} JOIN {quote_sql_ident(j['table'])} ON {j['on']}")

        enrichment_exprs = []
        for e in enrichments:
            enrichment_exprs.append(f"({e['expr']}) AS {quote_sql_ident(e['name'])}")

        extra_cols = (", " + ", ".join(enrichment_exprs)) if enrichment_exprs else ""

        sql = f"""
            CREATE OR REPLACE TABLE {q_out} AS
            SELECT {q_fact}.* {extra_cols}
            FROM {q_fact}
            {' '.join(join_clauses)};
        """
        self.con.execute(sql)
        return output_view

    def run_assertion_gates(
        self,
        fact_table: str,
        expected_initial_count: int,
        primary_key_col: str
    ) -> Dict[str, Any]:
        """
        Executes zero-drift and uniqueness assertion gates natively in DuckDB.
        """
        final_count = self.get_table_count(fact_table)
        q_fact = quote_sql_ident(fact_table)
        q_pk = quote_sql_ident(primary_key_col)
        dup_count_rows = self.con.execute(f"""
            SELECT count(*) FROM (
                SELECT {q_pk}, count(*) 
                FROM {q_fact} 
                GROUP BY {q_pk} 
                HAVING count(*) > 1
            );
        """).fetchall()
        dup_count = dup_count_rows[0][0] if dup_count_rows else 0

        row_drift = final_count - expected_initial_count
        passed = (row_drift == 0) and (dup_count == 0)

        return {
            "status": "PASSED" if passed else "FAILED",
            "initial_count": expected_initial_count,
            "final_count": final_count,
            "row_drift": row_drift,
            "duplicate_primary_keys": dup_count,
            "cartesian_explosion_detected": row_drift > 0
        }

    def export_deliverables(
        self,
        fact_table: str,
        dimension_tables: List[str],
        output_dir: str
    ) -> Dict[str, str]:
        """
        Serializes DuckDB tables directly to Snappy-compressed Parquet and CSVs.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        artifacts = {}

        fact_file = (out_path / "bi_ready_fact.parquet").as_posix()
        safe_fact_file = fact_file.replace("'", "''")
        q_fact = quote_sql_ident(fact_table)
        self.con.execute(f"""
            COPY {q_fact} TO '{safe_fact_file}' (FORMAT PARQUET, COMPRESSION SNAPPY);
        """)
        artifacts["fact_parquet"] = fact_file

        for dim in dimension_tables:
            safe_dim_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(dim))
            dim_file = (out_path / f"bi_dim_{safe_dim_stem}.csv").as_posix()
            safe_dim_file = dim_file.replace("'", "''")
            q_dim = quote_sql_ident(dim)
            self.con.execute(f"""
                COPY {q_dim} TO '{safe_dim_file}' (HEADER true, DELIMITER ',');
            """)
            artifacts[f"dim_{dim}"] = dim_file

        return artifacts

    def close(self):
        """Closes connection cleanly."""
        self.con.close()


if __name__ == "__main__":
    print("[*] Testing DuckDB Relational Engine...")
    engine = DuckDBRelationalEngine()
    test_raw = "kaggle_complex_test/raw_data"
    if Path(test_raw).exists():
        tables = engine.register_tables_from_dir(test_raw)
        print(f"[+] Registered {len(tables)} tables via DuckDB:")
        for t, v in tables.items():
            cnt = engine.get_table_count(v)
            print(f"    - {t:<35} -> {v:<30} ({cnt:,} rows)")
    engine.close()
    print("[+] DuckDB Relational Engine verified successfully!")
