"""Tests for waterbody settings + CLI precedence (Item W3, Task Group 3).

Covers the `waterbodies` config block: validated defaults (enabled by
default), field validation, YAML overrides, and sub-key CLI precedence.
"""

import pytest

from src.cli import resolve_settings
from src.config import (
    DEFAULTS,
    WATERBODY_PRESETS,
    ConfigError,
    build_settings,
)


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


# --- W4 regional presets: catalog + config expansion (TG-WB1) ---------------


def _wb_fields(wb):
    return {
        "color": wb.color,
        "stroke_width": wb.stroke_width,
        "min_inland_area_m2": wb.min_inland_area_m2,
        "min_coastal_area_m2": wb.min_coastal_area_m2,
        "coastal_mode": wb.coastal_mode,
        "render_order": wb.render_order,
    }


def test_screen_preset_applies_its_bundle():
    wb = build_settings({**DEFAULTS, "waterbodies": {"preset": "screen"}}).waterbodies
    for field, value in WATERBODY_PRESETS["screen"].items():
        assert _wb_fields(wb)[field] == value


def test_print_preset_bolder_stroke_and_area_thresholds():
    wb = build_settings({**DEFAULTS, "waterbodies": {"preset": "print"}}).waterbodies
    # The print preset is meant to declutter + survive ink: bolder stroke, and it
    # drops tiny ponds via positive area thresholds.
    assert wb.stroke_width == WATERBODY_PRESETS["print"]["stroke_width"]
    assert wb.stroke_width > DEFAULTS["waterbodies"]["stroke_width"]
    assert wb.min_inland_area_m2 > 0.0
    assert wb.min_coastal_area_m2 > 0.0


def test_explicit_field_overrides_preset_but_keeps_the_rest():
    wb = build_settings(
        {**DEFAULTS, "waterbodies": {"preset": "print", "stroke_width": 0.5}}
    ).waterbodies
    # Explicit sub-key wins over the preset...
    assert wb.stroke_width == 0.5
    # ...but the preset's other fields remain.
    assert wb.min_inland_area_m2 == WATERBODY_PRESETS["print"]["min_inland_area_m2"]


def test_unknown_preset_raises():
    with pytest.raises(ConfigError, match="preset"):
        build_settings({**DEFAULTS, "waterbodies": {"preset": "poster"}})


def test_no_preset_keeps_defaults_byte_identical():
    plain = build_settings(DEFAULTS).waterbodies
    assert _wb_fields(plain) == {
        "color": DEFAULTS["waterbodies"]["color"],
        "stroke_width": DEFAULTS["waterbodies"]["stroke_width"],
        "min_inland_area_m2": DEFAULTS["waterbodies"]["min_inland_area_m2"],
        "min_coastal_area_m2": DEFAULTS["waterbodies"]["min_coastal_area_m2"],
        "coastal_mode": DEFAULTS["waterbodies"]["coastal_mode"],
        "render_order": DEFAULTS["waterbodies"]["render_order"],
    }


# --- W4 regional presets: CLI flag + merge (TG-WB2) -------------------------


def test_cli_waterbody_preset_print_applies():
    settings = resolve_settings(["--waterbody-preset", "print"])
    assert settings.waterbodies.stroke_width == WATERBODY_PRESETS["print"]["stroke_width"]
    assert settings.waterbodies.min_inland_area_m2 > 0.0


def test_cli_explicit_stroke_beats_preset():
    settings = resolve_settings(
        ["--waterbody-preset", "print", "--waterbody-stroke-width", "0.5"]
    )
    # Explicit CLI flag wins over the preset...
    assert settings.waterbodies.stroke_width == 0.5
    # ...while the preset's other fields still apply.
    assert (
        settings.waterbodies.min_inland_area_m2
        == WATERBODY_PRESETS["print"]["min_inland_area_m2"]
    )


def test_yaml_preset_honored_and_cli_overrides(tmp_path):
    path = _write(tmp_path, "waterbodies:\n  preset: print\n")
    yaml_only = resolve_settings(["--config", path])
    assert yaml_only.waterbodies.stroke_width == WATERBODY_PRESETS["print"]["stroke_width"]
    # CLI preset overrides the YAML one.
    overridden = resolve_settings(["--config", path, "--waterbody-preset", "screen"])
    assert (
        overridden.waterbodies.stroke_width
        == WATERBODY_PRESETS["screen"]["stroke_width"]
    )
