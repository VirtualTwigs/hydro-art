"""Unit tests for the SVG geometry core (Item #8, Task Group 1).

Pure geometry -> SVG helpers, tested with hand-built shapely lines (no GDAL,
no real data). Covers bounding box, deterministic number formatting, the
cartesian Y-flip transform, path ``d`` string building, and streaming writer.
"""

import io

from shapely.geometry import LineString, MultiLineString

from src.rendering import (
    bounds,
    format_number,
    path_d,
    render_svg,
    render_svg_stream,
    transform_coords,
)


def test_bounds_over_lines_and_empty():
    lines = [
        LineString([(0.0, 0.0), (10.0, 5.0)]),
        LineString([(-4.0, 2.0), (3.0, 20.0)]),
    ]
    assert bounds(lines) == (-4.0, 0.0, 10.0, 20.0)
    # No geometries -> a well-defined zero box (never crashes).
    assert bounds([]) == (0.0, 0.0, 0.0, 0.0)


def test_format_number_is_deterministic():
    assert format_number(1.23456, 3) == "1.235"
    assert format_number(2.0, 3) == "2"          # trailing zeros + dot stripped
    assert format_number(0.5000, 3) == "0.5"
    # -0 must normalize to 0 so identical inputs never diverge on sign.
    assert format_number(-0.0001, 3) == "0"
    assert format_number(-3.0, 2) == "-3"


def test_transform_flips_y_and_translates_to_origin():
    # min_x = -4, max_y = 20 (from a bounding box); y-axis flips (north up).
    coords = [(-4.0, 20.0), (6.0, 0.0)]
    out = transform_coords(coords, min_x=-4.0, max_y=20.0, precision=3)
    # (-4 - -4, 20 - 20) = (0, 0); (6 - -4, 20 - 0) = (10, 20)
    assert out == [("0", "0"), ("10", "20")]


def test_path_d_single_line():
    geom = LineString([(0.0, 10.0), (5.0, 10.0), (5.0, 0.0)])
    # min_x=0, max_y=10 -> flip: (0,0) (5,0) (5,10)
    assert path_d(geom, min_x=0.0, max_y=10.0, precision=3) == "M 0,0 L 5,0 L 5,10"


def test_path_d_multiline_has_multiple_subpaths():
    geom = MultiLineString(
        [
            LineString([(0.0, 10.0), (5.0, 10.0)]),
            LineString([(0.0, 0.0), (5.0, 0.0)]),
        ]
    )
    d = path_d(geom, min_x=0.0, max_y=10.0, precision=3)
    # Two "M" move commands -> two sub-paths within one path string.
    assert d.count("M") == 2
    assert d == "M 0,0 L 5,0 M 0,10 L 5,10"


# ---------------------------------------------------------------------------
# Fixed year-max width scale (Item #25, Task Group 2)
# ---------------------------------------------------------------------------

import math

from src.rendering import (
    fixed_flow_span,
    monthly_width_frames,
    widths_on_span,
)


def test_fixed_flow_span_endpoints_and_floor():
    # Span is on log of the positive min/max across ALL values.
    lo, hi = fixed_flow_span([1.0, 10.0, 100.0])
    assert math.isclose(lo, math.log(1.0))
    assert math.isclose(hi, math.log(100.0))
    # Values at/below the floor are floored before the log.
    lo2, _ = fixed_flow_span([0.0, 1e-6, 5.0], floor=1e-2)
    assert math.isclose(lo2, math.log(1e-2))


def test_fixed_flow_span_empty_and_degenerate():
    l = math.log(1e-2)
    lo, hi = fixed_flow_span([], floor=1e-2)
    assert lo == hi == l
    lo0, hi0 = fixed_flow_span([0.0, 0.0], floor=1e-2)
    assert lo0 == hi0 == l


def test_widths_on_span_endpoints_and_clamp():
    lo, hi = fixed_flow_span([1.0, 100.0])
    w = widths_on_span({1: 1.0, 2: 100.0}, lo, hi, width_min=2.0, width_max=8.0)
    assert math.isclose(w[1], 2.0)   # smallest flow -> width_min
    assert math.isclose(w[2], 8.0)   # largest flow -> width_max
    # A flow above the span's max clamps to width_max (fixed scale, not renorm).
    w2 = widths_on_span({3: 10_000.0}, lo, hi, width_min=2.0, width_max=8.0)
    assert math.isclose(w2[3], 8.0)
    # A flow below the span's min clamps to width_min.
    w3 = widths_on_span({4: 1e-9}, lo, hi, width_min=2.0, width_max=8.0)
    assert math.isclose(w3[4], 2.0)


