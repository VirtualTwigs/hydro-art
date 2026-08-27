"""Offline unit tests for the pure historical-flow engine (numpy only, no GDAL).

A fake :class:`ClimateProvider` supplies hand-built per-year climate so the whole
year-over-year machinery is exercised without PRISM/rasterio.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.historical_flow import (
    PRISM_FIRST_YEAR,
    ClimateProvider,
    HistoricalFlowError,
    YearlyClimate,
    annual_mean_series,
    normalize_years,
    peak_month_series,
    year_span,
    yearly_flow_series,
)
from src.monthly_flow import disaggregate_monthly


# --- a tiny 3-reach headwater->mouth chain ---------------------------------
# hydroseq descends downstream; reach 0 (largest hydroseq) is the headwater,
# reach 2 (dnhydroseq 0) is the mouth.
HYDROSEQ = np.array([3.0, 2.0, 1.0])
DNHYDROSEQ = np.array([2.0, 1.0, 0.0])
Q_INCR = np.array([1.0, 1.0, 1.0])
N = 3


def _uniform_climate(year: int, *, temp: float = 12.0, precip: float = 50.0) -> YearlyClimate:
    """A warm, evenly-wet year: no snow, flat monthly shape."""
    return YearlyClimate(
        year=year,
        precip_mm=np.full((N, 12), precip),
        temp_c=np.full((N, 12), temp),
    )


def _july_spike_climate(year: int) -> YearlyClimate:
    """Warm year with all precip in July -> flow must peak in July."""
    precip = np.zeros((N, 12))
    precip[:, 6] = 100.0  # index 6 == July
    return YearlyClimate(year=year, precip_mm=precip, temp_c=np.full((N, 12), 15.0))


class FakeProvider:
    """Records how many times each year is fetched."""

    def __init__(self, by_year: dict[int, YearlyClimate]) -> None:
        self._by_year = by_year
        self.calls: list[int] = []

    def climate_for_year(self, year: int) -> YearlyClimate:
        self.calls.append(year)
        return self._by_year[year]


def test_prism_first_year_constant() -> None:
    assert PRISM_FIRST_YEAR == 1895


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(FakeProvider({}), ClimateProvider)


def test_normalize_years_dedup_and_sorts() -> None:
    assert normalize_years([2001, 1999, 2001, 2000]) == (1999, 2000, 2001)


@pytest.mark.parametrize(
    "years, latest",
    [
        ([1894], None),          # before the PRISM record
        ([2050], 2023),          # after the latest available year
        ([], None),              # empty request
        ([2000.5], None),        # non-integer
        ([True], None),          # bool is not a valid year
    ],
)
def test_normalize_years_rejects_bad_requests(years, latest) -> None:
    with pytest.raises(HistoricalFlowError):
        normalize_years(years, latest=latest)


def test_year_span_inclusive_and_ascending() -> None:
    assert year_span(1998, 2001) == (1998, 1999, 2000, 2001)


def test_year_span_rejects_reversed() -> None:
    with pytest.raises(HistoricalFlowError):
        year_span(2001, 1998)


@pytest.mark.parametrize(
    "precip, temp",
    [
        (np.zeros((N, 6)), np.zeros((N, 6))),   # not 12 columns
        (np.zeros((N, 12)), np.zeros((N + 1, 12))),  # mismatched shapes
    ],
)
def test_yearly_climate_validates_shape(precip, temp) -> None:
    with pytest.raises(HistoricalFlowError):
        YearlyClimate(year=2000, precip_mm=precip, temp_c=temp)


def test_yearly_flow_series_matches_disaggregate_monthly() -> None:
    clim = _july_spike_climate(2010)
    provider = FakeProvider({2010: clim})
    series = yearly_flow_series(
        provider, [2010], q_incr=Q_INCR, hydroseq=HYDROSEQ, dnhydroseq=DNHYDROSEQ
    )
    expected = disaggregate_monthly(
        clim.precip_mm, clim.temp_c, Q_INCR, HYDROSEQ, DNHYDROSEQ
    )
    assert set(series) == {2010}
    assert series[2010].shape == (N, 12)
    np.testing.assert_allclose(series[2010], expected)


def test_yearly_flow_series_calls_provider_once_per_distinct_year() -> None:
    provider = FakeProvider({y: _uniform_climate(y) for y in (2000, 2001)})
    yearly_flow_series(
        provider,
        [2001, 2000, 2001, 2000],  # duplicates collapse
        q_incr=Q_INCR,
        hydroseq=HYDROSEQ,
        dnhydroseq=DNHYDROSEQ,
    )
    assert sorted(provider.calls) == [2000, 2001]


def test_yearly_flow_series_rejects_reach_count_mismatch() -> None:
    # climate covers 4 reaches, network has 3
    bad = YearlyClimate(
        year=2005, precip_mm=np.zeros((N + 1, 12)), temp_c=np.zeros((N + 1, 12))
    )
    provider = FakeProvider({2005: bad})
    with pytest.raises(HistoricalFlowError):
        yearly_flow_series(
            provider, [2005], q_incr=Q_INCR, hydroseq=HYDROSEQ, dnhydroseq=DNHYDROSEQ
        )


def test_july_spike_year_peaks_in_july() -> None:
    provider = FakeProvider({2012: _july_spike_climate(2012)})
    series = yearly_flow_series(
        provider, [2012], q_incr=Q_INCR, hydroseq=HYDROSEQ, dnhydroseq=DNHYDROSEQ
    )
    peaks = peak_month_series(series)
    assert np.all(peaks[2012] == 7)  # every reach peaks in July


def test_annual_mean_series_collapses_to_per_reach_means() -> None:
    provider = FakeProvider({2000: _uniform_climate(2000)})
    series = yearly_flow_series(
        provider, [2000], q_incr=Q_INCR, hydroseq=HYDROSEQ, dnhydroseq=DNHYDROSEQ
    )
    means = annual_mean_series(series)
    assert means[2000].shape == (N,)
    # a flat year: each reach's annual mean equals its accumulated increment
    np.testing.assert_allclose(means[2000], series[2000].mean(axis=1))
    # mass conservation: mouth accumulates all three unit increments
    assert means[2000][2] == pytest.approx(3.0)
