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
    kwargs = dict(glow=True, glow_mode="blur", glow_radius=3.0)
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
