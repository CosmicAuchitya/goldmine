"""
=============================================================================
DATAX-RAY V6.0 — CANONICAL BUSINESS CATEGORY REGISTRY & 3-LAYER AUTO-DETECTOR
=============================================================================
Single Source of Truth unifying 02_domain_intelligence/business_ontology.py
across Upload Pre-Flight, Target Resolution, Category Economics/Statistics,
Ask AI, Decision Lab, Boardroom Advisor, and Stage 7 Bespoke Dashboards.

Safety & Non-Regression Guarantees:
1. Strict Enum Whitelist (`validate_category_id`) eliminates prompt/SQL injection.
2. 3-Layer Weighted Classifier with Honest Abstain (< 0.55 -> 'auto') prevents
   false-confidence misclassifications on generic headers (Bill_No, Amt, Status).
3. Soft Mismatch Guard alerts users when chosen category conflicts sharply with
   physical schema signals without ever crashing or fabricating KPIs.
=============================================================================
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _split_identifier_tokens(name: str) -> List[str]:
    """Splits snake_case, kebab-case, spaces, and CamelCase into lowercase tokens."""
    if not name:
        return []
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name).strip())
    s = re.sub(r"[^A-Za-z0-9\u0900-\u097F]+", "_", s).lower()
    return [tok for tok in s.split("_") if tok]


def _normalize_identifier(name: str) -> str:
    return "_".join(_split_identifier_tokens(name))


def load_master_ontology_safe() -> Dict[str, Any]:
    """Safely loads 02_domain_intelligence/business_ontology.py if available."""
    candidates = [
        Path(__file__).resolve().parent.parent / "02_domain_intelligence" / "business_ontology.py",
        Path.cwd() / "02_domain_intelligence" / "business_ontology.py",
    ]
    for path in candidates:
        if path.exists():
            try:
                spec = importlib.util.spec_from_file_location("dx_master_ontology_v6", str(path))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    data = getattr(mod, "MASTER_BUSINESS_ONTOLOGY", {})
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
    return {}


# =============================================================================
# CANONICAL 10-CATEGORY (+ AUTO) REGISTRY
# =============================================================================
BUSINESS_CATEGORY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "auto": {
        "id": "auto",
        "icon": "✨",
        "name_en": "Auto-Detect / General Business",
        "name_hi": "ऑटो-डिटेक्ट / सामान्य बिज़नेस",
        "short_desc_en": "Let DataX-Ray inspect your sheet automatically and run universal verified analytics.",
        "short_desc_hi": "डेटा को ऑटोमैटिक पहचानें और 100% सत्यापित यूनिवर्सल विश्लेषण चलाएँ।",
        "sub_categories": [
            {"id": "general", "name_en": "General Operations", "name_hi": "सामान्य बिज़नेस संचालन"},
        ],
        "ontology_keys": [],
        "strong_signals": [],
        "medium_signals": [],
        "value_signals": [],
        "target_priority_keywords": [],
        "non_monetary_default": False,
        "narrator_domain": "general",
        "stage7_archetype": "nordic_saas_command_center",
        "statistics_pack_en": ["Omnibus Chi-Square & Z-Tests", "Quantile Threshold Cliffs", "2x2 Interaction Matrix"],
        "statistics_pack_hi": ["सेगमेंट रिस्क टेस्ट", "खतरे की सीमा (Red-Line)", "2x2 कॉम्बो विश्लेषण"],
        "economics_pack_en": ["Total Volume & Problem Rate", "Money at Risk", "3-Pathway Excess-Risk Recovery"],
        "economics_pack_hi": ["कुल रिकॉर्ड व समस्या दर", "खतरे में पैसा", "3-स्तरीय बचत योजना"],
        "qa_presets_en": [
            "What are the top 5 highest risk segments and their total exposure?",
            "Compare average exposure between adverse events and normal records",
            "Show summary statistics and total records count",
            "Which factor has the highest problem rate?",
        ],
        "qa_presets_hi": [
            "सबसे ज़्यादा नुकसान किस ग्रुप में हो रहा है और क्यों?",
            "खराब बनाम सही केस की औसत रकम की तुलना दिखाएँ",
            "कुल रिकॉर्ड, समस्या दर और खतरे में पैसे का पूरा सार दिखाएँ",
            "कौन-सा कारण सबसे ज़्यादा समस्या बढ़ा रहा है?",
        ],
        "boardroom_blind_spots_en": [
            "Off-sheet cash transactions, verbal supplier agreements, or unrecorded discounts are outside this file.",
            "External competitor price drops or local market disruptions are not captured inside internal operational rows.",
            "Fixed overhead costs (rent, salaries, interest) are excluded unless explicit cost columns are uploaded.",
        ],
        "boardroom_blind_spots_hi": [
            "शीट के बाहर के नकद लेन-देन, मौखिक सप्लायर समझौते या अनरिकॉर्डेड छूट इस डेटा में नहीं दिखते।",
            "बाज़ार में प्रतियोगी के रेट गिरने या स्थानीय रुकावटों का असर आंतरिक फ़ाइल में दर्ज नहीं होता।",
            "किराया, वेतन और ब्याज जैसे फिक्स्ड खर्च तब तक शामिल नहीं होते जब तक उनका कॉलम अपलोड न हो।",
        ],
    },
    "retail_pos": {
        "id": "retail_pos",
        "icon": "🛒",
        "name_en": "Retail, Kirana & Shop POS",
        "name_hi": "रिटेल, किराना व दुकान (POS)",
        "short_desc_en": "Bills, SKU inventory, stock reorder points, basket combos, and store margins.",
        "short_desc_hi": "दैनिक बिल, स्टॉक री-ऑर्डर, मार्जिन, डेड स्टॉक और कॉम्बो बास्केट विश्लेषण।",
        "sub_categories": [
            {"id": "kirana_supermarket", "name_en": "Kirana / Supermarket", "name_hi": "किराना / सुपरमार्केट"},
            {"id": "pharmacy_medical", "name_en": "Pharmacy / Medical Store", "name_hi": "फार्मेसी / मेडिकल स्टोर"},
            {"id": "apparel_electronics", "name_en": "Apparel / Electronics Store", "name_hi": "कपड़ा / इलेक्ट्रॉनिक्स शोरूम"},
            {"id": "wholesale_pos", "name_en": "Cash & Carry / POS Wholesale", "name_hi": "थोक POS / कैश-एंड-कैरी"},
        ],
        "ontology_keys": ["ecommerce_retail"],
        "strong_signals": [
            "stock_code", "stockcode", "invoice_no", "invoiceno", "pos", "cashier", "barcode",
            "ean", "upc", "branch", "store_id", "store_type", "aisle", "shelf", "mrp",
            "unit_price", "unitprice", "basket", "supermarket", "product_line", "gross_income",
            "cogs", "tax_5", "receipt", "bill_no", "shop"
        ],
        "medium_signals": [
            "quantity", "qty", "sku", "item", "description", "customer_id", "customerid",
            "category", "sub_category", "sales", "profit", "discount", "store", "rating", "member"
        ],
        "value_signals": ["supermarket", "cash", "ewallet", "member", "walk-in", "grocery"],
        "target_priority_keywords": [
            "credit_note", "is_returned", "returned", "refund", "rating", "csat",
            "satisfaction", "stockout", "expiry", "spoilage", "void", "cancel"
        ],
        "non_monetary_default": False,
        "narrator_domain": "ecommerce",
        "stage7_archetype": "editorial_commerce_studio",
        "statistics_pack_en": ["ABC-XYZ Inventory Split", "Weekly Damped Holt Forecast", "Conformal Safety Stock", "Basket Size & Credit-Note Rate"],
        "statistics_pack_hi": ["ABC-XYZ इन्वेंट्री वर्गीकरण", "30-दिन डिमांड फ़ोरकास्ट", "सेफ़्टी स्टॉक री-ऑर्डर", "बास्केट साइज व रिटर्न दर"],
        "economics_pack_en": ["Gross Margin % & Profit", "Inventory/Slow-Mover Capital Lock-up", "Average Basket Value (AOV)", "Return / Credit-Note Drag"],
        "economics_pack_hi": ["ग्रॉस मार्जिन % और मुनाफ़ा", "स्लो-मूविंग/डेड स्टॉक में फँसी पूँजी", "औसत बिल (AOV)", "रिटर्न / क्रेडिट नोट नुकसान"],
        "qa_presets_en": [
            "Which top products drive 80% of our revenue and which items have highest returns?",
            "What is our average bill value (AOV) and total sales vs returns?",
            "Which store branch or customer type has the biggest problem rate?",
            "Show summary statistics and total records count",
        ],
        "qa_presets_hi": [
            "कौन से टॉप प्रोडक्ट्स सबसे ज़्यादा बिक्री और कौन से सबसे ज़्यादा रिटर्न ला रहे हैं?",
            "हमारा औसत बिल साइज (AOV), कुल बिक्री और रिटर्न नुकसान कितना है?",
            "किस ब्रांच या ग्राहक कैटेगरी में सबसे ज़्यादा समस्या है?",
            "कुल रिकॉर्ड, बिक्री और खतरे में पैसे का पूरा सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Physical shelf shrinkage, pilferage, and unreported expired stock cannot be seen unless stock-audit counts are uploaded.",
            "Supplier credit terms (days payable) and walk-in cash sales not punched into POS are outside this ledger.",
            "Local footfall weather/festival impacts require multi-year daily dates to separate seasonality from store performance.",
        ],
        "boardroom_blind_spots_hi": [
            "दुकान में माल चोरी, टूट-फूट या बिना एंट्री के एक्सपायर स्टॉक का पता सिर्फ़ फिज़िकल स्टॉक ऑडिट शीट से चलता है।",
            "सप्लायर उधारी के दिन और बिना बिल की नकद बिक्री इस POS डेटा में दर्ज नहीं होती।",
            "त्योहार या मौसम के कारण फुटफ़ॉल बदलाव को स्थायी गिरावट से अलग करने के लिए कम से कम 2 साल का डेटा चाहिए।",
        ],
    },
    "d2c_ecommerce": {
        "id": "d2c_ecommerce",
        "icon": "📦",
        "name_en": "D2C Brands & E-Commerce",
        "name_hi": "डी2सी ब्रांड व ई-कॉमर्स",
        "short_desc_en": "COD vs Prepaid RTO leaks, courier SLA delays, ad spend ROAS, CM3 margins, and toxic coupons.",
        "short_desc_hi": "COD बनाम प्रीपेड RTO नुकसान, कूरियर देरी, एड खर्च (ROAS), CM3 मार्जिन और कूपन लीकेज।",
        "sub_categories": [
            {"id": "d2c_brand", "name_en": "D2C Brand Website (Shopify/Woo)", "name_hi": "D2C ब्रांड वेबसाइट"},
            {"id": "marketplace_seller", "name_en": "Amazon / Flipkart / Meesho Seller", "name_hi": "मार्केटप्लेस सेलर"},
            {"id": "omnichannel_retail", "name_en": "Omnichannel D2C + Stores", "name_hi": "ओम्नीचैनल D2C + स्टोर"},
        ],
        "ontology_keys": ["d2c_brands", "ecommerce_retail", "two_sided_marketplace"],
        "strong_signals": [
            "rto", "is_rto", "cod", "is_cod", "courier", "courier_partner", "awb", "shipping_provider",
            "fulfillment_warehouse", "fulfillment_partner", "fulfillment_hub", "dispatch_delay",
            "reverse_shipping", "coupon_code", "promo_code", "ad_spend", "roas", "cac",
            "payment_gateway", "payment_mode", "unboxing", "shopify", "delivery_sla"
        ],
        "medium_signals": [
            "order_id", "order_status", "net_billed_amount", "city_tier", "customer_state",
            "shipping_cost", "discount_pct", "acquisition_channel", "transit_days", "delivery_days",
            "return", "cancelled", "cancelled_flag", "sku"
        ],
        "value_signals": ["cod", "cash on delivery", "prepaid", "upi", "delhivery", "bluedart", "rto", "delivered"],
        "target_priority_keywords": [
            "is_rto_or_cancelled", "is_rto", "rto_flag", "rto", "order_status",
            "is_returned", "returned", "delivery_sla_breach", "cancelled", "refund"
        ],
        "non_monetary_default": False,
        "narrator_domain": "ecommerce",
        "stage7_archetype": "editorial_commerce_studio",
        "statistics_pack_en": ["COD vs Prepaid RTO Lift (Z-Test)", "Dispatch Delay Red-Line Cliff", "2x2 Courier x Payment Matrix", "Repeat-Abuser & Cohort Retention"],
        "statistics_pack_hi": ["COD बनाम प्रीपेड RTO अंतर", "डिस्पैच देरी की लाल सीमा", "कूरियर × पेमेंट 2x2 मैट्रिक्स", "रिपीट ग्राहक व सीरियल RTO पहचान"],
        "economics_pack_en": ["CM1 / CM2 / CM3 Unit Economics", "COD RTO & Reverse Shipping Burn", "Promo / Coupon Margin Erosion", "ROAS & Net Contribution"],
        "economics_pack_hi": ["CM1 / CM2 / CM3 यूनिट इकोनॉमिक्स", "COD RTO व रिवर्स शिपिंग घाटा", "कूपन डिस्काउंट मार्जिन क्षरण", "ROAS व शुद्ध योगदान मार्जिन"],
        "qa_presets_en": [
            "Compare COD vs Prepaid return/RTO rates and total money at risk",
            "Which courier partner or warehouse hub has the worst failure rate?",
            "Which discount coupons are eroding profit margin while increasing returns?",
            "What are the top 5 highest risk segments and their total exposure?",
        ],
        "qa_presets_hi": [
            "COD बनाम प्रीपेड ऑर्डर का RTO रेट और फँसी हुई रकम की तुलना दिखाएँ",
            "किस कूरियर पार्टनर या वेयरहाउस में सबसे ज़्यादा नुकसान हो रहा है?",
            "कौन से कूपन कोड मुनाफ़ा घटा रहे हैं और रिटर्न बढ़ा रहे हैं?",
            "सबसे ज़्यादा नुकसान किस राज्य या सेगमेंट में हो रहा है?",
        ],
        "boardroom_blind_spots_en": [
            "Meta/Google ad creative fatigue and upper-funnel CAC changes are hidden unless ad-spend columns are joined.",
            "RTO blocking rules (like disabling COD) can cut top-line order volume by 15–35% in Tier-2/3 cities if not A/B tested.",
            "Courier damaged-in-transit claim recoveries and marketplace settlement penalties may lag order dates by 14–30 days.",
        ],
        "boardroom_blind_spots_hi": [
            "Meta/Google विज्ञापन की थकान (Ad Fatigue) और CAC बदलाव तब तक नहीं दिखते जब तक एड-स्पेंड डेटा जुड़ा न हो।",
            "COD पूरी तरह बंद करने से Tier-2/3 शहरों में कुल ऑर्डर वॉल्यूम 15–35% गिर सकता है — पहले छोटे ट्रायल से जाँचें।",
            "कूरियर डैमेज क्लेम और मार्केटप्लेस सेटलमेंट कटौती ऑर्डर तारीख से 14–30 दिन बाद दिखती है।",
        ],
    },
    "b2b_wholesale": {
        "id": "b2b_wholesale",
        "icon": "🏭",
        "name_en": "B2B Wholesale, Credit & Distribution",
        "name_hi": "बी2बी थोक, उधारी व डिस्ट्रीब्यूशन",
        "short_desc_en": "Accounts receivable aging, DSO payment delays, credit limits, party concentration, and bad-debt risk.",
        "short_desc_hi": "बकाया उधारी (AR Aging), भुगतान देरी (DSO), पार्टी क्रेडिट लिमिट और डूबत खाते का जोखिम।",
        "sub_categories": [
            {"id": "distributor_trader", "name_en": "Wholesale Distributor / Trader", "name_hi": "थोक विक्रेता / डिस्ट्रीब्यूटर"},
            {"id": "corporate_supply", "name_en": "B2B Industrial / Corporate Supply", "name_hi": "कॉर्पोरेट / इंडस्ट्रियल सप्लाई"},
            {"id": "b2b_services", "name_en": "B2B Agency / Contract Services", "name_hi": "बी2बी कॉन्ट्रैक्ट सेवाएँ"},
        ],
        "ontology_keys": ["b2b_enterprise"],
        "strong_signals": [
            "dso", "days_sales_outstanding", "accounts_receivable", "ar_aging", "invoice_status",
            "payment_terms", "net_30", "net_60", "net_90", "due_date", "overdue", "acv", "tcv",
            "contract_id", "deal_stage", "parent_company", "account_manager", "tally",
            "ledger", "voucher", "gstin", "credit_limit", "outstanding_due", "party_name"
        ],
        "medium_signals": [
            "invoice_id", "invoice_amount", "payment_date", "days_to_pay", "client",
            "account_id", "wholesale", "distributor", "dealer", "bad_debt", "writeoff"
        ],
        "value_signals": ["net 30", "net 60", "net 90", "overdue", "unpaid", "partial", "settled"],
        "target_priority_keywords": [
            "invoice_status", "overdue", "unpaid", "bad_debt", "payment_status",
            "is_overdue", "late_payment", "default", "dispute", "writeoff"
        ],
        "non_monetary_default": False,
        "narrator_domain": "banking",
        "stage7_archetype": "swiss_institutional_terminal",
        "statistics_pack_en": ["AR Aging Buckets (0-30/31-60/61-90/90+d)", "Pareto Top-10 Party Concentration", "Payment Delay Threshold Cliff"],
        "statistics_pack_hi": ["उधारी एजिंग बकेट्स (0-30/31-60/90+ दिन)", "टॉप-10 पार्टी निर्भरता (80/20)", "भुगतान देरी की लाल सीमा"],
        "economics_pack_en": ["Days Sales Outstanding (DSO)", "Overdue Capital & Working Capital Interest Burn", "Bad-Debt Exposure Ratio", "Average Contract / Invoice Value"],
        "economics_pack_hi": ["औसत वसूली दिन (DSO)", "बकाया पूँजी व वर्किंग कैपिटल ब्याज घाटा", "डूबत उधारी अनुपात", "औसत इनवॉइस / डील साइज"],
        "qa_presets_en": [
            "Which parties or accounts have the highest overdue unpaid dues?",
            "What is our average days to pay (DSO) and total overdue exposure?",
            "Compare overdue rates across payment terms or account managers",
            "Show summary statistics and total records count",
        ],
        "qa_presets_hi": [
            "किन पार्टियों या खातों पर सबसे ज़्यादा बकाया उधारी फँसी है?",
            "हमारा औसत भुगतान समय (DSO) और कुल ओवरड्यू रकम कितनी है?",
            "पेमेंट टर्म्स या मैनेजर के हिसाब से बकाया देरी की तुलना दिखाएँ",
            "कुल इनवॉइस, ओवरड्यू दर और फँसी रकम का सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "A distributor's off-book liquidity stress or post-dated cheque bounces only surface after bank clearing.",
            "Tightening credit limits too sharply can push loyal bulk buyers to rival distributors with looser Net-60 terms.",
            "Disputed invoices caused by goods-damage or GST mismatch need credit-note resolution before legal escalation.",
        ],
        "boardroom_blind_spots_hi": [
            "किसी डीलर की बाज़ार में नकदी तंगी या चेक बाउंस का पता बैंक क्लियरिंग के बाद ही चलता है।",
            "क्रेडिट लिमिट अचानक सख़्त करने से बड़े थोक ग्राहक प्रतिद्वंद्वी सप्लायर के पास जा सकते हैं।",
            "माल की गुणवत्ता या GST बिल मिलान विवाद वाली उधारी को सख़्ती से पहले क्रेडिट-नोट से सुलझाना ज़रूरी है।",
        ],
    },
    "manufacturing": {
        "id": "manufacturing",
        "icon": "⚙️",
        "name_en": "Manufacturing, Plant & Quality Lab",
        "name_hi": "मैन्युफैक्चरिंग, प्लांट व क्वालिटी लैब",
        "short_desc_en": "Machine uptime (OEE), scrap & defect rates, SPC 3-sigma limits, shift/batch yield, and telemetry.",
        "short_desc_hi": "मशीन अपटाइम (OEE), स्क्रैप व डिफ़ेक्ट दर, SPC 3-सिग्मा सीमा, शिफ़्ट व बैच क्वालिटी।",
        "sub_categories": [
            {"id": "factory_assembly", "name_en": "Factory / Machine Telemetry", "name_hi": "फ़ैक्टरी / मशीन टेलीमेट्री"},
            {"id": "dairy_agro", "name_en": "Dairy / Food / Agro Processing", "name_hi": "डेरी / फ़ूड प्रोसेसिंग"},
            {"id": "pharma_textile", "name_en": "Pharma / Chemical / Textile", "name_hi": "फ़ार्मा / केमिकल / टेक्सटाइल"},
        ],
        "ontology_keys": ["manufacturing_industrial"],
        "strong_signals": [
            "oee", "downtime", "scrap", "work_order", "machine_id", "plant_id", "shift_id",
            "rotational_speed", "torque", "tool_wear", "process_temperature", "air_temperature",
            "machine_failure", "turbidity", "ph", "batch_id", "lot_number", "cycle_time",
            "good_units", "defect", "yield", "cylinders", "horsepower", "mpg", "clarity", "carat"
        ],
        "medium_signals": [
            "temperature", "temprature", "pressure", "vibration", "operator_id", "part_number",
            "quality", "grade", "milk", "fat", "acidity", "spoilage", "failure", "maintenance"
        ],
        "value_signals": ["hdf", "osf", "pwf", "twf", "shift a", "shift b", "scrap", "rework"],
        "target_priority_keywords": [
            "machine_failure", "scrap", "defect", "failure", "fault", "quality",
            "grade", "downtime", "reject", "spoilage", "malfunction"
        ],
        "non_monetary_default": False,
        "narrator_domain": "dairy_quality",
        "stage7_archetype": "industrial_scada_telemetry",
        "statistics_pack_en": ["SPC Control Limits (Mean ± 3σ)", "First-Pass Yield (FPY %)", "Sensor Threshold Cliffs", "Shift / Machine Variance"],
        "statistics_pack_hi": ["SPC कंट्रोल सीमा (Mean ± 3σ)", "फ़र्स्ट-पास यील्ड (FPY %)", "सेंसर थ्रेशोल्ड क्लिफ़", "शिफ़्ट / मशीन तुलना"],
        "economics_pack_en": ["OEE (Availability × Performance × Quality)", "Scrap & Rework Cost Burn", "Downtime Capacity Loss", "Cost per Good Unit"],
        "economics_pack_hi": ["OEE दक्षता सूचकांक", "स्क्रैप व री-वर्क लागत घाटा", "डाउनटाइम उत्पादन नुकसान", "प्रति सही यूनिट लागत"],
        "qa_presets_en": [
            "Which machine, shift, or product type has the highest defect or failure rate?",
            "Which sensor or process parameter crosses the danger threshold most often?",
            "Compare average readings between failed batches and passed batches",
            "Show overall yield, failure rate, and total batches audited",
        ],
        "qa_presets_hi": [
            "किस मशीन, शिफ़्ट या बैच टाइप में सबसे ज़्यादा खराबी/डिफ़ेक्ट हो रहे हैं?",
            "कौन-सा तापमान, स्पीड या प्रोसेस मान खतरे की सीमा पार कर रहा है?",
            "फेल बनाम पास बैच की औसत रीडिंग की तुलना दिखाएँ",
            "कुल बैच, फ़र्स्ट-पास यील्ड और समस्या दर का पूरा सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Raw-material supplier lot quality shifts and ambient humidity/power surges are invisible unless logged per batch.",
            "Preventive maintenance reduces catastrophic breakdowns but incurs scheduled downtime and spare-parts inventory cost.",
            "Operator fatigue across night shifts or uncalibrated sensors can mimic machine wear in telemetry logs.",
        ],
        "boardroom_blind_spots_hi": [
            "कच्चे माल के बैच की क्वालिटी में गिरावट या बिजली वोल्टेज झटके तब तक नहीं दिखते जब तक बैच के साथ दर्ज न हों।",
            "प्रिवेंटिव मेंटेनेंस बड़े ब्रेकडाउन रोकता है, लेकिन इसमें तय शटडाउन और स्पेयर पार्ट्स लागत लगती है।",
            "नाइट शिफ़्ट थकान या सेंसर कैलिब्रेशन गड़बड़ी भी मशीन खराबी जैसी दिख सकती है।",
        ],
    },
    "saas_subscription": {
        "id": "saas_subscription",
        "icon": "🔁",
        "name_en": "SaaS, Subscriptions & Telecom",
        "name_hi": "सब्सक्रिप्शन, SaaS व टेलीकॉम",
        "short_desc_en": "Monthly/annual churn curves, MRR/ARR retention, contract upgrades, API usage, and tenure cliffs.",
        "short_desc_hi": "ग्राहक चर्न (Churn), MRR/ARR बचत, मासिक बनाम वार्षिक प्लान और शुरुआती 90-दिन रिटेंशन।",
        "sub_categories": [
            {"id": "b2b_saas", "name_en": "B2B / B2C SaaS", "name_hi": "SaaS सब्सक्रिप्शन"},
            {"id": "api_b2d", "name_en": "API / Developer Platform (B2D)", "name_hi": "API / डेवलपर प्लेटफ़ॉर्म"},
            {"id": "telecom_broadband", "name_en": "Telecom / Broadband / OTT", "name_hi": "टेलीकॉम / ब्रॉडबैंड / OTT"},
        ],
        "ontology_keys": ["b2d_developer_tools"],
        "strong_signals": [
            "churn", "mrr", "arr", "tenure", "monthlycharges", "monthly_charges", "totalcharges",
            "contract", "tipocontrato", "mesescomocliente", "plan_tier", "subscription",
            "renewal", "api_key", "latency_ms", "compute_units", "tokens_prompt", "seat_count",
            "internetservice", "techsupport", "paperlessbilling"
        ],
        "medium_signals": [
            "cancel", "active_users", "plan", "billing_cycle", "arpu", "ltv", "cac", "usage", "status"
        ],
        "value_signals": ["month-to-month", "one year", "two year", "fiber optic", "churned", "subscribed"],
        "target_priority_keywords": [
            "churn", "exited", "cancelled", "subscription_status", "is_churned",
            "renewal_failed", "downgrade", "error", "http_status_code"
        ],
        "non_monetary_default": False,
        "narrator_domain": "telecom",
        "stage7_archetype": "nordic_saas_command_center",
        "statistics_pack_en": ["Tenure-Bucket Churn Survival Curve", "Contract-Type Relative Risk", "Early 90-Day Onboarding Cliff"],
        "statistics_pack_hi": ["टेन्योर-बकेट चर्न सर्वाइवल कर्व", "कॉन्ट्रैक्ट प्लान रिस्क तुलना", "शुरुआती 90-दिन चर्न क्लिफ़"],
        "economics_pack_en": ["MRR & Annualized ARR at Risk", "Gross Revenue Retention (GRR %)", "ARPU (Churned vs Retained)", "Annual-Switch Recovery Value"],
        "economics_pack_hi": ["खतरे में मासिक MRR व वार्षिक ARR", "ग्रॉस रेवेन्यू रिटेंशन (GRR %)", "औसत ग्राहक कमाई (ARPU)", "वार्षिक प्लान शिफ़्ट बचत"],
        "qa_presets_en": [
            "Which contract type or plan tier has the highest churn rate and MRR at risk?",
            "How does churn change across customer tenure buckets (new vs long-term)?",
            "Compare monthly charges (ARPU) of churned customers vs retained customers",
            "Show overall churn rate, active accounts, and monthly revenue at risk",
        ],
        "qa_presets_hi": [
            "किस प्लान या कॉन्ट्रैक्ट में सबसे ज़्यादा ग्राहक छोड़ रहे हैं और कितना MRR खतरे में है?",
            "नए बनाम पुराने ग्राहकों (Tenure) में चर्न रेट कैसे बदलता है?",
            "छोड़ने वाले बनाम टिके रहने वाले ग्राहकों के मासिक बिल (ARPU) की तुलना दिखाएँ",
            "कुल ग्राहक, चर्न दर और मासिक कमाई का पूरा सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Product engagement drop-offs, support ticket sentiment, and competitor feature launches are invisible in billing-only logs.",
            "Aggressive annual-plan discounts reduce immediate cash flow per seat even as they lower month-to-month churn.",
            "Involuntary churn (expired cards / auto-debit failures) behaves completely differently from voluntary cancellations.",
        ],
        "boardroom_blind_spots_hi": [
            "प्रोडक्ट इस्तेमाल में गिरावट, सपोर्ट टिकट की नाराज़गी या प्रतियोगी के नए फ़ीचर्स सिर्फ़ बिलिंग डेटा में नहीं दिखते।",
            "वार्षिक प्लान पर भारी छूट देने से चर्न घटता है लेकिन प्रति-सीट तुरंत नकदी (ARPU) कम हो सकती है।",
            "कार्ड एक्सपायर/ऑटो-डेबिट फेल होने वाला चर्न और ग्राहक की मर्ज़ी से कैंसलेशन — दोनों का इलाज अलग होता है।",
        ],
    },
    "hospitality_fnb": {
        "id": "hospitality_fnb",
        "icon": "🏨",
        "name_en": "Hotels, Restaurants & Cloud Kitchens",
        "name_hi": "होटल, रेस्टोरेंट व क्लाउड किचन",
        "short_desc_en": "Booking cancellations, advance lead-time cliffs, ADR/RevPAR, food cost %, and aggregator fees.",
        "short_desc_hi": "बुकिंग कैंसलेशन, एडवांस लीड-टाइम सीमा, ADR/RevPAR, फ़ूड कॉस्ट % और एग्रीगेटर कमीशन।",
        "sub_categories": [
            {"id": "hotel_resort", "name_en": "Hotel / Resort / Homestay", "name_hi": "होटल / रिसॉर्ट / होमस्टे"},
            {"id": "restaurant_qsr", "name_en": "Dine-in Restaurant / Cafe / QSR", "name_hi": "रेस्टोरेंट / कैफ़े / QSR"},
            {"id": "cloud_kitchen", "name_en": "Cloud Kitchen / Food Delivery", "name_hi": "क्लाउड किचन / फ़ूड डिलीवरी"},
        ],
        "ontology_keys": ["food_beverage_qsr", "two_sided_marketplace"],
        "strong_signals": [
            "hotel", "adr", "lead_time", "assigned_room_type", "reserved_room_type", "deposit_type",
            "stays_in_weekend", "stays_in_week", "is_canceled", "reservation_status", "market_segment",
            "kitchen_order_ticket", "kot", "food_waste", "prep_time", "cuisine", "cuisines",
            "aggregator_commission", "raw_ingredient_cost", "menu_price", "table_booking", "tip", "smoker"
        ],
        "medium_signals": [
            "restaurant", "dining", "guest", "room", "booking", "check_in", "occupancy",
            "day", "time", "size", "total_bill", "rating", "online_delivery"
        ],
        "value_signals": ["city hotel", "resort hotel", "online ta", "non refund", "dinner", "lunch", "zomato", "swiggy"],
        "target_priority_keywords": [
            "is_canceled", "cancelled", "cancellation", "no_show", "rating",
            "customer_rating", "complaint", "food_waste", "smoker"
        ],
        "non_monetary_default": False,
        "narrator_domain": "hotel",
        "stage7_archetype": "nordic_saas_command_center",
        "statistics_pack_en": ["Advance Lead-Time Cancellation Cliff", "Channel / Room / Day-of-Week Surge", "Guest Segment Risk Matrix"],
        "statistics_pack_hi": ["एडवांस बुकिंग लीड-टाइम क्लिफ़", "चैनल / रूम / दिन के हिसाब से उछाल", "ग्राहक सेगमेंट रिस्क मैट्रिक्स"],
        "economics_pack_en": ["ADR & Realized RevPAR Proxy", "Cancellation / No-Show Revenue Drag", "Food Cost % & Aggregator Cut", "Direct vs OTA Channel Margin"],
        "economics_pack_hi": ["औसत रूम रेट (ADR) व कमाई", "कैंसलेशन / नो-शो राजस्व नुकसान", "फ़ूड कॉस्ट % व एग्रीगेटर कमीशन", "डायरेक्ट बनाम OTA मार्जिन"],
        "qa_presets_en": [
            "Which booking channel, hotel, or room type has the highest cancellation loss?",
            "At what advance lead-time do cancellations spike sharply?",
            "Compare average bill or ADR between cancelled and completed bookings",
            "Show overall cancellation rate and total revenue at risk",
        ],
        "qa_presets_hi": [
            "किस बुकिंग चैनल, रूम टाइप या दिन में सबसे ज़्यादा कैंसलेशन नुकसान हो रहा है?",
            "कितने दिन पहले की बुकिंग (Lead Time) पर कैंसलेशन अचानक बढ़ता है?",
            "कैंसल बनाम पूरी हुई बुकिंग के औसत रेट (ADR/Bill) की तुलना दिखाएँ",
            "कुल बुकिंग, कैंसलेशन दर और खतरे में रकम का सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Requiring non-refundable deposits cuts cancellations but can lower initial OTA search ranking and conversion.",
            "Ingredient price inflation, staff overtime, and walk-in turn-aways during weekend peaks are off-sheet.",
            "Guest review sentiment text and local event/holiday surges require external calendar context.",
        ],
        "boardroom_blind_spots_hi": [
            "नॉन-रिफंडेबल एडवांस अनिवार्य करने से कैंसलेशन घटता है, लेकिन नई बुकिंग कन्वर्जन और OTA रैंकिंग कम हो सकती है।",
            "कच्ची सामग्री की महंगाई, स्टाफ़ ओवरटाइम और वीकेंड वेटिंग से लौटे ग्राहक इस शीट में दर्ज नहीं होते।",
            "स्थानीय त्योहार/कॉन्फ़्रेंस या ग्राहक रिव्यू की भावना अलग से देखनी पड़ती है।",
        ],
    },
    "fintech_lending": {
        "id": "fintech_lending",
        "icon": "🏦",
        "name_en": "Finance, Lending, Banking & Insurance",
        "name_hi": "फ़ाइनेंस, लोन, बैंकिंग व बीमा",
        "short_desc_en": "Loan defaults (NPA/DPD), Expected Credit Loss (ECL), interest/DTI cliffs, and insurance claim frequency.",
        "short_desc_hi": "लोन डिफ़ॉल्ट (NPA/DPD), संभावित क्रेडिट लॉस (ECL), ब्याज/आय सीमा और बीमा क्लेम जोखिम।",
        "sub_categories": [
            {"id": "nbfc_lending", "name_en": "NBFC / Digital Lending", "name_hi": "NBFC / डिजिटल लेंडिंग"},
            {"id": "banking_cards", "name_en": "Retail Banking / Credit Cards", "name_hi": "बैंकिंग / क्रेडिट कार्ड"},
            {"id": "insurance_claims", "name_en": "Motor / Health / Life Insurance", "name_hi": "बीमा व क्लेम अंडरराइटिंग"},
        ],
        "ontology_keys": ["fintech_lending"],
        "strong_signals": [
            "loan", "loan_amount", "cibil", "credit_score", "credit_limit", "interest_rate",
            "dti", "loan_to_income", "dpd", "npa", "emi", "borrower", "default", "not_fully_paid",
            "charged_off", "delinquent", "policy_id", "claim", "claims", "is_claim", "premium",
            "underwriting", "collateral", "exited", "creditscore", "estimatedsalary"
        ],
        "medium_signals": [
            "balance", "tenure", "income", "salary", "employed", "geography", "numofproducts",
            "hascrcard", "age", "segment", "charges", "region"
        ],
        "value_signals": ["charged off", "fully paid", "default", "npa", "delinquent", "claim"],
        "target_priority_keywords": [
            "default", "loan_default", "is_default", "not_fully_paid", "npa",
            "loan_status", "is_claim", "claim_status", "exited", "churn", "fraud"
        ],
        "non_monetary_default": False,
        "narrator_domain": "banking",
        "stage7_archetype": "swiss_institutional_terminal",
        "statistics_pack_en": ["Default / Claim Decile Lift", "Interest Rate & DTI Risk Cliff", "DPD / Cohort Stratification"],
        "statistics_pack_hi": ["डिफ़ॉल्ट / क्लेम डेसाइल लिफ़्ट", "ब्याज दर व आय-अनुपात क्लिफ़", "सेगमेंट व रिस्क बकेट जाँच"],
        "economics_pack_en": ["Expected Credit Loss (ECL Proxy)", "Defaulted Principal / Claim Exposure", "Portfolio Default / Loss Ratio %", "Average Ticket (Default vs Performing)"],
        "economics_pack_hi": ["संभावित क्रेडिट लॉस (ECL)", "डिफ़ॉल्ट / क्लेम में फँसी पूँजी", "पोर्टफ़ोलियो डिफ़ॉल्ट / लॉस रेशियो", "औसत लोन/पॉलिसी साइज तुलना"],
        "qa_presets_en": [
            "Which borrower or policy segment has the highest default/claim exposure?",
            "Compare average loan/exposure between defaulted accounts and performing accounts",
            "At what interest rate, age, or credit score does default risk spike?",
            "Show total portfolio volume, default rate, and capital at risk",
        ],
        "qa_presets_hi": [
            "किस लोन या पॉलिसी सेगमेंट में सबसे ज़्यादा डिफ़ॉल्ट/क्लेम जोखिम है?",
            "डिफ़ॉल्ट बनाम सही खातों की औसत लोन रकम की तुलना दिखाएँ",
            "किस ब्याज दर, उम्र या स्कोर के बाद डिफ़ॉल्ट अचानक बढ़ता है?",
            "कुल पोर्टफ़ोलियो, डिफ़ॉल्ट दर और खतरे में पूँजी का सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Tightening underwriting cutoffs reduces default loss but also rejects profitable marginal borrowers and slows disbursement growth.",
            "Collateral liquidation haircuts, legal recovery costs (SARFAESI), and macro interest-rate cycles are not in origination rows.",
            "Fair-lending & regulatory compliance rules strictly prohibit underwriting decisions based on protected demographics.",
        ],
        "boardroom_blind_spots_hi": [
            "अंडरराइटिंग नियम ज़्यादा सख़्त करने से डिफ़ॉल्ट घटता है लेकिन कई सही ग्राहकों के लोन भी रिजेक्ट होकर ग्रोथ रुकती है।",
            "गिरवी संपत्ति बेचने की कानूनी लागत और बाज़ार ब्याज-दर चक्र सिर्फ़ लोन ओरिजिनेशन शीट में नहीं दिखते।",
            "नियामक (RBI/Fair-Lending) नियमों के तहत लिंग या संरक्षित वर्ग के आधार पर लोन निर्णय प्रतिबंधित हैं।",
        ],
    },
    "logistics_fleet": {
        "id": "logistics_fleet",
        "icon": "🚚",
        "name_en": "Logistics, Freight & Aviation",
        "name_hi": "लॉजिस्टिक्स, फ़्लीट व एविएशन",
        "short_desc_en": "OTIF on-time delivery, hub/carrier delay cascades, route bottlenecks, and demurrage/SLA penalties.",
        "short_desc_hi": "समय पर डिलीवरी (OTIF), हब/कूरियर देरी, रूट बॉटलनेक और SLA/डेमरेज पेनल्टी।",
        "sub_categories": [
            {"id": "courier_3pl", "name_en": "Courier / 3PL / Last-Mile", "name_hi": "कूरियर / 3PL / लास्ट-माइल"},
            {"id": "freight_trucking", "name_en": "Freight / Supply Chain / Fleet", "name_hi": "फ़्रेट / ट्रकिंग / सप्लाई चेन"},
            {"id": "aviation_transit", "name_en": "Airlines / Urban Mobility / Taxi", "name_hi": "एयरलाइन / टैक्सी / ट्रांज़िट"},
        ],
        "ontology_keys": ["logistics_freight"],
        "strong_signals": [
            "consignment", "origin_hub", "destination_hub", "freight", "demurrage", "pod_status",
            "carrier", "flight", "dep_delay", "arr_delay", "airport", "tailnum", "pickup_borough",
            "dropoff_borough", "distance", "fare", "trip", "route", "fleet", "fuel_surcharge",
            "risk_classification", "chargeable_weight", "otif", "transit_delay"
        ],
        "medium_signals": [
            "shipment", "warehouse", "delay", "hour", "origin", "dest", "delivery", "vehicle", "driver"
        ],
        "value_signals": ["delayed", "on time", "in transit", "disrupted", "cash", "credit card"],
        "target_priority_keywords": [
            "dep_delay", "delay", "is_delayed", "sla_breach", "disruption",
            "risk_classification", "pod_status", "late", "damage"
        ],
        "non_monetary_default": False,
        "narrator_domain": "ecommerce",
        "stage7_archetype": "nordic_saas_command_center",
        "statistics_pack_en": ["OTIF On-Time Delivery %", "Carrier / Hub Delay Cascade", "Departure / Dispatch Hour Cliff"],
        "statistics_pack_hi": ["समय पर डिलीवरी (OTIF %)", "कूरियर / हब देरी श्रृंखला", "पीक-आवर देरी की सीमा"],
        "economics_pack_en": ["Delayed Shipment / Freight Exposure", "SLA Penalty & Demurrage Burn", "Distance / Weight Efficiency", "Route Concentration Risk"],
        "economics_pack_hi": ["देरी वाले शिपमेंट में फँसी रकम", "SLA पेनल्टी व डेमरेज खर्च", "दूरी / वज़न दक्षता", "रूट निर्भरता जोखिम"],
        "qa_presets_en": [
            "Which carrier, hub, or route has the highest delay or disruption rate?",
            "Which departure hours or transit windows trigger cascading delays?",
            "Compare average fare, freight, or distance between delayed and on-time trips",
            "Show overall OTIF reliability rate and total shipments audited",
        ],
        "qa_presets_hi": [
            "किस कूरियर, हब या रूट में सबसे ज़्यादा देरी या रुकावट हो रही है?",
            "किस समय या घंटे के बाद देरी अचानक बढ़ जाती है?",
            "देरी वाले बनाम समय पर पहुँचे शिपमेंट की तुलना दिखाएँ",
            "कुल शिपमेंट, OTIF समयबद्धता दर और कुल नुकसान का सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Weather events, highway blockages, and port customs hold-ups require external weather/traffic feeds.",
            "Switching carriers for faster SLA often increases per-kg freight cost — validate margin impact before shifting 100% volume.",
            "Empty-mile deadhead return trips and fuel surcharge volatility must be tracked alongside on-time delivery.",
        ],
        "boardroom_blind_spots_hi": [
            "खराब मौसम, हाइवे जाम या कस्टम रोक का असर सिर्फ़ आंतरिक शिपमेंट शीट से अलग नहीं किया जा सकता।",
            "तेज़ कूरियर चुनने पर प्रति-किलो भाड़ा बढ़ सकता है — पूरा वॉल्यूम शिफ़्ट करने से पहले लागत तुलना करें।",
            "खाली लौटते ट्रक (Empty Miles) और डीज़ल कीमतों में उतार-चढ़ाव को OTIF के साथ देखना ज़रूरी है।",
        ],
    },
    "healthcare_clinical": {
        "id": "healthcare_clinical",
        "icon": "🏥",
        "name_en": "Healthcare, Hospitals & Clinical",
        "name_hi": "हेल्थकेयर, अस्पताल व क्लीनिक",
        "short_desc_en": "Patient risk stratification, clinical biomarker cliffs, zero fake currency, and hospital claim/ALOS audits.",
        "short_desc_hi": "मरीज़ रिस्क स्क्रीनिंग, बायोमार्कर सीमा, शून्य नकली मुद्रा और क्लेम/बेड ऑडिट।",
        "sub_categories": [
            {"id": "hospital_clinic", "name_en": "Hospital / Outpatient Clinic", "name_hi": "अस्पताल / क्लीनिक"},
            {"id": "diagnostics_lab", "name_en": "Diagnostics / Pathology Lab", "name_hi": "डायग्नोस्टिक्स / पैथोलॉजी लैब"},
            {"id": "clinical_trials", "name_en": "Clinical Cohort / Research", "name_hi": "क्लीनिकल रिसर्च / बायोमार्कर"},
        ],
        "ontology_keys": ["healthcare_operations"],
        "strong_signals": [
            "patient", "ejection_fraction", "serum_creatinine", "serum_sodium", "platelets",
            "creatinine_phosphokinase", "glucose", "insulin", "bloodpressure", "blood_pressure",
            "bmi", "pregnancies", "diabetes", "death_event", "readmission", "length_of_stay",
            "alos", "encounter_id", "doctor_id", "diagnosis", "bed_category", "claim_rejection",
            "anaemia", "high_blood_pressure", "stroke", "mortality", "hospital"
        ],
        "medium_signals": [
            "outcome", "age", "sex", "smoking", "department", "admission", "discharge", "clinical", "lab"
        ],
        "value_signals": ["readmitted", "admitted", "denied", "icu", "inpatient", "outpatient"],
        "target_priority_keywords": [
            "death_event", "mortality", "readmission_30d", "readmitted", "outcome",
            "diagnosis", "claim_status", "complication", "abnormal", "stroke"
        ],
        "non_monetary_default": True,
        "narrator_domain": "clinical",
        "stage7_archetype": "clinical_diagnostic_clarity",
        "statistics_pack_en": ["Clinical Risk Stratification (Wilson 95% CI)", "Biomarker Red-Line Thresholds", "Triage Recall vs False-Alert Boundary"],
        "statistics_pack_hi": ["क्लीनिकल रिस्क वर्गीकरण (95% CI)", "बायोमार्कर खतरे की सीमा", "अर्ली स्क्रीनिंग सटीकता"],
        "economics_pack_en": ["Zero Fabricated Currency on Clinical Telemetry", "Claim Denial Rate % (when billing present)", "Average Length of Stay (ALOS)"],
        "economics_pack_hi": ["क्लीनिकल डेटा पर शून्य नकली पैसा", "बीमा क्लेम रिजेक्शन % (बिलिंग होने पर)", "औसत भर्ती दिन (ALOS)"],
        "qa_presets_en": [
            "Which clinical cohorts or biomarker bands have the highest adverse risk?",
            "Compare average biomarker readings between high-risk and stable patient cases",
            "Which screening threshold captures the most high-risk cases cleanly?",
            "Show overall patient count, adverse event rate, and key drivers",
        ],
        "qa_presets_hi": [
            "किन क्लीनिकल ग्रुप या बायोमार्कर स्तर में सबसे ज़्यादा रिस्क दिख रहा है?",
            "हाई-रिस्क बनाम स्थिर मरीज़ों की औसत रीडिंग की तुलना दिखाएँ",
            "किस स्क्रीनिंग सीमा से सबसे ज़्यादा हाई-रिस्क केस समय पर पकड़े जा सकते हैं?",
            "कुल मरीज़ केस, रिस्क दर और मुख्य कारणों का सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Statistical patterns in retrospective clinical tables are decision-support only — never a substitute for physician diagnosis.",
            "Comorbidities, medication adherence, and post-discharge home-care quality are often absent from structured lab tables.",
            "Small subgroup sample sizes can produce wide confidence intervals; always inspect sample counts before protocol changes.",
        ],
        "boardroom_blind_spots_hi": [
            "डेटा के पैटर्न केवल क्लीनिकल निर्णय-सहायता हैं — ये डॉक्टर के प्रत्यक्ष निदान का विकल्प कभी नहीं हो सकते।",
            "अन्य सह-रोग, दवा के नियमित सेवन और डिस्चार्ज के बाद देखभाल की स्थिति अक्सर लैब शीट में दर्ज नहीं होती।",
            "छोटे सैंपल वाले ग्रुप में रिस्क रेंज चौड़ी हो सकती है; प्रोटोकॉल बदलने से पहले कुल केस संख्या ज़रूर देखें।",
        ],
    },
    "real_estate_edtech": {
        "id": "real_estate_edtech",
        "icon": "🏢",
        "name_en": "Real Estate, PropTech & EdTech",
        "name_hi": "रियल एस्टेट, प्रॉपर्टी व एडटेक",
        "short_desc_en": "Property valuation corridors, occupancy & rent yield (PropTech) or student completion & refund risk (EdTech).",
        "short_desc_hi": "प्रॉपर्टी वैल्यूएशन, ऑक्यूपेंसी व किराया यील्ड या एडटेक कोर्स कंप्लीशन व रिफ़ंड जोखिम।",
        "sub_categories": [
            {"id": "proptech_leasing", "name_en": "Real Estate / Leasing / PropTech", "name_hi": "रियल एस्टेट / लीज़िंग"},
            {"id": "edtech_coaching", "name_en": "EdTech / Coaching / Courses", "name_hi": "एडटेक / कोचिंग / कोर्स"},
        ],
        "ontology_keys": ["real_estate_proptech", "edtech_upskilling"],
        "strong_signals": [
            "ocean_proximity", "median_house_value", "median_income", "housing_median_age",
            "square_feet", "sqft", "rent_per_sqft", "occupancy_status", "lease_start", "property_name",
            "broker_commission", "enrollment_id", "student_id", "course_id", "course_fee",
            "learning_progress", "dropout", "placement_status", "scholarship", "completion_flag"
        ],
        "medium_signals": [
            "rooms", "bedrooms", "households", "population", "tenant", "listing_price",
            "course", "batch", "attendance", "installment", "fee"
        ],
        "value_signals": ["inland", "near ocean", "vacant", "occupied", "dropped", "completed", "placed"],
        "target_priority_keywords": [
            "occupancy_status", "vacancy", "dropout", "course_completion_flag",
            "refund", "median_house_value", "placement_status", "default"
        ],
        "non_monetary_default": False,
        "narrator_domain": "general",
        "stage7_archetype": "nordic_saas_command_center",
        "statistics_pack_en": ["Location / Cohort Valuation Cliffs", "Income / Engagement Gradient", "Dropout or Vacancy Concentration"],
        "statistics_pack_hi": ["लोकेशन / बैच वैल्यूएशन क्लिफ़", "आय या प्रोग्रेस थ्रेशोल्ड", "ड्रॉपआउट या वेकेंसी केंद्रीकरण"],
        "economics_pack_en": ["Valuation / Rent Exposure & Occupancy %", "Net Fee Realization & Scholarship/Refund Drag", "Top vs Bottom Zone Spread"],
        "economics_pack_hi": ["प्रॉपर्टी वैल्यू / ऑक्यूपेंसी %", "शुद्ध फ़ीस वसूली व रिफ़ंड/स्कॉलरशिप घाटा", "ज़ोन/कोर्स प्रीमियम अंतर"],
        "qa_presets_en": [
            "Which location zone, property type, or course has the highest risk exposure?",
            "Compare average value or fee across top and bottom performing groups",
            "What income, age, or progress threshold marks the sharpest drop-off?",
            "Show total portfolio value, risk rate, and summary statistics",
        ],
        "qa_presets_hi": [
            "किस लोकेशन ज़ोन, प्रॉपर्टी या कोर्स में सबसे ज़्यादा जोखिम या गिरावट है?",
            "सबसे मज़बूत बनाम कमज़ोर ग्रुप की औसत वैल्यू/फ़ीस की तुलना दिखाएँ",
            "किस आय, उम्र या प्रोग्रेस स्तर पर अचानक बदलाव आता है?",
            "कुल रिकॉर्ड, पोर्टफ़ोलियो वैल्यू और जोखिम दर का सार दिखाएँ",
        ],
        "boardroom_blind_spots_en": [
            "Upcoming zoning/metro projects (PropTech) or job-market hiring slowdowns (EdTech) lie outside historical rows.",
            "Hidden brokerage/maintenance CapEx or mentor/TA payout costs must be included to see true net yield.",
            "Trial-window refund spikes often stem from sales over-promising rather than product/curriculum quality alone.",
        ],
        "boardroom_blind_spots_hi": [
            "आने वाले मेट्रो/ज़ोनिंग प्रोजेक्ट (प्रॉपर्टी) या जॉब-मार्केट मंदी (एडटेक) का असर ऐतिहासिक शीट में नहीं होता।",
            "ब्रोकरेज/मेंटेनेंस खर्च या मेंटर/TA भुगतान जोड़े बिना असली शुद्ध मुनाफ़ा अधूरा रहता है।",
            "7–14 दिन के रिफ़ंड उछाल का कारण अक्सर सेल्स में ज़्यादा वादे करना होता है, सिर्फ़ कोर्स क्वालिटी नहीं।",
        ],
    },
}

VALID_CATEGORY_IDS = frozenset(BUSINESS_CATEGORY_REGISTRY.keys())


def validate_category_id(raw_cat: Optional[str]) -> str:
    """Strict canonical enum whitelist sanitizer (blocks SQL/prompt injection)."""
    if not raw_cat:
        return "auto"
    cleaned = re.sub(r"[^a-z0-9_]", "", str(raw_cat).strip().lower())
    if cleaned in VALID_CATEGORY_IDS:
        return cleaned
    # Safe alias resolution for friendly caller shortcuts
    aliases = {
        "general": "auto",
        "retail": "retail_pos",
        "pos": "retail_pos",
        "shop": "retail_pos",
        "kirana": "retail_pos",
        "d2c": "d2c_ecommerce",
        "ecommerce": "d2c_ecommerce",
        "ecom": "d2c_ecommerce",
        "b2b": "b2b_wholesale",
        "wholesale": "b2b_wholesale",
        "mfg": "manufacturing",
        "factory": "manufacturing",
        "dairy": "manufacturing",
        "saas": "saas_subscription",
        "telecom": "saas_subscription",
        "subscription": "saas_subscription",
        "b2d": "saas_subscription",
        "hotel": "hospitality_fnb",
        "restaurant": "hospitality_fnb",
        "fnb": "hospitality_fnb",
        "hospitality": "hospitality_fnb",
        "finance": "fintech_lending",
        "fintech": "fintech_lending",
        "banking": "fintech_lending",
        "lending": "fintech_lending",
        "insurance": "fintech_lending",
        "logistics": "logistics_fleet",
        "fleet": "logistics_fleet",
        "airline": "logistics_fleet",
        "aviation": "logistics_fleet",
        "healthcare": "healthcare_clinical",
        "health": "healthcare_clinical",
        "clinical": "healthcare_clinical",
        "hospital": "healthcare_clinical",
        "realestate": "real_estate_edtech",
        "real_estate": "real_estate_edtech",
        "proptech": "real_estate_edtech",
        "edtech": "real_estate_edtech",
    }
    return aliases.get(cleaned, "auto")


def validate_sub_category_id(cat_id: str, raw_sub: Optional[str]) -> Optional[str]:
    """Validates optional sub-category against the chosen category's allowed sub-categories."""
    norm_cat = validate_category_id(cat_id)
    if not raw_sub:
        return None
    cleaned = re.sub(r"[^a-z0-9_]", "", str(raw_sub).strip().lower())
    valid_subs = {s["id"] for s in BUSINESS_CATEGORY_REGISTRY[norm_cat].get("sub_categories", [])}
    return cleaned if cleaned in valid_subs else None


