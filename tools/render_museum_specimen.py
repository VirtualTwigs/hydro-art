"""Museum print concept #01 — "The Specimen" — as a real Washington render.

Turns the hand-drawn placeholder in ``experiments/museum-print-layouts.html``
(concept 01 / THE SPECIMEN) into a full-resolution, print-ready artwork driven by
real NHDPlus HR hydrography. A single watershed is held like a specimen inside a
generous museum mat: the river network is tinted by stream-surface *elevation* on
a near-monochrome teal ramp (deep tidewater trunk -> pale alpine headwaters) so the
saturated mainstem is the only strong mark, exactly as the concept intends.

Default subject is the **Skagit River Basin** (WBD HUC8 17110005 Upper Skagit,
17110006 Sauk, 17110007 Lower Skagit) — the same basin named in the mockup.

Pipeline:
  1. dissolve the basin's HUC8 polygons -> EPSG:5070 boundary (WBD).
  2. clip NHDPlus HR flowlines to it, carrying Strahler order, QAMA discharge and
     smoothed elevation (reuses ``tools/render_common`` + ``render_state_mono``).
  3. tint each reach by elevation (paper-friendly ramp), width by discharge.
  4. rasterize the river art to a transparent hi-res PNG (correct metre->px strokes).
  5. compose the museum layout in vector SVG — paper field, Fraunces title, DM Mono
     coordinate line, an elevation scale bar, watermark — with the art embedded.
  6. export a hi-res proof PNG (resvg) and a print-ready PDF (rsvg-convert).

Fonts: the layout uses Fraunces (title) + DM Mono (labels), both OFL/SIL-licensed
(commercially safe). ``resvg`` reads them from ``assets/fonts`` via
``--use-fonts-dir``; ``rsvg-convert`` (the PDF path) resolves them through
fontconfig, so the two TTFs must also live in ``~/Library/Fonts`` (a one-time
``cp assets/fonts/*.ttf ~/Library/Fonts && fc-cache -f``). The title uses a static
600-weight instance (``FrauncesDisplay-600.ttf``) because the shipped Fraunces
variable font defaults to weight 900.

Like every ``tools/`` script this imports the heavy GIS stack eagerly and reads
real data; it is outside ``src/`` and the offline suite.

    python tools/render_museum_specimen.py            # Skagit, defaults
    python tools/render_museum_specimen.py --min-order 2 --raster-width 7200
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.rendering import render_svg
from tools.museum_common import (
    COPYRIGHT, MONO_FONT, OUT_DIR, TITLE_FONT, copyright_text, export_pdf,
    export_png, fmt_lonlat, load_basin, lonlat_of, rasterize_art,
)
from tools.render_common import clip_flowlines, flow_scaled_widths
from tools.render_state_mono import derive_elevations

# --- Specimen art direction ------------------------------------------------- #
PAPER = "#f1efe7"          # cotton-rag paper field (matches the concept sheet)
INK = "#26302b"            # near-black title ink
MUTED = "#6a746b"          # DM Mono label grey
RULE = "#c2c3b8"           # hairline rule
#: Near-monochrome elevation ramp readable on paper: deep saturated tidewater
#: teal (low, t=0 — the one strong mark) -> pale cool sage (alpine, t=1).
RAMP_LOW = (18, 86, 94)    # #12565e
RAMP_HIGH = (150, 178, 166)  # #96b2a6

#: Skagit River Basin — the three HUC8s that make up the drainage.
SKAGIT_HUC8 = ("17110005", "17110006", "17110007")


def paper_elevation_colors(elevs, gamma: float, anchor: float) -> dict[int, str]:
    """Map per-reach elevation (m) -> RAMP_LOW..RAMP_HIGH hex on ``t=(e/anchor)^g``."""
    arr = np.clip(np.asarray(elevs, dtype=float), 0.0, None)
    t = np.zeros_like(arr) if anchor <= 0 else np.clip(arr / anchor, 0.0, 1.0) ** gamma
    lo, hi = np.array(RAMP_LOW, float), np.array(RAMP_HIGH, float)
    out: dict[int, str] = {}
    for i, ti in enumerate(t):
        r, g, b = (lo + (hi - lo) * ti).round().astype(int)
        out[i] = f"#{r:02x}{g:02x}{b:02x}"
    return out


def compose_layout(
    art_png: Path, title: str, region: str, lonlat: tuple[float, float],
    emax_m: float,
) -> str:
    """Compose the concept-01 print layout (viewBox 900x665) around the art PNG."""
    W, H = 900, 665
    b64 = base64.b64encode(art_png.read_bytes()).decode()
    href = f"data:image/png;base64,{b64}"
    # Specimen window (museum mat): the art floats inside with meet-letterboxing.
    mx, my, mw, mh = 60, 120, 780, 452
    coord = fmt_lonlat(*lonlat)
    # Elevation scale bar (bottom-left ramp swatch + tick labels).
    bar_x, bar_y, bar_w, bar_h = 60, 604, 250, 9
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="elev" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="rgb{RAMP_LOW}"/>
      <stop offset="1" stop-color="rgb{RAMP_HIGH}"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="{PAPER}"/>
  <text x="60" y="70" fill="{INK}" font-family="{TITLE_FONT}"
        font-size="30" letter-spacing="-0.3">{title}</text>
  <text x="61" y="95" fill="{MUTED}" font-family="{MONO_FONT}" font-size="10"
        letter-spacing="2">{region} \u00b7 {coord}</text>
  <rect x="{mx}" y="{my}" width="{mw}" height="{mh}" fill="none"
        stroke="{RULE}" stroke-width="0.8"/>
  <image xlink:href="{href}" x="{mx}" y="{my}" width="{mw}" height="{mh}"
         preserveAspectRatio="xMidYMid meet"/>
  <line x1="60" x2="840" y1="590" y2="590" stroke="{RULE}"/>
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="url(#elev)"
        stroke="{RULE}" stroke-width="0.5"/>
  <text x="{bar_x}" y="{bar_y + bar_h + 15}" fill="{MUTED}" font-family="DM Mono"
        font-size="9" letter-spacing="1">ELEVATION  0 M</text>
  <text x="{bar_x + bar_w}" y="{bar_y + bar_h + 15}" fill="{MUTED}"
        font-family="{MONO_FONT}" font-size="9" letter-spacing="1"
        text-anchor="end">{emax_m:,.0f} M</text>
  <text x="840" y="612" fill="#7f8881" font-family="{MONO_FONT}" font-size="9"
        letter-spacing="0.8" text-anchor="end">EDITION STUDY</text>
  {copyright_text(840, 628, fill="#9aa39b")}
</svg>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", default="Skagit River Basin")
    ap.add_argument("--region", default="WASHINGTON")
    ap.add_argument("--huc8", nargs="+", default=list(SKAGIT_HUC8))
    ap.add_argument("--spec", default="1711", help="HUC4(s) to scan for flowlines.")
    ap.add_argument("--min-order", type=int, default=2,
                    help="Drop streams below this Strahler order (higher = sparser).")
    ap.add_argument("--gamma", type=float, default=1.15)
    ap.add_argument("--anchor-pct", type=float, default=97.0)
    ap.add_argument("--art-width", type=int, default=4800,
                    help="Reference px width the river-art raster is authored at.")
    ap.add_argument("--min-px", type=float, default=1.1)
    ap.add_argument("--max-px", type=float, default=8.0)
    ap.add_argument("--raster-width", type=int, default=6000,
                    help="Final proof PNG width in px.")
    ap.add_argument("--print-w-in", type=float, default=24.0,
                    help="Physical width of the print PDF in inches (height follows "
                         "the layout's 900:665 landscape ratio).")
    ap.add_argument("--slug", default="specimen_skagit")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"loading basin {args.huc8} ...")
    boundary = load_basin(tuple(args.huc8))
    lonlat = lonlat_of(boundary)
    print(f"  centroid {fmt_lonlat(*lonlat)}")

    print(f"clipping flowlines (min_order={args.min_order}) from {args.spec} ...")
    geoms, _orders, flows, _basins, extras = clip_flowlines(
        boundary, args.spec, args.min_order,
        extra_vaa_cols=["MinElevSmo", "MaxElevSmo"],
    )
    if not geoms:
        raise SystemExit("No flowlines fell inside the basin.")
    print(f"  kept {len(geoms)} reaches")

    _elev_mean, elev_max = derive_elevations(extras["MinElevSmo"], extras["MaxElevSmo"])
    anchor = float(np.percentile(np.clip(elev_max, 0.0, None), args.anchor_pct))
    geometries = {i: g for i, g in enumerate(geoms)}
    segment_colors = paper_elevation_colors(elev_max, args.gamma, anchor)
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.art_width, args.min_px, args.max_px
    )
    print(f"elevation 0..{anchor:.0f} m (p{args.anchor_pct:g}) -> teal..sage; "
          f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px")

    # Transparent river art (no background rect fill).
    art_svg = render_svg(
        geometries, segment_colors, {},
        background="none", line_width=base_units, stroke_widths=widths, glow=False,
    )
    art_png = OUT_DIR / f"{args.slug}_art.png"
    rasterize_art(art_svg, art_png, args.art_width, args.max_px)
    print(f"wrote {art_png}")

    layout = compose_layout(art_png, args.title, args.region, lonlat, anchor)
    layout_svg = OUT_DIR / f"{args.slug}.svg"
    layout_svg.write_text(layout)
    print(f"wrote {layout_svg}")

    final_png = OUT_DIR / f"{args.slug}.png"
    export_png(layout_svg, final_png, args.raster_width)
    print(f"wrote {final_png}")

    final_pdf = OUT_DIR / f"{args.slug}.pdf"
    export_pdf(layout_svg, final_pdf, args.print_w_in)
    print(f"wrote {final_pdf}  ({args.print_w_in}\u00d7{args.print_w_in * 665 / 900:.1f} in)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
