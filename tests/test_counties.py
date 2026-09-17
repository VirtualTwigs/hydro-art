"""Tests for the county-boundary seam (roadmap #24, Task Group 3).

Pure functions (region -> Census FIPS resolution + delegation) are tested with a
hand-built fake provider so no shapefile / GDAL is touched.
"""

import pytest
from shapely.geometry import box

from src.config import SUPPORTED_REGIONS, ConfigError
from src.counties import (
    STATE_FIPS,
    CensusCountyProvider,
    county_boundary,
    state_fips_for_region,
)
from src.datasets import AcquisitionError


class FakeProvider:
    """Records the resolved FIPS/CRS and returns a fixed polygon."""

    def __init__(self, geom=None):
        self._geom = geom if geom is not None else box(0, 0, 1, 1)
        self.calls = []

    def load(self, *, state_fips, county, target_crs):
        self.calls.append((state_fips, county, target_crs))
        return self._geom


class NotFoundProvider:
    def load(self, *, state_fips, county, target_crs):
        raise AcquisitionError(f"County {county!r} not found in FIPS {state_fips}.")


def test_state_fips_for_each_supported_region():
    assert state_fips_for_region("Oregon") == "41"
    assert state_fips_for_region("Washington") == "53"
    assert state_fips_for_region("California") == "06"
    assert state_fips_for_region("Idaho") == "16"


def test_every_supported_region_has_a_fips():
    for region in SUPPORTED_REGIONS:
        assert region in STATE_FIPS


def test_state_fips_for_unknown_region_raises():
    with pytest.raises(ConfigError, match="no Census FIPS"):
        state_fips_for_region("Atlantis")


def test_county_boundary_delegates_with_resolved_fips_and_crs():
    provider = FakeProvider()
    geom = county_boundary(
        provider, region="Washington", county="Clark", target_crs="EPSG:5070"
    )
    assert geom is provider._geom
    assert provider.calls == [("53", "Clark", "EPSG:5070")]


def test_county_boundary_propagates_not_found():
    with pytest.raises(AcquisitionError, match="not found"):
        county_boundary(
            NotFoundProvider(),
            region="Oregon",
            county="Nowhere",
            target_crs="EPSG:5070",
        )


def test_census_provider_wraps_missing_shapefile_path():
    # A default provider pointed at a nonexistent shapefile still surfaces an
    # actionable error rather than an opaque one (offline; no real read).
    provider = CensusCountyProvider(shapefile="/nonexistent/counties.shp")
    with pytest.raises((AcquisitionError, OSError)):
        provider.load(state_fips="41", county="Multnomah", target_crs="EPSG:5070")
