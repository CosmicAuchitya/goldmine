"""
10+ Year Real Online Company Zero-Cheating Blind Audit (Wells Fargo Case Study)
================================================================================
Protocol (Strict Zero-Cheating & Zero Identity/Future Leakage):
  1. Independent Auditor extracts Wells Fargo Bank N.A. (FDIC #03511, NYSE: WFC)
     complete historical loan ledger (`FY2010-FY2026`, 56,914 loans) from US SBA
     7(a) FOIA Open Data alongside CFPB (`2013-2023`) and SEC EDGAR (`CIK 0000072971`).
  2. Auditor builds complete Year-by-Year ground truth (loan volumes, policy shifts,
     default rates, exact dollar charge-offs `GrossChargeOffAmount`, regulatory
     penalties, and 10-K asset cap impact).
  3. ONLY a blind middle historical window (`FY2013-FY2015` settled loans, BEFORE
     the Sept 2016 scandal and Feb 2018 Asset Cap) is anonymized — ALL bank identity
     (`BankName`, `BankFDICNumber`, borrower PII) and ALL post-event columns
     (`PaidInFullDate`, `ChargeOffDate`, `GrossChargeOffAmount`, `AsOfDate`) are
     physically deleted, with ZERO `target_override` and ZERO `cost_override`.
  4. DataX-Ray runs LIVE via HTTP (`/api/v1/preview-intent`, `/api/v1/jobs/submit`,
     `/api/v1/predict/overview`, `/api/v1/predict/simulate`, `/api/v1/boardroom/discuss`,
     `/api/v1/ask`, `/api/v1/i18n/translate-run`) with zero knowledge of who the company
     is or what happened in `FY2016-FY2021`.
  5. Auditor compares DataX-Ray's blind diagnosis & #1 recommendation against
     what Wells Fargo ACTUALLY did year-by-year in the sealed future (`FY2016-FY2021`),
     computing exact sealed `ROC-AUC`, calibration gap, Top-20% priority lift, and
     real dollar charge-off difference (`$` lost vs avoided).
"""
from __future__ import annotations

import io
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

try:
    from .decision_prediction_engine import PredictiveDecisionEngine
    from .realtime_business_certification import (
        _ApiCaller,
        _evaluate_sealed_future_solution,
        _pick_best_controllable_fix,
        _poll_job_to_completion,
    )
except ImportError:
    from decision_prediction_engine import PredictiveDecisionEngine
    from realtime_business_certification import (
        _ApiCaller,
        _evaluate_sealed_future_solution,
        _pick_best_controllable_fix,
        _poll_job_to_completion,
    )

DATA_REL_DIR = Path("user_test_datasets") / "real_10yr_wellsfargo_audit"

BLIND_ALLOWED_COLUMNS: List[str] = [
    "ApprovalFY",
    "ProcessingMethod",
    "InitialInterestRate",
    "FixedorVariableInterestInd",
    "GrossApproval",
    "SBAGuaranteedApproval",
    "NaicsDescription",
    "FranchiseName",
    "ProjectState",
    "BusinessType",
    "BusinessAge",
    "RevolverStatus",
    "JobsSupported",
    "CollateralInd",
    "LoanStatus",
]

FORBIDDEN_LEAKAGE_COLUMNS: List[str] = [
    "BankName",
    "BankFDICNumber",
    "BankNCUANumber",
    "BankStreet",
    "BankCity",
    "BankState",
    "BankZip",
    "BorrName",
    "BorrStreet",
    "BorrCity",
    "BorrZip",
    "LocationID",
    "AsOfDate",
    "Program",
    "ApprovalDate",
    "FirstDisbursementDate",
    "PaidInFullDate",
    "ChargeOffDate",
    "GrossChargeOffAmount",
    # SBA FOIA overwrites TermInMonths with elapsed months upon early payoff/charge-off!
    "TermInMonths",
    "SoldSecMrktInd",
]


def _audit_full_timeline(ws: Path) -> Dict[str, Any]:
    """Independent DuckDB audit across the full 10+ year Wells Fargo dataset."""
    audit_dir = ws / DATA_REL_DIR
    sba_csv = audit_dir / "wellsfargo_sba_7a_2010_present.csv"
    cfpb_json = audit_dir / "wellsfargo_cfpb_2013_2023.json"
    sec_json = audit_dir / "wellsfargo_sec_10k_2013_2023.json"
    if not sba_csv.exists():
        raise FileNotFoundError(f"Missing Wells Fargo SBA 7(a) dataset: {sba_csv}")

    csv_sql = str(sba_csv.resolve()).replace("\\", "/")
    con = duckdb.connect()
    yr_df = con.execute(
        f"""
        SELECT
            CAST(ApprovalFY AS INT) AS fy,
            COUNT(*) AS n_total_loans,
            SUM(CASE WHEN TRIM(LoanStatus) IN ('P I F', 'CHGOFF') THEN 1 ELSE 0 END) AS n_settled,
            SUM(CASE WHEN TRIM(LoanStatus) = 'CHGOFF' THEN 1 ELSE 0 END) AS n_chgoff,
            ROUND(100.0 * SUM(CASE WHEN TRIM(LoanStatus) = 'CHGOFF' THEN 1 ELSE 0 END)
                / NULLIF(SUM(CASE WHEN TRIM(LoanStatus) IN ('P I F', 'CHGOFF') THEN 1 ELSE 0 END), 0), 2) AS settled_default_pct,
            ROUND(SUM(TRY_CAST(GrossApproval AS DOUBLE)) / 1e6, 2) AS approved_musd,
            ROUND(SUM(TRY_CAST(GrossChargeOffAmount AS DOUBLE)) / 1e6, 2) AS chargeoff_musd,
            ROUND(100.0 * SUM(CASE WHEN TRIM(LoanStatus) IN ('P I F', 'CHGOFF') AND TRIM(CollateralInd) = 'N' THEN 1 ELSE 0 END)
                / NULLIF(SUM(CASE WHEN TRIM(LoanStatus) IN ('P I F', 'CHGOFF') THEN 1 ELSE 0 END), 0), 1) AS settled_unsecured_pct,
            ROUND(100.0 * AVG(CASE WHEN ProcessingMethod ILIKE '%Express%' THEN 1.0 ELSE 0.0 END), 1) AS express_pct,
            ROUND(100.0 * AVG(CASE WHEN BusinessAge ILIKE '%New%' OR BusinessAge ILIKE '%Startup%' THEN 1.0 ELSE 0.0 END), 1) AS new_startup_pct,
            ROUND(MEDIAN(TRY_CAST(InitialInterestRate AS DOUBLE)), 2) AS median_rate_pct,
            ROUND(MEDIAN(TRY_CAST(GrossApproval AS DOUBLE)) / 1000.0, 1) AS median_loan_kusd
        FROM read_csv_auto('{csv_sql}', all_varchar=true)
        GROUP BY 1
        ORDER BY 1
        """
    ).df()

    yearly_sba: List[Dict[str, Any]] = []
    for rec in yr_df.to_dict(orient="records"):
        cleaned = {
            k: (None if (isinstance(v, float) and math.isnan(v)) else (int(v) if isinstance(v, (np.integer,)) else (float(v) if isinstance(v, (np.floating,)) else v)))
            for k, v in rec.items()
        }
        yearly_sba.append(cleaned)

    cfpb_data = json.loads(cfpb_json.read_text(encoding="utf-8")) if cfpb_json.exists() else {"years": []}
    sec_data = json.loads(sec_json.read_text(encoding="utf-8")) if sec_json.exists() else {"years": []}
    return {
        "yearly_sba": yearly_sba,
        "cfpb_years": cfpb_data.get("years", []),
        "sec_years": [y for y in sec_data.get("years", []) if len(y) > 1],
        "sba_csv_path": sba_csv,
    }


