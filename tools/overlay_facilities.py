"""Overlay OSM water-infrastructure points on the Clark County river render.

Reads the facility points saved by the Overpass pull
(``datasets/osm/clark_water_infra.geojson``) and plots them on top of an
existing Clark County PNG (default ``output/clark_county_legend.png``).

Point pixels are computed with the *exact* same anchor the renderer used: the
flowlines are re-clipped (deterministically) to recover ``min_x/max_y`` in
EPSG:5070, then each facility ``(lon, lat)`` becomes
``((x-min_x)*sx, (max_y-y)*sy)`` — identical to ``draw_outline`` in
``render_county_clip.py``, so markers land on the matching streams.

    python tools/overlay_facilities.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
from PIL import Image, ImageDraw, ImageFont

from src.rendering import bounds
from tools.render_county_clip import (
    CLARK_BBOX_4326,
    bbox_boundary,
    clip_flowlines,
)

GEOJSON = "datasets/osm/clark_water_infra.geojson"
BASE_PNG = "output/clark_county_legend.png"
OUT_PNG = "output/clark_county_facilities.png"

#: (fill RGB, marker shape, human label) per OSM man_made category.
STYLE = {
    "pumping_station": ((255, 92, 92), "circle", "Pumping station"),
    "storage_tank": ((120, 230, 120), "square", "Storage tank / reservoir"),
    "water_tower": ((255, 214, 66), "triangle", "Water tower"),
    "water_works": ((90, 200, 255), "diamond", "Water works"),
    "water_well": ((210, 130, 255), "dot", "Water well"),
}


def load_points():
    gj = json.load(open(GEOJSON))
    pts = []
    for f in gj["features"]:
        cat = f["properties"]["category"]
        if cat not in STYLE:  # skip drainage centroids (need line geometry)
            continue
        lon, lat = f["geometry"]["coordinates"]
        pts.append((cat, lon, lat, f["properties"].get("name")))
    return pts


def _font(sz: int):
    for p in ("/System/Library/Fonts/SFNSMono.ttf",
              "/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size=sz)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _marker(draw, shape, cx, cy, r, fill):
    outline = (10, 12, 16)
    if shape == "circle":
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=2)
    elif shape == "dot":
        draw.ellipse([cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7],
                     fill=fill, outline=outline, width=2)
    elif shape == "square":
        draw.rectangle([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=2)
    elif shape == "triangle":
        draw.polygon([(cx, cy - r * 1.2), (cx - r, cy + r), (cx + r, cy + r)],
                     fill=fill, outline=outline)
    elif shape == "diamond":
        draw.polygon([(cx, cy - r * 1.3), (cx + r * 1.2, cy), (cx, cy + r * 1.3), (cx - r * 1.2, cy)],
                     fill=fill, outline=outline)


def main() -> int:
    print("re-clipping flowlines to recover render bounds ...")
    boundary = bbox_boundary(CLARK_BBOX_4326)
    geoms, *_ = clip_flowlines(boundary, "1708", 1)
    min_x, min_y, max_x, max_y = bounds({i: g for i, g in enumerate(geoms)}.values())

    im = Image.open(BASE_PNG).convert("RGB")
    W, H = im.size
    sx, sy = W / (max_x - min_x), H / (max_y - min_y)
    draw = ImageDraw.Draw(im)

    pts = load_points()
    # Reproject all facility lon/lat -> EPSG:5070 in one shot.
    g = gpd.GeoSeries(gpd.points_from_xy([p[1] for p in pts], [p[2] for p in pts]),
                      crs="EPSG:4326").to_crs("EPSG:5070")

    r = max(7, W // 380)
    from collections import Counter
    counts: Counter = Counter()
    for (cat, *_), pt in zip(pts, g):
        px, py = (pt.x - min_x) * sx, (max_y - pt.y) * sy
        if -r <= px <= W + r and -r <= py <= H + r:
            fill, shape, _ = STYLE[cat]
            _marker(draw, shape, px, py, r, fill)
            counts[cat] += 1
    print("plotted:", dict(counts))

    # Legend panel, bottom-left (top-left holds the sub-watershed key already).
    fs = max(26, W // 150)
    font, title_font = _font(fs), _font(int(fs * 1.25))
    rows = [(STYLE[c][2], STYLE[c][1], STYLE[c][0], counts.get(c, 0))
            for c in STYLE if counts.get(c, 0)]
    pad, lh = fs, int(fs * 1.7)
    title = "Water infrastructure (OSM)"
    text_w = max([draw.textlength(f"{lbl}  ({n})", font=font) for lbl, _, _, n in rows]
                 + [draw.textlength(title, font=title_font)])
    pw = int(pad * 3 + fs * 1.3 + text_w)
    ph = int(pad * 2 + lh * (len(rows) + 1))
    x0, y0 = pad, H - pad - ph
    draw.rectangle([x0, y0, x0 + pw, y0 + ph], fill=(8, 9, 13), outline=(70, 74, 88), width=2)
    draw.text((x0 + pad, y0 + pad), title, fill=(235, 239, 248), font=title_font)
    y = y0 + pad + lh
    for lbl, shape, color, n in rows:
        _marker(draw, shape, x0 + pad + fs * 0.6, y + fs * 0.55, int(fs * 0.55), color)
        draw.text((x0 + pad * 2 + fs * 0.9, y), f"{lbl}  ({n})", fill=(226, 230, 240), font=font)
        y += lh

    im.save(OUT_PNG)
    print(f"wrote {OUT_PNG} ({W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
