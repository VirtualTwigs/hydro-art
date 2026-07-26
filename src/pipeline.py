"""Pipeline skeleton.

Defines the ordered stages of the GIS -> SVG pipeline (PRD section 8). The
``download`` and ``extract`` stages are implemented (dataset acquisition and
extraction); the remaining stages are no-op stubs replaced by later roadmap
items. Every stage receives a :class:`RunContext` by dependency injection and
shares results through ``context.artifacts``; there is no global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from src.cache import Cache, DownloaderLike, ensure_cached, extract_all
from src.config import Settings
from src.datasets import resolve_required_files
from src.download import Downloader, UrllibFetcher

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
        artifacts: Mutable bag of results passed between stages.
    """

    settings: Settings
    console: Console
    cache_dir: Path
    datasets_dir: Path
    downloader: DownloaderLike
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


_STAGE_FUNCS: dict[str, Callable[[RunContext], None]] = {
    "download": _download_stage,
    "extract": _extract_stage,
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
    ) -> None:
        self._stages = stages
        self._console = console or Console()
        self._cache_dir = Path(cache_dir)
        self._datasets_dir = Path(datasets_dir)
        self._downloader = downloader

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
        )
        for stage in self._stages:
            stage.run(context)
        return context
