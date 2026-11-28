"""
=============================================================================
UNIT & INTEGRATION TESTS: V6.0 MULTI-TIER AUTONOMOUS SELF-HEALING SUPERVISOR
=============================================================================
Verifies:
1. Tier-0 zero-token deterministic repairs (.str accessor, CSV encoding/sep, KeyError).
2. Stage 4 true row-conservation catching Cartesian explosion & row drops inside sandbox loop.
3. Stuck-loop fail-fast signature detector avoiding wasted LLM retries.
4. Security invariance: Tier-0 NEVER weakens AST Security Gate.
5. Cost-smart tiered model escalation (fast Hydrogen vs reasoning Carbon Pro).
6. Post-Stage-7 Closed-Loop Logical & Structural Self-Healing (0 extra tokens).
7. OmniDimensionalLeakScanner immunity against temporal date leakage (e.g., date_received).
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from autonomous_engine.omni_leak_scanner import OmniDimensionalLeakScanner
from autonomous_engine.rate_limiter import PacedGeminiClient, get_token_usage_summary, reset_token_usage_ledger
from autonomous_engine.self_healing_supervisor import (
    audit_and_heal_logical_structural,
    classify_failure_signature,
)
from autonomous_engine.stage4_sandbox_executor import execute_with_self_healing


class _ForbiddenLlmPacer:
    """Fails the test if any LLM call is attempted when Tier-0 must solve it for 0 tokens."""

    def generate_content(self, contents, system_instruction=None, max_retries=5):
        raise AssertionError("LLM should NOT be called when Tier-0 deterministic fix handles the error!")


class _MockEscalationPacer:
    """Records tiered escalation calls cleanly for offline deterministic testing."""

    def __init__(self, responses: List[str]):
        self.responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def generate_content_tiered(self, contents, system_instruction=None, tier="fast", max_retries=5):
        self.calls.append({"tier": tier, "prompt_snippet": str(contents)[:400]})
        idx = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[idx]


def test_tier0_zero_token_heals_str_accessor_keyerror_and_csv_encoding(tmp_path: Path):
    reset_token_usage_ledger()

    # 1) .str accessor crash on int column
    raw_dir = tmp_path / "raw1"
    out_dir1 = tmp_path / "out1"
    raw_dir.mkdir()
    out_dir1.mkdir()
    pd.DataFrame({"id": [1, 2, 3], "code": [101, 202, 303], "status": ["Ok", "Fail", "Ok"]}).to_csv(
        raw_dir / "data.csv", index=False
    )
    sc1 = tmp_path / "etl_str.py"
    sc1.write_text(
        f"""import pandas as pd
from pathlib import Path
df = pd.read_csv({repr((raw_dir / 'data.csv').as_posix())})
df['code'] = df['code'].str.strip()
df.to_parquet({repr((out_dir1 / 'bi_ready_fact.parquet').as_posix())}, index=False)
""",
        encoding="utf-8",
    )
    ok1 = execute_with_self_healing(
        str(sc1),
        max_retries=2,
        timeout_sec=20,
        output_dir=str(out_dir1),
        pacer=_ForbiddenLlmPacer(),
        expected_initial_rows=3,
    )
    assert ok1 is True
    assert (out_dir1 / "bi_ready_fact.parquet").exists()
    rep1 = json.loads((out_dir1 / "self_healing_report.json").read_text(encoding="utf-8"))
    assert rep1["stage4_status"] == "SELF_HEALED"
    assert rep1["runtime_healing_events"][0]["tier"] == "tier0_deterministic"
    assert rep1["runtime_healing_events"][0]["tokens_spent"] == 0

    # 2) KeyError on trailing whitespace column resolved via topology_path (0 tokens)
    out_dir2 = tmp_path / "out2"
    out_dir2.mkdir()
    pd.DataFrame({"id": [1, 2], "order_status ": ["Ok", "Cancelled"]}).to_csv(raw_dir / "ws.csv", index=False)
    topo2 = tmp_path / "topo2.json"
    topo2.write_text(
        json.dumps({"tables": {"ws": {"columns": ["id", "order_status "], "estimated_rows": 2}}}),
        encoding="utf-8",
    )
    sc2 = tmp_path / "etl_key.py"
    sc2.write_text(
        f"""import pandas as pd
