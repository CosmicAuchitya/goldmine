"""10+ Year Real Company Zero-Cheating Blind Middle-Window Audit Suite (Wells Fargo)."""
from pathlib import Path
from fastapi.testclient import TestClient

from autonomous_engine.api_server import app
from autonomous_engine.ten_year_blind_audit import run_ten_year_blind_audit


def test_ten_year_wellsfargo_blind_middle_window_zero_cheating():
    """
    Feeds ONLY an anonymized middle historical slice (FY2013-FY2015 settled loans,
    stripped of bank identity, borrower PII, and all post-event SBA fields including
    TermInMonths and GrossChargeOffAmount) with ZERO overrides to DataX-Ray, then
    audits predictions and top fixes strictly on 6 unseen sealed years (FY2016-FY2021).
    """
    ws = Path(__file__).resolve().parents[1]
    client = TestClient(app)
    res = run_ten_year_blind_audit(
        client_or_url=client,
        workspace_root=ws,
        write_hindi_report=True,
    )
    summary = res["summary"]
    checks = {c["gate"]: c for c in res["checks"]}
    sf = res["sealed_future_evaluation"]

    assert summary["checks_total"] == 9
    assert checks["1_Blind_ZeroHint_AutoDetect"]["pass"] is True
    assert checks["2_Blind_DuckDB_GroundTruth"]["pass"] is True
    assert checks["4_Blind_RootCause_Discovery"]["pass"] is True
    assert checks["5_BlindSolution_Proven_In_SealedFuture"]["pass"] is True
    assert checks["9_AskAI_And_Hindi_Live"]["pass"] is True
    assert sf["risk_lift_x"] >= 3.0
    assert sf["fisher_p_value"] < 1e-10
    assert summary["overall_accuracy_pct"] >= 80.0
    assert (ws / "TEN_YEAR_COMPANY_BLIND_AUDIT_HI.md").exists()
