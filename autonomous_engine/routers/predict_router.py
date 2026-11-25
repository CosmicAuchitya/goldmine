"""Isolated FastAPI Router for Stage 8.3 Predictive Decision Lab & Outcome Accountability Tracker."""
from typing import Any, Callable, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field


class DecisionSimulateRequest(BaseModel):
    decision_text: Optional[str] = Field(None, max_length=600, description="Plain English or Hinglish business decision (supports single or 'A AND B' combos)")
    decision: Optional[Dict[str, Any]] = Field(None, description="Optional single structured decision spec")
    decisions: Optional[List[Dict[str, Any]]] = Field(None, description="Optional list of 2-4 simultaneous levers for zero-double-counting combo simulation")
    implementation_cost: Optional[float] = Field(0.0, ge=0.0, description="Optional one-time or rollout budget subtracted from net gain across all Monte Carlo draws")
    target_lang: str = Field("en", max_length=12, description="Optional target language code (supports all 43 world languages)")


class DecisionCommitRequest(BaseModel):
    baseline_run_id: str = Field(..., min_length=3, max_length=80)
    simulation: Dict[str, Any] = Field(..., description="Completed simulation response payload from /api/v1/predict/simulate/{run_id}")
    tenant_id: Optional[str] = Field(None, max_length=64)


class DecisionVerifyRequest(BaseModel):
    actual_run_id: str = Field(..., min_length=3, max_length=80, description="Audited next-period run_id to verify actual physical outcome against")
    tenant_id: Optional[str] = Field(None, max_length=64)


