"""Generate 5 high-res labeling concepts from a real Clark County SVG render."""
from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "output" / "clark_county.svg"
OUT = Path(__file__).resolve().parent

# Real Clark County, WA watershed data
# HUC10 code → (display name, color from SVG, centroid_x, centroid_y, max_stroke_width, path_count)
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

# Widest paths per watershed — for textPath labeling
# (watershed_id, path_d, stroke_width, midpoint_x, midpoint_y, angle_deg)
TRUNK_PATHS = {
    "1708000206": {"mid": (7683, 16912),  "angle": -5},
    "1708000205": {"mid": (12516, 17120), "angle": 10},
    "1708000301": {"mid": (7015, 18806),  "angle": -15},
    "1708000106": {"mid": (27505, 54386), "angle": 25},
    "1708000303": {"mid": (19290, 4918),  "angle": -30},
    "1708000204": {"mid": (43797, 14684), "angle": 45},
    "1708000107": {"mid": (27864, 57470), "angle": -10},
    "1708000108": {"mid": (27688, 55254), "angle": 5},
    "1708000302": {"mid": (6724, 17213),  "angle": -8},
    "1708000304": {"mid": (5168, 864),    "angle": -20},
    "1708000309": {"mid": (6748, 1681),   "angle": -12},
}

VB_W, VB_H = 51567.709, 64254.251


def read_source() -> str:
    return SOURCE.read_text()


def inject_before_close(svg: str, injection: str) -> str:
    """Insert content just before </svg>."""
    return svg.replace("</svg>", injection + "\n</svg>")


def add_defs(svg: str, extra_defs: str) -> str:
    """Add to the <defs> block."""
    return svg.replace("</defs>", extra_defs + "\n  </defs>")


def set_dimensions(svg: str, w: int, h: int) -> str:
    """Override the SVG width/height for high-res output."""
    svg = re.sub(r'width="[^"]*"', f'width="{w}px"', svg, count=1)
    svg = re.sub(r'height="[^"]*"', f'height="{h}px"', svg, count=1)
    return svg


