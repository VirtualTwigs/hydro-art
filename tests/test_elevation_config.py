"""Tests for elevation settings + CLI precedence (Item 11, DEM Task Group 1).

Covers the `elevation` config block: validated defaults (disabled by default),
field validation against the source/tier/cache-policy allowlists, YAML
overrides, and sub-key CLI precedence (deep-merge). The block adds no pipeline
behavior yet — DEM acquisition is item 12 — so a default build stays 2D.
"""

import pytest

from src.cli import resolve_settings
from src.config import DEFAULTS, ConfigError, build_settings


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return str(path)


def test_elevation_disabled_by_default_with_preview_tier():
    ev = build_settings(DEFAULTS).elevation
    assert ev.enabled is False
    assert ev.source == "3dep"
    assert ev.tier == "preview"
    assert ev.vertical_exaggeration == 1.0
    assert ev.cache_policy == "reuse"


def test_partial_elevation_dict_fills_missing_from_defaults():
    settings = build_settings({**DEFAULTS, "elevation": {"enabled": True}})
    assert settings.elevation.enabled is True
    # Untouched sub-keys still take their defaults.
    assert settings.elevation.tier == "preview"
    assert settings.elevation.vertical_exaggeration == 1.0


def test_invalid_tier_raises():
    with pytest.raises(ConfigError, match="tier"):
        build_settings({**DEFAULTS, "elevation": {"tier": "planet"}})


def test_invalid_source_raises():
    with pytest.raises(ConfigError, match="source"):
        build_settings({**DEFAULTS, "elevation": {"source": "srtm"}})


def test_invalid_cache_policy_raises():
    with pytest.raises(ConfigError, match="cache_policy"):
        build_settings({**DEFAULTS, "elevation": {"cache_policy": "always"}})


def test_non_positive_vertical_exaggeration_raises():
    with pytest.raises(ConfigError, match="vertical_exaggeration"):
        build_settings({**DEFAULTS, "elevation": {"vertical_exaggeration": 0}})


def test_tile_budget_defaults_to_unlimited():
    # 0 means "no cap" (mirrors the area-threshold convention).
    assert build_settings(DEFAULTS).elevation.tile_budget == 0


def test_positive_tile_budget_accepted():
    settings = build_settings({**DEFAULTS, "elevation": {"tile_budget": 12}})
    assert settings.elevation.tile_budget == 12


def test_negative_tile_budget_raises():
    with pytest.raises(ConfigError, match="tile_budget"):
        build_settings({**DEFAULTS, "elevation": {"tile_budget": -1}})


def test_non_integer_tile_budget_raises():
    with pytest.raises(ConfigError, match="tile_budget"):
        build_settings({**DEFAULTS, "elevation": {"tile_budget": "many"}})


def test_yaml_elevation_override(tmp_path):
    path = _write(
        tmp_path, "elevation:\n  enabled: true\n  tier: state\n"
    )
    settings = resolve_settings(["--config", path])
    assert settings.elevation.enabled is True
    assert settings.elevation.tier == "state"
    # A sub-key not set in YAML keeps its default.
    assert settings.elevation.cache_policy == "reuse"


def test_cli_elevation_overrides_yaml_but_keeps_other_subkeys(tmp_path):
    path = _write(
        tmp_path, "elevation:\n  enabled: false\n  vertical_exaggeration: 2.5\n"
    )
    settings = resolve_settings(["--config", path, "--elevation"])
    assert settings.elevation.enabled is True
    # CLI toggled only `enabled`; the YAML vertical_exaggeration survives.
    assert settings.elevation.vertical_exaggeration == 2.5


def test_cli_tier_and_exaggeration_override():
    settings = resolve_settings(
        ["--elevation-tier", "local", "--vertical-exaggeration", "1.75"]
    )
    assert settings.elevation.tier == "local"
    assert settings.elevation.vertical_exaggeration == 1.75


def test_default_2d_build_has_elevation_disabled():
    # Item 11 must not change default 2D behavior: elevation stays off.
    assert build_settings(DEFAULTS).elevation.enabled is False
