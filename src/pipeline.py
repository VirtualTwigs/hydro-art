"""Pipeline skeleton.

Defines the ordered stages of the GIS -> SVG pipeline (PRD section 8). The
``download`` and ``extract`` stages are implemented (dataset acquisition and
extraction); the remaining stages are no-op stubs replaced by later roadmap
items. Every stage receives a :class:`RunContext` by dependency injection and
shares results through ``context.artifacts``; there is no global state.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from src.cache import Cache, DownloaderLike, ensure_cached, extract_all
from src.config import ConfigError, Settings
from src.datasets import resolve_required_files
from src.clipping import clip_layers, region_boundary
from src.coloring import assign_colors
from src.download import Downloader, UrllibFetcher
from src.export import Exporter, FileExporter
from src.geometry import RepairStats, repair_layer
from src.graph import build_graph
from src.loading import LayerLoader, PyogrioLayerLoader
from src.optimize import SvgOptimizer, SvgoOptimizer
from src.ordering import assign_stream_order
from src.projection import reproject_layer
from src.rendering import render_svg, scaled_widths
from src.waterbodies import classify_layer
from src.waterbody_selection import (
    WaterbodySelectionPolicy,
    process_waterbodies,
)
from src.watersheds import group_segments_by_huc, watershed_stats

__all__ = ["Stage", "RunContext", "PIPELINE_STAGES", "Pipeline"]


@dataclass
class RunContext:
    """State shared across pipeline stages for a single run.

    Attributes:
        settings: The validated run settings.
        console: Rich console for user-facing output.
        cache_dir: Directory for cached archives.
        datasets_dir: Directory for extracted GIS data.
        output_dir: Directory where exported files are written.
        downloader: Injected downloader used by the acquisition stage.
        loader: Injected layer loader used by the validate stage.
        optimizer: Injected SVG optimizer used by the optimize_svg stage.
        exporter: Injected exporter used by the export stage.
        artifacts: Mutable bag of results passed between stages.
    """

    settings: Settings
    console: Console
    cache_dir: Path
    datasets_dir: Path
    output_dir: Path
    downloader: DownloaderLike
    loader: LayerLoader
    optimizer: SvgOptimizer
    exporter: Exporter
    artifacts: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        """Log a stage message to the console."""
        self.console.log(message)


@dataclass(frozen=True)
class Stage:
    """A single named pipeline stage."""

    name: str
    run: Callable[[RunContext], None]


def _stub(name: str) -> Callable[[RunContext], None]:
    """Build a no-op stage function that logs its own name."""

    def _run(ctx: RunContext) -> None:
        ctx.console.log(f"[dim]stage[/dim] {name} [yellow](stub)[/yellow]")

    return _run


def _download_stage(ctx: RunContext) -> None:
    """Resolve required files for the regions and ensure they are cached."""
    descriptors = resolve_required_files(ctx.settings)
    cache = Cache(ctx.cache_dir)
    ctx.artifacts["descriptors"] = descriptors
    ctx.artifacts["cache"] = cache
    ctx.log(f"[bold]download[/bold] resolving {len(descriptors)} file(s)")
    ensure_cached(descriptors, cache, ctx.downloader, log=ctx.log)


def _extract_stage(ctx: RunContext) -> None:
    """Extract every cached archive into the datasets directory."""
    descriptors = ctx.artifacts["descriptors"]
    cache = ctx.artifacts["cache"]
    dirs = extract_all(descriptors, cache, ctx.datasets_dir, log=ctx.log)
    ctx.artifacts["dataset_dirs"] = dirs


def _validate_stage(ctx: RunContext) -> None:
    """Load every extracted dataset's hydrography layers into memory."""
    descriptors = ctx.artifacts["descriptors"]
    dataset_dirs = ctx.artifacts["dataset_dirs"]
    layers = []
    for descriptor, dataset_dir in zip(descriptors, dataset_dirs):
        layers.extend(
            ctx.loader.load_layers(dataset_dir, descriptor.dataset_id, descriptor.huc4)
        )
    ctx.artifacts["layers"] = layers
    total = sum(len(layer.geometries) for layer in layers)
    ctx.log(f"[bold]validate[/bold] loaded {len(layers)} layer(s), {total} geometries")

    # Areal-water is an additive layer: only loaded when enabled AND the loader
    # supports it, so river-only loaders (and disabled builds) stay untouched.
    if ctx.settings.waterbodies.enabled and hasattr(
        ctx.loader, "load_waterbody_layers"
    ):
        wb_layers = []
        for descriptor, dataset_dir in zip(descriptors, dataset_dirs):
            wb_layers.extend(
                ctx.loader.load_waterbody_layers(
                    dataset_dir, descriptor.dataset_id, descriptor.huc4
                )
            )
        ctx.artifacts["waterbody_layers"] = wb_layers
        wb_total = sum(len(layer.geometries) for layer in wb_layers)
        ctx.log(
            f"[bold]validate[/bold] loaded {len(wb_layers)} waterbody layer(s), "
            f"{wb_total} polygons"
        )


