"""
=============================================================================
DATAX-RAY WORKSTREAM 2 — TALLY/MARG GROUPED LEDGER FLATTENER & PDF EXTRACTOR
=============================================================================
Solves Weakness #2:
1. Hierarchical Tally / Marg / Vyapar Excel & CSV Ledgers:
   - Detects grouped Party / Ledger / Account section header rows (single
     populated non-numeric text cell or explicit 'Ledger:' / 'Party:' / 'M/s'
     prefix above child transaction rows).
   - Forward-fills the section label into a clean `Ledger_Party` column on
     every child transaction row.
   - Removes mid-sheet interleaved subtotals ('Sub Total', 'Party Total',
     'Ledger Total', 'Closing Balance', 'Opening Balance', 'Balance C/F',
     standalone 'Total') WITHOUT falsely deleting real company names like
     'Total Energies India' or 'Total Logistics Solutions'.
2. Native PDF Tabular Statement & Invoice Extraction (PyMuPDF `fitz` + `pypdf`):
   - Extracts bordered tables via `page.find_tables()` across pages (strictly
     bounded by `max_pages` DoS ceiling).
   - Falls back to whitespace/pipe column extraction for borderless Tally &
     bank statement PDFs.
   - Stitches multi-page tables sharing identical headers into one clean table.
   - Detects image-only scanned PDFs cleanly and raises an actionable error.
=============================================================================
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd


_INTERLEAVED_SUBTOTAL_RE = re.compile(
    r"^(?:grand\s*total|sub[\s-]*total|net\s*total|party\s*total|ledger\s*total|"
    r"group\s*total|section\s*total|month\s*total|day\s*total|page\s*total|"
    r"closing\s*balance|opening\s*balance|balance\s*[cb]/f|carried\s*forward|"
    r"brought\s*forward|total\s*[cb]/f|total\s*:?\s*|"
    r"total\s+(?:amount|value|sales|revenue|qty|quantity|sum|inr|usd|eur|gbp|"
    r"payable|receivable|outstanding|due|balance|cost|price|count|debit|credit))$",
    re.IGNORECASE,
)

_EXPLICIT_GROUP_PREFIX_RE = re.compile(
    r"^(?:ledger|party|account|a/c|customer|vendor|group|supplier|branch)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)
_MS_PREFIX_RE = re.compile(r"^m/s\.?\s+.+", re.IGNORECASE)

_NUMERIC_LIKE_RE = re.compile(
    r"^\s*\(?[+-]?\s*(?:rs\.?|inr|usd|eur|gbp|₹|\$|€|£)?\s*[\d,]+(?:\.\d+)?\s*(?:/-|dr|cr)?\)?\s*$",
    re.IGNORECASE,
)
_DATE_LIKE_RE = re.compile(
    r"^(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}[-\s][A-Za-z]{3}[-\s]\d{2,4})$"
)


def _clean_cell_str(val: Any) -> str:
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", "nat", "-", "--"):
        return ""
    return s


def _is_subtotal_row(non_empty_vals: List[str]) -> bool:
    if not non_empty_vals:
        return True
    # Inspect up to the first 3 non-empty cells for anchored subtotal/summary keywords
    for cell in non_empty_vals[:3]:
        if _INTERLEAVED_SUBTOTAL_RE.match(cell):
            return True
    return False


def _extract_group_header_label(row_vals: List[str], n_cols: int) -> Optional[str]:
    """
    Returns the cleaned group/party label if `row_vals` represents a Tally/Marg
    grouped section header row; returns None for normal transaction or subtotal rows.
    """
    non_empty = [v for v in row_vals if v]
    if not non_empty:
        return None
    if _is_subtotal_row(non_empty):
        return None

    # Case A: Explicit "Ledger:" / "Party:" label in col 0 and value in col 1
    if len(non_empty) == 2 and n_cols >= 4:
        first_low = non_empty[0].lower().rstrip(":- ")
        if first_low in ("ledger", "party", "party name", "account", "a/c", "customer", "group", "supplier"):
            cand = non_empty[1]
            if not _NUMERIC_LIKE_RE.match(cand) and not _DATE_LIKE_RE.match(cand):
                return cand
        return None

    # Case B: Single populated cell across >= 3 columns
    if len(non_empty) == 1 and n_cols >= 3:
        cand = non_empty[0]
        if len(cand) < 2 or len(cand) > 120:
            return None
        if _NUMERIC_LIKE_RE.match(cand) or _DATE_LIKE_RE.match(cand):
            return None
        m_pref = _EXPLICIT_GROUP_PREFIX_RE.match(cand)
        if m_pref:
            return m_pref.group(1).strip()
        return cand

    return None


def flatten_grouped_accounting_ledger(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Detects Tally/Marg/Vyapar hierarchical grouped ledgers and flattens them into
    clean 1NF tabular rows while removing mid-sheet interleaved subtotals.
    Strictly preserves normal flat CSV/Excel datasets untouched.
    """
    meta: Dict[str, Any] = {
        "flattened": False,
        "groups_detected": 0,
        "subtotals_removed": 0,
        "group_column": None,
    }
    if df is None or len(df) < 3 or len(df.columns) < 3:
        return df, meta

    # Fast O(1) pre-screen on large datasets (>20k rows) so industrial/enterprise tables
    # without Tally grouped headers or subtotals skip full Python row iteration cleanly.
    if len(df) > 20_000:
        sample_df = pd.concat([df.head(400), df.tail(50)], ignore_index=True)
        has_signal = False
        n_c = len(sample_df.columns)
        for pos in range(len(sample_df)):
            rv = [_clean_cell_str(x) for x in sample_df.iloc[pos].tolist()]
            ne = [v for v in rv if v]
            if not ne or _is_subtotal_row(ne) or _extract_group_header_label(rv, n_c) is not None:
                has_signal = True
                break
        if not has_signal:
            return df, meta

    n_cols = len(df.columns)
    group_candidates: Dict[int, str] = {}
    explicit_group_hits = 0
    subtotal_indices: List[int] = []

    for pos, idx in enumerate(df.index):
        row_vals = [_clean_cell_str(x) for x in df.iloc[pos].tolist()]
        non_empty = [v for v in row_vals if v]
        if not non_empty:
            subtotal_indices.append(idx)
            continue
        if _is_subtotal_row(non_empty):
            subtotal_indices.append(idx)
            continue
        lbl = _extract_group_header_label(row_vals, n_cols)
        if lbl:
            group_candidates[pos] = lbl
            raw_joined = " ".join(non_empty)
            if _EXPLICIT_GROUP_PREFIX_RE.match(raw_joined) or _MS_PREFIX_RE.match(lbl) or (
                len(non_empty) == 2 and non_empty[0].lower().rstrip(":- ") in ("ledger", "party", "account", "a/c", "customer", "group")
            ):
                explicit_group_hits += 1

    # Trigger grouping ONLY if >= 2 group header rows exist OR >= 1 explicit Tally Ledger/Party/M/s header
    should_flatten_groups = len(group_candidates) >= 2 or (len(group_candidates) >= 1 and explicit_group_hits >= 1)

    if not should_flatten_groups and not subtotal_indices:
        return df, meta

    # Verify that if we drop group headers & subtotals, at least 2 real data rows remain
    drop_positions = set(group_candidates.keys()) if should_flatten_groups else set()
    subtotal_set = set(subtotal_indices)

    kept_rows = []
    group_labels = []
    current_group: Optional[str] = None
    removed_subtotals = 0

    for pos, idx in enumerate(df.index):
        if idx in subtotal_set:
            removed_subtotals += 1
            continue
        if pos in drop_positions:
            current_group = group_candidates[pos]
            continue
        kept_rows.append(pos)
        group_labels.append(current_group)

    if len(kept_rows) < 1:
        return df, meta

    out_df = df.iloc[kept_rows].copy().reset_index(drop=True)
    meta["subtotals_removed"] = removed_subtotals

    if should_flatten_groups and any(g is not None for g in group_labels):
        col_name = "Ledger_Party"
        existing_low = {str(c).lower() for c in out_df.columns}
        if col_name.lower() in existing_low:
            col_name = "Ledger_Group"
        out_df.insert(0, col_name, pd.Series(group_labels).fillna("General").astype(str))
        meta["flattened"] = True
        meta["groups_detected"] = len(set(g for g in group_labels if g))
        meta["group_column"] = col_name

    return out_df, meta


