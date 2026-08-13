"""Tests for 3DEP DEM tile discovery and caching (Item 12, Epoch 2 Phase 2.2).

Fully offline: discovery is deterministic (a 1-degree COG grid on the USGS
``prd-tnm`` S3 bucket, constructed from a lon/lat bbox — no network), and the
download seam is a fake that writes bytes to the cache path. No GDAL, no raster
libraries, no real DEM assets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cache import Cache
from src.config import build_settings
from src.datasets import FileDescriptor
from src.dem import (
    TIER_PRODUCTS,
    DemAsset,
    ThreeDEPDiscoverer,
    acquire_dem,
    acquire_dem_for_settings,
    count_tiles,
    geographic_cells,
)
from src.elevation import ElevationError, TileRef


class _FakeBoundary:
    """A shapely-geometry-like object exposing ``.bounds`` in lon/lat."""

    def __init__(self, bounds: tuple[float, float, float, float]) -> None:
        self.bounds = bounds


class _FakeDownloader:
    """A :class:`~src.cache.DownloaderLike` that writes deterministic bytes."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, descriptor: FileDescriptor, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-dem:" + descriptor.url.encode())
        self.calls.append(descriptor.key)
        return dest


def test_geographic_cells_names_one_degree_grid() -> None:
    # bbox lon [-123.5, -122.5], lat [44.2, 45.1] spans two lon and two lat cells.
    cells = geographic_cells(-123.5, 44.2, -122.5, 45.1)
    assert set(cells) == {"n45w124", "n46w124", "n45w123", "n46w123"}
    # Deterministic ordering (sorted) so repeat calls are identical.
    assert list(cells) == sorted(cells)
    assert list(cells) == list(geographic_cells(-123.5, 44.2, -122.5, 45.1))


def test_discover_preview_tier_builds_1_arcsecond_cog_urls() -> None:
    tiles = ThreeDEPDiscoverer().discover_tiles(
        _FakeBoundary((-123.8, 44.2, -123.2, 44.8)), "preview"
    )
    assert [t.tile_id for t in tiles] == ["n45w124"]
    tile = tiles[0]
    assert tile.resolution_m == 30.0
    assert tile.url == (
        "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/"
        "current/n45w124/USGS_1_n45w124.tif"
    )


def test_discover_state_tier_uses_13_arcsecond_product() -> None:
    tiles = ThreeDEPDiscoverer().discover_tiles((-123.8, 44.2, -123.2, 44.8), "state")
    tile = tiles[0]
    assert tile.resolution_m == 10.0
    assert "/Elevation/13/TIFF/current/n45w124/USGS_13_n45w124.tif" in tile.url


def test_discover_unsupported_tier_raises() -> None:
    with pytest.raises(ElevationError, match="local"):
        ThreeDEPDiscoverer().discover_tiles((-123.8, 44.2, -123.2, 44.8), "local")


def test_tier_products_registry_covers_preview_and_state() -> None:
    assert set(TIER_PRODUCTS) == {"preview", "state"}


