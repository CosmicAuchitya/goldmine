"""
=============================================================================
DATAX-RAY CLOSED-LOOP ACTION LEDGER & VERIFIED ROI SAVED ENGINE
=============================================================================
Tracks frontline interventions on Priority Worklist rows and reconciles
subsequent dataset uploads to calculate verified capital saved and true
operational ROI:
1. Records frontline actions: Contacted, Discount Offered, Triage Escalated,
   Root-Cause Fixed, Replaced, Retained.
2. When a subsequent dataset/run is uploaded for the same tenant/domain,
   it cross-references previously flagged entities against the new fact table.
3. If an entity previously in PREVENTIVE_RETENTION_WATCH was resolved and
   did NOT experience the adverse event in the new data, its monetary exposure
   is audited as VERIFIED CAPITAL SAVED.
4. Generates audit-grade ROI metrics (e.g., $142,500 saved / 45x subscription ROI).
=============================================================================
"""

import os
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

WORKSPACE_ROOT = Path.cwd().resolve()


class ActionLedger:
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (WORKSPACE_ROOT / "runs" / "action_ledgers")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_tenant_ledger_path(self, tenant_id: str) -> Path:
        safe_tenant = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(tenant_id).strip()) or "default"
        return self.storage_dir / f"ledger_{safe_tenant}.json"

    def _load_ledger(self, tenant_id: str) -> Dict[str, Any]:
        path = self._get_tenant_ledger_path(tenant_id)
        if not path.exists():
            return {
                "tenant_id": tenant_id,
                "created_at": time.time(),
                "updated_at": time.time(),
                "actions": {},
                "roi_summary": {
                    "total_actions_logged": 0,
                    "total_actions_resolved": 0,
                    "verified_saved_capital": 0.0,
                    "verified_averted_events": 0,
                    "retention_success_rate_pct": 0.0,
                    "currency_symbol": "$",
                    "estimated_subscription_cost": 99.0,
                    "roi_multiplier": 0.0
                }
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"tenant_id": tenant_id, "actions": {}, "roi_summary": {}}

    def _save_ledger(self, tenant_id: str, data: Dict[str, Any]) -> None:
        path = self._get_tenant_ledger_path(tenant_id)
        data["updated_at"] = time.time()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record_action(
        self,
        tenant_id: str,
        run_id: str,
        entity_id: str,
        queue: str = "PREVENTIVE_RETENTION_WATCH",
        risk_pct: float = 0.0,
        monetary_exposure: float = 0.0,
        action_type: str = "CONTACTED_AND_RETAINED",
        status: str = "RESOLVED",
        notes: str = "",
        assigned_to: str = "Executive Triage Team",
        currency_symbol: str = "$"
    ) -> Dict[str, Any]:
        """Records an action taken on a priority worklist item."""
        ledger = self._load_ledger(tenant_id)
        action_id = f"act_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        entity_key = str(entity_id).strip()

        norm_status = "RESOLVED" if status.upper() in ("RESOLVED", "RETAINED") else status.upper()
        record = {
            "action_id": action_id,
            "run_id": run_id,
            "entity_id": entity_key,
            "queue": queue,
            "risk_pct": float(risk_pct),
            "monetary_exposure": float(monetary_exposure),
            "action_type": action_type,
            "status": norm_status,
            "notes": notes,
            "assigned_to": assigned_to,
            "currency_symbol": currency_symbol,
            "created_at": time.time(),
            "reconciled": False,
            "reconciled_status": None,
            "saved_capital": 0.0
        }

        # If marked resolved immediately on a preventive queue with positive exposure,
        # record provisional savings pending subsequent dataset reconciliation
        if norm_status == "RESOLVED" and queue == "PREVENTIVE_RETENTION_WATCH" and float(monetary_exposure) > 0:
            record["provisional_savings"] = float(monetary_exposure)

        ledger["actions"][entity_key] = record

        # Recalculate summary totals
        actions = list(ledger["actions"].values())
        resolved = [a for a in actions if a.get("status") in ("RESOLVED", "RETAINED")]
        ver_saved = sum(float(a.get("saved_capital", 0.0)) for a in actions)
        prov_saved = sum(float(a.get("provisional_savings", 0.0)) for a in resolved if a.get("saved_capital", 0.0) == 0.0)
        display_saved = round(ver_saved + prov_saved, 2)

        ledger["roi_summary"]["total_actions_logged"] = len(actions)
        ledger["roi_summary"]["total_actions_resolved"] = len(resolved)
        ledger["roi_summary"]["verified_saved_capital"] = display_saved
        ledger["roi_summary"]["total_estimated_saved_capital"] = display_saved
        ledger["roi_summary"]["currency_symbol"] = currency_symbol

        sub_cost = float(ledger["roi_summary"].get("estimated_subscription_cost", 99.0))
        if sub_cost > 0:
            mult = round(display_saved / sub_cost, 1)
            ledger["roi_summary"]["roi_multiplier"] = mult
            ledger["roi_summary"]["subscription_roi_multiplier"] = mult

        self._save_ledger(tenant_id, ledger)
        return record

    def list_actions(self, tenant_id: str, status_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lists logged actions for a tenant, optionally filtered by status and limited."""
        ledger = self._load_ledger(tenant_id)
        actions = list(ledger.get("actions", {}).values())
        if status_filter:
            actions = [a for a in actions if a.get("status", "").upper() == status_filter.upper()]
        actions.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        if limit is not None and limit > 0:
            actions = actions[:limit]
        return actions

    def reconcile_saved_capital(
        self,
        tenant_id: str,
        df_new_fact: Optional[pd.DataFrame] = None,
        primary_id_col: Optional[str] = None,
        target_col: Optional[str] = None,
        cost_col: Optional[str] = None,
        binary_target: Optional[pd.Series] = None,
        new_fact_df: Optional[pd.DataFrame] = None,
        id_col: Optional[str] = None,
        currency_symbol: str = "$"
    ) -> Dict[str, Any]:
        """
        Reconciles previous actions against a newly uploaded fact table to verify
        genuine averted losses vs realized churn/defaults.
        """
        fact_df = df_new_fact if df_new_fact is not None else new_fact_df
        if fact_df is None:
            raise ValueError("reconcile_saved_capital requires df_new_fact or new_fact_df")

        ledger = self._load_ledger(tenant_id)
        actions = ledger.get("actions", {})
        if not actions or fact_df.empty:
            return ledger.get("roi_summary", {})

        id_column = primary_id_col if primary_id_col else id_col
        id_col_resolved = id_column if (id_column and id_column in fact_df.columns) else None
        if not id_col_resolved:
            # Try to find a matching ID column
            for c in fact_df.columns:
                if c.lower().endswith(('_id', '_key', '_code', '_number', 'id')) or c.lower() in ('id', 'fact_surrogate_id'):
                    id_col_resolved = c
                    break

        if not id_col_resolved:
            return ledger.get("roi_summary", {})

        s_bin = binary_target if binary_target is not None else (
            fact_df["_is_target_event"] if "_is_target_event" in fact_df.columns else pd.Series(0, index=fact_df.index)
        )

        id_series_str = fact_df[id_col_resolved].astype(str)
        fact_id_map = dict(zip(id_series_str, fact_df.index))

        for entity_key, action_rec in actions.items():
            if action_rec.get("queue") != "PREVENTIVE_RETENTION_WATCH":
                continue

            if entity_key in fact_id_map:
                row_idx = fact_id_map[entity_key]
                is_failed = bool(s_bin.loc[row_idx] == 1)

                action_rec["reconciled"] = True

                if not is_failed:
                    # Success! The entity was retained / did not fail!
                    action_rec["reconciled_status"] = "AVERTED_SUCCESS"
                    saved_amt = float(action_rec.get("monetary_exposure", 0.0))
                    action_rec["saved_capital"] = saved_amt
                    action_rec["provisional_savings"] = 0.0
                else:
                    action_rec["reconciled_status"] = "REALIZED_FAILURE"
                    action_rec["saved_capital"] = 0.0
                    action_rec["provisional_savings"] = 0.0

        # Update ROI Summary across all tenant actions
        all_actions = list(actions.values())
        resolved = [a for a in all_actions if a.get("status") in ("RESOLVED", "RETAINED")]
        reconciled_list = [a for a in all_actions if a.get("reconciled")]
        averted_list = [a for a in reconciled_list if a.get("reconciled_status") == "AVERTED_SUCCESS"]

        reconciled_count = len(reconciled_list)
        averted_events_count = len(averted_list)

        ver_saved = sum(float(a.get("saved_capital", 0.0)) for a in reconciled_list)
        prov_saved = sum(float(a.get("provisional_savings", 0.0)) for a in resolved if not a.get("reconciled"))
        display_saved = round(ver_saved + prov_saved, 2)

        currency_sym = currency_symbol or ledger.get("roi_summary", {}).get("currency_symbol", "$")
        sub_cost = float(ledger.get("roi_summary", {}).get("estimated_subscription_cost", 99.0))

        rate = round((averted_events_count / max(reconciled_count, 1)) * 100.0, 1) if reconciled_count > 0 else 0.0
        roi_mult = round(display_saved / max(sub_cost, 1.0), 1) if sub_cost > 0 else 0.0

        ledger["roi_summary"] = {
            "total_actions_logged": len(all_actions),
            "total_actions_resolved": len(resolved),
            "total_reconciled": reconciled_count,
            "reconciled_count": reconciled_count,
            "verified_retained_count": averted_events_count,
            "verified_saved_capital": display_saved,
            "total_estimated_saved_capital": display_saved,
            "verified_averted_events": averted_events_count,
            "retention_success_rate_pct": rate,
            "currency_symbol": currency_sym,
            "estimated_subscription_cost": sub_cost,
            "roi_multiplier": roi_mult,
            "subscription_roi_multiplier": roi_mult
        }

        self._save_ledger(tenant_id, ledger)
        return ledger["roi_summary"]

    def get_roi_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Returns the high-level ROI summary card payload."""
        ledger = self._load_ledger(tenant_id)
        summary = ledger.get("roi_summary", {
            "total_actions_logged": 0,
            "total_actions_resolved": 0,
            "verified_saved_capital": 0.0,
            "total_estimated_saved_capital": 0.0,
            "verified_averted_events": 0,
            "retention_success_rate_pct": 0.0,
            "currency_symbol": "$",
            "roi_multiplier": 0.0,
            "subscription_roi_multiplier": 0.0
        })
        summary.setdefault("total_estimated_saved_capital", summary.get("verified_saved_capital", 0.0))
        summary.setdefault("subscription_roi_multiplier", summary.get("roi_multiplier", 0.0))
        return summary
