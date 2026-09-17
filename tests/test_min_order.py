"""Tests for min_order pipeline filtering (Epoch 26, Item #107).

Covers config validation, pipeline-stage filtering after stream-order
computation, and byte-identical default (min_order=1 = no filter).
"""

import io
import zipfile
from pathlib import Path

from rich.console import Console
from shapely.geometry import LineString, box

from src.config import DEFAULTS, ConfigError, build_settings
from src.loading import Layer
from src.pipeline import Pipeline


# -- Config validation -------------------------------------------------------

def test_default_min_order_is_one():
    settings = build_settings(DEFAULTS)
    assert settings.min_order == 1


def test_min_order_accepts_positive_int():
    settings = build_settings({**DEFAULTS, "min_order": 3})
    assert settings.min_order == 3


def test_min_order_zero_raises():
    import pytest
    with pytest.raises(ConfigError, match="min_order"):
        build_settings({**DEFAULTS, "min_order": 0})


def test_min_order_negative_raises():
    import pytest
    with pytest.raises(ConfigError, match="min_order"):
        build_settings({**DEFAULTS, "min_order": -1})


# -- Pipeline integration (fake loader) --------------------------------------

BOUNDARY = box(-124.0, 42.0, -116.0, 46.0)

# A small network with a clear topology: two headwaters merge into a trunk.
# Strahler: order 1 for each headwater, order 2 for the trunk.
HEADWATER_A = LineString([(-122.0, 43.0), (-121.0, 44.0)])
HEADWATER_B = LineString([(-120.0, 43.0), (-121.0, 44.0)])
TRUNK = LineString([(-121.0, 44.0), (-121.0, 45.0)])


class FakeDownloader:
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
        geoms = (HEADWATER_A, HEADWATER_B, TRUNK) if huc4 == "1707" else ()
        return [Layer("NHDFlowline", dataset_id, huc4, geoms, crs="EPSG:4326")]


def _pipeline(tmp_path):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / "output",
        downloader=FakeDownloader(),
        loader=NetworkLoader(),
    )


def test_min_order_1_keeps_all_segments(tmp_path):
    """min_order=1 (default) keeps every segment — byte-identical behavior."""
    settings = build_settings({"region": ["Oregon"], "min_order": 1})
    ctx = _pipeline(tmp_path).run(settings)
    # All 3 segments survive.
    assert len(ctx.artifacts["segment_colors"]) == 3


def test_min_order_2_drops_headwaters(tmp_path):
    """min_order=2 drops order-1 headwaters, keeps the order-2 trunk."""
    settings = build_settings({"region": ["Oregon"], "min_order": 2})
    ctx = _pipeline(tmp_path).run(settings)
    # Only the trunk (order 2) survives.
    assert len(ctx.artifacts["segment_colors"]) == 1
    # The SVG should still contain a path.
    assert "<path" in ctx.artifacts["svg"]


def test_min_order_higher_than_max_produces_empty_svg(tmp_path):
    """min_order above the network's max order produces an SVG with no paths."""
    settings = build_settings({"region": ["Oregon"], "min_order": 99})
    ctx = _pipeline(tmp_path).run(settings)
    assert len(ctx.artifacts["segment_colors"]) == 0
    # SVG is still a valid document (background rect exists).
    assert "<svg" in ctx.artifacts["svg"]
    assert "<rect" in ctx.artifacts["svg"]


def test_default_build_is_byte_identical_with_explicit_min_order_1(tmp_path):
    """Explicit min_order=1 produces the same SVG as the default (no filter)."""
    default = build_settings({"region": ["Oregon"]})
    explicit = build_settings({"region": ["Oregon"], "min_order": 1})
    svg_default = _pipeline(tmp_path).run(default).artifacts["svg"]
    svg_explicit = _pipeline(tmp_path).run(explicit).artifacts["svg"]
    assert svg_default == svg_explicit
