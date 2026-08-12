"""Tests for web delivery of the print/experience output (roadmap #22 slice).

Pure, deterministic, offline. Serializes the two experience-mode products — a
hillshade ``RasterGrid`` (``src.hillshade``) and a camera path of ``CameraPose``
samples (``src.camera``) — into one stable, browser-loadable experience document,
mirroring how ``src.preview`` feeds ``web/3d.html``.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from src.camera import camera_path
from src.delivery import (
    DeliveryError,
    camera_track,
    experience_document,
    experience_json,
    hillshade_layer,
)
from src.hillshade import hillshade
from src.raster import GridTransform, RasterGrid
from src.scene import CameraPreset


def _tilted_dem(nodata_cell: bool = False):
    vals = np.array(
        [[0, 1, 2, 3], [1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]], dtype=float
    )
    nodata = None
    if nodata_cell:
        vals = vals.copy()
        vals[1, 1] = -9999.0
        nodata = -9999.0
    return RasterGrid(
        vals, GridTransform(500000.0, 5000000.0, 30.0, 30.0), "EPSG:5070", nodata
    )


def _cameras():
    a = CameraPreset("a", (0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 45.0)
    b = CameraPreset("b", (10.0, 0.0, 5.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 45.0)
    return camera_path([a, b], steps_per_segment=4)


# --- TG-W1: serializers ----------------------------------------------------

def test_hillshade_layer_shape_bounds_and_range() -> None:
    grid = hillshade(_tilted_dem())
    layer = hillshade_layer(grid)
    assert layer["width"] == grid.width
    assert layer["height"] == grid.height
    assert len(layer["shade"]) == grid.width * grid.height
    assert all(0.0 <= s <= 255.0 for s in layer["shade"])
    assert layer["bounds"] == {
        "min_x": grid.bounds[0],
        "min_y": grid.bounds[1],
        "max_x": grid.bounds[2],
        "max_y": grid.bounds[3],
    }
    assert layer["cell_size_m"] == pytest.approx(30.0)
    valid = [s for s in layer["shade"] if s is not None]
    assert layer["value_range"]["min"] == pytest.approx(min(valid))
    assert layer["value_range"]["max"] == pytest.approx(max(valid))


def test_hillshade_layer_propagates_nodata_as_none() -> None:
    grid = hillshade(_tilted_dem(nodata_cell=True))
    layer = hillshade_layer(grid)
    assert any(s is None for s in layer["shade"])  # sentinel surfaced as null
    # The void at (1,1) dilates over rows/cols 0-2; the far corner (3,3) stays valid.
    assert layer["shade"][-1] is not None


def test_camera_track_serializes_poses() -> None:
    track = camera_track(_cameras())
    assert len(track) == 5  # (2-1)*4 + 1
    first = track[0]
    assert first["position"] == [0.0, 0.0, 10.0]
    assert first["target"] == [0.0, 0.0, 0.0]
    assert first["up"] == [0.0, 0.0, 1.0]
    assert first["fov_deg"] == pytest.approx(45.0)


# --- TG-W2: document + json + validation -----------------------------------

def test_experience_document_structure() -> None:
    doc = experience_document(
        hillshade_grid=hillshade(_tilted_dem()), camera_poses=_cameras()
    )
    assert doc["crs"] == "EPSG:5070"
    assert "generator" in doc
    assert doc["hillshade"]["width"] == 4
    assert doc["camera"]["frame_count"] == 5
    assert len(doc["camera"]["track"]) == 5


def test_experience_json_roundtrips_with_null_nodata() -> None:
    doc = experience_document(
        hillshade_grid=hillshade(_tilted_dem(nodata_cell=True)),
        camera_poses=_cameras(),
    )
    text = experience_json(doc)
    parsed = json.loads(text)
    assert parsed["camera"]["frame_count"] == 5
    assert None in parsed["hillshade"]["shade"]  # JSON null survives round-trip


def test_experience_json_is_deterministic() -> None:
    grid = hillshade(_tilted_dem())
    cams = _cameras()
    a = experience_json(experience_document(hillshade_grid=grid, camera_poses=cams))
    b = experience_json(experience_document(hillshade_grid=grid, camera_poses=cams))
    assert a == b


def test_empty_inputs_raise() -> None:
    grid = hillshade(_tilted_dem())
    empty_grid = RasterGrid(
        np.empty((0, 0), dtype=float), GridTransform(0.0, 0.0, 1.0, 1.0), "EPSG:5070"
    )
    with pytest.raises(DeliveryError):
        hillshade_layer(empty_grid)
    with pytest.raises(DeliveryError):
        camera_track([])
    with pytest.raises(DeliveryError):
        experience_document(hillshade_grid=grid, camera_poses=[])