df = pd.read_csv({repr((raw_dir / 'ws.csv').as_posix())})
df['flag'] = (df['order_status'] == 'Cancelled').astype(int)
df.to_parquet({repr((out_dir2 / 'bi_ready_fact.parquet').as_posix())}, index=False)
""",
        encoding="utf-8",
    )
    ok2 = execute_with_self_healing(
        str(sc2),
        max_retries=2,
        timeout_sec=20,
        output_dir=str(out_dir2),
        pacer=_ForbiddenLlmPacer(),
        expected_initial_rows=2,
        topology_path=str(topo2),
    )
    assert ok2 is True

    # 3) Latin-1 + semicolon CSV decoding crash healed via Tier-0 resilient CSV wrapper (0 tokens)
    out_dir3 = tmp_path / "out3"
    out_dir3.mkdir()
    latin_csv = raw_dir / "eu.csv"
    latin_csv.write_bytes("id;city;status\n1;München;Fail\n2;Zürich;Pass\n".encode("latin1"))
    sc3 = tmp_path / "etl_enc.py"
    sc3.write_text(
        f"""import pandas as pd
df = pd.read_csv({repr(latin_csv.as_posix())})
assert 'status' in df.columns
df.to_parquet({repr((out_dir3 / 'bi_ready_fact.parquet').as_posix())}, index=False)
""",
        encoding="utf-8",
    )
    ok3 = execute_with_self_healing(
        str(sc3),
        max_retries=2,
        timeout_sec=20,
        output_dir=str(out_dir3),
        pacer=_ForbiddenLlmPacer(),
        expected_initial_rows=2,
    )
    assert ok3 is True
    assert get_token_usage_summary()["total_tokens"] == 0


def test_stage4_catches_cartesian_drift_and_heals_with_true_row_count(tmp_path: Path):
    out_dir = tmp_path / "out_drift"
    out_dir.mkdir()
    bad_pq = out_dir / "bi_ready_fact.parquet"

    drifting_script = tmp_path / "drift_etl.py"
    drifting_script.write_text(
        f"""import pandas as pd
