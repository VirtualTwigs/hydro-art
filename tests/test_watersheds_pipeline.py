"""End-to-end build_graph->compute_watersheds through the pipeline (Item #6, TG3).

Reuses the offline fake downloader/loader pattern so the compute_watersheds
stage runs on a real (reprojected, clipped) in-region network — stream orders
and HUC groups land in artifacts without GDAL or real data.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, box

from src.config import build_settings
from src.loading import Layer
from src.pipeline import Pipeline

BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)
# Two headwaters join at a confluence, then flow to an outlet — all in-region.
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


def test_pipeline_computes_orders_and_watersheds(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    stream_orders = context.artifacts["stream_orders"]
    watersheds = context.artifacts["watersheds"]
    max_order = context.artifacts["max_stream_order"]

    # Three segments ordered; the confluence yields a Strahler max of 2.
    assert len(stream_orders) == 3
    assert max_order == 2
    # All segments inherit HUC4 1707 -> a single watershed at the default level.
    assert watersheds == {"1707": {0, 1, 2}}


def test_pipeline_respects_selected_method_and_level(tmp_path):
    settings = build_settings(
        {"region": ["Oregon"], "stream_method": "shreve", "huc_level": "HUC2"}
    )
    context = _pipeline(tmp_path).run(settings)

    # Shreve magnitude sums at the confluence: 1 + 1 -> 2 for the outlet stem.
    assert context.artifacts["max_stream_order"] == 2
    orders = context.artifacts["stream_orders"]
    assert sorted(orders.values()) == [1, 1, 2]
    # HUC2 truncates 1707 -> "17".
    assert context.artifacts["watersheds"] == {"17": {0, 1, 2}}
