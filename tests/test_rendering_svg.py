"""Tests for SVG document assembly (Item #8, Task Group 2).

Exercises ``render_svg`` structure/styling/determinism and the optional
stream-order width-scaling helper, using hand-built geometries + color and
watershed dicts (no GDAL, no browser, no real data).
"""

import re
import xml.etree.ElementTree as ET

from shapely.geometry import LineString

from src.rendering import render_svg, stream_order_widths

# Two watersheds: 'A' (segments 0,1) and 'B' (segment 2).
GEOMS = {
    0: LineString([(0.0, 0.0), (10.0, 0.0)]),
    1: LineString([(10.0, 0.0), (10.0, 20.0)]),
    2: LineString([(10.0, 20.0), (30.0, 20.0)]),
}
SEGMENT_COLORS = {0: "#00ffff", 1: "#00ffff", 2: "#ff00ff"}
WATERSHEDS = {"A": {0, 1}, "B": {2}}


def _svg_root(text):
    # Well-formed XML that parses is a baseline correctness check.
    return ET.fromstring(text)


def test_root_viewbox_and_default_styling():
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, background="#000000", line_width=0.35)
    root = _svg_root(svg)
    assert root.tag.endswith("svg")
    # bounds: x 0..30, y 0..20 -> W=30 H=20
    assert root.get("viewBox") == "0 0 30 20"
    assert root.get("fill") == "none"
    assert root.get("stroke-linecap") == "round"
    assert root.get("stroke-linejoin") == "round"
    assert root.get("stroke-width") == "0.35"


def test_defs_and_background_rect_present():
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, background="#010203")
    assert "<defs/>" in svg or "<defs />" in svg
    root = _svg_root(svg)
    bg = root.find(".//*[@id='background']")
    assert bg is not None
    rect = bg.find("*")
    assert rect.tag.endswith("rect")
    assert rect.get("fill") == "#010203"
    assert rect.get("width") == "30" and rect.get("height") == "20"


def test_watershed_groups_sorted_with_color_and_paths():
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS)
    # Group ids appear in sorted watershed-code order.
    assert svg.index('id="watershed_A"') < svg.index('id="watershed_B"')
    root = _svg_root(svg)
    group_a = root.find(".//*[@id='watershed_A']")
    group_b = root.find(".//*[@id='watershed_B']")
    assert group_a.get("stroke") == "#00ffff"
    assert group_b.get("stroke") == "#ff00ff"
    # Watershed A holds its two segments as <path> elements.
    paths_a = [c for c in group_a if c.tag.endswith("path")]
    assert len(paths_a) == 2
    assert all(p.get("d") for p in paths_a)


def test_unassigned_segments_grouped_when_present_else_absent():
    # Segment 2 belongs to no watershed group here.
    watersheds = {"A": {0, 1}}
    svg = render_svg(GEOMS, SEGMENT_COLORS, watersheds)
    root = _svg_root(svg)
    unassigned = root.find(".//*[@id='rivers_unassigned']")
    assert unassigned is not None
    paths = [c for c in unassigned if c.tag.endswith("path")]
    assert len(paths) == 1

    # When every segment is grouped, no unassigned group is emitted.
    svg_full = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS)
    assert "rivers_unassigned" not in svg_full


def test_determinism_and_empty_input():
    a = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS)
    b = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS)
    assert a == b  # identical inputs -> byte-identical output

    empty = render_svg({}, {}, {})
    root = _svg_root(empty)  # must be valid, no crash
    assert root.get("viewBox") == "0 0 0 0"


def test_stroke_widths_override_and_stream_order_scaling():
    widths = stream_order_widths({0: 1, 1: 1, 2: 2}, max_order=2, base_width=0.35, max_scale=3.0)
    # order 1 -> base; order 2 (== max) -> base * max_scale
    assert widths[0] == 0.35
    assert widths[2] == 0.35 * 3.0
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, stroke_widths=widths)
    root = _svg_root(svg)
    seg2 = root.find(".//*[@id='watershed_B']/*")
    assert seg2.get("stroke-width") == "1.05"  # 0.35 * 3
