"""
=============================================================================
MASTER BUSINESS ONTOLOGY (वैश्विक व्यापार ज्ञानकोश) - VERSION 2.0 (PERFECT)
=============================================================================
यह विश्व के 12 सबसे बड़े बिजनेस मॉडल्स (B2B, B2C, B2D, D2C, Marketplaces, 
Manufacturing, FinTech, Healthcare, Logistics, Real Estate, F&B, EdTech) का
गहरा तकनीकी और वित्तीय ज्ञानकोश है।

प्रत्येक मॉडल में शामिल है:
- व्यापार का मॉडल और सब-टाइप्स (Sub-types)
- स्टैंडर्ड डेटा स्कीमा कॉलम्स (Standard Columns)
- बाउंडेड (सीमित) बनाम अनबाउंडेड (असीमित) कॉलम्स की परिभाषा
- मुख्य वित्तीय एवं तकनीकी KPIs
- गणितीय संतुलन सूत्र (Mathematical Assertions)
- लीकेज और नुकसान के गुप्त बिंदु (Hidden Margin Leaks)
- मिसलेनियस खर्चे (Domain-Specific Miscellaneous Expenses)
"""

MASTER_BUSINESS_ONTOLOGY = {
    # =========================================================================
    # 1. B2D: BUSINESS-TO-DEVELOPER (API-First, DevTools, Cloud Infra, AI APIs)
    # =========================================================================
    "b2d_developer_tools": {
        "domain_code": "B2D",
        "domain_name": "Business-to-Developer (B2D / API-First & DevTools)",
        "industry_examples": ["Stripe", "Twilio", "OpenAI API", "Cloudflare", "Supabase", "Datadog", "AWS SDKs"],
        "description": "सॉफ्टवेयर डेवलपर्स और इंजीनियरिंग टीमों को API, SDK, क्लाउड इंफ्रास्ट्रक्चर या टूल्स बेचना। यहाँ बिलिंग यूसेज (Usage-based / Consumption) या टोकन्स/रिक्वेस्ट्स पर आधारित होती है।",
        "typical_columns": [
            "request_id", "developer_id", "project_id", "api_key_id",
            "endpoint", "http_status_code", "latency_ms", "tokens_prompt",
            "tokens_completion", "data_transfer_bytes", "compute_units",
            "plan_tier", "rate_limit_hits", "billable_amount", "country_code", "timestamp"
        ],
        "bounded_columns": ["endpoint", "http_status_code", "plan_tier", "country_code"],
        "unbounded_columns": ["request_id", "developer_id", "project_id", "api_key_id", "timestamp"],
        "numeric_metrics": ["latency_ms", "tokens_prompt", "tokens_completion", "data_transfer_bytes", "compute_units", "rate_limit_hits", "billable_amount"],
        "key_metrics_kpis": [
            "Time to First Hello World (TTFHW) - पहली सफल API कॉल में लगा समय",
            "Monthly Active Developers (MAD)",
            "P95 & P99 Latency (विलंबता / सिस्टम स्पीड)",
            "API Error Rate (5xx सर्वर एरर प्रतिशत)",
            "Net Dollar Retention (NDR %) - मौजूदा डेवलपर्स द्वारा उपयोग का विस्तार",
            "Token / Compute Unit Margin"
        ],
        "mathematical_assertions": [
            "billable_amount == (compute_units * unit_rate) + (data_transfer_bytes * egress_rate)",
            "total_tokens == tokens_prompt + tokens_completion"
        ],
        "profit_drivers": [
            "Product-Led Growth (PLG) - डेवलपर्स का खुद इस्तेमाल शुरू करना",
            "Viral Adoption - कंपनी के अंदर एक डेवलपर से पूरी टीम तक पहुंचना",
            "Enterprise Tier SLAs और कमिटेड एनुअल कॉन्ट्रैक्ट्स"
        ],
        "loss_and_leakage_risks": [
            "Free Tier Abuse / Bot Traffic (फ्री कोटा चूसने वाले बॉट्स)",
            "Unmetered API Usage (मीटरींग सिस्टम में बग जिससे बिल न बने)",
            "High Egress Latency जिससे डेवलपर्स स्विच कर जाएं",
            "Credit Card Chargebacks on Unmonitored Spikes (अनचाहे ओवरएज पर विवाद)"
        ],
        "miscellaneous_expenses": [
            "Cloud Bandwidth Egress Costs (AWS/GCP डेटा बाहर भेजने का भारी चार्ज)",
            "Underlying AI Model / Compute Depreciation (GPU सर्वर किराया)",
            "Global CDN & Edge Hosting Fees",
            "Developer Sandbox & Test Environment Burn"
        ]
    },

    # =========================================================================
    # 2. B2B ENTERPRISE: CONTRACT-BASED WHOLESALE & CORPORATE SAAS
    # =========================================================================
    "b2b_enterprise": {
        "domain_code": "B2B_ENT",
        "domain_name": "B2B Enterprise (Corporate Contracts, Invoicing & Wholesale)",
        "industry_examples": ["Salesforce", "SAP", "Cisco", "Siemens", "Corporate IT Services", "Bulk Industrial Wholesale"],
        "description": "एक कंपनी का दूसरी कंपनी को भारी मात्रा में सामान या दीर्घकालिक (Long-term) सॉफ्टवेयर कॉन्ट्रैक्ट्स बेचना। यहाँ सेल्स साइकल 3 से 12 महीने लंबा होता है और इनवॉइस Net 30/60/90 क्रेडिट टर्म्स पर चलते हैं।",
        "typical_columns": [
            "invoice_id", "contract_id", "account_id", "parent_company",
            "deal_stage", "contract_start_date", "contract_end_date", "acv", "tcv",
            "payment_terms", "invoice_status", "days_sales_outstanding_dso",
            "account_manager", "industry_vertical", "payment_date"
        ],
        "bounded_columns": ["deal_stage", "payment_terms", "invoice_status", "industry_vertical"],
        "unbounded_columns": ["invoice_id", "contract_id", "account_id", "parent_company", "account_manager"],
        "numeric_metrics": ["acv", "tcv", "days_sales_outstanding_dso"],
        "key_metrics_kpis": [
            "Annual Contract Value (ACV) & Total Contract Value (TCV)",
            "Days Sales Outstanding (DSO) - पैसे वसूलने में लगने वाले औसत दिन",
            "Pipeline Velocity (लीड से क्लोज होने की गति)",
            "Customer Acquisition Cost (CAC) Payback Time",
            "Gross Revenue Retention (GRR) & Net Revenue Retention (NRR)"
        ],
        "mathematical_assertions": [
            "TCV == ACV * contract_years",
            "DSO == (Accounts_Receivable / Total_Credit_Sales) * Number_of_Days"
        ],
        "profit_drivers": [
            "Multi-Year Locked In Enterprise Contracts (3-5 साल के अनुबंध)",
            "Account Expansion (Cross-sell & Up-sell to sub-departments)",
            "Low Customer Count with Ultra High Ticket Size (₹50 लाख - ₹5 करोड़ डील)"
        ],
        "loss_and_leakage_risks": [
            "Bad Debts (कस्टमर कंपनी का दिवालिया हो जाना या बिल न भरना)",
            "SLA Penalty Deductions (सर्विस डाउनटाइम पर भारी कटौती)",
            "Scope Creep in Custom Integration (बिना एक्स्ट्रा बिल किए अतिरिक्त काम करना)"
        ],
        "miscellaneous_expenses": [
            "Legal & Contract Compliance Review Costs",
            "Executive Travel & Client Entertainment Expenses",
            "Dedicated Account Management & Solutions Engineering Salaries",
            "Late Payment Working Capital Interest"
        ]
    },

    # =========================================================================
    # 3. D2C: DIRECT-TO-CONSUMER BRANDS
    # =========================================================================
    "d2c_brands": {
        "domain_code": "D2C",
        "domain_name": "Direct-to-Consumer (D2C Brands & Consumer Products)",
        "industry_examples": ["boAt", "Mamaearth", "Warby Parker", "Gymshark", "Dollar Shave Club"],
        "description": "बिना किसी बिचौलिए (Retailer/Wholesaler) के अपनी वेबसाइट या ऐप से सीधे ग्राहकों को माल बेचना। यहाँ डिजिटल मार्केटिंग विज्ञापन (Meta/Google Ads), पैकेजिंग और डिलीवरी की गति सबसे अहम है।",
        "typical_columns": [
            "order_id", "customer_phone_hash", "sku", "product_category",
            "order_value", "discount_code", "ad_channel_attribution",
            "shipping_provider", "payment_mode", "delivery_status",
            "is_cod", "rto_flag", "unboxing_experience_rating", "dispatch_time_hours"
        ],
        "bounded_columns": ["product_category", "ad_channel_attribution", "shipping_provider", "payment_mode", "delivery_status", "is_cod", "rto_flag"],
        "unbounded_columns": ["order_id", "customer_phone_hash", "sku"],
        "numeric_metrics": ["order_value", "dispatch_time_hours", "unboxing_experience_rating"],
        "key_metrics_kpis": [
            "Return on Ad Spend (ROAS = Revenue / Ad_Spend)",
            "Customer Acquisition Cost (CAC)",
            "RTO Rate (% of Cash-on-Delivery orders returned)",
            "Repeat Purchase Rate at 30/60/90 days",
            "Gross Margin After Shipping & Marketing (Contribution Margin 3)"
        ],
        "mathematical_assertions": [
            "Net_Profit_Per_Order == order_value - (COGS + ad_cac + shipping_cost + payment_gateway_fee + packaging_cost)",
            "Contribution_Margin == (Revenue - Variable_Costs) / Revenue"
        ],
        "profit_drivers": [
            "High Customer Lifetime Value (LTV) through Repeat Orders",
            "Prepaid Orders (Card/UPI) over COD",
            "Brand Loyalty eliminating reliance on Meta/Google Ads"
        ],
        "loss_and_leakage_risks": [
            "COD Rejection at Doorstep (कस्टमर ने डिलीवरी बॉय को मना कर दिया)",
            "Ad Fatigue (विज्ञापन की लागत बढ़ना और कन्वर्जन गिरना)",
            "Dead Inventory (ना बिकने वाला पुराना माल गोदाम में सड़ना)"
        ],
        "miscellaneous_expenses": [
            "Unboxing & Premium Packaging Box / Branded Tape Costs",
            "COD Collection Convenience Surcharge from Couriers (₹30-₹50 प्रति पार्सल)",
            "Influencer Gifting & Affiliate Commission Cuts",
            "Payment Gateway Settlement Retention (Holdbacks)"
        ]
    },

    # =========================================================================
    # 4. TWO-SIDED MARKETPLACE & PLATFORM ECONOMY
    # =========================================================================
    "two_sided_marketplace": {
        "domain_code": "MARKETPLACE",
        "domain_name": "Two-Sided Marketplace & Platform Economy",
        "industry_examples": ["Uber", "Airbnb", "Amazon Marketplace", "Upwork", "Zomato", "Swiggy"],
        "description": "सप्लाई (Sellers/Drivers/Hosts) और डिमांड (Buyers/Riders/Guests) को जोड़ने वाला प्लेटफॉर्म। प्लेटफॉर्म खुद सामान नहीं बनाता, बल्कि प्रत्येक ट्रांजैक्शन पर कमीशन (Take Rate) काटता है।",
        "typical_columns": [
            "booking_id", "buyer_id", "seller_id", "listing_id",
            "gross_booking_value_gbv", "platform_take_rate_pct", "commission_earned",
            "seller_payout", "buyer_service_fee", "surge_multiplier",
            "booking_status", "cancellation_initiator", "city", "rating"
        ],
        "bounded_columns": ["booking_status", "cancellation_initiator", "city"],
        "unbounded_columns": ["booking_id", "buyer_id", "seller_id", "listing_id"],
        "numeric_metrics": ["gross_booking_value_gbv", "platform_take_rate_pct", "commission_earned", "seller_payout", "buyer_service_fee", "surge_multiplier", "rating"],
        "key_metrics_kpis": [
            "Gross Merchandise / Booking Value (GMV / GBV)",
            "Platform Take Rate (%) - प्लेटफॉर्म का कमीशन हिस्सा",
            "Liquidity Ratio (सप्लाई और डिमांड मैच होने की दर)",
            "Supply Churn (ड्राइवर्स या सेलर्स का प्लेटफॉर्म छोड़ना)",
            "Net Revenue = GMV * Take_Rate"
        ],
        "mathematical_assertions": [
            "gross_booking_value_gbv == seller_payout + commission_earned",
            "commission_earned == (gross_booking_value_gbv * platform_take_rate_pct / 100) + buyer_service_fee"
        ],
        "profit_drivers": [
            "Network Effects (जितने ज्यादा सेलर्स, उतने ज्यादा बायर्स)",
            "Zero Inventory Risk (इन्वेंट्री का कोई रिस्क नहीं)",
            "Ancillary Advertising (सेलर्स से स्पॉन्सर्ड लिस्टिंग के पैसे लेना)"
        ],
        "loss_and_leakage_risks": [
            "Disintermediation (बायर और सेलर का प्लेटफॉर्म के बाहर जाकर डील कर लेना)",
            "Subsidies & Promo Code Burning (मार्केट शेयर जीतने के लिए कैश जलाना)",
            "Customer Support Escalations and Chargebacks"
        ],
        "miscellaneous_expenses": [
            "Partner Payout Banking / Automated Clearing House (ACH) Fees",
            "Insurance Covers for Drivers/Hosts during Trips",
            "Customer Trust & Safety Verification (Background Checks) Costs",
            "Local Municipal Regulatory / Transport Compliance Levies"
        ]
    },

    # =========================================================================
    # 5. MANUFACTURING & INDUSTRIAL PROCESS (Discrete & Process)
    # =========================================================================
    "manufacturing_industrial": {
        "domain_code": "MFG",
        "domain_name": "Manufacturing & Industrial Operations",
        "industry_examples": ["Automobile Assembly", "Textile Mills", "Electronics Fabrication", "Pharma Chemical Plants", "Steel Rolling"],
        "description": "कच्चे माल (Raw Material) को मशीनरी और लेबर द्वारा तैयार माल (Finished Goods) में बदलना। यहाँ मुख्य फोकस मशीन अपटाइम, वेस्टेज और क्वालिटी पर होता है।",
        "typical_columns": [
            "work_order_id", "plant_id", "machine_id", "part_number",
            "shift_id", "planned_production_time_min", "actual_run_time_min",
            "downtime_minutes", "downtime_reason_code", "total_units_produced",
            "good_units_count", "scrap_units_count", "standard_cycle_time_sec",
            "scrap_cost", "operator_id"
        ],
        "bounded_columns": ["plant_id", "shift_id", "downtime_reason_code"],
        "unbounded_columns": ["work_order_id", "machine_id", "part_number", "operator_id"],
        "numeric_metrics": ["planned_production_time_min", "actual_run_time_min", "downtime_minutes", "total_units_produced", "good_units_count", "scrap_units_count", "standard_cycle_time_sec", "scrap_cost"],
        "key_metrics_kpis": [
            "Overall Equipment Effectiveness (OEE = Availability * Performance * Quality)",
            "Scrap Rate (% of produced parts defective)",
            "First Pass Yield (FPY %)",
            "Mean Time Between Failures (MTBF) & Mean Time to Repair (MTTR)",
            "Cost Per Unit Produced"
        ],
        "mathematical_assertions": [
            "total_units_produced == good_units_count + scrap_units_count",
            "actual_run_time_min == planned_production_time_min - downtime_minutes",
            "Scrap_Rate == scrap_units_count / total_units_produced",
            "OEE == (actual_run_time / planned_time) * (total_units / ideal_output) * (good_units / total_units)"
        ],
        "profit_drivers": [
            "High Capacity Utilization (कारखाना 24x7 बिना रुके चलना)",
            "Zero Defect Manufacturing (कम से कम कबाड़ / स्क्रैप)",
            "Bulk Raw Material Procurement Discounts"
        ],
        "loss_and_leakage_risks": [
            "Unplanned Machine Breakdown (मशीन अचानक खराब होना, पूरी लाइन रुकना)",
            "Raw Material Price Volatility (कच्चे माल का महंगा होना)",
            "Batch Contamination / Recall (पूरी लॉट खराब निकलना)"
        ],
        "miscellaneous_expenses": [
            "Machine Tool Wear & Tear / Consumables Replacement",
            "Hazardous Scrap Disposal & Environmental Compliance Levies",
            "Electricity Peak Demand Surcharges (औद्योगिक बिजली का बिल)",
            "Preventive Lubrication & Maintenance Spare Parts"
        ]
    },

    # =========================================================================
    # 6. HEALTHCARE, HOSPITALS & CLINICAL OPERATIONS
    # =========================================================================
    "healthcare_operations": {
        "domain_code": "HEALTH",
        "domain_name": "Healthcare, Hospitals & Clinical Diagnostics",
        "industry_examples": ["Apollo Hospitals", "Mayo Clinic", "Diagnostic Lab Chains", "Fortis", "Specialty Clinics"],
        "description": "मरीजों का इलाज, डायग्नोस्टिक टेस्ट और इनपेशेंट/आउटपेशेंट सेवाएं। यहाँ जीवन-मरण का सवाल होता है और इन्शुरन्स क्लेम रिजेक्शन से भारी रेवेन्यू नुकसान होता है।",
        "typical_columns": [
            "encounter_id", "patient_id", "doctor_id", "department",
            "admission_date", "discharge_date", "length_of_stay_days",
            "billing_type", "total_billed_amount", "insurance_provider",
            "claim_status", "claim_rejection_reason", "bed_category", "readmission_30d"
        ],
        "bounded_columns": ["department", "billing_type", "insurance_provider", "claim_status", "claim_rejection_reason", "bed_category", "readmission_30d"],
        "unbounded_columns": ["encounter_id", "patient_id", "doctor_id"],
        "numeric_metrics": ["length_of_stay_days", "total_billed_amount"],
        "key_metrics_kpis": [
            "Bed Occupancy Rate (BOR %)",
            "Average Length of Stay (ALOS - अस्पताल में ठहरने के औसत दिन)",
            "Insurance Claim Denial / Rejection Rate (%)",
            "Average Revenue Per Occupied Bed (ARPOB)",
            "30-Day Patient Readmission Rate"
        ],
        "mathematical_assertions": [
            "Bed_Occupancy_Rate == (Occupied_Beds / Total_Available_Beds) * 100",
            "Realized_Revenue == total_billed_amount - (denied_claims + uncollectible_debt)"
        ],
        "profit_drivers": [
            "High Operating Theater (OT) Surgical Utilization",
            "Advanced Diagnostics (MRI, CT, Specialized Pathology Labs)",
            "Preventive Health Checkup Packages"
        ],
        "loss_and_leakage_risks": [
            "TPA Insurance Claim Denials (बीमा कंपनियों द्वारा क्लेम खारिज करना)",
            "Medical Consumable Expiry (महंगी दवाइयों की एक्सपायरी)",
            "Doctor Idle Time and Empty Specialized Beds"
        ],
        "miscellaneous_expenses": [
            "Bio-Medical Waste Management & Incineration Costs",
            "Medical Malpractice & Liability Legal Insurance",
            "Sterilization, Linen & Hygiene Maintenance Services",
            "Emergency Ambulance Fleet Fuel & Standby Upkeep"
        ]
    },

    # =========================================================================
    # 7. FINTECH, LENDING & BANKING (NBFCs & Microfinance)
    # =========================================================================
    "fintech_lending": {
        "domain_code": "FINTECH_LEND",
        "domain_name": "FinTech, Lending & Credit Operations (NBFCs)",
        "industry_examples": ["Bajaj Finance", "LendingClub", "Cred", "Paytm Loans", "Klarna (BNPL)"],
        "description": "कस्टमर्स या बिजनेसेस को लोन बांटना और ईएमआई (EMI) वसूलना। यहाँ सबसे बड़ा खतरा डिफॉल्ट (NPA - Non-Performing Assets) का होता है।",
        "typical_columns": [
            "loan_account_number", "borrower_id", "cibil_score", "loan_amount_sanctioned",
            "interest_rate_annual", "tenure_months", "disbursed_date",
            "monthly_emi", "emi_due_date", "payment_status", "dpd",
            "npa_classification", "collateral_value", "recovery_agent_code"
        ],
        "bounded_columns": ["payment_status", "npa_classification"],
        "unbounded_columns": ["loan_account_number", "borrower_id", "recovery_agent_code"],
        "numeric_metrics": ["cibil_score", "loan_amount_sanctioned", "interest_rate_annual", "tenure_months", "monthly_emi", "dpd", "collateral_value"],
        "key_metrics_kpis": [
            "Net Interest Margin (NIM = Lending_Rate - Borrowing_Cost)",
            "Gross & Net NPA % (Non-Performing Assets - 90+ DPD डिफॉल्ट)",
            "Days Past Due (DPD) Bucket Distribution (30 DPD, 60 DPD, 90 DPD)",
            "Collection Efficiency Ratio (%)",
            "Cost of Funds (CoF %)"
        ],
        "mathematical_assertions": [
            "NIM == ((Interest_Income - Interest_Expense) / Total_Earning_Assets) * 100",
            "Gross_NPA_Pct == (NPA_Loans_Amount / Total_Loans_Disbursed) * 100"
        ],
        "profit_drivers": [
            "Healthy Net Interest Spread (कम ब्याज पर पैसा उठाना, ज्यादा पर बांटना)",
            "Processing Fees & Pre-payment Penalty Fees (Upfront Cash)",
            "Repeat Borrowers with High Credit Discipline"
        ],
        "loss_and_leakage_risks": [
            "Willful Defaults (लोन लेकर भाग जाना)",
            "Collateral Value Depreciation (गिरवी रखी संपत्ति की कीमत गिरना)",
            "Over-leveraged Borrowers taking multiple loans"
        ],
        "miscellaneous_expenses": [
            "Credit Bureau Pull Charges (Experian/CIBIL API प्रति इंक्वायरी खर्च)",
            "Third-Party Loan Recovery Agencies Commission (10% - 25% कटौतियां)",
            "Legal SARFAESI Notices and Court Filing Fees",
            "e-NACH / Auto-Debit Mandate Bounce Penalties"
        ]
    },

    # =========================================================================
    # 8. FOOD & BEVERAGE: RESTAURANTS, QSR & CLOUD KITCHENS
    # =========================================================================
    "food_beverage_qsr": {
        "domain_code": "FNB",
        "domain_name": "Food & Beverage (Restaurants, QSR & Cloud Kitchens)",
        "industry_examples": ["Domino's", "Rebel Foods (Faasos)", "Starbucks", "Local Dine-In Restaurants"],
        "description": "खाना बनाकर ग्राहकों को परोसना या ऑनलाइन डिलीवर करना। यहाँ भोजन की शेल्फ लाइफ बहुत कम होती है और एग्रीगेटर कमीशन बहुत ज्यादा होता है।",
        "typical_columns": [
            "kitchen_order_ticket_kot", "order_channel", "item_code", "cuisine_category",
            "raw_ingredient_cost", "menu_price", "quantity_sold", "food_waste_kg",
            "prep_time_minutes", "rider_pickup_time_minutes", "aggregator_commission_pct",
            "customer_rating", "order_cancellation_reason"
        ],
        "bounded_columns": ["order_channel", "cuisine_category", "order_cancellation_reason"],
        "unbounded_columns": ["kitchen_order_ticket_kot", "item_code"],
        "numeric_metrics": ["raw_ingredient_cost", "menu_price", "quantity_sold", "food_waste_kg", "prep_time_minutes", "rider_pickup_time_minutes", "aggregator_commission_pct", "customer_rating"],
        "key_metrics_kpis": [
            "Food Cost Percentage (आदर्श: 28% - 32% of Selling Price)",
            "Table Turnover Rate / Kitchen Dispatch Velocity",
            "Aggregator Commission Burden (25% - 30% cut by Zomato/Swiggy)",
            "Raw Material Spoilage / Wastage Rate (%)",
            "Average Revenue Per Cover (ARPC - प्रति डाइनिंग सीट औसत बिल)"
        ],
        "mathematical_assertions": [
            "Food_Cost_Pct == (raw_ingredient_cost / menu_price) * 100",
            "Net_Earning_Online_Order == menu_price - (raw_ingredient_cost + (menu_price * aggregator_commission_pct / 100) + packaging_cost)"
        ],
        "profit_drivers": [
            "High-Margin Beverage / Liquor Sales (शराब और पेय पदार्थों पर 80% मार्जिन)",
            "Direct Walk-in Orders (0% कमीशन)",
            "Catering & Corporate Bulk Orders"
        ],
        "loss_and_leakage_risks": [
            "Perishable Ingredient Spoilage (सब्जियां, दूध, मीट का खराब होना)",
            "Pilferage & Kitchen Theft by Staff",
            "Rider Delays causing cold food delivery & bad reviews"
        ],
        "miscellaneous_expenses": [
            "Heat, Gas & Commercial Kitchen Electricity Bills (PNG/LPG सिलिंडर खर्च)",
            "Disposable Food Containers, Cutlery & Foil Paper Packaging",
            "Grease Trap Cleaning & Kitchen Deep Sanitation Services",
            "Commercial Music / FSSAI Food Licenses"
        ]
    },

    # =========================================================================
    # 9. REAL ESTATE & PROPTECH (Property Sales, Leasing & Coworking)
    # =========================================================================
    "real_estate_proptech": {
        "domain_code": "PROPTECH",
        "domain_name": "Real Estate, Commercial Leasing & PropTech",
        "industry_examples": ["WeWork", "DLF", "CBRE", "Zillow", "Lodha", "PropTiger"],
        "description": "जमीन, मकान, या कमर्शियल ऑफिस स्पेस को बेचना, लीज पर देना या को-वर्किंग डेस्क किराए पर देना। यहाँ ट्रांजैक्शन साइज करोड़ों में होता है और कैपिटल लंबे समय तक फंसा रहता है।",
        "typical_columns": [
            "unit_id", "property_name", "asset_type", "square_feet_area",
            "listing_price", "rent_per_sqft_monthly", "lease_start_date",
            "lease_end_date", "occupancy_status", "tenant_type",
            "capex_maintenance_cost", "security_deposit_held", "broker_commission_paid"
        ],
        "bounded_columns": ["asset_type", "occupancy_status", "tenant_type"],
        "unbounded_columns": ["unit_id", "property_name"],
        "numeric_metrics": ["square_feet_area", "listing_price", "rent_per_sqft_monthly", "capex_maintenance_cost", "security_deposit_held", "broker_commission_paid"],
        "key_metrics_kpis": [
            "Capitalization Rate (Cap Rate = Net_Operating_Income / Property_Value)",
            "Physical & Financial Occupancy Rate (%)",
            "Tenant Retention / Lease Renewal Rate",
            "Revenue Per Available Square Foot (RevPASF)",
            "Maintenance CAPEX as % of Rental Revenue"
        ],
        "mathematical_assertions": [
            "Net_Operating_Income == Annual_Rental_Income - Operating_Expenses",
            "Cap_Rate == (Net_Operating_Income / Property_Value) * 100"
        ],
        "profit_drivers": [
            "Long-Term Multi-Year Corporate Leases with Escalation Clauses (हर साल 5% किराया बढ़ना)",
            "Appreciation in Underlying Land / Property Value",
            "High Occupancy (95%+ occupancy in co-working or residential towers)"
        ],
        "loss_and_leakage_risks": [
            "Prolonged Vacancy (महीनों तक ऑफिस या फ्लैट खाली रहना)",
            "Property Tax and Unpaid Common Area Maintenance (CAM)",
            "Tenant Default and Costly Eviction Lawsuits"
        ],
        "miscellaneous_expenses": [
            "Brokerage / Real Estate Agent Commission (1 to 2 months rent)",
            "Property Municipal Taxes & Sewerage/Water Cess",
            "HVAC Central Air-Conditioning & Elevator Maintenance Contracts",
            "24x7 Security Guard and CCTV Surveillance Contracts"
        ]
    },

    # =========================================================================
    # 10. EDTECH & HIGHER EDUCATION / UPSKILLING
    # =========================================================================
    "edtech_upskilling": {
        "domain_code": "EDTECH",
        "domain_name": "EdTech & Higher Education / Upskilling Bootcamps",
        "industry_examples": ["Coursera", "Scaler", "Udemy", "UpGrad", "Khan Academy"],
        "description": "ऑनलाइन कोर्सेस, डिग्री प्रोग्राम्स, या कोडिंग बूटकैंप्स बेचना। यहाँ अपफ्रंट मार्केटिंग कॉस्ट बहुत ज्यादा होती है और कोर्स कंप्लीशन रेट बहुत कम होता है।",
        "typical_columns": [
            "enrollment_id", "student_id", "course_id", "course_category",
            "course_fee", "discount_scholarship", "net_fee_paid",
            "payment_installments_opted", "learning_progress_pct",
            "assignment_submissions", "course_completion_flag",
            "placement_status", "dropout_date"
        ],
        "bounded_columns": ["course_category", "course_completion_flag", "placement_status"],
        "unbounded_columns": ["enrollment_id", "student_id", "course_id"],
        "numeric_metrics": ["course_fee", "discount_scholarship", "net_fee_paid", "payment_installments_opted", "learning_progress_pct", "assignment_submissions"],
        "key_metrics_kpis": [
            "Course Completion Rate (%) - कोर्स पूरा करने वाले छात्रों का प्रतिशत",
            "Student Dropout Rate across Modules",
            "Customer Acquisition Cost (CAC) vs Course Fee Margin",
            "Placement / Career Transition Success Rate (%)",
            "Net Promoter Score (NPS)"
        ],
        "mathematical_assertions": [
            "net_fee_paid == course_fee - discount_scholarship",
            "Completion_Rate == (Completed_Students / Enrolled_Students) * 100"
        ],
        "profit_drivers": [
            "Low Marginal Cost of Digital Content (एक बार रिकॉर्ड करो, लाखों को बेचो)",
            "Corporate Upskilling B2B Enterprise Packages",
            "Student Referral Engine"
        ],
        "loss_and_leakage_risks": [
            "High Refund Demands within 7/14 days trial window",
            "Extremely High Google/Facebook Ad Lead Costs",
            "Unpaid Student EMIs on Income Share Agreements (ISAs)"
        ],
        "miscellaneous_expenses": [
            "Live Teaching Assistant (TA) & Doubt Solver Hourly Payouts",
            "Video Streaming Bandwidth (AWS CloudFront / Vimeo Enterprise)",
            "Accreditation & University Partner Royalty Cuts (20% - 40%)",
            "Mock Interview and Resume Reviewer Contractor Fees"
        ]
    },

    # =========================================================================
    # 11. LOGISTICS, FREIGHT & WAREHOUSING
    # =========================================================================
    "logistics_freight": {
        "domain_code": "LOGISTICS",
        "domain_name": "Logistics, Freight Forwarding & Warehousing",
        "industry_examples": ["Delhivery", "FedEx", "DHL", "Maersk", "Blue Dart"],
        "description": "सामान को स्रोत से गंतव्य तक पहुंचाना (हवाई, समुद्री, रेल या सड़क मार्ग)। यहाँ ईंधन (Fuel), टोल और खाली ट्रक्स सबसे बड़ा नुकसान होते हैं।",
        "typical_columns": [
            "consignment_note_number", "origin_hub", "destination_hub",
            "transport_mode", "carrier_code", "chargeable_weight_kg",
            "actual_weight_kg", "freight_charges", "fuel_surcharge",
            "transit_delay_hours", "pod_status", "demurrage_charges_incurred"
        ],
        "bounded_columns": ["transport_mode", "pod_status"],
        "unbounded_columns": ["consignment_note_number", "origin_hub", "destination_hub", "carrier_code"],
        "numeric_metrics": ["chargeable_weight_kg", "actual_weight_kg", "freight_charges", "fuel_surcharge", "transit_delay_hours", "demurrage_charges_incurred"],
        "key_metrics_kpis": [
            "On-Time In-Full (OTIF %)",
            "Cost Per Ton-Kilometer",
            "Empty Miles / Deadhead Percentage (%)",
            "Volumetric vs Actual Weight Discrepancy Capture Rate",
            "Proof of Delivery (POD) Upload TAT"
        ],
        "mathematical_assertions": [
            "chargeable_weight_kg == max(actual_weight_kg, (length * width * height) / 5000)",
            "total_invoice == freight_charges + fuel_surcharge + demurrage_charges_incurred"
        ],
        "profit_drivers": [
            "Full Truck Load (FTL) Maximization",
            "Capturing Volumetric Deadweight Discrepancies",
            "Automated Hub Sorting Facilities"
        ],
        "loss_and_leakage_risks": [
            "Demurrage & Detention Charges (पोर्ट या वेयरहाउस में फंसा रहने पर जुर्माना)",
            "Pilferage & Goods Damage in Transit",
            "Fuel Price Spikes without Escalation Clauses"
        ],
        "miscellaneous_expenses": [
            "Interstate Border Toll Taxes & Green Cess",
            "Port Handling & Container Drayage Fees",
            "Driver En-Route Accommodation & Emergency Breakdown Assistance",
            "Cargo Transit Marine Insurance Premiums"
        ]
    },

    # =========================================================================
    # 12. E-COMMERCE & RETAIL (Physical / Omnichannel Goods)
    # =========================================================================
    "ecommerce_retail": {
        "domain_code": "ECOM",
        "domain_name": "E-Commerce & Omnichannel Retail",
        "industry_examples": ["Flipkart", "Amazon", "Myntra", "Walmart", "Zara"],
        "description": "भौतिक उत्पादों की ऑनलाइन या ऑफलाइन बिक्री। यहाँ रिटर्न (RTO), डैमेज और अनक्लेम्ड रिफंड्स सबसे बड़े लीकेज होते हैं।",
        "typical_columns": [
            "transaction_id", "order_id", "customer_id", "product_category",
            "product_name", "units_sold", "unit_price", "discount_amount",
            "tax_amount", "total_revenue", "region", "city", "payment_status"
        ],
        "bounded_columns": ["product_category", "region", "city", "payment_status"],
        "unbounded_columns": ["transaction_id", "order_id", "customer_id", "product_name"],
        "numeric_metrics": ["units_sold", "unit_price", "discount_amount", "tax_amount", "total_revenue"],
        "key_metrics_kpis": [
            "Gross Merchandise Value (GMV)",
            "Net Realized Revenue (Completed Orders Only)",
            "Average Order Value (AOV)",
            "Return & Cancellation Rate (%)",
            "Gross Margin per Category"
        ],
        "mathematical_assertions": [
            "Net_Revenue == df[df['payment_status'] == 'Completed']['total_revenue'].sum()",
            "Row_Revenue_Check == (units_sold * unit_price) - discount_amount + tax_amount"
        ],
        "profit_drivers": [
            "High Repeat Customer Purchase Rate",
            "High-Margin Categories (Accessories, Fashion)",
            "Basket Size Expansion (Cross-sell recommendations)"
        ],
        "loss_and_leakage_risks": [
            "RTO (Return to Origin) & Reverse Courier Fees",
            "Damaged Goods in Transit",
            "Discount Burn without Volume Lift"
        ],
        "miscellaneous_expenses": [
            "Payment Gateway Charges (2% - 3% non-refundable on returns)",
            "Packaging Materials (Corrugated Boxes, Bubble wrap)",
            "Reverse Logistics Pickup Surcharge",
            "Warehouse Long-Term Storage Penalties"
        ]
    }
}
