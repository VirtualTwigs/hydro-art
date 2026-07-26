"""End-to-end assign_colors through the pipeline (Item #7, TG3).

Reuses the offline fake downloader/loader pattern so the assign_colors stage runs
on a real (reprojected, clipped, graphed, grouped) in-region network — watershed
and segment colors land in artifacts without GDAL or real data.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, box

from src.coloring import PALETTES
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


def test_pipeline_assigns_watershed_and_segment_colors(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    watershed_colors = context.artifacts["watershed_colors"]
    segment_colors = context.artifacts["segment_colors"]

    # One watershed (1707) colored; all three segments inherit its color.
    assert set(watershed_colors) == {"1707"}
    assert set(segment_colors) == {0, 1, 2}
    assert all(color in PALETTES["neon"] for color in segment_colors.values())
    assert context.artifacts["palette"] == "neon"


def test_pipeline_coloring_is_deterministic(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    first = _pipeline(tmp_path).run(settings).artifacts
    second = _pipeline(tmp_path).run(settings).artifacts
    assert first["watershed_colors"] == second["watershed_colors"]
    assert first["segment_colors"] == second["segment_colors"]
