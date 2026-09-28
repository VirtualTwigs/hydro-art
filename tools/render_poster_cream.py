"""Render a museum-style art poster: elevation-tinted rivers on warm cream.

A gallery/print variant of ``render_state_mono.py`` that swaps the dark neon
aesthetic for a warm, archival look: cream paper background with rivers colored
on a deep-brown (lowland) to burnt-sienna to warm-gold (summit) ramp. No glow —
clean hairlines suitable for large-format giclée or offset printing.

    python tools/render_poster_cream.py --state Indiana --width 6000
    python tools/render_poster_cream.py --state Indiana --min-order 3 --width 8000
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.rendering import bounds, render_svg
from tools.render_common import (
    STATE_HUC4,
    clip_flowlines,
    flow_scaled_widths,
    load_state,
)
from tools.render_state_mono import (
    ELEV_NODATA,
    derive_elevations,
    rasterize_whole,
)

# ── Museum palette ──────────────────────────────────────────────────────────
#: Warm cream ground — like heavy cotton rag paper.
CREAM = "#f5f0e6"

#: River color ramp: deep brown (sea level/lowland) -> burnt sienna -> warm gold
#: (highest streams). Designed for legibility on cream.
LOW_COLOR = (62, 39, 25)       # dark umber — lowland rivers
HIGH_COLOR = (180, 120, 45)    # warm gold — highland headwaters

#: Title/text colors for the poster chrome.
TITLE_INK = (42, 32, 22)      # near-black warm brown
SUBTITLE_INK = (110, 90, 68)  # mid-brown


def museum_elevation_colors(elevs, gamma: float, anchor: float | None = None,
                            *, lo_rgb=None, hi_rgb=None):
    """Map per-reach elevation -> low..high hex, anchored at the max."""
    arr = np.clip(np.asarray(elevs, dtype=float), 0.0, None)
    emax = anchor if anchor else (float(arr.max()) if arr.size else 0.0)
    t = np.zeros_like(arr) if emax <= 0 else np.clip(arr / emax, 0.0, 1.0) ** gamma
    lo = np.array(lo_rgb or LOW_COLOR, dtype=float)
    hi = np.array(hi_rgb or HIGH_COLOR, dtype=float)
    colors: dict[int, str] = {}
    for i, ti in enumerate(t):
        r, g, b = (lo + (hi - lo) * ti).round().astype(int)
        colors[i] = f"#{r:02x}{g:02x}{b:02x}"
    return colors, emax


def _font(sz: int):
    for p in ("/System/Library/Fonts/NewYork.ttf",
              "/System/Library/Fonts/NewYorkItalic.ttf",
              "/Library/Fonts/Georgia.ttf",
              "/System/Library/Fonts/Times.ttc",
              "/System/Library/Fonts/SFNSMono.ttf",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size=sz)
        except Exception:
            continue
    return ImageFont.load_default()


def add_poster_chrome(png_path: str, state: str, n_streams: int,
                      elev_max: float, out_path: str,
                      bg_hex: str | None = None) -> None:
    """Add a title bar and attribution below the map."""
    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    bg_hex = bg_hex or CREAM

    # Title bar height
    bar_h = int(H * 0.12)
    footer_h = int(H * 0.04)
    bg_rgb = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    # Pick light or dark text based on background luminance
    lum = bg_rgb[0] * 0.299 + bg_rgb[1] * 0.587 + bg_rgb[2] * 0.114
    dark_text = lum > 128
    title_ink = TITLE_INK if dark_text else (235, 239, 248)
    sub_ink = SUBTITLE_INK if dark_text else (160, 170, 190)
    canvas = Image.new("RGB", (W, H + bar_h + footer_h), bg_rgb)
    canvas.paste(im, (0, bar_h))
    draw = ImageDraw.Draw(canvas)

    # Title
    fs_title = max(48, W // 18)
    fs_sub = max(20, W // 45)
    fs_foot = max(14, W // 60)
    title_font = _font(fs_title)
    sub_font = _font(fs_sub)
    foot_font = _font(fs_foot)

    pad = max(40, W // 30)
    # State name, centered
    title_y = int(bar_h * 0.12)
    tw = draw.textlength(state.upper(), font=title_font)
    draw.text(((W - tw) / 2, title_y), state.upper(),
              fill=title_ink, font=title_font)

    # Subtitle — positioned below the title with a gap
    subtitle_y = title_y + fs_title + int(bar_h * 0.08)
    subtitle = f"Rivers & Streams  |  {n_streams:,} waterways  |  elevation 0\u2013{elev_max:.0f} m"
    sw = draw.textlength(subtitle, font=sub_font)
    draw.text(((W - sw) / 2, subtitle_y), subtitle,
              fill=sub_ink, font=sub_font)

    # Footer
    footer = "USGS NHDPlus HR  \u00b7  Elevation-tinted  \u00b7  hydro-art"
    fw = draw.textlength(footer, font=foot_font)
    draw.text(((W - fw) / 2, H + bar_h + footer_h * 0.2), footer,
              fill=sub_ink, font=foot_font)

    canvas.save(out_path, quality=95)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="Indiana")
    ap.add_argument("--min-order", type=int, default=3,
                    help="Drop streams below this Strahler order.")
    ap.add_argument("--width", type=int, default=6000,
                    help="Raster width in px.")
    ap.add_argument("--min-px", type=float, default=0.5,
                    help="Stroke width (px) for lowest-flow headwaters.")
    ap.add_argument("--max-px", type=float, default=4.0,
                    help="Stroke width (px) for highest-flow mainstem.")
    ap.add_argument("--gamma", type=float, default=0.65,
                    help="Elevation ramp shaping; <1 brightens mid-slopes toward gold.")
    ap.add_argument("--anchor-pct", type=float, default=97.0,
                    help="Percentile of reach elevation mapping to pure gold.")
    ap.add_argument("--bg", default=None,
                    help="Background hex color (default: cream #f5f0e6).")
    ap.add_argument("--low-color", default=None,
                    help="Lowland stream RGB as 'R,G,B' (default: 62,39,25 dark umber).")
    ap.add_argument("--high-color", default=None,
                    help="Highland stream RGB as 'R,G,B' (default: 180,120,45 warm gold).")
    ap.add_argument("--tag", default=None,
                    help="Output filename tag (default: state name).")
    ap.add_argument("--no-chrome", action="store_true",
                    help="Skip the title bar / footer (raw map only).")
    args = ap.parse_args()

    spec = STATE_HUC4.get(args.state)
    if not spec:
        raise SystemExit(f"No HUC4 mapping for {args.state!r}; check STATE_HUC4.")

    # Custom palette overrides
    bg = args.bg or CREAM
    lo_color = tuple(int(x) for x in args.low_color.split(",")) if args.low_color else LOW_COLOR
    hi_color = tuple(int(x) for x in args.high_color.split(",")) if args.high_color else HIGH_COLOR

    tag = args.tag or args.state.lower().replace(" ", "_")
    state_tag = args.state.lower().replace(" ", "_")
    cache = Path(f"output/_clipcache_{state_tag}_mo{args.min_order}.pkl")
    if cache.exists():
        print(f"loading cached clip {cache} ...")
        geoms, elev_mean, elev_max, flows = pickle.loads(cache.read_bytes())
    else:
        print(f"loading {args.state} boundary ...")
        boundary = load_state(args.state)
        print(f"clipping flowlines (min_order={args.min_order}) from {spec} ...")
        geoms, _orders, flows, _basins, extras = clip_flowlines(
            boundary, spec, args.min_order,
            extra_vaa_cols=["MinElevSmo", "MaxElevSmo"],
        )
        elev_mean, elev_max_list = derive_elevations(
            extras["MinElevSmo"], extras["MaxElevSmo"]
        )
        cache.write_bytes(pickle.dumps((geoms, elev_mean, elev_max_list, flows)))
        elev_max = elev_max_list  # rename for clarity below
    print(f"total kept: {len(geoms)}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the state boundary.")

    # Use max elevation per reach for coloring
    elevs = elev_max if isinstance(elev_max, list) else elev_max
    anchor = float(np.percentile(np.clip(elevs, 0.0, None), args.anchor_pct))
    geometries = {i: g for i, g in enumerate(geoms)}
    segment_colors, emax = museum_elevation_colors(elevs, args.gamma, anchor,
                                                    lo_rgb=lo_color, hi_rgb=hi_color)
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px
    )
    print(f"elevation 0..{emax:.0f} m -> brown..gold "
          f"(gamma={args.gamma}, anchor p{args.anchor_pct:g})")
    print(f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px")

    # Render SVG with cream background, no glow (clean print lines)
    svg = render_svg(
        geometries, segment_colors, {},
        background=bg, line_width=base_units, stroke_widths=widths,
        glow=False,
    )

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    svg_out = out_dir / f"{tag}_poster.svg"
    png_raw = out_dir / f"{tag}_poster_raw.png"
    png_out = out_dir / f"{tag}_poster.png"

    svg_out.write_text(svg)
    print(f"wrote {svg_out} ({len(svg):,} bytes, {len(geometries):,} paths)")

    rasterize_whole(svg, str(png_raw), args.width, args.max_px)
    print(f"wrote {png_raw}")

    if not args.no_chrome:
        add_poster_chrome(str(png_raw), args.state, len(geoms), emax, str(png_out),
                          bg_hex=bg)
        print(f"wrote {png_out} (with title + footer)")
    else:
        import shutil
        shutil.copy(str(png_raw), str(png_out))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
