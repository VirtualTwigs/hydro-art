"""End-to-end generate_svg through the pipeline (Item #8, TG3).

Reuses the offline fake downloader/loader pattern so the generate_svg stage runs
on a real (reprojected, clipped, graphed, grouped, colored) in-region network —
a layered SVG string lands in artifacts without GDAL, a browser, or real data.
"""

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from rich.console import Console
from shapely.geometry import LineString, Point, box

from src.config import ConfigError, build_settings
from src.loading import Layer
from src.pipeline import Pipeline

BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)
NETWORK = (
    LineString([(-122.0, 43.0), (-121.0, 44.0)]),
    LineString([(-120.0, 43.0), (-121.0, 44.0)]),
    LineString([(-121.0, 44.0), (-121.0, 45.0)]),
)

# Engineered-water structures for Epoch 16 (Item #67, TG3) — one per source
# layer, all inside BOUNDARY. FType codes drive classification in
# src.hydro_structures: 343 DamWeir (line), 367 Gaging Station (point),
# 455 Spillway (area polygon).
DAM_LINE = LineString([(-121.5, 43.5), (-121.4, 43.6)])
GAGE_POINT = Point(-121.2, 43.8)
SPILLWAY_POLY = box(-121.3, 43.2, -121.2, 43.3)


class FakeZipDownloader:
    def fetch(self, descriptor, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{descriptor.huc4}.gdb", b"data")
        dest.write_bytes(buf.getvalue())
        return dest


class NetworkLoader:
    def load_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd":
            return [Layer("WBDHU4", "wbd", huc4, (BOUNDARY,), crs="EPSG:4326")]
        geoms = NETWORK if huc4 == "1707" else ()
        return [Layer("NHDFlowline", dataset_id, huc4, geoms, crs="EPSG:4326")]


class StructureLoader(NetworkLoader):
    """A NetworkLoader that also serves NHDLine/NHDPoint/NHDArea structures.

    The line/point/area loads mirror the real PyogrioLayerLoader seams. Only the
    hydrography-dataset HUC4 (1707) carries structures, matching the flowlines.
    """

    def load_line_features(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDLine",
                dataset_id,
                huc4,
                (DAM_LINE,),
                crs="EPSG:4326",
                attributes=({"FType": 343, "Permanent_Identifier": "dam1"},),
            )
        ]

    def load_point_features(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDPoint",
                dataset_id,
                huc4,
                (GAGE_POINT,),
                crs="EPSG:4326",
                attributes=({"FType": 367, "Permanent_Identifier": "gage1"},),
            )
        ]

    def load_waterbody_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDArea",
                dataset_id,
                huc4,
                (SPILLWAY_POLY,),
                crs="EPSG:4326",
                attributes=({"FType": 455, "Permanent_Identifier": "spill1"},),
            )
        ]


def _pipeline(tmp_path, loader=None):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / "output",
        downloader=FakeZipDownloader(),
        loader=loader or NetworkLoader(),
    )


def test_pipeline_generates_layered_colored_svg(tmp_path):
    settings = build_settings({"region": ["Oregon"], "background": "#000000"})
    context = _pipeline(tmp_path).run(settings)

    svg = context.artifacts["svg"]
    root = ET.fromstring(svg)  # well-formed
    assert root.tag.endswith("svg")

    # Background layer painted with the configured color.
    bg = root.find(".//*[@id='background']/*")
    assert bg.get("fill") == "#000000"

    # At least one watershed layer, holding colored river paths.
    groups = [g for g in root if g.get("id", "").startswith("watershed_")]
    assert groups, "expected at least one watershed <g> layer"
    total_paths = sum(len([c for c in g if c.tag.endswith("path")]) for g in groups)
    assert total_paths == 3  # the three NETWORK segments
    # Group stroke is a real neon hex color from item #7.
    assert all(g.get("stroke", "").startswith("#") for g in groups)


