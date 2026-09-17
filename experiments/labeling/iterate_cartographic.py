"""3 iterations on Concept 1 (Cartographic Classic) labeling.

Iteration A — Refined Neon: tighter halo, better font sizing hierarchy, offset
              labels away from trunk paths to reduce overlap with geometry.
Iteration B — Paper & Muted: warm cream background, muted earth-tone river
              colors, sepia-ink labels. Gallery / fine-art print feel.
Iteration C — Hybrid Dark: dark background kept, but labels use a single
              warm off-white with subtle weight/size hierarchy instead of
              per-watershed colors. Cleaner, less "rainbow text."
"""
from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "output" / "clark_county.svg"
OUT = Path(__file__).resolve().parent

WATERSHEDS = {
    "1708000206": ("Lewis River",        "#ff7a00", 7747,  16898, 35.1, 5532),
    "1708000205": ("N. Fork Lewis",      "#ff00ff", 12516, 17103, 31.2, 3697),
    "1708000301": ("Kalama River",        "#ffd700", 7137,  18858, 28.3, 1554),
    "1708000106": ("Salmon Creek",        "#0a5cff", 27505, 54368, 31.0, 1314),
    "1708000303": ("Washougal River",     "#00ffab", 19290, 4952,  22.8, 668),
    "1708000204": ("East Fork Lewis",     "#8f00ff", 43913, 14599, 34.1, 447),
    "1708000107": ("Burnt Bridge Cr.",    "#4b0082", 27831, 57445, 32.9, 277),
    "1708000108": ("Columbia Slough",     "#9d00ff", 27747, 55291, 42.5, 206),
    "1708000302": ("Columbia River",      "#aaff00", 6761,  17084, 43.0, 108),
    "1708000304": ("Wind River",          "#00e0d1", 5156,  869,   24.6, 89),
    "1708000309": ("Columbia Gorge",      "#00ff5f", 6744,  1627,  43.0, 62),
}

# Muted earth-tone palette for iteration B
MUTED_COLORS = {
    "1708000206": "#8b6914",   # burnt sienna → dark gold
    "1708000205": "#7a5230",   # warm brown
    "1708000301": "#5c7a3d",   # olive green
    "1708000106": "#3d6b7a",   # steel blue
    "1708000303": "#4a7a6b",   # sage
    "1708000204": "#6b4a7a",   # dusty plum
    "1708000107": "#3d4a5c",   # slate
    "1708000108": "#5c3d4a",   # mauve
    "1708000302": "#6b6b3d",   # khaki
    "1708000304": "#3d5c5c",   # dark teal
    "1708000309": "#4a5c3d",   # moss
}

# Label placement — offset from trunk midpoint to avoid sitting on the river
# (dx, dy offsets in SVG units, angle)
LABEL_PLACEMENT = {
    "1708000206": {"mid": (8800, 14500),  "angle": -8},
    "1708000205": {"mid": (14000, 14800), "angle": 12},
    "1708000301": {"mid": (5500,  21500), "angle": -18},
    "1708000106": {"mid": (29000, 52000), "angle": 20},
    "1708000303": {"mid": (21000, 3200),  "angle": -25},
    "1708000204": {"mid": (42000, 12500), "angle": 40},
    "1708000107": {"mid": (29500, 55800), "angle": -8},
    "1708000108": {"mid": (29500, 53500), "angle": 8},
    "1708000302": {"mid": (5200,  15500), "angle": -10},
    "1708000304": {"mid": (3500,  2200),  "angle": -22},
    "1708000309": {"mid": (8200,  3200),  "angle": -10},
}

VB_W, VB_H = 51567.709, 64254.251


def read_source() -> str:
    return SOURCE.read_text()


def inject_before_close(svg: str, injection: str) -> str:
    return svg.replace("</svg>", injection + "\n</svg>")


def add_defs(svg: str, extra_defs: str) -> str:
    return svg.replace("</defs>", extra_defs + "\n  </defs>")


def set_dimensions(svg: str, w: int, h: int) -> str:
    svg = re.sub(r'width="[^"]*"', f'width="{w}px"', svg, count=1)
    svg = re.sub(r'height="[^"]*"', f'height="{h}px"', svg, count=1)
    return svg


def replace_background(svg: str, color: str) -> str:
    """Change the background rect fill color."""
    return re.sub(
        r'(<rect x="0" y="0"[^/]*fill=")#[0-9a-fA-F]+(")',
        rf'\g<1>{color}\2',
        svg,
        count=1,
    )


def recolor_strokes(svg: str, color_map: dict[str, str]) -> str:
    """Replace stroke colors in watershed groups."""
    for huc, new_color in color_map.items():
        wid = f"watershed_{huc}"
        old_color = WATERSHEDS[huc][1]
        # Replace the stroke in the group opener
        svg = svg.replace(
            f'id="{wid}" stroke="{old_color}"',
            f'id="{wid}" stroke="{new_color}"',
        )
    return svg


