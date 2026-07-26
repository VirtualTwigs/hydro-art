"""End-to-end load->validate->repair through the pipeline (Item #3, TG3).

Runs the real validate/repair stages offline via a fake downloader (for the
upstream download/extract stages) and a fake loader that yields in-memory
geometries, so the geometry pipeline is exercised without GDAL or real data.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, MultiLineString, Polygon

from src.config import build_settings
from src.geometry import RepairStats
from src.loading import Layer
from src.pipeline import Pipeline


class FakeZipDownloader:
    def fetch(self, descriptor, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{descriptor.huc4}.gdb", b"data")
        dest.write_bytes(buf.getvalue())
        return dest


class DirtyLayerLoader:
    """Yields one flowline layer per dataset dir with mixed-quality geometry."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        geoms = (
            LineString([(0, 0), (1, 1), (2, 2)]),               # clean
            LineString([(0, 0), (0, 0), (1, 1)]),               # dup vertex
            LineString(),                                        # empty
            Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)]),  # invalid bowtie
            MultiLineString([[(3, 3), (4, 4)]]),                # singleton multipart
        )
        return [Layer("NHDFlowline", dataset_id, huc4, geoms)]


def _pipeline(tmp_path):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        downloader=FakeZipDownloader(),
        loader=DirtyLayerLoader(),
    )


def test_pipeline_loads_validates_and_repairs(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    layers = context.artifacts["layers"]
    assert layers, "validate stage should load layers"
    assert all(layer.name == "NHDFlowline" for layer in layers)

    stats = context.artifacts["repair_stats"]
    assert isinstance(stats, RepairStats)
    n_layers = len(layers)
    # Each layer contributes: 1 empty dropped, 1 dup vertex, 1 invalid fixed,
    # 1 multipart normalized, and 4 of 5 geometries survive.
    assert stats.empties_dropped == n_layers
    assert stats.invalid_fixed == n_layers
    assert stats.duplicate_vertices_removed == n_layers
    assert stats.multipart_normalized == n_layers
    assert stats.total_out == stats.total_in - n_layers


def test_repaired_layers_contain_only_valid_geometries(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)

    repaired = context.artifacts["repaired_layers"]
    assert repaired
    for layer in repaired:
        assert layer.geometries  # survivors present
        assert all(g.is_valid and not g.is_empty for g in layer.geometries)
