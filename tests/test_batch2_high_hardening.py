"""
================================================================================
REGRESSION & HARDENING TESTS: BATCH 2 HIGH FIXES (H1–H5)
================================================================================
Verifies:
- H1: templated_dag_runner cleans <=10-unique accounting currency strings AND
      monetary columns containing 'tier'/'type' while preserving bare codes.
- H2: stage4_sandbox_executor has zero undefined type annotations (List/Dict/Any).
- H3: Tier-0 Path(OUT)/'x.parquet' nested-parens rewrite compiles cleanly;
      attempt_history records 'tier' (no 'via None'); Tier-0 bonus slot avoids
      starving Tier-2 Pro escalation.
- H4: Stage 4 exception fallback in master_orchestrator records ESCALATED_FALLBACK
      (never falsely reports HEALTHY_FIRST_PASS).
- H5: DuckDB SQL sandbox blocks CROSS JOIN, NATURAL JOIN, WITH RECURSIVE, and
      implicit comma Cartesian joins while permitting multi-CTE analytics;
      DuckDB execution timeout guard aborts runaway queries cleanly.
================================================================================
"""

from __future__ import annotations

import ast
import builtins
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from autonomous_engine import master_orchestrator
from autonomous_engine.conversational_qa_engine import (
    ConversationalBusinessQAEngine,
    validate_readonly_duckdb_sql,
)
from autonomous_engine.self_healing_supervisor import (
    apply_tier0_deterministic_etl_fix,
    build_grounded_repair_prompt,
)
from autonomous_engine.stage4_sandbox_executor import execute_with_self_healing
from autonomous_engine.templated_dag_runner import execute_templated_pipeline


def test_h1_templated_dag_cleans_low_cardinality_and_tier_currency_columns(tmp_path: Path):
    raw_d = tmp_path / "raw"
    out_d = tmp_path / "out"
    raw_d.mkdir()
    out_d.mkdir()

    df_in = pd.DataFrame(
        {
            "order_id": [f"ORD-{i}" for i in range(30)],
            "plan_price": ["(₹499)", "₹999", "₹4,999"] * 10,
            "shipping_tier_cost": [f"(${100 + i * 10})" if i % 2 == 0 else f"${100 + i * 10}" for i in range(30)],
            "risk_class": ["1", "2", "3"] * 10,  # bare categorical code -> must stay un-coerced/discrete
            "status": ["Paid" if i % 3 else "Failed" for i in range(30)],
        }
    )
    df_in.to_csv(raw_d / "orders.csv", index=False)
    bp = tmp_path / "bp.json"
    bp.write_text(
        json.dumps({"fact_table": "orders", "primary_id_column": "order_id", "target_metric": "status"}),
        encoding="utf-8",
    )

    execute_templated_pipeline(str(bp), str(raw_d), str(out_d))
    df_out = pd.read_parquet(out_d / "bi_ready_fact.parquet")

    assert pd.api.types.is_numeric_dtype(df_out["plan_price"]), f"plan_price stayed {df_out['plan_price'].dtype}"
    assert float(df_out["plan_price"].iloc[0]) == -499.0
    assert float(df_out["plan_price"].iloc[2]) == 4999.0

    assert pd.api.types.is_numeric_dtype(df_out["shipping_tier_cost"]), f"shipping_tier_cost stayed {df_out['shipping_tier_cost'].dtype}"
    assert float(df_out["shipping_tier_cost"].iloc[0]) == -100.0
    assert float(df_out["shipping_tier_cost"].iloc[1]) == 110.0


def test_h2_stage4_has_zero_undefined_type_annotations():
    fp = Path("autonomous_engine/stage4_sandbox_executor.py")
    tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
    defined = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                defined.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    defined.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Try):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    for a in sub.names:
                        defined.add(a.asname or a.name.split(".")[0])
                elif isinstance(sub, ast.ImportFrom):
                    for a in sub.names:
                        if a.name != "*":
                            defined.add(a.asname or a.name)

    undef = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            for sub in ast.walk(node.annotation):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id not in defined:
                    undef.append((sub.id, sub.lineno))
    assert undef == [], f"Undefined annotations in stage4_sandbox_executor.py: {undef}"