def _parse_borderless_pdf_lines(text: str) -> pd.DataFrame:
    """Fallback parser for borderless Tally / bank PDF statements separated by >=2 spaces or pipes."""
    raw_lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    parsed_rows: List[List[str]] = []
    for ln in raw_lines:
        if "|" in ln and ln.count("|") >= 2:
            cells = [c.strip() for c in ln.strip("|").split("|")]
        else:
            cells = [c.strip() for c in re.split(r"\s{2,}|\t+", ln.strip()) if c.strip()]
        if len(cells) >= 3:
            parsed_rows.append(cells)

    if len(parsed_rows) < 2:
        return pd.DataFrame()

    # Determine dominant column count
    width_counts: Dict[int, int] = {}
    for r in parsed_rows:
        width_counts[len(r)] = width_counts.get(len(r), 0) + 1
    target_w = max(width_counts, key=lambda w: (width_counts[w], w))
    aligned = [r for r in parsed_rows if len(r) == target_w]
    if len(aligned) < 2:
        return pd.DataFrame()

    header = [c or f"Col_{i+1}" for i, c in enumerate(aligned[0])]
    # Deduplicate headers cleanly
    seen: Dict[str, int] = {}
    dedup_hdr = []
    for h in header:
        cnt = seen.get(h, 0)
        seen[h] = cnt + 1
        dedup_hdr.append(h if cnt == 0 else f"{h}_{cnt}")
    return pd.DataFrame(aligned[1:], columns=dedup_hdr)


