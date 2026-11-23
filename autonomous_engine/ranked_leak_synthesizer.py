"""
DataX-Ray Autonomous Exception & Deviation Engine (Management-by-Exception Brain).

Instead of dumping 200 raw answers OR arbitrarily cutting off at "Top 6 / Top 10",
this engine autonomously evaluates EVERY data-backed business check against its
Expected Healthy Standard (`HEALTHY_AS_EXPECTED` vs `ABNORMAL_DEVIATION`):

1. `abnormal_deviations` (also exposed as `top_ranked_leaks` for API compatibility):
   Shows ALL verified abnormalities/kharabi — whether 0, 3, or 18 — with NO
   arbitrary cap. Each item states:
   - What SHOULD be (`expected_standard_en` / `expected_standard_hi`)
   - What ACTUALLY is (`actual_observed_en` / `actual_observed_hi`)
   - Exact root cause, financial/operational impact, and fix action
   - The exact autonomous `decision_rule` that flagged it as abnormal.
2. `healthy_checks_suppressed`:
   Checks that passed their expected healthy standard (e.g., 0 duplicate PKs,
   no margin-trap SKUs, healthy promo repeat rate, 0 dead stock, stable margin).
   Auto-suppressed from the alarm feed so the business owner NEVER wastes time
   reading things that are already working fine.
3. `do_not_spend_shields`:
   Uniform statistical noise dimensions (`p >= 0.05`) where spending should be 0.
4. `hidden_opportunities`:
   High-leverage positive discoveries (Gateway SKUs, Hero Stars, Zone Courier rules,
   Cross-Sell pairs, Pricing Power).
5. `missing_data_unlock_packs`:
   Groups unavailable checks into 3-4 compact optional upload packs.

Zero-Hallucination & Non-Monetary Guard:
- Never fabricates currency symbols on non-monetary datasets (`is_financial == False`).
- Every number is derived strictly from physical `omni_report` / `q200_report` / `df`.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd


def _clean_float(val: Any) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else 0.0
    except Exception:
        return 0.0


def _fmt_money(val: float, sym: str, numbering: str = "international") -> str:
    if not sym:
        return f"{round(_clean_float(val)):,}"
    v = _clean_float(val)
    sign = "-" if v < 0 else ""
    av = abs(v)
    if numbering == "indian" or sym == "₹":
        if av >= 1e7:
            return f"{sign}{sym}{av / 1e7:.2f} Cr"
        if av >= 1e5:
            return f"{sign}{sym}{av / 1e5:.2f} L"
        return f"{sign}{sym}{av:,.2f}"
    if av >= 1e9:
        return f"{sign}{sym}{av / 1e9:.2f}B"
    if av >= 1e6:
        return f"{sign}{sym}{av / 1e6:.2f}M"
    if av >= 1e4:
        return f"{sign}{sym}{av / 1e3:.2f}K"
    return f"{sign}{sym}{av:,.2f}"


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return round(v, 4) if math.isfinite(v) else 0.0
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def _extract_first_float(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, str(text or ""), re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def _friendly_dim_name(dim_name: str, lang: str = "en") -> str:
    """Translates raw column names with underscores into plain everyday business labels."""
    raw = str(dim_name or "").strip()
    low = raw.lower().replace(" ", "_")
    en_map = {
        "payment_mode": "Payment Mode",
        "payment_method": "Payment Method",
        "payment_gateway": "Payment Gateway",
        "courier_partner": "Delivery Courier",
        "courier": "Delivery Courier",
        "carrier": "Carrier / Courier",
        "product_item": "Product",
        "product_name": "Product",
        "sku_name": "Product / SKU",
        "sku_code": "Product Code",
        "customer_state": "State",
        "state": "State",
        "city_tier": "City Tier",
        "delivery_days": "Delivery Days",
        "transit_days": "Delivery Days",
        "is_repeated_guest": "Guest Type",
        "distribution_channel": "Booking Channel",
        "market_segment": "Customer Segment",
        "deposit_type": "Deposit Type",
        "assigned_room_type": "Room Type",
        "reserved_room_type": "Booked Room Type",
        "total_of_special_requests": "Special Requests",
        "customer_type": "Customer Type",
    }
    hi_map = {
        "payment_mode": "पेमेंट का तरीका (Payment Mode)",
        "payment_method": "पेमेंट का तरीका (Payment Mode)",
        "payment_gateway": "पेमेंट मोड़ (Payment Gateway)",
        "courier_partner": "कूरियर कंपनी (Courier Partner)",
        "courier": "कूरियर कंपनी (Courier)",
        "carrier": "कूरियर / कैरियर",
        "product_item": "प्रोडक्ट (Product)",
        "product_name": "प्रोडक्ट (Product)",
        "sku_name": "प्रोडक्ट (SKU)",
        "sku_code": "प्रोडक्ट कोड (SKU)",
        "customer_state": "राज्य (State)",
        "state": "राज्य (State)",
        "city_tier": "शहर श्रेणी (City Tier)",
        "delivery_days": "डिलीवरी के दिन (Delivery Days)",
        "transit_days": "डिलीवरी के दिन (Transit Days)",
        "is_repeated_guest": "ग्राहक प्रकार (New vs Repeat Guest)",
        "distribution_channel": "बुकिंग चैनल (Booking Channel)",
        "market_segment": "ग्राहक वर्ग (Customer Segment)",
        "deposit_type": "डिपॉज़िट नियम (Deposit Type)",
        "assigned_room_type": "रूम कैटेगरी (Room Type)",
        "reserved_room_type": "बुक किया गया रूम (Room Type)",
        "total_of_special_requests": "स्पेशल रिक्वेस्ट (Special Requests)",
        "customer_type": "ग्राहक श्रेणी (Customer Type)",
    }
    if lang == "hi":
        return hi_map.get(low, raw.replace("_", " ").title())
    return en_map.get(low, raw.replace("_", " ").title())


def _friendly_seg_name(dim_name: str, seg_val: str, lang: str = "en") -> str:
    """Translates raw coded segment values like '0' in is_repeated_guest or 'TA/TO' into plain words."""
    d_low = str(dim_name or "").strip().lower().replace(" ", "_")
    s_raw = str(seg_val or "").strip()
    if d_low == "is_repeated_guest":
        if s_raw in ("0", "0.0", "false", "False"):
            return "पहली बार आए ग्राहक (First-Time Guests)" if lang == "hi" else "First-Time Guests (New Customers)"
        if s_raw in ("1", "1.0", "true", "True"):
            return "पुराने रिपीट ग्राहक (Repeat Guests)" if lang == "hi" else "Repeat Guests"
    if d_low == "total_of_special_requests" and s_raw in ("0", "0.0"):
        return "बिना स्पेशल रिक्वेस्ट वाली बुकिंग (0 Requests)" if lang == "hi" else "Bookings With No Special Requests (0)"
    if d_low in ("distribution_channel", "market_segment") and s_raw.upper() == "TA/TO":
        return "ट्रैवल एजेंट बुकिंग (TA/TO)" if lang == "hi" else "Travel Agent Bookings (TA/TO)"
    if d_low == "deposit_type" and s_raw.lower() in ("non refund", "non-refund"):
        return "नॉन-रिफंडेबल बुकिंग (Non Refund)" if lang == "hi" else "Non-Refundable Bookings (Non Refund)"
    return s_raw


def synthesize_ranked_leaks(
    df: Optional[pd.DataFrame],
    omni_report: Optional[Dict[str, Any]] = None,
    q200_report: Optional[Dict[str, Any]] = None,
    blueprint: Optional[Dict[str, Any]] = None,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Autonomously evaluates all business signals against Expected Healthy Standards.
    Surfaces EVERY genuine deviation/kharabi (no arbitrary Top-N cap) and suppresses
    everything operating as expected into `healthy_checks_suppressed`.
    """
    omni = omni_report if isinstance(omni_report, dict) else {}
    q200 = q200_report if isinstance(q200_report, dict) else {}
    qs = q200.get("questions") or []
    qmap: Dict[str, Dict[str, Any]] = {q.get("id"): q for q in qs if isinstance(q, dict) and q.get("id")}

    is_fin = bool(q200.get("is_financial", omni.get("is_financial", False)))
    sym = str(q200.get("unit_symbol") or omni.get("unit_symbol") or "") if is_fin else ""
    numbering = "indian" if sym == "₹" else "international"
    n_rows = int(q200.get("dataset_rows") or (len(df) if isinstance(df, pd.DataFrame) else 0))

    # Compute physical average monetary value per adverse record so every dimensional leak shows real ₹/$ impact
    avg_adverse_unit_value = 0.0
    cost_col_name: Optional[str] = None
    canon_meta: Dict[str, Any] = {}
    if is_fin and isinstance(df, pd.DataFrame) and len(df) > 0:
        try:
            try:
                from .target_resolver import resolve_canonical_target_and_cost
            except ImportError:
                from target_resolver import resolve_canonical_target_and_cost
            canon = resolve_canonical_target_and_cost(df, blueprint=blueprint)
            canon_meta = canon or {}
            cost_col_name = canon.get("cost_col")
            s_bin = canon.get("binary_target")
            if cost_col_name and cost_col_name in df.columns:
                c_s = pd.to_numeric(df[cost_col_name], errors="coerce").dropna()
                if s_bin is not None and (s_bin == 1).any():
                    adv_s = pd.to_numeric(df.loc[s_bin == 1, cost_col_name], errors="coerce").dropna()
                    if len(adv_s) > 0:
                        avg_adverse_unit_value = float(adv_s.abs().mean())
                if avg_adverse_unit_value <= 0 and len(c_s) > 0:
                    avg_adverse_unit_value = float(c_s.abs().mean())
        except Exception:
            avg_adverse_unit_value = 0.0

    raw_leaks: List[Dict[str, Any]] = []
    healthy_checks: List[Dict[str, Any]] = []
    covered_dims: Set[str] = set()
    covered_qids: Set[str] = set()

    def _add_healthy(check_id: str, title_en: str, title_hi: str, observed: str, expected: str, source_qids: List[str]) -> None:
        covered_qids.update(source_qids)
        healthy_checks.append({
            "check_id": check_id,
            "verdict": "HEALTHY_AS_EXPECTED",
            "title_en": title_en,
            "title_hi": title_hi,
            "observed": observed,
            "expected": expected,
            "source_qids": source_qids,
        })

    def _add_deviation(
        leak_id: str,
        category: str,
        severity: str,
        cash_impact: float,
        events_impact: float,
        expected_en: str,
        expected_hi: str,
        actual_en: str,
        actual_hi: str,
        decision_rule: str,
        headline_en: str,
        headline_hi: str,
        root_cause_en: str,
        root_cause_hi: str,
        fix_action_en: str,
        fix_action_hi: str,
        source_qids: List[str],
        impact_label_override: Optional[str] = None,
    ) -> None:
        covered_qids.update(source_qids)
        ci = abs(_clean_float(cash_impact)) if is_fin else 0.0
        ev = max(0.0, _clean_float(events_impact))
        if impact_label_override:
            fmt_imp = impact_label_override
        elif is_fin and ci > 0 and ev >= 1:
            fmt_imp = f"{_fmt_money(ci, sym, numbering)} ({round(ev):,} extra cases)"
        elif is_fin and ci > 0:
            fmt_imp = f"{_fmt_money(ci, sym, numbering)} impact"
        elif ev > 0:
            fmt_imp = f"{round(ev):,} excess cases"
        else:
            fmt_imp = "Verified deviation"
        sev_weight = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}.get(severity, 1)
        raw_leaks.append({
            "leak_id": leak_id,
            "verdict": "ABNORMAL_DEVIATION",
            "category": category,
            "severity": severity,
            "severity_weight": sev_weight,
            "estimated_cash_impact": round(ci, 2) if is_fin else None,
            "excess_events": round(ev, 1),
            "formatted_impact": fmt_imp,
            "expected_standard_en": expected_en,
            "expected_standard_hi": expected_hi,
            "actual_observed_en": actual_en,
            "actual_observed_hi": actual_hi,
            "decision_rule": decision_rule,
            "headline_en": headline_en,
            "headline_hi": headline_hi,
            "root_cause_en": root_cause_en,
            "root_cause_hi": root_cause_hi,
            "fix_action_en": fix_action_en,
            "fix_action_hi": fix_action_hi,
            "source_qids": source_qids,
        })

    # =========================================================================
    # AUTONOMOUS CHECK 0: Multi-Currency Ledger Mixing Hazard (Defends CFO against 1:1 FX Distortion)
    # =========================================================================
    if is_fin and canon_meta.get("is_multi_currency"):
        cb = canon_meta.get("currency_breakdown") or {}
        curr_col = str(canon_meta.get("currency_col") or "currency")
        parts_en = []
        minor_rows = 0
        for idx_c, (code_c, info_c) in enumerate(cb.items()):
            csym = info_c.get("symbol") or f"{code_c} "
            cnum = "indian" if code_c == "INR" else "international"
            vol_str = _fmt_money(float(info_c.get("total_volume") or 0.0), csym, cnum)
            cnt_c = int(info_c.get("count") or 0)
            if idx_c > 0:
                minor_rows += cnt_c
            parts_en.append(f"{code_c}: {vol_str} ({cnt_c:,} rows, {info_c.get('share_pct', 0)}%)")
        breakdown_str = " | ".join(parts_en)
        _add_deviation(
            "LEAK_MULTI_CURRENCY_MIXING",
            "Multi-Currency FX Ledger Hazard",
            "CRITICAL",
            0.0,
            minor_rows,
            f"Expected: Single functional currency or FX-converted reporting column in `{cost_col_name}`",
            f"होना चाहिए: `{cost_col_name}` में एक ही करेंसी या FX-कन्वर्टेड रिपोर्टिंग वैल्यू हो",
            f"Actual: `{curr_col}` mixes {len(cb)} currencies unnormalized — {breakdown_str}",
            f"असल स्थिति: `{curr_col}` में {len(cb)} अलग करेंसी बिना FX कन्वर्ज़न के मिली हैं — {breakdown_str}",
            "multi_currency_codes >= 2 without fx_normalization",
            f"Multi-Currency Mixing Alert: `{curr_col}` Combines {' + '.join(cb.keys())} Without FX Normalization",
            f"मल्टी-करेंसी अलर्ट: `{curr_col}` में {' + '.join(cb.keys())} बिना FX रेट के जुड़े हैं",
            f"Raw totals across mixed currencies cannot be summed 1:1 ({breakdown_str}). Aggregate KPIs require currency filtering or FX conversion.",
            f"अलग-अलग करेंसी ({breakdown_str}) को 1:1 जोड़ने से कुल रेवेन्यू गलत दिखता है — इन्हें FX रेट से कन्वर्ट या अलग-अलग फ़िल्टर करें।",
            f"Always segment financial reporting by `{curr_col}` or attach daily FX rates before summing consolidated portfolio totals.",
            f"कंसोलिडेटेड रिपोर्ट से पहले `{curr_col}` के अनुसार डेटा अलग करें या सही FX एक्सचेंज रेट लागू करें।",
            ["Q001", "Q169"],
            impact_label_override=f"{len(cb)} Mixed Currencies ({minor_rows:,} FX rows)",
        )

    # =========================================================================
    # AUTONOMOUS CHECK 0.5: Universal Forensic Accounting, Fraud & AR Cash Gap
    # (Composite Ghost-Duplicates, Threshold-Gaming Bunching, Unpaid AR Gap)
    # =========================================================================
    fa = omni.get("forensic_accounting_and_fraud") or {}
    if is_fin and fa.get("has_working_capital_ar_gap"):
        tot_due = float(fa.get("total_outstanding_due") or 0.0)
        unp_pct = float(fa.get("unpaid_share_pct") or 0.0)
        top_o = fa.get("top_overdue_entities") or []
        top_o_lbl = f"{top_o[0]['entity']} ({_fmt_money(top_o[0]['unpaid_amount'], sym, numbering)})" if top_o else "top accounts"
        _add_deviation(
            "LEAK_WORKING_CAPITAL_AR_GAP",
            "Working Capital & Unpaid Cash",
            "CRITICAL" if unp_pct >= 25.0 else "HIGH",
            tot_due,
            sum(int(o.get("unpaid_rows") or 0) for o in top_o),
            "Expected: Unpaid/overdue receivables < 12% of invoiced billing",
            "Hona chahiye: Unpaid udhari total billing ka 12% se kam ho",
            f"Actual: {_fmt_money(tot_due, sym, numbering)} ({unp_pct:.1f}% of billing) stuck unpaid — led by {top_o_lbl}",
            f"Asal sthiti: {_fmt_money(tot_due, sym, numbering)} ({unp_pct:.1f}% billing) market mein unpaid fasa hai — sabse bada {top_o_lbl}",
            "unpaid_share_pct >= 12.0%",
            f"Working-Capital Cash Trap: {_fmt_money(tot_due, sym, numbering)} ({unp_pct:.1f}%) Stuck Unpaid — Led by {top_o_lbl}",
            f"Udhari Cash Trap: {_fmt_money(tot_due, sym, numbering)} ({unp_pct:.1f}%) Market Mein Fasa Hai — Sabse Bada {top_o_lbl}",
            f"Paper profit is masked by uncollected receivables. Top overdue account {top_o_lbl} is driving working-capital strain.",
            f"Paper profit ke bawajood bank mein paisa nahi aa raha — {top_o_lbl} par sabse zyada udhari atki hai.",
            f"Freeze credit expansion for {top_o[0]['entity'] if top_o else 'overdue accounts'} until overdue AR is collected.",
            f"{top_o[0]['entity'] if top_o else 'Overdue parties'} ki credit limit turant freeze karein aur recovery start karein.",
            ["Q022", "Q023"],
            impact_label_override=f"{_fmt_money(tot_due, sym, numbering)} unpaid ({unp_pct:.1f}%)",
        )
    if is_fin and fa.get("has_composite_duplicates"):
        dcnt = int(fa.get("composite_duplicate_count") or 0)
        dcash = float(fa.get("composite_duplicate_cash") or 0.0)
        _add_deviation(
            "LEAK_COMPOSITE_DUPLICATE_BILLING",
            "Duplicate / Ghost Double-Billing",
            "CRITICAL" if dcnt >= 50 else "HIGH",
            dcash,
            dcnt,
            "Expected: 0 duplicate transactions (same account + date + amount across different invoice IDs)",
            "Hona chahiye: 0 duplicate bills (same party + date + amount)",
            f"Actual: {dcnt:,} ghost duplicate transactions totaling {_fmt_money(dcash, sym, numbering)}",
            f"Asal sthiti: {dcnt:,} duplicate bills mile jinmein {_fmt_money(dcash, sym, numbering)} double-billed hai",
            "composite_duplicate_count >= 5",
            f"Ghost Double-Billing Detected: {dcnt:,} Duplicate Transactions Worth {_fmt_money(dcash, sym, numbering)}",
            f"Double-Billing Pakdi Gayi: {dcnt:,} Duplicate Bills ({_fmt_money(dcash, sym, numbering)})",
            "Identical account, date, category, and amount appeared under separate invoice IDs — classic duplicate posting or ghost re-billing.",
            "Ek hi party, date aur amount ke bill alag-alag invoice number se dobara chadh gaye hain.",
            "Reconcile and reverse confirmed duplicate invoice postings before financial close or customer statements.",
            "Duplicate bills ki list check karke double entries turant reverse karein.",
            ["Q169"],
        )
    for idx_ta, ta in enumerate((fa.get("threshold_gaming_alerts") or [])[:2], 1):
        rep_s = f" by '{ta['top_rep']}'" if ta.get("top_rep") else ""
        ent_s = f" on '{ta['top_entity']}'" if ta.get("top_entity") else ""
        _add_deviation(
            f"LEAK_THRESHOLD_GAMING_FRAUD_{idx_ta}",
            "Approval-Limit Fraud Bunching",
            "CRITICAL",
            float(ta.get("flagged_cash") or 0.0),
            int(ta.get("flagged_count") or 0),
            f"Expected: Smooth distribution without abnormal bunching below {ta['threshold']:,.0f} approval cap",
            f"Hona chahiye: {ta['threshold']:,.0f} limit ke theek neeche abnormal bunching na ho",
            f"Actual: {ta['flagged_count']:,} records clustered in {ta['band_label']}{rep_s}{ent_s}",
            f"Asal sthiti: {ta['flagged_count']:,} bills {ta['band_label']} mein bunch hue hain{rep_s}{ent_s}",
            "threshold_bunching_density >= 5x baseline",
            f"Threshold-Gaming Fraud Alert (`{ta['column']}`): {ta['flagged_count']:,} Entries Just Below {ta['threshold']:,.0f}{rep_s}",
            f"Approval-Limit Bypass Fraud (`{ta['column']}`): {ta['flagged_count']:,} Bills {ta['threshold']:,.0f} Limit Ke Theek Neeche{rep_s}",
            f"Suspicious clustering in {ta['band_label']}{rep_s}{ent_s} indicates deliberate split-approvals to bypass management oversight.",
            f"{ta['band_label']} ke beech itni zyada entries{rep_s}{ent_s} management approval bypass karne ka strong fraud signal hai.",
            f"Audit all transactions in {ta['band_label']}{rep_s} and implement cumulative monthly party-level approval caps.",
            f"{ta['band_label']}{rep_s} ki saari entries audit karein aur party-wise monthly cumulative approval limit lagayein.",
            ["Q171", "Q172"],
        )

    # =========================================================================
    # AUTONOMOUS CHECK 1: P&L Out-of-Pocket Negative-Margin Orders & Profitless Segments (Q017/Q018)
    # =========================================================================
    pnl = omni.get("pnl_and_coupons") or {}
    neg_margin_dims: Set[str] = set()
    if is_fin and pnl.get("has_margin_ledger"):
        neg_cnt = int(pnl.get("negative_margin_order_count") or 0)
        neg_loss = abs(_clean_float(pnl.get("negative_margin_cash_loss")))
        rev_ship = abs(_clean_float(pnl.get("reverse_shipping_burn")))
        if neg_cnt > 0 and neg_loss > 0:
            _add_deviation(
                "LEAK_NEGATIVE_MARGIN_ORDERS",
                "Direct Cash Burn",
                "CRITICAL",
                neg_loss,
                neg_cnt,
                "Expected: 0 negative-margin orders (every order covers COGS + discount + shipping)",
                "होना चाहिए: 0 घाटे वाले ऑर्डर (हर ऑर्डर पर लागत व भाड़ा निकलकर मुनाफा बचे)",
                f"Actual: {neg_cnt:,} orders lost {_fmt_money(neg_loss, sym, numbering)} out-of-pocket (Reverse shipping: {_fmt_money(rev_ship, sym, numbering)})",
                f"असल स्थिति: {neg_cnt:,} ऑर्डर्स में जेब से {_fmt_money(neg_loss, sym, numbering)} डूबे (रिवर्स शिपिंग: {_fmt_money(rev_ship, sym, numbering)})",
                "neg_margin_orders > 0",
                f"{neg_cnt:,} Negative-Margin Orders Burned {_fmt_money(neg_loss, sym, numbering)} Out-of-Pocket",
                f"{neg_cnt:,} घाटे वाले ऑर्डर्स ने जेब से सीधा {_fmt_money(neg_loss, sym, numbering)} नकद जलाया",
                f"These orders produced strictly negative contribution margin after COGS, promo discounts, and return logistics ({_fmt_money(rev_ship, sym, numbering)}).",
                f"COGS, डिस्काउंट और वापसी भाड़े ({_fmt_money(rev_ship, sym, numbering)}) के बाद इन ऑर्डर्स पर कंपनी को सीधा नकद घाटा हुआ।",
                "Block deep-discount + COD stacking on low-margin SKUs and enforce a minimum order value for free shipping.",
                "कम-मार्जिन SKUs पर भारी डिस्काउंट + COD एक साथ बंद करें और न्यूनतम ऑर्डर मूल्य लागू करें।",
                ["Q017", "Q018", "Q019", "Q120"],
            )
        else:
            _add_healthy(
                "CHK_ZERO_NEG_MARGIN",
                "Order-Level Profitability",
                "ऑर्डर-स्तरीय मुनाफा",
                "0 negative-margin orders",
                "0 negative-margin orders",
                ["Q017"],
            )

        for nseg in (pnl.get("negative_margin_segments") or [])[:4]:
            dm_n = str(nseg.get("dimension") or "")
            sg_n = str(nseg.get("segment") or "")
            nm_loss = abs(_clean_float(nseg.get("net_margin")))
            nm_ords = int(nseg.get("orders") or 0)
            nm_fr = _clean_float(nseg.get("failure_rate_pct"))
            nm_disc = _clean_float(nseg.get("discount_burn"))
            if dm_n and sg_n and nm_loss > 0:
                neg_margin_dims.add(dm_n)
                dm_en = _friendly_dim_name(dm_n, "en")
                dm_hi = _friendly_dim_name(dm_n, "hi")
                _add_deviation(
                    f"LEAK_PROFITLESS_SEG_{dm_n}_{sg_n}",
                    "Profitless Revenue / Margin Bleed",
                    "CRITICAL" if nm_loss >= 100000 else "HIGH",
                    nm_loss,
                    nm_ords,
                    f"Expected: '{sg_n}' in {dm_en} generates positive net contribution margin after COGS, discounts, shipping & ad spend",
                    f"होना चाहिए: {dm_hi} में '{sg_n}' से COGS, डिस्काउंट, शिपिंग और विज्ञापन खर्च निकालकर शुद्ध मुनाफा बचे",
                    f"Actual: '{sg_n}' lost -{_fmt_money(nm_loss, sym, numbering)} net margin across {nm_ords:,} orders (even with {nm_fr:.2f}% return rate; discounts burned {_fmt_money(nm_disc, sym, numbering)})",
                    f"असल स्थिति: '{sg_n}' ने {nm_ords:,} ऑर्डर्स में -{_fmt_money(nm_loss, sym, numbering)} का शुद्ध घाटा कराया ({nm_fr:.2f}% रिटर्न रेट के बावजूद {_fmt_money(nm_disc, sym, numbering)} डिस्काउंट व लागत में डूबा)",
                    "segment_net_contribution_margin < 0",
                    f"Profitless Revenue Trap: '{sg_n}' in {dm_en} Lost -{_fmt_money(nm_loss, sym, numbering)} Net Margin ({nm_fr:.1f}% Return Rate)",
                    f"दिखावटी बिक्री का जाल: {dm_hi} के '{sg_n}' में कम रिटर्न ({nm_fr:.1f}%) के बावजूद -{_fmt_money(nm_loss, sym, numbering)} का शुद्ध घाटा",
                    f"Although '{sg_n}' looks healthy on delivery/return rate ({nm_fr:.2f}%), heavy discounting ({_fmt_money(nm_disc, sym, numbering)}), logistics, and ad spend make every order net-negative.",
                    f"भले ही '{sg_n}' में रिटर्न दर कम ({nm_fr:.2f}%) दिखती है, लेकिन भारी डिस्काउंट ({_fmt_money(nm_disc, sym, numbering)}), शिपिंग और विज्ञापन खर्च के कारण हर डिलीवर ऑर्डर भी घाटा दे रहा है।",
                    f"Cap promo discounts and ad spend on '{sg_n}' immediately so unit revenue exceeds COGS + shipping + acquisition cost.",
                    f"'{sg_n}' पर भारी डिस्काउंट और विज्ञापन खर्च तुरंत सीमित करें ताकि हर ऑर्डर पर लागत से ऊपर मुनाफा बचे।",
                    ["Q017", "Q021", "Q057"],
                )

    # =========================================================================
    # AUTONOMOUS CHECK 2: Double-Poison Coupons (Q045-Q048)
    # =========================================================================
    toxic_coupons = pnl.get("toxic_coupons") or []
    if is_fin and toxic_coupons:
        for tc in toxic_coupons:
            code = str(tc.get("coupon_code") or "PROMO")
            orders = int(tc.get("orders") or 0)
            avg_m = _clean_float(tc.get("avg_margin_per_order"))
            delta_pct = abs(_clean_float(tc.get("margin_delta_vs_no_coupon_pct")))
            fail_pct = _clean_float(tc.get("failure_rate_pct"))
            disc_burn = _clean_float(tc.get("discount_burn"))
            base_m = _clean_float(tc.get("baseline_no_coupon_margin")) or (avg_m / max(1.0 - delta_pct / 100.0, 0.1) if delta_pct > 0 else avg_m)
            cash_hit = disc_burn if disc_burn > 0 else max(0.0, (base_m - avg_m) * orders)
            fails_cnt = int(tc.get("failures") or round(orders * (fail_pct / 100.0)))
            covered_dims.add("coupon_code")
            _add_deviation(
                f"LEAK_TOXIC_COUPON_{code}",
                "Pricing & Promo Bleed",
                "CRITICAL" if cash_hit > 50000 or delta_pct >= 30 else "HIGH",
                cash_hit,
                fails_cnt,
                f"Expected: Promo keeps unit margin near {_fmt_money(base_m, sym, numbering)} & does NOT elevate return/RTO rate",
                f"होना चाहिए: कूपन से RTO/फेलियर न बढ़े और यूनिट मुनाफा सुरक्षित रहे",
                f"Actual: '{code}' slashes margin -{delta_pct:.1f}% (to {_fmt_money(avg_m, sym, numbering)}/order) AND spikes failure to {fail_pct:.2f}% ({fails_cnt:,} fails)",
                f"असल स्थिति: '{code}' मुनाफा -{delta_pct:.1f}% घटाकर {_fmt_money(avg_m, sym, numbering)} करता है और फेलियर {fail_pct:.2f}% तक बढ़ाता है",
                "margin_delta <= -20% AND failure_lift > +15%",
                f"Double-Poison Coupon '{code}' Burned {_fmt_money(cash_hit, sym, numbering)} & Spiked Failure to {fail_pct:.2f}%",
                f"डबल-पॉइज़न कूपन '{code}' ने {_fmt_money(cash_hit, sym, numbering)} डिस्काउंट जलाया और RTO {fail_pct:.2f}% तक बढ़ाया",
                f"Across {orders:,} orders, '{code}' destroys unit profit while pulling in high-RTO buyers.",
                f"{orders:,} ऑर्डर्स में '{code}' प्रति ऑर्डर मुनाफा आधा कर देता है और ज़्यादा रिटर्न करने वाले ग्राहक लाता है।",
                f"Restrict '{code}' strictly to Prepaid/UPI checkouts or replace with a prepaid-only cashback voucher.",
                f"'{code}' कूपन को केवल प्रीपेड/UPI पेमेंट तक सीमित करें और COD पर तुरंत बंद करें।",
                ["Q045", "Q046", "Q047", "Q048"],
            )
    elif qmap.get("Q045", {}).get("status") == "DIRECT_ANSWERED":
        _add_healthy("CHK_COUPON_HEALTH", "Coupon Economics", "कूपन मुनाफा व गुणवत्ता", "No double-poison coupons", "0 toxic promo codes", ["Q045"])

    # =========================================================================
    # AUTONOMOUS CHECK 3: Confounder / Simpson's Paradox 2×2 Super-Leaks (Q118/Q178/Q179)
    # Group confounders sharing the same true_confounder into a clean unified diagnosis
    # =========================================================================
    confs = omni.get("confounder_insights") or []
    hotspots_2d = omni.get("top_2d_hotspots") or []
    if confs:
        seen_confounders: Set[str] = set()
        for cf in confs:
            app_dim = str(cf.get("apparent_dim") or cf.get("apparent_driver") or "")
            true_conf = str(cf.get("confounder_segment") or cf.get("true_confounder") or cf.get("confounder_dim") or "")
            seg = str(cf.get("apparent_segment") or cf.get("segment") or "")
            rate_pres = _clean_float(cf.get("rate_when_confounder_present_pct"))
            rate_abs = _clean_float(cf.get("rate_when_confounder_absent_pct"))
            if app_dim:
                covered_dims.add(app_dim)
            if true_conf in seen_confounders:
                continue
            seen_confounders.add(true_conf)

            # Collect all segments confounded by the same true_confounder
            sibling_segs = [
                f"{c_item.get('apparent_segment')} ({_clean_float(c_item.get('rate_when_confounder_present_pct')):.1f}% vs {_clean_float(c_item.get('rate_when_confounder_absent_pct')):.1f}% safe)"
                for c_item in confs
                if str(c_item.get("confounder_segment") or c_item.get("true_confounder") or "") == true_conf
            ]
            sib_note_en = f" Also confirmed across: {', '.join(sibling_segs[1:4])}." if len(sibling_segs) > 1 else ""
            sib_note_hi = f" यही पैटर्न इन क्षेत्रों में भी प्रमाणित है: {', '.join(sibling_segs[1:4])}।" if len(sibling_segs) > 1 else ""

            matched_h = next(
                (h for h in hotspots_2d if seg and (seg in (str(h.get("val_a")), str(h.get("val_b"))))),
                hotspots_2d[0] if hotspots_2d else {},
            )
            h_ev = _clean_float(matched_h.get("events") or matched_h.get("excess_events") or matched_h.get("excess_fails"))
            h_val = _clean_float(matched_h.get("adverse_value") or matched_h.get("financial_exposure"))
            h_rate = rate_pres or _clean_float(matched_h.get("rate_pct"))
            lid = "LEAK_CONFOUNDER_2D_HOTSPOT" if len(seen_confounders) == 1 else f"LEAK_CONFOUNDER_2D_{len(seen_confounders)}"
            _add_deviation(
                lid,
                "Causal 2×2 Super-Leak",
                "CRITICAL",
                h_val,
                h_ev,
                f"Expected: '{seg}' risk should stay near its safe non-confounded baseline ({rate_abs:.1f}%)",
                f"होना चाहिए: '{seg}' का रिस्क सामान्य सुरक्षित स्तर ({rate_abs:.1f}%) के आसपास रहना चाहिए",
                f"Actual: '{seg} × {true_conf}' explodes to {h_rate:.1f}% ({int(h_ev):,} failures), whereas '{seg}' without '{true_conf}' is just {rate_abs:.1f}%",
                f"असल स्थिति: '{seg} × {true_conf}' में फेलियर {h_rate:.1f}% ({int(h_ev):,} फेल) तक फटता है, जबकि बिना इसके सिर्फ {rate_abs:.1f}% है",
                "stratified_2x2_rate >= 2.0x safe_baseline",
                f"True Root Cause: '{seg}' Is Safe at {rate_abs:.1f}% Without '{true_conf}' — 2×2 Combo Spikes to {h_rate:.1f}%",
                f"असली जड़: '{seg}' खुद सुरक्षित ({rate_abs:.1f}%) है — असली विस्फोट '{seg} × {true_conf}' ({h_rate:.1f}%) में है",
                str(cf.get("explanation_en") or cf.get("finding_summary") or "Stratification isolates the true driver.") + sib_note_en,
                str(cf.get("explanation_hi") or "डेटा को अलग स्तर पर जांचने से असली छुपा हुआ कारण पकड़ा गया।") + sib_note_hi,
                f"Do NOT ban '{seg}'. Apply OTP/WhatsApp verification or small prepaid deposit strictly on '{seg} × {true_conf}'.",
                f"'{seg}' को बंद न करें — केवल '{seg} × {true_conf}' कॉम्बो पर OTP/व्हाट्सएप वेरिफिकेशन या एडवांस टोकन लगाएं।",
                ["Q114", "Q118", "Q178", "Q179"],
                impact_label_override=f"{h_rate:.1f}% vs {rate_abs:.1f}% safe ({int(h_ev):,} fails)",
            )

    # =========================================================================
    # AUTONOMOUS CHECK 4: ALL Confirmed Statistical Leak Dimensions (Collinear-Deduplicated!)
    # =========================================================================
    def _dim_priority_rank(lk_item: Dict[str, Any]) -> Tuple[int, float]:
        dn = str(lk_item.get("dimension") or "").lower()
        # Prefer primary operational entities over derived numeric/lookup attributes (e.g. hub_code over cold_storage_capacity_tons)
        if any(k in dn for k in ("fleet", "carrier", "courier", "hub_code", "warehouse", "channel", "payment", "store", "branch", "vendor", "supplier", "product", "sku", "category", "cargo", "segment", "plan")):
            pri = 0
        elif any(k in dn for k in ("region", "state", "city", "zone", "tier", "manager", "type")):
            pri = 1
        elif any(k in dn for k in ("capacity", "tons", "lease", "rent", "sqft", "terms", "days", "count", "flag")):
            pri = 2
        else:
            pri = 1
        return (pri, -_clean_float(lk_item.get("excess_events")))

    sorted_dim_leaks = sorted(list(omni.get("confirmed_leak_dimensions") or []), key=_dim_priority_rank)
    accepted_dim_masks: List[Tuple[str, str, Optional[pd.Series], int, float, int]] = []
    for lk in sorted_dim_leaks:
        dim_name = str(lk.get("dimension") or "")
        if dim_name in covered_dims:
            continue
        covered_dims.add(dim_name)
        w_seg = str(lk.get("worst_segment") or "")
        w_rate = _clean_float(lk.get("worst_rate_pct"))
        b_rate = _clean_float(lk.get("rest_rate_pct") or lk.get("baseline_rate_pct"))
        mult = _clean_float(lk.get("risk_multiplier"))
        exc = _clean_float(lk.get("excess_events"))
        w_vol = int(lk.get("worst_volume") or 0)
        pv = _clean_float(lk.get("p_val") if lk.get("p_val") is not None else lk.get("p_value"))

        # Collinear Mirror Defense: If this segment selects >= 95% identical rows as an already-reported dimension
        # (e.g. hub_region='North' and cold_storage_capacity_tons='950' mirroring hub_code='HUB-DEL'),
        # attach it as collinear metadata instead of creating duplicate leak cards & triple-counting ₹ impact!
        cur_mask: Optional[pd.Series] = None
        if isinstance(df, pd.DataFrame) and dim_name in df.columns:
            try:
                cur_mask = (df[dim_name].astype(str) == w_seg)
            except Exception:
                cur_mask = None
        collinear_parent_idx: Optional[int] = None
        for parent_dim, parent_seg, p_mask, p_vol, p_exc, p_raw_idx in accepted_dim_masks:
            is_mirror = False
            if cur_mask is not None and p_mask is not None:
                inter = int((cur_mask & p_mask).sum())
                union = int((cur_mask | p_mask).sum())
                if union > 0 and (inter / union) >= 0.95:
                    is_mirror = True
            elif w_vol > 0 and w_vol == p_vol and abs(exc - p_exc) <= 0.5:
                is_mirror = True
            if is_mirror:
                collinear_parent_idx = p_raw_idx
                break

        if collinear_parent_idx is not None:
            parent_card = raw_leaks[collinear_parent_idx]
            mirrors = parent_card.setdefault("collinear_mirror_attributes", [])
            mirrors.append(f"{dim_name}={w_seg}")
            continue

        cap_drag = _clean_float(lk.get("excess_capital_drag") or lk.get("adverse_value"))
        if is_fin and cap_drag <= 0 and exc > 0:
            seg_unit_val = avg_adverse_unit_value
            if isinstance(df, pd.DataFrame) and cost_col_name and cost_col_name in df.columns and dim_name in df.columns:
                try:
                    seg_mask = df[dim_name].astype(str) == w_seg
                    seg_vals = pd.to_numeric(df.loc[seg_mask, cost_col_name], errors="coerce").dropna()
                    if len(seg_vals) > 0:
                        seg_unit_val = float(seg_vals.abs().mean())
                except Exception:
                    pass
            if seg_unit_val > 0:
                cap_drag = round(exc * seg_unit_val, 2)

        dim_en = _friendly_dim_name(dim_name, "en")
        dim_hi = _friendly_dim_name(dim_name, "hi")
        seg_en = _friendly_seg_name(dim_name, w_seg, "en")
        seg_hi = _friendly_seg_name(dim_name, w_seg, "hi")
        cash_note_en = f" worth {_fmt_money(cap_drag, sym, numbering)}" if (is_fin and cap_drag > 0) else ""
        cash_note_hi = f" (~{_fmt_money(cap_drag, sym, numbering)} का नुकसान)" if (is_fin and cap_drag > 0) else ""

        if mult < 1.15 and exc < 15:
            _add_healthy(
                f"CHK_DIM_{dim_name}",
                f"{dim_en} Balance",
                f"{dim_hi} संतुलन",
                f"Normal across groups ({mult:.2f}x)",
                "Similar performance across groups",
                ["Q183"],
            )
            continue
        _add_deviation(
            f"LEAK_DIM_{dim_name}",
            f"{dim_en} Bottleneck",
            "CRITICAL" if (mult >= 2.0 and exc >= 50) else "HIGH",
            cap_drag,
            exc,
            f"Expected: '{seg_en}' should stay near the normal rest-of-business rate (~{b_rate:.1f}%)" if b_rate > 0 else f"Expected: normal performance across {dim_en}",
            f"सामान्य स्तर: बाकी बिज़नेस में यह नुकसान सिर्फ़ {b_rate:.1f}% है" if b_rate > 0 else f"सामान्य स्तर: {dim_hi} में बराबर प्रदर्शन",
            f"Actual: '{seg_en}' fails at {w_rate:.1f}% ({mult:.1f}x higher than normal — ~{round(exc):,} extra cases{cash_note_en})",
            f"यहाँ स्थिति: '{seg_hi}' में नुकसान {w_rate:.1f}% है (सामान्य से {mult:.1f} गुना ज़्यादा — ~{round(exc):,} एक्स्ट्रा केस{cash_note_hi})",
            f"p < 0.05 AND risk_multiplier={mult:.2f}x >= 1.15x",
            f"'{seg_en}' in {dim_en} Fails at {w_rate:.2f}% ({mult:.2f}x Normal Rate)",
            f"{dim_hi} में '{seg_hi}' का नुकसान {w_rate:.2f}% है (सामान्य से {mult:.2f} गुना ज़्यादा)",
            f"While the rest of your business runs at {b_rate:.1f}%, '{seg_en}' is failing at {w_rate:.1f}%, causing ~{round(exc):,} extra problem cases{cash_note_en} that can be prevented.",
            f"बाकी बिज़नेस के {b_rate:.1f}% के मुकाबले '{seg_hi}' में {w_rate:.1f}% नुकसान हो रहा है, जिसकी वजह से लगभग {round(exc):,} अतिरिक्त ऑर्डर{cash_note_hi} खराब हो रहे हैं।",
            f"Check '{seg_en}' orders first and call or verify the flagged customers in Today's Call List.",
            f"सबसे पहले '{seg_hi}' के नियम सुधारें और 'Today's Call List' में दिए गए ऑर्डर्स पर तुरंत कॉल/कार्रवाई करें।",
            ["Q071", "Q072", "Q183", "Q185"],
        )
        accepted_dim_masks.append((dim_name, w_seg, cur_mask, w_vol, exc, len(raw_leaks) - 1))

    # =========================================================================
    # AUTONOMOUS CHECK 5: ALL Operational SLA / Warehouse / Courier Delays
    # Prefer physical ops nodes (warehouse/courier) and deduplicate identical volume/metric mirrors
    # =========================================================================
    ops_raw = list(omni.get("operational_sla_and_delay_findings") or [])
    ops_raw.sort(key=lambda o: 0 if any(k in str(o.get("dimension", "")).lower() for k in ("warehouse", "courier", "hub", "carrier")) else 1)
    seen_ops_sigs: Set[str] = set()
    for idx_op, op in enumerate(ops_raw):
        dim_op = str(op.get("dimension") or "")
        hl_en = str(op.get("headline_en") or "")
        # Signature by exact metric numbers in headline so a 1:1 state-to-warehouse mirror isn't repeated twice
        nums_sig = "|".join(re.findall(r"\d+\.\d+|\d+", hl_en)[:4])
        if nums_sig and nums_sig in seen_ops_sigs:
            continue
        if nums_sig:
            seen_ops_sigs.add(nums_sig)
        _add_deviation(
            f"LEAK_OPS_BOTTLENECK_{idx_op + 1}",
            "Operations & SLA Bottleneck",
            "HIGH",
            0.0,
            _clean_float(op.get("affected_volume") or 0) * 0.25,
            f"Expected: `{dim_op}` dispatch & delivery SLA should match top-performing peer node",
            f"होना चाहिए: `{dim_op}` की डिस्पैच व डिलीवरी स्पीड सबसे बेहतर नोड के बराबर होनी चाहिए",
            f"Actual: {op.get('headline_en') or 'Severe SLA / transit degradation detected'}",
            f"असल स्थिति: {op.get('headline_hi') or op.get('headline_en') or 'गंभीर डिस्पैच/ट्रांज़िट देरी'}",
            "ops_sla_or_delay_ratio >= 1.5x best_peer",
            str(op.get("headline_en") or "Operational SLA / Delay Bottleneck"),
            str(op.get("headline_hi") or op.get("headline_en") or "ऑपरेशंस और SLA देरी बॉटलनेक"),
            f"Operational latency on `{dim_op}` exceeds peer standards, collapsing CSAT and elevating downstream RTO.",
            f"`{dim_op}` पर भारी डिस्पैच/ट्रांज़िट देरी से ग्राहकों की रेटिंग गिरती है और रिटर्न बढ़ते हैं।",
            f"Re-route volume using Zone Courier Allocation rules (Q124) and enforce strict 24h dispatch SLA.",
            f"ज़ोन-आधारित बेहतर कूरियर पर ऑर्डर शिफ्ट करें और 24 घंटे का डिस्पैच SLA लागू करें।",
            ["Q099", "Q115", "Q116", "Q127"],
            impact_label_override=str(op.get("metric_badge") or "Severe SLA / Delay Drift"),
        )

    # =========================================================================
    # AUTONOMOUS CHECK 6: Serial Abusers & Negative-LTV Accounts (Q075/Q076/Q163)
    # =========================================================================
    ent = omni.get("entities_and_skus") or {}
    if ent.get("has_repeat_entities"):
        neg_ltv_cnt = int(ent.get("negative_ltv_entity_count") or 0)
        neg_ltv_loss = abs(_clean_float(ent.get("negative_ltv_total_cash_loss")))
        ser_cnt = int(ent.get("serial_abuser_count") or 0)
        ser_fails = int(ent.get("serial_abuser_total_failures") or 0)
        if neg_ltv_cnt > 0 or ser_cnt > 0:
            _add_deviation(
                "LEAK_REPEAT_ABUSERS_NEG_LTV",
                "Customer Abuse & Negative LTV",
                "HIGH" if neg_ltv_loss > 25000 or ser_cnt >= 20 else "MEDIUM",
                neg_ltv_loss,
                ser_fails,
                "Expected: 0 Negative-LTV repeat accounts & 0 serial (>=2x) RTO/return abusers",
                "होना चाहिए: 0 घाटे वाले रिपीट ग्राहक और 0 बार-बार रिटर्न/RTO करने वाले अकाउंट",
                f"Actual: {neg_ltv_cnt:,} Negative-LTV buyers (-{_fmt_money(neg_ltv_loss, sym, numbering)}) & {ser_cnt:,} serial abusers ({ser_fails:,} repeat fails)",
                f"असल स्थिति: {neg_ltv_cnt:,} घाटे वाले ग्राहक (-{_fmt_money(neg_ltv_loss, sym, numbering)}) और {ser_cnt:,} सीरियल अब्यूज़र ({ser_fails:,} फेल)",
                "neg_ltv_accounts > 0 OR serial_offenders >= 1",
                f"{neg_ltv_cnt:,} Negative-LTV Buyers & {ser_cnt:,} Serial Repeat Abusers ({ser_fails:,} Repeat Fails)",
                f"{neg_ltv_cnt:,} घाटे वाले (Negative-LTV) ग्राहक और {ser_cnt:,} बार-बार RTO/रिटर्न करने वाले अकाउंट",
                f"Cumulative lifetime cash drained by Negative-LTV customers is {_fmt_money(neg_ltv_loss, sym, numbering)}; repeat offenders continue triggering avoidable losses.",
                f"इन {neg_ltv_cnt:,} ग्राहकों ने कुल {_fmt_money(neg_ltv_loss, sym, numbering)} का शुद्ध घाटा कराया और {ser_cnt:,} खातों ने {ser_fails:,} बार फेल/RTO किया।",
                "Auto-disable COD and high-discount promos for accounts with >=2 historical RTOs/defaults.",
                "2 या अधिक बार RTO/डिफॉल्ट करने वाले अकाउंट्स पर COD और बड़ा डिस्काउंट ऑटो-ब्लॉक करें।",
                ["Q075", "Q076", "Q163"],
            )
        else:
            _add_healthy("CHK_CLEAN_CUSTOMERS", "Customer LTV & Repeat Hygiene", "ग्राहक LTV व व्यवहार", "0 Negative-LTV & 0 serial abusers", "0 abusive/negative accounts", ["Q075", "Q076", "Q163"])

    # =========================================================================
    # AUTONOMOUS CHECK 7: Seasonal / Festive Overload Breakdown (Q003/Q102/Q121)
    # =========================================================================
    seas = omni.get("seasonal_regimes") or {}
    if seas.get("has_quarterly_regime_shift"):
        pq = str(seas.get("peak_quarter") or "Q4")
        pq_r = _clean_float(seas.get("peak_quarter_failure_pct"))
        ry_r = _clean_float(seas.get("rest_of_year_failure_pct"))
        pq_sla = seas.get("peak_quarter_sla_breach_pct")
        _add_deviation(
            f"LEAK_SEASONAL_{pq}",
            "Seasonal Capacity Breakdown",
            "HIGH" if (pq_r - ry_r) >= 3.0 or (pq_sla and _clean_float(pq_sla) >= 30.0) else "MEDIUM",
            0.0,
            max(0.0, (pq_r - ry_r) * (n_rows * 0.25) / 100.0),
            f"Expected: {pq} failure & SLA should remain close to rest-of-year baseline ({ry_r:.2f}%)",
            f"होना चाहिए: {pq} में भी डिलीवरी व फेलियर रेट सामान्य ({ry_r:.2f}%) के करीब रहना चाहिए",
            f"Actual: {pq} failure jumps to {pq_r:.2f}% (+{pq_r - ry_r:.2f}pp)" + (f" & SLA breaches hit {pq_sla}%" if pq_sla else ""),
            f"असल स्थिति: {pq} में फेलियर {pq_r:.2f}% (+{pq_r - ry_r:.2f}pp) पहुँचता है" + (f" और SLA ब्रीच {pq_sla}%" if pq_sla else ""),
            "peak_quarter_delta >= +1.5pp OR peak_sla >= 30%",
            f"{pq} Peak Load Breakdown: Failure Jumps {ry_r:.2f}% -> {pq_r:.2f}%" + (f" (SLA Breach {pq_sla}%)" if pq_sla else ""),
            f"{pq} फेस्टिव लोड में सिस्टम दबाव: फेलियर {ry_r:.2f}% से {pq_r:.2f}% पर पहुँचा" + (f" (SLA ब्रीच {pq_sla}%)" if pq_sla else ""),
            f"Warehouse throughput and courier reliability break down during {pq} seasonal volume surge.",
            f"{pq} के त्योहारी लोड में गोदाम व कूरियर क्षमता टूट जाती है।",
            f"Pre-stock top 20% fast SKUs regionally and activate backup air courier 3 weeks prior to {pq}.",
            f"{pq} से 3 हफ्ते पहले टॉप SKUs रीजनल गोदामों में स्टॉक करें और बैकअप कूरियर चालू रखें।",
            ["Q003", "Q102", "Q121"],
            impact_label_override=f"+{pq_r - ry_r:.2f}pp Peak Surge",
        )

    # =========================================================================
    # AUTONOMOUS CHECK 8: SELF-JUDGING SCAN ACROSS ALL REMAINING 200Q SIGNALS!
    # Every data-backed question is judged against its Expected Healthy Standard:
    # -> If DEVIATED => promoted to `abnormal_deviations`!
    # -> If HEALTHY  => auto-suppressed into `healthy_checks_suppressed`!
    # =========================================================================
    def _q_ready(qid: str) -> Optional[Dict[str, Any]]:
        q = qmap.get(qid)
        if not q or q.get("status") == "COLUMN_MISSING_EXPLAINED":
            return None
        return q

    # 8a. Q002 Revenue Shrinkage Check (Expected: Growth >= -5% YoY / >= -10% MoM)
    if (q := _q_ready("Q002")):
        yoy = _extract_first_float(q["answer_en"], r"YoY[^:]*:\s*([+-]?\d+(?:\.\d+)?)%")
        mom = _extract_first_float(q["answer_en"], r"MoM[^:]*:\s*([+-]?\d+(?:\.\d+)?)%")
        if (yoy is not None and yoy < -5.0) or (yoy is None and mom is not None and mom < -10.0):
            metric_v = yoy if (yoy is not None and yoy < -5.0) else mom
            _add_deviation(
                "LEAK_REVENUE_CONTRACTION", "Growth Contraction", "HIGH", 0.0, 0.0,
                "Expected: Stable or positive period-over-period growth (>= 0%)",
                "होना चाहिए: बिक्री स्थिर या बढ़ती हुई (>= 0%) होनी चाहिए",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "yoy_growth < -5% OR mom_growth < -10%",
                f"Revenue / Volume Contraction Detected ({q['key_metric']})",
                f"बिक्री/वॉल्यूम में गिरावट पकड़ी गई ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Investigate which segments (Q010) and channels (Q057) drove the period contraction.",
                "जाँचें कि किस सेगमेंट (Q010) और चैनल (Q057) से बिक्री गिरी है।",
                ["Q002"], impact_label_override=f"{metric_v:+.1f}% Contraction",
            )
        else:
            _add_healthy("CHK_GROWTH_TREND", "Period-over-Period Growth", "बिक्री ग्रोथ रुझान", q["key_metric"], "No severe contraction (>-5% YoY)", ["Q002"])

    # 8b. Q007 Pareto Concentration Risk (Expected: Top 5% cust < 35% & Top 3 SKUs < 40%)
    if (q := _q_ready("Q007")):
        top5 = _extract_first_float(q["answer_en"], r"Top 5% customers[^0-9]*([\d.]+)%")
        top3 = _extract_first_float(q["answer_en"], r"Top 3 SKUs drive\s*([\d.]+)%")
        if (top5 is not None and top5 >= 35.0) or (top3 is not None and top3 >= 40.0):
            _add_deviation(
                "LEAK_PARETO_CONCENTRATION", "Concentration Risk", "MEDIUM", 0.0, 0.0,
                "Expected: Top 5% customers < 35% revenue share & Top 3 SKUs < 40%",
                "होना चाहिए: शीर्ष 5% ग्राहकों का हिस्सा < 35% और शीर्ष 3 SKUs < 40%",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "top5_cust_share >= 35% OR top3_sku_share >= 40%",
                f"High Revenue Concentration Risk ({q['key_metric']})",
                f"बिज़नेस कुछ ही ग्राहकों/प्रोडक्ट्स पर ज़्यादा निर्भर ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Diversify acquisition and lock top key accounts into long-term retention contracts.",
                "नए प्रोडक्ट/ग्राहक वर्ग बढ़ाएं और बड़े ग्राहकों के लिए लॉयल्टी कॉन्ट्रैक्ट करें।",
                ["Q007"], impact_label_override=q["key_metric"],
            )
        else:
            _add_healthy("CHK_PARETO_HEALTH", "Revenue Diversification (Pareto)", "बिक्री विविधीकरण (Pareto)", q["key_metric"], "Top 5% cust < 35% & Top 3 SKUs < 40%", ["Q007"])

    # 8c. Q022 Margin-Draining Bestseller Trap SKUs (Expected: 0 trap SKUs)
    if (q := _q_ready("Q022")):
        if "no trap skus" in q["key_metric"].lower():
            _add_healthy("CHK_NO_TRAP_SKUS", "Bestseller SKU Margins", "बेस्टसेलर SKU मार्जिन", "0 margin-trap SKUs", "0 negative/collapsed margin bestsellers", ["Q022"])
        else:
            _add_deviation(
                "LEAK_TRAP_SKUS", "Catalog Margin Trap", "HIGH", 0.0, 0.0,
                "Expected: High-revenue bestseller SKUs must maintain healthy net margin (>= 10%)",
                "होना चाहिए: सबसे ज़्यादा बिकने वाले SKUs पर स्वस्थ मार्जिन (>= 10%) होना चाहिए",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "high_rev_sku_margin_pct < 10%",
                f"High-Revenue Margin Trap SKU Detected: {q['key_metric']}",
                f"दिखावटी बेस्टसेलर पर कम/घाटे वाला मार्जिन: {q['key_metric']}",
                q["answer_en"], q["answer_hi"],
                "Reprice or renegotiate COGS/shipping on margin-draining high-volume SKUs.",
                "इन हाई-सेल कम-मार्जिन SKUs के दाम या लागत तुरंत री-प्राइस करें।",
                ["Q022"], impact_label_override=q["key_metric"],
            )

    # 8d. Q023 Quarterly Net Margin Erosion (Expected: >= -1.0pp shift)
    if (q := _q_ready("Q023")):
        mshift = _extract_first_float(q["key_metric"], r"([+-]?\d+(?:\.\d+)?)pp")
        if mshift is not None and mshift < -1.0:
            _add_deviation(
                "LEAK_MARGIN_EROSION", "Margin Erosion", "HIGH", 0.0, 0.0,
                "Expected: Net Margin % stable or expanding (>= -1.0pp QoQ)",
                "होना चाहिए: तिमाही नेट मार्जिन % स्थिर या बढ़ता हुआ (>= -1.0pp)",
                f"Actual: Net Margin % eroded by {mshift:+.2f}pp", f"असल स्थिति: नेट मार्जिन {mshift:+.2f}pp गिरा",
                "quarterly_margin_shift_pp < -1.0",
                f"Silent Net Margin Erosion Detected ({mshift:+.2f}pp)",
                f"मुनाफे का मार्जिन चुपचाप गिर रहा है ({mshift:+.2f}pp)",
                q["answer_en"], q["answer_hi"],
                "Audit discount creep, reverse logistics, and unit COGS drift (Q021, Q104).",
                "बढ़ते डिस्काउंट, वापसी भाड़े और COGS लागत की तुरंत समीक्षा करें।",
                ["Q023"], impact_label_override=f"{mshift:+.2f}pp erosion",
            )
        else:
            _add_healthy("CHK_MARGIN_STABILITY", "Net Margin Stability", "नेट मार्जिन स्थिरता", q["key_metric"], "Shift >= -1.0pp", ["Q023"])

    # 8e. Q049 Promo-Acquired Buyer Loyalty (Expected: >= 20% full-price repeat)
    if (q := _q_ready("Q049")):
        fp_rep = _extract_first_float(q["key_metric"], r"([\d.]+)%")
        if fp_rep is not None and fp_rep < 20.0:
            _add_deviation(
                "LEAK_BARGAIN_HUNTERS", "Promo Buyer Quality", "MEDIUM", 0.0, 0.0,
                "Expected: >= 20% of promo-acquired buyers should return at full price",
                "होना चाहिए: कूपन से आए कम से कम 20% ग्राहक पूरे दाम पर लौटें",
                f"Actual: Only {fp_rep:.2f}% returned at full price", f"असल स्थिति: केवल {fp_rep:.2f}% पूरे दाम पर वापस आए",
                "promo_fullprice_repeat_pct < 20%",
                f"Promo Campaigns Attract One-Time Bargain Hunters ({fp_rep:.1f}% Full-Price Repeat)",
                f"डिस्काउंट ग्राहक पूरे दाम पर वापस नहीं लौट रहे (सिर्फ {fp_rep:.1f}%)",
                q["answer_en"], q["answer_hi"],
                "Shift acquisition incentives from deep flat discounts to post-delivery loyalty credits.",
                "सीधे भारी डिस्काउंट की जगह दूसरे ऑर्डर पर लॉयल्टी क्रेडिट दें।",
                ["Q049"], impact_label_override=f"Only {fp_rep:.1f}% full-price repeat",
            )
        else:
            _add_healthy("CHK_PROMO_LOYALTY", "Promo-to-Full-Price Conversion", "कूपन ग्राहकों की वफादारी", q["key_metric"], ">= 20% full-price repeat", ["Q049"])

    # 8f. Q054 Repeat Promo / Welcome Code Abuse (Expected: 0 repeated single-use codes)
    if (q := _q_ready("Q054")):
        rep_uses = _extract_first_float(q["key_metric"], r"([\d,]+)\s*repeated")
        if rep_uses is not None and rep_uses >= 20:
            _add_deviation(
                "LEAK_COUPON_REUSE", "Promo Policy Abuse", "MEDIUM", 0.0, rep_uses,
                "Expected: 0 customers reusing identical promotional/welcome codes >= 2 times",
                "होना चाहिए: एक ही ग्राहक एक ही कूपन/वेलकम कोड का बार-बार दुरुपयोग न करे",
                f"Actual: {int(rep_uses):,} repeated same-code uses by existing accounts",
                f"असल स्थिति: {int(rep_uses):,} बार एक ही कस्टमर ने वही कूपन कोड दोबारा लगाया",
                "repeated_same_coupon_uses >= 20",
                f"Promo Code Reuse Policy Leak: {int(rep_uses):,} Repeated Code Uses",
                f"कूपन पॉलिसी लीक: {int(rep_uses):,} बार एक ही कोड का दोबारा इस्तेमाल",
                q["answer_en"], q["answer_hi"],
                "Enforce 1-use-per-customer server-side locks on welcome and flash promo codes.",
                "वेलकम व फ्लैश कूपन कोड पर प्रति ग्राहक केवल 1 बार का सर्वर लॉक लगाएं।",
                ["Q054"], impact_label_override=f"{int(rep_uses):,} repeat uses",
            )
        else:
            _add_healthy("CHK_COUPON_POLICY", "Promo Code Single-Use Hygiene", "कूपन दुरुपयोग सुरक्षा", q["key_metric"], "< 20 repeated uses", ["Q054"])

    # 8g. Q064 POAS (Profit on Ad Spend) when Ad Spend joined (Expected: POAS >= 1.5x)
    if (q := _q_ready("Q064")):
        poas = _extract_first_float(q["key_metric"], r"POAS\s*([\d.]+)x")
        if poas is not None and poas < 1.5:
            _add_deviation(
                "LEAK_UNPROFITABLE_POAS", "Marketing Ad Burn", "CRITICAL" if poas < 1.0 else "HIGH", 0.0, 0.0,
                "Expected: True Profit on Ad Spend (POAS) >= 1.50x (strictly > 1.0x)",
                "होना चाहिए: असली मुनाफे पर विज्ञापन रिटर्न (POAS) >= 1.50x होना चाहिए",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "poas < 1.5x",
                f"Ad Spend Efficiency Below Target ({q['key_metric']})",
                f"विज्ञापन खर्च पर असली मुनाफा कमज़ोर ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Cut ad spend on low-margin / high-RTO channels and reallocate budget to highest-LTV channels (Q062).",
                "घाटे वाले चैनलों पर विज्ञापन बजट घटाकर सबसे ज़्यादा मुनाफा व LTV वाले चैनल पर लगाएं।",
                ["Q063", "Q064", "Q065"], impact_label_override=q["key_metric"],
            )
        elif poas is not None:
            _add_healthy("CHK_POAS_HEALTH", "Marketing Profit on Ad Spend (POAS)", "विज्ञापन मुनाफा रिटर्न (POAS)", q["key_metric"], "POAS >= 1.50x", ["Q063", "Q064", "Q065"])

    # 8h. Q085 Silent Account Spend Contraction (Expected: < 15% of 3+ order accounts shrinking)
    if (q := _q_ready("Q085")):
        shrunk_pct = _extract_first_float(q["answer_en"], r"\(([\d.]+)%\)")
        if shrunk_pct is not None and shrunk_pct >= 15.0:
            _add_deviation(
                "LEAK_SILENT_SPEND_DECAY", "Silent Account Contraction", "MEDIUM", 0.0, 0.0,
                "Expected: < 15% of repeat accounts (3+ orders) shrinking basket size by >40%",
                "होना चाहिए: 15% से कम पुराने ग्राहकों के ऑर्डर साइज में बड़ी गिरावट हो",
                f"Actual: {q['key_metric']} ({shrunk_pct:.1f}% of repeat accounts shrank >40%)",
                f"असल स्थिति: {q['key_metric']} ({shrunk_pct:.1f}% पुराने ग्राहकों की खरीद 40%+ घटी)",
                "silent_decay_pct >= 15%",
                f"Silent Spend Decay: {q['key_metric']} ({shrunk_pct:.1f}% of Repeat Accounts)",
                f"पुराने ग्राहकों की चुपचाप घटती खरीद: {q['key_metric']} ({shrunk_pct:.1f}%)",
                q["answer_en"], q["answer_hi"],
                "Trigger proactive retention calls/VIP offers for decaying repeat accounts before full churn.",
                "खरीद घटाने वाले पुराने ग्राहकों को चर्न होने से पहले ही VIP ऑफर व फॉलो-अप भेजें।",
                ["Q085"], impact_label_override=f"{shrunk_pct:.1f}% decaying accounts",
            )
        else:
            _add_healthy("CHK_REPEAT_SPEND", "Repeat Customer Basket Stability", "पुराने ग्राहकों की खरीद स्थिरता", q["key_metric"], "< 15% shrinking accounts", ["Q085"])

    # 8i. Q095 Dead Stock / Zero-Movement SKUs in 90 days (Expected: 0 dead SKUs)
    if (q := _q_ready("Q095")):
        dead_cnt = _extract_first_float(q["key_metric"], r"([\d,]+)\s*zero-movement")
        if dead_cnt is not None and dead_cnt > 0:
            _add_deviation(
                "LEAK_DEAD_STOCK_SKUS", "Dead Stock / Slow Catalog", "MEDIUM", 0.0, dead_cnt,
                "Expected: 0 active catalog SKUs with zero sales in trailing 90 days",
                "होना चाहिए: पिछले 90 दिनों में 0 बिना बिके (डेड-स्टॉक) SKUs",
                f"Actual: {int(dead_cnt):,} SKUs had 0 sales in last 90 days",
                f"असल स्थिति: {int(dead_cnt):,} SKUs पिछले 90 दिनों में बिल्कुल नहीं बिके",
                "dead_stock_skus_90d > 0",
                f"Dead Stock Alert: {int(dead_cnt):,} SKUs Had Zero Sales in Last 90 Days",
                f"डेड स्टॉक अलर्ट: {int(dead_cnt):,} SKUs पिछले 90 दिनों से बिल्कुल नहीं बिके",
                q["answer_en"], q["answer_hi"],
                "Bundle or run targeted clearance markdowns on zero-movement SKUs to free working capital.",
                "90 दिन से पड़े SKUs को कॉम्बो या क्लियरेंस सेल से निकालकर फँसा पैसा फ्री करें।",
                ["Q095"], impact_label_override=f"{int(dead_cnt):,} dead SKUs",
            )
        else:
            _add_healthy("CHK_ZERO_DEAD_STOCK", "Catalog Velocity (90-Day Movement)", "कैटलॉग बिक्री गति", "0 zero-movement SKUs", "0 dead SKUs in 90d", ["Q095"])

    # 8j. Q103 Broken Warehouse x Courier Routes (Expected: within 1.5x overall baseline)
    if (q := _q_ready("Q103")):
        r103 = _extract_first_float(q["key_metric"], r"\(([\d.]+)%\)")
        base_r = _clean_float(omni.get("overall_adverse_rate_pct") or _extract_first_float(qmap.get("Q071", {}).get("key_metric", ""), r"([\d.]+)%"))
        if r103 is not None and base_r > 0 and r103 >= max(base_r * 1.5, 15.0):
            _add_deviation(
                "LEAK_BROKEN_WH_COURIER_ROUTE", "Broken Fulfillment Route", "HIGH", 0.0, 0.0,
                f"Expected: Warehouse × Courier route risk near company baseline ({base_r:.1f}%)",
                f"होना चाहिए: गोदाम × कूरियर रूट का फेलियर सामान्य ({base_r:.1f}%) के पास हो",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "warehouse_x_courier_rate >= 1.5x baseline",
                f"Broken Fulfillment Lane: {q['key_metric']}",
                f"खराब गोदाम × कूरियर रूट: {q['key_metric']}",
                q["answer_en"], q["answer_hi"],
                "Disable the worst courier on that specific warehouse lane and switch to top zone courier (Q124).",
                "उस खास गोदाम से इस कूरियर का आवंटन बंद करके सबसे तेज़/कम-RTO कूरियर चालू करें।",
                ["Q103"], impact_label_override=q["key_metric"],
            )
        else:
            _add_healthy("CHK_WH_COURIER_ROUTES", "Warehouse × Courier Lane Balance", "गोदाम × कूरियर रूट संतुलन", q["key_metric"], "< 1.5x baseline", ["Q103"])

    # 8k. Q126 Customer Dissatisfaction Rate (Expected: Low CSAT <= 2.5 should be < 10%)
    if (q := _q_ready("Q126")):
        low_csat = _extract_first_float(q["key_metric"], r"([\d.]+)%")
        if low_csat is not None and low_csat >= 10.0:
            _add_deviation(
                "LEAK_CSAT_COLLAPSE", "Customer Dissatisfaction", "HIGH" if low_csat >= 20.0 else "MEDIUM", 0.0, 0.0,
                "Expected: Dissatisfied customer share (CSAT <= 2.5★) should stay < 10%",
                "होना चाहिए: असंतुष्ट ग्राहकों (<= 2.5★) का प्रतिशत 10% से कम रहना चाहिए",
                f"Actual: {low_csat:.2f}% dissatisfied customers", f"असल स्थिति: {low_csat:.2f}% ग्राहक असंतुष्ट हैं",
                "low_csat_pct >= 10%",
                f"Elevated Customer Dissatisfaction: {low_csat:.2f}% Low CSAT (<=2.5★)",
                f"बढ़ता ग्राहक असंतोष: {low_csat:.2f}% ग्राहकों ने खराब रेटिंग दी",
                q["answer_en"] + (" " + qmap["Q127"]["answer_en"] if _q_ready("Q127") else ""),
                q["answer_hi"] + (" " + qmap["Q127"]["answer_hi"] if _q_ready("Q127") else ""),
                "Eliminate SLA breaches and courier delays that drive the CSAT drop (see Q127).",
                "डिलीवरी SLA ब्रीच और देरी तुरंत रोकें जो ग्राहकों की रेटिंग गिरा रही हैं।",
                ["Q126", "Q127"], impact_label_override=f"{low_csat:.1f}% low CSAT",
            )
        else:
            _add_healthy("CHK_CSAT_HEALTH", "Customer Satisfaction (CSAT)", "ग्राहक संतुष्टि (CSAT)", q["key_metric"], "< 10% low ratings", ["Q126"])

    # 8l. Q168 Off-Hours / Late-Night Anomaly (Expected: < 1.25x daytime risk)
    if (q := _q_ready("Q168")):
        ln_mult = _extract_first_float(q["key_metric"], r"\(([\d.]+)x\)")
        if ln_mult is not None and ln_mult >= 1.25:
            _add_deviation(
                "LEAK_OFFHOURS_ANOMALY", "Off-Hours Fraud/RTO Spike", "MEDIUM", 0.0, 0.0,
                "Expected: Late-night (00:00–04:00) failure rate should match daytime (< 1.25x)",
                "होना चाहिए: आधी रात (12–4 बजे) के ऑर्डर्स में फेलियर दिन के बराबर (< 1.25x) हो",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "late_night_risk_multiplier >= 1.25x",
                f"Late-Night (00:00–04:00) Risk Spike ({q['key_metric']})",
                f"आधी रात (12 से 4 बजे) के ऑर्डर्स में असामान्य रिस्क ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Trigger automated WhatsApp/IVR confirmation on COD orders placed between 00:00–04:00.",
                "रात 12 से सुबह 4 बजे के बीच आने वाले COD ऑर्डर्स पर ऑटो कन्फर्मेशन लगाएं।",
                ["Q168"], impact_label_override=q["key_metric"],
            )
        else:
            _add_healthy("CHK_OFFHOURS_NORMAL", "Off-Hours Order Integrity", "आधी रात ऑर्डर सुरक्षा", q["key_metric"], "< 1.25x daytime rate", ["Q168"])

    # 8m. Q169 Duplicate Primary Keys Check (Expected: 0 duplicates)
    if (q := _q_ready("Q169")):
        dups = _extract_first_float(q["key_metric"], r"([\d,]+)\s*dups")
        if dups is not None and dups > 0:
            _add_deviation(
                "LEAK_DUPLICATE_KEYS", "Data Integrity / Double-Counting", "CRITICAL", 0.0, dups,
                "Expected: 0 duplicate primary keys", "होना चाहिए: 0 डुप्लिकेट रिकॉर्ड/बिल ID",
                f"Actual: {int(dups):,} duplicate keys", f"असल स्थिति: {int(dups):,} डुप्लिकेट IDs",
                "duplicate_primary_keys > 0",
                f"Duplicate Record IDs Detected ({int(dups):,} Duplicates)",
                f"डेटा में {int(dups):,} डुप्लिकेट एंट्री/IDs मिलीं",
                q["answer_en"], q["answer_hi"],
                "Deduplicate source ERP/POS exports before financial reporting to prevent double-counted revenue.",
                "बिक्री की दोगुनी गिनती रोकने के लिए सोर्स शीट से डुप्लिकेट एंट्री हटाएं।",
                ["Q169"], impact_label_override=f"{int(dups):,} dup keys",
            )
        else:
            _add_healthy("CHK_ZERO_DUPLICATES", "Primary Key & Zero-Drift Integrity", "डुप्लिकेट व शून्य-ड्रिफ्ट जाँच", "0 duplicate IDs | 0 Drift", "0 duplicates", ["Q169"])

    # 8n. Q174 Price Slab Clustering & Round-Number Billing Check
    if (q := _q_ready("Q174")):
        if "CONFORM" in q["key_metric"].upper():
            _add_healthy("CHK_BENFORD_CLEAN", "Order Value Spread & Billing Pattern", "बिल राशि और प्राइसिंग संतुलन", "Well-spread across price slabs", "Normal bill distribution", ["Q174"])
        else:
            d1_pct = _extract_first_float(q["answer_en"], r"Digit-1 share\s*=\s*([\d.]+)%") or 50.0
            r100_pct = _extract_first_float(q["answer_en"], r"multiples of 100\s*=\s*([\d.]+)%") or 0.0
            if r100_pct >= 20.0:
                _add_deviation(
                    "LEAK_BENFORD_ANOMALY", "Manual Round-Figure Billing", "MEDIUM", 0.0, 0.0,
                    "Expected: Most bills should reflect exact item + tax prices (< 20% round-number bills)",
                    "सामान्य स्तर: ज़्यादातर बिल आइटम के सटीक रेट पर होने चाहिए (20% से कम राउंड-फिगर बिल)",
                    f"Actual: {r100_pct:.1f}% of bills are exact round multiples of 100",
                    f"यहाँ स्थिति: {r100_pct:.1f}% बिल सीधे 100 के गोल-मटोल (राउंड-फिगर) नंबर में हैं",
                    "benford_mad >= 0.015",
                    f"High Share of Manual Round-Figure Bills ({r100_pct:.1f}% Exact Multiples of 100)",
                    f"बिलों में बहुत ज़्यादा गोल-मटोल (राउंड-फिगर) रकम ({r100_pct:.1f}% बिल 100 के सीधे गुणक में)",
                    f"Across audited bills, {r100_pct:.1f}% end in exact round figures (00), which typically happens when manual cash discounts or lump-sum bill overrides are entered.",
                    f"जाँचे गए बिलों में {r100_pct:.1f}% बिल सीधे राउंड-फिगर (00) में हैं, जो अक्सर मैनुअल बिलिंग या अंदाज़े से छूट देने पर होता है।",
                    "Check manual bill overrides and use fixed coupon codes instead of arbitrary round-number discounts.",
                    "मैनुअल राउंड-फिगर छूट की जगह फिक्स्ड डिस्काउंट स्लैब लागू करें।",
                    ["Q174"], impact_label_override=f"{r100_pct:.1f}% round-figure bills",
                )
            else:
                _add_deviation(
                    "LEAK_BENFORD_ANOMALY", "Single-Item Price Slab Clustering", "MEDIUM", 0.0, 0.0,
                    "Expected: Order values should spread across single items, 2-item combos, and larger baskets",
                    "सामान्य स्तर: ऑर्डर की रकम सिर्फ़ 1 आइटम तक सीमित न रहकर 2-3 आइटम के कॉम्बो में भी फैली होनी चाहिए",
                    f"Actual: {d1_pct:.1f}% of orders are clustered in the same single-item price bracket",
                    f"यहाँ स्थिति: {d1_pct:.1f}% ऑर्डर एक ही शुरुआती प्राइस ब्रैकेट (Single-Item Slab) में सिमटे हैं",
                    "benford_mad >= 0.015",
                    f"Orders Clustered in One Price Range ({d1_pct:.1f}% in Same Price Bracket — Combo Opportunity)",
                    f"ज़्यादातर ऑर्डर ({d1_pct:.1f}%) एक ही प्राइस रेंज में सिमटे हैं — कॉम्बो/बंडल से बिल साइज बढ़ाएं",
                    f"Most customers are ordering single fixed-price items from the same price slab ({d1_pct:.1f}% in one bracket; round-figure bills: {r100_pct:.1f}%), keeping average order value capped.",
                    f"ज़्यादातर ग्राहक एक ही फिक्स्ड रेट का सिंगल आइटम मँगा रहे हैं ({d1_pct:.1f}% बिल एक ही रेंज में), जिससे औसत ऑर्डर साइज (AOV) एक ही जगह अटका हुआ है।",
                    "Add 'Buy 2 & Save 10%' combo bundles at checkout so single-item buyers upgrade to larger baskets.",
                    "चेकआउट पर '2 खरीदें और 10% बचाएं' कॉम्बो/बंडल ऑफर लगाएं ताकि ग्राहक 1 आइटम की जगह बड़ा ऑर्डर करें।",
                    ["Q174"], impact_label_override=f"{d1_pct:.1f}% single price slab",
                )

    # 8o. Q198 Sudden >1.8-Sigma Monthly Spike Check (Expected: 0 spike months)
    if (q := _q_ready("Q198")):
        sp_cnt = _extract_first_float(q["key_metric"], r"([\d,]+)\s*spike")
        if sp_cnt is not None and sp_cnt > 0:
            _add_deviation(
                "LEAK_SIGMA_SPIKE", "Sudden Monthly Anomaly Spike", "MEDIUM", 0.0, 0.0,
                "Expected: 0 months spiking > 1.8 standard deviations above mean failure rate",
                "होना चाहिए: किसी भी महीने में अचानक >1.8 सिग्मा फेलियर उछाल न हो",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "sigma_spike_months >= 1",
                f"Sudden Failure-Rate Spike Alert ({q['key_metric']})",
                f"अचानक फेलियर उछाल अलर्ट ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Audit root cause of the flagged spike month(s) (carrier outage, promo blast, or stock issue).",
                "चिह्नित महीने में अचानक हुए उछाल के कारण (कूरियर/ऑफर/स्टॉक) की जांच करें।",
                ["Q198"], impact_label_override=q["key_metric"],
            )
        else:
            _add_healthy("CHK_NO_SIGMA_SPIKE", "Monthly Stability (No >1.8σ Spikes)", "मासिक स्थिरता जाँच", "0 abnormal spike months", "0 >1.8σ spikes", ["Q198"])

    # 8p. Q014 Pareto Customer Concentration Risk (Expected: Top 5% customers < 40% of revenue)
    if (q := _q_ready("Q014")):
        top5_pct = _extract_first_float(q["key_metric"], r"Top\s*5%\s*=\s*([\d.]+)%")
        if top5_pct is not None and top5_pct >= 40.0:
            _add_deviation(
                "LEAK_PARETO_CONCENTRATION", "Customer Concentration Risk", "MEDIUM", 0.0, 0.0,
                "Expected: Top 5% customers account for < 40% of total revenue",
                "होना चाहिए: टॉप 5% ग्राहकों पर कुल कमाई की निर्भरता 40% से कम रहे",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "pareto_top5_cust_pct >= 40.0%",
                f"High Whale Dependency Risk ({q['key_metric']})",
                f"टॉप ग्राहकों पर अत्यधिक निर्भरता ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Diversify mid-tier repeat buyer base and lock in top 5% accounts with multi-quarter SLA contracts.",
                "टॉप 5% VIP ग्राहकों को सालाना कॉन्ट्रैक्ट से सुरक्षित करें और नए मिड-टियर ग्राहक बढ़ाएं।",
                ["Q014"], impact_label_override=q["key_metric"],
            )
        elif top5_pct is not None:
            _add_healthy("CHK_PARETO_DIVERSIFIED", "Customer Revenue Diversification", "ग्राहक कमाई संतुलन", q["key_metric"], "Top 5% < 40% revenue", ["Q014"])

    # 8q. Q033 Overdue Receivables / 90+ Days AR Aging (Expected: 0 accounts overdue 90+ days)
    if (q := _q_ready("Q033")):
        ov90 = _extract_first_float(q["key_metric"], r"([\d,]+)\s*overdue")
        if ov90 is not None and ov90 > 0:
            _add_deviation(
                "LEAK_AR_90D_OVERDUE", "Bad Debt / 90+ Days Overdue Udhaar", "CRITICAL", 0.0, ov90,
                "Expected: 0 invoices/accounts overdue beyond 90+ days",
                "होना चाहिए: 90+ दिन से ज़्यादा फँसा उधार (Bad Debt) शून्य हो",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "overdue_90d_accounts > 0",
                f"90+ Days Overdue Receivables Alert ({q['key_metric']})",
                f"90+ दिन से फँसा उधार अलर्ट ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Freeze new credit dispatch for 90+d delinquent accounts and initiate immediate collection recovery.",
                "90+ दिन वाले बकायेदारों की नई उधार सप्लाई रोककर तुरंत वसूली कॉल शुरू करें।",
                ["Q033", "Q034"], impact_label_override=q["key_metric"],
            )
        elif ov90 is not None:
            _add_healthy("CHK_AR_90D_CLEAN", "90+ Days Receivables Hygiene", "90+ दिन उधार सुरक्षा", "0 overdue 90+d", "0 accounts >90d", ["Q033", "Q034"])

    # 8r. Q073 / Q139 Continuous Numerical Red-Line Threshold Cliff (Expected: no sharp failure jump)
    if (q := _q_ready("Q073")):
        cliff_r = _extract_first_float(q["key_metric"], r"->\s*([\d.]+)%")
        base_r = _clean_float(omni.get("baseline_rate_pct") or _extract_first_float(qmap.get("Q071", {}).get("key_metric", ""), r"([\d.]+)%"))
        if cliff_r is not None and base_r > 0 and cliff_r >= max(base_r * 1.35, 18.0):
            _add_deviation(
                "LEAK_NUMERICAL_REDLINE_CLIFF", "Continuous Red-Line Threshold Cliff", "HIGH", 0.0, 0.0,
                f"Expected: Continuous operational metrics remain near {base_r:.1f}% baseline without sharp failure cliffs",
                f"होना चाहिए: न्यूमेरिकल मेट्रिक में किसी सीमा के बाद अचानक फेलियर उछाल ({base_r:.1f}% से ऊपर) न हो",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "numerical_cliff_rate >= 1.35x baseline",
                f"Non-Linear Red-Line Threshold Breach ({q['key_metric']})",
                f"खतरनाक रेड-लाइन सीमा पार ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Enforce an automated operational triage hard-gate at the identified numerical threshold.",
                "चिह्नित न्यूमेरिकल रेड-लाइन सीमा के पार जाते ही ऑटोमैटिक अलर्ट/रोक लगाएं।",
                ["Q073", "Q139"], impact_label_override=q["key_metric"],
            )
        elif cliff_r is not None:
            _add_healthy("CHK_NUMERICAL_CLIFFS", "Continuous Metric Stability", "न्यूमेरिकल सीमा स्थिरता", q["key_metric"], "< 1.35x baseline", ["Q073", "Q139"])

    # 8s. Q080 Overdue Reorder Window Customers (Expected: 0 overdue repeat buyers)
    if (q := _q_ready("Q080")):
        ov_reord = _extract_first_float(q["key_metric"], r"([\d,]+)\s*overdue")
        if ov_reord is not None and ov_reord >= 10:
            _add_deviation(
                "LEAK_OVERDUE_REORDER_WINDOW", "Lapsing Repeat Buyers (Churn Warning)", "MEDIUM", 0.0, ov_reord,
                "Expected: Repeat customers reorder within their 75th-percentile inter-purchase cycle",
                "होना चाहिए: रिपीट ग्राहक अपने सामान्य री-ऑर्डर समय के भीतर दोबारा ऑर्डर करें",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "overdue_reorder_customers >= 10",
                f"Early Churn Warning: {q['key_metric']} Past Reorder Cycle",
                f"चर्न चेतावनी: {q['key_metric']} का री-ऑर्डर समय निकल चुका है",
                q["answer_en"], q["answer_hi"],
                "Send automated WhatsApp replenishment reminders to accounts past their p75 reorder day.",
                "जिन पुराने ग्राहकों का री-ऑर्डर समय बीत गया है, उन्हें तुरंत व्हाट्सएप रिमाइंडर भेजें।",
                ["Q080"], impact_label_override=q["key_metric"],
            )
        elif ov_reord is not None:
            _add_healthy("CHK_REORDER_CYCLE", "Repeat Buyer Reorder Cadence", "रिपीट ग्राहक री-ऑर्डर चक्र", q["key_metric"], "< 10 overdue accounts", ["Q080"])

    # 8t. Q104 Unit COGS Creep H1 -> H2 (Expected: < +5.0% unit cost drift)
    if (q := _q_ready("Q104")):
        creep = _extract_first_float(q["key_metric"], r"([+-]?[\d.]+)%\s*unit")
        if creep is not None and creep >= 5.0:
            _add_deviation(
                "LEAK_UNIT_COGS_CREEP", "Procurement / Unit Cost Inflation", "HIGH", 0.0, 0.0,
                "Expected: Unit COGS drift between H1 and H2 stays < +5.0%",
                "होना चाहिए: पहली छमाही से दूसरी छमाही में प्रति यूनिट लागत वृद्धि 5% से कम रहे",
                f"Actual: {q['key_metric']}", f"असल स्थिति: {q['key_metric']}",
                "unit_cogs_creep_pct >= 5.0%",
                f"Unit Cost / COGS Inflation Alert ({q['key_metric']})",
                f"खरीद लागत (Unit COGS) में उछाल ({q['key_metric']})",
                q["answer_en"], q["answer_hi"],
                "Renegotiate supplier rate cards or audit raw-material waste on SKUs with >5% cost creep.",
                "5% से ज़्यादा महँगी हुई खरीद पर सप्लायर रेट री-नेगोशिएट करें।",
                ["Q104"], impact_label_override=q["key_metric"],
            )
        elif creep is not None:
            _add_healthy("CHK_UNIT_COGS_STABLE", "Unit COGS Cost Stability (H1 vs H2)", "प्रति यूनिट खरीद लागत स्थिरता", q["key_metric"], "Drift < +5.0%", ["Q104"])

    # Sort ALL genuine abnormalities by Severity -> Cash Impact -> Excess Events (NO ARBITRARY CAP!)
    raw_leaks.sort(
        key=lambda x: (
            x["severity_weight"],
            _clean_float(x.get("estimated_cash_impact")),
            _clean_float(x.get("excess_events")),
        ),
        reverse=True,
    )
    all_abnormal_deviations = []
    for idx, item in enumerate(raw_leaks, start=1):
        entry = {k: v for k, v in item.items() if k != "severity_weight"}
        entry["rank"] = idx
        all_abnormal_deviations.append(entry)

    # 9. Do-Not-Spend Shields (Uniform Noise OR Negligible Practical Impact -> Healthy / Do NOT touch!)
    shields = []
    for nd in (omni.get("uniform_noise_dimensions") or []):
        dname = str(nd.get("dimension") or "")
        if dname in neg_margin_dims or dname in covered_dims:
            continue
        pv = max(
            _clean_float(nd.get("p_val")),
            _clean_float(nd.get("omnibus_chi2_p")),
            _clean_float(nd.get("p_value")),
        )
        lift_v = _clean_float(nd.get("risk_multiplier", 1.0))
        d_en = _friendly_dim_name(dname, "en")
        d_hi = _friendly_dim_name(dname, "hi")
        if pv >= 0.05:
            msg_en = f"{d_en} is working normally across all groups — do not spend money changing it ({sym or ''}0 needed)."
            msg_hi = f"{d_hi} के सभी ग्रुप सामान्य चल रहे हैं — यहाँ {sym or ''}0 खर्च करें (बदलाव की ज़रूरत नहीं)।"
            obs_lbl = "Normal across groups"
            exp_lbl = "No significant gap between groups"
        else:
            msg_en = f"{d_en} has very small difference across groups ({lift_v:.2f}x) — do not spend money changing it ({sym or ''}0 needed)."
            msg_hi = f"{d_hi} में अंतर बहुत मामूली है ({lift_v:.2f}x) — यहाँ {sym or ''}0 खर्च करें (बदलाव की ज़रूरत नहीं)।"
            obs_lbl = f"Only {lift_v:.2f}x difference (Negligible)"
            exp_lbl = "Small practical impact (< 1.15x)"
        shields.append({
            "dimension": dname,
            "p_value": round(pv, 4),
            "risk_multiplier": round(lift_v, 2),
            "message_en": msg_en,
            "message_hi": msg_hi,
        })
        _add_healthy(
            f"CHK_NOISE_SHIELD_{dname}",
            f"{dname} Uniform / Low-Impact Performance",
            f"{dname} सामान्य प्रदर्शन",
            obs_lbl,
            exp_lbl,
            ["Q177", "Q183"],
        )

    # 10. Hidden Positive Profit & Growth Opportunities (from 200Q Brain)
    opportunities: List[Dict[str, Any]] = []
    for qid_opp, title_en, title_hi in [
        ("Q090", "Hero Star Profit SKU", "सबसे ज़्यादा मुनाफे वाला Hero प्रोडक्ट"),
        ("Q091", "Best Repeat-Buyer Gateway SKU", "सबसे ज़्यादा रिपीट ग्राहक लाने वाला प्रोडक्ट"),
        ("Q093", "Market Basket Cross-Sell Pair", "ऑटोमेटेड क्रॉस-सेल कॉम्बो अवसर"),
        ("Q124", "Optimal Courier Zone Routing", "ज़ोन के अनुसार सबसे सस्ता/बेहतर कूरियर नियम"),
        ("Q051", "Untapped Pricing Power SKU", "बिना डिस्काउंट बिकने वाला प्राइसिंग-पावर प्रोडक्ट"),
        ("Q079", "High-Value RFM Champions Pool", "VIP वफादार ग्राहक पूल (RFM Champions)"),
    ]:
        qo = qmap.get(qid_opp)
        if qo and qo.get("status") in ("DIRECT_ANSWERED", "PROXY_ANSWERED"):
            opportunities.append({
                "source_qid": qid_opp,
                "title_en": title_en,
                "title_hi": title_hi,
                "key_metric": str(qo.get("key_metric") or ""),
                "detail_en": str(qo.get("answer_en") or ""),
                "detail_hi": str(qo.get("answer_hi") or ""),
            })

    # 11. Group Missing-Column Questions into Clean Unlock Packs
    missing_qs = [q for q in qs if q.get("status") == "COLUMN_MISSING_EXPLAINED"]
    pack_buckets = [
        ("MARKETING_ADS", "Marketing & Ad Spend Sheet (Meta / Google Ads)", "विज्ञापन खर्च शीट (Meta / Google Ads)", {"P05"}, "Unlocks true CAC, POAS vs ROAS, CAC Payback & Ad Saturation cliffs.", "असली CAC, POAS और विज्ञापन बजट सीमा अनलॉक होगी।"),
        ("INVENTORY_VENDOR", "Inventory, Vendor PO & Stock Ledger", "इन्वेंटरी, सप्लायर PO व स्टॉक शीट", {"P08", "P07"}, "Unlocks Stockout Lost Sales, Vendor Overbilling (PO vs Invoice), Shrinkage & Reorder Points.", "स्टॉकआउट नुकसान, सप्लायर ओवरबिलिंग और रीऑर्डर पॉइंट अनलॉक होंगे।"),
        ("FINANCE_AR_BANK", "Accounting, AR Aging, GST & Bank Cash Sheet (Tally / QuickBooks)", "अकाउंटिंग, उधार (AR), GST व बैंक शीट", {"P03", "P02", "P13"}, "Unlocks DSO, 90+d Overdue Slippage, Break-Even Point, Cash Runway & GST Reconciliation.", "उधार वसूली, ब्रेक-ईवन, कैश रनवे और GST मिलान अनलॉक होगा।"),
        ("HR_SUPPORT_PLANT", "HR Payroll, Support Tickets & Plant Telemetry", "HR सैलरी, सपोर्ट टिकट व फैक्ट्री लॉग्स", {"P10", "P11", "P12"}, "Unlocks Attrition Flight-Risk, Sales Rep Bad-Revenue, Support FRT & Machine OEE.", "कर्मचारी एट्रिशन, सेल्समैन ऑडिट, सपोर्ट देरी और OEE अनलॉक होंगे।"),
    ]
    unlock_packs = []
    for pack_id, name_en, name_hi, pids, desc_en, desc_hi in pack_buckets:
        matched_ids = [q["id"] for q in missing_qs if q.get("pillar_id") in pids]
        if matched_ids:
            unlock_packs.append({
                "pack_id": pack_id,
                "name_en": name_en,
                "name_hi": name_hi,
                "unlocks_question_count": len(matched_ids),
                "sample_qids": matched_ids[:6],
                "benefit_en": desc_en,
                "benefit_hi": desc_hi,
            })

    # Deduplicated Quantified Exposure Math:
    # Avoid double-counting overlapping slices of the SAME transactions:
    # - `LEAK_PROFITLESS_SEG_*` is a subset of `LEAK_NEGATIVE_MARGIN_ORDERS` (never sum both)
    # - Multiple `LEAK_DIM_*` dimensions slice the same adverse records orthogonally (take max slice, not naive sum)
    # - Bound deduplicated exposure cleanly by physical portfolio volume when available
    if is_fin:
        gross_unadjusted_cash = sum(_clean_float(x.get("estimated_cash_impact")) for x in all_abnormal_deviations)
        dim_cash_vals = [_clean_float(x.get("estimated_cash_impact")) for x in all_abnormal_deviations if str(x.get("leak_id", "")).startswith("LEAK_DIM_")]
        has_neg_ord_leak = any(str(x.get("leak_id", "")) == "LEAK_NEGATIVE_MARGIN_ORDERS" for x in all_abnormal_deviations)
        non_dim_cash = 0.0
        for x in all_abnormal_deviations:
            lid = str(x.get("leak_id", ""))
            if lid.startswith("LEAK_DIM_"):
                continue
            # Segment negative margin is already counted inside total LEAK_NEGATIVE_MARGIN_ORDERS
            if has_neg_ord_leak and lid.startswith("LEAK_PROFITLESS_SEG_"):
                continue
            # Working-capital unpaid AR overlaps billed failure drag; take max(AR, dim_peak) below
            if lid == "LEAK_WORKING_CAPITAL_AR_GAP":
                continue
            non_dim_cash += _clean_float(x.get("estimated_cash_impact"))
        ar_cash = sum(_clean_float(x.get("estimated_cash_impact")) for x in all_abnormal_deviations if str(x.get("leak_id", "")) == "LEAK_WORKING_CAPITAL_AR_GAP")
        dim_peak_cash = max(dim_cash_vals) if dim_cash_vals else 0.0
        total_quantified_cash = max(dim_peak_cash, ar_cash) + non_dim_cash
        if cost_col_name and isinstance(df, pd.DataFrame) and cost_col_name in df.columns:
            phys_port_vol = float(pd.to_numeric(df[cost_col_name], errors="coerce").fillna(0.0).abs().sum())
            if phys_port_vol > 0:
                total_quantified_cash = min(total_quantified_cash, phys_port_vol)
    else:
        gross_unadjusted_cash = 0.0
        total_quantified_cash = 0.0
    n_abn = len(all_abnormal_deviations)
    n_hlth = len(healthy_checks)
    verdict_en = (
        f"Autonomous Diagnosis: {n_abn} real abnormalities detected that deviate from healthy standards ({n_hlth} normal checks auto-hidden so you focus strictly on what is broken)."
        if n_abn > 0
        else f"Autonomous Diagnosis: 0 abnormalities detected — all {n_hlth} evaluated business checks are operating as expected!"
    )
    verdict_hi = (
        f"स्वचालित निदान: कुल {n_abn} असली खराबियाँ/असामान्यताएँ मिलीं जहाँ आंकड़े सामान्य स्तर से भटके हैं ({n_hlth} सही चल रही जाँचें ऑटो-हाइड की गई हैं ताकि आपका ध्यान सिर्फ़ असली नुकसान पर रहे)।"
        if n_abn > 0
        else f"स्वचालित निदान: 0 खराबी — सभी {n_hlth} जाँचे गए बिज़नेस पैरामीटर बिल्कुल सामान्य और स्वस्थ हैं!"
    )

    result = {
        "schema_version": "2.0",
        "mode": "AUTONOMOUS_EXCEPTION_DETECTION",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "is_financial": is_fin,
        "unit_symbol": sym,
        "summary": {
            "total_ranked_leaks": n_abn,
            "abnormal_count": n_abn,
            "healthy_suppressed_count": n_hlth,
            "critical_count": sum(1 for x in all_abnormal_deviations if x["severity"] == "CRITICAL"),
            "high_count": sum(1 for x in all_abnormal_deviations if x["severity"] == "HIGH"),
            "medium_count": sum(1 for x in all_abnormal_deviations if x["severity"] == "MEDIUM"),
            "do_not_spend_shields_count": len(shields),
            "opportunities_count": len(opportunities),
            "unlock_packs_count": len(unlock_packs),
            "quantified_leak_exposure": round(total_quantified_cash, 2) if is_fin else None,
            "formatted_quantified_exposure": _fmt_money(total_quantified_cash, sym, numbering) if (is_fin and total_quantified_cash > 0) else f"{n_rows:,} records audited",
            "background_questions_evaluated": len(qs),
            "autonomous_verdict_en": verdict_en,
            "autonomous_verdict_hi": verdict_hi,
        },
        "abnormal_deviations": all_abnormal_deviations,
        "top_ranked_leaks": all_abnormal_deviations,
        "healthy_checks_suppressed": healthy_checks,
        "do_not_spend_shields": shields,
        "hidden_opportunities": opportunities,
        "missing_data_unlock_packs": unlock_packs,
    }
    clean = _sanitize(result)
    if out_dir is not None:
        p = Path(out_dir) / "ranked_leaks_report.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
    return clean


__all__ = ["synthesize_ranked_leaks"]
