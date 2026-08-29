"""Download & stage PRISM monthly climate GeoTIFFs (ppt, tmean) on the NAS.

Non-offline data-acquisition helper for the year-over-year flow feature (Option
C, roadmap #45). Pulls monthly grids from the NACSE PRISM public web service
(the centralized ``/prism/data/get/us/4km/<var>/<YYYYMM>`` endpoint), unzips the
GeoTIFF, and stages it under ``<root>/prism/<var>/prism_<var>_<YYYYMM>.tif``.

Idempotent/resumable: a month already staged is skipped. Polite: a small pause
between requests. PRISM grids are EPSG:4269 (NAD83 geographic), ~4 km, CONUS.

    python tools/prism_fetch.py --start 2014 --end 2023 \
        --vars ppt tmean --root /Volumes/home/data/hydro-art
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://services.nacse.org/prism/data/get/us/4km"
UA = "hydro-art/1.0 (research; year-over-year flow)"


def staged_path(root: Path, var: str, year: int, month: int) -> Path:
    return root / "prism" / var / f"prism_{var}_{year}{month:02d}.tif"


def fetch_month(root: Path, var: str, year: int, month: int, *,
                pause: float = 0.5) -> tuple[str, Path]:
    """Download one (var, year, month) grid; return (status, path).

    status is 'skip' if already staged, else 'ok'. Raises on HTTP/zip failure.
    """
    out = staged_path(root, var, year, month)
    if out.exists() and out.stat().st_size > 0:
        return "skip", out
    out.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{var}/{year}{month:02d}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        blob = resp.read()
    ctype = ""
    if not blob[:2] == b"PK":  # not a zip -> PRISM returned an HTML message
        raise RuntimeError(f"{var} {year}{month:02d}: non-zip reply "
                           f"({len(blob)}b): {blob[:160]!r}")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        tif = next((n for n in zf.namelist() if n.endswith(".tif")), None)
        if tif is None:
            raise RuntimeError(f"{var} {year}{month:02d}: no .tif in zip "
                               f"({zf.namelist()})")
        tmp = out.with_suffix(".tif.part")
        tmp.write_bytes(zf.read(tif))
        tmp.replace(out)
    time.sleep(pause)
    return "ok", out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--vars", nargs="+", default=["ppt", "tmean"])
    ap.add_argument("--root", default="/Volumes/home/data/hydro-art",
                    help="External root; grids go under <root>/prism/<var>/.")
    ap.add_argument("--pause", type=float, default=0.5)
    args = ap.parse_args()

    root = Path(args.root)
    years = range(args.start, args.end + 1)
    total = len(args.vars) * len(list(years)) * 12
    done = 0
    ok = skip = 0
    for var in args.vars:
        for year in years:
            for month in range(1, 13):
                done += 1
                try:
                    status, path = fetch_month(root, var, year, month,
                                               pause=args.pause)
                except Exception as exc:  # noqa: BLE001 - report & continue
                    print(f"[{done}/{total}] FAIL {var} {year}-{month:02d}: {exc}",
                          flush=True)
                    continue
                if status == "skip":
                    skip += 1
                else:
                    ok += 1
                    print(f"[{done}/{total}] {status} {var} {year}-{month:02d} "
                          f"-> {path.name} ({path.stat().st_size} b)", flush=True)
    print(f"done: {ok} downloaded, {skip} already staged, "
          f"{total - ok - skip} failed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