def test_widths_on_span_is_fixed_not_renormalized():
    # Two frames sharing one span: the same flow yields the same width, and a
    # smaller-max frame does NOT stretch to width_max (that's the whole point).
    lo, hi = fixed_flow_span([1.0, 100.0])
    dry = widths_on_span({1: 1.0, 2: 10.0}, lo, hi, width_min=2.0, width_max=8.0)
    wet = widths_on_span({1: 1.0, 2: 100.0}, lo, hi, width_min=2.0, width_max=8.0)
    assert math.isclose(dry[1], wet[1])          # same flow, same width
    assert dry[2] < wet[2]                        # seasonal swell is visible
    assert dry[2] < 8.0                           # dry frame doesn't hit the max


def test_monthly_width_frames_wet_gt_dry_on_shared_span():
    # seg 1 swells mid-year, seg 2 is flat. One shared span across all months.
    monthly = {
        1: [1.0, 1.0, 2.0, 10.0, 100.0, 100.0, 50.0, 10.0, 2.0, 1.0, 1.0, 1.0],
        2: [5.0] * 12,
    }
    frames = monthly_width_frames(monthly, width_min=2.0, width_max=8.0)
    assert len(frames) == 12
    # seg 1 wider at its peak month (index 4) than at its trough (index 0).
    assert frames[4][1] > frames[0][1]
    # seg 2 constant across months (flat flow, fixed span).
    assert math.isclose(frames[0][2], frames[6][2])


# -- Streaming SVG writer (Item #108) ----------------------------------------

# A small network used by the streaming tests.
_STREAM_LINE_A = LineString([(0.0, 0.0), (5.0, 10.0)])
_STREAM_LINE_B = LineString([(5.0, 10.0), (10.0, 15.0)])
_STREAM_GEOMS = {1: _STREAM_LINE_A, 2: _STREAM_LINE_B}
_STREAM_COLORS = {1: "#ff0000", 2: "#00ff00"}
_STREAM_WATERSHEDS = {"HUC_A": {1}, "HUC_B": {2}}


def test_render_svg_stream_byte_identical_to_render_svg():
    """render_svg_stream produces the exact same bytes as render_svg."""
    string_svg = render_svg(_STREAM_GEOMS, _STREAM_COLORS, _STREAM_WATERSHEDS)
    buf = io.StringIO()
    render_svg_stream(buf, _STREAM_GEOMS, _STREAM_COLORS, _STREAM_WATERSHEDS)
    streamed_svg = buf.getvalue()
    assert string_svg == streamed_svg


def test_render_svg_stream_byte_identical_with_glow():
    """Streaming matches string output when glow is enabled."""
    kwargs = {"glow": True, "glow_mode": "blur", "glow_radius": 3.0}
    string_svg = render_svg(_STREAM_GEOMS, _STREAM_COLORS, _STREAM_WATERSHEDS, **kwargs)
    buf = io.StringIO()
    render_svg_stream(buf, _STREAM_GEOMS, _STREAM_COLORS, _STREAM_WATERSHEDS, **kwargs)
    assert string_svg == buf.getvalue()


def test_render_svg_stream_writes_valid_svg():
    """Streamed output starts with XML header and contains <svg> and </svg>."""
    buf = io.StringIO()
    render_svg_stream(buf, _STREAM_GEOMS, _STREAM_COLORS, _STREAM_WATERSHEDS)
    svg = buf.getvalue()
    assert svg.startswith('<?xml version="1.0"')
    assert "<svg" in svg
    assert "</svg>" in svg
    assert svg.endswith("\n")


# ---------------------------------------------------------------------------
# Coverage additions for missing lines
# ---------------------------------------------------------------------------


from shapely.geometry import Point, Polygon

from src import rendering
from src.rendering import (
    hypsometric_colors,
    polygon_path_d,
    stream_order_widths,
)


def test_path_d_none_returns_empty():
    """path_d with None geometry returns empty string (line 66)."""
    assert path_d(None, 0, 10, 3) == ""


def test_polygon_path_d_none_returns_empty():
    """polygon_path_d with None returns empty string (line 149)."""
    assert polygon_path_d(None, 0, 10, 3) == ""


def test_bounds_with_none_and_empty_geoms_returns_zero_box():
    """bounds with list of None/empty geoms returns the zero box (line 174).

    ``bounds()`` is defined over *line* geometries and always returns a
    4-tuple (never None).  Passing None/empty items simply yields no
    coordinates, so the result is the well-defined zero box ``(0,0,0,0)``.
    """
    assert bounds([None, LineString()]) == (0.0, 0.0, 0.0, 0.0)


