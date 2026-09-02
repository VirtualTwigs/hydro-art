"""Render a standalone labeling key (legend) for the 2-D hydro-art SVG.

The 2-D pipeline emits pure art with no legend, so this tool produces a separate
key SVG describing every encoding the render uses:

* **Watershed colors** — the named palette (default ``neon``) and the fact that
  colors are a deterministic *max-contrast graph coloring* at the chosen HUC
  level (adjacent basins differ; a color is not a fixed basin identity).
* **Flow -> width** — the stroke-width ramp for a named ``--width-preset``
  (``state``/``basin``/``watershed``), sampled from the *same* ``scaled_widths``
  resolver the pipeline uses, so the wedge shows the real gamma/log character.
* **Point glyphs** — spring / waterfall / rapids markers drawn with the real
  glyph geometry (``_glyph_element``) and colors (``DEFAULT_POINT_STYLES``).
* **Areal fills** — wetland / perennial-ice / playa fills, plus the waterbody
  outline stroke, drawn with the real fill modes (``DEFAULT_AREAL_STYLES``).

Because it draws no real GIS data, this tool imports only ``src`` constants (no
GDAL / shapely), keeping the key authoritative: it reads the exact tables the
renderer draws from, so the two can never drift. It is standalone and does not
touch the deterministic pipeline, whose default output stays byte-identical.

Usage::

    python tools/render_legend.py --palette neon --width-preset state \
        --huc-level HUC8 --output output/washington_legend.svg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import SUPPORTED_WIDTH_PRESETS, WIDTH_PRESETS
from src.coloring import PALETTES
from src.rendering import (
    DEFAULT_AREAL_STYLES,
    DEFAULT_POINT_STYLES,
    POINT_GLYPHS,
    _areal_pattern_defs,
    _glyph_element,
    format_number,
    scaled_widths,
)

#: Human-readable names for the neon palette, in ``PALETTES["neon"]`` order
#: (mirrors the docstring in ``src/coloring.py``). Falls back to the hex string
#: for any palette without a curated name list.
PALETTE_NAMES: dict[str, tuple[str, ...]] = {
    "neon": (
        "cyan", "electric blue", "indigo", "purple", "violet", "magenta",
        "orange", "gold", "lime", "teal", "turquoise", "green",
    ),
}

#: Default waterbody outline color (mirrors ``render_svg``'s ``waterbody_color``).
WATERBODY_COLOR = "#2ec4ff"

BG = "#000000"
INK = "#e8f4ff"
DIM = "#9fb4c6"
FONT = 'font-family="Helvetica, Arial, sans-serif"'
PREC = 3

#: Human-readable one-liners for the point/areal families.
POINT_LABELS = {"spring": "Spring / seep", "waterfall": "Waterfall", "rapids": "Rapids"}
AREAL_LABELS = {
    "wetland": "Wetland",
    "perennial_ice": "Perennial ice / snowfield",
    "playa": "Playa (dry lakebed)",
}


def _text(x: float, y: float, s: str, *, size: float = 13, fill: str = INK,
          weight: str = "normal", anchor: str = "start") -> str:
    return (
        f'  <text x="{format_number(x, 1)}" y="{format_number(y, 1)}" '
        f'{FONT} font-size="{format_number(size, 1)}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{s}</text>'
    )


def _swatch(x: float, y: float, w: float, h: float, fill: str,
            *, stroke: str | None = None, dash: str | None = None,
            opacity: float = 1.0) -> str:
    attrs = [
        f'x="{format_number(x, 1)}"', f'y="{format_number(y, 1)}"',
        f'width="{format_number(w, 1)}"', f'height="{format_number(h, 1)}"',
        f'fill="{fill}"', f'fill-opacity="{format_number(opacity, 2)}"',
    ]
    if stroke:
        attrs.append(f'stroke="{stroke}"')
        attrs.append('stroke-width="1.5"')
    if dash:
        attrs.append(f'stroke-dasharray="{dash}"')
    return f'  <rect {" ".join(attrs)}/>'


def _section_title(x: float, y: float, s: str) -> str:
    return _text(x, y, s, size=16, weight="bold")


def build_legend_svg(
    *, palette: str = "neon", width_preset: str = "state", huc_level: str = "HUC8",
) -> str:
    """Return the full legend SVG document as a string."""
    colors = PALETTES.get(palette.lower())
    if colors is None:
        valid = ", ".join(sorted(PALETTES))
        raise SystemExit(f"Unknown palette {palette!r}; valid: {valid}")
    preset = WIDTH_PRESETS[width_preset]
    names = PALETTE_NAMES.get(palette.lower(), tuple(colors))

    W = 620
    margin = 28
    x = margin
    y = 46
    body: list[str] = []

    # --- Header -----------------------------------------------------------
    body.append(_text(x, y, "Map key", size=24, weight="bold"))
    y += 22
    body.append(_text(
        x, y,
        f"palette: {palette}   \u00b7   width preset: {width_preset}   "
        f"\u00b7   watershed level: {huc_level}",
        size=12, fill=DIM,
    ))
    y += 34

    # --- Watershed colors -------------------------------------------------
    body.append(_section_title(x, y, "Watershed colors"))
    y += 20
    body.append(_text(
        x, y,
        f"Deterministic max-contrast graph coloring at {huc_level}: adjacent "
        "sub-basins always get",
        size=11.5, fill=DIM,
    ))
    y += 15
    body.append(_text(
        x, y,
        "different colors, so a color distinguishes neighbors \u2014 it is not a "
        "fixed basin identity.",
        size=11.5, fill=DIM,
    ))
    y += 18
    sw = 26
    gap = 8
    per_row = 6
    for i, hexc in enumerate(colors):
        col = i % per_row
        row = i // per_row
        cx = x + col * (sw + gap + 66)
        cy = y + row * (sw + 20)
        body.append(_swatch(cx, cy, sw, sw, hexc))
        label = names[i] if i < len(names) else hexc
        body.append(_text(cx + sw + 6, cy + sw - 8, label, size=10.5, fill=INK))
    rows = (len(colors) + per_row - 1) // per_row
    y += rows * (sw + 20) + 18

    # --- Flow -> width ----------------------------------------------------
    log = bool(preset["width_log"])
    gamma = float(preset["width_gamma"])
    wmin = float(preset["width_min"])
    wmax = float(preset["width_max"])
    body.append(_section_title(x, y, "Flow \u2192 stroke width"))
    y += 20
    ramp = "logarithmic" if log else f"power-law (Q^{format_number(gamma, 2)})"
    body.append(_text(
        x, y,
        f"{ramp} ramp, width {format_number(wmin, 2)}\u2013"
        f"{format_number(wmax, 2)} px. Thin = headwaters, thick = trunk river.",
        size=11.5, fill=DIM,
    ))
    y += 22
    # Sample the *real* resolver: a synthetic order/discharge metric spanning a
    # wide range, mapped through the preset's own params.
    n = 9
    metric = {i: float(10 ** (i * (4.0 / (n - 1)))) for i in range(n)}
    widths = scaled_widths(metric, width_min=wmin, width_max=wmax, gamma=gamma, log=log)
    ramp_w = W - 2 * margin
    x0 = x
    seg = ramp_w / n
    for i in range(n):
        stroke_w = widths[i]
        cx = x0 + i * seg + seg / 2
        y_mid = y + 16
        body.append(
            f'  <line x1="{format_number(cx, 1)}" y1="{format_number(y_mid - 12, 1)}" '
            f'x2="{format_number(cx, 1)}" y2="{format_number(y_mid + 12, 1)}" '
            f'stroke="{colors[0]}" stroke-width="{format_number(stroke_w, PREC)}" '
            'stroke-linecap="round"/>'
        )
    y += 38
    body.append(_text(x, y, "low flow", size=10.5, fill=DIM))
    body.append(_text(x + ramp_w, y, "high flow", size=10.5, fill=DIM, anchor="end"))
    y += 26

    # --- Point glyphs -----------------------------------------------------
    body.append(_section_title(x, y, "Point features"))
    y += 24
    gsize = 8.0
    col_w = (W - 2 * margin) / 3
    for i, family in enumerate(("spring", "waterfall", "rapids")):
        style = DEFAULT_POINT_STYLES[family]
        color = style["color"]
        shape = POINT_GLYPHS[family]
        cx = x + i * col_w + 14
        cy = y
        glyph = _glyph_element(shape, f"legend_{family}", cx, cy, gsize, PREC)
        if shape == "dot":
            body.append(f'  <g fill="{color}">{glyph}</g>')
        else:
            body.append(
                f'  <g fill="none" stroke="{color}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round">{glyph}</g>'
            )
        body.append(_text(cx + 18, cy + 5, POINT_LABELS[family], size=11.5, fill=INK))
    y += 34

    # --- Areal fills + waterbodies ---------------------------------------
    body.append(_section_title(x, y, "Areal features &amp; water"))
    y += 20
    defs: list[str] = _areal_pattern_defs(
        [("l", None, fam) for fam in DEFAULT_AREAL_STYLES], None
    )
    row_h = 30
    sw2 = 40
    for family in ("wetland", "perennial_ice", "playa"):
        style = DEFAULT_AREAL_STYLES[family]
        color = style["color"]
        fill_mode = style.get("fill", "none")
        cx = x
        cy = y
        if fill_mode == "hatch":
            body.append(_swatch(cx, cy, sw2, sw2 * 0.5, f"url(#areal_{family}_hatch)",
                                stroke=color))
        elif fill_mode == "solid":
            body.append(_swatch(cx, cy, sw2, sw2 * 0.5, color,
                                opacity=float(style.get("opacity", 1.0)), stroke=color))
        else:  # none -> dashed outline (playa)
            body.append(_swatch(cx, cy, sw2, sw2 * 0.5, "none", stroke=color,
                                dash=style.get("dash", "4,3")))
        body.append(_text(cx + sw2 + 12, cy + sw2 * 0.5 - 4, AREAL_LABELS[family],
                          size=11.5, fill=INK))
        y += row_h
    # Waterbody outline
    body.append(_swatch(x, y, sw2, sw2 * 0.5, "none", stroke=WATERBODY_COLOR))
    body.append(_text(x + sw2 + 12, y + sw2 * 0.5 - 4, "Lake / reservoir outline",
                      size=11.5, fill=INK))
    y += row_h + margin

    H = int(y)
    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'  <rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>',
    ]
    if defs:
        head.append("  <defs>")
        head.extend(defs)
        head.append("  </defs>")
    return "\n".join(head + body + ["</svg>", ""])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render a standalone hydro-art map key.")
    p.add_argument("--palette", default="neon", help="Named color palette (e.g. neon).")
    p.add_argument("--width-preset", default="state", choices=SUPPORTED_WIDTH_PRESETS,
                   help="Flow-width preset whose ramp the key illustrates.")
    p.add_argument("--huc-level", default="HUC8",
                   help="Watershed grouping level (label only).")
    p.add_argument("--output", default="output/legend.svg",
                   help="Output SVG path.")
    args = p.parse_args(argv)

    svg = build_legend_svg(
        palette=args.palette, width_preset=args.width_preset, huc_level=args.huc_level,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
