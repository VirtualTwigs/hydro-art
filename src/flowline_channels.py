"""NHDFlowline engineered-channel classification (Item #66).

Classifies NHDFlowline segments by their ``FType`` attribute into normalized
channel classes — ``stream``, ``canal_ditch``, ``pipeline``, ``artificial_path``,
``connector``, ``coastline`` — and maps engineered classes to SVG dash-array
strings for per-segment rendering.

This module operates on the **NHDFlowline** layer (the same segments already in
the graph/watershed/coloring pipeline). It is COMPLEMENTARY to
:mod:`src.hydro_structures`, which classifies the ``NHDLine``/``NHDPoint``/
``NHDArea`` occurrences of codes like 336 (CanalDitch). The two taxonomies
target different source layers, so their FType keys are disjoint by design.

Like the sibling classification modules, this performs no geometry math and
imports no GIS libraries — it consumes integer FType codes and produces strings,
so it runs fully offline without even shapely.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "DEFAULT_CHANNEL_DASHES",
    "ENGINEERED_CLASSES",
    "FLOWLINE_CHANNEL_CLASSES",
    "FLOWLINE_CHANNEL_FTYPE_CLASS",
    "FLOWLINE_CHANNEL_FTYPE_LABELS",
    "FLOWLINE_CHANNEL_POLICY_VERSION",
    "build_channel_dashes",
    "classify_ftype",
]

#: Bumped whenever the classification policy table changes.
FLOWLINE_CHANNEL_POLICY_VERSION = "2026-09-17.1"

#: The normalized channel-class vocabulary for NHDFlowline segments.
FLOWLINE_CHANNEL_CLASSES: tuple[str, ...] = (
    "stream",
    "canal_ditch",
    "pipeline",
    "artificial_path",
    "connector",
    "coastline",
)

#: NHD FType code -> normalized channel class. Segments whose FType is missing
#: or not in this table default to ``"stream"`` (conservative — render normally).
FLOWLINE_CHANNEL_FTYPE_CLASS: dict[int, str] = {
    460: "stream",           # StreamRiver
    336: "canal_ditch",      # CanalDitch
    428: "pipeline",         # Pipeline
    558: "artificial_path",  # ArtificialPath (e.g. through a reservoir)
    334: "connector",        # Connector (network topology)
    566: "coastline",        # Coastline
}

#: Human-readable FType labels for reports and diagnostics.
FLOWLINE_CHANNEL_FTYPE_LABELS: dict[int, str] = {
    460: "StreamRiver",
    336: "CanalDitch",
    428: "Pipeline",
    558: "ArtificialPath",
    334: "Connector",
    566: "Coastline",
}

#: Channel classes that receive distinct dash styling (engineered channels).
ENGINEERED_CLASSES: frozenset[str] = frozenset({
    "canal_ditch",
    "pipeline",
    "artificial_path",
})

#: Default SVG ``stroke-dasharray`` values per engineered class.
DEFAULT_CHANNEL_DASHES: dict[str, str] = {
    "canal_ditch": "8,4",
    "pipeline": "2,4",
    "artificial_path": "6,3,2,3",
}


def _as_int(value: Any) -> int | None:
    """Coerce a source FType to ``int``, or ``None`` on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def classify_ftype(ftype: int | str | None) -> str:
    """Return the normalized channel class for an NHDFlowline FType.

    Missing, empty-string, non-integer, or unrecognized FType values
    conservatively default to ``"stream"`` (render normally).
    """
    code = _as_int(ftype)
    if code is None:
        return "stream"
    return FLOWLINE_CHANNEL_FTYPE_CLASS.get(code, "stream")


def build_channel_dashes(
    edge_ftypes: Mapping[int, int | str | None],
    dashes: Mapping[str, str] | None = None,
) -> dict[int, str]:
    """Build a segment_id -> SVG dasharray mapping for engineered segments.

    Parameters:
        edge_ftypes: Maps ``segment_id`` to the raw NHD FType value for each
            edge in the graph.
        dashes: Optional per-class dash overrides. When ``None``, uses
            :data:`DEFAULT_CHANNEL_DASHES`.

    Returns:
        A dict mapping only the segment_ids whose FType classifies as an
        engineered channel to their SVG ``stroke-dasharray`` string. Segments
        classified as natural (stream, connector, coastline) are omitted.
    """
    dash_table = dashes if dashes is not None else DEFAULT_CHANNEL_DASHES
    result: dict[int, str] = {}
    for seg_id, ftype_val in edge_ftypes.items():
        cls = classify_ftype(ftype_val)
        if cls in ENGINEERED_CLASSES:
            dash = dash_table.get(cls)
            if dash is not None:
                result[seg_id] = dash
    return result