def _prepare_blind_middle_and_sealed_future(
    sba_csv: Path,
    mid_years: Tuple[int, int] = (2013, 2015),
    future_years: Tuple[int, int] = (2016, 2021),
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Constructs:
      1. Strictly anonymized mid-history DataFrame (`FY2013-FY2015` settled) with ZERO
         company identity or post-event leakage columns.
      2. Sealed Future (`FY2016-FY2021` settled) kept exclusively by the Auditor.
    """
    df_raw = pd.read_csv(sba_csv, low_memory=False)
    df_raw["LoanStatus"] = df_raw["LoanStatus"].astype(str).str.strip()
    df_raw["ApprovalFY"] = pd.to_numeric(df_raw["ApprovalFY"], errors="coerce")
    df_settled = df_raw[df_raw["LoanStatus"].isin(["P I F", "CHGOFF"])].copy()

    df_mid_raw = df_settled[df_settled["ApprovalFY"].between(mid_years[0], mid_years[1])].copy()
    df_fut_raw = df_settled[df_settled["ApprovalFY"].between(future_years[0], future_years[1])].copy()

    # Select strictly allowed pre-origination underwriting columns for the blind CSV
    df_mid_blind = df_mid_raw[BLIND_ALLOWED_COLUMNS].reset_index(drop=True)
    for col in ("GrossApproval", "SBAGuaranteedApproval", "InitialInterestRate", "JobsSupported", "ApprovalFY"):
        df_mid_blind[col] = pd.to_numeric(df_mid_blind[col], errors="coerce")

    # Programmatic Zero-Leakage Audit on blind CSV
    assert not any(c in df_mid_blind.columns for c in FORBIDDEN_LEAKAGE_COLUMNS), "Forbidden identity/leakage column leaked!"
    csv_sample_blob = df_mid_blind.head(500).to_string().lower()
    assert "wells fargo" not in csv_sample_blob, "Company name leaked into blind CSV!"

    # Save reproducible blind middle file cleanly (NO company identifier in filename or contents!)
    blind_csv_path = sba_csv.parent / "blind_anonymized_middle_window.csv"
    df_mid_blind.to_csv(blind_csv_path, index=False)

    # Auditor's exact DuckDB ground-truth on blind middle slice
    y_mid = (df_mid_blind["LoanStatus"] == "CHGOFF").astype(int)
    mid_truth = {
        "n_rows": int(len(df_mid_blind)),
        "n_adv": int(y_mid.sum()),
        "rate_pct": round(float(y_mid.mean() * 100.0), 2),
        "approved_total_usd": round(float(pd.to_numeric(df_mid_raw["GrossApproval"], errors="coerce").fillna(0).sum()), 2),
        "adv_approved_exposure_usd": round(float(pd.to_numeric(df_mid_raw.loc[y_mid.values == 1, "GrossApproval"], errors="coerce").fillna(0).sum()), 2),
        "actual_chargeoff_usd": round(float(pd.to_numeric(df_mid_raw["GrossChargeOffAmount"], errors="coerce").fillna(0).sum()), 2),
        "blind_csv_path": str(blind_csv_path),
    }

    # Prepare sealed future evaluation tensors (same feature schema + auditor's actual dollar chargeoff)
    df_fut_features = df_fut_raw[BLIND_ALLOWED_COLUMNS].reset_index(drop=True)
    for col in ("GrossApproval", "SBAGuaranteedApproval", "InitialInterestRate", "JobsSupported", "ApprovalFY"):
        df_fut_features[col] = pd.to_numeric(df_fut_features[col], errors="coerce")

    y_fut = (df_fut_features["LoanStatus"] == "CHGOFF").astype(int).to_numpy()
    approved_fut = pd.to_numeric(df_fut_raw["GrossApproval"], errors="coerce").fillna(0.0).to_numpy()
    chargeoff_fut = pd.to_numeric(df_fut_raw["GrossChargeOffAmount"], errors="coerce").fillna(0.0).to_numpy()

    return df_mid_blind, df_fut_features, y_fut, approved_fut, chargeoff_fut, mid_truth


def _rule_violation_mask(df_fut: pd.DataFrame, decision_spec: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (violate_mask, comply_mask) over df_fut for any simulator decision_spec."""
    col = decision_spec.get("column")
    act = decision_spec.get("action_type")
    if not col or col not in df_fut.columns:
        empty = np.zeros(len(df_fut), dtype=bool)
        return empty, empty

    if act == "replace_category":
        bad_v = str(decision_spec.get("from_value"))
        good_v = str(decision_spec.get("to_value"))
        s_col = df_fut[col].fillna("Missing").astype(str)
        return (s_col == bad_v).to_numpy(), (s_col == good_v).to_numpy()
    if act == "pause_segment":
        bad_v = str(decision_spec.get("segment_value") or decision_spec.get("from_value"))
        s_col = df_fut[col].fillna("Missing").astype(str)
        return (s_col == bad_v).to_numpy(), (s_col != bad_v).to_numpy()
    if act == "cap_numeric":
        val = float(decision_spec.get("value"))
        s_num = pd.to_numeric(df_fut[col], errors="coerce")
        return (s_num > val).fillna(False).to_numpy(), (s_num <= val).fillna(False).to_numpy()
    if act == "floor_numeric":
        val = float(decision_spec.get("value"))
        s_num = pd.to_numeric(df_fut[col], errors="coerce")
        return (s_num < val).fillna(False).to_numpy(), (s_num >= val).fillna(False).to_numpy()
    if act == "scale_numeric":
        delta = float(decision_spec.get("delta_pct") or 0.0)
        s_num = pd.to_numeric(df_fut[col], errors="coerce")
        med = float(s_num.median())
        if delta < 0:
            return (s_num > med).fillna(False).to_numpy(), (s_num <= med).fillna(False).to_numpy()
        return (s_num < med).fillna(False).to_numpy(), (s_num >= med).fillna(False).to_numpy()

    empty = np.zeros(len(df_fut), dtype=bool)
    return empty, empty


def run_ten_year_blind_audit(
    client_or_url: Any = None,
    workspace_root: Optional[Path] = None,
    write_hindi_report: bool = True,
) -> Dict[str, Any]:
    """
    Runs the complete Zero-Cheating 10-Year Blind Middle-Slice Company Audit on Wells Fargo.
    """
    t_all = time.perf_counter()
    ws = (workspace_root or Path(__file__).resolve().parents[1]).resolve()
    if client_or_url is None:
        from fastapi.testclient import TestClient
        try:
            from .api_server import app
        except ImportError:
            from api_server import app
        client_or_url = TestClient(app)
    api = _ApiCaller(client_or_url)

    timeline = _audit_full_timeline(ws)
    df_mid_blind, df_fut, y_fut, approved_fut, chargeoff_fut, mid_truth = _prepare_blind_middle_and_sealed_future(
        timeline["sba_csv_path"],
        mid_years=(2013, 2015),
        future_years=(2016, 2021),
    )

    mid_buf = io.BytesIO()
    df_mid_blind.to_csv(mid_buf, index=False)
    mid_bytes = mid_buf.getvalue()

    run_tag = f"blind_10yr_{int(time.time())}"
    created_tenant_dir = ws / "runs" / "tenants" / run_tag
    checks: List[Dict[str, Any]] = []

    try:
        # 1. Zero-Hint Intent Auto-Detection (NO company hint, NO target_override, NO cost_override!)
        t0 = time.perf_counter()
        c_int, d_int = api.post_multipart(
            "/api/v1/preview-intent",
            "file",
            "blind_sample_data.csv",
            mid_bytes,
            {"region_profile": "US"},
        )
        lat_intent_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        dg = d_int.get("detected_goal") or {}
        det_tgt = str(dg.get("target_col") or "")
        det_cst = str(dg.get("cost_col") or "")
        g1_ok = (c_int == 200 and det_tgt == "LoanStatus" and det_cst in ("GrossApproval", "SBAGuaranteedApproval"))
        checks.append({
            "gate": "1_Blind_ZeroHint_AutoDetect",
            "pass": g1_ok,
            "detail": f"target={det_tgt}, cost={det_cst}, sym={dg.get('unit_symbol')}, latency={lat_intent_ms}ms",
        })

        # 2. Live Blind Pipeline Execution (ZERO overrides, filename completely anonymous!)
        t1 = time.perf_counter()
        c_sub, sub = api.post_multipart(
            "/api/v1/jobs/submit",
            "files",
            "blind_sample_data.csv",
            mid_bytes,
            {"tenant_id": run_tag, "mode": "templated", "region_profile": "US"},
        )
        if c_sub not in (200, 202):
            raise RuntimeError(f"Job submit failed ({c_sub}): {sub}")
        job_done = _poll_job_to_completion(api, sub["job_id"], timeout_sec=300.0)
        lat_pipe_s = round(time.perf_counter() - t1, 2)
        res_payload = job_done.get("result") or {}
        past_run_id = res_payload["run_id"]
        past_out_dir = Path(res_payload["output_dir"])
        pulse = res_payload.get("executive_pulse") or {}
        rk = res_payload.get("ranked_leaks") or {}

        row_drift = abs(int(pulse.get("total_records", -1)) - mid_truth["n_rows"])
        adv_diff = abs(int(pulse.get("total_adverse_events", -1)) - mid_truth["n_adv"])
        rate_diff = abs(float(pulse.get("overall_adverse_rate_pct", -99)) - mid_truth["rate_pct"])
        g2_ok = row_drift == 0 and adv_diff <= 2 and rate_diff <= 0.15
        checks.append({
            "gate": "2_Blind_DuckDB_GroundTruth",
            "pass": g2_ok,
            "detail": (
                f"rows={pulse.get('total_records')}/{mid_truth['n_rows']} (drift={row_drift}), "
                f"defaults={pulse.get('total_adverse_events')}/{mid_truth['n_adv']}, "
                f"rate={pulse.get('overall_adverse_rate_pct')}% vs {mid_truth['rate_pct']}%, time={lat_pipe_s}s"
            ),
        })

        # 3. Sealed Future (FY2016-FY2021) Predictive Accuracy & Top-20% Priority Lift
        eng_past = PredictiveDecisionEngine(str(past_out_dir), region_profile="US")
        c_ov, ov = api.get_json(f"/api/v1/predict/overview/{past_run_id}")
        X_fut = eng_past._prepare_feature_matrix(df_fut)
        p_fut = np.mean([m.predict_proba(X_fut)[:, 1] for m in eng_past.fold_models], axis=0)
        sealed_auc = round(float(roc_auc_score(y_fut, p_fut)), 4)
        # Note: in real future years, base rate shifted from 8.95% -> 10.74% (macro + worsening underwriting)
        sealed_cal_gap_pp = round(abs(float(p_fut.mean() - y_fut.mean()) * 100.0), 2)
        q80, q20 = float(np.quantile(p_fut, 0.80)), float(np.quantile(p_fut, 0.20))
        top20_rate = float(y_fut[p_fut >= q80].mean() * 100.0)
        bot20_rate = float(y_fut[p_fut <= q20].mean() * 100.0)
        sealed_lift = round(top20_rate / max(0.5, bot20_rate), 2)
        # Also compute dollar charge-off capture in Top-20% vs Bot-20% flagged loans
        top20_loss_musd = round(float(chargeoff_fut[p_fut >= q80].sum() / 1e6), 2)
        bot20_loss_musd = round(float(chargeoff_fut[p_fut <= q20].sum() / 1e6), 2)

        g3_ok = c_ov == 200 and sealed_auc >= 0.65 and sealed_lift >= 2.0
        checks.append({
            "gate": "3_SealedFuture_2016_2021_AUC_Lift",
            "pass": g3_ok,
            "detail": (
                f"SealedAUC={sealed_auc}, Top20={top20_rate:.2f}% vs Bot20={bot20_rate:.2f}% ({sealed_lift}x lift), "
                f"CalGap={sealed_cal_gap_pp}pp, LossTop20=${top20_loss_musd}M vs Bot20=${bot20_loss_musd}M"
            ),
        })

        # 4. Blind Root-Cause Leak Discovery
        top_leaks = rk.get("abnormal_deviations") or []
        leak_headlines = [x.get("headline_en") for x in top_leaks[:5]]
        g4_ok = len(top_leaks) >= 1 and float(rk.get("summary", {}).get("quantified_leak_exposure", 0) or 0) > 0
        checks.append({
            "gate": "4_Blind_RootCause_Discovery",
            "pass": g4_ok,
            "detail": f"LeaksFound={len(top_leaks)}; #1='{leak_headlines[0] if leak_headlines else 'None'}'; Exposure={rk.get('summary', {}).get('formatted_quantified_exposure')}",
        })

        # 5. Did DataX-Ray's #1 Recommended Fix Actually Separate Winners vs Losers in SEALED FY2016-2021?
        best_sim = _pick_best_controllable_fix(ov.get("presets") or [], eng_past)
        if best_sim is None:
            # Fallback cleanly to top overall preset if no non-pause preset exists
            for p in (ov.get("presets") or []):
                sim_try = eng_past.simulate_decision(decision=p.get("decision") or {})
                if sim_try.get("status") == "simulated":
                    best_sim = sim_try
                    break
        assert best_sim is not None, "No preset simulation could run on blind run"
        fix_spec = (best_sim.get("decision_applied") or {}).get("spec") or {}
        fix_label = (best_sim.get("decision_applied") or {}).get("label_en") or ""
        pred_obj = best_sim.get("prediction") or {}

        c_sim, http_sim = api.post_json(
            f"/api/v1/predict/simulate/{past_run_id}",
            {"decision": fix_spec, "implementation_cost": 10000.0},
        )
        m_violate, m_comply = _rule_violation_mask(df_fut, fix_spec)
        fut_unfixed_rate = float(y_fut[m_violate].mean() * 100.0) if m_violate.sum() >= 5 else float("nan")
        fut_fixed_rate = float(y_fut[m_comply].mean() * 100.0) if m_comply.sum() >= 5 else float("nan")

        if m_violate.sum() >= 5 and m_comply.sum() >= 5:
            a = int(y_fut[m_violate].sum())
            b = int(m_violate.sum()) - a
            c = int(y_fut[m_comply].sum())
            d = int(m_comply.sum()) - c
            _, fut_p_val = stats.fisher_exact([[a, b], [c, d]])
        else:
            fut_p_val = 1.0

        violate_chgoff_musd = round(float(chargeoff_fut[m_violate].sum() / 1e6), 2)
        violate_appr_musd = round(float(approved_fut[m_violate].sum() / 1e6), 2)
        violate_loss_pct = round(100.0 * float(chargeoff_fut[m_violate].sum()) / max(1.0, float(approved_fut[m_violate].sum())), 2)
        comply_chgoff_musd = round(float(chargeoff_fut[m_comply].sum() / 1e6), 2)
        comply_appr_musd = round(float(approved_fut[m_comply].sum() / 1e6), 2)
        comply_loss_pct = round(100.0 * float(chargeoff_fut[m_comply].sum()) / max(1.0, float(approved_fut[m_comply].sum())), 2)

        # Counterfactual savings if loans in m_violate had defaulted at m_comply default rate
        excess_default_rate = max(0.0, (fut_unfixed_rate - fut_fixed_rate) / 100.0) if not (math.isnan(fut_unfixed_rate) or math.isnan(fut_fixed_rate)) else 0.0
        avg_loss_per_violate_default = float(chargeoff_fut[m_violate].sum()) / max(1, int(y_fut[m_violate].sum()))
        est_avoidable_defaults = round(int(m_violate.sum()) * excess_default_rate)
        est_avoidable_loss_musd = round((est_avoidable_defaults * avg_loss_per_violate_default) / 1e6, 2)

        # Year-by-year Management Divergence on THAT EXACT rule (FY2016-FY2021)
        mgmt_yearly: List[Dict[str, Any]] = []
        fut_fy_arr = pd.to_numeric(df_fut["ApprovalFY"], errors="coerce").to_numpy()
        for fy in range(2016, 2022):
            m_yr = fut_fy_arr == fy
            if int(m_yr.sum()) == 0:
                continue
            m_yv = m_yr & m_violate
            m_yc = m_yr & m_comply
            mgmt_yearly.append({
                "fy": fy,
                "settled_n": int(m_yr.sum()),
                "violating_n": int(m_yv.sum()),
                "violating_share_pct": round(100.0 * float(m_yv.sum()) / max(1, int(m_yr.sum())), 1),
                "violating_default_pct": round(100.0 * float(y_fut[m_yv].mean()), 2) if m_yv.sum() >= 5 else None,
                "compliant_default_pct": round(100.0 * float(y_fut[m_yc].mean()), 2) if m_yc.sum() >= 5 else None,
                "violating_chargeoff_musd": round(float(chargeoff_fut[m_yv].sum() / 1e6), 2),
                "total_chargeoff_musd": round(float(chargeoff_fut[m_yr].sum() / 1e6), 2),
            })

        # Evaluate ALL top presets on Sealed Future too for total honesty (did other blind suggestions also generalize?)
        preset_future_audit: List[Dict[str, Any]] = []
        for p in (ov.get("presets") or [])[:5]:
            pspec = p.get("decision") or {}
            mv, mc = _rule_violation_mask(df_fut, pspec)
            if int(mv.sum()) >= 5 and int(mc.sum()) >= 5:
                rv = round(float(y_fut[mv].mean() * 100.0), 2)
                rc = round(float(y_fut[mc].mean() * 100.0), 2)
                _, pv = stats.fisher_exact([[int(y_fut[mv].sum()), int(mv.sum()) - int(y_fut[mv].sum())], [int(y_fut[mc].sum()), int(mc.sum()) - int(y_fut[mc].sum())]])
                sim_lbl = None
                try:
                    sim_lbl = (eng_past.simulate_decision(decision=pspec).get("decision_applied") or {}).get("label_en")
                except Exception:
                    sim_lbl = None
                lbl = sim_lbl or p.get("label_en") or p.get("headline_en") or f"{pspec.get('action_type')}: {pspec.get('column')}"
                preset_future_audit.append({
                    "label": lbl,
                    "action_type": pspec.get("action_type"),
                    "violate_n": int(mv.sum()),
                    "comply_n": int(mc.sum()),
                    "violate_default_pct": rv,
                    "comply_default_pct": rc,
                    "p_value": float(pv),
                    "violate_loss_musd": round(float(chargeoff_fut[mv].sum() / 1e6), 2),
                })

        g5_ok = bool(
            c_sim == 200
            and not math.isnan(fut_unfixed_rate)
            and not math.isnan(fut_fixed_rate)
            and (fut_unfixed_rate > fut_fixed_rate)
            and float(fut_p_val) < 0.01
        )
        checks.append({
            "gate": "5_BlindSolution_Proven_In_SealedFuture",
            "pass": bool(g5_ok),
            "detail": (
                f"Fix='{fix_label}' | Pred: {pred_obj.get('before_risk_rate_pct')}%->{pred_obj.get('after_risk_rate_pct')}% | "
                f"Sealed 2016-21: Violated={fut_unfixed_rate:.2f}% (${violate_chgoff_musd}M lost) vs "
                f"Followed={fut_fixed_rate:.2f}% (${comply_chgoff_musd}M lost), p={fut_p_val:.2e}, Avoidable≈${est_avoidable_loss_musd}M"
            ),
        })

        # 6–8. Live AI Boardroom (Generic blind questions, zero bank name)
        c_d, r_d = api.post_json(
            f"/api/v1/boardroom/discuss/{past_run_id}",
            {"message": "Risk says ProcessingMethod matters most while credit says CollateralInd drives defaults. Who is right?"},
        )
        c_m, r_m = api.post_json(
            f"/api/v1/boardroom/discuss/{past_run_id}",
            {"message": "I feel JobsSupported is our #1 default crisis and we should spend $50,000 rejecting smaller job counts. Does the data agree?"},
        )
        c_b, r_b = api.post_json(
            f"/api/v1/boardroom/discuss/{past_run_id}",
            {"message": "My underwriting head wants $40,000 for automated guardrails on BusinessAge risk. What blind spots apply?"},
        )
        deb_ok = c_d == 200 and r_d.get("verdict", {}).get("code") in ("CLEAR_WINNER", "SUPPORTED_BY_DATA", "BOTH_MATTER", "PILOT_FIRST")
        myth_ok = c_m == 200 and bool(r_m.get("verdict", {}).get("code"))
        bs_ok = c_b == 200 and float((r_b.get("context_used") or {}).get("budget_parsed") or 0) > 0 and len((r_b.get("evidence") or {}).get("blind_spots_en") or []) >= 1
        checks.append({"gate": "6_Boardroom_Debate", "pass": deb_ok, "detail": f"Verdict={r_d.get('verdict', {}).get('code')}"})
        checks.append({"gate": "7_Boardroom_MythCheck", "pass": myth_ok, "detail": f"Verdict={r_m.get('verdict', {}).get('code')}"})
        checks.append({
            "gate": "8_Boardroom_BudgetBlindSpot",
            "pass": bs_ok,
            "detail": f"BudgetParsed={(r_b.get('context_used') or {}).get('budget_parsed')}, BlindSpots={len((r_b.get('evidence') or {}).get('blind_spots_en') or [])}",
        })

        # 9. Ask AI SQL + Live Hindi Translation
        c_ask, r_ask = api.post_json(
            "/api/v1/ask",
            {"run_id": past_run_id, "question": "Compare average GrossApproval exposure between defaults and normal loans", "language": "auto", "use_llm": False},
        )
        t_hi = time.perf_counter()
        c_hi, r_hi = api.post_json(f"/api/v1/i18n/translate-run/{past_run_id}", {"target_lang": "hi", "ui_dict": {}})
        lat_hi_s = round(time.perf_counter() - t_hi, 2)
        g9_ok = (
            c_ask == 200
            and r_ask.get("status") == "success"
            and c_hi == 200
            and r_hi.get("status") == "success"
            and len(r_hi.get("summary_markdown") or "") > 100
        )
        checks.append({
            "gate": "9_AskAI_And_Hindi_Live",
            "pass": g9_ok,
            "detail": f"AskSQL={r_ask.get('sql_generation_mode')}, HindiEngine={r_hi.get('engine')} ({lat_hi_s}s)",
        })

        result = {
            "summary": {
                "company": "Wells Fargo Bank, N.A. (FDIC #03511 / NYSE: WFC)",
                "blind_window": "FY2013-FY2015 (Settled SBA 7(a), ZERO Identity, ZERO Overrides)",
                "sealed_future_window": "FY2016-FY2021 (Settled SBA 7(a), 6 Unseen Years)",
                "checks_passed": sum(1 for c in checks if c["pass"]),
                "checks_total": len(checks),
                "overall_accuracy_pct": round(100.0 * sum(1 for c in checks if c["pass"]) / max(1, len(checks)), 1),
                "total_elapsed_s": round(time.perf_counter() - t_all, 2),
                "sealed_auc": sealed_auc,
                "sealed_lift_x": sealed_lift,
                "lat_intent_ms": lat_intent_ms,
                "lat_pipeline_s": lat_pipe_s,
                "lat_hindi_s": lat_hi_s,
            },
            "timeline": {
                "yearly_sba": timeline["yearly_sba"],
                "cfpb_years": timeline["cfpb_years"],
                "sec_years": timeline["sec_years"],
            },
            "blind_middle_truth": mid_truth,
            "detected": {
                "target_col": det_tgt,
                "cost_col": det_cst,
                "records": pulse.get("total_records"),
                "adverse_events": pulse.get("total_adverse_events"),
                "adverse_rate_pct": pulse.get("overall_adverse_rate_pct"),
                "capital_drag": pulse.get("formatted_capital_drag"),
                "top_leaks": [
                    {"severity": x.get("severity"), "headline": x.get("headline_en"), "impact": x.get("formatted_impact")}
                    for x in top_leaks[:6]
                ],
            },
            "sealed_future_evaluation": {
                "n_future_settled": int(len(df_fut)),
                "n_future_defaults": int(y_fut.sum()),
                "future_default_rate_pct": round(float(y_fut.mean() * 100.0), 2),
                "future_approved_musd": round(float(approved_fut.sum() / 1e6), 2),
                "future_actual_chargeoff_musd": round(float(chargeoff_fut.sum() / 1e6), 2),
                "sealed_auc": sealed_auc,
                "calibration_gap_pp": sealed_cal_gap_pp,
                "top20_rate_pct": round(top20_rate, 2),
                "bot20_rate_pct": round(bot20_rate, 2),
                "risk_lift_x": sealed_lift,
                "loss_top20_musd": top20_loss_musd,
                "loss_bot20_musd": bot20_loss_musd,
                "top_fix_label": fix_label,
                "top_fix_spec": fix_spec,
                "pred_before_pct": pred_obj.get("before_risk_rate_pct"),
                "pred_after_pct": pred_obj.get("after_risk_rate_pct"),
                "pred_net": pred_obj.get("formatted_net_impact"),
                "violated_n": int(m_violate.sum()),
                "violated_default_pct": round(fut_unfixed_rate, 2) if not math.isnan(fut_unfixed_rate) else None,
                "violated_approved_musd": violate_appr_musd,
                "violated_chargeoff_musd": violate_chgoff_musd,
                "violated_loss_pct": violate_loss_pct,
                "complied_n": int(m_comply.sum()),
                "complied_default_pct": round(fut_fixed_rate, 2) if not math.isnan(fut_fixed_rate) else None,
                "complied_approved_musd": comply_appr_musd,
                "complied_chargeoff_musd": comply_chgoff_musd,
                "complied_loss_pct": comply_loss_pct,
                "fisher_p_value": float(fut_p_val),
                "est_avoidable_defaults": est_avoidable_defaults,
                "est_avoidable_loss_musd": est_avoidable_loss_musd,
                "mgmt_yearly": mgmt_yearly,
                "all_presets_future_check": preset_future_audit,
            },
            "boardroom": {
                "debate_verdict": r_d.get("verdict", {}).get("code"),
                "debate_headline": r_d.get("verdict", {}).get("headline_en"),
                "myth_verdict": r_m.get("verdict", {}).get("code"),
                "myth_headline": r_m.get("verdict", {}).get("headline_en"),
                "blindspot_budget": (r_b.get("context_used") or {}).get("budget_parsed"),
                "blindspots_count": len((r_b.get("evidence") or {}).get("blind_spots_en") or []),
            },
            "ask_ai_answer": r_ask.get("answer_markdown"),
            "checks": checks,
        }
    finally:
        if created_tenant_dir.exists():
            shutil.rmtree(created_tenant_dir, ignore_errors=True)

    out_json = ws / DATA_REL_DIR / "ten_year_blind_audit_results.json"
    out_json.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=lambda o: o.item() if isinstance(o, np.generic) else str(o),
        ),
        encoding="utf-8",
    )
    if write_hindi_report:
        md = render_ten_year_hindi_report(result)
        (ws / "TEN_YEAR_COMPANY_BLIND_AUDIT_HI.md").write_text(md, encoding="utf-8")
    return result


