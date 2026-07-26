"""End-to-end integration tests for config resolution (Task Group 4).

Fills the critical gap left by the per-layer tests: exercising the full
defaults -> YAML -> CLI resolution path as a whole, plus the PRD's
reproducibility acceptance criterion.
"""

import warnings

import pytest

from src.cli import resolve_settings
from src.config import ConfigError


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return str(path)


def test_full_resolution_yaml_and_cli_together(tmp_path):
    # YAML sets glow + line_width; CLI overrides region + outputs.
    path = _write(
        tmp_path,
        "region:\n  - Washington\nglow: true\nline_width: 0.5\n",
    )
    settings = resolve_settings(
        [
            "--config",
            path,
            "--region",
            "oregon",
            "washington",
            "--output",
            "svg",
            "pdf",
        ]
    )
    # From CLI:
    assert settings.regions == ("Oregon", "Washington")
    assert settings.outputs == frozenset({"svg", "pdf"})
    # Untouched by CLI, so YAML wins:
    assert settings.glow is True
    assert settings.line_width == 0.5


def test_identical_inputs_produce_identical_settings(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\npalette: neon\n")
    argv = ["--config", path, "--glow"]
    assert resolve_settings(argv) == resolve_settings(argv)


def test_invalid_output_format_is_rejected_end_to_end(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\n")
    with pytest.raises(ConfigError, match="Unsupported output format"):
        resolve_settings(["--config", path, "--output", "gif"])


def test_unknown_yaml_key_warns_but_still_resolves(tmp_path):
    path = _write(tmp_path, "region:\n  - Oregon\nbogus_key: 1\n")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        settings = resolve_settings(["--config", path])
    assert settings.regions == ("Oregon",)
    assert any("bogus_key" in str(w.message) for w in caught)
