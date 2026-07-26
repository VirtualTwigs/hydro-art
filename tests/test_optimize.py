"""Unit tests for the SVGO optimizer seam (Item #9, TG3)."""

import pytest

from src.optimize import SvgOptimizer, SvgoOptimizer


def test_missing_svgo_returns_input_unchanged_with_warning():
    # A command that does not exist -> graceful fallback, never crashes.
    optimizer = SvgoOptimizer(command="hydro-no-such-svgo-binary")
    svg = "<svg><g/></svg>"
    with pytest.warns(UserWarning, match="not found"):
        assert optimizer.optimize(svg) == svg


def test_svgo_optimizer_satisfies_protocol():
    assert isinstance(SvgoOptimizer(), SvgOptimizer)
