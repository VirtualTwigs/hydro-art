"""Waterbody geographic-QA fixtures (Item W4, Task Group 4 — offline slice).

Acceptance-criterion-1 checks that exercise the whole selection→render path on
hand-built geometries: holes and multipolygons survive into the SVG outline,
conservative coast policy drops clip-boundary fragments end-to-end, and shared
polygon edges are reported rather than silently double-dropped. Real-region
validation (Clark County / Oregon / Washington) lives in ``tools/waterbody_qa.py``
because it needs GDAL + the NAS datasets; these stay fully offline.
"""

import xml.etree.ElementTree as ET

from shapely.geometry import LineString, MultiPolygon, Polygon, box

from src.rendering import render_svg
from src.waterbodies import WaterbodyFeature
from src.waterbody_selection import (
    WaterbodySelectionPolicy,
    process_waterbodies,
)

# Minimal river network shared by the render-level QA cases.
_GEOMS = {1: LineString([(0, 0), (100, 100)])}
_COLORS = {1: "#ff0000"}
_WSHEDS = {"1701": {1}}


def _square(x0, y0, size):
    return Polygon(
        [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]
    )


def _feature(source_id, geom, wb_class):
    """A pre-classified inland feature in EPSG:5070 (reproject is a no-op)."""
    return WaterbodyFeature(
        source_id=source_id,
        source_layer="NHDWaterbody",
        dataset_id="nhdplus_hr",
        huc4="1701",
        geometry=geom,
        ftype=390,
        fcode=39004,
        name=None,
        wb_class=wb_class,
        source_crs="EPSG:5070",
    )


def _render_selection(selection):
    items = [
        (f.source_id, f.geometry, f.wb_class) for f in selection.selected
    ]
    return render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=items or None)


def test_waterbodies_group_declares_linejoin():
    items = [("a", _square(0, 0, 20), "lake")]
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=items)
    group = svg.split('id="waterbodies"')[1].split(">")[0]
    assert 'stroke-linejoin="round"' in group
    assert 'stroke-linecap="round"' in group


def test_hole_survives_into_outline_path():
    donut = Polygon(
        [(0, 0), (100, 0), (100, 100), (0, 100)],
        [[(40, 40), (60, 40), (60, 60), (40, 60)]],
    )
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=[("lk", donut, "lake")])
    root = ET.fromstring(svg)
    path = root.find(".//*[@id='waterbody_lk_outline']")
    d = path.get("d")
    # Exterior + interior ring → two closed subpaths.
    assert d.count("M") == 2
    assert d.count("Z") == 2


def test_multipolygon_renders_one_group_with_multiple_subpaths():
    multi = MultiPolygon([_square(0, 0, 10), _square(50, 50, 10)])
    svg = render_svg(_GEOMS, _COLORS, _WSHEDS, waterbodies=[("mp", multi, "lake")])
    root = ET.fromstring(svg)
    groups = root.findall(".//*[@id='waterbody_mp']")
    assert len(groups) == 1  # one source feature → one group
    d = root.find(".//*[@id='waterbody_mp_outline']").get("d")
    assert d.count("M") == 2  # two parts, one path


def test_coastal_clip_fragment_excluded_but_inland_lake_kept():
    boundary = box(0, 0, 100, 100)
    lake = _feature("lake-1", _square(20, 20, 30), "lake")
    # Bay straddles the boundary → conservative policy drops the fragment.
    bay = _feature("bay-1", _square(80, 80, 40), "bay")
    selection = process_waterbodies(
        [lake, bay],
        boundary=boundary,
        policy=WaterbodySelectionPolicy(coastal_mode="conservative"),
    )
    kept = {f.source_id for f in selection.selected}
    dropped = {f.source_id for f in selection.excluded}
    assert kept == {"lake-1"}
    assert "bay-1" in dropped

    svg = _render_selection(selection)
    assert 'id="waterbody_lake-1_outline"' in svg
    assert "waterbody_bay-1" not in svg


def test_shared_edge_pairs_reported_not_silently_dropped():
    # Two lakes sharing the x=10 edge; both must survive, overlap reported.
    left = _feature("L", _square(0, 0, 10), "lake")
    right = _feature("R", _square(10, 0, 10), "lake")
    selection = process_waterbodies([left, right])
    assert selection.shared_edge_pairs == 1
    assert {f.source_id for f in selection.selected} == {"L", "R"}
    flagged = {f.source_id for f in selection.selected if "shared_edge" in f.qa_flags}
    assert flagged == {"L", "R"}

    svg = _render_selection(selection)
    assert 'id="waterbody_L_outline"' in svg
    assert 'id="waterbody_R_outline"' in svg
