"""Michigan state facility map — data centers, water plants, dams & industrial users on neon hydrography.

Renders the full state of Michigan with:
  • Neon basin-colored, flow-scaled river network
  • Data-center markers (Switch, QTS, Equinix, Coresite, 365, DuPont Fabros)
  • Water-facility markers (treatment plants, intakes)
  • Dam / reservoir markers (Mio, Tippy, Croton, Hardy, Baraga)
  • Industrial water users (Consumers Energy, DTE Monroe, Dow Midland)
  • HUC sub-watershed basin labels
  • All facilities labeled by name
  • Symbol key / legend

    python tools/render_michigan_facilities.py
    python tools/render_michigan_facilities.py --min-order 3 --width 8000
"""

from __future__ import annotations

import argparse
import glob as glob_mod
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from src.rendering import bounds, render_svg
from tools.render_common import (
    EPSG,
    STATE_HUC4,
    WBD_GLOB,
    assign_subwatersheds,
    build_inputs,
    clip_flowlines,
    flow_scaled_widths,
    load_state,
    rasterize,
    render_art_svg,
    _hex_rgb,
)

BG = "#04060c"

# ── Curated facility data (WGS84 lon/lat) ──────────────────────────────────
# Sources: datacentermap.com, EPA, USGS, Wikipedia, GLWA.
# All coordinates are approximate public-domain centroid positions.

FACILITIES: list[dict] = [
    # ── Data Centers ───────────────────────────────────────────────────────
    {"name": "Switch Grand Rapids",            "lon": -85.655, "lat": 42.963, "type": "data_center"},
    {"name": "QTS Suwanee (Troy MI)",          "lon": -83.150, "lat": 42.606, "type": "data_center"},
    {"name": "Equinix Detroit",                "lon": -83.046, "lat": 42.331, "type": "data_center"},
    {"name": "Coresite (Southfield MI)",       "lon": -83.222, "lat": 42.473, "type": "data_center"},
    {"name": "365 Data Centers (Southfield)",  "lon": -83.249, "lat": 42.468, "type": "data_center"},
    {"name": "DuPont Fabros (Ashburn MI/Det)", "lon": -83.180, "lat": 42.385, "type": "data_center"},

    # ── Water Treatment ────────────────────────────────────────────────────
    {"name": "Detroit Water Works Park WTP",   "lon": -82.970, "lat": 42.367, "type": "water_treatment"},
    {"name": "Springwells WTP (GLWA)",         "lon": -83.120, "lat": 42.295, "type": "water_treatment"},
    {"name": "Lake Huron WTP (GLWA)",          "lon": -82.570, "lat": 43.080, "type": "water_treatment"},
    {"name": "Grand Rapids WTP",               "lon": -85.667, "lat": 42.970, "type": "water_treatment"},
    {"name": "Flint WTP",                      "lon": -83.690, "lat": 43.013, "type": "water_treatment"},
    {"name": "Lansing Water Works",            "lon": -84.556, "lat": 42.733, "type": "water_treatment"},
    {"name": "Ann Arbor WTP",                  "lon": -83.741, "lat": 42.284, "type": "water_treatment"},
    {"name": "Kalamazoo WTP",                  "lon": -85.580, "lat": 42.291, "type": "water_treatment"},

    # ── Water Intakes ──────────────────────────────────────────────────────
    {"name": "Lake Huron Intake (GLWA)",       "lon": -82.520, "lat": 43.100, "type": "water_intake"},
    {"name": "Lake Michigan Intake (GR)",      "lon": -86.240, "lat": 43.060, "type": "water_intake"},
    {"name": "Detroit River Intake",           "lon": -83.100, "lat": 42.290, "type": "water_intake"},

    # ── Dams / Reservoirs ──────────────────────────────────────────────────
    {"name": "Mio Dam (Au Sable R.)",          "lon": -84.130, "lat": 44.652, "type": "dam"},
    {"name": "Tippy Dam (Manistee R.)",        "lon": -85.918, "lat": 44.310, "type": "dam"},
    {"name": "Croton Dam (Muskegon R.)",       "lon": -85.660, "lat": 43.440, "type": "dam"},
    {"name": "Hardy Dam (Muskegon R.)",        "lon": -85.570, "lat": 43.490, "type": "dam"},
    {"name": "Baraga Dam (Sturgeon R.)",       "lon": -88.490, "lat": 46.780, "type": "dam"},

    # ── Industrial Water Users ─────────────────────────────────────────────
    {"name": "Consumers Energy Karn-Weadock",  "lon": -83.890, "lat": 43.640, "type": "industrial"},
    {"name": "DTE Monroe Power Plant",         "lon": -83.380, "lat": 41.900, "type": "industrial"},
    {"name": "Dow Chemical Midland",           "lon": -84.247, "lat": 43.615, "type": "industrial"},
]

