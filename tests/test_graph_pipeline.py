"""End-to-end clip->build_graph through the pipeline (Item #5, TG3).

A fake downloader satisfies download/extract and a fake loader yields a WBD
boundary plus a small in-region river network, so graph construction runs on
real (reprojected, clipped) geometry without GDAL or real data.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, box

from src.config import build_settings
from src.graph import HydroGraph, NetworkStats
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
    """WBD boundary for wbd datasets; the network only in HUC4 1707."""

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


def test_pipeline_builds_graph_from_clipped_flowlines(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    graph = context.artifacts["hydro_graph"]
    stats = context.artifacts["network_stats"]
    assert isinstance(graph, HydroGraph)
    assert isinstance(stats, NetworkStats)
    assert stats.num_edges == 3
    assert stats.num_nodes == 4
    assert stats.num_sources == 2
    assert stats.num_outlets == 1
    assert graph.statistics() == stats


def test_pipeline_graph_supports_basin_extraction(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)
    graph = context.artifacts["hydro_graph"]

    (outlet,) = graph.outlets()
    # The whole network drains to the single outlet.
    assert graph.basin(outlet) == {0, 1, 2}
    assert graph.upstream(outlet) == set(graph.digraph.nodes) - {outlet}
