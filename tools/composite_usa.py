#!/usr/bin/env python3
"""Composite N state-level SVG+PNG renders into a single USA image.

Usage:
    # After rendering each state to output/usa-states/<State>.{svg,png}:
    python tools/composite_usa.py --dir output/usa-states --output output/usa-composite.png --size 8192

Reads the viewBox from each SVG to compute the unified EPSG:5070 bounding box,
then places each rasterised PNG at the correct pixel offset on a shared black
canvas sized to ``--size`` pixels wide (height proportional).
"""

from __future__ import annotations

import argparse
import glob
import os
import xml.etree.ElementTree as ET

from PIL import Image


def parse_viewbox(svg_path: str) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, width, height) from the SVG viewBox."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb = root.get("viewBox")
    if vb is None:
        raise ValueError(f"No viewBox in {svg_path}")
    parts = vb.split()
    return float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])


def composite(
    input_dir: str,
    output_path: str,
    target_width: int = 8192,
) -> None:
    # Discover all SVG+PNG pairs
    svg_files = sorted(glob.glob(os.path.join(input_dir, "*.svg")))
    if not svg_files:
        raise FileNotFoundError(f"No SVGs found in {input_dir}")

    layers: list[tuple[str, str, float, float, float, float]] = []
    for svg_path in svg_files:
        stem = os.path.splitext(svg_path)[0]
        png_path = stem + ".png"
        if not os.path.exists(png_path):
            print(f"  SKIP {os.path.basename(svg_path)} (no matching PNG)")
            continue
        vx, vy, vw, vh = parse_viewbox(svg_path)
        layers.append((svg_path, png_path, vx, vy, vw, vh))
        print(f"  {os.path.basename(svg_path):30s}  viewBox=({vx:.0f}, {vy:.0f}, {vw:.0f}, {vh:.0f})")

    if not layers:
        raise FileNotFoundError(f"No SVG+PNG pairs found in {input_dir}")

    # Unified bounding box in projected coords
    uni_x = min(vx for _, _, vx, _, _, _ in layers)
    uni_y = min(vy for _, _, _, vy, _, _ in layers)
    uni_right = max(vx + vw for _, _, vx, _, vw, _ in layers)
    uni_bottom = max(vy + vh for _, _, _, vy, _, vh in layers)
    uni_w = uni_right - uni_x
    uni_h = uni_bottom - uni_y

    scale = target_width / uni_w
    canvas_h = int(uni_h * scale)

    print(f"\nUnified bbox: ({uni_x:.0f}, {uni_y:.0f}) — ({uni_right:.0f}, {uni_bottom:.0f})")
    print(f"Canvas: {target_width} x {canvas_h} px  ({len(layers)} layers)")

    canvas = Image.new("RGB", (target_width, canvas_h), (0, 0, 0))

    for svg_path, png_path, vx, vy, vw, vh in layers:
        name = os.path.basename(svg_path)
        img = Image.open(png_path)

        px = int((vx - uni_x) * scale)
        py = int((vy - uni_y) * scale)
        pw = int(vw * scale)
        ph = int(vh * scale)

        if pw < 1 or ph < 1:
            print(f"  SKIP {name} (too small at this canvas size)")
            continue

        resized = img.resize((pw, ph), Image.LANCZOS)

        # Composite with lighten blend (max of existing and new pixel) so
        # overlapping border regions merge rather than overwrite.
        for c in range(3):  # R, G, B
            canvas_crop = canvas.crop((px, py, px + pw, py + ph))
            # Use ImageChops for max blend
            from PIL import ImageChops
            blended = ImageChops.lighter(canvas_crop, resized)
            canvas.paste(blended, (px, py))
            break  # lighter works on full RGB, only need one pass

        print(f"  Placed {name:30s} at ({px:5d}, {py:5d}) size {pw}x{ph}")

    canvas.save(output_path, "PNG")
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nSaved {output_path} ({target_width}x{canvas_h}, {size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Composite state renders into USA map")
    parser.add_argument("--dir", required=True, help="Directory with <State>.svg + <State>.png pairs")
    parser.add_argument("--output", default="output/usa-composite.png", help="Output path")
    parser.add_argument("--size", type=int, default=8192, help="Target canvas width in pixels")
    args = parser.parse_args()
    composite(args.dir, args.output, args.size)


if __name__ == "__main__":
    main()
