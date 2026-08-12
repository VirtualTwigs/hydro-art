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
    "WaterbodySettings",
    "ElevationSettings",
    "DEFAULTS",
    "SUPPORTED_REGIONS",
    "SUPPORTED_PROJECTIONS",
    "SUPPORTED_OUTPUTS",
    "SUPPORTED_PNG_SIZES",
    "SUPPORTED_STREAM_METHODS",
    "SUPPORTED_HUC_LEVELS",
    "SUPPORTED_PALETTES",
    "SUPPORTED_COLOR_MODES",
    "SUPPORTED_WIDTH_MODES",
    "SUPPORTED_GLOW_MODES",
    "SUPPORTED_COASTAL_MODES",
    "SUPPORTED_RENDER_ORDERS",
    "SUPPORTED_ELEVATION_SOURCES",
    "SUPPORTED_ELEVATION_TIERS",
    "SUPPORTED_CACHE_POLICIES",
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
SUPPORTED_REGIONS: tuple[str, ...] = ("Oregon", "Washington", "California")

#: Coordinate reference systems the pipeline knows how to handle.
SUPPORTED_PROJECTIONS: tuple[str, ...] = ("EPSG:5070", "EPSG:4326", "EPSG:3857")

#: Output formats selectable via config/CLI (PRD section 22): SVG is required,
#: the rest optional and produced by converting the SVG (PRD section 23).
SUPPORTED_OUTPUTS: tuple[str, ...] = ("svg", "pdf", "png", "tiff", "eps")

#: Raster export sizes in pixels (PRD section 23), user selectable via
#: ``png_size``. The largest relies on the converter's tile rendering.
SUPPORTED_PNG_SIZES: tuple[int, ...] = (4096, 8192, 16384, 32768, 65536)

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

#: Color art-direction modes (roadmap #23). ``watershed`` = deterministic
#: high-contrast palette per HUC group (default, unchanged); ``single`` = one
#: color for every flowline (``single_color``); ``elevation`` = hypsometric tint
#: mirroring ``tools/render_state_mono.py``.
SUPPORTED_COLOR_MODES: tuple[str, ...] = ("watershed", "single", "elevation")

#: Line-width art-direction modes (roadmap #23). ``uniform`` = every stroke is
#: the base ``line_width`` (default, unchanged); ``flow`` = width scales with a
#: channel's flow, mapped ``[width_min, width_max]`` shaped by ``width_gamma``.
SUPPORTED_WIDTH_MODES: tuple[str, ...] = ("uniform", "flow")

#: Glow rendering modes (PRD section 20): ``vector`` (pure-vector halo) or
#: ``blur`` (SVG Gaussian-blur filter). Only used when ``glow`` is enabled.
SUPPORTED_GLOW_MODES: tuple[str, ...] = ("vector", "blur")

#: Coast-handling policies for waterbody outlines (Item W2/W3).
#: ``conservative`` excludes coastal clip-boundary fragments (avoids portraying
#: truncated sea as closed shapes); ``permissive`` treats coastal like inland.
SUPPORTED_COASTAL_MODES: tuple[str, ...] = ("conservative", "permissive")

#: Where the waterbody-outline layer sits relative to the flowline layers.
SUPPORTED_RENDER_ORDERS: tuple[str, ...] = ("below", "above")

#: Authoritative elevation sources (Item 11 / Epoch 2). USGS 3DEP bare-earth
#: DEMs are the only source for the first release; the allowlist leaves room
#: for lidar/other products later without changing downstream code.
SUPPORTED_ELEVATION_SOURCES: tuple[str, ...] = ("3dep",)

#: Elevation resolution tiers (requirements.md #1). ``preview`` is a coarse,
#: cheap default; ``state``/``local`` escalate detail explicitly (never a
#: statewide 1 m default — see the non-functional budget constraint).
SUPPORTED_ELEVATION_TIERS: tuple[str, ...] = ("preview", "state", "local")

#: Cache reuse policy for elevation assets. ``reuse`` prefers cached tiles;
#: ``refresh`` re-fetches even when a cached copy exists.
SUPPORTED_CACHE_POLICIES: tuple[str, ...] = ("reuse", "refresh")

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