def replace_glow_filter(svg: str, new_filter: str) -> str:
    """Replace the hydro-glow filter definition."""
    return re.sub(
        r'<filter id="hydro-glow"[^>]*>.*?</filter>',
        new_filter,
        svg,
        flags=re.DOTALL,
    )


# ---------------------------------------------------------------------------
# Iteration A: Refined Neon
# ---------------------------------------------------------------------------
def iter_a_refined_neon(svg: str) -> str:
    defs = """
    <style>
      .ia-river { font-family: Georgia, 'Times New Roman', serif; font-style: italic; }
      .ia-basin { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 600;
                  letter-spacing: 600px; text-transform: uppercase; }
    </style>
    <filter id="ia-halo" x="-5%" y="-15%" width="110%" height="130%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="45" result="fat"/>
      <feFlood flood-color="#000000" flood-opacity="0.92" result="black"/>
      <feComposite in="black" in2="fat" operator="in" result="halo"/>
      <feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""
    svg = add_defs(svg, defs)

    major = {"1708000206", "1708000205", "1708000106", "1708000303", "1708000301"}
    medium = {"1708000204", "1708000108", "1708000302"}

    labels = '\n  <!-- Iter A: Refined Neon -->\n  <g id="labels-refined" filter="url(#ia-halo)">\n'

    for huc, (name, color, cx, cy, sw, count) in WATERSHEDS.items():
        pl = LABEL_PLACEMENT[huc]
        mx, my = pl["mid"]
        angle = pl["angle"]

        if huc in major:
            size, opacity, weight = 800, 0.90, "normal"
        elif huc in medium:
            size, opacity, weight = 520, 0.72, "normal"
        else:
            size, opacity, weight = 380, 0.55, "normal"

        labels += (
            f'    <text x="{mx}" y="{my}" class="ia-river" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" fill-opacity="{opacity}" '
            f'text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name}</text>\n'
        )

    # Basin watermark
    labels += (
        f'    <text x="{VB_W*0.5:.0f}" y="{VB_H*0.35:.0f}" class="ia-basin" '
        f'font-size="2200" fill="#e8f4ff" fill-opacity="0.04" text-anchor="middle">'
        f'CLARK COUNTY</text>\n'
    )
    labels += "  </g>\n"

    # Title
    title = f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.955:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="bold"
          font-size="1400" fill="#e8f4ff" fill-opacity="0.9">Clark County, Washington</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.978:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="300"
          font-size="500" fill="#6b8da6" fill-opacity="0.6" letter-spacing="40">NHDPlus HR Hydrography  ·  USGS National Hydrography Dataset</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    return set_dimensions(svg, 4000, 4984)


# ---------------------------------------------------------------------------
# Iteration B: Paper & Muted
# ---------------------------------------------------------------------------
def iter_b_paper_muted(svg: str) -> str:
    # Swap background to warm cream
    svg = replace_background(svg, "#f4efe4")

    # Recolor all river strokes to muted tones
    svg = recolor_strokes(svg, MUTED_COLORS)

    # Replace glow with a subtle shadow (no neon glow on paper)
    new_filter = (
        '<filter id="hydro-glow" x="-10%" y="-10%" width="120%" height="120%">'
        '<feGaussianBlur stdDeviation="1.2" result="blur"/>'
        '<feFlood flood-color="#2a1f0e" flood-opacity="0.15" result="shadow-color"/>'
        '<feComposite in="shadow-color" in2="blur" operator="in" result="shadow"/>'
        '<feOffset in="shadow" dx="8" dy="12" result="offset-shadow"/>'
        '<feMerge><feMergeNode in="offset-shadow"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )
    svg = replace_glow_filter(svg, new_filter)

    defs = """
    <style>
      .ib-river { font-family: Georgia, 'Times New Roman', serif; font-style: italic; }
      .ib-basin { font-family: 'Garamond', 'Times New Roman', serif; font-weight: normal;
                  letter-spacing: 900px; text-transform: uppercase; }
      .ib-credit { font-family: 'Garamond', 'Times New Roman', serif; }
    </style>
    <filter id="ib-halo" x="-5%" y="-15%" width="110%" height="130%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="50" result="fat"/>
      <feFlood flood-color="#f4efe4" flood-opacity="0.88" result="paper"/>
      <feComposite in="paper" in2="fat" operator="in" result="halo"/>
      <feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""
    svg = add_defs(svg, defs)

    major = {"1708000206", "1708000205", "1708000106", "1708000303", "1708000301"}
    medium = {"1708000204", "1708000108", "1708000302"}

    # Label color: dark sepia ink
    ink = "#2a1f0e"

    labels = '\n  <!-- Iter B: Paper & Muted -->\n  <g id="labels-paper" filter="url(#ib-halo)">\n'

    for huc, (name, _, cx, cy, sw, count) in WATERSHEDS.items():
        pl = LABEL_PLACEMENT[huc]
        mx, my = pl["mid"]
        angle = pl["angle"]

        if huc in major:
            size, opacity = 750, 0.80
        elif huc in medium:
            size, opacity = 500, 0.60
        else:
            size, opacity = 360, 0.45

        labels += (
            f'    <text x="{mx}" y="{my}" class="ib-river" '
            f'font-size="{size}" fill="{ink}" fill-opacity="{opacity}" '
            f'text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name}</text>\n'
        )

    # Basin watermark — dark ink on paper
    labels += (
        f'    <text x="{VB_W*0.5:.0f}" y="{VB_H*0.35:.0f}" class="ib-basin" '
        f'font-size="2400" fill="{ink}" fill-opacity="0.06" text-anchor="middle">'
        f'CLARK COUNTY</text>\n'
    )
    labels += "  </g>\n"

    # Title — sepia tones
    title = f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.955:.0f}"
          class="ib-credit" font-weight="normal"
          font-size="1400" fill="{ink}" fill-opacity="0.85">Clark County, Washington</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.978:.0f}"
          class="ib-credit" font-weight="normal" font-style="italic"
          font-size="480" fill="#5c4a32" fill-opacity="0.55" letter-spacing="30">NHDPlus HR Hydrography  ·  United States Geological Survey</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    return set_dimensions(svg, 4000, 4984)