def test_hypsometric_colors_empty_dict():
    """hypsometric_colors with empty dict returns empty dict (line 1363)."""
    assert hypsometric_colors({}) == {}


def test_stream_order_widths_max_order_le_1():
    """stream_order_widths with max_order=1 returns flat widths (line 1122-1123)."""
    orders = {1: 1, 2: 1, 3: 1}
    result = stream_order_widths(orders, max_order=1, base_width=0.5)
    assert all(v == 0.5 for v in result.values())
    assert set(result.keys()) == {1, 2, 3}


def test_stream_order_widths_interpolation():
    """stream_order_widths interpolates middle orders (lines 1131-1132)."""
    orders = {1: 1, 2: 2, 3: 3}
    result = stream_order_widths(orders, max_order=3, base_width=1.0, max_scale=3.0)
    # Order 1 -> base_width = 1.0
    assert math.isclose(result[1], 1.0)
    # Order 3 (max_order) -> base_width * max_scale = 3.0
    assert math.isclose(result[3], 3.0)
    # Order 2 -> midpoint: frac = (2-1)/(3-1) = 0.5, so 1.0 + (3.0 - 1.0) * 0.5 = 2.0
    assert math.isclose(result[2], 2.0)


def test_render_svg_empty_geoms_point_features_seeds_bounds():
    """render_svg with empty geometries but non-empty point_features seeds bounds
    from extras (lines 989-990).
    """
    svg = render_svg(
        {},
        {},
        {},
        point_features=[(1, Point(5.0, 5.0), "spring")],
    )
    assert len(svg) > 0
    assert "<svg" in svg
    assert "</svg>" in svg


def test_render_svg_structure_empty_linestring():
    """Exercise _structure_bar_element degenerate path with an empty
    LineString (lines 510-514): falls back to (0,0) bar.
    """
    from shapely import wkt

    empty_line = wkt.loads("LINESTRING EMPTY")
    svg = render_svg(
        _STREAM_GEOMS,
        _STREAM_COLORS,
        _STREAM_WATERSHEDS,
        hydro_structures=[(99, empty_line, "dam_weir")],
    )
    # Empty geom → _iter_line_parts yields nothing → degenerate fallback bar
    assert "<svg" in svg


def test_render_svg_glyph_shapes_dot_diamond_triangle():
    """Exercise dot, diamond, triangle glyph shapes (lines 543-544, 550-553)."""
    pt = Point(5.0, 5.0)
    for shape, family in [("dot", "spring"), ("diamond", "gate"), ("triangle", "spillway")]:
        svg = render_svg(
            _STREAM_GEOMS,
            _STREAM_COLORS,
            _STREAM_WATERSHEDS,
            hydro_structures=[(1, pt, family)],
            hydro_structure_styles={family: {"marker": shape}},
        )
        assert "<svg" in svg
        assert "hydro_" + family in svg


def test_render_svg_structure_polygon_outline_with_dash():
    """Exercise structure polygon with fill_mode outline and dash style
    (lines 607-610).
    """
    poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    svg = render_svg(
        _STREAM_GEOMS,
        _STREAM_COLORS,
        _STREAM_WATERSHEDS,
        hydro_structures=[(42, poly, "lock_chamber")],
        hydro_structure_styles={"lock_chamber": {"fill": "outline", "dash": "2 1"}},
    )
    assert "stroke-dasharray" in svg
    assert "hydro_lock_chamber" in svg


# ---------------------------------------------------------------------------
# Additional coverage for uncovered lines
# ---------------------------------------------------------------------------


from src.rendering import polygon_bounds


class _FakeLineString:
    """A fake geometry that _iter_line_parts yields but whose coords are empty."""

    is_empty = False
    geom_type = "LineString"
    coords = ()  # type: ignore[assignment]


def test_path_d_continue_on_empty_transform(monkeypatch):
    """path_d skips a line part whose coords transform to nothing (line 139).

    A degenerate LineString-like object with empty coords causes
    transform_coords to return [], triggering the continue branch.
    """
    result = path_d(_FakeLineString(), min_x=0.0, max_y=10.0, precision=3)
    assert result == ""


def test_path_d_multiline_skips_degenerate_part():
    """path_d skips degenerate parts in a MultiLineString (line 139).

    Construct a MultiLineString-like where one part has empty coords
    while another is valid — only the valid part appears in output.
    """

    class _FakeMulti:
        is_empty = False
        geom_type = "MultiLineString"
        geoms = (_FakeLineString(), LineString([(0.0, 10.0), (5.0, 0.0)]))

    d = path_d(_FakeMulti(), min_x=0.0, max_y=10.0, precision=3)
    assert d.count("M") == 1
    assert d == "M 0,0 L 5,10"


