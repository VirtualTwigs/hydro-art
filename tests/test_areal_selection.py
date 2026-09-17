"""Tests for areal + point repair/reproject/clip/select (Epoch 15, Item 62).

Features are built already in EPSG:5070 (``source_crs="EPSG:5070"``) so the
reprojection step is a no-op and planar shapely ``area`` is directly in m²; this
keeps the suite offline (no pyproj/GDAL) while exercising repair, clip, per-class
area thresholds, WKB dedup, the selection report, and the deterministic point
density cap.
"""

from shapely.geometry import Point, Polygon

from src.areal_features import ArealFeature
from src.areal_selection import (
    ArealSelection,
    ArealSelectionPolicy,
    PointSelection,
    PointSelectionPolicy,
    process_areal_features,
    process_point_features,
)
from src.point_features import PointFeature


def _areal(geometry, ar_class="wetland", source_id="ar", **kw):
    return ArealFeature(
        source_id=source_id,
        source_layer="NHDWaterbody",
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometry=geometry,
        ftype=kw.get("ftype", 466),
        fcode=None,
        name=kw.get("name"),
        ar_class=ar_class,
        source_crs="EPSG:5070",
        inclusion_reason="classified",
    )


def _point(geometry, pt_class="spring", source_id="pt", **kw):
    return PointFeature(
        source_id=source_id,
        source_layer="NHDPoint",
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometry=geometry,
        ftype=kw.get("ftype", 458),
        fcode=None,
        name=kw.get("name"),
        pt_class=pt_class,
        source_crs="EPSG:5070",
        inclusion_reason="classified",
    )


def _square(x0, y0, size):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


# --- Areal selection -------------------------------------------------------


def test_areal_area_measured_and_kept_with_zero_threshold():
    feat = _areal(_square(0, 0, 100))  # 10_000 m^2
    result = process_areal_features([feat])
    assert isinstance(result, ArealSelection)
    assert len(result.selected) == 1
    assert result.selected[0].area_m2 == 100 * 100
    assert not result.excluded


def test_areal_per_class_min_area_threshold():
    small_wet = _areal(_square(0, 0, 20), ar_class="wetland", source_id="w")  # 400
    big_playa = _areal(_square(200, 0, 20), ar_class="playa", source_id="p")  # 400
    policy = ArealSelectionPolicy(min_area_m2={"wetland": 1000, "playa": 100})
    result = process_areal_features([small_wet, big_playa], policy=policy)
    kept = {f.source_id for f in result.selected}
    dropped = {f.source_id for f in result.excluded}
    assert kept == {"p"}  # playa above its threshold, wetland below its own
    assert dropped == {"w"}
    assert "below min" in result.excluded[0].inclusion_reason.lower()


def test_areal_holes_preserved_and_clip_trims_at_boundary():
    boundary = _square(0, 0, 100)
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    hole = [(40, 40), (60, 40), (60, 60), (40, 60)]
    donut = _areal(Polygon(outer, [hole]), source_id="donut")
    outside = _areal(_square(500, 500, 10), source_id="outside")
    result = process_areal_features([donut, outside], boundary=boundary)
    kept = {f.source_id: f for f in result.selected}
    assert "donut" in kept
    assert len(kept["donut"].geometry.interiors) == 1
    assert kept["donut"].area_m2 == 100 * 100 - 20 * 20
    assert {f.source_id for f in result.excluded} == {"outside"}


def test_areal_duplicate_geometry_deduped_and_report_accounts_all():
    a = _areal(_square(0, 0, 30), source_id="a")
    b = _areal(_square(0, 0, 30), source_id="b")  # identical footprint
    pre_excluded = _areal(_square(0, 0, 1), ar_class="excluded", source_id="ex")
    result = process_areal_features([a, b, pre_excluded])
    assert [f.source_id for f in result.selected] == ["a"]
    dropped = {f.source_id for f in result.excluded}
    assert dropped == {"b", "ex"}
    assert result.counts["candidates"] == 3
    assert result.counts["selected"] == 1
    assert result.policy_version


# --- Point selection -------------------------------------------------------


def test_point_clip_drops_outside_and_keeps_inside():
    boundary = _square(0, 0, 100)
    inside = _point(Point(50, 50), source_id="in")
    outside = _point(Point(500, 500), source_id="out")
    result = process_point_features([inside, outside], boundary=boundary)
    assert isinstance(result, PointSelection)
    assert [f.source_id for f in result.selected] == ["in"]
    assert [f.source_id for f in result.excluded] == ["out"]


def test_point_min_spacing_thins_deterministically_by_source_order():
    # Three springs in a line 30 m apart; a 50 m min-spacing keeps the first,
    # drops the too-close second, then keeps the third (60 m from the first).
    a = _point(Point(0, 0), source_id="a")
    b = _point(Point(30, 0), source_id="b")
    c = _point(Point(60, 0), source_id="c")
    policy = PointSelectionPolicy(min_spacing_m={"spring": 50})
    result = process_point_features([a, b, c], policy=policy)
    assert [f.source_id for f in result.selected] == ["a", "c"]
    assert [f.source_id for f in result.excluded] == ["b"]
    # Spacing is per-family: a waterfall in the same spot is not thinned.
    wf = _point(Point(30, 0), pt_class="waterfall", source_id="wf")
    result2 = process_point_features([a, wf], policy=policy)
    assert {f.source_id for f in result2.selected} == {"a", "wf"}


def test_point_duplicate_coordinates_suppressed():
    a = _point(Point(10, 10), source_id="a")
    dup = _point(Point(10, 10), source_id="dup")
    result = process_point_features([a, dup])
    assert [f.source_id for f in result.selected] == ["a"]
    assert [f.source_id for f in result.excluded] == ["dup"]
    assert "duplicate" in result.excluded[0].inclusion_reason.lower()
