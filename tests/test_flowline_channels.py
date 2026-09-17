"""Tests for flowline channel classification (Item #66, Task Group 1)."""

from __future__ import annotations

import re

from src.flowline_channels import (
    DEFAULT_CHANNEL_DASHES,
    ENGINEERED_CLASSES,
    FLOWLINE_CHANNEL_CLASSES,
    FLOWLINE_CHANNEL_FTYPE_CLASS,
    FLOWLINE_CHANNEL_FTYPE_LABELS,
    FLOWLINE_CHANNEL_POLICY_VERSION,
    build_channel_dashes,
    classify_ftype,
)
from src.hydro_structures import HYDRO_STRUCTURE_FTYPE_CLASS


def test_classify_known_ftypes():
    """Each of the 6 known FTypes maps to the expected class."""
    assert classify_ftype(460) == "stream"
    assert classify_ftype(336) == "canal_ditch"
    assert classify_ftype(428) == "pipeline"
    assert classify_ftype(558) == "artificial_path"
    assert classify_ftype(334) == "connector"
    assert classify_ftype(566) == "coastline"


def test_classify_missing_ftype():
    """None, empty string, non-integer all fall back to 'stream'."""
    assert classify_ftype(None) == "stream"
    assert classify_ftype("") == "stream"
    assert classify_ftype("not_a_number") == "stream"


def test_classify_unknown_ftype():
    """Unrecognized integer FType falls back to 'stream'."""
    assert classify_ftype(9999) == "stream"
    assert classify_ftype(0) == "stream"


def test_engineered_classes_subset():
    """ENGINEERED_CLASSES is a strict subset of FLOWLINE_CHANNEL_CLASSES."""
    assert ENGINEERED_CLASSES < set(FLOWLINE_CHANNEL_CLASSES)


def test_build_channel_dashes_basic():
    """3 segments: stream/canal/pipeline. Only 2 get dashes."""
    edge_ftypes = {
        1: 460,   # stream -> no dash
        2: 336,   # canal_ditch -> dash
        3: 428,   # pipeline -> dash
    }
    result = build_channel_dashes(edge_ftypes)
    assert 1 not in result
    assert result[2] == DEFAULT_CHANNEL_DASHES["canal_ditch"]
    assert result[3] == DEFAULT_CHANNEL_DASHES["pipeline"]
    assert len(result) == 2


def test_build_channel_dashes_custom_override():
    """Custom dashes dict replaces the defaults."""
    edge_ftypes = {10: 336}
    custom = {"canal_ditch": "12,6"}
    result = build_channel_dashes(edge_ftypes, dashes=custom)
    assert result[10] == "12,6"


def test_build_channel_dashes_empty():
    """No engineered segments -> empty dict."""
    edge_ftypes = {1: 460, 2: 334, 3: 566}
    result = build_channel_dashes(edge_ftypes)
    assert result == {}


def test_policy_version_format():
    """Version matches YYYY-MM-DD.N pattern."""
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}\.\d+", FLOWLINE_CHANNEL_POLICY_VERSION
    )


def test_ftype_class_disjoint_from_structures():
    """Flowline-channel and hydro-structure FType keys share only 336.

    FType 336 (CanalDitch) intentionally appears in BOTH tables because
    the code carries the same meaning across NHDFlowline (classified here)
    and NHDArea/NHDLine (classified by hydro_structures). The taxonomies
    operate on different source layers, so no feature is double-classified.
    Any OTHER overlap would be a bug.
    """
    flowline_keys = set(FLOWLINE_CHANNEL_FTYPE_CLASS.keys())
    structure_keys = set(HYDRO_STRUCTURE_FTYPE_CLASS.keys())
    overlap = flowline_keys & structure_keys
    # 336 is the only expected shared code (see spec and module docstrings)
    assert overlap == {336}, (
        f"Unexpected FType overlap between flowline_channels and "
        f"hydro_structures: {overlap - {336}} (336 is expected)"
    )
