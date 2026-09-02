"""Tests for natural-feature settings + presets + CLI precedence (Item 64).

Covers the `point_features` and `areal_features` config blocks: opt-in-disabled
defaults (byte-identical default build), field validation → ConfigError, preset
expansion (`defaults < preset < explicit`, preset not stored on Settings), and
sub-key CLI precedence. Mirrors `tests/test_waterbody_config.py`.
"""

import pytest

from src.cli import resolve_settings
from src.config import (
    AREAL_FEATURE_PRESETS,
    DEFAULTS,
    POINT_FEATURE_PRESETS,
    ConfigError,
    build_settings,
)


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return str(path)


# --- Defaults: opt-in disabled, byte-identical default build ----------------


def test_point_and_areal_features_disabled_by_default():
    s = build_settings(DEFAULTS)
    assert s.point_features.enabled is False
    assert s.areal_features.enabled is False
    # Empty color means "use the rendering layer's per-family defaults".
    assert s.point_features.color == ""
    assert s.areal_features.color == ""
    assert s.point_features.render_order == "above"
    assert s.areal_features.render_order == "below"
    assert s.point_features.min_spacing_m == 0.0
    assert s.areal_features.min_area_m2 == 0.0


def test_partial_point_dict_fills_missing_from_defaults():
    s = build_settings({**DEFAULTS, "point_features": {"enabled": True}})
    assert s.point_features.enabled is True
    # Untouched sub-keys still take their defaults.
    assert s.point_features.render_order == "above"
    assert s.point_features.size > 0


# --- Field validation -------------------------------------------------------


def test_invalid_point_color_raises():
    with pytest.raises(ConfigError, match="point_features.color"):
        build_settings({**DEFAULTS, "point_features": {"color": "blue"}})


def test_negative_point_spacing_raises():
    with pytest.raises(ConfigError, match="min_spacing_m"):
        build_settings({**DEFAULTS, "point_features": {"min_spacing_m": -1}})


def test_non_positive_point_size_raises():
    with pytest.raises(ConfigError, match="size"):
        build_settings({**DEFAULTS, "point_features": {"size": 0}})


def test_invalid_areal_render_order_raises():
    with pytest.raises(ConfigError, match="render_order"):
        build_settings({**DEFAULTS, "areal_features": {"render_order": "sideways"}})


def test_areal_opacity_out_of_range_raises():
    with pytest.raises(ConfigError, match="opacity"):
        build_settings({**DEFAULTS, "areal_features": {"opacity": 2.0}})
    with pytest.raises(ConfigError, match="opacity"):
        build_settings({**DEFAULTS, "areal_features": {"opacity": 0}})


def test_negative_areal_min_area_raises():
    with pytest.raises(ConfigError, match="min_area_m2"):
        build_settings({**DEFAULTS, "areal_features": {"min_area_m2": -5}})


def test_invalid_areal_dash_raises():
    with pytest.raises(ConfigError, match="dash"):
        build_settings({**DEFAULTS, "areal_features": {"dash": "dotty"}})


# --- Presets: defaults < preset < explicit, preset not stored ---------------


def test_point_print_state_preset_thins_denser_than_county():
    state = build_settings(
        {**DEFAULTS, "point_features": {"preset": "print-state"}}
    ).point_features
    county = build_settings(
        {**DEFAULTS, "point_features": {"preset": "print-county"}}
    ).point_features
    assert state.min_spacing_m == POINT_FEATURE_PRESETS["print-state"]["min_spacing_m"]
    # State scale thins harder (wider spacing) than county scale.
    assert state.min_spacing_m > county.min_spacing_m > 0.0


def test_areal_print_state_preset_prunes_more_than_county():
    state = build_settings(
        {**DEFAULTS, "areal_features": {"preset": "print-state"}}
    ).areal_features
    county = build_settings(
        {**DEFAULTS, "areal_features": {"preset": "print-county"}}
    ).areal_features
    assert state.min_area_m2 == AREAL_FEATURE_PRESETS["print-state"]["min_area_m2"]
    assert state.min_area_m2 > county.min_area_m2 > 0.0


def test_explicit_field_overrides_preset_but_keeps_the_rest():
    ar = build_settings(
        {**DEFAULTS, "areal_features": {"preset": "print-state", "min_area_m2": 10.0}}
    ).areal_features
    # Explicit sub-key wins over the preset...
    assert ar.min_area_m2 == 10.0
    # ...but the preset's other fields remain.
    assert ar.render_order == AREAL_FEATURE_PRESETS["print-state"]["render_order"]


def test_unknown_point_preset_raises():
    with pytest.raises(ConfigError, match="preset"):
        build_settings({**DEFAULTS, "point_features": {"preset": "poster"}})


def test_preset_is_not_stored_on_frozen_settings():
    ar = build_settings(
        {**DEFAULTS, "areal_features": {"preset": "print-state"}}
    ).areal_features
    assert not hasattr(ar, "preset")


# --- CLI flags + precedence -------------------------------------------------


def test_cli_enable_flags():
    s = resolve_settings(["--point-features", "--areal-features"])
    assert s.point_features.enabled is True
    assert s.areal_features.enabled is True


def test_cli_no_point_features_overrides_yaml_but_keeps_other_subkeys(tmp_path):
    path = _write(
        tmp_path, "point_features:\n  enabled: true\n  min_spacing_m: 500\n"
    )
    s = resolve_settings(["--config", path, "--no-point-features"])
    assert s.point_features.enabled is False
    # CLI toggled only `enabled`; the YAML min_spacing_m survives.
    assert s.point_features.min_spacing_m == 500.0


def test_cli_preset_applies_and_explicit_flag_wins(tmp_path):
    path = _write(tmp_path, "areal_features:\n  preset: print-county\n")
    yaml_only = resolve_settings(["--config", path])
    assert (
        yaml_only.areal_features.min_area_m2
        == AREAL_FEATURE_PRESETS["print-county"]["min_area_m2"]
    )
    # CLI preset overrides the YAML preset.
    overridden = resolve_settings(
        ["--config", path, "--areal-feature-preset", "print-state"]
    )
    assert (
        overridden.areal_features.min_area_m2
        == AREAL_FEATURE_PRESETS["print-state"]["min_area_m2"]
    )


def test_cli_unset_flags_do_not_clobber_yaml(tmp_path):
    path = _write(tmp_path, "point_features:\n  enabled: true\n  size: 3.0\n")
    # No point-feature flags passed → YAML values survive untouched.
    s = resolve_settings(["--config", path])
    assert s.point_features.enabled is True
    assert s.point_features.size == 3.0
