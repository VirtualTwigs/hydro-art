"""Derive the HUC4 basins covering a U.S. state, for ``REGION_HUC4``/``STATE_HUC4``.

The pipeline maps a region name to concrete NHDPlus HR / WBD downloads through a
hand-maintained state -> HUC4 table (``src.datasets.REGION_HUC4`` and its
``tools/render_common.STATE_HUC4`` mirror). HUC4 watershed basins are shaped by
hydrology, not politics, so they cross state lines and there is no clean lookup
in the repo. This script derives the list *from geometry*: it intersects a state's
Census polygon with the WBD ``WBDHU4`` boundaries and prints every HUC4 that
overlaps, formatted ready to paste into those tables.

Source of the HU4 polygons (in priority order):
  1. ``--wbd-hu4 PATH`` -- an explicit WBD source (a ``*.gdb`` with a ``WBDHU4``
     layer, or a shapefile carrying a ``huc4`` column). Use the national WBD GDB
     to derive *any* state, including ones whose per-HU2 archives aren't local yet.
  2. Otherwise the locally-downloaded WBD GDBs under ``datasets/wbd/`` (``WBD_GLOB``).
     This only covers states whose HU2 archives are already present, so the script
     warns which HU2 regions it actually found.

Like the other ``tools/`` scripts this eagerly imports the heavy GIS stack and
reads real datasets; it does not run in the offline test environment. It must not
be imported by ``src/``.

Examples:
    python tools/derive_state_huc4.py Oregon
    python tools/derive_state_huc4.py California --wbd-hu4 /path/to/WBD_National_GDB.gdb
    python tools/derive_state_huc4.py Nevada --min-overlap-frac 0.01
    python tools/derive_state_huc4.py --all --wbd-hu4 /path/to/WBD_National_GDB.gdb
"""

from __future__ import annotations

import argparse
import glob
import sys

import geopandas as gpd
import pandas as pd

from tools.render_common import EPSG, STATES_SHP, WBD_GLOB

HU4_LAYER = "WBDHU4"


def _resolve_columns(gdf: gpd.GeoDataFrame) -> tuple[str, str | None]:
    """Find the HUC4-code and name columns regardless of source casing."""
    lower = {c.lower(): c for c in gdf.columns}
    code_col = lower.get("huc4") or lower.get("huc_4")
    if code_col is None:
        raise SystemExit(
            f"No HUC4 column found (columns: {list(gdf.columns)}). "
            "Expected a 'huc4' field in the WBD source."
        )
    return code_col, lower.get("name")


def load_hu4(wbd_path: str | None) -> gpd.GeoDataFrame:
    """Load WBD HUC4 polygons (reprojected to ``EPSG``) with ``huc4``/``name`` columns.

    Reads either the explicit ``wbd_path`` source or every local WBD GDB, then
    normalizes the code/name columns so downstream code doesn't care about the
    source's casing or which HU2 archives contributed.
    """
    sources: list[str]
    if wbd_path:
        sources = [wbd_path]
    else:
        sources = sorted(glob.glob(WBD_GLOB, recursive=True))
        if not sources:
            raise SystemExit(
                "No WBD GDBs under datasets/wbd/ and no --wbd-hu4 given. "
                "Point --wbd-hu4 at the national WBD GDB to derive any state."
            )

    frames = []
    for src in sources:
        # A .gdb needs the layer name; a shapefile is read directly.
        read_kwargs = {"layer": HU4_LAYER} if src.rstrip("/").endswith(".gdb") else {}
        try:
            gdf = gpd.read_file(src, **read_kwargs)
        except Exception as exc:  # noqa: BLE001 -- report and skip unreadable sources
            print(f"  skip {src}: {exc}", file=sys.stderr)
            continue
        code_col, name_col = _resolve_columns(gdf)
        keep = gdf[[code_col, "geometry"]].rename(columns={code_col: "huc4"})
        keep["name"] = gdf[name_col].astype(str) if name_col else ""
        frames.append(keep.to_crs(EPSG))

    if not frames:
        raise SystemExit("No readable WBD HUC4 polygons found.")
    hu4 = pd.concat(frames, ignore_index=True)
    hu4 = gpd.GeoDataFrame(hu4, geometry="geometry", crs=EPSG)
    hu4["huc4"] = hu4["huc4"].astype(str).str.zfill(4)
    # Dedup HU4s shared across multiple source GDBs.
    return hu4.drop_duplicates(subset="huc4").reset_index(drop=True)


