"""Tests for hydro-structure repair/reproject/clip/select (Epoch 16, Item 67).

Structures are built already in EPSG:5070 (``source_crs="EPSG:5070"``) so the
reprojection step is a no-op and planar shapely ``area`` is directly in m²; this
keeps the suite offline (no pyproj/GDAL) while exercising the geometry-type
dispatch that distinguishes this module from the Epoch 15 points-only /
polygons-only selectors: polygon ``min_area_m2``, point ``min_spacing_m``
density thinning, and line clip-only.
"""

import subprocess
import sys

from shapely.geometry import LineString, Point, Polygon

from src.hydro_structure_selection import (
    HydroStructureSelection,
    HydroStructureSelectionPolicy,
    process_hydro_structures,
)
from src.hydro_structures import HydroStructure


def _structure(geometry, struct_class="dam_weir", source_id="s", layer="NHDLine"):
    return HydroStructure(
        source_id=source_id,
        source_layer=layer,
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometry=geometry,
        ftype=343,
        fcode=None,
        name=None,
        struct_class=struct_class,
        source_crs="EPSG:5070",
        inclusion_reason="classified",
    )


def _square(x0, y0, size):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])


def test_polygon_min_area_threshold():
    small = _structure(_square(0, 0, 20), struct_class="spillway", source_id="small")
    big = _structure(_square(200, 0, 40), struct_class="spillway", source_id="big")
    policy = HydroStructureSelectionPolicy(min_area_m2={"spillway": 1000})
    result = process_hydro_structures(
        [small, big], boundary=None, policy=policy
    )
    assert isinstance(result, HydroStructureSelection)
    assert {f.source_id for f in result.selected} == {"big"}  # 1600 >= 1000
    assert {f.source_id for f in result.excluded} == {"small"}  # 400 < 1000
    assert "below min" in result.excluded[0].inclusion_reason.lower()


def test_point_min_spacing_thins_deterministically_in_source_order():
    a = _structure(Point(0, 0), struct_class="gaging_station", source_id="a",
                   layer="NHDPoint")
    b = _structure(Point(30, 0), struct_class="gaging_station", source_id="b",
                   layer="NHDPoint")
    c = _structure(Point(60, 0), struct_class="gaging_station", source_id="c",
                   layer="NHDPoint")
    policy = HydroStructureSelectionPolicy(min_spacing_m={"gaging_station": 50})
    result = process_hydro_structures([a, b, c], boundary=None, policy=policy)
    # First kept, second dropped (30 m < 50), third kept (60 m from first).
    assert [f.source_id for f in result.selected] == ["a", "c"]
    assert [f.source_id for f in result.excluded] == ["b"]


def test_line_clip_only_kept_and_outside_excluded():
    boundary = _square(0, 0, 100)
    inside = _structure(LineString([(10, 50), (90, 50)]), source_id="in")
    outside = _structure(LineString([(500, 500), (600, 600)]), source_id="out")
    result = process_hydro_structures(
        [inside, outside], boundary=boundary, policy=HydroStructureSelectionPolicy()
    )
    assert {f.source_id for f in result.selected} == {"in"}
    assert {f.source_id for f in result.excluded} == {"out"}


def test_boundary_straddling_line_clipped_not_dropped():
    boundary = _square(0, 0, 100)
    straddle = _structure(LineString([(50, 50), (200, 50)]), source_id="straddle")
    result = process_hydro_structures(
        [straddle], boundary=boundary, policy=HydroStructureSelectionPolicy()
    )
    assert [f.source_id for f in result.selected] == ["straddle"]
    kept = result.selected[0]
    assert "clipped" in kept.qa_flags
    # The clipped geometry stops at the boundary (x=100), not the source end.
    assert kept.geometry.bounds[2] <= 100.0 + 1e-9


def test_selection_carries_provenance_counts_and_policy_version():
    poly = _structure(_square(0, 0, 40), struct_class="spillway", source_id="p")
    pt = _structure(Point(10, 10), struct_class="gaging_station", source_id="g",
                    layer="NHDPoint")
    result = process_hydro_structures(
        [poly, pt], boundary=None, policy=HydroStructureSelectionPolicy()
    )
    assert result.policy_version
    assert result.counts["candidates"] == 2
    assert result.counts["selected"] == 2
    assert result.counts["by_class"] == {"spillway": 1, "gaging_station": 1}
    kept = {f.source_id: f for f in result.selected}
    assert kept["p"].struct_class == "spillway"
    assert kept["g"].source_id == "g"


def test_module_import_does_not_pull_pyproj_eagerly():
    # Offline discipline: importing the selection module must NOT eagerly pull
    # pyproj (the reproject seam is lazy). Checked in a FRESH interpreter so the
    # assertion can't be polluted by a sibling test in the same session that
    # legitimately imports pyproj (e.g. a pipeline test reprojecting 4326->5070).
    snippet = (
        "import sys; import src.hydro_structure_selection; "
        "sys.exit(1 if 'pyproj' in sys.modules else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        "importing src.hydro_structure_selection eagerly pulled pyproj: "
        f"{result.stderr.decode()}"
    )


def test_injectable_reproject_seam_used():
    calls: list[str] = []

    def fake_reproject(geom, src_crs, dst_crs):
        calls.append(f"{src_crs}->{dst_crs}")
        return geom

    feat = _structure(Point(1, 1), struct_class="gaging_station", source_id="g",
                      layer="NHDPoint")
    feat = HydroStructure(**{**feat.__dict__, "source_crs": "EPSG:4269"})
    result = process_hydro_structures(
        [feat], boundary=None, policy=HydroStructureSelectionPolicy(),
        reproject=fake_reproject,
    )
    assert calls == ["EPSG:4269->EPSG:5070"]
    assert [f.source_id for f in result.selected] == ["g"]
