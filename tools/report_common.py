"""Watershed-report shared load + reach selection + figure recipe (roadmap #54).

The single "report-quality" recipe that ``tools/build_watershed_report.py`` calls,
so every watershed report reads as one product. Three parts:

1. **Shared load** — ``load_watershed_series`` reuses the year-over-year machinery
   (``render_watershed_yoy``'s HUC12 clip + ``render_state_yoy``'s PRISM flow) and
   its on-disk caches (``output/_wshed_<tag>_mo<n>.pkl`` clip + ``output/_yoy_net_
   <huc4>.pkl`` network), assembling a ``{year: [n,12]}`` flow series for the kept
   reaches.
2. **Reach selection** — the watershed *outlet* is the max-accumulated reach
   (``src.flow_metrics.outlet_index``); its per-year ``[12]`` row is the watershed
   hydrograph that the gauge (also at the outlet) is validated against.
3. **Figure recipe** — a set of matplotlib panels driven purely by the offline
   metric layer (``src.flow_metrics`` #48/#49/#53 + #50/#51 validation):
   watershed map, per-year hydrographs, long-record trend (Mann-Kendall + Sen's
   slope), typical-year band, summer-low trend, model-vs-gauge validation, and the
   ENSO teleconnection scatter.

Heavy GIS + matplotlib live here (a ``tools/`` module), never in ``src/``; the
metrics themselves stay in the offline ``src/`` layer.
"""

from __future__ import annotations

import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Point

from src import flow_metrics as fm
from src.crs import INTERNAL_CRS
from src.historical_flow import normalize_years
from tools.historical_flow import DEFAULT_ROOT
from tools.monthly_flow import MONTH_ABBR
from tools.render_state_mono import derive_elevations, elevation_colors
from tools.render_state_yoy import yearly_flow_by_id
from tools.render_watershed_yoy import clip_watershed, load_huc12_boundary

FLOOR = 1e-2
FIG_DIR = Path("notebooks/figures")

# NWIS horizontal-datum codes -> EPSG (for snapping the gauge to a model reach).
_DATUM_EPSG = {"NAD83": "EPSG:4269", "NAD27": "EPSG:4267", "WGS84": "EPSG:4326"}


def gauge_reach_index(
    geoms: list, lat: float, lon: float, *, datum: str = "NAD83"
) -> tuple[int, float]:
    """Index (+ distance, m) of the reach nearest the gauge.

    The watershed *outlet* is the basin mouth — a far larger drainage than a
    mid-watershed gauge, so validating the outlet against the gauge compares two
    different drainage areas. Snapping to the reach at the gauge location fixes
    the magnitude mismatch (``geoms`` are in ``INTERNAL_CRS`` / EPSG:5070).
    """
    src_crs = _DATUM_EPSG.get(datum.upper(), "EPSG:4269")
    pt = gpd.GeoSeries([Point(lon, lat)], crs=src_crs).to_crs(INTERNAL_CRS).iloc[0]
    dists = np.array([g.distance(pt) for g in geoms])
    idx = int(dists.argmin())
    return idx, float(dists[idx])


@dataclass
class WatershedSeries:
    """Everything a report figure needs, assembled once per watershed."""

    name: str
    huc4: str
    huc12: list[str]
    years: list[int]
    geoms: list  # shapely LineStrings (EPSG:5070), one per kept reach
    elev_max: np.ndarray  # [n] smoothed max elevation, for the hypsometric tint
    per_year: dict[int, np.ndarray]  # {year: [n,12]} monthly flow
    outlet_idx: int  # index of the watershed outlet reach (max accumulated flow)
    outlet: dict[int, np.ndarray]  # {year: [12]} the outlet hydrograph
    peak_month: int  # 0..11, month of max decade-mean network flow

    @property
    def n(self) -> int:
        return len(self.geoms)

    def annual_mean(self) -> dict[int, float]:
        """Outlet annual-mean flow per year (the long-record trend signal)."""
        return {y: float(np.mean(row)) for y, row in self.outlet.items()}

    def peak_by_year(self) -> dict[int, float]:
        """Outlet peak-month flow per year (the ENSO teleconnection signal)."""
        return {y: float(row[self.peak_month]) for y, row in self.outlet.items()}

    def summer_low(self) -> dict[int, float]:
        """Outlet summer-low (Jun–Aug min) flow per year."""
        lows = fm.low_flow({y: row[None, :] for y, row in self.outlet.items()})
        return {y: float(v[0]) for y, v in lows.items()}


