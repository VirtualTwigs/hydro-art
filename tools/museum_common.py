"""Shared composition + export plumbing for the museum print concepts.

The ``experiments/museum-print-layouts.html`` sheet defines five framed print
directions. Each concept has its own ``tools/render_museum_*.py`` that builds a
real, data-driven artwork, but they all share the same finishing pipeline:

  * transparent hi-res raster of the river art (correct metre->px strokes),
  * a vector SVG layout composed around it (Fraunces title + DM Mono labels),
  * export to a hi-res proof PNG (``resvg``) and a print-ready vector PDF
    (``rsvg-convert``), with a Runde Strategies copyright line.

Fonts are OFL/SIL (commercially safe): Fraunces (display, a static 600 instance
``FrauncesDisplay-600.ttf`` since the variable font defaults to weight 900) and
DM Mono. ``resvg`` reads them from ``assets/fonts`` via ``--use-fonts-dir``;
``rsvg-convert`` resolves them through fontconfig, so the TTFs must also be
installed in ``~/Library/Fonts`` (``cp assets/fonts/*.ttf ~/Library/Fonts &&
fc-cache -f``).

Like the rest of ``tools/`` this reads real data and imports GIS eagerly; it is
outside ``src/`` and the offline suite.
"""

from __future__ import annotations

import datetime as _dt
import glob
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from tools.render_common import EPSG, WBD_GLOB

REPO = Path(__file__).resolve().parent.parent
FONTS_DIR = REPO / "assets" / "fonts"
OUT_DIR = REPO / "output" / "museum"

TITLE_FONT = "Fraunces Display"   # static 600 instance
MONO_FONT = "DM Mono"
COPYRIGHT = f"\u00a9 {_dt.date.today().year} RUNDE STRATEGIES"

# Layout authoring space is a 900-wide canvas; per-concept aspect sets the height.
CANVAS_W = 900


# --------------------------------------------------------------------------- #
# Boundaries
# --------------------------------------------------------------------------- #
def _wbd_frames(layer: str, col: str):
    frames = []
    for gdb in sorted(glob.glob(WBD_GLOB, recursive=True)):
        try:
            frames.append(gpd.read_file(gdb, layer=layer, columns=[col, "name"]))
        except Exception:  # noqa: BLE001
            continue
    return frames


def load_hucs(level: int, codes) -> gpd.GeoDataFrame:
    """Return WBD ``WBDHU{level}`` polygons (EPSG:5070) whose code is in ``codes``.

    ``codes`` may be full HUC codes or shorter prefixes (a prefix keeps every
    sub-unit that starts with it, e.g. ``"1711"`` -> all HUC8s in that HUC4).
    """
    col, layer = f"huc{level}", f"WBDHU{level}"
    wanted = tuple(str(c) for c in codes)
    frames = []
    for df in _wbd_frames(layer, col):
        s = df[col].astype(str)
        keep = s.apply(lambda v: v.startswith(wanted))
        sel = df[keep]
        if len(sel):
            frames.append(sel.to_crs(EPSG))
    if not frames:
        raise SystemExit(f"No {layer} polygons matching {wanted} under datasets/wbd/.")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True))


def load_basin(huc8) -> object:
    """Dissolve the named HUC8 polygons into one EPSG:5070 boundary geometry."""
    hucs = load_hucs(8, huc8)
    return shapely.union_all(np.array(hucs.geometry.values, dtype=object))


def lonlat_of(geom) -> tuple[float, float]:
    """Return the (lon, lat) centroid of an EPSG:5070 geometry in WGS84."""
    c = gpd.GeoSeries([geom.centroid], crs=EPSG).to_crs("EPSG:4326").iloc[0]
    return c.x, c.y


def fmt_lonlat(lon: float, lat: float) -> str:
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    return f"{abs(lat):.3f}\u00b0 {ns} / {abs(lon):.3f}\u00b0 {ew}"


# --------------------------------------------------------------------------- #
# Rasterize + export
# --------------------------------------------------------------------------- #
def rasterize_art(svg: str, png_path: Path, width: int, stroke_px: float,
                  glow_px: float | None = None) -> None:
    """Rescale metre-unit root stroke (and glow) to px, then one transparent
    ``resvg`` pass (no background => RGBA transparency for compositing)."""
    m = re.search(r'viewBox="0 0 ([0-9.]+) ', svg)
    units_per_px = float(m.group(1)) / width
    svg = re.sub(r'(stroke-width=")[0-9.]+(")',
                 rf'\g<1>{stroke_px * units_per_px:.4f}\g<2>', svg, count=1)
    if glow_px is not None:
        svg = re.sub(r'(stdDeviation=")[0-9.]+(")',
                     rf'\g<1>{glow_px * units_per_px:.4f}\g<2>', svg)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tmp:
        tmp.write(svg)
        tmp_path = tmp.name
    subprocess.run(["resvg", "--width", str(width), tmp_path, str(png_path)], check=True)
    Path(tmp_path).unlink(missing_ok=True)


