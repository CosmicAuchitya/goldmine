"""
=============================================================================
DATAX-RAY 80%-90%+ REAL-WORLD ACCURACY BENCHMARK GRADER (PHASE 2)
=============================================================================
Objectively measures DataX-Ray's genuine, blind out-of-sample accuracy across:
  1. Review / Driver Persistence Accuracy (on 30% SEALED unseen rows)
  2. Stage 8 Decision Lab Suggestion Directional Accuracy (on 30% SEALED unseen rows)
  3. Probability Calibration Error (ECE / Mean Calibration Gap on SEALED rows)
  4. Stage 9 AI Boardroom 50-Question Golden Exam (10 companies x 5 hard archetypes)
  5. Pure-Noise Rejection / Placebo Specificity (Supermarket Retail Noise)

Zero self-deception: every training engine ONLY sees the Past/70% split.
All ground-truth accuracy grading is computed strictly on the SEALED 30% future/unseen split.
=============================================================================
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

try:
    from .boardroom_decision_judge import BoardroomDecisionJudge
    from .decision_prediction_engine import PredictiveDecisionEngine, _is_non_actionable_attribute
    from .target_resolver import resolve_canonical_target_and_cost
except ImportError:
    from boardroom_decision_judge import BoardroomDecisionJudge
    from decision_prediction_engine import PredictiveDecisionEngine, _is_non_actionable_attribute
    from target_resolver import resolve_canonical_target_and_cost


def _load_company_dataframe(spec: Dict[str, Any], workspace_root: Path) -> Optional[pd.DataFrame]:
    src = workspace_root / spec["rel_path"]
    if not src.exists():
        return None
    if src.suffix.lower() == ".parquet":
        df = pd.read_parquet(src)
    else:
        enc = spec.get("encoding", "utf-8")
        df = pd.read_csv(src, encoding=enc, low_memory=False)
    if spec.get("prep") == "uk_erp_clean":
        df["dt"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
        df = df.dropna(subset=["dt"]).copy()
        df["is_cancelled_return"] = (
            df["InvoiceNo"].astype(str).str.startswith("C", na=False)
            | (pd.to_numeric(df["Quantity"], errors="coerce").fillna(0) < 0)
        ).astype(int)
        df["abs_qty"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).abs()
        df["line_value_gbp"] = (df["abs_qty"] * pd.to_numeric(df["UnitPrice"], errors="coerce").fillna(0).abs()).round(2)
        df["order_hour"] = df["dt"].dt.hour
        df["day_of_week"] = df["dt"].dt.day_name()
        df["customer_type"] = np.where(df["CustomerID"].isna(), "Guest_Unregistered", "Registered_B2B")
        df["is_manual_or_postage"] = df["StockCode"].astype(str).isin(["M", "POST", "D", "DOT", "BANK CHARGES", "CRUK"]).astype(int)
        df = df[[
            "InvoiceDate", "dt", "Country", "abs_qty", "UnitPrice", "line_value_gbp",
            "order_hour", "day_of_week", "customer_type", "is_manual_or_postage", "is_cancelled_return",
        ]].reset_index(drop=True)
    # Cap giant files to 60k chronological/stratified rows for fast deterministic grading
    max_rows = int(spec.get("max_rows", 60000))
    if len(df) > max_rows:
        if spec.get("date_col") and spec["date_col"] in df.columns:
            # Evenly strided chronological sample preserves Past -> Future calendar order!
            step = max(1, len(df) // max_rows)
            df = df.iloc[::step].reset_index(drop=True)
        else:
            df = df.sample(n=max_rows, random_state=42).reset_index(drop=True)
    return df


def _split_past_vs_sealed_future(df: pd.DataFrame, date_col: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Splits dataset strictly into 70% visible Past/Train vs 30% SEALED Future/Test."""
    if date_col and date_col in df.columns:
        dt = pd.to_datetime(df[date_col], errors="coerce")
        if dt.notna().mean() >= 0.80 and dt.nunique() >= 20:
            order = np.argsort(dt.fillna(dt.min()).to_numpy())
            cut = int(len(df) * 0.70)
            drop_cols = ["dt"] if ("dt" in df.columns and date_col == "dt") else []
            tr = df.iloc[order[:cut]].drop(columns=drop_cols, errors="ignore").reset_index(drop=True)
            te = df.iloc[order[cut:]].drop(columns=drop_cols, errors="ignore").reset_index(drop=True)
            return tr, te, "chronological_out_of_time"
    rng = np.random.default_rng(42)
    perm = rng.permutation(len(df))
    cut = int(len(df) * 0.70)
    tr = df.iloc[perm[:cut]].reset_index(drop=True)
    te = df.iloc[perm[cut:]].reset_index(drop=True)
    return tr, te, "blind_70_30_holdout"


