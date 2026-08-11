"""Rasterize a huge layered hydro SVG that exceeds rasterizer node caps.

librsvg and resvg both refuse SVGs with more than ~1,048,576 nodes. The pipeline
emits one ``<g id="watershed_...">`` layer per HUC4 basin, each under that cap, so
we split the document into one standalone SVG per layer (transparent background),
rasterize each with ``resvg``, then alpha-composite them over a black canvas.

Usage:
    python tools/rasterize_layered.py <input.svg> <output.png> [--width N]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

_GROUP_OPEN = re.compile(r'<g id="watershed_\d+"')


def _rescale_svg_open(svg_open: str, width_px: int, stroke_px: float) -> str:
    """Set a pixel-appropriate ``stroke-width`` on the root ``<svg>`` tag.

    The pipeline authors strokes in projected-meter user units (e.g. 0.35 m),
    which become sub-pixel — invisible — once the huge viewBox is scaled down to
    a normal raster. Recompute a stroke width that yields ~``stroke_px`` pixels.
    """
    vb = re.search(r'viewBox="([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)"', svg_open)
    if not vb:
        return svg_open
    vb_w = float(vb.group(3))
    units_per_px = vb_w / width_px
    stroke_units = stroke_px * units_per_px
    return re.sub(
        r'stroke-width="[\d.]+"', f'stroke-width="{stroke_units:.4f}"', svg_open
    )


def split_layers(
    svg_path: Path, work: Path, width_px: int, stroke_px: float, glow_px: float
) -> tuple[list[Path], str]:
    """Write one standalone SVG per watershed layer; return (paths, svg_open_tag)."""
    svg_open = ""
    defs_lines: list[str] = []
    in_defs = False
    layer_files: list[Path] = []
    current = None
    idx = 0
    units_per_px = 1.0

    with svg_path.open() as f:
        for line in f:
            stripped = line.strip()
            if not svg_open and stripped.startswith("<svg"):
                svg_open = _rescale_svg_open(stripped, width_px, stroke_px)
                vb = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.\-]+)', svg_open)
                units_per_px = float(vb.group(1)) / width_px if vb else 1.0
                continue
            if "<defs>" in line:
                in_defs = True
            if in_defs:
                # Scale the glow blur (also authored in user units) to ~glow_px.
                blur_units = glow_px * units_per_px
                line = re.sub(
                    r'stdDeviation="[\d.]+"',
                    f'stdDeviation="{blur_units:.4f}"',
                    line,
                )
                defs_lines.append(line)
            if "</defs>" in line:
                in_defs = False
                continue
            if _GROUP_OPEN.search(line):
                if current is not None:
                    current.write("</svg>\n")
                    current.close()
                idx += 1
                out = work / f"layer_{idx}.svg"
                layer_files.append(out)
                current = out.open("w")
                current.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                current.write(svg_open + "\n")
                current.writelines(defs_lines)
                current.write(line)
            elif current is not None:
                # Skip the shared background rect group entirely (kept transparent).
                current.write(line)

    if current is not None:
        current.close()
    return layer_files, svg_open


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("png")
    ap.add_argument("--width", type=int, default=8000)
    ap.add_argument("--stroke-px", type=float, default=1.4)
    ap.add_argument("--glow-px", type=float, default=2.5)
    args = ap.parse_args()

    svg_path = Path(args.svg)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        layers, _ = split_layers(
            svg_path, work, args.width, args.stroke_px, args.glow_px
        )
        print(f"split into {len(layers)} layer SVG(s)")

        base: Image.Image | None = None
        for i, layer in enumerate(layers, 1):
            png = work / f"layer_{i}.png"
            print(f"rasterizing layer {i}/{len(layers)} ...", flush=True)
            subprocess.run(
                ["resvg", "--width", str(args.width), str(layer), str(png)],
                check=True,
            )
            img = Image.open(png).convert("RGBA")
            if base is None:
                base = Image.new("RGBA", img.size, (0, 0, 0, 255))
            base.alpha_composite(img)

        assert base is not None, "no layers found"
        base.convert("RGB").save(args.png)
        print(f"wrote {args.png} ({base.size[0]}x{base.size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
