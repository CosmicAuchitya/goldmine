"""
=============================================================================
ENTERPRISE KAGGLE DATASET HARVESTER & SAFE ZIP EXTRACTION GUARD
=============================================================================
Automates downloading, safely extracting (Zip-Slip & Zip-Bomb protected), and
registering real-world Kaggle datasets for autonomous data pipeline certification.
=============================================================================
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path
from typing import Optional

MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB safety ceiling


def safe_extract_zip(zip_path: Path, dest_dir: Path, max_bytes: int = MAX_UNCOMPRESSED_BYTES) -> None:
    """
    Extracts a ZIP archive safely into dest_dir while blocking:
    1. Zip-Slip path traversal ('../', absolute paths, drive letters)
    2. Symbolic link archive entries
    3. Decompression bombs exceeding max_bytes
    """
    dest_root = dest_dir.resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Reject POSIX symlinks encoded in external_attr (mode 0o120000)
            is_symlink = ((member.external_attr >> 16) & 0o170000) == 0o120000
            if is_symlink:
                raise ValueError(f"Security Violation: Refusing symlink entry '{member.filename}' in archive.")

            target_path = (dest_root / member.filename).resolve()
            if not target_path.is_relative_to(dest_root):
                raise ValueError(
                    f"Security Violation (Zip-Slip Blocked): Archive entry '{member.filename}' escapes '{dest_root}'."
                )

            total_uncompressed += max(member.file_size, 0)
            if total_uncompressed > max_bytes:
                raise ValueError(
                    f"Security Violation (Zip-Bomb Blocked): Uncompressed archive size exceeds {max_bytes:,} bytes."
                )

        # Second pass: extract verified entries via stream copy
        for member in zf.infolist():
            target_path = (dest_root / member.filename).resolve()
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)


def download_and_prepare_kaggle_dataset(dataset_ref: str, target_dir: str) -> Optional[Path]:
    """
    Downloads a Kaggle dataset via KaggleApi and safely extracts it to target_dir.
    Returns Path to raw_data directory.
    """
    dest = Path(target_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    existing_files = [f for f in dest.iterdir() if f.suffix.lower() in ['.csv', '.parquet', '.xlsx', '.tsv', '.txt']]
    if existing_files:
        print(f"[*] Dataset '{dataset_ref}' already present at: {dest} ({len(existing_files)} file(s))")
        return dest

    print(f"[*] Downloading Kaggle dataset '{dataset_ref}' to: {dest}...")
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        # Download with unzip=False so extraction passes strictly through safe_extract_zip
        api.dataset_download_files(dataset_ref, path=str(dest), unzip=False)
    except Exception as e:
        print(f"[X] Kaggle API download failed: {e}")
        return None

    for z in list(dest.glob("*.zip")):
        try:
            safe_extract_zip(z, dest)
            z.unlink()
        except Exception as ze:
            print(f"[X] Archive extraction rejected for '{z.name}': {ze}")
            return None

    discovered = [f for f in dest.iterdir() if f.suffix.lower() in ['.csv', '.parquet', '.xlsx', '.tsv', '.txt']]
    print(f"[+] Download complete: {len(discovered)} data file(s) extracted.")
    for f in discovered:
        print(f"    - {f.name} ({f.stat().st_size:,} bytes)")

    return dest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Safe Kaggle Dataset Harvester")
    parser.add_argument("pos_slug", nargs="?", default=None, help="Kaggle slug owner/dataset")
    parser.add_argument("pos_dest", nargs="?", default=None, help="Target destination directory")
    parser.add_argument("--slug", dest="flag_slug", default=None, help="Kaggle slug owner/dataset")
    parser.add_argument("--dest", dest="flag_dest", default=None, help="Target destination directory")
    args = parser.parse_args()

    slug = args.flag_slug or args.pos_slug
    out_dir = args.flag_dest or args.pos_dest
    if slug and out_dir:
        download_and_prepare_kaggle_dataset(slug, out_dir)
    else:
        print("Usage: python kaggle_harvester.py --slug <owner/dataset> --dest <target_dir>")