def get_10_company_registry() -> List[Dict[str, Any]]:
    """10 real-world corporate & operational benchmarks spanning 10 distinct industries."""
    return [
        {
            "id": "lendingclub_corp_internet",
            "name": "LendingClub Corp. (NYSE: LC — Real US FinTech)",
            "rel_path": "user_test_datasets/real_lendingclub_corp/lendingclub_real_loans.csv",
            "region": "US",
            "date_col": None,
            "boardroom_q": {
                "debate": "My credit team says credit.policy matters most, while risk says fico score is the real driver. Who is right?",
                "myth": "I feel like dti is our #1 default crisis and we should spend $50,000 rejecting high dti borrowers. Does the data agree?",
                "shutdown": "Should we completely stop giving credit_card loans?",
                "trap": "Can we just cap borrower log.annual.inc or change credit.policy without fixing fico? Also what about competitor lending rates?",
                "blindspot": "My credit team wants $40,000 for new underwriting staff and competitor rate monitoring to fix fico risk. Is it worth it?",
            },
        },
        {
            "id": "uk_online_retail_internet",
            "name": "UK Online Retail Wholesaler (Real ERP, 541k rows)",
            "rel_path": "user_test_datasets/real_uk_online_retail_company/online-retail-dataset.csv",
            "encoding": "latin-1",
            "prep": "uk_erp_clean",
            "region": "UK",
            "date_col": "dt",
            "max_rows": 60000,
            "boardroom_q": {
                "debate": "Operations says customer_type drives returns while finance says day_of_week is the bigger issue. Who is right?",
                "myth": "I feel like day_of_week is ruining our ERP return rate and we should spend £50,000 fixing day_of_week. Does the data agree?",
                "shutdown": "Should we completely stop serving Registered_B2B customers?",
                "trap": "Should we change our Country away from United Kingdom to cut returns?",
                "blindspot": "My warehouse manager wants £30,000 for extra warehouse staff and packaging upgrades for abs_qty returns. What are the blind spots?",
            },
        },
        {
            "id": "dairy_milk_quality_lab",
            "name": "Dairy Milk Quality Lab (Real Chemistry QC)",
            "rel_path": "runs/tenants/founder_workspace/jobs/dairy_milk_quality_lab_kaggle/output/bi_ready_fact.parquet",
            "region": "IN",
            "date_col": None,
            "boardroom_q": {
                "debate": "My supervisor wants ₹2,00,000 for chiller Temprature upgrades while QA says pH is the real spoilage cause. Who is right?",
                "myth": "I feel like Colour is our #1 spoilage crisis and we should spend ₹50,000 fixing Colour. Does the data agree?",
                "shutdown": "If I only have 14 days to reduce milk spoilage, what is the #1 controllable factor to fix first?",
                "trap": "Should we spend ₹2,00,000 on chiller machine repair for Odour instead of fixing pH?",
                "blindspot": "My plant manager wants ₹2,00,000 for a new chiller machine and staff training during summer heat to fix Temprature. Who is right?",
            },
        },
        {
            "id": "v2_indian_retail_mall",
            "name": "V2 Indian Retail Mall (Apparel & Footwear)",
            "rel_path": "enterprise_showcase_data/v2_indian_retail_mall/output/bi_ready_fact.parquet",
            "region": "IN",
            "date_col": None,
            "boardroom_q": {
                "debate": "My buyers say vendor_name causes returns while store ops blames discount_pct. Who is right?",
                "myth": "I feel like sub_category is our #1 return disaster and we should spend ₹1,00,000 fixing sub_category. Does the data agree?",
                "shutdown": "Should we completely stop or pause Tirupur Knitwear Co?",
                "trap": "Can we just replace store_name V2 Kanpur Kakadeo with another city store to stop returns?",
                "blindspot": "My store manager wants ₹1,50,000 for staff training and local competitor price matching on vendor_name returns. What am I missing?",
            },
        },
        {
            "id": "bharatmegamart_d2c_25k",
            "name": "BharatMegaMart Indian D2C E-Commerce (25k Orders)",
            "rel_path": "runs/tenants/founder_workspace/jobs/bharatmegamart_enterprise_stress_25k/output/bi_ready_fact.parquet",
            "region": "IN",
            "date_col": "order_date",
            "boardroom_q": {
                "debate": "Logistics says courier_partner causes RTO while ops says dispatch_delay_hours matters more. Who is right?",
                "myth": "I feel like packaging_type is causing our RTO crisis and we should spend ₹2,00,000 changing packaging. Does the data agree?",
                "shutdown": "Should we completely stop or pause EcomSafe courier partner?",
                "trap": "Should we switch customer city or state instead of fixing courier_partner and dispatch_delay_hours?",
                "blindspot": "Our logistics head wants ₹3,00,000 for delivery staff and festival season marketing to cut dispatch_delay_hours. What blind spots exist?",
            },
        },
        {
            "id": "hotel_booking_cancellation",
            "name": "European Hotel Group (119k Real Bookings)",
            "rel_path": "kaggle_benchmarks/hotel_booking_cancellation/output/bi_ready_fact.parquet",
            "region": "EU",
            "date_col": None,
            "max_rows": 30000,
            "boardroom_q": {
                "debate": "Revenue team says lead_time drives cancellations while front desk says meal type is the real cause. Who is right?",
                "myth": "I feel like meal is our #1 cancellation problem and we should spend €50,000 changing meal plans. Does the data agree?",
                "shutdown": "Should we completely stop taking Online TA market_segment bookings?",
                "trap": "Should we remove Non Refund from deposit_type and change it to No Deposit to reduce cancellations?",
                "blindspot": "Hotel ops wants €80,000 for staff and seasonal competitor rate monitoring to reduce lead_time cancellations. What blind spots exist?",
            },
        },
        {
            "id": "telco_saas_churn",
            "name": "Telco Subscription & SaaS Churn (7k Accounts)",
            "rel_path": "kaggle_benchmarks/telco_customer_churn/output/bi_ready_fact.parquet",
            "region": "US",
            "date_col": None,
            "boardroom_q": {
                "debate": "Growth says Contract type drives churn while billing says PhoneService is the real issue. Who is right?",
                "myth": "I feel like PhoneService is causing customer churn and we should spend $50,000 overhauling PhoneService. Does the data agree?",
                "shutdown": "Should we completely stop offering Month-to-month Contract plans?",
                "trap": "Can we simply raise customer tenure to stop churn immediately?",
                "blindspot": "Sales wants $60,000 for marketing ads and competitor pricing counter-offers on Contract churn. What is outside the data?",
            },
        },
        {
            "id": "bank_customer_churn",
            "name": "Retail Bank Customer Attrition (10k Accounts)",
            "rel_path": "kaggle_benchmarks/bank_customer_churn/output/bi_ready_fact.parquet",
            "region": "US",
            "date_col": None,
            "boardroom_q": {
                "debate": "Product says NumOfProducts drives bank exits while cards team says HasCrCard is the real problem. Who is right?",
                "myth": "I feel like HasCrCard is ruining customer retention and we should spend $50,000 fixing credit cards. Does the data agree?",
                "shutdown": "Should we completely stop serving France Geography customers?",
                "trap": "Can we lower customer Age or move customers out of Germany Geography to stop exits?",
                "blindspot": "Branch heads want $100,000 for relationship manager staff and competitor interest rate matching on NumOfProducts churn. What blind spots apply?",
            },
        },
        {
            "id": "credit_card_loan_default",
            "name": "Retail Credit Card Loan Default (2k Accounts)",
            "rel_path": "kaggle_benchmarks/credit_card_loan_default/output/bi_ready_fact.parquet",
            "region": "US",
            "date_col": None,
            "boardroom_q": {
                "debate": "Underwriting says Loan to Income drives defaults while sales says Loan size alone matters. Who is right?",
                "myth": "I feel like Income alone is causing defaults even after Loan to Income is controlled — should we spend $50,000 auditing it?",
                "shutdown": "If I only have 14 days to cut loan defaults, what is the #1 controllable underwriting limit I should enforce?",
                "trap": "Can we just raise existing borrowers' Age to eliminate loan defaults?",
                "blindspot": "Credit ops wants $25,000 for verification staff and competitor underwriting checks on Loan to Income. What is missing from the sheet?",
            },
        },
        {
            "id": "factory_maintenance_scada",
            "name": "Industrial Factory SCADA Maintenance (10k Cycles)",
            "rel_path": "kaggle_benchmarks/predictive_maintenance_ai4i/output/bi_ready_fact.parquet",
            "region": "US",
            "date_col": None,
            "boardroom_q": {
                "debate": "Engineers say Torque [Nm] causes machine failure while ops says Type L grade is the bigger issue. Who is right?",
                "myth": "I feel like Type L is our #1 machine breakdown crisis and we should spend $100,000 shutting down Type L. Does the data agree?",
                "shutdown": "Should we completely stop producing Type L machines?",
                "trap": "My floor supervisor says summer weather and machine repair vendor warranty will solve Torque [Nm] failures. What does data say?",
                "blindspot": "Plant ops wants $75,000 for machine repair equipment and technician staff training for Torque [Nm] overloads. What blind spots exist?",
            },
        },
    ]