def test_pipeline_svg_is_deterministic(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    first = _pipeline(tmp_path).run(settings).artifacts["svg"]
    second = _pipeline(tmp_path).run(settings).artifacts["svg"]
    assert first == second


def _paths(svg):
    root = ET.fromstring(svg)
    return [p for g in root for p in g if p.tag.endswith("path")]


def test_default_render_uniform_has_no_per_path_widths(tmp_path):
    # Byte-identical baseline: color_by=watershed + width_by=uniform (the
    # defaults) render the current code path — no per-path stroke-width attrs.
    settings = build_settings({"region": ["Oregon"]})
    svg = _pipeline(tmp_path).run(settings).artifacts["svg"]
    assert all(p.get("stroke-width") is None for p in _paths(svg))


def test_color_by_single_paints_every_flowline_one_color(tmp_path):
    settings = build_settings(
        {"region": ["Oregon"], "color_by": "single", "single_color": "#ff00ff"}
    )
    context = _pipeline(tmp_path).run(settings)
    svg = context.artifacts["svg"]
    root = ET.fromstring(svg)
    groups = [g for g in root if g.get("id", "").startswith("watershed_")]
    assert groups
    assert all(g.get("stroke") == "#ff00ff" for g in groups)
    # No stray per-segment stroke overrides — the whole network is one color.
    assert all(p.get("stroke") in (None, "#ff00ff") for p in _paths(svg))


def test_color_by_elevation_raises_without_metric_data(tmp_path):
    settings = build_settings({"region": ["Oregon"], "color_by": "elevation"})
    with pytest.raises(ConfigError, match="elevation"):
        _pipeline(tmp_path).run(settings)


def test_width_by_flow_scales_stroke_widths(tmp_path):
    settings = build_settings(
        {
            "region": ["Oregon"],
            "width_by": "flow",
            "width_min": 0.5,
            "width_max": 3.0,
        }
    )
    svg = _pipeline(tmp_path).run(settings).artifacts["svg"]
    widths = [float(p.get("stroke-width")) for p in _paths(svg)]
    assert widths, "expected per-path stroke widths under width_by=flow"
    # The confluence mainstem (higher stream order) is the widest channel.
    # Absolute values are in document units (projected meters scaled by
    # units_per_px), so assert the ratio matches the configured min/max.
    assert max(widths) > min(widths)
    assert max(widths) / min(widths) == pytest.approx(3.0 / 0.5, rel=1e-3)


def test_stroke_width_scales_with_viewbox_extent(tmp_path):
    """Regression: stroke widths must be in document units, not raw pixel values.

    The SVG viewBox is in EPSG:5070 projected meters (tens of thousands of
    units). A raw 0.35px stroke in that coordinate space becomes sub-pixel
    (~0.003px) when rasterised to 2048px, producing a blank black image.
    The pipeline must scale line_width by units_per_px so strokes are visible.
    """
    settings = build_settings({"region": ["Oregon"], "line_width": 0.35})
    svg = _pipeline(tmp_path).run(settings).artifacts["svg"]
    root = ET.fromstring(svg)

    # Parse the viewBox width (projected meters).
    vb = root.get("viewBox").split()
    viewbox_width = float(vb[2])

    # The root stroke-width attribute should be scaled to document units,
    # not the raw 0.35 pixel value.
    base_stroke = float(root.get("stroke-width"))
    assert viewbox_width > 1000, "viewBox should be in projected meters"
    # At 2048px reference, a 0.35px stroke → ~0.35 * (viewbox_width / 2048).
    # Assert it's at least 1 document unit (i.e. visibly scaled).
    assert base_stroke > 1.0, (
        f"stroke-width {base_stroke} is too small for viewBox width "
        f"{viewbox_width} — strokes will be invisible when rasterised"
    )


def test_stroke_width_tracks_png_size(tmp_path):
    """Smaller png_size → thicker document-unit strokes (fewer pixels to fill)."""
    svg_small = _pipeline(tmp_path).run(
        build_settings({"region": ["Oregon"], "png_size": 512})
    ).artifacts["svg"]
    svg_large = _pipeline(tmp_path).run(
        build_settings({"region": ["Oregon"], "png_size": 4096})
    ).artifacts["svg"]
    root_s = ET.fromstring(svg_small)
    root_l = ET.fromstring(svg_large)
    stroke_small = float(root_s.get("stroke-width"))
    stroke_large = float(root_l.get("stroke-width"))
    # 512px render needs wider document-unit strokes than 4096px.
    assert stroke_small > stroke_large


def test_generate_svg_feeds_downstream_stages(tmp_path):
    import warnings

    settings = build_settings({"region": ["Oregon"]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        context = _pipeline(tmp_path).run(settings)
    # generate_svg produced the SVG the optimize + export stages consume.
    assert "svg" in context.artifacts
    assert "optimized_svg" in context.artifacts
    assert "export_paths" in context.artifacts


# --- Epoch 16, Item #67 TG3: hydro-structure pipeline integration ------------


def _hydro_group(svg):
    root = ET.fromstring(svg)
    return root.find(".//*[@id='hydro_structures']")


def test_hydro_structures_enabled_renders_all_three_source_layers(tmp_path):
    # A structure-aware loader yields NHDLine (dam) + NHDPoint (gage) + NHDArea
    # (spillway); with hydro_structures enabled they select, clip, and land in a
    # dedicated <g id="hydro_structures"> group above the water.
    settings = build_settings(
        {"region": ["Oregon"], "hydro_structures": {"enabled": True}}
    )
    context = _pipeline(tmp_path, loader=StructureLoader()).run(settings)
    svg = context.artifacts["svg"]

    group = _hydro_group(svg)
    assert group is not None, "expected a <g id='hydro_structures'> group"

    # All three structure classes rendered, one per source layer.
    class_ids = {g.get("id") for g in group}
    assert "hydro_dam_weir" in class_ids  # NHDLine
    assert "hydro_gaging_station" in class_ids  # NHDPoint
    assert "hydro_spillway" in class_ids  # NHDArea polygon

    selection = context.artifacts["hydro_structure_selection"]
    assert selection.counts["selected"] == 3


def test_hydro_structures_disabled_is_byte_identical_to_baseline(tmp_path):
    # Default (disabled) build must be byte-for-byte identical to a build with no
    # hydro_structures config at all — no line_layers load, no structure markup.
    baseline_settings = build_settings({"region": ["Oregon"]})
    baseline = _pipeline(tmp_path, loader=StructureLoader()).run(baseline_settings)

    disabled_settings = build_settings(
        {"region": ["Oregon"], "hydro_structures": {"enabled": False}}
    )
    disabled = _pipeline(tmp_path, loader=StructureLoader()).run(disabled_settings)

    assert disabled.artifacts["svg"] == baseline.artifacts["svg"]
    assert "line_layers" not in disabled.artifacts
    assert "hydro_structure_selection" not in disabled.artifacts
    assert _hydro_group(disabled.artifacts["svg"]) is None


def test_hydro_structures_only_still_loads_point_and_area(tmp_path):
    # Enabling ONLY hydro_structures (point_features + areal_features +
    # waterbodies all OFF) must still pull NHDPoint and NHDArea via the widened
    # shared loads so point/area structures appear.
    settings = build_settings(
        {
            "region": ["Oregon"],
            "waterbodies": {"enabled": False},
            "hydro_structures": {"enabled": True},
        }
    )
    assert not settings.point_features.enabled
    assert not settings.areal_features.enabled
    assert not settings.waterbodies.enabled

    context = _pipeline(tmp_path, loader=StructureLoader()).run(settings)
    assert "point_layers" in context.artifacts  # shared NHDPoint load reused
    assert "waterbody_layers" in context.artifacts  # shared NHDArea load reused

    group = _hydro_group(context.artifacts["svg"])
    class_ids = {g.get("id") for g in group}
    assert "hydro_gaging_station" in class_ids  # point structure appeared
    assert "hydro_spillway" in class_ids  # area structure appeared


# --- Epoch 16, Item #67 TG4.1: complementarity / no double-draw --------------


# A spring point (FType 458 -> point_features) and a wetland polygon (FType 466
# -> areal_features), disjoint from the structure codes (367 gaging, 455
# spillway). Placed inside BOUNDARY, distinct from the structure geometries.
SPRING_POINT = Point(-121.6, 43.4)
WETLAND_POLY = box(-121.9, 43.1, -121.8, 43.2)


class MixedFeatureLoader(StructureLoader):
    """NHDPoint/NHDArea loads each carry a structure AND a natural feature.

    NHDPoint -> a gaging station (367, structure) + a spring (458, point
    feature). NHDArea -> a spillway (455, structure) + a wetland (466, areal
    feature). Because the structure taxonomy's included codes are disjoint from
    the point/areal taxonomies' codes, each geometry is owned by exactly one
    taxonomy and must draw under exactly one layer.
    """

    def load_point_features(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDPoint",
                dataset_id,
                huc4,
                (GAGE_POINT, SPRING_POINT),
                crs="EPSG:4326",
                attributes=(
                    {"FType": 367, "Permanent_Identifier": "gage1"},
                    {"FType": 458, "Permanent_Identifier": "spring1"},
                ),
            )
        ]

    def load_waterbody_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDArea",
                dataset_id,
                huc4,
                (SPILLWAY_POLY, WETLAND_POLY),
                crs="EPSG:4326",
                attributes=(
                    {"FType": 455, "Permanent_Identifier": "spill1"},
                    {"FType": 466, "Permanent_Identifier": "wetland1"},
                ),
            )
        ]


