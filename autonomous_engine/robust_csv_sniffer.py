"""
=============================================================================
ENTERPRISE CSV DELIMITER, ENCODING & EUROPEAN DECIMAL-COMMA SNIFFER
=============================================================================
Defeats Weakness #1: Foreign, European, and legacy CSV delimiter/encoding chaos.
Solves:
- Semicolon (;), tab (\t), pipe (|), and comma (,) delimiters
- Encoding failures: utf-8, utf-8-sig, latin1, cp1252, iso-8859-1
- European / LATAM decimal-comma & dot-thousand numbers (e.g. '1.234,56', '840,50')
  normalized safely per-column without corrupting ISO dot-decimal columns.
=============================================================================
"""

import csv
import io
import re
import sys
from pathlib import Path
from typing import Tuple, Optional
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

CANDIDATE_ENCODINGS = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
CANDIDATE_DELIMITERS = [',', ';', '\t', '|']

# Matches European formatted numbers: optional EUR/€ currency, optional dot-thousands, comma followed by 1-2 decimal digits OR dot-thousands followed by 1-4 decimals
_EU_DECIMAL_RE = re.compile(
    r'^\s*[+-]?\s*(?:€|EUR)?\s*(?:(?:\d{1,3}(?:\.\d{3})+,\d{1,4})|(?:\d+,\d{1,2}))\s*(?:€|EUR|%)?\s*$',
    re.IGNORECASE,
)
_PLAIN_INT_RE = re.compile(
    r'^\s*[+-]?\s*(?:€|EUR)?\s*\d+\s*(?:€|EUR|%)?\s*$',
    re.IGNORECASE,
)
# Matches Indian Tally/Vyapar/Busy & US/UK formatted currency strings (incl. parenthetical negatives & Cr/Dr)
_INTL_CURRENCY_RE = re.compile(
    r'^\s*\(?\s*[+-]?\s*(?:₹|â‚¹|\$|£|Rs\.?|INR|USD|GBP)\s*[+-]?\s*\d[\d,]*(?:\.\d{1,4})?\s*(?:/-|(?:\s*(?:INR|USD|GBP|Rs\.?|Dr|Cr)))?\s*\)?\s*$'
    r'|^\s*\(?\s*[+-]?\s*\d[\d,]*(?:\.\d{1,4})?\s*(?:/-|\s*(?:₹|â‚¹|\$|£|INR|USD|GBP|Rs\.?|Dr|Cr))\s*\)?\s*$',
    re.IGNORECASE,
)
_STD_NUM_COMMA_RE = re.compile(r'^\s*[+-]?\s*\d{1,3}(?:,\d{2,3})+(?:\.\d{1,4})?\s*$')


def _sniff_delimiter_from_text(sample_text: str, fallback: str = ',') -> str:
    lines = [line.strip() for line in sample_text.splitlines() if line.strip()][:10]
    if not lines:
        return fallback
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff("\n".join(lines), delimiters=CANDIDATE_DELIMITERS)
        return dialect.delimiter
    except Exception:
        delim_scores = {}
        for d in CANDIDATE_DELIMITERS:
            counts = [line.count(d) for line in lines]
            if counts and min(counts) > 0 and max(counts) == min(counts):
                delim_scores[d] = sum(counts)
            elif counts:
                delim_scores[d] = sum(counts) * 0.5
        if delim_scores:
            best = max(delim_scores, key=delim_scores.get)
            if delim_scores[best] > 0:
                return best
    return fallback


