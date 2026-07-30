"""Render NHD flowlines clipped to a single *county* boundary.

A county-granularity sibling of ``render_region_clip.py`` (which clips to whole
states). It loads a county polygon from the Census cartographic-boundary
counties shapefile, clips the local NHDPlus HR flowlines to it, colors each
by its HUC4 basin, renders a layered SVG, and rasterizes a PNG (with the county
outline overlaid in red for orientation).

    python tools/render_county_clip.py --state-fp 53 --county Clark --huc4 1708

Clark County, WA (STATEFP 53) sits in HUC4 1708 (Lower Columbia), so only that
GDB is scanned by default; pass ``--huc4 all`` to scan every local GDB.
"""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from src.coloring import get_palette
from src.rendering import bounds, flow_widths, render_svg

EPSG = "EPSG:5070"
COUNTIES_SHP = "/tmp/counties_shp/cb_2023_us_county_500k.shp"
GDB_ROOT = "datasets/nhdplus_hr"
REPO = "/Users/neilrunde/code/hydro-art"

#: Approximate Clark County, WA extent in lon/lat (WGS84) for the no-download
#: "rough" bbox clip. Not the true county outline — a rectangle around it.
CLARK_BBOX_4326 = (-122.90, 45.52, -122.24, 45.99)


def load_county(state_fp: str, county: str):
    """Return the (reprojected) county polygon for ``county`` in ``state_fp``."""
    df = gpd.read_file(COUNTIES_SHP)
    sel = df[(df.STATEFP == str(state_fp)) & (df.NAME.str.lower() == county.lower())]
    if sel.empty:
        raise SystemExit(
            f"County {county!r} in STATEFP {state_fp!r} not found in {COUNTIES_SHP}."
        )
    return sel.to_crs(EPSG).geometry.iloc[0]


def bbox_boundary(bbox_4326: tuple[float, float, float, float]):
    """Return a rectangular boundary (EPSG:5070) from a lon/lat bbox."""
    west, south, east, north = bbox_4326
    box = shapely.geometry.box(west, south, east, north)
    return (
        gpd.GeoSeries([box], crs="EPSG:4326").to_crs(EPSG).iloc[0]
    )


def gdb_paths(huc4: str) -> list[str]:
    pat = f"{GDB_ROOT}/{'*' if huc4 == 'all' else huc4}/*.gdb"
    return sorted(glob.glob(pat))


