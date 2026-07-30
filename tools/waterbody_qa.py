"""Real-region waterbody QA (Item W4, Task Group 4 — real-data slice).

Runs the *same* classification + selection code the pipeline uses
(:mod:`src.waterbodies` + :mod:`src.waterbody_selection`) against real NHD
waterbody/area polygons, then prints a QA report that cross-checks the
:class:`~src.waterbody_selection.WaterbodySelection`: class counts, holes,
multipolygons, coastal kept-vs-dropped, duplicate-geometry drops, shared-edge
pairs, and source-id traceability. This validates the acceptance criteria that
the offline fixture suite can only prove on hand-built geometry.

It reads real .gdb datasets and imports GDAL-backed libraries eagerly, so it
lives outside the offline test suite (needs the NAS-cached datasets mounted).

    # Clip to a US state polygon (same shapefile as render_region_clip.py):
    python tools/waterbody_qa.py --state Oregon
    python tools/waterbody_qa.py --state Washington

    # No political clip — QA every waterbody in the given basin(s):
    python tools/waterbody_qa.py --gdb-glob 'datasets/nhdplus_hr/1708/*.gdb' --no-clip

Clark County, WA (needs a county shapefile; pass its path + the county name):
    python tools/waterbody_qa.py --county-shp /tmp/counties.shp \
        --county "Clark" --state-fp 53
"""

from __future__ import annotations

import argparse
import glob
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
from pyogrio import list_layers

from src.loading import (
    WATERBODY_ATTRIBUTE_FIELDS,
    discover_waterbody_layers,
)
from src.waterbodies import classify_waterbody
from src.waterbody_selection import (
    COASTAL_CLASSES,
    WaterbodySelectionPolicy,
    process_waterbodies,
)

EPSG = "EPSG:5070"
GDB_GLOB = "datasets/nhdplus_hr/17*/*.gdb"
STATES_SHP = "/tmp/states_shp/cb_2023_us_state_500k.shp"


def load_state_boundary(name: str) -> Any:
    """Return a state polygon in EPSG:5070 from the Census states shapefile."""
    st = gpd.read_file(STATES_SHP)
    return st[st.NAME == name].to_crs(EPSG).geometry.iloc[0]


def load_county_boundary(shp: str, name: str, state_fp: str | None) -> Any:
    """Return a county polygon in EPSG:5070 by NAME (optionally scoped to STATEFP)."""
    cty = gpd.read_file(shp)
    sel = cty[cty.NAME == name]
    if state_fp is not None and "STATEFP" in cty.columns:
        sel = sel[sel.STATEFP == str(state_fp)]
    if sel.empty:
        raise SystemExit(f"county {name!r} (state_fp={state_fp}) not found in {shp}")
    return sel.to_crs(EPSG).geometry.iloc[0]


def _attrs_for_row(row: Any) -> dict:
    """Pull the classification attribute subset from a GeoDataFrame row."""
    attrs: dict = {}
    for field in WATERBODY_ATTRIBUTE_FIELDS:
        if field in row and row[field] is not None:
            attrs[field] = row[field]
    return attrs


def load_features(gdb_glob: str) -> list:
    """Classify every waterbody/area polygon under ``gdb_glob`` (in EPSG:5070)."""
    features: list = []
    for gdb in sorted(glob.glob(gdb_glob)):
        huc4 = Path(gdb).parent.name
        available = [str(row[0]) for row in list_layers(gdb)]
        selected = discover_waterbody_layers(available)
        if not selected:
            print(f"  {huc4}: no waterbody layers (saw {available})")
            continue
        for name in selected:
            try:
                frame = gpd.read_file(gdb, layer=name).to_crs(EPSG)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {huc4}/{name}: {exc}")
                continue
            n = 0
            for _, row in frame.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                features.append(
                    classify_waterbody(
                        _attrs_for_row(row),
                        source_layer=name,
                        dataset_id="nhdplus_hr",
                        huc4=huc4,
                        geometry=geom,
                        source_crs=EPSG,
                    )
                )
                n += 1
            print(f"  {huc4}/{name}: {n} polygon(s)")
    return features