#: Built-in defaults, reflecting PRD sections 19 and 25.
DEFAULTS: dict[str, Any] = {
    "region": ["Oregon", "Washington"],
    "county": None,
    "projection": "EPSG:5070",
    "stream_order": "all",
    "stream_method": "strahler",
    "huc_level": "HUC4",
    "background": "#000000",
    "line_width": 0.35,
    "palette": "neon",
    "color_by": "watershed",
    "single_color": "#00ffff",
    "width_by": "uniform",
    "width_min": 0.35,
    "width_max": 2.0,
    "width_gamma": 1.0,
    "glow": False,
    "glow_mode": "blur",
    "glow_radius": 2.0,
    "png_size": 4096,
    "output": {"svg": True, "png": False, "pdf": False},
    "waterbodies": {
        "enabled": True,
        "color": "#2ec4ff",
        "stroke_width": 0.45,
        "min_inland_area_m2": 0.0,
        "min_coastal_area_m2": 0.0,
        "coastal_mode": "conservative",
        "render_order": "below",
    },
    "elevation": {
        "enabled": False,
        "source": "3dep",
        "tier": "preview",
        "vertical_exaggeration": 1.0,
        "cache_policy": "reuse",
    },
}


@dataclass(frozen=True)
class WaterbodySettings:
    """Validated settings for the optional waterbody-outline layer (Item W3).

    Attributes:
        enabled: Whether waterbody outlines are rendered (on by default).
        color: Single distinct water stroke color (hex), independent of the
            watershed palette.
        stroke_width: Outline stroke width in SVG user units; must be > 0.
        min_inland_area_m2: Minimum projected area (m²) for inland classes;
            ``0`` keeps every valid inland feature.
        min_coastal_area_m2: Minimum projected area (m²) for coastal classes.
        coastal_mode: Coast-handling policy (one of
            :data:`SUPPORTED_COASTAL_MODES`).
        render_order: Waterbody layer position relative to flowlines (one of
            :data:`SUPPORTED_RENDER_ORDERS`).
    """

    enabled: bool
    color: str
    stroke_width: float
    min_inland_area_m2: float
    min_coastal_area_m2: float
    coastal_mode: str
    render_order: str


@dataclass(frozen=True)
class ElevationSettings:
    """Validated settings for the optional elevation stage (Item 11).

    This is the configuration contract only: it selects the source, resolution
    tier, display exaggeration, and cache behavior for DEM-backed elevation.
    No pipeline stage reads it yet (acquisition is item 12), so a default build
    stays fully 2D. Per the vertical-reference decision, source datum/units are
    *preserved* downstream and never normalized here; vertical exaggeration is a
    display-only multiplier that never overwrites source-derived Z.

    Attributes:
        enabled: Whether elevation data is requested (off by default).
        source: Authoritative DEM source (one of
            :data:`SUPPORTED_ELEVATION_SOURCES`).
        tier: Resolution tier (one of :data:`SUPPORTED_ELEVATION_TIERS`).
        vertical_exaggeration: Display-only Z multiplier; must be > 0.
        cache_policy: Asset cache behavior (one of
            :data:`SUPPORTED_CACHE_POLICIES`).
    """

    enabled: bool
    source: str
    tier: str
    vertical_exaggeration: float
    cache_policy: str


@dataclass(frozen=True)
class Settings:
    """Validated, immutable configuration for a single pipeline run.

    Attributes:
        regions: Canonical region names to build (e.g. ``("Oregon",)``).
        county: Optional single Census county name to scope the build to
            (roadmap #24); ``None`` builds the whole region. Requires exactly
            one region when set.
        projection: Internal EPSG code used for all geometry operations.
        stream_order: Stream-order render filter (e.g. ``"all"``).
        stream_method: Stream-hierarchy method (strahler/shreve/hack/custom).
        huc_level: Watershed grouping level (HUC2..HUC12).
        background: Background color as a hex string (e.g. ``"#000000"``).
        line_width: Default stroke width in SVG user units; must be > 0.
        palette: Named color palette (e.g. ``"neon"``).
        color_by: Color art-direction mode (one of
            :data:`SUPPORTED_COLOR_MODES`); ``"watershed"`` is the default.
        single_color: Hex color used when ``color_by == "single"``.
        width_by: Line-width art-direction mode (one of
            :data:`SUPPORTED_WIDTH_MODES`); ``"uniform"`` is the default.
        width_min: Minimum stroke width for ``width_by == "flow"``; must be > 0.
        width_max: Maximum stroke width for ``width_by == "flow"``; must be > 0
            and >= ``width_min``.
        width_gamma: Shaping exponent for the flow→width ramp; must be > 0.
        glow: Whether the optional glow effect is enabled.
        glow_mode: Glow style when enabled (``"vector"`` or ``"blur"``).
        glow_radius: Glow radius in SVG user units; must be > 0.
        png_size: Raster export size in pixels (one of
            :data:`SUPPORTED_PNG_SIZES`).
        outputs: Set of output formats to produce (subset of
            :data:`SUPPORTED_OUTPUTS`).
        waterbodies: Validated waterbody-outline settings (Item W3).
        elevation: Validated elevation settings (Item 11); disabled by default.
    """

    regions: tuple[str, ...]
    county: str | None
    projection: str
    stream_order: str
    stream_method: str
    huc_level: str
    background: str
    line_width: float
    palette: str
    color_by: str
    single_color: str
    width_by: str
    width_min: float
    width_max: float
    width_gamma: float
    glow: bool
    glow_mode: str
    glow_radius: float
    png_size: int
    outputs: frozenset[str]
    waterbodies: WaterbodySettings
    elevation: ElevationSettings


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


