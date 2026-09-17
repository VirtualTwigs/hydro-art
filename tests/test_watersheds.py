"""Tests for watershed (HUC) grouping (Item #6, Task Group 2)."""

import networkx as nx
import pytest

from src.config import DEFAULTS, ConfigError, build_settings
from src.watersheds import (
    HUC_LEVEL_DIGITS,
    group_segments_by_huc,
    watershed_stats,
)


def _graph(*edges):
    """Build a MultiDiGraph from (segment_id, huc4) tuples."""
    g = nx.MultiDiGraph()
    for i, (sid, huc4) in enumerate(edges):
        g.add_edge(i, i + 1, segment_id=sid, huc4=huc4, length=1.0)
    return g


def test_group_by_huc4_code():
    g = _graph((0, "1707"), (1, "1707"), (2, "1710"))
    groups = group_segments_by_huc(g, "HUC4")
    assert groups == {"1707": {0, 1}, "1710": {2}}


def test_huc2_truncates_to_two_digit_prefix():
    g = _graph((0, "1707"), (1, "1801"))
    groups = group_segments_by_huc(g, "HUC2")
    assert groups == {"17": {0}, "18": {1}}


def test_finer_than_available_degrades_to_huc4_with_warning():
    g = _graph((0, "1707"), (1, "1707"))
    with pytest.warns(UserWarning):
        groups = group_segments_by_huc(g, "HUC8")
    assert groups == {"1707": {0, 1}}  # degraded to full HUC4


def test_watershed_stats_counts():
    g = _graph((0, "1707"), (1, "1707"), (2, "1710"))
    stats = watershed_stats(group_segments_by_huc(g, "HUC4"))
    assert stats.num_watersheds == 2
    assert stats.num_segments == 3


def test_huc_level_validation_and_yaml_survives_unset_flag():
    with pytest.raises(ConfigError):
        build_settings({**DEFAULTS, "huc_level": "HUC99"})
    settings = build_settings({**DEFAULTS, "huc_level": "HUC8"})
    assert settings.huc_level == "HUC8"


def test_all_levels_mapped():
    assert HUC_LEVEL_DIGITS["HUC2"] == 2
    assert HUC_LEVEL_DIGITS["HUC12"] == 12
