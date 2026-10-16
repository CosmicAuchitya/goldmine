"""
=============================================================================
ENTERPRISE KAGGLE DATASET HARVESTER & BENCHMARK SUITE
=============================================================================
Automates downloading, unzipping, and registering real-world, industry-standard
Kaggle datasets for autonomous data pipeline certification.
=============================================================================
"""

import os
import sys
import zipfile
from pathlib import Path
from typing import Optional

def download_and_prepare_kaggle_dataset(dataset_ref: str, target_dir: str) -> Optional[Path]:
    """
    Downloads a Kaggle dataset via KaggleApi and extracts it to target_dir.
    Returns Path to raw_data directory.
    """
    dest = Path(target_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    
    # Check if data already exists in target_dir
    existing_files = [f for f in dest.iterdir() if f.suffix.lower() in ['.csv', '.parquet', '.xlsx', '.tsv', '.txt']]
    if existing_files:
        print(f"[*] Dataset '{dataset_ref}' already present at: {dest} ({len(existing_files)} file(s))")
        return dest

    print(f"[*] Downloading Kaggle dataset '{dataset_ref}' to: {dest}...")
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        api.dataset_download_files(dataset_ref, path=str(dest), unzip=True)
    except Exception as e:
        print(f"[X] Kaggle API download failed: {e}")
        return None

    # Check for any remaining zip files
    for z in dest.glob("*.zip"):
        try:
            with zipfile.ZipFile(z, 'r') as zip_ref:
                zip_ref.extractall(dest)
            z.unlink()
        except Exception:
            pass

    discovered = [f for f in dest.iterdir() if f.suffix.lower() in ['.csv', '.parquet', '.xlsx', '.tsv', '.txt']]
    print(f"[+] Download complete: {len(discovered)} data file(s) extracted.")
    for f in discovered:
        print(f"    - {f.name} ({f.stat().st_size:,} bytes)")

    return dest

if __name__ == "__main__":
    if len(sys.argv) > 2:
        ref = sys.argv[1]
        out = sys.argv[2]
        download_and_prepare_kaggle_dataset(ref, out)
    else:
        print("Usage: python kaggle_harvester.py <dataset_ref> <target_dir>")
