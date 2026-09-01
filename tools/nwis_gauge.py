"""USGS NWIS gauge provider — observed monthly-mean discharge (roadmap #50).

Non-offline data-acquisition helper for the watershed-report validation section.
The pure comparison metrics live in ``src/flow_validation.py`` (offline, numpy
only); this script supplies the *observed* side of that comparison: it fetches
daily-mean discharge (parameter ``00060``, statistic ``00003`` = mean, in cfs)
from the USGS NWIS "dv" web service, aggregates to a monthly mean, and returns a
``{year: [12]}`` observed series aligned to the report years.

Reproducibility, the Epoch 8/10 lesson: the raw NWIS response is **snapshotted**
to the NAS (``<root>/nwis/<site>/dv_00060_<start>_<end>.rdb`` + a small manifest),
so a re-run is offline and byte-stable — the parse always runs off the local
snapshot, never a fresh network read, once staged.

    # Salmon Creek near Battle Ground, WA (site 14212000 — the basin's gauge;
    # daily-discharge period of record 1943-10-01..1990-05-10, discontinued 1990,
    # so the honest model-vs-gauge overlap is the water-year span 1944..1989):
    python -m tools.nwis_gauge --site 14212000 --start 1944 --end 1989

Heavy network/parsing lives here (a ``tools/`` script), never in ``src/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_ROOT = "/Volumes/home/data/hydro-art"
NWIS_DV = "https://waterservices.usgs.gov/nwis/dv/"
NWIS_SITE = "https://waterservices.usgs.gov/nwis/site/"
UA = "hydro-art/1.0 (research; watershed report validation)"
PARAM = "00060"   # discharge, cubic feet per second
STAT = "00003"    # daily mean


def snapshot_path(root: Path, site: str, start: int, end: int) -> Path:
    return root / "nwis" / site / f"dv_{PARAM}_{start}_{end}.rdb"


def site_snapshot_path(root: Path, site: str) -> Path:
    return root / "nwis" / site / "site.rdb"


def fetch_rdb(site: str, start: int, end: int, *, timeout: int = 120) -> str:
    """Fetch the NWIS daily-values RDB table for a site over [start, end]."""
    url = (f"{NWIS_DV}?format=rdb&sites={site}&parameterCd={PARAM}"
           f"&statCd={STAT}&startDT={start}-01-01&endDT={end}-12-31")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def ensure_snapshot(root: Path, site: str, start: int, end: int) -> Path:
    """Stage the raw RDB + a manifest once; reuse it on every later run."""
    out = snapshot_path(root, site, start, end)
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    rdb = fetch_rdb(site, start, end)
    tmp = out.with_suffix(".rdb.part")
    tmp.write_text(rdb, encoding="utf-8")
    tmp.replace(out)
    manifest = {
        "site": site, "param": PARAM, "stat": STAT,
        "start": start, "end": end, "bytes": out.stat().st_size,
        "source": NWIS_DV,
    }
    out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return out


def fetch_site_rdb(site: str, *, timeout: int = 120) -> str:
    """Fetch the NWIS site-description RDB table (carries the site lat/lon)."""
    url = f"{NWIS_SITE}?format=rdb&sites={site}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def ensure_site_snapshot(root: Path, site: str) -> Path:
    """Stage the raw site RDB + a manifest once; reuse it on every later run."""
    out = site_snapshot_path(root, site)
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    rdb = fetch_site_rdb(site)
    tmp = out.with_suffix(".rdb.part")
    tmp.write_text(rdb, encoding="utf-8")
    tmp.replace(out)
    manifest = {"site": site, "bytes": out.stat().st_size, "source": NWIS_SITE}
    out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return out


def parse_site_rdb(text: str) -> tuple[float, float, str]:
    """Parse an NWIS site RDB table -> (lat, lon, horizontal-datum code).

    The columns of interest are ``dec_lat_va`` / ``dec_long_va`` (decimal degrees)
    and ``dec_coord_datum_cd`` (e.g. ``NAD83``). ``#`` comment lines, a header row,
    and the RDB format-spec row are skipped; the first data row wins.
    """
    header: list[str] | None = None
    saw_format_line = False
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cells = line.split("\t")
        if header is None:
            header = cells
            continue
        if not saw_format_line:
            saw_format_line = True
            continue
        row = dict(zip(header, cells))
        try:
            lat = float(row["dec_lat_va"])
            lon = float(row["dec_long_va"])
        except (KeyError, ValueError):
            continue
        datum = (row.get("dec_coord_datum_cd") or "NAD83").strip() or "NAD83"
        return lat, lon, datum
    raise ValueError("no decimal lat/lon row found in NWIS site RDB")


def parse_rdb(text: str) -> tuple[str, dict[int, np.ndarray]]:
    """Parse an NWIS dv RDB table -> (site_name, {year: [12] monthly means}).

    RDB is tab-separated: ``#`` comment lines (the site name lives here), then a
    column-header line, a format line (``5s 15s ...``, skipped), then data rows.
    The discharge column is the one whose name ends ``_00060_00003``. Months with
    no observations stay ``nan`` (skipped downstream, never zero-filled).
    """
    site_name = ""
    header: list[str] | None = None
    saw_format_line = False
    value_col = -1
    date_col = -1
    # year -> month(0-11) -> [sum, count] for a daily->monthly mean
    acc: dict[int, list[list[float]]] = {}
    for line in text.splitlines():
        if line.startswith("#"):
            # e.g. "#    USGS 14211550 SALMON CREEK NEAR BATTLE GROUND, WA"
            if "USGS" in line and any(ch.isdigit() for ch in line):
                site_name = line.lstrip("#").strip()
            continue
        if not line.strip():
            continue
        cells = line.split("\t")
        if header is None:
            header = cells
            date_col = header.index("datetime") if "datetime" in header else 2
            for i, name in enumerate(header):
                if name.endswith(f"_{PARAM}_{STAT}"):
                    value_col = i
                    break
            continue
        if not saw_format_line:
            saw_format_line = True  # the RDB format-spec row ("5s\t15s\t...")
            continue
        if value_col < 0 or len(cells) <= max(value_col, date_col):
            continue
        date = cells[date_col]
        raw = cells[value_col].strip()
        if not raw or len(date) < 7:
            continue
        try:
            year = int(date[:4])
            month = int(date[5:7])
            val = float(raw)
        except ValueError:
            continue
        acc.setdefault(year, [[0.0, 0.0] for _ in range(12)])
        acc[year][month - 1][0] += val
        acc[year][month - 1][1] += 1.0

    series: dict[int, np.ndarray] = {}
    for year, months in acc.items():
        row = np.full(12, np.nan)
        for m, (total, count) in enumerate(months):
            if count > 0:
                row[m] = total / count
        series[year] = row
    return site_name, series


class GaugeProvider:
    """Observed monthly-mean discharge for one NWIS site, snapshot-backed."""

    def __init__(self, site: str, root: str | Path = DEFAULT_ROOT) -> None:
        self.site = str(site)
        self.root = Path(root)
        self.name = ""

    def monthly_means(self, start: int, end: int) -> dict[int, np.ndarray]:
        """Return ``{year: [12]}`` observed means (nan where a month is missing)."""
        snap = ensure_snapshot(self.root, self.site, start, end)
        self.name, series = parse_rdb(snap.read_text(encoding="utf-8"))
        return {y: series[y] for y in range(start, end + 1) if y in series}

    def location(self) -> tuple[float, float, str]:
        """Return the gauge's ``(lat, lon, horizontal-datum code)`` (snapshotted).

        Used to snap the model-vs-gauge comparison to the reach *at the gauge*
        rather than the watershed outlet (the outlet is the basin mouth, a much
        larger drainage than a mid-watershed gauge — an apples-to-oranges match).
        """
        snap = ensure_site_snapshot(self.root, self.site)
        return parse_site_rdb(snap.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="14212000",
                    help="USGS NWIS site id (default: 14212000 Salmon Creek nr "
                         "Battle Ground, WA; dv discharge 1943-10..1990-05).")
    ap.add_argument("--start", type=int, default=1944)
    ap.add_argument("--end", type=int, default=1989)
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="External root; snapshot goes under <root>/nwis/<site>/.")
    args = ap.parse_args()

    prov = GaugeProvider(args.site, args.root)
    series = prov.monthly_means(args.start, args.end)
    print(f"site {args.site}: {prov.name or '(name not found in RDB header)'}")
    if not series:
        print("no observations returned for the requested span.")
        return 1
    print(f"period returned: {min(series)}..{max(series)} "
          f"({len(series)} years with data)")
    for y in sorted(series):
        row = series[y]
        n = int(np.isfinite(row).sum())
        annual = float(np.nanmean(row)) if n else float("nan")
        print(f"  {y}: {n}/12 months, annual mean {annual:,.1f} cfs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
