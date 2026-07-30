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
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import shapely

from src.coloring import get_palette
from tools.render_county_3d import build_segments, draw_caption, project, render

EPSG = "EPSG:5070"
STATES_SHP = "/tmp/states_shp/cb_2023_us_state_500k.shp"
GDB_ROOT = "datasets/nhdplus_hr"

#: HUC4 basins to scan per state (matches src/datasets.REGION_HUC4, plus 1707
#: which carries WA's Klickitat-area streams). Only those present locally are read.
STATE_HUC4 = {
    "Washington": ("1701", "1702", "1703", "1707", "1708", "1710", "1711"),
    "Oregon": ("1707", "1708", "1709", "1710", "1712", "1801"),
}


def load_state(name: str):
    st = gpd.read_file(STATES_SHP)
    sel = st[st.NAME == name]
    if sel.empty:
        raise SystemExit(f"State {name!r} not found in {STATES_SHP}.")
    return sel.to_crs(EPSG).geometry.iloc[0]


def gdb_for(huc4: str) -> list[str]:
    return sorted(glob.glob(f"{GDB_ROOT}/{huc4}/*.gdb"))


def clip_flowlines(boundary, huc4s, min_order: int):
    """Clip flowlines from the given HUC4 basins to the state polygon.

    Order is joined from ``NHDPlusFlowlineVAA`` and mean-annual discharge
    (``QAMA``, cfs) from ``NHDPlusEROMMA``; the ``min_order`` filter is applied
    *before* the (expensive) spatial clip to keep the geometry count manageable.
    Returns parallel lists ``(geoms, orders, flows, huc4s_of_geom)``.
    """
    shapely.prepare(boundary)
    geoms: list = []
    orders: list[int] = []
    flows: list[float] = []
    basins: list[str] = []
    for huc4 in huc4s:
        for gdb in gdb_for(huc4):
            try:
                f = gpd.read_file(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
            except Exception as exc:  # noqa: BLE001
                print(f"  skip {huc4}: {exc}")
                continue
            vaa = gpd.read_file(
                gdb, layer="NHDPlusFlowlineVAA",
                columns=["NHDPlusID", "StreamOrde"], read_geometry=False,
            )
            order_by_id = dict(zip(vaa["NHDPlusID"], vaa["StreamOrde"]))
            erom = gpd.read_file(
                gdb, layer="NHDPlusEROMMA",
                columns=["NHDPlusID", "QAMA"], read_geometry=False,
            )
            flow_by_id = dict(zip(erom["NHDPlusID"], erom["QAMA"]))
            seg_orders = (
                f["NHDPlusID"].map(lambda i: int(order_by_id.get(i, 1) or 1)).to_numpy()
            )
            seg_flows = (
                f["NHDPlusID"].map(lambda i: float(flow_by_id.get(i, 0.0) or 0.0)).to_numpy()
            )
            if min_order > 1:
                keep = seg_orders >= min_order
                f = f[keep]
                seg_orders = seg_orders[keep]
                seg_flows = seg_flows[keep]
            f = f.to_crs(EPSG)
            arr = np.array(f.geometry.values, dtype=object)
            covered = shapely.covers(boundary, arr)
            crossing = shapely.intersects(boundary, arr) & ~covered
            for gi in np.nonzero(covered)[0]:
                geoms.append(arr[gi]); orders.append(int(seg_orders[gi]))
                flows.append(float(seg_flows[gi])); basins.append(huc4)
            cross_idx = np.nonzero(crossing)[0]
            if cross_idx.size:
                trimmed = shapely.intersection(boundary, arr[cross_idx])
                for local_i, gi in enumerate(cross_idx):
                    g = trimmed[local_i]
                    if not g.is_empty:
                        geoms.append(g); orders.append(int(seg_orders[gi]))
                        flows.append(float(seg_flows[gi])); basins.append(huc4)
            print(f"  {huc4}: kept {sum(1 for b in basins if b == huc4)}")
    return geoms, orders, flows, basins


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