# ── Marker styles ───────────────────────────────────────────────────────────
# (fill_rgb, outline_rgb, marker_shape, legend_label, marker_size_mult)
MARKER_STYLES = {
    "data_center":       ((255, 60, 200),  (180, 30, 140), "diamond",  "Data Center",           1.3),
    "water_treatment":   ((60, 200, 255),  (30, 140, 200), "square",   "Water Treatment Plant",  1.2),
    "water_intake":      ((100, 255, 180), (50, 180, 120), "triangle", "Water Intake",           1.2),
    "dam":               ((120, 160, 255), (70, 110, 200), "circle",   "Dam / Reservoir",        1.4),
    "industrial":        ((255, 180, 60),  (200, 130, 30), "circle",   "Industrial Water User",  1.2),
}


# ── Drawing helpers ─────────────────────────────────────────────────────────
def _font(sz: int):
    for p in ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size=sz)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _marker(draw, shape, cx, cy, r, fill, outline):
    if shape == "circle":
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=fill, outline=outline, width=2)
    elif shape == "square":
        draw.rectangle([cx - r, cy - r, cx + r, cy + r],
                       fill=fill, outline=outline, width=2)
    elif shape == "triangle":
        draw.polygon([(cx, cy - r * 1.2), (cx - r, cy + r), (cx + r, cy + r)],
                     fill=fill, outline=outline)
    elif shape == "diamond":
        draw.polygon([(cx, cy - r * 1.3), (cx + r * 1.2, cy),
                      (cx, cy + r * 1.3), (cx - r * 1.2, cy)],
                     fill=fill, outline=outline)


