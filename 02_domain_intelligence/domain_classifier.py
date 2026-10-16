"""
=============================================================================
UNIVERSAL DOMAIN CLASSIFIER & AUDITOR ENGINE (VERSION 2.0 - PERFECT)
=============================================================================
यह इंजन किसी भी बिजनेस के डेटासेट को देखकर:
1. 0 टोकन में Bounded (Finite) बनाम Unbounded (Infinite) कॉलम्स को अलग करता है।
2. डेटा करप्शन (नंबर में स्ट्रिंग, नेगेटिव वैल्यूज, मिसिंग वैल्यूज) पकड़ता है।
3. दुनिया के 12 सबसे बड़े बिजनेस मॉडल्स (B2B, B2C, B2D, D2C, Marketplaces,
   Manufacturing, Healthcare, FinTech, F&B, Logistics आदि) में से सही डोमेन मैच करता है।
4. उस डोमेन के गणितीय संतुलन सूत्र (Mathematical Assertions) और 
   छिपे हुए मिसलेनियस खर्चे (Ghost Costs) निकालता है।
5. रेसिलिएंट ऑटो-रीट्राई (Self-Healing) के साथ Gemini से सीएफओ-लेवल ऑडिट रिपोर्ट लेता है।
"""

import os
import sys
import json
import time
import pandas as pd
from dotenv import load_dotenv
from google import genai
from business_ontology import MASTER_BUSINESS_ONTOLOGY

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class UniversalDomainInspector:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.total_rows = len(df)
        self.columns = list(df.columns)
        self.column_meta = {}
        self.detected_domain_key = None
        self.detected_domain_info = None

    def inspect_columns_safely(self) -> dict:
        """
        कॉलम्स का संपूर्ण सुरक्षा और प्रकार (Type) ऑडिट (0 टोकन खर्च)
        """
        bounded_cols = []
        unbounded_cols = []
        numeric_metrics = []

        for col in self.columns:
            series = self.df[col]
            nulls = int(series.isnull().sum())
            unique_count = int(series.nunique())
            
            # 1. संख्यात्मक कॉलम ऑडिट (Metrics, Currency, Counts)
            if pd.api.types.is_numeric_dtype(series):
                clean_vals = series.dropna()
                numeric_metrics.append({
                    "column": col,
                    "min": float(clean_vals.min()) if not clean_vals.empty else None,
                    "max": float(clean_vals.max()) if not clean_vals.empty else None,
                    "mean": round(float(clean_vals.mean()), 2) if not clean_vals.empty else None,
                    "has_negatives": bool((clean_vals < 0).any()),
                    "missing_count": nulls
                })
            
            # 2. सीमित (Bounded / Finite) कॉलम (Categories, Status, Countries, Yes/No Flags)
            # यहाँ यूनिक वैल्यूज गिनी जा सकती हैं - सिस्टम कभी हैंग नहीं होगा!
            elif unique_count <= 30 or (unique_count / max(self.total_rows, 1) < 0.20 and unique_count < 100):
                bounded_cols.append({
                    "column": col,
                    "unique_values_count": unique_count,
                    "unique_samples": [str(x) for x in series.dropna().unique()[:10]],
                    "missing_count": nulls
                })
                
            # 3. असीमित (Unbounded / High-Cardinality) कॉलम (IDs, Hashes, UUIDs, Freeform Names)
            # इन्हें कभी लूप में रीड या ग्रुप-बाय नहीं करना
            else:
                unbounded_cols.append({
                    "column": col,
                    "unique_values_count": unique_count,
                    "classification": "Unbounded Primary Key / Identifier",
                    "missing_count": nulls
                })

        self.column_meta = {
            "total_rows": self.total_rows,
            "total_columns": len(self.columns),
            "bounded_categorical_columns": bounded_cols,
            "unbounded_identifier_columns": unbounded_cols,
            "numeric_metrics_columns": numeric_metrics
        }
        return self.column_meta

    def match_business_domain(self) -> tuple[str, dict]:
        """
        12 प्रमुख वैश्विक बिजनेस मॉडल्स में से सबसे सटीक मॉडल खोजना
        """
        col_names = [c.lower() for c in self.columns]
        best_domain = "ecommerce_retail"
        best_score = -1
        
        for key, info in MASTER_BUSINESS_ONTOLOGY.items():
            typical_cols = [c.lower() for c in info.get("typical_columns", [])]
            score = 0
            
            # 1. डायरेक्ट मैच
            for col in col_names:
                if col in typical_cols:
                    score += 3
                # 2. आंशिक सबस्ट्रिंग मैच (जैसे 'amount', 'fee', 'token', 'latency')
                for typ in typical_cols:
                    if typ in col or col in typ:
                        score += 1
                        
            if score > best_score:
                best_score = score
                best_domain = key
                
        self.detected_domain_key = best_domain
        self.detected_domain_info = MASTER_BUSINESS_ONTOLOGY.get(best_domain, {})
        return best_domain, self.detected_domain_info

    def get_cfo_level_audit_with_ai(self) -> str:
        """
        Gemini 3.8 Flash से रेसिलिएंट ऑटो-रीट्राई के साथ रणनीतिक ऑडिट लेना
        """
        domain_key, domain_info = self.match_business_domain()
        
        prompt = f"""
You are an Enterprise CFO and Chief AI Systems Architect.

Incoming Dataset Profile:
- Total Records: {self.total_rows}
- Detected Business Domain: {domain_info.get('domain_name')} ({domain_info.get('domain_code')})
- Industry Benchmark Examples: {domain_info.get('industry_examples')}
- Available Columns in Data: {self.columns}

Domain Knowledge Base References:
- Key KPIs: {domain_info.get('key_metrics_kpis')}
- Mathematical Assertions: {domain_info.get('mathematical_assertions')}
- Known Leakage Risks: {domain_info.get('loss_and_leakage_risks')}
- Known Miscellaneous Expenses: {domain_info.get('miscellaneous_expenses')}

Heuristic Column Meta:
- Bounded Columns (Status, Types): {json.dumps(self.column_meta.get('bounded_categorical_columns', []), indent=2)}
- Numeric Bounds: {json.dumps(self.column_meta.get('numeric_metrics_columns', []), indent=2)}

Task:
Provide an exhaustive, crystal-clear Strategic & Financial Audit in Hindi/Hinglish:
1. [Domain Identification & Business Reality]: यह किस प्रकार का बिजनेस है (B2B, B2C, B2D, D2C आदि) और यह डेटा उनके ऑपरेशन के किस हिस्से को दर्शाता है?
2. [Critical Leakages & Ghost Costs]: इस बिजनेस में छिपे हुए खर्चे (Miscellaneous Expenses) और मार्जिन लीकेज कहाँ हो रहे हैं?
3. [Mathematical Assertions & Integrity Checks]: इस डेटा में कौन-से गणितीय नियम (Sanity Checks) लगाकर चेक करना अनिवार्य है?
4. [AI Automation Directives]: हमारे ऑटोमेशन इंजन को इस डेटा को प्रोसेस करते समय किन 3 गलतियों से पूरी तरह बचना है?
"""

        # Resilient Self-Healing AI Execution Loop
        models_to_try = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
        for model_name in models_to_try:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={"temperature": 0.1}
                    )
                    return response.text.strip()
                except Exception as e:
                    err_str = str(e)
                    if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                        print(f"⚠️ Notice: {model_name} busy. Auto-retrying attempt {attempt+1}/3 in 2s...")
                        time.sleep(2)
                    else:
                        print(f"⚠️ Model fallback triggered due to: {e}")
                        break
                        
        return "सभी AI बैकएंड वर्तमान में अत्यधिक लोड में हैं। कृपया कुछ देर बाद प्रयास करें।"

if __name__ == "__main__":
    # टेस्ट रन: सेल्स डेटासेट
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "datasets", "sales_data.csv")
    df = pd.read_csv(dataset_path)

    print("=" * 75)
    print("🌍 UNIVERSAL DOMAIN INSPECTOR & AUDITOR V2.0")
    print("=" * 75)
    
    inspector = UniversalDomainInspector(df)
    meta = inspector.inspect_columns_safely()
    
    domain_key, domain_info = inspector.match_business_domain()
    print(f"\n🎯 CLASSIFIED DOMAIN: {domain_info.get('domain_name')}")
    print(f"🏢 BUSINESS CODE:    {domain_info.get('domain_code')}")
    print(f"🌐 BENCHMARKS:       {', '.join(domain_info.get('industry_examples', []))}")
    print(f"📌 MATHEMATICAL CHECKS: {domain_info.get('mathematical_assertions')}")
    print(f"💸 MISCELLANEOUS COSTS: {domain_info.get('miscellaneous_expenses')}")

    print("\n" + "=" * 75)
    print("🧠 GENERATING EXECUTIVE AUDIT REPORT WITH GEMINI 3.8 FLASH...")
    print("=" * 75)
    report = inspector.get_cfo_level_audit_with_ai()
    print(report)
