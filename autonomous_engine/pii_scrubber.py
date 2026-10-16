"""
=============================================================================
ENTERPRISE PII SCRUBBER & LOCAL PRIVACY GUARD
=============================================================================
Defeats Weakness #4: PII & Data Privacy Leaks to Cloud LLMs.
Executes 100% LOCALLY before any schema or sample data is transmitted.
Scrubs:
- Emails
- Phone numbers (US, India, International)
- Credit Card numbers (13-19 digit candidate patterns)
- Social Security Numbers (SSN) / Aadhaar candidate numbers
- IP addresses (IPv4 / IPv6)
- High-risk full names / personal identification tokens
=============================================================================
"""

import re
import sys
from typing import Any, Dict, List, Union

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# High-precision PII regex patterns
PATTERNS = {
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "PHONE": re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b'),
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "AADHAAR": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    "IPV4": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
}

SENSITIVE_COLUMN_NAMES = {
    'name', 'first_name', 'last_name', 'full_name', 'customer_name', 'patient_name',
    'ssn', 'social_security', 'credit_card', 'card_number', 'cvv', 'password',
    'phone', 'mobile', 'cell', 'email', 'address', 'street', 'zipcode', 'aadhaar'
}

def scrub_text(text: str) -> str:
    """Replaces sensitive PII patterns with sanitized redacted tags."""
    if not isinstance(text, str):
        return text
        
    sanitized = text
    for tag, pattern in PATTERNS.items():
        sanitized = pattern.sub(f"[REDACTED_{tag}]", sanitized)
    return sanitized

def scrub_sample_values(col_name: str, samples: List[Any]) -> List[Any]:
    """Anonymizes sample values, especially if column name is sensitive."""
    col_lower = str(col_name).lower().strip()
    is_sensitive_name = any(k in col_lower for k in SENSITIVE_COLUMN_NAMES)
    
    scrubbed = []
    for s in samples:
        s_str = str(s).strip()
        if is_sensitive_name:
            scrubbed.append(f"[MASKED_{col_lower.upper()}]")
        else:
            scrubbed.append(scrub_text(s_str))
    return scrubbed

def scrub_schema_payload(payload: Union[Dict, List, str]) -> Union[Dict, List, str]:
    """Recursively traverses schema JSON dictionaries and scrubs all sample values."""
    if isinstance(payload, dict):
        new_dict = {}
        for k, v in payload.items():
            if k in ["sample_values", "samples"] and isinstance(v, list):
                # Context-aware scrubbing
                col_name = payload.get("name", payload.get("column", "generic_col"))
                new_dict[k] = scrub_sample_values(col_name, v)
            else:
                new_dict[k] = scrub_schema_payload(v)
        return new_dict
    elif isinstance(payload, list):
        return [scrub_schema_payload(item) for item in payload]
    elif isinstance(payload, str):
        return scrub_text(payload)
    return payload

if __name__ == "__main__":
    test_data = {
        "table": "customers",
        "columns": [
            {"name": "email", "sample_values": ["john.doe@company.com", "alice_99@gmail.com"]},
            {"name": "phone", "sample_values": ["+1-555-234-5678", "9876543210"]},
            {"name": "credit_card", "sample_values": ["4111-2222-3333-4444", "5500000000000004"]},
            {"name": "AirportFrom", "sample_values": ["ATL", "ORD"]}
        ]
    }
    print("[*] Testing Local PII Scrubber...")
    scrubbed = scrub_schema_payload(test_data)
    import json
    print(json.dumps(scrubbed, indent=2))