def load_states() -> gpd.GeoDataFrame:
    """All Census state polygons (NAME + geometry), reprojected to ``EPSG``."""
    st = gpd.read_file(STATES_SHP)
    return st[["NAME", "geometry"]].to_crs(EPSG)


def derive(state_geom, hu4: gpd.GeoDataFrame, min_frac: float) -> list[tuple[str, float]]:
    """Return ``[(huc4, overlap_fraction), ...]`` for basins overlapping ``state_geom``.

    ``overlap_fraction`` is the share of each HUC4's *own* area that falls inside
    the state, so a basin barely clipping the border reports a small fraction and
    can be dropped via ``min_frac`` (default keeps any intersection).
    """
    cand = hu4[hu4.intersects(state_geom)]
    out: list[tuple[str, float]] = []
    for code, geom in zip(cand["huc4"], cand.geometry):
        inter = geom.intersection(state_geom).area
        frac = inter / geom.area if geom.area else 0.0
        if frac >= min_frac:
            out.append((code, frac))
    out.sort(key=lambda t: t[0])
    return out


def _format_tuple(codes: list[str]) -> str:
    return "(" + ", ".join(f'"{c}"' for c in codes) + ")"


def _report_one(name: str, rows: list[tuple[str, float]], hu2_present: set[str]) -> None:
    codes = [c for c, _ in rows]
    print(f"\n{name}: {len(codes)} HUC4 basin(s) overlapping")
    for code, frac in rows:
        note = "" if frac >= 0.02 else "  # border sliver"
        print(f"    {code}  ({frac * 100:5.1f}% of basin in-state){note}")
    print(f'  "{name}": {_format_tuple(codes)},')
    covering_hu2 = {c[:2] for c in codes}
    missing = covering_hu2 - hu2_present
    if missing:
        print(
            f"  WARNING: no local HU4 polygons for HU2 region(s) {sorted(missing)}; "
            "result may be incomplete. Use --wbd-hu4 with the national WBD GDB.",
            file=sys.stderr,
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("state", nargs="?", help="State name (Census NAME), e.g. 'California'.")
    ap.add_argument("--all", action="store_true", help="Derive for every Census state.")
    ap.add_argument(
        "--wbd-hu4",
        default=None,
        help="WBD source for HU4 polygons (national WBD .gdb or a shapefile). "
        "Defaults to the local datasets/wbd/ GDBs.",
    )
    ap.add_argument(
        "--min-overlap-frac",
        type=float,
        default=0.0,
        help="Drop HUC4s whose in-state share of their own area is below this "
        "fraction (default 0.0 = keep any intersection). Try 0.01 to trim slivers.",
    )
    args = ap.parse_args()
    if not args.all and not args.state:
        ap.error("give a state name or --all")

    hu4 = load_hu4(args.wbd_hu4)
    hu2_present = {c[:2] for c in hu4["huc4"]}
    print(
        f"loaded {len(hu4)} HUC4 polygons from HU2 region(s) {sorted(hu2_present)}",
        file=sys.stderr,
    )

    states = load_states()
    if args.all:
        for name in sorted(states["NAME"]):
            geom = states.loc[states["NAME"] == name, "geometry"].iloc[0]
            rows = derive(geom, hu4, args.min_overlap_frac)
            if rows:
                _report_one(name, rows, hu2_present)
    else:
        sel = states[states["NAME"].str.lower() == args.state.strip().lower()]
        if sel.empty:
            raise SystemExit(f"State {args.state!r} not found in {STATES_SHP}.")
        name = sel["NAME"].iloc[0]
        rows = derive(sel.geometry.iloc[0], hu4, args.min_overlap_frac)
        if not rows:
            raise SystemExit(f"No HUC4 basins intersect {name!r} in the loaded WBD source.")
        _report_one(name, rows, hu2_present)


if __name__ == "__main__":
    main()