def test_polygon_bounds_returns_none_for_all_empty():
    """polygon_bounds returns None when all geometries are empty (line 174)."""
    empty_poly = Polygon()
    assert polygon_bounds([empty_poly, Polygon()]) is None


def test_polygon_path_d_skips_ring_with_fewer_than_2_points():
    """polygon_path_d skips a ring with <2 distinct points after transform
    (line 192).

    A fake polygon whose ring has only one unique coordinate (after the
    closing-duplicate is dropped) results in <2 points -> skip.
    """

    class _SinglePointPoly:
        """Polygon-like with a degenerate single-point ring."""

        is_empty = False
        geom_type = "Polygon"

        class exterior:
            coords = ((5.0, 5.0), (5.0, 5.0))

        interiors = ()  # type: ignore[assignment]

    result = polygon_path_d(_SinglePointPoly(), min_x=0.0, max_y=10.0, precision=3)
    assert result == ""


def test_point_bounds_returns_none_for_all_empty_or_none():
    """_point_bounds returns None when all items have None/empty geom (line 285)."""
    items = [
        (1, None, "spring"),
        (2, Point(), "well"),
    ]
    result = rendering._point_bounds(items)
    assert result is None


def test_structure_bounds_skips_geom_with_falsy_bounds():
    """_structure_bounds skips geom where .bounds is falsy (line 309).

    A mock geometry that is not empty but has falsy (empty tuple) bounds.
    """

    class _FalsyBoundsGeom:
        is_empty = False
        bounds = ()

    items = [(1, _FalsyBoundsGeom(), "dam_weir")]
    result = rendering._structure_bounds(items)
    assert result is None


def test_halo_lines_per_segment_stroke_and_channel_dashes():
    """_halo_lines with color=None appends per-segment stroke (line 743) and
    channel_dashes entry appends stroke-dasharray (line 745).

    Unassigned segments get color=None at line 1061; exercising them with
    vector_glow=True and channel_dashes hits both branches.
    """
    geoms = {1: LineString([(0.0, 0.0), (5.0, 10.0)])}
    colors = {1: "#ff0000"}
    # Segment 1 is unassigned (not in any watershed), so the river_groups
    # entry will be ("rivers_unassigned", None, [1]).
    svg = render_svg(
        geoms,
        colors,
        {},  # no watersheds -> segment 1 is unassigned -> color=None
        glow=True,
        glow_mode="vector",
        channel_dashes={1: "4 2"},
    )
    assert "<svg" in svg
    # The halo group should have per-segment stroke since group color is None.
    assert 'stroke="#ff0000"' in svg
    # Channel dashes should appear on the halo path.
    assert 'stroke-dasharray="4 2"' in svg


def test_point_features_rendered_below():
    """Point features with point_feature_order='below' are rendered before
    rivers (line 1040).
    """
    svg = render_svg(
        _STREAM_GEOMS,
        _STREAM_COLORS,
        _STREAM_WATERSHEDS,
        point_features=[(10, Point(3.0, 3.0), "spring")],
        point_feature_order="below",
    )
    assert "<svg" in svg
    # Point features group appears before watershed groups.
    pf_pos = svg.find("point_features")
    ws_pos = svg.find("watershed_")
    assert pf_pos < ws_pos, "point features should appear before rivers when order=below"


def test_hydro_structures_rendered_below():
    """Hydro structures with hydro_structure_order='below' are rendered before
    rivers (line 1045).
    """
    svg = render_svg(
        _STREAM_GEOMS,
        _STREAM_COLORS,
        _STREAM_WATERSHEDS,
        hydro_structures=[(20, Point(3.0, 3.0), "dam_weir")],
        hydro_structure_order="below",
    )
    assert "<svg" in svg
    # Structures group appears before watershed groups.
    hs_pos = svg.find("hydro_")
    ws_pos = svg.find("watershed_")
    assert hs_pos < ws_pos, "hydro structures should appear before rivers when order=below"


def test_empty_watershed_group_skipped():
    """A watershed whose segment IDs are all absent from geometries is skipped
    (line 1056).
    """
    geoms = {1: LineString([(0.0, 0.0), (5.0, 10.0)])}
    colors = {1: "#ff0000"}
    watersheds = {
        "PRESENT": {1},
        "ABSENT": {999, 998},  # IDs not in geoms -> skipped
    }
    svg = render_svg(geoms, colors, watersheds)
    assert "watershed_PRESENT" in svg
    assert "watershed_ABSENT" not in svg
