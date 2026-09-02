"""Tests for point-glyph + differentiated areal SVG rendering (Epoch 15, Item 63).

Exercises the additive `point_features` / `areal_features` layers in
`render_svg`. Core guarantee (mirroring the waterbody layer): with no point/areal
features supplied, the output is byte-identical to the pre-feature render.
"""

from shapely.geometry import LineString, Point, Polygon

from src.rendering import render_svg

# A minimal river network shared across tests.
_GEOMS = {1: LineString([(0, 0), (10, 10)])}
_COLORS = {1: "#ff0000"}
_WSHEDS = {"1701": {1}}


def _square(x0, y0, size):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def test_render_without_natural_features_is_byte_identical():
    baseline = render_svg(_GEOMS, _COLORS, _WSHEDS)
    with_none = render_svg(_GEOMS, _COLORS, _WSHEDS, point_features=None, areal_features=None)
    with_empty = render_svg(_GEOMS, _COLORS, _WSHEDS, point_features=[], areal_features=[])
    assert with_none == baseline
    assert with_empty == baseline
    assert 'id="point_features"' not in baseline
    assert 'id="areal_' not in baseline


def test_point_glyph_layer_groups_and_stable_ids():
    pts = [
        ("sp1", Point(1, 1), "spring"),
        ("wf2", Point(2, 2), "waterfall"),
        ("rp3", Point(3, 3), "rapids"),
    ]
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, point_features=pts)
    assert '<g id="point_features">' in svg
    assert '<g id="point_spring"' in svg
    assert '<g id="point_waterfall"' in svg
    assert '<g id="point_rapids"' in svg
    assert 'id="point_spring_sp1"' in svg
    assert 'id="point_waterfall_wf2"' in svg
    # Springs are dots (<circle>); waterfalls/rapids are stroked <path> glyphs.
    spring_block = svg.split('id="point_spring"')[1].split("</g>")[0]
    assert "<circle" in spring_block
    wf_block = svg.split('id="point_waterfall"')[1].split("</g>")[0]
    rp_block = svg.split('id="point_rapids"')[1].split("</g>")[0]
    assert "<path" in wf_block and 'fill="none"' in wf_block
    assert "<path" in rp_block


def test_areal_families_have_differentiated_treatments():
    ar = [
        ("we", _square(0, 0, 10), "wetland"),
        ("ic", _square(20, 0, 10), "perennial_ice"),
        ("pl", _square(40, 0, 10), "playa"),
    ]
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, areal_features=ar)
    assert '<g id="areal_wetland" data-class="wetland"' in svg
    assert '<g id="areal_perennial_ice" data-class="perennial_ice"' in svg
    assert '<g id="areal_playa" data-class="playa"' in svg
    # Wetland = hatch pattern fill (pattern defined in <defs>).
    assert 'id="areal_wetland_hatch"' in svg
    assert 'fill="url(#areal_wetland_hatch)"' in svg
    # Perennial ice = low-opacity solid fill.
    ice_block = svg.split('id="areal_perennial_ice"')[1].split(">")[0]
    assert "fill-opacity=" in ice_block
    # Playa = dashed outline, no fill.
    playa_block = svg.split('id="areal_playa"')[1].split(">")[0]
    assert "stroke-dasharray=" in playa_block
    assert 'fill="none"' in playa_block


def test_zorder_areal_beneath_and_points_on_top():
    pts = [("sp", Point(1, 1), "spring")]
    ar = [("we", _square(0, 0, 10), "wetland")]
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, point_features=pts, areal_features=ar)
    # Areal groups default beneath the flowlines; point glyphs on top of them.
    assert svg.index('id="areal_wetland"') < svg.index('id="watershed_1701"')
    assert svg.index('id="point_features"') > svg.index('id="watershed_1701"')


def test_point_and_areal_styles_are_configurable():
    pts = [("sp", Point(1, 1), "spring")]
    ar = [("pl", _square(0, 0, 10), "playa")]
    svg = render_svg(
        _GEOMS, _COLORS, _WSHEDS,
        point_features=pts,
        point_feature_styles={"spring": {"color": "#00ffcc", "size": 3.0}},
        areal_features=ar,
        areal_feature_styles={"playa": {"color": "#ffaa00", "dash": "6,2"}},
    )
    spring_block = svg.split('id="point_features"')[1].split('id="areal_')[0] if 'id="areal_' in svg else svg.split('id="point_features"')[1]
    assert 'stroke="#00ffcc"' in spring_block or 'fill="#00ffcc"' in spring_block
    assert 'r="3"' in spring_block
    playa_block = svg.split('id="areal_playa"')[1].split(">")[0]
    assert 'stroke="#ffaa00"' in playa_block
    assert 'stroke-dasharray="6,2"' in playa_block
