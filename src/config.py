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

from src.crs import INTERNAL_CRS

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
    "WIDTH_PRESETS",
    "SUPPORTED_WIDTH_PRESETS",
    "SUPPORTED_GLOW_MODES",
    "SUPPORTED_COASTAL_MODES",
    "SUPPORTED_RENDER_ORDERS",
    "WATERBODY_PRESETS",
    "SUPPORTED_WATERBODY_PRESETS",
    "PointFeatureSettings",
    "ArealFeatureSettings",
    "HydroStructureSettings",
    "POINT_FEATURE_PRESETS",
    "AREAL_FEATURE_PRESETS",
    "HYDRO_STRUCTURE_PRESETS",
    "SUPPORTED_POINT_FEATURE_PRESETS",
    "SUPPORTED_AREAL_FEATURE_PRESETS",
    "SUPPORTED_HYDRO_STRUCTURE_PRESETS",
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
SUPPORTED_REGIONS: tuple[str, ...] = ("Oregon", "Washington", "California", "Idaho")

#: Coordinate reference systems the pipeline knows how to handle.
SUPPORTED_PROJECTIONS: tuple[str, ...] = (INTERNAL_CRS, "EPSG:4326", "EPSG:3857")

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

#: Named waterbody art-direction presets (Item W4). A preset is a convenience
#: directive: naming one in the ``waterbodies`` block expands to this bundle of
#: existing ``WaterbodySettings`` fields (precedence ``defaults < preset <
#: explicit``), inventing no new render behavior. ``screen`` mirrors the default
#: on-screen build; the two ``print-*`` presets use a bolder stroke and positive
#: area thresholds to declutter tiny ponds so outlines survive ink / large-format
#: rasterization.
#:
#: The print thresholds are **scale-specific** because one global value cannot serve
#: both zooms: ``print-state`` (100k/250k m²) is tuned for a whole-state / wall-sized
#: sheet, where it keeps ~46k Oregon outlines; ``print-county`` (25k/50k m²) is tuned
#: for a single-county sheet, where the state thresholds over-prune (Clark County, WA
#: evidence 2026-08-12: 100k m² drops 97% of waterbodies to 24, while 25k m² keeps a
#: readable ~62). Values remain human-tunable here; the ratios are art direction, not
#: a hard contract.
WATERBODY_PRESETS: dict[str, dict[str, Any]] = {
    "screen": {
        "color": "#2ec4ff",
        "stroke_width": 0.45,
        "min_inland_area_m2": 0.0,
        "min_coastal_area_m2": 0.0,
        "coastal_mode": "conservative",
        "render_order": "below",
    },
    "print-state": {
        "color": "#2ec4ff",
        "stroke_width": 0.9,
        "min_inland_area_m2": 100_000.0,  # ~0.1 km²: state / large-format legibility
        "min_coastal_area_m2": 250_000.0,
        "coastal_mode": "conservative",
        "render_order": "below",
    },
    "print-county": {
        "color": "#2ec4ff",
        "stroke_width": 0.9,
        "min_inland_area_m2": 25_000.0,  # ~2.5 ha: county-scale declutter (keeps ponds)
        "min_coastal_area_m2": 50_000.0,
        "coastal_mode": "conservative",
        "render_order": "below",
    },
}

#: Allowlist of preset names (for CLI ``choices`` + validation).
SUPPORTED_WATERBODY_PRESETS: tuple[str, ...] = tuple(WATERBODY_PRESETS)

#: Natural-feature art-direction presets (Item 64), mirroring
#: :data:`WATERBODY_PRESETS`. A preset is a convenience directive expanding to a
#: bundle of existing settings fields (precedence ``defaults < preset <
#: explicit``); it invents no new render behavior and is never stored on the
#: frozen settings. ``screen`` mirrors the on-screen default (no thinning); the
#: ``print-*`` presets declutter for ink — points thin to a wider minimum
#: spacing and tiny areal features are pruned by a positive area threshold.
#: ``print-state`` is tuned for a whole-state / wall sheet (thins harder);
#: ``print-county`` is less aggressive so a single county still reads.
POINT_FEATURE_PRESETS: dict[str, dict[str, Any]] = {
    "screen": {"min_spacing_m": 0.0, "render_order": "above"},
    "print-state": {"min_spacing_m": 8_000.0, "render_order": "above"},
    "print-county": {"min_spacing_m": 2_000.0, "render_order": "above"},
}

