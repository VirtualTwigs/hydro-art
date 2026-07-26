"""End-to-end export through the pipeline + reproducibility (Item #10, TG3).

Reuses the offline fake downloader/loader pattern so the export stage runs on a
real (rendered, optimized) SVG. A fake exporter records writes so the wiring is
verified deterministically without a rasterizer, GDAL, or real data.
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, box

from src.config import build_settings
from src.loading import Layer
from src.pipeline import PIPELINE_STAGES, Pipeline

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


class WritingExporter:
    """Writes every format to disk verbatim so exports can be diffed on disk."""

    def export(self, svg, dest, fmt, *, png_size):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(svg, encoding="utf-8")
        return dest


def _pipeline(tmp_path, exporter=None, output_sub="output"):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / output_sub,
        downloader=FakeZipDownloader(),
        loader=NetworkLoader(),
        exporter=exporter or WritingExporter(),
    )


def test_export_stage_writes_requested_formats(tmp_path):
    settings = build_settings({"region": ["Oregon"], "output": ["svg", "pdf"]})
    context = _pipeline(tmp_path).run(settings)

    paths = context.artifacts["export_paths"]
    assert set(paths) == {"svg", "pdf"}
    assert paths["svg"] == tmp_path / "output" / "oregon.svg"
    assert paths["svg"].read_text(encoding="utf-8") == context.artifacts["optimized_svg"]
    assert "svg_sha256" in context.artifacts


def test_no_pipeline_stage_remains_a_stub(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    context = _pipeline(tmp_path).run(settings)
    # Every stage now produces an artifact; export is the last, real stage.
    assert [s.name for s in PIPELINE_STAGES][-1] == "export"
    assert "export_paths" in context.artifacts
    # A stub would only log "(stub)"; the real export recorded the SVG digest.
    assert len(context.artifacts["svg_sha256"]) == 64


def test_identical_inputs_produce_byte_identical_svg(tmp_path):
    settings = build_settings({"region": ["Oregon"]})
    first = _pipeline(tmp_path, output_sub="run1").run(settings)
    second = _pipeline(tmp_path, output_sub="run2").run(settings)

    a = first.artifacts["export_paths"]["svg"].read_bytes()
    b = second.artifacts["export_paths"]["svg"].read_bytes()
    assert a == b
    assert first.artifacts["svg_sha256"] == second.artifacts["svg_sha256"]


def test_default_exporter_degrades_for_nonsvg_without_tool(tmp_path):
    # No exporter injected -> real FileExporter; rsvg-convert isn't installed,
    # so pdf is skipped (warning) but svg is still written.
    import warnings

    settings = build_settings({"region": ["Oregon"], "output": ["svg", "pdf"]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        context = Pipeline(
            console=Console(),
            cache_dir=tmp_path / "cache",
            datasets_dir=tmp_path / "datasets",
            output_dir=tmp_path / "output",
            downloader=FakeZipDownloader(),
            loader=NetworkLoader(),
        ).run(settings)

    paths = context.artifacts["export_paths"]
    assert "svg" in paths and paths["svg"].exists()
    assert "pdf" not in paths  # gracefully skipped
