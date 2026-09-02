"""End-to-end natural-feature wiring through the pipeline (Item 64, Group 5).

Exercises the additive point/areal path: the validate stage loads NHDPoint
layers (only when enabled AND the loader supports it) and reuses the NHDWaterbody
load for areal classification; generate_svg selects + renders them into their own
`<g>` layers. Core guarantee: with features disabled (default), the render is
byte-identical to the river + waterbody build.
"""

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, Point, Polygon, box

from src.areal_selection import ArealSelection, PointSelection
from src.config import build_settings
from src.loading import Layer
from src.pipeline import Pipeline

BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)
NETWORK = (
    LineString([(-122.0, 43.0), (-121.0, 44.0)]),
    LineString([(-120.0, 43.0), (-121.0, 44.0)]),
    LineString([(-121.0, 44.0), (-121.0, 45.0)]),
)
# A marsh polygon (FType 466 SwampMarsh) inside the region boundary.
MARSH = Polygon([(-121.6, 43.8), (-121.4, 43.8), (-121.4, 44.0), (-121.6, 44.0)])
# A spring point (FType 458) inside the region boundary.
SPRING = Point(-121.5, 43.9)


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
    """River-only loader (no waterbody/point support)."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd":
            return [Layer("WBDHU4", "wbd", huc4, (BOUNDARY,), crs="EPSG:4326")]
        geoms = NETWORK if huc4 == "1707" else ()
        return [Layer("NHDFlowline", dataset_id, huc4, geoms, crs="EPSG:4326")]


class WaterbodyLoader(NetworkLoader):
    """Adds an NHDWaterbody marsh polygon (FType 466) in HUC 1707."""

    def load_waterbody_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDWaterbody",
                dataset_id,
                huc4,
                (MARSH,),
                crs="EPSG:4326",
                attributes=(
                    {"FType": 466, "GNIS_Name": "Test Marsh", "Permanent_Identifier": "marsh-1"},
                ),
            )
        ]


class PointLoader(WaterbodyLoader):
    """Also exposes an NHDPoint spring (FType 458) in HUC 1707."""

    def load_point_features(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDPoint",
                dataset_id,
                huc4,
                (SPRING,),
                crs="EPSG:4326",
                attributes=(
                    {"FType": 458, "GNIS_Name": "Test Spring", "Permanent_Identifier": "spring-1"},
                ),
            )
        ]


# Two springs ~4 km apart (in-region) + one spring well outside the boundary.
SPRING_NEAR = Point(-121.55, 43.9)
SPRING_FAR_EAST = Point(-100.0, 43.9)  # east of the region box → outside


class MultiPointLoader(WaterbodyLoader):
    """A dense in-region spring cluster plus one out-of-region spring."""

    def load_point_features(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDPoint",
                dataset_id,
                huc4,
                (SPRING, SPRING_NEAR, SPRING_FAR_EAST),
                crs="EPSG:4326",
                attributes=(
                    {"FType": 458, "Permanent_Identifier": "spring-1"},
                    {"FType": 458, "Permanent_Identifier": "spring-2"},
                    {"FType": 458, "Permanent_Identifier": "spring-out"},
                ),
            )
        ]


def _pipeline(tmp_path, loader):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / "output",
        downloader=FakeZipDownloader(),
        loader=loader,
    )


def test_disabled_features_build_is_byte_identical(tmp_path):
    # Default build (point/areal disabled) with a loader that CAN supply them.
    baseline = _pipeline(tmp_path, WaterbodyLoader()).run(
        build_settings({"region": ["Oregon"]})
    ).artifacts["svg"]
    with_capable_loader = _pipeline(tmp_path, PointLoader()).run(
        build_settings({"region": ["Oregon"]})
    ).artifacts["svg"]
    assert with_capable_loader == baseline
    assert 'id="point_features"' not in with_capable_loader
    assert 'id="areal_' not in with_capable_loader


def test_enabled_point_features_render_glyphs(tmp_path):
    settings = build_settings(
        {"region": ["Oregon"], "point_features": {"enabled": True}}
    )
    context = _pipeline(tmp_path, PointLoader()).run(settings)
    svg = context.artifacts["svg"]
    ET.fromstring(svg)  # well-formed

    assert '<g id="point_features">' in svg
    assert '<g id="point_spring"' in svg
    assert 'id="point_spring_spring-1"' in svg
    # Selection report stashed for auditability.
    selection = context.artifacts["point_selection"]
    assert isinstance(selection, PointSelection)
    assert selection.counts["selected"] == 1


def test_enabled_areal_features_render_group(tmp_path):
    settings = build_settings(
        {"region": ["Oregon"], "areal_features": {"enabled": True}}
    )
    context = _pipeline(tmp_path, PointLoader()).run(settings)
    svg = context.artifacts["svg"]
    root = ET.fromstring(svg)

    assert root.find(".//*[@id='areal_wetland']") is not None
    selection = context.artifacts["areal_selection"]
    assert isinstance(selection, ArealSelection)
    assert selection.counts["selected"] == 1
    assert selection.selected[0].ar_class == "wetland"


def test_areal_enabled_loads_waterbody_even_when_waterbodies_disabled(tmp_path):
    # areal reuses the NHDWaterbody load; it must load even if the waterbody
    # OUTLINE layer is turned off.
    settings = build_settings(
        {
            "region": ["Oregon"],
            "waterbodies": {"enabled": False},
            "areal_features": {"enabled": True},
        }
    )
    context = _pipeline(tmp_path, PointLoader()).run(settings)
    svg = context.artifacts["svg"]
    assert 'id="areal_wetland"' in svg
    # Waterbody outline layer stays off.
    assert 'id="waterbodies"' not in svg


def test_loader_without_point_seam_skips_gracefully(tmp_path):
    # point_features enabled, but the loader lacks load_point_features → no crash,
    # no point layer, render still valid.
    settings = build_settings(
        {"region": ["Oregon"], "point_features": {"enabled": True}}
    )
    context = _pipeline(tmp_path, WaterbodyLoader()).run(settings)
    svg = context.artifacts["svg"]
    assert 'id="point_features"' not in svg
    assert "point_layers" not in context.artifacts


def test_both_families_enabled_zorder_end_to_end(tmp_path):
    settings = build_settings(
        {
            "region": ["Oregon"],
            "point_features": {"enabled": True},
            "areal_features": {"enabled": True},
        }
    )
    svg = _pipeline(tmp_path, PointLoader()).run(settings).artifacts["svg"]
    ET.fromstring(svg)  # well-formed
    # Areal (default "below") sits before the flowlines; points (default "above")
    # sit after them — the spec's z-order over the existing river/waterbody art.
    assert svg.index('id="areal_wetland"') < svg.index('id="watershed_')
    assert svg.index('id="point_features"') > svg.index('id="watershed_')


def test_enabled_features_render_is_deterministic(tmp_path):
    settings = build_settings(
        {
            "region": ["Oregon"],
            "point_features": {"enabled": True},
            "areal_features": {"enabled": True},
        }
    )
    first = _pipeline(tmp_path / "a", PointLoader()).run(settings).artifacts["svg"]
    second = _pipeline(tmp_path / "b", PointLoader()).run(settings).artifacts["svg"]
    assert first == second


def test_point_preset_thins_dense_cluster_end_to_end(tmp_path):
    # No thinning (default spacing 0): both in-region springs survive; the
    # out-of-region one is clipped away.
    plain = _pipeline(tmp_path / "plain", MultiPointLoader()).run(
        build_settings({"region": ["Oregon"], "point_features": {"enabled": True}})
    )
    assert plain.artifacts["point_selection"].counts["selected"] == 2

    # print-state preset (wide min-spacing) collapses the ~4 km cluster to one.
    thinned = _pipeline(tmp_path / "thin", MultiPointLoader()).run(
        build_settings(
            {
                "region": ["Oregon"],
                "point_features": {"enabled": True, "preset": "print-state"},
            }
        )
    )
    assert thinned.artifacts["point_selection"].counts["selected"] == 1


def test_point_outside_boundary_dropped_end_to_end(tmp_path):
    context = _pipeline(tmp_path, MultiPointLoader()).run(
        build_settings({"region": ["Oregon"], "point_features": {"enabled": True}})
    )
    selection = context.artifacts["point_selection"]
    kept_ids = {feat.source_id for feat in selection.selected}
    assert "spring-out" not in kept_ids
    assert any(reason for feat in selection.excluded
               for reason in [feat.inclusion_reason] if "boundary" in reason)
