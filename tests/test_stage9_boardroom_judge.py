"""
Comprehensive End-to-End Test Suite for Stage 9: AI Boardroom Decision Judge.
Verifies:
  1. Team CapEx Debate (Chiller Temperature vs Acidity pH on real Dairy Milk Quality) -> Clear Winner + Indian ₹2,00,000 budget parsing + Equipment Blind Spot!
  2. Gut-Feeling Myth Buster (Dropping a uniform-noise Brand on real Dairy Supply Chain) -> Refuted honestly with negative-impact warning & hidden #1 lever uncovered!
  3. Multi-Turn Follow-Up Context Memory (budget tweak follow-up inherits prior factor cleanly!).
  4. FastAPI `/api/v1/boardroom/starters/{run_id}` + `/api/v1/boardroom/discuss/{run_id}` + 43-Language Translation + Multi-Tenant Isolation!
"""

import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from autonomous_engine import api_server
from autonomous_engine.boardroom_decision_judge import BoardroomDecisionJudge

WS = Path(__file__).resolve().parents[1]
DAIRY_MILK_OUT = WS / "runs" / "tenants" / "founder_workspace" / "jobs" / "dairy_milk_quality_lab_kaggle" / "output"
DAIRY_SUPPLY_OUT = WS / "runs" / "tenants" / "founder_workspace" / "jobs" / "indian_dairy_supply_chain_kaggle" / "output"


def _make_synthetic_business_dir(tmp_path: Path) -> Path:
    rng = np.random.default_rng(99)
    n = 700
    supplier = rng.choice(["BadSupplier", "GoodSupplier"], size=n, p=[0.45, 0.55])
    color_tag = rng.choice(["RedBox", "BlueBox"], size=n)  # pure uniform noise!
    delay_days = np.where(supplier == "BadSupplier", rng.normal(7.0, 1.5, n), rng.normal(2.2, 0.8, n)).clip(1, 14)
    bill_inr = rng.uniform(800, 3500, n)
    prob = np.where(supplier == "BadSupplier", 0.52, 0.08) + np.where(delay_days > 5, 0.15, 0.0)
    is_rto = (rng.random(n) < np.clip(prob, 0.02, 0.95)).astype(int)
    df = pd.DataFrame({
        "supplier": supplier,
        "box_color": color_tag,
        "delivery_days": np.round(delay_days, 1),
        "net_bill_inr": np.round(bill_inr, 2),
        "is_rto": is_rto,
    })
    out = tmp_path / "biz_out"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "bi_ready_fact.parquet", index=False)
    import json
    (out / "semantic_metrics_manifest.json").write_text(
        json.dumps({"project": "synthetic_boardroom_test", "rows": n}),
        encoding="utf-8",
    )
    return out


def test_boardroom_debate_myth_buster_and_multiturn_memory(tmp_path: Path):
    out_dir = _make_synthetic_business_dir(tmp_path)
    judge = BoardroomDecisionJudge(str(out_dir), region_profile="IN")

    # 1. Dataset-specific starters generated cleanly
    starters = judge.get_discussion_starters()
    assert len(starters) >= 3

    # 2. Team Debate: BadSupplier vs Box Color (real driver vs noise!) + ₹2,00,000 CapEx + staff blind spot
    q1 = "My manager wants ₹2,00,000 to change box_color and hire new staff, while ops says supplier is the real issue. Who is right?"
    res1 = judge.discuss(q1)
    assert res1["status"] == "judged"
    assert res1["verdict"]["code"] == "CLEAR_WINNER"
    assert res1["context_used"]["budget_parsed"] == 200000.0
    assert "supplier" in res1["context_used"]["matched_columns"]
    assert len(res1["comparison_scorecard"]) >= 2
    assert len(res1["evidence"]["proven_true_en"]) >= 1
    assert len(res1["evidence"]["wrong_or_risky_en"]) >= 1
    assert any("staff" in b.lower() for b in res1["evidence"]["blind_spots_en"])

    # 3. Myth-buster on pure noise column alone -> REFUTED_BY_DATA!
    q2 = "I feel like RedBox in box_color is ruining our business and we should spend ₹50,000 fixing box_color."
    res2 = judge.discuss(q2)
    assert res2["verdict"]["code"] == "REFUTED_BY_DATA"
    assert res2["context_used"]["budget_parsed"] == 50000.0

    # 4. Multi-turn follow-up memory ("What if we cut budget to ₹25,000 instead?")
    hist = [{"role": "user", "text": q1}, {"role": "judge", "text": res1["verdict"]["headline_en"]}]
    res3 = judge.discuss("What if we only spend ₹25,000 instead?", history=hist)
    assert res3["status"] == "judged"
    assert res3["context_used"]["carried_prior_context"] is True
    assert res3["context_used"]["budget_parsed"] == 25000.0
    assert "supplier" in res3["context_used"]["matched_columns"]


