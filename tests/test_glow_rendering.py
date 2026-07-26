"""Tests for optional glow in render_svg (Item #9, Task Group 2)."""

import xml.etree.ElementTree as ET

from shapely.geometry import LineString

from src.rendering import render_svg

GEOMS = {
    0: LineString([(0.0, 0.0), (10.0, 0.0)]),
    1: LineString([(10.0, 0.0), (10.0, 20.0)]),
    2: LineString([(10.0, 20.0), (30.0, 20.0)]),
}
SEGMENT_COLORS = {0: "#00ffff", 1: "#00ffff", 2: "#ff00ff"}
WATERSHEDS = {"A": {0, 1}, "B": {2}}


def _render(**kw):
    return render_svg(GEOMS, SEGMENT_COLORS, WATERSHEDS, **kw)


def test_glow_off_is_byte_identical_to_default():
    # Backward compatibility: glow=False must not change item #8 output.
    assert _render(glow=False) == _render()
    assert "hydro-glow" not in _render(glow=False)
    assert "_glow" not in _render(glow=False)


def test_blur_glow_adds_filter_and_references_it():
    svg = _render(glow=True, glow_mode="blur", glow_radius=3.0)
    root = ET.fromstring(svg)
    blur = root.find(".//*[@id='hydro-glow']/*")
    assert blur.tag.endswith("feGaussianBlur")
    assert blur.get("stdDeviation") == "3"
    # Every river group references the filter.
    river_groups = [g for g in root if g.get("id", "").startswith(("watershed_", "rivers_"))]
    assert river_groups
    assert all(g.get("filter") == "url(#hydro-glow)" for g in river_groups)
    # No pure-vector halo groups in blur mode.
    assert "_glow" not in svg.replace("hydro-glow", "")


def test_vector_glow_adds_halo_groups_before_sharp_groups():
    svg = _render(glow=True, glow_mode="vector", glow_radius=2.0, line_width=0.35)
    # A halo group exists and comes before its sharp counterpart.
    assert svg.index('id="watershed_A_glow"') < svg.index('id="watershed_A"')
    root = ET.fromstring(svg)
    halo = root.find(".//*[@id='watershed_A_glow']")
    assert halo.get("stroke") == "#00ffff"
    # Halo is wider than the base stroke and semi-transparent; no filter used.
    assert float(halo.get("stroke-width")) > 0.35
    assert 0.0 < float(halo.get("stroke-opacity")) < 1.0
    assert "hydro-glow" not in svg
    # Halo carries the same number of paths as the sharp group.
    sharp = root.find(".//*[@id='watershed_A']")
    assert len([p for p in halo if p.tag.endswith("path")]) == len(
        [p for p in sharp if p.tag.endswith("path")]
    )


def test_glow_is_deterministic_per_mode():
    assert _render(glow=True, glow_mode="blur") == _render(glow=True, glow_mode="blur")
    assert _render(glow=True, glow_mode="vector") == _render(glow=True, glow_mode="vector")
