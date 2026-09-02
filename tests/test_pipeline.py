"""Unit tests for the pipeline orchestrator (roadmap #37).

`src/pipeline.py` was previously exercised only indirectly through the
``test_*_pipeline.py`` integration files. These tests cover its structural
contracts directly and offline: canonical stage order, the "no stubs remain"
invariant, ``_stub`` no-op behavior, ``Stage`` immutability, ``stage_names``, and
that ``Pipeline.run`` threads a single ``RunContext`` through the stages in order
sharing ``artifacts`` — using inert sentinel collaborators so no GDAL/network is
touched.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from src.config import build_settings
from src.pipeline import (
    PIPELINE_STAGES,
    Pipeline,
    RunContext,
    Stage,
    _STAGE_FUNCS,
    _resolve_stroke_widths,
    _stub,
)
from src.rendering import scaled_widths

CANONICAL_ORDER = (
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


def _quiet_console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False)


def _fake_context() -> RunContext:
    """A RunContext with inert sentinel collaborators (stages under test never
    invoke I/O), so nothing imports GDAL or hits the network."""
    return RunContext(
        settings=object(),  # type: ignore[arg-type]
        console=_quiet_console(),
        cache_dir="cache",  # type: ignore[arg-type]
        datasets_dir="datasets",  # type: ignore[arg-type]
        output_dir="output",  # type: ignore[arg-type]
        downloader=object(),  # type: ignore[arg-type]
        loader=object(),  # type: ignore[arg-type]
        optimizer=object(),  # type: ignore[arg-type]
        exporter=object(),  # type: ignore[arg-type]
    )


def _flow_context(settings, orders) -> RunContext:
    ctx = _fake_context()
    ctx.settings = settings
    ctx.artifacts["stream_orders"] = orders
    return ctx


def test_resolve_stroke_widths_respects_width_log():
    # roadmap #77: the newly-exposed `width_log` knob reaches scaled_widths.
    orders = {0: 1.0, 1: 2.0, 2: 4.0, 3: 7.0}
    log_settings = build_settings(
        {
            "region": ["Oregon"],
            "width_by": "flow",
            "width_log": True,
            "width_min": 0.5,
            "width_max": 3.0,
        }
    )
    lin_settings = build_settings(
        {
            "region": ["Oregon"],
            "width_by": "flow",
            "width_log": False,
            "width_min": 0.5,
            "width_max": 3.0,
        }
    )
    got_log = _resolve_stroke_widths(_flow_context(log_settings, orders))
    got_lin = _resolve_stroke_widths(_flow_context(lin_settings, orders))

    assert got_log == scaled_widths(
        orders, width_min=0.5, width_max=3.0, gamma=1.0, log=True
    )
    assert got_lin == scaled_widths(
        orders, width_min=0.5, width_max=3.0, gamma=1.0, log=False
    )
    # log vs linear normalization differ for this non-degenerate order set.
    assert got_log != got_lin


def test_resolve_stroke_widths_uniform_returns_none_regardless_of_log():
    settings = build_settings(
        {"region": ["Oregon"], "width_by": "uniform", "width_log": True}
    )
    ctx = _flow_context(settings, {0: 1.0, 1: 3.0})
    assert _resolve_stroke_widths(ctx) is None


def test_pipeline_stages_are_canonical_order():
    assert tuple(s.name for s in PIPELINE_STAGES) == CANONICAL_ORDER


def test_no_stubs_remain():
    """Every stage in PIPELINE_STAGES is wired to its real function, not a stub."""
    for stage in PIPELINE_STAGES:
        assert stage.name in _STAGE_FUNCS
        assert stage.run is _STAGE_FUNCS[stage.name]


def test_stub_is_noop_and_logs():
    ctx = _fake_context()
    ctx.artifacts["sentinel"] = 1
    _stub("phantom")(ctx)
    # A stub never mutates artifacts...
    assert ctx.artifacts == {"sentinel": 1}


def test_stub_labels_itself_as_stub():
    buffer = io.StringIO()
    ctx = _fake_context()
    ctx.console = Console(file=buffer, force_terminal=False)
    _stub("phantom")(ctx)
    assert "phantom" in buffer.getvalue()
    assert "stub" in buffer.getvalue()


def test_stage_is_frozen():
    stage = Stage(name="x", run=lambda ctx: None)
    with pytest.raises(Exception):  # FrozenInstanceError
        stage.name = "y"  # type: ignore[misc]


def test_pipeline_stage_names_reflect_injected_stages():
    stages = (
        Stage(name="a", run=lambda ctx: None),
        Stage(name="b", run=lambda ctx: None),
    )
    assert Pipeline(stages=stages).stage_names == ("a", "b")


def test_run_threads_single_context_in_order():
    """Two fake stages: the first writes an artifact the second reads, proving the
    stages share one RunContext and run in declaration order."""
    seen: list[str] = []

    def first(ctx: RunContext) -> None:
        seen.append("first")
        ctx.artifacts["token"] = "from-first"

    def second(ctx: RunContext) -> None:
        seen.append("second")
        # The second stage must see what the first wrote (same context).
        ctx.artifacts["echo"] = ctx.artifacts["token"]

    stages = (Stage(name="first", run=first), Stage(name="second", run=second))
    pipeline = Pipeline(
        stages=stages,
        console=_quiet_console(),
        downloader=object(),  # type: ignore[arg-type]
        loader=object(),  # type: ignore[arg-type]
        optimizer=object(),  # type: ignore[arg-type]
        exporter=object(),  # type: ignore[arg-type]
    )

    ctx = pipeline.run(settings=object())  # type: ignore[arg-type]

    assert seen == ["first", "second"]
    assert ctx.artifacts["token"] == "from-first"
    assert ctx.artifacts["echo"] == "from-first"


def test_run_returns_populated_context():
    def stage(ctx: RunContext) -> None:
        ctx.artifacts["ran"] = True

    pipeline = Pipeline(
        stages=(Stage(name="only", run=stage),),
        console=_quiet_console(),
        downloader=object(),  # type: ignore[arg-type]
        loader=object(),  # type: ignore[arg-type]
        optimizer=object(),  # type: ignore[arg-type]
        exporter=object(),  # type: ignore[arg-type]
    )
    ctx = pipeline.run(settings=object())  # type: ignore[arg-type]
    assert isinstance(ctx, RunContext)
    assert ctx.artifacts == {"ran": True}


def test_runcontext_log_delegates_to_console():
    buffer = io.StringIO()
    ctx = _fake_context()
    ctx.console = Console(file=buffer, force_terminal=False)
    ctx.log("hello-orchestrator")
    assert "hello-orchestrator" in buffer.getvalue()
