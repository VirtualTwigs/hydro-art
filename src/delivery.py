"""Web delivery of the print/experience output (roadmap #22, experience slice).

Packages the two experience-mode products into one stable, browser-loadable
document: the hillshade shaded-relief :class:`~src.raster.RasterGrid`
(``src.hillshade``) and a camera path of :class:`~src.camera.CameraPose` samples
(``src.camera``). The result is a plain dict serialized to deterministic JSON via
:func:`experience_json` and consumed by ``web/experience.html`` — mirroring how
:mod:`src.preview` feeds ``web/3d.html``.

Pure, deterministic, and offline: imports only stdlib (:mod:`json`) +
:class:`~src.raster.RasterGrid` + :class:`~src.camera.CameraPose` (numpy only via
the grid it reads). It carries no browser/runtime state and is **not** wired into
``PIPELINE_STAGES``; ``src/`` never imports ``web/``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from src.camera import CameraPose
from src.raster import RasterGrid

__all__ = [
    "GENERATOR",
    "DeliveryError",
    "camera_track",
    "experience_document",
    "experience_json",
    "hillshade_layer",
]

#: Identifies the asset producer in the serialized output.
GENERATOR = "hydro-art experience (item 22)"


class DeliveryError(ValueError):
    """Raised for empty inputs that cannot form an experience document."""


def hillshade_layer(grid: RasterGrid) -> dict[str, Any]:
    """Serialize a hillshade ``RasterGrid`` (0-255) as a browser-ready layer.

    Emits a row-major ``shade`` list (a cell equal to ``grid.nodata`` becomes
    ``None`` — shade is never invented), the geographic ``bounds`` and per-cell
    ``cell_size_m``, and a ``value_range`` computed over valid cells only (both
    ends ``None`` when the layer is entirely nodata).
    """
    if grid.height == 0 or grid.width == 0:
        raise DeliveryError("Cannot deliver an empty hillshade grid.")

    shade: list[float | None] = []
    valid: list[float] = []
    for r in range(grid.height):
        for c in range(grid.width):
            v = float(grid.values[r, c])
            if grid.nodata is not None and v == grid.nodata:
                shade.append(None)
            else:
                shade.append(v)
                valid.append(v)

    min_x, min_y, max_x, max_y = grid.bounds
    return {
        "width": grid.width,
        "height": grid.height,
        "cell_size_m": grid.transform.pixel_width,
        "bounds": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
        "value_range": {
            "min": min(valid) if valid else None,
            "max": max(valid) if valid else None,
        },
        "shade": shade,
    }


def camera_track(poses: Sequence[CameraPose]) -> list[dict[str, Any]]:
    """Serialize a camera path to a list of ``{position,target,up,fov_deg}`` dicts."""
    if not poses:
        raise DeliveryError("Cannot deliver an empty camera path.")
    return [
        {
            "position": list(p.position),
            "target": list(p.target),
            "up": list(p.up),
            "fov_deg": p.fov_deg,
        }
        for p in poses
    ]


def experience_document(
    *,
    hillshade_grid: RasterGrid,
    camera_poses: Sequence[CameraPose],
    crs: str | None = None,
    generator: str = GENERATOR,
) -> dict[str, Any]:
    """Combine a hillshade layer and a camera track into one experience document.

    ``crs`` defaults to the hillshade grid's CRS. The returned dict is plain data
    (no numpy) ready for :func:`experience_json`.
    """
    track = camera_track(camera_poses)
    return {
        "generator": generator,
        "crs": crs if crs is not None else hillshade_grid.crs,
        "hillshade": hillshade_layer(hillshade_grid),
        "camera": {"frame_count": len(track), "track": track},
    }


def experience_json(doc: Mapping[str, Any]) -> str:
    """Serialize an experience document to deterministic JSON."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))
