"""Elevation provenance model and injected seams (Item 11, Epoch 2 Phase 2.1).

This module defines the *contract* for DEM-backed elevation without performing
any raster I/O. It provides:

- :class:`ElevationProvenance` — immutable metadata recording exactly where a
  height came from (source product/URL, acquisition date, horizontal + vertical
  CRS/datum, units, nominal cell size, checksum, and processing lineage), plus
  :func:`build_provenance` which validates it at the boundary.
- Value objects :class:`TileRef` and :class:`ElevationSample` returned by the
  discovery and sampling seams.
- Plain (structural) protocols :class:`TileDiscoverer`, :class:`RasterReader`,
  and :class:`ElevationSampler`, mirroring the existing downloader/loader/
  exporter seams so later items (12/13/14) inject real GDAL-backed
  implementations while tests inject fakes.

Design constraints carried from the requirements:

- **Provenance records the source vertical reference verbatim.** The DEM's own
  vertical CRS/datum and units are stored as-is; when a source states none, the
  fields stay ``None`` rather than inventing a datum. This module never
  normalizes — the resolved product decision to normalize to NAVD88 is enforced
  in the raster-normalization stage (item 13), not in the provenance contract.
  (3DEP 1"/13" tiles are natively NAVD88, so that transform is identity there.)
- Heavy raster libraries are never imported here; they belong behind the
  injected seams, keeping this module (and the pipeline) importable offline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from src.datasets import AcquisitionError

__all__ = [
    "ElevationError",
    "ElevationProvenance",
    "ElevationSample",
    "ElevationSampler",
    "RasterReader",
    "TileDiscoverer",
    "TileRef",
    "build_provenance",
]


class ElevationError(AcquisitionError):
    """Raised when elevation assets or provenance are missing or invalid.

    Subclasses :class:`~src.datasets.AcquisitionError` so ``build.py`` maps it
    to the acquisition exit code (2), consistent with the DEM stages being an
    acquisition concern. The message is intended to be shown to the user.
    """


@dataclass(frozen=True)
class ElevationProvenance:
    """Immutable lineage for a single elevation asset (requirements.md #3).

    Every elevation artifact must be auditable back to its authoritative
    source. The vertical fields are optional because not every DEM states a
    datum/units; when absent they are recorded as ``None`` and preserved as-is
    (never normalized).

    Attributes:
        source_product: Human-readable product name (e.g. "USGS 3DEP 1/3
            arc-second DEM").
        source_url: URL the asset was retrieved from.
        acquisition_date: Retrieval/publication date (ISO ``YYYY-MM-DD``).
        horizontal_crs: Source horizontal CRS (e.g. ``"EPSG:4269"``).
        vertical_crs: Source vertical CRS/datum when supplied (e.g.
            ``"NAVD88"``), else ``None``.
        vertical_units: Source vertical units when supplied (e.g.
            ``"meters"``), else ``None``.
        resolution_m: Nominal cell size in meters; must be > 0.
        checksum: Content hash of the retrieved asset (e.g. ``"sha256:..."``).
        processing_parameters: Immutable record of the lineage/processing
            applied (resampling, clip, reproject params, etc.).
    """

    source_product: str
    source_url: str
    acquisition_date: str
    horizontal_crs: str
    vertical_crs: str | None
    vertical_units: str | None
    resolution_m: float
    checksum: str
    processing_parameters: Mapping[str, Any]


#: Provenance fields that must always be present (the vertical datum/units are
#: intentionally excluded — a source may legitimately state neither).
_REQUIRED_PROVENANCE_FIELDS: tuple[str, ...] = (
    "source_product",
    "source_url",
    "acquisition_date",
    "horizontal_crs",
    "checksum",
)


def build_provenance(
    *,
    source_product: str,
    source_url: str,
    acquisition_date: str,
    horizontal_crs: str,
    vertical_crs: str | None,
    vertical_units: str | None,
    resolution_m: float,
    checksum: str,
    processing_parameters: Mapping[str, Any] | None = None,
) -> ElevationProvenance:
    """Validate and construct an :class:`ElevationProvenance`.

    Required identity fields must be non-empty; ``resolution_m`` must be > 0.
    The vertical CRS/units are preserved verbatim (including ``None``) — this
    function never substitutes a default datum.

    Raises:
        ElevationError: If a required field is empty or ``resolution_m`` <= 0.
    """
    provided = {
        "source_product": source_product,
        "source_url": source_url,
        "acquisition_date": acquisition_date,
        "horizontal_crs": horizontal_crs,
        "checksum": checksum,
    }
    for field_name in _REQUIRED_PROVENANCE_FIELDS:
        value = provided[field_name]
        if value is None or str(value).strip() == "":
            raise ElevationError(
                f"Elevation provenance is missing required field {field_name!r}."
            )

    try:
        resolution = float(resolution_m)
    except (TypeError, ValueError):
        raise ElevationError(
            f"Invalid provenance resolution_m: {resolution_m!r}. "
            "Expected a positive number of meters."
        )
    if resolution <= 0:
        raise ElevationError(
            f"Provenance resolution_m must be greater than 0, got {resolution}."
        )

    return ElevationProvenance(
        source_product=source_product,
        source_url=source_url,
        acquisition_date=acquisition_date,
        horizontal_crs=horizontal_crs,
        vertical_crs=vertical_crs,
        vertical_units=vertical_units,
        resolution_m=resolution,
        checksum=checksum,
        processing_parameters=dict(processing_parameters or {}),
    )


@dataclass(frozen=True)
class TileRef:
    """A reference to one DEM tile discovered for a region/tier.

    Attributes:
        tile_id: Stable identifier for the tile (e.g. a USGS cell name).
        url: Location the tile can be fetched from.
        resolution_m: Nominal cell size in meters for this tile.
    """

    tile_id: str
    url: str
    resolution_m: float


@dataclass(frozen=True)
class ElevationSample:
    """The result of sampling ground elevation at a projected point.

    Attributes:
        value_m: Sampled elevation in meters, or ``None`` when not covered.
        covered: Whether the point falls within loaded raster coverage.
        nodata: Whether the sample resolved to a raster nodata value.
    """

    value_m: float | None
    covered: bool
    nodata: bool


class TileDiscoverer(Protocol):
    """Seam that lists the DEM tiles covering a boundary at a resolution tier.

    A plain (non ``runtime_checkable``) protocol: implementations are matched
    structurally, and consumers depend only on the method signature.
    """

    def discover_tiles(self, boundary: Any, tier: str) -> Sequence[TileRef]:
        ...


class RasterReader(Protocol):
    """Seam that reads a windowed array of samples from a DEM tile."""

    def read_window(self, tile: TileRef, bounds: Any) -> Any:
        ...


class ElevationSampler(Protocol):
    """Seam that samples ground elevation at a projected (x, y) point."""

    def sample(self, x: float, y: float) -> ElevationSample:
        ...
