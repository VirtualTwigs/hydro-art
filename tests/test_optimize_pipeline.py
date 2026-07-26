"""End-to-end optimize_svg through the pipeline (Item #9, TG3).

Reuses the offline fake downloader/loader pattern so the optimize_svg stage runs
on a real (rendered) SVG string. A fake optimizer is injected to verify the
wiring deterministically without depending on Node/SVGO being installed.
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


class FakeOptimizer:
    """Records the SVG it received and returns a sentinel-tagged string."""

    def __init__(self):
        self.received = None

    def optimize(self, svg):
        self.received = svg
        return svg + "<!--optimized-->"


def _pipeline(tmp_path, optimizer=None):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        downloader=FakeZipDownloader(),
        loader=NetworkLoader(),
        optimizer=optimizer,
    )


def test_injected_optimizer_runs_on_rendered_svg(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    fake = FakeOptimizer()
    context = _pipeline(tmp_path, optimizer=fake).run(settings)

    svg = context.artifacts["svg"]
    # The optimizer saw exactly the rendered SVG...
    assert fake.received == svg
    # ...and its output landed in artifacts.
    assert context.artifacts["optimized_svg"] == svg + "<!--optimized-->"


def test_pipeline_optimizes_svg_with_glow_on(tmp_path):
    settings = build_settings(
        {"region": ["Oregon"], "glow": True, "glow_mode": "blur"}
    )
    context = _pipeline(tmp_path, optimizer=FakeOptimizer()).run(settings)

    svg = context.artifacts["svg"]
    # Glow flowed into rendering (blur filter present) and was optimized.
    assert "hydro-glow" in svg
    assert "optimized_svg" in context.artifacts


def test_default_optimizer_degrades_without_svgo(tmp_path):
    # No optimizer injected -> real SvgoOptimizer; svgo isn't installed, so it
    # returns the SVG unchanged (with a warning) rather than crashing.
    import warnings

    settings = build_settings({"region": ["Oregon"]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        context = _pipeline(tmp_path).run(settings)
    assert context.artifacts["optimized_svg"] == context.artifacts["svg"]


def test_export_remains_a_stub(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path, optimizer=FakeOptimizer()).run(settings)
    # optimize_svg produced output; export hasn't (still a stub).
    assert "optimized_svg" in context.artifacts
    assert "export_paths" not in context.artifacts
