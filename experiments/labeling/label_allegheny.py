"""Apply Iteration B (Paper & Muted) labeling to Allegheny County, PA."""
from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "output" / "pennsylvania-allegheny.svg"
OUT = Path(__file__).resolve().parent / "allegheny_paper_muted.svg"

VB_W, VB_H = 54960.064, 55140.666

# Allegheny County watersheds (HUC4-level from the render)
# code → (name, neon_color, muted_color, centroid, label_placement, angle)
WATERSHEDS = {
    "0501": {
        "name": "Upper Ohio River",
        "neon": "#00ffff",
        "muted": "#2a5463",       # steel blue, darker
        "centroid": (35650, 12510),
        "label": (36000, 10000),
        "angle": -5,
        "paths": 974,
    },
    "0502": {
        "name": "Allegheny River",
        "neon": "#0a5cff",
        "muted": "#3d4f28",       # olive, darker
        "centroid": (43129, 38622),
        "label": (44000, 36000),
        "angle": 30,
        "paths": 879,
    },
    "0503": {
        "name": "Monongahela River",
        "neon": "#4b0082",
        "muted": "#4f3428",       # warm umber, darker
        "centroid": (16149, 27059),
        "label": (14000, 24000),
        "angle": -15,
        "paths": 1041,
    },
}

# Named streams for additional labeling (manually placed based on geometry)
NAMED_STREAMS = [
    {"name": "Chartiers Creek",    "x": 8000,  "y": 38000, "angle": 55,  "size": 400, "color": "#6b4a3d", "opacity": 0.55},
    {"name": "Turtle Creek",       "x": 38000, "y": 34000, "angle": -20, "size": 380, "color": "#5c6b3d", "opacity": 0.50},
    {"name": "Pine Creek",         "x": 28000, "y": 8000,  "angle": 10,  "size": 380, "color": "#3d6b7a", "opacity": 0.50},
    {"name": "Deer Creek",         "x": 48000, "y": 22000, "angle": -35, "size": 350, "color": "#3d6b7a", "opacity": 0.45},
    {"name": "Buffalo Creek",      "x": 50000, "y": 42000, "angle": 40,  "size": 350, "color": "#5c6b3d", "opacity": 0.45},
    {"name": "Youghiogheny River", "x": 3000,  "y": 42000, "angle": 70,  "size": 420, "color": "#6b4a3d", "opacity": 0.55},
    {"name": "Peters Creek",       "x": 22000, "y": 43000, "angle": 50,  "size": 350, "color": "#6b4a3d", "opacity": 0.45},
]

# Sepia ink for labels
INK = "#2a1f0e"
BG = "#f4efe4"


