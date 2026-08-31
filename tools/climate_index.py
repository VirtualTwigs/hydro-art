"""Climate-index provider — ENSO ONI / PDO annual series (roadmap #51).

Non-offline data-acquisition helper for the watershed-report teleconnection
section. The pure correlation metrics live in ``src/flow_validation.py``
(offline, numpy only) — ``align_index`` / ``correlate``; this script supplies the
*index* side of that join: it fetches a monthly climate index, aggregates to an
annual mean, and returns a ``{year: value}`` mapping ready to correlate against a
per-year flow metric (e.g. Salmon Creek annual peak flow).

Two indices are supported:

* ``oni`` — ENSO Oceanic Niño Index (NOAA CPC 3-month running SST anomaly). The
  annual value is the mean of that year's overlapping 3-month ONI seasons.
* ``pdo`` — Pacific Decadal Oscillation (NOAA NCEI ERSST v5). The annual value is
  the mean of that year's valid monthly values (the ``99.99`` fill is skipped,
  never averaged in).

Reproducibility, the Epoch 8/10 lesson: the raw upstream table is **snapshotted**
to the NAS (``<root>/climate/<index>/<index>.txt`` + a small manifest), so a
re-run is offline and byte-stable — the parse always runs off the local snapshot,
never a fresh network read, once staged.

    python -m tools.climate_index --index oni --start 1944 --end 1989
    python -m tools.climate_index --index pdo --start 1944 --end 1989

Heavy network/parsing lives here (a ``tools/`` script), never in ``src/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_ROOT = "/Volumes/home/data/hydro-art"
UA = "hydro-art/1.0 (research; watershed report teleconnection)"

SOURCES = {
    "oni": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "pdo": "https://www.ncei.noaa.gov/pub/data/cmb/ersst/v5/index/ersst.v5.pdo.dat",
}
PDO_FILL = 99.99   # NCEI ERSST PDO missing-month sentinel (also -9.9 in old files)


def snapshot_path(root: Path, index: str) -> Path:
    return root / "climate" / index / f"{index}.txt"


def fetch_text(index: str, *, timeout: int = 120) -> str:
    """Fetch the raw upstream index table."""
    url = SOURCES[index]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def ensure_snapshot(root: Path, index: str) -> Path:
    """Stage the raw table + a manifest once; reuse it on every later run."""
    out = snapshot_path(root, index)
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    text = fetch_text(index)
    tmp = out.with_suffix(".txt.part")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    manifest = {
        "index": index, "bytes": out.stat().st_size, "source": SOURCES[index],
    }
    out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def parse_oni(text: str) -> dict[int, float]:
    """Parse the CPC ONI table -> {year: mean seasonal anomaly}.

    Columns are ``SEAS YR TOTAL ANOM``; a header row (``SEAS``) is skipped. Each
    year's value is the mean of its overlapping 3-month ONI anomalies.
    """
    acc: dict[int, list[float]] = {}
    for line in text.splitlines():
        cells = line.split()
        if len(cells) != 4 or cells[0] == "SEAS":
            continue
        try:
            year = int(cells[1])
            anom = float(cells[3])
        except ValueError:
            continue
        acc.setdefault(year, []).append(anom)
    return {y: _mean(v) for y, v in acc.items() if v}


def parse_pdo(text: str) -> dict[int, float]:
    """Parse the NCEI ERSST PDO table -> {year: mean valid monthly value}.

    Rows are ``Year Jan..Dec``; header/title lines are skipped. The ``99.99``
    (and legacy ``-9.9``) fill months are dropped, never averaged in — a year
    with no valid month is omitted entirely (never zero-filled).
    """
    acc: dict[int, float] = {}
    for line in text.splitlines():
        cells = line.split()
        if not cells or not cells[0].lstrip("-").isdigit():
            continue
        try:
            year = int(cells[0])
        except ValueError:
            continue
        months: list[float] = []
        for cell in cells[1:13]:
            try:
                val = float(cell)
            except ValueError:
                continue
            if abs(val - PDO_FILL) < 1e-6 or abs(val - (-9.9)) < 1e-6:
                continue
            months.append(val)
        if months:
            acc[year] = _mean(months)
    return acc


PARSERS = {"oni": parse_oni, "pdo": parse_pdo}


class ClimateIndexProvider:
    """Annual climate-index series for one index, snapshot-backed."""

    def __init__(self, index: str, root: str | Path = DEFAULT_ROOT) -> None:
        if index not in SOURCES:
            raise ValueError(f"unknown index {index!r}; choose from {sorted(SOURCES)}")
        self.index = index
        self.root = Path(root)

    def index_by_year(
        self, start: int | None = None, end: int | None = None
    ) -> dict[int, float]:
        """Return ``{year: annual value}``, optionally clipped to [start, end]."""
        snap = ensure_snapshot(self.root, self.index)
        series = PARSERS[self.index](snap.read_text(encoding="utf-8"))
        if start is not None:
            series = {y: v for y, v in series.items() if y >= start}
        if end is not None:
            series = {y: v for y, v in series.items() if y <= end}
        return series


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", default="oni", choices=sorted(SOURCES),
                    help="Climate index to fetch (default: oni).")
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="External root; snapshot goes under <root>/climate/<index>/.")
    args = ap.parse_args()

    prov = ClimateIndexProvider(args.index, args.root)
    series = prov.index_by_year(args.start, args.end)
    if not series:
        print(f"{args.index}: no values in the requested span.")
        return 1
    print(f"{args.index}: {min(series)}..{max(series)} "
          f"({len(series)} years)")
    for y in sorted(series):
        print(f"  {y}: {series[y]:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