AREAL_FEATURE_PRESETS: dict[str, dict[str, Any]] = {
    "screen": {"min_area_m2": 0.0, "render_order": "below"},
    "print-state": {"min_area_m2": 100_000.0, "render_order": "below"},
    "print-county": {"min_area_m2": 25_000.0, "render_order": "below"},
}

#: Engineered-structure art-direction presets (Item #67), mirroring
#: :data:`AREAL_FEATURE_PRESETS`. A preset is a convenience directive expanding
#: to a bundle of existing settings fields (precedence
#: ``defaults < preset < explicit``); it invents no new render behavior and is
#: never stored on the frozen settings. ``screen`` mirrors the on-screen default
#: (no thinning/pruning); the ``print-*`` presets declutter for ink — tiny areal
#: structures are pruned by a positive area threshold and dense point structures
#: thin to a wider minimum spacing. ``print-state`` is tuned for a whole-state /
#: wall sheet (prunes harder); ``print-county`` is less aggressive so a single
#: county still reads. Structures render above the water by default.
#:
#: Values tuned from the Item #68 real-data QA run (HUC4 1807, Oregon coastal):
#: an unthinned basin selects ~557 structures (dam_weir 174, gaging_station 305,
#: canal_ditch 52, spillway 15, intake 9, gate 2) with 553/557 on-network at a
#: 3 m median — dense but legible on screen, a smear on a printed wall sheet. So
#: ``screen`` keeps everything at the default marker weight; ``print-county``
#: prunes sub-10k m² NHDArea slivers and thins point clusters to ~1.5 km while
#: enlarging markers so structures read at county zoom; ``print-state`` prunes
#: harder (60k m² / 8 km) and pushes marker size, fill opacity, and canal dash
#: further so the sparser set still reads at wall scale (see
#: ``implementation/real-data-findings.md``).
HYDRO_STRUCTURE_PRESETS: dict[str, dict[str, Any]] = {
    "screen": {
        "min_area_m2": 0.0,
        "min_spacing_m": 0.0,
        "size": 1.0,
        "opacity": 0.35,
        "dash": "4,3",
        "render_order": "above",
    },
    "print-county": {
        "min_area_m2": 10_000.0,
        "min_spacing_m": 1_500.0,
        "size": 1.3,
        "opacity": 0.45,
        "dash": "5,3",
        "render_order": "above",
    },
    "print-state": {
        "min_area_m2": 60_000.0,
        "min_spacing_m": 8_000.0,
        "size": 1.6,
        "opacity": 0.55,
        "dash": "7,4",
        "render_order": "above",
    },
}

#: Named scale-aware flow→width presets (Epoch 18). A preset is a convenience
#: directive: naming one (top-level ``width_preset`` / ``--width-preset``) expands
#: to this bundle of existing ``width_*`` fields, inventing no new render behavior.
#: One width mapping cannot serve every extent — discharge spans ~5 orders of
#: magnitude across a whole state, so ``state`` uses a **logarithmic** ramp (the
#: only thing that keeps headwaters visible next to the Columbia); ``basin`` and
#: ``watershed`` cover a smaller range, so a **power-law** ramp (``width_gamma``
#: 0.45 ≈ ``Q^0.45``; 0.5 ≈ ``√Q``) reads as both legible and geomorphologically
#: honest (Leopold & Maddock downstream hydraulic geometry ``w ∝ Q^0.5``). Values
#: are art direction, human-tunable — not a hard contract. Precedence is
#: ``defaults < preset < explicit``; the preset is consumed at config time and is
#: NOT stored on :class:`Settings`, so a build without one stays byte-identical.
WIDTH_PRESETS: dict[str, dict[str, Any]] = {
    "state": {  # log, ~10:1 dynamic range
        "width_by": "flow",
        "width_min": 0.35,
        "width_max": 3.5,
        "width_gamma": 1.0,
        "width_log": True,
    },
    "basin": {  # power-law ~Q^0.45, ~6:1
        "width_by": "flow",
        "width_min": 0.35,
        "width_max": 2.1,
        "width_gamma": 0.45,
        "width_log": False,
    },
    "watershed": {  # √Q hydraulic geometry, ~4:1
        "width_by": "flow",
        "width_min": 0.35,
        "width_max": 1.4,
        "width_gamma": 0.5,
        "width_log": False,
    },
}

