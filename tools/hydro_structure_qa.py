"""Real-region engineered-structure QA (Epoch 16, Item #68 — real-data slice).

Runs the *same* classification + selection code the pipeline uses
(:mod:`src.hydro_structures` + :mod:`src.hydro_structure_selection`) against real
NHD engineered-water infrastructure (``NHDLine`` / ``NHDPoint`` / ``NHDArea``),
then folds the selected structures through the offline QA module
(:mod:`src.hydro_structure_qa`) against the real flowline network and the natural
water taxonomy, printing the three infrastructure-QA verdicts the fixture suite
can only prove on hand-built geometry:

* **on-network placement** — median/max nearest-flowline distance, off-network
  count (is a dam on its channel, a gaging station on its reach?);
* **cross-layer duplicate groups** — the same real-world structure classified
  from two source layers (e.g. a dam as both an ``NHDLine`` and an ``NHDArea``);
* **canal / natural separation** — no structure double-draws a natural feature.

Plus per-class selected counts and source-id traceability.

It reads real .gdb datasets and imports GDAL-backed libraries eagerly, so it
lives outside the offline test suite (needs the NAS-cached datasets mounted).
Mirrors :mod:`tools.waterbody_qa` exactly (same CLI shape).

    # Clip to a US state polygon (same shapefile as render_region_clip.py):
    python tools/hydro_structure_qa.py --state Oregon
    python tools/hydro_structure_qa.py --state Washington

    # No political clip — QA every structure in the given basin(s):
    python tools/hydro_structure_qa.py \
        --gdb-glob 'datasets/nhdplus_hr/1807/*.gdb' --no-clip

Clark County, WA (needs a county shapefile; pass its path + the county name):
    python tools/hydro_structure_qa.py --county-shp /tmp/counties.shp \
        --county "Clark" --state-fp 53
"""

from __future__ import annotations

import argparse
import glob
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
from pyogrio import list_layers

from src.areal_features import classify_areal_feature
from src.hydro_structure_qa import build_qa_report
from src.hydro_structure_selection import (
    HydroStructureSelectionPolicy,
    process_hydro_structures,
)
from src.hydro_structures import (
    HYDRO_STRUCTURE_FTYPE_LABELS,
    classify_hydro_structure,
)
from src.loading import (
    LINE_ATTRIBUTE_FIELDS,
    POINT_ATTRIBUTE_FIELDS,
    WATERBODY_ATTRIBUTE_FIELDS,
    discover_line_layers,
    discover_point_layers,
    discover_waterbody_layers,
)
from src.point_features import classify_point_feature
from src.waterbodies import classify_waterbody

EPSG = "EPSG:5070"
GDB_GLOB = "datasets/nhdplus_hr/17*/*.gdb"
STATES_SHP = "/tmp/states_shp/cb_2023_us_state_500k.shp"

#: NHD structure source layers, in the order the report lists them.
STRUCTURE_LAYERS: tuple[str, ...] = ("NHDLine", "NHDPoint", "NHDArea")

#: On-network tolerance (m, EPSG:5070) — a structure within this of a flowline is
#: counted "on the network". 250 m is generous enough to absorb the offset
#: between an area/point structure centroid and the reach it governs while still
#: flagging genuinely floating features.
DEFAULT_TOLERANCE_M = 250.0

#: Cross-layer duplicate proximity (m) — a dam present on both NHDLine and
#: NHDArea sits within this distance; two distinct dams do not.
DEFAULT_DUP_TOLERANCE_M = 150.0


@dataclass(frozen=True)
class _NaturalFeature:
    """Minimal natural-taxonomy record the QA separation check needs.

    :func:`src.hydro_structure_qa.canal_natural_separation` only reads
    ``.geometry`` and ``.source_id``, so we adapt every natural family
    (waterbodies / areal / points) into this common shape.
    """

    source_id: str
    geometry: Any
    kind: str


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


def _attrs_for_row(row: Any, fields: tuple[str, ...]) -> dict:
    """Pull a classification attribute subset from a GeoDataFrame row."""
    attrs: dict = {}
    for field in fields:
        if field in row and row[field] is not None:
            attrs[field] = row[field]
    return attrs


def load_structures(gdb_glob: str) -> list:
    """Classify every engineered structure under ``gdb_glob`` (in EPSG:5070).

    Reads all three structure-bearing layers (``NHDLine``/``NHDPoint``/
    ``NHDArea``) and classifies each row through the *same* pipeline classifier;
    the ``excluded`` outcomes (open water, natural areal, etc.) are kept here so
    selection accounts for every candidate, matching :mod:`tools.waterbody_qa`.
    """
    features: list = []
    for gdb in sorted(glob.glob(gdb_glob)):
        huc4 = Path(gdb).parent.name
        available = [str(row[0]) for row in list_layers(gdb)]
        line = set(discover_line_layers(available))
        point = set(discover_point_layers(available))
        # NHDArea comes from the waterbody allowlist; NHDWaterbody is polygon-only
        # water, never a structure, so keep only NHDArea for structures.
        area = {n for n in discover_waterbody_layers(available) if n == "NHDArea"}
        selected = [n for n in STRUCTURE_LAYERS if n in (line | point | area)]
        if not selected:
            print(f"  {huc4}: no structure layers (saw {available})")
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
                    classify_hydro_structure(
                        _attrs_for_row(row, LINE_ATTRIBUTE_FIELDS),
                        source_layer=name,
                        dataset_id="nhdplus_hr",
                        huc4=huc4,
                        geometry=geom,
                        source_crs=EPSG,
                    )
                )
                n += 1
            print(f"  {huc4}/{name}: {n} geometry(ies)")
    return features


