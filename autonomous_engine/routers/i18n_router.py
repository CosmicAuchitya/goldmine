"""Isolated FastAPI Router for 43 World Languages + Automatic RTL Translation."""
import json
from pathlib import Path
from typing import Any, Callable, Dict
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


class TranslateUiRequest(BaseModel):
    target_lang: str = Field(..., min_length=2, max_length=12)
    ui_dict: Dict[str, str] = Field(default_factory=dict)


class TranslateRunRequest(BaseModel):
    target_lang: str = Field(..., min_length=2, max_length=12)
    ui_dict: Dict[str, str] = Field(default_factory=dict)


class TranslateTextsRequest(BaseModel):
    target_lang: str = Field(..., min_length=2, max_length=12)
    texts: Dict[str, str] = Field(default_factory=dict)


def build_i18n_router(
    *,
    workspace_root: Path,
    resolve_staging_out: Callable,
    enforce_tenant_access: Callable,
    extract_executive_pulse: Callable,
) -> APIRouter:
    router = APIRouter(tags=["Worldwide Multilingual i18n"])

    @router.get("/api/v1/i18n/languages")
    def list_world_languages() -> Dict[str, Any]:
        from ..global_i18n_engine import WORLD_LANGUAGES
        return {
            "status": "success",
            "count": len(WORLD_LANGUAGES),
            "languages": WORLD_LANGUAGES,
        }

    @router.post("/api/v1/i18n/translate-ui")
    def translate_portal_ui(req: TranslateUiRequest) -> Dict[str, Any]:
        from ..global_i18n_engine import get_language_meta, normalize_lang_code, translate_ui_dictionary
        code = normalize_lang_code(req.target_lang)
        ui_tr, engine = translate_ui_dictionary(req.ui_dict, code, workspace_root)
        return {
            "status": "success",
            "lang": get_language_meta(code),
            "engine": engine,
            "ui_dict": ui_tr,
        }

    @router.post("/api/v1/i18n/translate-run/{run_id}")
    def translate_audited_run(run_id: str, req: TranslateRunRequest, request: Request) -> Dict[str, Any]:
        staging_out, run_tenant = resolve_staging_out(run_id)
        enforce_tenant_access(request, run_tenant, run_id=run_id, allow_public_benchmark=True)
        from ..global_i18n_engine import normalize_lang_code, translate_full_run_bundle

        code = normalize_lang_code(req.target_lang)
        manifest_data: Dict[str, Any] = {}
        m_path = staging_out / "semantic_metrics_manifest.json"
        if m_path.exists():
            try:
                manifest_data = json.loads(m_path.read_text(encoding="utf-8"))
            except Exception:
                manifest_data = {}
        plain_summary_text = ""
        s_path = staging_out / "PLAIN_BUSINESS_SUMMARY.md"
        if s_path.exists():
            try:
                plain_summary_text = s_path.read_text(encoding="utf-8")
            except Exception:
                plain_summary_text = ""
        pulse = extract_executive_pulse(staging_out, manifest_data, plain_summary_text)
        owner_en = (pulse.get("owner_friendly") or {}).get("en") or {}
        eng_md = pulse.get("english_summary_markdown") or plain_summary_text or ""

        rk_data = None
        rk_path = staging_out / "ranked_leaks_report.json"
        if rk_path.exists():
            try:
                rk_data = json.loads(rk_path.read_text(encoding="utf-8"))
            except Exception:
                rk_data = None

        return translate_full_run_bundle(
            staging_out=staging_out,
            target_lang=code,
            owner_friendly_en=owner_en,
            ranked_leaks_data=rk_data,
            english_summary_md=eng_md,
            ui_dict_en=req.ui_dict,
            workspace_root=workspace_root,
        )

    @router.post("/api/v1/i18n/translate-texts")
    def translate_dynamic_texts(req: TranslateTextsRequest) -> Dict[str, Any]:
        from ..global_i18n_engine import get_language_meta, normalize_lang_code, translate_string_map
        code = normalize_lang_code(req.target_lang)
        safe_map = {str(k)[:80]: str(v)[:2000] for k, v in list((req.texts or {}).items())[:40]}
        tr_map, engine = translate_string_map(safe_map, code, max_workers=6)
        return {
            "status": "success",
            "lang": get_language_meta(code),
            "engine": engine,
            "texts": tr_map,
        }

    return router
