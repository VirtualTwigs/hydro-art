"""Render a 12-frame "year in motion" GIF where channel width tracks monthly flow.

Ties together :mod:`tools.monthly_flow` (which disaggregates each reach's
mean-annual ``QAMA`` into 12 monthly flows from real NHDPlus precip/temperature)
and the shared neon-glow render recipe (:mod:`tools.render_common`). For a chosen
HUC4 basin it renders one flow-scaled SVG per month, rasterizes each, labels it,
and assembles an animated GIF -- so you watch the network swell through the wet
season / snowmelt and thin out in late summer.

The key trick vs. the static renderers: the log flow->width mapping is computed
**once** across *all twelve months* and held fixed, so a fat January mainstem
really looks fatter than its trickle in August. If each frame renormalized to its
own min/max, the seasonal change would be invisible.

Whole-basin renders are large; ``--min-order`` thins headwaters for a cleaner,
faster animation (raise it to shrink, lower it for detail). Like every ``tools/``
script it needs the full GIS stack + real datasets (not offline).

    python tools/render_monthly.py --huc4 1709 --min-order 4
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

from src.rendering import bounds
from tools.monthly_flow import MONTH_ABBR, build_monthly_flow
from tools.render_common import (
    EPSG,
    assign_subwatersheds,
    build_inputs,
    gdb_paths,
    rasterize,
    render_art_svg,
)

FLOOR = 1e-2  # min flow substituted before log (keeps dry headwaters finite)


def load_basin_flowlines(spec, min_order: int):
    """Load NHD flowlines for ``spec``, keeping ``NHDPlusID`` for the monthly join.

    Returns parallel lists ``(geoms, ids, orders)`` reprojected to EPSG:5070.
    """
    geoms, ids, orders = [], [], []
    for gdb in gdb_paths(spec):
        f = gpd.read_file(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
        vaa = gpd.read_file(
            gdb, layer="NHDPlusFlowlineVAA",
            columns=["NHDPlusID", "StreamOrde"], read_geometry=False,
        )
        order_by_id = dict(zip(vaa["NHDPlusID"], vaa["StreamOrde"]))
        seg_orders = f["NHDPlusID"].map(
            lambda i: int(order_by_id.get(i, 1) or 1)
        ).to_numpy()
        if min_order > 1:
            keep = seg_orders >= min_order
            f = f[keep]
            seg_orders = seg_orders[keep]
        f = f.to_crs(EPSG)
        for g, i, o in zip(f.geometry.values, f["NHDPlusID"].values, seg_orders):
            geoms.append(g)
            ids.append(int(i))
            orders.append(int(o))
    return geoms, ids, orders


def monthly_flow_by_id(spec) -> dict[int, np.ndarray]:
    """Union each GDB's ``id -> [12 cfs]`` monthly flow map for ``spec``."""
    out: dict[int, np.ndarray] = {}
    for gdb in gdb_paths(spec):
        gids, flow, _ = build_monthly_flow(gdb)
        for i, row in zip(gids, flow):
            out[int(i)] = row
    return out


def fixed_widths(month_flow, base_units: float, top_units: float,
                 lo: float, hi: float) -> dict[int, float]:
    """Map one month's flows to stroke widths on a *fixed* global log scale."""
    span = max(hi - lo, 1e-9)
    return {
        idx: base_units + (top_units - base_units)
        * min(max((math.log(max(q, FLOOR)) - lo) / span, 0.0), 1.0)
        for idx, q in month_flow.items()
    }


def _label(png_path: str, month: str, subtitle: str) -> Image.Image:
    """Open a rasterized frame and stamp the month + subtitle."""
    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im)
    fs = max(48, W // 22)

    def font(sz):
        for p in ("/System/Library/Fonts/SFNSMono.ttf",
                  "/System/Library/Fonts/Menlo.ttc"):
            try:
                return ImageFont.truetype(p, size=sz)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()

    draw.text((fs, fs), month, fill=(235, 239, 248), font=font(fs))
    draw.text((fs, fs + int(fs * 1.2)), subtitle, fill=(120, 150, 200),
              font=font(int(fs * 0.4)))
    return im


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--huc4", default="1709", help="HUC4 basin spec (e.g. 1709).")
    ap.add_argument("--min-order", type=int, default=4,
                    help="Drop streams below this Strahler order.")
    ap.add_argument("--huc-digits", type=int, default=8,
                    help="WBD level for sub-watershed coloring.")
    ap.add_argument("--width", type=int, default=2400,
                    help="Raster width in px.")
    ap.add_argument("--min-px", type=float, default=0.8,
                    help="Stroke width for the lowest annual-min flow.")
    ap.add_argument("--max-px", type=float, default=9.0,
                    help="Stroke width for the highest annual-max flow.")
    ap.add_argument("--ms-per-frame", type=int, default=450)
    args = ap.parse_args()

    print(f"loading flowlines (huc4={args.huc4}, min_order={args.min_order}) ...")
    geoms, ids, orders = load_basin_flowlines(args.huc4, args.min_order)
    if not geoms:
        raise SystemExit("No flowlines matched; lower --min-order.")
    print(f"  {len(geoms)} paths, orders 1..{max(orders)}")

    print("computing monthly flows ...")
    flow_map = monthly_flow_by_id(args.huc4)

    print(f"coloring by HUC{args.huc_digits} ...")
    codes, names = assign_subwatersheds(geoms, args.huc_digits)
    geometries, segment_colors, watersheds, _ = build_inputs(geoms, codes)

    # Per-geometry monthly flow matrix [n, 12], aligned to geometries' indices.
    monthly = np.zeros((len(geoms), 12))
    for idx in geometries:
        row = flow_map.get(ids[idx])
        if row is not None:
            monthly[idx] = row

    # Fixed global log scale across ALL months (so seasonal change is visible).
    positive = monthly[monthly > 0]
    lo = math.log(max(positive.min(), FLOOR)) if positive.size else 0.0
    hi = math.log(positive.max()) if positive.size else 1.0
    min_x, _, max_x, _ = bounds(geometries.values())
    units_per_px = (max_x - min_x) / args.width
    base_units, top_units = args.min_px * units_per_px, args.max_px * units_per_px
    print(f"  flow scale {math.exp(lo):.2f}..{math.exp(hi):.0f} cfs (fixed across year)")

    out_dir = Path("output/monthly")
    out_dir.mkdir(parents=True, exist_ok=True)
    subtitle = f"HUC4 {args.huc4} - monthly flow (min order {args.min_order})"
    frames: list[Image.Image] = []
    for m in range(12):
        month_flow = {idx: monthly[idx, m] for idx in geometries}
        widths = fixed_widths(month_flow, base_units, top_units, lo, hi)
        svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
        svg_path = out_dir / f"frame_{m + 1:02d}.svg"
        png_path = out_dir / f"frame_{m + 1:02d}.png"
        svg_path.write_text(svg)
        rasterize(str(svg_path), str(png_path), args.width, args.max_px)
        total = sum(month_flow.values())
        print(f"  {MONTH_ABBR[m]}: sum flow {total:,.0f} cfs")
        frames.append(_label(str(png_path), MONTH_ABBR[m], subtitle))

    gif_path = f"output/monthly_flow_{args.huc4}.gif"
    frames[0].save(
        gif_path, save_all=True, append_images=frames[1:],
        duration=args.ms_per_frame, loop=0, optimize=True,
    )
    print(f"\nwrote {gif_path} (12 frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
