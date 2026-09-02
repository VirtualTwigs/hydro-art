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
    SUPPORTED_AREAL_FEATURE_PRESETS,
    SUPPORTED_POINT_FEATURE_PRESETS,
    SUPPORTED_WATERBODY_PRESETS,
    SUPPORTED_WIDTH_PRESETS,
    Settings,
    build_settings,
    load_yaml,
)

__all__ = [
    "build_parser",
    "cli_overrides",
    "merge_values",
    "resolve_settings",
    "settings_from_args",
]

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
        "--county",
        default=None,
        help="Scope the build to a single Census county within the selected "
        "state (e.g. Clark). Requires exactly one --region.",
    )
    parser.add_argument(
        "--months",
        default=None,
        help="Month selection: 'annual' (default, annual mean), a single month "
        "(7/jul/july), or a range (5-9, may-sep, wrapping like nov-feb).",
    )
    parser.add_argument(
        "--palette",
        default=None,
        help="Named color palette (e.g. neon).",
    )
    parser.add_argument(
        "--color-by",
        default=None,
        help="Color art-direction mode: watershed single elevation.",
    )
    parser.add_argument(
        "--single-color",
        default=None,
        help="Stroke color for --color-by single (hex, e.g. #00ffff).",
    )
    parser.add_argument(
        "--width-by",
        default=None,
        help="Line-width art-direction mode: uniform flow.",
    )
    parser.add_argument(
        "--width-min",
        type=float,
        default=None,
        help="Minimum stroke width for --width-by flow (positive number).",
    )
    parser.add_argument(
        "--width-max",
        type=float,
        default=None,
        help="Maximum stroke width for --width-by flow (>= --width-min).",
    )
    parser.add_argument(
        "--width-gamma",
        type=float,
        default=None,
        help="Shaping exponent for the flow-to-width ramp (positive number).",
    )
    parser.add_argument(
        "--width-preset",
        choices=SUPPORTED_WIDTH_PRESETS,
        default=None,
        help="Named scale-aware flow-width preset (state basin watershed); "
        "expands to a bundle of --width-* options, explicit flags still win.",
    )
    parser.add_argument(
        "--width-log",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Normalize the flow-to-width ramp on log(metric) (--no-width-log "
        "keeps linear).",
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
    parser.add_argument(
        "--waterbody-preset",
        choices=SUPPORTED_WATERBODY_PRESETS,
        default=None,
        help="Named waterbody art-direction preset (expands to a bundle of "
        "waterbody options; explicit --waterbody-* flags still win).",
    )
    parser.add_argument(
        "--point-features",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Render natural point glyphs — springs/waterfalls/rapids (use "
        "--no-point-features to disable).",
    )
    parser.add_argument(
        "--point-feature-preset",
        choices=SUPPORTED_POINT_FEATURE_PRESETS,
        default=None,
        help="Named point-feature preset (expands to a density/z-order bundle; "
        "explicit point-feature settings still win).",
    )
    parser.add_argument(
        "--areal-features",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Render natural areal fills — wetlands/playas/perennial ice (use "
        "--no-areal-features to disable).",
    )
    parser.add_argument(
        "--areal-feature-preset",
        choices=SUPPORTED_AREAL_FEATURE_PRESETS,
        default=None,
        help="Named areal-feature preset (expands to an area-threshold/z-order "
        "bundle; explicit areal-feature settings still win).",
    )
    parser.add_argument(
        "--elevation",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Request DEM-backed elevation (use --no-elevation to disable).",
    )
    parser.add_argument(
        "--elevation-source",
        default=None,
        help="Elevation source: 3dep.",
    )
    parser.add_argument(
        "--elevation-tier",
        default=None,
        help="Elevation resolution tier: preview state local.",
    )
    parser.add_argument(
        "--vertical-exaggeration",
        type=float,
        default=None,
        help="Display-only vertical exaggeration multiplier (positive number).",
    )
    parser.add_argument(
        "--cache-policy",
        default=None,
        help="Elevation asset cache policy: reuse refresh.",
    )

    # Storage layout (roadmap #29). These select *where* large files live and do
    # not affect the rendered bytes, so they are resolved by build.py through
    # src.storage.resolve_storage and are deliberately excluded from
    # cli_overrides — they never leak into the deterministic Settings.
    parser.add_argument(
        "--external-root",
        default=None,
        help="External drive root; expands to <root>/cache, /datasets, /output "
        f"(or the {'$' + 'HYDRO_ART_EXTERNAL_ROOT'} env var). Used only when the "
        "drive is mounted, else local paths.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Explicit downloaded-archive cache dir (wins over --external-root).",
    )
    parser.add_argument(
        "--datasets-dir",
        default=None,
        help="Explicit extracted-datasets dir (wins over --external-root).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Explicit rendered-output dir (wins over --external-root).",
    )
    parser.add_argument(
        "--staging",
        default=None,
        help="Optional local working dir; render output here then move the "
        "finished file to the resolved output dir.",
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
    if args.county is not None:
        overrides["county"] = args.county
    if args.months is not None:
        overrides["months"] = args.months
    if args.palette is not None:
        overrides["palette"] = args.palette
    if args.color_by is not None:
        overrides["color_by"] = args.color_by
    if args.single_color is not None:
        overrides["single_color"] = args.single_color
    if args.width_by is not None:
        overrides["width_by"] = args.width_by
    if args.width_min is not None:
        overrides["width_min"] = args.width_min
    if args.width_max is not None:
        overrides["width_max"] = args.width_max
    if args.width_gamma is not None:
        overrides["width_gamma"] = args.width_gamma
    if args.width_preset is not None:
        overrides["width_preset"] = args.width_preset
    if args.width_log is not None:
        overrides["width_log"] = args.width_log
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
    if args.waterbody_preset is not None:
        waterbodies["preset"] = args.waterbody_preset
    if args.waterbodies is not None:
        waterbodies["enabled"] = args.waterbodies
    if args.waterbody_color is not None:
        waterbodies["color"] = args.waterbody_color
    if args.waterbody_stroke_width is not None:
        waterbodies["stroke_width"] = args.waterbody_stroke_width
    if waterbodies:
        overrides["waterbodies"] = waterbodies

    # Point/areal natural-feature sub-keys are collected under nested mappings so
    # precedence can deep-merge them onto YAML/defaults (see `resolve_settings`).
    point_features: dict[str, Any] = {}
    if args.point_feature_preset is not None:
        point_features["preset"] = args.point_feature_preset
    if args.point_features is not None:
        point_features["enabled"] = args.point_features
    if point_features:
        overrides["point_features"] = point_features

    areal_features: dict[str, Any] = {}
    if args.areal_feature_preset is not None:
        areal_features["preset"] = args.areal_feature_preset
    if args.areal_features is not None:
        areal_features["enabled"] = args.areal_features
    if areal_features:
        overrides["areal_features"] = areal_features

    # Elevation sub-keys are collected under a nested mapping so precedence can
    # deep-merge them onto YAML/defaults (see :func:`resolve_settings`).
    elevation: dict[str, Any] = {}
    if args.elevation is not None:
        elevation["enabled"] = args.elevation
    if args.elevation_source is not None:
        elevation["source"] = args.elevation_source
    if args.elevation_tier is not None:
        elevation["tier"] = args.elevation_tier
    if args.vertical_exaggeration is not None:
        elevation["vertical_exaggeration"] = args.vertical_exaggeration
    if args.cache_policy is not None:
        elevation["cache_policy"] = args.cache_policy
    if elevation:
        overrides["elevation"] = elevation
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
    return settings_from_args(build_parser().parse_args(argv))


def settings_from_args(args: argparse.Namespace) -> Settings:
    """Build validated :class:`Settings` from already-parsed arguments.

    Split out from :func:`resolve_settings` so an entry point that also reads the
    non-``Settings`` storage flags (``--external-root`` etc.) off the same
    namespace can parse ``argv`` once.
    """
    yaml_values = load_yaml(args.config)
    overrides = cli_overrides(args)
    merged = merge_values(dict(DEFAULTS), yaml_values, overrides)

    # `waterbodies` is a nested block; a shallow merge would let a later layer
    # replace the whole dict. Deep-merge its sub-keys so YAML < CLI precedence
    # holds per sub-key (e.g. --no-waterbodies keeps a YAML stroke_width). Start
    # from `{}` (not seeded defaults): `_coerce_waterbodies` fills every missing
    # field from DEFAULTS anyway, and pre-seeding would make a `preset` bundle
    # indistinguishable from — and shadowed by — explicit values (Item W4).
    waterbodies: dict[str, Any] = {}
    for layer in (yaml_values, overrides):
        block = layer.get("waterbodies")
        if isinstance(block, dict):
            waterbodies.update(block)
    merged["waterbodies"] = waterbodies

    # `point_features` / `areal_features` are nested blocks like `waterbodies`;
    # deep-merge their sub-keys from `{}` (not seeded defaults) so a `preset`
    # bundle isn't shadowed by pre-seeded explicit values (mirrors Item W4).
    for block_key in ("point_features", "areal_features"):
        block_merged: dict[str, Any] = {}
        for layer in (yaml_values, overrides):
            block = layer.get(block_key)
            if isinstance(block, dict):
                block_merged.update(block)
        merged[block_key] = block_merged

    # `elevation` is likewise a nested block; deep-merge its sub-keys so
    # YAML < CLI precedence holds per sub-key (e.g. --elevation keeps a YAML
    # vertical_exaggeration).
    elevation: dict[str, Any] = dict(DEFAULTS["elevation"])
    for layer in (yaml_values, overrides):
        block = layer.get("elevation")
        if isinstance(block, dict):
            elevation.update(block)
    merged["elevation"] = elevation

    return build_settings(merged)
