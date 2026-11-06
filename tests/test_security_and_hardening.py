"""
Adversarial Security, Privacy, Concurrency & Audit Regression Suite
Covers all 10 hardened areas + side-effect regression checks across real benchmarks.
"""

import io
import os
import json
import zipfile
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from autonomous_engine.common_utils import (
    validate_etl_ast_security,
    build_sanitized_subprocess_env,
    sanitize_untrusted_metadata_token,
    quote_sql_ident,
    resolve_safe_workspace_path,
)
from autonomous_engine.pii_scrubber import (
    scrub_text,
    scrub_schema_payload,
    is_sensitive_column_name,
)
from autonomous_engine.stage2_ai_blueprint import validate_and_sanitize_blueprint
from autonomous_engine.stage4_sandbox_executor import execute_with_self_healing
from autonomous_engine.run_manager import RunManager
from autonomous_engine.kaggle_harvester import safe_extract_zip
from autonomous_engine.duckdb_engine import DuckDBRelationalEngine
from autonomous_engine.target_resolver import resolve_canonical_target_and_cost
from autonomous_engine.stage5_bi_synthesizer import synthesize_deliverables
from autonomous_engine.stage6_semantic_viz_synthesizer import (
    build_dax_target_filter,
    build_sql_target_filter,
    synthesize_semantic_and_viz,
)
from autonomous_engine.anti_hallucination_guard import run_anti_hallucination_audit


