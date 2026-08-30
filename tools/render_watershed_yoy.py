"""True year-over-year river print of a *single named watershed* (HUC12 group).

A watershed-scoped sibling of ``render_state_yoy.py``. Where that tool walks a
whole state's HUC4 basins, this one clips a single HUC4's flowlines to a set of
WBD ``WBDHU12`` sub-watershed polygons (e.g. the two Salmon Creek HUC12s that
make up the Salmon Creek watershed in Clark County, WA) and renders one frame per
real calendar year: color is the constant hypsometric elevation tint
(``render_state_mono``), width is that year's flow at the network's peak month, on
a **fixed cross-year log span** so wet/drought years differ in thickness.

Flow is the shared, offline engine (``src.historical_flow.yearly_flow_series``,
#44) driven by the real PRISM provider (``tools.historical_flow``, #45): the flow
is accumulated over the *whole* parent HUC4 network (so a reach's upstream
contribution is correct) and then mapped by ``NHDPlusID`` onto the clipped
watershed reaches.

    python tools/render_watershed_yoy.py \
        --huc4 1708 --huc12 170800030102 170800030103 \
        --name "Salmon Creek" --start 2014 --end 2023

Needs the PRISM grids staged first (see ``tools/prism_fetch.py``) and reuses the
per-basin network cache ``output/_yoy_net_<huc4>.pkl`` if present.
"""

from __future__ import annotations

import argparse
import glob
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import pandas as pd

from src.historical_flow import normalize_years
from src.rendering import bounds, fixed_flow_span, render_svg, widths_on_span
from tools.historical_flow import DEFAULT_ROOT
from tools.monthly_flow import MONTH_ABBR
from tools.render_common import EPSG, WBD_GLOB, clip_flowlines
from tools.render_state_mono import (
    BG,
    derive_elevations,
    elevation_colors,
    rasterize_whole,
)
from tools.render_state_yoy import _label, yearly_flow_by_id

FLOOR = 1e-2


def load_huc12_boundary(codes):
    """Return the (unioned, EPSG:5070) boundary of the given ``WBDHU12`` codes."""
    codes = {str(c) for c in codes}
    frames = []
    for gdb in sorted(glob.glob(WBD_GLOB, recursive=True)):
        try:
            g = gpd.read_file(gdb, layer="WBDHU12", columns=["huc12", "name"])
        except Exception:  # noqa: BLE001 - a WBD GDB without this layer
            continue
        sel = g[g["huc12"].astype(str).isin(codes)]
        if not sel.empty:
            frames.append(sel)
    if not frames:
        raise SystemExit(f"No WBDHU12 polygons matched {sorted(codes)}.")
    hus = pd.concat(frames, ignore_index=True).drop_duplicates("huc12")
    names = ", ".join(hus["name"].astype(str))
    print(f"watershed: {len(hus)} HUC12 -> {names}")
    return hus.to_crs(EPSG).geometry.union_all()


