"""Config surface for export formats + PNG size (Item #10, TG1)."""

import pytest

from src.cli import cli_overrides, build_parser
from src.config import (
    ConfigError,
    SUPPORTED_PNG_SIZES,
    build_settings,
)


def _base(**over):
    values = {"region": ["Oregon"]}
    values.update(over)
    return values


def test_output_accepts_tiff_and_eps_mapping_and_list():
    m = build_settings(_base(output={"svg": True, "tiff": True, "eps": True}))
    assert m.outputs == frozenset({"svg", "tiff", "eps"})
    l = build_settings(_base(output=["pdf", "tiff", "eps"]))
    assert l.outputs == frozenset({"pdf", "tiff", "eps"})


def test_unknown_output_still_raises():
    with pytest.raises(ConfigError, match="Unsupported output"):
        build_settings(_base(output=["svg", "bmp"]))


def test_png_size_defaults_to_4096():
    assert build_settings(_base()).png_size == 4096


def test_png_size_accepts_supported_sizes():
    for size in SUPPORTED_PNG_SIZES:
        assert build_settings(_base(png_size=size)).png_size == size


def test_png_size_draft_tiers_present_and_sorted():
    # Small draft/preview tiers exist for fast design + e2e iteration (Epoch 24 #94).
    assert {512, 1024, 2048}.issubset(set(SUPPORTED_PNG_SIZES))
    assert list(SUPPORTED_PNG_SIZES) == sorted(SUPPORTED_PNG_SIZES)


def test_png_size_accepts_draft_tiers():
    for size in (512, 1024, 2048):
        assert build_settings(_base(png_size=size)).png_size == size


def test_png_size_rejects_unsupported():
    with pytest.raises(ConfigError, match="png_size"):
        build_settings(_base(png_size=1234))


def test_cli_png_size_override_and_no_clobber():
    # Flag provided -> override present.
    args = build_parser().parse_args(["--png-size", "8192"])
    assert cli_overrides(args)["png_size"] == 8192
    # Flag omitted -> no key, so YAML/default survives.
    args = build_parser().parse_args([])
    assert "png_size" not in cli_overrides(args)
