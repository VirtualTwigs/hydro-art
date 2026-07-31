"""Shared "art quality" rendering recipe for the ``tools/`` clip renderers.

One place for the pipeline that makes ``output/clark_county_outlined.png`` the
most pleasing render: QAMA flow-scaled stroke widths (channels taper and widen at
every confluence), HUC-N sub-watershed coloring via a true point-in-polygon join
against WBD boundaries, a neon glow, and high-resolution layered rasterization.
Every 2-D clip renderer (county/region/state) calls these helpers so the recipe
never drifts between outputs again.

Like the other ``tools/`` scripts, this eagerly imports the heavy GIS stack
(``geopandas``/``shapely``) and reads real datasets, so it only works in a full
(non-offline) environment. It must not be imported by ``src/`` or the test suite,
which stay GDAL-free.
"""

from __future__ import annotations

import glob
import subprocess
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from src.coloring import get_palette
from src.rendering import bounds, flow_widths, render_svg

EPSG = "EPSG:5070"
REPO = Path(__file__).resolve().parent.parent
STATES_SHP = "/tmp/states_shp/cb_2023_us_state_500k.shp"
COUNTIES_SHP = "/tmp/counties_shp/cb_2023_us_county_500k.shp"
GDB_ROOT = "datasets/nhdplus_hr"
WBD_GLOB = "datasets/wbd/**/*.gdb"

#: HUC4 basins to scan per state (matches src/datasets.REGION_HUC4, plus 1707
#: which carries WA's Klickitat-area streams). Only those present locally are read.
STATE_HUC4: dict[str, tuple[str, ...]] = {
    "Washington": ("1701", "1702", "1703", "1707", "1708", "1710", "1711"),
    "Oregon": ("1707", "1708", "1709", "1710", "1712", "1801"),
}

#: Approximate Clark County, WA extent in lon/lat (WGS84) for the no-download
#: "rough" bbox clip. Not the true county outline — a rectangle around it.
CLARK_BBOX_4326 = (-122.90, 45.52, -122.24, 45.99)


# --------------------------------------------------------------------------- #
# Boundaries
# --------------------------------------------------------------------------- #
def load_state(name: str):
    """Return the (reprojected) Census state polygon named ``name``."""
    st = gpd.read_file(STATES_SHP)
    sel = st[st.NAME == name]
    if sel.empty:
        raise SystemExit(f"State {name!r} not found in {STATES_SHP}.")
    return sel.to_crs(EPSG).geometry.iloc[0]


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
    return gpd.GeoSeries([box], crs="EPSG:4326").to_crs(EPSG).iloc[0]


# --------------------------------------------------------------------------- #
# Flowline acquisition + clip
# --------------------------------------------------------------------------- #
def gdb_paths(spec: str | Iterable[str]) -> list[str]:
    """Resolve NHDPlus HR GDBs for a HUC4 ``spec``.

    ``spec`` may be a single code (``"1708"``), a glob (``"17*"``), the literal
    ``"all"`` (every local GDB), or an iterable of any of those. Returns the
    de-duplicated, sorted list of ``*.gdb`` paths that exist locally.
    """
    specs = [spec] if isinstance(spec, str) else list(spec)
    paths: list[str] = []
    for s in specs:
        pat = f"{GDB_ROOT}/{'*' if s == 'all' else s}/*.gdb"
        paths.extend(glob.glob(pat))
    return sorted(set(paths))


