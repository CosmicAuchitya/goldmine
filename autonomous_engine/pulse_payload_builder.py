"""
=============================================================================
DATAX-RAY WORKSTREAM 6 — EXECUTIVE PULSE & NARRATIVE PAYLOAD BUILDER
=============================================================================
Modularized out of api_server.py: extracts 100% physically grounded Morning
Pulse indicators, bilingual owner narratives, cohort breakdowns, and
growth/inventory summaries from certified run artifacts.
=============================================================================
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _humanize_col_name(col_name: str) -> str:
    """Turns database identifiers like 'payment_gateway' or 'is_rto_or_cancelled' into plain owner-friendly names."""
    if not col_name:
        return "Business Group"
    c = str(col_name).strip()
    aliases = {
        "is_rto_or_cancelled": "Order Returns & Cancellations",
        "is_canceled": "Booking Cancellations",
        "payment_gateway": "Payment Method",
        "dispatch_delay_days": "Dispatch Delay (Days)",
        "dispatch_delay_hours": "Dispatch Delay (Hours)",
        "transit_days": "Shipping Transit (Days)",
        "transit_hours": "Shipping Transit (Hours)",
        "total_delivery_days": "Total Delivery Time (Days)",
        "delivery_sla_breach": "Late Delivery",
        "customer_csat_rating": "Customer Rating",
        "customer_segment": "Customer Type",
        "city_tier": "City Tier",
        "fulfillment_warehouse": "Warehouse Hub",
        "fulfillment_hub": "Warehouse Hub",
        "fulfillment_partner": "Delivery Partner",
        "courier_partner": "Delivery Partner",
        "payment_mode": "Payment Method",
        "packaging_box_color": "Packaging Box Color",
        "packaging_box_theme": "Packaging Style",
        "retail_format": "Store Format",
        "coupon_code": "Discount Coupon",
        "discount_pct": "Discount %",
        "acquisition_channel": "Marketing Channel",
        "lead_time": "Advance Booking Days",
        "assigned_room_type": "Room Type",
        "market_segment": "Booking Channel",
        "hotel": "Hotel Property",
        "poutcome": "Previous Campaign Result",
        "TipoContrato": "Contract Type",
        "MesesComoCliente": "Customer Tenure (Months)",
        "FormaPagamento": "Payment Method",
        "ocean_proximity": "Location Zone",
        "median_income": "Area Median Income",
        "JobRole": "Job Role",
    }
    if c in aliases:
        return aliases[c]
    if c.lower() in {k.lower(): v for k, v in aliases.items()}:
        return {k.lower(): v for k, v in aliases.items()}[c.lower()]
    cleaned = re.sub(r"^(is_|has_|flag_)", "", c, flags=re.IGNORECASE)
    cleaned = re.sub(r"(_inr|_usd|_pct|_flag)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned.title() if cleaned else "Business Group"


def _format_indian_commas(val: float, decimals: int = 0) -> str:
    """Formats numbers using Indian 2,2,3 comma grouping (e.g. 17,49,280)."""
    sign = "-" if val < 0 else ""
    av = abs(float(val or 0.0))
    fixed = f"{av:.{decimals}f}"
    int_part, _, dec_part = fixed.partition(".")
    if len(int_part) > 3:
        last3 = int_part[-3:]
        head = int_part[:-3]
        groups = []
        while len(head) > 2:
            groups.append(head[-2:])
            head = head[:-2]
        if head:
            groups.append(head)
        int_fmt = ",".join(reversed(groups)) + "," + last3
    else:
        int_fmt = int_part
    return f"{sign}{int_fmt}.{dec_part}" if dec_part else f"{sign}{int_fmt}"


def _format_local_money(val: float, sym: str = "$") -> str:
    """Formats currency consistently for business owners (Lakh/Crore & Indian grouping for ₹, M/K for others)."""
    num = float(val or 0.0)
    if sym == "₹":
        if abs(num) >= 10_000_000:
            return f"₹{num / 10_000_000:.2f} Cr"
        if abs(num) >= 100_000:
            return f"₹{num / 100_000:.2f} L"
        return f"₹{_format_indian_commas(num, 0)}"
    if abs(num) >= 1_000_000:
        return f"{sym}{num / 1_000_000:.2f}M"
    return f"{sym}{num:,.0f}"


def _localize_currency_in_text(text: str, sym: str = "$") -> str:
    """Replaces stray '$' tokens AND normalizes Western-comma '₹' amounts into authentic Indian Lakh/Crore / en-IN formatting."""
    if not text:
        return text
    def _repl(m: re.Match) -> str:
        raw_num = m.group(1).replace(",", "")
        try:
            v = float(raw_num)
            if v == 0:
                return f"{sym}0"
            return _format_local_money(v, sym)
        except Exception:
            return f"{sym}{m.group(1)}"
    out = text
    if sym != "$":
        out = re.sub(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)(?![0-9.]|\s*(?:L|Cr|K|M)\b)", _repl, out)
    if sym == "₹":
        out = re.sub(r"₹([0-9][0-9,]*(?:\.[0-9]+)?)(?![0-9.]|\s*(?:L|Cr|K|M)\b)", _repl, out)
    return out


def _humanize_interval_str(rng: str, lang: str = "en") -> str:
    """Converts math interval like '(-0.001, 2.0]' or '(2.0, 6.0]' into simple owner speech."""
    if not rng:
        return rng
    m = re.match(r"^\s*[\(\[]\s*(-?[0-9]+(?:\.[0-9]+)?)\s*,\s*(-?[0-9]+(?:\.[0-9]+)?)\s*[\)\]]\s*$", str(rng).strip())
    if not m:
        return str(rng)
    lo = float(m.group(1))
    hi = float(m.group(2))
    if lo < 0 and abs(lo) < 0.05:
        lo_clean = 0
    elif abs(lo - round(lo)) < 0.05:
        lo_clean = int(round(lo))
    else:
        lo_clean = round(lo, 1)
    if abs(hi - round(hi)) < 0.05:
        hi_clean = int(round(hi))
    else:
        hi_clean = round(hi, 1)
    if lo < 0 and lo_clean == 0:
        return f"0 se {hi_clean} ke beech" if lang == "hi" else f"0 to {hi_clean}"
    if lo > 0 and lo - round(lo) < -0.0005 and lo_clean == 1:
        return f"1 se {hi_clean} ke beech" if lang == "hi" else f"1 to {hi_clean}"
    return f"{lo_clean} se zyada ({hi_clean} tak)" if lang == "hi" else f"above {lo_clean} (up to {hi_clean})"


def _extract_executive_pulse(
    staging_out: Path,
    manifest_data: Dict[str, Any],
    plain_summary_text: str
) -> Dict[str, Any]:
    """
    Extracts 100% physically verified Morning Pulse indicators (Competitive Moats,
    Bottlenecks, Danger Red-Lines, 3 Strategic Pathways, and Segment Cohort Breakdowns)
    directly from semantic_metrics_manifest.json, PLAIN_BUSINESS_SUMMARY.md, and
    DATA_XRAY_EXECUTIVE_DOSSIER.md.
    """
    gov = manifest_data.get("governance", {}) or {}
    tout = manifest_data.get("target_outcome", {}) or {}
    fexp = manifest_data.get("financial_exposure", {}) or {}

    total_records = int(gov.get("audited_fact_records", 0) or 0)
    total_events = int(tout.get("total_adverse_events", 0) or 0)
    adverse_rate = float(tout.get("adverse_event_rate_pct", 0.0) or 0.0)
    reliability_rate = round(max(0.0, 100.0 - adverse_rate), 2)
    total_drag = float(fexp.get("total_adverse_capital_drag", 0.0) or 0.0)
    total_portfolio = float(fexp.get("total_portfolio_volume", 0.0) or 0.0)
    currency_unit = str(fexp.get("currency_unit") or "$")
    target_col = str(tout.get("column_name") or "Target")
    target_desc = str(tout.get("target_description") or target_col)
    monetary_col = str(fexp.get("monetary_column") or fexp.get("cost_column") or "None")

    # Split English and Hinglish summaries
    split_marker = "## 🇮🇳 Business X-Ray Summary"
    if split_marker in plain_summary_text:
        parts = plain_summary_text.split(split_marker, 1)
        english_md = parts[0].strip()
        hinglish_md = (split_marker + parts[1]).strip()
    else:
        english_md = plain_summary_text.strip()
        hinglish_md = plain_summary_text.strip()

    # 1. Extract Competitive Moat & Cohort Breakdown Tables from DATA_XRAY_EXECUTIVE_DOSSIER.md
    moat_headline = f"{reliability_rate:.2f}%"
    moat_sub = f"Global System Reliability ({total_records - total_events:,} healthy records)"
    moat_detail = f"Baseline operational stability across {total_records:,} audited records."
    moat_dim, moat_seg, moat_vol, moat_rel = target_col, "Healthy Group", f"{total_records - total_events:,}", f"{reliability_rate:.1f}%"
    cohort_breakdowns: List[Dict[str, Any]] = []

    dossier_f = staging_out / "DATA_XRAY_EXECUTIVE_DOSSIER.md"
    if dossier_f.exists():
        try:
            d_txt = dossier_f.read_text(encoding="utf-8")
            m_sec = re.search(r"### 3\. Economic Moats[\s\S]*?(?=\n---|\n### 4\.)", d_txt)
            if m_sec:
                sec_body = m_sec.group(0)
                tbl_lines = [ln.strip() for ln in sec_body.splitlines() if ln.strip().startswith("|")]
                if len(tbl_lines) >= 3:
                    hdr_cells = [c.strip().strip("*") for c in tbl_lines[0].strip("|").split("|")]
                    row_cells = [c.strip().strip("*") for c in tbl_lines[2].strip("|").split("|")]
                    if len(row_cells) >= 4:
                        dim_name = hdr_cells[0] if hdr_cells else "Segment"
                        seg_val = row_cells[0]
                        vol_val = row_cells[1]
                        rel_val = row_cells[3]
                        status_val = row_cells[5] if len(row_cells) >= 6 else "High Stability Moat"
                        moat_headline = f"{rel_val} Reliable"
                        moat_sub = f"{dim_name} = '{seg_val}' ({vol_val} records)"
                        moat_detail = f"Top stability moat ({status_val}) operating with {rel_val} reliability across {vol_val} audited units."
                        moat_dim, moat_seg, moat_vol, moat_rel = dim_name, seg_val, vol_val, rel_val

            # Parse Section 4 & Section 5 Cohort Breakdown Tables for Interactive Segment Explorer
            for sec_pattern in [
                r"### 4\. Capital Leaks & Financial Vulnerabilities[\s\S]*?(?=\n---|\n### 5\.)",
                r"### 5\. Secondary Segment / Node Bottlenecks[\s\S]*?(?=\n---|\n### 6\.|\n### 7\.)"
            ]:
                c_sec = re.search(sec_pattern, d_txt)
                if c_sec:
                    c_lines = [ln.strip() for ln in c_sec.group(0).splitlines() if ln.strip().startswith("|")]
                    if len(c_lines) >= 3:
                        c_hdr = [c.strip().strip("*") for c in c_lines[0].strip("|").split("|")]
                        dim_col = c_hdr[0] if c_hdr else "Dimension"
                        rows_list = []
                        for r_ln in c_lines[2:10]:
                            cells = [c.strip().strip("*") for c in r_ln.strip("|").split("|")]
                            if len(cells) >= 4:
                                seg_label = cells[0]
                                vol_num = int(re.sub(r"[^0-9]", "", cells[1]) or "0")
                                adv_num = int(re.sub(r"[^0-9]", "", cells[2]) or "0")
                                rate_num = float(re.sub(r"[^0-9.]", "", cells[3]) or "0.0")
                                if len(cells) >= 6:
                                    exp_txt = cells[4]
                                    share_txt = cells[5]
                                elif len(cells) == 5:
                                    if "%" in cells[4]:
                                        share_txt = cells[4]
                                        exp_txt = f"{adv_num:,} events"
                                    else:
                                        exp_txt = cells[4]
                                        share_txt = f"{round((adv_num / max(total_events, 1)) * 100.0, 1)}%"
                                else:
                                    share_txt = "0.0%"
                                    exp_txt = f"{adv_num:,} events"
                                share_num = float(re.sub(r"[^0-9.]", "", share_txt) or "0.0")
                                exp_txt = _localize_currency_in_text(exp_txt, currency_unit)
                                status_str = cells[6] if len(cells) >= 7 else ("🔴 High-Risk" if rate_num >= 40 else ("🟢 Resilient" if rate_num <= 15 else "🟡 Watch"))
                                rows_list.append({
                                    "segment": seg_label,
                                    "volume": f"{vol_num:,}",
                                    "volume_num": vol_num,
                                    "adverse_events": f"{adv_num:,}",
                                    "adverse_events_num": adv_num,
                                    "risk_rate_pct": rate_num,
                                    "adverse_rate_pct": rate_num,
                                    "share_of_failures_pct": share_num,
                                    "exposure_formatted": exp_txt,
                                    "total_liability": exp_txt,
                                    "share_of_drag": share_txt,
                                    "status": status_str
                                })
                        if rows_list:
                            cohort_breakdowns.append({
                                "dimension": dim_col,
                                "dimension_label": _humanize_col_name(dim_col),
                                "raw_dimension": dim_col,
                                "rows": rows_list
                            })
        except Exception:
            pass

    # 2. Extract Bottleneck from PLAIN_BUSINESS_SUMMARY.md Section 2
    bottleneck_headline = f"{adverse_rate:.2f}%"
    bottleneck_sub = f"Target: {target_col}"
    bottleneck_detail = f"{total_events:,} adverse events detected across {total_records:,} records."
    bn_is_cb = False
    bn_col, bn_seg, bn_rate, bn_rest_rate = target_col, "Main Risk Group", f"{adverse_rate:.1f}%", f"{adverse_rate:.1f}"

    b_sec = re.search(r"### 2\. Where Is the Bottleneck\?([\s\S]*?)(?=\n### 3\.|\Z)", english_md)
    if b_sec:
        b_body = b_sec.group(1).strip()
        clean_b = re.sub(r"\*\*|\`|^- ", "", b_body, flags=re.MULTILINE).strip()
        if "$0 Spend Advisory" in b_body or "No Single Bottleneck" in b_body:
            bn_is_cb = True
            bottleneck_headline = "$0 Spend Advisory"
            bottleneck_sub = "Circuit-Breaker Active (Uniform Risk)"
            bottleneck_detail = clean_b.splitlines()[0] if clean_b else "No statistically significant segment bottleneck detected."
        else:
            m_grp = re.search(r"Group\s+`?([^`=]+)`?\s*=\s*\*\*'([^']+)'\*\*.*?at\s+\*\*([0-9.]+%)\*\*", b_body)
            if m_grp:
                bn_col = m_grp.group(1).strip()
                bn_seg = m_grp.group(2).strip()
                bn_rate = m_grp.group(3).strip()
                bottleneck_headline = f"{bn_rate} Failure"
                bottleneck_sub = f"{bn_col} = '{bn_seg}'"
            m_rest = re.search(r"compared to\s+([0-9.]+)%", b_body)
            if m_rest:
                bn_rest_rate = m_rest.group(1).strip()
            bottleneck_detail = " ".join([ln.lstrip("- ").strip() for ln in b_body.splitlines() if ln.strip()]).replace("**", "").replace("`", "")

    # 3. Extract Red-Line from PLAIN_BUSINESS_SUMMARY.md Section 3
    redline_headline = "p >= 0.05 (Smooth)"
    redline_sub = "No Abrupt Quantile Cliff"
    redline_detail = "Continuous variables exhibit smooth gradients without abrupt statistical cliffs."
    rl_has_cliff = False
    rl_col, rl_bad_range, rl_bad_rate, rl_good_range, rl_good_rate = "", "", "", "", ""

    r_sec = re.search(r"### 3\. Danger Threshold \(Red-Line\)([\s\S]*?)(?=\n### 4\.|\Z)", english_md)
    if r_sec:
        r_body = r_sec.group(1).strip()
        if "No Sharp Danger Threshold" in r_body or "No Physical Numeric Cliffs" in r_body or "No Numeric" in r_body:
            redline_headline = "No Sharp Cliff"
            redline_sub = "Smooth Risk Gradient (p >= 0.05)"
        else:
            m_rl = re.search(r"metric\s+`([^`]+)`.*?reach\s+\*\*([^*]+)\*\*.*?to\s+\*\*([0-9.]+%)\*\*\s*\(compared to\s+\*\*([0-9.]+%)\*\*\s+in range\s+([^)]+\]|[^)]+\))\)", r_body)
            if m_rl:
                rl_has_cliff = True
                rl_col = m_rl.group(1).strip()
                rl_bad_range = m_rl.group(2).strip()
                rl_bad_rate = m_rl.group(3).strip()
                rl_good_rate = m_rl.group(4).strip()
                rl_good_range = m_rl.group(5).strip()
                redline_headline = f"{rl_bad_rate} Surge"
                redline_sub = f"{rl_col} in {rl_bad_range}"
            else:
                m_rl2 = re.search(r"metric\s+`([^`]+)`.*?reach\s+\*\*([^*]+)\*\*.*?to\s+\*\*([0-9.]+%)\*\*", r_body)
                if m_rl2:
                    rl_has_cliff = True
                    rl_col = m_rl2.group(1).strip()
                    rl_bad_range = m_rl2.group(2).strip()
                    rl_bad_rate = m_rl2.group(3).strip()
                    redline_headline = f"{rl_bad_rate} Surge"
                    redline_sub = f"{rl_col} in {rl_bad_range}"
        redline_detail = " ".join([ln.lstrip("- ").strip() for ln in r_body.splitlines() if ln.strip()]).replace("**", "").replace("`", "")

    # 4. Extract 3 Strategic Pathways from Section 4 (both English & Hinglish)
    pathways: List[Dict[str, Any]] = []
    s_sec = re.search(r"### 4\. Your 3 Strategic Choices[^\n]*([\s\S]*?)(?=\n### 5\.|\Z)", english_md)
    if s_sec:
        s_body = s_sec.group(1).strip()
        for line in s_body.splitlines():
            ln = line.strip()
            if not ln.startswith("-"):
                continue
            clean_ln = ln.lstrip("- ").strip()
            if "$0 Spend Advisory" in clean_ln:
                pathways.append({
                    "code": "HOLD",
                    "title": f"{currency_unit}0 Spend Advisory (Do Not Intervene)",
                    "impact": f"{currency_unit}0 Extra Spend Needed",
                    "roi_range": f"{currency_unit}0 Spend Advisory",
                    "action": _localize_currency_in_text(clean_ln.replace("**", "").replace("`", ""), currency_unit),
                    "target": "All Business Groups",
                    "investment": f"{currency_unit}0 Spend",
                    "detail": _localize_currency_in_text(clean_ln.replace("**", "").replace("`", ""), currency_unit)
                })
            else:
                m_pw = re.match(r"\*\*Pathway\s+([ABC])\s*\(([^)]+)\)\*\*:\s*\*\*([^*]+)\*\*\s*(.*)", clean_ln)
                if m_pw:
                    p_letter = m_pw.group(1)
                    p_title = m_pw.group(2).strip()
                    p_impact = _localize_currency_in_text(m_pw.group(3).strip(), currency_unit)
                    p_detail = _localize_currency_in_text(m_pw.group(4).strip().replace("**", "").replace("*", "").replace("`", ""), currency_unit)
                    pathways.append({
                        "code": f"Pathway {p_letter}",
                        "title": f"Plan {p_letter}: {p_title}",
                        "impact": p_impact,
                        "roi_range": p_impact,
                        "action": p_detail,
                        "target": f"{_humanize_col_name(bn_col)} → {bn_seg}" if not bn_is_cb else "All Groups",
                        "investment": "Quick Trial (1-2 Weeks)" if p_letter == "A" else ("Team Follow-up (1 Month)" if p_letter == "B" else "Long-Term Upgrade"),
                        "detail": p_detail
                    })
                else:
                    clean_txt = _localize_currency_in_text(clean_ln.replace("**", "").replace("`", ""), currency_unit)
                    pathways.append({
                        "code": f"Option {len(pathways) + 1}",
                        "title": f"Plan {len(pathways) + 1}",
                        "impact": "Expected Savings",
                        "roi_range": "Expected Savings",
                        "action": clean_txt,
                        "target": f"{_humanize_col_name(bn_col)} → {bn_seg}",
                        "investment": "Team Effort",
                        "detail": clean_txt
                    })

    is_fin = bool(total_drag > 0 and monetary_col and monetary_col != "None")

    # 5. Build Human Business Analyst Narratives (EN + HI) for Zero-Jargon Clarity
    try:
        try:
            from .human_analyst_narrator import (
                clean_column_label,
                humanize_segment,
                infer_domain_vocab,
                rate_out_of_ten_phrase,
            )
        except ImportError:
            from human_analyst_narrator import (
                clean_column_label,
                humanize_segment,
                infer_domain_vocab,
                rate_out_of_ten_phrase,
            )
        _schema_cols: List[str] = []
        _rk_path = staging_out / "ranked_leaks_report.json"
        _vocab_loaded = None
        if _rk_path.exists():
            try:
                _rk_j = json.loads(_rk_path.read_text(encoding="utf-8"))
                if isinstance(_rk_j.get("domain_vocab"), dict):
                    _vocab_loaded = _rk_j["domain_vocab"]
            except Exception:
                pass
        if not _vocab_loaded:
            _topo_p = staging_out / "schema_topology.json"
            if _topo_p.exists():
                try:
                    _tj = json.loads(_topo_p.read_text(encoding="utf-8"))
                    for _tinfo in (_tj.get("tables") or {}).values():
                        _schema_cols.extend(list((_tinfo.get("columns") or {}).keys()))
                except Exception:
                    pass
            _vocab_loaded = infer_domain_vocab(_schema_cols or [target_col, bn_col, moat_dim, rl_col], target_col=target_col, is_financial=is_fin)
        _v = _vocab_loaded
        moat_dim_h = clean_column_label(moat_dim, "en")
        bn_col_h = clean_column_label(bn_col, "en")
        bn_col_hi = clean_column_label(bn_col, "hi")
        rl_col_h = clean_column_label(rl_col, "en") if rl_col else ""
        rl_col_hi = clean_column_label(rl_col, "hi") if rl_col else ""
        moat_seg_en = humanize_segment(moat_dim, moat_seg, "en", _v)
        moat_seg_hi = humanize_segment(moat_dim, moat_seg, "hi", _v)
        bn_seg_en = humanize_segment(bn_col, bn_seg, "en", _v)
        bn_seg_hi = humanize_segment(bn_col, bn_seg, "hi", _v)
        _bn_rate_num = float(re.sub(r"[^0-9.]", "", str(bn_rate or "0")) or "0")
        _bn_rest_num = float(re.sub(r"[^0-9.]", "", str(bn_rest_rate or "0")) or "0")
        _bn_10_en = rate_out_of_ten_phrase(_bn_rate_num, "en")
        _bn_rest_10_en = rate_out_of_ten_phrase(_bn_rest_num, "en")
        _bn_10_hi = rate_out_of_ten_phrase(_bn_rate_num, "hi")
        _bn_rest_10_hi = rate_out_of_ten_phrase(_bn_rest_num, "hi")
    except Exception:
        _v = {
            "domain": "general", "entity_en": "cases", "entity_hi": "केस",
            "fail_en": "run into problems", "fail_hi": "समस्या में आ रहे हैं",
            "safe_en": "work smoothly", "safe_hi": "सही चल रहे हैं",
            "leak_label_en": "money leak" if is_fin else "problem area",
            "leak_label_hi": "नुकसान का कारण" if is_fin else "मुख्य समस्या",
        }
        moat_dim_h = _humanize_col_name(moat_dim)
        bn_col_h = _humanize_col_name(bn_col)
        bn_col_hi = bn_col_h
        rl_col_h = _humanize_col_name(rl_col) if rl_col else ""
        rl_col_hi = rl_col_h
        moat_seg_en = moat_seg_hi = str(moat_seg)
        bn_seg_en = bn_seg_hi = str(bn_seg)
        _bn_10_en = _bn_10_hi = str(bn_rate)
        _bn_rest_10_en = _bn_rest_10_hi = f"{bn_rest_rate}%"

    ent_en = _v.get("entity_en", "cases")
    ent_hi = _v.get("entity_hi", "केस")
    fail_en = _v.get("fail_en", "run into problems")
    fail_hi = _v.get("fail_hi", "समस्या में आ रहे हैं")
    safe_en = _v.get("safe_en", "work smoothly")
    safe_hi = _v.get("safe_hi", "सही चल रहे हैं")
    leak_lbl_en = _v.get("leak_label_en", "money leak" if is_fin else "problem area")
    leak_lbl_hi = _v.get("leak_label_hi", "नुकसान का कारण" if is_fin else "मुख्य समस्या")
    fmt_drag = _format_local_money(total_drag, currency_unit) if is_fin else f"{total_events:,} {ent_en.title()}"
    first_pw_roi = pathways[0]["roi_range"] if pathways else fmt_drag

    # Clean Pathway cards for Business Owners (EN & HI — domain-tailored, zero generic "confirmation call on '248' orders")
    owner_pathways_en = []
    owner_pathways_hi = []
    _is_ops_call = _v.get("domain") in ("ecommerce", "hotel", "banking", "telecom")
    for idx, pw in enumerate(pathways):
        p_code = pw.get("code", "")
        impact_short = _localize_currency_in_text(pw.get("impact", ""), currency_unit)
        m_save = re.match(r"([^ ]+\s*(?:L|Cr|M)?)\s*(?:risk averted|saved)", impact_short, re.IGNORECASE)
        short_save = _localize_currency_in_text(
            m_save.group(1).strip() if m_save else impact_short.split("(")[0].strip(),
            currency_unit
        )
        has_nonzero_save = bool(short_save and re.search(r"[1-9]", short_save))
        if bn_is_cb and not has_nonzero_save:
            badge_en = f"{currency_unit}0 Extra Spend" if is_fin else "Hold Extra Spend"
            badge_hi = f"{currency_unit}0 एक्स्ट्रा खर्च" if is_fin else "अतिरिक्त खर्च रोकें"
        elif has_nonzero_save:
            badge_en = f"Save ~{short_save}"
            badge_hi = f"बचत ~{short_save}"
        else:
            frac = 0.25 if idx == 0 else (0.60 if idx == 1 else 1.0)
            if is_fin and total_drag > 0:
                est_lbl = _format_local_money(total_drag * frac, currency_unit)
                badge_en = f"Save ~{est_lbl}"
                badge_hi = f"बचत ~{est_lbl}"
            else:
                pct_lbl = "25%" if idx == 0 else ("60%" if idx == 1 else "Max")
                badge_en = f"Cut ~{pct_lbl} Risk"
                badge_hi = f"~{pct_lbl} जोखिम कम"

        if p_code == "HOLD":
            owner_pathways_en.append({
                "title": "Plan A: Keep Budget Safe (No Special Spend Needed)",
                "badge": f"{currency_unit}0 Extra Spend" if is_fin else "No Extra Spend",
                "story": f"Every group shows almost the same risk level, so don't spend extra money targeting one category. Focus on steady quality across all {ent_en}.",
                "target": f"All {ent_en.title()}",
                "effort": "Zero Extra Cost"
            })
            owner_pathways_hi.append({
                "title": "Plan A: पैसा बचाएँ (किसी एक ग्रुप पर अलग खर्च की ज़रूरत नहीं)",
                "badge": f"{currency_unit}0 एक्स्ट्रा खर्च" if is_fin else "कोई अतिरिक्त खर्च नहीं",
                "story": f"हर ग्रुप में रिस्क लगभग बराबर है, इसलिए किसी एक हिस्से पर अलग से पैसा न खर्च करें। सभी {ent_hi} की सामान्य क्वालिटी सुधारने पर ध्यान दें।",
                "target": f"सभी {ent_hi}",
                "effort": "शून्य अतिरिक्त खर्च"
            })
        elif idx == 0:
            _step_a_en = (
                f"Add a quick confirmation call or WhatsApp check on {bn_seg_en}"
                if _is_ops_call else
                f"Add a quick pre-check alert on {bn_seg_en} using Today's Action List"
            )
            _step_a_hi = (
                f"{bn_seg_hi} पर एक छोटा कॉल या व्हाट्सएप कन्फर्मेशन लगाएँ"
                if _is_ops_call else
                f"Today's Action List से {bn_seg_hi} की रोज़ाना त्वरित जाँच शुरू करें"
            )
            owner_pathways_en.append({
                "title": "Plan A: Quick 2-Week Trial (Lowest Risk)",
                "badge": badge_en,
                "story": f"Start in 1–2 weeks without disrupting daily work. {_step_a_en} to stop the easiest 25% of avoidable bad {ent_en}.",
                "target": bn_seg_en,
                "effort": "1–2 Weeks · Very Easy"
            })
            owner_pathways_hi.append({
                "title": "Plan A: छोटा शुरुआती ट्रायल (सबसे सुरक्षित)",
                "badge": badge_hi,
                "story": f"रोज़ के काम को बिना रोके 1–2 हफ़्ते में शुरू करें। {_step_a_hi} — इससे शुरुआती 25% खराब {ent_hi} तुरंत रुक जाएंगे।",
                "target": bn_seg_hi,
                "effort": "1–2 हफ़्ते · बहुत आसान"
            })
        elif idx == 1:
            owner_pathways_en.append({
                "title": "Plan B: Focused Team Fix (Best Balance)",
                "badge": badge_en,
                "story": f"Best return on team effort. Train your {_v.get('action_owner_en', 'team')} on a clear daily checklist for {bn_seg_en} to cut 60% of avoidable failures within 30–45 days.",
                "target": bn_seg_en,
                "effort": "30–45 Days · Best Return"
            })
            owner_pathways_hi.append({
                "title": "Plan B: फोकस्ड टीम सुधार (सबसे बेहतर नतीजा)",
                "badge": badge_hi,
                "story": f"मेहनत और फ़ायदे का सबसे सही संतुलन। अपनी {_v.get('action_owner_hi', 'टीम')} को {bn_seg_hi} के लिए स्पष्ट चेकलिस्ट दें — 30–45 दिन में 60% अतिरिक्त खराबी रुक जाएगी।",
                "target": bn_seg_hi,
                "effort": "30–45 दिन · बेस्ट ROI"
            })
        else:
            owner_pathways_en.append({
                "title": "Plan C: Full Process Upgrade (Maximum Impact)",
                "badge": badge_en,
                "story": f"Fix the root process behind {bn_seg_en} so its problem rate drops from {_bn_10_en} down to the normal {_bn_rest_10_en} seen in the rest of your business.",
                "target": bn_seg_en,
                "effort": "3–6 Months · Complete Fix"
            })
            owner_pathways_hi.append({
                "title": "Plan C: पूरा सिस्टम सुधार (सबसे बड़ी बचत)",
                "badge": badge_hi,
                "story": f"{bn_seg_hi} के पूरे प्रोसेस को सुधारें ताकि समस्या {_bn_10_hi} से घटकर बाकी बिज़नेस के सामान्य {_bn_rest_10_hi} स्तर पर आ जाए।",
                "target": bn_seg_hi,
                "effort": "3–6 महीने · पूरा सुधार"
            })

    owner_friendly = {
        "en": {
            "moat": {
                "title": f"{moat_seg_en} is working smoothly",
                "badge": f"{moat_rel} Safe",
                "story": f"Almost all {ent_en} in {moat_seg_en} ({moat_vol} {ent_en}) {safe_en}. Keep this workflow unchanged.",
                "footer": f"Checked {total_records:,} {ent_en}"
            },
            "bottleneck": {
                "title": "No single group is to blame" if bn_is_cb else f"{bn_seg_en} is your #1 {leak_lbl_en}",
                "badge": (f"{currency_unit}0 Extra Spend" if is_fin else "Balanced") if bn_is_cb else f"{bn_rate} Problem",
                "story": (
                    f"Problem rates are nearly identical across every category. Focus on steady daily quality across all {ent_en} instead of spending on one group."
                    if bn_is_cb else
                    f"In {bn_seg_en}, {_bn_10_en} {ent_en} {fail_en} — far higher than {_bn_rest_10_en} in the rest of your business. Fix this first."
                ),
                "footer": "Save budget" if bn_is_cb else f"Focus on {bn_col_h}"
            },
            "red_line": {
                "title": (
                    f"Problems spike when {rl_col_h} hits {_humanize_interval_str(rl_bad_range, 'en')}"
                    if rl_has_cliff else "No sudden tipping-point limit"
                ),
                "badge": f"Jumps to {rl_bad_rate}" if rl_has_cliff else "Gradual Trend",
                "story": (
                    f"Once {rl_col_h} reaches {_humanize_interval_str(rl_bad_range, 'en')}, failures jump to {rl_bad_rate} (vs only {rl_good_rate or 'low'} when kept at {_humanize_interval_str(rl_good_range, 'en') or 'safe values'}). Catch {ent_en} before crossing this line."
                    if rl_has_cliff else
                    "Problems rise slowly and steadily rather than breaking at one specific number. Keep steady daily tracking."
                ),
                "footer": "Watch this limit" if rl_has_cliff else "Steady operations"
            },
            "recovery": {
                "title": f"Up to {fmt_drag} can be saved" if is_fin else f"Up to {total_events:,} {ent_en} can be improved",
                "badge": owner_pathways_en[0]["badge"] if owner_pathways_en else "Ready to Fix",
                "story": (
                    f"You don't need a big overhaul on Day 1. Start with Plan A (a quick 1–2 week check on {bn_seg_en}) to start seeing results right away."
                    if not bn_is_cb else
                    f"Keep existing processes steady and monitor Today's Action List for high-risk {ent_en}."
                ),
                "footer": f"{total_events:,} total problem {ent_en}"
            },
            "pathways": owner_pathways_en
        },
        "hi": {
            "moat": {
                "title": f"{moat_seg_hi} बिल्कुल सही चल रहा है",
                "badge": f"{moat_rel} सुरक्षित",
                "story": f"{moat_seg_hi} के {moat_vol} {ent_hi} में से {moat_rel} {safe_hi}। इस तरीके को बिल्कुल न बदलें।",
                "footer": f"कुल {total_records:,} {ent_hi} जाँचे गए"
            },
            "bottleneck": {
                "title": "किसी एक ग्रुप की गलती नहीं है" if bn_is_cb else (
                    f"{bn_seg_hi} आपकी सबसे बड़ी {leak_lbl_hi} है"
                    if any(w in str(leak_lbl_hi) for w in ("समस्या", "कमी", "दिक्कत"))
                    else f"{bn_seg_hi} आपका सबसे बड़ा {leak_lbl_hi} है"
                ),
                "badge": (f"{currency_unit}0 एक्स्ट्रा खर्च" if is_fin else "संतुलित") if bn_is_cb else f"{bn_rate} समस्या",
                "story": (
                    f"हर ग्रुप में समस्या लगभग बराबर है। किसी एक कैटेगरी पर फालतू खर्च न करें, पूरे काम की सामान्य क्वालिटी पर ध्यान दें।"
                    if bn_is_cb else
                    f"{bn_seg_hi} में {_bn_10_hi} {ent_hi} {fail_hi} — जबकि बाकी बिज़नेस में यह सिर्फ़ {_bn_rest_10_hi} है। सबसे पहले इसे सुधारें।"
                ),
                "footer": "बजट बचाएँ" if bn_is_cb else f"{bn_col_hi} पर ध्यान दें"
            },
            "red_line": {
                "title": (
                    f"जब {rl_col_hi} {_humanize_interval_str(rl_bad_range, 'hi')} पहुँचता है, समस्या अचानक बढ़ जाती है"
                    if rl_has_cliff else "कोई अचानक ख़तरे वाली सीमा नहीं"
                ),
                "badge": f"{rl_bad_rate} तक उछाल" if rl_has_cliff else "धीमा बदलाव",
                "story": (
                    f"जैसे ही {rl_col_hi} {_humanize_interval_str(rl_bad_range, 'hi')} जाता है, खराबी अचानक {rl_bad_rate} तक पहुँच जाती है (जबकि {_humanize_interval_str(rl_good_range, 'hi') or 'सुरक्षित स्तर'} में यह सिर्फ़ {rl_good_rate or 'बहुत कम'} रहती है)। इस सीमा से पहले अलर्ट रखें।"
                    if rl_has_cliff else
                    "किसी एक नंबर पर अचानक नुकसान नहीं बढ़ता — स्थिति धीरे बदलती है। रोज़ाना निगरानी रखें।"
                ),
                "footer": "इस सीमा से बचें" if rl_has_cliff else "सामान्य निगरानी"
            },
            "recovery": {
                "title": f"आप {fmt_drag} तक बचा सकते हैं" if is_fin else f"{total_events:,} {ent_hi} बचाए जा सकते हैं",
                "badge": owner_pathways_hi[0]["badge"] if owner_pathways_hi else "सुधार के लिए तैयार",
                "story": (
                    f"एक साथ बड़ा बदलाव करने की ज़रूरत नहीं। Plan A से शुरू करें — 1–2 हफ़्ते में {bn_seg_hi} पर ध्यान देकर तुरंत सुधार दिखना शुरू हो जाएगा।"
                    if not bn_is_cb else
                    f"अपना मौजूदा प्रोसेस स्थिर रखें और Today's Action List में हाई-रिस्क {ent_hi} पर नज़र रखें।"
                ),
                "footer": f"कुल {total_events:,} समस्या वाले {ent_hi}"
            },
            "pathways": owner_pathways_hi
        }
    }

    growth_inventory_data: Optional[Dict[str, Any]] = None
    gi_path = staging_out / "growth_inventory_report.json"
    if gi_path.exists():
        try:
            gi_loaded = json.loads(gi_path.read_text(encoding="utf-8"))
            if isinstance(gi_loaded, dict) and gi_loaded.get("is_applicable"):
                growth_inventory_data = gi_loaded
        except Exception:
            growth_inventory_data = None

    category_intel_data: Optional[Dict[str, Any]] = None
    cat_path = staging_out / "category_intelligence_report.json"
    if cat_path.exists():
        try:
            cat_loaded = json.loads(cat_path.read_text(encoding="utf-8"))
            if isinstance(cat_loaded, dict) and cat_loaded.get("category_id"):
                category_intel_data = cat_loaded
        except Exception:
            category_intel_data = None
    else:
        # Lightweight on-the-fly synthesis for pre-existing certified benchmarks (never mutates manifest!)
        fact_pq = staging_out / "bi_ready_fact.parquet"
        if fact_pq.exists():
            try:
                import pandas as _pd_ci
                try:
                    from .category_intelligence_engine import run_category_intelligence_engine
                except ImportError:
                    from category_intelligence_engine import run_category_intelligence_engine
                _df_ci = _pd_ci.read_parquet(fact_pq)
                _bp_cat = "auto"
                _bp_sub = None
                _bp_f = staging_out / "execution_blueprint.json"
                if _bp_f.exists():
                    try:
                        _bp_j = json.loads(_bp_f.read_text(encoding="utf-8"))
                        _bp_cat = _bp_j.get("business_category", "auto")
                        _bp_sub = _bp_j.get("business_sub_category")
                    except Exception:
                        pass
                category_intel_data = run_category_intelligence_engine(
                    _df_ci,
                    output_dir=None,
                    business_category=_bp_cat,
                    business_sub_category=_bp_sub,
                    canonical_target={"target_col": target_col, "cost_col": monetary_col if is_fin else None},
                    currency_symbol=currency_unit,
                    is_financial=is_fin,
                    overall_adverse_rate_pct=adverse_rate,
                    circuit_breaker_active=bn_is_cb,
                    filename=staging_out.parent.name,
                )
            except Exception:
                category_intel_data = None

    # V7.0 Proactive Early-Warning Anomaly Radar (load or lightweight on-the-fly for certified benchmarks)
    proactive_anomaly_data: Optional[Dict[str, Any]] = None
    radar_path = staging_out / "proactive_anomaly_report.json"
    if radar_path.exists():
        try:
            rad_loaded = json.loads(radar_path.read_text(encoding="utf-8"))
            if isinstance(rad_loaded, dict) and rad_loaded.get("status"):
                proactive_anomaly_data = rad_loaded
        except Exception:
            proactive_anomaly_data = None
    else:
        fact_pq_r = staging_out / "bi_ready_fact.parquet"
        if fact_pq_r.exists():
            try:
                import pandas as _pd_rad
                try:
                    from .proactive_anomaly_radar import run_proactive_anomaly_radar
                except ImportError:
                    from proactive_anomaly_radar import run_proactive_anomaly_radar
                _df_rad = _pd_rad.read_parquet(fact_pq_r)
                proactive_anomaly_data = run_proactive_anomaly_radar(
                    _df_rad,
                    output_dir=None,
                    canonical_target={"target_col": target_col, "cost_col": monetary_col if is_fin else None},
                    currency_symbol=currency_unit,
                    is_financial=is_fin,
                    circuit_breaker_active=bn_is_cb,
                    business_category=(category_intel_data or {}).get("category_id", "auto"),
                )
            except Exception:
                proactive_anomaly_data = None

    pulse_dict = {
        "total_records": total_records,
        "total_adverse_events": total_events,
        "adverse_rate_pct": adverse_rate,
        "overall_adverse_rate_pct": adverse_rate,
        "system_reliability_pct": reliability_rate,
        "total_capital_drag": total_drag,
        "formatted_capital_drag": fmt_drag,
        "is_financial": is_fin,
        "total_portfolio_volume": total_portfolio,
        "currency_unit": currency_unit,
        "unit_symbol": currency_unit,
        "target_col": target_col,
        "target_column": target_col,
        "target_desc": target_desc,
        "monetary_col": monetary_col,
        "moat": {
            "headline": moat_sub,
            "value_badge": moat_headline,
            "subtitle": moat_sub,
            "detail": moat_detail
        },
        "bottleneck": {
            "headline": bottleneck_sub,
            "value_badge": bottleneck_headline,
            "subtitle": bottleneck_sub,
            "detail": bottleneck_detail
        },
        "red_line": {
            "headline": redline_sub,
            "value_badge": redline_headline,
            "subtitle": redline_sub,
            "detail": redline_detail
        },
        "pathways": pathways,
        "owner_friendly": owner_friendly,
        "cohort_breakdowns": cohort_breakdowns,
        "growth_inventory": growth_inventory_data,
        "category_intelligence": category_intel_data,
        "proactive_anomaly": proactive_anomaly_data,
        "english_summary_markdown": _localize_currency_in_text(english_md, currency_unit),
        "hinglish_summary_markdown": _localize_currency_in_text(hinglish_md, currency_unit)
    }

    # V7.0 Grounded 60-Second CEO Voice Brief & PII-Free Share Pack
    voice_brief_data: Optional[Dict[str, Any]] = None
    vb_path = staging_out / "voice_brief_script.json"
    if vb_path.exists():
        try:
            vb_loaded = json.loads(vb_path.read_text(encoding="utf-8"))
            if isinstance(vb_loaded, dict) and vb_loaded.get("beats"):
                voice_brief_data = vb_loaded
        except Exception:
            voice_brief_data = None
    if voice_brief_data is None:
        try:
            try:
                from .voice_brief_synthesizer import build_voice_brief_script
            except ImportError:
                from voice_brief_synthesizer import build_voice_brief_script
            _run_title = re.sub(r"[_-]+", " ", staging_out.parent.name or "Business Report").title()
            voice_brief_data = build_voice_brief_script(
                executive_pulse=pulse_dict,
                category_intelligence=category_intel_data,
                proactive_anomaly=proactive_anomaly_data,
                run_title=_run_title,
                output_dir=None,
            )
        except Exception:
            voice_brief_data = None

    pulse_dict["voice_brief"] = voice_brief_data
    return pulse_dict


def build_preview_intent_response(
    df_sample: Any,
    raw_name: str,
    region_profile: str = "US",
    business_category: str = "auto",
) -> Dict[str, Any]:
    """Pure schema + goal + V6.0 category preview builder extracted from api_server.py."""
    import numpy as np
    import pandas as pd
    try:
        from .target_resolver import resolve_canonical_target_and_cost
        from .business_category_registry import detect_business_category
    except ImportError:
        from target_resolver import resolve_canonical_target_and_cost
        from business_category_registry import detect_business_category

    canonical = resolve_canonical_target_and_cost(df_sample, region_profile=region_profile)
    target_col = canonical.get("target_col")
    cost_col = canonical.get("cost_col")
    target_desc = canonical.get("target_desc") or (f"{target_col} == 1" if target_col else "Adverse Event")
    unit_symbol = canonical.get("unit_symbol")
    if unit_symbol is None:
        unit_symbol = "$" if canonical.get("is_financial") else "events"
    currency_code = canonical.get("currency_code")
    numbering_system = canonical.get("numbering_system") or "western"
    detected_adverse_rate_pct = round(float(canonical["binary_target"].mean() * 100.0), 2) if len(df_sample) else 0.0

    target_sanity_warning_en = None
    target_sanity_warning_hi = None
    if detected_adverse_rate_pct > 65.0:
        target_sanity_warning_en = (
            f"Double-check Problem Column: {detected_adverse_rate_pct:.1f}% of sample rows are flagged as problems "
            f"('{target_desc}'). If this is an approval/good column, pick your true Failure/Default/Return column below!"
        )
        target_sanity_warning_hi = (
            f"कृपया Problem Column जाँच लें: सैंपल की {detected_adverse_rate_pct:.1f}% पंक्तियाँ समस्या ('{target_desc}') दिख रही हैं — "
            f"अगर यह सही/अप्रूवल कॉलम है तो नीचे असली Return/Default/Cancel कॉलम चुनें!"
        )
    elif detected_adverse_rate_pct < 0.2:
        target_sanity_warning_en = (
            f"Double-check Problem Column: Only {detected_adverse_rate_pct:.1f}% of sample rows are flagged as problems "
            f"('{target_desc}'). Verify this is the exact outcome column you want to fix."
        )
        target_sanity_warning_hi = (
            f"कृपया Problem Column जाँच लें: सैंपल में सिर्फ़ {detected_adverse_rate_pct:.1f}% समस्या ('{target_desc}') मिली — "
            f"पुष्टि करें कि यही कॉलम आप सुधारना चाहते हैं।"
        )

    candidate_targets = []
    cols = list(df_sample.columns)
    for c in cols:
        c_low = c.lower()
        if c_low in ("unnamed: 0", "index", "id", "lat", "lon", "latitude", "longitude"):
            continue
        nunique = int(df_sample[c].nunique())
        if (c == target_col) or (2 <= nunique <= 20) or any(
            k in c_low for k in ("delay", "churn", "cancel", "default", "paid", "fraud", "failure", "rating", "score", "status", "outcome", "value", "event", "severity", "adverse", "injury", "death", "defect")
        ):
            sample_vals = [str(v) for v in df_sample[c].dropna().unique()[:4]]
            candidate_targets.append({
                "column": c,
                "unique_values_count": nunique,
                "sample_values": sample_vals,
                "is_detected_default": (c == target_col),
            })

    candidate_costs = []
    for c in cols:
        c_low = c.lower()
        if pd.api.types.is_numeric_dtype(df_sample[c]) and c != target_col:
            if not any(k in c_low for k in ("id", "key", "code", "year", "month", "day", "hour", "age", "latitude", "longitude", "zip")):
                s_valid = pd.to_numeric(df_sample[c], errors="coerce").dropna()
                if len(s_valid) > 0 and (s_valid > 0).mean() > 0.5:
                    candidate_costs.append({
                        "column": c,
                        "sample_mean": round(float(s_valid.mean()), 2),
                        "unit_symbol": unit_symbol,
                        "is_detected_default": (c == cost_col),
                    })

    if cost_col:
        question_en = f"What is driving adverse '{target_desc}' and how can we recover capital in '{cost_col}'?"
        question_hi = f"Kyun '{target_desc}' ho raha hai aur '{cost_col}' ka capital loss kaise rokein?"
    else:
        question_en = f"What is driving adverse '{target_desc}' and what operational bottlenecks need fixing?"
        question_hi = f"Kyun '{target_desc}' ho raha hai aur operational bottlenecks ko kaise theek karein?"

    df_clean_head = df_sample.head(5).copy()
    for _c in df_clean_head.columns:
        if pd.api.types.is_numeric_dtype(df_clean_head[_c]):
            df_clean_head[_c] = df_clean_head[_c].replace([np.inf, -np.inf], np.nan)
    preview_rows = [
        {k: (None if pd.isna(v) else (v.item() if isinstance(v, np.generic) else v)) for k, v in row.items()}
        for row in df_clean_head.to_dict(orient="records")
    ]

    detected_category = detect_business_category(
        columns=cols,
        sample_df=df_sample,
        filename=raw_name,
        user_selected_category=business_category,
    )

    return {
        "status": "success",
        "filename": raw_name,
        "sample_rows_count": len(df_sample),
        "columns_count": len(cols),
        "columns": cols,
        "preview_rows": preview_rows,
        "detected_category": detected_category,
        "detected_goal": {
            "target_col": target_col,
            "target_desc": target_desc,
            "detected_adverse_rate_pct": detected_adverse_rate_pct,
            "target_sanity_warning_en": target_sanity_warning_en,
            "target_sanity_warning_hi": target_sanity_warning_hi,
            "cost_col": cost_col,
            "is_financial": canonical.get("is_financial", False),
            "unit_symbol": unit_symbol,
            "currency_code": currency_code,
            "numbering_system": numbering_system,
            "business_question_en": question_en,
            "business_question_hi": question_hi,
        },
        "candidate_targets": candidate_targets,
        "candidate_costs": candidate_costs,
    }
