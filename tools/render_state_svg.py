"""Emit a browser-friendly *state* river SVG for ``web/3d.html``.

The state-scale sibling of ``render_county_clip.py``'s SVG output: it clips the
local NHDPlus HR flowlines to a Census state polygon (sharing the exact basin set
and Strahler ``StreamOrde`` / ``QAMA`` joins via :mod:`tools.render_common`),
colors each ``<g>`` layer by HUC4 basin, and encodes flow as the per-path
``stroke-width``. The interactive 3D lab reads that width as a proxy for order, so
thin headwaters ride high and thick mainstems sink to the valley floor — the same
color+elevation contract as ``render_state_3d.py``.

A whole state at ``--min-order 3`` is hundreds of thousands of paths (too large to
fetch/parse in a browser), so ``--min-order`` defaults higher here to keep the SVG
small; raise it to shrink the file, lower it for more detail.

    python tools/render_state_svg.py --state Washington --min-order 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.render_common import (
    STATE_HUC4,
    build_inputs,
    clip_flowlines,
    flow_scaled_widths,
    load_state,
    render_art_svg,
)


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

    # Color by HUC4 basin (the web 3D lab pairs basin color with flow-width);
    # width tracks log-scaled NHDPlus EROM mean-annual discharge (QAMA).
    geometries, segment_colors, watersheds, _code_color = build_inputs(geoms, basins)
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px
    )
    print(f"basins {sorted(watersheds)}; stream orders 1..{max(orders)}; "
          f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px "
          f"({units_per_px:.2f} m/px)")

    svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
    out = f"output/{args.state.lower()}_display.svg"
    Path(out).write_text(svg)
    print(f"wrote {out} ({len(svg)} bytes, {len(geometries)} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
