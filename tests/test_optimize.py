"""Unit tests for the SVGO optimizer seam (Item #9, TG3; gap-closure Epoch 20 #82)."""

import subprocess
import types

import pytest

from src import optimize as optimize_mod
from src.optimize import SvgOptimizer, SvgoOptimizer


def test_missing_svgo_returns_input_unchanged_with_warning():
    # A command that does not exist -> graceful fallback, never crashes.
    optimizer = SvgoOptimizer(command="hydro-no-such-svgo-binary")
    svg = "<svg><g/></svg>"
    with pytest.warns(UserWarning, match="not found"):
        assert optimizer.optimize(svg) == svg


def test_svgo_optimizer_satisfies_protocol():
    assert isinstance(SvgoOptimizer(), SvgOptimizer)


def test_svgo_present_but_failing_returns_input_with_warning(monkeypatch):
    # svgo present but exits non-zero -> CalledProcessError branch, unoptimized SVG back.
    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=3, cmd=args[0])

    monkeypatch.setattr(optimize_mod.subprocess, "run", boom)
    svg = "<svg><g/></svg>"
    with pytest.warns(UserWarning, match="optimization failed"):
        assert SvgoOptimizer().optimize(svg) == svg


def test_svgo_success_returns_optimized_stdout(monkeypatch):
    def ok(*args, **kwargs):
        return types.SimpleNamespace(stdout="<svg/>")

    monkeypatch.setattr(optimize_mod.subprocess, "run", ok)
    assert SvgoOptimizer().optimize("<svg><g/></svg>") == "<svg/>"


def test_svgo_success_empty_stdout_falls_back_to_input(monkeypatch):
    def empty(*args, **kwargs):
        return types.SimpleNamespace(stdout="")

    monkeypatch.setattr(optimize_mod.subprocess, "run", empty)
    svg = "<svg><g/></svg>"
    assert SvgoOptimizer().optimize(svg) == svg