def _repair_stage(ctx: RunContext) -> None:
    """Repair invalid/degenerate geometries and record repair statistics."""
    layers = ctx.artifacts["layers"]
    repaired = []
    stats = RepairStats()
    for layer in layers:
        kept, layer_stats = repair_layer(layer.geometries)
        stats = stats.merge(layer_stats)
        repaired.append(replace(layer, geometries=tuple(kept)))
    ctx.artifacts["repaired_layers"] = repaired
    ctx.artifacts["repair_stats"] = stats
    dropped = stats.empties_dropped + stats.collapsed_dropped
    ctx.log(
        f"[bold]repair_geometries[/bold] {stats.total_in}->{stats.total_out} "
        f"(fixed {stats.invalid_fixed} invalid, dropped {dropped}, "
        f"removed {stats.duplicate_vertices_removed} dup vertices)"
    )


def _reproject_stage(ctx: RunContext) -> None:
    """Normalize every repaired layer to the configured internal projection."""
    target = ctx.settings.projection
    layers = ctx.artifacts["repaired_layers"]
    projected = [reproject_layer(layer, target) for layer in layers]
    ctx.artifacts["projected_layers"] = projected
    ctx.log(f"[bold]reproject[/bold] normalized {len(projected)} layer(s) to {target}")


def _clip_stage(ctx: RunContext) -> None:
    """Clip the projected hydrography to the region boundary (WBD polygons)."""
    layers = ctx.artifacts["projected_layers"]
    boundary = region_boundary(layers)
    clipped, stats = clip_layers(layers, boundary)
    ctx.artifacts["region_boundary"] = boundary
    ctx.artifacts["clipped_layers"] = clipped
    ctx.artifacts["clip_stats"] = stats
    ctx.log(
        f"[bold]clip_to_region[/bold] {stats.total_in}->{stats.total_out} "
        f"(dropped {stats.dropped_outside} outside, "
        f"trimmed {stats.clipped_partial})"
    )


def _build_graph_stage(ctx: RunContext) -> None:
    """Construct the directed river network from the clipped flowlines."""
    layers = ctx.artifacts["clipped_layers"]
    hydro_graph = build_graph(layers)
    stats = hydro_graph.statistics()
    ctx.artifacts["hydro_graph"] = hydro_graph
    ctx.artifacts["network_stats"] = stats
    ctx.log(
        f"[bold]build_graph[/bold] {stats.num_nodes} nodes, {stats.num_edges} "
        f"segments ({stats.num_sources} sources, {stats.num_outlets} outlets, "
        f"{stats.total_length:.1f} total length)"
    )


def _compute_watersheds_stage(ctx: RunContext) -> None:
    """Compute stream orders and watershed (HUC) groups from the hydro graph."""
    hydro_graph = ctx.artifacts["hydro_graph"]
    method = ctx.settings.stream_method
    level = ctx.settings.huc_level

    stream_orders = assign_stream_order(hydro_graph, method)
    max_order = max(stream_orders.values(), default=0)
    watersheds = group_segments_by_huc(hydro_graph, level)
    stats = watershed_stats(watersheds)

    ctx.artifacts["stream_orders"] = stream_orders
    ctx.artifacts["watersheds"] = watersheds
    ctx.artifacts["max_stream_order"] = max_order
    ctx.log(
        f"[bold]compute_watersheds[/bold] {method} order (max {max_order}) "
        f"for {len(stream_orders)} segments; {stats.num_watersheds} {level} "
        f"watershed(s) over {stats.num_segments} segments"
    )


