"""
=============================================================================
STAGE 9: AI BOARDROOM DECISION JUDGE (PERSONAL CHIEF DATA SCIENTIST + CA)
=============================================================================
Allows any non-technical business owner to type or speak an open-ended business
thought, team debate, CapEx proposal, or gut-feeling hypothesis in plain language
(English, Hindi/Hinglish, or any of the 43 supported world languages), and returns
a brutally honest, 100% data-verified Boardroom Judgment:

  1. OVERALL VERDICT       — Supported / Partly True (Pivot) / Refuted / Option A vs B Winner
  2. PROVEN TRUE BY DATA   — Exact physical counts, "X in 10" ratios, ML driver weight & Stage 8.3 simulation
  3. WRONG / RISKY CLAIMS  — Courageously debunks team myths, random noise (p >= 0.05), confounders,
                             negative ROI budgets, and thin historical overlap (< 35% causal support)
  4. HONEST BLIND SPOTS    — Explicitly names external factors mentioned by the owner (staff morale,
                             competitors, vendor warranty, rent, local footfall) that are NOT in the data
  5. 14-DAY ACTION PLAN    — Concrete, low-risk pilot plan + multi-turn follow-up discussion memory

Zero-Hallucination & Zero-Sycophancy Architecture:
  - Every single number is computed live from physical DuckDB/Parquet fact rows + Stage 8.3
    Multi-Model Calibrated Causal ML (`PredictiveDecisionEngine`).
  - Never flatters or agrees blindly with the owner if the data shows random noise or net loss.
  - Works 100% deterministically in <1s with zero LLM quota failures, plus optional number-locked
    Gemini conversational synthesis when enabled.
=============================================================================
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from .decision_prediction_engine import PredictiveDecisionEngine, _fmt_money, _two_prop_p_value
    from .human_analyst_narrator import (
        clean_column_label,
        humanize_segment,
        infer_domain_vocab,
        multiplier_human_phrase,
        rate_out_of_ten_phrase,
    )
except ImportError:
    from decision_prediction_engine import PredictiveDecisionEngine, _fmt_money, _two_prop_p_value
    from human_analyst_narrator import (
        clean_column_label,
        humanize_segment,
        infer_domain_vocab,
        multiplier_human_phrase,
        rate_out_of_ten_phrase,
    )


# Semantic concept synonyms so natural owner language ("chiller", "sour", "cloudiness", "reviews", "late")
# maps cleanly onto real schema columns across industries!
SEMANTIC_CONCEPT_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "temperature": ("chiller", "cooling", "cold chain", "cold-chain", "fridge", "heat", "hot", "warm", "temp", "temprature", "temperature", "तापन", "तापमान", "चिलर", "ठंडा", "गर्म"),
    "ph": ("acidity", "acid", "sour", "spoiled", "spoilage", "curdle", "ph", "खट्टा", "फटना", "एसिडिटी"),
    "turbidity": ("cloudy", "cloudiness", "filtration", "filter", "dirty", "clarity", "turbidity", "धुंधला", "फिल्टर"),
    "fat": ("fat", "cream", "richness", "फैट", "क्रीम", "मलाई"),
    "odor": ("smell", "odor", "odour", "stink", "गंध", "बदबू"),
    "taste": ("taste", "flavor", "flavour", "स्वाद"),
    "colour": ("color", "colour", "shade", "white", "yellow", "रंग"),
    "online_delivery": ("online delivery", "delivery", "zomato delivery", "swiggy", "home delivery", "डिलीवरी", "ऑनलाइन डिलीवरी"),
    "table_booking": ("table booking", "reservation", "dine in", "dine-in", "booking", "टेबल बुकिंग", "रिज़र्वेशन"),
    "votes": ("reviews", "review", "votes", "feedback", "popularity", "रिव्यू", "वोट"),
    "price_cost": ("price", "pricing", "cost", "expensive", "cheap", "bill", "rate", "average cost", "price range", "दाम", "कीमत", "रेट", "बिल"),
    "discount": ("discount", "offer", "promo", "coupon", "markdown", "डिस्काउंट", "छूट", "ऑफ़र"),
    "delivery_time": ("late", "delay", "slow", "sla", "transit", "shipping time", "dispatch", "lead time", "देरी", "लेट"),
    "courier": ("courier", "carrier", "logistics", "van", "fleet", "transport", "shipping partner", "कूरियर", "ट्रांसपोर्ट"),
    "payment": ("cod", "cash on delivery", "prepaid", "upi", "payment", "कैश", "पेमेंट"),
    "contract": ("contract", "monthly", "annual", "plan", "subscription", "प्लान", "कॉन्ट्रैक्ट"),
    "brand": ("brand", "supplier", "vendor", "company", "manufacturer", "ब्रांड", "सप्लायर"),
    "channel": ("channel", "online", "retail", "wholesale", "store", "outlet", "चैनल", "स्टोर"),
    "quantity": ("volume", "quantity", "sales volume", "units sold", "stock", "inventory", "मात्रा", "स्टॉक"),
}

# Real-world external factors that spreadsheets rarely capture — used for honest Blind-Spot Transparency!
EXTERNAL_BLIND_SPOT_PATTERNS: List[Tuple[Tuple[str, ...], str, str]] = [
    (
        ("competitor", "competition", "rival", "nearby shop", "market rate", "कॉम्पिटिटर", "बाज़ार"),
        "Competitor actions & local rival pricing are not recorded in your uploaded data.",
        "आस-पास के कॉम्पिटिटर के दाम और उनकी रणनीति आपके डेटा में दर्ज नहीं है।",
    ),
    (
        ("staff", "employee", "boy", "waiter", "chef", "manager", "hiring", "salary", "training", "स्टाफ़", "मैनेजर", "लड़के", "सैलरी"),
        "Staff skill, morale, hiring friction, and training execution speed are not in this file — manage team rollout carefully.",
        "स्टाफ़ की ट्रेनिंग, मेहनत और नई भर्ती का ज़मीनी असर इस डेटा में नहीं है — टीम के साथ इसे खुद मॉनिटर करें।",
    ),
    (
        ("marketing", "ads", "instagram", "meta", "google ads", "influencer", "promotion", "मार्केटिंग", "विज्ञापन"),
        "Ad creative quality, brand awareness lift, and paid marketing conversion rates are outside this dataset.",
        "विज्ञापन की क्वालिटी और मार्केटिंग से आने वाले नए ग्राहकों का असर इस शीट के बाहर है।",
    ),
    (
        ("machine", "chiller", "equipment", "maintenance", "electricity", "repair", "rent", "lease", "मशीन", "चिलर", "बिजली", "किराया"),
        "Equipment vendor quotes, electricity/maintenance savings, and physical plant downtime are external to this table — verify vendor ROI separately.",
        "मशीन/चिलर की असली खरीद कीमत, बिजली खर्च और मेंटेनेंस वारंटी इस डेटा में नहीं है — सप्लायर कोटेशन अलग से जाँचें।",
    ),
    (
        ("recipe", "taste", "hygiene", "ambience", "packaging", "menu", "kitchen", "किचन", "पैकेजिंग", "मेनू"),
        "Kitchen recipe tweaks, dine-in ambience, and packaging feel cannot be directly measured from tabular rows alone.",
        "किचन की रेसिपी, स्वाद का बदलाव या माहौल का असर सीधे इस शीट से नहीं नापा जा सकता।",
    ),
    (
        ("weather", "summer", "rain", "festival", "diwali", "season", "गर्मी", "बारिश", "त्योहार"),
        "Upcoming weather shifts and festive demand spikes can alter baseline risk beyond historical averages.",
        "आने वाले मौसम (गर्मी/बारिश) और त्योहारों का असर पुराने औसत से अलग हो सकता है।",
    ),
]


def _extract_budget_from_text(text: str, unit_sym: str) -> Optional[float]:
    """Extracts CapEx / rollout budget mentioned in plain English/Hindi (e.g. ₹3 lakh, 50,000, $25k, 1.2 Cr)."""
    s = str(text or "")
    # Explicit scaled Indian & Western numbers (3 lakh, 1.5 cr, 50k, 2 million)
    m_scaled = re.search(
        r"(?:₹|rs\.?|inr|\$|€|£|aed|budget|spend|invest|cost|kharch|खर्च|लगा|बजट)?\s*"
        r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(crore|cr\b|lakh|lac|lacs|lakhs|लाख|करोड़|million|mn\b|k\b|thousand|हज़ार)",
        s,
        re.IGNORECASE,
    )
    if m_scaled:
        num = float(m_scaled.group(1).replace(",", ""))
        unit = m_scaled.group(2).lower()
        if unit in ("crore", "cr", "करोड़"):
            return round(num * 10_000_000.0, 2)
        if unit in ("lakh", "lac", "lacs", "lakhs", "लाख"):
            return round(num * 100_000.0, 2)
        if unit in ("million", "mn"):
            return round(num * 1_000_000.0, 2)
        if unit in ("k", "thousand", "हज़ार"):
            return round(num * 1_000.0, 2)

    # Explicit currency-prefixed raw amount (₹2,00,000 or ₹50,000 or $15,000 or Rs 25000)
    m_curr = re.search(r"(?:₹|rs\.?\s*|inr\s*|\$|€|£)\s*(\d{1,3}(?:,\d{2,3})+|\d{4,9})(?:\.\d+)?", s, re.IGNORECASE)
    if m_curr:
        return float(m_curr.group(1).replace(",", ""))
    return None


def _is_debate_prompt(text: str) -> bool:
    low = str(text or "").lower()
    return bool(re.search(
        r"\b(?:vs\.?|versus|or\s+should|instead\s+of|who\s+is\s+right|which\s+is\s+better|between|"
        r"ya\s+phir|ya\s+fir|kiski\s+baat|banam|बनाम|किसकी\s+बात|या\s+फिर|पहले\s+क्या)\b",
        low,
    ))


class BoardroomDecisionJudge:
    """
    Personal Chief Data Scientist & CA Boardroom Advisor grounded 100% in physical
    DuckDB/Parquet fact rows + Stage 8.3 Multi-Model Calibrated Causal ML.
    """

    def __init__(self, output_dir: str, region_profile: Optional[str] = None, engine: Optional[PredictiveDecisionEngine] = None):
        self.output_dir = Path(output_dir).resolve()
        self.region_profile = region_profile
        self.engine = engine or PredictiveDecisionEngine(str(self.output_dir), region_profile=region_profile)
        self.df = self.engine.df_full
        self.y = self.df["_dx_y_bin"].to_numpy()
        self.base_rate = float(self.y.mean()) if len(self.y) else 0.0
        self.is_fin = self.engine.is_monetary
        self.sym = self.engine.unit_sym if self.is_fin else ""
        self.vocab = infer_domain_vocab(list(self.df.columns), target_col=self.engine.target_col, is_financial=self.is_fin)

        # Pre-index driver importances & clean column labels
        self.imp_map: Dict[str, float] = {
            f["feature"]: float(f.get("importance_pct", 0.0))
            for f in (self.engine.feature_importances or [])
        }
        self.top_drivers: List[str] = [f["feature"] for f in (self.engine.feature_importances or [])]

        # Preload ranked leaks if present for extra context
        self.ranked_leaks: List[Dict[str, Any]] = []
        rk_p = self.output_dir / "ranked_leaks_report.json"
        if rk_p.exists():
            try:
                rk_j = json.loads(rk_p.read_text(encoding="utf-8"))
                self.ranked_leaks = list(rk_j.get("abnormal_deviations") or [])
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 1. SMART DATASET-SPECIFIC BOARDROOM DEBATE STARTERS
    # -------------------------------------------------------------------------
    def get_discussion_starters(self) -> List[Dict[str, str]]:
        """Generates 4 hyper-realistic boardroom debates tailored to THIS specific dataset."""
        starters: List[Dict[str, str]] = []
        domain = self.vocab.get("domain", "general")
        ent_en = self.vocab.get("entity_en", "records")
        top_feats = self.top_drivers[:4] or self.engine.all_features[:4]

        # Starter 1: Top-2 Drivers Head-to-Head Debate (e.g. pH vs Temperature, Votes vs City, Courier vs Discount)
        if len(top_feats) >= 2:
            f1_en = clean_column_label(top_feats[0], "en")
            f2_en = clean_column_label(top_feats[1], "en")
            f1_hi = clean_column_label(top_feats[0], "hi")
            f2_hi = clean_column_label(top_feats[1], "hi")
            if domain == "dairy_quality":
                starters.append({
                    "icon": "⚖️",
                    "tag_en": "CapEx Debate",
                    "tag_hi": "बजट बहस",
                    "prompt_en": f"My plant supervisor wants ₹2,00,000 to upgrade the chiller for {f2_en}, while QA says {f1_en} is the real reason milk is spoiling. Who is right?",
                    "prompt_hi": f"मेरा सुपरवाइज़र चिलर ({f2_hi}) के लिए ₹2 लाख माँग रहा है, जबकि QA कहता है {f1_hi} असली वजह है — मेरे डेटा के हिसाब से किसकी बात सही है?",
                })
            elif domain == "restaurant":
                starters.append({
                    "icon": "⚖️",
                    "tag_en": "Team Debate",
                    "tag_hi": "टीम की बहस",
                    "prompt_en": "My manager says we should push Online Delivery first, while my partner says Table Booking and Price Tier matter more. Who is right in our data?",
                    "prompt_hi": "मेरा मैनेजर कहता है पहले Online Delivery बढ़ाएँ, जबकि पार्टनर कहता है Table Booking और Price Tier ज़्यादा ज़रूरी है — डेटा के हिसाब से कौन सही है?",
                })
            else:
                starters.append({
                    "icon": "⚖️",
                    "tag_en": "Priority Debate",
                    "tag_hi": "प्राथमिकता बहस",
                    "prompt_en": f"My team is split: half say fix {f1_en} first, half say fix {f2_en} first. According to our real data, who is right?",
                    "prompt_hi": f"हमारी टीम दो हिस्सों में बँटी है: आधे कहते हैं पहले {f1_hi} सुधारें, आधे कहते हैं {f2_hi} — असली डेटा से बताओ कौन सही है?",
                })

        # Starter 2: Worst Segment Gut-Check / Drop-or-Fix Question
        cat_candidates = [c for c in self.top_drivers if c in self.engine.categorical_features] or self.engine.categorical_features[:2]
        if cat_candidates:
            c0 = cat_candidates[0]
            grp = self.df.groupby(c0, dropna=False)["_dx_y_bin"].agg(["count", "mean"])
            valid = grp[grp["count"] >= max(10, int(len(self.df) * 0.02))].sort_values("mean", ascending=False)
            if len(valid) >= 2:
                worst_v = str(valid.index[0])
                best_v = str(valid.index[-1])
                w_lbl_en = humanize_segment(c0, worst_v, "en", self.vocab)
                w_lbl_hi = humanize_segment(c0, worst_v, "hi", self.vocab)
                starters.append({
                    "icon": "🧐",
                    "tag_en": "Gut-Check",
                    "tag_hi": "अंदाज़ा जाँचें",
                    "prompt_en": f"Should we completely stop or pause {w_lbl_en}, or is it smarter to fix/shift it toward {best_v}?",
                    "prompt_hi": f"क्या हमें {w_lbl_hi} को पूरी तरह बंद कर देना चाहिए, या उसे सुधारकर '{best_v}' जैसा बनाना ज़्यादा समझदारी है?",
                })

        # Starter 3: Noise / False-Alarm Myth Buster (checks a low-importance column so owner sees honest pushback!)
        low_cats = [c for c in self.engine.categorical_features if self.imp_map.get(c, 0.0) < 3.0]
        if low_cats:
            lc = low_cats[0]
            top_v = str(self.df[lc].dropna().astype(str).value_counts().index[0]) if len(self.df[lc].dropna()) else ""
            lc_en = clean_column_label(lc, "en")
            lc_hi = clean_column_label(lc, "hi")
            starters.append({
                "icon": "🛡️",
                "tag_en": "Myth Buster",
                "tag_hi": "भ्रम तोड़ें",
                "prompt_en": f"I feel like '{top_v}' in {lc_en} is hurting our business and we should spend ₹50,000 fixing {lc_en}. Does the data agree?",
                "prompt_hi": f"मुझे लग रहा है {lc_hi} में '{top_v}' से नुकसान हो रहा है और ₹50,000 इस पर खर्च करें — क्या डेटा मेरी बात से सहमत है?",
            })

        # Starter 4: 14-Day Safe Action Roadmap Question
        starters.append({
            "icon": "🚀",
            "tag_en": "14-Day Board Plan",
            "tag_hi": "14-दिन का प्लान",
            "prompt_en": f"If I only have 14 days and a small team to reduce bad {ent_en}, what is the single highest-impact move I should make first — and what risks should I watch?",
            "prompt_hi": f"अगर मेरे पास सिर्फ़ 14 दिन और छोटी टीम है, तो खराब {ent_en} कम करने के लिए सबसे पहला और सुरक्षित कदम क्या होना चाहिए?",
        })
        return starters[:4]

    # -------------------------------------------------------------------------
    # 2. SEMANTIC COLUMN, SEGMENT & CLAIM EXTRACTOR
    # -------------------------------------------------------------------------
    def _match_mentioned_columns_and_segments(self, text: str) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Maps free-form owner words (English, Hindi, synonyms) onto actual schema columns & segment values."""
        low = str(text or "").lower()
        low_clean = re.sub(r"[^a-z0-9\u0900-\u097f\s_\-]+", " ", low)

        matched_cols: List[str] = []
        matched_segs: List[Tuple[str, str]] = []

        # 1. Direct column name & humanized label match
        for col in self.engine.all_features:
            c_low = col.lower()
            c_sp = c_low.replace("_", " ")
            lbl_en = clean_column_label(col, "en").lower()
            lbl_hi = clean_column_label(col, "hi").lower()
            tokens_to_check = [c_low, c_sp, lbl_en]
            if len(lbl_hi) >= 3:
                tokens_to_check.append(lbl_hi)
            # Also check meaningful individual words of multi-word columns
            for tok in tokens_to_check:
                if len(tok) >= 2 and re.search(rf"(?<![a-z0-9\u0900-\u097f]){re.escape(tok)}(?![a-z0-9\u0900-\u097f])", low_clean):
                    if col not in matched_cols:
                        matched_cols.append(col)
                    break

        # 2. Semantic synonym dictionary match (e.g. "chiller" -> Temprature, "sour" -> pH, "cloudy" -> Turbidity)
        for _concept, syn_words in SEMANTIC_CONCEPT_SYNONYMS.items():
            if any(re.search(rf"(?<![a-z0-9\u0900-\u097f]){re.escape(sw)}(?![a-z0-9\u0900-\u097f])", low_clean) for sw in syn_words):
                for col in self.engine.all_features:
                    c_norm = re.sub(r"[\s_\-]+", " ", col.lower())
                    if any(sw in c_norm or c_norm in sw for sw in syn_words if len(sw) >= 2):
                        if col not in matched_cols:
                            matched_cols.append(col)

        # 3. Direct category value match across categorical columns (e.g. "Faridabad", "Amul", "City Hotel", "SlowRoad")
        for col in self.engine.categorical_features:
            vals = self.engine._top_cat_maps.get(col) or []
            for v in vals:
                v_s = str(v).strip()
                if len(v_s) < 2 or v_s.lower() in ("no", "yes", "0", "1", "0.0", "1.0", "other", "missing", "true", "false"):
                    continue
                if re.search(rf"(?<![a-z0-9\u0900-\u097f]){re.escape(v_s.lower())}(?![a-z0-9\u0900-\u097f])", low_clean):
                    if (col, v_s) not in matched_segs:
                        matched_segs.append((col, v_s))
                    if col not in matched_cols:
                        matched_cols.append(col)

        # Order matched columns by ML predictive strength so primary drivers lead
        matched_cols.sort(key=lambda c: self.imp_map.get(c, 0.0), reverse=True)
        return matched_cols, matched_segs

    def _audit_single_factor(self, col: str, focus_val: Optional[str] = None, budget: float = 0.0) -> Dict[str, Any]:
        """Runs live DuckDB/Pandas statistical fact-check + Stage 8.3 Causal ML simulation on a single factor."""
        df = self.df
        y = self.y
        imp_pct = round(self.imp_map.get(col, 0.0), 1)
        auc_drop = round(float(self.engine.feature_auc_drop_map.get(col, 0.0)), 4)
        col_en = clean_column_label(col, "en")
        col_hi = clean_column_label(col, "hi")
        ent_en = self.vocab["entity_en"]
        ent_hi = self.vocab["entity_hi"]

        fact: Dict[str, Any] = {
            "column": col,
            "label_en": col_en,
            "label_hi": col_hi,
            "ml_importance_pct": imp_pct,
            "auc_drop": auc_drop,
            "is_strong_driver": bool(imp_pct >= 12.0 or auc_drop >= 0.015),
            "is_statistically_significant": False,
            "p_value": 1.0,
            "focus_segment": focus_val,
            "simulation": None,
            "summary_en": "",
            "summary_hi": "",
        }

        if col in self.engine.categorical_features or (
            pd.api.types.is_numeric_dtype(df[col]) and set(pd.to_numeric(df[col].dropna(), errors="coerce").unique()).issubset({0, 1, 0.0, 1.0})
        ):
            s_cat = df[col].fillna("Missing").astype(str)
            grp = pd.DataFrame({"g": s_cat, "y": y}).groupby("g")["y"].agg(["count", "sum", "mean"])
            valid = grp[grp["count"] >= max(5, int(len(df) * 0.01))].sort_values("mean", ascending=False)
            if len(valid) >= 2:
                tgt_val = focus_val if (focus_val and focus_val in valid.index) else str(valid.index[0])
                best_val = str(valid.index[-1])
                m_t = s_cat == tgt_val
                m_o = ~m_t
                k1, n1 = int(y[m_t].sum()), int(m_t.sum())
                k2, n2 = int(y[m_o].sum()), int(m_o.sum())
                r1 = (k1 / max(1, n1)) * 100.0
                r2 = (k2 / max(1, n2)) * 100.0
                pv = _two_prop_p_value(k1, n1, k2, n2)
                mult = (r1 / r2) if r2 > 0.1 else 1.0
                exc = max(0.0, (r1 - r2) / 100.0 * n1)
                seg_en = humanize_segment(col, tgt_val, "en", self.vocab)
                seg_hi = humanize_segment(col, tgt_val, "hi", self.vocab)

                fact["p_value"] = round(pv, 5)
                raw_sig = bool(pv < 0.05 and abs(r1 - r2) >= 2.0)
                model_auc = float(self.engine.model_metrics.get("roc_auc") or 0.0)
                is_multivariate_bystander = bool(model_auc >= 0.68 and imp_pct < 6.0 and auc_drop < 0.015)
                fact["is_confounded_noise"] = bool(raw_sig and is_multivariate_bystander)
                fact["is_statistically_significant"] = bool(raw_sig and not is_multivariate_bystander)
                fact["worst_rate_pct"] = round(r1, 1)
                fact["rest_rate_pct"] = round(r2, 1)
                fact["excess_cases"] = int(round(exc))
                fact["focus_segment"] = tgt_val

                if fact["is_confounded_noise"]:
                    fact["summary_en"] = (
                        f"{seg_en} looks slightly different on surface averages ({r1:.1f}% vs {r2:.1f}%), BUT once our multi-factor AI controls for real drivers, "
                        f"{col_en} carries only {imp_pct:.1f}% causal weight — it is a false alarm / bystander, NOT a true root cause."
                    )
                    fact["summary_hi"] = (
                        f"{seg_hi} सीधे औसत में थोड़ा अलग ({r1:.1f}% बनाम {r2:.1f}%) दिखता है, लेकिन जब AI असली कारणों को कंट्रोल करके जाँचता है तो "
                        f"{col_hi} का असली असर सिर्फ़ {imp_pct:.1f}% है — यह असली वजह नहीं, बल्कि भ्रम है।"
                    )
                elif fact["is_statistically_significant"] and r1 > r2:
                    fact["summary_en"] = (
                        f"{seg_en}: {rate_out_of_ten_phrase(r1, 'en')} {ent_en} fail vs {rate_out_of_ten_phrase(r2, 'en')} normally "
                        f"({multiplier_human_phrase(mult, 'en')}, ~{int(round(exc)):,} avoidable cases; ML driver share: {imp_pct:.1f}%)."
                    )
                    fact["summary_hi"] = (
                        f"{seg_hi}: {rate_out_of_ten_phrase(r1, 'hi')} {ent_hi} में समस्या है बनाम सामान्य {rate_out_of_ten_phrase(r2, 'hi')} "
                        f"({multiplier_human_phrase(mult, 'hi')}, ~{int(round(exc)):,} बचाये जा सकने वाले केस; AI महत्व: {imp_pct:.1f}%)।"
                    )
                elif fact["is_statistically_significant"] and r1 < r2:
                    fact["summary_en"] = (
                        f"{seg_en} actually performs BETTER than average ({r1:.1f}% risk vs {r2:.1f}% rest of business) — it is a strength, NOT a problem!"
                    )
                    fact["summary_hi"] = (
                        f"{seg_hi} असल में बाकी बिज़नेस से बेहतर प्रदर्शन कर रहा है ({r1:.1f}% रिस्क बनाम बाकी में {r2:.1f}%) — यह आपकी ताकत है, समस्या नहीं!"
                    )
                else:
                    fact["summary_en"] = (
                        f"{seg_en} has almost the exact same problem rate ({r1:.1f}%) as the rest of your business ({r2:.1f}%) — statistically random noise (ML weight: {imp_pct:.1f}%)."
                    )
                    fact["summary_hi"] = (
                        f"{seg_hi} में समस्या दर ({r1:.1f}%) बाकी बिज़नेस ({r2:.1f}%) के लगभग बराबर है — यह सिर्फ़ रैंडम शोर है (AI महत्व: {imp_pct:.1f}%)।"
                    )

                # Simulate shifting tgt_val -> best_val (if categorical & valid lever)
                if col in self.engine.categorical_features and tgt_val != best_val:
                    try:
                        sim = self.engine.simulate_decision(
                            decision={"action_type": "replace_category", "column": col, "from_value": tgt_val, "to_value": best_val},
                            implementation_cost=budget,
                        )
                        if sim.get("status") == "simulated":
                            fact["simulation"] = sim
                    except Exception:
                        pass
        else:
            # Continuous numeric driver (e.g., pH, Temprature, Votes, Average Cost for two, Delivery Days, Discount)
            s_num = pd.to_numeric(df[col], errors="coerce")
            good_vals = s_num[y == 0].dropna()
            bad_vals = s_num[y == 1].dropna()
            if len(good_vals) >= 10 and len(bad_vals) >= 10:
                q05, q95 = float(good_vals.quantile(0.05)), float(good_vals.quantile(0.95))
                bad_out_pct = float(((bad_vals < q05) | (bad_vals > q95)).mean() * 100.0)
                bad_above = float((bad_vals > q95).mean() * 100.0)
                bad_below = float((bad_vals < q05).mean() * 100.0)
                med_g, med_b = float(good_vals.median()), float(bad_vals.median())

                # Statistical significance via breach vs safe band
                in_safe = (s_num >= q05) & (s_num <= q95)
                out_safe = ~in_safe & s_num.notna()
                pv = _two_prop_p_value(
                    int(y[out_safe].sum()), int(out_safe.sum()),
                    int(y[in_safe].sum()), int(in_safe.sum()),
                )
                r_out = float(y[out_safe].mean() * 100.0) if out_safe.sum() >= 5 else self.base_rate * 100.0
                r_in = float(y[in_safe].mean() * 100.0) if in_safe.sum() >= 5 else self.base_rate * 100.0

                fact["p_value"] = round(pv, 5)
                raw_sig = bool((pv < 0.05 and abs(r_out - r_in) >= 5.0) or imp_pct >= 8.0)
                model_auc = float(self.engine.model_metrics.get("roc_auc") or 0.0)
                is_multivariate_bystander = bool(model_auc >= 0.68 and imp_pct < 6.0 and auc_drop < 0.015)
                fact["is_confounded_noise"] = bool(raw_sig and is_multivariate_bystander)
                fact["is_statistically_significant"] = bool(raw_sig and not is_multivariate_bystander)
                fact["bad_out_of_safe_pct"] = round(bad_out_pct, 1)
                fact["safe_band"] = f"{q05:g}–{q95:g}"

                if fact["is_confounded_noise"]:
                    fact["summary_en"] = (
                        f"{col_en} shows minor surface differences, BUT once our multi-factor AI controls for real drivers, "
                        f"{col_en} carries only {imp_pct:.1f}% causal weight — it is a false alarm / bystander, NOT a true root cause."
                    )
                    fact["summary_hi"] = (
                        f"{col_hi} में सीधे औसत में हल्का फ़र्क़ दिखता है, लेकिन जब AI असली कारणों को कंट्रोल करके जाँचता है तो "
                        f"{col_hi} का असली असर सिर्फ़ {imp_pct:.1f}% है — यह असली वजह नहीं, बल्कि भ्रम है।"
                    )
                elif bad_out_pct >= 25.0 and r_out > r_in + 5.0:
                    fact["summary_en"] = (
                        f"{col_en} carries {imp_pct:.1f}% of total AI predictive power: {bad_out_pct:.0f}% of all failed {ent_en} went outside the safe range ({q05:g}–{q95:g}), "
                        f"where failure jumps to {r_out:.0f}% (vs only {r_in:.0f}% inside the safe zone)."
                    )
                    fact["summary_hi"] = (
                        f"{col_hi} का कुल AI प्रभाव {imp_pct:.1f}% है: {bad_out_pct:.0f}% खराब {ent_hi} सुरक्षित सीमा ({q05:g}–{q95:g}) के बाहर गए, "
                        f"जहाँ खराबी {r_out:.0f}% तक पहुँच जाती है (जबकि सुरक्षित दायरे में सिर्फ़ {r_in:.0f}%)।"
                    )
                else:
                    fact["summary_en"] = (
                        f"{col_en} carries {imp_pct:.1f}% of AI predictive power (typical value {med_b:g} in failed cases vs {med_g:g} in healthy cases)."
                    )
                    fact["summary_hi"] = (
                        f"{col_hi} का AI प्रभाव {imp_pct:.1f}% है (खराब केस में औसत {med_b:g} बनाम सही केस में {med_g:g})।"
                    )

                # Simulate capping or flooring into the healthy band!
                try:
                    if bad_above >= bad_below and (s_num > q95).sum() >= 10:
                        sim = self.engine.simulate_decision(
                            decision={"action_type": "cap_numeric", "column": col, "value": round(q95, 2)},
                            implementation_cost=budget,
                        )
                        if sim.get("status") == "simulated":
                            fact["simulation"] = sim
                    elif (s_num < q05).sum() >= 10:
                        sim = self.engine.simulate_decision(
                            decision={"action_type": "floor_numeric", "column": col, "value": round(q05, 2)},
                            implementation_cost=budget,
                        )
                        if sim.get("status") == "simulated":
                            fact["simulation"] = sim
                except Exception:
                    pass

        return fact

    # -------------------------------------------------------------------------
    # 3. MAIN BOARDROOM DISCUSSION & JUDGMENT ENGINE
    # -------------------------------------------------------------------------
    def discuss(
        self,
        message: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates an owner's open-ended business question, team debate, CapEx pitch,
        or follow-up refinement against physical Parquet data + Stage 8.3 Causal ML.
        """
        raw_msg = str(message or "").strip()
        if not raw_msg:
            raise ValueError("Please enter your business question, team debate, or decision idea.")

        hist = history or []
        ent_en = self.vocab["entity_en"]
        ent_hi = self.vocab["entity_hi"]

        # 1. Context carry-over for multi-turn follow-ups ("What if we spend ₹50,000 instead?")
        budget = _extract_budget_from_text(raw_msg, self.sym)
        is_debate = _is_debate_prompt(raw_msg)
        is_stop_question = bool(re.search(r"\b(?:stop|pause|drop|ban|shut|cancel|बंद|हटा|रोक)\b", raw_msg.lower()))

        matched_cols, matched_segs = self._match_mentioned_columns_and_segments(raw_msg)

        # Carry forward context from the most recent user turn if current turn is a short follow-up (e.g. budget tweak!)
        carried_context = False
        if not matched_cols and hist:
            for prev in reversed(hist[-4:]):
                if prev.get("role") == "user" and prev.get("text"):
                    p_cols, p_segs = self._match_mentioned_columns_and_segments(prev["text"])
                    if p_cols:
                        matched_cols = p_cols
                        matched_segs = matched_segs or p_segs
                        carried_context = True
                        if not is_debate:
                            is_debate = _is_debate_prompt(prev["text"])
                        break

        # If owner asked a broad strategic question ("What should I do first in 14 days?"), audit the Top 2 real ML drivers!
        broad_strategy_mode = False
        if not matched_cols:
            broad_strategy_mode = True
            matched_cols = self.top_drivers[:2] or self.engine.all_features[:2]

        # 2. Check direct Stage 8.3 natural-language action simulation (e.g. explicit switch/cap/pause)
        direct_sim = None
        if not is_debate:
            try:
                parsed_specs = self.engine.parse_combo_decision_text(raw_msg)
                if parsed_specs:
                    s_res = self.engine.simulate_decision(
                        decisions=parsed_specs,
                        implementation_cost=budget or 0.0,
                    )
                    if s_res.get("status") == "simulated":
                        direct_sim = s_res
            except Exception:
                direct_sim = None

        # Also check explicit pause simulation if owner asked "Should we stop/drop X?"
        pause_sim = None
        if is_stop_question and matched_segs:
            p_col, p_val = matched_segs[0]
            try:
                ps = self.engine.simulate_decision(
                    decision={"action_type": "pause_segment", "column": p_col, "from_value": p_val},
                    implementation_cost=budget or 0.0,
                )
                if ps.get("status") == "simulated":
                    pause_sim = ps
            except Exception:
                pause_sim = None

        # 3. Live Physical Evidence Audit across matched factors (up to top 3)
        seg_by_col = {c: v for c, v in matched_segs}
        audited_factors: List[Dict[str, Any]] = []
        for col in matched_cols[:3]:
            audited_factors.append(self._audit_single_factor(col, focus_val=seg_by_col.get(col), budget=budget or 0.0))

        # Also check the #1 true ML driver in the entire dataset if the owner didn't mention it!
        top1_col = self.top_drivers[0] if self.top_drivers else None
        top1_missing_note_en = ""
        top1_missing_note_hi = ""
        if top1_col and top1_col not in matched_cols and self.imp_map.get(top1_col, 0.0) >= 20.0:
            t1_fact = self._audit_single_factor(top1_col, budget=budget or 0.0)
            top1_missing_note_en = f"Even bigger hidden lever you didn't mention: {t1_fact['summary_en']}"
            top1_missing_note_hi = f"एक और बड़ा कारण जिसका ज़िक्र आपने नहीं किया: {t1_fact['summary_hi']}"
            audited_factors.append(t1_fact)

        # 4. Build Head-to-Head Scorecard (for debates or multi-factor comparisons!)
        comparison_rows: List[Dict[str, Any]] = []
        for f in audited_factors[:3]:
            sim = f.get("simulation")
            pred = (sim or {}).get("prediction") or {}
            comparison_rows.append({
                "option_en": f["label_en"] + (f" ({f['focus_segment']})" if f.get("focus_segment") else ""),
                "option_hi": f["label_hi"] + (f" ({f['focus_segment']})" if f.get("focus_segment") else ""),
                "ml_driver_share_pct": f["ml_importance_pct"],
                "statistically_proven": f["is_statistically_significant"],
                "benefit_chance_pct": pred.get("chance_of_benefit_pct"),
                "expected_impact": pred.get("formatted_net_impact") or (f"~{f.get('excess_cases', 0):,} avoidable cases" if f.get("excess_cases") else "Fact-checked"),
                "trust_score": ((pred.get("simulation_confidence") or {}).get("score")),
                "causal_support_pct": pred.get("causal_support_pct"),
                "verdict_code": pred.get("verdict_code") or ("PROVEN" if f["is_statistically_significant"] else "NOISE"),
            })

        # 5. Synthesize 4 Crystal-Clear Boardroom Sections:
        #    (A) Proven True, (B) Wrong / Risky, (C) Honest Blind Spots, (D) Verdict & 14-Day Plan
        proven_true_en: List[str] = []
        proven_true_hi: List[str] = []
        wrong_or_risky_en: List[str] = []
        wrong_or_risky_hi: List[str] = []
        blind_spots_en: List[str] = []
        blind_spots_hi: List[str] = []

        # Populate from audited factors
        primary_factors = [f for f in audited_factors if f["column"] in matched_cols[:3]]
        for f in primary_factors:
            sim = f.get("simulation")
            pred = (sim or {}).get("prediction") or {}
            if f["is_statistically_significant"] or f["is_strong_driver"]:
                proven_true_en.append(f["summary_en"])
                proven_true_hi.append(f["summary_hi"])
                if sim and pred.get("expected_net_impact", 0) > 0 and not pred.get("noise_circuit_breaker_active"):
                    be = (pred.get("break_even_analysis") or {})
                    be_note_en = f" {be['summary_en']}" if be.get("summary_en") else ""
                    be_note_hi = f" {be['summary_hi']}" if be.get("summary_hi") else ""
                    proven_true_en.append(
                        f"Causal ML Simulation ({f['label_en']}): {pred['chance_of_benefit_pct']:.0f}% chance of net gain "
                        f"({pred['formatted_net_impact']}, 95% range {pred['formatted_ci_95']}).{be_note_en}"
                    )
                    proven_true_hi.append(
                        f"AI सिमुलेशन ({f['label_hi']}): फ़ायदे का {pred['chance_of_benefit_pct']:.0f}% चांस "
                        f"(शुद्ध असर: {pred['formatted_net_impact']}, 95% रेंज: {pred['formatted_ci_95']})।{be_note_hi}"
                    )
                elif sim and pred.get("expected_net_impact", 0) <= 0:
                    wrong_or_risky_en.append(
                        f"Budget / ROI Warning on {f['label_en']}: Even though {f['label_en']} is real, simulating this change "
                        f"{f'with {_fmt_money(budget, self.sym, self.is_fin)} budget ' if budget else ''}yields net {pred['formatted_net_impact']} "
                        f"({pred['chance_of_benefit_pct']:.0f}% chance of profit) — start cheaper before committing full capital."
                    )
                    wrong_or_risky_hi.append(
                        f"बजट / ROI चेतावनी ({f['label_hi']}): समस्या असली है, लेकिन "
                        f"{f'{_fmt_money(budget, self.sym, self.is_fin)} खर्च के साथ ' if budget else ''}अनुमानित शुद्ध असर {pred['formatted_net_impact']} है "
                        f"(सिर्फ़ {pred['chance_of_benefit_pct']:.0f}% लाभ का चांस) — पहले कम खर्च वाले पायलट से जाँचें।"
                    )
                if pred.get("extrapolation_warning"):
                    wrong_or_risky_en.append(
                        f"Thin Historical Overlap ({f['label_en']}): Only {pred.get('causal_support_pct', 0):.0f}% of similar historical cases operated at this target setting — do not roll out blindly to 100%."
                    )
                    wrong_or_risky_hi.append(
                        f"कम ऐतिहासिक मिलान ({f['label_hi']}): पुराने डेटा में सिर्फ़ {pred.get('causal_support_pct', 0):.0f}% समान केस इस सेटिंग पर चले हैं — 100% रोलआउट एक साथ न करें।"
                    )
                if pred.get("confounder_alert_active"):
                    wrong_or_risky_en.append(
                        f"Confounder Trap ({f['label_en']}): Surface averages exaggerate this lever — hidden co-drivers explain most of the gap."
                    )
                    wrong_or_risky_hi.append(
                        f"छुपे कारण का जाल ({f['label_hi']}): सीधा औसत इसे बड़ा दिखाता है, लेकिन असली वजह दूसरे जुड़े हुए फैक्टर हैं।"
                    )
            else:
                wrong_or_risky_en.append(
                    f"Not Supported by Data ({f['label_en']}): {f['summary_en']} Spending capital targeting this alone is likely wasted."
                )
                wrong_or_risky_hi.append(
                    f"डेटा इसे सही नहीं मानता ({f['label_hi']}): {f['summary_hi']} सिर्फ़ इस पर पैसा खर्च करना बेकार जा सकता है।"
                )

        if top1_missing_note_en:
            proven_true_en.append(top1_missing_note_en)
            proven_true_hi.append(top1_missing_note_hi)

        # Include explicit pause_segment simulation verdict if user asked "Should we stop/drop X?"
        if pause_sim:
            pp = pause_sim["prediction"]
            if pp["verdict_code"] == "LIKELY_LOSS" or pp["expected_net_impact"] < 0:
                wrong_or_risky_en.insert(
                    0,
                    f"Do NOT Stop/Drop It: Stopping '{matched_segs[0][1]}' completely sacrifices too many healthy {ent_en}, "
                    f"causing an estimated net LOSS of {pp['formatted_net_impact']} ({pp['chance_of_loss_pct']:.0f}% chance of loss). Fix/shift instead of shutting down!",
                )
                wrong_or_risky_hi.insert(
                    0,
                    f"पूरी तरह बंद न करें: '{matched_segs[0][1]}' बंद करने से बहुत से अच्छे {ent_hi} भी चले जाएंगे और लगभग {pp['formatted_net_impact']} का शुद्ध नुकसान "
                    f"({pp['chance_of_loss_pct']:.0f}% घाटे का ख़तरा) होगा — बंद करने की जगह सुधारें!",
                )
            else:
                proven_true_en.insert(
                    0,
                    f"Pausing '{matched_segs[0][1]}' Is Mathematically Justified: High failure loss outweighs healthy volume, projecting {pp['formatted_net_impact']} net gain ({pp['chance_of_benefit_pct']:.0f}% confidence).",
                )
                proven_true_hi.insert(
                    0,
                    f"'{matched_segs[0][1]}' को रोकना गणित के हिसाब से सही है: इससे {pp['formatted_net_impact']} शुद्ध बचत का अनुमान है ({pp['chance_of_benefit_pct']:.0f}% भरोसा)।",
                )

        # Include direct explicit action simulation if distinct
        if direct_sim and not pause_sim:
            dp = direct_sim["prediction"]
            if dp.get("noise_circuit_breaker_active") or dp["verdict_code"] == "LIKELY_LOSS":
                wrong_or_risky_en.insert(0, f"Direct Decision Test: {dp['verdict_en']} (Net: {dp['formatted_net_impact']}, Benefit chance: {dp['chance_of_benefit_pct']:.0f}%).")
                wrong_or_risky_hi.insert(0, f"सीधा फ़ैसला टेस्ट: {dp['verdict_hi']} (शुद्ध असर: {dp['formatted_net_impact']}, लाभ चांस: {dp['chance_of_benefit_pct']:.0f}%)।")
            elif dp["expected_net_impact"] > 0:
                proven_true_en.insert(0, f"Direct Decision Test: {dp['verdict_en']} — Expected {dp['formatted_net_impact']} ({dp['chance_of_benefit_pct']:.0f}% chance of benefit, Trust Score {dp['simulation_confidence']['score']}/100).")
                proven_true_hi.insert(0, f"सीधा फ़ैसला टेस्ट: {dp['verdict_hi']} — अनुमानित असर {dp['formatted_net_impact']} (लाभ चांस {dp['chance_of_benefit_pct']:.0f}%, भरोसा स्कोर {dp['simulation_confidence']['score']}/100)।")

        # Detect external real-world blind spots mentioned in the owner's prompt
        low_full = raw_msg.lower()
        for kws, bs_en, bs_hi in EXTERNAL_BLIND_SPOT_PATTERNS:
            if any(k in low_full for k in kws):
                blind_spots_en.append(bs_en)
                blind_spots_hi.append(bs_hi)
        if budget and not self.is_fin:
            blind_spots_en.append(
                f"Your uploaded dataset tracks quality/events (no currency ledger), so you should multiply saved {ent_en} by your internal per-batch rupee/dollar value to verify payback against {_fmt_money(budget, '₹', True)}."
            )
            blind_spots_hi.append(
                f"इस फ़ाइल में रुपये/कीमत का कॉलम नहीं है (सिर्फ़ क्वालिटी/बैच डेटा है) — इसलिए अपने {_fmt_money(budget, '₹', True)} बजट की वापसी जाँचने के लिए बचाए गए {ent_hi} को प्रति-बैच कीमत से गुणा करके देखें।"
            )
        if not blind_spots_en:
            blind_spots_en.append(
                "External real-world factors (competitor discounts, staff discipline, vendor reliability, and sudden seasonal demand shifts) are not stored in this sheet — combine this data verdict with your ground-level judgment."
            )
            blind_spots_hi.append(
                "बाहरी ज़मीनी कारण (कॉम्पिटिटर के ऑफ़र, स्टाफ़ का व्यवहार, सप्लायर की समयबद्धता और मौसम) इस शीट में नहीं हैं — इस डेटा फ़ैसले के साथ अपना व्यापारिक अनुभव ज़रूर मिलाएँ।"
            )

        # 6. Determine Clear Overall Verdict Code & Headline
        winner_factor = primary_factors[0] if primary_factors else (audited_factors[0] if audited_factors else None)
        if is_debate and len(primary_factors) >= 2:
            f_a, f_b = primary_factors[0], primary_factors[1]
            # Primary factors are already sorted by ML importance; verify winner clearly!
            score_a = f_a["ml_importance_pct"] + (20.0 if f_a["is_statistically_significant"] else 0.0)
            score_b = f_b["ml_importance_pct"] + (20.0 if f_b["is_statistically_significant"] else 0.0)
            if score_a >= score_b + 8.0:
                verdict_code = "CLEAR_WINNER"
                verdict_badge_en = f"🏆 DATA VERDICT: FOCUS ON {f_a['label_en'].upper()} FIRST"
                verdict_badge_hi = f"🏆 डेटा का फ़ैसला: पहले {f_a['label_hi']} पर काम करें"
                verdict_hl_en = (
                    f"{f_a['label_en']} is the bigger real driver ({f_a['ml_importance_pct']:.0f}% AI impact) compared to {f_b['label_en']} ({f_b['ml_importance_pct']:.0f}%). "
                    f"Fix {f_a['label_en']} first before spending heavy money on {f_b['label_en']}."
                )
                verdict_hl_hi = (
                    f"असली डेटा के हिसाब से {f_a['label_hi']} ({f_a['ml_importance_pct']:.0f}% असर) की भूमिका {f_b['label_hi']} ({f_b['ml_importance_pct']:.0f}%) से ज़्यादा बड़ी है — "
                    f"बड़ा बजट लगाने से पहले {f_a['label_hi']} ठीक करें।"
                )
            else:
                verdict_code = "BOTH_MATTER"
                verdict_badge_en = "🤝 DATA VERDICT: BOTH FACTORS MATTER TOGETHER"
                verdict_badge_hi = "🤝 डेटा का फ़ैसला: दोनों कारण मिलकर असर डाल रहे हैं"
                verdict_hl_en = (
                    f"Both {f_a['label_en']} ({f_a['ml_importance_pct']:.0f}%) and {f_b['label_en']} ({f_b['ml_importance_pct']:.0f}%) drive real risk. "
                    f"Run a combined low-cost 14-day pilot addressing both instead of picking only one side."
                )
                verdict_hl_hi = (
                    f"{f_a['label_hi']} ({f_a['ml_importance_pct']:.0f}%) और {f_b['label_hi']} ({f_b['ml_importance_pct']:.0f}%) दोनों का असली असर है — "
                    f"किसी एक के बजाय दोनों पर एक छोटा 14-दिन का संयुक्त पायलट चलाएँ।"
                )
        elif pause_sim and (pause_sim["prediction"]["verdict_code"] == "LIKELY_LOSS" or pause_sim["prediction"]["expected_net_impact"] < 0):
            verdict_code = "REFUTED_BY_DATA"
            verdict_badge_en = "❌ DATA SAYS NO: DO NOT SHUT THIS DOWN"
            verdict_badge_hi = "❌ डेटा की सलाह: इसे बंद न करें (नुकसान होगा)"
            verdict_hl_en = (
                f"Shutting down '{matched_segs[0][1]}' completely will hurt your business more than it helps "
                f"({pause_sim['prediction']['formatted_net_impact']} net impact). Keep it running and fix the root cause instead."
            )
            verdict_hl_hi = (
                f"'{matched_segs[0][1]}' को पूरी तरह बंद करने से फ़ायदे की जगह नुकसान ({pause_sim['prediction']['formatted_net_impact']}) होगा — "
                f"बंद करने की जगह इसकी असली कमज़ोरी सुधारें।"
            )
        elif primary_factors and all((not f["is_statistically_significant"] and not f["is_strong_driver"]) for f in primary_factors):
            verdict_code = "REFUTED_BY_DATA"
            verdict_badge_en = "❌ MYTH BUSTED: DATA DOES NOT SUPPORT THIS SPEND"
            verdict_badge_hi = "❌ भ्रम टूटा: डेटा इस खर्च को सही नहीं मानता"
            verdict_hl_en = (
                f"Your data shows {primary_factors[0]['label_en']} is statistically flat (random noise, not a true root cause). "
                f"Save your money — focus instead on your real #1 driver ({clean_column_label(top1_col, 'en') if top1_col else 'overall operations'})."
            )
            verdict_hl_hi = (
                f"डेटा बताता है कि {primary_factors[0]['label_hi']} में फ़र्क़ सिर्फ़ रैंडम शोर है, असली कारण नहीं। "
                f"यहाँ पैसा बचाएँ और असली मुख्य कारण ({clean_column_label(top1_col, 'hi') if top1_col else 'सामान्य प्रोसेस'}) पर लगाएँ।"
            )
        elif budget and winner_factor and winner_factor.get("simulation") and winner_factor["simulation"]["prediction"]["expected_net_impact"] <= 0:
            verdict_code = "PARTIALLY_SUPPORTED"
            verdict_badge_en = "🟡 RIGHT PROBLEM, TOO EXPENSIVE AT THIS BUDGET"
            verdict_badge_hi = "🟡 समस्या असली है, पर इतना बड़ा बजट ज़्यादा है"
            verdict_hl_en = (
                f"The problem in {winner_factor['label_en']} is real, but spending {_fmt_money(budget, self.sym or '₹', True)} upfront "
                f"does not pay back cleanly yet. Start with a lean 14-day operational trial first."
            )
            verdict_hl_hi = (
                f"{winner_factor['label_hi']} की समस्या तो असली है, लेकिन अभी {_fmt_money(budget, self.sym or '₹', True)} का बड़ा खर्च एक साथ लगाना सुरक्षित नहीं है — "
                f"पहले कम खर्च वाला 14-दिन का ट्रायल करें।"
            )
        else:
            verdict_code = "SUPPORTED_BY_DATA"
            top_lbl_en = winner_factor["label_en"] if winner_factor else "Top Bottleneck"
            top_lbl_hi = winner_factor["label_hi"] if winner_factor else "मुख्य समस्या"
            verdict_badge_en = f"✅ DATA-BACKED MOVE: PRIORITIZE {top_lbl_en.upper()}"
            verdict_badge_hi = f"✅ डेटा समर्थित फ़ैसला: {top_lbl_hi} को प्राथमिकता दें"
            verdict_hl_en = (
                f"Your data backs focusing on {top_lbl_en} ({winner_factor['ml_importance_pct']:.0f}% AI driver share). "
                f"Start with a controlled 14-day pilot on the highest-risk {ent_en} and track real results."
                if winner_factor else
                f"Focus first on the top flagged {ent_en} in Today's Action List with a 14-day measurable pilot."
            )
            verdict_hl_hi = (
                f"आपका डेटा {top_lbl_hi} ({winner_factor['ml_importance_pct']:.0f}% AI प्रभाव) पर काम करने का समर्थन करता है। "
                f"सबसे ज़्यादा रिस्क वाले {ent_hi} पर 14-दिन का नियंत्रित पायलट चलाकर असली नतीजे नापें।"
                if winner_factor else
                f"Today's Action List के टॉप फ्लैग्ड {ent_hi} पर 14-दिन का पायलट शुरू करें।"
            )

        # Ensure neither True nor Risky box is ever awkwardly blank
        if not proven_true_en:
            if audited_factors and (audited_factors[-1]["is_statistically_significant"] or audited_factors[-1]["is_strong_driver"]):
                proven_true_en.append(audited_factors[-1]["summary_en"])
                proven_true_hi.append(audited_factors[-1]["summary_hi"])
            else:
                proven_true_en.append(
                    f"Baseline Reality Check: Across all {len(self.df):,} audited {ent_en}, overall problem rate is {self.base_rate * 100.0:.1f}% — protecting your capital from false alarms is itself a direct profit win."
                )
                proven_true_hi.append(
                    f"बेसलाइन सच: कुल {len(self.df):,} जाँचे गए {ent_hi} में औसत समस्या दर {self.base_rate * 100.0:.1f}% है — ग़लत जगह पैसा फँसने से बचाना भी सीधा मुनाफ़ा है।"
                )
        if not wrong_or_risky_en:
            wrong_or_risky_en.append(
                f"No direct statistical refutation found, but rolling out overnight to 100% of {ent_en} without a 20% pilot still carries operational execution risk."
            )
            wrong_or_risky_hi.append(
                f"डेटा में कोई सीधा विरोध नहीं मिला, फिर भी 100% काम एक रात में बदलने से ऑपरेशनल रिस्क रहता है — पहले 20% पायलट ज़रूर करें।"
            )

        # 7. Concrete 14-Day Safe Action Plan + Smart Follow-up Prompts
        # When the owner's hypothesis was REFUTED, pivot the action plan & follow-ups to the TRUE #1 driver!
        if verdict_code == "REFUTED_BY_DATA" and top1_col:
            focus_lbl_en = clean_column_label(top1_col, "en")
            focus_lbl_hi = clean_column_label(top1_col, "hi")
        else:
            focus_lbl_en = (winner_factor["label_en"] if winner_factor else "your top bottleneck")
            focus_lbl_hi = (winner_factor["label_hi"] if winner_factor else "आपकी मुख्य समस्या")
        action_plan_en = [
            f"Days 1–3 (Audit & Isolate): Open Today's Action List and pull the top 25 highest-risk {ent_en} linked to {focus_lbl_en}.",
            f"Days 4–10 (20% Controlled Pilot): Test the fix on ~20% of volume first{f' (cap initial pilot spend at 15–20% of {_fmt_money(budget, self.sym or chr(8377), True)})' if budget else ''} without disrupting healthy operations.",
            "Days 11–14 (Verify Reality): Upload fresh 2-week data into DataX-Ray and use Decision Predictor → Commit & Track Reality to measure true before-vs-after gain before full rollout.",
        ]
        action_plan_hi = [
            f"दिन 1–3 (जाँच और पहचान): Today's Action List खोलें और {focus_lbl_hi} से जुड़े टॉप 25 सबसे ज़्यादा रिस्क वाले {ent_hi} अलग करें।",
            f"दिन 4–10 (20% सुरक्षित पायलट): पूरे बिज़नेस को छेड़े बिना पहले सिर्फ़ ~20% काम पर सुधार आज़माएँ{f' (शुरुआत में बजट का सिर्फ़ 15–20% ही लगाएँ)' if budget else ''}।",
            "दिन 11–14 (असली नतीजे मिलाएँ): 2 हफ़्ते का नया डेटा अपलोड करके असली पहले-बनाम-बाद का सुधार नापें, तभी 100% लागू करें।",
        ]

        followups_en = [
            f"What if we cut our rollout budget to half and run a 20% pilot on {focus_lbl_en}?",
            "Which specific group or store will benefit the MOST — and where won't this help?",
            f"Compare fixing {focus_lbl_en} vs our #2 driver head-to-head.",
        ]
        followups_hi = [
            f"अगर हम बजट आधा कर दें और {focus_lbl_hi} पर सिर्फ़ 20% पायलट चलाएँ तो क्या होगा?",
            "किस खास ग्रुप/शहर में सबसे ज़्यादा फ़ायदा होगा और कहाँ कोई फ़र्क़ नहीं पड़ेगा?",
            f"{focus_lbl_hi} बनाम दूसरे सबसे बड़े कारण की सीधी तुलना करके बताओ।",
        ]

        return {
            "status": "judged",
            "verdict": {
                "code": verdict_code,
                "badge_en": verdict_badge_en,
                "badge_hi": verdict_badge_hi,
                "headline_en": verdict_hl_en,
                "headline_hi": verdict_hl_hi,
            },
            "evidence": {
                "proven_true_en": proven_true_en[:4],
                "proven_true_hi": proven_true_hi[:4],
                "wrong_or_risky_en": wrong_or_risky_en[:4],
                "wrong_or_risky_hi": wrong_or_risky_hi[:4],
                "blind_spots_en": blind_spots_en[:3],
                "blind_spots_hi": blind_spots_hi[:3],
            },
            "comparison_scorecard": comparison_rows,
            "action_plan_en": action_plan_en,
            "action_plan_hi": action_plan_hi,
            "follow_up_prompts_en": followups_en,
            "follow_up_prompts_hi": followups_hi,
            "context_used": {
                "matched_columns": matched_cols[:3],
                "matched_segments": [f"{c}={v}" for c, v in matched_segs[:3]],
                "budget_parsed": budget,
                "carried_prior_context": carried_context,
                "broad_strategy_mode": broad_strategy_mode,
                "model_roc_auc": self.engine.model_metrics.get("roc_auc"),
                "temporal_backtest_auc": self.engine.model_metrics.get("temporal_backtest_auc"),
                "rows_audited": int(len(self.df)),
            },
        }


__all__ = ["BoardroomDecisionJudge"]
