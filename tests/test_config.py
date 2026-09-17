"""Tests for the settings model, defaults, and validation (Task Group 1)."""

import dataclasses

import pytest

from src.config import (
    DEFAULTS,
    SUPPORTED_WIDTH_PRESETS,
    WIDTH_PRESETS,
    ConfigError,
    Settings,
    build_settings,
)


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


def test_idaho_is_a_supported_region():
    settings = build_settings({**DEFAULTS, "region": ["idaho"]})
    assert settings.regions == ("Idaho",)


def test_unsupported_region_raises():
    with pytest.raises(ConfigError, match="Unsupported region"):
        build_settings({**DEFAULTS, "region": ["Atlantis"]})


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


# --- Scale-aware flow-width presets + width_log (roadmap #77) ----------------


def test_width_log_defaults_false():
    settings = build_settings(DEFAULTS)
    assert settings.width_log is False
    assert isinstance(settings.width_log, bool)


def test_width_log_accepted_and_coerced_to_bool():
    settings = build_settings({**DEFAULTS, "width_log": True})
    assert settings.width_log is True
    assert isinstance(settings.width_log, bool)


def test_width_presets_table_shape():
    assert set(WIDTH_PRESETS) == {"state", "basin", "watershed"}
    assert SUPPORTED_WIDTH_PRESETS == tuple(WIDTH_PRESETS)


def test_width_preset_state_expands_to_log_bundle():
    settings = build_settings({**DEFAULTS, "width_preset": "state"})
    assert settings.width_by == "flow"
    assert settings.width_log is True
    assert settings.width_max == 3.5
    assert settings.width_gamma == 1.0


def test_width_preset_basin_and_watershed_bundles():
    basin = build_settings({**DEFAULTS, "width_preset": "basin"})
    assert basin.width_by == "flow"
    assert basin.width_gamma == 0.45
    assert basin.width_log is False

    watershed = build_settings({**DEFAULTS, "width_preset": "watershed"})
    assert watershed.width_gamma == 0.5
    assert watershed.width_max == 1.4
    assert watershed.width_log is False


def test_width_preset_explicit_override_wins():
    # Precedence: defaults < preset < explicit. An explicit value that differs
    # from the default beats the preset; an unspecified field still comes from it.
    settings = build_settings(
        {**DEFAULTS, "width_preset": "basin", "width_gamma": 0.8, "width_max": 5.0}
    )
    assert settings.width_gamma == 0.8
    assert settings.width_max == 5.0
    assert settings.width_by == "flow"  # unspecified → from preset


def test_unknown_width_preset_raises():
    with pytest.raises(ConfigError, match="width_preset"):
        build_settings({**DEFAULTS, "width_preset": "galactic"})


def test_width_preset_not_stored_on_settings():
    settings = build_settings({**DEFAULTS, "width_preset": "state"})
    assert not hasattr(settings, "width_preset")


def test_default_build_keeps_uniform_and_no_log():
    # Byte-identical guard: no preset → uniform width, log off.
    settings = build_settings(DEFAULTS)
    assert settings.width_by == "uniform"
    assert settings.width_log is False


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


# ---------------------------------------------------------------------------
# --months option (Item #25, Task Group 3)
# ---------------------------------------------------------------------------

from src.config import parse_months


def test_months_default_is_annual_empty_tuple():
    settings = build_settings(DEFAULTS)
    assert settings.months == ()


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ()),
        ("", ()),
        ("annual", ()),
        ("all", ()),
        ("mean", ()),
        ("7", (7,)),
        ("jul", (7,)),
        ("July", (7,)),
        ("5-9", (5, 6, 7, 8, 9)),
        ("may-sep", (5, 6, 7, 8, 9)),
        ("nov-feb", (11, 12, 1, 2)),  # wrapping range
    ],
)
def test_parse_months_forms(value, expected):
    assert parse_months(value) == expected


