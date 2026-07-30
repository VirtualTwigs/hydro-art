"""Command-line parsing and precedence merging into :class:`Settings`.

Resolution order (lowest to highest precedence):

    built-in defaults  <  YAML config file  <  CLI flags

Only flags the user explicitly passes override YAML; unspecified flags leave
YAML (or default) values untouched. The public entry point is
:func:`resolve_settings`.
"""

from __future__ import annotations

import argparse
from typing import Any, Sequence

from src.config import (
    DEFAULTS,
    Settings,
    build_settings,
    load_yaml,
)

__all__ = ["build_parser", "cli_overrides", "merge_values", "resolve_settings"]

DEFAULT_CONFIG_PATH = "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for ``build.py``.

    Flags default to ``None`` so that "not provided" is distinguishable from an
    explicit value; this is what lets YAML values survive when a flag is
    omitted.
    """
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Generate hydrographic vector art from public GIS data.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to the YAML config file (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--region",
        nargs="+",
        default=None,
        metavar="REGION",
        help="One or more regions to build (e.g. Oregon Washington).",
    )
    parser.add_argument(
        "--palette",
        default=None,
        help="Named color palette (e.g. neon).",
    )
    parser.add_argument(
        "--stream-method",
        default=None,
        help="Stream-hierarchy method: strahler shreve hack custom.",
    )
    parser.add_argument(
        "--huc-level",
        default=None,
        help="Watershed grouping level: HUC2 HUC4 HUC6 HUC8 HUC10 HUC12.",
    )
    parser.add_argument(
        "--glow",
        action="store_true",
        default=None,
        help="Enable the optional glow effect.",
    )
    parser.add_argument(
        "--glow-mode",
        default=None,
        help="Glow style when enabled: vector blur.",
    )
    parser.add_argument(
        "--glow-radius",
        default=None,
        help="Glow radius in SVG user units (positive number).",
    )
    parser.add_argument(
        "--output",
        nargs="+",
        default=None,
        metavar="FORMAT",
        help="One or more output formats: svg pdf png tiff eps.",
    )
    parser.add_argument(
        "--png-size",
        type=int,
        default=None,
        help="Raster export size in pixels: 4096 8192 16384 32768 65536.",
    )
    parser.add_argument(
        "--waterbodies",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Render waterbody outlines (use --no-waterbodies to disable).",
    )
    parser.add_argument(
        "--waterbody-color",
        default=None,
        help="Waterbody outline stroke color (hex, e.g. #2ec4ff).",
    )
    parser.add_argument(
        "--waterbody-stroke-width",
        type=float,
        default=None,
        help="Waterbody outline stroke width in SVG user units (positive number).",
    )
    return parser


def cli_overrides(args: argparse.Namespace) -> dict[str, Any]:
    """Extract only the explicitly-provided CLI values as config overrides.

    Keys map onto the same names used in :data:`~src.config.DEFAULTS` and the
    YAML file, so the result can be merged directly.
    """
    overrides: dict[str, Any] = {}
    if args.region is not None:
        overrides["region"] = args.region
    if args.palette is not None:
        overrides["palette"] = args.palette
    if args.stream_method is not None:
        overrides["stream_method"] = args.stream_method
    if args.huc_level is not None:
        overrides["huc_level"] = args.huc_level
    if args.glow is not None:
        overrides["glow"] = args.glow
    if args.glow_mode is not None:
        overrides["glow_mode"] = args.glow_mode
    if args.glow_radius is not None:
        overrides["glow_radius"] = args.glow_radius
    if args.output is not None:
        overrides["output"] = args.output
    if args.png_size is not None:
        overrides["png_size"] = args.png_size

    # Waterbody sub-keys are collected under a nested mapping so precedence can
    # deep-merge them onto YAML/defaults (see :func:`resolve_settings`).
    waterbodies: dict[str, Any] = {}
    if args.waterbodies is not None:
        waterbodies["enabled"] = args.waterbodies
    if args.waterbody_color is not None:
        waterbodies["color"] = args.waterbody_color
    if args.waterbody_stroke_width is not None:
        waterbodies["stroke_width"] = args.waterbody_stroke_width
    if waterbodies:
        overrides["waterbodies"] = waterbodies
    return overrides


def merge_values(*layers: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge config layers left-to-right (later layers win)."""
    merged: dict[str, Any] = {}
    for layer in layers:
        merged.update(layer)
    return merged


def resolve_settings(argv: Sequence[str] | None = None) -> Settings:
    """Parse ``argv``, load YAML, apply precedence, and validate.

    Args:
        argv: Argument vector (defaults to ``sys.argv[1:]`` when ``None``).

    Returns:
        A validated :class:`Settings` instance.

    Raises:
        ConfigError: If the config file is malformed or any value is invalid.
    """
    args = build_parser().parse_args(argv)
    yaml_values = load_yaml(args.config)
    overrides = cli_overrides(args)
    merged = merge_values(dict(DEFAULTS), yaml_values, overrides)

    # `waterbodies` is a nested block; a shallow merge would let a later layer
    # replace the whole dict. Deep-merge its sub-keys so YAML < CLI precedence
    # holds per sub-key (e.g. --no-waterbodies keeps a YAML stroke_width).
    waterbodies: dict[str, Any] = dict(DEFAULTS["waterbodies"])
    for layer in (yaml_values, overrides):
        block = layer.get("waterbodies")
        if isinstance(block, dict):
            waterbodies.update(block)
    merged["waterbodies"] = waterbodies

    return build_settings(merged)
