"""Low-res, state-shaped *all-features* preview render.

Fills the gap between the two existing 2-D clip renderers: ``build.py`` renders
every water feature (rivers + waterbodies + areal fills + point glyphs) but
clips to the *watershed* extent (the union of WBD HUC4 basins), so the outline
is not the political state; ``render_state_svg.py`` clips to the true state
polygon but draws rivers only. This tool does both at once — political-boundary
clip **and** all feature families — at a small pixel width so issues (shape,
missing/duplicate features, colors, the key) are catchable before committing to
a slow full-resolution build.

Like the other ``tools/`` scripts it imports the heavy GIS stack eagerly and
reads real datasets, so it only runs in a full (non-offline) environment.

    python tools/render_state_allfeatures.py --state Washington \
        --min-order 4 --huc-level 8 --width 2400

Add ``--structures`` to overlay engineered infrastructure (dams/weirs, gates,
gaging stations, intakes, spillways, canals) above the water, using the SAME
classification + selection code the pipeline uses. Off by default, so existing
invocations render byte-for-byte the same.
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402

from src.areal_features import AREAL_FTYPE_CLASS  # noqa: E402
from src.hydro_structure_selection import (  # noqa: E402
    HydroStructureSelectionPolicy,
    process_hydro_structures,
)
from src.hydro_structures import classify_hydro_structure  # noqa: E402
from src.loading import LINE_ATTRIBUTE_FIELDS  # noqa: E402
from src.point_features import POINT_FTYPE_CLASS  # noqa: E402
from src.rendering import render_svg  # noqa: E402
from src.waterbodies import FTYPE_CLASS as WB_FTYPE_CLASS  # noqa: E402
from tools.render_common import (  # noqa: E402
    EPSG,
    GDB_ROOT,
    STATE_HUC4,
    assign_subwatersheds,
    build_inputs,
    clip_flowlines,
    flow_scaled_widths,
    load_state,
)

#: Waterbody FType classes that read as open water — rendered as a filled
#: "lake" areal family so they are visible at preview scale (the built-in
#: waterbody layer is a thin no-fill outline that vanishes when downscaled).
_OPEN_WATER = {"lake", "reservoir", "coastal", "bay"}

#: Preview styles: lakes get a solid translucent cyan fill; the natural areal
#: families keep their pipeline defaults (merged in by render_svg).
_AREAL_STYLES = {
    "lake": {"fill": "solid", "color": "#2ec4ff", "opacity": 0.55,
             "render_order": "below"},
}

#: NHD structure source layers (line/point/area) scanned when --structures is on.
_STRUCTURE_LAYERS = ("NHDLine", "NHDPoint", "NHDArea")


def _gdbs(huc4s):
    paths: list[str] = []
    for h in huc4s:
        paths.extend(glob.glob(f"{GDB_ROOT}/{h}/*.gdb"))
    return sorted(set(paths))


def _load_layer(gdbs, layer):
    frames = []
    for gdb in gdbs:
        try:
            frames.append(gpd.read_file(gdb, layer=layer))
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {Path(gdb).parent.name}/{layer}: {exc}")
    if not frames:
        return None
    df = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    return df.to_crs(EPSG)


def _ftype(row) -> int | None:
    for k in ("FType", "FTYPE", "ftype"):
        if k in row and row[k] is not None:
            try:
                return int(row[k])
            except (TypeError, ValueError):
                return None
    return None


def _name(row) -> str | None:
    for k in ("GNIS_Name", "GNIS_NAME", "gnis_name"):
        if k in row and row[k]:
            s = str(row[k]).strip()
            if s:
                return s
    return None


def _river_names(gdbs) -> dict:
    """Map NHDPlusID -> GNIS river name (attribute-only read, no geometry)."""
    names: dict = {}
    for gdb in gdbs:
        try:
            df = gpd.read_file(
                gdb, layer="NHDFlowline",
                columns=["NHDPlusID", "GNIS_Name"], read_geometry=False,
            )
        except Exception:  # noqa: BLE001
            continue
        for nid, nm in zip(df["NHDPlusID"], df["GNIS_Name"]):
            if nm and str(nm).strip():
                names[nid] = str(nm).strip()
    return names


def _polys(geom):
    """Yield the polygonal parts of a (possibly mixed/collection) geometry."""
    if geom is None or geom.is_empty:
        return
    gt = geom.geom_type
    if gt == "Polygon":
        yield geom
    elif gt in ("MultiPolygon", "GeometryCollection"):
        for g in geom.geoms:
            yield from _polys(g)


def _load_polygon_features(gdbs, boundary, min_area):
    """Return (lake_items, areal_items) from NHDWaterbody, clipped to boundary."""
    df = _load_layer(gdbs, "NHDWaterbody")
    lakes: list[tuple] = []
    areal: list[tuple] = []
    lake_named: list[tuple] = []  # (name, representative_point, area)
    fid = 0
    if df is None:
        return lakes, areal, lake_named
    shapely.prepare(boundary)
    for row in df.itertuples(index=False):
        rd = row._asdict()
        geom = rd.get("geometry")
        if geom is None or geom.is_empty:
            continue
        ft = _ftype(rd)
        if ft is None:
            continue
        nm = _name(rd)
        clipped = geom.intersection(boundary)
        for part in _polys(clipped):
            if part.area < min_area:
                continue
            fid += 1
            wb_class = WB_FTYPE_CLASS.get(ft, "excluded")
            if wb_class in _OPEN_WATER:
                lakes.append((f"wb_{fid}", part, "lake"))
                if nm:
                    lake_named.append((nm, part.representative_point(), part.area))
            elif ft in AREAL_FTYPE_CLASS:
                areal.append((f"ar_{fid}", part, AREAL_FTYPE_CLASS[ft]))
    return lakes, areal, lake_named


def _load_point_features(gdbs, boundary):
    df = _load_layer(gdbs, "NHDPoint")
    pts: list[tuple] = []
    if df is None:
        return pts
    shapely.prepare(boundary)
    fid = 0
    for row in df.itertuples(index=False):
        rd = row._asdict()
        geom = rd.get("geometry")
        if geom is None or geom.is_empty:
            continue
        ft = _ftype(rd)
        family = POINT_FTYPE_CLASS.get(ft) if ft is not None else None
        if family in (None, "excluded"):
            continue
        if not boundary.contains(geom):
            continue
        fid += 1
        pts.append((f"pt_{fid}", geom, family))
    return pts


def _attrs_for_row(rd, fields):
    """Pull the structure classification attribute subset from a row dict."""
    return {f: rd[f] for f in fields if f in rd and rd[f] is not None}


def _load_hydro_structures(gdbs, boundary, min_area, min_spacing):
    """Classify + select engineered structures via the pipeline code.

    Loads all three structure-bearing layers (``NHDLine``/``NHDPoint``/
    ``NHDArea``), classifies each row with :func:`classify_hydro_structure`, then
    runs the SAME :func:`process_hydro_structures` selection (repair → clip →
    per-kind thinning) the pipeline uses. Returns the ``(feature_id, geometry,
    struct_class)`` tuples :func:`render_svg` draws in its ``hydro_structures``
    layer.
    """
    features: list = []
    for gdb in gdbs:
        huc4 = Path(gdb).parent.name
        for layer in _STRUCTURE_LAYERS:
            df = _load_layer([gdb], layer)
            if df is None:
                continue
            for row in df.itertuples(index=False):
                rd = row._asdict()
                geom = rd.get("geometry")
                if geom is None or geom.is_empty:
                    continue
                features.append(
                    classify_hydro_structure(
                        _attrs_for_row(rd, LINE_ATTRIBUTE_FIELDS),
                        source_layer=layer,
                        dataset_id="nhdplus_hr",
                        huc4=huc4,
                        geometry=geom,
                        source_crs=EPSG,
                    )
                )
    policy = HydroStructureSelectionPolicy(
        default_min_area_m2=min_area,
        default_min_spacing_m=min_spacing,
    )
    selection = process_hydro_structures(features, boundary=boundary, policy=policy)
    items = [
        (f"st_{i}", f.geometry, f.struct_class)
        for i, f in enumerate(selection.selected)
    ]
    return items, selection.counts["by_class"]


def _font(sz):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size=sz)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _text(draw, xy, s, font, fill=(235, 235, 235)):
    """Draw text with a dark halo so it stays legible over bright rivers."""
    x, y = xy
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        draw.text((x + dx, y + dy), s, fill=(0, 0, 0), font=font)
    draw.text((x, y), s, fill=fill, font=font)


def _annotate(png_path, *, boundary, bounds, river_labels, lake_labels) -> str:
    """Draw the state outline, feature labels, and the key onto the PNG."""
    from PIL import Image, ImageDraw

    min_x, min_y, max_x, max_y = bounds
    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    sx = W / (max_x - min_x)
    sy = H / (max_y - min_y)

    def to_px(x, y):
        return ((x - min_x) * sx, (max_y - y) * sy)

    # State boundary outline — makes the WA shape explicit.
    polys = list(boundary.geoms) if boundary.geom_type == "MultiPolygon" else [boundary]
    for p in polys:
        pts = [to_px(x, y) for x, y in p.exterior.coords]
        draw.line(pts, fill=(255, 255, 255, 140), width=max(2, W // 1200),
                  joint="curve")

    # Feature labels (major named lakes + rivers).
    f_lake = _font(max(14, W // 150))
    f_river = _font(max(15, W // 130))
    for nm, pt in lake_labels:
        _text(draw, to_px(pt.x, pt.y), nm, f_lake, fill=(190, 235, 255))
    for nm, pt in river_labels:
        _text(draw, to_px(pt.x, pt.y), nm, f_river, fill=(240, 240, 240))

    # Key.
    rows = [
        ("swatch", "#2ec4ff", "Lake / reservoir (filled)"),
        ("hatch", "#4fae86", "Wetland"),
        ("swatch", "#dbeeff", "Perennial ice / snowfield"),
        ("dash", "#c9a86a", "Playa (dry lakebed)"),
        ("dot", "#7fe3ff", "Spring / seep"),
        ("dot", "#eaf6ff", "Waterfall"),
        ("dot", "#bfefff", "Rapids"),
        ("line", "#c026d3", "River - hue = sub-watershed, width = flow"),
    ]
    fs = max(16, W // 95)
    ft = _font(fs)
    fh = _font(int(fs * 1.3))
    pad = fs
    sw = int(fs * 1.6)
    line_h = int(fs * 1.8)
    box_w = int(sw + fs * 24)
    box_h = line_h * (len(rows) + 1) + pad
    draw.rectangle([pad, pad, pad + box_w, pad + box_h], fill=(0, 0, 0, 195))
    x0 = pad + fs
    y = pad + fs // 2
    draw.text((x0, y), "Map key", fill=(255, 255, 255), font=fh)
    y += line_h
    for kind, color, label in rows:
        cx0, cy0, cx1, cy1 = x0, y + 2, x0 + sw, y + sw
        rgb = tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        if kind in ("swatch", "hatch"):
            draw.rectangle([cx0, cy0, cx1, cy1], fill=rgb)
        elif kind == "dash":
            draw.rectangle([cx0, cy0, cx1, cy1], outline=rgb, width=3)
        elif kind == "dot":
            draw.ellipse([cx0, cy0, cx1, cy1], fill=rgb)
        elif kind == "line":
            my = (cy0 + cy1) // 2
            draw.line([cx0, my, cx1, my], fill=rgb, width=max(4, sw // 4))
        draw.text((x0 + sw + fs // 2, y), label, fill=(230, 230, 230), font=ft)
        y += line_h

    out = png_path.replace(".png", "_annotated.png")
    im.save(out)
    print(f"wrote {out}")
    return out


def _pick_river_labels(geoms, flows, ids, names, limit):
    """Top ``limit`` named rivers by peak flow -> [(name, representative_point)]."""
    best: dict = {}
    for i in range(len(geoms)):
        nm = names.get(ids[i])
        if not nm:
            continue
        fl = flows[i]
        cur = best.get(nm)
        if cur is None or fl > cur[0]:
            best[nm] = (fl, geoms[i].representative_point())
    top = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    return [(nm, pt) for nm, (_fl, pt) in top]


def _pick_lake_labels(lake_named, limit):
    """Top ``limit`` named lakes by area -> [(name, representative_point)]."""
    best: dict = {}
    for nm, pt, area in lake_named:
        cur = best.get(nm)
        if cur is None or area > cur[0]:
            best[nm] = (area, pt)
    top = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    return [(nm, pt) for nm, (_a, pt) in top]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="Washington")
    ap.add_argument("--min-order", type=int, default=4,
                    help="Drop streams below this Strahler order (higher = fewer).")
    ap.add_argument("--huc-level", type=int, default=8,
                    help="Sub-watershed level for river coloring (more = more hues).")
    ap.add_argument("--width", type=int, default=2400,
                    help="Output raster width in px (raise for full-res).")
    ap.add_argument("--min-px", type=float, default=0.5)
    ap.add_argument("--max-px", type=float, default=5.0)
    ap.add_argument("--min-area", type=float, default=1e5,
                    help="Drop polygon features below this area (m^2) as clutter.")
    ap.add_argument("--label-rivers", type=int, default=24,
                    help="Number of major named rivers to label (0 = none).")
    ap.add_argument("--label-lakes", type=int, default=14,
                    help="Number of major named lakes to label (0 = none).")
    ap.add_argument("--structures", action="store_true",
                    help="Overlay engineered hydro structures (off by default).")
    ap.add_argument("--structure-min-area", type=float, default=0.0,
                    help="Per-polygon min area (m^2) for structure selection.")
    ap.add_argument("--structure-min-spacing", type=float, default=0.0,
                    help="Per-point min spacing (m) for structure thinning.")
    ap.add_argument("--output", default="/tmp/hydro_output/wa_allfeatures.png")
    args = ap.parse_args()

    huc4s = STATE_HUC4.get(args.state)
    if not huc4s:
        raise SystemExit(f"No HUC4 mapping for {args.state!r}.")
    gdbs = _gdbs(huc4s)

    print(f"loading {args.state} boundary ...")
    boundary = load_state(args.state)

    print(f"clipping flowlines (min_order={args.min_order}) ...")
    geoms, orders, flows, basins, extras = clip_flowlines(
        boundary, huc4s, args.min_order, include_id=True
    )
    if not geoms:
        raise SystemExit("No flowlines inside the state boundary.")
    print(f"  rivers: {len(geoms)}")

    codes, _names = assign_subwatersheds(geoms, args.huc_level)
    geometries, segment_colors, watersheds, _code_color = build_inputs(geoms, codes)
    widths, base_units, _upp, _qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px
    )

    print("loading + clipping polygon features (waterbodies/areal) ...")
    lakes, areal, lake_named = _load_polygon_features(gdbs, boundary, args.min_area)
    print(f"  lakes/reservoirs: {len(lakes)}; natural areal: {len(areal)}")

    print("loading + clipping point features ...")
    points = _load_point_features(gdbs, boundary)
    print(f"  points: {len(points)}")

    structures = None
    if args.structures:
        print("loading + selecting engineered structures ...")
        structures, struct_by_class = _load_hydro_structures(
            gdbs, boundary, args.structure_min_area, args.structure_min_spacing
        )
        print(f"  structures: {len(structures)} ({struct_by_class})")

    river_labels = (
        _pick_river_labels(geoms, flows, extras["nhdplus_id"],
                           _river_names(gdbs), args.label_rivers)
        if args.label_rivers else []
    )
    lake_labels = _pick_lake_labels(lake_named, args.label_lakes) if args.label_lakes else []
    print(f"  labels: {len(river_labels)} rivers, {len(lake_labels)} lakes")

    svg = render_svg(
        geometries, segment_colors, watersheds,
        line_width=base_units, stroke_widths=widths,
        glow=True, glow_mode="blur", glow_radius=2.0,
        areal_features=(lakes + areal) or None,
        areal_feature_styles=_AREAL_STYLES,
        point_features=points or None,
        hydro_structures=structures or None,
        hydro_structure_order="above",
    )

    out_png = Path(args.output)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    svg_path = out_png.with_suffix(".svg")
    svg_path.write_text(svg)
    print(f"wrote {svg_path} ({len(svg)} bytes, {len(geometries)} river paths)")

    # Bounds match render_svg's viewBox (union of every drawn geometry), so the
    # PIL overlay transform lines up with the raster exactly.
    all_geoms = list(geometries.values())
    all_geoms += [g for _fid, g, _fam in lakes + areal]
    all_geoms += [g for _fid, g, _fam in points]
    if structures:
        all_geoms += [g for _fid, g, _fam in structures]
    bounds = (
        min(g.bounds[0] for g in all_geoms),
        min(g.bounds[1] for g in all_geoms),
        max(g.bounds[2] for g in all_geoms),
        max(g.bounds[3] for g in all_geoms),
    )

    import subprocess
    print(f"rasterizing at {args.width}px ...", flush=True)
    r = subprocess.run(["resvg", "--width", str(args.width),
                        str(svg_path), str(out_png)])
    if r.returncode != 0:
        print("  resvg single-shot failed (node cap?); using layered rasterizer ...")
        subprocess.run(
            [sys.executable,
             str(Path(__file__).resolve().parent / "rasterize_layered.py"),
             str(svg_path), str(out_png), "--width", str(args.width), "--all-groups"],
            check=True,
        )
    print(f"wrote {out_png}")

    _annotate(str(out_png), boundary=boundary, bounds=bounds,
              river_labels=river_labels, lake_labels=lake_labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
