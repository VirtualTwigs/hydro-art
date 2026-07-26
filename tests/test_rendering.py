"""Unit tests for the SVG geometry core (Item #8, Task Group 1).

Pure geometry -> SVG helpers, tested with hand-built shapely lines (no GDAL,
no real data). Covers bounding box, deterministic number formatting, the
cartesian Y-flip transform, and path ``d`` string building.
"""

from shapely.geometry import LineString, MultiLineString

from src.rendering import bounds, format_number, path_d, transform_coords


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