def clip_flowlines(boundary, huc4: str, min_order: int):
    """Return (geometries, stream_order, flow) clipped to boundary.

    Each kept geometry carries its USGS Strahler ``StreamOrde`` (from the
    ``NHDPlusFlowlineVAA`` table) and its mean-annual discharge ``QAMA`` in cfs
    (from ``NHDPlusEROMMA``), both joined on ``NHDPlusID``, so the renderer can
    widen channels by actual flow at that point.
    """
    shapely.prepare(boundary)
    geoms: list = []
    orders: list[int] = []
    flows: list[float] = []
    for gdb in gdb_paths(huc4):
        code = Path(gdb).parent.name
        try:
            f = gpd.read_file(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {code}: {exc}")
            continue
        f = f.to_crs(EPSG)
        vaa = gpd.read_file(
            gdb, layer="NHDPlusFlowlineVAA",
            columns=["NHDPlusID", "StreamOrde"], read_geometry=False,
        )
        order_by_id = dict(zip(vaa["NHDPlusID"], vaa["StreamOrde"]))
        erom = gpd.read_file(
            gdb, layer="NHDPlusEROMMA",
            columns=["NHDPlusID", "QAMA"], read_geometry=False,
        )
        flow_by_id = dict(zip(erom["NHDPlusID"], erom["QAMA"]))
        seg_orders = (
            f["NHDPlusID"].map(lambda i: int(order_by_id.get(i, 1) or 1)).to_numpy()
        )
        seg_flows = (
            f["NHDPlusID"].map(lambda i: float(flow_by_id.get(i, 0.0) or 0.0)).to_numpy()
        )
        if min_order > 1:
            keep = seg_orders >= min_order
            f = f[keep]
            seg_orders = seg_orders[keep]
            seg_flows = seg_flows[keep]
        arr = np.array(f.geometry.values, dtype=object)
        covered = shapely.covers(boundary, arr)
        crossing = shapely.intersects(boundary, arr) & ~covered

        kept0 = len(geoms)
        for gi in np.nonzero(covered)[0]:
            geoms.append(arr[gi]); orders.append(int(seg_orders[gi]))
            flows.append(float(seg_flows[gi]))
        cross_idx = np.nonzero(crossing)[0]
        if cross_idx.size:
            trimmed = shapely.intersection(boundary, arr[cross_idx])
            for local_i, gi in enumerate(cross_idx):
                g = trimmed[local_i]
                if not g.is_empty:
                    geoms.append(g); orders.append(int(seg_orders[gi]))
                    flows.append(float(seg_flows[gi]))
        print(f"  {code}: kept {len(geoms) - kept0}")
    return geoms, orders, flows


def assign_subwatersheds(geoms, digits: int):
    """Spatially assign each flowline to its true HUC-``digits`` sub-watershed.

    A flowline's ReachCode is *not* a nested HUC10/12 (it's HUC8 + a reach
    sequence), so the code is resolved by a point-in-polygon join against the
    WBD ``WBDHU{digits}`` boundaries. Returns ``(codes, names)`` where ``codes``
    is parallel to ``geoms`` and ``names`` maps code -> WBD name. Flowlines
    outside every polygon fall into a single ``0``-filled group.
    """
    col, layer = f"huc{digits}", f"WBDHU{digits}"
    frames = []
    for gdb in sorted(glob.glob("datasets/wbd/**/*.gdb", recursive=True)):
        try:
            frames.append(gpd.read_file(gdb, layer=layer, columns=[col, "name"]).to_crs(EPSG))
        except Exception:  # noqa: BLE001
            continue
    if not frames:
        raise SystemExit(f"No WBD {layer} boundaries found under datasets/wbd/.")
    hus = pd.concat(frames, ignore_index=True)
    hus[col] = hus[col].astype(str)

    pts = gpd.GeoDataFrame(
        geometry=[g.representative_point() for g in geoms], crs=EPSG
    )
    joined = gpd.sjoin(pts, hus[[col, "name", "geometry"]], how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")].sort_index()
    codes = joined[col].fillna("0" * digits).astype(str).tolist()
    names = dict(zip(hus[col], hus["name"].astype(str)))
    return codes, names


def build_inputs(geoms, codes):
    geometries = {i: g for i, g in enumerate(geoms)}
    watersheds: dict[str, set[int]] = {}
    for i, code in enumerate(codes):
        watersheds.setdefault(code, set()).add(i)
    palette = get_palette("neon")
    ordered = sorted(watersheds)
    # Adjacent HUC codes are usually spatial neighbours, so cycling the palette
    # in sorted order keeps most neighbours in distinct hues.
    code_color = {c: palette[i % len(palette)] for i, c in enumerate(ordered)}
    segment_colors = {i: code_color[codes[i]] for i in geometries}
    return geometries, segment_colors, watersheds, code_color


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def draw_legend(png_path: str, code_color: dict, names: dict, huc_level: str):
    """Overlay a color key (swatch + sub-watershed name) in the top-left."""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im)
    fs = max(26, W // 150)
    def load(sz):
        for p in ("/System/Library/Fonts/SFNSMono.ttf",
                  "/System/Library/Fonts/Menlo.ttc",
                  "/Library/Fonts/Arial.ttf"):
            try:
                return ImageFont.truetype(p, size=sz)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()
    font, title_font = load(fs), load(int(fs * 1.25))

    rows = []
    for code in sorted(code_color):
        if set(code) == {"0"}:
            name = "unassigned / artificial paths"
        else:
            name = names.get(code, "unnamed")
        rows.append((f"{name}", code, code_color[code]))

    pad, sw, lh = fs, int(fs * 1.1), int(fs * 1.7)
    title = f"Sub-watersheds — {huc_level}"
    text_w = max([draw.textlength(f"{n}   {c}", font=font) for n, c, _ in rows]
                 + [draw.textlength(title, font=title_font)])
    pw = int(pad * 3 + sw + text_w)
    ph = int(pad * 2 + lh * (len(rows) + 1))
    x0 = y0 = pad
    draw.rectangle([x0, y0, x0 + pw, y0 + ph], fill=(8, 9, 13), outline=(70, 74, 88), width=2)
    draw.text((x0 + pad, y0 + pad), title, fill=(235, 239, 248), font=title_font)
    y = y0 + pad + lh
    for name, code, color in rows:
        sy = y + (lh - sw) // 2
        draw.rectangle([x0 + pad, sy, x0 + pad + sw, sy + sw], fill=_hex_rgb(color))
        draw.text((x0 + pad * 2 + sw, y), name, fill=(226, 230, 240), font=font)
        draw.text((x0 + pad * 2 + sw + draw.textlength(name + "   ", font=font), y),
                  code, fill=(120, 126, 142), font=font)
        y += lh
    out = png_path.replace(".png", "_legend.png")
    im.save(out)
    return out


def draw_outline(png_path: str, boundary, geoms):
    """Overlay the county boundary in red, anchored to the render's bounds."""
    from PIL import Image, ImageDraw

    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)
    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    sx, sy = W / (maxx - minx), H / (maxy - miny)
    draw = ImageDraw.Draw(im)
    polys = list(boundary.geoms) if boundary.geom_type == "MultiPolygon" else [boundary]
    for p in polys:
        pts = [((x - minx) * sx, (maxy - y) * sy) for x, y in p.exterior.coords]
        draw.line(pts, fill=(255, 30, 30), width=max(4, W // 900), joint="curve")
    out = png_path.replace(".png", "_outlined.png")
    im.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-fp", default="53", help="Census STATEFP (WA=53).")
    ap.add_argument("--county", default="Clark")
    ap.add_argument("--bbox", action="store_true",
                    help="Rough mode: clip to a lon/lat bounding box (no download) "
                         "instead of the real county polygon.")
    ap.add_argument("--huc4", default="1708",
                    help="HUC4 GDB to scan, or 'all' for every local GDB.")
    ap.add_argument("--huc-level", default="HUC10", choices=["HUC8", "HUC10", "HUC12"],
                    help="Sub-watershed level to color by (finer = more colors).")
    ap.add_argument("--min-order", type=int, default=1,
                    help="Drop streams below this Strahler order (1 = keep all).")
    ap.add_argument("--width", type=int, default=6000)
    ap.add_argument("--min-px", type=float, default=0.6,
                    help="Stroke width (px) for the lowest-flow headwater channels.")
    ap.add_argument("--max-px", type=float, default=5.0,
                    help="Stroke width (px) for the highest-flow mainstem.")
    args = ap.parse_args()

    if args.bbox:
        print(f"loading {args.county} County as ROUGH bbox {CLARK_BBOX_4326} ...")
        boundary = bbox_boundary(CLARK_BBOX_4326)
    else:
        print(f"loading {args.county} County (STATEFP {args.state_fp}) ...")
        boundary = load_county(args.state_fp, args.county)
    print(f"clipping flowlines from HUC4 {args.huc4} (min_order={args.min_order}) ...")
    geoms, orders, flows = clip_flowlines(boundary, args.huc4, args.min_order)
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the county boundary.")

    digits = int(args.huc_level[3:])
    codes, names = assign_subwatersheds(geoms, digits)
    geometries, segment_colors, watersheds, code_color = build_inputs(geoms, codes)
    print(f"colored by {args.huc_level}: {len(watersheds)} sub-watersheds")

    # Flow-scaled widths: width tracks log-scaled mean-annual discharge (QAMA),
    # so a channel widens at every confluence, not just at Strahler-order jumps.
    # Authored in projected user units (meters) so they survive the layered
    # rasterizer, which only rescales the *root* stroke width.
    flow_map = {i: flows[i] for i in geometries}
    min_x, _, max_x, _ = bounds(geometries.values())
    units_per_px = (max_x - min_x) / args.width
    base_units = args.min_px * units_per_px
    widths = flow_widths(
        flow_map, base_units, max_scale=args.max_px / args.min_px
    )
    print(f"stream orders 1..{max(orders)}; flow 0..{max(flow_map.values()):.0f} cfs "
          f"-> {args.min_px}..{args.max_px}px ({units_per_px:.2f} m/px)")

    svg = render_svg(
        geometries, segment_colors, watersheds,
        line_width=base_units, stroke_widths=widths,
        glow=True, glow_mode="blur", glow_radius=2.0,
    )
    stem = f"{args.county.lower()}_county"
    svg_path = f"output/{stem}.svg"
    Path(svg_path).write_text(svg)
    print(f"wrote {svg_path} ({len(svg)} bytes, {len(geometries)} paths)")

    png_path = f"output/{stem}.png"
    subprocess.run(
        [f"{REPO}/.venv/bin/python", "tools/rasterize_layered.py",
         svg_path, png_path, "--width", str(args.width),
         "--stroke-px", str(args.max_px)],
        check=True,
    )
    outlined = draw_outline(png_path, boundary, geoms)
    print(f"wrote {png_path} and {outlined}")

    legend = draw_legend(png_path, code_color, names, args.huc_level)
    print(f"wrote {legend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
