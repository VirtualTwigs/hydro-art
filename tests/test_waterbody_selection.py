"""Tests for waterbody repair/clip/area selection (Item W2, Task Group 2).

Features are built already in EPSG:5070 (``source_crs="EPSG:5070"``) so the
reprojection step is a no-op and planar shapely ``area`` is directly in m²;
this keeps the suite offline (no pyproj/GDAL) while exercising repair, clip,
area thresholds, coast policy, dedup, and the selection report.
"""

from shapely.geometry import Polygon

from src.waterbodies import WaterbodyFeature
from src.waterbody_selection import (
    WaterbodySelection,
    WaterbodySelectionPolicy,
    process_waterbodies,
)


def _feature(geometry, wb_class="lake", source_id="wb", **kw):
    return WaterbodyFeature(
        source_id=source_id,
        source_layer=kw.get("source_layer", "NHDWaterbody"),
        dataset_id="nhdplus_hr",
        huc4="1709",
        geometry=geometry,
        ftype=kw.get("ftype", 390),
        fcode=None,
        name=kw.get("name"),
        wb_class=wb_class,
        source_crs="EPSG:5070",
        inclusion_reason="classified",
    )


def _square(x0, y0, size):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def test_area_measured_in_m2_and_kept_with_zero_threshold():
    feat = _feature(_square(0, 0, 100))  # 100 m x 100 m = 10_000 m^2
    result = process_waterbodies([feat])
    assert isinstance(result, WaterbodySelection)
    assert len(result.selected) == 1
    assert result.selected[0].area_m2 == 100 * 100
    assert not result.excluded


def test_inland_area_threshold_is_inclusive_boundary():
    small = _feature(_square(0, 0, 20), source_id="small")   # 400 m^2
    exact = _feature(_square(200, 0, 20), source_id="exact")  # 400 m^2
    big = _feature(_square(400, 0, 50), source_id="big")      # 2500 m^2
    policy = WaterbodySelectionPolicy(min_inland_area_m2=400)
    result = process_waterbodies([small, exact, big], policy=policy)
    kept = {f.source_id for f in result.selected}
    dropped = {f.source_id for f in result.excluded}
    # >= threshold is kept; strictly below is dropped.
    assert "exact" in kept and "big" in kept
    assert dropped == set()
    smaller = _feature(_square(0, 0, 10), source_id="tiny")  # 100 m^2
    result2 = process_waterbodies([smaller], policy=policy)
    assert not result2.selected
    assert "below min" in result2.excluded[0].inclusion_reason.lower()


def test_invalid_polygon_repaired_then_measured():
    # Self-intersecting "bowtie" polygon is made valid before area measurement.
    bowtie = Polygon([(0, 0), (100, 100), (0, 100), (100, 0)])
    assert not bowtie.is_valid
    result = process_waterbodies([_feature(bowtie)])
    assert len(result.selected) == 1
    assert result.selected[0].area_m2 > 0
    assert result.selected[0].geometry.is_valid


def test_holes_are_preserved_and_reduce_area():
    outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
    hole = [(40, 40), (60, 40), (60, 60), (40, 60)]
    donut = Polygon(outer, [hole])
    result = process_waterbodies([_feature(donut)])
    geom = result.selected[0].geometry
    assert len(geom.interiors) == 1
    assert result.selected[0].area_m2 == 100 * 100 - 20 * 20


def test_clip_trims_partial_and_drops_outside():
    boundary = _square(0, 0, 100)
    straddler = _feature(_square(50, 0, 100), source_id="straddler")  # half inside
    outside = _feature(_square(500, 500, 10), source_id="outside")
    result = process_waterbodies([straddler, outside], boundary=boundary)
    kept = {f.source_id: f for f in result.selected}
    assert "straddler" in kept
    assert kept["straddler"].area_m2 == 50 * 100  # trimmed to the boundary
    assert "clipped" in kept["straddler"].qa_flags
    assert {f.source_id for f in result.excluded} == {"outside"}


def test_conservative_coast_excludes_clipped_bay_keeps_inland():
    boundary = _square(0, 0, 100)
    clipped_bay = _feature(_square(50, 0, 100), wb_class="bay", source_id="bay")
    inland_bay = _feature(_square(10, 10, 20), wb_class="bay", source_id="inbay")
    result = process_waterbodies([clipped_bay, inland_bay], boundary=boundary)
    kept = {f.source_id for f in result.selected}
    excluded = {f.source_id: f for f in result.excluded}
    assert "inbay" in kept
    assert "bay" in excluded
    assert "coast" in excluded["bay"].inclusion_reason.lower()


def test_duplicate_geometry_is_deduplicated():
    geom = _square(0, 0, 30)
    a = _feature(geom, source_id="a")
    b = _feature(_square(0, 0, 30), source_id="b")  # identical footprint
    result = process_waterbodies([a, b])
    assert [f.source_id for f in result.selected] == ["a"]
    assert [f.source_id for f in result.excluded] == ["b"]
    assert "duplicate" in result.excluded[0].inclusion_reason.lower()


def test_report_accounts_for_every_candidate_and_flags_shared_edges():
    boundary = None
    left = _feature(_square(0, 0, 50), source_id="left")
    right = _feature(_square(50, 0, 50), source_id="right")  # shares the x=50 edge
    pre_excluded = _feature(_square(0, 0, 1), wb_class="excluded", source_id="ex")
    result = process_waterbodies([left, right, pre_excluded], boundary=boundary)
    assert len(result.selected) + len(result.excluded) == 3
    assert result.counts["candidates"] == 3
    assert result.policy_version
    assert result.shared_edge_pairs >= 1
