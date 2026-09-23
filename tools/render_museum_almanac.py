"""Museum print concept #03 — "The Almanac" — a river's year in four panels.

A single watershed drawn four times, once per season, so the seasonal rhythm of
the river reads at a glance: the same Snoqualmie skeleton in a 2x2 grid where each
panel re-weights the network by a modeled seasonal flow multiplier and wears its
own almanac colour (concept 03 / THE ALMANAC in
``experiments/museum-print-layouts.html``).

The skeleton is real NHDPlus HR hydrography (clipped once, drawn four times); the
per-season widths are a *climatological* shaping of the base discharge — snow-fed
high country swells in spring melt, rain-fed lowlands in winter — so the panels
compare like an almanac plate, not a gauge record. Everything is authored in
canvas pixels -> one crisp vector SVG -> hi-res PNG (resvg) + print PDF
(rsvg-convert).

    python tools/render_museum_almanac.py
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
    fmt_lonlat, geom_to_path, load_basin, lonlat_of, make_rect_projector,
)
from tools.render_common import clip_flowlines
from tools.render_state_mono import derive_elevations

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PAPER = "#f7f3e8"          # warm almanac paper
INK = "#2b2a22"            # near-black title ink
MUTED = "#6f6a58"          # DM Mono label grey

#: Snoqualmie River Basin (WBD HUC8) — the mockup's subject.
SNOQUALMIE_HUC8 = ("17110010",)

#: Four seasons: (label, month tag, river ink, panel ground, elevation bias).
#: ``bias`` skews the seasonal width multiplier by normalized elevation: a
#: positive bias swells the high country (snowmelt), negative swells the lowlands
#: (rain). The multiplier is ``base * (1 + amp * (bias * (elev_norm - 0.5) * 2))``.
SEASONS = [
    ("Winter", "JAN", "#367a88", "#dbe9e7", -1.0, 0.55),  # rain-driven, lowlands
    ("Spring", "APR", "#b67c36", "#e9e4c7", +1.0, 0.85),  # snowmelt, high country
    ("Summer", "JUL", "#607d4d", "#dde5c8", -0.3, 0.30),  # low flow everywhere
    ("Autumn", "OCT", "#aa573f", "#efd6c4", +0.2, 0.50),  # moderate, early rains
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", default="A year in the Snoqualmie")
    ap.add_argument("--subtitle",
                    default="FOUR SEASONS \u00b7 MODELED FLOW \u00b7 SNOQUALMIE, WA")
    ap.add_argument("--huc8", nargs="+", default=list(SNOQUALMIE_HUC8))
    ap.add_argument("--spec", default="1711", help="HUC4(s) to scan for flowlines.")
    ap.add_argument("--min-order", type=int, default=3)
    ap.add_argument("--art-width", type=int, default=4000)
    ap.add_argument("--min-px", type=float, default=1.0)
    ap.add_argument("--max-px", type=float, default=7.0)
    ap.add_argument("--raster-width", type=int, default=6000)
    ap.add_argument("--print-w-in", type=float, default=24.0)
    ap.add_argument("--slug", default="almanac_snoqualmie")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    W = args.art_width
    H = W  # square sheet (24x24)

    print(f"loading basin {args.huc8} ...")
    boundary = load_basin(tuple(args.huc8))
    lon, lat = lonlat_of(boundary)
    pb = boundary.bounds  # already EPSG:5070

    print(f"clipping flowlines (min_order={args.min_order}) from {args.spec} ...")
    geoms, _orders, flows, _basins, extras = clip_flowlines(
        boundary, args.spec, args.min_order,
        extra_vaa_cols=["MinElevSmo", "MaxElevSmo"],
    )
    if not geoms:
        raise SystemExit("No flowlines fell inside the Snoqualmie basin.")
    print(f"  kept {len(geoms)} reaches")

    _elev_mean, elev_max = derive_elevations(extras["MinElevSmo"], extras["MaxElevSmo"])
    elev_max = np.clip(np.asarray(elev_max, float), 0.0, None)
    span = float(elev_max.max() - elev_max.min())
    elev_norm = (elev_max - elev_max.min()) / span if span > 0 else np.zeros_like(elev_max)

    flows = np.asarray(flows, float)
    base_map = flow_widths({i: f for i, f in enumerate(flows)}, args.min_px,
                           max_scale=args.max_px / args.min_px)
    base = np.array([base_map[i] for i in range(len(geoms))], float)

    # ---- 2x2 grid geometry ------------------------------------------------- #
    ts, ss = W * 0.030, W * 0.0085
    mx = W * 0.06                        # outer margin
    top = H * 0.135                      # space for the title block
    bot = H * 0.055                      # space for caption + copyright
    gap = W * 0.035                      # gutter between panels
    grid_w = W - 2 * mx
    grid_h = H - top - bot
    pw = (grid_w - gap) / 2
    ph = (grid_h - gap) / 2
    pad = pw * 0.055                     # inner padding for the map inside a panel

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        # title block
        f'<text x="{mx:.0f}" y="{H*0.075:.0f}" fill="{INK}" '
        f'font-family="{TITLE_FONT}" font-size="{ts:.0f}" '
        f'letter-spacing="-0.5">{_esc(args.title)}</text>',
        f'<text x="{mx+2:.0f}" y="{H*0.098:.0f}" fill="{MUTED}" '
        f'font-family="{MONO_FONT}" font-size="{ss:.0f}" '
        f'letter-spacing="2">{_esc(args.subtitle)}</text>',
    ]

    for idx, (label, tag, ink, ground, bias, amp) in enumerate(SEASONS):
        r, c = divmod(idx, 2)
        rx = mx + c * (pw + gap)
        ry = top + r * (ph + gap)
        # panel ground + hairline
        parts.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{pw:.1f}" '
                     f'height="{ph:.1f}" fill="{ground}" stroke="{MUTED}" '
                     f'stroke-width="{W*0.0006:.1f}"/>')
        # seasonal width multiplier: swell high or low country by elevation bias
        mult = 1.0 + amp * (bias * (elev_norm - 0.5) * 2.0)
        widths = np.clip(base * mult, 0.35, None)
        P = make_rect_projector(pb, rx + pad, ry + pad, pw - 2 * pad, ph - 2 * pad)
        parts.append(f'<g fill="none" stroke="{ink}" stroke-linecap="round" '
                     'stroke-linejoin="round">')
        for i, g in enumerate(geoms):
            parts.append(f'<path d="{geom_to_path(g, P, close=False)}" '
                         f'stroke-width="{widths[i]:.2f}"/>')
        parts.append('</g>')
        # season label (top-left of panel) + month tag (top-right)
        parts.append(f'<text x="{rx + pad:.1f}" y="{ry + pad + ss*1.1:.1f}" '
                     f'fill="{ink}" font-family="{TITLE_FONT}" '
                     f'font-size="{ss*1.7:.0f}">{label}</text>')
        parts.append(f'<text x="{rx + pw - pad:.1f}" y="{ry + pad + ss*1.0:.1f}" '
                     f'fill="{MUTED}" font-family="{MONO_FONT}" font-size="{ss*0.9:.0f}" '
                     f'letter-spacing="1.5" text-anchor="end">{tag}</text>')

    # caption + coords + copyright
    cap_y = H - bot + H * 0.028
    parts.append(f'<text x="{mx:.0f}" y="{cap_y:.0f}" fill="{MUTED}" '
                 f'font-family="{MONO_FONT}" font-size="{ss*0.85:.0f}" '
                 f'letter-spacing="0.8">SAME NETWORK, SEASONAL FLOW \u00b7 '
                 f'{fmt_lonlat(lon, lat)}</text>')
    parts.append(copyright_text(W - mx, cap_y, fill=MUTED, size=ss * 0.85))
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