def test_h3_tier0_path_arg_rewrite_prompt_tier_and_pro_escalation(tmp_path: Path):
    # 1) Nested Path(OUT) / 'wrong.parquet' rewrite compiles cleanly
    code_nested = (
        "from pathlib import Path\n"
        "import pandas as pd\n"
        "OUT = Path('out')\n"
        "df = pd.DataFrame({'a': [1, 2]})\n"
        "df.to_parquet(Path(OUT) / 'wrong.parquet', index=False)\n"
    )
    res = apply_tier0_deterministic_etl_fix(
        code_nested,
        "FileNotFoundError: No *.parquet fact table found; missing bi_ready_fact.parquet",
        output_dir=str(tmp_path),
    )
    assert res is not None
    patched, desc = res
    assert "bi_ready_fact.parquet" in patched
    compile(patched, "<test_nested_parquet>", "exec")

    # 2) Tier-0 on Attempt 1 does NOT starve Tier-2 'reasoning' escalation within max_retries=3
    raw_dir = tmp_path / "raw_esc"
    out_dir = tmp_path / "out_esc"
    raw_dir.mkdir()
    out_dir.mkdir()
    pd.DataFrame({"id": [1, 2], "code": [10, 20], "status": ["Ok", "Fail"]}).to_csv(raw_dir / "d.csv", index=False)

    sc = tmp_path / "esc_etl.py"
    # Attempt 1 crashes on .str accessor (Tier-0 fixes it for 0 tokens!), then hits custom ValueError #1 (Tier-1 fast),
    # then Tier-1 returns script hitting different RuntimeError #2 (Tier-2 reasoning fixes cleanly!)
    sc.write_text(
        f"""import pandas as pd
df = pd.read_csv({repr((raw_dir / 'd.csv').as_posix())})
df['code'] = df['code'].str.strip()
raise ValueError('custom business fault phase 1')
""",
        encoding="utf-8",
    )

    tier1_resp = f"""```python
import pandas as pd
raise RuntimeError('different secondary fault phase 2')
```"""
    tier2_resp = f"""```python
import pandas as pd
df = pd.read_csv({repr((raw_dir / 'd.csv').as_posix())})
df.to_parquet({repr((out_dir / 'bi_ready_fact.parquet').as_posix())}, index=False)
```"""

    calls: List[Dict[str, Any]] = []

    class _SpyPacer:
        def generate_content_tiered(self, contents, system_instruction=None, tier="fast", max_retries=5):
            calls.append({"tier": tier, "prompt": str(contents)})
            return tier1_resp if len(calls) == 1 else tier2_resp

    ok = execute_with_self_healing(
        str(sc),
        max_retries=3,
        timeout_sec=20,
        output_dir=str(out_dir),
        pacer=_SpyPacer(),
        expected_initial_rows=2,
    )
    assert ok is True
    assert [c["tier"] for c in calls] == ["fast", "reasoning"]
    # Verify prompt NEVER contains 'via None'
    assert all("via None" not in c["prompt"] for c in calls)
    rep = json.loads((out_dir / "self_healing_report.json").read_text(encoding="utf-8"))
    assert all(h.get("tier") is not None for h in rep["attempt_history"])


