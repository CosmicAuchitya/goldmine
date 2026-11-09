"""
=============================================================================
DATAX-RAY HISTORICAL DRIFT RADAR & INSTITUTIONAL MEMORY ENGINE
=============================================================================
Tracks week-over-week or run-over-run trajectory for tenants:
1. Automatically discovers historical runs for the tenant.
2. Compares volume, adverse event rate, capital drag, and top bottleneck failure rates.
3. Classifies operational trajectory: IMPROVING, STABLE, or DETERIORATING.
4. Generates bilingual executive briefs in Plain English & Roman Hinglish.
5. Saves 'historical_drift_summary.json' into output directory.
=============================================================================
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

WORKSPACE_ROOT = Path.cwd().resolve()


def analyze_historical_drift(
    current_out_dir: Path,
    tenant_id: str = "default_tenant",
    current_manifest: Optional[Dict[str, Any]] = None,
    current_plain_summary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scans prior runs for the tenant to compute period-over-period drift
    and institutional memory deltas.
    """
    out_path = Path(current_out_dir).resolve()
    
    # 1. Load current run metrics
    if not current_manifest:
        mf_path = out_path / "semantic_metrics_manifest.json"
        if mf_path.exists():
            try:
                current_manifest = json.loads(mf_path.read_text(encoding="utf-8"))
            except Exception:
                current_manifest = {}
        else:
            current_manifest = {}

    t_out = current_manifest.get("target_outcome", {})
    f_exp = current_manifest.get("financial_exposure", {})
    gov = current_manifest.get("governance", {})

    curr_records = int(gov.get("audited_fact_records", 0) or 0)
    curr_events = int(t_out.get("total_adverse_events", 0) or 0)
    curr_rate = float(t_out.get("adverse_event_rate_pct", 0.0) or 0.0)
    curr_drag = float(f_exp.get("total_adverse_capital_drag", 0.0) or 0.0)
    currency_unit = str(f_exp.get("currency_unit", "$"))
    target_name = str(t_out.get("column_name", "Target"))

    # Extract current bottleneck from PLAIN_BUSINESS_SUMMARY.md if available
    curr_bottleneck_col = None
    curr_bottleneck_seg = None
    curr_bottleneck_rate = 0.0
    if not current_plain_summary:
        sum_path = out_path / "PLAIN_BUSINESS_SUMMARY.md"
        if sum_path.exists():
            try:
                current_plain_summary = sum_path.read_text(encoding="utf-8")
            except Exception:
                current_plain_summary = ""

    if current_plain_summary:
        import re
        b_m = re.search(r"Group\s+`([^`]+)`\s*=\s*\*\*'([^']+)'\*\*\s+has the highest failure rate at\s+\*\*([0-9.]+)%\*\*", current_plain_summary)
        if b_m:
            curr_bottleneck_col = b_m.group(1)
            curr_bottleneck_seg = b_m.group(2)
            curr_bottleneck_rate = float(b_m.group(3))

    # 2. Discover previous historical runs for this tenant
    safe_tenant = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(tenant_id).strip()) or "default"
    tenant_jobs_dir = WORKSPACE_ROOT / "runs" / "tenants" / safe_tenant / "jobs"
    upload_runs_dir = WORKSPACE_ROOT / "runs" / "uploads"

    candidate_runs: List[Path] = []
    if tenant_jobs_dir.exists():
        candidate_runs.extend([d / "output" for d in tenant_jobs_dir.iterdir() if d.is_dir() and (d / "output" / "semantic_metrics_manifest.json").exists()])
    elif upload_runs_dir.exists() and safe_tenant in ("default", "default_tenant", "self_serve_user"):
        candidate_runs.extend([d / "output" for d in upload_runs_dir.iterdir() if d.is_dir() and (d / "output" / "semantic_metrics_manifest.json").exists()])

    # Filter out current output directory and sort by modification time descending
    prev_runs = [p for p in candidate_runs if p.resolve() != out_path]
    prev_runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Require matching target outcome metric to ensure domain comparability
    matching_runs: List[Path] = []
    for p in prev_runs:
        try:
            m = json.loads((p / "semantic_metrics_manifest.json").read_text(encoding="utf-8"))
            if m.get("target_outcome", {}).get("column_name") == target_name:
                matching_runs.append(p)
        except Exception:
            pass
    prev_runs = matching_runs

    if not prev_runs:
        # First baseline run for this tenant
        msg_en = "First baseline run recorded. Trajectory tracking will compare future uploads against this benchmark."
        msg_hi = "Pehla baseline record ban gaya hai. Agle uploads ko is run ke sath compare karke progress dikhayi jayegi."
        drift_result = {
            "has_historical_baseline": False,
            "has_historical_comparison": False,
            "trajectory": "BASELINE",
            "trajectory_badge": "BASELINE",
            "message_en": msg_en,
            "message_hi": msg_hi,
            "executive_drift_notes": {
                "english": msg_en,
                "hinglish": msg_hi
            },
            "current_run": {
                "records": curr_records,
                "adverse_events": curr_events,
                "adverse_rate_pct": curr_rate,
                "capital_drag": curr_drag,
                "bottleneck": f"{curr_bottleneck_col}='{curr_bottleneck_seg}' ({curr_bottleneck_rate}%)" if curr_bottleneck_col else "None"
            },
            "deltas": {
                "records_delta": 0,
                "adverse_rate_delta_pp": 0.0,
                "capital_drag_delta": 0.0,
                "adverse_events_delta": 0
            }
        }
        (out_path / "historical_drift_summary.json").write_text(json.dumps(drift_result, indent=2), encoding="utf-8")
        return drift_result

    # 3. Read previous run metrics
    prev_out = prev_runs[0]
    prev_manifest = {}
    try:
        prev_manifest = json.loads((prev_out / "semantic_metrics_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        pass

    prev_tout = prev_manifest.get("target_outcome", {})
    prev_fexp = prev_manifest.get("financial_exposure", {})
    prev_gov = prev_manifest.get("governance", {})

    prev_records = int(prev_gov.get("audited_fact_records", 0) or 0)
    prev_events = int(prev_tout.get("total_adverse_events", 0) or 0)
    prev_rate = float(prev_tout.get("adverse_event_rate_pct", 0.0) or 0.0)
    prev_drag = float(prev_fexp.get("total_adverse_capital_drag", 0.0) or 0.0)

    # 4. Calculate deltas
    delta_records = curr_records - prev_records
    delta_rate_pp = round(curr_rate - prev_rate, 2)
    delta_drag = round(curr_drag - prev_drag, 2)
    delta_events = curr_events - prev_events

    # Classify trajectory
    if delta_rate_pp <= -1.0 or (delta_drag < 0 and curr_drag < prev_drag * 0.95):
        trajectory = "IMPROVING"
        traj_en = "IMPROVING (Defect rate fell)"
        traj_hi = "SUDHAR RAHA HAI (Failure rate kam hua)"
    elif delta_rate_pp >= 1.0 or (delta_drag > 0 and curr_drag > prev_drag * 1.05):
        trajectory = "DETERIORATING"
        traj_en = "DETERIORATING (Defect rate rose)"
        traj_hi = "BIGAD RAHA HAI (Failure rate badh gaya)"
    else:
        trajectory = "STABLE"
        traj_en = "STABLE (Within normal bounds)"
        traj_hi = "STABLE (Normal range mein hai)"

    drag_str_en = f"{currency_unit}{abs(delta_drag):,.2f} {'saved / reduced' if delta_drag < 0 else 'increase in risk'}" if (curr_drag > 0 or prev_drag > 0) else f"{abs(delta_events):,} {'fewer' if delta_events < 0 else 'more'} adverse events"
    drag_str_hi = f"{currency_unit}{abs(delta_drag):,.2f} {'ka bachat / reduction' if delta_drag < 0 else 'ka extra nuksan'}" if (curr_drag > 0 or prev_drag > 0) else f"{abs(delta_events):,} {'kam' if delta_events < 0 else 'zyada'} failure events"

    narrative_en = (
        f"Compared to your previous run ({prev_records:,} records), the adverse event rate shifted by "
        f"{delta_rate_pp:+.2f} percentage points (from {prev_rate:.2f}% to {curr_rate:.2f}%), with {drag_str_en}. "
        f"Your operational trajectory is **{traj_en}**."
    )
    narrative_hi = (
        f"Pichle run ({prev_records:,} records) ke mukable, failure rate mein {delta_rate_pp:+.2f} percentage points ka farak aaya hai "
        f"({prev_rate:.2f}% se badal kar {curr_rate:.2f}%), sath hi {drag_str_hi}. "
        f"Aapka business abhi **{traj_hi}** trend mein hai."
    )

    drift_result = {
        "has_historical_baseline": True,
        "has_historical_comparison": True,
        "trajectory": trajectory,
        "trajectory_badge": trajectory,
        "message_en": narrative_en,
        "message_hi": narrative_hi,
        "executive_drift_notes": {
            "english": narrative_en,
            "hinglish": narrative_hi
        },
        "current_run": {
            "records": curr_records,
            "adverse_events": curr_events,
            "adverse_rate_pct": curr_rate,
            "capital_drag": curr_drag,
            "bottleneck": f"{curr_bottleneck_col}='{curr_bottleneck_seg}' ({curr_bottleneck_rate}%)" if curr_bottleneck_col else "None"
        },
        "previous_run": {
            "records": prev_records,
            "adverse_events": prev_events,
            "adverse_rate_pct": prev_rate,
            "capital_drag": prev_drag
        },
        "deltas": {
            "records_delta": delta_records,
            "adverse_rate_delta_pp": delta_rate_pp,
            "capital_drag_delta": delta_drag,
            "adverse_events_delta": delta_events
        }
    }

    try:
        (out_path / "historical_drift_summary.json").write_text(json.dumps(drift_result, indent=2), encoding="utf-8")
    except Exception:
        pass

    return drift_result
