"""Tests for the package preflight planner (roadmap #21, offline slice).

Offline and deterministic. Uses a real :class:`src.cache.Cache` in ``tmp_path``
plus hand-written archive files (no network / GDAL / NAS). The module under test
imports only stdlib + src.manifest/datasets/config/cache; the DEM tile count is
injected, never computed here, so the suite stays fully offline.
"""

from __future__ import annotations

import pytest

from src.cache import Cache
from src.config import build_settings
from src.datasets import resolve_required_files
from src.packaging import PackagePlan, format_plan, plan_package


def _settings():
    return build_settings({"region": ["Oregon"]})


def _cache_with(tmp_path, descriptors, *, payload=b"hydro-archive", name="cache"):
    """Build a Cache and record a payload file for each descriptor."""
    cache = Cache(tmp_path / name)
    for d in descriptors:
        path = cache.path_for(d)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        cache.record(d)
    return cache


# --- TG-P1: cache-coverage planning ---------------------------------------

def test_full_coverage_is_complete(tmp_path):
    settings = _settings()
    required = resolve_required_files(settings)
    cache = _cache_with(tmp_path, required)
    plan = plan_package(cache, settings)
    assert isinstance(plan, PackagePlan)
    keys = [d.key for d in required]
    assert list(plan.required) == keys
    assert set(plan.present) == set(keys)
    assert plan.missing == ()
    assert plan.corrupt == ()
    assert plan.is_complete
    assert plan.total_bytes == len(b"hydro-archive") * len(keys)


def test_missing_required_file_is_reported(tmp_path):
    settings = _settings()
    required = resolve_required_files(settings)
    cache = _cache_with(tmp_path, required[1:])  # omit the first required file
    plan = plan_package(cache, settings)
    assert required[0].key in plan.missing
    assert required[0].key not in plan.present
    assert not plan.is_complete


def test_corrupt_cached_file_is_reported(tmp_path):
    settings = _settings()
    required = resolve_required_files(settings)
    cache = _cache_with(tmp_path, required)
    # Mutate one file on disk after it was recorded → checksum mismatch.
    cache.path_for(required[0]).write_bytes(b"tampered-different-length")
    plan = plan_package(cache, settings)
    assert required[0].key in plan.corrupt
    assert required[0].key not in plan.present
    assert not plan.is_complete


def test_plan_is_deterministic(tmp_path):
    settings = _settings()
    cache = _cache_with(tmp_path, resolve_required_files(settings))
    assert plan_package(cache, settings) == plan_package(cache, settings)


# --- TG-P2: tile-budget preflight + readiness + formatting -----------------

def test_tile_budget_preflight(tmp_path):
    settings = build_settings(
        {"region": ["Oregon"], "elevation": {"enabled": True, "tile_budget": 10}}
    )
    cache = _cache_with(tmp_path, resolve_required_files(settings))
    assert plan_package(cache, settings, tile_count=8).within_tile_budget
    assert not plan_package(cache, settings, tile_count=12).within_tile_budget
    # tile_count omitted → preflight skipped → considered within budget.
    assert plan_package(cache, settings).within_tile_budget


def test_unlimited_budget_and_readiness(tmp_path):
    settings = _settings()  # tile_budget defaults to 0 (unlimited)
    cache = _cache_with(tmp_path, resolve_required_files(settings))
    plan = plan_package(cache, settings, tile_count=9999)
    assert plan.within_tile_budget  # 0 = unlimited
    assert plan.is_ready  # complete AND within budget

    # An incomplete cache is not ready even within budget.
    partial = _cache_with(tmp_path, resolve_required_files(settings)[2:], name="partial")
    assert not plan_package(partial, settings, tile_count=1).is_ready


def test_format_plan_summary(tmp_path):
    settings = _settings()
    required = resolve_required_files(settings)
    cache = _cache_with(tmp_path, required[1:])  # one missing
    text = format_plan(plan_package(cache, settings))
    assert isinstance(text, str)
    assert "missing" in text.lower()
    assert "1" in text  # the one missing file is surfaced