def load_watershed_series(
    huc4: str,
    huc12: list[str],
    name: str,
    start: int,
    end: int,
    *,
    root: str = DEFAULT_ROOT,
    min_order: int = 1,
    climate_source: str = "nclimgrid",
) -> WatershedSeries:
    """Assemble a watershed's year-over-year flow series (cache-backed)."""
    tag = name.lower().replace(" ", "_")
    clip_cache = Path(f"output/_wshed_{tag}_mo{min_order}.pkl")
    if clip_cache.exists():
        geoms, elev_max, nhdids = pickle.loads(clip_cache.read_bytes())
    else:
        boundary = load_huc12_boundary(huc12)
        geoms, elev_max, nhdids = clip_watershed(boundary, huc4, min_order)
        clip_cache.parent.mkdir(parents=True, exist_ok=True)
        clip_cache.write_bytes(pickle.dumps((geoms, elev_max, nhdids)))
    n = len(geoms)
    if not n:
        raise SystemExit("No flowlines fell inside the watershed boundary.")

    years = list(normalize_years(range(start, end + 1), latest=end))
    by_id = yearly_flow_by_id(huc4, years, root, latest=end,
                              climate_source=climate_source)
    per_year: dict[int, np.ndarray] = {}
    for y in years:
        bucket = by_id[y]
        mat = np.zeros((n, 12))
        for k, iid in enumerate(nhdids):
            row = bucket.get(int(iid))
            if row is not None:
                mat[k] = row
        per_year[y] = mat

    decade_mean = np.mean([per_year[y] for y in years], axis=0)
    peak_month = int(decade_mean.sum(axis=0).argmax())
    # Outlet = the max-accumulated reach over the whole membership (#53 helper).
    mean_annual = decade_mean.mean(axis=1)
    outlet_idx = fm.outlet_index(mean_annual, np.arange(n))
    outlet = {y: per_year[y][outlet_idx] for y in years}

    return WatershedSeries(
        name=name, huc4=str(huc4), huc12=[str(c) for c in huc12], years=years,
        geoms=geoms, elev_max=np.asarray(elev_max, dtype=float),
        per_year=per_year, outlet_idx=outlet_idx, outlet=outlet,
        peak_month=peak_month,
    )


# --- figure recipe --------------------------------------------------------
# Each panel takes the assembled series (+ optional gauge/index) and an Axes.

def _year_colors(years: list[int]):
    cmap = plt.get_cmap("viridis")
    span = max(years) - min(years) or 1
    return {y: cmap((y - min(years)) / span) for y in years}


def _parts(geom):
    """Yield each single-part line's (xs, ys) — handles Multi* geometries."""
    if geom.geom_type.startswith("Multi") or geom.geom_type == "GeometryCollection":
        for part in geom.geoms:
            yield from _parts(part)
    elif not geom.is_empty:
        xs, ys = geom.xy
        yield xs, ys


def fig_watershed_map(ws: WatershedSeries, ax, *, gauge_idx: int | None = None) -> None:
    """The watershed's reaches, colored by hypsometric elevation tint."""
    anchor = float(np.percentile(np.clip(ws.elev_max, 0.0, None), 97.0))
    colors, emax = elevation_colors(ws.elev_max, 0.8, anchor)
    for i, geom in enumerate(ws.geoms):
        for xs, ys in _parts(geom):
            ax.plot(xs, ys, color=colors[i], linewidth=0.7, solid_capstyle="round")
    last = list(_parts(ws.geoms[ws.outlet_idx]))
    if last:
        ox, oy = last[-1]
        ax.plot(ox[-1], oy[-1], "o", color="#ff4d5e", ms=7, label="outlet")
    if gauge_idx is not None:
        gparts = list(_parts(ws.geoms[gauge_idx]))
        if gparts:
            gx, gy = gparts[-1]
            ax.plot(gx[-1], gy[-1], "^", color="#ffe14d", ms=9, label="gauge")
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(f"{ws.name} — {ws.n} reaches (tint: elev 0–{emax:.0f} m)")
    ax.legend(loc="lower right", fontsize=8, frameon=False)


def fig_hydrographs(ws: WatershedSeries, ax) -> None:
    """The outlet hydrograph, one line per year (viridis by year)."""
    colors = _year_colors(ws.years)
    for y in ws.years:
        ax.plot(range(1, 13), ws.outlet[y], color=colors[y], lw=1.0, alpha=0.8)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTH_ABBR, fontsize=7)
    ax.set_ylabel("outlet flow (cfs)")
    ax.set_title(f"Year-over-year hydrographs ({ws.years[0]}–{ws.years[-1]})")
    sm = plt.cm.ScalarMappable(
        cmap="viridis",
        norm=plt.Normalize(vmin=min(ws.years), vmax=max(ws.years)),
    )
    ax.figure.colorbar(sm, ax=ax, label="year", pad=0.01)