#: Allowlists of preset names (for CLI ``choices`` + validation).
SUPPORTED_POINT_FEATURE_PRESETS: tuple[str, ...] = tuple(POINT_FEATURE_PRESETS)
SUPPORTED_AREAL_FEATURE_PRESETS: tuple[str, ...] = tuple(AREAL_FEATURE_PRESETS)
SUPPORTED_HYDRO_STRUCTURE_PRESETS: tuple[str, ...] = tuple(HYDRO_STRUCTURE_PRESETS)
SUPPORTED_WIDTH_PRESETS: tuple[str, ...] = tuple(WIDTH_PRESETS)

#: Validation pattern for an SVG ``stroke-dasharray`` value (comma/space
#: separated positive numbers, e.g. ``"4,3"`` or ``"6 2 1"``).
_DASHARRAY = re.compile(r"^\d+(?:\.\d+)?(?:[,\s]+\d+(?:\.\d+)?)*$")

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
    "months": "annual",
    "projection": INTERNAL_CRS,
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
    "width_log": False,
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
    "point_features": {
        "enabled": False,
        "color": "",
        "size": 1.0,
        "min_spacing_m": 0.0,
        "render_order": "above",
    },
    "areal_features": {
        "enabled": False,
        "color": "",
        "opacity": 0.35,
        "dash": "4,3",
        "min_area_m2": 0.0,
        "render_order": "below",
    },
    "hydro_structures": {
        "enabled": False,
        "color": "",
        "size": 1.0,
        "opacity": 0.35,
        "dash": "4,3",
        "min_area_m2": 0.0,
        "min_spacing_m": 0.0,
        "render_order": "above",
    },
    "elevation": {
        "enabled": False,
        "source": "3dep",
        "tier": "preview",
        "vertical_exaggeration": 1.0,
        "cache_policy": "reuse",
        "tile_budget": 0,
    },
}

#: Top-level config keys that are consumed directives, not stored defaults (Epoch
#: 18). They are valid in a config file / CLI but expand into other fields, so
#: :func:`load_yaml` must not flag them as unknown.
_CONFIG_DIRECTIVES: frozenset[str] = frozenset({"width_preset"})


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
class PointFeatureSettings:
    """Validated settings for the optional point-glyph layer (Item 64).

    Spring/waterfall/rapids points are rendered as glyphs; this block controls
    the group-level knobs the pipeline bridges into the rendering layer's
    per-family styles (:data:`~src.rendering.DEFAULT_POINT_STYLES`).

    Attributes:
        enabled: Whether point glyphs are rendered (off by default, so a default
            build is byte-identical).
        color: Optional single glyph color (hex) overriding every family's
            default; ``""`` keeps the rendering layer's per-family colors.
        size: Glyph size multiplier applied over the per-family defaults; > 0.
        min_spacing_m: Deterministic per-family density cap — the minimum spacing
            (m) between kept points of the same family; ``0`` keeps every point.
        render_order: Layer position relative to flowlines (one of
            :data:`SUPPORTED_RENDER_ORDERS`); ``"above"`` by default.
    """

    enabled: bool
    color: str
    size: float
    min_spacing_m: float
    render_order: str


@dataclass(frozen=True)
class ArealFeatureSettings:
    """Validated settings for the optional areal natural-feature layer (Item 64).

    Wetlands/playas/perennial-ice polygons get differentiated fills; this block
    controls the group-level knobs the pipeline bridges into the rendering
    layer's per-family styles (:data:`~src.rendering.DEFAULT_AREAL_STYLES`).

    Attributes:
        enabled: Whether areal fills are rendered (off by default, so a default
            build is byte-identical).
        color: Optional single fill/stroke color (hex) overriding every family's
            default; ``""`` keeps the rendering layer's per-family colors.
        opacity: Fill opacity for solid-filled families (perennial ice); in
            ``(0, 1]``.
        dash: ``stroke-dasharray`` for dashed-outline families (playa).
        min_area_m2: Minimum projected area (m²) an areal feature must exceed to
            be kept; ``0`` keeps every valid feature.
        render_order: Layer position relative to flowlines (one of
            :data:`SUPPORTED_RENDER_ORDERS`); ``"below"`` by default.
    """

    enabled: bool
    color: str
    opacity: float
    dash: str
    min_area_m2: float
    render_order: str


