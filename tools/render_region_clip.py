"""Render NHD flowlines clipped to a *political* boundary (e.g. Oregon state).

The main pipeline clips to WBD HUC4 watershed basins, which cross state lines, so
``output/oregon.svg`` covers more than Oregon. This one-off clips the same
flowlines to an actual state polygon so the art matches the state's shape, with a
Strahler ``--min-order`` filter to drop the smallest streams (cuts clutter and
keeps each layer under the ~1M-node rasterizer cap).

    python tools/render_region_clip.py --state Oregon --min-order 2 --width 8000

Shares the same "art quality" recipe as ``render_county_clip.py`` via
:mod:`tools.render_common`: QAMA flow-scaled stroke widths and HUC-N sub-watershed
coloring (default HUC8 at state scale), a neon glow, and layered rasterization —
so a state render reads with the same taper and hue variety as the county one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.render_common import (
    assign_subwatersheds,
    build_inputs,
    clip_flowlines,
    draw_legend,
    draw_outline,
    flow_scaled_widths,
    load_state,
    rasterize,
    render_art_svg,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="Oregon")
    ap.add_argument("--huc4", default="17*",
                    help="HUC4 GDB spec to scan (glob ok), or 'all'.")
    ap.add_argument("--huc-level", default="HUC8", choices=["HUC4", "HUC8", "HUC10", "HUC12"],
                    help="Sub-watershed level to color by (finer = more colors).")
    ap.add_argument("--min-order", type=int, default=1,
                    help="Drop streams below this Strahler order (1 = keep all).")
    ap.add_argument("--width", type=int, default=8000)
    ap.add_argument("--min-px", type=float, default=0.6,
                    help="Stroke width (px) for the lowest-flow headwater channels.")
    ap.add_argument("--max-px", type=float, default=5.0,
                    help="Stroke width (px) for the highest-flow mainstem.")
    ap.add_argument("--legend", action="store_true",
                    help="Overlay a sub-watershed color key (busy at state scale).")
    ap.add_argument("--suffix", default="",
                    help="Appended to output filenames (e.g. '_ord3').")
    args = ap.parse_args()

    print(f"loading {args.state} boundary ...")
    boundary = load_state(args.state)
    print(f"clipping flowlines from HUC4 {args.huc4} (min_order={args.min_order}) ...")
    geoms, orders, flows, _basins = clip_flowlines(boundary, args.huc4, args.min_order)
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the state boundary.")

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
    stem = args.state.lower() + args.suffix
    svg_path = f"output/{stem}_state.svg"
    Path(svg_path).write_text(svg)
    print(f"wrote {svg_path} ({len(svg)} bytes, {len(geometries)} paths)")

    png_path = f"output/{stem}_state.png"
    rasterize(svg_path, png_path, args.width, args.max_px)
    outlined = draw_outline(png_path, boundary, geoms)
    print(f"wrote {png_path} and {outlined}")

    if args.legend:
        legend = draw_legend(png_path, code_color, names, args.huc_level)
        print(f"wrote {legend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
