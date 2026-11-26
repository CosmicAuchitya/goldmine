"""Zero-Cheating Real-Time End-to-End Business Accuracy (90%-100%) & Solution Proof Suite."""
from pathlib import Path
from fastapi.testclient import TestClient

from autonomous_engine.api_server import app
from autonomous_engine.realtime_business_certification import run_realtime_business_certification


def test_realtime_business_90_to_100_accuracy_zero_cheating():
    """
    Uploads real historical corporate CSVs live via FastAPI with ZERO overrides,
    audits DuckDB ground truth + zero row drift, evaluates problem/solution performance
    strictly on SEALED FUTURE unseen data, verifies AI Boardroom, Ask AI, Hindi translation,
    and Placebo noise rejection — enforcing 90% to 100% genuine overall accuracy.
    """
    ws = Path(__file__).resolve().parents[1]
    client = TestClient(app)
    report = run_realtime_business_certification(
        client_or_url=client,
        workspace_root=ws,
        write_hindi_report=True,
    )
    summary = report["summary"]
    assert summary["checks_total"] >= 25
    assert summary["placebo_rejected"] is True
    assert summary["mean_sealed_auc"] >= 0.72
    assert summary["median_worklist_lift_x"] >= 2.0
    assert summary["overall_accuracy_pct"] >= 90.0, (
        f"Real-Time Business Certification scored {summary['overall_accuracy_pct']}% "
        f"({summary['checks_passed']}/{summary['checks_total']}): "
        f"{[c for c in report['checks'] if not c['pass']]}"
    )
    assert (ws / "REALTIME_BUSINESS_AUDIT_REPORT_HI.md").exists()
