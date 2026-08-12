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
import shapely
from PIL import Image, ImageDraw, ImageFont

from src.rendering import bounds, widths_on_span
from tools.monthly_flow import MONTH_ABBR, build_monthly_flow
from tools.render_common import (
    CLARK_BBOX_4326,
    EPSG,
    assign_subwatersheds,
    bbox_boundary,
    build_inputs,
    gdb_paths,
    rasterize,
    render_art_svg,
)

FLOOR = 1e-2  # min flow substituted before log (keeps dry headwaters finite)
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def load_basin_flowlines(spec, min_order: int, boundary=None):
    """Load NHD flowlines for ``spec``, keeping ``NHDPlusID`` for the monthly join.

    If ``boundary`` (EPSG:5070) is given, flowlines are clipped to it (covered
    ones kept whole, crossing ones trimmed). Returns parallel lists
    ``(geoms, ids, orders)`` reprojected to EPSG:5070.
    """
    if boundary is not None:
        shapely.prepare(boundary)
    geoms, ids, orders = [], [], []
    for gdb in gdb_paths(spec):
        try:
            f = gpd.read_file(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
        except Exception as exc:  # noqa: BLE001 - skip a partial/corrupt GDB
            print(f"  skip {Path(gdb).parent.name}: {exc}")
            continue
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
        seg_ids = f["NHDPlusID"].to_numpy()
        arr = np.array(f.geometry.values, dtype=object)
        if boundary is not None:
            covered = shapely.covers(boundary, arr)
            crossing = shapely.intersects(boundary, arr) & ~covered
            for gi in np.nonzero(covered)[0]:
                geoms.append(arr[gi]); ids.append(int(seg_ids[gi]))
                orders.append(int(seg_orders[gi]))
            cross_idx = np.nonzero(crossing)[0]
            if cross_idx.size:
                trimmed = shapely.intersection(boundary, arr[cross_idx])
                for local_i, gi in enumerate(cross_idx):
                    g = trimmed[local_i]
                    if not g.is_empty:
                        geoms.append(g); ids.append(int(seg_ids[gi]))
                        orders.append(int(seg_orders[gi]))
        else:
            for g, i, o in zip(arr, seg_ids, seg_orders):
                geoms.append(g); ids.append(int(i)); orders.append(int(o))
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
    """Map one month's flows to stroke widths on a *fixed* global log scale.

    Thin wrapper over :func:`src.rendering.widths_on_span` (the shared source of
    truth); ``base_units``/``top_units`` map to ``width_min``/``width_max``.
    """
    return widths_on_span(
        month_flow, lo, hi, width_min=base_units, width_max=top_units, floor=FLOOR
    )


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


def frame_phase(i: int, n: int) -> tuple[int, int, float, str]:
    """Map frame ``i`` of ``n`` to a cyclic month interpolation + date label.

    ``phase`` runs [0, 12) over the year; returns the bracketing month indices
    ``(m0, m1)``, the blend fraction, and a ``"Mon DD"`` label. For ``n == 12``
    the phase lands on whole months (exact monthly values); ``n == 24`` gives
    semi-monthly frames, etc.
    """
    phase = i * 12.0 / n
    m0 = int(phase) % 12
    frac = phase - int(phase)
    m1 = (m0 + 1) % 12
    day = int(frac * DAYS[m0]) + 1
    return m0, m1, frac, f"{MONTH_ABBR[m0]} {day:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clark", action="store_true",
                    help="Clip to Clark County, WA (bbox) instead of a whole basin.")
    ap.add_argument("--huc4", default=None, help="HUC4 basin spec (e.g. 1709).")
    ap.add_argument("--frames", type=int, default=12,
                    help="Number of frames; 12=monthly, 24=semi-monthly (the "
                         "monthly curve is linearly interpolated between).")
    ap.add_argument("--min-order", type=int, default=None,
                    help="Drop streams below this Strahler order.")
    ap.add_argument("--huc-digits", type=int, default=None,
                    help="WBD level for sub-watershed coloring.")
    ap.add_argument("--width", type=int, default=2400, help="Raster width in px.")
    ap.add_argument("--min-px", type=float, default=0.8,
                    help="Stroke width for the lowest annual-min flow.")
    ap.add_argument("--max-px", type=float, default=9.0,
                    help="Stroke width for the highest annual-max flow.")
    ap.add_argument("--activation", type=float, default=0.5,
                    help="A reach is drawn in a frame when its flow is at least "
                         "this fraction of its own annual peak; smaller streams "
                         "drain out of dry months (0 = always draw all).")
    ap.add_argument("--persist", type=float, default=0.03,
                    help="Reaches above this fraction of the region's peak flow "
                         "stay lit year-round (keeps major rivers from vanishing "
                         "in summer, so frames never go empty).")
    ap.add_argument("--ms-per-frame", type=int, default=300)
    args = ap.parse_args()

    # Clark County pulls smaller, denser defaults than a whole HUC4 basin.
    if args.clark:
        spec = args.huc4 or "1708"  # Lower Columbia basin covers Clark County
        boundary = bbox_boundary(CLARK_BBOX_4326)
        min_order = args.min_order if args.min_order is not None else 2
        huc_digits = args.huc_digits if args.huc_digits is not None else 12
        tag, region_name = "clark_county", "Clark County, WA"
    else:
        spec = args.huc4 or "1709"
        boundary = None
        min_order = args.min_order if args.min_order is not None else 4
        huc_digits = args.huc_digits if args.huc_digits is not None else 8
        tag, region_name = f"huc4_{spec}", f"HUC4 {spec}"

    print(f"loading flowlines (spec={spec}, min_order={min_order}, "
          f"clip={'Clark' if boundary is not None else 'none'}) ...")
    geoms, ids, orders = load_basin_flowlines(spec, min_order, boundary)
    if not geoms:
        raise SystemExit("No flowlines matched; lower --min-order.")
    print(f"  {len(geoms)} paths, orders 1..{max(orders)}")

    print("computing monthly flows ...")
    flow_map = monthly_flow_by_id(spec)

    print(f"coloring by HUC{huc_digits} ...")
    codes, names = assign_subwatersheds(geoms, huc_digits)
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

    # Each reach is "active" in a frame only near its own annual peak; below that
    # its width is zeroed so SVG paints nothing. Geometries stay in the set every
    # frame (bounds/framing pinned), only the visible network pulses.
    annual_max = monthly.max(axis=1)
    persist_floor = args.persist * math.exp(hi)  # absolute cfs; major rivers stay lit

    out_dir = Path("output/monthly")
    out_dir.mkdir(parents=True, exist_ok=True)
    subtitle = f"{region_name} - flow ({args.frames} frames/yr, min order {min_order})"
    frames: list[Image.Image] = []
    for i in range(args.frames):
        m0, m1, frac, label = frame_phase(i, args.frames)
        flow_i = monthly[:, m0] * (1 - frac) + monthly[:, m1] * frac
        frame_flow = {idx: flow_i[idx] for idx in geometries}
        widths = fixed_widths(frame_flow, base_units, top_units, lo, hi)
        active = 0
        for idx in geometries:
            q = flow_i[idx]
            visible = q > 0 and (q >= args.activation * annual_max[idx]
                                 or q >= persist_floor)
            if visible:
                active += 1
            else:
                widths[idx] = 0.0  # drained out this frame -> paints nothing
        svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
        svg_path = out_dir / f"{tag}_{i + 1:02d}.svg"
        png_path = out_dir / f"{tag}_{i + 1:02d}.png"
        svg_path.write_text(svg)
        rasterize(str(svg_path), str(png_path), args.width, args.max_px)
        print(f"  {label}: {active:>6,} streams active, "
              f"sum flow {sum(frame_flow.values()):,.0f} cfs")
        frames.append(_label(str(png_path), label, subtitle))

    gif_path = f"output/monthly_flow_{tag}_{args.frames}f.gif"
    frames[0].save(
        gif_path, save_all=True, append_images=frames[1:],
        duration=args.ms_per_frame, loop=0, optimize=True,
    )
    print(f"\nwrote {gif_path} ({args.frames} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
