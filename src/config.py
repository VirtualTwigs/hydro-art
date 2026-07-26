"""Configuration model, defaults, and validation for the pipeline.

This module defines the immutable :class:`Settings` object that drives every
downstream pipeline stage, along with the built-in defaults, the allowlists of
supported values, and the validation that turns raw (defaults + YAML + CLI)
values into a validated, typed settings object.

The module holds no global mutable state: a :class:`Settings` instance is
constructed once (see :func:`build_settings`) and passed by dependency
injection into the pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

__all__ = [
    "ConfigError",
    "Settings",
    "DEFAULTS",
    "SUPPORTED_REGIONS",
    "SUPPORTED_PROJECTIONS",
    "SUPPORTED_OUTPUTS",
    "SUPPORTED_STREAM_METHODS",
    "SUPPORTED_HUC_LEVELS",
    "SUPPORTED_PALETTES",
    "SUPPORTED_GLOW_MODES",
    "load_yaml",
    "build_settings",
]


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or invalid.

    The message is intended to be shown directly to the user, so it should be
    clear and actionable rather than exposing internal detail.
    """


# --- Allowlists (single source of truth; extend here to add regions/etc.) ---

#: Regions supported by the initial release. Keys are the canonical display
#: names; lookup is case-insensitive (see :func:`_normalize_region`).
SUPPORTED_REGIONS: tuple[str, ...] = ("Oregon", "Washington")

#: Coordinate reference systems the pipeline knows how to handle.
SUPPORTED_PROJECTIONS: tuple[str, ...] = ("EPSG:5070", "EPSG:4326", "EPSG:3857")

#: Output formats selectable in this feature. Additional formats (tiff, eps)
#: are handled by a later roadmap item.
SUPPORTED_OUTPUTS: tuple[str, ...] = ("svg", "pdf", "png")

#: Stream-hierarchy methods (PRD section 12), user selectable.
SUPPORTED_STREAM_METHODS: tuple[str, ...] = ("strahler", "shreve", "hack", "custom")

#: Watershed HUC levels (PRD section 13), user selectable.
SUPPORTED_HUC_LEVELS: tuple[str, ...] = (
    "HUC2",
    "HUC4",
    "HUC6",
    "HUC8",
    "HUC10",
    "HUC12",
)

#: Named color palettes (PRD section 16), user selectable. Palette colors live
#: in :mod:`src.coloring`; this allowlist gates the ``palette`` config value.
SUPPORTED_PALETTES: tuple[str, ...] = ("neon",)

#: Glow rendering modes (PRD section 20): ``vector`` (pure-vector halo) or
#: ``blur`` (SVG Gaussian-blur filter). Only used when ``glow`` is enabled.
SUPPORTED_GLOW_MODES: tuple[str, ...] = ("vector", "blur")

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

#: Built-in defaults, reflecting PRD sections 19 and 25.
DEFAULTS: dict[str, Any] = {
    "region": ["Oregon", "Washington"],
    "projection": "EPSG:5070",
    "stream_order": "all",
    "stream_method": "strahler",
    "huc_level": "HUC4",
    "background": "#000000",
    "line_width": 0.35,
    "palette": "neon",
    "glow": False,
    "glow_mode": "blur",
    "glow_radius": 2.0,
    "output": {"svg": True, "png": False, "pdf": False},
}


@dataclass(frozen=True)
class Settings:
    """Validated, immutable configuration for a single pipeline run.

    Attributes:
        regions: Canonical region names to build (e.g. ``("Oregon",)``).
        projection: Internal EPSG code used for all geometry operations.
        stream_order: Stream-order render filter (e.g. ``"all"``).
        stream_method: Stream-hierarchy method (strahler/shreve/hack/custom).
        huc_level: Watershed grouping level (HUC2..HUC12).
        background: Background color as a hex string (e.g. ``"#000000"``).
        line_width: Default stroke width in SVG user units; must be > 0.
        palette: Named color palette (e.g. ``"neon"``).
        glow: Whether the optional glow effect is enabled.
        glow_mode: Glow style when enabled (``"vector"`` or ``"blur"``).
        glow_radius: Glow radius in SVG user units; must be > 0.
        outputs: Set of output formats to produce (subset of
            :data:`SUPPORTED_OUTPUTS`).
    """

    regions: tuple[str, ...]
    projection: str
    stream_order: str
    stream_method: str
    huc_level: str
    background: str
    line_width: float
    palette: str
    glow: bool
    glow_mode: str
    glow_radius: float
    outputs: frozenset[str]


def _normalize_region(name: str) -> str:
    """Return the canonical region name for ``name`` (case-insensitive).

    Raises:
        ConfigError: If ``name`` is not a supported region.
    """
    for canonical in SUPPORTED_REGIONS:
        if canonical.lower() == str(name).strip().lower():
            return canonical
    valid = ", ".join(SUPPORTED_REGIONS)
    raise ConfigError(
        f"Unsupported region: {name!r}. Valid regions are: {valid}."
    )


