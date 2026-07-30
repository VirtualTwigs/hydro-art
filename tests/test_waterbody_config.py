"""Tests for waterbody settings + CLI precedence (Item W3, Task Group 3).

Covers the `waterbodies` config block: validated defaults (enabled by
default), field validation, YAML overrides, and sub-key CLI precedence.
"""

import pytest

from src.cli import resolve_settings
from src.config import DEFAULTS, ConfigError, build_settings


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return str(path)


def test_waterbodies_enabled_by_default_with_water_color():
    wb = build_settings(DEFAULTS).waterbodies
    assert wb.enabled is True
    assert wb.color.startswith("#")
    assert wb.stroke_width > 0
    assert wb.coastal_mode == "conservative"
    assert wb.render_order in ("below", "above")
    assert wb.min_inland_area_m2 == 0.0


def test_partial_waterbodies_dict_fills_missing_from_defaults():
    settings = build_settings({**DEFAULTS, "waterbodies": {"enabled": False}})
    assert settings.waterbodies.enabled is False
    # Untouched sub-keys still take their defaults.
    assert settings.waterbodies.coastal_mode == "conservative"
    assert settings.waterbodies.stroke_width > 0


def test_invalid_waterbody_color_raises():
    with pytest.raises(ConfigError, match="waterbod"):
        build_settings({**DEFAULTS, "waterbodies": {"color": "blue"}})


def test_invalid_coastal_mode_raises():
    with pytest.raises(ConfigError, match="coastal_mode"):
        build_settings({**DEFAULTS, "waterbodies": {"coastal_mode": "wild"}})


def test_negative_stroke_width_raises():
    with pytest.raises(ConfigError, match="stroke_width"):
        build_settings({**DEFAULTS, "waterbodies": {"stroke_width": -1}})


def test_yaml_waterbodies_override(tmp_path):
    path = _write(tmp_path, "waterbodies:\n  enabled: false\n  stroke_width: 0.9\n")
    settings = resolve_settings(["--config", path])
    assert settings.waterbodies.enabled is False
    assert settings.waterbodies.stroke_width == 0.9
    # A sub-key not set in YAML keeps its default.
    assert settings.waterbodies.coastal_mode == "conservative"


def test_cli_no_waterbodies_overrides_yaml_but_keeps_other_subkeys(tmp_path):
    path = _write(tmp_path, "waterbodies:\n  enabled: true\n  stroke_width: 0.9\n")
    settings = resolve_settings(["--config", path, "--no-waterbodies"])
    assert settings.waterbodies.enabled is False
    # CLI toggled only `enabled`; the YAML stroke_width survives.
    assert settings.waterbodies.stroke_width == 0.9


def test_cli_waterbody_color_and_width_override(tmp_path):
    settings = resolve_settings(
        ["--waterbody-color", "#123456", "--waterbody-stroke-width", "1.25"]
    )
    assert settings.waterbodies.color == "#123456"
    assert settings.waterbodies.stroke_width == 1.25
