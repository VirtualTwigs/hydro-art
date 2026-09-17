"""Bulk-download NHDPlus HR and WBD archives for all supported regions.

Downloads zip archives to the NAS cache directory and extracts GDBs to the
datasets directory. Resumes partial downloads, skips already-extracted basins.

Usage:
    python tools/bulk_download.py --cache-dir /Volumes/home/data/incoming \
        --datasets-dir /Volumes/home/data/hydro-art/datasets
    python tools/bulk_download.py --dry-run   # show what would be downloaded
    python tools/bulk_download.py --download-only  # skip extraction

Requires network access and the NAS mounted. Not part of the offline suite.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

# Allow importing src/ when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.datasets import DATASETS, REGION_HUC4, FileDescriptor


def _resolve_for_regions(regions: list[str]) -> list[FileDescriptor]:
    """Resolve required archives for the given region names."""
    seen: dict[str, FileDescriptor] = {}
    for region in regions:
        huc4s = REGION_HUC4.get(region)
        if not huc4s:
            print(f"WARNING: no HUC4 mapping for {region!r}, skipping",
                  file=sys.stderr)
            continue
        for ds in DATASETS:
            if not ds.required:
                continue
            for huc4 in huc4s:
                code = huc4[: ds.code_digits]
                url = ds.url_template.format(code=code)
                filename = url.rsplit("/", 1)[-1]
                descriptor = FileDescriptor(
                    dataset_id=ds.id,
                    huc4=code,
                    filename=filename,
                    url=url,
                )
                seen.setdefault(descriptor.key, descriptor)
    return list(seen.values())


def _all_descriptors() -> list[FileDescriptor]:
    """Resolve every required archive across all supported regions."""
    return _resolve_for_regions(list(REGION_HUC4))


def _download(url: str, dest: Path, *, resume: bool = True) -> None:
    """Download ``url`` to ``dest`` with optional HTTP Range resume."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    start_byte = 0
    if resume and part.exists():
        start_byte = part.stat().st_size

    req = urllib.request.Request(url)
    if start_byte:
        req.add_header("Range", f"bytes={start_byte}-")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            # If server doesn't support Range, re-download from scratch
            if start_byte and resp.status != 206:
                start_byte = 0
                part.unlink(missing_ok=True)

            total = resp.headers.get("Content-Length")
            total_bytes = int(total) + start_byte if total else None

            mode = "ab" if start_byte else "wb"
            downloaded = start_byte
            with open(part, mode) as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes:
                        pct = downloaded / total_bytes * 100
                        print(
                            f"\r  {downloaded / 1e6:.0f}/{total_bytes / 1e6:.0f} MB "
                            f"({pct:.0f}%)",
                            end="", flush=True,
                        )
            print()  # newline after progress
    except Exception as exc:
        print(f"\n  FAILED: {exc}", file=sys.stderr)
        return

    part.rename(dest)


