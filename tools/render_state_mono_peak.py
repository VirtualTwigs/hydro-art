"""High-res *elevation* river print of a US state, sized at **peak flow**.

Combines two existing recipes:

* Color = NHDPlus smoothed *elevation* (white alpine summit -> deep-blue sea),
  exactly the hypsometric tint of ``render_state_mono.py``.
* Width = the state's **peak-flow month**, not the annual mean. The monthly
  climatology disaggregation of ``tools/monthly_flow.py`` turns each reach's
  mean-annual EROM discharge (``QAMA``) into a 12-month series; we pick the single
  month where the *whole network's* summed discharge peaks (snowmelt for the
  interior mountain states, winter rains for California) and freeze channel widths
  at that month. So the print shows the rivers at their seasonal fullest, tinted by
  height.

Unlike the year-in-motion GIF this is one still, so widths are normalized to the
peak month's own maximum (mainstem = ``--max-px``). Reaches missing monthly
climate fall back to their annual ``QAMA``.

    python tools/render_state_mono_peak.py --state Idaho --width 8000
    python tools/render_state_mono_peak.py --state California --width 8000
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.rendering import render_svg
from tools.monthly_flow import MONTH_ABBR, build_monthly_flow
from tools.render_common import (
    STATE_HUC4,
    clip_flowlines,
    flow_scaled_widths,
    gdb_paths,
    load_state,
)
from tools.render_state_mono import (
    BG,
    derive_elevations,
    elevation_colors,
    rasterize_whole,
)


def load_monthly_by_id(spec) -> dict[int, np.ndarray]:
    """Return ``{NHDPlusID: monthly flow [12] cfs}`` across every basin in ``spec``.

    Delegates the disaggregation to ``tools.monthly_flow.build_monthly_flow`` per
    GDB (the shared, mass-conserving model), merging the per-basin results.
    """
    out: dict[int, np.ndarray] = {}
    for gdb in gdb_paths(spec):
        code = Path(gdb).parent.name
        try:
            ids, flow, _qama = build_monthly_flow(gdb)
        except Exception as exc:  # noqa: BLE001 - skip a partial/corrupt GDB
            print(f"  monthly skip {code}: {exc}")
            continue
        for i, row in zip(ids, flow):
            out[int(i)] = row
        print(f"  {code}: monthly for {len(ids)} reaches")
    return out


def peak_month_flows(nhdids, qama, monthly_by_id):
    """Pick the network's peak-flow month and return per-reach flow at that month.

    Assembles an ``[n, 12]`` matrix (each reach's monthly series, or its flat
    ``QAMA`` when it has no monthly climatology), sums across reaches to find the
    single month of maximum total discharge, and returns
    ``(peak_flows[n], peak_month_index)``.
    """
    n = len(nhdids)
    matrix = np.empty((n, 12), dtype=float)
    for k, (iid, q) in enumerate(zip(nhdids, qama)):
        row = monthly_by_id.get(int(iid))
        matrix[k] = row if row is not None else np.full(12, q, dtype=float)
    totals = matrix.sum(axis=0)
    peak = int(np.argmax(totals))
    return matrix[:, peak], peak


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="Idaho")
    ap.add_argument("--min-order", type=int, default=4,
                    help="Drop streams below this Strahler order (higher = sparser).")
    ap.add_argument("--width", type=int, default=8000,
                    help="Output raster width in px (print quality; default 8000).")
    ap.add_argument("--min-px", type=float, default=0.8,
                    help="Stroke width (px) for the lowest-flow headwater channels.")
    ap.add_argument("--max-px", type=float, default=4.2,
                    help="Stroke width (px) for the highest-flow peak-month mainstem.")
    ap.add_argument("--gamma", type=float, default=0.75,
                    help="Elevation ramp shaping; <1 brightens mid-slopes.")
    ap.add_argument("--metric", choices=["mean", "max"], default="max",
                    help="Per-reach elevation used for color: reach mean or its "
                         "highest (upstream) point.")
    ap.add_argument("--anchor-pct", type=float, default=97.0,
                    help="Percentile of reach elevation that maps to pure white.")
    ap.add_argument("--glow", action="store_true",
                    help="Add a soft neon bloom (dims thin hairlines; off by default).")
    args = ap.parse_args()

    spec = STATE_HUC4.get(args.state)
    if not spec:
        raise SystemExit(f"No HUC4 mapping for {args.state!r}; add it to STATE_HUC4.")

    tag = args.state.lower().replace(" ", "_")
    # Cache the (expensive) clip + monthly disaggregation so ramp/width iterations
    # are instant. Keyed by state + min_order.
    cache = Path(f"output/_peakcache_{tag}_mo{args.min_order}.pkl")
    if cache.exists():
        print(f"loading cached clip+monthly {cache} ...")
        geoms, elev_mean, elev_max, qama, nhdids, monthly = pickle.loads(
            cache.read_bytes()
        )
    else:
        print(f"loading {args.state} boundary ...")
        boundary = load_state(args.state)
        print(f"clipping flowlines (min_order={args.min_order}) from {spec} ...")
        geoms, _orders, qama, _basins, extras = clip_flowlines(
            boundary, spec, args.min_order,
            extra_vaa_cols=["MinElevSmo", "MaxElevSmo"],
            include_id=True,
        )
        elev_mean, elev_max = derive_elevations(
            extras["MinElevSmo"], extras["MaxElevSmo"]
        )
        nhdids = extras["nhdplus_id"]
        print(f"disaggregating monthly flow from {spec} ...")
        monthly_by_id = load_monthly_by_id(spec)
        # Freeze the per-geom monthly rows so the cache is self-contained.
        monthly = [
            (monthly_by_id.get(int(i)).tolist()
             if monthly_by_id.get(int(i)) is not None else None)
            for i in nhdids
        ]
        cache.write_bytes(
            pickle.dumps((geoms, elev_mean, elev_max, qama, nhdids, monthly))
        )
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the state boundary.")

    # Rebuild the id->monthly map from the cached per-geom rows.
    monthly_by_id = {
        int(i): np.asarray(row, dtype=float)
        for i, row in zip(nhdids, monthly)
        if row is not None
    }
    peak_flows, peak = peak_month_flows(nhdids, qama, monthly_by_id)

    elevs = elev_max if args.metric == "max" else elev_mean
    anchor = float(np.percentile(np.clip(elevs, 0.0, None), args.anchor_pct))
    geometries = {i: g for i, g in enumerate(geoms)}
    segment_colors, emax = elevation_colors(elevs, args.gamma, anchor)
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, peak_flows.tolist(), args.width, args.min_px, args.max_px
    )
    print(f"peak-flow month: {MONTH_ABBR[peak]} "
          f"({len([1 for r in monthly if r is not None])}/{len(nhdids)} reaches w/ "
          f"monthly climate)")
    print(f"elevation ({args.metric}) 0..{emax:.0f} m -> deep-blue..white "
          f"(anchor p{args.anchor_pct:g}); peak flow 0..{qmax:.0f} cfs -> "
          f"{args.min_px}..{args.max_px}px ({units_per_px:.2f} m/px)")

    # Empty watersheds => every path keeps its own elevation color.
    svg = render_svg(
        geometries, segment_colors, {},
        background=BG, line_width=base_units, stroke_widths=widths,
        glow=args.glow, glow_mode="blur", glow_radius=2.0,
    )
    svg_out = f"output/{tag}_elevation_peak.svg"
    png_out = f"output/{tag}_elevation_peak.png"
    Path(svg_out).write_text(svg)
    print(f"wrote {svg_out} ({len(svg)} bytes, {len(geometries)} paths)")
    rasterize_whole(svg, png_out, args.width, args.max_px)
    print(f"wrote {png_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
