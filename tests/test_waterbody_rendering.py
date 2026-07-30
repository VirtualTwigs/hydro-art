"""Tests for waterbody-outline SVG rendering (Item W3, Task Group 3).

Exercises the additive `waterbodies` layer in `render_svg` plus the polygon
outline path builder. A core guarantee: with no waterbodies the output is
byte-identical to the pre-W3 river-only render.
"""

from shapely.geometry import LineString, Polygon

from src.rendering import polygon_path_d, render_svg

# A minimal river network shared across tests.
_GEOMS = {1: LineString([(0, 0), (10, 10)])}
_COLORS = {1: "#ff0000"}
_WSHEDS = {"1701": {1}}


def _square(x0, y0, size):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def test_polygon_path_d_closes_exterior_and_hole():
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    hole = [(40, 40), (60, 40), (60, 60), (40, 60)]
    donut = Polygon(outer, [hole])
    d = polygon_path_d(donut, min_x=0, max_y=100, precision=3)
    # One subpath per ring, each explicitly closed with Z.
    assert d.count("Z") == 2
    assert d.count("M") == 2
    assert d.startswith("M ")


def test_render_without_waterbodies_is_byte_identical():
    baseline = render_svg(_GEOMS, _COLORS, _WSHEDS)
    with_none = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=None)
    with_empty = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=[])
    assert with_none == baseline
    assert with_empty == baseline
    assert 'id="waterbodies"' not in baseline


def test_waterbodies_group_is_fill_none_with_stable_ids():
    items = [("lake-7", _square(0, 0, 20), "lake")]
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=items)
    assert '<g id="waterbodies" fill="none"' in svg
    assert '<g id="waterbody_lake-7" data-class="lake">' in svg
    assert '<path id="waterbody_lake-7_outline"' in svg


def test_waterbody_group_uses_configured_color_and_width():
    items = [("a", _square(0, 0, 5), "pond")]
    svg = render_svg(
        _GEOMS, _COLORS, _WSHEDS,
        waterbodies=items, waterbody_color="#00ffcc", waterbody_stroke_width=1.5,
    )
    assert 'stroke="#00ffcc"' in svg
    assert 'stroke-width="1.5"' in svg.split('id="waterbodies"')[1]


def test_render_order_below_vs_above_flowlines():
    items = [("a", _square(0, 0, 5), "lake")]
    below = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=items, waterbody_order="below")
    above = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=items, waterbody_order="above")
    # "below" → waterbodies group precedes the river layer; "above" → follows it.
    assert below.index('id="waterbodies"') < below.index('id="watershed_1701"')
    assert above.index('id="waterbodies"') > above.index('id="watershed_1701"')
