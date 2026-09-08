"""Museum print concept #04 — "The Divide" — Cascade watersheds as a color field.

Basin boundaries become the composition: each HUC8 in a North/Central Washington
Cascades window is flooded with a flat gallery color, the watershed divides drawn
as fine light seams, and the real river network traced over the top in ivory —
a modern color-field painting that rewards distance and close inspection equally
(concept 04 / THE DIVIDE in ``experiments/museum-print-layouts.html``).

Everything is authored directly in the canvas pixel space (via
``museum_common.make_projector``) so the polygons, seams, rivers and Fraunces /
DM Mono type all live in one crisp vector SVG, exported to a hi-res PNG (resvg)
and a print-ready vector PDF (rsvg-convert).

    python tools/render_museum_divide.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import shapely

from src.rendering import flow_widths
from tools.museum_common import (
    MONO_FONT, OUT_DIR, TITLE_FONT, copyright_text, export_pdf, export_png,
    geom_to_path, load_hucs, make_projector, projected_bbox,
)
from tools.render_common import clip_flowlines

BG = "#111b29"
SEAM = "#f1efe4"      # light watershed-divide seams
RIVER = "#f9f3df"     # ivory river ink over the color field
#: Gallery color-field palette (the concept's four hues, extended so neighbouring
#: basins stay distinct as the field grows).
GALLERY = ["#e76f51", "#3c8d99", "#e9c46a", "#264653", "#8ab17d",
           "#c05746", "#457b9d", "#e9a227", "#52796f", "#bc6c25"]

#: North/Central Washington Cascades window (lon/lat) — Skykomish, Snoqualmie,
#: Sauk, Wenatchee, Upper Yakima, Naches drain across the crest here.
CASCADE_BBOX = (-121.95, 46.95, -120.35, 48.35)
CASCADE_SPEC = ("1702", "1703", "1711")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", default="Where the Rain Chooses to Go")
    ap.add_argument("--subtitle", default="WATERSHED DIVIDES \u00b7 NORTH CASCADES, WA")
    ap.add_argument("--bbox", nargs=4, type=float, default=list(CASCADE_BBOX))
    ap.add_argument("--spec", nargs="+", default=list(CASCADE_SPEC))
    ap.add_argument("--min-order", type=int, default=4)
    ap.add_argument("--art-width", type=int, default=4800)
    ap.add_argument("--min-px", type=float, default=1.6)
    ap.add_argument("--max-px", type=float, default=9.0)
    ap.add_argument("--raster-width", type=int, default=6000)
    ap.add_argument("--print-w-in", type=float, default=40.0)
    ap.add_argument("--slug", default="divide_cascades")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pb, _quad = projected_bbox(tuple(args.bbox))
    clip = shapely.geometry.box(*pb)  # axis-aligned canvas rect -> full bleed
    P, W, H = make_projector(pb, args.art_width)
    print(f"canvas {W}x{H}")

    print("loading HUC8 basins ...")
    hucs = load_hucs(8, ("17",))  # everything; filter to the window next
    hucs = hucs[hucs.intersects(clip)].copy()
    hucs["geometry"] = hucs.geometry.intersection(clip)
    hucs = hucs[~hucs.geometry.is_empty].sort_values("huc8").reset_index(drop=True)
    print(f"  {len(hucs)} basins in window")

    print(f"clipping flowlines (min_order={args.min_order}) from {args.spec} ...")
    geoms, _orders, flows, _basins = clip_flowlines(clip, args.spec, args.min_order)
    print(f"  kept {len(geoms)} reaches")
    widths = flow_widths({i: f for i, f in enumerate(flows)}, args.min_px,
                         max_scale=args.max_px / args.min_px)

    # ---- compose one vector SVG ------------------------------------------- #
    ts = W * 0.028   # title size
    ss = W * 0.0088  # subtitle / label size
    parts = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">',
        '<defs><linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0b1420" stop-opacity="0.82"/>'
        '<stop offset="1" stop-color="#0b1420" stop-opacity="0"/>'
        '</linearGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        '<g stroke="' + SEAM + f'" stroke-width="{W*0.0011:.2f}" '
        'stroke-linejoin="round">',
    ]
    for i, row in hucs.iterrows():
        color = GALLERY[i % len(GALLERY)]
        parts.append(f'<path d="{geom_to_path(row.geometry, P, close=True)}" '
                     f'fill="{color}"/>')
    parts.append('</g>')
    # rivers over the field
    parts.append(f'<g fill="none" stroke="{RIVER}" stroke-linecap="round" '
                 'stroke-linejoin="round" opacity="0.92">')
    for i, g in enumerate(geoms):
        parts.append(f'<path d="{geom_to_path(g, P, close=False)}" '
                     f'stroke-width="{widths[i]:.2f}"/>')
    parts.append('</g>')
    # type (over a soft top scrim for legibility against the color field)
    parts.append(f'<rect width="{W}" height="{H*0.16:.0f}" fill="url(#scrim)"/>')
    parts.append(
        f'<text x="{W*0.03:.0f}" y="{W*0.058:.0f}" fill="#ffffff" '
        f'font-family="{TITLE_FONT}" font-size="{ts:.0f}" '
        f'letter-spacing="-0.5">{args.title}</text>'
    )
    parts.append(
        f'<text x="{W*0.031:.0f}" y="{W*0.079:.0f}" fill="#eef1ea" '
        f'font-family="{MONO_FONT}" font-size="{ss:.0f}" letter-spacing="2" '
        f'opacity="0.9">{args.subtitle}</text>'
    )
    parts.append(copyright_text(W - W * 0.03, H - W * 0.02, fill="#e9ede6",
                                size=ss))
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
