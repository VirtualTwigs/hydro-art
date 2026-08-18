"""Terrain-backed print renderer (roadmap #30, Epoch 8 — non-offline).

Composites the canonical neon river art over a DEM-derived shaded-relief
background so mountains and valleys read behind the network, using the pure,
offline compositing seam in :mod:`src.compositing` (generalising the flat-black
canvas that ``tools/rasterize_layered.py`` composites over into a *supplied*
relief background).

Pipeline:

    clip flowlines (render_common) -> art SVG -> split into per-watershed layers
    -> resvg each to a transparent RGBA PNG
    DEM grid -> src.hillshade.hillshade -> src.compositing.shade_to_background
    solid black canvas <- relief <- river layers   (src.compositing)
    -> PNG

Like the other ``tools/`` scripts this eagerly imports the GIS stack, reads real
datasets, and shells out to ``resvg`` — so it only runs in a full (non-offline)
environment and is **not** part of the offline test suite. The pure compositing
math it drives *is* tested (``tests/test_compositing.py``).

DEM input, two ways:

* **Auto (roadmap #31):** with no ``--dem`` the tool acquires real 3DEP relief
  for the DEM region (``--region-dem``, default: ``--state``) —
  ``dem.acquire_dem_for_settings`` caches the COG tiles, then
  ``raster.normalize_dem`` reads/reprojects them through the concrete
  ``raster_io.RasterioRasterReader`` / ``RasterioReprojector`` seams and clips the
  relief to the *flowlines' EPSG:5070 extent* so it lines up with the art.
* **Supplied override:** ``--dem`` reads a bare-earth grid as a ``.npy`` array or
  a PIL-readable image, assumed to cover the rendered extent (resampled to the
  canvas). Handy for offline experiments / a DEM the tool can't auto-acquire.

Usage::

    # Auto-acquire real relief for the DEM region.
    python tools/render_terrain_print.py --state Oregon out.png --width 6000 \
        --min-order 3 --tint 210 180 140 --relief-opacity 0.9 --cache-dir ./cache

    # Or supply your own bare-earth grid.
    python tools/render_terrain_print.py --state Oregon --dem or_dem.npy out.png
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dataclasses

from src.compositing import (
    composite_over_background,
    shade_to_background,
    solid_canvas,
)
from src.hillshade import hillshade
from src.raster import GridTransform, RasterGrid, normalize_dem
from src.raster_io import RasterioRasterReader, RasterioReprojector

# ``tools`` is a package sibling; import the shared recipe + layer splitter.
from tools import render_common as rc
from tools.rasterize_layered import split_layers


def _load_dem_grid(path: str, *, cellsize: float, nodata: float | None) -> RasterGrid:
    """Load a bare-earth elevation grid (``.npy`` or image) into a ``RasterGrid``.

    The grid is treated as north-up with square ``cellsize``-metre cells at an
    arbitrary origin (only the cell size matters for shading). ``nodata``, when
    given, marks undefined cells so the relief stays transparent there.
    """
    p = Path(path)
    if p.suffix.lower() == ".npy":
        arr = np.load(p).astype(float)
    else:
        arr = np.asarray(Image.open(p).convert("F"), dtype=float)
    if arr.ndim != 2:
        raise SystemExit(f"DEM {path!r} must be a 2-D grid, got shape {arr.shape}.")
    transform = GridTransform(0.0, float(arr.shape[0]) * cellsize, cellsize, cellsize)
    return RasterGrid(arr, transform, rc.EPSG, nodata)


def _acquire_relief_grid(
    region: str,
    *,
    clip_bounds: tuple[float, float, float, float],
    cache_dir: str,
    tier: str | None,
    tile_budget: int | None,
    refresh: bool,
) -> RasterGrid:
    """Auto-acquire a bare-earth ``RasterGrid`` for ``region`` from cached 3DEP.

    Discovers/caches the region's COG tiles (``acquire_dem_for_settings``), then
    reads + reprojects them to EPSG:5070 through the concrete ``raster_io`` seams
    and clips to the flowlines' extent (``clip_bounds`` in EPSG:5070) via
    ``normalize_dem`` — the read path #31 supplies. Non-offline (rasterio + real
    tiles), so it lives only in this tool.
    """
    from src.cache import Cache
    from src.cli import resolve_settings
    from src.dem import acquire_dem_for_settings, region_bounds
    from src.download import Downloader, UrllibFetcher

    settings = resolve_settings(["--region", region])
    overrides: dict = {"enabled": True}
    if refresh:
        overrides["cache_policy"] = "refresh"
    if tier is not None:
        overrides["tier"] = tier
    if tile_budget is not None:
        overrides["tile_budget"] = tile_budget
    elevation = dataclasses.replace(settings.elevation, **overrides)
    settings = dataclasses.replace(settings, elevation=elevation)

    cache = Cache(cache_dir)
    downloader = Downloader(UrllibFetcher())
    assets = acquire_dem_for_settings(
        settings,
        boundary=region_bounds(region),  # EPSG:4326 for tile discovery
        cache=cache,
        downloader=downloader,
        log=lambda msg: print(f"  {msg}"),
    )
    dem = normalize_dem(
        assets=assets,
        boundary=clip_bounds,  # relief clipped to the flowlines' EPSG:5070 extent
        reader=RasterioRasterReader(),
        reprojector=RasterioReprojector(),
    )
    return dem.base


def _geom_bounds(geoms) -> tuple[float, float, float, float]:
    """Union bounds (min_x, min_y, max_x, max_y) of the clipped EPSG:5070 geoms."""
    boxes = [g.bounds for g in geoms]
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _resolve_boundary(args: argparse.Namespace):
    """Pick the clip boundary + HUC4 spec from the state/county/bbox flags."""
    if args.county:
        # Census STATEFP is resolved via src.counties in the pipeline; here the
        # user passes --state-fp so this tool stays independent of that lookup.
        boundary = rc.load_county(args.state_fp, args.county)
        spec = rc.STATE_HUC4.get(args.state, "all") if args.state else "all"
    elif args.state:
        boundary = rc.load_state(args.state)
        spec = rc.STATE_HUC4.get(args.state, "all")
    else:
        boundary = rc.bbox_boundary(rc.CLARK_BBOX_4326)
        spec = rc.STATE_HUC4["Washington"]
    return boundary, spec


def _river_layers(svg_path: Path, width: int, stroke_px: float, glow_px: float):
    """Split the art SVG and resvg each layer to a transparent RGBA array."""
    import subprocess

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        layers, _ = split_layers(svg_path, work, width, stroke_px, glow_px)
        arrays: list[np.ndarray] = []
        for i, layer in enumerate(layers, 1):
            png = work / f"layer_{i}.png"
            subprocess.run(
                ["resvg", "--width", str(width), str(layer), str(png)], check=True
            )
            arrays.append(np.asarray(Image.open(png).convert("RGBA"), dtype=np.uint8))
    return arrays


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", help="Output PNG path.")
    ap.add_argument(
        "--dem", default=None,
        help="Supplied DEM grid (.npy or image); omit to auto-acquire 3DEP relief.",
    )
    ap.add_argument("--dem-cellsize", type=float, default=10.0, help="DEM cell metres.")
    ap.add_argument("--dem-nodata", type=float, default=None, help="DEM nodata value.")
    ap.add_argument(
        "--region-dem", default=None,
        help="Region to auto-acquire DEM for (default: --state).",
    )
    ap.add_argument(
        "--cache-dir", default="cache", help="DEM tile cache root (may be a NAS mount)."
    )
    ap.add_argument("--dem-tier", default=None, help="Override elevation.tier.")
    ap.add_argument(
        "--dem-tile-budget", type=int, default=None,
        help="Override elevation.tile_budget (0 = unlimited).",
    )
    ap.add_argument(
        "--dem-refresh", action="store_true", help="Redownload already-cached tiles."
    )
    ap.add_argument("--state", default=None, help="Whole-state clip (Census polygon).")
    ap.add_argument("--county", default=None, help="County clip (needs --state-fp).")
    ap.add_argument("--state-fp", default=None, help="Census STATEFP for --county.")
    ap.add_argument("--width", type=int, default=6000, help="Render width in px.")
    ap.add_argument("--min-order", type=int, default=1, help="Drop Strahler < N.")
    ap.add_argument("--huc-digits", type=int, default=8, help="Sub-watershed HUC-N.")
    ap.add_argument("--stroke-px", type=float, default=1.4)
    ap.add_argument("--glow-px", type=float, default=2.5)
    ap.add_argument("--azimuth", type=float, default=315.0)
    ap.add_argument("--altitude", type=float, default=45.0)
    ap.add_argument("--z-factor", type=float, default=1.0)
    ap.add_argument(
        "--tint", type=int, nargs=3, default=None, metavar=("R", "G", "B"),
        help="Relief tint (default grayscale).",
    )
    ap.add_argument("--relief-opacity", type=float, default=1.0)
    ap.add_argument(
        "--base-color", type=int, nargs=3, default=(0, 0, 0), metavar=("R", "G", "B")
    )
    args = ap.parse_args(argv)

    # 1. River art -> transparent per-layer RGBA rasters.
    boundary, spec = _resolve_boundary(args)
    print(f"clipping flowlines ({spec}) ...")
    geoms, orders, flows, basins = rc.clip_flowlines(boundary, spec, args.min_order)
    if not geoms:
        raise SystemExit("no flowlines in the selected area.")
    codes, _names = rc.assign_subwatersheds(geoms, args.huc_digits)
    geometries, seg_colors, watersheds, _cc = rc.build_inputs(geoms, codes)
    widths, base_units, _upp, _q = rc.flow_scaled_widths(
        geometries, flows, args.width, args.stroke_px, args.stroke_px * 6
    )
    svg = rc.render_art_svg(geometries, seg_colors, watersheds, base_units, widths)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
        fh.write(svg)
        svg_path = Path(fh.name)
    layers = _river_layers(svg_path, args.width, args.stroke_px, args.glow_px)
    height, canvas_w = layers[0].shape[0], layers[0].shape[1]
    print(f"rasterized {len(layers)} river layer(s) at {canvas_w}x{height}")

    # 2. DEM -> hillshade -> relief background, resized to the render canvas.
    if args.dem:
        grid = _load_dem_grid(
            args.dem, cellsize=args.dem_cellsize, nodata=args.dem_nodata
        )
    else:
        region = args.region_dem or args.state
        if not region:
            raise SystemExit(
                "no DEM source: pass --dem or a --region-dem/--state to auto-acquire."
            )
        print(f"acquiring 3DEP relief for {region} ...")
        grid = _acquire_relief_grid(
            region,
            clip_bounds=_geom_bounds(geoms),
            cache_dir=args.cache_dir,
            tier=args.dem_tier,
            tile_budget=args.dem_tile_budget,
            refresh=args.dem_refresh,
        )
    relief_grid = hillshade(
        grid,
        azimuth_deg=args.azimuth,
        altitude_deg=args.altitude,
        z_factor=args.z_factor,
    )
    relief = shade_to_background(
        relief_grid,
        tint=tuple(args.tint) if args.tint else None,
        opacity=args.relief_opacity,
    )
    relief_img = Image.fromarray(relief, "RGBA").resize(
        (canvas_w, height), Image.BILINEAR
    )
    relief = np.asarray(relief_img, dtype=np.uint8)

    # 3. Composite: black base <- relief <- river layers.
    base = solid_canvas(height, canvas_w, tuple(args.base_color))
    result = composite_over_background(base, [relief, *layers])
    Image.fromarray(result, "RGBA").convert("RGB").save(args.output)
    print(f"wrote {args.output} ({canvas_w}x{height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