class TestASTSecurityAndSubprocessSandbox:
    def test_blocks_forbidden_imports_calls_and_escapes(self):
        malicious_snippets = [
            "import subprocess\nsubprocess.run(['whoami'])",
            "from urllib import request\nrequest.urlopen('https://evil.example')",
            "import requests\nrequests.get('https://evil.example')",
            "import socket\ns = socket.socket()",
            "import pickle\npickle.loads(b'x')",
            "import os\nos.system('calc.exe')",
            "import shutil\nshutil.rmtree('/tmp/data')",
            "x = eval('2 + 2')",
            "cls = ().__class__.__base__.__subclasses__()",
            "secret = open('.env').read()",
        ]
        for snippet in malicious_snippets:
            violations = validate_etl_ast_security(snippet)
            assert len(violations) >= 1, f"Expected AST gate to block: {snippet}"

    def test_allows_legitimate_etl_and_historical_benchmark_scripts(self):
        valid_etl = """
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

df = pd.DataFrame({'id': ['1', '2'], 'val': [10.0, 20.0]})
df['ratio'] = np.where(df['val'] > 0, df['val'] / 10.0, 0.0)
"""
        assert validate_etl_ast_security(valid_etl) == []

        # Regression check: ensure real generated ETL scripts in workspace pass with 0 false positives
        repo_root = Path(__file__).resolve().parent.parent
        checked = 0
        for script_path in (repo_root / "kaggle_benchmarks").glob("*/output/dynamic_etl_runner.py"):
            code = script_path.read_text(encoding="utf-8")
            assert validate_etl_ast_security(code) == [], f"False positive on {script_path}"
            checked += 1
        # Even if output scripts aren't stored in every folder, check autonomous_engine/dynamic_etl_runner.py if present
        root_etl = repo_root / "autonomous_engine" / "dynamic_etl_runner.py"
        if root_etl.exists():
            assert validate_etl_ast_security(root_etl.read_text(encoding="utf-8")) == []

    def test_sanitized_subprocess_env_strips_all_credentials(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFakeSecretKey12345678901234567890")
        monkeypatch.setenv("GEMINI_API_KEY_SECONDARY", "AIzaSyFakeSecondaryKey123456789012345")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-supersecret123456789012345")
        monkeypatch.setenv("KAGGLE_KEY", "kaggle_secret_999")
        monkeypatch.setenv("SAFE_CUSTOM_VAR", "hello_world")

        clean_env = build_sanitized_subprocess_env()
        assert "GEMINI_API_KEY" not in clean_env
        assert "GEMINI_API_KEY_SECONDARY" not in clean_env
        assert "OPENROUTER_API_KEY" not in clean_env
        assert "KAGGLE_KEY" not in clean_env
        assert clean_env.get("SAFE_CUSTOM_VAR") == "hello_world"
        assert clean_env.get("PYTHONIOENCODING") == "utf-8"

    def test_stage4_blocks_malicious_script_before_execution(self, tmp_path):
        marker = tmp_path / "pwned.txt"
        bad_script = tmp_path / "evil_etl.py"
        bad_script.write_text(
            f"import subprocess\nfrom pathlib import Path\nPath({repr(marker.as_posix())}).write_text('pwned')\n",
            encoding="utf-8",
        )
        res = execute_with_self_healing(str(bad_script), max_retries=1, timeout_sec=10, output_dir=str(tmp_path))
        assert res is False
        assert not marker.exists(), "Malicious script must be blocked BEFORE subprocess launch!"


class TestPromptInjectionAndPIIScrubbing:
    def test_blueprint_validator_neutralizes_prompt_injection(self):
        topology = {
            "dataset_name": "customer_service",
            "tables": {
                "tickets": {
                    "columns": ["Ticket_ID", "CSAT Score", "Order_Amount", "Category"],
                    "estimated_rows": 5000,
                    "recommended_primary_key": "Ticket_ID",
                }
            },
        }
        poisoned_bp = {
            "project_title": "Normal Title ```python import os ``` <|im_start|>",
            "fact_table": "non_existent_table; DROP TABLE x",
            "primary_id_column": "injected_pk'); os.system('whoami')",
            "target_metric": "status'); import subprocess; subprocess.run(['calc']) #",
        }
        clean_bp = validate_and_sanitize_blueprint(poisoned_bp, topology)
        assert clean_bp["fact_table"] == "tickets"
        assert clean_bp["primary_id_column"] == "Ticket_ID"
        assert clean_bp["target_metric"] == "CSAT Score"
        assert "```" not in clean_bp["project_title"]
        assert "<|" not in clean_bp["project_title"]

        # Ensure legitimate physical column with spaces is preserved
        valid_bp = {
            "project_title": "Service Analytics",
            "fact_table": "tickets",
            "primary_id_column": "ticket_id",
            "target_metric": "csat score",
        }
        clean_valid = validate_and_sanitize_blueprint(valid_bp, topology)
        assert clean_valid["primary_id_column"] == "Ticket_ID"
        assert clean_valid["target_metric"] == "CSAT Score"

    def test_pii_scrubber_multilingual_and_no_false_positives(self):
        # Must catch multilingual person names, remarks, and secrets
        assert is_sensitive_column_name("NomeCliente") is True
        assert is_sensitive_column_name("customer_name") is True
        assert is_sensitive_column_name("Nachname") is True
        assert is_sensitive_column_name("CPF") is True
        assert is_sensitive_column_name("cell_phone") is True
        assert is_sensitive_column_name("Customer_Remarks") is True

        # Must NOT falsely flag operational columns ('cell' in cancellation, 'name' in product_name)
        assert is_sensitive_column_name("cancellation") is False
        assert is_sensitive_column_name("excellent_score") is False
        assert is_sensitive_column_name("product_name") is False
        assert is_sensitive_column_name("department_name") is False
        assert is_sensitive_column_name("AirportFrom") is False

        payload = {
            "columns": [
                {"name": "NomeCliente", "sample_values": ["João Silva", "Maria Souza"]},
                {"name": "cancellation", "sample_values": ["Yes", "No"]},
                {"name": "ticket_note", "sample_values": ["Customer John called from +1-555-234-5678 asking for a full refund immediately"]},
            ]
        }
        scrubbed = scrub_schema_payload(payload)
        assert scrubbed["columns"][0]["sample_values"] == ["[MASKED_NOMECLIENTE]", "[MASKED_NOMECLIENTE]"]
        assert scrubbed["columns"][1]["sample_values"] == ["Yes", "No"]
        assert scrubbed["columns"][2]["sample_values"][0].startswith("[MASKED_FREETEXT_LEN_")

        leak = scrub_text("Key AIzaSyB123456789012345678901234567890 failed for user@corp.io")
        assert "AIzaSy" not in leak
        assert "user@corp.io" not in leak


class TestZipSlipPathTraversalAndConcurrency:
    def test_safe_extract_zip_blocks_traversal_and_allows_clean_zip(self, tmp_path):
        evil_zip = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil_zip, "w") as zf:
            zf.writestr("../../escaped_evil.txt", "malicious")

        with pytest.raises(ValueError, match="Zip-Slip"):
            safe_extract_zip(evil_zip, tmp_path / "extract_dest")
        assert not (tmp_path.parent / "escaped_evil.txt").exists()

        good_zip = tmp_path / "good.zip"
        with zipfile.ZipFile(good_zip, "w") as zf:
            zf.writestr("subdir/data.csv", "id,val\n1,10\n")
        dest = tmp_path / "clean_dest"
        safe_extract_zip(good_zip, dest)
        assert (dest / "subdir" / "data.csv").exists()

    def test_resolve_safe_workspace_path_blocks_escape(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        inside = resolve_safe_workspace_path("benchmarks/data", ws)
        assert inside.is_relative_to(ws.resolve())

        with pytest.raises(ValueError, match="Security Violation"):
            resolve_safe_workspace_path("../../outside_secret", ws)

    def test_run_manager_unique_concurrent_ids(self, tmp_path):
        r1 = RunManager(dataset_name="telecom_users", base_runs_dir=str(tmp_path / "runs"))
        r2 = RunManager(dataset_name="telecom_users", base_runs_dir=str(tmp_path / "runs"))
        assert r1.run_id != r2.run_id
        assert r1.artifacts_dir != r2.artifacts_dir

    def test_duckdb_engine_quotes_tricky_identifiers(self, tmp_path):
        eng = DuckDBRelationalEngine()
        eng.con.execute('CREATE TABLE "Order" ("Default" INTEGER, "cust""id" VARCHAR);')
        eng.con.execute('INSERT INTO "Order" VALUES (1, \'A\'), (0, \'B\');')
        assert eng.get_table_count("Order") == 2
        gate = eng.run_assertion_gates("Order", expected_initial_count=2, primary_key_col='cust"id')
        assert gate["status"] == "PASSED"
        eng.close()


class TestStage6FiltersXSSAndAntiHallucinationTeeth:
    def test_sql_and_dax_filters_match_exact_rows_across_all_target_types(self):
        df = pd.DataFrame({
            "Default": [0, 1, 0, 1, 1],
            "CSAT Score": [1, 2, 4, 5, 5],
            "Churn": ["Sim", "Nao", "Sim", "UNKNOWN", "Nao"],
            "IsFraud": [True, False, False, True, False],
        })
        con = duckdb.connect()
        con.register("fact", df)

        # 1. Reserved SQL keyword binary numeric ('Default')
        c_def = resolve_canonical_target_and_cost(df[["Default"]])
        sql_def = build_sql_target_filter(df, "Default", c_def["binary_target"])
        cnt_def = con.execute(f"SELECT SUM(CASE WHEN {sql_def} THEN 1 ELSE 0 END) FROM fact").fetchone()[0]
        assert int(cnt_def) == int(c_def["binary_target"].sum()) == 3

        # 2. Lower-tail rating ('CSAT Score')
        c_csat = resolve_canonical_target_and_cost(df[["CSAT Score"]])
        dax_csat = build_dax_target_filter(df, "CSAT Score", c_csat["binary_target"])
        sql_csat = build_sql_target_filter(df, "CSAT Score", c_csat["binary_target"])
        assert "<=" in dax_csat, f"Lower-tail rating DAX must use <=, got: {dax_csat}"
        cnt_csat = con.execute(f"SELECT SUM(CASE WHEN {sql_csat} THEN 1 ELSE 0 END) FROM fact").fetchone()[0]
        assert int(cnt_csat) == int(c_csat["binary_target"].sum())

        # 3. Multilingual string target with UNKNOWN ('Churn')
        c_churn = resolve_canonical_target_and_cost(df[["Churn"]])
        sql_churn = build_sql_target_filter(df, "Churn", c_churn["binary_target"])
        cnt_churn = con.execute(f"SELECT SUM(CASE WHEN {sql_churn} THEN 1 ELSE 0 END) FROM fact").fetchone()[0]
        assert int(cnt_churn) == int(c_churn["binary_target"].sum()) == 2
        con.close()

    def test_end_to_end_stage5_stage6_xss_and_anti_hallucination_gates(self, tmp_path):
        rng = np.random.default_rng(7)
        n = 300
        seg = rng.choice(["Month-to-month", "</script><script>alert(1)</script>", "Two year"], size=n, p=[0.5, 0.2, 0.3])
        churn = np.where(seg == "Month-to-month", rng.choice(["Sim", "Nao"], size=n, p=[0.45, 0.55]), "Nao")
        df = pd.DataFrame({
            "IDCliente": [f"C_{i:04d}" for i in range(n)],
            "TipoContrato": seg,
            "ValorMensal": rng.uniform(30.0, 120.0, size=n).round(2),
            "Tenencia": rng.integers(1, 72, size=n),
            "Churn": churn,
        })
        df.to_parquet(tmp_path / "bi_ready_fact.parquet", index=False)
        bp = {
            "project_title": "Telecom Security Audit",
            "fact_table": "telecom",
            "primary_id_column": "IDCliente",
            "target_metric": "Churn",
        }
        (tmp_path / "execution_blueprint.json").write_text(json.dumps(bp), encoding="utf-8")

        synthesize_deliverables(str(tmp_path))
        synthesize_semantic_and_viz(str(tmp_path))

        # 1. Clean output MUST pass strict anti-hallucination audit 100%
        audit_ok = run_anti_hallucination_audit(str(tmp_path), str(tmp_path / "execution_blueprint.json"))
        assert audit_ok["grounding_confidence"] == "100.0% VERIFIED TRUTH", audit_ok["physics_invariant_violations"]

        # 2. Verify HTML Dashboard neutralized </script> breakout and includes offline fallback
        html_doc = (tmp_path / "enterprise_interactive_dashboard.html").read_text(encoding="utf-8")
        assert "</script><script>alert(1)" not in html_doc
        assert "renderOfflineFallback" in html_doc

        # 3. Verify Checklist has exact dynamic counts (300 rows, 5 columns — zero stale '4,410' or '34')
        chk_doc = (tmp_path / "CERTIFICATION_AUDIT_CHECKLIST.md").read_text(encoding="utf-8")
        assert "4,410" not in chk_doc
        assert "All 5 columns physically exist" in chk_doc

        # 4. Tamper manifest SQL/count -> Anti-Hallucination Guard MUST fail!
        manifest_path = tmp_path / "semantic_metrics_manifest.json"
        orig_manifest_bytes = manifest_path.read_text(encoding="utf-8")
        m_obj = json.loads(orig_manifest_bytes)
        m_obj["target_outcome"]["total_adverse_events"] = 0
        manifest_path.write_text(json.dumps(m_obj), encoding="utf-8")

        audit_fail = run_anti_hallucination_audit(str(tmp_path), str(tmp_path / "execution_blueprint.json"))
        assert audit_fail["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        assert any("Zero-Event Target Collapse" in v for v in audit_fail["physics_invariant_violations"])

        # 5. Restore count but inject broken '= 1' SQL formula on string target -> Guard MUST fail!
        m_obj2 = json.loads(orig_manifest_bytes)
        m_obj2["certified_metrics"][1]["sql_formula"] = "SUM(CASE WHEN Churn = 1 THEN 1 ELSE 0 END)"
        manifest_path.write_text(json.dumps(m_obj2), encoding="utf-8")
        audit_sql_fail = run_anti_hallucination_audit(str(tmp_path), str(tmp_path / "execution_blueprint.json"))
        assert audit_sql_fail["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        assert any("Manifest SQL Formula" in v for v in audit_sql_fail["physics_invariant_violations"])

        # 6. Restore manifest, tamper checklist column count ('All 34 columns') -> Guard MUST fail!
        manifest_path.write_text(orig_manifest_bytes, encoding="utf-8")
        (tmp_path / "CERTIFICATION_AUDIT_CHECKLIST.md").write_text(
            chk_doc.replace("All 5 columns physically exist", "All 34 columns physically exist"),
            encoding="utf-8",
        )
        audit_chk_fail = run_anti_hallucination_audit(str(tmp_path), str(tmp_path / "execution_blueprint.json"))
        assert audit_chk_fail["grounding_confidence"] != "100.0% VERIFIED TRUTH"
        assert any("Certification Checklist column mismatch" in v for v in audit_chk_fail["physics_invariant_violations"])
