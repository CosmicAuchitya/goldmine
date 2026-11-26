"""
Independent Auditor Script (Zero App Knowledge):
Streams genuine public Wells Fargo Bank N.A. (FDIC #03511, NYSE: WFC, CIK 0000072971)
multi-year data directly from official US Government APIs:
  1. US SBA 7(a) FOIA Ledgers (FY2010-FY2019 & FY2020-Present as of 2026-09-30)
  2. US CFPB Consumer Complaint API (2013-2023 annual aggregations)
  3. US SEC EDGAR XBRL Company Facts (CIK0000072971 annual 10-K metrics)
"""
from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

OUT_DIR = Path(__file__).resolve().parent

SBA_URLS = [
    ("FY2010_FY2019", "https://data.sba.gov/sites/default/files/uploaded_resources/FOIA_7a_FY2010_FY2019_asof_260930.csv"),
    ("FY2020_Present", "https://data.sba.gov/sites/default/files/uploaded_resources/FOIA_7a_FY2020_Present_asof_260930.csv"),
]


def stream_sba_wellsfargo() -> Path:
    out_csv = OUT_DIR / "wellsfargo_sba_7a_2010_present.csv"
    total_scanned = 0
    wf_rows = 0
    header: List[str] = []

    with open(out_csv, "w", encoding="utf-8", newline="") as f_out:
        writer = None
        for tag, url in SBA_URLS:
            t0 = time.perf_counter()
            print(f"[*] Streaming {tag}: {url} ...", flush=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                text_stream = io.TextIOWrapper(resp, encoding="utf-8", errors="replace", newline="")
                reader = csv.reader(text_stream)
                src_header = next(reader)
                if not header:
                    header = src_header
                    writer = csv.writer(f_out)
                    writer.writerow(header)
                idx_bank = src_header.index("BankName")
                idx_fdic = src_header.index("BankFDICNumber")
                file_rows = 0
                file_wf = 0
                for row in reader:
                    file_rows += 1
                    total_scanned += 1
                    if len(row) <= max(idx_bank, idx_fdic):
                        continue
                    fdic = row[idx_fdic].strip().lstrip("0").split(".")[0]
                    bname = row[idx_bank].strip().upper()
                    if fdic == "3511" or "WELLS FARGO" in bname:
                        writer.writerow(row)
                        wf_rows += 1
                        file_wf += 1
                print(f"[+] {tag}: scanned {file_rows:,} rows -> matched {file_wf:,} Wells Fargo loans in {time.perf_counter()-t0:.1f}s", flush=True)

    print(f"[+] Saved {wf_rows:,} Wells Fargo SBA 7(a) loans (from {total_scanned:,} total rows) to {out_csv}", flush=True)
    return out_csv


def fetch_cfpb_annual_history() -> Path:
    out_json = OUT_DIR / "wellsfargo_cfpb_2013_2023.json"
    yearly: List[Dict[str, Any]] = []
    for yr in range(2013, 2024):
        url = (
            "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
            f"?company=WELLS%20FARGO%20%26%20COMPANY&date_received_min={yr}-01-01&date_received_max={yr}-12-31&size=0"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib/3.14"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        tot = int((data.get("hits", {}).get("total") or {}).get("value", 0))
        aggs = data.get("aggregations") or {}
        resp_map = {b["key"]: b["doc_count"] for b in (aggs.get("company_response", {}).get("company_response", {}).get("buckets") or [])}
        prod_map = {b["key"]: b["doc_count"] for b in (aggs.get("product", {}).get("product", {}).get("buckets") or [])}
        timely_map = {b["key"]: b["doc_count"] for b in (aggs.get("timely", {}).get("timely", {}).get("buckets") or [])}
        mon_relief = int(resp_map.get("Closed with monetary relief", 0))
        yearly.append({
            "year": yr,
            "total_complaints": tot,
            "monetary_relief_count": mon_relief,
            "monetary_relief_pct": round(100.0 * mon_relief / max(1, tot), 2),
            "untimely_count": int(timely_map.get("No", 0)),
            "top_responses": dict(list(resp_map.items())[:5]),
            "top_products": dict(list(prod_map.items())[:5]),
        })
        print(f"    CFPB {yr}: total={tot:,}, monetary_relief={mon_relief:,} ({yearly[-1]['monetary_relief_pct']}%)", flush=True)
    out_json.write_text(json.dumps({"company": "WELLS FARGO & COMPANY", "years": yearly}, indent=2), encoding="utf-8")
    return out_json


def fetch_sec_edgar_annual_facts() -> Path:
    out_json = OUT_DIR / "wellsfargo_sec_10k_2013_2023.json"
    url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000072971.json"
    req = urllib.request.Request(url, headers={"User-Agent": "DataXRayResearchAudit/1.0 audit@dataxray.local"})
    raw = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    us_gaap = (raw.get("facts") or {}).get("us-gaap") or {}

    candidate_tags = {
        "net_income": ["NetIncomeLoss"],
        "noninterest_expense": ["NoninterestExpense"],
        "provision_credit_losses": ["ProvisionForLoanLossesExpensed", "ProvisionForLoanLeaseAndOtherLosses"],
        "assets": ["Assets"],
        "deposits": ["Deposits"],
        "interest_and_fee_income_loans": ["InterestAndFeeIncomeLoansAndLeases", "InterestIncomeOperating"],
    }

    extracted: Dict[int, Dict[str, Any]] = {y: {"year": y} for y in range(2013, 2025)}
    for metric, tags in candidate_tags.items():
        for tag in tags:
            node = us_gaap.get(tag) or {}
            units = (node.get("units") or {}).get("USD") or []
            for entry in units:
                if entry.get("form") != "10-K":
                    continue
                fp = str(entry.get("fp") or "")
                fy = entry.get("fy")
                frame = str(entry.get("frame") or "")
                # Prefer canonical full-year frame like CY2018 or instant CY2018Q4I
                end_dt = str(entry.get("end") or "")
                if not end_dt.startswith("20"):
                    continue
                yr = int(end_dt[:4])
                if yr not in extracted:
                    continue
                if frame and (frame == f"CY{yr}" or frame == f"CY{yr}Q4I"):
                    extracted[yr][metric] = float(entry.get("val", 0.0))
                elif metric not in extracted[yr] and fp == "FY":
                    # Only annual (start-to-end ~ 365 days) or instant balance sheet
                    start_dt = str(entry.get("start") or "")
                    if not start_dt or (int(end_dt[:4]) == int(start_dt[:4])):
                        extracted[yr][metric] = float(entry.get("val", 0.0))

    summary = {"entity": raw.get("entityName"), "cik": "0000072971", "years": list(extracted.values())}
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[+] Saved SEC EDGAR 10-K metrics for {raw.get('entityName')} -> {out_json}", flush=True)
    return out_json


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stream_sba_wellsfargo()
    fetch_cfpb_annual_history()
    fetch_sec_edgar_annual_facts()
