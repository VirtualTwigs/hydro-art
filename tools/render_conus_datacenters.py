"""CONUS datacenter map — all major US data centers on neon hydrography.

Renders the 48 contiguous US states with:
  • Neon basin-colored, flow-scaled river network (HUC2 coloring)
  • All major US data-center markers (hyperscale + major colo campuses)
  • Optional facility name labels
  • Symbol key / legend

    python tools/render_conus_datacenters.py
    python tools/render_conus_datacenters.py --min-order 4 --width 10000 --no-labels

NON-OFFLINE: requires all NHDPlus HR GDBs for the 48 contiguous states
extracted under ``datasets/``, plus the Census state shapefile.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd  # noqa: E402
import shapely  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from src.config import CONUS_STATES  # noqa: E402
from src.rendering import bounds  # noqa: E402
from tools.render_common import (  # noqa: E402
    EPSG,
    STATE_HUC4,
    build_inputs,
    clip_flowlines,
    flow_scaled_widths,
    load_state,
    rasterize,
    render_art_svg,
    _hex_rgb,
)

OUT_DIR = Path("output/gallery/conus-datacenters")

# ── Curated US data-center locations (WGS84 lon/lat) ─────────────────────────
# Sources: datacentermap.com, Baxtel, company announcements, EPA FRS, public
# filings. Coordinates are approximate public-domain campus centroids.
#
# Organized by market / region.

DATACENTERS: list[dict] = [
    # ── Northern Virginia ("Data Center Alley") ────────────────────────────
    {"name": "Equinix Ashburn Campus",      "lon": -77.4875, "lat": 39.0437},
    {"name": "AWS US-East-1 (Ashburn)",     "lon": -77.4720, "lat": 39.0465},
    {"name": "Digital Realty Ashburn",       "lon": -77.4810, "lat": 39.0510},
    {"name": "Microsoft Azure Ashburn",     "lon": -77.4630, "lat": 39.0390},
    {"name": "Google Cloud (Sterling)",     "lon": -77.4100, "lat": 39.0060},
    {"name": "Meta Ashburn Campus",         "lon": -77.4950, "lat": 39.0550},
    {"name": "QTS Ashburn",                 "lon": -77.5010, "lat": 39.0490},
    {"name": "CyrusOne Sterling",           "lon": -77.4200, "lat": 39.0130},
    {"name": "CoreSite Reston",             "lon": -77.3560, "lat": 38.9580},
    {"name": "Vantage Ashburn",             "lon": -77.4780, "lat": 39.0600},
    {"name": "CloudHQ Ashburn",             "lon": -77.5080, "lat": 39.0410},
    {"name": "Iron Mountain (Manassas)",    "lon": -77.4550, "lat": 39.0320},

    # ── Dallas / Fort Worth, TX ────────────────────────────────────────────
    {"name": "CyrusOne Carrollton",         "lon": -96.8900, "lat": 32.9537},
    {"name": "Equinix Dallas",              "lon": -96.8200, "lat": 32.9200},
    {"name": "Digital Realty Dallas",        "lon": -96.8100, "lat": 32.9010},
    {"name": "QTS Dallas-Fort Worth",       "lon": -97.0200, "lat": 32.8100},
    {"name": "DataBank Dallas",             "lon": -96.8500, "lat": 32.9400},
    {"name": "Meta Fort Worth",             "lon": -97.3700, "lat": 32.7600},
    {"name": "Stream Data Centers Dallas",  "lon": -96.8350, "lat": 32.9150},

    # ── San Antonio / Austin, TX ───────────────────────────────────────────
    {"name": "Microsoft San Antonio",       "lon": -98.5200, "lat": 29.4430},
    {"name": "CyrusOne San Antonio",        "lon": -98.4800, "lat": 29.4300},
    {"name": "Rackspace HQ San Antonio",    "lon": -98.4350, "lat": 29.5050},
    {"name": "Google Midlothian TX",        "lon": -96.9800, "lat": 32.4850},

    # ── Houston, TX ────────────────────────────────────────────────────────
    {"name": "CyrusOne Houston",            "lon": -95.5300, "lat": 29.8100},
    {"name": "Digital Realty Houston",       "lon": -95.4600, "lat": 29.7800},

    # ── Phoenix / Mesa, AZ ─────────────────────────────────────────────────
    {"name": "CyrusOne Chandler",           "lon": -111.8600, "lat": 33.2830},
    {"name": "Digital Realty Phoenix",       "lon": -111.9200, "lat": 33.4500},
    {"name": "QTS Phoenix (Mesa)",          "lon": -111.7200, "lat": 33.4100},
    {"name": "EdgeCore Mesa",               "lon": -111.7100, "lat": 33.3800},
    {"name": "Meta Mesa",                   "lon": -111.7000, "lat": 33.3600},
    {"name": "Apple Mesa",                  "lon": -111.6800, "lat": 33.3700},
    {"name": "Microsoft Goodyear AZ",       "lon": -112.3600, "lat": 33.4200},
    {"name": "Google Mesa AZ",              "lon": -111.7300, "lat": 33.3900},

    # ── Chicago / Northern Illinois ────────────────────────────────────────
    {"name": "Equinix Chicago",             "lon": -87.6500, "lat": 41.8500},
    {"name": "Digital Realty Chicago",       "lon": -87.6600, "lat": 41.8650},
    {"name": "QTS Chicago (Elk Grove)",     "lon": -87.9700, "lat": 42.0100},
    {"name": "CyrusOne Aurora IL",          "lon": -88.3200, "lat": 41.7600},
    {"name": "Meta DeKalb IL",              "lon": -88.7500, "lat": 41.9300},

    # ── New York Metro / New Jersey ────────────────────────────────────────
    {"name": "Equinix Secaucus NJ",         "lon": -74.0700, "lat": 40.7900},
    {"name": "Digital Realty NJ",            "lon": -74.0900, "lat": 40.7600},
    {"name": "CyrusOne NJ",                 "lon": -74.1100, "lat": 40.7500},
    {"name": "CoreSite NJ (Somerville)",    "lon": -74.5800, "lat": 40.5700},
    {"name": "Equinix NY (Manhattan)",      "lon": -74.0060, "lat": 40.7128},

    # ── Silicon Valley / Bay Area, CA ──────────────────────────────────────
    {"name": "Equinix SV (San Jose)",       "lon": -121.8900, "lat": 37.3382},
    {"name": "Digital Realty Santa Clara",   "lon": -121.9600, "lat": 37.3540},
    {"name": "CoreSite Santa Clara",        "lon": -121.9500, "lat": 37.3520},
    {"name": "Vantage Santa Clara",         "lon": -121.9550, "lat": 37.3500},
    {"name": "CyrusOne San Jose",           "lon": -121.8800, "lat": 37.3500},

    # ── Los Angeles / SoCal ────────────────────────────────────────────────
    {"name": "CoreSite Los Angeles",        "lon": -118.2600, "lat": 34.0400},
    {"name": "Equinix Los Angeles",         "lon": -118.3100, "lat": 34.0420},
    {"name": "Digital Realty LA",            "lon": -118.2400, "lat": 34.0500},

    # ── Portland / Hillsboro, OR ───────────────────────────────────────────
    {"name": "Google The Dalles OR",        "lon": -121.1700, "lat": 45.6000},
    {"name": "Meta Prineville OR",          "lon": -120.7340, "lat": 44.3000},
    {"name": "Digital Realty Portland",      "lon": -122.8900, "lat": 45.5200},
    {"name": "QTS Hillsboro OR",            "lon": -122.9600, "lat": 45.5230},
    {"name": "Stack Hillsboro OR",          "lon": -122.9500, "lat": 45.5400},

    # ── Seattle / Quincy / Moses Lake, WA ──────────────────────────────────
    {"name": "Microsoft Quincy WA",         "lon": -119.8500, "lat": 47.2340},
    {"name": "Yahoo Quincy WA",             "lon": -119.8400, "lat": 47.2300},
    {"name": "Sabey Quincy WA",             "lon": -119.8300, "lat": 47.2350},
    {"name": "Equinix Seattle",             "lon": -122.3400, "lat": 47.6100},
    {"name": "Digital Realty Westin Seattle","lon": -122.3370, "lat": 47.6130},
    {"name": "Google Douglas County WA",    "lon": -119.7400, "lat": 47.3900},
    {"name": "Microsoft Moses Lake WA",     "lon": -119.2800, "lat": 47.1300},

    # ── Salt Lake City / Utah ──────────────────────────────────────────────
    {"name": "Meta Eagle Mountain UT",      "lon": -112.0000, "lat": 40.3100},
    {"name": "Aligned SLC",                 "lon": -111.9300, "lat": 40.7600},
    {"name": "Flexential West Jordan UT",   "lon": -111.9700, "lat": 40.6100},
    {"name": "NSA Utah Data Center",        "lon": -111.9000, "lat": 40.4300},

    # ── Denver / Colorado ──────────────────────────────────────────────────
    {"name": "CoreSite Denver",             "lon": -104.8700, "lat": 39.7500},
    {"name": "Flexential Denver",           "lon": -104.8400, "lat": 39.7200},
    {"name": "ViaWest Denver",              "lon": -104.9200, "lat": 39.7400},

    # ── Atlanta, GA ────────────────────────────────────────────────────────
    {"name": "Equinix Atlanta",             "lon": -84.3880, "lat": 33.7490},
    {"name": "QTS Atlanta (Suwanee)",       "lon": -84.0600, "lat": 34.0500},
    {"name": "Digital Realty Atlanta",       "lon": -84.4000, "lat": 33.7600},
    {"name": "Switch Atlanta",              "lon": -84.5700, "lat": 33.6400},
    {"name": "Meta Newton County GA",       "lon": -83.8600, "lat": 33.5600},
    {"name": "Google Douglas County GA",    "lon": -84.7700, "lat": 33.7200},
    {"name": "Microsoft Douglas County GA", "lon": -84.7800, "lat": 33.7300},

    # ── Carolinas ──────────────────────────────────────────────────────────
    {"name": "Apple Maiden NC",             "lon": -81.1800, "lat": 35.5700},
    {"name": "Google Lenoir NC",            "lon": -81.5400, "lat": 35.9100},
    {"name": "Meta Forest City NC",         "lon": -81.8700, "lat": 35.3300},
    {"name": "Microsoft Boydton VA",        "lon": -78.4000, "lat": 36.6700},
    {"name": "QTS Richmond VA",             "lon": -77.4400, "lat": 37.5400},

    # ── Iowa / Nebraska (Midwest Hyperscale) ───────────────────────────────
    {"name": "Google Council Bluffs IA",    "lon": -95.8700, "lat": 41.2600},
    {"name": "Meta Altoona IA",             "lon": -93.4700, "lat": 41.6400},
    {"name": "Microsoft West Des Moines IA","lon": -93.7500, "lat": 41.5700},
    {"name": "Apple Waukee IA",             "lon": -93.8700, "lat": 41.6000},
    {"name": "Meta Papillion NE",           "lon": -96.0400, "lat": 41.1500},
    {"name": "Meta Sarpy County NE",        "lon": -96.0300, "lat": 41.1200},

    # ── Ohio / Midwest ─────────────────────────────────────────────────────
    {"name": "Google New Albany OH",         "lon": -82.7800, "lat": 40.0800},
    {"name": "Meta New Albany OH",           "lon": -82.7900, "lat": 40.0900},
    {"name": "AWS Columbus OH",             "lon": -82.9000, "lat": 40.0000},
    {"name": "QTS Columbus OH",             "lon": -82.8500, "lat": 40.0500},

    # ── Kansas City, MO ────────────────────────────────────────────────────
    {"name": "Google KC MO",                "lon": -94.5800, "lat": 39.0997},
    {"name": "DataBank Kansas City",        "lon": -94.6100, "lat": 39.0800},

    # ── Minneapolis / Minnesota ────────────────────────────────────────────
    {"name": "Cologix Minneapolis",         "lon": -93.2650, "lat": 44.9780},
    {"name": "Flexential Minneapolis",      "lon": -93.3200, "lat": 44.9500},

    # ── Las Vegas / Reno, NV ───────────────────────────────────────────────
    {"name": "Switch Las Vegas (SuperNAP)", "lon": -115.0800, "lat": 36.0800},
    {"name": "Switch Tahoe Reno",           "lon": -119.6200, "lat": 39.5200},
    {"name": "Apple Reno NV",               "lon": -119.8000, "lat": 39.5300},
    {"name": "Google Henderson NV",         "lon": -114.9800, "lat": 36.0400},

    # ── Oklahoma ───────────────────────────────────────────────────────────
    {"name": "Google Pryor Creek OK",       "lon": -95.3200, "lat": 36.3100},

    # ── New Mexico ─────────────────────────────────────────────────────────
    {"name": "Meta Los Lunas NM",           "lon": -106.733, "lat": 34.806},
    {"name": "H5 Data Centers ABQ",         "lon": -106.651, "lat": 35.084},

    # ── South Carolina ─────────────────────────────────────────────────────
    {"name": "Google Berkeley County SC",   "lon": -80.0800, "lat": 33.1800},

    # ── Tennessee ──────────────────────────────────────────────────────────
    {"name": "Google Clarksville TN",       "lon": -87.3600, "lat": 36.5300},
    {"name": "Meta Gallatin TN",            "lon": -86.4500, "lat": 36.3900},

    # ── Alabama ────────────────────────────────────────────────────────────
    {"name": "Google Bridgeport AL",        "lon": -85.7100, "lat": 34.9500},
    {"name": "Meta Huntsville AL",          "lon": -86.5860, "lat": 34.7300},

    # ── Mississippi ────────────────────────────────────────────────────────
    {"name": "AWS (Lena MS area)",          "lon": -89.5900, "lat": 32.5900},

    # ── Indiana ────────────────────────────────────────────────────────────
    {"name": "Meta Lebanon IN",             "lon": -86.4700, "lat": 40.0500},
    {"name": "Microsoft Boone County IN",   "lon": -86.4800, "lat": 40.0600},

    # ── Wisconsin ──────────────────────────────────────────────────────────
    {"name": "Meta DeForest WI",            "lon": -89.3500, "lat": 43.2500},
    {"name": "Microsoft Mount Pleasant WI", "lon": -87.8800, "lat": 42.7200},

    # ── Wyoming ────────────────────────────────────────────────────────────
    {"name": "Microsoft Cheyenne WY",       "lon": -104.8200, "lat": 41.1400},
]


# ── Marker styles ──────────────────────────────────────────────────────────────
MARKER_STYLES = {
    "data_center": ((255, 60, 200), (180, 30, 140), "diamond", "Data Center", 1.0),
}


# ── Drawing helpers ────────────────────────────────────────────────────────────
def _font(sz: int):
    for p in ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size=sz)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _marker(draw, cx, cy, r, fill, outline):
    """Draw a diamond marker."""
    draw.polygon([(cx, cy - r * 1.3), (cx + r * 1.2, cy),
                  (cx, cy + r * 1.3), (cx - r * 1.2, cy)],
                 fill=fill, outline=outline)


def _draw_label(draw, text, cx, cy, font, color=(230, 235, 245),
                anchor_y_offset=-18, bg=(8, 9, 13, 200)):
    tw = draw.textlength(text, font=font)
    th = font.size
    tx = cx - tw / 2
    ty = cy + anchor_y_offset - th
    pad = 4
    draw.rounded_rectangle(
        [tx - pad, ty - pad, tx + tw + pad, ty + th + pad],
        radius=5, fill=bg, outline=(60, 65, 80, 160), width=1,
    )
    draw.text((tx, ty), text, fill=color, font=font)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _all_conus_huc4s() -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for state in CONUS_STATES:
        for h in STATE_HUC4.get(state, ()):
            if h not in seen:
                seen.add(h)
                ordered.append(h)
    return tuple(ordered)


def _read_svg_viewbox(svg_path: Path) -> tuple[float, float, float, float]:
    """Extract the viewBox from an SVG and return (origin_x, origin_y, width, height)."""
    import re
    with svg_path.open() as f:
        head = f.read(4000)
    m = re.search(r'viewBox="([^"]+)"', head)
    if not m:
        raise SystemExit(f"No viewBox found in {svg_path}")
    parts = m.group(1).split()
    return tuple(float(p) for p in parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="CONUS datacenter map")
    ap.add_argument("--base-png", type=str, default=None,
                    help="Existing CONUS hero PNG to overlay on (skips re-render).")
    ap.add_argument("--base-svg", type=str, default=None,
                    help="SVG whose viewBox defines the coordinate bounds (required with --base-png).")
    ap.add_argument("--min-order", type=int, default=5,
                    help="Drop streams below this Strahler order (default 5).")
    ap.add_argument("--width", type=int, default=8000,
                    help="Reference pixel width for stroke scaling (default 8000).")
    ap.add_argument("--min-px", type=float, default=0.3,
                    help="Stroke width (px) for the lowest-flow headwater.")
    ap.add_argument("--max-px", type=float, default=6.0,
                    help="Stroke width (px) for the highest-flow mainstem.")
    ap.add_argument("--no-labels", action="store_true",
                    help="Suppress datacenter name labels (less clutter at full-CONUS).")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Datacenters to plot: {len(DATACENTERS)}")

    if args.base_png:
        # ── Overlay-only mode: use existing hero render ────────────────
        png_path = args.base_png
        if not Path(png_path).exists():
            raise SystemExit(f"Base PNG not found: {png_path}")
        svg_ref = Path(args.base_svg) if args.base_svg else None
        if not svg_ref:
            svg_ref = Path(png_path).with_suffix(".svg")
        if not svg_ref.exists():
            raise SystemExit(
                f"Need --base-svg to read viewBox coordinates (tried {svg_ref})."
            )
        # The SVG uses a "0 0 W H" viewBox: all coordinates are shifted
        # by -min_x on X and flipped via max_y - y.  To map datacenter
        # lon/lats we need those original min_x / max_y.  Load the CONUS
        # boundary (fast — no flowlines) and use its bounds as a close
        # proxy; the flowline extent is slightly tighter but the state
        # boundary reliably contains all datacenters.
        print("loading CONUS boundary for coordinate mapping ...")
        state_geoms = [load_state(s) for s in CONUS_STATES]
        boundary = shapely.unary_union(state_geoms)
        bx = boundary.bounds  # (minx, miny, maxx, maxy)
        _, _, vb_w, vb_h = _read_svg_viewbox(svg_ref)
        # Use boundary center + viewBox dimensions to recover the render frame.
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        min_x = cx - vb_w / 2
        min_y = cy - vb_h / 2
        max_x = cx + vb_w / 2
        max_y = cy + vb_h / 2
        code_color = None
        print(f"overlay mode: base={png_path}, viewBox {vb_w:.0f}x{vb_h:.0f}")
    else:
        # ── Full render mode ───────────────────────────────────────────
        huc4s = _all_conus_huc4s()
        print(f"CONUS: {len(CONUS_STATES)} states, {len(huc4s)} HUC4 basins")

        print("loading CONUS boundary (48 state polygons) ...")
        state_geoms = [load_state(s) for s in CONUS_STATES]
        boundary = shapely.unary_union(state_geoms)
        print(f"boundary: {boundary.geom_type}")

        print(f"clipping flowlines (min_order={args.min_order}) from {len(huc4s)} HUC4s ...")
        geoms, orders, flows, basins = clip_flowlines(boundary, huc4s, args.min_order)
        print(f"total kept: {len(geoms):,}")
        if not geoms:
            raise SystemExit("No flowlines fell inside the CONUS boundary.")

        huc2_codes = [b[:2] for b in basins]
        geometries, segment_colors, watersheds, code_color = build_inputs(geoms, huc2_codes)
        widths, base_units, units_per_px, qmax = flow_scaled_widths(
            geometries, flows, args.width, args.min_px, args.max_px,
        )
        print(
            f"HUC2 groups: {sorted(watersheds)}; orders 1..{max(orders)}; "
            f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px"
        )

        svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)
        svg_path = OUT_DIR / "conus-datacenters.svg"
        svg_path.write_text(svg)
        print(f"wrote {svg_path} ({len(svg):,} bytes, {len(geometries):,} paths)")
        print(f"  sha256: {_sha256(svg_path)}")

        # Rasterize via rsvg-convert (handles large SVGs better than resvg).
        png_path = str(OUT_DIR / "conus-datacenters-base.png")
        import subprocess
        try:
            subprocess.run(
                ["rsvg-convert", "-w", str(args.width), str(svg_path), "-o", png_path],
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(f"rsvg-convert failed ({exc}); trying layered rasterizer ...")
            rasterize(str(svg_path), png_path, args.width, args.max_px)
        print(f"wrote {png_path}")

        min_x, min_y, max_x, max_y = bounds(geometries.values())

    # Overlay datacenter markers + legend.
    im = Image.open(png_path).convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    W, H = im.size
    sx, sy = W / (max_x - min_x), H / (max_y - min_y)
    draw = ImageDraw.Draw(overlay)

    marker_r = max(8, W // 500)
    label_font = _font(max(12, W // 500))
    legend_font = _font(max(18, W // 280))
    title_font = _font(max(24, W // 220))

    # Reproject datacenter locations from WGS84 to EPSG:5070.
    dc_lons = [d["lon"] for d in DATACENTERS]
    dc_lats = [d["lat"] for d in DATACENTERS]
    dc_pts = gpd.GeoSeries(
        gpd.points_from_xy(dc_lons, dc_lats), crs="EPSG:4326"
    ).to_crs(EPSG)

    # Draw markers.
    fill, outline, _, _, _ = MARKER_STYLES["data_center"]
    plotted = 0
    for dc, pt in zip(DATACENTERS, dc_pts):
        px = (pt.x - min_x) * sx
        py = (max_y - pt.y) * sy
        if -marker_r <= px <= W + marker_r and -marker_r <= py <= H + marker_r:
            _marker(draw, px, py, marker_r, fill, outline)
            plotted += 1
            if not args.no_labels:
                _draw_label(draw, dc["name"], px, py, label_font,
                            anchor_y_offset=-(marker_r + 4))
    print(f"plotted: {plotted}/{len(DATACENTERS)} datacenters")

    # Legend (bottom-left).
    pad = legend_font.size
    lh = int(legend_font.size * 1.8)

    title = "US Data Centers on CONUS Hydrography"
    subtitle = f"{plotted} major data-center campuses"

    # Region counts
    region_counts: Counter = Counter()
    for dc in DATACENTERS:
        # Rough region assignment from lon
        lon = dc["lon"]
        if lon > -80:
            region_counts["East"] += 1
        elif lon > -100:
            region_counts["Central"] += 1
        else:
            region_counts["West"] += 1
    region_line = "  ".join(f"{k}: {v}" for k, v in sorted(region_counts.items()))

    # Build legend box
    legend_lines = [
        ("marker", "Data Center Campus", f"({plotted})", fill, outline),
    ]

    all_labels = [title, subtitle, region_line] + [
        f"{r[1]}  {r[2]}" for r in legend_lines
    ]
    text_w = max(draw.textlength(lbl, font=legend_font) for lbl in all_labels)
    sw = int(legend_font.size * 1.1)
    pw = int(pad * 3 + sw + text_w + 20)

    # HUC2 basin swatches (top-level macro-basins) — only in full-render mode.
    basin_rows = []
    huc2_names = {
        "01": "New England",    "02": "Mid-Atlantic",   "03": "South Atlantic",
        "04": "Great Lakes",    "05": "Ohio",            "06": "Tennessee",
        "07": "Upper Mississippi", "08": "Lower Mississippi", "09": "Souris-Red-Rainy",
        "10": "Missouri",       "11": "Arkansas-White-Red", "12": "Texas-Gulf",
        "13": "Rio Grande",     "14": "Upper Colorado",  "15": "Lower Colorado",
        "16": "Great Basin",    "17": "Pacific Northwest", "18": "California",
    }
    if code_color:
        for code in sorted(code_color):
            bname = huc2_names.get(code, f"HUC2-{code}")
            basin_rows.append((bname, code, code_color[code]))

    total_rows = len(legend_lines) + len(basin_rows) + 4  # title, subtitle, region, + separator lines
    ph = int(pad * 2 + lh * total_rows)

    x0, y0 = pad, H - pad - ph
    draw.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=8,
                           fill=(8, 9, 13, 220), outline=(70, 74, 88), width=2)

    draw.text((x0 + pad, y0 + pad), title, fill=(235, 239, 248), font=title_font)
    y = y0 + pad + lh
    draw.text((x0 + pad, y), subtitle, fill=(160, 170, 190), font=legend_font)
    y += lh
    draw.text((x0 + pad, y), region_line, fill=(140, 150, 170), font=legend_font)
    y += lh

    # Facility marker row
    draw.text((x0 + pad, y), "SYMBOLS", fill=(160, 170, 190), font=legend_font)
    y += lh
    for _, label, count_str, mfill, moutline in legend_lines:
        sy_center = y + lh // 2
        _marker(draw, x0 + pad + sw // 2, sy_center, int(sw * 0.45), mfill, moutline)
        draw.text((x0 + pad * 2 + sw, y + (lh - legend_font.size) // 2),
                  f"{label}  {count_str}", fill=(226, 230, 240), font=legend_font)
        y += lh

    # Basin swatches
    for bname, code, color in basin_rows:
        sy_top = y + (lh - sw) // 2
        rgb = _hex_rgb(color)
        draw.rectangle([x0 + pad, sy_top, x0 + pad + sw, sy_top + sw], fill=rgb)
        draw.text((x0 + pad * 2 + sw, y + (lh - legend_font.size) // 2),
                  bname, fill=(226, 230, 240), font=legend_font)
        draw.text((x0 + pad * 2 + sw + draw.textlength(bname + "   ", font=legend_font),
                   y + (lh - legend_font.size) // 2),
                  code, fill=(120, 126, 142), font=legend_font)
        y += lh

    # Composite overlay onto base.
    im = Image.alpha_composite(im, overlay)
    final = im.convert("RGB")

    final_path = str(OUT_DIR / "conus-datacenters.png")
    final.save(final_path)
    print(f"wrote {final_path} ({W}x{H})")
    print(f"  sha256: {_sha256(Path(final_path))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
