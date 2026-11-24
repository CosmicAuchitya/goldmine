"""
=============================================================================
STAGE 8.2: PREDICTED VS ACTUAL DECISION OUTCOME & ACCOUNTABILITY TRACKER
=============================================================================
Dual-driver persistent ledger (SQLite WAL <-> PostgreSQL 16 via DatabaseAdapter)
that closes the enterprise decision loop:
1. COMMIT: After simulating any single or multi-lever combo decision, a founder
   or COO commits the prediction (expected net impact, 95% CI, rollout cost,
   confidence score, and decision spec) scoped strictly to their `tenant_id`.
2. VERIFY: When a subsequent period's audited dataset (`actual_run_id`) arrives,
   this engine physically reads BOTH the baseline and actual `bi_ready_fact.parquet`
   tables to compute:
   - Execution Compliance % (did operations actually reduce the bad vendor / cap SLA?)
   - Observed Risk Rate Change (Baseline % -> Actual %)
   - Actual Realized Net Impact (after rollout cost, normalized to actual volume)
   - Honest Calibration Hit (did actual fall inside predicted 95% CI?) & Accuracy %
3. ZERO FORCING: If operations never executed the change, or actual results missed
   expectations, this tracker reports the exact shortfall honestly.
=============================================================================
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from .db_adapter import DatabaseAdapter
    from .decision_prediction_engine import _fmt_money
    from .target_resolver import resolve_canonical_target_and_cost
except ImportError:
    from db_adapter import DatabaseAdapter
    from decision_prediction_engine import _fmt_money
    from target_resolver import resolve_canonical_target_and_cost


WORKSPACE_ROOT = Path.cwd().resolve()


class DecisionOutcomeTracker:
    """Thread-safe, multi-tenant Predicted-vs-Actual decision accountability ledger."""

    def __init__(self, storage_dir: Optional[Path] = None, database_url: Optional[str] = None):
        self.storage_dir = (storage_dir or (WORKSPACE_ROOT / "runs" / "decision_outcomes")).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "decision_outcomes.sqlite"
        self.db = DatabaseAdapter(self.db_path, database_url=database_url)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return self.db.connect()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_commitments (
                    commitment_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    baseline_run_id TEXT NOT NULL,
                    decision_label_en TEXT NOT NULL,
                    decision_label_hi TEXT NOT NULL,
                    decision_specs_json TEXT NOT NULL,
                    verdict_code TEXT NOT NULL,
                    predicted_before_rate_pct REAL NOT NULL DEFAULT 0.0,
                    predicted_after_rate_pct REAL NOT NULL DEFAULT 0.0,
                    predicted_net_impact REAL NOT NULL DEFAULT 0.0,
                    predicted_ci_low REAL NOT NULL DEFAULT 0.0,
                    predicted_ci_high REAL NOT NULL DEFAULT 0.0,
                    predicted_benefit_prob_pct REAL NOT NULL DEFAULT 50.0,
                    confidence_score INTEGER NOT NULL DEFAULT 50,
                    implementation_cost REAL NOT NULL DEFAULT 0.0,
                    unit_symbol TEXT NOT NULL DEFAULT '$',
                    is_monetary INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'COMMITTED',
                    created_at REAL NOT NULL,
                    verified_at REAL,
                    actual_run_id TEXT,
                    actual_baseline_scope_rate_pct REAL,
                    actual_observed_rate_pct REAL,
                    actual_net_impact REAL,
                    actual_affected_records INTEGER,
                    execution_compliance_pct REAL,
                    calibration_hit_ci95 INTEGER,
                    accuracy_score_pct REAL,
                    verification_note_en TEXT,
                    verification_note_hi TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dc_tenant_created ON decision_commitments(tenant_id, created_at DESC)"
            )
            conn.commit()

    def commit_decision(
        self,
        tenant_id: str,
        baseline_run_id: str,
        simulation_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persists a simulated decision (single or combo) for future Predicted-vs-Actual verification."""
        if not simulation_payload or simulation_payload.get("status") != "simulated":
            raise ValueError("Only a completed simulation (`status == 'simulated'`) can be committed.")

        app = simulation_payload.get("decision_applied") or {}
        pred = simulation_payload.get("prediction") or {}
        specs = app.get("specs") or ([app["spec"]] if app.get("spec") else [])
        if not specs:
            raise ValueError("Simulation payload is missing decision specification.")

        cid = f"dec_{uuid.uuid4().hex[:12]}"
        now = time.time()
        sc = pred.get("simulation_confidence") or {}

        row_vals = (
            cid,
            str(tenant_id),
            str(baseline_run_id),
            str(app.get("label_en") or "Committed Decision")[:300],
            str(app.get("label_hi") or app.get("label_en") or "Committed Decision")[:300],
            json.dumps(specs, ensure_ascii=False),
            str(pred.get("verdict_code") or "NEUTRAL"),
            float(pred.get("before_risk_rate_pct") or 0.0),
            float(pred.get("after_risk_rate_pct") or 0.0),
            float(pred.get("expected_net_impact") or 0.0),
            float(pred.get("ci_95_low") or 0.0),
            float(pred.get("ci_95_high") or 0.0),
            float(pred.get("chance_of_benefit_pct") or 50.0),
            int(sc.get("score") or 50),
            float(app.get("implementation_cost") or pred.get("implementation_cost") or 0.0),
            str(pred.get("unit_symbol") or "$"),
            1 if pred.get("is_monetary", True) else 0,
            "COMMITTED",
            now,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decision_commitments (
                    commitment_id, tenant_id, baseline_run_id, decision_label_en, decision_label_hi,
                    decision_specs_json, verdict_code, predicted_before_rate_pct, predicted_after_rate_pct,
                    predicted_net_impact, predicted_ci_low, predicted_ci_high, predicted_benefit_prob_pct,
                    confidence_score, implementation_cost, unit_symbol, is_monetary, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row_vals,
            )
            conn.commit()

        return self.get_commitment(tenant_id, cid)

    def _hydrate_row(self, row: Any) -> Dict[str, Any]:
        d = dict(row)
        sym = d.get("unit_symbol") or "$"
        is_mon = bool(d.get("is_monetary", 1))
        try:
            d["specs"] = json.loads(d.get("decision_specs_json") or "[]")
        except Exception:
            d["specs"] = []
        d["is_monetary"] = is_mon
        d["formatted_predicted_net"] = _fmt_money(float(d.get("predicted_net_impact") or 0.0), sym, is_mon)
        d["formatted_predicted_ci"] = (
            f"[{_fmt_money(float(d.get('predicted_ci_low') or 0.0), sym, is_mon)} to "
            f"{_fmt_money(float(d.get('predicted_ci_high') or 0.0), sym, is_mon)}]"
        )
        if d.get("actual_net_impact") is not None:
            d["formatted_actual_net"] = _fmt_money(float(d["actual_net_impact"]), sym, is_mon)
        else:
            d["formatted_actual_net"] = None
        if d.get("calibration_hit_ci95") is not None:
            d["calibration_hit_ci95"] = bool(d["calibration_hit_ci95"])
        return d

    def get_commitment(self, tenant_id: str, commitment_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM decision_commitments WHERE commitment_id = ? AND tenant_id = ?",
                (str(commitment_id), str(tenant_id)),
            ).fetchone()
            return self._hydrate_row(row) if row else None

    def list_commitments(self, tenant_id: str, limit: int = 30) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decision_commitments WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (str(tenant_id), int(limit)),
            ).fetchall()
        items = [self._hydrate_row(r) for r in rows]
        verified = [it for it in items if it.get("status") == "VERIFIED"]
        avg_acc = round(sum(float(v.get("accuracy_score_pct") or 0.0) for v in verified) / len(verified), 1) if verified else None
        ci_hit_rate = round(
            100.0 * sum(1 for v in verified if v.get("calibration_hit_ci95")) / len(verified), 1
        ) if verified else None

        return {
            "tenant_id": str(tenant_id),
            "total_committed": len(items),
            "total_verified": len(verified),
            "average_accuracy_pct": avg_acc,
            "ci95_calibration_hit_rate_pct": ci_hit_rate,
            "commitments": items,
        }

    def delete_commitment(self, tenant_id: str, commitment_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM decision_commitments WHERE commitment_id = ? AND tenant_id = ?",
                (str(commitment_id), str(tenant_id)),
            )
            conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def _load_fact_and_canonical(out_dir: Path):
        fact_p = out_dir / "bi_ready_fact.parquet"
        if not fact_p.exists():
            pqs = list(out_dir.glob("*.parquet"))
            if not pqs:
                raise FileNotFoundError(f"No Parquet fact table found in {out_dir}")
            fact_p = pqs[0]
        df = pd.read_parquet(fact_p)
        blueprint = {}
        for cand in (out_dir / "execution_blueprint.json", out_dir.parent / "execution_blueprint.json"):
            if cand.exists():
                try:
                    blueprint = json.loads(cand.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass
        can = resolve_canonical_target_and_cost(df, blueprint=blueprint)
        return df, can

    @staticmethod
    def _compute_execution_compliance(
        df_base: pd.DataFrame,
        df_act: pd.DataFrame,
        specs: List[Dict[str, Any]],
    ) -> float:
        """Measures how thoroughly operations actually executed the committed lever(s) in the new period."""
        scores: List[float] = []
        for sp in specs:
            act_type = str(sp.get("action_type") or "").lower()
            col = str(sp.get("column") or "")
            if col not in df_base.columns or col not in df_act.columns:
                continue

            sc_col = sp.get("scope_column")
            sc_val = sp.get("scope_value")
            b_sub = df_base
            a_sub = df_act
            if sc_col and sc_col in df_base.columns and sc_col in df_act.columns and sc_val not in (None, "", "All"):
                b_sub = df_base[df_base[sc_col].fillna("Missing").astype(str) == str(sc_val)]
                a_sub = df_act[df_act[sc_col].fillna("Missing").astype(str) == str(sc_val)]
            if len(b_sub) == 0 or len(a_sub) == 0:
                continue

            if act_type in ("replace_category", "pause_segment"):
                fv = str(sp.get("from_value") or "")
                b_share = float((b_sub[col].fillna("Missing").astype(str) == fv).mean())
                a_share = float((a_sub[col].fillna("Missing").astype(str) == fv).mean())
                if b_share > 1e-6:
                    scores.append(max(0.0, min(100.0, (b_share - a_share) / b_share * 100.0)))
            elif act_type == "cap_numeric":
                cap_v = float(sp.get("value", 0.0))
                b_over = float((pd.to_numeric(b_sub[col], errors="coerce") > cap_v).mean())
                a_over = float((pd.to_numeric(a_sub[col], errors="coerce") > cap_v).mean())
                if b_over > 1e-6:
                    scores.append(max(0.0, min(100.0, (b_over - a_over) / b_over * 100.0)))
            elif act_type == "floor_numeric":
                fl_v = float(sp.get("value", 0.0))
                b_under = float((pd.to_numeric(b_sub[col], errors="coerce") < fl_v).mean())
                a_under = float((pd.to_numeric(a_sub[col], errors="coerce") < fl_v).mean())
                if b_under > 1e-6:
                    scores.append(max(0.0, min(100.0, (b_under - a_under) / b_under * 100.0)))
            elif act_type == "scale_numeric":
                b_mean = float(pd.to_numeric(b_sub[col], errors="coerce").dropna().mean() or 0.0)
                a_mean = float(pd.to_numeric(a_sub[col], errors="coerce").dropna().mean() or 0.0)
                delta_pct = float(sp.get("delta_pct") if sp.get("delta_pct") is not None else ((float(sp.get("multiplier", 1.0)) - 1.0) * 100.0))
                target_mean = b_mean * (1.0 + delta_pct / 100.0)
                denom = abs(target_mean - b_mean)
                if denom > 1e-6:
                    progress = (a_mean - b_mean) / (target_mean - b_mean)
                    scores.append(max(0.0, min(100.0, progress * 100.0)))

        return round(float(np.mean(scores)), 1) if scores else 0.0

    def verify_commitment_against_actual(
        self,
        tenant_id: str,
        commitment_id: str,
        actual_run_id: str,
        actual_output_dir: Path,
        baseline_output_dir: Path,
    ) -> Dict[str, Any]:
        """
        Physically compares the committed prediction against actual next-period Parquet records
        and records honest realized ₹/events, execution compliance %, CI hit, and accuracy %.
        """
        comm = self.get_commitment(tenant_id, commitment_id)
        if not comm:
            raise KeyError(f"Decision commitment '{commitment_id}' not found in your workspace.")

        df_base, can_base = self._load_fact_and_canonical(baseline_output_dir)
        df_act, can_act = self._load_fact_and_canonical(actual_output_dir)

        y_base = can_base["binary_target"].astype(int).to_numpy()
        y_act = can_act["binary_target"].astype(int).to_numpy()
        cost_col = can_act.get("cost_col") or can_base.get("cost_col")
        is_mon = bool(comm.get("is_monetary") and cost_col and cost_col in df_act.columns)
        sym = str(comm.get("unit_symbol") or "$")
        specs = comm.get("specs") or []

        # Restrict portfolio scope ONLY when EVERY spec in the commitment shares the exact same scope!
        # (If a combo mixes a company-wide lever + a store-scoped lever, evaluate company-wide!)
        all_scoped = bool(specs) and all(sp.get("scope_column") and sp.get("scope_value") for sp in specs)
        scopes = {(sp.get("scope_column"), sp.get("scope_value")) for sp in specs if sp.get("scope_column") and sp.get("scope_value")}
        b_mask = np.ones(len(df_base), dtype=bool)
        a_mask = np.ones(len(df_act), dtype=bool)
        if all_scoped and len(scopes) == 1:
            sc_c, sc_v = next(iter(scopes))
            if sc_c in df_base.columns and sc_c in df_act.columns:
                b_mask = (df_base[sc_c].fillna("Missing").astype(str) == str(sc_v)).to_numpy()
                a_mask = (df_act[sc_c].fillna("Missing").astype(str) == str(sc_v)).to_numpy()

        if b_mask.sum() < 5 or a_mask.sum() < 5:
            b_mask = np.ones(len(df_base), dtype=bool)
            a_mask = np.ones(len(df_act), dtype=bool)

        base_scope_rate = float(y_base[b_mask].mean())
        act_scope_rate = float(y_act[a_mask].mean())
        rate_drop = base_scope_rate - act_scope_rate  # positive = risk dropped!

        act_n = int(a_mask.sum())
        if is_mon:
            act_exposure_sum = float(np.maximum(0.0, pd.to_numeric(df_act.loc[a_mask, cost_col], errors="coerce").fillna(0.0)).sum())
            realized_gross = rate_drop * act_exposure_sum
        else:
            realized_gross = rate_drop * float(act_n)

        # Include physical realized discount margin delta on each discount lever's own scope!
        disc_specs = [sp for sp in specs if "discount" in str(sp.get("column") or "").lower()]
        if is_mon and disc_specs:
            dsp = disc_specs[0]
            dc = str(dsp.get("column") or "")
            mrp_c = next((c for c in df_act.columns if c.lower() in ("mrp_inr", "mrp", "list_price", "base_price")), None)
            if dc in df_base.columns and dc in df_act.columns and mrp_c:
                db_m = b_mask
                da_m = a_mask
                dsc_c, dsc_v = dsp.get("scope_column"), dsp.get("scope_value")
                if dsc_c and dsc_v and dsc_c in df_base.columns and dsc_c in df_act.columns:
                    db_m = (df_base[dsc_c].fillna("Missing").astype(str) == str(dsc_v)).to_numpy()
                    da_m = (df_act[dsc_c].fillna("Missing").astype(str) == str(dsc_v)).to_numpy()
                if db_m.sum() >= 5 and da_m.sum() >= 5:
                    b_disc = float(pd.to_numeric(df_base.loc[db_m, dc], errors="coerce").dropna().mean() or 0.0)
                    a_disc = float(pd.to_numeric(df_act.loc[da_m, dc], errors="coerce").dropna().mean() or 0.0)
                    if b_disc > a_disc + 0.1:
                        healthy_mrp_sum = float(
                            np.maximum(0.0, pd.to_numeric(df_act.loc[da_m, mrp_c], errors="coerce").fillna(0.0).to_numpy())[y_act[da_m] == 0].sum()
                        )
                        realized_gross += healthy_mrp_sum * ((b_disc - a_disc) / 100.0)

        impl_cost = float(comm.get("implementation_cost") or 0.0)
        actual_net = float(realized_gross - impl_cost)

        compliance_pct = self._compute_execution_compliance(df_base, df_act, specs)
        pred_net = float(comm.get("predicted_net_impact") or 0.0)
        ci_low = float(comm.get("predicted_ci_low") or 0.0)
        ci_high = float(comm.get("predicted_ci_high") or 0.0)

        # Allow a narrow 10% tolerance band for volume growth between months while keeping strict CI honesty
        hit_ci = 1 if (ci_low <= actual_net <= ci_high) else 0
        denom = max(abs(pred_net), abs(actual_net), 1.0)
        rel_err = abs(actual_net - pred_net) / denom
        accuracy_pct = round(max(0.0, (1.0 - rel_err) * 100.0), 1)

        pred_fmt = _fmt_money(pred_net, sym, is_mon)
        act_fmt = _fmt_money(actual_net, sym, is_mon)

        if compliance_pct < 20.0:
            note_en = (
                f"Low Execution ({compliance_pct:.0f}%): Operations barely implemented this change in '{actual_run_id}'. "
                f"Observed scope risk moved {base_scope_rate*100:.2f}% → {act_scope_rate*100:.2f}% (Actual Net: {act_fmt} vs Predicted: {pred_fmt})."
            )
            note_hi = (
                f"कम अमल ({compliance_pct:.0f}%): '{actual_run_id}' डेटा बताता है कि टीम ने यह बदलाव ज़मीन पर लागू नहीं किया। "
                f"रिस्क {base_scope_rate*100:.2f}% → {act_scope_rate*100:.2f}% रहा (असली असर: {act_fmt} बनाम अनुमान: {pred_fmt})।"
            )
        elif hit_ci:
            note_en = (
                f"Verified Hit (Inside 95% CI · {accuracy_pct:.1f}% Accurate · {compliance_pct:.0f}% Executed): "
                f"Risk moved {base_scope_rate*100:.2f}% → {act_scope_rate*100:.2f}%, realizing {act_fmt} vs predicted {pred_fmt}."
            )
            note_hi = (
                f"सटीक प्रमाणित (95% रेंज के भीतर · {accuracy_pct:.1f}% सटीक · {compliance_pct:.0f}% लागू): "
                f"रिस्क {base_scope_rate*100:.2f}% से {act_scope_rate*100:.2f}% पर आया और असली असर {act_fmt} मिला (अनुमान: {pred_fmt})।"
            )
        else:
            direction_en = "outperformed" if actual_net > pred_net else "lagged"
            direction_hi = "उम्मीद से बेहतर रहा" if actual_net > pred_net else "अनुमान से कम रहा"
            note_en = (
                f"Variance Alert ({accuracy_pct:.1f}% Match · {compliance_pct:.0f}% Executed): "
                f"Actual outcome ({act_fmt}) {direction_en} predicted {pred_fmt} (outside 95% CI). Risk: {base_scope_rate*100:.2f}% → {act_scope_rate*100:.2f}%."
            )
            note_hi = (
                f"अंतर अलर्ट ({accuracy_pct:.1f}% मिलान · {compliance_pct:.0f}% लागू): "
                f"असली रिज़ल्ट ({act_fmt}) अनुमान ({pred_fmt}) से {direction_hi}। रिस्क: {base_scope_rate*100:.2f}% → {act_scope_rate*100:.2f}%।"
            )

        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE decision_commitments
                SET status = ?, verified_at = ?, actual_run_id = ?,
                    actual_baseline_scope_rate_pct = ?, actual_observed_rate_pct = ?,
                    actual_net_impact = ?, actual_affected_records = ?,
                    execution_compliance_pct = ?, calibration_hit_ci95 = ?,
                    accuracy_score_pct = ?, verification_note_en = ?, verification_note_hi = ?
                WHERE commitment_id = ? AND tenant_id = ?
                """,
                (
                    "VERIFIED",
                    now,
                    str(actual_run_id),
                    round(base_scope_rate * 100.0, 2),
                    round(act_scope_rate * 100.0, 2),
                    round(actual_net, 2),
                    act_n,
                    compliance_pct,
                    hit_ci,
                    accuracy_pct,
                    note_en,
                    note_hi,
                    str(commitment_id),
                    str(tenant_id),
                ),
            )
            conn.commit()

        return self.get_commitment(tenant_id, commitment_id)
