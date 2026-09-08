"""Museum print concept #02 — "The Compass" — a river portrait of the Columbia.

An old-world survey sheet reimagined for a single contemporary waterway: the
Columbia and its Gorge tributaries held inside a radial grid, drawn in copper on
a near-black ground, with N/E/S/W bearings around the rim (concept 02 / THE
COMPASS in ``experiments/museum-print-layouts.html``).

Real NHDPlus HR flowlines are clipped to a circular window centred on the Gorge;
each reach is tinted along a copper ramp by log-discharge (dim copper headwaters
-> bright copper mainstem) and widened by flow, so the Columbia itself is the
luminous spine. Authored directly in canvas pixels -> one crisp vector SVG ->
hi-res PNG (resvg) + print PDF (rsvg-convert).

    python tools/render_museum_compass.py
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import shapely

from src.rendering import flow_widths
from tools.museum_common import (
    EPSG, MONO_FONT, OUT_DIR, TITLE_FONT, copyright_text, export_pdf, export_png,
    fmt_lonlat, geom_to_path, make_projector,
)
from tools.render_common import clip_flowlines

BG = "#141f1c"
GRID = "#a7a08c"       # muted survey-grid ink
COPPER_DIM = (122, 82, 52)    # #7a5234 dim copper (low flow)
COPPER_HOT = (227, 167, 101)  # #e3a765 bright copper (mainstem)
LABEL = "#d8d1bd"

#: Columbia River Gorge — centre (lon/lat) and window radius (metres).
GORGE_CENTER = (-121.55, 45.70)
GORGE_RADIUS_M = 52_000.0
GORGE_SPEC = ("1707", "1708")


def copper_colors(flows) -> list[str]:
    """Copper ramp by normalized log-discharge (dim -> hot)."""
    f = np.asarray(flows, dtype=float)
    logs = np.log(np.clip(f, 1e-2, None))
    lo, hi = float(logs.min()), float(logs.max())
    t = np.zeros_like(logs) if hi <= lo else (logs - lo) / (hi - lo)
    c0, c1 = np.array(COPPER_DIM, float), np.array(COPPER_HOT, float)
    out = []
    for ti in t:
        r, g, b = (c0 + (c1 - c0) * ti).round().astype(int)
        out.append(f"#{r:02x}{g:02x}{b:02x}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", default="The Columbia")
    ap.add_argument("--subtitle", default="A RIVER PORTRAIT \u00b7 COLUMBIA GORGE")
    ap.add_argument("--center", nargs=2, type=float, default=list(GORGE_CENTER))
    ap.add_argument("--radius-m", type=float, default=GORGE_RADIUS_M)
    ap.add_argument("--spec", nargs="+", default=list(GORGE_SPEC))
    ap.add_argument("--min-order", type=int, default=3)
    ap.add_argument("--art-width", type=int, default=4800)
    ap.add_argument("--min-px", type=float, default=1.0)
    ap.add_argument("--max-px", type=float, default=11.0)
    ap.add_argument("--raster-width", type=int, default=6000)
    ap.add_argument("--print-w-in", type=float, default=24.0)
    ap.add_argument("--slug", default="compass_columbia")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lon, lat = args.center
    center = gpd.GeoSeries([shapely.geometry.Point(lon, lat)], crs="EPSG:4326") \
        .to_crs(EPSG).iloc[0]
    circle = center.buffer(args.radius_m)
    b = circle.bounds
    pad = 0.14 * (b[2] - b[0])  # margin around the rim for bearings + title
    pbp = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    P, W, H = make_projector(pbp, args.art_width)
    cx, cy = P(center.x, center.y)
    R = args.radius_m * (W / (pbp[2] - pbp[0]))
    print(f"canvas {W}x{H}, R={R:.0f}px")

    print(f"clipping flowlines (min_order={args.min_order}) from {args.spec} ...")
    geoms, _orders, flows, _basins = clip_flowlines(circle, args.spec, args.min_order)
    print(f"  kept {len(geoms)} reaches")
    widths = flow_widths({i: f for i, f in enumerate(flows)}, args.min_px,
                         max_scale=args.max_px / args.min_px)
    colors = copper_colors(flows)

    ts, ss = W * 0.03, W * 0.0092
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
    ]
    # radial survey grid (rings + spokes) behind the river
    gw = W * 0.0009
    parts.append(f'<g stroke="{GRID}" fill="none" stroke-width="{gw:.2f}">')
    for frac, op in ((1.0, 0.85), (0.76, 0.5), (0.5, 0.5), (0.24, 0.5)):
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R*frac:.1f}" '
                     f'opacity="{op}"/>')
    for k in range(8):
        a = math.pi * k / 4.0
        x2, y2 = cx + R * math.cos(a), cy + R * math.sin(a)
        parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" '
                     f'y2="{y2:.1f}" opacity="0.4"/>')
    parts.append('</g>')
    # river portrait (copper), clipped to the rim
    parts.append(f'<clipPath id="rim"><circle cx="{cx:.1f}" cy="{cy:.1f}" '
                 f'r="{R:.1f}"/></clipPath>')
    parts.append('<g clip-path="url(#rim)" fill="none" stroke-linecap="round" '
                 'stroke-linejoin="round">')
    for i, g in enumerate(geoms):
        parts.append(f'<path d="{geom_to_path(g, P, close=False)}" '
                     f'stroke="{colors[i]}" stroke-width="{widths[i]:.2f}"/>')
    parts.append('</g>')
    parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R:.1f}" fill="none" '
                 f'stroke="{GRID}" stroke-width="{gw*1.6:.2f}"/>')
    parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{W*0.006:.1f}" '
                 f'fill="{COPPER_HOT}"/>')
    # cardinal bearings
    for lab, dx, dy, anch in (("N", 0, -1, "middle"), ("E", 1, 0, "start"),
                              ("S", 0, 1, "middle"), ("W", -1, 0, "end")):
        lx = cx + dx * (R + W * 0.028)
        ly = cy + dy * (R + W * 0.028) + (ss * 0.35 if dy == 0 else 0)
        parts.append(f'<text x="{lx:.0f}" y="{ly:.0f}" fill="{LABEL}" '
                     f'font-family="{MONO_FONT}" font-size="{ss:.0f}" '
                     f'letter-spacing="2" text-anchor="{anch}">{lab}</text>')
    # type
    parts.append(f'<text x="{W*0.035:.0f}" y="{W*0.06:.0f}" fill="{LABEL}" '
                 f'font-family="{TITLE_FONT}" font-size="{ts:.0f}" '
                 f'letter-spacing="-0.5">{args.title}</text>')
    parts.append(f'<text x="{W*0.036:.0f}" y="{W*0.08:.0f}" fill="#9da699" '
                 f'font-family="{MONO_FONT}" font-size="{ss:.0f}" '
                 f'letter-spacing="2">{args.subtitle}</text>')
    parts.append(f'<text x="{W*0.036:.0f}" y="{H-W*0.035:.0f}" fill="#9da699" '
                 f'font-family="{MONO_FONT}" font-size="{ss:.0f}" '
                 f'letter-spacing="1">{fmt_lonlat(lon, lat)}</text>')
    parts.append(copyright_text(W - W * 0.035, H - W * 0.035, fill="#9da699", size=ss))
    parts.append('</svg>')

    layout_svg = OUT_DIR / f"{args.slug}.svg"
    layout_svg.write_text("\n".join(parts))
    print(f"wrote {layout_svg}")
    export_png(layout_svg, OUT_DIR / f"{args.slug}.png", args.raster_width)
    print(f"wrote {OUT_DIR / (args.slug + '.png')}")
    export_pdf(layout_svg, OUT_DIR / f"{args.slug}.pdf", args.print_w_in)
    print(f"wrote {OUT_DIR / (args.slug + '.pdf')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
