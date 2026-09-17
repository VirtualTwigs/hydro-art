"""Tests for the elevation provenance model + injected seams (Item 11).

These cover the immutable :class:`ElevationProvenance` metadata, its
boundary validation via :func:`build_provenance`, the value objects a sampler
returns, and structural conformance of the injected protocols. No real raster
I/O happens here — the protocols exist so later items (12/13/14) can inject
fakes exactly as the loader/downloader seams already do.
"""

import dataclasses

import pytest

from src.datasets import AcquisitionError
from src.elevation import (
    ElevationError,
    ElevationSample,
    ElevationSampler,
    RasterReader,
    TileDiscoverer,
    TileRef,
    build_provenance,
)


def _kwargs(**overrides):
    base = {
        "source_product": "USGS 3DEP 1/3 arc-second DEM",
        "source_url": "https://example.usgs.gov/3dep/n46w123.tif",
        "acquisition_date": "2024-05-01",
        "horizontal_crs": "EPSG:4269",
        "vertical_crs": "NAVD88",
        "vertical_units": "meters",
        "resolution_m": 10.0,
        "checksum": "sha256:abc123",
        "processing_parameters": {"resampling": "bilinear"},
    }
    base.update(overrides)
    return base


def test_build_provenance_records_all_fields():
    prov = build_provenance(**_kwargs())
    assert prov.source_product.startswith("USGS 3DEP")
    assert prov.horizontal_crs == "EPSG:4269"
    assert prov.vertical_crs == "NAVD88"
    assert prov.vertical_units == "meters"
    assert prov.resolution_m == 10.0
    assert prov.processing_parameters == {"resampling": "bilinear"}


def test_provenance_is_immutable():
    prov = build_provenance(**_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        prov.resolution_m = 30.0  # type: ignore[misc]


def test_missing_required_field_raises_elevation_error():
    with pytest.raises(ElevationError, match="source_product"):
        build_provenance(**_kwargs(source_product=""))


def test_non_positive_resolution_raises():
    with pytest.raises(ElevationError, match="resolution_m"):
        build_provenance(**_kwargs(resolution_m=0.0))


def test_elevation_error_is_acquisition_error():
    # build.py maps AcquisitionError subclasses to exit code 2.
    assert issubclass(ElevationError, AcquisitionError)


def test_vertical_reference_may_be_absent_but_is_preserved_verbatim():
    # Decision: preserve source only. When a DEM has no stated vertical datum
    # the model records that absence rather than inventing NAVD88.
    prov = build_provenance(**_kwargs(vertical_crs=None, vertical_units=None))
    assert prov.vertical_crs is None
    assert prov.vertical_units is None


def test_elevation_sample_value_object():
    hit = ElevationSample(value_m=812.5, covered=True, nodata=False)
    miss = ElevationSample(value_m=None, covered=False, nodata=True)
    assert hit.value_m == 812.5 and hit.covered and not hit.nodata
    assert miss.value_m is None and not miss.covered and miss.nodata


def test_tile_ref_value_object():
    ref = TileRef(tile_id="n46w123", url="https://x/n46w123.tif", resolution_m=10.0)
    assert ref.tile_id == "n46w123"
    assert ref.resolution_m == 10.0


def test_protocols_accept_structural_fakes():
    class FakeDiscoverer:
        def discover_tiles(self, boundary, tier):
            return [TileRef("t", "u", 10.0)]

    class FakeReader:
        def read_window(self, tile, bounds):
            return [[1.0]]

    class FakeSampler:
        def sample(self, x, y):
            return ElevationSample(value_m=1.0, covered=True, nodata=False)

    # Plain (non-runtime_checkable) protocols: structural typing suffices.
    discoverer: TileDiscoverer = FakeDiscoverer()
    reader: RasterReader = FakeReader()
    sampler: ElevationSampler = FakeSampler()
    assert discoverer.discover_tiles(None, "preview")[0].tile_id == "t"
    assert reader.read_window(None, None) == [[1.0]]
    assert sampler.sample(0.0, 0.0).value_m == 1.0