def clip_flowlines(boundary, spec: str | Iterable[str], min_order: int):
    """Clip NHD flowlines under ``spec`` to ``boundary``.

    Each kept flowline carries its USGS Strahler ``StreamOrde`` (from
    ``NHDPlusFlowlineVAA``) and its mean-annual discharge ``QAMA`` in cfs (from
    ``NHDPlusEROMMA``), both joined on ``NHDPlusID``, so the renderer can widen
    channels by actual flow. ``min_order`` drops headwater tributaries below that
    Strahler order (1 keeps all); the filter runs *before* the expensive spatial
    clip to keep geometry counts manageable. Fully-inside flowlines are kept as
    is; boundary-crossing ones are trimmed to the boundary.

    Returns parallel lists ``(geoms, orders, flows, basins)`` where ``basins`` is
    each geometry's source HUC4 (the GDB's parent directory name).
    """
    shapely.prepare(boundary)
    geoms: list = []
    orders: list[int] = []
    flows: list[float] = []
    basins: list[str] = []
    for gdb in gdb_paths(spec):
        code = Path(gdb).parent.name
        try:
            f = gpd.read_file(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {code}: {exc}")
            continue
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
        f = f.to_crs(EPSG)
        arr = np.array(f.geometry.values, dtype=object)
        covered = shapely.covers(boundary, arr)
        crossing = shapely.intersects(boundary, arr) & ~covered

        kept0 = len(geoms)
        for gi in np.nonzero(covered)[0]:
            geoms.append(arr[gi]); orders.append(int(seg_orders[gi]))
            flows.append(float(seg_flows[gi])); basins.append(code)
        cross_idx = np.nonzero(crossing)[0]
        if cross_idx.size:
            trimmed = shapely.intersection(boundary, arr[cross_idx])
            for local_i, gi in enumerate(cross_idx):
                g = trimmed[local_i]
                if not g.is_empty:
                    geoms.append(g); orders.append(int(seg_orders[gi]))
                    flows.append(float(seg_flows[gi])); basins.append(code)
        print(f"  {code}: kept {len(geoms) - kept0}")
    return geoms, orders, flows, basins


# --------------------------------------------------------------------------- #
# Coloring
# --------------------------------------------------------------------------- #
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
    for gdb in sorted(glob.glob(WBD_GLOB, recursive=True)):
        try:
            frames.append(
                gpd.read_file(gdb, layer=layer, columns=[col, "name"]).to_crs(EPSG)
            )
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
    """Group flowlines into per-code ``<g>`` layers with a cycled neon color.

    ``codes`` is parallel to ``geoms`` (any grouping key — a spatial HUC-N code
    or a source HUC4 basin). Adjacent codes are usually spatial neighbours, so
    cycling the 12-color neon palette in sorted order keeps most neighbours in
    distinct hues. Returns ``(geometries, segment_colors, watersheds, code_color)``
    with ``geometries`` mapping index -> the actual flowline geometry.
    """
    geometries = {i: g for i, g in enumerate(geoms)}
    watersheds: dict[str, set[int]] = {}
    for i, code in enumerate(codes):
        watersheds.setdefault(code, set()).add(i)
    palette = get_palette("neon")
    ordered = sorted(watersheds)
    code_color = {c: palette[i % len(palette)] for i, c in enumerate(ordered)}
    segment_colors = {i: code_color[codes[i]] for i in geometries}
    return geometries, segment_colors, watersheds, code_color


# --------------------------------------------------------------------------- #
# Widths + SVG
# --------------------------------------------------------------------------- #
def flow_scaled_widths(geometries, flows, width: int, min_px: float, max_px: float):
    """Compute per-path stroke widths from log-scaled discharge.

    Widths are authored in projected user units (meters) — the layered rasterizer
    only rescales the *root* stroke width, so per-path widths must already be in
    document units. Returns ``(widths, base_units, units_per_px, qmax)``.
    """
    flow_map = {i: flows[i] for i in geometries}
    min_x, _, max_x, _ = bounds(geometries.values())
    units_per_px = (max_x - min_x) / width
    base_units = min_px * units_per_px
    widths = flow_widths(flow_map, base_units, max_scale=max_px / min_px)
    qmax = max(flow_map.values(), default=0.0)
    return widths, base_units, units_per_px, qmax


def render_art_svg(geometries, segment_colors, watersheds, base_units, widths):
    """Render the canonical neon-glow, flow-scaled SVG shared by every renderer."""
    return render_svg(
        geometries, segment_colors, watersheds,
        line_width=base_units, stroke_widths=widths,
        glow=True, glow_mode="blur", glow_radius=2.0,
    )


def rasterize(svg_path: str, png_path: str, width: int, stroke_px: float) -> None:
    """Rasterize a layered SVG to PNG via ``tools/rasterize_layered.py``."""
    subprocess.run(
        [f"{REPO}/.venv/bin/python", str(REPO / "tools" / "rasterize_layered.py"),
         svg_path, png_path, "--width", str(width), "--stroke-px", str(stroke_px)],
        check=True,
    )


# --------------------------------------------------------------------------- #
# Overlays
# --------------------------------------------------------------------------- #
def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def draw_outline(png_path: str, boundary, geoms):
    """Overlay the region boundary in red, anchored to the render's bounds."""
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