def _extract(zip_path: Path, target_dir: Path) -> None:
    """Extract a zip archive into ``target_dir``."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cache-dir",
        default="/Volumes/home/data/incoming",
        help="Root for downloaded zip archives (default: NAS incoming).",
    )
    ap.add_argument(
        "--datasets-dir",
        default=None,
        help="Root for extracted GDBs (default: <cache-dir>/../hydro-art/datasets "
        "or repo datasets/).",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be downloaded without fetching.",
    )
    ap.add_argument(
        "--download-only", action="store_true",
        help="Download archives but skip extraction.",
    )
    ap.add_argument(
        "--regions", nargs="*", default=None,
        help="Limit to specific regions (default: all).",
    )
    args = ap.parse_args()

    cache_root = Path(args.cache_dir)
    if args.datasets_dir:
        datasets_root = Path(args.datasets_dir)
    else:
        # Try NAS path first, fall back to local
        nas_ds = cache_root.parent / "hydro-art" / "datasets"
        if nas_ds.exists():
            datasets_root = nas_ds
        else:
            datasets_root = Path("datasets")

    if not args.dry_run and not cache_root.exists():
        print(f"ERROR: cache dir {cache_root} does not exist (NAS not mounted?)",
              file=sys.stderr)
        sys.exit(1)

    # Resolve all needed archives
    if args.regions:
        descriptors = _resolve_for_regions(args.regions)
    else:
        descriptors = _all_descriptors()

    # Separate NHDPlus HR and WBD
    nhdplus = [d for d in descriptors if d.dataset_id == "nhdplus_hr"]
    wbd = [d for d in descriptors if d.dataset_id == "wbd"]

    # Check what's already present
    need_download = []
    already_extracted = []
    already_cached = []

    for d in descriptors:
        cache_path = cache_root / d.dataset_id / d.huc4 / d.filename
        ds_path = datasets_root / d.dataset_id / d.huc4
        if ds_path.exists() and any(ds_path.iterdir()):
            already_extracted.append(d)
        elif cache_path.exists():
            already_cached.append(d)
        else:
            need_download.append(d)

    print(f"Total archives:      {len(descriptors)}")
    print(f"  NHDPlus HR (HU4):  {len(nhdplus)}")
    print(f"  WBD (HU2):         {len(wbd)}")
    print(f"Already extracted:   {len(already_extracted)}")
    print(f"Downloaded (unextracted): {len(already_cached)}")
    print(f"Need to download:    {len(need_download)}")
    print(f"Cache dir:           {cache_root}")
    print(f"Datasets dir:        {datasets_root}")
    print()

    if args.dry_run:
        if need_download:
            print("Would download:")
            for d in need_download:
                print(f"  {d.dataset_id}/{d.huc4}: {d.url}")
        if already_cached and not args.download_only:
            print("\nWould extract:")
            for d in already_cached:
                cache_path = cache_root / d.dataset_id / d.huc4 / d.filename
                print(f"  {cache_path} → {datasets_root / d.dataset_id / d.huc4}")
        return

    # Phase 1: Download
    if need_download:
        print(f"=== Downloading {len(need_download)} archives ===")
        for i, d in enumerate(need_download, 1):
            cache_path = cache_root / d.dataset_id / d.huc4 / d.filename
            print(f"[{i}/{len(need_download)}] {d.dataset_id}/{d.huc4} ({d.filename})")
            t0 = time.monotonic()
            _download(d.url, cache_path)
            elapsed = time.monotonic() - t0
            if cache_path.exists():
                size_mb = cache_path.stat().st_size / 1e6
                print(f"  done ({size_mb:.0f} MB in {elapsed:.0f}s)")
            already_cached.append(d)
        print()

    # Phase 2: Extract
    if args.download_only:
        print("Skipping extraction (--download-only).")
        return

    to_extract = already_cached  # newly downloaded + previously cached but unextracted
    if to_extract:
        print(f"=== Extracting {len(to_extract)} archives ===")
        for i, d in enumerate(to_extract, 1):
            cache_path = cache_root / d.dataset_id / d.huc4 / d.filename
            ds_path = datasets_root / d.dataset_id / d.huc4
            if not cache_path.exists():
                print(f"[{i}/{len(to_extract)}] SKIP {d.dataset_id}/{d.huc4} "
                      f"(archive missing)")
                continue
            print(f"[{i}/{len(to_extract)}] {d.dataset_id}/{d.huc4} → {ds_path}")
            t0 = time.monotonic()
            _extract(cache_path, ds_path)
            elapsed = time.monotonic() - t0
            print(f"  done ({elapsed:.0f}s)")
        print()

    print("=== Summary ===")
    total_ds = 0
    for d in descriptors:
        ds_path = datasets_root / d.dataset_id / d.huc4
        if ds_path.exists() and any(ds_path.iterdir()):
            total_ds += 1
    print(f"Extracted datasets: {total_ds}/{len(descriptors)}")


if __name__ == "__main__":
    main()