@dataclass(frozen=True)
class HydroStructureSettings:
    """Validated settings for the optional engineered-structure layer (Item #67).

    Dams/weirs, gates, gaging stations, water intakes/outflows, spillways, lock
    chambers, and canals/ditches (classified in :mod:`src.hydro_structures`) span
    three geometry kinds, so this one block controls the group-level knobs the
    pipeline bridges into the rendering layer's per-class styles
    (:data:`~src.rendering.DEFAULT_HYDRO_STRUCTURE_STYLES`). Structures sit above
    the water by default so a dam reads on the channel it crosses. Disabled by
    default so a default build stays byte-identical.

    Attributes:
        enabled: Whether structures are rendered (off by default).
        color: Optional single color (hex) overriding every class's default;
            ``""`` keeps the rendering layer's per-class colors.
        size: Point-marker size multiplier applied over the per-class defaults;
            must be > 0.
        opacity: Fill opacity for solid-filled polygon structures; in ``(0, 1]``.
        dash: ``stroke-dasharray`` for dashed-outline polygon structures.
        min_area_m2: Minimum projected area (m²) a polygon structure must exceed
            to be kept; ``0`` keeps every valid polygon.
        min_spacing_m: Deterministic per-class density cap — the minimum spacing
            (m) between kept point structures of the same class; ``0`` keeps all.
        render_order: Layer position relative to the water stack (one of
            :data:`SUPPORTED_RENDER_ORDERS`); ``"above"`` by default.
    """

    enabled: bool
    color: str
    size: float
    opacity: float
    dash: str
    min_area_m2: float
    min_spacing_m: float
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
        tile_budget: Maximum number of DEM tiles a single acquisition may fetch
            (roadmap #21). ``0`` means unlimited; a positive cap makes DEM
            acquisition fail fast before downloading when a region's tile count
            exceeds it.
    """

    enabled: bool
    source: str
    tier: str
    vertical_exaggeration: float
    cache_policy: str
    tile_budget: int


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
        width_log: Whether the flow→width ramp normalizes on ``log(metric)``
            (Epoch 18); ``False`` (default) keeps a linear normalization.
        glow: Whether the optional glow effect is enabled.
        glow_mode: Glow style when enabled (``"vector"`` or ``"blur"``).
        glow_radius: Glow radius in SVG user units; must be > 0.
        png_size: Raster export size in pixels (one of
            :data:`SUPPORTED_PNG_SIZES`).
        outputs: Set of output formats to produce (subset of
            :data:`SUPPORTED_OUTPUTS`).
        waterbodies: Validated waterbody-outline settings (Item W3).
        point_features: Validated point-glyph settings (Item 64); disabled by
            default.
        areal_features: Validated areal natural-feature settings (Item 64);
            disabled by default.
        hydro_structures: Validated engineered-structure settings (Item
            #67); disabled by default.
        elevation: Validated elevation settings (Item 11); disabled by default.
    """

    regions: tuple[str, ...]
    county: str | None
    months: tuple[int, ...]
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
    width_log: bool
    glow: bool
    glow_mode: str
    glow_radius: float
    png_size: int
    outputs: frozenset[str]
    waterbodies: WaterbodySettings
    point_features: PointFeatureSettings
    areal_features: ArealFeatureSettings
    hydro_structures: HydroStructureSettings
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


#: Lowercase month tokens -> month number, for :func:`parse_months`. Kept here
#: (not imported from ``src.monthly_flow``) so ``config.py`` stays numpy-free.
_MONTH_TOKENS: dict[str, int] = {}
for _i, (_abbr, _full) in enumerate(
    [
        ("jan", "january"), ("feb", "february"), ("mar", "march"),
        ("apr", "april"), ("may", "may"), ("jun", "june"),
        ("jul", "july"), ("aug", "august"), ("sep", "september"),
        ("oct", "october"), ("nov", "november"), ("dec", "december"),
    ],
    start=1,
):
    _MONTH_TOKENS[_abbr] = _i
    _MONTH_TOKENS[_full] = _i

#: Tokens that mean "no month selection" (annual mean, the default behavior).
_ANNUAL_TOKENS = {"", "annual", "all", "mean"}


def _month_number(token: str) -> int:
    """Return the 1-12 month number for a numeric or named ``token``.

    Raises:
        ConfigError: If ``token`` is not a valid month.
    """
    token = token.strip().lower()
    if token in _MONTH_TOKENS:
        return _MONTH_TOKENS[token]
    if token.isdigit():
        n = int(token)
        if 1 <= n <= 12:
            return n
    raise ConfigError(
        f"Invalid month: {token!r}. Use 1-12, a month name (jul/july), a range "
        "(5-9, may-sep, wrapping like nov-feb), or 'annual'."
    )


def parse_months(value: Any) -> tuple[int, ...]:
    """Parse a ``--months`` value into a canonical ``tuple[int, ...]``.

    Forms (case-insensitive): ``None``/``""``/``annual``/``all``/``mean`` ->
    ``()`` (annual mean, the default); a single month ``"7"``/``"jul"``/
    ``"july"`` -> ``(7,)``; an inclusive range ``"5-9"``/``"may-sep"`` ->
    ``(5, 6, 7, 8, 9)``; a wrapping range ``"nov-feb"`` -> ``(11, 12, 1, 2)``.
    Out-of-range or unparseable input raises :class:`ConfigError`.
    """
    if value is None:
        return ()
    text = str(value).strip().lower()
    if text in _ANNUAL_TOKENS:
        return ()
    if "-" in text:
        parts = text.split("-")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ConfigError(
                f"Invalid month range: {value!r}. Use forms like '5-9' or "
                "'may-sep' (wrapping like 'nov-feb')."
            )
        start, end = _month_number(parts[0]), _month_number(parts[1])
        months: list[int] = []
        m = start
        while True:
            months.append(m)
            if m == end:
                break
            m = m + 1 if m < 12 else 1
        return tuple(months)
    return (_month_number(text),)


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

    A ``preset`` directive (Item W4) expands a named :data:`WATERBODY_PRESETS`
    bundle with precedence ``defaults < preset < explicit`` — so an explicit
    sub-key passed alongside a preset still wins. ``preset`` is consumed here and
    never stored on :class:`WaterbodySettings`, so a build without one is unchanged.

    Raises:
        ConfigError: If any provided sub-value (or the preset name) is invalid.
    """
    defaults = DEFAULTS["waterbodies"]
    if value is None:
        provided: dict[str, Any] = {}
    elif isinstance(value, Mapping):
        provided = dict(value)
    else:
        raise ConfigError(
            f"Invalid 'waterbodies' value: {value!r}. Expected a mapping."
        )

    preset_values: dict[str, Any] = {}
    preset_name = provided.pop("preset", None)
    if preset_name is not None:
        key = str(preset_name).lower()
        if key not in WATERBODY_PRESETS:
            valid = ", ".join(SUPPORTED_WATERBODY_PRESETS)
            raise ConfigError(
                f"Unsupported waterbodies.preset: {preset_name!r}. Valid: {valid}."
            )
        preset_values = WATERBODY_PRESETS[key]

    merged = {**defaults, **preset_values, **provided}

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


def _coerce_optional_color(value: Any, field: str) -> str:
    """Validate an optional hex color; ``""``/``None`` means "use defaults"."""
    if value is None:
        return ""
    color = str(value)
    if color == "":
        return ""
    if not _HEX_COLOR.match(color):
        raise ConfigError(
            f"Invalid {field}: {color!r}. Expected a hex color like '#2ec4ff' "
            "(or empty to use the per-family defaults)."
        )
    return color


def _coerce_preset(
    provided: dict[str, Any], presets: dict[str, dict[str, Any]], field: str
) -> dict[str, Any]:
    """Pop + validate a ``preset`` directive, returning its expansion bundle.

    Mirrors :func:`_coerce_waterbodies`: the preset is consumed here and never
    stored on the resulting settings, so a build without one is unchanged.
    """
    preset_name = provided.pop("preset", None)
    if preset_name is None:
        return {}
    key = str(preset_name).lower()
    if key not in presets:
        valid = ", ".join(presets)
        raise ConfigError(
            f"Unsupported {field}.preset: {preset_name!r}. Valid: {valid}."
        )
    return presets[key]


def _coerce_nonneg(value: Any, field: str) -> float:
    """Coerce ``value`` to a float and require it be >= 0."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid {field}: {value!r}. Expected a non-negative number."
        )
    if result < 0:
        raise ConfigError(f"{field} must be >= 0, got {result}.")
    return result


