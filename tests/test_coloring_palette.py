"""Tests for the neon palette + palette config validation (Item #7, TG1)."""

import re

import pytest

from src.coloring import PALETTES, ColoringError, get_palette
from src.config import (
    DEFAULTS,
    SUPPORTED_PALETTES,
    ConfigError,
    build_settings,
)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_neon_palette_has_twelve_valid_hex_colors():
    neon = PALETTES["neon"]
    assert len(neon) == 12
    assert all(_HEX.match(color) for color in neon)
    # No duplicates — twelve distinct neon colors.
    assert len(set(neon)) == 12


def test_get_palette_returns_tuple_for_known_name():
    assert get_palette("neon") == PALETTES["neon"]


def test_get_palette_unknown_name_raises():
    with pytest.raises(ColoringError, match="Unknown palette"):
        get_palette("pastel")


def test_palette_allowlist_contains_neon():
    assert "neon" in SUPPORTED_PALETTES


def test_unknown_palette_raises_config_error():
    with pytest.raises(ConfigError, match="Unsupported palette"):
        build_settings({**DEFAULTS, "palette": "pastel"})


def test_default_palette_validates_and_survives():
    settings = build_settings({**DEFAULTS})
    assert settings.palette == "neon"