# ---------------------------------------------------------------------------
# Concept 1: Cartographic Classic
# ---------------------------------------------------------------------------
def concept1_cartographic(svg: str) -> str:
    defs = """
    <style>
      .c1-river { font-family: Georgia, 'Times New Roman', serif; font-style: italic; }
      .c1-basin { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 600;
                  letter-spacing: 800px; text-transform: uppercase; }
    </style>
    <filter id="c1-halo" x="-3%" y="-10%" width="106%" height="120%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="60" result="fat"/>
      <feFlood flood-color="#000000" flood-opacity="0.85" result="black"/>
      <feComposite in="black" in2="fat" operator="in" result="halo"/>
      <feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""
    svg = add_defs(svg, defs)

    labels = '\n  <!-- Concept 1: Cartographic Classic Labels -->\n  <g id="labels-cartographic" filter="url(#c1-halo)">\n'

    # Major rivers get larger text
    major = ["1708000206", "1708000205", "1708000106", "1708000303", "1708000301"]
    for huc, (name, color, cx, cy, sw, count) in WATERSHEDS.items():
        info = TRUNK_PATHS[huc]
        mx, my = info["mid"]
        angle = info["angle"]

        if huc in major:
            size, opacity = 700, 0.88
        elif count > 100:
            size, opacity = 480, 0.72
        else:
            size, opacity = 350, 0.55

        labels += (
            f'    <text x="{mx}" y="{my}" class="c1-river" '
            f'font-size="{size}" fill="{color}" fill-opacity="{opacity}" '
            f'text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name}</text>\n'
        )

    # Basin-level background labels
    labels += (
        f'    <text x="{VB_W*0.5:.0f}" y="{VB_H*0.30:.0f}" class="c1-basin" '
        f'font-size="1800" fill="#e8f4ff" fill-opacity="0.06" text-anchor="middle">'
        f'CLARK COUNTY</text>\n'
    )

    labels += "  </g>\n"

    # Title block bottom-left
    title = f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.96:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="bold"
          font-size="1200" fill="#e8f4ff" fill-opacity="0.9">Clark County, Washington</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.98:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="300"
          font-size="550" fill="#6b8da6" fill-opacity="0.7">NHDPlus HR Hydrography  ·  Cartographic Classic</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    return set_dimensions(svg, 4000, 4984)


# ---------------------------------------------------------------------------
# Concept 2: Text-on-Path Flow
# ---------------------------------------------------------------------------
def concept2_textpath(svg: str) -> str:
    # We need to extract the widest path 'd' attribute for each watershed
    # and add it as a named path in defs for textPath to reference
    defs = """
    <style>
      .c2-flow { font-family: Georgia, serif; font-style: italic; letter-spacing: 200px; }
    </style>
    <filter id="c2-halo" x="-3%" y="-15%" width="106%" height="130%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="80" result="fat"/>
      <feFlood flood-color="#0a0a12" flood-opacity="0.88" result="black"/>
      <feComposite in="black" in2="fat" operator="in" result="halo"/>
      <feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""

    # Extract widest path d for each watershed
    path_defs = ""
    for huc in WATERSHEDS:
        wid = f"watershed_{huc}"
        # Find the group
        pat = rf'<g id="{wid}"[^>]*>(.*?)</g>'
        m = re.search(pat, svg, re.DOTALL)
        if not m:
            continue
        body = m.group(1)
        paths = re.findall(r'<path d="([^"]+)"[^/]*stroke-width="([\d.]+)"', body)
        if not paths:
            continue
        # Get widest
        widest_d, widest_sw = max(paths, key=lambda p: float(p[1]))
        path_defs += f'    <path id="c2-path-{huc}" d="{widest_d}"/>\n'

    defs = path_defs + defs
    svg = add_defs(svg, defs)

    labels = '\n  <!-- Concept 2: Text-on-Path Flow Labels -->\n  <g id="labels-textpath" filter="url(#c2-halo)">\n'

    major = ["1708000206", "1708000205", "1708000106", "1708000303", "1708000301"]
    for huc, (name, color, cx, cy, sw, count) in WATERSHEDS.items():
        if count < 50:
            size, opacity, offset = 350, 0.5, "10%"
        elif huc in major:
            size, opacity, offset = 650, 0.85, "25%"
        else:
            size, opacity, offset = 450, 0.7, "20%"

        labels += (
            f'    <text class="c2-flow" font-size="{size}" '
            f'fill="{color}" fill-opacity="{opacity}">'
            f'<textPath href="#c2-path-{huc}" startOffset="{offset}">'
            f'{name}</textPath></text>\n'
        )

    labels += "  </g>\n"

    title = f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.96:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="bold"
          font-size="1200" fill="#e8f4ff" fill-opacity="0.9">Clark County, Washington</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.98:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="300"
          font-size="550" fill="#6b8da6" fill-opacity="0.7">NHDPlus HR Hydrography  ·  Text-on-Path Flow</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    return set_dimensions(svg, 4000, 4984)


