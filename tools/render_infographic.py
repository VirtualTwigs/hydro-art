"""Compose a single clean infographic: info panel + lowest-water river map.

Renders the Clark County (WA) monthly river map at its **driest month** (when
the network has drained back to its major rivers), labels the surviving named
waterways, and sets it beside a left panel carrying:

* the map's date (the driest month),
* an Earth axial-tilt diagram placing that month in the seasonal cycle,
* that month's county-average precipitation (12-bar chart, month highlighted),
* an Earth-Moon lunar-cycle diagram.

Curved vector art (Earth, Sun, Moon phases, orbits, leader lines) is drawn on a
supersampled overlay and downsampled for clean edges; text is drawn at native
resolution for crispness. Like every ``tools/`` script it needs the full GIS
stack + real datasets (not offline).

    python tools/render_infographic.py            # driest month, Clark County
    python tools/render_infographic.py --month 7  # force July
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pyogrio
import shapely
from PIL import Image, ImageDraw, ImageFont

from src.rendering import bounds
from tools.monthly_flow import _value_column, build_monthly_flow
from tools.render_common import (
    CLARK_BBOX_4326,
    assign_subwatersheds,
    bbox_boundary,
    build_inputs,
    gdb_paths,
    rasterize,
    render_art_svg,
)
from tools.render_monthly import FLOOR, fixed_widths, load_basin_flowlines

MONTHS_FULL = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MON3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Palette (matches the neon-on-black map).
BG = (8, 9, 13)
INK = (232, 236, 245)
DIM = (120, 128, 145)
ACCENT = (46, 196, 255)
WARM = (255, 196, 72)
EARTH_SEA = (44, 104, 200)
EARTH_LAND = (66, 156, 110)
MOON_LIT = (236, 240, 250)
MOON_DARK = (26, 30, 40)

FONT_PATHS = ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Arial.ttf")


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def gnis_names(spec, keep_ids: set[int]) -> dict[int, str]:
    """Map NHDPlusID -> GNIS name for the reaches we render (named only)."""
    out: dict[int, str] = {}
    for gdb in gdb_paths(spec):
        try:
            df = pyogrio.read_dataframe(
                gdb, layer="NHDFlowline", columns=["NHDPlusID", "GNIS_Name"],
                read_geometry=False,
            )
        except Exception:  # noqa: BLE001 - partial/corrupt GDB (no NHDFlowline)
            continue
        for i, name in zip(df["NHDPlusID"], df["GNIS_Name"]):
            if isinstance(name, str) and name.strip() and int(i) in keep_ids:
                out[int(i)] = name.strip()
    return out


def county_monthly_precip(spec, keep_ids: set[int]) -> np.ndarray:
    """County-average incremental precipitation per month (mm)."""
    out = np.zeros(12)
    gdb = gdb_paths(spec)[0]
    for m in range(12):
        layer = f"NHDPlusIncrPrecipMM{m + 1:02d}"
        col = _value_column(gdb, layer, "Precip")
        df = pyogrio.read_dataframe(
            gdb, layer=layer, columns=["NHDPlusID", col], read_geometry=False
        )
        df = df[df["NHDPlusID"].isin(keep_ids)]
        out[m] = float(df[col].mean()) / 100.0 if len(df) else 0.0
    return out


# --------------------------------------------------------------------------- #
# Supersampled vector helpers (draw at Sx, caller downsamples)
# --------------------------------------------------------------------------- #
def draw_moon(d: ImageDraw.ImageDraw, cx, cy, r, phase, edge=DIM) -> None:
    """Draw a moon-phase disk. ``phase`` 0=new, 0.5=full, cycling to 1=new."""
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.ellipse(bbox, fill=MOON_DARK)
    if phase <= 0.5:
        d.pieslice(bbox, -90, 90, fill=MOON_LIT)       # lit on right (waxing)
    else:
        d.pieslice(bbox, 90, 270, fill=MOON_LIT)       # lit on left (waning)
    tw = math.cos(2 * math.pi * phase) * r             # terminator half-width
    fill = MOON_DARK if tw >= 0 else MOON_LIT
    tw = abs(tw)
    d.ellipse([cx - tw, cy - r, cx + tw, cy + r], fill=fill)
    d.ellipse(bbox, outline=edge, width=max(2, r // 40))


def solar_declination(month: int) -> float:
    """Approx sub-solar latitude (deg) at mid-month; +N summer, -S."""
    doy = month * 30.4 + 15
    return 23.44 * math.sin(2 * math.pi * (doy - 80) / 365.24)


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #
def build_panel(pw: int, ph: int, month: int, precip: np.ndarray,
                county: str) -> Image.Image:
    """Render the left info panel at (pw, ph)."""
    S = 3
    panel = Image.new("RGB", (pw, ph), BG)
    ov = Image.new("RGBA", (pw * S, ph * S), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    td = ImageDraw.Draw(panel)

    mx = int(pw * 0.09)                       # left margin
    decl = solar_declination(month)
    season = ("summer" if decl > 5 else "winter" if decl < -5 else
              "equinox")

    # ---- Header ---------------------------------------------------------- #
    y = int(ph * 0.045)
    td.text((mx, y), county.upper(), font=font(int(pw * 0.045)), fill=DIM)
    y += int(pw * 0.075)
    td.text((mx, y), MONTHS_FULL[month].upper(), font=font(int(pw * 0.14)),
            fill=INK)
    y += int(pw * 0.18)
    td.text((mx, y), "LOWEST FLOW  ·  DRIEST MONTH",
            font=font(int(pw * 0.033)), fill=ACCENT)
    y += int(pw * 0.07)
    od.line([mx * S, y * S, (pw - mx) * S, y * S], fill=DIM + (255,),
            width=S * 2)

    def section_title(yy, text):
        td.text((mx, yy), text, font=font(int(pw * 0.036)), fill=DIM)

    # ---- Axial tilt ------------------------------------------------------ #
    y += int(ph * 0.03)
    section_title(y, "AXIAL TILT  ·  SEASON")
    ecx, ecy, er = int(pw * 0.62), y + int(ph * 0.12), int(pw * 0.13)
    scx, scy, sr = int(pw * 0.20), ecy, int(pw * 0.055)
    # sun + rays
    od.ellipse([(scx - sr) * S, (scy - sr) * S, (scx + sr) * S, (scy + sr) * S],
               fill=WARM + (255,))
    for a in range(0, 360, 30):
        rad = math.radians(a)
        x1 = scx + math.cos(rad) * sr * 1.3
        y1 = scy + math.sin(rad) * sr * 1.3
        x2 = scx + math.cos(rad) * sr * 1.75
        y2 = scy + math.sin(rad) * sr * 1.75
        od.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=WARM + (255,), width=S * 2)
    # orbit plane
    od.line([(scx + sr) * S, scy * S, (ecx - er) * S, ecy * S],
            fill=DIM + (150,), width=S)
    # earth
    od.ellipse([(ecx - er) * S, (ecy - er) * S, (ecx + er) * S, (ecy + er) * S],
               fill=EARTH_SEA + (255,))
    od.chord([(ecx - er) * S, (ecy - er) * S, (ecx + er) * S, (ecy + er) * S],
             200, 340, fill=EARTH_LAND + (255,))
    # tilt axis (23.5deg); top leans toward Sun in summer, away in winter
    lean = math.radians(23.5) * (1 if decl >= 0 else -1)
    ax = math.sin(lean) * er * 1.5
    ay = math.cos(lean) * er * 1.5
    od.line([(ecx - ax) * S, (ecy + ay) * S, (ecx + ax) * S, (ecy - ay) * S],
            fill=INK + (255,), width=S * 3)
    # north pole marker
    npx, npy = ecx + ax, ecy - ay
    od.ellipse([(npx - er * 0.11) * S, (npy - er * 0.11) * S,
                (npx + er * 0.11) * S, (npy + er * 0.11) * S], fill=ACCENT + (255,))
    ov_small = ov.resize((pw, ph), Image.LANCZOS)
    panel.paste(ov_small, (0, 0), ov_small)
    td.text((npx + er * 0.16, npy - er * 0.3), "N", font=font(int(pw * 0.03)),
            fill=ACCENT)
    td.text((mx, ecy + er + int(ph * 0.02)),
            f"23.5\u00b0 tilt  ·  N hemisphere {season}",
            font=font(int(pw * 0.03)), fill=DIM)
    td.text((mx, ecy + er + int(ph * 0.02) + int(pw * 0.045)),
            f"sub-solar lat {decl:+.0f}\u00b0", font=font(int(pw * 0.03)),
            fill=DIM)

    # ---- Precipitation --------------------------------------------------- #
    py0 = ecy + er + int(ph * 0.09)
    section_title(py0, "AVG. PRECIPITATION")
    td.text((int(pw * 0.55), py0 - int(pw * 0.01)),
            f"{precip[month]:.0f} mm", font=font(int(pw * 0.075)), fill=ACCENT)
    bx0, bx1 = mx, pw - mx
    by1 = py0 + int(ph * 0.14)
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

    # ---- Lunar cycle ----------------------------------------------------- #
    ly = by1 + int(ph * 0.05)
    section_title(ly, "LUNAR CYCLE")
    ov2 = Image.new("RGBA", (pw * S, ph * S), (0, 0, 0, 0))
    o2 = ImageDraw.Draw(ov2)
    mcx, mcy = int(pw * 0.5), ly + int(ph * 0.135)
    orbit = int(pw * 0.28)
    o2.ellipse([(mcx - orbit) * S, (mcy - orbit * 0.55) * S,
                (mcx + orbit) * S, (mcy + orbit * 0.55) * S],
               outline=DIM + (150,), width=S)
    # central earth
    er2 = int(pw * 0.055)
    o2.ellipse([(mcx - er2) * S, (mcy - er2) * S, (mcx + er2) * S,
                (mcy + er2) * S], fill=EARTH_SEA + (255,))
    o2.chord([(mcx - er2) * S, (mcy - er2) * S, (mcx + er2) * S,
              (mcy + er2) * S], 200, 340, fill=EARTH_LAND + (255,))
    mr = int(pw * 0.038)
    for k in range(8):
        ang = math.pi - k / 8 * 2 * math.pi     # New at Sun side (left)
        mxp = mcx + math.cos(ang) * orbit
        myp = mcy - math.sin(ang) * orbit * 0.55
        draw_moon(o2, mxp * S, myp * S, mr * S, k / 8)
    ov2s = ov2.resize((pw, ph), Image.LANCZOS)
    panel.paste(ov2s, (0, 0), ov2s)
    td.text((mx, mcy + orbit * 0.55 + int(ph * 0.02)),
            "synodic month  ·  29.5 days", font=font(int(pw * 0.03)), fill=DIM)

    # ---- Footer ---------------------------------------------------------- #
    td.text((mx, ph - int(ph * 0.03)),
            "USGS NHDPlus HR  ·  EROM flow + monthly climate",
            font=font(int(pw * 0.024)), fill=DIM)
    return panel


# --------------------------------------------------------------------------- #
# Map labels
# --------------------------------------------------------------------------- #
def label_map(map_im: Image.Image, anchors, min_x, min_y, max_x, max_y) -> None:
    """Draw named-waterway labels on the rasterized map."""
    W, H = map_im.size
    sx, sy = W / (max_x - min_x), H / (max_y - min_y)
    d = ImageDraw.Draw(map_im)
    f = font(max(20, H // 75))
    used: list[float] = []
    for name, pt in anchors:
        px, py = (pt.x - min_x) * sx, (max_y - pt.y) * sy
        left = px < W * 0.58
        tx = px + 18 if left else px - 18 - d.textlength(name, font=f)
        ty = py
        for u in used:                      # crude vertical de-overlap
            if abs(ty - u) < H // 42:
                ty = u + H // 42
        used.append(ty)
        d.line([px, py, tx if left else tx + d.textlength(name, font=f),
                ty + f.size // 2], fill=(90, 96, 112), width=2)
        d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=ACCENT)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):   # halo
            d.text((tx + ox, ty + oy), name, font=f, fill=BG)
        d.text((tx, ty), name, font=f, fill=INK)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--month", type=int, default=None,
                    help="1-12; default = the driest (lowest total flow) month.")
    ap.add_argument("--width", type=int, default=1500, help="Map raster width px.")
    ap.add_argument("--min-order", type=int, default=2)
    ap.add_argument("--min-px", type=float, default=0.8)
    ap.add_argument("--max-px", type=float, default=9.0)
    ap.add_argument("--activation", type=float, default=0.5)
    ap.add_argument("--persist", type=float, default=0.018)
    ap.add_argument("--max-labels", type=int, default=11)
    args = ap.parse_args()

    spec = "1708"
    boundary = bbox_boundary(CLARK_BBOX_4326)
    print("loading Clark County flowlines ...")
    geoms, ids, orders = load_basin_flowlines(spec, args.min_order, boundary)
    keep_ids = {int(i) for i in ids}
    names = gnis_names(spec, keep_ids)
    flow_map = {}
    for gdb in gdb_paths(spec):
        gids, flow, _ = build_monthly_flow(gdb)
        for i, row in zip(gids, flow):
            if int(i) in keep_ids:
                flow_map[int(i)] = row

    codes, _ = assign_subwatersheds(geoms, 12)
    geometries, seg_colors, watersheds, _ = build_inputs(geoms, codes)

    monthly = np.zeros((len(geoms), 12))
    for idx in geometries:
        row = flow_map.get(ids[idx])
        if row is not None:
            monthly[idx] = row

    month = (args.month - 1) if args.month else int(monthly.sum(axis=0).argmin())
    print(f"driest month = {MONTHS_FULL[month]}")

    # Fixed log scale + widths for that month; hide drained reaches.
    positive = monthly[monthly > 0]
    lo = math.log(max(positive.min(), FLOOR))
    hi = math.log(positive.max())
    min_x, min_y, max_x, max_y = bounds(geometries.values())
    upp = (max_x - min_x) / args.width
    base_units, top_units = args.min_px * upp, args.max_px * upp
    annual_max = monthly.max(axis=1)
    persist_floor = args.persist * math.exp(hi)
    flow_i = monthly[:, month]
    widths = fixed_widths({idx: flow_i[idx] for idx in geometries},
                          base_units, top_units, lo, hi)
    active: list[int] = []
    for idx in geometries:
        q = flow_i[idx]
        if q > 0 and (q >= args.activation * annual_max[idx] or q >= persist_floor):
            active.append(idx)
        else:
            widths[idx] = 0.0
    print(f"  {len(active)} waterways still flowing")

    svg = render_art_svg(geometries, seg_colors, watersheds, base_units, widths)
    out_dir = Path("output/monthly")
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "infographic_map.svg"
    png_path = out_dir / "infographic_map.png"
    svg_path.write_text(svg)
    rasterize(str(svg_path), str(png_path), args.width, args.max_px)
    map_im = Image.open(png_path).convert("RGB")

    # Label the largest named survivors.
    by_name: dict[str, list[int]] = {}
    for idx in active:
        nm = names.get(ids[idx])
        if nm:
            by_name.setdefault(nm, []).append(idx)
    ranked = sorted(by_name.items(),
                    key=lambda kv: sum(geoms[i].length for i in kv[1]),
                    reverse=True)[:args.max_labels]
    anchors = [(nm, shapely.union_all([geoms[i] for i in idxs]).representative_point())
               for nm, idxs in ranked]
    anchors.sort(key=lambda a: a[1].y, reverse=True)   # north-to-south
    label_map(map_im, anchors, min_x, min_y, max_x, max_y)
    print("  labeled:", ", ".join(nm for nm, _ in anchors))

    precip = county_monthly_precip(spec, keep_ids)
    W_map, H_map = map_im.size
    pw = int(W_map * 0.62)
    panel = build_panel(pw, H_map, month, precip, "Clark County, WA")

    canvas = Image.new("RGB", (pw + W_map, H_map), BG)
    canvas.paste(panel, (0, 0))
    canvas.paste(map_im, (pw, 0))
    out = f"output/infographic_clark_{MON3[month].lower()}.png"
    canvas.save(out)
    print(f"\nwrote {out} ({canvas.size[0]}x{canvas.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
