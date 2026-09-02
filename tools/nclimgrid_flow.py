"""nClimGrid-backed :class:`~src.historical_flow.ClimateProvider` (roadmap #60).

The license-free replacement for ``tools/historical_flow.PrismClimateProvider``.
PRISM climate is not public domain (its commercial-use Rights gate blocks selling
any PRISM-derived animation/report); **NOAA nClimGrid-Monthly is U.S. federal public
domain** — free to sell with attribution — and is the direct equivalent: monthly
``prcp`` (mm) + ``tavg`` (degC), ~5 km, CONUS, record from January 1895.

Unlike PRISM's one-GeoTIFF-per-month layout, nClimGrid ships as **two stacked
NetCDF files** (``nclimgrid_prcp.nc`` / ``nclimgrid_tavg.nc``) with a monthly
``time`` axis. GDAL/rasterio's NETCDF driver exposes each month as a **band**, so the
sampling mirrors the PRISM provider almost exactly: compute each reach's (row, col)
once from the shared geotransform, then read one band per (year, month). The pure
band-index / cell / nodata math lives in :mod:`src.climate_grid` (numpy-only,
offline-tested); rasterio is **lazy-imported inside the reader** so importing this
module stays GDAL-free.

Missing/ocean cells fall back exactly like ``tools/monthly_flow.py`` /
``PrismClimateProvider``: precip -> 0 mm, temp -> 10 degC (mild, no snow). nClimGrid
is EPSG:4326 (WGS84) vs PRISM's EPSG:4269 (NAD83); the datum offset is sub-cell at
5 km, so reach lon/lat sample directly with no reprojection.

Heavy GDAL reads live here (a ``tools/`` script), never in ``src/`` — so the offline
suite stays GDAL-free.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.climate_grid import band_for_month, cells_from_lonlat, fill_nodata  # noqa: E402
from src.historical_flow import YearlyClimate  # noqa: E402
from src.monthly_flow import MONTHS  # noqa: E402

DEFAULT_ROOT = "/Volumes/home/data/hydro-art"
PPT_FILL = 0.0     # nodata precip -> no water
TAVG_FILL = 10.0   # nodata temp -> mild, no snow (mirrors tools/monthly_flow)


def staged_path(root: Path, var: str) -> Path:
    """Location of one staged nClimGrid NetCDF (mirrors ``nclimgrid_fetch``)."""
    return root / "nclimgrid" / f"nclimgrid_{var}.nc"


def netcdf_uri(path: Path, var: str) -> str:
    """GDAL NETCDF subdataset URI addressing ``var`` inside a stacked NetCDF."""
    return f"netcdf:{path}:{var}"


class BandReader(Protocol):
    """Seam over the one rasterio touch: read a single month's band as a grid.

    The default implementation (:class:`RasterioBandReader`) lazy-imports rasterio;
    a fake can stand in for it so the provider's orchestration is exercisable without
    GDAL.
    """

    def open(self, uri: str) -> None:
        ...

    def grid_shape(self) -> tuple[int, int]:
        ...

    def inverse_transform(self) -> tuple[float, float, float, float, float, float]:
        ...

    def nodata(self) -> float | None:
        ...

    def read_band(self, band: int) -> np.ndarray:
        ...


class RasterioBandReader:
    """rasterio-backed :class:`BandReader` (rasterio imported lazily on ``open``)."""

    def __init__(self) -> None:
        self._ds = None

    def open(self, uri: str) -> None:
        import rasterio  # lazy: keep module import GDAL-free

        self._ds = rasterio.open(uri)

    def grid_shape(self) -> tuple[int, int]:
        return int(self._ds.width), int(self._ds.height)

    def inverse_transform(self) -> tuple[float, float, float, float, float, float]:
        inv = ~self._ds.transform
        return (inv.a, inv.b, inv.c, inv.d, inv.e, inv.f)

    def nodata(self) -> float | None:
        return self._ds.nodata

    def read_band(self, band: int) -> np.ndarray:
        return self._ds.read(band)

    def close(self) -> None:
        if self._ds is not None:
            self._ds.close()
            self._ds = None


class NClimGridClimateProvider:
    """Sample staged nClimGrid monthly NetCDFs at fixed reach locations.

    Constructed with the reach centroid lon/lat arrays (EPSG:4326; nClimGrid's CRS)
    in the exact order the network's ``q_incr``/``hydroseq`` arrays use — the same
    constructor shape as :class:`~tools.historical_flow.PrismClimateProvider`, so it
    is a drop-in behind the ``--climate-source`` factory. ``climate_for_year``
    returns a :class:`~src.historical_flow.YearlyClimate` of shape ``[n, 12]``.
    """

    def __init__(
        self,
        root: str | Path,
        lon: np.ndarray,
        lat: np.ndarray,
        *,
        prcp_var: str = "prcp",
        tavg_var: str = "tavg",
        reader_factory=RasterioBandReader,
    ) -> None:
        self.root = Path(root)
        self.lon = np.asarray(lon, dtype=np.float64)
        self.lat = np.asarray(lat, dtype=np.float64)
        if self.lon.shape != self.lat.shape or self.lon.ndim != 1:
            raise ValueError("lon/lat must be matching 1-D arrays")
        self.prcp_var = prcp_var
        self.tavg_var = tavg_var
        self._reader_factory = reader_factory

    def _read_var_year(self, var: str, year: int, fill: float) -> np.ndarray:
        """Sample one variable's 12 monthly bands -> ``[n, 12]`` at reach cells."""
        path = staged_path(self.root, var)
        if not path.exists():
            raise FileNotFoundError(f"missing nClimGrid file: {path}")
        reader = self._reader_factory()
        reader.open(netcdf_uri(path, var))
        try:
            width, height = reader.grid_shape()
            rows, cols = cells_from_lonlat(
                self.lon, self.lat, reader.inverse_transform(),
                width=width, height=height,
            )
            nodata = reader.nodata()
            out = np.full((self.lon.shape[0], 12), fill, dtype=np.float64)
            for m in MONTHS:
                band = reader.read_band(band_for_month(year, m))
                vals = band[rows, cols].astype(np.float64)
                out[:, m - 1] = fill_nodata(vals, nodata=nodata, fill=fill)
            return out
        finally:
            close = getattr(reader, "close", None)
            if callable(close):
                close()

    def climate_for_year(self, year: int) -> YearlyClimate:
        precip = self._read_var_year(self.prcp_var, year, PPT_FILL)
        temp = self._read_var_year(self.tavg_var, year, TAVG_FILL)
        return YearlyClimate(year=year, precip_mm=precip, temp_c=temp)
