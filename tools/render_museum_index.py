"""Museum print concept #05 — "The Index" — field-guide cartography of the Elwha.

A map and its cast of characters, for the curious collector: the Elwha river
network drawn on uncoated paper inside a ruled border, with a real river
long-profile inset, habitat markers at the river mouth and headwaters, and a
legend keying the marks (concept 05 / THE INDEX in
``experiments/museum-print-layouts.html``).

Everything is real NHDPlus HR data: reaches are tinted teal by discharge, the
profile inset plots the smoothed elevation of the high-flow trunk against its
cumulative length, and the two markers sit at the lowest (mouth) and highest
(headwaters) reaches. Authored in canvas pixels -> one crisp vector SVG ->
hi-res PNG (resvg) + print PDF (rsvg-convert).

    python tools/render_museum_index.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.rendering import flow_widths
from tools.museum_common import (
    MONO_FONT, OUT_DIR, TITLE_FONT, copyright_text, export_pdf, export_png,
    fmt_lonlat, geom_to_path, lonlat_of, projected_bbox,
)
from tools.render_common import clip_flowlines
from tools.render_state_mono import derive_elevations

PAPER = "#ece8d8"
FRAME = "#1d382f"
INK = "#1d382f"
MUTED = "#5e7064"
MAIN = "#23686b"       # main-stem teal
TRIB = "#7baeb0"       # tributary teal
MARKER = "#d26c4d"     # habitat marker (river mouth / headwaters)
PANEL = "#d9e2d2"      # profile inset panel

#: Elwha River window (lon/lat) — mouth at the Strait down to the Olympic core.
ELWHA_BBOX = (-123.62, 47.72, -123.34, 48.16)
ELWHA_SPEC = ("1711",)


def make_rect_projector(pb, rx, ry, rw, rh):
    """Map EPSG:5070 (x,y) into the target rect (rx,ry,rw,rh), aspect-preserved."""
    minx, miny, maxx, maxy = pb
    s = min(rw / (maxx - minx), rh / (maxy - miny))
    ox = rx + (rw - s * (maxx - minx)) / 2
    oy = ry + (rh - s * (maxy - miny)) / 2

    def P(x, y):
        return (ox + (x - minx) * s, oy + (maxy - y) * s)

    return P


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", default="Field guide to a living river")
    ap.add_argument("--subtitle", default="THE ELWHA \u00b7 OLYMPIC PENINSULA")
    ap.add_argument("--bbox", nargs=4, type=float, default=list(ELWHA_BBOX))
    ap.add_argument("--spec", nargs="+", default=list(ELWHA_SPEC))
    ap.add_argument("--min-order", type=int, default=1)
    ap.add_argument("--art-width", type=int, default=3600)
    ap.add_argument("--min-px", type=float, default=1.1)
    ap.add_argument("--max-px", type=float, default=8.0)
    ap.add_argument("--raster-width", type=int, default=5400)
    ap.add_argument("--print-w-in", type=float, default=18.0)
    ap.add_argument("--slug", default="index_elwha")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    W = args.art_width
    H = int(round(W * 4 / 3))  # 3:4 portrait (18x24)
    pb, clip = projected_bbox(tuple(args.bbox))

    print(f"clipping flowlines (min_order={args.min_order}) from {args.spec} ...")
    geoms, _orders, flows, _basins, extras = clip_flowlines(
        clip, args.spec, args.min_order,
        extra_vaa_cols=["MinElevSmo", "MaxElevSmo"],
    )
    if not geoms:
        raise SystemExit("No flowlines fell inside the Elwha window.")
    print(f"  kept {len(geoms)} reaches")
    _elev_mean, elev_max = derive_elevations(extras["MinElevSmo"], extras["MaxElevSmo"])
    elev_max = np.asarray(elev_max, float)
    flows = np.asarray(flows, float)
    lengths = np.array([g.length for g in geoms], float)
    widths = flow_widths({i: f for i, f in enumerate(flows)}, args.min_px,
                         max_scale=args.max_px / args.min_px)

    # main stem = high-flow trunk (top decile of discharge)
    main_cut = np.percentile(flows, 90)
    is_main = flows >= main_cut

    # map projector into the left/centre region
    mx, my, mw, mh = W * 0.07, H * 0.14, W * 0.60, H * 0.66
    P = make_rect_projector(pb, mx, my, mw, mh)

    ts, ss = W * 0.033, W * 0.011
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        f'<rect x="{W*0.04:.0f}" y="{H*0.03:.0f}" width="{W*0.92:.0f}" '
        f'height="{H*0.94:.0f}" fill="none" stroke="{FRAME}" '
        f'stroke-width="{W*0.0018:.1f}"/>',
        # title
        f'<text x="{W*0.08:.0f}" y="{H*0.085:.0f}" fill="{INK}" '
        f'font-family="{TITLE_FONT}" font-size="{ts:.0f}" '
        f'letter-spacing="-0.5">{args.title}</text>',
        f'<text x="{W*0.081:.0f}" y="{H*0.105:.0f}" fill="{MUTED}" '
        f'font-family="{MONO_FONT}" font-size="{ss:.0f}" '
        f'letter-spacing="2">{args.subtitle}</text>',
    ]
    # rivers: tributaries first, then main stem on top
    parts.append(f'<g fill="none" stroke="{TRIB}" stroke-linecap="round" '
                 'stroke-linejoin="round">')
    for i, g in enumerate(geoms):
        if not is_main[i]:
            parts.append(f'<path d="{geom_to_path(g, P, close=False)}" '
                         f'stroke-width="{widths[i]:.2f}"/>')
    parts.append('</g>')
    parts.append(f'<g fill="none" stroke="{MAIN}" stroke-linecap="round" '
                 'stroke-linejoin="round">')
    for i, g in enumerate(geoms):
        if is_main[i]:
            parts.append(f'<path d="{geom_to_path(g, P, close=False)}" '
                         f'stroke-width="{widths[i]:.2f}"/>')
    parts.append('</g>')

    # markers at mouth (lowest reach) + headwaters (highest reach)
    i_mouth = int(np.argmin(elev_max))
    i_head = int(np.argmax(elev_max))
    for i_pt, lab in ((i_mouth, "river mouth"), (i_head, "headwaters")):
        rp = geoms[i_pt].representative_point()
        px, py = P(rp.x, rp.y)
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{W*0.006:.1f}" '
                     f'fill="{MARKER}"/>')
        parts.append(f'<text x="{px + W*0.011:.1f}" y="{py + ss*0.35:.1f}" '
                     f'fill="{INK}" font-family="{MONO_FONT}" font-size="{ss*0.85:.0f}" '
                     f'letter-spacing="0.5">{lab}</text>')

    # ---- river long-profile inset (top-right panel) ----------------------- #
    ix, iy, iw, ih = W * 0.70, H * 0.14, W * 0.24, H * 0.20
    parts.append(f'<rect x="{ix:.0f}" y="{iy:.0f}" width="{iw:.0f}" '
                 f'height="{ih:.0f}" fill="{PANEL}" stroke="{MUTED}" '
                 f'stroke-width="{W*0.0006:.1f}"/>')
    order = np.argsort(-elev_max[is_main])
    e_main = elev_max[is_main][order]
    l_main = lengths[is_main][order]
    cum = np.cumsum(l_main)
    total = cum[-1] if len(cum) else 1.0
    emax = float(e_main.max()) if len(e_main) else 0.0
    prof = []
    for c, e in zip(cum, e_main):
        gx = ix + iw * (c / total)
        gy = iy + ih - ih * (e / emax if emax else 0)
        prof.append(f"{gx:.1f} {gy:.1f}")
    if prof:
        parts.append(f'<polyline points="{" ".join(prof)}" fill="none" '
                     f'stroke="{MAIN}" stroke-width="{W*0.0016:.1f}"/>')
    parts.append(f'<text x="{ix:.0f}" y="{iy + ih + ss*1.6:.0f}" fill="{MUTED}" '
                 f'font-family="{MONO_FONT}" font-size="{ss*0.8:.0f}" '
                 f'letter-spacing="0.5">RIVER PROFILE / {emax:,.0f} M to 0 M</text>')

    # ---- legend (bottom-left) --------------------------------------------- #
    ly = H * 0.9
    lx = W * 0.08
    parts.append(f'<circle cx="{lx:.0f}" cy="{ly:.0f}" r="{W*0.006:.1f}" '
                 f'fill="{MARKER}"/>')
    parts.append(f'<text x="{lx + W*0.016:.0f}" y="{ly + ss*0.35:.0f}" fill="{INK}" '
                 f'font-family="{MONO_FONT}" font-size="{ss*0.9:.0f}">habitat marker</text>')
    lx2 = W * 0.30
    parts.append(f'<line x1="{lx2:.0f}" y1="{ly:.0f}" x2="{lx2 + W*0.03:.0f}" '
                 f'y2="{ly:.0f}" stroke="{MAIN}" stroke-width="{W*0.003:.1f}"/>')
    parts.append(f'<text x="{lx2 + W*0.04:.0f}" y="{ly + ss*0.35:.0f}" fill="{INK}" '
                 f'font-family="{MONO_FONT}" font-size="{ss*0.9:.0f}">main stem</text>')
    lx3 = W * 0.52
    parts.append(f'<line x1="{lx3:.0f}" y1="{ly:.0f}" x2="{lx3 + W*0.03:.0f}" '
                 f'y2="{ly:.0f}" stroke="{TRIB}" stroke-width="{W*0.0016:.1f}"/>')
    parts.append(f'<text x="{lx3 + W*0.04:.0f}" y="{ly + ss*0.35:.0f}" fill="{INK}" '
                 f'font-family="{MONO_FONT}" font-size="{ss*0.9:.0f}">tributary</text>')

    # coords + copyright
    lon, lat = lonlat_of(clip)
    parts.append(f'<text x="{W*0.08:.0f}" y="{H*0.945:.0f}" fill="{MUTED}" '
                 f'font-family="{MONO_FONT}" font-size="{ss*0.85:.0f}" '
                 f'letter-spacing="1">{fmt_lonlat(lon, lat)}</text>')
    parts.append(copyright_text(W * 0.92, H * 0.945, fill=MUTED, size=ss * 0.85))
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