# Buggy 2x Cartesian blowup on 50 expected rows -> writes 100 rows
df = pd.DataFrame({{'id': list(range(100)), 'status': ['Ok'] * 100}})
df.to_parquet({repr(bad_pq.as_posix())}, index=False)
""",
        encoding="utf-8",
    )
    fixed_script_code = f"""```python
import pandas as pd
df = pd.DataFrame({{'id': list(range(50)), 'status': ['Ok' if i % 5 else 'Fail' for i in range(50)]}})
df.to_parquet({repr(bad_pq.as_posix())}, index=False)
```"""
    pacer = _MockEscalationPacer([fixed_script_code])
    ok = execute_with_self_healing(
        str(drifting_script),
        max_retries=3,
        timeout_sec=20,
        output_dir=str(out_dir),
        pacer=pacer,
        expected_initial_rows=50,
    )
    assert ok is True
    assert len(pacer.calls) == 1
    assert pacer.calls[0]["tier"] == "fast"
    assert "Expected Initial Fact Rows: 50" in pacer.calls[0]["prompt_snippet"] or "ROW_DRIFT_CARTESIAN" in pacer.calls[0]["prompt_snippet"]
    assert len(pd.read_parquet(bad_pq)) == 50


def test_stuck_loop_breaker_aborts_redundant_retries(tmp_path: Path):
    out_dir = tmp_path / "out_stuck"
    out_dir.mkdir()
    sc = tmp_path / "stuck_etl.py"
    failing_code = "import math\nraise ValueError('unrecoverable custom business assertion')\n"
    sc.write_text(failing_code, encoding="utf-8")

    # LLM returns the exact same broken logic -> stuck signature repeats -> fail fast after 1 LLM call (not 3)
    pacer = _MockEscalationPacer([f"```python\n{failing_code}\n```", f"```python\n{failing_code}\n```"])
    ok = execute_with_self_healing(
        str(sc),
        max_retries=4,
        timeout_sec=20,
        output_dir=str(out_dir),
        pacer=pacer,
    )
    assert ok is False
    assert len(pacer.calls) == 1
    rep = json.loads((out_dir / "self_healing_report.json").read_text(encoding="utf-8"))
    assert any(ev.get("tier") == "stuck_loop_breaker" for ev in rep["runtime_healing_events"])


def test_ast_security_gate_never_weakened_by_tier0(tmp_path: Path):
    out_dir = tmp_path / "out_sec"
    out_dir.mkdir()
    sc = tmp_path / "sec_etl.py"
    sc.write_text("import subprocess\nprint('should never run')\n", encoding="utf-8")
    pacer = _MockEscalationPacer(["```python\nimport subprocess\nprint('still blocked')\n```"])
    ok = execute_with_self_healing(str(sc), max_retries=2, timeout_sec=10, output_dir=str(out_dir), pacer=pacer)
    assert ok is False


def test_tiered_model_escalation_routes_pro_on_reasoning(monkeypatch):
    pacer = PacedGeminiClient(max_calls_per_minute=28, quiet=True)
    seen_models = []

    def _spy_generate_content(contents, system_instruction=None, max_retries=5):
        seen_models.append(getattr(pacer, "_override_models", None))
        return "ok"

    monkeypatch.setattr(pacer, "generate_content", _spy_generate_content)
    assert pacer.generate_content_tiered("fix1", tier="fast") == "ok"
    assert pacer.generate_content_tiered("fix2", tier="reasoning") == "ok"
    assert seen_models[0] is None
    assert "gemini-2.5-pro" in (seen_models[1] or [])
    assert not hasattr(pacer, "_override_models")


def test_logical_structural_closed_loop_healer_repairs_poisoned_target(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    raw_dir.mkdir()
    out_dir.mkdir()
    cache_dir.mkdir()

    df = pd.DataFrame({
        "case_id": [f"C-{i}" for i in range(60)],
        "patient_age": [25 + (i % 50) for i in range(60)],
        "department": ["Cardio" if i % 2 == 0 else "Ortho" for i in range(60)],
        "event_severity": ["Injury" if i % 4 == 0 else "Malfunction" for i in range(60)],
    })
    df.to_csv(raw_dir / "clinical.csv", index=False)
    df.to_parquet(out_dir / "bi_ready_fact.parquet", index=False)

    bp_path = tmp_path / "bp.json"
    poisoned_bp = {
        "fact_table": "clinical",
        "target_metric": "patient_age",
        "primary_id_column": "case_id",
    }
    bp_path.write_text(json.dumps(poisoned_bp), encoding="utf-8")
    (out_dir / "execution_blueprint.json").write_text(json.dumps(poisoned_bp), encoding="utf-8")
    # Simulate poisoned manifest & non-monetary violation
    (out_dir / "semantic_metrics_manifest.json").write_text(
        json.dumps({
            "target_outcome": {"column_name": "patient_age", "total_adverse_events": 20},
            "financial_exposure": {"has_monetary_ledger": True, "unit_symbol": "$"},
        }),
        encoding="utf-8",
    )

    rebuilt = []

    def _mock_resynth(o_dir: str, _bp: str):
        rebuilt.append(o_dir)
        new_bp = json.loads((Path(o_dir) / "execution_blueprint.json").read_text(encoding="utf-8"))
        (Path(o_dir) / "semantic_metrics_manifest.json").write_text(
            json.dumps({
                "target_outcome": {"column_name": new_bp["target_metric"], "total_adverse_events": 15},
                "financial_exposure": {"has_monetary_ledger": False, "unit_symbol": "events"},
            }),
            encoding="utf-8",
        )

    def _mock_audit(o_dir: str, _bp: str | None = None):
        return {"grounding_confidence": "100.0% VERIFIED TRUTH", "physics_invariant_violations": []}

    res = audit_and_heal_logical_structural(
        data_dir=str(raw_dir),
        out_dir=str(out_dir),
        cache_dir=str(cache_dir),
        blueprint_path=str(bp_path),
        mode="ai",
        expected_initial_rows=60,
        expected_pk="case_id",
        run_anti_hallucination_fn=_mock_audit,
        resynthesize_downstream_fn=_mock_resynth,
        audit_res={"grounding_confidence": "100.0% VERIFIED TRUTH", "physics_invariant_violations": []},
    )
    assert res["healed"] is True
    assert len(rebuilt) == 1
    healed_bp = json.loads((out_dir / "execution_blueprint.json").read_text(encoding="utf-8"))
    assert healed_bp["target_metric"] == "event_severity"


def test_omni_leak_scanner_excludes_temporal_dates():
    dates = ["2016-04-01", "2016-05-01", "2016-06-01"] * 40
    facs = (["Alpha", "Beta", "Gamma", "Delta"] * 30)[:120]
    events = [
        "Injury" if (f == "Alpha" and i % 2 == 0) or (f != "Alpha" and i % 10 == 0) else "Malfunction"
        for i, f in enumerate(facs)
    ]
    df = pd.DataFrame({
        "date_received": dates,
        "facility": facs,
        "event_type": events,
    })
    scanner = OmniDimensionalLeakScanner(df)
    dims = scanner._discover_operational_dimensions()
    assert "date_received" not in dims
    assert "facility" in dims
    sig = classify_failure_signature("Can only use .str accessor with string values!")
    assert sig["category"] == "STR_ACCESSOR" and sig["recoverable_tier0"] is True
