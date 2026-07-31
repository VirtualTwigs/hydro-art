"""Render NHD flowlines clipped to a single *county* boundary.

A county-granularity sibling of ``render_region_clip.py`` (which clips to whole
states). It loads a county polygon from the Census cartographic-boundary
counties shapefile, clips the local NHDPlus HR flowlines to it, colors each by
its HUC10 sub-watershed, renders a flow-scaled neon-glow SVG, and rasterizes a
PNG (with the county outline overlaid in red for orientation, plus a legend).

    python tools/render_county_clip.py --state-fp 53 --county Clark --huc4 1708

Clark County, WA (STATEFP 53) sits in HUC4 1708 (Lower Columbia), so only that
GDB is scanned by default; pass ``--huc4 all`` to scan every local GDB.

The shared "art quality" recipe (flow-scaled widths, HUC-N spatial coloring,
glow, layered rasterize) lives in :mod:`tools.render_common`; this module is a
thin driver over it. The recipe helpers are re-exported here because
``render_county_3d`` and ``overlay_facilities`` import them from this module.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.render_common import (  # noqa: F401  (re-exported for sibling tools)
    CLARK_BBOX_4326,
    _hex_rgb,
    assign_subwatersheds,
    bbox_boundary,
    build_inputs,
    clip_flowlines,
    draw_legend,
    draw_outline,
    flow_scaled_widths,
    load_county,
    rasterize,
    render_art_svg,
)


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
    geoms, orders, flows, _basins = clip_flowlines(boundary, args.huc4, args.min_order)
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the county boundary.")

    digits = int(args.huc_level[3:])
    codes, names = assign_subwatersheds(geoms, digits)
    geometries, segment_colors, watersheds, code_color = build_inputs(geoms, codes)
    print(f"colored by {args.huc_level}: {len(watersheds)} sub-watersheds")

    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px
    )
    print(f"stream orders 1..{max(orders)}; flow 0..{qmax:.0f} cfs "
          f"-> {args.min_px}..{args.max_px}px ({units_per_px:.2f} m/px)")

    svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
    stem = f"{args.county.lower()}_county"
    svg_path = f"output/{stem}.svg"
    Path(svg_path).write_text(svg)
    print(f"wrote {svg_path} ({len(svg)} bytes, {len(geometries)} paths)")

    png_path = f"output/{stem}.png"
    rasterize(svg_path, png_path, args.width, args.max_px)
    outlined = draw_outline(png_path, boundary, geoms)
    print(f"wrote {png_path} and {outlined}")

    legend = draw_legend(png_path, code_color, names, args.huc_level)
    print(f"wrote {legend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