def clip_watershed(boundary, huc4, min_order):
    """Clip ``huc4`` flowlines to ``boundary`` -> (geoms, elev_max, nhdids).

    Carries each reach's smoothed elevation (for the hypsometric tint) and its
    ``NHDPlusID`` (the join key onto the PRISM year-over-year flow series).
    """
    geoms, _orders, _flows, _basins, extras = clip_flowlines(
        boundary, huc4, min_order,
        extra_vaa_cols=["MinElevSmo", "MaxElevSmo"], include_id=True,
    )
    _elev_mean, elev_max = derive_elevations(
        extras["MinElevSmo"], extras["MaxElevSmo"]
    )
    return geoms, elev_max, extras["nhdplus_id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--huc4", default="1708", help="Parent NHDPlus HR HUC4 basin.")
    ap.add_argument("--huc12", nargs="+", default=["170800030102", "170800030103"],
                    help="WBDHU12 codes making up the watershed.")
    ap.add_argument("--name", default="Salmon Creek", help="Label for the frames.")
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2023)
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="External root holding prism/<var>/ grids.")
    ap.add_argument("--min-order", type=int, default=1,
                    help="Strahler filter (1 keeps the whole small-creek network).")
    ap.add_argument("--width", type=int, default=3200)
    ap.add_argument("--min-px", type=float, default=0.8)
    ap.add_argument("--max-px", type=float, default=6.0)
    ap.add_argument("--gamma", type=float, default=0.8)
    ap.add_argument("--anchor-pct", type=float, default=97.0)
    ap.add_argument("--ms-per-frame", type=int, default=700)
    ap.add_argument("--glow", action="store_true", default=True)
    ap.add_argument("--no-glow", dest="glow", action="store_false")
    args = ap.parse_args()

    tag = args.name.lower().replace(" ", "_")

    # Clip cache (geometry + elevation + ids) so notebook + ramp tweaks stay fast.
    clip_cache = Path(f"output/_wshed_{tag}_mo{args.min_order}.pkl")
    if clip_cache.exists():
        print(f"loading cached clip {clip_cache} ...")
        geoms, elev_max, nhdids = pickle.loads(clip_cache.read_bytes())
    else:
        boundary = load_huc12_boundary(args.huc12)
        print(f"clipping {args.huc4} flowlines (min_order={args.min_order}) ...")
        geoms, elev_max, nhdids = clip_watershed(boundary, args.huc4, args.min_order)
        clip_cache.write_bytes(pickle.dumps((geoms, elev_max, nhdids)))
    n = len(geoms)
    print(f"{n} kept reaches in {args.name}")
    if not n:
        raise SystemExit("No flowlines fell inside the watershed boundary.")

    years = normalize_years(range(args.start, args.end + 1), latest=args.end)
    print(f"disaggregating {len(years)} yrs {years[0]}..{years[-1]} from PRISM ...")
    by_id = yearly_flow_by_id(args.huc4, years, args.root, latest=args.end)

    # Assemble each year's [n,12] flow for the kept reaches. Reaches missing from
    # the topology read keep a flat zero row (dropped by the log floor).
    per_year = {}
    for y in years:
        bucket = by_id[y]
        mat = np.zeros((n, 12))
        hit = 0
        for k, iid in enumerate(nhdids):
            row = bucket.get(int(iid))
            if row is not None:
                mat[k] = row
                hit += 1
        per_year[y] = mat
        print(f"  {y}: {hit}/{n} reaches with PRISM flow")

    # Fixed peak month = month of max total flow across the decade-mean network.
    decade_mean = np.mean([per_year[y] for y in years], axis=0)
    peak = int(decade_mean.sum(axis=0).argmax())
    print(f"peak month (decade mean): {MONTH_ABBR[peak]}")

    # Elevation tint (constant across frames).
    anchor = float(np.percentile(np.clip(elev_max, 0.0, None), args.anchor_pct))
    segment_colors, emax = elevation_colors(elev_max, args.gamma, anchor)
    geometries = {i: g for i, g in enumerate(geoms)}

    # Fixed cross-year log span over every year's peak-month flow.
    peak_flows = {y: per_year[y][:, peak] for y in years}
    all_vals = np.concatenate([peak_flows[y] for y in years])
    lo, hi = fixed_flow_span(all_vals.tolist(), floor=FLOOR)
    min_x, _, max_x, _ = bounds(geometries.values())
    units_per_px = (max_x - min_x) / args.width
    base_units = args.min_px * units_per_px
    top_units = args.max_px * units_per_px
    print(f"elevation 0..{emax:.0f} m; flow span {np.exp(lo):.2f}..{np.exp(hi):.0f}"
          f" cfs -> {args.min_px}..{args.max_px}px; peak={MONTH_ABBR[peak]}")

    out_dir = Path("output/yoy")
    out_dir.mkdir(parents=True, exist_ok=True)
    subtitle = (f"{args.name} - {MONTH_ABBR[peak]} flow, year over year "
                f"(PRISM {years[0]}-{years[-1]})")
    frames = []
    from PIL import Image

    for y in years:
        flow = peak_flows[y]
        widths = widths_on_span(
            {i: flow[i] for i in geometries}, lo, hi,
            width_min=base_units, width_max=top_units, floor=FLOOR,
        )
        svg = render_svg(
            geometries, segment_colors, {},
            background=BG, line_width=base_units, stroke_widths=widths,
            glow=args.glow, glow_mode="blur", glow_radius=2.0,
        )
        png = out_dir / f"{tag}_{y}.png"
        rasterize_whole(svg, str(png), args.width, args.max_px)
        print(f"  {y}: sum {MONTH_ABBR[peak]} flow {float(flow.sum()):,.0f} cfs "
              f"-> {png.name}")
        frames.append(_label(Image.open(png).convert("RGB"), str(y), subtitle))

    gif = f"output/{tag}_year_over_year.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:],
        duration=args.ms_per_frame, loop=0, optimize=True,
    )
    print(f"\nwrote {gif} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
