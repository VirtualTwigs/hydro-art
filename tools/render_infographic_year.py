"""Animate the Clark County (WA) infographic across a full year, one frame/week.

The animated sibling of :mod:`tools.render_infographic`. Instead of a single
still at the driest month, it walks the calendar in ``--frames`` steps (52 =
weekly) and, for each step, re-renders the whole infographic:

* the river **map** at that week's interpolated flow (monthly EROM flow from
  :mod:`tools.monthly_flow`, linearly blended between calendar months, on a
  *fixed* log width scale so the seasonal swell/retreat is visible);
* the left **key panel** whose date, axial-tilt/season diagram, precipitation
  highlight, and live **moon phase** all advance with the date.

The named mainstems (Columbia, Lewis, Sandy, ...) are labeled once from their
annual extent and pinned every frame, so labels stay stable while the smaller
tributaries pulse in and out with flow.

Whole-map SVGs here are well under the rasterizer node cap (~7k paths), so each
frame is rasterized in a single ``resvg`` call (not the per-layer split of
:mod:`tools.rasterize_layered`) -- ~30x faster, which makes 52 frames practical.
Frames are written to ``output/year/`` and assembled into an animated GIF.

The region is either Clark County, WA (default, bbox clip) or a whole US state
(``--state Oregon``), which spans several HUC4 basins and clips to the Census
state polygon. Layout is height-driven, so a wide state map and a tall county map
both sit cleanly beside the portrait key panel.

    python tools/render_infographic_year.py                 # 52 weekly frames
    python tools/render_infographic_year.py --state Oregon  # whole-state cycle
    python tools/render_infographic_year.py --frames 26     # fortnightly
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import pickle
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pyogrio
import shapely
from PIL import Image, ImageDraw

from src.rendering import bounds, render_svg
from tools.monthly_flow import _value_column, build_monthly_flow
from tools.render_common import (
    CLARK_BBOX_4326,
    STATE_HUC4,
    assign_subwatersheds,
    bbox_boundary,
    build_inputs,
    gdb_paths,
    load_state,
    render_art_svg,
)
from tools.render_state_mono import (
    ELEV_NODATA,
    MAP_BG,
    elevation_colors,
    load_elevations,
)
from tools.render_infographic import (
    ACCENT,
    BG,
    DIM,
    EARTH_LAND,
    EARTH_SEA,
    INK,
    MON3,
    MONTHS_FULL,
    WARM,
    draw_moon,
    font,
    gnis_names,
    label_map,
)
from tools.render_monthly import FLOOR, fixed_widths, load_basin_flowlines

# Reference new moon: 2000-01-06 18:14 UT (JD ~2451550.1); synodic month days.
NEW_MOON_JD = 2451550.1
SYNODIC = 29.530588853
YEAR = 2026  # calendar year the animation walks (for real moon phases)

PHASE_NAMES = [
    "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def region_monthly_precip(spec, keep_ids: set[int]) -> np.ndarray:
    """Region-average incremental precip per month (mm), across all basins.

    The still :func:`tools.render_infographic.county_monthly_precip` samples only
    the first GDB; a whole state spans several HUC4 basins, so average over every
    kept reach in all of them.
    """
    totals = np.zeros(12)
    counts = np.zeros(12)
    for gdb in gdb_paths(spec):
        for m in range(12):
            layer = f"NHDPlusIncrPrecipMM{m + 1:02d}"
            col = _value_column(gdb, layer, "Precip")
            df = pyogrio.read_dataframe(
                gdb, layer=layer, columns=["NHDPlusID", col], read_geometry=False
            )
            df = df[df["NHDPlusID"].isin(keep_ids)]
            if len(df):
                totals[m] += float(df[col].sum()) / 100.0
                counts[m] += len(df)
    return np.divide(totals, counts, out=np.zeros(12), where=counts > 0)


# --------------------------------------------------------------------------- #
# Astronomy helpers
# --------------------------------------------------------------------------- #
def julian_day(y: int, m: int, d: float) -> float:
    """Gregorian calendar date -> Julian Day (noon-based)."""
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def moon_phase(date: dt.date) -> float:
    """Fraction through the synodic cycle: 0=new, 0.5=full, ->1 back to new."""
    jd = julian_day(date.year, date.month, date.day)
    return ((jd - NEW_MOON_JD) % SYNODIC) / SYNODIC


def declination(doy: float) -> float:
    """Sub-solar latitude (deg) for a continuous day-of-year; +N summer, -S."""
    return 23.44 * math.sin(2 * math.pi * (doy - 80) / 365.24)


def phase_label(phase: float) -> str:
    """Name + illumination for a moon phase fraction."""
    name = PHASE_NAMES[int((phase * 8 + 0.5)) % 8]
    illum = (1 - math.cos(2 * math.pi * phase)) / 2
    return f"{name}  ·  {illum * 100:.0f}% lit"


# --------------------------------------------------------------------------- #
# Single-call rasterizer (whole SVG is under the node cap here)
# --------------------------------------------------------------------------- #
def rasterize_whole(svg_path: Path, png_path: Path, width: int,
                    stroke_px: float, glow_px: float = 2.5) -> None:
    """Rescale root stroke/glow to pixels and rasterize the whole SVG at once."""
    lines: list[str] = []
    svg_done = False
    in_defs = False
    upp = 1.0
    for line in svg_path.read_text().splitlines(keepends=True):
        if not svg_done and line.lstrip().startswith("<svg"):
            vb = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.\-]+)', line)
            upp = float(vb.group(1)) / width if vb else 1.0
            line = re.sub(r'stroke-width="[\d.]+"',
                          f'stroke-width="{stroke_px * upp:.4f}"', line)
            svg_done = True
            lines.append(line)
            continue
        if "<defs>" in line:
            in_defs = True
        if in_defs:
            line = re.sub(r'stdDeviation="[\d.]+"',
                          f'stdDeviation="{glow_px * upp:.4f}"', line)
        if "</defs>" in line:
            in_defs = False
        lines.append(line)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tf:
        tf.write("".join(lines))
        tmp = tf.name
    subprocess.run(["resvg", "--width", str(width), tmp, str(png_path)],
                   check=True, stdout=subprocess.DEVNULL)
    Path(tmp).unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Panel (weekly variant of tools.render_infographic.build_panel)
# --------------------------------------------------------------------------- #
def build_panel(pw: int, ph: int, date: dt.date, doy: float, precip: np.ndarray,
                phase: float, rel_flow: float, rising: bool,
                county: str) -> Image.Image:
    """Render the left info panel for a specific calendar ``date``."""
    S = 3
    month = date.month - 1
    panel = Image.new("RGB", (pw, ph), BG)
    ov = Image.new("RGBA", (pw * S, ph * S), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    td = ImageDraw.Draw(panel)

    mx = int(pw * 0.09)
    decl = declination(doy)
    season = ("summer" if decl > 5 else "winter" if decl < -5 else "equinox")

    # ---- Header ---------------------------------------------------------- #
    y = int(ph * 0.045)
    td.text((mx, y), county.upper(), font=font(int(pw * 0.045)), fill=DIM)
    y += int(pw * 0.075)
    td.text((mx, y), MONTHS_FULL[month].upper(), font=font(int(pw * 0.14)),
            fill=INK)
    y += int(pw * 0.18)
    td.text((mx, y), f"{MON3[month].upper()} {date.day:02d}  ·  DAY {int(doy) + 1}",
            font=font(int(pw * 0.033)), fill=ACCENT)

    # ---- Flow gauge ------------------------------------------------------ #
    y += int(pw * 0.065)
    gx1 = pw - mx
    gh = int(pw * 0.018)
    od.rounded_rectangle([mx * S, y * S, gx1 * S, (y + gh) * S], radius=gh * S // 2,
                         fill=(30, 38, 54, 255))
    fillw = mx + (gx1 - mx) * max(0.02, rel_flow)
    od.rounded_rectangle([mx * S, y * S, fillw * S, (y + gh) * S],
                         radius=gh * S // 2, fill=ACCENT + (255,))
    ov_hdr = ov.resize((pw, ph), Image.LANCZOS)
    panel.paste(ov_hdr, (0, 0), ov_hdr)
    ov = Image.new("RGBA", (pw * S, ph * S), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    arrow = "\u25b2 rising" if rising else "\u25bc falling"
    td.text((mx, y + gh + int(ph * 0.008)),
            f"NETWORK FLOW  {rel_flow * 100:.0f}%  ·  {arrow}",
            font=font(int(pw * 0.028)), fill=DIM)
    y += gh + int(ph * 0.045)
    od.line([mx * S, y * S, (pw - mx) * S, y * S], fill=DIM + (255,), width=S * 2)

    def section_title(yy, text):
        td.text((mx, yy), text, font=font(int(pw * 0.036)), fill=DIM)

    # ---- Axial tilt ------------------------------------------------------ #
    y += int(ph * 0.028)
    section_title(y, "AXIAL TILT  ·  SEASON")
    ecx, ecy, er = int(pw * 0.62), y + int(ph * 0.115), int(pw * 0.12)
    scx, scy, sr = int(pw * 0.20), ecy, int(pw * 0.05)
    od.ellipse([(scx - sr) * S, (scy - sr) * S, (scx + sr) * S, (scy + sr) * S],
               fill=WARM + (255,))
    for a in range(0, 360, 30):
        rad = math.radians(a)
        x1, y1 = scx + math.cos(rad) * sr * 1.3, scy + math.sin(rad) * sr * 1.3
        x2, y2 = scx + math.cos(rad) * sr * 1.75, scy + math.sin(rad) * sr * 1.75
        od.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=WARM + (255,), width=S * 2)
    od.line([(scx + sr) * S, scy * S, (ecx - er) * S, ecy * S],
            fill=DIM + (150,), width=S)
    od.ellipse([(ecx - er) * S, (ecy - er) * S, (ecx + er) * S, (ecy + er) * S],
               fill=EARTH_SEA + (255,))
    od.chord([(ecx - er) * S, (ecy - er) * S, (ecx + er) * S, (ecy + er) * S],
             200, 340, fill=EARTH_LAND + (255,))
    # Apparent axial lean varies continuously with the sub-solar latitude:
    # N pole leans toward the Sun (left) in summer, away (right) in winter,
    # and appears vertical at the equinoxes.
    lean = -math.radians(decl)
    ax, ay = math.sin(lean) * er * 1.5, math.cos(lean) * er * 1.5
    od.line([(ecx - ax) * S, (ecy + ay) * S, (ecx + ax) * S, (ecy - ay) * S],
            fill=INK + (255,), width=S * 3)
    npx, npy = ecx + ax, ecy - ay
    od.ellipse([(npx - er * 0.11) * S, (npy - er * 0.11) * S,
                (npx + er * 0.11) * S, (npy + er * 0.11) * S], fill=ACCENT + (255,))
    panel.paste(ov.resize((pw, ph), Image.LANCZOS), (0, 0),
                ov.resize((pw, ph), Image.LANCZOS))
    td.text((npx + er * 0.16, npy - er * 0.3), "N", font=font(int(pw * 0.03)),
            fill=ACCENT)
    td.text((mx, ecy + er + int(ph * 0.02)),
            f"23.5\u00b0 tilt  ·  N hemisphere {season}",
            font=font(int(pw * 0.03)), fill=DIM)
    td.text((mx, ecy + er + int(ph * 0.02) + int(pw * 0.045)),
            f"sub-solar lat {decl:+.0f}\u00b0", font=font(int(pw * 0.03)), fill=DIM)

    # ---- Precipitation --------------------------------------------------- #
    py0 = ecy + er + int(ph * 0.085)
    section_title(py0, "AVG. PRECIPITATION")
    td.text((int(pw * 0.55), py0 - int(pw * 0.01)),
            f"{precip[month]:.0f} mm", font=font(int(pw * 0.075)), fill=ACCENT)
    bx0, bx1 = mx, pw - mx
    by1 = py0 + int(ph * 0.135)
    by0 = py0 + int(pw * 0.10)
    bw = (bx1 - bx0) / 12
    pmax = max(precip.max(), 1e-6)
    bd = ImageDraw.Draw(panel)
    for m in range(12):
        h = (precip[m] / pmax) * (by1 - by0)
        x0 = bx0 + m * bw + bw * 0.15
        x1 = bx0 + (m + 1) * bw - bw * 0.15
        color = ACCENT if m == month else (44, 58, 82)
        bd.rectangle([x0, by1 - h, x1, by1], fill=color)
        bd.text((x0, by1 + 4), MON3[m][0], font=font(int(pw * 0.022)),
                fill=INK if m == month else DIM)

    # ---- Lunar cycle (live phase) ---------------------------------------- #
    ly = by1 + int(ph * 0.045)
    section_title(ly, "LUNAR PHASE")
    ov2 = Image.new("RGBA", (pw * S, ph * S), (0, 0, 0, 0))
    o2 = ImageDraw.Draw(ov2)
    mcx, mcy = int(pw * 0.5), ly + int(ph * 0.12)
    orbit = int(pw * 0.26)
    o2.ellipse([(mcx - orbit) * S, (mcy - orbit * 0.55) * S,
                (mcx + orbit) * S, (mcy + orbit * 0.55) * S],
               outline=DIM + (120,), width=S)
    er2 = int(pw * 0.05)
    o2.ellipse([(mcx - er2) * S, (mcy - er2) * S, (mcx + er2) * S,
                (mcy + er2) * S], fill=EARTH_SEA + (255,))
    o2.chord([(mcx - er2) * S, (mcy - er2) * S, (mcx + er2) * S,
              (mcy + er2) * S], 200, 340, fill=EARTH_LAND + (255,))
    # faint 8-phase reference ring
    for k in range(8):
        ang = math.pi - k / 8 * 2 * math.pi
        rxp = mcx + math.cos(ang) * orbit
        ryp = mcy - math.sin(ang) * orbit * 0.55
        draw_moon(o2, rxp * S, ryp * S, int(pw * 0.022) * S, k / 8,
                  edge=(60, 66, 82))
    # the live moon, larger + accent ring, at its true orbital angle
    ang = math.pi - phase * 2 * math.pi
    mxp = mcx + math.cos(ang) * orbit
    myp = mcy - math.sin(ang) * orbit * 0.55
    mr = int(pw * 0.05)
    o2.ellipse([(mxp - mr * 1.28) * S, (myp - mr * 1.28) * S,
                (mxp + mr * 1.28) * S, (myp + mr * 1.28) * S],
               outline=ACCENT + (255,), width=S * 2)
    draw_moon(o2, mxp * S, myp * S, mr * S, phase, edge=DIM)
    panel.paste(ov2.resize((pw, ph), Image.LANCZOS), (0, 0),
                ov2.resize((pw, ph), Image.LANCZOS))
    td.text((mx, mcy + orbit * 0.55 + int(ph * 0.015)), phase_label(phase),
            font=font(int(pw * 0.03)), fill=INK)

    # ---- Footer ---------------------------------------------------------- #
    td.text((mx, ph - int(ph * 0.03)),
            "USGS NHDPlus HR  ·  EROM flow + monthly climate",
            font=font(int(pw * 0.024)), fill=DIM)
    return panel


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def days_in_month(y: int, m: int) -> int:
    nxt = dt.date(y + (m == 12), (m % 12) + 1, 1)
    return (nxt - dt.date(y, m, 1)).days


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default=None,
                    help="US state name (e.g. Oregon) spanning several HUC4 "
                         "basins; default = Clark County, WA (bbox).")
    ap.add_argument("--frames", type=int, default=52, help="Frames per year (52=weekly).")
    ap.add_argument("--height", type=int, default=2000,
                    help="Canvas/panel height px (map width follows region aspect; "
                         "rendered high, downscaled for the GIF).")
    ap.add_argument("--min-order", type=int, default=None,
                    help="Drop streams below this Strahler order "
                         "(default 2 for Clark, 5 for a whole state).")
    ap.add_argument("--huc-digits", type=int, default=None,
                    help="WBD level for sub-watershed coloring "
                         "(default 12 for Clark, 8 for a state).")
    ap.add_argument("--min-px", type=float, default=0.45,
                    help="Hairline width for the smallest channels.")
    ap.add_argument("--max-px", type=float, default=3.6,
                    help="Width for the largest mainstem (kept slim for elegance).")
    ap.add_argument("--activation", type=float, default=0.5)
    ap.add_argument("--persist", type=float, default=None,
                    help="Reaches above this fraction of the region's peak flow "
                         "stay lit year-round (default 0.02 Clark, 0.006 state).")
    ap.add_argument("--max-labels", type=int, default=None,
                    help="Named waterways to label (default 6 for Clark, 12 for a state).")
    ap.add_argument("--elevation", action="store_true",
                    help="Color streams by their smoothed elevation (white summit "
                         "-> deep-blue sea level) instead of by sub-watershed; one "
                         "shared hypsometric ramp across the whole region.")
    ap.add_argument("--gamma", type=float, default=0.75,
                    help="Elevation ramp shaping (only with --elevation); "
                         "<1 brightens mid-slopes toward white.")
    ap.add_argument("--anchor-pct", type=float, default=97.0,
                    help="Percentile of reach elevation mapping to pure white "
                         "(only with --elevation).")
    ap.add_argument("--ms-per-frame", type=int, default=140)
    ap.add_argument("--gif-width", type=int, default=1600,
                    help="Downscale each composed frame to this width for the GIF.")
    args = ap.parse_args()

    # ---- Region config --------------------------------------------------- #
    if args.state:
        spec = STATE_HUC4.get(args.state)
        if not spec:
            raise SystemExit(f"No HUC4 mapping for {args.state!r}; add it to STATE_HUC4.")
        boundary = load_state(args.state)
        min_order = args.min_order if args.min_order is not None else 4
        huc_digits = args.huc_digits if args.huc_digits is not None else 8
        max_labels = args.max_labels if args.max_labels is not None else 12
        persist = args.persist if args.persist is not None else 0.006
        region_name, tag = args.state, args.state.lower().replace(" ", "_")
    else:
        spec = "1708"
        boundary = bbox_boundary(CLARK_BBOX_4326)
        min_order = args.min_order if args.min_order is not None else 2
        huc_digits = args.huc_digits if args.huc_digits is not None else 12
        max_labels = args.max_labels if args.max_labels is not None else 6
        persist = args.persist if args.persist is not None else 0.02
        region_name, tag = "Clark County, WA", "clark"

    print(f"loading {region_name} flowlines (spec={spec}, min_order={min_order}) ...")
    geoms, ids, orders = load_basin_flowlines(spec, min_order, boundary)
    if not geoms:
        raise SystemExit("No flowlines matched; lower --min-order.")
    keep_ids = {int(i) for i in ids}
    names = gnis_names(spec, keep_ids)
    flow_map = {}
    for gdb in gdb_paths(spec):
        gids, flow, _ = build_monthly_flow(gdb)
        for i, row in zip(gids, flow):
            if int(i) in keep_ids:
                flow_map[int(i)] = row

    if args.elevation:
        print("coloring by elevation (white summit -> deep-blue sea) ...")
        elev_by_id = load_elevations(spec, keep_ids)
        geometries = {i: g for i, g in enumerate(geoms)}
        elevs = [elev_by_id.get(int(ids[i]), 0.0) for i in geometries]
        anchor = float(np.percentile(np.clip(elevs, 0.0, None), args.anchor_pct))
        seg_colors, emax = elevation_colors(elevs, args.gamma, anchor)
        watersheds: dict = {}  # color-None group -> per-path elevation colors kept
        map_bg = MAP_BG
        print(f"  elevation 0..{emax:.0f} m -> deep-blue..white "
              f"(anchor p{args.anchor_pct:g})")
    else:
        print(f"coloring by HUC{huc_digits} ...")
        codes, _ = assign_subwatersheds(geoms, huc_digits)
        geometries, seg_colors, watersheds, _ = build_inputs(geoms, codes)
        map_bg = BG

    monthly = np.zeros((len(geoms), 12))
    for idx in geometries:
        row = flow_map.get(ids[idx])
        if row is not None:
            monthly[idx] = row

    # Fixed scale across the whole year (so seasonal swell/retreat is visible).
    positive = monthly[monthly > 0]
    lo = math.log(max(positive.min(), FLOOR))
    hi = math.log(positive.max())
    min_x, min_y, max_x, max_y = bounds(geometries.values())
    # Height-driven layout: portrait key panel + full-height map (map width
    # follows the region's aspect, so wide states and tall counties both fit).
    H = args.height
    aspect = (max_x - min_x) / (max_y - min_y)
    map_w = int(round(H * aspect))
    pw = int(H * 0.5)
    upp = (max_x - min_x) / map_w
    base_units, top_units = args.min_px * upp, args.max_px * upp
    annual_max = monthly.max(axis=1)
    persist_floor = persist * math.exp(hi)

    precip = region_monthly_precip(spec, keep_ids)

    # Stable labels: top named reaches by annual extent, positions pinned.
    by_name: dict[str, list[int]] = {}
    for idx in geometries:
        nm = names.get(ids[idx])
        if nm and annual_max[idx] > 0:
            by_name.setdefault(nm, []).append(idx)
    ranked = sorted(by_name.items(),
                    key=lambda kv: sum(geoms[i].length for i in kv[1]),
                    reverse=True)[:max_labels]
    anchors = [(nm, shapely.union_all([geoms[i] for i in idxs]).representative_point())
               for nm, idxs in ranked]
    anchors.sort(key=lambda a: a[1].y, reverse=True)
    print("labels:", ", ".join(nm for nm, _ in anchors))

    # Pre-compute each frame's date + interpolated flow, and the flow gauge scale.
    dates, flows_i, doys = [], [], []
    for w in range(args.frames):
        doy = w * 365.2425 / args.frames
        date = dt.date(YEAR, 1, 1) + dt.timedelta(days=doy)
        mpos = (date.month - 1) + (date.day - 1) / days_in_month(YEAR, date.month)
        m0 = int(mpos) % 12
        f = mpos - int(mpos)
        m1 = (m0 + 1) % 12
        flow = monthly[:, m0] * (1 - f) + monthly[:, m1] * f
        dates.append(date)
        doys.append(doy)
        flows_i.append(flow)
    totals = np.array([fl.sum() for fl in flows_i])
    tmin, tmax = totals.min(), totals.max()

    out_dir = Path(f"output/year_{tag}")
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_svg = out_dir / "_frame.svg"
    tmp_png = out_dir / "_frame_map.png"
    frames: list[Image.Image] = []
    for w in range(args.frames):
        flow_i = flows_i[w]
        widths = fixed_widths({idx: flow_i[idx] for idx in geometries},
                              base_units, top_units, lo, hi)
        active = 0
        for idx in geometries:
            q = flow_i[idx]
            if q > 0 and (q >= args.activation * annual_max[idx] or q >= persist_floor):
                active += 1
            else:
                widths[idx] = 0.0
        if args.elevation:
            # No glow (blur dims the hairline headwaters where the white summits
            # live); MAP_BG keeps deep-blue tidewater legible.
            svg = render_svg(
                geometries, seg_colors, watersheds,
                background=map_bg, line_width=base_units, stroke_widths=widths,
                glow=False,
            )
        else:
            svg = render_art_svg(geometries, seg_colors, watersheds, base_units, widths)
        tmp_svg.write_text(svg)
        rasterize_whole(tmp_svg, tmp_png, map_w, args.max_px)
        map_im = Image.open(tmp_png).convert("RGB")
        label_map(map_im, anchors, min_x, min_y, max_x, max_y)

        rel = float((totals[w] - tmin) / max(tmax - tmin, 1e-9))
        rising = totals[w] >= totals[w - 1] if w > 0 else True
        map_h = map_im.size[1]
        phase = moon_phase(dates[w])
        panel = build_panel(pw, H, dates[w], doys[w], precip, phase, rel,
                            rising, region_name)

        canvas_h = max(H, map_h)
        canvas = Image.new("RGB", (pw + map_w, canvas_h), BG)
        canvas.paste(panel, (0, (canvas_h - H) // 2))
        canvas.paste(map_im, (pw, (canvas_h - map_h) // 2))
        canvas.save(out_dir / f"week_{w + 1:02d}.png")
        if canvas.size[0] > args.gif_width:
            h = int(canvas.size[1] * args.gif_width / canvas.size[0])
            canvas = canvas.resize((args.gif_width, h), Image.LANCZOS)
        frames.append(canvas)
        print(f"  frame {w + 1:>2}/{args.frames}  {dates[w]:%b %d}  "
              f"flow {rel * 100:>3.0f}%  {active:>4} active")

    gif = f"output/infographic_year_{tag}.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:],
                   duration=args.ms_per_frame, loop=0, optimize=True)
    print(f"\nwrote {len(frames)} frames -> {out_dir}/ and {gif}")
    subprocess.run(["open", gif], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