@pytest.mark.parametrize("bad", ["0", "13", "foo", "3-", "-3", "jan-foo", "3-15"])
def test_parse_months_invalid_raises(bad):
    with pytest.raises(ConfigError):
        parse_months(bad)


def test_months_stored_on_settings():
    settings = build_settings({**DEFAULTS, "months": "may-sep"})
    assert settings.months == (5, 6, 7, 8, 9)


# --- Hydro-structure settings (Epoch 16, Item #67) --------------------------


def test_hydro_structures_disabled_by_default():
    s = build_settings(DEFAULTS)
    assert s.hydro_structures.enabled is False
    # Empty color means "use the rendering layer's per-class defaults".
    assert s.hydro_structures.color == ""
    assert s.hydro_structures.render_order == "above"
    assert s.hydro_structures.min_area_m2 == 0.0
    assert s.hydro_structures.min_spacing_m == 0.0


def test_hydro_structures_preset_expands_defaults_preset_explicit():
    from src.config import HYDRO_STRUCTURE_PRESETS

    state = build_settings(
        {**DEFAULTS, "hydro_structures": {"preset": "print-state"}}
    ).hydro_structures
    county = build_settings(
        {**DEFAULTS, "hydro_structures": {"preset": "print-county"}}
    ).hydro_structures
    # Preset fields expand onto the settings...
    assert (
        state.min_area_m2 == HYDRO_STRUCTURE_PRESETS["print-state"]["min_area_m2"]
    )
    # ...state scale prunes harder than county scale.
    assert state.min_area_m2 > county.min_area_m2 > 0.0

    # Explicit sub-key wins over the preset; other preset fields remain.
    override = build_settings(
        {
            **DEFAULTS,
            "hydro_structures": {"preset": "print-state", "min_area_m2": 7.0},
        }
    ).hydro_structures
    assert override.min_area_m2 == 7.0
    assert (
        override.render_order
        == HYDRO_STRUCTURE_PRESETS["print-state"]["render_order"]
    )


def test_hydro_structures_invalid_render_order_raises():
    with pytest.raises(ConfigError, match="render_order"):
        build_settings(
            {**DEFAULTS, "hydro_structures": {"render_order": "sideways"}}
        )


def test_hydro_structures_preset_not_stored_on_settings():
    hs = build_settings(
        {**DEFAULTS, "hydro_structures": {"preset": "print-state"}}
    ).hydro_structures
    assert not hasattr(hs, "preset")


def test_hydro_structure_presets_monotonic_thinning():
    """print-state >= print-county >= screen for both thinning knobs (Item #68).

    The tuned presets must declutter monotonically as the sheet gets larger, so a
    whole-state wall render prunes at least as hard as a single county, which
    prunes at least as hard as the (unthinned) screen view. Locks the density
    contract so a future retune can't accidentally invert it.
    """
    from src.config import HYDRO_STRUCTURE_PRESETS

    screen = HYDRO_STRUCTURE_PRESETS["screen"]
    county = HYDRO_STRUCTURE_PRESETS["print-county"]
    state = HYDRO_STRUCTURE_PRESETS["print-state"]

    for key in ("min_area_m2", "min_spacing_m"):
        assert state[key] >= county[key] >= screen[key]
    # print scales actually thin (a positive threshold), screen does not.
    assert screen["min_area_m2"] == 0.0 and screen["min_spacing_m"] == 0.0
    assert county["min_area_m2"] > 0.0 and county["min_spacing_m"] > 0.0
    assert state["min_area_m2"] > county["min_area_m2"]
    assert state["min_spacing_m"] > county["min_spacing_m"]


def test_hydro_structure_preset_tuning_leaves_default_disabled():
    """Preset value changes must NOT touch the default (byte-identical) build.

    No preset applies unless explicitly requested, so the default structure
    settings stay disabled with zero thinning — the render path sees no
    structures and output is unchanged.
    """
    hs = build_settings(DEFAULTS).hydro_structures
    assert hs.enabled is False
    assert hs.min_area_m2 == 0.0
    assert hs.min_spacing_m == 0.0
