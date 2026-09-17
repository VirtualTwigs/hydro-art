"""Render a labeled 12-month flow cycle for a US state as PNG frames + animated GIF.

Extends :mod:`tools.render_monthly` to full state boundaries: clips NHD flowlines
to the Census state polygon, disaggregates mean-annual flow into 12 monthly flows
via the NHDPlus precipitation/temperature climatology, and renders one neon
flow-scaled frame per month. Channel widths pulse on a fixed global log scale so
seasonal swelling (wet season / snowmelt) and thinning (dry season) are visible.

Each frame is labeled with the month name and a subtitle. The 12 frames are
assembled into an animated GIF.

    python tools/render_state_monthly.py --state Florida
    python tools/render_state_monthly.py --state Florida --min-order 4 --width 4000
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.rendering import bounds, widths_on_span
from tools.monthly_flow import MONTH_ABBR, build_monthly_flow
from tools.render_common import (
    EPSG,
    STATE_HUC4,
    assign_subwatersheds,
    build_inputs,
    gdb_paths,
    load_state,
    rasterize,
    render_art_svg,
)
from tools.render_monthly import load_basin_flowlines, monthly_flow_by_id

FLOOR = 1e-2
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_FULL = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _font(sz: int):
    for p in ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size=sz)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


# ── Per-state facility catalogs ─────────────────────────────────────────────
# Curated from public sources (EPA FRS, Wikipedia, datacentermap.com).
STATE_FACILITIES: dict[str, list[dict]] = {
    "Florida": [
        # Data Centers
        {"name": "Equinix MI1 (NAP)",       "lon": -80.193, "lat": 25.782, "type": "data_center"},
        {"name": "Digital Realty MIA10",     "lon": -80.191, "lat": 25.776, "type": "data_center"},
        {"name": "QTS Miami",               "lon": -80.360, "lat": 25.790, "type": "data_center"},
        {"name": "NextNRG Jacksonville",    "lon": -81.680, "lat": 30.500, "type": "data_center"},
        {"name": "Fort Meade DC Campus",    "lon": -81.800, "lat": 27.753, "type": "data_center"},
        # Water Treatment
        {"name": "Alexander Orr WTP",       "lon": -80.337, "lat": 25.701, "type": "water_treatment"},
        {"name": "Hialeah-Preston WTP",     "lon": -80.310, "lat": 25.833, "type": "water_treatment"},
        {"name": "Tampa Bay Desal Plant",   "lon": -82.402, "lat": 27.793, "type": "water_treatment"},
        {"name": "Ironbridge WRF",          "lon": -81.240, "lat": 28.490, "type": "water_treatment"},
        # Springs
        {"name": "Silver Springs",          "lon": -82.054, "lat": 29.201, "type": "spring"},
        {"name": "Rainbow Springs",         "lon": -82.428, "lat": 29.110, "type": "spring"},
        {"name": "Ichetucknee Springs",     "lon": -82.776, "lat": 29.967, "type": "spring"},
        {"name": "Wakulla Springs",         "lon": -84.305, "lat": 30.234, "type": "spring"},
        # Dams / Reservoirs
        {"name": "Herbert Hoover Dike",     "lon": -80.800, "lat": 26.950, "type": "dam"},
        {"name": "EAA Reservoir (planned)", "lon": -80.700, "lat": 26.700, "type": "reservoir"},
    ],
}

MARKER_STYLES = {
    "data_center":     ((255, 60, 200), (180, 30, 140), "diamond",  "Data Center"),
    "water_treatment": ((60, 200, 255), (30, 140, 200), "square",   "Water Treatment"),
    "spring":          ((100, 255, 160), (50, 200, 100), "circle",  "Spring"),
    "dam":             ((255, 110, 110), (200, 60, 60),  "square",  "Dam"),
    "reservoir":       ((120, 160, 255), (70, 110, 200), "circle",  "Reservoir"),
}


def _marker(draw, shape, cx, cy, r, fill, outline):
    if shape == "circle":
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=fill, outline=outline, width=2)
    elif shape == "square":
        draw.rectangle([cx - r, cy - r, cx + r, cy + r],
                       fill=fill, outline=outline, width=2)
    elif shape == "diamond":
        draw.polygon([(cx, cy - r * 1.3), (cx + r * 1.2, cy),
                      (cx, cy + r * 1.3), (cx - r * 1.2, cy)],
                     fill=fill, outline=outline)


def _draw_facility_label(draw, text, cx, cy, font, r):
    """Small label above a facility marker."""
    tw = draw.textlength(text, font=font)
    th = font.size
    tx = cx - tw / 2
    ty = cy - r - th - 6
    pad = 3
    draw.rounded_rectangle(
        [tx - pad, ty - pad, tx + tw + pad, ty + th + pad],
        radius=4, fill=(8, 9, 13, 210), outline=(60, 65, 80, 140), width=1,
    )
    draw.text((tx, ty), text, fill=(220, 225, 235), font=font)


def _overlay_facilities(im: Image.Image, facilities: list[dict],
                        min_x: float, max_y: float,
                        sx: float, sy: float) -> Image.Image:
    """Overlay facility markers and labels onto an RGBA image."""
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    W, H = im.size
    marker_r = max(7, W // 400)
    label_font = _font(max(14, W // 320))

    fac_lons = [f["lon"] for f in facilities]
    fac_lats = [f["lat"] for f in facilities]
    fac_pts = gpd.GeoSeries(
        gpd.points_from_xy(fac_lons, fac_lats), crs="EPSG:4326"
    ).to_crs(EPSG)

    for fac, pt in zip(facilities, fac_pts):
        px = (pt.x - min_x) * sx
        py = (max_y - pt.y) * sy
        if -marker_r <= px <= W + marker_r and -marker_r <= py <= H + marker_r:
            ftype = fac["type"]
            fill, outline, shape, _ = MARKER_STYLES[ftype]
            r = marker_r
            _marker(draw, shape, px, py, r, fill, outline)
            _draw_facility_label(draw, fac["name"], px, py, label_font, r)

    return Image.alpha_composite(im.convert("RGBA"), overlay)


def _label_frame_from_image(im: Image.Image, month: str, subtitle: str,
                            state: str, facilities: list[dict]) -> Image.Image:
    """Add a dark title bar below the map with month label + symbol key."""
    W, H = im.size

    fs_state = max(28, W // 36)
    fs_month = max(42, W // 22)
    fs_sub = max(18, W // 60)
    fs_key = max(16, W // 70)

    state_font = _font(fs_state)
    month_font = _font(fs_month)
    sub_font = _font(fs_sub)
    key_font = _font(fs_key)

    # Determine unique facility types present
    ftypes = []
    seen = set()
    for f in facilities:
        ft = f["type"]
        if ft not in seen:
            ftypes.append(ft)
            seen.add(ft)

    # Bar height: text rows + key row
    key_h = int(fs_key * 1.8) if ftypes else 0
    bar_h = int(fs_month * 1.3 + fs_state * 1.1 + fs_sub * 1.1 + key_h + 36)
    composite = Image.new("RGB", (W, H + bar_h), (4, 6, 12))
    composite.paste(im, (0, 0))

    draw = ImageDraw.Draw(composite)
    pad = max(20, W // 90)
    y = H + 10

    # State name
    draw.text((pad, y), state, fill=(235, 239, 248), font=state_font)
    y += int(fs_state * 1.1)

    # Month name (large, accent color)
    draw.text((pad, y), month, fill=(100, 210, 255), font=month_font)
    y += int(fs_month * 1.15)

    # Subtitle
    draw.text((pad, y), subtitle, fill=(100, 120, 160), font=sub_font)
    y += int(fs_sub * 1.3)

    # Symbol key row (horizontal)
    if ftypes:
        x = pad
        kr = max(5, fs_key // 3)
        for ft in ftypes:
            fill, outline, shape, label = MARKER_STYLES[ft]
            _marker(draw, shape, x + kr, y + fs_key // 2, kr, fill, outline)
            x += kr * 2 + 6
            draw.text((x, y), label, fill=(180, 185, 200), font=key_font)
            x += int(draw.textlength(label, font=key_font)) + pad

    return composite


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="Florida")
    ap.add_argument("--min-order", type=int, default=3,
                    help="Drop streams below this Strahler order")
    ap.add_argument("--huc-digits", type=int, default=8,
                    help="WBD level for sub-watershed coloring")
    ap.add_argument("--width", type=int, default=4000, help="Raster width in px")
    ap.add_argument("--min-px", type=float, default=0.3,
                    help="Stroke width for lowest flow")
    ap.add_argument("--max-px", type=float, default=3.0,
                    help="Stroke width for highest flow")
    ap.add_argument("--activation", type=float, default=0.3,
                    help="Reach drawn when flow >= this fraction of its annual peak "
                         "(0 = always draw all)")
    ap.add_argument("--persist", type=float, default=0.02,
                    help="Reaches above this fraction of region peak stay lit year-round")
    ap.add_argument("--ms-per-frame", type=int, default=800,
                    help="Milliseconds per GIF frame")
    args = ap.parse_args()

    state = args.state
    spec = STATE_HUC4.get(state)
    if not spec:
        raise SystemExit(f"No HUC4 mapping for {state!r}; check STATE_HUC4.")
    tag = state.lower().replace(" ", "_")

    # 1) Load state boundary and clip flowlines
    print(f"loading {state} boundary ...")
    boundary = load_state(state)

    print(f"loading flowlines (min_order={args.min_order}) from {spec} ...")
    geoms, ids, orders = load_basin_flowlines(spec, args.min_order, boundary)
    if not geoms:
        raise SystemExit("No flowlines matched; lower --min-order.")
    print(f"  {len(geoms)} paths, orders {min(orders)}..{max(orders)}")

    # 2) Monthly flow disaggregation
    print("computing monthly flows ...")
    flow_map = monthly_flow_by_id(spec)

    # 3) Sub-watershed coloring
    print(f"coloring by HUC{args.huc_digits} ...")
    codes, names = assign_subwatersheds(geoms, args.huc_digits)
    geometries, segment_colors, watersheds, _ = build_inputs(geoms, codes)

    # Per-geometry monthly flow matrix [n, 12]
    monthly = np.zeros((len(geoms), 12))
    for idx in geometries:
        row = flow_map.get(ids[idx])
        if row is not None:
            monthly[idx] = row

    # Fixed global log scale across all months
    positive = monthly[monthly > 0]
    lo = math.log(max(positive.min(), FLOOR)) if positive.size else 0.0
    hi = math.log(positive.max()) if positive.size else 1.0
    min_x, _, max_x, _ = bounds(geometries.values())
    units_per_px = (max_x - min_x) / args.width
    base_units = args.min_px * units_per_px
    top_units = args.max_px * units_per_px
    print(f"  flow scale {math.exp(lo):.2f}..{math.exp(hi):.0f} cfs (fixed across year)")

    annual_max = monthly.max(axis=1)
    persist_floor = args.persist * math.exp(hi)

    # Precompute transform for facility overlay
    min_x, min_y, max_x, max_y = bounds(geometries.values())
    # sx/sy will be set after first rasterize (need image dimensions)
    sx = sy = 0.0

    out_dir = Path(f"output/monthly_{tag}")
    out_dir.mkdir(parents=True, exist_ok=True)
    subtitle = f"Monthly flow cycle — {len(geoms):,} streams, order {args.min_order}+"
    facilities = STATE_FACILITIES.get(state, [])
    frames: list[Image.Image] = []

    for m in range(12):
        flow_m = monthly[:, m]
        frame_flow = {idx: flow_m[idx] for idx in geometries}
        widths = widths_on_span(
            frame_flow, lo, hi, width_min=base_units, width_max=top_units, floor=FLOOR
        )
        active = 0
        for idx in geometries:
            q = flow_m[idx]
            visible = q > 0 and (q >= args.activation * annual_max[idx]
                                 or q >= persist_floor)
            if visible:
                active += 1
            else:
                widths[idx] = 0.0
        svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
        svg_path = out_dir / f"{tag}_{m + 1:02d}_{MONTH_ABBR[m].lower()}.svg"
        png_path = out_dir / f"{tag}_{m + 1:02d}_{MONTH_ABBR[m].lower()}.png"
        svg_path.write_text(svg)
        rasterize(str(svg_path), str(png_path), args.width, args.max_px)
        total_flow = sum(frame_flow.values())
        print(f"  {MONTH_FULL[m]:>9}: {active:>6,} / {len(geoms):,} streams active, "
              f"total flow {total_flow:>12,.0f} cfs")

        # Overlay facilities onto the rasterized frame
        base_im = Image.open(str(png_path)).convert("RGBA")
        W, H = base_im.size
        if sx == 0.0:
            sx = W / (max_x - min_x)
            sy = H / (max_y - min_y)
        if facilities:
            base_im = _overlay_facilities(
                base_im, facilities, min_x, max_y, sx, sy
            )
        frames.append(
            _label_frame_from_image(base_im.convert("RGB"), MONTH_FULL[m],
                                    subtitle, state, facilities)
        )

    gif_path = f"output/{tag}_monthly_12f.gif"
    frames[0].save(
        gif_path, save_all=True, append_images=frames[1:],
        duration=args.ms_per_frame, loop=0, optimize=True,
    )
    print(f"\nwrote {gif_path} ({len(frames)} frames, {args.ms_per_frame}ms/frame)")
    print(f"individual frames in {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
