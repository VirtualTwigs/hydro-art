"""3DEP DEM tile discovery and caching (Item 12, Epoch 2 Phase 2.2).

Delivery decision (resolved): the primary cache source is the USGS **3DEP
Cloud-Optimized GeoTIFFs on the ``prd-tnm`` AWS S3 bucket** — the same staged-
products bucket the hydrography datasets already use. For the seamless
1 arc-second (``preview``) and 1/3 arc-second (``state``) products, USGS stages
one COG per 1°×1° cell named by the cell's NW corner (e.g. ``n45w124``), so
discovery is *deterministic and offline-constructible* from a lon/lat bounding
box — no discovery API call is required. This mirrors ``datasets.py``, where a
region maps to a fixed set of archive URLs.

Vertical reference (resolved): the first CONUS release normalizes to **NAVD88**.
The 3DEP 1"/13" products are natively NAD83 horizontal (EPSG:4269) and NAVD88
vertical in meters, so for these tiers normalization to NAVD88 is an identity —
recorded here verbatim in each tile's :class:`~src.elevation.ElevationProvenance`.
Any actual datum/units transform for non-NAVD88 sources is enforced later in the
raster-normalization stage (item 13), not here.

Scope: ``preview`` and ``state`` tiers cover CONUS deterministically. The
``local`` (1 m) tier is project/UTM-tiled rather than 1-degree-gridded and needs
project-based discovery; it is intentionally deferred and raises a clear
:class:`~src.elevation.ElevationError` for now. Alaska/other sources are out of
scope but the seam (:class:`~src.elevation.TileDiscoverer`) leaves room for them.

All network and disk I/O reuses the existing injected seams: discovery returns
:class:`~src.elevation.TileRef`s, each bridged to a
:class:`~src.datasets.FileDescriptor` so the persistent :class:`~src.cache.Cache`
and any :class:`~src.cache.DownloaderLike` handle resume/verify/record. No heavy
raster libraries are imported.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from src.cache import Cache, DownloaderLike
from src.datasets import FileDescriptor
from src.elevation import (
    ElevationError,
    ElevationProvenance,
    TileRef,
    build_provenance,
)

__all__ = [
    "DemProduct",
    "DemAsset",
    "TIER_PRODUCTS",
    "geographic_cells",
    "cell_name",
    "ThreeDEPDiscoverer",
    "dem_descriptor",
    "count_tiles",
    "acquire_dem",
]

#: The staged-products S3 bucket USGS publishes 3DEP COGs to (same host as the
#: hydrography archives in ``datasets.py``).
_TNM_ELEVATION_ROOT = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/{product_key}/"
    "TIFF/current/{cell}/USGS_{product_key}_{cell}.tif"
)

_CHUNK = 1 << 16

# The 3DEP seamless products are natively NAD83 / NAVD88 in meters; record this
# verbatim (the resolved "normalize to NAVD88" decision is identity for CONUS).
_SOURCE_HORIZONTAL_CRS = "EPSG:4269"
_SOURCE_VERTICAL_CRS = "NAVD88"
_SOURCE_VERTICAL_UNITS = "meters"


@dataclass(frozen=True)
class DemProduct:
    """A 3DEP staged product tied to a resolution tier.

    Attributes:
        tier: The user-facing resolution tier (``preview``/``state``).
        product_key: The USGS staged-product key used in the S3 path and
            filename (``"1"`` = 1 arc-second, ``"13"`` = 1/3 arc-second).
        label: Human-readable product name recorded in provenance.
        resolution_m: Nominal cell size in meters for this product.
    """

    tier: str
    product_key: str
    label: str
    resolution_m: float

    def url_for(self, cell: str) -> str:
        """Deterministic COG URL for a 1-degree ``cell`` (e.g. ``n45w124``)."""
        return _TNM_ELEVATION_ROOT.format(product_key=self.product_key, cell=cell)


#: Resolution tiers backed by the deterministic 1-degree COG grid. ``local``
#: (1 m) is deliberately absent; it needs project-based discovery (deferred).
TIER_PRODUCTS: dict[str, DemProduct] = {
    "preview": DemProduct("preview", "1", "USGS 3DEP 1 arc-second DEM", 30.0),
    "state": DemProduct("state", "13", "USGS 3DEP 1/3 arc-second DEM", 10.0),
}


@dataclass(frozen=True)
class DemAsset:
    """A discovered-and-cached DEM tile with its lineage.

    Attributes:
        tile: The discovered :class:`~src.elevation.TileRef`.
        path: Local cache path of the retrieved COG.
        provenance: Immutable lineage for this asset.
    """

    tile: TileRef
    path: Path
    provenance: ElevationProvenance


def cell_name(west: int, north: int) -> str:
    """Name the 1°×1° cell whose NW corner is (``north`` lat, ``west`` lon).

    ``west`` is the integer western-edge longitude (negative in CONUS); ``north``
    is the integer northern-edge latitude. E.g. ``cell_name(-124, 45)`` ->
    ``"n45w124"`` covering lon [-124, -123], lat [44, 45].
    """
    return f"n{north:02d}w{abs(west):03d}"


def geographic_cells(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> tuple[str, ...]:
    """Return the sorted 1-degree cell names covering a lon/lat bounding box.

    Cells are indexed by their western-edge longitude (``floor``) and northern-
    edge latitude (``floor(lat) + 1``). The result is sorted for deterministic
    ordering, so identical bounds always yield an identical tuple.
    """
    if min_lon > max_lon or min_lat > max_lat:
        raise ElevationError(
            f"Invalid boundary bounds: ({min_lon}, {min_lat}, {max_lon}, "
            f"{max_lat}); expected min <= max for both axes."
        )
    west_edges = range(math.floor(min_lon), math.ceil(max_lon))
    south_edges = range(math.floor(min_lat), math.ceil(max_lat))
    cells = [
        cell_name(west, south + 1) for west in west_edges for south in south_edges
    ]
    return tuple(sorted(cells))


def _boundary_bounds(boundary: Any) -> tuple[float, float, float, float]:
    """Extract (min_lon, min_lat, max_lon, max_lat) from a geometry or tuple.

    Accepts a shapely-geometry-like object exposing ``.bounds`` or a plain
    4-tuple. Discovery operates in geographic (lon/lat) space because the 3DEP
    1"/13" tiles are named in degrees.
    """
    bounds = getattr(boundary, "bounds", None)
    if bounds is None:
        bounds = boundary
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in bounds)
    return min_lon, min_lat, max_lon, max_lat


class ThreeDEPDiscoverer:
    """:class:`~src.elevation.TileDiscoverer` over the 3DEP 1-degree COG grid.

    Deterministic and offline: for a supported tier it constructs one
    :class:`~src.elevation.TileRef` per 1°×1° cell intersecting the boundary's
    lon/lat bounding box. Unsupported tiers raise
    :class:`~src.elevation.ElevationError`.
    """

    def __init__(self, products: dict[str, DemProduct] | None = None) -> None:
        self._products = products if products is not None else TIER_PRODUCTS

    def discover_tiles(self, boundary: Any, tier: str) -> tuple[TileRef, ...]:
        product = self._products.get(tier)
        if product is None:
            supported = ", ".join(sorted(self._products))
            raise ElevationError(
                f"Elevation tier {tier!r} has no deterministic 3DEP grid; "
                f"supported tiers: {supported}. The 'local' (1 m) tier needs "
                "project-based discovery and is not yet implemented."
            )
        min_lon, min_lat, max_lon, max_lat = _boundary_bounds(boundary)
        cells = geographic_cells(min_lon, min_lat, max_lon, max_lat)
        return tuple(
            TileRef(
                tile_id=cell,
                url=product.url_for(cell),
                resolution_m=product.resolution_m,
            )
            for cell in cells
        )


def count_tiles(
    boundary: Any,
    tier: str,
    discoverer: ThreeDEPDiscoverer | None = None,
) -> int:
    """Count the DEM tiles a region will need, without downloading anything.

    A pure, offline preflight for the tile budget (roadmap #21): callers (and the
    UX) can estimate acquisition size up front and decide whether to proceed.

    Raises:
        ElevationError: If ``tier`` is unsupported (via the discoverer).
    """
    discoverer = discoverer or ThreeDEPDiscoverer()
    return len(discoverer.discover_tiles(boundary, tier))


def dem_descriptor(tile: TileRef, product_key: str) -> FileDescriptor:
    """Bridge a :class:`~src.elevation.TileRef` to a cache descriptor.

    Reuses the existing :class:`~src.cache.Cache` layout: DEM tiles land under
    ``cache/dem/<product_key>/<filename>`` with a shared metadata index.
    """
    filename = tile.url.rsplit("/", 1)[-1]
    return FileDescriptor(
        dataset_id="dem",
        huc4=product_key,
        filename=filename,
        url=tile.url,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _noop(_message: str) -> None:
    """Default logger that discards messages."""


def acquire_dem(
    *,
    boundary: Any,
    tier: str,
    cache: Cache,
    downloader: DownloaderLike,
    discoverer: ThreeDEPDiscoverer | None = None,
    refresh: bool = False,
    max_tiles: int = 0,
    log: Callable[[str], None] = _noop,
    clock: Callable[[], str] = lambda: date.today().isoformat(),
) -> list[DemAsset]:
    """Discover, cache, and record provenance for the DEM tiles of a region.

    For each tile covering ``boundary`` at ``tier``: reuse the cached COG when
    present (``refresh=False``, the ``reuse`` cache policy) or re-download it
    (``refresh=True``, the ``refresh`` policy); then compute its content checksum
    and build an :class:`~src.elevation.ElevationProvenance` recording the source
    product/URL, retrieval date, horizontal + vertical CRS/units, cell size, and
    lineage.

    ``max_tiles`` is the tile budget (roadmap #21): ``0`` means unlimited, while a
    positive cap makes acquisition **fail fast before any download** when the
    region's discovered tile count exceeds it (feed it
    ``settings.elevation.tile_budget``).

    Returns the assets in the discoverer's deterministic order.

    Raises:
        ElevationError: If ``tier`` is unsupported (via the discoverer) or the
            discovered tile count exceeds ``max_tiles``.
    """
    discoverer = discoverer or ThreeDEPDiscoverer()
    product = TIER_PRODUCTS[tier] if tier in TIER_PRODUCTS else None
    tiles = discoverer.discover_tiles(boundary, tier)
    if max_tiles and len(tiles) > max_tiles:
        raise ElevationError(
            f"DEM acquisition needs {len(tiles)} tiles for tier {tier!r}, "
            f"exceeding the tile budget of {max_tiles}. Raise "
            "elevation.tile_budget, narrow the boundary, or choose a coarser "
            "tier (0 = unlimited)."
        )
    # If a custom discoverer produced tiles for a tier not in the registry we
    # still need a product label/key; fall back to the tile's own resolution.
    acquired_at = clock()

    assets: list[DemAsset] = []
    for tile in tiles:
        product_key = product.product_key if product is not None else tier
        descriptor = dem_descriptor(tile, product_key)
        if refresh or not cache.has(descriptor):
            log(f"downloading {descriptor.key}")
            downloader.fetch(descriptor, cache.path_for(descriptor))
            cache.record(descriptor)
        else:
            log(f"cached {descriptor.key}")

        path = cache.path_for(descriptor)
        provenance = build_provenance(
            source_product=(
                product.label if product is not None else f"3DEP tier {tier}"
            ),
            source_url=tile.url,
            acquisition_date=acquired_at,
            horizontal_crs=_SOURCE_HORIZONTAL_CRS,
            vertical_crs=_SOURCE_VERTICAL_CRS,
            vertical_units=_SOURCE_VERTICAL_UNITS,
            resolution_m=tile.resolution_m,
            checksum="sha256:" + _sha256(path),
            processing_parameters={"tier": tier, "delivery": "3dep-cog-s3"},
        )
        assets.append(DemAsset(tile=tile, path=path, provenance=provenance))
    return assets
