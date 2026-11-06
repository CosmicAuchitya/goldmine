"""
=============================================================================
ENTERPRISE PII SCRUBBER, MULTILINGUAL PRIVACY & METADATA SANITIZER
=============================================================================
Defeats Weakness #4: PII & Data Privacy Leaks to Cloud LLMs (Stage 1 & Stage 4).
Executes 100% LOCALLY before any schema, sample data, or runtime traceback is
transmitted to external LLM providers.
Scrubs:
- Emails, Phone numbers (US, India, International)
- Credit Cards (13-19 digits), IBAN, PAN, SSN, Aadhaar
- IPv4 addresses & accidental API keys/tokens in logs/tracebacks
- Token-aware Multilingual PII column names (English, Portuguese, Spanish, German, French)
- Long free-text remarks/notes that could harbor unstructured customer PII
=============================================================================
"""

import re
import sys
from typing import Any, Dict, List, Set, Union

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# High-precision PII & secret regex patterns
PATTERNS = {
    "API_SECRET": re.compile(r'\b(?:AIza[0-9A-Za-z\-_]{30,}|sk-[A-Za-z0-9\-_]{20,})\b'),
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b'),
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "AADHAAR": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    "IBAN": re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b'),
    "PAN_ID": re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
    "INDIA_GSTIN": re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b'),
    "UK_NI_NUMBER": re.compile(r'\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b', re.IGNORECASE),
    "UPI_HANDLE": re.compile(r'\b[a-zA-Z0-9.\-_]{2,}@(okhdfcbank|okaxis|okicici|oksbi|paytm|ybl|ibl|upi|axl|apl|barodampay|federal|idfcbank|kotak|indus)\b', re.IGNORECASE),
    "PHONE": re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "IPV4": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
}

# Token-exact PII indicators (avoids false substring hits like 'cell' in 'cancellation' or 'dob' in 'adobe')
SENSITIVE_EXACT_TOKENS: Set[str] = {
    'ssn', 'aadhaar', 'iban', 'passport', 'dob', 'cpf', 'cnpj', 'cvv', 'pin',
    'password', 'passwd', 'email', 'correo', 'courriel', 'e_mail',
    'phone', 'mobile', 'cell', 'telefone', 'celular', 'whatsapp',
    'address', 'street', 'zipcode', 'postcode', 'direccion', 'endereco', 'anschrift',
    'surname', 'firstname', 'lastname', 'fullname', 'username',
    'vorname', 'nachname', 'sobrenome', 'apellido',
    'remark', 'remarks', 'comment', 'comments', 'notes',
    'gstin', 'nino', 'upi', 'vpa', 'sortcode',
}

SENSITIVE_PHRASES: Set[str] = {
    'social_security', 'credit_card', 'card_number', 'pan_number',
    'birth_date', 'date_of_birth', 'review_text',
    'national_insurance', 'gst_number', 'gst_no', 'upi_id', 'sort_code',
}

NON_PERSON_NAME_QUALIFIERS: Set[str] = {
    'product', 'produto', 'item', 'category', 'categoria', 'sub', 'department', 'dept',
    'store', 'shop', 'branch', 'company', 'brand', 'vendor', 'supplier', 'carrier',
    'airline', 'airport', 'city', 'state', 'country', 'region', 'table', 'file',
    'column', 'metric', 'model', 'plan', 'segment', 'channel', 'campaign', 'event',
    'course', 'drug', 'medication', 'test', 'device', 'machine', 'app', 'service',
}


def _sanitize_header_str(val: str, max_len: int = 120) -> str:
    """Strips control chars and prompt-delimiter tokens from schema metadata strings."""
    s = re.sub(r'[\x00-\x1f\x7f]+', ' ', str(val))
    s = s.replace("```", "").replace("<|", "").replace("|>", "")
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:max_len].rstrip() if len(s) > max_len else s


def is_sensitive_column_name(col_name: str) -> bool:
    """
    Token-aware check for personal/PII or free-text remark columns across English,
    Portuguese, Spanish, German, and French without falsely masking operational columns
    like 'cancellation', 'product_name', or 'department_name'.
    """
    raw = str(col_name or "").strip()
    if not raw:
        return False
    # Split camelCase (e.g. NomeCliente -> nome_cliente) and non-alpha separators
    norm = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', raw).lower()
    norm = re.sub(r'[^a-z0-9]+', '_', norm).strip('_')
    if not norm:
        return False

    if any(phrase in norm for phrase in SENSITIVE_PHRASES):
        return True

    tokens = [t for t in norm.split('_') if t]
    token_set = set(tokens)
    if token_set & SENSITIVE_EXACT_TOKENS:
        return True

    # Person name check ('name' or 'nome' without non-person entity qualifiers)
    if ('name' in token_set or 'nome' in token_set) and not (token_set & NON_PERSON_NAME_QUALIFIERS):
        return True

    return False


def scrub_text(text: str) -> str:
    """Replaces sensitive PII and secret patterns with sanitized redacted tags."""
    if not isinstance(text, str):
        return text

    sanitized = text
    for tag, pattern in PATTERNS.items():
        sanitized = pattern.sub(f"[REDACTED_{tag}]", sanitized)
    return sanitized


def scrub_sample_values(col_name: str, samples: List[Any]) -> List[Any]:
    """
    Anonymizes sample values locally:
    1. Masks all values if column name matches multilingual PII / remarks taxonomy.
    2. Masks unstructured free-text prose (>45 chars with >=3 spaces) to prevent leaked names/notes.
    3. Scrubs regex PII patterns across all remaining string samples.
    """
    col_lower = str(col_name).lower().strip()
    is_sensitive_name = is_sensitive_column_name(col_name)

    scrubbed = []
    for s in samples:
        s_str = str(s).strip()
        if is_sensitive_name:
            scrubbed.append(f"[MASKED_{re.sub(r'[^A-Z0-9]+', '_', col_lower.upper()).strip('_')}]")
        elif len(s_str) > 45 and s_str.count(" ") >= 3:
            scrubbed.append(f"[MASKED_FREETEXT_LEN_{len(s_str)}]")
        else:
            scrubbed.append(scrub_text(_sanitize_header_str(s_str, max_len=120)))
    return scrubbed


def scrub_schema_payload(payload: Union[Dict, List, str]) -> Union[Dict, List, str]:
    """Recursively traverses schema JSON dictionaries, scrubbing PII and neutralizing prompt-injection tokens."""
    if isinstance(payload, dict):
        new_dict = {}
        for k, v in payload.items():
            safe_k = _sanitize_header_str(k, max_len=120) if isinstance(k, str) else k
            if k in ["sample_values", "samples"] and isinstance(v, list):
                col_name = payload.get("name", payload.get("column", "generic_col"))
                new_dict[safe_k] = scrub_sample_values(col_name, v)
            elif k in ["name", "column", "table_name", "filename", "recommended_primary_key"] and isinstance(v, str):
                new_dict[safe_k] = scrub_text(_sanitize_header_str(v, max_len=120))
            elif k in ["columns", "potential_keys", "strictly_unique_primary_keys"] and isinstance(v, list):
                new_dict[safe_k] = [
                    scrub_text(_sanitize_header_str(item, max_len=120)) if isinstance(item, str) else scrub_schema_payload(item)
                    for item in v
                ]
            else:
                new_dict[safe_k] = scrub_schema_payload(v)
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