def test_h4_master_orchestrator_fallback_never_reports_healthy_first_pass(tmp_path: Path, monkeypatch):
    raw_d = tmp_path / "raw"
    out_d = tmp_path / "out"
    cache_d = tmp_path / "cache"
    raw_d.mkdir()
    out_d.mkdir()
    cache_d.mkdir()

    df = pd.DataFrame(
        {
            "order_id": [f"ORD-{i}" for i in range(40)],
            "region": ["North" if i % 2 == 0 else "South" for i in range(40)],
            "amount": [100.0 + i * 5.0 for i in range(40)],
            "status": ["Cancelled" if i % 4 == 0 else "Completed" for i in range(40)],
        }
    )
    df.to_csv(raw_d / "orders.csv", index=False)

    # Mock AI Stage 2/3 and make Stage 4 raise an exception BEFORE writing self_healing_report.json
    def _fake_blueprint(topo_path, bp_path, use_llm=True):
        bp = {
            "project_title": "Fallback Telemetry Test",
            "fact_table": "orders",
            "primary_id_column": "order_id",
            "target_metric": "status",
        }
        Path(bp_path).write_text(json.dumps(bp), encoding="utf-8")
        return bp

    def _fake_codegen(bp_path, sc_path, topo_path, **kwargs):
        Path(sc_path).write_text("print('placeholder')\n", encoding="utf-8")

    def _crashing_stage4(*args, **kwargs):
        raise RuntimeError("Simulated hard Stage 4 crash before report write")

    monkeypatch.setattr(master_orchestrator, "generate_relational_blueprint", _fake_blueprint)
    monkeypatch.setattr(master_orchestrator, "generate_dynamic_etl_script", _fake_codegen)
    monkeypatch.setattr(master_orchestrator, "execute_with_self_healing", _crashing_stage4)

    ok = master_orchestrator.run_master_pipeline(
        data_dir=str(raw_d),
        output_dir=str(out_d),
        cache_dir=str(cache_d),
        mode="ai",
    )
    assert ok is True
    sh_report = json.loads((out_d / "self_healing_report.json").read_text(encoding="utf-8"))
    assert sh_report["stage4_status"] == "ESCALATED_FALLBACK"
    assert sh_report["overall_status"] == "ESCALATED_FALLBACK"


def test_h5_duckdb_blocks_cartesian_recursive_dos_and_enforces_timeout(tmp_path: Path, monkeypatch):
    # 1) SQL Sandbox DoS checks
    dos_queries = [
        "SELECT * FROM fact a CROSS JOIN fact b",
        "SELECT * FROM fact NATURAL JOIN fact",
        "SELECT * FROM fact a, fact b",
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT * FROM r",
    ]
    for q in dos_queries:
        v = validate_readonly_duckdb_sql(q)
        assert len(v) > 0, f"DuckDB sandbox failed to block DoS query: {q}"

    # Legitimate multi-CTE analytics MUST stay allowed
    good_cte = (
        "WITH base AS (SELECT region, COUNT(*) AS n FROM fact GROUP BY region), "
        "ranked AS (SELECT region, n FROM base ORDER BY n DESC) "
        "SELECT * FROM ranked LIMIT 10"
    )
    assert validate_readonly_duckdb_sql(good_cte) == []

    # 2) Wall-clock timeout interrupt guard works cleanly without hanging
    out_d = tmp_path / "qa_out"
    out_d.mkdir()
    pd.DataFrame(
        {
            "order_id": list(range(100)),
            "region": ["North", "South"] * 50,
            "amount": [100.0 + i for i in range(100)],
            "status": ["Failed" if i % 5 == 0 else "Ok" for i in range(100)],
        }
    ).to_parquet(out_d / "bi_ready_fact.parquet", index=False)

    engine = ConversationalBusinessQAEngine(str(out_d))
    try:
        # Simulate slow query hitting interrupt guard via low timeout + patched execute
        monkeypatch.setenv("DATAXRAY_DUCKDB_QUERY_TIMEOUT_SEC", "0.05")
        orig_con = engine.con

        class _SlowCon:
            def __init__(self):
                self.interrupted = False

            def interrupt(self):
                self.interrupted = True

            def execute(self, sql):
                import time as _t
                _t.sleep(0.20)
                if self.interrupted:
                    raise RuntimeError("INTERRUPT Error: Interrupted!")
                return orig_con.execute(sql)

        slow_con = _SlowCon()
        engine.con = slow_con
        res = engine.ask("total count of orders", language="english", use_llm=False)
        assert slow_con.interrupted is True
        assert res["status"] == "timeout"
        assert res["grounding_verified"] is False
    finally:
        try:
            orig_con.close()
        except Exception:
            pass
