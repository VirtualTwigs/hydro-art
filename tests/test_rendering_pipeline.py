"""End-to-end generate_svg through the pipeline (Item #8, TG3).

Reuses the offline fake downloader/loader pattern so the generate_svg stage runs
on a real (reprojected, clipped, graphed, grouped, colored) in-region network —
a layered SVG string lands in artifacts without GDAL, a browser, or real data.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import io
import zipfile

from rich.console import Console
from shapely.geometry import LineString, box

import pytest

from src.config import ConfigError, build_settings
from src.loading import Layer
from src.pipeline import Pipeline

BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)
NETWORK = (
    LineString([(-122.0, 43.0), (-121.0, 44.0)]),
    LineString([(-120.0, 43.0), (-121.0, 44.0)]),
    LineString([(-121.0, 44.0), (-121.0, 45.0)]),
)


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


def _pipeline(tmp_path):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / "output",
        downloader=FakeZipDownloader(),
        loader=NetworkLoader(),
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
    assert max(widths) == 3.0
    assert min(widths) == 0.5
    assert max(widths) > min(widths)


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
