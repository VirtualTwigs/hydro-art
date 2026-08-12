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


# --- Art-direction options (roadmap #23) ------------------------------------


def test_art_direction_defaults_are_byte_identical_baseline():
    settings = build_settings(DEFAULTS)
    assert settings.color_by == "watershed"
    assert settings.single_color == "#00ffff"
    assert settings.width_by == "uniform"
    assert settings.width_min == 0.35
    assert settings.width_max == 2.0
    assert settings.width_gamma == 1.0


def test_color_by_and_width_by_are_normalized_and_accepted():
    settings = build_settings(
        {**DEFAULTS, "color_by": "SINGLE", "width_by": "Flow"}
    )
    assert settings.color_by == "single"
    assert settings.width_by == "flow"


def test_unsupported_color_by_raises():
    with pytest.raises(ConfigError, match="Unsupported color_by"):
        build_settings({**DEFAULTS, "color_by": "rainbow"})


def test_unsupported_width_by_raises():
    with pytest.raises(ConfigError, match="Unsupported width_by"):
        build_settings({**DEFAULTS, "width_by": "thickness"})


def test_invalid_single_color_hex_raises():
    with pytest.raises(ConfigError, match="Invalid single_color"):
        build_settings({**DEFAULTS, "single_color": "cyan"})


def test_non_positive_width_min_raises():
    with pytest.raises(ConfigError, match="width_min must be greater than 0"):
        build_settings({**DEFAULTS, "width_min": 0})


def test_width_max_below_width_min_raises():
    with pytest.raises(ConfigError, match="width_max must be >= width_min"):
        build_settings({**DEFAULTS, "width_min": 1.0, "width_max": 0.5})


def test_non_positive_width_gamma_raises():
    with pytest.raises(ConfigError, match="width_gamma must be greater than 0"):
        build_settings({**DEFAULTS, "width_gamma": 0})


# --- County scope (roadmap #24) ---------------------------------------------


def test_county_defaults_to_none():
    settings = build_settings(DEFAULTS)
    assert settings.county is None


def test_single_region_county_is_accepted_and_stripped():
    settings = build_settings(
        {**DEFAULTS, "region": ["Oregon"], "county": "  Multnomah  "}
    )
    assert settings.county == "Multnomah"
    assert settings.regions == ("Oregon",)


def test_empty_county_normalizes_to_none():
    settings = build_settings({**DEFAULTS, "region": ["Oregon"], "county": "   "})
    assert settings.county is None


def test_county_with_multiple_regions_raises():
    with pytest.raises(ConfigError, match="exactly one state"):
        build_settings(
            {**DEFAULTS, "region": ["Oregon", "Washington"], "county": "Clark"}
        )
