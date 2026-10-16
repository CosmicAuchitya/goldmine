"""
=============================================================================
MULTI-INDUSTRY DOMAIN TESTER (B2D, E-COM, ANY BUSINESS)
=============================================================================
यह स्क्रिप्ट साबित करती है कि हमारा AI ऑटोमेशन केवल ई-कॉमर्स नहीं,
बल्कि B2D (API / DevTools), B2B, Manufacturing या किसी भी बिजनेस डेटा
को सटीकता से क्लासिफाई करता है और उसके लीकेजेस पकड़ता है।
"""

import os
import sys
import pandas as pd
from domain_classifier import UniversalDomainInspector

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def test_dataset(file_path: str, dataset_label: str):
    print("\n" + "=" * 80)
    print(f"🚀 TESTING DATASET: [{dataset_label}]")
    print(f"📁 PATH: {file_path}")
    print("=" * 80)
    
    df = pd.read_csv(file_path)
    inspector = UniversalDomainInspector(df)
    inspector.inspect_columns_safely()
    
    domain_key, domain_info = inspector.match_business_domain()
    print(f"\n✅ CLASSIFIED DOMAIN: {domain_info.get('domain_name')}")
    print(f"🏢 DOMAIN CODE:       {domain_info.get('domain_code')}")
    print(f"🌐 BENCHMARKS:        {', '.join(domain_info.get('industry_examples', []))}")
    print(f"📌 MATHEMATICAL CHECKS: {domain_info.get('mathematical_assertions')}")
    print(f"💸 KNOWN MISC EXPENSES: {domain_info.get('miscellaneous_expenses')}")

    print("\n🧠 RUNNING AI CFO & SYSTEMS ARCHITECT AUDIT...")
    audit = inspector.get_cfo_level_audit_with_ai()
    print("\n" + "-" * 40 + " AI AUDIT REPORT " + "-" * 40)
    print(audit)
    print("-" * 97 + "\n")

if __name__ == "__main__":
    base_dir = os.path.join(os.path.dirname(__file__), "..", "datasets")
    
    # 1. B2D (Business-to-Developer) API डेटासेट टेस्ट
    b2d_file = os.path.join(base_dir, "b2d_api_metrics.csv")
    test_dataset(b2d_file, "B2D Developer & AI API Infrastructure")