def _assign_colors_stage(ctx: RunContext) -> None:
    """Assign flowline colors per the ``color_by`` art-direction mode (roadmap #23).

    ``watershed`` (default) assigns a deterministic, high-contrast palette color
    per HUC group; ``single`` paints every flowline ``single_color``;
    ``elevation`` (hypsometric tint) requires per-segment elevation the 2D
    pipeline does not carry, so it fails fast with an actionable message.
    """
    hydro_graph = ctx.artifacts["hydro_graph"]
    watersheds = ctx.artifacts["watersheds"]
    color_by = ctx.settings.color_by

    if color_by == "elevation":
        raise ConfigError(
            "color_by=elevation needs per-segment ground elevation, which the "
            "2D pipeline does not load. Use tools/render_state_mono.py (or the "
            "DEM subsystem) for the hypsometric tint, or choose color_by "
            "watershed/single."
        )

    all_segments = {
        segment_id
        for segment_ids in watersheds.values()
        for segment_id in segment_ids
    }
    if color_by == "single":
        single = ctx.settings.single_color
        watershed_colors = {code: single for code in watersheds}
        segment_colors = {segment_id: single for segment_id in all_segments}
        detail = f"single color {single}"
    else:  # watershed (default)
        watershed_colors = assign_colors(hydro_graph, watersheds, ctx.settings.palette)
        segment_colors = {
            segment_id: watershed_colors[code]
            for code, segment_ids in watersheds.items()
            for segment_id in segment_ids
        }
        detail = (
            f"{len(set(watershed_colors.values()))} distinct "
            f"{ctx.settings.palette} color(s)"
        )

    ctx.artifacts["watershed_colors"] = watershed_colors
    ctx.artifacts["segment_colors"] = segment_colors
    ctx.artifacts["palette"] = ctx.settings.palette
    ctx.log(
        f"[bold]assign_colors[/bold] colored {len(watershed_colors)} watershed(s) "
        f"({detail}) over {len(segment_colors)} segments"
    )


def _resolve_stroke_widths(ctx: RunContext) -> dict[int, float] | None:
    """Resolve per-segment stroke widths for the ``width_by`` mode (roadmap #23).

    ``uniform`` (default) returns ``None`` so every stroke inherits the base
    ``line_width`` — byte-identical to a pre-#23 render. ``flow`` scales width
    with the channel's flow; the 2D pipeline's available flow proxy is the
    computed stream order (PRD §17 width scaling), mapped onto
    ``[width_min, width_max]`` and shaped by ``width_gamma``. True EROM-discharge
    scaling remains a ``tools/`` capability.
    """
    if ctx.settings.width_by != "flow":
        return None
    stream_orders = ctx.artifacts.get("stream_orders")
    if not stream_orders:
        return None
    return scaled_widths(
        stream_orders,
        width_min=ctx.settings.width_min,
        width_max=ctx.settings.width_max,
        gamma=ctx.settings.width_gamma,
    )


def _generate_svg_stage(ctx: RunContext) -> None:
    """Render the colored network into a layered SVG document (in memory)."""
    hydro_graph = ctx.artifacts["hydro_graph"]
    segment_colors = ctx.artifacts["segment_colors"]
    watersheds = ctx.artifacts["watersheds"]

    geometries = {
        data["segment_id"]: data["geometry"]
        for _, _, data in hydro_graph.digraph.edges(data=True)
    }

    waterbody_items = _select_waterbody_outlines(ctx)

    stroke_widths = _resolve_stroke_widths(ctx)

    wb = ctx.settings.waterbodies
    svg = render_svg(
        geometries,
        segment_colors,
        watersheds,
        background=ctx.settings.background,
        line_width=ctx.settings.line_width,
        stroke_widths=stroke_widths,
        glow=ctx.settings.glow,
        glow_mode=ctx.settings.glow_mode,
        glow_radius=ctx.settings.glow_radius,
        waterbodies=waterbody_items or None,
        waterbody_color=wb.color,
        waterbody_stroke_width=wb.stroke_width,
        waterbody_order=wb.render_order,
    )
    ctx.artifacts["svg"] = svg

    groups = sum(
        1 for code, ids in watersheds.items() if any(sid in geometries for sid in ids)
    )
    ctx.log(
        f"[bold]generate_svg[/bold] rendered {len(geometries)} path(s) in "
        f"{groups} watershed layer(s), {len(waterbody_items)} waterbody outline(s); "
        f"{len(svg)} bytes"
    )


def _select_waterbody_outlines(ctx: RunContext) -> list[tuple]:
    """Classify + select loaded waterbody layers into render-ready outline items.

    Returns a list of ``(feature_id, geometry, wb_class)`` tuples for the
    selected features, stashing the full :class:`WaterbodySelection` report in
    ``artifacts["waterbody_selection"]``. Returns ``[]`` when the feature is
    disabled or no waterbody layers were loaded, leaving the render river-only.
    """
    wb = ctx.settings.waterbodies
    wb_layers = ctx.artifacts.get("waterbody_layers")
    if not wb.enabled or not wb_layers:
        return []

    features = [feat for layer in wb_layers for feat in classify_layer(layer)]
    policy = WaterbodySelectionPolicy(
        min_inland_area_m2=wb.min_inland_area_m2,
        min_coastal_area_m2=wb.min_coastal_area_m2,
        coastal_mode=wb.coastal_mode,
    )
    selection = process_waterbodies(
        features,
        boundary=ctx.artifacts.get("region_boundary"),
        policy=policy,
        target_crs=ctx.settings.projection,
    )
    ctx.artifacts["waterbody_selection"] = selection

    items: list[tuple] = []
    for index, feat in enumerate(selection.selected):
        feature_id = feat.source_id or f"wb{index}"
        items.append((feature_id, feat.geometry, feat.wb_class))
    return items