def main() -> None:
    svg = SOURCE.read_text()
    print(f"Read {len(svg):,} bytes")

    # 1. Replace background
    svg = re.sub(
        r'(<rect x="0" y="0"[^/]*fill=")#[0-9a-fA-F]+(")',
        rf'\g<1>{BG}\2',
        svg,
        count=1,
    )

    # 2. Recolor river strokes to muted tones
    for code, ws in WATERSHEDS.items():
        wid = f"watershed_{code}"
        svg = svg.replace(
            f'id="{wid}" stroke="{ws["neon"]}"',
            f'id="{wid}" stroke="{ws["muted"]}"',
        )

    # 3. Recolor waterbody outlines to muted blue-grey, thicker
    svg = svg.replace('stroke="#2ec4ff"', 'stroke="#5a7a88"')
    svg = re.sub(r'(id="waterbodies"[^>]*stroke-width=")[\d.]+(\")', r'\g<1>18\2', svg)

    # 3b. Thicken all river strokes — base stroke-width is ~4.7 across 55k units, way too thin
    svg = re.sub(
        r'(stroke-linejoin="round" stroke-width=")[\d.]+(\")',
        r'\g<1>28\2',
        svg,
        count=1,
    )

    # 4. Replace glow with subtle paper shadow
    new_filter = (
        '<filter id="hydro-glow" x="-10%" y="-10%" width="120%" height="120%">'
        '<feGaussianBlur stdDeviation="8" result="blur"/>'
        '<feFlood flood-color="#2a1f0e" flood-opacity="0.12" result="shadow-color"/>'
        '<feComposite in="shadow-color" in2="blur" operator="in" result="shadow"/>'
        '<feOffset in="shadow" dx="6" dy="8" result="offset-shadow"/>'
        '<feMerge><feMergeNode in="offset-shadow"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )
    svg = re.sub(
        r'<filter id="hydro-glow"[^>]*>.*?</filter>',
        new_filter,
        svg,
        flags=re.DOTALL,
    )

    # 5. Add label defs
    label_defs = """
    <style>
      .river-label { font-family: Georgia, 'Times New Roman', serif; font-style: italic; }
      .basin-label { font-family: 'Garamond', 'Times New Roman', serif;
                     letter-spacing: 700px; text-transform: uppercase; }
      .stream-label { font-family: Georgia, 'Times New Roman', serif; font-style: italic; }
      .credit { font-family: 'Garamond', 'Times New Roman', serif; }
    </style>
    <filter id="paper-halo" x="-5%" y="-15%" width="110%" height="130%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="45" result="fat"/>
      <feFlood flood-color="#f4efe4" flood-opacity="0.88" result="paper"/>
      <feComposite in="paper" in2="fat" operator="in" result="halo"/>
      <feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""
    svg = svg.replace("</defs>", label_defs + "\n  </defs>")

    # 6. Build label layer
    labels = '\n  <!-- Iteration B: Paper & Muted Labels -->\n'

    # Basin watermark
    labels += (
        f'  <text x="{VB_W*0.50:.0f}" y="{VB_H*0.52:.0f}" class="basin-label" '
        f'font-size="2600" fill="{INK}" fill-opacity="0.05" text-anchor="middle">'
        f'ALLEGHENY COUNTY</text>\n'
    )

    # River labels with halo
    labels += '  <g id="river-labels" filter="url(#paper-halo)">\n'

    for code, ws in WATERSHEDS.items():
        x, y = ws["label"]
        labels += (
            f'    <text x="{x}" y="{y}" class="river-label" '
            f'font-size="750" fill="{INK}" fill-opacity="0.78" '
            f'text-anchor="middle" '
            f'transform="rotate({ws["angle"]}, {x}, {y})">{ws["name"]}</text>\n'
        )

    # Named streams — smaller
    for s in NAMED_STREAMS:
        labels += (
            f'    <text x="{s["x"]}" y="{s["y"]}" class="stream-label" '
            f'font-size="{s["size"]}" fill="{INK}" fill-opacity="{s["opacity"]}" '
            f'text-anchor="middle" '
            f'transform="rotate({s["angle"]}, {s["x"]}, {s["y"]})">{s["name"]}</text>\n'
        )

    labels += '  </g>\n'

    # Title block — bottom left, sepia
    labels += f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.94:.0f}"
          class="credit" font-weight="normal"
          font-size="1500" fill="{INK}" fill-opacity="0.82">Allegheny County, Pennsylvania</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.965:.0f}"
          class="credit" font-weight="normal" font-style="italic"
          font-size="480" fill="#5c4a32" fill-opacity="0.50" letter-spacing="25">NHDPlus HR Hydrography  ·  United States Geological Survey</text>
  </g>
"""

    svg = svg.replace("</svg>", labels + "\n</svg>")

    # 7. Set hi-res dimensions
    svg = re.sub(r'width="[^"]*"', 'width="4500px"', svg, count=1)
    svg = re.sub(r'height="[^"]*"', 'height="4514px"', svg, count=1)

    OUT.write_text(svg)
    print(f"Wrote {len(svg):,} bytes → {OUT.name}")


if __name__ == "__main__":
    main()
