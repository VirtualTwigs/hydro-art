"""Offline tests for the pure structure-QA module (Epoch 16, Item 68, TG1).

Hand-built shapely geometries already in a metric frame (EPSG:5070 contract),
so the module does pure distance/coincidence math with no reprojection. No
GDAL beyond top-level shapely; no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, Point, Polygon

from src.hydro_structure_qa import (
    HydroStructureQAReport,
    NetworkPlacement,
    build_qa_report,
    canal_natural_separation,
    cross_layer_duplicates,
    structure_network_placement,
)
from src.hydro_structures import HydroStructure


def _structure(
    source_id: str,
    geometry: Any,
    *,
    source_layer: str = "NHDLine",
    struct_class: str = "dam_weir",
) -> HydroStructure:
    """Build a minimal classified structure for QA (metric-frame geometry)."""
    return HydroStructure(
        source_id=source_id,
        source_layer=source_layer,
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometry=geometry,
        ftype=343,
        fcode=None,
        name=None,
        struct_class=struct_class,
    )


@dataclass(frozen=True)
class _Natural:
    """A minimal natural-taxonomy feature carrying only a ``.geometry``."""

    source_id: str
    geometry: Any


def test_placement_on_vs_off_network_with_median_and_max() -> None:
    """On-network within tolerance; a far one is off-network; median/max exact."""
    flowline = LineString([(0.0, 0.0), (100.0, 0.0)])
    # Distances to the flowline: 5 m, 20 m, 500 m (off-network at tol=50).
    near = _structure("near", Point(10.0, 5.0))
    mid = _structure("mid", Point(50.0, 20.0))
    far = _structure("far", Point(50.0, 500.0))

    placement = structure_network_placement(
        [near, mid, far], [flowline], tolerance_m=50.0
    )

    assert placement.count == 3
    assert placement.on_network == 2
    assert placement.off_network_ids == ("far",)
    # Sorted distances 5, 20, 500 -> median 20, max 500.
    assert placement.median_distance_m == 20.0
    assert placement.max_distance_m == 500.0


def test_cross_layer_duplicate_grouped_distinct_dams_not() -> None:
    """A dam on NHDLine + NHDArea within tolerance groups; two distinct do not."""
    line_dam = _structure(
        "dam-line", LineString([(0.0, 0.0), (0.0, 10.0)]), source_layer="NHDLine"
    )
    area_dam = _structure(
        "dam-area",
        Polygon([(1.0, 0.0), (3.0, 0.0), (3.0, 10.0), (1.0, 10.0)]),
        source_layer="NHDArea",
    )
    far_dam = _structure(
        "dam-far",
        LineString([(9000.0, 0.0), (9000.0, 10.0)]),
        source_layer="NHDLine",
    )

    groups = cross_layer_duplicates(
        [line_dam, area_dam, far_dam], tolerance_m=25.0
    )

    assert groups == (("dam-line", "dam-area"),)


def test_same_layer_near_pair_not_grouped() -> None:
    """Two near dams on the SAME layer are not a cross-layer duplicate."""
    a = _structure("a", Point(0.0, 0.0), source_layer="NHDLine")
    b = _structure("b", Point(1.0, 0.0), source_layer="NHDLine")

    assert cross_layer_duplicates([a, b], tolerance_m=25.0) == ()


def test_separation_violation_vs_disjoint() -> None:
    """A canal coinciding with a natural feature fails; disjoint passes."""
    lake = _Natural(
        "lake", Polygon([(0.0, 0.0), (0.0, 20.0), (20.0, 20.0), (20.0, 0.0)])
    )
    overlapping = _structure(
        "canal-bad",
        LineString([(5.0, 5.0), (15.0, 15.0)]),
        struct_class="canal_ditch",
    )
    disjoint = _structure(
        "canal-ok",
        LineString([(100.0, 100.0), (200.0, 200.0)]),
        struct_class="canal_ditch",
    )

    bad_ok, bad_pairs = canal_natural_separation([overlapping], [lake])
    assert bad_ok is False
    assert bad_pairs == (("canal-bad", "lake"),)

    good_ok, good_pairs = canal_natural_separation([disjoint], [lake])
    assert good_ok is True
    assert good_pairs == ()


def test_shared_boundary_adjacency_is_not_a_violation() -> None:
    """An engineered polygon that only *touches* a natural polygon is clean.

    Two polygons sharing an edge intersect in a zero-area line, so the
    area-based coincidence fraction is 0 — real NHD data is full of such
    adjacency and it must not register as a separation leak.
    """
    lake = _Natural(
        "lake", Polygon([(0.0, 0.0), (0.0, 20.0), (20.0, 20.0), (20.0, 0.0)])
    )
    # Shares the x=20 edge with the lake but occupies a disjoint interior.
    adjacent = _structure(
        "area-adjacent",
        Polygon([(20.0, 0.0), (40.0, 0.0), (40.0, 20.0), (20.0, 20.0)]),
        source_layer="NHDArea",
        struct_class="canal_ditch",
    )

    ok, pairs = canal_natural_separation([adjacent], [lake])
    assert ok is True
    assert pairs == ()


def test_build_qa_report_aggregates() -> None:
    """``build_qa_report`` folds the three checks into one frozen report."""
    flowline = LineString([(0.0, 0.0), (100.0, 0.0)])
    line_dam = _structure(
        "dam-line", Point(10.0, 5.0), source_layer="NHDLine"
    )
    area_dam = _structure(
        "dam-area", Point(11.0, 5.0), source_layer="NHDArea"
    )
    lake = _Natural("lake", Polygon([(9.0, 4.0), (9.0, 6.0), (13.0, 6.0), (13.0, 4.0)]))

    report = build_qa_report(
        [line_dam, area_dam], [flowline], [lake], tolerance_m=50.0
    )

    assert isinstance(report, HydroStructureQAReport)
    assert isinstance(report.on_network, NetworkPlacement)
    assert report.on_network.on_network == 2
    assert report.duplicate_groups == (("dam-line", "dam-area"),)
    assert report.separation_ok is False
    assert report.overlaps == (("dam-line", "lake"), ("dam-area", "lake"))


def test_build_qa_report_all_clean() -> None:
    """A healthy build: on-network, no duplicates, separation intact.

    Two distinct dams on different layers but well beyond ``tolerance_m`` of
    each other (not a duplicate), each sitting on the flowline, and a natural
    feature far from both — the all-green verdict a good render produces.
    """
    flowline = LineString([(0.0, 0.0), (1000.0, 0.0)])
    dam_a = _structure("dam-a", Point(10.0, 5.0), source_layer="NHDLine")
    dam_b = _structure("dam-b", Point(900.0, 5.0), source_layer="NHDArea")
    far_lake = _Natural(
        "lake",
        Polygon([(0.0, 5000.0), (0.0, 5020.0), (20.0, 5020.0), (20.0, 5000.0)]),
    )

    report = build_qa_report(
        [dam_a, dam_b], [flowline], [far_lake], tolerance_m=50.0
    )

    assert report.on_network.count == 2
    assert report.on_network.on_network == 2
    assert report.on_network.off_network_ids == ()
    assert report.duplicate_groups == ()
    assert report.separation_ok is True
    assert report.overlaps == ()


def test_build_qa_report_all_violating() -> None:
    """A pathological build trips every check at once.

    A cross-layer duplicate dam pair, both floating off-network, both
    coincident with a natural feature — asserts the three checks compose
    independently rather than one masking another.
    """
    flowline = LineString([(0.0, 0.0), (100.0, 0.0)])
    lake = _Natural(
        "lake",
        Polygon([(0.0, 900.0), (0.0, 1100.0), (200.0, 1100.0), (200.0, 900.0)]),
    )
    # Both dams sit inside the lake (~1000 m off the flowline) and within
    # tolerance of each other on different layers.
    dam_line = _structure("dam-line", Point(100.0, 1000.0), source_layer="NHDLine")
    dam_area = _structure(
        "dam-area",
        Polygon([(101.0, 999.0), (103.0, 999.0), (103.0, 1001.0), (101.0, 1001.0)]),
        source_layer="NHDArea",
    )

    report = build_qa_report(
        [dam_line, dam_area], [flowline], [lake], tolerance_m=50.0
    )

    assert report.on_network.on_network == 0
    assert set(report.on_network.off_network_ids) == {"dam-line", "dam-area"}
    assert report.duplicate_groups == (("dam-line", "dam-area"),)
    assert report.separation_ok is False
    assert {pair[0] for pair in report.overlaps} == {"dam-line", "dam-area"}