def load_flowlines(gdb_glob: str, boundary: Any | None) -> list:
    """Return NHDFlowline geometries (EPSG:5070), clipped to ``boundary`` if set."""
    lines: list = []
    for gdb in sorted(glob.glob(gdb_glob)):
        huc4 = Path(gdb).parent.name
        try:
            frame = gpd.read_file(gdb, layer="NHDFlowline", columns=[]).to_crs(EPSG)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip flowlines {huc4}: {exc}")
            continue
        kept = 0
        for geom in frame.geometry.values:
            if geom is None or geom.is_empty:
                continue
            if boundary is not None:
                if not geom.intersects(boundary):
                    continue
                if not boundary.covers(geom):
                    geom = geom.intersection(boundary)
                    if geom.is_empty:
                        continue
            lines.append(geom)
            kept += 1
        print(f"  {huc4}/NHDFlowline: {kept} reach(es)")
    return lines


def load_natural_features(gdb_glob: str, boundary: Any | None) -> list:
    """Classify the natural-water taxonomy (waterbodies + areal + points).

    Only non-``excluded`` natural features are returned, each adapted into a
    :class:`_NaturalFeature`. These are what the canal/natural separation check
    asserts structures stay disjoint from. Geometries are clipped to ``boundary``.
    """
    naturals: list[_NaturalFeature] = []

    def _clip(geom: Any) -> Any | None:
        if boundary is None:
            return geom
        if not geom.intersects(boundary):
            return None
        if boundary.covers(geom):
            return geom
        clipped = geom.intersection(boundary)
        return None if clipped.is_empty else clipped

    for gdb in sorted(glob.glob(gdb_glob)):
        huc4 = Path(gdb).parent.name
        available = [str(row[0]) for row in list_layers(gdb)]

        # Waterbody polygons (NHDWaterbody + NHDArea) + areal natural features.
        for name in discover_waterbody_layers(available):
            try:
                frame = gpd.read_file(gdb, layer=name).to_crs(EPSG)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {huc4}/{name}: {exc}")
                continue
            for _, row in frame.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                attrs = _attrs_for_row(row, WATERBODY_ATTRIBUTE_FIELDS)
                wb = classify_waterbody(
                    attrs, source_layer=name, dataset_id="nhdplus_hr",
                    huc4=huc4, geometry=geom, source_crs=EPSG,
                )
                ar = classify_areal_feature(
                    attrs, source_layer=name, dataset_id="nhdplus_hr",
                    huc4=huc4, geometry=geom, source_crs=EPSG,
                )
                if wb.wb_class != "excluded":
                    clipped = _clip(geom)
                    if clipped is not None:
                        naturals.append(
                            _NaturalFeature(wb.source_id, clipped, wb.wb_class)
                        )
                elif ar.ar_class != "excluded":
                    clipped = _clip(geom)
                    if clipped is not None:
                        naturals.append(
                            _NaturalFeature(ar.source_id, clipped, ar.ar_class)
                        )

        # Natural point features (springs / waterfalls / rapids).
        for name in discover_point_layers(available):
            try:
                frame = gpd.read_file(gdb, layer=name).to_crs(EPSG)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {huc4}/{name}: {exc}")
                continue
            for _, row in frame.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                pt = classify_point_feature(
                    _attrs_for_row(row, POINT_ATTRIBUTE_FIELDS),
                    source_layer=name, dataset_id="nhdplus_hr",
                    huc4=huc4, geometry=geom, source_crs=EPSG,
                )
                if pt.pt_class == "excluded":
                    continue
                clipped = _clip(geom)
                if clipped is not None:
                    naturals.append(
                        _NaturalFeature(pt.source_id, clipped, pt.pt_class)
                    )
    return naturals