def test_shared_loads_are_complementary_no_double_draw(tmp_path):
    # With hydro_structures, point_features, and areal_features ALL enabled over
    # a shared NHDPoint/NHDArea load that mixes structure and natural-feature
    # codes, each geometry must render under exactly ONE taxonomy: the disjoint
    # code tables guarantee no double-draw.
    settings = build_settings(
        {
            "region": ["Oregon"],
            "hydro_structures": {"enabled": True},
            "point_features": {"enabled": True},
            "areal_features": {"enabled": True},
        }
    )
    context = _pipeline(tmp_path, loader=MixedFeatureLoader()).run(settings)
    svg = context.artifacts["svg"]

    # The spillway (455) draws ONLY as a structure, never as an areal feature.
    assert "hydro_spillway_spill1" in svg
    assert "areal_wetland_spill1" not in svg
    # The wetland (466) draws ONLY as an areal feature, never as a structure.
    assert "areal_wetland_wetland1" in svg
    assert "hydro_spillway_wetland1" not in svg
    assert "hydro_" not in svg.split('id="areal_features"')[1].split("</g>")[0] \
        if 'id="areal_features"' in svg else True

    # The gaging station (367) draws ONLY as a structure, never as a point glyph.
    assert "hydro_gaging_station_gage1" in svg
    assert "point_spring_gage1" not in svg
    # The spring (458) draws ONLY as a point glyph, never as a structure.
    assert "point_spring_spring1" in svg
    assert "hydro_gaging_station_spring1" not in svg

    # Selection reports agree: structures selected exactly the two structure
    # geometries (dam via NHDLine + gage + spillway), not the natural features.
    struct_ids = {f.source_id for f in context.artifacts["hydro_structure_selection"].selected}
    assert "spring1" not in struct_ids and "wetland1" not in struct_ids
    assert {"gage1", "spill1", "dam1"} <= struct_ids
