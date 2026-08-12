"""County-scoped clip through the pipeline (roadmap #24, Task Group 4).

Runs the real reproject/clip/export stages offline. A fake downloader satisfies
download/extract, a fake loader yields in-memory layers, and a fake county
provider returns a hand-built county polygon (reprojected with pyproj, exactly
as the pipeline reprojects its layers) so the county clip is exercised without
GDAL, a shapefile, or real data.
"""

import io
import zipfile
from pathlib import Path

from pyproj import Transformer
from rich.console import Console
from shapely.geometry import LineString, box
from shapely.ops import transform as shapely_transform

from src.config import build_settings
from src.loading import Layer
from src.pipeline import Pipeline

# WBD region boundary (broad) vs. a small county box inside it (lon/lat).
REGION = box(-124.0, 42.0, -116.0, 46.0)
COUNTY = box(-122.0, 45.5, -121.0, 46.0)
INSIDE_COUNTY = LineString([(-121.8, 45.6), (-121.5, 45.9)])   # inside county
OUTSIDE_COUNTY = LineString([(-119.0, 43.0), (-118.5, 43.2)])  # in region, not county


def _to_crs(geom, dst_crs, src_crs="EPSG:4326"):
    """Reproject a lon/lat geometry the same way the pipeline does (pyproj)."""
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return shapely_transform(transformer.transform, geom)


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
    def load_layers(self, dataset_dir, dataset_id, huc4):
        if dataset_id == "wbd":
            return [Layer("WBDHU4", "wbd", huc4, (REGION,), crs="EPSG:4326")]
        return [
            Layer(
                "NHDFlowline",
                dataset_id,
                huc4,
                (INSIDE_COUNTY, OUTSIDE_COUNTY),
                crs="EPSG:4326",
            )
        ]


class FakeCountyProvider:
    """Returns a fixed county polygon already reprojected to target_crs."""

    def __init__(self):
        self.calls = []

    def load(self, *, state_fips, county, target_crs):
        self.calls.append((state_fips, county, target_crs))
        return _to_crs(COUNTY, target_crs)


def _pipeline(tmp_path, county_provider=None):
    return Pipeline(
        console=Console(),
        cache_dir=tmp_path / "cache",
        datasets_dir=tmp_path / "datasets",
        output_dir=tmp_path / "output",
        downloader=FakeZipDownloader(),
        loader=GeoLoader(),
        county_provider=county_provider,
    )


def test_county_scope_clips_to_county_polygon(tmp_path):
    provider = FakeCountyProvider()
    settings = build_settings(
        {"region": ["Oregon"], "county": "Hood River",
         "waterbodies": {"enabled": False}}
    )
    context = _pipeline(tmp_path, provider).run(settings)

    # Provider was asked for Oregon's FIPS (41) at the internal projection.
    assert provider.calls == [("41", "Hood River", "EPSG:5070")]

    # Only the in-county flowline survives; the in-region-but-out-of-county drops.
    n_flow = sum(
        1 for layer in context.artifacts["projected_layers"]
        if layer.dataset_id != "wbd"
    )
    stats = context.artifacts["clip_stats"]
    assert stats.total_out == 1 * n_flow
    assert stats.dropped_outside == 1 * n_flow

    # The county polygon (not the WBD region) is the boundary artifact.
    assert context.artifacts["region_boundary"].equals(
        _to_crs(COUNTY, settings.projection)
    )


def test_county_scope_names_output_after_county(tmp_path):
    provider = FakeCountyProvider()
    settings = build_settings(
        {"region": ["Oregon"], "county": "Hood River",
         "waterbodies": {"enabled": False}}
    )
    context = _pipeline(tmp_path, provider).run(settings)

    paths = context.artifacts["export_paths"]
    assert "svg" in paths
    assert paths["svg"].name == "oregon-hood-river.svg"


def test_default_build_still_clips_to_region(tmp_path):
    # No county provider needed; the WBD boundary path is unchanged.
    settings = build_settings(
        {"region": ["Oregon"], "waterbodies": {"enabled": False}}
    )
    context = _pipeline(tmp_path).run(settings)

    assert context.artifacts["region_boundary"].equals(
        _to_crs(REGION, settings.projection)
    )
    paths = context.artifacts["export_paths"]
    assert paths["svg"].name == "oregon.svg"