def _hole_count(geom: Any) -> int:
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return sum(len(p.interiors) for p in polys)


def report(selection) -> None:
    sel = selection.selected
    exc = selection.excluded
    print("\n=== Waterbody QA report ===")
    print(f"policy version:  {selection.policy_version}")
    print(f"candidates:      {selection.counts['candidates']}")
    print(f"selected:        {selection.counts['selected']}")
    print(f"excluded:        {selection.counts['excluded']}")
    print(f"by class:        {selection.counts['by_class']}")

    with_holes = [f for f in sel if _hole_count(f.geometry) > 0]
    total_holes = sum(_hole_count(f.geometry) for f in sel)
    multipart = [f for f in sel if f.geometry.geom_type == "MultiPolygon"]
    coastal_kept = [f for f in sel if f.wb_class in COASTAL_CLASSES]
    print(f"\nholes:           {total_holes} across {len(with_holes)} feature(s)")
    print(f"multipolygons:   {len(multipart)} selected feature(s)")
    print(f"coastal kept:    {len(coastal_kept)} ({sorted({f.wb_class for f in coastal_kept})})")

    # Excluded-reason histogram (reason prefix before the first ':').
    reasons = Counter(f.inclusion_reason.split(":")[0].strip() for f in exc)
    coastal_frag = sum(
        1 for f in exc if "coastal clip-boundary fragment" in f.inclusion_reason
    )
    dup = sum(1 for f in exc if "duplicate geometry" in f.inclusion_reason)
    print(f"\ncoastal fragments dropped: {coastal_frag}")
    print(f"duplicate geometries dropped: {dup}")
    print(f"shared-edge pairs: {selection.shared_edge_pairs}")
    shared_flagged = sum(1 for f in sel if "shared_edge" in f.qa_flags)
    print(f"shared-edge features flagged: {shared_flagged}")
    print("\nexcluded reasons:")
    for reason, count in reasons.most_common():
        print(f"  {count:5d}  {reason}")

    # Source traceability: every selected feature should carry a source id.
    untraceable = [f for f in sel if not f.source_id]
    if untraceable:
        print(f"\nWARNING: {len(untraceable)} selected feature(s) have no source_id")
    else:
        print("\nall selected features carry a source id (traceable)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gdb-glob", default=GDB_GLOB)
    ap.add_argument("--state", default=None, help="Clip to this US state polygon.")
    ap.add_argument("--county-shp", default=None, help="County shapefile path.")
    ap.add_argument("--county", default=None, help="County NAME to clip to.")
    ap.add_argument("--state-fp", default=None, help="STATEFP to disambiguate county.")
    ap.add_argument("--no-clip", action="store_true", help="Skip political clipping.")
    ap.add_argument("--min-inland-area-m2", type=float, default=0.0)
    ap.add_argument("--min-coastal-area-m2", type=float, default=0.0)
    ap.add_argument(
        "--coastal-mode", default="conservative",
        choices=["conservative", "permissive"],
    )
    args = ap.parse_args()

    boundary = None
    if not args.no_clip:
        if args.county:
            if not args.county_shp:
                raise SystemExit("--county requires --county-shp")
            print(f"loading county boundary {args.county!r} ...")
            boundary = load_county_boundary(args.county_shp, args.county, args.state_fp)
        elif args.state:
            print(f"loading state boundary {args.state!r} ...")
            boundary = load_state_boundary(args.state)
        else:
            raise SystemExit("give --state/--county or pass --no-clip")

    print(f"loading + classifying waterbodies from {args.gdb_glob} ...")
    features = load_features(args.gdb_glob)
    print(f"classified {len(features)} candidate polygon(s)")

    policy = WaterbodySelectionPolicy(
        min_inland_area_m2=args.min_inland_area_m2,
        min_coastal_area_m2=args.min_coastal_area_m2,
        coastal_mode=args.coastal_mode,
    )
    selection = process_waterbodies(features, boundary=boundary, policy=policy)
    report(selection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
