"""Isolated FastAPI Router for Stage 9: AI Boardroom Decision Judge."""
from typing import Any, Callable, Dict, List
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field


class BoardroomDiscussRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1500, description="Founder's open-ended business question, team debate, CapEx pitch, or follow-up")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Prior conversation turns for multi-turn context carry-over")
    target_lang: str = Field("en", max_length=12, description="Optional target language code (supports all 43 world languages)")


def build_boardroom_router(
    *,
    resolve_staging_out: Callable,
    enforce_tenant_access: Callable,
    get_cached_decision_engine: Callable,
) -> APIRouter:
    router = APIRouter(tags=["Stage 9 AI Boardroom"])

    @router.get("/api/v1/boardroom/starters/{run_id}")
    def get_boardroom_starters(run_id: str, request: Request, lang: str = Query("en")) -> Dict[str, Any]:
        staging_out, run_tenant = resolve_staging_out(run_id)
        enforce_tenant_access(request, run_tenant, run_id=run_id, allow_public_benchmark=True)
        try:
            from ..boardroom_decision_judge import BoardroomDecisionJudge
            eng = get_cached_decision_engine(staging_out)
            judge = BoardroomDecisionJudge(str(staging_out), engine=eng)
            starters = judge.get_discussion_starters()

            code = str(lang or "en").strip()
            if code not in ("en", "hi") and starters:
                try:
                    from ..global_i18n_engine import normalize_lang_code, translate_string_map
                    norm_c = normalize_lang_code(code)
                    if norm_c not in ("en", "hi"):
                        s_map = {}
                        for i, st in enumerate(starters):
                            s_map[f"t{i}"] = st["tag_en"]
                            s_map[f"p{i}"] = st["prompt_en"]
                        tr_map, _ = translate_string_map(s_map, norm_c, max_workers=4)
                        for i, st in enumerate(starters):
                            st["tag_en"] = tr_map.get(f"t{i}", st["tag_en"])
                            st["prompt_en"] = tr_map.get(f"p{i}", st["prompt_en"])
                except Exception:
                    pass

            return {
                "status": "success",
                "run_id": run_id,
                "model_roc_auc": eng.model_metrics.get("roc_auc"),
                "blind_backtest_badge": eng.model_metrics.get("blind_backtest_badge"),
                "rows_audited": int(len(eng.df_full)),
                "starters": starters,
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Boardroom starters error: {exc}")

    @router.post("/api/v1/boardroom/discuss/{run_id}")
    def discuss_in_boardroom(run_id: str, req: BoardroomDiscussRequest, request: Request) -> Dict[str, Any]:
        staging_out, run_tenant = resolve_staging_out(run_id)
        enforce_tenant_access(request, run_tenant, run_id=run_id, allow_public_benchmark=True)
        try:
            from ..boardroom_decision_judge import BoardroomDecisionJudge
            eng = get_cached_decision_engine(staging_out)
            judge = BoardroomDecisionJudge(str(staging_out), engine=eng)
            result = judge.discuss(message=req.message, history=req.history)
            result["run_id"] = run_id

            code = str(req.target_lang or "en").strip()
            if code not in ("en", "hi"):
                try:
                    from ..global_i18n_engine import normalize_lang_code, translate_string_map
                    norm_c = normalize_lang_code(code)
                    if norm_c not in ("en", "hi"):
                        flat: Dict[str, str] = {
                            "v_badge": result["verdict"]["badge_en"],
                            "v_hl": result["verdict"]["headline_en"],
                        }
                        for i, s in enumerate(result["evidence"]["proven_true_en"]):
                            flat[f"pt_{i}"] = s
                        for i, s in enumerate(result["evidence"]["wrong_or_risky_en"]):
                            flat[f"wr_{i}"] = s
                        for i, s in enumerate(result["evidence"]["blind_spots_en"]):
                            flat[f"bs_{i}"] = s
                        for i, s in enumerate(result["action_plan_en"]):
                            flat[f"ap_{i}"] = s
                        for i, s in enumerate(result["follow_up_prompts_en"]):
                            flat[f"fu_{i}"] = s
                        for i, r in enumerate(result["comparison_scorecard"]):
                            flat[f"sc_{i}"] = r["option_en"]
                        tr_map, _ = translate_string_map(flat, norm_c, max_workers=6)
                        result["verdict"]["badge_en"] = tr_map.get("v_badge", result["verdict"]["badge_en"])
                        result["verdict"]["headline_en"] = tr_map.get("v_hl", result["verdict"]["headline_en"])
                        result["evidence"]["proven_true_en"] = [tr_map.get(f"pt_{i}", s) for i, s in enumerate(result["evidence"]["proven_true_en"])]
                        result["evidence"]["wrong_or_risky_en"] = [tr_map.get(f"wr_{i}", s) for i, s in enumerate(result["evidence"]["wrong_or_risky_en"])]
                        result["evidence"]["blind_spots_en"] = [tr_map.get(f"bs_{i}", s) for i, s in enumerate(result["evidence"]["blind_spots_en"])]
                        result["action_plan_en"] = [tr_map.get(f"ap_{i}", s) for i, s in enumerate(result["action_plan_en"])]
                        result["follow_up_prompts_en"] = [tr_map.get(f"fu_{i}", s) for i, s in enumerate(result["follow_up_prompts_en"])]
                        for i, r in enumerate(result["comparison_scorecard"]):
                            r["option_en"] = tr_map.get(f"sc_{i}", r["option_en"])
                except Exception:
                    pass

            return result
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Boardroom judge error: {exc}")

    return router
