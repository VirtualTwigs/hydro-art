"""County-boundary resolution seam (roadmap #24).

Promotes ``tools/render_common.load_county`` into an injectable, offline-testable
collaborator for the pipeline: a county build clips hydrography to a single
Census county polygon instead of the WBD region boundary.

The region -> Census STATEFP mapping and the delegation logic are pure functions
(no I/O, GDAL-free). Only :class:`CensusCountyProvider` touches the filesystem,
and it lazy-imports geopandas — mirroring the ``Downloader``/``LayerLoader``
seams so ``src/`` and the test suite stay importable without GDAL. ``src/`` must
not import ``tools/``, so the shapefile path constant is redeclared here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.config import ConfigError
from src.datasets import AcquisitionError

__all__ = [
    "STATE_FIPS",
    "DEFAULT_COUNTY_SHAPEFILE",
    "CountyBoundaryProvider",
    "CensusCountyProvider",
    "state_fips_for_region",
    "county_boundary",
]

#: Census STATEFP code for each supported region. Kept in sync with
#: :data:`src.config.SUPPORTED_REGIONS` (a test asserts full coverage); extend
#: here whenever a region is added.
STATE_FIPS: dict[str, str] = {
    "Oregon": "41",
    "Washington": "53",
    "California": "06",
}

#: Default Census cartographic-boundary counties shapefile (matches the path the
#: ``tools/`` renderers stage under ``/tmp``).
DEFAULT_COUNTY_SHAPEFILE = "/tmp/counties_shp/cb_2023_us_county_500k.shp"


class CountyBoundaryProvider(Protocol):
    """Loads a single county's boundary polygon (the injectable I/O seam)."""

    def load(self, *, state_fips: str, county: str, target_crs: str) -> Any:
        """Return the county polygon (in ``target_crs``) for ``county``.

        Raises:
            AcquisitionError: If the county cannot be resolved.
        """
        ...


def state_fips_for_region(region: str) -> str:
    """Return the Census STATEFP for a supported ``region``.

    Raises:
        ConfigError: If ``region`` has no FIPS mapping (should not happen for a
            validated region, but fails loudly if the maps drift apart).
    """
    try:
        return STATE_FIPS[region]
    except KeyError:
        raise ConfigError(
            f"Region {region!r} has no Census FIPS mapping; add it to "
            "src.counties.STATE_FIPS."
        )


def county_boundary(
    provider: CountyBoundaryProvider,
    *,
    region: str,
    county: str,
    target_crs: str,
) -> Any:
    """Resolve ``region`` -> FIPS (pure) then delegate to ``provider.load``.

    Keeps FIPS resolution testable without I/O; the provider is the only
    collaborator that reads the dataset.
    """
    state_fips = state_fips_for_region(region)
    return provider.load(
        state_fips=state_fips, county=county, target_crs=target_crs
    )


class CensusCountyProvider:
    """Default provider: reads the Census counties shapefile via geopandas.

    Filters on ``STATEFP`` + ``NAME`` (case-insensitive) and reprojects the
    matched polygon to ``target_crs``. geopandas is imported lazily so importing
    this module (and running the offline suite) never requires GDAL.
    """

    def __init__(self, shapefile: str | Path = DEFAULT_COUNTY_SHAPEFILE) -> None:
        self._shapefile = str(shapefile)

    def load(self, *, state_fips: str, county: str, target_crs: str) -> Any:
        if not Path(self._shapefile).exists():
            raise AcquisitionError(
                f"County shapefile not found: {self._shapefile}. Stage the Census "
                "cartographic-boundary counties shapefile there first."
            )
        try:
            import geopandas as gpd  # lazy: keeps src/ GDAL-free at import time
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise AcquisitionError(
                "geopandas is required to load county boundaries; install the GIS "
                "stack (requirements.txt)."
            ) from exc

        df = gpd.read_file(self._shapefile)
        sel = df[
            (df.STATEFP == str(state_fips))
            & (df.NAME.str.lower() == county.lower())
        ]
        if sel.empty:
            raise AcquisitionError(
                f"County {county!r} (STATEFP {state_fips}) not found in "
                f"{self._shapefile}."
            )
        return sel.to_crs(target_crs).geometry.iloc[0]