def build_predict_router(
    *,
    resolve_staging_out: Callable,
    enforce_tenant_access: Callable,
    require_role: Callable,
    sanitize_tenant_id: Callable,
    get_cached_decision_engine: Callable,
    decision_outcome_tracker: Any,
) -> APIRouter:
    router = APIRouter(tags=["Stage 8 Predictive Decision Lab"])

    @router.get("/api/v1/predict/overview/{run_id}")
    def get_decision_predictor_overview(run_id: str, request: Request, lang: str = Query("en")) -> Dict[str, Any]:
        staging_out, tenant_id = resolve_staging_out(run_id)
        enforce_tenant_access(request, tenant_id, run_id=run_id, allow_public_benchmark=True)
        try:
            eng = get_cached_decision_engine(staging_out)
            data = eng.get_model_overview_and_presets()
            data["run_id"] = run_id

            code = str(lang or "en").strip()
            if code not in ("en", "hi"):
                try:
                    import copy
                    from ..global_i18n_engine import normalize_lang_code, translate_string_map
                    norm_c = normalize_lang_code(code)
                    if norm_c not in ("en", "hi"):
                        data = copy.deepcopy(data)
                        flat: Dict[str, str] = {}
                        for i, p in enumerate(data.get("presets") or []):
                            if p.get("title_en"):
                                flat[f"pt_{i}"] = str(p["title_en"])
                            if p.get("subtitle_en"):
                                flat[f"ps_{i}"] = str(p["subtitle_en"])
                        badge = (data.get("model_metrics") or {}).get("blind_backtest_badge")
                        if isinstance(badge, dict) and badge.get("label_en"):
                            flat["badge_en"] = str(badge["label_en"])
                        if flat:
                            tr_map, _ = translate_string_map(flat, norm_c, max_workers=6)
                            for i, p in enumerate(data.get("presets") or []):
                                if f"pt_{i}" in tr_map:
                                    p["title_en"] = tr_map[f"pt_{i}"]
                                if f"ps_{i}" in tr_map:
                                    p["subtitle_en"] = tr_map[f"ps_{i}"]
                            if isinstance(badge, dict) and "badge_en" in tr_map:
                                badge["label_en"] = tr_map["badge_en"]
                except Exception:
                    pass

            return data
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Predictive model error: {exc}")

    @router.post("/api/v1/predict/simulate/{run_id}")
    def simulate_client_decision(run_id: str, req: DecisionSimulateRequest, request: Request) -> Dict[str, Any]:
        staging_out, tenant_id = resolve_staging_out(run_id)
        enforce_tenant_access(request, tenant_id, run_id=run_id, allow_public_benchmark=True)
        if not req.decision and not (req.decisions and len(req.decisions) > 0) and not (req.decision_text and req.decision_text.strip()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide 'decision_text', 'decision', or 'decisions' list.")
        try:
            eng = get_cached_decision_engine(staging_out)
            res = eng.simulate_decision(
                decision=req.decision,
                decision_text=req.decision_text,
                decisions=req.decisions,
                implementation_cost=float(req.implementation_cost or 0.0),
            )
            res["run_id"] = run_id

            code = str(req.target_lang or "en").strip()
            if code not in ("en", "hi"):
                try:
                    from ..global_i18n_engine import normalize_lang_code, translate_string_map
                    norm_c = normalize_lang_code(code)
                    if norm_c not in ("en", "hi"):
                        flat: Dict[str, str] = {}
                        for fld in ("verdict_en", "label_en"):
                            if res.get(fld):
                                flat[fld] = str(res[fld])
                        dec = res.get("decision")
                        if isinstance(dec, dict) and dec.get("label_en"):
                            flat["dec_lbl"] = str(dec["label_en"])
                        be = res.get("break_even_analysis")
                        if isinstance(be, dict) and be.get("summary_en"):
                            flat["be_sum"] = str(be["summary_en"])
                        wloss = res.get("why_loss_could_happen")
                        if isinstance(wloss, dict) and wloss.get("en"):
                            flat["wl_en"] = str(wloss["en"])
                        dr_aud = res.get("doubly_robust_audit")
                        if isinstance(dr_aud, dict) and dr_aud.get("summary_en"):
                            flat["dr_en"] = str(dr_aud["summary_en"])
                        for i, seg in enumerate((res.get("where_it_helps_most") or [])[:5]):
                            if isinstance(seg, dict) and seg.get("note_en"):
                                flat[f"wh_{i}"] = str(seg["note_en"])
                        for i, seg in enumerate((res.get("no_gain_zones") or [])[:5]):
                            if isinstance(seg, dict) and seg.get("note_en"):
                                flat[f"ng_{i}"] = str(seg["note_en"])
                        if flat:
                            tr_map, _ = translate_string_map(flat, norm_c, max_workers=6)
                            for fld in ("verdict_en", "label_en"):
                                if fld in tr_map:
                                    res[fld] = tr_map[fld]
                            if isinstance(dec, dict) and "dec_lbl" in tr_map:
                                dec["label_en"] = tr_map["dec_lbl"]
                            if isinstance(be, dict) and "be_sum" in tr_map:
                                be["summary_en"] = tr_map["be_sum"]
                            if isinstance(wloss, dict) and "wl_en" in tr_map:
                                wloss["en"] = tr_map["wl_en"]
                            if isinstance(dr_aud, dict) and "dr_en" in tr_map:
                                dr_aud["summary_en"] = tr_map["dr_en"]
                            for i, seg in enumerate((res.get("where_it_helps_most") or [])[:5]):
                                if isinstance(seg, dict) and f"wh_{i}" in tr_map:
                                    seg["note_en"] = tr_map[f"wh_{i}"]
                            for i, seg in enumerate((res.get("no_gain_zones") or [])[:5]):
                                if isinstance(seg, dict) and f"ng_{i}" in tr_map:
                                    seg["note_en"] = tr_map[f"ng_{i}"]
                except Exception:
                    pass

            return res
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Decision simulation error: {exc}")

    @router.post("/api/v1/predict/commitments", status_code=status.HTTP_201_CREATED)
    def commit_predicted_decision(req: DecisionCommitRequest, request: Request) -> Dict[str, Any]:
        require_role(request, "analyst")
        _, run_tenant = resolve_staging_out(req.baseline_run_id)
        enforce_tenant_access(request, run_tenant, run_id=req.baseline_run_id, allow_public_benchmark=True)
        auth_tenant = getattr(request.state, "auth_tenant_id", None)
        eff_tid = sanitize_tenant_id(auth_tenant or req.tenant_id or "founder_workspace")
        try:
            return decision_outcome_tracker.commit_decision(
                tenant_id=eff_tid,
                baseline_run_id=req.baseline_run_id,
                simulation_payload=req.simulation,
            )
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    @router.get("/api/v1/predict/commitments")
    def list_predicted_commitments(request: Request, tenant_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        auth_tenant = getattr(request.state, "auth_tenant_id", None)
        eff_tid = sanitize_tenant_id(auth_tenant or tenant_id or "founder_workspace")
        if auth_tenant and tenant_id and sanitize_tenant_id(tenant_id) != sanitize_tenant_id(auth_tenant) and not getattr(request.state, "is_admin", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Cross-tenant commitments access denied.")
        return decision_outcome_tracker.list_commitments(eff_tid)

    @router.post("/api/v1/predict/commitments/{commitment_id}/verify")
    def verify_committed_decision(commitment_id: str, req: DecisionVerifyRequest, request: Request) -> Dict[str, Any]:
        require_role(request, "analyst")
        auth_tenant = getattr(request.state, "auth_tenant_id", None)
        eff_tid = sanitize_tenant_id(auth_tenant or req.tenant_id or "founder_workspace")

        comm = decision_outcome_tracker.get_commitment(eff_tid, commitment_id)
        if not comm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Commitment '{commitment_id}' not found in your workspace.")

        base_out, base_tenant = resolve_staging_out(comm["baseline_run_id"])
        enforce_tenant_access(request, base_tenant, run_id=comm["baseline_run_id"], allow_public_benchmark=True)

        act_out, act_tenant = resolve_staging_out(req.actual_run_id)
        enforce_tenant_access(request, act_tenant, run_id=req.actual_run_id, allow_public_benchmark=True)

        try:
            return decision_outcome_tracker.verify_commitment_against_actual(
                tenant_id=eff_tid,
                commitment_id=commitment_id,
                actual_run_id=req.actual_run_id,
                actual_output_dir=act_out,
                baseline_output_dir=base_out,
            )
        except KeyError as ke:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Outcome verification error: {exc}")

    @router.delete("/api/v1/predict/commitments/{commitment_id}")
    def delete_committed_decision(commitment_id: str, request: Request, tenant_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        require_role(request, "analyst")
        auth_tenant = getattr(request.state, "auth_tenant_id", None)
        eff_tid = sanitize_tenant_id(auth_tenant or tenant_id or "founder_workspace")
        deleted = decision_outcome_tracker.delete_commitment(eff_tid, commitment_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found in your workspace.")
        return {"status": "deleted", "commitment_id": commitment_id}

    return router
