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


# --- CensusCountyProvider.load with mocked geopandas (lines 161-179) --------


class _BoolMask(list):
    """List of bools supporting element-wise & (like pandas Series)."""

    def __and__(self, other):
        return _BoolMask(a and b for a, b in zip(self, other))

    def __rand__(self, other):
        return self.__and__(other)


class _FakeStrAccessor:
    """Mimics pandas .str accessor for a column of string values."""

    def __init__(self, values):
        self._values = values

    def lower(self):
        return _FakeColumn([v.lower() for v in self._values])


class _FakeColumn:
    """Minimal column supporting == comparison and .str accessor."""

    def __init__(self, values):
        self._values = values
        self.str = _FakeStrAccessor(values)

    def __eq__(self, other):
        if isinstance(other, _FakeColumn):
            return _BoolMask(a == b for a, b in zip(self._values, other._values))
        return _BoolMask(v == other for v in self._values)


class _FakeGeoDataFrame:
    """Minimal GeoDataFrame stand-in for CensusCountyProvider.load tests."""

    def __init__(self, rows):
        self._rows = rows  # list of dicts with STATEFP, NAME, geom
        self.STATEFP = _FakeColumn([r["STATEFP"] for r in rows])
        self.NAME = _FakeColumn([r["NAME"] for r in rows])
        self.empty = len(rows) == 0

    def __getitem__(self, mask):
        filtered = [r for r, keep in zip(self._rows, mask) if keep]
        return _FakeGeoDataFrame(filtered)

    def to_crs(self, crs):
        self._crs = crs
        return self

    @property
    def geometry(self):
        return _FakeGeomSeries([r["geom"] for r in self._rows])


class _FakeGeomSeries:
    """Mimics a geopandas geometry series with .iloc indexing."""

    def __init__(self, geoms):
        self._geoms = geoms

    @property
    def iloc(self):
        return self

    def __getitem__(self, idx):
        return self._geoms[idx]


def _fake_gpd_module(rows):
    """Return a module-like object whose read_file returns a _FakeGeoDataFrame."""
    import types

    mod = types.ModuleType("geopandas")
    mod.read_file = lambda path: _FakeGeoDataFrame(rows)
    return mod


def test_census_provider_load_success(tmp_path, monkeypatch):
    """CensusCountyProvider.load reads, filters, and reprojects correctly."""
    shp = tmp_path / "counties.shp"
    shp.write_text("")  # just needs to exist

    sentinel = box(10, 20, 30, 40)
    rows = [
        {"STATEFP": "41", "NAME": "Multnomah", "geom": sentinel},
        {"STATEFP": "41", "NAME": "Clackamas", "geom": box(0, 0, 1, 1)},
        {"STATEFP": "53", "NAME": "Clark", "geom": box(0, 0, 2, 2)},
    ]
    fake_gpd = _fake_gpd_module(rows)
    import sys

    monkeypatch.setitem(sys.modules, "geopandas", fake_gpd)

    provider = CensusCountyProvider(shapefile=str(shp))
    result = provider.load(state_fips="41", county="Multnomah", target_crs="EPSG:5070")
    assert result is sentinel


def test_census_provider_load_case_insensitive(tmp_path, monkeypatch):
    """County name matching is case-insensitive."""
    shp = tmp_path / "counties.shp"
    shp.write_text("")

    sentinel = box(5, 5, 15, 15)
    rows = [{"STATEFP": "53", "NAME": "Clark", "geom": sentinel}]
    fake_gpd = _fake_gpd_module(rows)
    import sys

    monkeypatch.setitem(sys.modules, "geopandas", fake_gpd)

    provider = CensusCountyProvider(shapefile=str(shp))
    result = provider.load(state_fips="53", county="clark", target_crs="EPSG:5070")
    assert result is sentinel


def test_census_provider_load_not_found(tmp_path, monkeypatch):
    """AcquisitionError when county doesn't match any row."""
    shp = tmp_path / "counties.shp"
    shp.write_text("")

    rows = [{"STATEFP": "41", "NAME": "Multnomah", "geom": box(0, 0, 1, 1)}]
    fake_gpd = _fake_gpd_module(rows)
    import sys

    monkeypatch.setitem(sys.modules, "geopandas", fake_gpd)

    provider = CensusCountyProvider(shapefile=str(shp))
    with pytest.raises(AcquisitionError, match="not found"):
        provider.load(state_fips="41", county="Nonexistent", target_crs="EPSG:5070")
