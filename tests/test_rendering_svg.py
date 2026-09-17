"""Tests for SVG document assembly (Item #8, Task Group 2).

Exercises ``render_svg`` structure/styling/determinism and the optional
stream-order width-scaling helper, using hand-built geometries + color and
watershed dicts (no GDAL, no browser, no real data).
"""

import io
import xml.etree.ElementTree as ET

from shapely.geometry import LineString, Point, Polygon

from src.rendering import (
    flow_widths,
    hypsometric_colors,
    render_svg,
    render_svg_stream,
    scaled_widths,
    stream_order_widths,
)

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


def test_flow_widths_log_scaled_between_base_and_top():
    # Discharge spans orders of magnitude; smallest flow -> base, largest -> top,
    # and the mapping is log-linear (a geometric mid-point lands at the midpoint).
    widths = flow_widths({0: 1.0, 1: 100.0, 2: 10000.0}, base_width=0.6, max_scale=6.0)
    assert widths[0] == 0.6
    assert widths[2] == 0.6 * 6.0
    assert abs(widths[1] - (0.6 + (0.6 * 6.0 - 0.6) * 0.5)) < 1e-9


def test_flow_widths_floors_nonpositive_and_handles_degenerate():
    # Zero/negative flow is floored (finite, at base); an all-equal network is uniform.
    w = flow_widths({0: 0.0, 1: -5.0, 2: 1.0}, base_width=0.6, max_scale=6.0, floor=1.0)
    assert w[0] == w[1] == w[2] == 0.6  # all floored to 1.0 -> single value -> uniform
    assert flow_widths({}, base_width=0.6) == {}


# --- Art-direction primitives (roadmap #23) ---------------------------------


def test_hypsometric_colors_anchors_sea_level_and_summit():
    # Sea level (0 m) -> deep blue; the max reach -> white; gamma=1 is linear.
    colors = hypsometric_colors({0: 0.0, 1: 500.0, 2: 1000.0}, gamma=1.0)
    assert colors[0] == "#1a489c"  # DEEP_BLUE (26, 72, 156)
    assert colors[2] == "#ffffff"  # WHITE at the anchor
    # Midpoint sits between the two anchors on every channel.
    r, g, b = int(colors[1][1:3], 16), int(colors[1][3:5], 16), int(colors[1][5:7], 16)
    assert 26 < r < 255 and 72 < g < 255 and 156 < b < 255


def test_hypsometric_colors_gamma_and_degenerate():
    # gamma < 1 brightens mid-slopes (higher toward white) vs. gamma = 1.
    lin = hypsometric_colors({0: 250.0}, gamma=1.0, anchor=1000.0)[0]
    bright = hypsometric_colors({0: 250.0}, gamma=0.5, anchor=1000.0)[0]
    assert int(bright[1:3], 16) > int(lin[1:3], 16)  # brighter red channel
    # All-sea-level (anchor <= 0) collapses to the low color, no divide-by-zero.
    assert hypsometric_colors({0: 0.0, 1: 0.0}) == {0: "#1a489c", 1: "#1a489c"}


def test_scaled_widths_maps_endpoints_and_gamma():
    w = scaled_widths({0: 1.0, 1: 2.0, 2: 3.0}, width_min=0.5, width_max=2.5, gamma=1.0)
    assert w[0] == 0.5  # min metric -> width_min
    assert w[2] == 2.5  # max metric -> width_max
    assert abs(w[1] - 1.5) < 1e-9  # linear midpoint
    # gamma > 1 pulls mid values down toward width_min.
    wg = scaled_widths({0: 1.0, 1: 2.0, 2: 3.0}, width_min=0.5, width_max=2.5, gamma=2.0)
    assert wg[1] < w[1]


def test_scaled_widths_log_and_degenerate():
    # log=True orders by magnitude; a geometric midpoint lands at the middle.
    wl = scaled_widths(
        {0: 1.0, 1: 100.0, 2: 10000.0}, width_min=0.6, width_max=3.6, log=True
    )
    assert wl[0] == 0.6 and wl[2] == 3.6
    assert abs(wl[1] - 2.1) < 1e-9
    # Single distinct value -> uniform width_min; empty -> empty.
    assert scaled_widths({0: 5.0, 1: 5.0}, width_min=0.6, width_max=3.6) == {0: 0.6, 1: 0.6}
    assert scaled_widths({}, width_min=0.6, width_max=3.6) == {}


# --- Hydro-structure symbology (Epoch 16, Item #67) -------------------------


def _square(x0, y0, size):
    return Polygon(
        [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]
    )


def test_hydro_structures_none_is_byte_identical():
    baseline = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS)
    with_none = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, hydro_structures=None)
    with_empty = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, hydro_structures=[])
    assert with_none == baseline
    assert with_empty == baseline
    assert 'id="hydro_structures"' not in baseline


