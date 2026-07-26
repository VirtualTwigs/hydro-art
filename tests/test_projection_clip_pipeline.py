"""End-to-end repair->reproject->clip through the pipeline (Item #4, TG3).

Runs the real reproject/clip stages offline: a fake downloader satisfies the
upstream download/extract stages and a fake loader yields in-memory layers
carrying a CRS plus a WBD boundary layer, so projection + clipping are
exercised without GDAL or real data.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, box

from src.config import build_settings
from src.loading import Layer
from src.pipeline import Pipeline

# A boundary roughly covering the Pacific Northwest (lon/lat).
BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)
INSIDE = LineString([(-122.0, 44.0), (-121.0, 45.0)])
CROSSING = LineString([(-126.0, 44.0), (-122.0, 44.0)])   # half west of -124
OUTSIDE = LineString([(-110.0, 40.0), (-108.0, 39.0)])    # far east


class FakeZipDownloader:
    def fetch(self, descriptor, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{descriptor.huc4}.gdb", b"data")
        dest.write_bytes(buf.getvalue())
        return dest


class GeoLoader:
    """Yields a WBD boundary for wbd datasets and flowlines otherwise."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd":
            return [Layer("WBDHU4", "wbd", huc4, (BOUNDARY,), crs="EPSG:4326")]
        return [
            Layer(
                "NHDFlowline",
                dataset_id,
                huc4,
                (INSIDE, CROSSING, OUTSIDE),
                crs="EPSG:4326",
            )
        ]


def _pipeline(tmp_path):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        downloader=FakeZipDownloader(),
        loader=GeoLoader(),
    )


def test_pipeline_reprojects_all_layers_to_settings_projection(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    projected = context.artifacts["projected_layers"]
    assert projected
    assert all(layer.crs == "EPSG:5070" for layer in projected)


def test_pipeline_clips_flowlines_to_region_boundary(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    assert context.artifacts["region_boundary"] is not None
    stats = context.artifacts["clip_stats"]
    # Per flowline layer: 1 inside kept, 1 crossing trimmed, 1 outside dropped.
    n_flow = sum(
        1 for layer in context.artifacts["projected_layers"]
        if layer.dataset_id != "wbd"
    )
    assert stats.total_in == 3 * n_flow
    assert stats.dropped_outside == n_flow
    assert stats.clipped_partial == n_flow
    assert stats.total_out == 2 * n_flow

    # Boundary (WBD) layers pass through unchanged.
    wbd_layers = [
        layer for layer in context.artifacts["clipped_layers"]
        if layer.dataset_id == "wbd"
    ]
    assert wbd_layers