def export_png(layout_svg: Path, png_path: Path, width: int) -> None:
    """Rasterize a finished layout SVG to a proof PNG with the museum fonts."""
    subprocess.run(
        ["resvg", "--use-fonts-dir", str(FONTS_DIR), "--width", str(width),
         str(layout_svg), str(png_path)], check=True,
    )


def export_pdf(layout_svg: Path, pdf_path: Path, print_w_in: float) -> None:
    """Vector print PDF at ``print_w_in`` wide (height follows the SVG aspect).

    Fonts resolve via fontconfig, so the TTFs must be in ``~/Library/Fonts``.
    """
    subprocess.run(
        ["rsvg-convert", "-f", "pdf", "-o", str(pdf_path),
         "--width", f"{print_w_in}in", "--keep-aspect-ratio", str(layout_svg)],
        check=True,
    )


def projected_bbox(bbox_4326: tuple[float, float, float, float]):
    """Return the axis-aligned EPSG:5070 bounds of a lon/lat bbox + its clip box."""
    w, s, e, n = bbox_4326
    box = gpd.GeoSeries([shapely.geometry.box(w, s, e, n)], crs="EPSG:4326").to_crs(EPSG)
    return box.iloc[0].bounds, box.iloc[0]  # (minx,miny,maxx,maxy), polygon


def make_projector(pb, width: int):
    """Map EPSG:5070 (x, y) -> SVG px in a ``width``-wide, y-flipped canvas.

    Returns ``(P, W, H)`` where ``P(x, y)`` is the pixel mapper and ``W, H`` are
    the canvas size (H preserves the projected aspect, so nothing is squashed).
    """
    minx, miny, maxx, maxy = pb
    W = width
    H = int(round(width * (maxy - miny) / (maxx - minx)))
    sx = W / (maxx - minx)
    sy = H / (maxy - miny)

    def P(x: float, y: float) -> tuple[float, float]:
        return ((x - minx) * sx, (maxy - y) * sy)

    return P, W, H


def make_rect_projector(pb, rx, ry, rw, rh):
    """Map EPSG:5070 (x, y) into a target rect ``(rx, ry, rw, rh)``.

    Aspect-preserving and centred (letterboxed within the rect), y flipped so
    north is up. Use to place a map inside a sub-panel of a larger layout.
    """
    minx, miny, maxx, maxy = pb
    s = min(rw / (maxx - minx), rh / (maxy - miny))
    ox = rx + (rw - s * (maxx - minx)) / 2
    oy = ry + (rh - s * (maxy - miny)) / 2

    def P(x, y):
        return (ox + (x - minx) * s, oy + (maxy - y) * s)

    return P


def _ring_d(coords, P) -> str:
    pts = [P(x, y) for x, y, *_ in coords]
    return "M" + "L".join(f"{px:.1f} {py:.1f}" for px, py in pts)


def geom_to_path(geom, P, *, close: bool) -> str:
    """Flatten a shapely line/polygon geometry to one SVG path ``d`` string."""
    from shapely.geometry import (
        LineString, MultiLineString, MultiPolygon, Polygon,
    )

    d: list[str] = []
    if isinstance(geom, (Polygon,)):
        d.append(_ring_d(geom.exterior.coords, P) + "Z")
        for r in geom.interiors:
            d.append(_ring_d(r.coords, P) + "Z")
    elif isinstance(geom, MultiPolygon):
        for g in geom.geoms:
            d.append(geom_to_path(g, P, close=close))
    elif isinstance(geom, LineString):
        seg = _ring_d(geom.coords, P)
        d.append(seg + ("Z" if close else ""))
    elif isinstance(geom, MultiLineString):
        for g in geom.geoms:
            d.append(geom_to_path(g, P, close=close))
    return " ".join(d)


def copyright_text(x: float, y: float, *, fill: str, anchor: str = "end",
                   size: float = 9.0) -> str:
    """Return the standard right-aligned Runde Strategies copyright ``<text>``."""
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="{MONO_FONT}" '
            f'font-size="{size}" letter-spacing="0.8" text-anchor="{anchor}">'
            f'{COPYRIGHT}</text>')
