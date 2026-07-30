"""End-to-end waterbody wiring through the pipeline (Item W3, Task Group 3).

Exercises the additive waterbody path: the validate stage loads areal-water
layers (only when the loader supports it), and generate_svg classifies +
selects them and folds their outlines into the SVG. A core guarantee: when the
loader has no waterbody support (or the feature is disabled) the render is
byte-identical to the river-only build.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import io
import zipfile

from rich.console import Console
from shapely.geometry import LineString, Polygon, box

from src.config import build_settings
from src.loading import Layer
from src.pipeline import Pipeline
from src.waterbody_selection import WaterbodySelection

BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)
NETWORK = (
    LineString([(-122.0, 43.0), (-121.0, 44.0)]),
    LineString([(-120.0, 43.0), (-121.0, 44.0)]),
    LineString([(-121.0, 44.0), (-121.0, 45.0)]),
)
# A lake polygon well inside the region boundary (EPSG:4326).
LAKE = Polygon(
    [(-121.6, 43.8), (-121.4, 43.8), (-121.4, 44.0), (-121.6, 44.0)]
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
    """River-only loader (no waterbody support)."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd":
            return [Layer("WBDHU4", "wbd", huc4, (BOUNDARY,), crs="EPSG:4326")]
        geoms = NETWORK if huc4 == "1707" else ()
        return [Layer("NHDFlowline", dataset_id, huc4, geoms, crs="EPSG:4326")]


class WaterbodyLoader(NetworkLoader):
    """Adds a single classified LakePond polygon in HUC 1707."""

    def load_waterbody_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd" or huc4 != "1707":
            return []
        return [
            Layer(
                "NHDWaterbody",
                dataset_id,
                huc4,
                (LAKE,),
                crs="EPSG:4326",
                attributes=(
                    {"FType": 390, "GNIS_Name": "Test Lake", "Permanent_Identifier": "lake-1"},
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


def test_loader_without_waterbody_support_has_no_group(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    svg = _pipeline(tmp_path, NetworkLoader()).run(settings).artifacts["svg"]
    assert 'id="waterbodies"' not in svg


def test_disabled_waterbodies_build_is_byte_identical(tmp_path):
    enabled = build_settings({"region": ["Oregon"]})
    disabled = build_settings(
        {"region": ["Oregon"], "waterbodies": {"enabled": False}}
    )
    river_only = _pipeline(tmp_path, NetworkLoader()).run(enabled).artifacts["svg"]
    with_loader_off = (
        _pipeline(tmp_path, WaterbodyLoader()).run(disabled).artifacts["svg"]
    )
    assert with_loader_off == river_only
    assert 'id="waterbodies"' not in with_loader_off


def test_enabled_waterbodies_render_outlines(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path, WaterbodyLoader()).run(settings)
    svg = context.artifacts["svg"]
    root = ET.fromstring(svg)  # well-formed

    wb = root.find(".//*[@id='waterbodies']")
    assert wb is not None, "expected a waterbodies <g> layer"
    outline = root.find(".//*[@id='waterbody_lake-1_outline']")
    assert outline is not None
    assert outline.get("d", "").count("Z") == 1


def test_waterbody_selection_stashed_in_artifacts(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path, WaterbodyLoader()).run(settings)
    selection = context.artifacts["waterbody_selection"]
    assert isinstance(selection, WaterbodySelection)
    assert selection.counts["selected"] == 1
    assert selection.selected[0].wb_class == "lake"
