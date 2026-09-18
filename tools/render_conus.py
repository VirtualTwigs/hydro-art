"""CONUS hero render — neon-basin river art for the 48 contiguous states.

Produces a continental-scale SVG + PNG showing every major river basin in
the contiguous United States with HUC2 coloring and flow-scaled widths.
The ``--min-order`` filter (default 3) is essential — unfiltered CONUS is
~5M flowlines and will not fit in memory.

    python tools/render_conus.py
    python tools/render_conus.py --min-order 4 --width 12000

NON-OFFLINE: requires all NHDPlus HR GDBs for the 48 contiguous states
extracted under ``datasets/``, plus the Census state shapefile. Never
imported by ``src/`` or ``tests/``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shapely  # noqa: E402

from src.config import CONUS_STATES  # noqa: E402
from tools.render_common import (  # noqa: E402
    STATE_HUC4,
    build_inputs,
    clip_flowlines,
    flow_scaled_widths,
    load_state,
    render_art_svg,
)

OUT_DIR = Path("output/gallery/conus-neon-hero")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _all_conus_huc4s() -> tuple[str, ...]:
    """Collect all HUC4 codes across the 48 CONUS states, deduplicated."""
    seen: set[str] = set()
    ordered: list[str] = []
    for state in CONUS_STATES:
        for h in STATE_HUC4.get(state, ()):
            if h not in seen:
                seen.add(h)
                ordered.append(h)
    return tuple(ordered)


def main() -> int:
    ap = argparse.ArgumentParser(description="CONUS hero image render")
    ap.add_argument(
        "--min-order", type=int, default=3,
        help="Drop streams below this Strahler order (default 3).",
    )
    ap.add_argument(
        "--width", type=int, default=8000,
        help="Reference pixel width for stroke scaling (default 8000).",
    )
    ap.add_argument(
        "--min-px", type=float, default=0.3,
        help="Stroke width (px) for the lowest-flow headwater.",
    )
    ap.add_argument(
        "--max-px", type=float, default=6.0,
        help="Stroke width (px) for the highest-flow mainstem.",
    )
    args = ap.parse_args()

    huc4s = _all_conus_huc4s()
    print(f"CONUS: {len(CONUS_STATES)} states, {len(huc4s)} HUC4 basins")

    # Union all 48 state boundaries into one CONUS boundary.
    print("loading CONUS boundary (48 state polygons) ...")
    state_geoms = [load_state(s) for s in CONUS_STATES]
    boundary = shapely.unary_union(state_geoms)
    print(f"boundary: {boundary.geom_type}")

    print(f"clipping flowlines (min_order={args.min_order}) from {len(huc4s)} HUC4s ...")
    geoms, orders, flows, basins = clip_flowlines(boundary, huc4s, args.min_order)
    print(f"total kept: {len(geoms):,}")
    if not geoms:
        raise SystemExit("No flowlines fell inside the CONUS boundary.")

    # Color by HUC2 (first 2 chars of the HUC4 basin code) for continent-scale
    # readability — ~18 macro-basin color families.
    huc2_codes = [b[:2] for b in basins]
    geometries, segment_colors, watersheds, _code_color = build_inputs(geoms, huc2_codes)
    widths, base_units, units_per_px, qmax = flow_scaled_widths(
        geometries, flows, args.width, args.min_px, args.max_px,
    )
    print(
        f"HUC2 groups: {sorted(watersheds)}; orders 1..{max(orders)}; "
        f"flow 0..{qmax:.0f} cfs -> {args.min_px}..{args.max_px}px"
    )

    svg = render_art_svg(geometries, segment_colors, watersheds, base_units, widths)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = OUT_DIR / "conus-neon-hero.svg"
    svg_path.write_text(svg)
    print(f"wrote {svg_path} ({len(svg):,} bytes, {len(geometries):,} paths)")
    print(f"  sha256: {_sha256(svg_path)}")

    # PNG via rsvg-convert (optional — degrades gracefully).
    png_path = OUT_DIR / "conus-neon-hero.png"
    try:
        import subprocess
        subprocess.run(
            ["rsvg-convert", "-w", "8000", str(svg_path), "-o", str(png_path)],
            check=True,
        )
        print(f"wrote {png_path} ({png_path.stat().st_size:,} bytes)")
        print(f"  sha256: {_sha256(png_path)}")
    except FileNotFoundError:
        print("rsvg-convert not found — skipping PNG export.")
    except subprocess.CalledProcessError as exc:
        print(f"rsvg-convert failed: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
