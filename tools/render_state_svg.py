"""Emit a browser-friendly *state* river SVG for ``web/3d.html``.

The state-scale sibling of ``render_county_clip.py``'s SVG output: it clips the
local NHDPlus HR flowlines to a Census state polygon (reusing
``render_state_3d.clip_flowlines`` so it shares the exact basin set and Strahler
``StreamOrde`` join), colors each ``<g>`` layer by HUC4 basin, and encodes stream
order as the per-path ``stroke-width``. The interactive 3D lab reads that width as
a proxy for order, so thin headwaters ride high and thick mainstems sink to the
valley floor — the same color+elevation method as ``render_state_3d.py``.

A whole state at ``--min-order 3`` is hundreds of thousands of paths (too large to
fetch/parse in a browser), so ``--min-order`` defaults higher here to keep the SVG
small; raise it further to shrink the file, lower it for more detail.

    python tools/render_state_svg.py --state Washington --min-order 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.coloring import get_palette
from src.rendering import bounds, flow_widths, render_svg
from tools.render_state_3d import STATE_HUC4, clip_flowlines, load_state


def build_inputs(geoms, basins):
    """Group flowlines into per-HUC4 ``<g>`` layers with a cycled neon color."""
    geometries = {i: g for i, g in enumerate(geoms)}
    watersheds: dict[str, set[int]] = {}
    for i, code in enumerate(basins):
        watersheds.setdefault(code, set()).add(i)
    palette = get_palette("neon")
    codes = sorted(watersheds)
    code_color = {c: palette[i % len(palette)] for i, c in enumerate(codes)}
    segment_colors = {i: code_color[basins[i]] for i in geometries}
    return geometries, segment_colors, watersheds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="Washington")
    ap.add_argument("--min-order", type=int, default=5,
                    help="Drop streams below this Strahler order (higher = smaller SVG).")
    ap.add_argument("--width", type=int, default=6000,
                    help="Reference px width the stroke widths are authored against.")
    ap.add_argument("--min-px", type=float, default=0.6,
                    help="Stroke width (px) for the lowest-flow headwater channels.")
    ap.add_argument("--max-px", type=float, default=5.0,
                    help="Stroke width (px) for the highest-flow mainstem.")
    args = ap.parse_args()

    huc4s = STATE_HUC4.get(args.state)
    if not huc4s:
        raise SystemExit(f"No HUC4 mapping for {args.state!r}; add it to STATE_HUC4.")

    print(f"loading {args.state} boundary ...")
    boundary = load_state(args.state)
    print(f"clipping flowlines (min_order={args.min_order}) from {huc4s} ...")
    geoms, orders, flows, basins = clip_flowlines(boundary, huc4s, args.min_order)
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the state boundary.")

    geometries, segment_colors, watersheds = build_inputs(geoms, basins)
    # Width tracks flow "at that point": log-scaled NHDPlus EROM mean-annual
    # discharge (QAMA), so each channel widens at every confluence rather than
    # only at Strahler-order jumps.
    flow_map = {i: flows[i] for i in geometries}
    min_x, _, max_x, _ = bounds(geometries.values())
    units_per_px = (max_x - min_x) / args.width
    base_units = args.min_px * units_per_px
    widths = flow_widths(
        flow_map, base_units, max_scale=args.max_px / args.min_px
    )
    qmax = max(flow_map.values())
    print(f"basins {sorted(watersheds)}; stream orders 1..{max(orders)}; "
          f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px "
          f"({units_per_px:.2f} m/px)")

    svg = render_svg(
        geometries, segment_colors, watersheds,
        line_width=base_units, stroke_widths=widths,
        glow=True, glow_mode="blur", glow_radius=2.0,
    )
    out = f"output/{args.state.lower()}_display.svg"
    Path(out).write_text(svg)
    print(f"wrote {out} ({len(svg)} bytes, {len(geometries)} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