def _coerce_waterbodies(value: Any) -> WaterbodySettings:
    """Validate the ``waterbodies`` block into a :class:`WaterbodySettings`.

    A partial mapping is tolerated: any sub-key the caller omits falls back to
    :data:`DEFAULTS`, so ``{"enabled": False}`` keeps every other default. This
    makes both direct ``build_settings`` calls and merged CLI/YAML input safe.

    Raises:
        ConfigError: If any provided sub-value is invalid.
    """
    defaults = DEFAULTS["waterbodies"]
    if value is None:
        merged = dict(defaults)
    elif isinstance(value, Mapping):
        merged = {**defaults, **value}
    else:
        raise ConfigError(
            f"Invalid 'waterbodies' value: {value!r}. Expected a mapping."
        )

    enabled = bool(merged.get("enabled", defaults["enabled"]))

    color = str(merged.get("color", defaults["color"]))
    if not _HEX_COLOR.match(color):
        raise ConfigError(
            f"Invalid waterbodies.color: {color!r}. Expected a hex color like "
            "'#2ec4ff'."
        )

    try:
        stroke_width = float(merged.get("stroke_width", defaults["stroke_width"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid waterbodies.stroke_width: {merged.get('stroke_width')!r}. "
            "Expected a positive number."
        )
    if stroke_width <= 0:
        raise ConfigError(
            f"waterbodies.stroke_width must be greater than 0, got {stroke_width}."
        )

    areas: dict[str, float] = {}
    for field_name in ("min_inland_area_m2", "min_coastal_area_m2"):
        try:
            area = float(merged.get(field_name, defaults[field_name]))
        except (TypeError, ValueError):
            raise ConfigError(
                f"Invalid waterbodies.{field_name}: {merged.get(field_name)!r}. "
                "Expected a non-negative number."
            )
        if area < 0:
            raise ConfigError(
                f"waterbodies.{field_name} must be >= 0, got {area}."
            )
        areas[field_name] = area

    coastal_mode = str(merged.get("coastal_mode", defaults["coastal_mode"])).lower()
    if coastal_mode not in SUPPORTED_COASTAL_MODES:
        valid = ", ".join(SUPPORTED_COASTAL_MODES)
        raise ConfigError(
            f"Unsupported waterbodies.coastal_mode: {coastal_mode!r}. Valid: {valid}."
        )

    render_order = str(merged.get("render_order", defaults["render_order"])).lower()
    if render_order not in SUPPORTED_RENDER_ORDERS:
        valid = ", ".join(SUPPORTED_RENDER_ORDERS)
        raise ConfigError(
            f"Unsupported waterbodies.render_order: {render_order!r}. Valid: {valid}."
        )

    return WaterbodySettings(
        enabled=enabled,
        color=color,
        stroke_width=stroke_width,
        min_inland_area_m2=areas["min_inland_area_m2"],
        min_coastal_area_m2=areas["min_coastal_area_m2"],
        coastal_mode=coastal_mode,
        render_order=render_order,
    )


def _coerce_elevation(value: Any) -> ElevationSettings:
    """Validate the ``elevation`` block into an :class:`ElevationSettings`.

    A partial mapping is tolerated: any sub-key the caller omits falls back to
    :data:`DEFAULTS`, so ``{"enabled": True}`` keeps every other default. This
    makes both direct ``build_settings`` calls and merged CLI/YAML input safe.

    Raises:
        ConfigError: If any provided sub-value is invalid.
    """
    defaults = DEFAULTS["elevation"]
    if value is None:
        merged = dict(defaults)
    elif isinstance(value, Mapping):
        merged = {**defaults, **value}
    else:
        raise ConfigError(
            f"Invalid 'elevation' value: {value!r}. Expected a mapping."
        )

    enabled = bool(merged.get("enabled", defaults["enabled"]))

    source = str(merged.get("source", defaults["source"])).lower()
    if source not in SUPPORTED_ELEVATION_SOURCES:
        valid = ", ".join(SUPPORTED_ELEVATION_SOURCES)
        raise ConfigError(
            f"Unsupported elevation.source: {source!r}. Valid: {valid}."
        )

    tier = str(merged.get("tier", defaults["tier"])).lower()
    if tier not in SUPPORTED_ELEVATION_TIERS:
        valid = ", ".join(SUPPORTED_ELEVATION_TIERS)
        raise ConfigError(
            f"Unsupported elevation.tier: {tier!r}. Valid: {valid}."
        )

    try:
        vertical_exaggeration = float(
            merged.get("vertical_exaggeration", defaults["vertical_exaggeration"])
        )
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid elevation.vertical_exaggeration: "
            f"{merged.get('vertical_exaggeration')!r}. Expected a positive number."
        )
    if vertical_exaggeration <= 0:
        raise ConfigError(
            "elevation.vertical_exaggeration must be greater than 0, got "
            f"{vertical_exaggeration}."
        )

    cache_policy = str(merged.get("cache_policy", defaults["cache_policy"])).lower()
    if cache_policy not in SUPPORTED_CACHE_POLICIES:
        valid = ", ".join(SUPPORTED_CACHE_POLICIES)
        raise ConfigError(
            f"Unsupported elevation.cache_policy: {cache_policy!r}. Valid: {valid}."
        )

    return ElevationSettings(
        enabled=enabled,
        source=source,
        tier=tier,
        vertical_exaggeration=vertical_exaggeration,
        cache_policy=cache_policy,
    )


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

    county_raw = values.get("county", DEFAULTS["county"])
    county = str(county_raw).strip() if county_raw is not None else None
    if not county:
        county = None
    if county is not None and len(regions) != 1:
        raise ConfigError(
            "A county build must target exactly one state; got regions="
            f"{list(regions)}. Select a single region alongside --county."
        )

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

    color_by = str(values.get("color_by", DEFAULTS["color_by"])).lower()
    if color_by not in SUPPORTED_COLOR_MODES:
        valid = ", ".join(SUPPORTED_COLOR_MODES)
        raise ConfigError(
            f"Unsupported color_by: {color_by!r}. Valid: {valid}."
        )

    single_color = str(values.get("single_color", DEFAULTS["single_color"]))
    if not _HEX_COLOR.match(single_color):
        raise ConfigError(
            f"Invalid single_color: {single_color!r}. "
            "Expected a hex color like '#00ffff'."
        )

    width_by = str(values.get("width_by", DEFAULTS["width_by"])).lower()
    if width_by not in SUPPORTED_WIDTH_MODES:
        valid = ", ".join(SUPPORTED_WIDTH_MODES)
        raise ConfigError(
            f"Unsupported width_by: {width_by!r}. Valid: {valid}."
        )

    try:
        width_min = float(values.get("width_min", DEFAULTS["width_min"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid width_min: {values.get('width_min')!r}. "
            "Expected a positive number."
        )
    if width_min <= 0:
        raise ConfigError(f"width_min must be greater than 0, got {width_min}.")

    try:
        width_max = float(values.get("width_max", DEFAULTS["width_max"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid width_max: {values.get('width_max')!r}. "
            "Expected a positive number."
        )
    if width_max <= 0:
        raise ConfigError(f"width_max must be greater than 0, got {width_max}.")
    if width_max < width_min:
        raise ConfigError(
            f"width_max must be >= width_min, got width_max={width_max} "
            f"and width_min={width_min}."
        )

    try:
        width_gamma = float(values.get("width_gamma", DEFAULTS["width_gamma"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid width_gamma: {values.get('width_gamma')!r}. "
            "Expected a positive number."
        )
    if width_gamma <= 0:
        raise ConfigError(
            f"width_gamma must be greater than 0, got {width_gamma}."
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

    try:
        png_size = int(values.get("png_size", DEFAULTS["png_size"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid png_size: {values.get('png_size')!r}. "
            f"Expected one of: {', '.join(str(s) for s in SUPPORTED_PNG_SIZES)}."
        )
    if png_size not in SUPPORTED_PNG_SIZES:
        valid = ", ".join(str(s) for s in SUPPORTED_PNG_SIZES)
        raise ConfigError(f"Unsupported png_size: {png_size}. Valid: {valid}.")

    outputs = _coerce_outputs(values.get("output", DEFAULTS["output"]))
    if not outputs:
        raise ConfigError("At least one output format must be enabled.")

    waterbodies = _coerce_waterbodies(values.get("waterbodies", DEFAULTS["waterbodies"]))
    elevation = _coerce_elevation(values.get("elevation", DEFAULTS["elevation"]))

    return Settings(
        regions=regions,
        county=county,
        projection=projection,
        stream_order=stream_order,
        stream_method=stream_method,
        huc_level=huc_level,
        background=background,
        line_width=line_width,
        palette=palette,
        color_by=color_by,
        single_color=single_color,
        width_by=width_by,
        width_min=width_min,
        width_max=width_max,
        width_gamma=width_gamma,
        glow=glow,
        glow_mode=glow_mode,
        glow_radius=glow_radius,
        png_size=png_size,
        outputs=outputs,
        waterbodies=waterbodies,
        elevation=elevation,
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
