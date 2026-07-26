"""Config/CLI tests for glow mode + radius (Item #9, Task Group 1)."""

import pytest

from src.cli import resolve_settings
from src.config import (
    SUPPORTED_GLOW_MODES,
    ConfigError,
    build_settings,
)


def test_glow_mode_and_radius_defaults():
    settings = build_settings({"region": ["Oregon"]})
    assert settings.glow_mode == "blur"
    assert settings.glow_radius == 2.0
    assert set(SUPPORTED_GLOW_MODES) == {"vector", "blur"}


def test_glow_mode_validated():
    settings = build_settings({"region": ["Oregon"], "glow_mode": "VECTOR"})
    assert settings.glow_mode == "vector"  # normalized
    with pytest.raises(ConfigError, match="glow_mode"):
        build_settings({"region": ["Oregon"], "glow_mode": "sparkle"})


def test_glow_radius_must_be_positive_number():
    assert build_settings({"region": ["Oregon"], "glow_radius": 5}).glow_radius == 5.0
    with pytest.raises(ConfigError, match="glow_radius"):
        build_settings({"region": ["Oregon"], "glow_radius": 0})
    with pytest.raises(ConfigError, match="glow_radius"):
        build_settings({"region": ["Oregon"], "glow_radius": "wide"})


def test_cli_flags_override_yaml_but_unset_flags_do_not(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("region:\n  - Oregon\nglow_mode: vector\nglow_radius: 4.5\n")
    # No glow flags on the CLI -> YAML values survive.
    settings = resolve_settings(["--config", str(cfg)])
    assert settings.glow_mode == "vector"
    assert settings.glow_radius == 4.5
    # CLI flags win when provided.
    overridden = resolve_settings(
        ["--config", str(cfg), "--glow-mode", "blur", "--glow-radius", "1.5"]
    )
    assert overridden.glow_mode == "blur"
    assert overridden.glow_radius == 1.5