def report(
    selection,
    qa,
    *,
    tolerance_m: float,
    dup_tolerance_m: float,
    candidates: int,
    flowline_count: int,
    natural_count: int,
) -> None:
    """Print the structure-QA cross-check report."""
    sel = selection.selected
    print("\n=== Hydro-structure QA report ===")
    print(f"policy version:  {selection.policy_version}")
    print(f"candidates:      {candidates}")
    print(f"selected:        {selection.counts['selected']}")
    print(f"excluded:        {selection.counts['excluded']}")
    print(f"by class:        {selection.counts['by_class']}")

    # By source layer, so a report can distinguish line vs point vs area supply.
    by_layer = Counter(f.source_layer for f in sel)
    print(f"by source layer: {dict(by_layer)}")

    # FType labels observed among the selected set (traceability to raw codes).
    ftypes = Counter(
        HYDRO_STRUCTURE_FTYPE_LABELS.get(f.ftype, f"FType {f.ftype}") for f in sel
    )
    print(f"by FType label:  {dict(ftypes)}")

    # --- On-network placement --------------------------------------------- #
    np_ = qa.on_network
    print(f"\n--- On-network placement (tolerance {tolerance_m:.0f} m) ---")
    print(f"flowlines loaded:        {flowline_count}")
    print(f"structures placed:       {np_.count}")
    print(f"on-network:              {np_.on_network}")
    off = np_.count - np_.on_network
    print(f"off-network:             {off}")
    print(f"median nearest-flowline: {np_.median_distance_m:.1f} m")
    print(f"max nearest-flowline:    {np_.max_distance_m:.1f} m")
    if np_.off_network_ids:
        shown = ", ".join(np_.off_network_ids[:10])
        more = "" if len(np_.off_network_ids) <= 10 else f" (+{len(np_.off_network_ids) - 10} more)"
        print(f"off-network source ids:  {shown}{more}")

    # --- Cross-layer duplicate groups ------------------------------------- #
    print(f"\n--- Cross-layer duplicate groups (proximity {dup_tolerance_m:.0f} m) ---")
    print(f"duplicate groups:        {len(qa.duplicate_groups)}")
    for group in qa.duplicate_groups[:10]:
        print(f"  {group}")
    if len(qa.duplicate_groups) > 10:
        print(f"  (+{len(qa.duplicate_groups) - 10} more groups)")

    # --- Canal / natural separation --------------------------------------- #
    print("\n--- Canal / natural separation ---")
    print(f"natural features loaded: {natural_count}")
    print(f"separation ok:           {qa.separation_ok}")
    print(f"offending overlaps:      {len(qa.overlaps)}")
    for pair in qa.overlaps[:10]:
        print(f"  structure {pair[0]} overlaps natural {pair[1]}")
    if len(qa.overlaps) > 10:
        print(f"  (+{len(qa.overlaps) - 10} more overlaps)")

    # --- Source traceability ---------------------------------------------- #
    untraceable = [f for f in sel if not f.source_id]
    if untraceable:
        print(f"\nWARNING: {len(untraceable)} selected structure(s) have no source_id")
    else:
        print("\nall selected structures carry a source id (traceable)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gdb-glob", default=GDB_GLOB)
    ap.add_argument("--state", default=None, help="Clip to this US state polygon.")
    ap.add_argument("--county-shp", default=None, help="County shapefile path.")
    ap.add_argument("--county", default=None, help="County NAME to clip to.")
    ap.add_argument("--state-fp", default=None, help="STATEFP to disambiguate county.")
    ap.add_argument("--no-clip", action="store_true", help="Skip political clipping.")
    ap.add_argument("--min-area-m2", type=float, default=0.0,
                    help="Per-polygon min area (m^2) for selection.")
    ap.add_argument("--min-spacing-m", type=float, default=0.0,
                    help="Per-point min spacing (m) for density thinning.")
    ap.add_argument("--tolerance-m", type=float, default=DEFAULT_TOLERANCE_M,
                    help="On-network nearest-flowline tolerance (m).")
    ap.add_argument("--dup-tolerance-m", type=float, default=DEFAULT_DUP_TOLERANCE_M,
                    help="Cross-layer duplicate proximity (m).")
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

    print(f"loading + classifying structures from {args.gdb_glob} ...")
    features = load_structures(args.gdb_glob)
    print(f"classified {len(features)} candidate structure geometry(ies)")

    policy = HydroStructureSelectionPolicy(
        default_min_area_m2=args.min_area_m2,
        default_min_spacing_m=args.min_spacing_m,
    )
    selection = process_hydro_structures(features, boundary=boundary, policy=policy)

    print("loading flowline network for on-network placement ...")
    flowlines = load_flowlines(args.gdb_glob, boundary)
    print(f"loaded {len(flowlines)} flowline geometry(ies)")

    print("loading + classifying natural water features for separation ...")
    naturals = load_natural_features(args.gdb_glob, boundary)
    print(f"loaded {len(naturals)} natural feature(s)")

    # The QA module is projection-free (inputs already EPSG:5070). Cross-layer
    # duplicate proximity is a separate, tighter tolerance than on-network
    # placement, so the report runs the duplicate check at its own tolerance.
    qa = build_qa_report(
        selection.selected, flowlines, naturals, tolerance_m=args.tolerance_m
    )
    from src.hydro_structure_qa import cross_layer_duplicates

    dup_groups = cross_layer_duplicates(
        selection.selected, tolerance_m=args.dup_tolerance_m
    )
    from dataclasses import replace as _replace

    qa = _replace(qa, duplicate_groups=dup_groups)

    report(
        selection, qa,
        tolerance_m=args.tolerance_m,
        dup_tolerance_m=args.dup_tolerance_m,
        candidates=len(features),
        flowline_count=len(flowlines),
        natural_count=len(naturals),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
