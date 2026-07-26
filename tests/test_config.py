"""Tests for the settings model, defaults, and validation (Task Group 1)."""

import dataclasses

import pytest

from src.config import DEFAULTS, ConfigError, Settings, build_settings


def test_defaults_build_valid_settings():
    settings = build_settings(DEFAULTS)
    assert settings.regions == ("Oregon", "Washington")
    assert settings.projection == "EPSG:5070"
    assert settings.background == "#000000"
    assert settings.line_width == 0.35
    assert settings.palette == "neon"
    assert settings.glow is False
    assert settings.outputs == frozenset({"svg"})


def test_region_is_normalized_case_insensitively():
    settings = build_settings({**DEFAULTS, "region": ["washington"]})
    assert settings.regions == ("Washington",)


def test_unsupported_region_raises():
    with pytest.raises(ConfigError, match="Unsupported region"):
        build_settings({**DEFAULTS, "region": ["Idaho"]})


def test_invalid_background_hex_raises():
    with pytest.raises(ConfigError, match="Invalid background color"):
        build_settings({**DEFAULTS, "background": "black"})


def test_non_positive_line_width_raises():
    with pytest.raises(ConfigError, match="greater than 0"):
        build_settings({**DEFAULTS, "line_width": 0})


def test_settings_is_immutable():
    settings = build_settings(DEFAULTS)
    assert dataclasses.is_dataclass(settings)
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.line_width = 1.0  # type: ignore[misc]
