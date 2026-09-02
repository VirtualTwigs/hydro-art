"""Pure, source-agnostic gridded-climate sampling helpers (numpy only, offline).

The year-over-year flow feature samples a monthly climate grid at each catchment
centroid (`tools/nclimgrid_flow.py` for NOAA nClimGrid, `tools/historical_flow.py`
for PRISM). The heavy NetCDF/GeoTIFF reads live in those `tools/` scripts behind the
`src.historical_flow.ClimateProvider` seam; this module holds the *pure* logic those
providers share so it is unit-testable under the repo rule that the offline suite
never imports `tools/`:

- :func:`band_for_month` — the monthly-time-axis band index for a stacked grid whose
  record starts January :data:`GRIDDED_FIRST_YEAR` (nClimGrid == PRISM == 1895).
  Isolating this pins the two classic off-by-one traps (the 1895 epoch origin, and
  0- vs 1-based bands) behind a test.
- :func:`cells_from_lonlat` — vectorized (row, col) of every reach from a grid's
  inverse affine transform, computed once and reused across all months/years.
- :func:`fill_nodata` — honest ocean/nodata replacement (never invent data).

Numpy-only and pure: identical inputs yield identical outputs and no argument is
mutated. No rasterio, no I/O.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "GRIDDED_FIRST_YEAR",
    "ClimateGridError",
    "band_for_month",
    "cells_from_lonlat",
    "fill_nodata",
]

# NOAA nClimGrid-Monthly (and PRISM) monthly records begin January 1895; no month
# request may precede it.
GRIDDED_FIRST_YEAR = 1895


class ClimateGridError(ValueError):
    """Raised for an out-of-range or malformed gridded-climate sampling request."""


def band_for_month(
    year: int,
    month: int,
    *,
    first_year: int = GRIDDED_FIRST_YEAR,
    one_based: bool = True,
) -> int:
    """Band index of ``(year, month)`` in a monthly grid stacked from ``first_year``.

    Month ``m`` of ``year`` is the ``(year - first_year) * 12 + (m - 1)``-th month of
    the record (0-based); rasterio band numbering is 1-based, so ``one_based`` adds 1
    (the default, since the concrete reader hands these straight to ``ds.read(band)``).

    Fail fast (:class:`ClimateGridError`) on a non-int year/month, a year before
    ``first_year``, or a month outside ``1..12`` — an off-by-one here silently shifts
    every rendered frame by a month or a year.
    """
    for label, value in (("year", year), ("month", month)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ClimateGridError(f"{label} must be an int; got {value!r}")
    if year < first_year:
        raise ClimateGridError(
            f"year {year} precedes the record start {first_year}"
        )
    if not 1 <= month <= 12:
        raise ClimateGridError(f"month must be 1..12; got {month}")
    idx = (year - first_year) * 12 + (month - 1)
    return idx + 1 if one_based else idx


def cells_from_lonlat(
    lon: np.ndarray,
    lat: np.ndarray,
    inv_transform: tuple[float, float, float, float, float, float],
    *,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized ``(rows, cols)`` of each ``(lon, lat)`` in a north-up grid.

    ``inv_transform`` is the affine inverse ``(a, b, c, d, e, f)`` mapping
    ``(x, y) -> (col, row)`` (``col = a*x + b*y + c``; ``row = d*x + e*y + f``) — i.e.
    ``~rasterio_dataset.transform`` unpacked. Cells are floored to integers and
    clipped into ``[0, width-1] x [0, height-1]`` so an off-grid reach snaps to the
    nearest edge cell rather than indexing out of bounds (matching the PRISM
    provider). ``lon``/``lat`` must be matching 1-D arrays.
    """
    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    if lon.shape != lat.shape or lon.ndim != 1:
        raise ClimateGridError("lon/lat must be matching 1-D arrays")
    a, b, c, d, e, f = inv_transform
    cols = a * lon + b * lat + c
    rows = d * lon + e * lat + f
    cols = np.clip(np.floor(cols).astype(int), 0, width - 1)
    rows = np.clip(np.floor(rows).astype(int), 0, height - 1)
    return rows, cols


def fill_nodata(
    values: np.ndarray,
    *,
    nodata: float | None,
    fill: float,
) -> np.ndarray:
    """Replace ``nodata`` sentinels and non-finite entries with ``fill`` (new array).

    Honest ocean/nodata handling: a masked-out or missing cell becomes the caller's
    physical fallback (precip 0 mm, temp a mild degC) rather than a fabricated value.
    Pure — the input array is never mutated.
    """
    out = np.asarray(values, dtype=np.float64).copy()
    if nodata is not None:
        out = np.where(out == nodata, fill, out)
    out = np.where(np.isfinite(out), out, fill)
    return out
