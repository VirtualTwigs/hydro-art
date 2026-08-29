"""PRISM-backed :class:`~src.historical_flow.ClimateProvider` (roadmap #45).

The pure year-over-year engine (`src/historical_flow.py`, #44) runs the shared
`disaggregate_monthly` model for a specific historical calendar year *behind an
injectable* ``ClimateProvider`` seam. This module supplies the real, non-offline
implementation of that seam: it samples the NAS-staged PRISM monthly grids
(``prism_fetch.py`` downloads them) at each catchment's location and returns a
``YearlyClimate`` — real per-year monthly precip (mm) + mean temperature (degC),
in the exact reach order the caller uses.

PRISM 4 km grids are EPSG:4269 (NAD83 geographic); every monthly ``ppt``/``tmean``
GeoTIFF shares one geotransform, so the (row, col) of each reach centroid is
computed **once** from the first grid and reused for fast vectorized sampling of
every month/year. Missing/ocean cells (nodata ``-9999``) fall back the same way
``tools/monthly_flow.py`` does: precip -> 0 mm, temp -> 10 degC (mild, no snow).

Heavy GDAL/rasterio reads live here (a ``tools/`` script), never in ``src/`` — so
the offline suite injects a fake provider and stays GDAL-free.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.historical_flow import YearlyClimate  # noqa: E402
from src.monthly_flow import MONTHS  # noqa: E402

DEFAULT_ROOT = "/Volumes/home/data/hydro-art"
PPT_FILL = 0.0    # nodata precip -> no water
TMEAN_FILL = 10.0  # nodata temp -> mild, no snow (mirrors tools/monthly_flow)


def staged_path(root: Path, var: str, year: int, month: int) -> Path:
    """Location of one staged PRISM grid (mirrors ``prism_fetch.staged_path``)."""
    return root / "prism" / var / f"prism_{var}_{year}{month:02d}.tif"


class PrismClimateProvider:
    """Sample staged PRISM monthly grids at fixed reach locations.

    Constructed with the reach centroid lon/lat arrays (EPSG:4269) in the exact
    order the network's ``q_incr``/``hydroseq`` arrays use. ``climate_for_year``
    returns a ``YearlyClimate`` with ``precip_mm``/``temp_c`` of shape ``[n, 12]``.
    """

    def __init__(self, root: str | Path, lon: np.ndarray, lat: np.ndarray, *,
                 ppt_var: str = "ppt", tmean_var: str = "tmean") -> None:
        self.root = Path(root)
        self.lon = np.asarray(lon, dtype=np.float64)
        self.lat = np.asarray(lat, dtype=np.float64)
        if self.lon.shape != self.lat.shape or self.lon.ndim != 1:
            raise ValueError("lon/lat must be matching 1-D arrays")
        self.ppt_var = ppt_var
        self.tmean_var = tmean_var
        self._rows: np.ndarray | None = None
        self._cols: np.ndarray | None = None

    def _ensure_index(self, sample_tif: Path) -> None:
        """Precompute (row, col) of every reach from one grid's geotransform."""
        if self._rows is not None:
            return
        with rasterio.open(sample_tif) as ds:
            inv = ~ds.transform  # (x, y) -> (col, row), vectorized over arrays
            cols = inv.a * self.lon + inv.b * self.lat + inv.c
            rows = inv.d * self.lon + inv.e * self.lat + inv.f
            self._cols = np.clip(np.floor(cols).astype(int), 0, ds.width - 1)
            self._rows = np.clip(np.floor(rows).astype(int), 0, ds.height - 1)

    def _read_var_year(self, var: str, year: int, fill: float) -> np.ndarray:
        """Sample one variable's 12 monthly grids -> ``[n, 12]`` at reach cells."""
        out = np.full((self.lon.shape[0], 12), fill, dtype=np.float64)
        for m in MONTHS:
            tif = staged_path(self.root, var, year, m)
            if not tif.exists():
                raise FileNotFoundError(f"missing PRISM grid: {tif}")
            self._ensure_index(tif)
            with rasterio.open(tif) as ds:
                band = ds.read(1)
                nodata = ds.nodata
            vals = band[self._rows, self._cols].astype(np.float64)
            if nodata is not None:
                vals = np.where(vals == nodata, fill, vals)
            vals = np.where(np.isfinite(vals), vals, fill)
            out[:, m - 1] = vals
        return out

    def climate_for_year(self, year: int) -> YearlyClimate:
        precip = self._read_var_year(self.ppt_var, year, PPT_FILL)
        temp = self._read_var_year(self.tmean_var, year, TMEAN_FILL)
        return YearlyClimate(year=year, precip_mm=precip, temp_c=temp)