def test_acquire_dem_downloads_caches_and_records_provenance(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    assets = acquire_dem(
        boundary=(-123.8, 44.2, -123.2, 44.8),
        tier="preview",
        cache=cache,
        downloader=downloader,
        clock=lambda: "2026-07-30",
    )
    assert [a.tile.tile_id for a in assets] == ["n45w124"]
    assert len(downloader.calls) == 1

    asset = assets[0]
    assert isinstance(asset, DemAsset)
    assert asset.path.exists()
    prov = asset.provenance
    assert prov.source_product == "USGS 3DEP 1 arc-second DEM"
    assert prov.horizontal_crs == "EPSG:4269"
    assert prov.vertical_crs == "NAVD88"
    assert prov.vertical_units == "meters"
    assert prov.resolution_m == 30.0
    assert prov.acquisition_date == "2026-07-30"
    assert prov.checksum.startswith("sha256:")
    assert prov.processing_parameters["tier"] == "preview"


def test_acquire_dem_reuses_cache_on_second_call(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    boundary = (-123.8, 44.2, -123.2, 44.8)
    acquire_dem(boundary=boundary, tier="preview", cache=cache, downloader=downloader)
    acquire_dem(boundary=boundary, tier="preview", cache=cache, downloader=downloader)
    assert len(downloader.calls) == 1  # second call is a pure cache hit


def test_acquire_dem_refresh_forces_redownload(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    boundary = (-123.8, 44.2, -123.2, 44.8)
    acquire_dem(boundary=boundary, tier="preview", cache=cache, downloader=downloader)
    acquire_dem(
        boundary=boundary,
        tier="preview",
        cache=cache,
        downloader=downloader,
        refresh=True,
    )
    assert len(downloader.calls) == 2


def test_count_tiles_matches_discovery(tmp_path: Path) -> None:
    # bbox spanning two lon x two lat cells -> 4 tiles, computed offline.
    boundary = _FakeBoundary((-123.5, 44.2, -122.5, 45.1))
    assert count_tiles(boundary, "preview") == 4
    assert count_tiles(boundary, "preview") == len(
        ThreeDEPDiscoverer().discover_tiles(boundary, "preview")
    )


def test_acquire_dem_within_budget_proceeds(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    assets = acquire_dem(
        boundary=(-123.8, 44.2, -123.2, 44.8),  # single tile
        tier="preview",
        cache=cache,
        downloader=downloader,
        max_tiles=1,
    )
    assert len(assets) == 1 and len(downloader.calls) == 1


def test_acquire_dem_over_budget_raises_before_any_fetch(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    with pytest.raises(ElevationError, match="tile budget"):
        acquire_dem(
            boundary=(-123.5, 44.2, -122.5, 45.1),  # 4 tiles
            tier="preview",
            cache=cache,
            downloader=downloader,
            max_tiles=2,
        )
    # Fail fast: nothing was downloaded.
    assert downloader.calls == []


def test_acquire_dem_zero_budget_is_unlimited(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    assets = acquire_dem(
        boundary=(-123.5, 44.2, -122.5, 45.1),  # 4 tiles
        tier="preview",
        cache=cache,
        downloader=downloader,
        max_tiles=0,  # unlimited
    )
    assert len(assets) == 4 and len(downloader.calls) == 4


# --- TG-W1: settings-driven acquisition entry point (tile-budget wiring) ----


def _elev_settings(**elevation):
    """Build Settings with an elevation block (enabled by default here)."""
    elevation = {"enabled": True, "tier": "preview", **elevation}
    return build_settings({"region": ["Oregon"], "elevation": elevation})


def test_acquire_dem_for_settings_reads_tier_and_budget(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    settings = _elev_settings(tier="preview", tile_budget=1)
    assets = acquire_dem_for_settings(
        settings,
        boundary=(-123.8, 44.2, -123.2, 44.8),  # single preview tile
        cache=cache,
        downloader=downloader,
    )
    assert len(assets) == 1 and len(downloader.calls) == 1
    # Tier came from settings → 1 arc-second (preview) product at 30 m.
    assert assets[0].tile.resolution_m == 30.0


def test_acquire_dem_for_settings_over_budget_fails_fast(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    settings = _elev_settings(tier="preview", tile_budget=2)
    with pytest.raises(ElevationError, match="tile budget"):
        acquire_dem_for_settings(
            settings,
            boundary=(-123.5, 44.2, -122.5, 45.1),  # 4 tiles > budget 2
            cache=cache,
            downloader=downloader,
        )
    assert downloader.calls == []  # fail fast: nothing downloaded


def test_acquire_dem_for_settings_zero_budget_is_unlimited(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    settings = _elev_settings(tier="preview")  # tile_budget defaults to 0
    assert settings.elevation.tile_budget == 0
    assets = acquire_dem_for_settings(
        settings,
        boundary=(-123.5, 44.2, -122.5, 45.1),  # 4 tiles
        cache=cache,
        downloader=downloader,
    )
    assert len(assets) == 4 and len(downloader.calls) == 4


def test_acquire_dem_for_settings_disabled_raises_before_discovery(
    tmp_path: Path,
) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    settings = _elev_settings(enabled=False)
    with pytest.raises(ElevationError, match="disabled"):
        acquire_dem_for_settings(
            settings,
            boundary=(-123.8, 44.2, -123.2, 44.8),
            cache=cache,
            downloader=downloader,
        )
    assert downloader.calls == []  # nothing discovered or fetched


def test_acquire_dem_for_settings_refresh_policy_redownloads(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "cache")
    downloader = _FakeDownloader()
    boundary = (-123.8, 44.2, -123.2, 44.8)
    refresh = _elev_settings(cache_policy="refresh")
    acquire_dem_for_settings(refresh, boundary=boundary, cache=cache, downloader=downloader)
    acquire_dem_for_settings(refresh, boundary=boundary, cache=cache, downloader=downloader)
    assert len(downloader.calls) == 2  # refresh policy re-downloads

    # Default "reuse" policy → the second call is a pure cache hit.
    reuse_dl = _FakeDownloader()
    reuse = _elev_settings(cache_policy="reuse")
    acquire_dem_for_settings(reuse, boundary=boundary, cache=cache, downloader=reuse_dl)
    assert len(reuse_dl.calls) == 0  # already cached by the refresh run above


def test_acquire_dem_is_deterministic(tmp_path: Path) -> None:
    def run(root: str) -> list[tuple[str, str, str]]:
        cache = Cache(tmp_path / root)
        assets = acquire_dem(
            boundary=(-124.6, 44.0, -122.9, 45.2),
            tier="state",
            cache=cache,
            downloader=_FakeDownloader(),
            clock=lambda: "2026-07-30",
        )
        return [(a.tile.tile_id, a.tile.url, a.provenance.checksum) for a in assets]

    assert run("a") == run("b")