def fig_long_record(ws: WatershedSeries, ax) -> dict:
    """Annual-mean outlet flow per year + Mann-Kendall / Sen's-slope trend line."""
    years = ws.years
    annual = np.array([ws.annual_mean()[y] for y in years])
    mk = fm.mann_kendall(annual)
    slope = fm.sens_slope(annual)
    x = np.arange(len(years))
    fit = np.median(annual) + slope * (x - np.median(x))
    ax.plot(years, annual, "o-", color="#00ffff", lw=1.2, ms=4, label="annual mean")
    ax.plot(years, fit, "--", color="#9d00ff", lw=1.2,
            label=f"Sen {slope:+.2f} cfs/yr")
    ax.set_ylabel("annual-mean flow (cfs)")
    ax.set_title(f"Long record — trend {mk.trend} (τ={mk.tau:+.2f}, p={mk.p:.3f})")
    ax.legend(fontsize=8, frameon=False)
    return {"trend": mk.trend, "tau": mk.tau, "p": mk.p, "sens_slope": slope}


def fig_typical_year(ws: WatershedSeries, ax) -> None:
    """The mean monthly hydrograph with a P10–P90 across-year band."""
    stack = np.array([ws.outlet[y] for y in ws.years])  # [years,12]
    mean = stack.mean(axis=0)
    p10 = np.percentile(stack, 10, axis=0)
    p90 = np.percentile(stack, 90, axis=0)
    m = range(1, 13)
    ax.fill_between(m, p10, p90, color="#00ffff", alpha=0.15, label="P10–P90")
    ax.plot(m, mean, color="#00ffff", lw=1.6, label="mean")
    cot = fm.center_of_timing(mean)
    ax.axvline(cot, color="#ff9c3a", ls=":", lw=1, label=f"COT {cot:.1f}")
    ax.set_xticks(list(m))
    ax.set_xticklabels(MONTH_ABBR, fontsize=7)
    ax.set_ylabel("flow (cfs)")
    ax.set_title("Typical year — mean monthly flow + spread")
    ax.legend(fontsize=8, frameon=False)


def fig_low_flow(ws: WatershedSeries, ax) -> dict:
    """Summer-low (Jun–Aug min) outlet flow per year + Sen's-slope trend."""
    years = ws.years
    low = np.array([ws.summer_low()[y] for y in years])
    slope = fm.sens_slope(low)
    mk = fm.mann_kendall(low)
    x = np.arange(len(years))
    fit = np.median(low) + slope * (x - np.median(x))
    ax.plot(years, low, "o-", color="#00ff9c", lw=1.2, ms=4, label="summer low")
    ax.plot(years, fit, "--", color="#9d00ff", lw=1.2,
            label=f"Sen {slope:+.3f} cfs/yr")
    ax.set_ylabel("summer-low flow (cfs)")
    ax.set_title(f"Summer low flow — trend {mk.trend} (p={mk.p:.3f})")
    ax.legend(fontsize=8, frameon=False)
    return {"low_trend": mk.trend, "low_sens_slope": slope}


def fig_validation(
    ws: WatershedSeries,
    gauge_obs: dict[int, np.ndarray],
    ax,
    *,
    gauge_idx: int | None = None,
    gauge_dist: float | None = None,
) -> dict:
    """Model vs. gauge over the overlap years; report r/NSE/bias + verdict.

    The model side is the reach *at the gauge* when ``gauge_idx`` is supplied
    (snapped via ``gauge_reach_index``), else the watershed outlet. The comparison
    is over the flattened monthly overlap; ``nan`` gauge months are skipped (never
    zero-filled) inside ``src.flow_metrics``.
    """
    reach = ws.outlet_idx if gauge_idx is None else gauge_idx
    model_by_year = {y: ws.per_year[y][reach] for y in ws.years}
    common = sorted(set(model_by_year) & set(gauge_obs))
    if not common:
        ax.text(0.5, 0.5, "no model/gauge overlap years", ha="center",
                transform=ax.transAxes)
        ax.set_axis_off()
        return {}
    model = np.concatenate([model_by_year[y] for y in common])
    obs = np.concatenate([np.asarray(gauge_obs[y], dtype=float) for y in common])
    rep = fm.validate(model, obs)
    ax.scatter(obs, model, s=12, color="#00ffff", alpha=0.6)
    lim = [0, float(np.nanmax([np.nanmax(obs), np.nanmax(model)])) * 1.05]
    ax.plot(lim, lim, "--", color="#8891a8", lw=1, label="1:1")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("gauge flow (cfs)")
    ax.set_ylabel("model flow (cfs)")
    ax.set_title(
        f"Validation [{rep.verdict}] — r={rep.pearson_r:.2f} "
        f"NSE={rep.nash_sutcliffe:.2f} bias={rep.bias:+.1f}"
    )
    where = ("outlet reach" if gauge_idx is None
             else f"reach {reach} @ {gauge_dist:.0f} m from gauge")
    ax.text(0.02, 0.98, f"model @ {where}", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color="#8891a8")
    ax.legend(fontsize=8, frameon=False)
    return {
        "verdict": rep.verdict, "r": rep.pearson_r, "nse": rep.nash_sutcliffe,
        "bias": rep.bias, "rmse": rep.rmse, "overlap_years": common,
        "reach": int(reach),
        "reach_dist_m": None if gauge_dist is None else round(gauge_dist, 1),
    }


