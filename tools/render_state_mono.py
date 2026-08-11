"""Monochromatic *elevation* river map for a US state (white summit -> deep-blue sea).

Unlike the neon basin-colored siblings (``render_state_svg.py`` colors each ``<g>``
by HUC4 basin), this renderer paints every flowline by its **stream-surface
elevation**: the single highest stream point in the state is pure white and sea
level (0 m) is a deep blue, with one shared ramp applied to all streams. So the
whole network reads as a hypsometric tint -- bright alpine headwaters fading down
to dark tidewater mainstems.

Elevation is the NHDPlus HR smoothed flowline elevation (``MinElevSmo`` /
``MaxElevSmo`` in ``NHDPlusFlowlineVAA``, centimetres; the ``-9998`` no-data
sentinel is treated as sea level). Each reach is colored by its mean smoothed
elevation, normalized so the state's maximum reach elevation maps to white.

Widths still taper by NHDPlus EROM mean-annual discharge (``QAMA``) for the same
elegant confluence swell as the other renderers. Per-path colors require the
color-``None`` ``rivers_unassigned`` group (a watershed ``<g>`` would repaint all
its paths one color), so this bypasses ``build_inputs``.

    python tools/render_state_mono.py --state Washington --min-order 4
"""

from __future__ import annotations

import argparse
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import shapely

from src.rendering import bounds, render_svg
from tools.render_common import (
    EPSG,
    STATE_HUC4,
    flow_scaled_widths,
    gdb_paths,
    load_state,
)

#: Deep-blue (sea level) -> white (highest stream point) monochromatic ramp.
#: The low anchor stays a visibly saturated blue (not near-black) so tidewater
#: reaches still read as blue against the dark ground.
DEEP_BLUE = (26, 72, 156)
WHITE = (255, 255, 255)
BG = "#04060c"

#: Background for the elevation-tinted infographic map (a touch lighter than the
#: still renderer's ``BG`` so the deep-blue tidewater reaches stay legible when
#: composited beside the key panel).
MAP_BG = "#05070d"

#: NHDPlus no-data sentinel for the smoothed-elevation fields (centimetres).
ELEV_NODATA = -9998.0


def load_elevations(spec, keep_ids: set[int]) -> dict[int, float]:
    """Return ``{NHDPlusID: max smoothed elevation (m)}`` for the kept reaches.

    Reads ``MaxElevSmo``/``MinElevSmo`` (centimetres) from each basin's
    ``NHDPlusFlowlineVAA`` and keeps the higher (upstream) endpoint per reach --
    the same "max" metric :func:`main` uses so the infographic tint matches the
    still map. The ``-9998`` no-data sentinel maps to sea level (0 m). Only ids in
    ``keep_ids`` are returned, so the caller can align colors to its geometry set.
    """
    out: dict[int, float] = {}
    for gdb in gdb_paths(spec):
        vaa = gpd.read_file(
            gdb, layer="NHDPlusFlowlineVAA",
            columns=["NHDPlusID", "MinElevSmo", "MaxElevSmo"],
            read_geometry=False,
        )
        for i, mn, mx in zip(vaa["NHDPlusID"], vaa["MinElevSmo"], vaa["MaxElevSmo"]):
            iid = int(i)
            if iid not in keep_ids:
                continue
            vals = [v for v in (mn, mx) if v is not None and v > ELEV_NODATA]
            out[iid] = (float(max(vals)) / 100.0) if vals else 0.0
    return out