# ---------------------------------------------------------------------------
# Concept 3: Neon Tier System
# ---------------------------------------------------------------------------
def concept3_neon_tier(svg: str) -> str:
    defs = """
    <style>
      .c3-t1 { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: bold;
               letter-spacing: 400px; text-transform: uppercase; }
      .c3-t2 { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 600;
               letter-spacing: 250px; text-transform: uppercase; }
      .c3-t3 { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 300;
               letter-spacing: 150px; text-transform: uppercase; }
      .c3-marquee { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: bold;
                    letter-spacing: 1500px; text-transform: uppercase; }
    </style>
    <filter id="c3-glow-strong" x="-15%" y="-15%" width="130%" height="130%">
      <feGaussianBlur stdDeviation="120" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="c3-glow-med" x="-15%" y="-15%" width="130%" height="130%">
      <feGaussianBlur stdDeviation="60" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="c3-glow-soft" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur stdDeviation="30" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>"""
    svg = add_defs(svg, defs)

    labels = '\n  <!-- Concept 3: Neon Tier Labels -->\n'

    # Marquee title — huge, faint, glowing
    labels += (
        f'  <text x="{VB_W*0.5:.0f}" y="{VB_H*0.18:.0f}" class="c3-marquee" '
        f'font-size="3500" fill="#e8f4ff" fill-opacity="0.07" text-anchor="middle" '
        f'filter="url(#c3-glow-strong)">CLARK COUNTY</text>\n'
    )

    # Tier 1: Major rivers
    tier1 = ["1708000206", "1708000205", "1708000106"]
    # Tier 2: Medium
    tier2 = ["1708000303", "1708000301", "1708000204", "1708000108"]
    # Tier 3: Small
    tier3 = ["1708000107", "1708000302", "1708000304", "1708000309"]

    labels += '  <g id="c3-tier1" filter="url(#c3-glow-strong)">\n'
    for huc in tier1:
        name, color, cx, cy, sw, count = WATERSHEDS[huc]
        mx, my = TRUNK_PATHS[huc]["mid"]
        angle = TRUNK_PATHS[huc]["angle"]
        labels += (
            f'    <text x="{mx}" y="{my}" class="c3-t1" font-size="900" '
            f'fill="{color}" fill-opacity="0.82" text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name.upper()}</text>\n'
        )
    labels += '  </g>\n'

    labels += '  <g id="c3-tier2" filter="url(#c3-glow-med)">\n'
    for huc in tier2:
        name, color, cx, cy, sw, count = WATERSHEDS[huc]
        mx, my = TRUNK_PATHS[huc]["mid"]
        angle = TRUNK_PATHS[huc]["angle"]
        labels += (
            f'    <text x="{mx}" y="{my}" class="c3-t2" font-size="600" '
            f'fill="{color}" fill-opacity="0.65" text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name.upper()}</text>\n'
        )
    labels += '  </g>\n'

    labels += '  <g id="c3-tier3" filter="url(#c3-glow-soft)">\n'
    for huc in tier3:
        name, color, cx, cy, sw, count = WATERSHEDS[huc]
        mx, my = TRUNK_PATHS[huc]["mid"]
        angle = TRUNK_PATHS[huc]["angle"]
        labels += (
            f'    <text x="{mx}" y="{my}" class="c3-t3" font-size="400" '
            f'fill="{color}" fill-opacity="0.45" text-anchor="middle" '
            f'transform="rotate({angle}, {mx}, {my})">{name.upper()}</text>\n'
        )
    labels += '  </g>\n'

    title = f"""
  <g id="title-block">
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.96:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="bold"
          font-size="1200" fill="#e8f4ff" fill-opacity="0.9">Clark County, Washington</text>
    <text x="{VB_W*0.03:.0f}" y="{VB_H*0.98:.0f}"
          font-family="'Helvetica Neue', Helvetica, sans-serif" font-weight="300"
          font-size="550" fill="#6b8da6" fill-opacity="0.7">NHDPlus HR Hydrography  ·  Neon Tier System</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    return set_dimensions(svg, 4000, 4984)


# ---------------------------------------------------------------------------
# Concept 4: Leader-Line Callouts
# ---------------------------------------------------------------------------
def concept4_callouts(svg: str) -> str:
    defs = """
    <style>
      .c4-name { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 600;
                 letter-spacing: 80px; }
      .c4-detail { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 300;
                   letter-spacing: 40px; }
      .c4-title { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 300;
                  letter-spacing: 500px; text-transform: uppercase; }
      .c4-title-bold { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: bold; }
    </style>"""
    svg = add_defs(svg, defs)

    labels = '\n  <!-- Concept 4: Leader-Line Callouts -->\n  <g id="labels-callouts">\n'

    # Place callouts in alternating left/right positions to avoid overlap
    # Sort by Y position for vertical layout
    sorted_ws = sorted(WATERSHEDS.items(), key=lambda x: x[1][3])  # sort by cy

    margin_left = -3000
    margin_right = VB_W + 1000
    callout_y = 3000
    callout_spacing = 5200

    for i, (huc, (name, color, cx, cy, sw, count)) in enumerate(sorted_ws):
        mx, my = TRUNK_PATHS[huc]["mid"]
        # Alternate sides
        if i % 2 == 0:
            label_x = margin_right
            anchor = "start"
            elbow_x = VB_W - 2000
        else:
            label_x = margin_left + 3500
            anchor = "end"
            elbow_x = 3500

        label_y = callout_y + i * callout_spacing

        # Circle on river
        labels += f'    <circle cx="{mx}" cy="{my}" r="200" fill="none" stroke="{color}" stroke-width="40" stroke-opacity="0.6"/>\n'

        # Leader line: river → elbow → label
        labels += (
            f'    <line x1="{mx}" y1="{my}" x2="{elbow_x}" y2="{label_y}" '
            f'stroke="{color}" stroke-width="20" stroke-opacity="0.25"/>\n'
        )
        labels += (
            f'    <line x1="{elbow_x}" y1="{label_y}" x2="{label_x}" y2="{label_y}" '
            f'stroke="{color}" stroke-width="20" stroke-opacity="0.25"/>\n'
        )

        # Name
        labels += (
            f'    <text x="{label_x}" y="{label_y - 200}" class="c4-name" '
            f'font-size="500" fill="{color}" fill-opacity="0.9" text-anchor="{anchor}">'
            f'{name}</text>\n'
        )
        # Detail line
        detail = f"HUC10 {huc}  ·  {count:,} segments"
        labels += (
            f'    <text x="{label_x}" y="{label_y + 350}" class="c4-detail" '
            f'font-size="350" fill="{color}" fill-opacity="0.45" text-anchor="{anchor}">'
            f'{detail}</text>\n'
        )

    labels += "  </g>\n"

    # Title block — bottom right, gallery style
    title = f"""
  <g id="title-block">
    <line x1="{VB_W*0.60:.0f}" y1="{VB_H*0.945:.0f}" x2="{VB_W*0.97:.0f}" y2="{VB_H*0.945:.0f}"
          stroke="#e8f4ff" stroke-opacity="0.12" stroke-width="15"/>
    <text x="{VB_W*0.97:.0f}" y="{VB_H*0.96:.0f}" class="c4-title"
          font-size="650" fill="#e8f4ff" fill-opacity="0.35" text-anchor="end">Clark County</text>
    <text x="{VB_W*0.97:.0f}" y="{VB_H*0.975:.0f}" class="c4-title-bold"
          font-size="900" fill="#e8f4ff" fill-opacity="0.18" text-anchor="end">Washington State</text>
    <text x="{VB_W*0.97:.0f}" y="{VB_H*0.99:.0f}" class="c4-detail"
          font-size="400" fill="#6b8da6" fill-opacity="0.5" text-anchor="end">NHDPlus HR  ·  Leader-Line Callouts</text>
  </g>
