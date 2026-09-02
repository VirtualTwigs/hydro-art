"""True year-over-year river print of a US state, one frame per calendar year.

The "year in motion" GIF (``render_monthly.py``) animates a *synthetic average
year* — twelve months disaggregated from the GDB's long-term climate *normals*,
so 2014 and 2017 look identical. This tool walks **real calendar years** instead:
each frame is one historical year's flow at a fixed month, so you watch the
network swell in wet years and thin out in droughts.

It drives the shared, offline engine (`src.historical_flow.yearly_flow_series`,
roadmap #44) with the real PRISM provider (`tools.historical_flow`, #45): per
HUC4 basin it reads the network topology + incremental annual flow, samples the
NAS-staged PRISM monthly precip/temperature grids at each catchment for every
requested year, and runs the snow-aware `disaggregate_monthly` model per year.
Color is the constant hypsometric elevation tint (`render_state_mono`); width is
that year's flow at the network's peak month, on a **fixed cross-year log span**
so inter-year change is visible (per-frame renormalization would hide it).

    python tools/render_state_yoy.py --state Washington --start 2014 --end 2023

Needs the PRISM grids staged first:
    python tools/prism_fetch.py --start 2014 --end 2023 --vars ppt tmean
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pyogrio
from PIL import Image, ImageDraw, ImageFont

from src.historical_flow import (
    normalize_years,
    peak_month_series,
    yearly_flow_series,
)
from src.rendering import bounds, fixed_flow_span, render_svg, widths_on_span
from tools.historical_flow import DEFAULT_ROOT, PrismClimateProvider
from tools.monthly_flow import MONTH_ABBR
from tools.nclimgrid_flow import NClimGridClimateProvider
from tools.render_common import STATE_HUC4, gdb_paths
from tools.render_state_mono import BG, elevation_colors, rasterize_whole

FLOOR = 1e-2


def _make_provider(source: str, root, lon, lat):
    """Construct the climate provider for the chosen source (the one swap point).

    ``nclimgrid`` (default) is NOAA nClimGrid-Monthly — federal public domain, free
    to sell (roadmap #60); ``prism`` keeps the original PRISM path for A/B
    comparison. Both share the ``(root, lon, lat)`` constructor + ``climate_for_year``
    seam, so nothing downstream branches on source.
    """
    if source == "nclimgrid":
        return NClimGridClimateProvider(root, lon, lat)
    if source == "prism":
        return PrismClimateProvider(root, lon, lat)
    raise SystemExit(f"unknown --climate-source {source!r} (nclimgrid|prism)")


def build_network(gdb: str):
    """Read one HUC4 GDB -> (ids, q_incr, hydroseq, dnhydroseq, lon, lat).

    ``lon``/``lat`` are each reach's representative-point centroid in EPSG:4269
    (PRISM's CRS), aligned to the topology arrays. Cached per basin so year
    iteration and ramp tweaks stay fast.
    """
    erom = pyogrio.read_dataframe(
        gdb, layer="NHDPlusEROMMA",
        columns=["NHDPlusID", "QIncrAMA"], read_geometry=False,
    )
    vaa = pyogrio.read_dataframe(
        gdb, layer="NHDPlusFlowlineVAA",
        columns=["NHDPlusID", "HydroSeq", "DnHydroSeq"], read_geometry=False,
    )
    df = erom.merge(vaa, on="NHDPlusID", how="inner").dropna(
        subset=["HydroSeq", "DnHydroSeq"]
    )
    df = df[df["HydroSeq"] > 0].reset_index(drop=True)

    geo = pyogrio.read_dataframe(gdb, layer="NHDFlowline", columns=["NHDPlusID"])
    geo = geo.to_crs(4269)
    pts = geo.geometry.representative_point()
    geo = geo.assign(lon=pts.x.to_numpy(), lat=pts.y.to_numpy())
    df = df.merge(geo[["NHDPlusID", "lon", "lat"]], on="NHDPlusID", how="left")
    df["lon"] = df["lon"].fillna(df["lon"].median())
    df["lat"] = df["lat"].fillna(df["lat"].median())

    return (
        df["NHDPlusID"].to_numpy(),
        df["QIncrAMA"].to_numpy(dtype=np.float64),
        df["HydroSeq"].to_numpy(),
        df["DnHydroSeq"].to_numpy(),
        df["lon"].to_numpy(dtype=np.float64),
        df["lat"].to_numpy(dtype=np.float64),
    )


def yearly_flow_by_id(spec, years, root, *, latest, climate_source="nclimgrid"):
    """Per-basin true year-over-year flow, merged to ``{year: {id: flow[12]}}``.

    For each HUC4 GDB in ``spec``: build the network, wrap the staged climate grids
    in the provider chosen by ``climate_source`` (``nclimgrid`` default, ``prism``
    optional — see :func:`_make_provider`), and run the shared
    :func:`src.historical_flow.yearly_flow_series` (real per-year disaggregation).
    """
    out: dict[int, dict[int, np.ndarray]] = {y: {} for y in years}
    root = Path(root)
    for gdb in gdb_paths(spec):
        code = Path(gdb).parent.name
        cache = Path(f"output/_yoy_net_{code}.pkl")
        if cache.exists():
            ids, q_incr, hydroseq, dnhydroseq, lon, lat = pickle.loads(
                cache.read_bytes()
            )
        else:
            try:
                ids, q_incr, hydroseq, dnhydroseq, lon, lat = build_network(gdb)
            except Exception as exc:  # noqa: BLE001 - skip a partial/corrupt GDB
                print(f"  network skip {code}: {exc}")
                continue
            cache.write_bytes(
                pickle.dumps((ids, q_incr, hydroseq, dnhydroseq, lon, lat))
            )
        provider = _make_provider(climate_source, root, lon, lat)
        series = yearly_flow_series(
            provider, years, q_incr=q_incr, hydroseq=hydroseq,
            dnhydroseq=dnhydroseq, latest=latest,
        )
        for y, flow in series.items():
            bucket = out[y]
            for i, row in zip(ids, flow):
                bucket[int(i)] = row
        print(f"  {code}: {len(ids)} reaches x {len(years)} yrs")
    return out


def _label(im: Image.Image, title: str, subtitle: str) -> Image.Image:
    """Stamp the year (big) + a subtitle onto a rasterized frame."""
    W = im.size[0]
    draw = ImageDraw.Draw(im)
    fs = max(48, W // 18)

    def font(sz):
        for p in ("/System/Library/Fonts/SFNSMono.ttf",
                  "/System/Library/Fonts/Menlo.ttc"):
            try:
                return ImageFont.truetype(p, size=sz)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()

    draw.text((fs, fs), title, fill=(235, 239, 248), font=font(fs))
    draw.text((fs, fs + int(fs * 1.15)), subtitle, fill=(120, 150, 200),
              font=font(int(fs * 0.32)))
    return im


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="Washington")
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2023)
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="External root holding the staged climate grids.")
    ap.add_argument("--climate-source", choices=["nclimgrid", "prism"],
                    default="nclimgrid",
                    help="Climate source: nclimgrid (public domain, default) or "
                         "prism (legacy, rights-gated).")
    ap.add_argument("--min-order", type=int, default=4,
                    help="Peakcache Strahler filter (must match a staged cache).")
    ap.add_argument("--width", type=int, default=5000)
    ap.add_argument("--min-px", type=float, default=0.6)
    ap.add_argument("--max-px", type=float, default=4.4)
    ap.add_argument("--gamma", type=float, default=0.75)
    ap.add_argument("--anchor-pct", type=float, default=97.0)
    ap.add_argument("--ms-per-frame", type=int, default=700)
    ap.add_argument("--glow", action="store_true")
    args = ap.parse_args()

    spec = STATE_HUC4.get(args.state)
    if not spec:
        raise SystemExit(f"No HUC4 mapping for {args.state!r}.")
    tag = args.state.lower().replace(" ", "_")

    # Reuse the still-render's clip+elevation cache for geometry & hypsometric tint.
    pk = Path(f"output/_peakcache_{tag}_mo{args.min_order}.pkl")
    if not pk.exists():
        raise SystemExit(
            f"missing {pk}; run render_state_mono_peak.py --state {args.state} "
            f"--min-order {args.min_order} first to stage the clip."
        )
    geoms, _elev_mean, elev_max, qama, nhdids, monthly = pickle.loads(
        pk.read_bytes()
    )
    print(f"{len(geoms)} kept reaches (min_order {args.min_order})")

    years = normalize_years(range(args.start, args.end + 1), latest=args.end)
    print(f"disaggregating {len(years)} yrs {years[0]}..{years[-1]} "
          f"from {args.climate_source} ...")
    by_id = yearly_flow_by_id(spec, years, args.root, latest=args.end,
                              climate_source=args.climate_source)

    # Baseline monthly (from the still cache) is the fallback for reaches absent
    # from the topology read; flat QAMA if even that is missing.
    n = len(geoms)
    base = np.empty((n, 12))
    for k, (row, q) in enumerate(zip(monthly, qama)):
        base[k] = np.asarray(row, float) if row is not None else np.full(12, q)

    # Assemble each year's [n,12] flow for the kept reaches (fallback to baseline).
    per_year = {}
    for y in years:
        bucket = by_id[y]
        mat = np.empty((n, 12))
        hit = 0
        for k, iid in enumerate(nhdids):
            row = bucket.get(int(iid))
            if row is not None:
                mat[k] = row
                hit += 1
            else:
                mat[k] = base[k]
        per_year[y] = mat
        print(f"  {y}: {hit}/{n} reaches with {args.climate_source} flow")

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
    print(f"flow span {np.exp(lo):.2f}..{np.exp(hi):.0f} cfs -> "
          f"{args.min_px}..{args.max_px}px; peak={MONTH_ABBR[peak]}")

    out_dir = Path("output/yoy")
    out_dir.mkdir(parents=True, exist_ok=True)
    subtitle = (f"{args.state} - {MONTH_ABBR[peak]} flow, year over year "
                f"(PRISM {years[0]}-{years[-1]})")
    frames: list[Image.Image] = []
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
        total = float(flow.sum())
        print(f"  {y}: sum {MONTH_ABBR[peak]} flow {total:,.0f} cfs -> {png.name}")
        im = Image.open(png).convert("RGB")
        frames.append(_label(im, str(y), subtitle))

    gif = f"output/{tag}_year_over_year.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:],
        duration=args.ms_per_frame, loop=0, optimize=True,
    )
    print(f"\nwrote {gif} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
