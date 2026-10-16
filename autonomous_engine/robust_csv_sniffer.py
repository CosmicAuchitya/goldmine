"""
=============================================================================
ENTERPRISE CSV DELIMITER & ENCODING SNIFFER
=============================================================================
Defeats Weakness #1: Foreign, European, and legacy CSV delimiter/encoding chaos.
Solves:
- Semicolon (;), tab (\\t), pipe (|), and comma (,) delimiters
- Encoding failures: utf-8, utf-8-sig, latin1, cp1252, iso-8859-1
- Prevents reading entire CSV files as a single gigantic column
=============================================================================
"""

import csv
import io
import sys
from pathlib import Path
from typing import Tuple, Optional
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

CANDIDATE_ENCODINGS = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
CANDIDATE_DELIMITERS = [',', ';', '\t', '|']

def detect_encoding_and_delimiter(file_path: Path, sample_bytes: int = 65536) -> Tuple[str, str]:
    """
    Sniffs both the encoding and the delimiter of a text/CSV file.
    """
    valid_encoding = 'utf-8'
    sample_text = ""
    
    # 1. Detect Encoding
    with open(file_path, 'rb') as f:
        raw_bytes = f.read(sample_bytes)
        
    for enc in CANDIDATE_ENCODINGS:
        try:
            sample_text = raw_bytes.decode(enc)
            # If candidate is utf-8 or utf-8-sig, verify full stream to avoid late non-UTF8 byte traps (e.g. £ symbol in latin1)
            if enc in ['utf-8', 'utf-8-sig']:
                try:
                    with open(file_path, 'r', encoding=enc) as f_test:
                        while f_test.read(65536):
                            pass
                except UnicodeDecodeError:
                    continue  # Falls through to next encoding (e.g. latin1)
            valid_encoding = enc
            break
        except UnicodeDecodeError:
            continue
            
    if not sample_text:
        # Ultimate fallback
        sample_text = raw_bytes.decode('latin1', errors='replace')
        valid_encoding = 'latin1'

    # 2. Sniff Delimiter
    delimiter = ','
    lines = [line.strip() for line in sample_text.splitlines() if line.strip()][:10]
    
    if lines:
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff("\n".join(lines), delimiters=CANDIDATE_DELIMITERS)
            delimiter = dialect.delimiter
        except Exception:
            # Fallback heuristic: count delimiter occurrences across lines
            delim_scores = {}
            for d in CANDIDATE_DELIMITERS:
                counts = [line.count(d) for line in lines]
                # High score if count is > 0 and consistent across lines
                if counts and min(counts) > 0 and max(counts) == min(counts):
                    delim_scores[d] = sum(counts)
                elif counts:
                    delim_scores[d] = sum(counts) * 0.5
            if delim_scores:
                delimiter = max(delim_scores, key=delim_scores.get)

    return valid_encoding, delimiter

def smart_read_csv(file_path: Path, **kwargs) -> pd.DataFrame:
    """
    Production-grade CSV reader that auto-detects encoding and delimiter.
    """
    p = Path(file_path)
    encoding, delimiter = detect_encoding_and_delimiter(p)
    
    # If delimiter or encoding specified in kwargs, let kwargs override
    enc = kwargs.pop('encoding', encoding)
    sep = kwargs.pop('sep', kwargs.pop('delimiter', delimiter))
    if 'na_values' not in kwargs:
        kwargs['na_values'] = ['?']
    
    return pd.read_csv(p, encoding=enc, sep=sep, **kwargs)

if __name__ == "__main__":
    # Test with synthetic semicolon-separated and pipe-separated files
    test_dir = Path("error/test_data")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Semicolon test file (German/European format)
    semi_file = test_dir / "sample_german.csv"
    with open(semi_file, "w", encoding="latin1") as f:
        f.write("id;kunde_name;umsatz;stadt\n101;Müller;1250,50;Berlin\n102;Schmidt;840,00;München\n")
        
    enc, sep = detect_encoding_and_delimiter(semi_file)
    print(f"[*] Detected for '{semi_file.name}': Encoding='{enc}', Delimiter='{sep}'")
    df = smart_read_csv(semi_file)
    print(f"[+] Loaded successfully with {len(df.columns)} columns: {df.columns.tolist()}")