"""
    svg = inject_before_close(svg, labels + title)
    # Wider to accommodate margins
    return set_dimensions(svg, 5000, 4984)


# ---------------------------------------------------------------------------
# Concept 5: Minimal Margin Index
# ---------------------------------------------------------------------------
def concept5_margin(svg: str) -> str:
    defs = """
    <style>
      .c5-idx-name { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 300;
                     letter-spacing: 100px; }
      .c5-title { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 100;
                  letter-spacing: 800px; text-transform: uppercase; }
      .c5-sub { font-family: 'Helvetica Neue', Helvetica, sans-serif; font-weight: 300;
                letter-spacing: 300px; text-transform: uppercase; }
    </style>"""
    svg = add_defs(svg, defs)

    # Expand viewBox downward to create margin space
    margin_h = 8000
    new_h = VB_H + margin_h
    svg = re.sub(
        r'viewBox="0 0 [\d.]+ [\d.]+"',
        f'viewBox="0 -3000 {VB_W:.3f} {new_h:.3f}"',
        svg,
    )

    labels = '\n  <!-- Concept 5: Minimal Margin Index -->\n'

    # Gallery title above art
    labels += (
        f'  <text x="{VB_W*0.5:.0f}" y="-800" class="c5-title" '
        f'font-size="2200" fill="#e8f4ff" fill-opacity="0.10" text-anchor="middle">'
        f'Clark County</text>\n'
    )
    labels += (
        f'  <text x="{VB_W*0.5:.0f}" y="400" class="c5-sub" '
        f'font-size="700" fill="#e8f4ff" fill-opacity="0.06" text-anchor="middle">'
        f'Pacific Northwest Hydrography</text>\n'
    )

    # Divider line
    div_y = VB_H + 1500
    labels += (
        f'  <line x1="{VB_W*0.05:.0f}" y1="{div_y}" '
        f'x2="{VB_W*0.95:.0f}" y2="{div_y}" '
        f'stroke="#e8f4ff" stroke-opacity="0.08" stroke-width="15"/>\n'
    )

    # Index grid — sorted by path count (importance)
    sorted_ws = sorted(WATERSHEDS.items(), key=lambda x: -x[1][5])
    cols = 4
    idx_x_start = VB_W * 0.06
    idx_y_start = div_y + 1800
    col_w = VB_W * 0.88 / cols
    row_h = 1600

    labels += '  <g id="c5-index">\n'
    for i, (huc, (name, color, cx, cy, sw, count)) in enumerate(sorted_ws):
        col = i % cols
        row = i // cols
        x = idx_x_start + col * col_w
        y = idx_y_start + row * row_h

        # Color dot
        r = 200 if count > 500 else 140 if count > 100 else 100
        opacity = 0.8 if count > 500 else 0.6 if count > 100 else 0.4
        labels += f'    <circle cx="{x}" cy="{y}" r="{r}" fill="{color}" fill-opacity="{opacity}"/>\n'
        # Name
        labels += (
            f'    <text x="{x + r + 200}" y="{y + 100}" class="c5-idx-name" '
            f'font-size="420" fill="{color}" fill-opacity="{opacity}">{name}</text>\n'
        )
        # Segment count, dimmer
        labels += (
            f'    <text x="{x + r + 200}" y="{y + 550}" class="c5-idx-name" '
            f'font-size="300" fill="{color}" fill-opacity="{opacity * 0.5:.2f}">'
            f'{count:,} segments</text>\n'
        )
    labels += '  </g>\n'

    # Bottom credit
    labels += (
        f'  <text x="{VB_W*0.5:.0f}" y="{new_h - 3500}" '
        f'font-family="\'Helvetica Neue\', Helvetica, sans-serif" font-weight="300" '
        f'font-size="400" fill="#6b8da6" fill-opacity="0.4" text-anchor="middle">'
        f'NHDPlus HR Hydrography  ·  Minimal Margin Index</text>\n'
    )

    svg = inject_before_close(svg, labels)
    return set_dimensions(svg, 4000, int(4000 * new_h / VB_W))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    base = read_source()
    print(f"Read {len(base):,} bytes from {SOURCE.name}")

    renderers = [
        ("concept1_cartographic_hires.svg", concept1_cartographic),
        ("concept2_textpath_hires.svg",     concept2_textpath),
        ("concept3_neon_tier_hires.svg",    concept3_neon_tier),
        ("concept4_callouts_hires.svg",     concept4_callouts),
        ("concept5_margin_hires.svg",       concept5_margin),
    ]

    for filename, fn in renderers:
        result = fn(base)
        out_path = OUT / filename
        out_path.write_text(result)
        print(f"  → {filename} ({len(result):,} bytes)")

    print("Done. Open in browser to compare.")


if __name__ == "__main__":
    main()
