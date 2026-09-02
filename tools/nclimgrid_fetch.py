"""Download & stage NOAA nClimGrid-Monthly climate NetCDFs (prcp, tavg) on the NAS.

License-free counterpart to ``tools/prism_fetch.py`` (roadmap #60). nClimGrid is
**U.S. federal public domain** (free to sell with attribution) — the direct PRISM
equivalent: monthly ``prcp`` (mm) + ``tavg`` (degC), ~5 km, CONUS, record from
January 1895.

Unlike PRISM's one-GeoTIFF-per-month layout, nClimGrid ships as **two stacked
NetCDF files** (each ~1-1.5 GB) with a monthly ``time`` axis, so this fetches two
whole files rather than a grid per month. Pulls from the NCEI HTTPS access endpoint
(NODD/Azure blob as a fallback), streams to a ``.part`` temp, then atomically
renames into ``<root>/nclimgrid/nclimgrid_<var>.nc``.

Idempotent/resumable: a file already staged with non-zero size is skipped. Prints
staged path + byte size per file.

    python tools/nclimgrid_fetch.py --vars prcp tavg \
        --root /Volumes/home/data/hydro-art

Attribution to stamp on sold assets:
    "Climate data: NOAA NCEI nClimGrid-Monthly (public domain)."
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

# Primary: NCEI direct HTTPS access. Fallback: NOAA Open Data (Azure blob).
NCEI_BASE = "https://www.ncei.noaa.gov/data/nclimgrid-monthly/access"
AZURE_BASE = "https://nclimgrideastus.blob.core.windows.net/nclimgrid/nclimgrid-monthly"
UA = "hydro-art/1.0 (research; license-free year-over-year flow)"


def staged_path(root: Path, var: str) -> Path:
    return root / "nclimgrid" / f"nclimgrid_{var}.nc"


def source_urls(var: str) -> list[str]:
    return [f"{NCEI_BASE}/nclimgrid_{var}.nc", f"{AZURE_BASE}/nclimgrid_{var}.nc"]


def fetch_var(root: Path, var: str) -> tuple[str, Path]:
    """Download one variable's NetCDF; return (status, path).

    status is 'skip' if already staged, else 'ok'. Streams to a ``.part`` temp and
    atomically renames. Tries each source URL in turn.
    """
    out = staged_path(root, var)
    if out.exists() and out.stat().st_size > 0:
        return "skip", out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".nc.part")
    last_err: Exception | None = None
    for url in source_urls(var):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as resp, \
                    open(tmp, "wb") as fh:
                expected = resp.headers.get("Content-Length")
                expected = int(expected) if expected else None
                shutil.copyfileobj(resp, fh, length=1 << 20)
            got = tmp.stat().st_size
            if got == 0:
                raise RuntimeError("empty download")
            # A dropped connection yields a short file with no exception; verify the
            # byte count against Content-Length so a truncated NetCDF never stages.
            if expected is not None and got != expected:
                raise RuntimeError(
                    f"truncated download: got {got} of {expected} bytes"
                )
            tmp.replace(out)
            return "ok", out
        except Exception as exc:  # noqa: BLE001 - try next mirror
            last_err = exc
            if tmp.exists():
                tmp.unlink()
            continue
    raise RuntimeError(f"all sources failed for {var}: {last_err}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vars", nargs="+", default=["prcp", "tavg"])
    ap.add_argument("--root", default="/Volumes/home/data/hydro-art",
                    help="External root; files go under <root>/nclimgrid/.")
    args = ap.parse_args()

    root = Path(args.root)
    ok = skip = fail = 0
    for var in args.vars:
        try:
            status, path = fetch_var(root, var)
        except Exception as exc:  # noqa: BLE001 - report & continue
            print(f"FAIL {var}: {exc}", flush=True)
            fail += 1
            continue
        if status == "skip":
            skip += 1
            print(f"skip {var} -> {path} ({path.stat().st_size} b)", flush=True)
        else:
            ok += 1
            print(f"ok   {var} -> {path} ({path.stat().st_size} b)", flush=True)
    print(f"done: {ok} downloaded, {skip} already staged, {fail} failed", flush=True)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