def fig_enso(ws: WatershedSeries, index_by_year: dict[int, float], ax,
             *, index_name: str = "ONI") -> dict:
    """Peak-flow vs. climate index scatter with the Pearson r (and lag-1 r)."""
    peak = ws.peak_by_year()
    try:
        metric, index = fm.align_index(peak, index_by_year)
    except fm.FlowValidationError:
        ax.text(0.5, 0.5, "no metric/index overlap", ha="center",
                transform=ax.transAxes)
        ax.set_axis_off()
        return {}
    r0 = fm.correlate(peak, index_by_year)
    r1 = fm.correlate(peak, index_by_year, lag=1)
    ax.scatter(index, metric, s=16, color="#9d00ff", alpha=0.7)
    ax.set_xlabel(f"{index_name} (annual)")
    ax.set_ylabel(f"peak-month flow ({MONTH_ABBR[ws.peak_month]}, cfs)")
    ax.set_title(f"ENSO teleconnection — r={r0:+.2f} (lag-1 r={r1:+.2f}, "
                 f"n={len(metric)})")
    return {"enso_r": r0, "enso_r_lag1": r1, "enso_n": int(len(metric))}


def build_report(
    ws: WatershedSeries,
    *,
    gauge_obs: dict[int, np.ndarray] | None = None,
    gauge_loc: tuple[float, float, str] | None = None,
    index_by_year: dict[int, float] | None = None,
    index_name: str = "ONI",
    out_dir: Path = FIG_DIR,
) -> dict:
    """Render the full panel set to ``out_dir``; return a metrics summary dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = ws.name.lower().replace(" ", "_")
    summary: dict = {"watershed": ws.name, "huc4": ws.huc4,
                     "years": [ws.years[0], ws.years[-1]], "reaches": ws.n,
                     "peak_month": MONTH_ABBR[ws.peak_month]}

    gauge_idx = gauge_dist = None
    if gauge_obs and gauge_loc is not None:
        lat, lon, datum = gauge_loc
        gauge_idx, gauge_dist = gauge_reach_index(ws.geoms, lat, lon, datum=datum)

    def _save(fig, stem):
        path = out_dir / f"{tag}_{stem}.png"
        fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="#07080c")
        plt.close(fig)
        return path

    fig, ax = plt.subplots(figsize=(7, 7), facecolor="#07080c")
    _style(ax)
    fig_watershed_map(ws, ax, gauge_idx=gauge_idx)
    _save(fig, "map")

    fig, ax = plt.subplots(figsize=(8, 4), facecolor="#07080c")
    _style(ax)
    fig_hydrographs(ws, ax)
    _save(fig, "hydrographs")

    fig, ax = plt.subplots(figsize=(8, 4), facecolor="#07080c")
    _style(ax)
    summary.update(fig_long_record(ws, ax))
    _save(fig, "long_record")

    fig, ax = plt.subplots(figsize=(6, 4), facecolor="#07080c")
    _style(ax)
    fig_typical_year(ws, ax)
    _save(fig, "typical_year")

    fig, ax = plt.subplots(figsize=(8, 4), facecolor="#07080c")
    _style(ax)
    summary.update(fig_low_flow(ws, ax))
    _save(fig, "low_flow")

    if gauge_obs:
        fig, ax = plt.subplots(figsize=(5, 5), facecolor="#07080c")
        _style(ax)
        summary.update(fig_validation(ws, gauge_obs, ax,
                                      gauge_idx=gauge_idx, gauge_dist=gauge_dist))
        _save(fig, "validation")

    if index_by_year:
        fig, ax = plt.subplots(figsize=(5, 5), facecolor="#07080c")
        _style(ax)
        summary.update(fig_enso(ws, index_by_year, ax, index_name=index_name))
        _save(fig, "enso")

    return summary


def _style(ax) -> None:
    """Dark neon theme to match the web report view."""
    ax.set_facecolor("#10121b")
    for spine in ax.spines.values():
        spine.set_color("#232838")
    ax.tick_params(colors="#8891a8", labelsize=8)
    ax.xaxis.label.set_color("#e6ebf5")
    ax.yaxis.label.set_color("#e6ebf5")
    ax.title.set_color("#e6ebf5")
    ax.title.set_fontsize(10)