# ---------------------------------------------------------------------------
# Iteration C: Hybrid Dark (monochrome labels)
# ---------------------------------------------------------------------------
def iter_c_hybrid(svg: str) -> str:
    defs = """
    <style>
      .ic-river { font-family: Georgia, 'Times New Roman', serif; font-style: italic; }
      .ic-basin { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 200;
                  letter-spacing: 700px; text-transform: uppercase; }
    </style>
    <filter id="ic-halo" x="-5%" y="-15%" width="110%" height="130%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="50" result="fat"/>
      <feFlood flood-color="#080810" flood-opacity="0.90" result="black"/>
      <feComposite in="black" in2="fat" operator="in" result="halo"/>
      <feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""
    svg = add_defs(svg, defs)

    # All labels in warm off-white — hierarchy via size/weight only
    label_color = "#ddd5c8"

    major = {"1708000206", "1708000205", "1708000106", "1708000303", "1708000301"}
    medium = {"1708000204", "1708000108", "1708000302"}

    labels = '\n  <!-- Iter C: Hybrid Dark -->\n  <g id="labels-hybrid" filter="url(#ic-halo)">\n'

    for huc, (name, _, cx, cy, sw, count) in WATERSHEDS.items():
        pl = LABEL_PLACEMENT[huc]
        mx, my = pl["mid"]
        angle = pl["angle"]

        if huc in major:
            size, opacity, weight = 850, 0.85, "normal"
        elif huc in medium:
            size, opacity, weight = 550, 0.60, "normal"
        else:
            size, opacity, weight = 400, 0.42, "300"

        labels += (
            f'    <text x="{mx}" y="{my}" class="ic-river" '
            f'font-size="{size}" font-weight="{weight}" '
            f'fill="{label_color}" fill-opacity="{opacity}" '
            f'text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name}</text>\n'
        )

    # Basin watermark
    labels += (
        f'    <text x="{VB_W*0.5:.0f}" y="{VB_H*0.35:.0f}" class="ic-basin" '
        f'font-size="2400" fill="{label_color}" fill-opacity="0.04" text-anchor="middle">'
        f'CLARK COUNTY</text>\n'
    )
    labels += "  </g>\n"

    # Title — warm neutral
    title = f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.955:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="bold"
          font-size="1400" fill="{label_color}" fill-opacity="0.88">Clark County, Washington</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.978:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="300"
          font-size="500" fill="#9a9080" fill-opacity="0.55" letter-spacing="40">NHDPlus HR Hydrography  ·  Monochrome Labels on Neon</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    return set_dimensions(svg, 4000, 4984)


# ---------------------------------------------------------------------------
def main() -> None:
    base = read_source()
    print(f"Read {len(base):,} bytes from {SOURCE.name}")

    renderers = [
        ("iter_a_refined_neon.svg",   iter_a_refined_neon),
        ("iter_b_paper_muted.svg",    iter_b_paper_muted),
        ("iter_c_hybrid_dark.svg",    iter_c_hybrid),
    ]

    for filename, fn in renderers:
        result = fn(base)
        out_path = OUT / filename
        out_path.write_text(result)
        print(f"  → {filename} ({len(result):,} bytes)")

    print("Done.")


if __name__ == "__main__":
    main()