def _optimize_svg_stage(ctx: RunContext) -> None:
    """Run the generated SVG through the injected optimizer (SVGO)."""
    svg = ctx.artifacts["svg"]
    optimized = ctx.optimizer.optimize(svg)
    ctx.artifacts["optimized_svg"] = optimized
    ctx.log(
        f"[bold]optimize_svg[/bold] {len(svg)} -> {len(optimized)} bytes"
    )


def _export_stage(ctx: RunContext) -> None:
    """Write the optimized SVG to disk and export the requested formats."""
    svg = ctx.artifacts["optimized_svg"]
    stem = "-".join(region.lower() for region in ctx.settings.regions)
    export_paths: dict[str, Path] = {}
    for fmt in sorted(ctx.settings.outputs):
        dest = ctx.output_dir / f"{stem}.{fmt}"
        written = ctx.exporter.export(svg, dest, fmt, png_size=ctx.settings.png_size)
        if written is not None:
            export_paths[fmt] = written

    digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    ctx.artifacts["export_paths"] = export_paths
    ctx.artifacts["svg_sha256"] = digest
    written_fmts = ", ".join(sorted(export_paths)) or "none"
    ctx.log(
        f"[bold]export[/bold] wrote {len(export_paths)} file(s) to "
        f"{ctx.output_dir} ({written_fmts}); svg sha256 {digest[:12]}"
    )


_STAGE_FUNCS: dict[str, Callable[[RunContext], None]] = {
    "download": _download_stage,
    "extract": _extract_stage,
    "validate": _validate_stage,
    "repair_geometries": _repair_stage,
    "reproject": _reproject_stage,
    "clip_to_region": _clip_stage,
    "build_graph": _build_graph_stage,
    "compute_watersheds": _compute_watersheds_stage,
    "assign_colors": _assign_colors_stage,
    "generate_svg": _generate_svg_stage,
    "optimize_svg": _optimize_svg_stage,
    "export": _export_stage,
}

#: Stage order per PRD section 8. Implemented stages use their real function;
#: the rest are stubs until their roadmap item lands.
PIPELINE_STAGES: tuple[Stage, ...] = tuple(
    Stage(name=name, run=_STAGE_FUNCS.get(name, _stub(name)))
    for name in (
        "download",
        "extract",
        "validate",
        "repair_geometries",
        "reproject",
        "clip_to_region",
        "build_graph",
        "compute_watersheds",
        "assign_colors",
        "generate_svg",
        "optimize_svg",
        "export",
    )
)


class Pipeline:
    """Runs the ordered pipeline stages against a :class:`Settings`."""

    def __init__(
        self,
        stages: tuple[Stage, ...] = PIPELINE_STAGES,
        console: Console | None = None,
        cache_dir: str | Path = "cache",
        datasets_dir: str | Path = "datasets",
        output_dir: str | Path = "output",
        downloader: DownloaderLike | None = None,
        loader: LayerLoader | None = None,
        optimizer: SvgOptimizer | None = None,
        exporter: Exporter | None = None,
    ) -> None:
        self._stages = stages
        self._console = console or Console()
        self._cache_dir = Path(cache_dir)
        self._datasets_dir = Path(datasets_dir)
        self._output_dir = Path(output_dir)
        self._downloader = downloader
        self._loader = loader
        self._optimizer = optimizer
        self._exporter = exporter

    @property
    def stage_names(self) -> tuple[str, ...]:
        """Names of the stages in execution order."""
        return tuple(stage.name for stage in self._stages)

    def run(self, settings: Settings) -> RunContext:
        """Execute every stage in order, returning the populated context."""
        context = RunContext(
            settings=settings,
            console=self._console,
            cache_dir=self._cache_dir,
            datasets_dir=self._datasets_dir,
            output_dir=self._output_dir,
            downloader=self._downloader or Downloader(UrllibFetcher()),
            loader=self._loader or PyogrioLayerLoader(),
            optimizer=self._optimizer or SvgoOptimizer(),
            exporter=self._exporter or FileExporter(),
        )
        for stage in self._stages:
            stage.run(context)
        return context