def _coerce_render_order(value: Any, field: str) -> str:
    """Validate a ``render_order`` sub-key against :data:`SUPPORTED_RENDER_ORDERS`."""
    order = str(value).lower()
    if order not in SUPPORTED_RENDER_ORDERS:
        valid = ", ".join(SUPPORTED_RENDER_ORDERS)
        raise ConfigError(f"Unsupported {field}.render_order: {order!r}. Valid: {valid}.")
    return order


def _coerce_point_features(value: Any) -> PointFeatureSettings:
    """Validate the ``point_features`` block into :class:`PointFeatureSettings`.

    A partial mapping is tolerated (omitted sub-keys fall back to
    :data:`DEFAULTS`); a ``preset`` directive expands a named
    :data:`POINT_FEATURE_PRESETS` bundle with precedence
    ``defaults < preset < explicit``. Mirrors :func:`_coerce_waterbodies`.

    Raises:
        ConfigError: If any provided sub-value (or the preset name) is invalid.
    """
    defaults = DEFAULTS["point_features"]
    if value is None:
        provided: dict[str, Any] = {}
    elif isinstance(value, Mapping):
        provided = dict(value)
    else:
        raise ConfigError(
            f"Invalid 'point_features' value: {value!r}. Expected a mapping."
        )

    preset_values = _coerce_preset(provided, POINT_FEATURE_PRESETS, "point_features")
    merged = {**defaults, **preset_values, **provided}

    enabled = bool(merged.get("enabled", defaults["enabled"]))
    color = _coerce_optional_color(merged.get("color", defaults["color"]), "point_features.color")

    try:
        size = float(merged.get("size", defaults["size"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid point_features.size: {merged.get('size')!r}. "
            "Expected a positive number."
        )
    if size <= 0:
        raise ConfigError(f"point_features.size must be greater than 0, got {size}.")

    min_spacing_m = _coerce_nonneg(
        merged.get("min_spacing_m", defaults["min_spacing_m"]),
        "point_features.min_spacing_m",
    )
    render_order = _coerce_render_order(
        merged.get("render_order", defaults["render_order"]), "point_features"
    )

    return PointFeatureSettings(
        enabled=enabled,
        color=color,
        size=size,
        min_spacing_m=min_spacing_m,
        render_order=render_order,
    )


def _coerce_areal_features(value: Any) -> ArealFeatureSettings:
    """Validate the ``areal_features`` block into :class:`ArealFeatureSettings`.

    A partial mapping is tolerated (omitted sub-keys fall back to
    :data:`DEFAULTS`); a ``preset`` directive expands a named
    :data:`AREAL_FEATURE_PRESETS` bundle with precedence
    ``defaults < preset < explicit``. Mirrors :func:`_coerce_waterbodies`.

    Raises:
        ConfigError: If any provided sub-value (or the preset name) is invalid.
    """
    defaults = DEFAULTS["areal_features"]
    if value is None:
        provided: dict[str, Any] = {}
    elif isinstance(value, Mapping):
        provided = dict(value)
    else:
        raise ConfigError(
            f"Invalid 'areal_features' value: {value!r}. Expected a mapping."
        )

    preset_values = _coerce_preset(provided, AREAL_FEATURE_PRESETS, "areal_features")
    merged = {**defaults, **preset_values, **provided}

    enabled = bool(merged.get("enabled", defaults["enabled"]))
    color = _coerce_optional_color(merged.get("color", defaults["color"]), "areal_features.color")

    try:
        opacity = float(merged.get("opacity", defaults["opacity"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid areal_features.opacity: {merged.get('opacity')!r}. "
            "Expected a number in (0, 1]."
        )
    if not 0 < opacity <= 1:
        raise ConfigError(
            f"areal_features.opacity must be in (0, 1], got {opacity}."
        )

    dash = str(merged.get("dash", defaults["dash"]))
    if not _DASHARRAY.match(dash):
        raise ConfigError(
            f"Invalid areal_features.dash: {dash!r}. Expected a stroke-dasharray "
            "like '4,3'."
        )

    min_area_m2 = _coerce_nonneg(
        merged.get("min_area_m2", defaults["min_area_m2"]),
        "areal_features.min_area_m2",
    )
    render_order = _coerce_render_order(
        merged.get("render_order", defaults["render_order"]), "areal_features"
    )

    return ArealFeatureSettings(
        enabled=enabled,
        color=color,
        opacity=opacity,
        dash=dash,
        min_area_m2=min_area_m2,
        render_order=render_order,
    )


def _coerce_hydro_structures(value: Any) -> HydroStructureSettings:
    """Validate the ``hydro_structures`` block into :class:`HydroStructureSettings`.

    A partial mapping is tolerated (omitted sub-keys fall back to
    :data:`DEFAULTS`); a ``preset`` directive expands a named
    :data:`HYDRO_STRUCTURE_PRESETS` bundle with precedence
    ``defaults < preset < explicit``. Mirrors :func:`_coerce_areal_features`, but
    validates the point-marker ``size`` / ``min_spacing_m`` knobs too, because
    engineered structures span point, line, and polygon geometry.

    Raises:
        ConfigError: If any provided sub-value (or the preset name) is invalid.
    """
    defaults = DEFAULTS["hydro_structures"]
    if value is None:
        provided: dict[str, Any] = {}
    elif isinstance(value, Mapping):
        provided = dict(value)
    else:
        raise ConfigError(
            f"Invalid 'hydro_structures' value: {value!r}. Expected a mapping."
        )

    preset_values = _coerce_preset(
        provided, HYDRO_STRUCTURE_PRESETS, "hydro_structures"
    )
    merged = {**defaults, **preset_values, **provided}

    enabled = bool(merged.get("enabled", defaults["enabled"]))
    color = _coerce_optional_color(
        merged.get("color", defaults["color"]), "hydro_structures.color"
    )

    try:
        size = float(merged.get("size", defaults["size"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid hydro_structures.size: {merged.get('size')!r}. "
            "Expected a positive number."
        )
    if size <= 0:
        raise ConfigError(
            f"hydro_structures.size must be greater than 0, got {size}."
        )

    try:
        opacity = float(merged.get("opacity", defaults["opacity"]))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid hydro_structures.opacity: {merged.get('opacity')!r}. "
            "Expected a number in (0, 1]."
        )
    if not 0 < opacity <= 1:
        raise ConfigError(
            f"hydro_structures.opacity must be in (0, 1], got {opacity}."
        )

    dash = str(merged.get("dash", defaults["dash"]))
    if not _DASHARRAY.match(dash):
        raise ConfigError(
            f"Invalid hydro_structures.dash: {dash!r}. Expected a "
            "stroke-dasharray like '4,3'."
        )

    min_area_m2 = _coerce_nonneg(
        merged.get("min_area_m2", defaults["min_area_m2"]),
        "hydro_structures.min_area_m2",
    )
    min_spacing_m = _coerce_nonneg(
        merged.get("min_spacing_m", defaults["min_spacing_m"]),
        "hydro_structures.min_spacing_m",
    )
    render_order = _coerce_render_order(
        merged.get("render_order", defaults["render_order"]), "hydro_structures"
    )

    return HydroStructureSettings(
        enabled=enabled,
        color=color,
        size=size,
        opacity=opacity,
        dash=dash,
        min_area_m2=min_area_m2,
        min_spacing_m=min_spacing_m,
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

    raw_budget = merged.get("tile_budget", defaults["tile_budget"])
    if isinstance(raw_budget, bool):
        raise ConfigError(
            f"Invalid elevation.tile_budget: {raw_budget!r}. "
            "Expected a non-negative integer (0 = unlimited)."
        )
    try:
        tile_budget = int(raw_budget)
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid elevation.tile_budget: {raw_budget!r}. "
            "Expected a non-negative integer (0 = unlimited)."
        )
    if tile_budget < 0:
        raise ConfigError(
            f"elevation.tile_budget must be >= 0 (0 = unlimited), got {tile_budget}."
        )

    return ElevationSettings(
        enabled=enabled,
        source=source,
        tier=tier,
        vertical_exaggeration=vertical_exaggeration,
        cache_policy=cache_policy,
        tile_budget=tile_budget,
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

    months = parse_months(values.get("months", DEFAULTS["months"]))

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

    # Scale-aware flow→width preset (Epoch 18). A top-level ``width_preset``
    # expands to a bundle of ``width_*`` fields with precedence
    # ``defaults < preset < explicit``. Because production always passes a
    # DEFAULTS-spread mapping (see :func:`cli.settings_from_args`), "explicit"
    # is detected by comparison against the default: a field that differs from
    # its default is an explicit override and wins; otherwise the preset (if any)
    # supplies the value. The directive is consumed here, never stored.
    width_preset_name = values.get("width_preset")
    width_preset_values: dict[str, Any] = {}
    if width_preset_name is not None:
        key = str(width_preset_name).lower()
        if key not in WIDTH_PRESETS:
            valid = ", ".join(SUPPORTED_WIDTH_PRESETS)
            raise ConfigError(
                f"Unsupported width_preset: {width_preset_name!r}. Valid: {valid}."
            )
        width_preset_values = WIDTH_PRESETS[key]

    def _width_value(field: str) -> Any:
        provided = values.get(field, DEFAULTS[field])
        if provided != DEFAULTS[field]:
            return provided  # explicit override (differs from default) wins
        return width_preset_values.get(field, DEFAULTS[field])

    width_by = str(_width_value("width_by")).lower()
    if width_by not in SUPPORTED_WIDTH_MODES:
        valid = ", ".join(SUPPORTED_WIDTH_MODES)
        raise ConfigError(
            f"Unsupported width_by: {width_by!r}. Valid: {valid}."
        )

    try:
        width_min = float(_width_value("width_min"))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid width_min: {_width_value('width_min')!r}. "
            "Expected a positive number."
        )
    if width_min <= 0:
        raise ConfigError(f"width_min must be greater than 0, got {width_min}.")

    try:
        width_max = float(_width_value("width_max"))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid width_max: {_width_value('width_max')!r}. "
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
        width_gamma = float(_width_value("width_gamma"))
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid width_gamma: {_width_value('width_gamma')!r}. "
            "Expected a positive number."
        )
    if width_gamma <= 0:
        raise ConfigError(
            f"width_gamma must be greater than 0, got {width_gamma}."
        )

    width_log = bool(_width_value("width_log"))

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
    point_features = _coerce_point_features(
        values.get("point_features", DEFAULTS["point_features"])
    )
    areal_features = _coerce_areal_features(
        values.get("areal_features", DEFAULTS["areal_features"])
    )
    hydro_structures = _coerce_hydro_structures(
        values.get("hydro_structures", DEFAULTS["hydro_structures"])
    )
    elevation = _coerce_elevation(values.get("elevation", DEFAULTS["elevation"]))

    return Settings(
        regions=regions,
        county=county,
        months=months,
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
        width_log=width_log,
        glow=glow,
        glow_mode=glow_mode,
        glow_radius=glow_radius,
        png_size=png_size,
        outputs=outputs,
        waterbodies=waterbodies,
        point_features=point_features,
        areal_features=areal_features,
        hydro_structures=hydro_structures,
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
    unknown = set(raw) - set(DEFAULTS) - _CONFIG_DIRECTIVES
    if unknown:
        # Warn, don't fail: surface likely typos without blocking the run.
        import warnings

        warnings.warn(
            f"Ignoring unknown config keys in {p}: {', '.join(sorted(unknown))}",
            stacklevel=2,
        )
    return dict(raw)