def test_hydro_structures_geometry_dispatch_and_classes():
    structs = [
        ("gs1", Point(1, 1), "gaging_station"),
        ("dam1", LineString([(0, 5), (10, 5)]), "dam_weir"),
        ("spill1", _square(20, 0, 10), "spillway"),
    ]
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, hydro_structures=structs)
    assert '<g id="hydro_structures">' in svg
    # Distinct per-class child groups.
    assert 'id="hydro_gaging_station"' in svg
    assert 'id="hydro_dam_weir"' in svg
    assert 'id="hydro_spillway"' in svg
    # Point → glyph marker.
    gs_block = svg.split('id="hydro_gaging_station"')[1].split("</g>")[0]
    assert "<circle" in gs_block or "<path" in gs_block
    # Polygon → areal path (a closed subpath).
    sp_block = svg.split('id="hydro_spillway"')[1].split("</g>")[0]
    assert "Z" in sp_block


def test_hydro_structures_above_water_layers():
    structs = [("dam1", LineString([(0, 5), (10, 5)]), "dam_weir")]
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, hydro_structures=structs)
    # Structures sit above the river/watershed layers by default.
    assert svg.index('id="watershed_A"') < svg.index('id="hydro_structures"')


def test_hydro_structures_line_bar_is_open_path_distinct_from_polygon():
    # TG4.1 gap: geometry-type dispatch must emit a *distinct* element for a line
    # structure — a 2-point open bar across the channel ('M ... L ...' with NO
    # closing 'Z') — versus a polygon structure's closed 'Z' areal path. The
    # existing dispatch test only checks point/polygon, so it wouldn't catch a
    # regression that routed the line branch through the areal (closed) path.
    structs = [
        ("dam1", LineString([(0, 5), (10, 5)]), "dam_weir"),
        ("spill1", _square(20, 0, 10), "spillway"),
    ]
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, hydro_structures=structs)

    dam_block = svg.split('id="hydro_dam_weir"')[1].split("</g>")[0]
    bar = dam_block.split('id="hydro_dam_weir_dam1"')[1].split("/>")[0]
    # Line -> a single open segment: exactly one L, no polygon close.
    assert bar.count(" L ") == 1
    assert "Z" not in bar

    # The polygon in the same render still closes (distinct treatment).
    sp_block = svg.split('id="hydro_spillway"')[1].split("</g>")[0]
    assert "Z" in sp_block


# --- Channel dash patterns (Item #66, Task Group 3) --------------------------


def test_render_svg_no_dashes_default():
    """No channel_dashes arg -> no stroke-dasharray in output."""
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS)
    assert "stroke-dasharray" not in svg


def test_render_svg_with_channel_dashes():
    """Segment with dash entry gets stroke-dasharray on its <path>."""
    dashes = {0: "8,4"}
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, channel_dashes=dashes)
    root = _svg_root(svg)
    group_a = root.find(".//*[@id='watershed_A']")
    paths = [c for c in group_a if c.tag.endswith("path")]
    # Segment 0 should have the dasharray; segment 1 should not.
    dash_paths = [p for p in paths if p.get("stroke-dasharray") == "8,4"]
    assert len(dash_paths) == 1
    no_dash_paths = [p for p in paths if p.get("stroke-dasharray") is None]
    assert len(no_dash_paths) == 1


def test_render_svg_mixed_dashes():
    """Only engineered segments get dashes; natural segments do not."""
    # Segment 0 = canal (dashed), segment 1 = stream (no dash),
    # segment 2 = pipeline (dotted).
    dashes = {0: "8,4", 2: "2,4"}
    svg = render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, channel_dashes=dashes)
    root = _svg_root(svg)
    # Watershed A: segment 0 dashed, segment 1 not.
    group_a = root.find(".//*[@id='watershed_A']")
    paths_a = [c for c in group_a if c.tag.endswith("path")]
    dashed_a = [p for p in paths_a if p.get("stroke-dasharray") is not None]
    assert len(dashed_a) == 1
    assert dashed_a[0].get("stroke-dasharray") == "8,4"
    # Watershed B: segment 2 dashed.
    group_b = root.find(".//*[@id='watershed_B']")
    paths_b = [c for c in group_b if c.tag.endswith("path")]
    assert len(paths_b) == 1
    assert paths_b[0].get("stroke-dasharray") == "2,4"


def test_render_svg_stream_with_dashes():
    """Streaming path produces identical output to render_svg."""
    dashes = {0: "8,4", 2: "2,4"}
    svg_string = render_svg(
        GEOMS, SEGMENT_COLORS, WATERSHEDS, channel_dashes=dashes
    )
    buf = io.StringIO()
    render_svg_stream(
        buf, GEOMS, SEGMENT_COLORS, WATERSHEDS, channel_dashes=dashes
    )
    assert buf.getvalue() == svg_string