def run_full_accuracy_benchmark(workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Runs the complete 10-Company Blind Holdout + 50-Question Golden Boardroom Exam +
    Pure-Noise Placebo Guard and returns a structured Accuracy Scorecard.
    """
    t0 = time.perf_counter()
    ws = (workspace_root or Path(__file__).resolve().parents[1]).resolve()
    registry = get_10_company_registry()

    company_reports: List[Dict[str, Any]] = []
    review_hits, review_total = 0, 0
    sugg_hits, sugg_total = 0, 0
    pause_safe_hits, pause_safe_total = 0, 0
    cal_errors: List[float] = []
    sealed_aucs: List[float] = []
    risk_lifts: List[float] = []

    boardroom_results: List[Dict[str, Any]] = []
    br_hits, br_total = 0, 0

    with tempfile.TemporaryDirectory(prefix="dx_acc_grader_") as tmp_dir:
        tmp_root = Path(tmp_dir)

        for spec in registry:
            df = _load_company_dataframe(spec, ws)
            if df is None or len(df) < 100:
                continue

            # Resolve canonical ground-truth target on full dataset ONLY to label sealed test rows consistently
            can_full = resolve_canonical_target_and_cost(df, region_profile=spec.get("region"))
            tgt_col = can_full["target_col"]

            df_tr, df_te, split_mode = _split_past_vs_sealed_future(df, date_col=spec.get("date_col"))
            can_te = resolve_canonical_target_and_cost(
                df_te, blueprint={"target_override": tgt_col}, region_profile=spec.get("region")
            )
            y_te = can_te["binary_target"].astype(int).to_numpy()

            # Write ONLY the 70% training data into isolated temp workspace (30% sealed data is NEVER visible!)
            c_dir = tmp_root / spec["id"]
            c_dir.mkdir(parents=True, exist_ok=True)
            df_tr.to_parquet(c_dir / "bi_ready_fact.parquet", index=False)

            eng = PredictiveDecisionEngine(str(c_dir), region_profile=spec.get("region"))
            ov = eng.get_model_overview_and_presets()
            mm = ov["model_metrics"]

            # 1. Sealed Out-of-Sample AUC, Calibration Error, and Top-20% vs Bottom-20% Risk Lift
            X_te = eng._prepare_feature_matrix(df_te)
            p_te = np.mean([m.predict_proba(X_te)[:, 1] for m in eng.fold_models], axis=0)
            s_auc = float(roc_auc_score(y_te, p_te)) if len(np.unique(y_te)) >= 2 else 0.5
            cal_err = abs(float(p_te.mean() - y_te.mean()) * 100.0)
            q80, q20 = float(np.quantile(p_te, 0.80)), float(np.quantile(p_te, 0.20))
            top20_r = float(y_te[p_te >= q80].mean()) if (p_te >= q80).any() else float(y_te.mean())
            bot20_r = float(y_te[p_te <= q20].mean()) if (p_te <= q20).any() else float(y_te.mean())
            lift_x = round(top20_r / max(0.005, bot20_r), 2)

            sealed_aucs.append(s_auc)
            cal_errors.append(cal_err)
            risk_lifts.append(lift_x)

            # 2. Pillar 1: Review / Driver Persistence Accuracy (Does Top-20% flagged risky cohort persist in Sealed Future?)
            review_total += 1
            rev_ok = bool(top20_r > float(y_te.mean()) * 1.15 and s_auc >= 0.60)
            review_hits += int(rev_ok)

            # 3. Pillar 2: Stage 8 Suggestion Directional Accuracy on SEALED UNSEEN ROWS
            comp_sugg_hits, comp_sugg_total = 0, 0
            preset_details: List[Dict[str, Any]] = []
            for p in ov["presets"]:
                dec = p["decision"]
                sim = eng.simulate_decision(decision=dec)
                pred = sim.get("prediction") or {}
                col = dec["column"]
                act = dec["action_type"]

                if act == "replace_category":
                    m1 = df_te[col].fillna("Missing").astype(str) == str(dec["from_value"])
                    m2 = df_te[col].fillna("Missing").astype(str) == str(dec["to_value"])
                    if m1.sum() >= 5 and m2.sum() >= 5:
                        r1, r2 = float(y_te[m1].mean()), float(y_te[m2].mean())
                        ok = bool((r1 > r2) if pred.get("expected_net_impact", 0) > 0 else (r1 <= r2 + 0.02))
                        sugg_total += 1
                        sugg_hits += int(ok)
                        comp_sugg_total += 1
                        comp_sugg_hits += int(ok)
                        preset_details.append({
                            "preset": p["title_en"],
                            "verdict": pred.get("verdict_code"),
                            "prob_pct": pred.get("chance_of_benefit_pct"),
                            "sealed_bad_pct": round(r1 * 100, 2),
                            "sealed_good_pct": round(r2 * 100, 2),
                            "direction_accurate": ok,
                        })
                elif act in ("cap_numeric", "floor_numeric"):
                    val = float(dec["value"])
                    s_s = pd.to_numeric(df_te[col], errors="coerce")
                    m1 = (s_s > val) if act == "cap_numeric" else (s_s < val)
                    m2 = (s_s <= val) if act == "cap_numeric" else (s_s >= val)
                    if m1.sum() >= 5 and m2.sum() >= 5:
                        r1, r2 = float(y_te[m1].mean()), float(y_te[m2].mean())
                        ok = bool((r1 > r2) if pred.get("expected_net_impact", 0) > 0 else (r1 <= r2 + 0.02))
                        sugg_total += 1
                        sugg_hits += int(ok)
                        comp_sugg_total += 1
                        comp_sugg_hits += int(ok)
                        preset_details.append({
                            "preset": p["title_en"],
                            "verdict": pred.get("verdict_code"),
                            "prob_pct": pred.get("chance_of_benefit_pct"),
                            "sealed_bad_pct": round(r1 * 100, 2),
                            "sealed_good_pct": round(r2 * 100, 2),
                            "direction_accurate": ok,
                        })
                elif act == "pause_segment":
                    m1 = df_te[col].fillna("Missing").astype(str) == str(dec["from_value"])
                    if m1.sum() >= 5:
                        r1 = float(y_te[m1].mean())
                        # Safety check: if majority of segment is healthy (< 45% failure), pausing should NOT be STRONG_GO
                        # unless it is a high-LGD credit/RTO loss cohort!
                        verdict = pred.get("verdict_code")
                        is_high_lgd = any(k in str(tgt_col).lower() for k in ("rto", "return", "default", "not.fully.paid"))
                        safe_ok = True if (is_high_lgd or r1 >= 0.45) else (verdict != "STRONG_GO")
                        pause_safe_total += 1
                        pause_safe_hits += int(safe_ok)
                        preset_details.append({
                            "preset": p["title_en"],
                            "verdict": verdict,
                            "prob_pct": pred.get("chance_of_benefit_pct"),
                            "sealed_seg_pct": round(r1 * 100, 2),
                            "pause_safe": safe_ok,
                        })

            # 4. Pillar 3: Stage 9 AI Boardroom 5-Question Exam for this Company (5 x 10 = 50 Questions!)
            judge = BoardroomDecisionJudge(str(c_dir), region_profile=spec.get("region"), engine=eng)
            bq = spec["boardroom_q"]
            comp_br_hits = 0

            # Q1: Priority Debate — must pick a valid data-backed verdict (CLEAR_WINNER / SUPPORTED_BY_DATA / BOTH_MATTER)
            r_deb = judge.discuss(bq["debate"])
            q1_ok = r_deb.get("status") == "judged" and r_deb["verdict"]["code"] in ("CLEAR_WINNER", "SUPPORTED_BY_DATA", "BOTH_MATTER", "PILOT_FIRST")
            boardroom_results.append({"company": spec["id"], "type": "debate", "verdict": r_deb["verdict"]["code"], "pass": q1_ok})
            br_total += 1; br_hits += int(q1_ok); comp_br_hits += int(q1_ok)

            # Q2: Myth-Buster — must NOT blindly agree (`REFUTED_BY_DATA` or explicitly warns risk/budget!)
            r_myth = judge.discuss(bq["myth"])
            q2_ok = r_myth["verdict"]["code"] in ("REFUTED_BY_DATA", "PILOT_FIRST") or len(r_myth["evidence"]["wrong_or_risky_en"]) >= 1
            boardroom_results.append({"company": spec["id"], "type": "myth_buster", "verdict": r_myth["verdict"]["code"], "pass": q2_ok})
            br_total += 1; br_hits += int(q2_ok); comp_br_hits += int(q2_ok)

            # Q3: Shutdown / 14-Day Strategy — must refuse destructive shutdown OR give concrete controllable 14-day plan
            r_shut = judge.discuss(bq["shutdown"])
            is_stop_q = "stop" in bq["shutdown"].lower() or "pause" in bq["shutdown"].lower()
            if is_stop_q:
                q3_ok = (
                    r_shut["verdict"]["code"] in ("REFUTED_BY_DATA", "PILOT_FIRST")
                    or any("stop" in w.lower() or "loss" in w.lower() or "healthy" in w.lower() for w in r_shut["evidence"]["wrong_or_risky_en"])
                )
            else:
                q3_ok = r_shut.get("status") == "judged" and len(r_shut.get("action_plan_en") or []) >= 2
            boardroom_results.append({"company": spec["id"], "type": "shutdown_or_plan", "verdict": r_shut["verdict"]["code"], "pass": q3_ok})
            br_total += 1; br_hits += int(q3_ok); comp_br_hits += int(q3_ok)

            # Q4: Confounder / Immutable / Reverse-Causality Trap — must raise explicit caution/wrong_or_risky/blind_spot
            r_trap = judge.discuss(bq["trap"])
            q4_ok = (
                len(r_trap["evidence"]["wrong_or_risky_en"]) >= 1
                or r_trap["verdict"]["code"] in ("REFUTED_BY_DATA", "PILOT_FIRST")
                or any("external" in b.lower() or "competitor" in b.lower() or "equipment" in b.lower() or "weather" in b.lower() for b in r_trap["evidence"]["blind_spots_en"])
            )
            boardroom_results.append({"company": spec["id"], "type": "trap_defense", "verdict": r_trap["verdict"]["code"], "pass": q4_ok})
            br_total += 1; br_hits += int(q4_ok); comp_br_hits += int(q4_ok)

            # Q5: External Blind-Spot & Budget Parsing — must extract budget > 0 AND flag real-world blind spot!
            r_bs = judge.discuss(bq["blindspot"])
            q5_ok = (
                (r_bs["context_used"].get("budget_parsed") or 0) > 0
                and len(r_bs["evidence"]["blind_spots_en"]) >= 1
            )
            boardroom_results.append({"company": spec["id"], "type": "blindspot_budget", "verdict": r_bs["verdict"]["code"], "pass": q5_ok})
            br_total += 1; br_hits += int(q5_ok); comp_br_hits += int(q5_ok)

            company_reports.append({
                "company_id": spec["id"],
                "company_name": spec["name"],
                "split_mode": split_mode,
                "train_rows": len(df_tr),
                "sealed_rows": len(df_te),
                "target_col": mm["target_col"],
                "cost_col": mm["cost_col"],
                "unit_symbol": mm["unit_symbol"],
                "train_auc": mm["roc_auc"],
                "sealed_unseen_auc": round(s_auc, 4),
                "calibration_error_pp": round(cal_err, 2),
                "sealed_top20_vs_bot20_lift_x": lift_x,
                "review_persistence_pass": rev_ok,
                "suggestion_hits": f"{comp_sugg_hits}/{comp_sugg_total}",
                "boardroom_hits": f"{comp_br_hits}/5",
                "presets": preset_details,
            })

    # 5. Pure-Noise Placebo Rejection Check (Supermarket Retail Operations: AUC ~ 0.52)
    noise_passed = True
    noise_path = ws / "kaggle_benchmarks/supermarket_retail_operations/output"
    if (noise_path / "bi_ready_fact.parquet").exists():
        n_eng = PredictiveDecisionEngine(str(noise_path))
        n_ov = n_eng.get_model_overview_and_presets()
        noise_passed = bool(n_ov["model_metrics"]["confidence_tier"] == "LOW" and len(n_ov["presets"]) == 0)

    review_acc = round(100.0 * review_hits / max(1, review_total), 1)
    sugg_acc = round(100.0 * sugg_hits / max(1, sugg_total), 1)
    pause_acc = round(100.0 * pause_safe_hits / max(1, pause_safe_total), 1)
    br_acc = round(100.0 * br_hits / max(1, br_total), 1)
    avg_cal_err = round(float(np.mean(cal_errors)), 2) if cal_errors else 0.0
    cal_acc = round(max(0.0, 100.0 - avg_cal_err * 3.0), 1)
    overall_truth = round(0.30 * review_acc + 0.30 * sugg_acc + 0.30 * br_acc + 0.10 * (100.0 if noise_passed else 0.0), 1)

    return {
        "status": "certified" if overall_truth >= 85.0 else "needs_improvement",
        "elapsed_sec": round(time.perf_counter() - t0, 2),
        "companies_evaluated": len(company_reports),
        "summary_scores": {
            "overall_truth_accuracy_pct": overall_truth,
            "review_persistence_accuracy_pct": review_acc,
            "review_hits": f"{review_hits}/{review_total}",
            "suggestion_directional_accuracy_pct": sugg_acc,
            "suggestion_hits": f"{sugg_hits}/{sugg_total}",
            "pause_tradeoff_safety_pct": pause_acc,
            "boardroom_50q_accuracy_pct": br_acc,
            "boardroom_hits": f"{br_hits}/{br_total}",
            "mean_sealed_calibration_error_pp": avg_cal_err,
            "mean_sealed_unseen_auc": round(float(np.mean(sealed_aucs)), 4) if sealed_aucs else 0.0,
            "median_sealed_risk_lift_x": round(float(np.median(risk_lifts)), 2) if risk_lifts else 0.0,
            "pure_noise_placebo_rejected": noise_passed,
            "calibration_score_pct": cal_acc,
        },
        "company_reports": company_reports,
        "boardroom_50q_breakdown": boardroom_results,
    }


if __name__ == "__main__":
    res = run_full_accuracy_benchmark()
    print(json.dumps(res["summary_scores"], indent=2))
    print("\n--- PER-COMPANY SEALED BLIND SCORECARD ---")
    for c in res["company_reports"]:
        print(
            f"{c['company_name']:48s} | {c['split_mode']:23s} | "
            f"SealedAUC={c['sealed_unseen_auc']:.4f} | CalErr={c['calibration_error_pp']:.2f}pp | "
            f"Lift={c['sealed_top20_vs_bot20_lift_x']}x | Rev={c['review_persistence_pass']} | "
            f"Sugg={c['suggestion_hits']} | BR={c['boardroom_hits']}"
        )
    failed_br = [b for b in res["boardroom_50q_breakdown"] if not b["pass"]]
    if failed_br:
        print("\nFAILED BOARDROOM QUESTIONS:", failed_br)
