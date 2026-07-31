"""Render a whole *state* river network as a tilted, stream-order 3D art image.

The state-scale sibling of ``render_county_3d.py``. It clips the local NHDPlus HR
flowlines to a Census state polygon, keeps each flowline's USGS Strahler
``StreamOrde`` (so headwater tributaries ride high and high-order mainstems sink
into the valleys — elevation derived from the hydrography, no DEM), colors each
by its HUC4 basin, then reuses the same projection/relief/render pipeline as the
county tool.

State networks are huge, so ``--min-order`` thins headwater clutter (and keeps
the render tractable); default 3 keeps the major network only.

    python tools/render_state_3d.py --state Washington --min-order 3

Requires the Census state shapefile at ``/tmp/states_shp/`` and the region-17
HUC4 GDBs under ``datasets/nhdplus_hr/`` (large files live on the NAS and are
symlinked in).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.coloring import get_palette
from tools.render_common import STATE_HUC4, clip_flowlines, load_state
from tools.render_county_3d import build_segments, draw_caption, project, render


def build_colors(basins):
    palette = get_palette("neon")
    codes = sorted(set(basins))
    code_color = {c: palette[i % len(palette)] for i, c in enumerate(codes)}
    return [code_color[b] for b in basins], code_color


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="Washington")
    ap.add_argument("--min-order", type=int, default=3,
                    help="Drop streams below this Strahler order (thins clutter).")
    ap.add_argument("--yaw", type=float, default=22.0)
    ap.add_argument("--elev", type=float, default=24.0)
    ap.add_argument("--amp", type=float, default=0.5)
    ap.add_argument("--width", type=int, default=4000)
    ap.add_argument("--ss", type=int, default=2)
    ap.add_argument("--min-px", type=float, default=0.5)
    ap.add_argument("--max-px", type=float, default=5.0)
    ap.add_argument("--no-glow", action="store_true")
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

    colors, code_color = build_colors(basins)
    max_order = max(orders)
    print(f"basins: {sorted(code_color)}; stream orders 1..{max_order}; "
          f"flow 0..{max(flows):.0f} cfs")

    segs = build_segments(geoms, orders, flows, colors, max_order, args.amp)
    projected, sbounds = project(segs, args.yaw, args.elev)
    img = render(projected, sbounds, args.width, args.ss,
                 args.min_px, args.max_px, not args.no_glow)
    draw_caption(
        img,
        f"{args.state} — 3D hydrography (yaw {args.yaw:.0f} / elev {args.elev:.0f}) "
        f"· height = stream order · width = flow · order>={args.min_order}",
    )
    out = f"output/{args.state.lower()}_state_3d.png"
    img.save(out)
    print(f"wrote {out} ({img.size[0]}x{img.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