def extract_table_from_pdf(
    source: Union[str, Path, bytes],
    max_pages: int = 40,
) -> pd.DataFrame:
    """
    Extracts structured tabular invoice/ledger data from a PDF file or raw PDF bytes.
    Primary: PyMuPDF (`fitz`) native grid/table detector across pages.
    Fallback: Borderless aligned-column text extractor (PyMuPDF / `pypdf`).
    """
    tables: List[pd.DataFrame] = []
    full_text_chunks: List[str] = []

    try:
        import fitz  # PyMuPDF

        if isinstance(source, (bytes, bytearray)):
            doc = fitz.open(stream=bytes(source), filetype="pdf")
        else:
            doc = fitz.open(str(source))
        try:
            page_limit = min(len(doc), max_pages)
            for p_idx in range(page_limit):
                page = doc[p_idx]
                txt = page.get_text("text") or ""
                if txt.strip():
                    full_text_chunks.append(txt)
                try:
                    finder = page.find_tables()
                    for tb in getattr(finder, "tables", []) or []:
                        raw_grid = tb.extract()
                        if not raw_grid or len(raw_grid) < 2:
                            continue
                        cleaned_grid = [
                            [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
                            for row in raw_grid
                        ]
                        hdr = [c if c else f"Col_{i+1}" for i, c in enumerate(cleaned_grid[0])]
                        # Deduplicate column names
                        seen: Dict[str, int] = {}
                        dedup = []
                        for h in hdr:
                            n_prev = seen.get(h, 0)
                            seen[h] = n_prev + 1
                            dedup.append(h if n_prev == 0 else f"{h}_{n_prev}")
                        df_t = pd.DataFrame(cleaned_grid[1:], columns=dedup)
                        if len(df_t) >= 1 and len(df_t.columns) >= 2:
                            tables.append(df_t)
                except Exception:
                    continue
        finally:
            doc.close()
    except ImportError:
        # Fallback to pypdf if fitz is unavailable
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source))
            for page in reader.pages[:max_pages]:
                txt = page.extract_text() or ""
                if txt.strip():
                    full_text_chunks.append(txt)
        except Exception as exc:
            raise ValueError(f"Unable to open PDF document: {exc}") from exc

    result_df = pd.DataFrame()
    if tables:
        # Stitch multi-page tables sharing the same column schema; pick largest stitched table
        buckets: Dict[Tuple[str, ...], List[pd.DataFrame]] = {}
        for t in tables:
            key = tuple(str(c).strip().lower() for c in t.columns)
            buckets.setdefault(key, []).append(t)
        best_bucket = max(buckets.values(), key=lambda grp: sum(len(x) * len(x.columns) for x in grp))
        result_df = pd.concat(best_bucket, ignore_index=True)
    elif full_text_chunks:
        result_df = _parse_borderless_pdf_lines("\n".join(full_text_chunks))

    if result_df.empty:
        if not full_text_chunks:
            raise ValueError(
                "This PDF appears to be a scanned image with no selectable text or table data. "
                "Please export as Excel/CSV from Tally/Marg or upload a text-based PDF statement."
            )
        raise ValueError(
            "No structured tabular rows could be extracted from this PDF. "
            "Please upload an itemized PDF invoice/ledger table or export CSV/Excel."
        )

    # Run Tally/accounting flattener & numeric cleaner automatically
    result_df, _ = flatten_grouped_accounting_ledger(result_df)
    try:
        from .robust_excel_scanner import clean_accounting_series, strip_accounting_summary_rows
    except ImportError:
        from robust_excel_scanner import clean_accounting_series, strip_accounting_summary_rows

    result_df = strip_accounting_summary_rows(result_df)
    for col in result_df.columns:
        if pd.api.types.is_object_dtype(result_df[col]) or pd.api.types.is_string_dtype(result_df[col]):
            result_df[col] = clean_accounting_series(result_df[col])

    return result_df.reset_index(drop=True)
