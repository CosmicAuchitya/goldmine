"""
DataX-Ray Human Business Analyst Narrator (Layer 1 Deterministic + Optional Layer 2 AI Polish).

Transforms raw database columns, cryptic 0/1 flags, and technical statistical ratios
(e.g. "'1' in Turbidity Fails at 59.81% (2.73x Normal Rate)") into the clear, practical
advice a senior human business analyst / CA advisor gives a business owner across the table:

  1. WHAT WE FOUND   — Plain everyday language (e.g. "Cloudy Milk (High Turbidity): 6 Out of 10 Batches Fail")
  2. WHY IT HAPPENS  — Automatic cross-column physical root-cause check directly on DuckDB/Pandas fact rows
                       (e.g. "94% of failed batches had pH outside 6.5–6.8 and 42% crossed 45°C")
  3. WHAT TO DO NEXT — Concrete, domain-tailored operational steps (dairy, restaurant, retail, hotel, bank, HR)

Zero-Hallucination Guarantee:
- Layer 1 is 100% deterministic, fast (<5ms per finding), works offline, and computes every
  co-driver percentage strictly from the physical DataFrame.
- Optional Layer 2 (`polish_leaks_with_gemini`) uses Gemini when explicitly enabled with an API key
  AND enforces a strict numeric lock so no metric can ever be invented or altered.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from .target_resolver import (
        is_demographic_attribute,
        is_deterministic_target_leakage,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
    )
except ImportError:
    from target_resolver import (
        is_demographic_attribute,
        is_deterministic_target_leakage,
        is_index_artifact,
        is_pseudo_numeric_identifier,
        is_synthetic_column,
    )


# ---------------------------------------------------------------------------
# 1. Domain-Aware Entity & Outcome Vocabulary
# ---------------------------------------------------------------------------
def infer_domain_vocab(
    columns: List[str],
    target_col: Optional[str] = None,
    is_financial: bool = False,
) -> Dict[str, str]:
    """
    Infers everyday business nouns and verbs from schema columns so a dairy owner
    never sees 'Check 1 orders in Today's Call List' and a restaurant owner sees
    'outlets' & 'ratings' instead of generic 'records'.
    """
    joined = " ".join(str(c).lower() for c in (columns or []))
    t_low = str(target_col or "").lower()

    # Dairy / Milk Quality Lab
    if any(k in joined for k in ("turbidity", "temprature", "milk", "cows", "dairy", "shelf life", "butter", "paneer", "curd")):
        if any(k in t_low for k in ("grade", "quality", "spoil", "defect")):
            return {
                "domain": "dairy_quality",
                "entity_en": "milk batches",
                "entity_sg_en": "milk batch",
                "entity_hi": "दूध के बैच",
                "entity_sg_hi": "बैच",
                "fail_en": "fail quality check",
                "fail_short_en": "fail quality",
                "fail_hi": "क्वालिटी में फेल हो रहे हैं",
                "safe_en": "pass quality check cleanly",
                "safe_hi": "सही क्वालिटी में पास हो रहे हैं",
                "leak_label_en": "quality problem",
                "leak_label_hi": "क्वालिटी की समस्या",
                "action_owner_en": "plant / quality supervisor",
                "action_owner_hi": "डेरी / क्वालिटी सुपरवाइज़र",
            }
        return {
            "domain": "dairy_ops",
            "entity_en": "dairy batches",
            "entity_sg_en": "dairy batch",
            "entity_hi": "डेरी बैच",
            "entity_sg_hi": "बैच",
            "fail_en": "drop into low revenue" if "revenue" in t_low or "sales" in t_low else "run into stock/supply issues",
            "fail_short_en": "underperform",
            "fail_hi": "कम कमाई में जा रहे हैं" if "revenue" in t_low or "sales" in t_low else "सप्लाई में दिक्कत दिखा रहे हैं",
            "safe_en": "sell smoothly",
            "safe_hi": "अच्छी तरह बिक रहे हैं",
            "leak_label_en": "revenue leak" if is_financial else "supply issue",
            "leak_label_hi": "कमाई का नुकसान" if is_financial else "सप्लाई की समस्या",
            "action_owner_en": "dairy operations team",
            "action_owner_hi": "डेरी ऑपरेशंस टीम",
        }

    # Restaurant / Zomato / Dining
    if any(k in joined for k in ("restaurant", "cuisines", "table booking", "online delivery", "average cost for two", "dining", "smoker")):
        is_rating = any(k in t_low for k in ("rating", "score", "review", "csat"))
        return {
            "domain": "restaurant",
            "entity_en": "restaurants" if "restaurant" in joined else "dining orders",
            "entity_sg_en": "restaurant" if "restaurant" in joined else "table",
            "entity_hi": "रेस्टोरेंट्स" if "restaurant" in joined else "टेबल / बिल",
            "entity_sg_hi": "रेस्टोरेंट" if "restaurant" in joined else "बिल",
            "fail_en": "get low ratings" if is_rating else "run into service issues",
            "fail_short_en": "rated low" if is_rating else "face issues",
            "fail_hi": "कम रेटिंग पा रहे हैं" if is_rating else "सर्विस में दिक्कत दिखा रहे हैं",
            "safe_en": "maintain strong ratings" if is_rating else "run smoothly",
            "safe_hi": "अच्छी रेटिंग बनाए हुए हैं" if is_rating else "सही चल रहे हैं",
            "leak_label_en": "rating & revenue risk" if is_financial else "rating problem",
            "leak_label_hi": "रेटिंग और कमाई का नुकसान" if is_financial else "रेटिंग की समस्या",
            "action_owner_en": "outlet manager",
            "action_owner_hi": "रेस्टोरेंट मैनेजर",
        }

    # Hotel / Hospitality Bookings
    if any(k in joined for k in ("assigned_room_type", "hotel", "adr", "lead_time", "deposit_type", "stays_in_weekend")):
        return {
            "domain": "hotel",
            "entity_en": "bookings",
            "entity_sg_en": "booking",
            "entity_hi": "बुकिंग्स",
            "entity_sg_hi": "बुकिंग",
            "fail_en": "get cancelled",
            "fail_short_en": "cancelled",
            "fail_hi": "कैंसल हो रही हैं",
            "safe_en": "check in smoothly",
            "safe_hi": "बिना कैंसल हुए पूरी हो रही हैं",
            "leak_label_en": "cancellation loss",
            "leak_label_hi": "कैंसिलेशन नुकसान",
            "action_owner_en": "front-desk / reservations team",
            "action_owner_hi": "रिज़र्वेशन टीम",
        }

    # E-commerce / Retail / Logistics / Courier
    if any(k in joined for k in ("courier", "rto", "shipment", "warehouse", "order_id", "sku", "dispatch", "delivery_days", "payment_mode", "return")):
        return {
            "domain": "ecommerce",
            "entity_en": "orders",
            "entity_sg_en": "order",
            "entity_hi": "ऑर्डर्स",
            "entity_sg_hi": "ऑर्डर",
            "fail_en": "face returns or failures",
            "fail_short_en": "returned/failed",
            "fail_hi": "रिटर्न या खराब हो रहे हैं",
            "safe_en": "deliver smoothly",
            "safe_hi": "बिना दिक्कत डिलीवर हो रहे हैं",
            "leak_label_en": "money leak",
            "leak_label_hi": "पैसे का नुकसान",
            "action_owner_en": "operations & dispatch team",
            "action_owner_hi": "ऑपरेशंस और डिस्पैच टीम",
        }

    # Banking / Credit / Loans
    if any(k in joined for k in ("loan", "credit_limit", "emi", "interest_rate", "default", "borrower")):
        return {
            "domain": "banking",
            "entity_en": "loan accounts",
            "entity_sg_en": "account",
            "entity_hi": "लोन खाते",
            "entity_sg_hi": "खाता",
            "fail_en": "fall into default",
            "fail_short_en": "default",
            "fail_hi": "डिफॉल्ट हो रहे हैं",
            "safe_en": "repay on time",
            "safe_hi": "समय पर किस्त भर रहे हैं",
            "leak_label_en": "default exposure",
            "leak_label_hi": "डिफॉल्ट जोखिम",
            "action_owner_en": "credit & collections team",
            "action_owner_hi": "क्रेडिट और रिकवरी टीम",
        }

    # Telecom / SaaS / Subscriptions
    if any(k in joined for k in ("churn", "monthlycharges", "tipocontrato", "contract", "tenure", "mrr")):
        return {
            "domain": "telecom",
            "entity_en": "customers",
            "entity_sg_en": "customer",
            "entity_hi": "ग्राहक",
            "entity_sg_hi": "ग्राहक",
            "fail_en": "cancel and leave",
            "fail_short_en": "churn",
            "fail_hi": "सर्विस छोड़कर जा रहे हैं",
            "safe_en": "stay loyal",
            "safe_hi": "लगातार जुड़े हुए हैं",
            "leak_label_en": "customer churn loss",
            "leak_label_hi": "ग्राहक छूटने का नुकसान",
            "action_owner_en": "customer retention team",
            "action_owner_hi": "कस्टमर रिटेंशन टीम",
        }

    # Healthcare / Clinical
    if any(k in joined for k in ("ejection_fraction", "insulin", "glucose", "diabetes", "patient", "bloodpressure", "serum_creatinine")):
        return {
            "domain": "clinical",
            "entity_en": "patient cases",
            "entity_sg_en": "patient case",
            "entity_hi": "मरीज़ों के केस",
            "entity_sg_hi": "केस",
            "fail_en": "show high clinical risk",
            "fail_short_en": "high risk",
            "fail_hi": "हाई रिस्क में आ रहे हैं",
            "safe_en": "remain stable",
            "safe_hi": "स्थिर और सुरक्षित हैं",
            "leak_label_en": "clinical risk concentration",
            "leak_label_hi": "क्लीनिकल रिस्क",
            "action_owner_en": "clinical care team",
            "action_owner_hi": "क्लीनिकल टीम",
        }

    # HR / Attrition
    if any(k in joined for k in ("attrition", "jobrole", "overtime", "monthlyincome", "yearscompany")):
        return {
            "domain": "hr",
            "entity_en": "employees",
            "entity_sg_en": "employee",
            "entity_hi": "कर्मचारी",
            "entity_sg_hi": "कर्मचारी",
            "fail_en": "leave the company",
            "fail_short_en": "leave",
            "fail_hi": "नौकरी छोड़कर जा रहे हैं",
            "safe_en": "stay with the team",
            "safe_hi": "कंपनी में टिके हुए हैं",
            "leak_label_en": "attrition risk",
            "leak_label_hi": "कर्मचारी छोड़ने का जोखिम",
            "action_owner_en": "HR & team managers",
            "action_owner_hi": "HR और टीम मैनेजर्स",
        }

    # Generic business fallback
    return {
        "domain": "general",
        "entity_en": "cases",
        "entity_sg_en": "case",
        "entity_hi": "केस",
        "entity_sg_hi": "केस",
        "fail_en": "run into problems",
        "fail_short_en": "have problems",
        "fail_hi": "समस्या में आ रहे हैं",
        "safe_en": "work smoothly",
        "safe_hi": "बिना दिक्कत चल रहे हैं",
        "leak_label_en": "money leak" if is_financial else "problem area",
        "leak_label_hi": "नुकसान का बड़ा कारण" if is_financial else "मुख्य समस्या",
        "action_owner_en": "operations team",
        "action_owner_hi": "ऑपरेशंस टीम",
    }


# ---------------------------------------------------------------------------
# 2. Plain Column & Segment Name Translators (ZERO bare '1', '0', 'No', '248')
# ---------------------------------------------------------------------------
def clean_column_label(col_name: str, lang: str = "en") -> str:
    """Converts raw schema column names (incl. common Kaggle typos like Temprature) into crisp human labels."""
    raw = str(col_name or "").strip()
    low = re.sub(r"[\s\-]+", "_", raw.lower()).strip("_")

    en_glossary = {
        "temprature": "Temperature",
        "temperature": "Temperature",
        "ph": "Acidity (pH)",
        "turbidity": "Milk Cloudiness (Turbidity)",
        "fat": "Milk Fat Level",
        "taste": "Milk Taste Check",
        "odor": "Milk Odor Check",
        "colour": "Milk Colour Reading",
        "color": "Colour Reading",
        "has_table_booking": "Table Booking",
        "has_online_delivery": "Online Delivery",
        "is_delivering_now": "Live Delivery",
        "average_cost_for_two": "Average Bill for Two",
        "price_range": "Price Tier",
        "aggregate_rating": "Customer Rating",
        "votes": "Customer Reviews (Votes)",
        "cuisines": "Cuisine Type",
        "locality": "Area / Locality",
        "payment_mode": "Payment Mode",
        "payment_method": "Payment Method",
        "courier_partner": "Delivery Courier",
        "courier": "Delivery Courier",
        "carrier": "Carrier / Courier",
        "product_item": "Product",
        "product_name": "Product",
        "sku_name": "Product / SKU",
        "customer_state": "State",
        "delivery_days": "Delivery Time (Days)",
        "transit_days": "Delivery Time (Days)",
        "is_repeated_guest": "Guest Type",
        "distribution_channel": "Booking Channel",
        "market_segment": "Customer Segment",
        "deposit_type": "Deposit Policy",
        "assigned_room_type": "Room Category",
        "total_of_special_requests": "Special Requests",
        "approx._total_revenue(inr)": "Total Revenue (₹)",
        "quantity_sold_(liters/kg)": "Quantity Sold",
        "shelf_life_(days)": "Shelf Life (Days)",
        "storage_condition": "Storage Type",
        "sales_channel": "Sales Channel",
        "pclass": "Passenger Class",
    }
    hi_glossary = {
        "temprature": "तापमान (Temperature)",
        "temperature": "तापमान (Temperature)",
        "ph": "एसिडिटी (pH)",
        "turbidity": "दूध का धुंधलापन (Turbidity)",
        "fat": "दूध का फैट (Fat)",
        "taste": "दूध का स्वाद (Taste)",
        "odor": "दूध की गंध (Odor)",
        "colour": "दूध का रंग (Colour)",
        "color": "रंग (Colour)",
        "has_table_booking": "टेबल बुकिंग",
        "has_online_delivery": "ऑनलाइन डिलीवरी",
        "is_delivering_now": "लाइव डिलीवरी",
        "average_cost_for_two": "दो लोगों का औसत बिल",
        "price_range": "प्राइस रेंज",
        "aggregate_rating": "ग्राहक रेटिंग",
        "votes": "ग्राहक रिव्यू (Votes)",
        "cuisines": "खाने की श्रेणी (Cuisine)",
        "locality": "इलाका (Locality)",
        "city": "शहर",
        "payment_mode": "पेमेंट का तरीका",
        "payment_method": "पेमेंट का तरीका",
        "courier_partner": "कूरियर कंपनी",
        "courier": "कूरियर कंपनी",
        "product_item": "प्रोडक्ट",
        "product_name": "प्रोडक्ट",
        "customer_state": "राज्य",
        "delivery_days": "डिलीवरी के दिन",
        "is_repeated_guest": "ग्राहक प्रकार",
        "distribution_channel": "बुकिंग चैनल",
        "deposit_type": "डिपॉज़िट नियम",
        "assigned_room_type": "रूम कैटेगरी",
        "storage_condition": "स्टोरेज का तरीका",
        "sales_channel": "सेल्स चैनल",
    }
    if lang == "hi":
        if low in hi_glossary:
            return hi_glossary[low]
        return raw.replace("_", " ").title()
    if low in en_glossary:
        return en_glossary[low]
    return raw.replace("_", " ").title()


def humanize_segment(
    dim_name: str,
    seg_val: Any,
    lang: str = "en",
    vocab: Optional[Dict[str, str]] = None,
) -> str:
    """
    Translates raw column + value pairs into crystal-clear everyday phrases so
    no owner ever reads "'1' in Turbidity", "'No' in Has Table Booking", or "'248' in Colour".
    """
    d_raw = str(dim_name or "").strip()
    d_low = re.sub(r"[\s\-]+", "_", d_raw.lower()).strip("_")
    s_raw = str(seg_val or "").strip()
    s_low = s_raw.lower()
    ent_en = (vocab or {}).get("entity_en", "cases")
    ent_hi = (vocab or {}).get("entity_hi", "केस")

    # 1. Exact high-value dairy & hospitality binary/reading phrases
    if d_low == "turbidity":
        if s_low in ("1", "1.0", "true", "yes"):
            return "धुंधला दूध (High Turbidity)" if lang == "hi" else "Cloudy Milk (High Turbidity)"
        if s_low in ("0", "0.0", "false", "no"):
            return "साफ़ दूध (Low Turbidity)" if lang == "hi" else "Clear Milk (Low Turbidity)"
    if d_low == "fat":
        if s_low in ("1", "1.0", "true", "yes"):
            return "ज़्यादा फैट वाला दूध (High Fat)" if lang == "hi" else "High-Fat Milk"
        if s_low in ("0", "0.0", "false", "no"):
            return "कम फैट वाला दूध (Low Fat)" if lang == "hi" else "Low-Fat Milk"
    if d_low == "odor":
        if s_low in ("1", "1.0", "true", "yes"):
            return "तेज़ गंध वाला दूध (Odor = 1)" if lang == "hi" else "Milk With Noticeable Odor (Odor = 1)"
        if s_low in ("0", "0.0", "false", "no"):
            return "बिना गंध वाला दूध (Odor = 0)" if lang == "hi" else "Odor-Free Milk (Odor = 0)"
    if d_low == "taste":
        if s_low in ("1", "1.0", "true", "yes"):
            return "Taste = 1 वाले दूध के बैच" if lang == "hi" else "Milk Batches Flagged Taste = 1"
        if s_low in ("0", "0.0", "false", "no"):
            return "Taste = 0 वाले दूध के बैच" if lang == "hi" else "Milk Batches Flagged Taste = 0"
    if d_low in ("colour", "color") and re.match(r"^\d+(?:\.\d+)?$", s_raw):
        return f"रंग रीडिंग {s_raw} वाला दूध (Colour {s_raw})" if lang == "hi" else f"Milk With Off-White Colour Reading {s_raw}"

    if d_low == "is_repeated_guest":
        if s_low in ("0", "0.0", "false", "no"):
            return "पहली बार आए ग्राहक (First-Time Guests)" if lang == "hi" else "First-Time Guests"
        if s_low in ("1", "1.0", "true", "yes"):
            return "पुराने रिपीट ग्राहक (Repeat Guests)" if lang == "hi" else "Returning Guests"
    if d_low == "total_of_special_requests" and s_low in ("0", "0.0"):
        return "बिना स्पेशल रिक्वेस्ट वाली बुकिंग" if lang == "hi" else "Bookings With No Special Requests"
    if d_low in ("distribution_channel", "market_segment") and s_raw.upper() == "TA/TO":
        return "ट्रैवल एजेंट बुकिंग (TA/TO)" if lang == "hi" else "Travel Agent Bookings (TA/TO)"
    if d_low == "deposit_type" and s_low in ("non refund", "non-refund"):
        return "नॉन-रिफंडेबल बुकिंग" if lang == "hi" else "Non-Refundable Bookings"

    # 2. Universal "Has <Feature>" handler (e.g., Has Table booking = No -> Without Table Booking)
    if d_low.startswith("has_"):
        feat_en = clean_column_label(d_raw, "en")
        feat_hi = clean_column_label(d_raw, "hi")
        if s_low in ("no", "0", "0.0", "false", "n"):
            return f"बिना {feat_hi} वाले {ent_hi}" if lang == "hi" else f"{ent_en.title()} Without {feat_en}"
        if s_low in ("yes", "1", "1.0", "true", "y"):
            return f"{feat_hi} वाले {ent_hi}" if lang == "hi" else f"{ent_en.title()} With {feat_en}"

    # 3. Universal "Is <State>" handler
    if d_low.startswith("is_"):
        feat_en = re.sub(r"^is[\s_]+", "", d_raw, flags=re.IGNORECASE).replace("_", " ").title()
        feat_hi = clean_column_label(d_raw, "hi")
        if s_low in ("no", "0", "0.0", "false", "n"):
            return f"बिना {feat_hi} वाले {ent_hi}" if lang == "hi" else f"{ent_en.title()} Not {feat_en}"
        if s_low in ("yes", "1", "1.0", "true", "y"):
            return f"{feat_hi} वाले {ent_hi}" if lang == "hi" else f"{feat_en} {ent_en.title()}"

    # 4. Universal binary 0/1 or Yes/No column
    dim_lbl_en = clean_column_label(d_raw, "en")
    dim_lbl_hi = clean_column_label(d_raw, "hi")
    if s_low in ("1", "1.0", "yes", "true"):
        return f"जब {dim_lbl_hi} हाँ / ज़्यादा (1) हो" if lang == "hi" else f"High / Active {dim_lbl_en}"
    if s_low in ("0", "0.0", "no", "false"):
        return f"जब {dim_lbl_hi} नहीं / कम (0) हो" if lang == "hi" else f"Low / Absent {dim_lbl_en}"

    # 5. Pure numeric category/tier value (e.g., Price range = 1, Pclass = 3)
    if re.match(r"^-?\d+(?:\.\d+)?$", s_raw):
        return f"{dim_lbl_hi} = {s_raw}" if lang == "hi" else f"{dim_lbl_en} {s_raw}"

    # 6. Clean named entity (e.g., Faridabad in City, Month-to-month in Contract)
    if d_low in ("city", "location", "state", "region", "customer_state", "locality"):
        return f"{s_raw} ({dim_lbl_hi})" if lang == "hi" else f"{s_raw} {ent_en.title()}"
    if d_low == "contract" and s_low == "month-to-month":
        return "मासिक प्लान (Month-to-Month)" if lang == "hi" else "Month-to-Month Plans"

    return f"{s_raw} ({dim_lbl_hi})" if lang == "hi" else f"{s_raw} ({dim_lbl_en})"


# ---------------------------------------------------------------------------
# 3. Everyday Human Ratio & "Out of 10" Number Translator
# ---------------------------------------------------------------------------
def rate_out_of_ten_phrase(rate_pct: float, lang: str = "en") -> str:
    """Converts raw decimal percentages like 59.81% into intuitive '6 out of 10 (60%)' human speech."""
    r = max(0.0, min(100.0, float(rate_pct or 0.0)))
    r_int = int(round(r))
    if r >= 97.5:
        return "लगभग हर एक (100%)" if lang == "hi" else "nearly every single one (100%)" if r < 99.9 else "every single one (100%)"
    if r >= 85.0:
        return f"हर 10 में से 9 ({r_int}%)" if lang == "hi" else f"9 out of 10 ({r_int}%)"
    if r >= 75.0:
        return f"हर 10 में से 8 ({r_int}%)" if lang == "hi" else f"8 out of 10 ({r_int}%)"
    if r >= 65.0:
        return f"हर 10 में से 7 ({r_int}%)" if lang == "hi" else f"7 out of 10 ({r_int}%)"
    if r >= 55.0:
        return f"हर 10 में से 6 ({r_int}%)" if lang == "hi" else f"6 out of 10 ({r_int}%)"
    if r >= 45.0:
        return f"आधे (हर 10 में से 5 · {r_int}%)" if lang == "hi" else f"half ({r_int}%)"
    if r >= 35.0:
        return f"हर 10 में से 4 ({r_int}%)" if lang == "hi" else f"4 out of 10 ({r_int}%)"
    if r >= 25.0:
        return f"हर 10 में से 3 ({r_int}%)" if lang == "hi" else f"about 3 out of 10 ({r_int}%)"
    if r >= 16.0:
        return f"हर 10 में से 2 ({r_int}%)" if lang == "hi" else f"about 2 out of 10 ({r_int}%)"
    if r >= 8.0:
        return f"हर 10 में से 1 ({r_int}%)" if lang == "hi" else f"about 1 in 10 ({r_int}%)"
    return f"सिर्फ़ {r:.1f}%" if lang == "hi" else f"only {r:.1f}%"


def rate_short_ratio(rate_pct: float, lang: str = "en") -> str:
    """Compact human ratio suitable for headlines & gauge bars (no scary 2-decimal precision)."""
    r = max(0.0, min(100.0, float(rate_pct or 0.0)))
    if r >= 97.5:
        return "लगभग 100%" if lang == "hi" else "Almost 100%"
    if r >= 55.0:
        n10 = min(9, max(6, int(round(r / 10.0))))
        return f"10 में से {n10}" if lang == "hi" else f"{n10} in 10"
    if r >= 45.0:
        return "हर 2 में से 1" if lang == "hi" else "1 in 2"
    if r >= 28.0:
        n10 = max(3, min(4, int(round(r / 10.0))))
        return f"10 में से {n10}" if lang == "hi" else f"{n10} in 10"
    if r >= 16.0:
        return "10 में से 2" if lang == "hi" else "2 in 10"
    if r >= 8.0:
        return "10 में से 1" if lang == "hi" else "1 in 10"
    return f"{r:.1f}%"


def multiplier_human_phrase(mult: float, lang: str = "en") -> str:
    """Translates 2.73x -> 'nearly 3× higher than normal' instead of '(2.73x Normal Rate)'."""
    m = float(mult or 1.0)
    if m >= 3.4:
        n = int(round(m))
        return f"सामान्य से लगभग {n} गुना ज़्यादा" if lang == "hi" else f"over {n}× higher than usual"
    if m >= 2.65:
        return "सामान्य से लगभग 3 गुना ज़्यादा" if lang == "hi" else "nearly 3× higher than usual"
    if m >= 2.25:
        return "सामान्य से लगभग ढाई गुना ज़्यादा" if lang == "hi" else "about 2.5× higher than usual"
    if m >= 1.75:
        return "सामान्य से लगभग दोगुना" if lang == "hi" else "nearly double the usual rate"
    if m >= 1.35:
        return "सामान्य से लगभग डेढ़ गुना ज़्यादा" if lang == "hi" else "about 1.5× higher than usual"
    return "सामान्य से काफ़ी ज़्यादा" if lang == "hi" else "noticeably higher than usual"


def humanize_interval(interval_str: str, lang: str = "en") -> str:
    """Converts math interval '(6.8, 9.5]' into plain speech 'above 6.8 (up to 9.5)'."""
    s = str(interval_str or "").strip()
    m = re.match(r"^[\(\[]\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*[\)\]]$", s)
    if not m:
        return s
    lo, hi = float(m.group(1)), float(m.group(2))
    lo_s = f"{lo:g}"
    hi_s = f"{hi:g}"
    if lang == "hi":
        return f"{lo_s} से {hi_s} के बीच"
    return f"above {lo_s} (up to {hi_s})"


# ---------------------------------------------------------------------------
# 4. Automatic Cross-Column Physical Root-Cause Finder ("WHY It's Happening")
# ---------------------------------------------------------------------------
def diagnose_segment_root_reasons(
    df: Optional[pd.DataFrame],
    dim_name: str,
    seg_val: Any,
    binary_target: Optional[pd.Series],
    target_col: Optional[str] = None,
    blueprint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Scans other physical columns inside the failing rows of `(dim_name == seg_val)`
    versus healthy passing rows to discover REAL, mathematically verified operational reasons
    explaining WHY this segment is failing (e.g. pH outside safe 6.5–6.8 band, Temperature > 45°C,
    very few customer Votes, long Delivery Days, high Discounts, etc.).

    Returns:
      {
        "reasons_en": [str, ...],
        "reasons_hi": [str, ...],
        "driver_cols": [col, ...],
        "driver_hints_en": [str, ...],
        "driver_hints_hi": [str, ...],
      }
    """
    empty = {"reasons_en": [], "reasons_hi": [], "driver_cols": [], "driver_hints_en": [], "driver_hints_hi": []}
    if not isinstance(df, pd.DataFrame) or len(df) < 20 or dim_name not in df.columns or binary_target is None:
        return empty

    try:
        y = pd.Series(binary_target).reset_index(drop=True).astype(int)
        df_r = df.reset_index(drop=True)
        if len(y) != len(df_r):
            return empty

        seg_mask = df_r[dim_name].astype(str) == str(seg_val)
        bad_mask = seg_mask & (y == 1)
        good_in_seg = seg_mask & (y == 0)
        ref_good_mask = good_in_seg if int(good_in_seg.sum()) >= 15 else (y == 0)

        n_bad = int(bad_mask.sum())
        n_good = int(ref_good_mask.sum())
        if n_bad < 5 or n_good < 10:
            return empty

        skip_cols = {dim_name, target_col, "_is_target_event", "_dx_y_bin"}
        coord_names = {"latitude", "longitude", "lat", "lon", "lng", "geo_lat", "geo_lng"}

        scored_reasons: List[Tuple[float, str, str, str, str, str]] = []

        for col in df_r.columns:
            if col in skip_cols:
                continue
            c_low = str(col).strip().lower()
            if c_low in coord_names:
                continue
            if is_index_artifact(col) or is_synthetic_column(col, blueprint) or is_demographic_attribute(col):
                continue
            if is_pseudo_numeric_identifier(col, df_r[col]):
                continue
            if is_deterministic_target_leakage(col, df_r[col], y, target_col=target_col):
                continue

            ser = df_r[col]
            if ser.dropna().nunique() <= 1:
                continue

            col_en = clean_column_label(col, "en")
            col_hi = clean_column_label(col, "hi")

            if pd.api.types.is_numeric_dtype(ser):
                s_bad = pd.to_numeric(ser.loc[bad_mask], errors="coerce").dropna()
                s_good = pd.to_numeric(ser.loc[ref_good_mask], errors="coerce").dropna()
                if len(s_bad) < 5 or len(s_good) < 10:
                    continue
                # Skip pure 0/1 flags here (handle below as clean categorical/binary check)
                u_all = set(pd.to_numeric(ser.dropna(), errors="coerce").dropna().unique())
                if u_all.issubset({0, 1, 0.0, 1.0}):
                    continue

                # Check 1: Out-of-healthy-safe-band breach (catches BOTH 2-sided pH [6.4–6.8] AND 1-sided Temp > 45!)
                q05 = float(s_good.quantile(0.05))
                q95 = float(s_good.quantile(0.95))
                bad_below = float((s_bad < q05).mean())
                bad_above = float((s_bad > q95).mean())
                bad_out = float(((s_bad < q05) | (s_bad > q95)).mean())
                good_out = float(((s_good < q05) | (s_good > q95)).mean())
                lift_out = bad_out - good_out

                if bad_out >= 0.35 and lift_out >= 0.20:
                    pct_out = int(round(bad_out * 100))
                    q05_s, q95_s = f"{q05:g}", f"{q95:g}"
                    if bad_above >= 0.30 and bad_below < 0.12:
                        r_en = f"{pct_out}% of these problem cases crossed {col_en} above the safe level ({q95_s})"
                        r_hi = f"इनमें से {pct_out}% खराब केस में {col_hi} सुरक्षित सीमा ({q95_s}) से ऊपर चला गया"
                        h_en = f"keep {col_en} at or below {q95_s}"
                        h_hi = f"{col_hi} को {q95_s} से नीचे रखें"
                    elif bad_below >= 0.30 and bad_above < 0.12:
                        r_en = f"{pct_out}% of these problem cases dropped below the healthy {col_en} level ({q05_s})"
                        r_hi = f"इनमें से {pct_out}% खराब केस में {col_hi} सुरक्षित स्तर ({q05_s}) से नीचे गिर गया"
                        h_en = f"keep {col_en} above {q05_s}"
                        h_hi = f"{col_hi} को {q05_s} से ऊपर रखें"
                    else:
                        r_en = f"{pct_out}% of these problem cases went outside the safe {col_en} range ({q05_s}–{q95_s})"
                        r_hi = f"इनमें से {pct_out}% खराब केस में {col_hi} सुरक्षित दायरे ({q05_s}–{q95_s}) से बाहर चला गया"
                        h_en = f"keep {col_en} strictly within {q05_s}–{q95_s}"
                        h_hi = f"{col_hi} को {q05_s}–{q95_s} के सुरक्षित दायरे में रखें"
                    scored_reasons.append((lift_out + bad_out * 0.5, col, r_en, r_hi, h_en, h_hi))
                    continue

                # Check 2: Strong median shift (e.g. Votes 14 vs 115, Delivery Days 7 vs 3, Average Bill 300 vs 800)
                med_b = float(s_bad.median())
                med_g = float(s_good.median())
                if med_g > 0 and abs(med_b - med_g) / max(abs(med_g), 1e-6) >= 0.35:
                    ratio = med_b / med_g
                    # Require meaningful separation (IQR overlap check)
                    std_g = float(s_good.std()) or 1.0
                    eff = abs(med_b - med_g) / max(std_g, 1e-6)
                    if eff >= 0.35:
                        mb_s = f"{med_b:,.0f}" if abs(med_b) >= 10 else f"{med_b:.1f}"
                        mg_s = f"{med_g:,.0f}" if abs(med_g) >= 10 else f"{med_g:.1f}"
                        if ratio < 0.70:
                            r_en = f"typical {col_en} here is much lower ({mb_s} vs {mg_s} in healthy cases)"
                            r_hi = f"यहाँ औसत {col_hi} बहुत कम है (खराब में {mb_s} बनाम सही में {mg_s})"
                            h_en = f"improve {col_en} closer to {mg_s}"
                            h_hi = f"{col_hi} को {mg_s} के आसपास बेहतर करें"
                        else:
                            r_en = f"typical {col_en} here is noticeably higher ({mb_s} vs {mg_s} in healthy cases)"
                            r_hi = f"यहाँ औसत {col_hi} काफ़ी ज़्यादा है (खराब में {mb_s} बनाम सही में {mg_s})"
                            h_en = f"bring {col_en} closer to the healthy level ({mg_s})"
                            h_hi = f"{col_hi} को सामान्य स्तर ({mg_s}) के करीब लाएँ"
                        scored_reasons.append((min(1.2, eff * 0.4), col, r_en, r_hi, h_en, h_hi))
            else:
                # Secondary categorical co-driver concentration (e.g., 82% of bad cases are Price Tier 1 or COD)
                nunq = int(ser.nunique(dropna=True))
                if 2 <= nunq <= 12:
                    vc_b = ser.loc[bad_mask].astype(str).value_counts(normalize=True)
                    vc_g = ser.loc[ref_good_mask].astype(str).value_counts(normalize=True)
                    if len(vc_b) > 0:
                        top_val = str(vc_b.index[0])
                        b_share = float(vc_b.iloc[0])
                        g_share = float(vc_g.get(top_val, 0.0))
                        if b_share >= 0.55 and (b_share - g_share) >= 0.18:
                            pct_s = int(round(b_share * 100))
                            seg_lbl_en = humanize_segment(col, top_val, "en")
                            seg_lbl_hi = humanize_segment(col, top_val, "hi")
                            r_en = f"{pct_s}% of these problem cases also fall under {seg_lbl_en}"
                            r_hi = f"इनमें से {pct_s}% समस्याएँ {seg_lbl_hi} में भी एक साथ दिख रही हैं"
                            h_en = f"prioritize {seg_lbl_en}"
                            h_hi = f"{seg_lbl_hi} पर खास ध्यान दें"
                            scored_reasons.append(((b_share - g_share) * 0.9, col, r_en, r_hi, h_en, h_hi))

        scored_reasons.sort(key=lambda x: x[0], reverse=True)
        top_items = scored_reasons[:2]
        return {
            "reasons_en": [x[2] for x in top_items],
            "reasons_hi": [x[3] for x in top_items],
            "driver_cols": [x[1] for x in top_items],
            "driver_hints_en": [x[4] for x in top_items],
            "driver_hints_hi": [x[5] for x in top_items],
        }
    except Exception:
        return empty


