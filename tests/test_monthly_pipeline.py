"""Pipeline behavior for the ``--months`` option (Item #25, Task Group 5).

A non-annual ``--months`` fails fast in ``generate_svg`` because the 2D pipeline
does not load per-reach monthly discharge/climatology (same limitation as
``color_by=elevation``); the annual default (``months == ()``) builds an SVG
unchanged. Reuses the offline fake downloader/loader harness — no GDAL, no
network, no real data.
"""

import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from rich.console import Console
from shapely.geometry import LineString, box

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


def test_non_annual_months_fails_fast(tmp_path):
    settings = build_settings({"region": ["Oregon"], "months": "jul"})
    assert settings.months == (7,)
    with pytest.raises(ConfigError, match="months"):
        _pipeline(tmp_path).run(settings)


def test_annual_default_builds_svg(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    assert settings.months == ()
    svg = _pipeline(tmp_path).run(settings).artifacts["svg"]
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    groups = [g for g in root if g.get("id", "").startswith("watershed_")]
    assert groups
