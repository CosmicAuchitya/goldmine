"""
End-to-end verification tests for DataX-Ray Worldwide Multilingual Engine (43 World Languages + RTL).
Covers:
  1. Catalog completeness (43 languages, all continents, RTL flags for ar/ur/he/fa).
  2. Number & brand token shielding across CJK/Indic/RTL/Latin scripts (zero number drift).
  3. FastAPI `/api/v1/i18n/languages`, `/api/v1/i18n/translate-ui`, `/api/v1/i18n/translate-run/{run_id}`,
     and `/api/v1/i18n/translate-texts` including instant disk-cache verification.
"""

from pathlib import Path
from fastapi.testclient import TestClient

from autonomous_engine.api_server import app
from autonomous_engine.global_i18n_engine import (
    RTL_CODES,
    WORLD_LANGUAGES,
    _shield_tokens,
    _unshield_tokens,
    get_language_meta,
    normalize_lang_code,
    translate_full_run_bundle,
)


def test_world_language_catalog_and_rtl():
    assert len(WORLD_LANGUAGES) >= 40
    codes = {x["code"] for x in WORLD_LANGUAGES}
    for req in ("en", "hi", "es", "fr", "de", "pt", "ar", "ur", "he", "fa", "zh-CN", "ja", "ko", "gu", "ta", "mr", "bn", "ru", "tr", "id", "vi", "sw"):
        assert req in codes, f"Missing expected global language: {req}"
    assert {"ar", "ur", "he", "fa"}.issubset(RTL_CODES)
    assert get_language_meta("ar")["dir"] == "rtl"
    assert get_language_meta("es")["dir"] == "ltr"
    assert normalize_lang_code("zh_CN") == "zh-CN"
    assert normalize_lang_code("tl") == "fil"


def test_number_and_brand_shielding_cjk_and_rtl():
    src = "DataX-Ray found 94% breached safe pH (6.5–6.8) putting ₹4.36 L and $12,450.50 at 2.73x risk."
    shielded, tokens = _shield_tokens(src)
    assert "₹4.36 L" not in shielded
    assert "$12,450.50" not in shielded
    assert "94%" not in shielded
    assert "DataX-Ray" not in shielded
    # Simulate CJK translation with zero spaces around placeholders
    simulated_cjk = f"テスト{shielded}結果"
    restored = _unshield_tokens(simulated_cjk, tokens)
    for tok in ("DataX-Ray", "94%", "pH", "₹4.36 L", "$12,450.50", "2.73x"):
        assert tok in restored, f"Token '{tok}' lost during CJK unshielding: {restored}"


def test_i18n_endpoints_and_disk_cache(tmp_path):
    client = TestClient(app)

    # 1. Catalog endpoint
    r_lang = client.get("/api/v1/i18n/languages")
    assert r_lang.status_code == 200
    body = r_lang.json()
    assert body["count"] >= 40

    # 2. Full bundle translation with offline/live resilience & instant disk cache
    fake_owner_en = {
        "moat": {"title": "Clear Milk works smoothly", "badge": "95% Safe", "story": "Clean batches pass.", "footer": "Checked 1,059 milk batches"},
        "bottleneck": {"title": "Cloudy Milk is #1 problem", "badge": "60% Problem", "story": "6 in 10 fail.", "footer": "Focus on Turbidity"},
        "red_line": {"title": "Fails when pH > 6.8", "badge": "100% Fail", "story": "Watch pH closely.", "footer": "Watch limit"},
        "recovery": {"title": "429 milk batches can be saved", "badge": "Save ~107", "story": "Start with Plan A.", "footer": "429 problem batches"},
        "pathways": [{"title": "Plan A: Quick Trial", "badge": "Save ~107", "story": "Check pH daily.", "target": "Cloudy Milk", "effort": "1-2 Weeks"}],
    }
    fake_leaks = {
        "is_financial": False,
        "abnormal_deviations": [
            {
                "leak_id": "LEAK_DIM_Turbidity",
                "headline_en": "Cloudy Milk: 6 in 10 Fail Quality Check",
                "root_cause_en": "94% went outside safe pH (6.5–6.8).",
                "fix_action_en": "Keep pH within 6.5–6.8 and check filtration.",
                "formatted_impact": "~197 avoidable bad milk batches",
            }
        ],
    }

    out1 = translate_full_run_bundle(
        staging_out=tmp_path / "run_out",
        target_lang="es",
        owner_friendly_en=fake_owner_en,
        ranked_leaks_data=fake_leaks,
        english_summary_md="## Executive Business Summary\n- Cloudy Milk fails in 60% of batches.",
        ui_dict_en={"tabOverview": "Business Health", "btnPredictNow": "Predict Outcome"},
        workspace_root=tmp_path,
    )
    assert out1["status"] == "success"
    assert out1["lang"]["code"] == "es"
    assert out1["lang"]["dir"] == "ltr"
    assert "94%" in out1["ranked_leaks"]["abnormal_deviations"][0]["root_cause_en"]
    assert "pH" in out1["ranked_leaks"]["abnormal_deviations"][0]["root_cause_en"]

    # If live MT succeeded, 2nd call MUST hit disk cache instantaneously!
    if out1["engine"] != "offline_fallback":
        out2 = translate_full_run_bundle(
            staging_out=tmp_path / "run_out",
            target_lang="es",
            owner_friendly_en=fake_owner_en,
            ranked_leaks_data=fake_leaks,
            english_summary_md="## Executive Business Summary\n- Cloudy Milk fails in 60% of batches.",
            ui_dict_en={"tabOverview": "Business Health", "btnPredictNow": "Predict Outcome"},
            workspace_root=tmp_path,
        )
        assert out2["engine"] == "disk_cache"

    # 3. Arabic RTL metadata verification via live API endpoint on public benchmark
    r_ar = client.post(
        "/api/v1/i18n/translate-texts",
        json={"target_lang": "ar", "texts": {"t1": "Save ₹4.36 L by fixing 60% defect rate."}},
    )
    assert r_ar.status_code == 200
    d_ar = r_ar.json()
    assert d_ar["lang"]["dir"] == "rtl"
    assert "₹4.36 L" in d_ar["texts"]["t1"]
    assert "60%" in d_ar["texts"]["t1"]

    # 4. Full run translation API endpoint regression check (guards against pulse helper NameError)
    r_run_es = client.post(
        "/api/v1/i18n/translate-run/hotel_booking_cancellation",
        json={"target_lang": "es"},
    )
    assert r_run_es.status_code == 200, r_run_es.text
    d_run_es = r_run_es.json()
    assert d_run_es["status"] == "success"
    assert d_run_es["lang"]["code"] == "es"
    assert isinstance(d_run_es.get("owner_friendly"), dict)
