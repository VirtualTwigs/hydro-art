"""Pipeline skeleton.

Defines the ordered stages of the GIS -> SVG pipeline (PRD section 8). The
``download`` and ``extract`` stages are implemented (dataset acquisition and
extraction); the remaining stages are no-op stubs replaced by later roadmap
items. Every stage receives a :class:`RunContext` by dependency injection and
shares results through ``context.artifacts``; there is no global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from src.cache import Cache, DownloaderLike, ensure_cached, extract_all
from src.config import Settings
from src.datasets import resolve_required_files
from src.clipping import clip_layers, region_boundary
from src.coloring import assign_colors
from src.download import Downloader, UrllibFetcher
from src.geometry import RepairStats, repair_layer
from src.graph import build_graph
from src.loading import LayerLoader, PyogrioLayerLoader
from src.ordering import assign_stream_order
from src.projection import reproject_layer
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
        downloader: Injected downloader used by the acquisition stage.
        loader: Injected layer loader used by the validate stage.
        artifacts: Mutable bag of results passed between stages.
    """

    settings: Settings
    console: Console
    cache_dir: Path
    datasets_dir: Path
    downloader: DownloaderLike
    loader: LayerLoader
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
    """Assign deterministic, high-contrast colors to each watershed."""
    hydro_graph = ctx.artifacts["hydro_graph"]
    watersheds = ctx.artifacts["watersheds"]
    palette = ctx.settings.palette

    watershed_colors = assign_colors(hydro_graph, watersheds, palette)
    segment_colors = {
        segment_id: watershed_colors[code]
        for code, segment_ids in watersheds.items()
        for segment_id in segment_ids
    }

    ctx.artifacts["watershed_colors"] = watershed_colors
    ctx.artifacts["segment_colors"] = segment_colors
    ctx.artifacts["palette"] = palette
    ctx.log(
        f"[bold]assign_colors[/bold] colored {len(watershed_colors)} watershed(s) "
        f"({len(set(watershed_colors.values()))} distinct {palette} color(s)) "
        f"over {len(segment_colors)} segments"
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
        downloader: DownloaderLike | None = None,
        loader: LayerLoader | None = None,
    ) -> None:
        self._stages = stages
        self._console = console or Console()
        self._cache_dir = Path(cache_dir)
        self._datasets_dir = Path(datasets_dir)
        self._downloader = downloader
        self._loader = loader

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
            downloader=self._downloader or Downloader(UrllibFetcher()),
            loader=self._loader or PyogrioLayerLoader(),
        )
        for stage in self._stages:
            stage.run(context)
        return context