def _coerce_outputs(output: Any) -> frozenset[str]:
    """Normalize the ``output`` value (mapping or sequence) into a format set.

    Accepts either the YAML mapping form (``{"svg": True, "png": False}``) or a
    sequence form (``["svg", "png"]``, as produced by the CLI).

    Raises:
        ConfigError: If an unknown output format is requested.
    """
    if isinstance(output, Mapping):
        requested = [str(fmt).lower() for fmt, on in output.items() if on]
    elif isinstance(output, (list, tuple, set, frozenset)):
        requested = [str(fmt).lower() for fmt in output]
    else:
        raise ConfigError(
            f"Invalid 'output' value: {output!r}. Expected a mapping or list."
        )

    unknown = [fmt for fmt in requested if fmt not in SUPPORTED_OUTPUTS]
    if unknown:
        valid = ", ".join(SUPPORTED_OUTPUTS)
        raise ConfigError(
            f"Unsupported output format(s): {', '.join(unknown)}. "
            f"Valid formats are: {valid}."
        )
    return frozenset(requested)


def build_settings(values: Mapping[str, Any]) -> Settings:
    """Validate a merged mapping of config values into a :class:`Settings`.

    ``values`` is expected to already be the result of merging defaults, YAML,
    and CLI overrides (see :func:`~src.cli.build_settings`). This function
    validates every field at the boundary and fails fast with a
    :class:`ConfigError` describing the first problem found.

    Raises:
        ConfigError: If any field is missing or invalid.
    """
    regions_raw = values.get("region")
    if not regions_raw:
        raise ConfigError("At least one region must be specified.")
    if isinstance(regions_raw, str):
        regions_raw = [regions_raw]
    regions = tuple(dict.fromkeys(_normalize_region(r) for r in regions_raw))

    projection = str(values.get("projection", DEFAULTS["projection"]))
    if projection not in SUPPORTED_PROJECTIONS:
        valid = ", ".join(SUPPORTED_PROJECTIONS)
        raise ConfigError(
            f"Unsupported projection: {projection!r}. Valid: {valid}."
        )

    background = str(values.get("background", DEFAULTS["background"]))
    if not _HEX_COLOR.match(background):
        raise ConfigError(
            f"Invalid background color: {background!r}. "
            "Expected a hex color like '#000000'."
        )

    try:
        line_width = float(values.get("line_width", DEFAULTS["line_width"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid line_width: {values.get('line_width')!r}. "
            "Expected a positive number."
        )
    if line_width <= 0:
        raise ConfigError(
            f"line_width must be greater than 0, got {line_width}."
        )

    stream_order = str(values.get("stream_order", DEFAULTS["stream_order"]))

    stream_method = str(values.get("stream_method", DEFAULTS["stream_method"])).lower()
    if stream_method not in SUPPORTED_STREAM_METHODS:
        valid = ", ".join(SUPPORTED_STREAM_METHODS)
        raise ConfigError(
            f"Unsupported stream_method: {stream_method!r}. Valid: {valid}."
        )

    huc_level = str(values.get("huc_level", DEFAULTS["huc_level"])).upper()
    if huc_level not in SUPPORTED_HUC_LEVELS:
        valid = ", ".join(SUPPORTED_HUC_LEVELS)
        raise ConfigError(
            f"Unsupported huc_level: {huc_level!r}. Valid: {valid}."
        )

    palette = str(values.get("palette", DEFAULTS["palette"])).lower()
    if palette not in SUPPORTED_PALETTES:
        valid = ", ".join(SUPPORTED_PALETTES)
        raise ConfigError(
            f"Unsupported palette: {palette!r}. Valid: {valid}."
        )

    glow = bool(values.get("glow", DEFAULTS["glow"]))

    glow_mode = str(values.get("glow_mode", DEFAULTS["glow_mode"])).lower()
    if glow_mode not in SUPPORTED_GLOW_MODES:
        valid = ", ".join(SUPPORTED_GLOW_MODES)
        raise ConfigError(
            f"Unsupported glow_mode: {glow_mode!r}. Valid: {valid}."
        )

    try:
        glow_radius = float(values.get("glow_radius", DEFAULTS["glow_radius"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid glow_radius: {values.get('glow_radius')!r}. "
            "Expected a positive number."
        )
    if glow_radius <= 0:
        raise ConfigError(
            f"glow_radius must be greater than 0, got {glow_radius}."
        )

    outputs = _coerce_outputs(values.get("output", DEFAULTS["output"]))
    if not outputs:
        raise ConfigError("At least one output format must be enabled.")

    return Settings(
        regions=regions,
        projection=projection,
        stream_order=stream_order,
        stream_method=stream_method,
        huc_level=huc_level,
        background=background,
        line_width=line_width,
        palette=palette,
        glow=glow,
        glow_mode=glow_mode,
        glow_radius=glow_radius,
        outputs=outputs,
    )


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file into a plain mapping.

    A missing file is tolerated and yields an empty mapping (defaults will be
    used). A present-but-malformed file raises :class:`ConfigError`.

    Raises:
        ConfigError: If the file exists but is not valid YAML, or does not
            parse to a mapping.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse config file {p}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ConfigError(
            f"Config file {p} must contain a mapping at the top level."
        )
    unknown = set(raw) - set(DEFAULTS)
    if unknown:
        # Warn, don't fail: surface likely typos without blocking the run.
        import warnings

        warnings.warn(
            f"Ignoring unknown config keys in {p}: {', '.join(sorted(unknown))}",
            stacklevel=2,
        )
    return dict(raw)