def _draw_label(draw, text, cx, cy, font, color=(230, 235, 245), anchor_y_offset=-18,
                bg=(8, 9, 13, 200)):
    """Draw a text label with a dark background pill for legibility."""
    tw = draw.textlength(text, font=font)
    th = font.size
    tx = cx - tw / 2
    ty = cy + anchor_y_offset - th
    pad = 4
    draw.rounded_rectangle(
        [tx - pad, ty - pad, tx + tw + pad, ty + th + pad],
        radius=5, fill=bg, outline=(60, 65, 80, 160), width=1,
    )
    draw.text((tx, ty), text, fill=color, font=font)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-order", type=int, default=3,
                    help="Min Strahler order (1=all, higher=sparser; 3 good for state)")
    ap.add_argument("--width", type=int, default=8000,
                    help="Output image width in pixels")
    ap.add_argument("--min-px", type=float, default=0.5,
                    help="Min stroke width (px) for headwaters")
    ap.add_argument("--max-px", type=float, default=4.5,
                    help="Max stroke width (px) for mainstems")
    ap.add_argument("--huc-digits", type=int, default=8,
                    help="HUC level for sub-watershed coloring (8 or 10)")
    ap.add_argument("--no-labels", action="store_true",
                    help="Suppress facility labels")
    args = ap.parse_args()

    state = "Michigan"
    tag = "michigan"
    spec = STATE_HUC4.get(state)
    if not spec:
        raise SystemExit(f"No HUC4 mapping for {state!r}.")

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    # 1) Load state boundary
    print(f"loading {state} boundary ...")
    boundary = load_state(state)

    # 2) Clip flowlines
    print(f"clipping flowlines (min_order={args.min_order}) from {spec} ...")
    geoms, orders, flows, basins = clip_flowlines(boundary, spec, args.min_order)
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the state boundary.")

    # 3) Assign sub-watershed colors
    print(f"assigning HUC-{args.huc_digits} sub-watershed colors ...")
    codes, names = assign_subwatersheds(geoms, args.huc_digits)
    geometries, segment_colors, watersheds, code_color = build_inputs(geoms, codes)

    # 4) Flow-scaled widths
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px
    )
    print(f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px "
          f"({units_per_px:.2f} m/px)")

    # 5) Render base SVG
    svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
    svg_path = str(out_dir / f"{tag}_facilities.svg")
    Path(svg_path).write_text(svg)
    print(f"wrote {svg_path} ({len(svg)} bytes, {len(geometries)} paths)")

    # 6) Rasterize to PNG
    png_path = str(out_dir / f"{tag}_facilities.png")
    rasterize(svg_path, png_path, args.width, args.max_px)
    print(f"wrote {png_path}")

    # 7) Overlay facilities, labels, basin labels, and legend
    min_x, min_y, max_x, max_y = bounds(geometries.values())
    im = Image.open(png_path).convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    W, H = im.size
    sx, sy = W / (max_x - min_x), H / (max_y - min_y)
    draw = ImageDraw.Draw(overlay)

    marker_r = max(10, W // 300)
    label_font = _font(max(18, W // 280))
    basin_font = _font(max(20, W // 240))
    legend_font = _font(max(20, W // 220))
    title_font = _font(max(26, W // 180))

    # ── Reproject facility locations ────────────────────────────────────
    fac_lons = [f["lon"] for f in FACILITIES]
    fac_lats = [f["lat"] for f in FACILITIES]
    fac_pts = gpd.GeoSeries(
        gpd.points_from_xy(fac_lons, fac_lats), crs="EPSG:4326"
    ).to_crs(EPSG)

    # ── Draw basin labels ───────────────────────────────────────────────
    print("adding basin labels ...")
    frames = []
    col = f"huc{args.huc_digits}"
    layer = f"WBDHU{args.huc_digits}"
    for gdb in sorted(glob_mod.glob(WBD_GLOB, recursive=True)):
        try:
            frames.append(
                gpd.read_file(gdb, layer=layer, columns=[col, "name"]).to_crs(EPSG)
            )
        except Exception:  # noqa: BLE001
            continue
    if frames:
        hus = pd.concat(frames, ignore_index=True)
        active_codes = set(codes) - {("0" * args.huc_digits)}
        for _, row in hus.iterrows():
            huc_code = str(row[col])
            if huc_code not in active_codes:
                continue
            centroid = row.geometry.representative_point()
            px = (centroid.x - min_x) * sx
            py = (max_y - centroid.y) * sy
            if 0 <= px <= W and 0 <= py <= H:
                basin_name = str(row["name"])
                if len(basin_name) > 28:
                    basin_name = basin_name[:26] + "..."
                _draw_label(draw, basin_name, px, py, basin_font,
                            color=(180, 200, 220, 220), anchor_y_offset=0,
                            bg=(8, 9, 13, 140))

    # ── Draw facility markers + labels ──────────────────────────────────
    print("adding facility markers and labels ...")
    counts: Counter = Counter()
    for fac, pt in zip(FACILITIES, fac_pts):
        px = (pt.x - min_x) * sx
        py = (max_y - pt.y) * sy
        if -marker_r <= px <= W + marker_r and -marker_r <= py <= H + marker_r:
            ftype = fac["type"]
            fill, outline, shape, _, size_mult = MARKER_STYLES[ftype]
            r = int(marker_r * size_mult)
            _marker(draw, shape, px, py, r, fill, outline)
            counts[ftype] += 1
            if not args.no_labels:
                _draw_label(draw, fac["name"], px, py, label_font,
                            anchor_y_offset=-(r + 8))
    print(f"plotted: {dict(counts)}")

    # ── Symbol key / legend (bottom-left) ───────────────────────────────
    print("drawing symbol key ...")
    pad = legend_font.size
    lh = int(legend_font.size * 1.8)

    legend_rows = []
    for ftype in ("data_center", "water_treatment", "water_intake",
                  "dam", "industrial"):
        n = counts.get(ftype, 0)
        if n == 0:
            continue
        fill, outline, shape, label, _ = MARKER_STYLES[ftype]
        legend_rows.append(("marker", label, f"({n})", fill, outline, shape))

    # Basin swatches (cap at 12)
    basin_rows = []
    for code in sorted(code_color):
        if set(code) == {"0" * len(code)}:
            continue
        bname = names.get(code, "unnamed")
        if len(bname) > 30:
            bname = bname[:28] + "..."
        basin_rows.append(("swatch", bname, code, code_color[code]))
    basin_rows = basin_rows[:12]

    title = "Michigan \u2014 Water Infrastructure & Data Centers"
    subtitle_1 = "SYMBOL KEY"
    subtitle_2 = f"Sub-watersheds (HUC-{args.huc_digits})"

    all_labels = ([r[1] + "  " + r[2] for r in legend_rows]
                  + [r[1] + "  " + r[2] for r in basin_rows]
                  + [title, subtitle_1, subtitle_2])
    text_w = max(draw.textlength(lbl, font=legend_font) for lbl in all_labels)
    sw = int(legend_font.size * 1.1)
    pw = int(pad * 3 + sw + text_w + 20)
    total_rows = len(legend_rows) + len(basin_rows) + 3
    ph = int(pad * 2 + lh * total_rows)

    x0, y0 = pad, H - pad - ph
    draw.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=8,
                           fill=(8, 9, 13, 220), outline=(70, 74, 88), width=2)

    draw.text((x0 + pad, y0 + pad), title, fill=(235, 239, 248), font=title_font)
    y = y0 + pad + lh

    draw.text((x0 + pad, y), subtitle_1, fill=(160, 170, 190), font=legend_font)
    y += lh

    for _, label, count_str, fill, outline, shape in legend_rows:
        sy_center = y + lh // 2
        _marker(draw, shape, x0 + pad + sw // 2, sy_center, int(sw * 0.45), fill, outline)
        draw.text((x0 + pad * 2 + sw, y + (lh - legend_font.size) // 2),
                  f"{label}  {count_str}", fill=(226, 230, 240), font=legend_font)
        y += lh

    draw.text((x0 + pad, y), subtitle_2, fill=(160, 170, 190), font=legend_font)
    y += lh

    for _, bname, code, color in basin_rows:
        sy_top = y + (lh - sw) // 2
        rgb = _hex_rgb(color)
        draw.rectangle([x0 + pad, sy_top, x0 + pad + sw, sy_top + sw], fill=rgb)
        draw.text((x0 + pad * 2 + sw, y + (lh - legend_font.size) // 2),
                  bname, fill=(226, 230, 240), font=legend_font)
        draw.text((x0 + pad * 2 + sw + draw.textlength(bname + "   ", font=legend_font),
                   y + (lh - legend_font.size) // 2),
                  code, fill=(120, 126, 142), font=legend_font)
        y += lh

    # Composite
    im = Image.alpha_composite(im, overlay)
    final = im.convert("RGB")
    final_path = str(out_dir / f"{tag}_facilities.png")
    final.save(final_path)
    print(f"wrote {final_path} ({W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
