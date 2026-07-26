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
        "--glow",
        action="store_true",
        default=None,
        help="Enable the optional glow effect.",
    )
    parser.add_argument(
        "--output",
        nargs="+",
        default=None,
        metavar="FORMAT",
        help="One or more output formats: svg pdf png.",
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
    if args.glow is not None:
        overrides["glow"] = args.glow
    if args.output is not None:
        overrides["output"] = args.output
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
    merged = merge_values(dict(DEFAULTS), yaml_values, cli_overrides(args))
    return build_settings(merged)
