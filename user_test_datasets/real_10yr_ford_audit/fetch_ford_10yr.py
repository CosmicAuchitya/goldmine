"""
Independent Auditor Extractor (Zero Engine Changes):
Downloads 10 full years (2015-2024) of real Ford Motor Company (NYSE: F, CIK 0000037996)
vehicle defect complaints, crashes, fires, injuries & component failures from official
US Govt NHTSA (`COMPLAINTS_RECEIVED_2015-2019.zip`, `COMPLAINTS_RECEIVED_2020-2024.zip`)
plus official SEC EDGAR 10-K financial/warranty metrics.
"""
from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List

OUT_DIR = Path(__file__).resolve().parent

NHTSA_ZIPS = [
    ("2015_2019", "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2015-2019.zip"),
    ("2020_2024", "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2020-2024.zip"),
]

# Official NHTSA CMPL.txt 51-field schema (as of April 30, 2026)
CMPL_COLS: List[str] = [
    "CMPLID", "ODINO", "MFR_NAME", "MAKETXT", "MODELTXT", "YEARTXT", "CRASH", "FAILDATE",
    "FIRE", "INJURED", "DEATHS", "COMPDESC", "CITY", "STATE", "VIN", "DATEA", "LDATE",
    "MILES", "OCCURENCES", "CDESCR", "CMPL_TYPE", "POLICE_RPT_YN", "PURCH_DT",
    "ORIG_OWNER_YN", "ANTI_BRAKES_YN", "CRUISE_CONT_YN", "NUM_CYLS", "DRIVE_TRAIN",
    "FUEL_SYS", "FUEL_TYPE", "TRANS_TYPE", "VEH_SPEED", "DOT", "TIRE_SIZE",
    "LOC_OF_TIRE", "TIRE_FAIL_TYPE", "ORIG_EQUIP_YN", "MANUF_DT", "SEAT_TYPE",
    "RESTRAINT_TYPE", "DEALER_NAME", "DEALER_TEL", "DEALER_CITY", "DEALER_STATE",
    "DEALER_ZIP", "PROD_TYPE", "REPAIRED_YN", "MEDICAL_ATTN", "VEHICLES_TOWED_YN",
    "STATE_OF_INCIDENT", "VEHICLE_OPERATOR",
]


def stream_ford_nhtsa() -> Path:
    out_csv = OUT_DIR / "ford_nhtsa_complaints_2015_2024.csv"
    total_scanned = 0
    ford_matched = 0
    tmp_zip = OUT_DIR / "_tmp_nhtsa.zip"

    with open(out_csv, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(CMPL_COLS)
        for tag, url in NHTSA_ZIPS:
            t0 = time.perf_counter()
            print(f"[*] Downloading NHTSA {tag}: {url} ...", flush=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=240) as resp, open(tmp_zip, "wb") as zf_out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    zf_out.write(chunk)
            print(f"    Downloaded {tag} ({tmp_zip.stat().st_size / 1e6:.1f} MB) in {time.perf_counter()-t0:.1f}s", flush=True)

            chunk_scanned = 0
            chunk_ford = 0
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                txt_name = [n for n in zf.namelist() if n.lower().endswith(".txt")][0]
                with zf.open(txt_name) as z_stream:
                    text_io = io.TextIOWrapper(z_stream, encoding="latin-1", errors="replace", newline="")
                    reader = csv.reader(text_io, delimiter="\t", quoting=csv.QUOTE_NONE)
                    for row in reader:
                        chunk_scanned += 1
                        total_scanned += 1
                        if len(row) < 20:
                            continue
                        make = row[3].strip().upper()
                        if make == "FORD":
                            padded = (row + [""] * len(CMPL_COLS))[:len(CMPL_COLS)]
                            writer.writerow(padded)
                            chunk_ford += 1
                            ford_matched += 1
            print(f"[+] {tag}: scanned {chunk_scanned:,} rows -> matched {chunk_ford:,} FORD records", flush=True)

    if tmp_zip.exists():
        tmp_zip.unlink()
    print(f"[+] Saved {ford_matched:,} FORD records (out of {total_scanned:,}) -> {out_csv}", flush=True)
    return out_csv


def fetch_ford_sec_edgar() -> Path:
    out_json = OUT_DIR / "ford_sec_10k_2015_2024.json"
    url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000037996.json"
    req = urllib.request.Request(url, headers={"User-Agent": "DataXRayResearchAudit/1.0 audit@dataxray.local"})
    raw = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    us_gaap = (raw.get("facts") or {}).get("us-gaap") or {}

    candidate_tags = {
        "revenues": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        "cost_of_sales": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
        "net_income": ["NetIncomeLoss"],
        "warranty_accrual_issued": ["ProductWarrantyAccrualWarrantiesIssued", "StandardProductWarrantyAccrual"],
        "warranty_payments": ["ProductWarrantyAccrualPayments"],
    }

    extracted: Dict[int, Dict[str, Any]] = {y: {"year": y} for y in range(2014, 2026)}
    for metric, tags in candidate_tags.items():
        for tag in tags:
            node = us_gaap.get(tag) or {}
            units = (node.get("units") or {}).get("USD") or []
            for entry in units:
                if entry.get("form") != "10-K":
                    continue
                fp = str(entry.get("fp") or "")
                frame = str(entry.get("frame") or "")
                end_dt = str(entry.get("end") or "")
                if not end_dt.startswith("20"):
                    continue
                yr = int(end_dt[:4])
                if yr not in extracted:
                    continue
                if frame and (frame == f"CY{yr}" or frame == f"CY{yr}Q4I"):
                    extracted[yr][metric] = float(entry.get("val", 0.0))
                elif metric not in extracted[yr] and fp == "FY":
                    start_dt = str(entry.get("start") or "")
                    if not start_dt or (int(end_dt[:4]) == int(start_dt[:4])):
                        extracted[yr][metric] = float(entry.get("val", 0.0))

    summary = {"entity": raw.get("entityName"), "cik": "0000037996", "years": [y for y in extracted.values() if len(y) > 1]}
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[+] Saved SEC EDGAR 10-K facts for {raw.get('entityName')} -> {out_json}", flush=True)
    return out_json


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stream_ford_nhtsa()
    fetch_ford_sec_edgar()
