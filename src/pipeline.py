"""Pipeline skeleton.

Defines the ordered stages of the GIS -> SVG pipeline (PRD section 8) as
no-op stubs for this foundational feature. Each stage receives the validated
:class:`~src.config.Settings` by dependency injection and, for now, only logs
that it ran. Later roadmap items replace individual stubs with real
implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from rich.console import Console

from src.config import Settings

__all__ = ["Stage", "PIPELINE_STAGES", "Pipeline"]


@dataclass(frozen=True)
class Stage:
    """A single named pipeline stage.

    Attributes:
        name: Human-readable stage name (matches PRD section 8 ordering).
        run: Callable invoked with the run's :class:`Settings`.
    """

    name: str
    run: Callable[[Settings, Console], None]


def _stub(name: str) -> Callable[[Settings, Console], None]:
    """Build a no-op stage function that logs its own name."""

    def _run(settings: Settings, console: Console) -> None:
        console.log(f"[dim]stage[/dim] {name} [yellow](stub)[/yellow]")

    return _run


#: Stage order per PRD section 8. Replace stubs as roadmap items land.
PIPELINE_STAGES: tuple[Stage, ...] = tuple(
    Stage(name=name, run=_stub(name))
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
    ) -> None:
        self._stages = stages
        self._console = console or Console()

    @property
    def stage_names(self) -> tuple[str, ...]:
        """Names of the stages in execution order."""
        return tuple(stage.name for stage in self._stages)

    def run(self, settings: Settings) -> None:
        """Execute every stage in order, injecting ``settings``."""
        for stage in self._stages:
            stage.run(settings, self._console)
