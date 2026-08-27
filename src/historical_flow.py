"""Year-over-year historical flow: real-year climate -> per-year monthly flow.

Today's year-in-motion render (``src.monthly_flow.disaggregate_monthly``) drives
its twelve frames from the NHDPlus HR GDB's long-term *climate normals* -- a
single synthetic "average year" with no calendar year attached. This module adds
the pure, offline machinery to run that same disaggregation for a *specific
historical calendar year* (and a span of years), giving the render a
year-over-year axis without changing the default synthetic-year behavior.

Real per-year monthly climate comes from PRISM (monthly record begins Jan 1895).
The heavy raster reads live in ``tools/historical_flow.py`` behind the injectable
:class:`ClimateProvider` seam, so this module stays numpy-only and fully
offline-testable: tests inject a fake provider and hand-built arrays, no GDAL.

Purely a function of its inputs -- no ``datetime.now``/clock, so an identical
``(provider, years, network)`` always yields identical flow. The newest available
year is passed in as ``latest`` by the caller (the tool knows which PRISM years it
has staged) rather than read from the system clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from src.monthly_flow import disaggregate_monthly

__all__ = [
    "PRISM_FIRST_YEAR",
    "HistoricalFlowError",
    "YearlyClimate",
    "ClimateProvider",
    "normalize_years",
    "year_span",
    "yearly_flow_series",
    "annual_mean_series",
    "peak_month_series",
]

# PRISM's monthly precipitation/temperature record begins January 1895; no
# historical-year request may go earlier than this.
PRISM_FIRST_YEAR = 1895


class HistoricalFlowError(ValueError):
    """Raised for an out-of-range or malformed historical-year request."""


@dataclass(frozen=True)
class YearlyClimate:
    """Per-catchment monthly climate for one calendar year.

    ``precip_mm`` and ``temp_c`` are ``[n, 12]`` (n reaches in the network's own
    order, columns Jan..Dec) in physical units (mm, degC), ready to feed
    :func:`src.monthly_flow.disaggregate_monthly`.
    """

    year: int
    precip_mm: np.ndarray
    temp_c: np.ndarray

    def __post_init__(self) -> None:
        if self.precip_mm.shape != self.temp_c.shape:
            raise HistoricalFlowError(
                f"precip/temp shapes differ for year {self.year}: "
                f"{self.precip_mm.shape} vs {self.temp_c.shape}"
            )
        if self.precip_mm.ndim != 2 or self.precip_mm.shape[1] != 12:
            raise HistoricalFlowError(
                f"climate for year {self.year} must be [n, 12]; "
                f"got {self.precip_mm.shape}"
            )

    @property
    def reach_count(self) -> int:
        """Number of reaches (n) this year's climate covers."""
        return int(self.precip_mm.shape[0])


@runtime_checkable
class ClimateProvider(Protocol):
    """Seam that yields one calendar year of per-catchment monthly climate.

    The real implementation (``tools/historical_flow.PrismClimateProvider``)
    samples PRISM monthly grids per catchment and needs GDAL/rasterio; tests
    inject a fake so this module stays offline.
    """

    def climate_for_year(self, year: int) -> YearlyClimate:
        ...


def normalize_years(years: object, *, latest: int | None = None) -> tuple[int, ...]:
    """Validate, de-duplicate, and sort a set of requested calendar years.

    Every year must be an integer no earlier than :data:`PRISM_FIRST_YEAR`; if
    ``latest`` is given, no later than it. Returns the years ascending with
    duplicates removed. Raises :class:`HistoricalFlowError` on an empty request,
    a non-integer, or an out-of-range year (fail fast at the boundary).
    """
    try:
        raw = list(years)  # type: ignore[arg-type]
    except TypeError as exc:
        raise HistoricalFlowError(f"years must be iterable; got {years!r}") from exc
    if not raw:
        raise HistoricalFlowError("no years requested (need at least one)")
    if latest is not None and latest < PRISM_FIRST_YEAR:
        raise HistoricalFlowError(
            f"latest year {latest} precedes the PRISM record start "
            f"{PRISM_FIRST_YEAR}"
        )
    clean: set[int] = set()
    for y in raw:
        if isinstance(y, bool) or not isinstance(y, int):
            raise HistoricalFlowError(f"year must be an int; got {y!r}")
        if y < PRISM_FIRST_YEAR:
            raise HistoricalFlowError(
                f"year {y} precedes the PRISM record start {PRISM_FIRST_YEAR}"
            )
        if latest is not None and y > latest:
            raise HistoricalFlowError(
                f"year {y} is after the latest available year {latest}"
            )
        clean.add(y)
    return tuple(sorted(clean))


def year_span(start: int, end: int) -> tuple[int, ...]:
    """Inclusive ascending span of years ``[start, end]`` as a convenience.

    Range-checking against the PRISM record is left to :func:`normalize_years`;
    this only rejects a reversed span.
    """
    if not isinstance(start, int) or not isinstance(end, int) \
            or isinstance(start, bool) or isinstance(end, bool):
        raise HistoricalFlowError(f"start/end must be ints; got {start!r}, {end!r}")
    if start > end:
        raise HistoricalFlowError(f"reversed year span: {start} > {end}")
    return tuple(range(start, end + 1))


def yearly_flow_series(
    provider: ClimateProvider,
    years: object,
    *,
    q_incr: np.ndarray,
    hydroseq: np.ndarray,
    dnhydroseq: np.ndarray,
    latest: int | None = None,
) -> dict[int, np.ndarray]:
    """Per-reach accumulated monthly flow for each requested historical year.

    For every (validated, de-duplicated) year, pull that year's climate from the
    injected ``provider`` and run the shared
    :func:`src.monthly_flow.disaggregate_monthly` against the fixed network
    (``q_incr``/``hydroseq``/``dnhydroseq``). Returns ``{year: flow[n, 12]}``.
    The provider is called exactly once per distinct year.

    Raises :class:`HistoricalFlowError` if a year's climate does not cover the
    same ``n`` reaches as the network arrays.
    """
    n = int(q_incr.shape[0])
    out: dict[int, np.ndarray] = {}
    for year in normalize_years(years, latest=latest):
        clim = provider.climate_for_year(year)
        if clim.reach_count != n:
            raise HistoricalFlowError(
                f"year {year} climate covers {clim.reach_count} reaches, "
                f"network has {n}"
            )
        out[year] = disaggregate_monthly(
            clim.precip_mm, clim.temp_c, q_incr, hydroseq, dnhydroseq
        )
    return out


def annual_mean_series(series: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
    """Collapse each year's ``[n, 12]`` monthly flow to a per-reach annual mean ``[n]``."""
    return {year: flow.mean(axis=1) for year, flow in series.items()}


def peak_month_series(series: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
    """Per-reach 1-based peak-flow month ``[n]`` for each year (argmax + 1)."""
    return {year: (flow.argmax(axis=1) + 1) for year, flow in series.items()}