def normalize_european_decimal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Safely parses per-column European decimal-comma numbers ('1.234,56', '840,50 €')
    into standard IEEE floats without corrupting regular dot-decimal columns.
    """
    if df is None or df.empty:
        return df

    for col in df.columns:
        ser = df[col]
        if pd.api.types.is_numeric_dtype(ser):
            continue
        non_null = ser.dropna().astype(str).str.strip()
        non_null = non_null[non_null != ""]
        if len(non_null) == 0:
            continue

        sample = non_null.head(100)
        has_non_eu_currency = any(re.search(r'[₹\$£]|(?:INR|USD|GBP|rs\.?\s*\d|/-|â‚¹)', v, re.IGNORECASE) for v in sample)
        if has_non_eu_currency:
            curr_hits = sum(1 for v in sample if _INTL_CURRENCY_RE.match(v) or _STD_NUM_COMMA_RE.match(v) or _PLAIN_INT_RE.match(v))
            if curr_hits >= 1 and (curr_hits / len(sample)) >= 0.75:
                s_raw = ser.astype(str).str.strip()
                is_paren_neg = s_raw.str.startswith('(') & s_raw.str.endswith(')')
                is_cr_neg = s_raw.str.contains(r'(?i)(?:\s|\d)cr\s*\)?$', regex=True, na=False)
                cleaned = (
                    s_raw
                    .str.replace(r'^\(|\)$', '', regex=True)
                    .str.replace(r'(?i)(?:INR|USD|GBP|Rs\.?|â‚¹|[₹\$£,\s])', '', regex=True)
                    .str.replace(r'(?i)(?:/-|dr|cr)$', '', regex=True)
                    .str.replace(r'/-$', '', regex=True)
                )
                parsed = pd.to_numeric(cleaned, errors='coerce')
                parsed = parsed.where(~(is_paren_neg | is_cr_neg), -parsed.abs())
                if parsed.notna().sum() >= max(1, int(len(non_null) * 0.75)):
                    # Preserve detected currency hint on DataFrame attrs for downstream resolvers
                    sample_joined = " ".join(sample.tolist())
                    hint = "INR" if re.search(r'(?:₹|â‚¹|Rs\.?|INR|/-)', sample_joined, re.IGNORECASE) else ("GBP" if "£" in sample_joined else "USD")
                    hints = dict(df.attrs.get("_detected_currency_hints") or {})
                    hints[col] = hint
                    df.attrs["_detected_currency_hints"] = hints
                    df[col] = parsed
            continue
        eu_hits = sum(1 for v in sample if _EU_DECIMAL_RE.match(v))
        int_hits = sum(1 for v in sample if _PLAIN_INT_RE.match(v))
        if eu_hits >= 1 and ((eu_hits + int_hits) / len(sample)) >= 0.75:
            cleaned = (
                ser.astype(str)
                .str.replace(r'(?i)(?:EUR|USD|GBP|INR|[€£$₹%\s])', '', regex=True)
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
            )
            parsed = pd.to_numeric(cleaned, errors='coerce')
            if parsed.notna().sum() >= max(1, int(len(non_null) * 0.75)):
                df[col] = parsed

    return df


def detect_encoding_and_delimiter(file_path: Path, sample_bytes: int = 65536) -> Tuple[str, str]:
    """
    Sniffs both the encoding and the delimiter of a text/CSV file.
    """
    valid_encoding = 'utf-8'
    sample_text = ""

    with open(file_path, 'rb') as f:
        raw_bytes = f.read(sample_bytes)

    # Detect UTF-16LE / UTF-16BE BOM (e.g. Microsoft Excel 'Unicode Text' exports) before latin1 mis-decodes NUL bytes
    if raw_bytes.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            sample_text = raw_bytes.decode('utf-16')
            return 'utf-16', _sniff_delimiter_from_text(sample_text, fallback=',')
        except UnicodeDecodeError:
            pass

    for enc in CANDIDATE_ENCODINGS:
        try:
            sample_text = raw_bytes.decode(enc)
            if enc in ['utf-8', 'utf-8-sig']:
                try:
                    with open(file_path, 'r', encoding=enc) as f_test:
                        while f_test.read(65536):
                            pass
                except UnicodeDecodeError:
                    continue
            valid_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if not sample_text:
        sample_text = raw_bytes.decode('latin1', errors='replace')
        valid_encoding = 'latin1'

    delimiter = _sniff_delimiter_from_text(sample_text, fallback=',')
    return valid_encoding, delimiter


def smart_read_csv(file_path: Path, **kwargs) -> pd.DataFrame:
    """
    Production-grade CSV reader that auto-detects encoding, delimiter, and
    European decimal-comma formatting ('1.234,56').
    """
    p = Path(file_path)
    encoding, delimiter = detect_encoding_and_delimiter(p)

    enc = kwargs.pop('encoding', encoding)
    sep = kwargs.pop('sep', kwargs.pop('delimiter', delimiter))
    if 'na_values' not in kwargs:
        kwargs['na_values'] = ['?']

    df = pd.read_csv(p, encoding=enc, sep=sep, **kwargs)
    if kwargs.get('header', 'infer') is None:
        return df
    df.columns = [str(c).lstrip('\ufeff').strip() for c in df.columns]
    return normalize_european_decimal_columns(df)


def smart_read_csv_bytes(raw_bytes: bytes, fallback_sep: str = ',', **kwargs) -> pd.DataFrame:
    """
    In-memory counterpart to smart_read_csv for fast API preview/handshake ingestion.
    Handles UTF-8/BOM/Latin-1 encodings, semicolon/tab/pipe delimiters, and EU decimal commas.
    """
    sample = raw_bytes[:65536]
    valid_enc = 'utf-8'
    sample_text = ''
    if raw_bytes.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            sample_text = raw_bytes.decode('utf-16')
            valid_enc = 'utf-16'
        except UnicodeDecodeError:
            sample_text = ''
    if not sample_text:
        for enc in CANDIDATE_ENCODINGS:
            try:
                sample_text = sample.decode(enc)
                raw_bytes.decode(enc)
                valid_enc = enc
                break
            except UnicodeDecodeError:
                continue
    if not sample_text:
        sample_text = sample.decode('latin1', errors='replace')
        valid_enc = 'latin1'

    enc = kwargs.pop('encoding', valid_enc)
    sep = kwargs.pop('sep', kwargs.pop('delimiter', _sniff_delimiter_from_text(sample_text, fallback=fallback_sep)))
    if 'na_values' not in kwargs:
        kwargs['na_values'] = ['?']

    df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=sep, **kwargs)
    if kwargs.get('header', 'infer') is None:
        return df
    df.columns = [str(c).lstrip('\ufeff').strip() for c in df.columns]
    return normalize_european_decimal_columns(df)


if __name__ == "__main__":
    test_dir = Path("cache/test_data")
    test_dir.mkdir(parents=True, exist_ok=True)
    semi_file = test_dir / "sample_german.csv"
    with open(semi_file, "w", encoding="latin1") as f:
        f.write("id;kunde_name;umsatz;stadt\n101;Müller;1.250,50;Berlin\n102;Schmidt;840,00;München\n")
    df = smart_read_csv(semi_file)
    print(f"[+] Loaded {len(df)} rows, umsatz dtype={df['umsatz'].dtype}, values={df['umsatz'].tolist()}")