def get_category_spec(cat_id: Optional[str]) -> Dict[str, Any]:
    """Returns canonical category spec dictionary safely."""
    return BUSINESS_CATEGORY_REGISTRY[validate_category_id(cat_id)]


def get_category_catalog_for_ui() -> List[Dict[str, Any]]:
    """Returns lightweight, UI-ready catalog for GET /api/v1/categories."""
    catalog: List[Dict[str, Any]] = []
    for cid, spec in BUSINESS_CATEGORY_REGISTRY.items():
        catalog.append({
            "id": cid,
            "icon": spec["icon"],
            "name_en": spec["name_en"],
            "name_hi": spec["name_hi"],
            "short_desc_en": spec["short_desc_en"],
            "short_desc_hi": spec["short_desc_hi"],
            "sub_categories": spec["sub_categories"],
            "statistics_pack_en": spec["statistics_pack_en"],
            "statistics_pack_hi": spec["statistics_pack_hi"],
            "economics_pack_en": spec["economics_pack_en"],
            "economics_pack_hi": spec["economics_pack_hi"],
        })
    return catalog


def detect_business_category(
    columns: List[str],
    sample_df: Optional[pd.DataFrame] = None,
    filename: Optional[str] = None,
    user_selected_category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    3-Layer Weighted Business Category Auto-Detector with Honest Abstain Rule:
    - Layer A: Strong (3.0) & medium (1.2) normalized column & token matches.
    - Layer B: Structural value-shape signals from sample_df (e.g., negative Quantity
      credit notes, COD/Prepaid tokens, City/Resort hotel strings).
    - Layer C: Honest Abstain (< 0.55 confidence or weak ambiguous tie -> 'auto').
    - Soft Mismatch Guard when user_selected_category conflicts sharply with data.
    """
    norm_cols = [_normalize_identifier(c) for c in (columns or [])]
    col_tokens = set()
    for c in (columns or []):
        col_tokens.update(_split_identifier_tokens(c))
    fname_norm = _normalize_identifier(filename or "")

    # Sample string values (bounded & fast: first 80 rows of object columns only)
    sample_val_blob = ""
    has_neg_qty_pos = False
    if sample_df is not None and not sample_df.empty:
        try:
            head_df = sample_df.head(80)
            str_parts: List[str] = []
            for c in head_df.columns:
                if pd.api.types.is_object_dtype(head_df[c]) or str(head_df[c].dtype) == "category":
                    vals = head_df[c].dropna().astype(str).unique()[:15]
                    str_parts.extend(v.lower() for v in vals)
            sample_val_blob = " | ".join(str_parts)

            # Structural POS signature: Quantity with negative credit notes + price/invoice column
            qty_cols = [c for c in head_df.columns if _normalize_identifier(c) in ("quantity", "qty", "units_sold")]
            price_cols = [c for c in head_df.columns if any(k in _normalize_identifier(c) for k in ("unit_price", "unitprice", "rate", "mrp", "selling_price"))]
            if qty_cols and price_cols:
                q_num = pd.to_numeric(sample_df[qty_cols[0]], errors="coerce").dropna()
                if len(q_num) >= 10 and (q_num < 0).any() and (q_num > 0).any():
                    has_neg_qty_pos = True
        except Exception:
            pass

    scores: Dict[str, float] = {}
    matched_map: Dict[str, List[str]] = {}

    for cid, spec in BUSINESS_CATEGORY_REGISTRY.items():
        if cid == "auto":
            continue
        score = 0.0
        hits: List[str] = []

        for sig in spec.get("strong_signals", []):
            sig_n = _normalize_identifier(sig)
            if not sig_n:
                continue
            hit = False
            for nc in norm_cols:
                if sig_n == nc or (len(sig_n) >= 4 and sig_n in nc):
                    hit = True
                    break
            if not hit and "_" not in sig_n and len(sig_n) >= 3 and sig_n in col_tokens:
                hit = True
            if hit:
                score += 3.0
                hits.append(sig)
            elif fname_norm and len(sig_n) >= 4 and sig_n in fname_norm:
                score += 1.25
                hits.append(f"file:{sig}")

        for sig in spec.get("medium_signals", []):
            sig_n = _normalize_identifier(sig)
            if not sig_n:
                continue
            hit = False
            for nc in norm_cols:
                if sig_n == nc or (len(sig_n) >= 4 and sig_n in nc):
                    hit = True
                    break
            if not hit and "_" not in sig_n and len(sig_n) >= 3 and sig_n in col_tokens:
                hit = True
            if hit:
                score += 1.15
                hits.append(sig)

        if sample_val_blob:
            for vsig in spec.get("value_signals", []):
                if vsig.lower() in sample_val_blob:
                    score += 1.6
                    hits.append(f"val:{vsig}")

        # Structural POS boost (UCI retail / Tally POS register with negative credit-note Quantity)
        if cid == "retail_pos" and has_neg_qty_pos:
            score += 4.5
            hits.append("shape:pos_credit_notes")

        scores[cid] = round(score, 2)
        matched_map[cid] = hits[:6]

    ranked: List[Tuple[str, float]] = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_cat, top_score = ranked[0] if ranked else ("auto", 0.0)
    sec_cat, sec_score = ranked[1] if len(ranked) > 1 else ("auto", 0.0)

    # Calibrated confidence [0.0, 0.99]
    if top_score < 2.2:
        confidence = round(min(0.45, top_score / 6.0), 2)
        detected_cat = "auto"
        is_confident = False
    else:
        margin_ratio = (top_score - sec_score) / max(top_score, 1.0)
        raw_conf = min(0.98, 0.45 + min(0.35, top_score / 18.0) + min(0.18, margin_ratio * 0.25))
        confidence = round(raw_conf, 2)
        # Honest Abstain if low confidence or tight weak tie
        if confidence < 0.55 or (top_score < 3.5 and (top_score - sec_score) < 0.6):
            detected_cat = "auto"
            is_confident = False
        else:
            detected_cat = top_cat
            is_confident = True

    # Best sub-category guess
    sub_cat_guess: Optional[str] = None
    if detected_cat != "auto":
        subs = BUSINESS_CATEGORY_REGISTRY[detected_cat].get("sub_categories", [])
        if subs:
            sub_cat_guess = subs[0]["id"]
            if detected_cat == "hospitality_fnb" and any(k in col_tokens for k in ("kot", "cuisine", "cuisines", "restaurant", "menu", "smoker", "tip")):
                sub_cat_guess = "restaurant_qsr"
            elif detected_cat == "real_estate_edtech" and any(k in col_tokens for k in ("student", "course", "enrollment", "dropout")):
                sub_cat_guess = "edtech_coaching"
            elif detected_cat == "fintech_lending" and any(k in col_tokens for k in ("claim", "claims", "policy", "premium")):
                sub_cat_guess = "insurance_claims"
            elif detected_cat == "fintech_lending" and any(k in col_tokens for k in ("exited", "creditscore", "geography")):
                sub_cat_guess = "banking_cards"
            elif detected_cat == "logistics_fleet" and any(k in col_tokens for k in ("flight", "airport", "tailnum", "fare", "borough")):
                sub_cat_guess = "aviation_transit"
            elif detected_cat == "manufacturing" and any(k in col_tokens for k in ("milk", "turbidity", "temprature", "dairy")):
                sub_cat_guess = "dairy_agro"

    # Soft Mismatch Guard when user explicitly selected a category that strongly conflicts with schema
    user_norm = validate_category_id(user_selected_category) if user_selected_category else "auto"
    mismatch_warning_en: Optional[str] = None
    mismatch_warning_hi: Optional[str] = None
    if user_norm != "auto" and is_confident and detected_cat != "auto" and user_norm != detected_cat:
        # Allow close sibling pairs (retail_pos <-> d2c_ecommerce, b2b_wholesale <-> retail_pos) without noisy alarm
        close_siblings = {
            frozenset({"retail_pos", "d2c_ecommerce"}),
            frozenset({"retail_pos", "b2b_wholesale"}),
            frozenset({"d2c_ecommerce", "logistics_fleet"}),
        }
        user_score = scores.get(user_norm, 0.0)
        if frozenset({user_norm, detected_cat}) not in close_siblings and confidence >= 0.72 and user_score < top_score * 0.45:
            det_spec = BUSINESS_CATEGORY_REGISTRY[detected_cat]
            usr_spec = BUSINESS_CATEGORY_REGISTRY[user_norm]
            sig_preview = ", ".join(matched_map.get(detected_cat, [])[:3]) or "schema columns"
            mismatch_warning_en = (
                f"Your selected category is '{usr_spec['name_en']}', but your file signals ({sig_preview}) "
                f"strongly resemble '{det_spec['name_en']}' ({int(confidence * 100)}% match). "
                f"Safety Gate active: missing category KPIs will never be fabricated."
            )
            mismatch_warning_hi = (
                f"आपने '{usr_spec['name_hi']}' चुना है, लेकिन आपकी फ़ाइल के कॉलम ({sig_preview}) "
                f"'{det_spec['name_hi']}' ({int(confidence * 100)}% मिलान) से ज़्यादा मेल खाते हैं। "
                f"सेफ़्टी गेट सक्रिय है: जो कॉलम डेटा में नहीं हैं, उनके नकली आँकड़े कभी नहीं बनाए जाएँगे।"
            )

    det_spec = BUSINESS_CATEGORY_REGISTRY[detected_cat]
    return {
        "detected_category": detected_cat,
        "detected_sub_category": sub_cat_guess,
        "category_name_en": det_spec["name_en"],
        "category_name_hi": det_spec["name_hi"],
        "icon": det_spec["icon"],
        "confidence": confidence,
        "confidence_pct": int(round(confidence * 100)),
        "is_confident": is_confident,
        "matched_signals": matched_map.get(detected_cat, []),
        "runner_up_category": sec_cat if sec_score >= 2.0 else None,
        "runner_up_score": sec_score if sec_score >= 2.0 else 0.0,
        "mismatch_warning_en": mismatch_warning_en,
        "mismatch_warning_hi": mismatch_warning_hi,
        "top_candidates": [
            {
                "id": c,
                "name_en": BUSINESS_CATEGORY_REGISTRY[c]["name_en"],
                "name_hi": BUSINESS_CATEGORY_REGISTRY[c]["name_hi"],
                "icon": BUSINESS_CATEGORY_REGISTRY[c]["icon"],
                "score": sc,
            }
            for c, sc in ranked[:3]
            if sc >= 1.5
        ],
    }
