#!/usr/bin/env python3
"""Compose the landing page's "Watershed report" thumbnail from real report figures.

The customer landing (`web/start.html`) shows one card per production endpoint. The
report card should *look like the final report* a buyer receives — so this stitches the
actual deliverable panels produced by ``tools/build_watershed_report.py``
(``notebooks/figures/salmon_creek_*.png``) into a single report-style card:

    header (title + provenance)
    river-network map          (full-width hero)
    year-over-year hydrographs | typical-year flow   (two columns)

Output is ``output/watershed_report_card.png``; ``deploy/stage-artifacts.sh`` down-scales
it to ``deploy/output/landing/clark-report.webp``. Pure Pillow, no GIS — but it reads real
figures, so it lives in ``tools/`` (outside the offline suite), like the other renderers.

Usage:
    python tools/build_report_card.py            # default figures + output path
"""
from __future__ import annotations

import argparse
import os

from PIL import Image, ImageDraw, ImageFont

# Site-dark background, matching the matplotlib figure canvas (~ #0a0e1a).
BG = (10, 14, 26)
FG = (233, 238, 247)
SUB = (150, 165, 190)

WIDTH = 1400
MARGIN = 22
GUTTER = 18
HEADER = 92

TITLE = "Salmon Creek — Watershed Report"
SUBTITLE = "Clark County, WA · year-over-year flow · 1944–1989 · USGS NHDPlus HR"

_FONT_CANDIDATES = {
    True: [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    False: [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES[bold]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit(img: Image.Image, width: int) -> Image.Image:
    height = round(img.height * (width / img.width))
    return img.resize((width, height), Image.LANCZOS)


def build_card(figdir: str, out_path: str) -> str:
    load = lambda name: Image.open(os.path.join(figdir, name)).convert("RGB")
    hydro = load("salmon_creek_hydrographs.png")
    mp = load("salmon_creek_map.png")
    typ = load("salmon_creek_typical_year.png")

    inner = WIDTH - 2 * MARGIN
    map_r = _fit(mp, inner)
    col_w = (inner - GUTTER) // 2
    hydro_r = _fit(hydro, col_w)
    typ_r = _fit(typ, col_w)
    row2_h = max(hydro_r.height, typ_r.height)

    total_h = HEADER + map_r.height + GUTTER + row2_h + MARGIN
    canvas = Image.new("RGB", (WIDTH, total_h), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN, 20), TITLE, font=_font(40, True), fill=FG)
    draw.text((MARGIN, 66), SUBTITLE, font=_font(19, False), fill=SUB)

    y = HEADER
    canvas.paste(map_r, (MARGIN, y))
    y += map_r.height + GUTTER
    canvas.paste(hydro_r, (MARGIN, y))
    canvas.paste(typ_r, (MARGIN + col_w + GUTTER, y))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)
    return out_path


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--figures", default=os.path.join(repo, "notebooks", "figures"))
    ap.add_argument("--out", default=os.path.join(repo, "output", "watershed_report_card.png"))
    args = ap.parse_args()
    out = build_card(args.figures, args.out)
    with Image.open(out) as im:
        print(f"wrote {out} {im.size}")


if __name__ == "__main__":
    main()