def clip_flowlines_elev(boundary, spec, min_order: int):
    """Clip NHD flowlines under ``spec`` to ``boundary``, carrying elevation + flow.

    Mirrors :func:`tools.render_common.clip_flowlines` but joins the smoothed
    flowline elevation (``MinElevSmo``/``MaxElevSmo``, metres) alongside ``QAMA``.
    Each reach carries both its mean and its max smoothed elevation so the color
    ramp can pick a metric later. Returns ``(geoms, elev_mean, elev_max, flows)``.
    """
    shapely.prepare(boundary)
    geoms: list = []
    elev_mean: list[float] = []
    elev_max: list[float] = []
    flows: list[float] = []
    for gdb in gdb_paths(spec):
        code = Path(gdb).parent.name
        try:
            f = gpd.read_file(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
        except Exception as exc:  # noqa: BLE001 - skip a partial/corrupt GDB
            print(f"  skip {code}: {exc}")
            continue
        vaa = gpd.read_file(
            gdb, layer="NHDPlusFlowlineVAA",
            columns=["NHDPlusID", "StreamOrde", "MinElevSmo", "MaxElevSmo"],
            read_geometry=False,
        )
        order_by_id = dict(zip(vaa["NHDPlusID"], vaa["StreamOrde"]))

        def _elev(row_min, row_max):
            vals = [v for v in (row_min, row_max) if v is not None and v > ELEV_NODATA]
            if not vals:
                return 0.0, 0.0
            return float(np.mean(vals)) / 100.0, float(max(vals)) / 100.0

        elev_by_id = {
            i: _elev(mn, mx)
            for i, mn, mx in zip(vaa["NHDPlusID"], vaa["MinElevSmo"], vaa["MaxElevSmo"])
        }
        erom = gpd.read_file(
            gdb, layer="NHDPlusEROMMA",
            columns=["NHDPlusID", "QAMA"], read_geometry=False,
        )
        flow_by_id = dict(zip(erom["NHDPlusID"], erom["QAMA"]))

        seg_orders = (
            f["NHDPlusID"].map(lambda i: int(order_by_id.get(i, 1) or 1)).to_numpy()
        )
        seg_em = f["NHDPlusID"].map(lambda i: elev_by_id.get(i, (0.0, 0.0))[0]).to_numpy()
        seg_ex = f["NHDPlusID"].map(lambda i: elev_by_id.get(i, (0.0, 0.0))[1]).to_numpy()
        seg_flows = (
            f["NHDPlusID"].map(lambda i: float(flow_by_id.get(i, 0.0) or 0.0)).to_numpy()
        )
        if min_order > 1:
            keep = seg_orders >= min_order
            f = f[keep]
            seg_em = seg_em[keep]
            seg_ex = seg_ex[keep]
            seg_flows = seg_flows[keep]
        f = f.to_crs(EPSG)
        arr = np.array(f.geometry.values, dtype=object)
        covered = shapely.covers(boundary, arr)
        crossing = shapely.intersects(boundary, arr) & ~covered

        kept0 = len(geoms)
        for gi in np.nonzero(covered)[0]:
            geoms.append(arr[gi])
            elev_mean.append(float(seg_em[gi]))
            elev_max.append(float(seg_ex[gi]))
            flows.append(float(seg_flows[gi]))
        cross_idx = np.nonzero(crossing)[0]
        if cross_idx.size:
            trimmed = shapely.intersection(boundary, arr[cross_idx])
            for local_i, gi in enumerate(cross_idx):
                g = trimmed[local_i]
                if not g.is_empty:
                    geoms.append(g)
                    elev_mean.append(float(seg_em[gi]))
                    elev_max.append(float(seg_ex[gi]))
                    flows.append(float(seg_flows[gi]))
        print(f"  {code}: kept {len(geoms) - kept0}")
    return geoms, elev_mean, elev_max, flows


def elevation_colors(elevs, gamma: float, anchor: float | None = None):
    """Map per-reach elevation (m) -> deep-blue..white hex, anchored at the max.

    ``t = (elev / anchor) ** gamma``; ``t=0`` (sea level) is deep blue and the
    highest stream reach (``t=1``) is white. ``gamma < 1`` lifts the mid-slopes
    toward white; ``> 1`` keeps more of the network in deep blue. ``anchor``
    overrides the white point (defaults to the max elevation in ``elevs``) so a
    percentile can pull more of the high country toward white.
    Returns ``(colors_by_index, anchor_elev)``.
    """
    arr = np.clip(np.asarray(elevs, dtype=float), 0.0, None)
    emax = anchor if anchor else (float(arr.max()) if arr.size else 0.0)
    t = np.zeros_like(arr) if emax <= 0 else np.clip(arr / emax, 0.0, 1.0) ** gamma
    b = np.array(DEEP_BLUE, dtype=float)
    w = np.array(WHITE, dtype=float)
    colors: dict[int, str] = {}
    for i, ti in enumerate(t):
        r, g, bl = (b + (w - b) * ti).round().astype(int)
        colors[i] = f"#{r:02x}{g:02x}{bl:02x}"
    return colors, emax


def rasterize_whole(svg: str, png_path: str, width: int, stroke_px: float,
                    glow_px: float = 2.0) -> None:
    """Rescale meter-unit stroke/glow to pixels, then one ``resvg`` call.

    The document authors stroke widths in projected metres; ``resvg`` needs the
    root ``stroke-width`` and the glow ``stdDeviation`` in the SVG's own units, so
    rescale both by ``units_per_px`` before rendering the whole document at once
    (fast; fine while the path count stays under librsvg/resvg's ~1M-node cap).
    """
    import re

    m = re.search(r'viewBox="0 0 ([0-9.]+) ', svg)
    vb_w = float(m.group(1))
    units_per_px = vb_w / width
    stroke_units = stroke_px * units_per_px
    glow_units = glow_px * units_per_px
    svg = re.sub(r'(stroke-width=")[0-9.]+(")',
                 rf'\g<1>{stroke_units:.4f}\g<2>', svg, count=1)
    svg = re.sub(r'(stdDeviation=")[0-9.]+(")',
                 rf'\g<1>{glow_units:.4f}\g<2>', svg)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tmp:
        tmp.write(svg)
        tmp_path = tmp.name
    subprocess.run(["resvg", "--width", str(width), tmp_path, str(png_path)],
                   check=True)
    Path(tmp_path).unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="Washington")
    ap.add_argument("--min-order", type=int, default=4,
                    help="Drop streams below this Strahler order (higher = sparser).")
    ap.add_argument("--width", type=int, default=6000,
                    help="Reference px width the stroke widths are authored against.")
    ap.add_argument("--min-px", type=float, default=0.8,
                    help="Stroke width (px) for the lowest-flow headwater channels.")
    ap.add_argument("--max-px", type=float, default=3.8,
                    help="Stroke width (px) for the highest-flow mainstem.")
    ap.add_argument("--gamma", type=float, default=0.75,
                    help="Elevation ramp shaping; <1 brightens mid-slopes.")
    ap.add_argument("--metric", choices=["mean", "max"], default="max",
                    help="Per-reach elevation used for color: reach mean or its "
                         "highest (upstream) point.")
    ap.add_argument("--anchor-pct", type=float, default=97.0,
                    help="Percentile of reach elevation that maps to pure white "
                         "(100 = the single highest stream point; a touch below "
                         "lets the whole high country reach white).")
    ap.add_argument("--glow", action="store_true",
                    help="Add a soft neon bloom (dims thin hairlines; off by default).")
    args = ap.parse_args()

    spec = STATE_HUC4.get(args.state)
    if not spec:
        raise SystemExit(f"No HUC4 mapping for {args.state!r}; add it to STATE_HUC4.")

    # Clipping reads several multi-GB GDBs over SMB (~3 min); cache the result so
    # color/ramp iterations are instant. Keyed by state + min_order.
    tag = args.state.lower().replace(" ", "_")
    cache = Path(f"output/_clipcache_{tag}_mo{args.min_order}.pkl")
    if cache.exists():
        print(f"loading cached clip {cache} ...")
        geoms, elev_mean, elev_max, flows = pickle.loads(cache.read_bytes())
    else:
        print(f"loading {args.state} boundary ...")
        boundary = load_state(args.state)
        print(f"clipping flowlines (min_order={args.min_order}) from {spec} ...")
        geoms, elev_mean, elev_max, flows = clip_flowlines_elev(
            boundary, spec, args.min_order
        )
        cache.write_bytes(pickle.dumps((geoms, elev_mean, elev_max, flows)))
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the state boundary.")

    elevs = elev_max if args.metric == "max" else elev_mean
    anchor = float(np.percentile(np.clip(elevs, 0.0, None), args.anchor_pct))
    geometries = {i: g for i, g in enumerate(geoms)}
    segment_colors, emax = elevation_colors(elevs, args.gamma, anchor)
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px
    )
    print(f"elevation ({args.metric}) 0..{emax:.0f} m -> deep-blue..white "
          f"(anchor p{args.anchor_pct:g}); flow 0..{qmax:.0f} cfs -> "
          f"{args.min_px}..{args.max_px}px ({units_per_px:.2f} m/px)")

    # Empty watersheds => every path lands in the color-None group, so each
    # path keeps its own elevation color (a watershed <g> would override them).
    svg = render_svg(
        geometries, segment_colors, {},
        background=BG, line_width=base_units, stroke_widths=widths,
        glow=args.glow, glow_mode="blur", glow_radius=2.0,
    )
    svg_out = f"output/{tag}_elevation.svg"
    png_out = f"output/{tag}_elevation.png"
    Path(svg_out).write_text(svg)
    print(f"wrote {svg_out} ({len(svg)} bytes, {len(geometries)} paths)")
    rasterize_whole(svg, png_out, args.width, args.max_px)
    print(f"wrote {png_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