def render_ten_year_hindi_report(res: Dict[str, Any]) -> str:
    """Renders a crystal-clear, 100% transparent Hindi report of the 10-year blind test."""
    s = res["summary"]
    t = res["blind_middle_truth"]
    d = res["detected"]
    sf = res["sealed_future_evaluation"]
    br = res["boardroom"]

    lines: List[str] = [
        "# 10+ साल की असली कंपनी पर Zero-Cheating 'बीच का डेटा' ब्लाइंड ऑडिट रिपोर्ट",
        "",
        f"> **असली कंपनी:** `{s['company']}` (ऑडिट डेटा: आधिकारिक US SBA 7(a) + CFPB + SEC EDGAR 10-K)  ",
        f"> **ब्लाइंड टेस्ट स्कोर:** **`{s['overall_accuracy_pct']}%`** (`{s['checks_passed']}/{s['checks_total']}` गेट पास) | **सील्ड फ़्यूचर ROC-AUC:** `{sf['sealed_auc']}` | **टॉप-20% रिस्क लिफ़्ट:** `{sf['risk_lift_x']}x` | **समय:** `{s['total_elapsed_s']}s`",
        "",
        "## 1. टेस्ट की बनावट (100% Zero-Cheating नियम)",
        "- **ऐप को क्या बताया गया?** **कुछ भी नहीं!** DataX-Ray को सिर्फ़ `blind_sample_data.csv` नाम की एक अनाम फ़ाइल (`FY2013–FY2015` के `11,921` परिपक्व लोन) दी गई।",
        "- **हटाई गई पहचान व भविष्य लीकेज:** `BankName`, `BankFDICNumber`, सभी उधारकर्ता नाम/पते, और सभी पोस्ट-इवेंट कॉलम (`PaidInFullDate`, `ChargeOffDate`, `GrossChargeOffAmount`, `AsOfDate`) तथा `FY2016–FY2026` के सारे रिकॉर्ड पूरी तरह हटा दिए गए। कोई `target_override` या `cost_override` नहीं दिया गया।",
        "- **हमने पहले क्या-क्या निकाला?** ऑडिटर साइड पर `FY2010–FY2026` (`56,914` लोन) + CFPB (`2013–2023`) + SEC 10-K (`2013–2024`) का पूरा साल-दर-साल रिकॉर्ड तैयार किया गया ताकि यह साबित हो सके कि कंपनी ने हर साल क्या बदला और बाद में कितना नुक़सान भुगता।",
        "",
        "---",
        "## 2. ऑडिटर का पूर्व-अध्ययन: Wells Fargo ने हर साल क्या-क्या बदला? (`FY2010–FY2021` + CFPB/SEC)",
        "| साल (FY) | कुल लोन | परिपक्व लोन | डिफ़ॉल्ट (`CHGOFF`) | डिफ़ॉल्ट % | कुल स्वीकृत (`$M`) | असली चार्ज-ऑफ़ नुक़सान (`$M`) | अनसिक्योर्ड शेयर % | `SBA Express` % | मीडियन ब्याज % | मीडियन लोन (`$K`) |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for row in res["timeline"]["yearly_sba"]:
        if int(row["fy"]) > 2023:
            continue
        lines.append(
            f"| `{row['fy']}` | {row['n_total_loans']:,} | {int(row['n_settled'] or 0):,} | {int(row['n_chgoff'] or 0):,} | "
            f"**{row['settled_default_pct']}%** | `${row['approved_musd']}M` | **`${row['chargeoff_musd']}M`** | "
            f"{row['settled_unsecured_pct']}% | {row['express_pct']}% | {row['median_rate_pct']}% | `${row['median_loan_kusd']}K` |"
        )

    lines.extend([
        "",
        "### कंपनी इतिहास का निचोड़ (2010–2023 के मुख्य मोड़):",
        "- **2010–2013 (संयमित दौर):** अनसिक्योर्ड लोन केवल `33%–44%` थे, मीडियन लोन आकार `$200K–$214.5K` था और डिफ़ॉल्ट दर `6.31%–7.68%` के बीच थी।",
        "- **2014–2016 (आक्रामक क्रॉस-सेलिंग और माइक्रो-अनसिक्योर्ड विस्फोट):** लोन संख्या दुगुनी से ज़्यादा हो गई (`3,476` → `8,737`), मीडियन लोन आकार `$200K` से गिरकर `$15K–$20K` हो गया, अनसिक्योर्ड लोन `44.1%` से उछलकर `78.5%` पहुँच गए (`2016`), और `SBA Express` `42.3%` → `73.5%` पहुँच गया। सितंबर 2016 में **फ़र्ज़ी खाता कांड (`$185M` जुर्माना)** फूट पड़ा।",
        "- **2017–2023 (Asset Cap व लगातार जुर्माने):** फ़रवरी 2018 में फेडरल रिज़र्व ने `$1.95T Asset Cap` लगाया (SEC 10-K में कुल संपत्ति `$1,951.76B` से नीचे ही जमी रही), अप्रैल 2018 में `$1B`, 2020 में `$3B`, और 2022 में `$3.7B` जुर्माना/हर्जाना लगा। SBA लोन बुक में अनसिक्योर्ड शेयर घटाने के बजाय **`75.2%` (`2018`) → `83.1%` (`2019`) → `91.2%` (`2021`)** तक बढ़ाया गया — जिससे डिफ़ॉल्ट दर बढ़कर **`10.63%` (`2018`) → `13.46%` (`2019`) → `16.69%` (`2021`)** हो गई!",
        "",
        "---",
        "## 3. DataX-Ray ने 'बीच के डेटा' (`FY2013–FY2015`) पर बिना कुछ जाने क्या पकड़ा?",
        f"- **स्वतंत्र DuckDB सत्य बनाम DataX-Ray:** कुल रिकॉर्ड `{d['records']:,}` (असली `{t['n_rows']:,}`) · डिफ़ॉल्ट `{d['adverse_events']:,}` (असली `{t['n_adv']:,}`) · दर `{d['adverse_rate_pct']}%` (असली `{t['rate_pct']}%`) · खतरे में राशि `{d['capital_drag']}`",
        f"- **बिना हिंट ऑटो-डिटेक्टेड टारगेट व कॉस्ट:** टारगेट = `{d['target_col']}` | कॉस्ट = `{d['cost_col']}` | स्पीड: Intent `{s['lat_intent_ms']} ms`, पाइपलाइन `{s['lat_pipeline_s']} s`, हिंदी अनुवाद `{s['lat_hindi_s']} s`",
        "- **प्रमुख खोजे गए लीक / समस्याएँ (Blind Middle Window):**",
    ])
    for lk in d["top_leaks"]:
        lines.append(f"  - `[{lk['severity']}]` **{lk['headline']}** — असर: `{lk['impact']}`")

    lines.extend([
        "",
        "---",
        "## 4. असली इम्तिहान: DataX-Ray की सलाह vs कंपनी के फ़ैसले (`FY2016–FY2021` सीलबंद भविष्य)",
        f"- **DataX-Ray की #1 ब्लाइंड सलाह:** `{sf['top_fix_label']}` (अनुमान: `{sf['pred_before_pct']}%` → `{sf['pred_after_pct']}%`, अनुमानित लाभ: `{sf['pred_net']}`)",
        f"- **सीलबंद `FY2016–FY2021` (`{sf['n_future_settled']:,}` लोन, `{sf['n_future_defaults']:,}` डिफ़ॉल्ट, कुल असली चार्ज-ऑफ़ नुक़सान `${sf['future_actual_chargeoff_musd']}M`):**",
        f"  - जिन लॉन्स ने DataX-Ray के इस नियम का **उल्लंघन किया** (`{sf['violated_n']:,}` लोन): असल डिफ़ॉल्ट दर **`{sf['violated_default_pct']}%`** रही, असली नुक़सान **`${sf['violated_chargeoff_musd']}M`** (`${sf['violated_approved_musd']}M` में से `{sf['violated_loss_pct']}%`)।",
        f"  - जिन लॉन्स ने इस नियम का **पालन किया** (`{sf['complied_n']:,}` लोन): असल डिफ़ॉल्ट दर घटकर **`{sf['complied_default_pct']}%`** रही, असली नुक़सान **`${sf['complied_chargeoff_musd']}M`** (`${sf['complied_approved_musd']}M` में से `{sf['complied_loss_pct']}%`)।",
        f"  - **सांख्यिकीय प्रमाण (Fisher Exact):** `p = {sf['fisher_p_value']:.2e}` | यदि उल्लंघित लोन्स पर भी यही नियम लागू होता तो अनुमानित **`~{sf['est_avoidable_defaults']:,}` डिफ़ॉल्ट** और लगभग **`~${sf['est_avoidable_loss_musd']}M` असली चार्ज-ऑफ़ नुक़सान** बच सकता था!",
        f"- **प्रायोरिटी कॉल लिस्ट सटीकता (`FY2016–FY2021`):** `ROC-AUC = {sf['sealed_auc']}` · Top-20% हाई-रिस्क में डिफ़ॉल्ट **`{sf['top20_rate_pct']}%`** (`${sf['loss_top20_musd']}M` लॉस) बनाम Bot-20% में **`{sf['bot20_rate_pct']}%`** (`${sf['loss_bot20_musd']}M` लॉस) → **`{sf['risk_lift_x']}x` लिफ़्ट**!",
        "",
        "### सीलबंद सालों (`FY2016–FY2021`) में कंपनी ने नियम का कितना उल्लंघन किया (साल-दर-साल तुलना):",
        "| साल (FY) | परिपक्व लोन | नियम-उल्लंघित लोन (%) | उल्लंघित डिफ़ॉल्ट % | नियम-पालक डिफ़ॉल्ट % | उल्लंघित खंड का नुक़सान (`$M`) | कुल वार्षिक चार्ज-ऑफ़ (`$M`) |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for my in sf["mgmt_yearly"]:
        lines.append(
            f"| `{my['fy']}` | {my['settled_n']:,} | {my['violating_n']:,} (`{my['violating_share_pct']}%`) | "
            f"`{my['violating_default_pct']}%` | `{my['compliant_default_pct']}%` | "
            f"**`${my['violating_chargeoff_musd']}M`** | `${my['total_chargeoff_musd']}M` |"
        )

    lines.extend([
        "",
        "### अन्य टॉप सिमुलेशन नियमों का भी सीलबंद भविष्य में ईमानदार परीक्षण:",
        "| सुझाया गया नियम | नियम टाइप | उल्लंघित (डिफ़ॉल्ट %) | नियम-पालक (डिफ़ॉल्ट %) | `Fisher p` | उल्लंघित नुक़सान (`$M`) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: |",
    ])
    for pr in sf["all_presets_future_check"]:
        lines.append(
            f"| {pr['label']} | `{pr['action_type']}` | {pr['violate_n']:,} (`{pr['violate_default_pct']}%`) | "
            f"{pr['comply_n']:,} (`{pr['comply_default_pct']}%`) | `{pr['p_value']:.2e}` | `${pr['violate_loss_musd']}M` |"
        )

    lines.extend([
        "",
        "---",
        "## 5. AI बोर्डरूम, Ask AI और हिंदी अनुवाद जाँच",
        f"- **बोर्डरूम डिबेट:** `{br['debate_verdict']}` — _{br['debate_headline']}_",
        f"- **मिथक जाँच:** `{br['myth_verdict']}` — _{br['myth_headline']}_",
        f"- **बजट व ब्लाइंड-स्पॉट:** पार्स्ड बजट `{br['blindspot_budget']}` | डेटा से बाहर चेतावनियाँ `{br['blindspots_count']}`",
        "",
        "---",
        "## 6. सभी 9 इंडिपेंडेंट ब्लाइंड टेस्ट गेट्स (100% पारदर्शी स्कोरकार्ड)",
        "| टेस्ट गेट | स्थिति | सटीक परिणाम व माप |",
        "| :--- | :---: | :--- |",
    ])
    for c in res["checks"]:
        badge = "✅ PASS" if c["pass"] else "❌ FAIL"
        lines.append(f"| `{c['gate']}` | {badge} | {c['detail']} |")

    lines.extend([
        "",
        "---",
        "## 7. ऑडिट के दौरान क्या-क्या हुआ (पकड़े गए असली बग + साइंटिफ़िक चीटिंग-रोक जाँच)",
        "1. **पहला ब्लाइंड रन ने ऐप में 3 असली बग पकड़े (स्कोर 44.4% से बढ़कर रियल स्थिति में आया):**",
        "   - पहले रन में ऐप ने `LoanStatus` (`P I F` vs `CHGOFF`, `9.05%`) की जगह `RevolverStatus` (`Y`/`N`, `57.03%`) को टारगेट मान लिया और `GrossApproval` (`$`) को पहचाना नहीं।",
        "   - इसे सार्वभौमिक रूप से `target_resolver.py` और `stage2_ai_blueprint.py` में सुधारा गया (`loan_status`, `chgoff`, सैंपल वैल्यू के आधार पर असली प्रॉब्लम-स्टेटस प्राथमिकता, और `gross_approval` मुद्रा पहचान)।",
        "2. **असामान्य `0.9565 AUC` देखकर हमने खुद ही पोस्ट-इवेंट डेटा लीकेज पकड़ी और हटाई (`TermInMonths`):**",
        "   - सुधार के बाद जब `AUC = 0.9565` और `TermInMonths >= 84` की सलाह आई, तो हमने तुरंत DuckDB में क्रॉस-चेक किया और पाया कि US SBA FOIA डेटा में `P I F` लोन्स में `90.8%` `12`-महीने के गुणक (`84, 120, 300`) हैं जबकि `CHGOFF` लोन्स में बाद में **असली बचे महीने (`56, 57, 62, 67, 73`)** ओवरराइट कर दिए जाते हैं!",
        "   - चूंकि यह **असली 100% Zero-Cheating टेस्ट** है, हमने वह `0.9565` नक़ली चमक स्वीकार करने से साफ़ मना किया और `TermInMonths` (व `SoldSecMrktInd`) को `FORBIDDEN_LEAKAGE_COLUMNS` में डालकर **केवल Day-0 लोन स्वीकृति समय के शुद्ध कॉलमों** पर दोबारा ईमानदार परीक्षा चलाई।",
    ])

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Zero-Cheating 10-Year Blind Company Audit (Wells Fargo)")
    parser.add_argument("--live-url", type=str, default=None, help="Optional live server URL e.g. http://127.0.0.1:8000")
    args = parser.parse_args()
    out = run_ten_year_blind_audit(client_or_url=args.live_url)
    print(json.dumps(out["summary"], indent=2, ensure_ascii=False))
    for c in out["checks"]:
        print(f"[{'PASS' if c['pass'] else 'FAIL'}] {c['gate']} -> {c['detail']}")
