"""Tests for YAML loading, CLI parsing, and precedence merge (Task Group 2)."""

import pytest

from src.cli import resolve_settings
from src.config import ConfigError


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return str(path)


def test_missing_config_falls_back_to_defaults(tmp_path):
    settings = resolve_settings(["--config", str(tmp_path / "nope.yaml")])
    assert settings.regions == ("Oregon", "Washington")
    assert settings.palette == "neon"


def test_malformed_yaml_raises(tmp_path):
    path = _write(tmp_path, "region: [Oregon\n  bad: :")
    with pytest.raises(ConfigError, match="Could not parse"):
        resolve_settings(["--config", path])


def test_yaml_overrides_defaults(tmp_path):
    path = _write(tmp_path, "region:\n  - Washington\nline_width: 0.5\n")
    settings = resolve_settings(["--config", path])
    assert settings.regions == ("Washington",)
    assert settings.line_width == 0.5


def test_cli_overrides_yaml(tmp_path):
    path = _write(tmp_path, "region:\n  - Washington\npalette: neon\n")
    settings = resolve_settings(["--config", path, "--region", "Oregon"])
    assert settings.regions == ("Oregon",)


def test_unset_flag_does_not_clobber_yaml(tmp_path):
    path = _write(tmp_path, "glow: true\nregion:\n  - Oregon\n")
    # --glow not passed; YAML's glow=true must survive.
    settings = resolve_settings(["--config", path])
    assert settings.glow is True


def test_cli_glow_and_output_flags(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\n")
    settings = resolve_settings(
        ["--config", path, "--glow", "--output", "svg", "png"]
    )
    assert settings.glow is True
    assert settings.outputs == frozenset({"svg", "png"})


def test_cli_art_direction_flags(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\n")
    settings = resolve_settings(
        [
            "--config", path,
            "--color-by", "single",
            "--single-color", "#ff00ff",
            "--width-by", "flow",
            "--width-min", "0.5",
            "--width-max", "4.0",
            "--width-gamma", "0.5",
        ]
    )
    assert settings.color_by == "single"
    assert settings.single_color == "#ff00ff"
    assert settings.width_by == "flow"
    assert settings.width_min == 0.5
    assert settings.width_max == 4.0
    assert settings.width_gamma == 0.5


def test_unset_art_direction_flags_keep_yaml(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\ncolor_by: single\nwidth_by: flow\n")
    # Neither --color-by nor --width-by passed; YAML values must survive.
    settings = resolve_settings(["--config", path])
    assert settings.color_by == "single"
    assert settings.width_by == "flow"


def test_cli_county_flag(tmp_path):
    path = _write(tmp_path, "region:\n  - Washington\n")
    settings = resolve_settings(["--config", path, "--county", "Clark"])
    assert settings.county == "Clark"


def test_unset_county_flag_keeps_yaml(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\ncounty: Multnomah\n")
    # --county not passed; YAML's county must survive.
    settings = resolve_settings(["--config", path])
    assert settings.county == "Multnomah"


def test_cli_county_overrides_yaml(tmp_path):
    path = _write(tmp_path, "region:\n  - Washington\ncounty: King\n")
    settings = resolve_settings(["--config", path, "--county", "Clark"])
    assert settings.county == "Clark"


def test_cli_months_flag(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\n")
    settings = resolve_settings(["--config", path, "--months", "jul"])
    assert settings.months == (7,)


def test_unset_months_flag_keeps_yaml(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\nmonths: may-sep\n")
    # --months not passed; YAML's months must survive.
    settings = resolve_settings(["--config", path])
    assert settings.months == (5, 6, 7, 8, 9)
