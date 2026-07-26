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

from src.config import build_settings
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


def test_downstream_stages_remain_stubs(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)
    # generate_svg produced output; optimize/export haven't (still stubs).
    assert "svg" in context.artifacts
    assert "optimized_svg" not in context.artifacts
    assert "export_paths" not in context.artifacts