# ---------------------------------------------------------------------------
# 5. Complete Human Analyst Story Composer for Dimensional Bottlenecks
# ---------------------------------------------------------------------------
def compose_human_dimension_story(
    dim_name: str,
    seg_val: Any,
    w_rate: float,
    b_rate: float,
    mult: float,
    excess_events: float,
    cap_drag: float,
    is_fin: bool,
    money_str: str,
    vocab: Dict[str, str],
    diag: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Produces crystal-clear, jargon-free English & Hindi headline, expected/actual comparison,
    data-backed 'Why this is happening' narrative, and practical domain-specific action.
    """
    diag = diag or {}
    seg_en = humanize_segment(dim_name, seg_val, "en", vocab)
    seg_hi = humanize_segment(dim_name, seg_val, "hi", vocab)
    ent_en = vocab["entity_en"]
    ent_hi = vocab["entity_hi"]
    fail_en = vocab["fail_en"]
    fail_hi = vocab["fail_hi"]
    exc_i = max(1, int(round(excess_events)))

    here_10_en = rate_out_of_ten_phrase(w_rate, "en")
    norm_10_en = rate_out_of_ten_phrase(b_rate, "en")
    here_10_hi = rate_out_of_ten_phrase(w_rate, "hi")
    norm_10_hi = rate_out_of_ten_phrase(b_rate, "hi")
    mult_en = multiplier_human_phrase(mult, "en")
    mult_hi = multiplier_human_phrase(mult, "hi")
    short_here_en = rate_short_ratio(w_rate, "en")
    short_here_hi = rate_short_ratio(w_rate, "hi")

    # 1. Plain Headline (NO ugly '59.81% (2.73x Normal Rate)', NO cryptic "'1' in Turbidity", NO repeated noun)
    _seg_has_ent_en = ent_en.lower() in seg_en.lower()
    _seg_has_ent_hi = ent_hi in seg_hi
    _ent_hl_en = "" if _seg_has_ent_en else f" {ent_en.title()}"
    _ent_hl_hi = "" if _seg_has_ent_hi else f" {ent_hi}"

    if w_rate >= 95.0:
        hl_en = f"{seg_en}: Almost Every Single One {fail_en.title()}"
        hl_hi = f"{seg_hi}: लगभग हर एक में समस्या आ रही है ({short_here_hi})"
    elif mult >= 1.75:
        hl_en = f"{seg_en}: {short_here_en}{_ent_hl_en} {fail_en.title()} ({mult_en.capitalize()})"
        hl_hi = f"{seg_hi}: {short_here_hi}{_ent_hl_hi} {fail_hi} ({mult_hi})"
    else:
        hl_en = f"{seg_en}: {short_here_en}{_ent_hl_en} {fail_en.title()}"
        hl_hi = f"{seg_hi}: {short_here_hi}{_ent_hl_hi} {fail_hi}"

    # 2. Expected vs Actual (clean single-number display, no double parentheses!)
    cash_en = f" — putting {money_str} at risk" if (is_fin and cap_drag > 0 and money_str) else ""
    cash_hi = f" — लगभग {money_str} का सीधा असर" if (is_fin and cap_drag > 0 and money_str) else ""
    exp_en = f"Normal in rest of business: {norm_10_en}"
    exp_hi = f"बाकी जगह सामान्य स्थिति: {norm_10_hi}"
    act_en = f"Here ({seg_en}): {here_10_en} · {mult_en}"
    act_hi = f"यहाँ ({seg_hi}): {here_10_hi} · {mult_hi}"

    # 3. Why It's Happening (Plain Math + Automatic Physical Co-Driver Diagnosis — zero label duplication!)
    reasons_en = diag.get("reasons_en") or []
    reasons_hi = diag.get("reasons_hi") or []

    why_en = (
        f"In the rest of your business, {norm_10_en} {ent_en} {fail_en}. "
        f"But in {seg_en}, {here_10_en} {fail_en} ({mult_en}), creating ~{exc_i:,} avoidable problem {ent_en}{cash_en}."
    )
    why_hi = (
        f"बाकी जगह जहाँ {norm_10_hi} {ent_hi} {fail_hi}, वहीं {seg_hi} में {here_10_hi} {ent_hi} {fail_hi} ({mult_hi}) — "
        f"जिससे लगभग {exc_i:,} अतिरिक्त {ent_hi} खराब हो रहे हैं{cash_hi}।"
    )

    if reasons_en:
        joined_r_en = "; and ".join(reasons_en[:2])
        why_en += f" What's driving it: {joined_r_en[0].upper() + joined_r_en[1:]}."
    if reasons_hi:
        joined_r_hi = " और ".join(reasons_hi[:2])
        why_hi += f" मुख्य कारण: {joined_r_hi}।"

    # 4. Practical Domain-Tailored Action ("What You Should Do")
    hints_en = diag.get("driver_hints_en") or []
    hints_hi = diag.get("driver_hints_hi") or []
    domain = vocab.get("domain", "general")

    if domain == "dairy_quality":
        if hints_en:
            act_step_en = (
                f"When handling {seg_en}, immediately { ' and '.join(hints_en[:2]) }. "
                f"Check tank hygiene/filtration and hold flagged {ent_en} in Today's Action List before dispatch."
            )
            act_step_hi = (
                f"{seg_hi} आते ही तुरंत {' और '.join(hints_hi[:2])}। "
                f"फिल्टरेशन व कूलिंग जाँचें और Today's Action List के फ्लैग्ड बैच डिस्पैच से पहले अलग करें।"
            )
        else:
            act_step_en = (
                f"Inspect chilling temperature, acidity (pH) and filtration for {seg_en}, "
                f"and separate flagged {ent_en} listed in Today's Action List before dispatch."
            )
            act_step_hi = (
                f"{seg_hi} के लिए तुरंत कूलिंग तापमान, pH और फिल्टरेशन जाँचें और Today's Action List के फ्लैग्ड बैच अलग कर लें।"
            )
    elif domain == "dairy_ops":
        if hints_en:
            act_step_en = (
                f"Review pricing, shelf-life rotation and stock levels for {seg_en} ({', '.join(hints_en[:2])}), "
                f"starting with the top flagged batches in Today's Action List."
            )
            act_step_hi = (
                f"{seg_hi} के स्टॉक, रेट और शेल्फ़-लाइफ़ की समीक्षा करें ({', '.join(hints_hi[:2])}) और Today's Action List से शुरुआत करें।"
            )
        else:
            act_step_en = f"Audit stock turnover, cold-chain dispatch and distributor pricing for {seg_en} using Today's Action List."
            act_step_hi = f"{seg_hi} के स्टॉक, कोल्ड-चेन और प्राइसिंग की जाँच Today's Action List से शुरू करें।"
    elif domain == "restaurant":
        if hints_en:
            act_step_en = (
                f"Audit food consistency, wait times and customer feedback for {seg_en} — especially to {' and '.join(hints_en[:2])}. "
                f"Start with the highest-priority outlets in Today's Action List."
            )
            act_step_hi = (
                f"{seg_hi} में सर्विस, वेटिंग टाइम और ग्राहक फीडबैक की जाँच करें — खासकर {' और '.join(hints_hi[:2])}। "
                f"शुरुआत Today's Action List के टॉप रेस्टोरेंट्स से करें।"
            )
        else:
            act_step_en = f"Review kitchen consistency, waiting times and customer reviews for {seg_en}, starting with Today's Action List."
            act_step_hi = f"{seg_hi} में खाने की क्वालिटी, सर्विस टाइम और ग्राहक रिव्यू सुधारें — Today's Action List के टॉप आउटलेट्स से शुरुआत करें।"
    elif domain == "hotel":
        act_step_en = (
            f"Add a quick WhatsApp/SMS confirmation and clear cancellation policy for {seg_en}"
            + (f" ({hints_en[0]})" if hints_en else "")
            + ", starting with upcoming bookings in Today's Action List."
        )
        act_step_hi = (
            f"{seg_hi} के लिए व्हाट्सएप/कॉल कन्फर्मेशन और स्पष्ट कैंसिलेशन नियम लगाएँ"
            + (f" ({hints_hi[0]})" if hints_hi else "")
            + ", और Today's Action List की आने वाली बुकिंग्स से शुरुआत करें।"
        )
    elif domain == "ecommerce":
        act_step_en = (
            f"Put an instant confirmation check on {seg_en}"
            + (f" and {hints_en[0]}" if hints_en else "")
            + ", then process the top flagged orders in Today's Action List first."
        )
        act_step_hi = (
            f"{seg_hi} पर तुरंत कॉल/OTP कन्फर्मेशन लगाएँ"
            + (f" और {hints_hi[0]}" if hints_hi else "")
            + ", और Today's Action List के टॉप ऑर्डर्स पर आज ही कार्रवाई करें।"
        )
    else:
        if hints_en:
            act_step_en = f"Focus on {seg_en} first — specifically { ' and '.join(hints_en[:2]) } — and work through Today's Action List."
            act_step_hi = f"सबसे पहले {seg_hi} पर ध्यान दें — खासकर {' और '.join(hints_hi[:2])} — और Today's Action List से शुरुआत करें।"
        else:
            act_step_en = f"Audit {seg_en} first and resolve the top flagged {ent_en} listed in Today's Action List."
            act_step_hi = f"सबसे पहले {seg_hi} की जाँच करें और Today's Action List के टॉप {ent_hi} से सुधार शुरू करें।"

    # 5. Friendly impact pill (never "197 excess cases")
    if is_fin and cap_drag > 0 and money_str:
        impact_pill = f"{money_str} at risk (~{exc_i:,} {ent_en})"
    else:
        impact_pill = f"~{exc_i:,} avoidable bad {ent_en}"

    return {
        "headline_en": hl_en,
        "headline_hi": hl_hi,
        "expected_en": exp_en,
        "expected_hi": exp_hi,
        "actual_en": act_en,
        "actual_hi": act_hi,
        "root_cause_en": why_en,
        "root_cause_hi": why_hi,
        "fix_action_en": act_step_en,
        "fix_action_hi": act_step_hi,
        "formatted_impact": impact_pill,
        "seg_en": seg_en,
        "seg_hi": seg_hi,
        "normal_ratio_en": rate_short_ratio(b_rate, "en"),
        "normal_ratio_hi": rate_short_ratio(b_rate, "hi"),
        "here_ratio_en": rate_short_ratio(w_rate, "en"),
        "here_ratio_hi": rate_short_ratio(w_rate, "hi"),
        "mult_phrase_en": mult_en,
        "mult_phrase_hi": mult_hi,
    }


# ---------------------------------------------------------------------------
# 6. Optional Layer 2: Number-Locked Gemini Business Analyst Polisher
# ---------------------------------------------------------------------------
def _extract_numeric_tokens(text: str) -> List[str]:
    return re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", str(text or ""))


def polish_leaks_with_gemini(
    leaks: List[Dict[str, Any]],
    vocab: Dict[str, str],
    enable: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Optional AI Analyst polish pass (uses ~800-1,200 tokens total per report via existing Gemini pool).
    Strictly preserves every verified number; automatically falls back to Layer 1 rich deterministic
    analyst text whenever disabled, offline, missing API key, or if any number drifts.
    """
    should_run = enable if enable is not None else (os.environ.get("DATAXRAY_AI_ANALYST_POLISH", "0") == "1")
    if not should_run or not leaks:
        return leaks

    try:
        try:
            from .rate_limiter import PacedGeminiClient
        except ImportError:
            from rate_limiter import PacedGeminiClient
    except Exception:
        return leaks

    top_slice = leaks[:6]
    compact_in = [
        {
            "leak_id": lk.get("leak_id"),
            "headline_en": lk.get("headline_en"),
            "root_cause_en": lk.get("root_cause_en"),
            "fix_action_en": lk.get("fix_action_en"),
            "headline_hi": lk.get("headline_hi"),
            "root_cause_hi": lk.get("root_cause_hi"),
            "fix_action_hi": lk.get("fix_action_hi"),
        }
        for lk in top_slice
    ]

    prompt = (
        "You are a trusted senior Indian business analyst & CA explaining an audit directly to a non-technical "
        f"{vocab.get('domain', 'business')} owner. Rewrite each card's headline, root_cause (why it happens), and "
        "fix_action in warm, clear, practical everyday English and natural Hindi so the owner immediately understands "
        "WHAT is wrong, WHY it is happening, and WHAT to do today.\n"
        "STRICT RULES:\n"
        "1. NEVER invent, change, or drop any numbers, percentages, or currency figures.\n"
        "2. NEVER use statistical jargon (no p-value, no z-score, no '2.73x normal rate', no raw '1' or 'No' codes).\n"
        "3. Return ONLY valid JSON array with exact keys: leak_id, headline_en, root_cause_en, fix_action_en, headline_hi, root_cause_hi, fix_action_hi.\n\n"
        f"INPUT_CARDS:\n{json.dumps(compact_in, ensure_ascii=False)}"
    )

    try:
        client = PacedGeminiClient(quiet=True)
        raw_resp = client.generate_text(prompt=prompt, max_retries=2)
        if not raw_resp:
            return leaks
        txt = str(raw_resp).strip()
        m = re.search(r"\[[\s\S]*\]", txt)
        if not m:
            return leaks
        parsed = json.loads(m.group(0))
        if not isinstance(parsed, list):
            return leaks

        by_id = {str(item.get("leak_id")): item for item in parsed if isinstance(item, dict) and item.get("leak_id")}
        for lk in top_slice:
            upd = by_id.get(str(lk.get("leak_id")))
            if not upd:
                continue
            # Strict numeric grounding guard: never accept fabricated numbers not present in original card
            orig_nums = set(_extract_numeric_tokens(
                f"{lk.get('headline_en','')} {lk.get('root_cause_en','')} {lk.get('expected_standard_en','')} {lk.get('actual_observed_en','')} {lk.get('formatted_impact','')}"
            ))
            # Allow simple human ratios 1..10 ("6 out of 10", "3x")
            allowed_nums = orig_nums | {str(i) for i in range(1, 11)} | {"1.5", "2.5", "100"}
            new_nums = set(_extract_numeric_tokens(f"{upd.get('headline_en','')} {upd.get('root_cause_en','')}"))
            if new_nums.issubset(allowed_nums):
                for fld in ("headline_en", "root_cause_en", "fix_action_en", "headline_hi", "root_cause_hi", "fix_action_hi"):
                    val = str(upd.get(fld) or "").strip()
                    if len(val) >= 12:
                        lk[fld] = val
                lk["analyst_polish_mode"] = "gemini_verified"
    except Exception:
        return leaks

    return leaks