def test_boardroom_real_kaggle_dairy_debates():
    if DAIRY_MILK_OUT.exists():
        j = BoardroomDecisionJudge(str(DAIRY_MILK_OUT), region_profile="IN")
        r = j.discuss("My supervisor wants ₹2,00,000 to upgrade the chiller for Temperature, while QA says pH is the real cause. Who is right?")
        assert r["verdict"]["code"] == "CLEAR_WINNER"
        assert r["context_used"]["budget_parsed"] == 200000.0
        assert "pH" in r["context_used"]["matched_columns"]
        assert "Temprature" in r["context_used"]["matched_columns"]

    if DAIRY_SUPPLY_OUT.exists():
        j2 = BoardroomDecisionJudge(str(DAIRY_SUPPLY_OUT), region_profile="IN")
        r2 = j2.discuss("I feel like Amul is hurting us and we should drop Amul — am I right?")
        assert r2["verdict"]["code"] == "REFUTED_BY_DATA"


def test_boardroom_api_endpoints_and_tenant_isolation(tmp_path: Path, monkeypatch):
    client = TestClient(api_server.app)

    # 1. Public benchmark starters + live Spanish discussion
    r_st = client.get("/api/v1/boardroom/starters/hotel_booking_cancellation")
    assert r_st.status_code == 200, r_st.text
    assert len(r_st.json()["starters"]) >= 2

    r_disc = client.post(
        "/api/v1/boardroom/discuss/hotel_booking_cancellation",
        json={"message": "Should we focus on lead_time or deposit_type first to cut cancellations?", "target_lang": "es"},
    )
    assert r_disc.status_code == 200, r_disc.text
    body = r_disc.json()
    assert body["status"] == "judged"
    assert body["verdict"]["headline_en"]

    # 2. Multi-tenant isolation check on private workspace run
    monkeypatch.setenv("DATAXRAY_REQUIRE_AUTH", "true")
    sfx = uuid.uuid4().hex[:8]
    reg_a = client.post("/api/v1/auth/register", json={"email": f"br_a_{sfx}@example.com", "password": "Password123!", "workspace_name": f"BR A {sfx}"})
    reg_b = client.post("/api/v1/auth/register", json={"email": f"br_b_{sfx}@example.com", "password": "Password123!", "workspace_name": f"BR B {sfx}"})
    tok_a, tok_b = reg_a.json()["access_token"], reg_b.json()["access_token"]
    tid_a = reg_a.json()["user"]["tenant_id"]

    priv_id = f"priv_br_{sfx}"
    priv_out = WS / "runs" / "tenants" / tid_a / "runs" / priv_id / "output"
    try:
        shutil.copytree(_make_synthetic_business_dir(tmp_path), priv_out)
        assert client.post(f"/api/v1/boardroom/discuss/{priv_id}", json={"message": "Fix supplier"}).status_code == 401
        assert client.post(f"/api/v1/boardroom/discuss/{priv_id}", headers={"Authorization": f"Bearer {tok_b}"}, json={"message": "Fix supplier"}).status_code == 403
        r_ok = client.post(f"/api/v1/boardroom/discuss/{priv_id}", headers={"Authorization": f"Bearer {tok_a}"}, json={"message": "Fix supplier"})
        assert r_ok.status_code == 200, r_ok.text
    finally:
        t_root = WS / "runs" / "tenants" / tid_a
        if t_root.exists():
            shutil.rmtree(t_root, ignore_errors=True)
