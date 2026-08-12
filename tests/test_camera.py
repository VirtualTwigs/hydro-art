"""Tests for animation camera paths (roadmap #22, experience-mode slice).

Pure, deterministic, offline. Interpolates :class:`CameraPreset` viewpoints
(from ``src.scene``) into smooth camera motion (a tuple of :class:`CameraPose`),
supporting open and looping keyframe paths. No browser/runtime state.
"""

from __future__ import annotations

import math

import pytest

from src.camera import CameraPathError, CameraPose, camera_path, interpolate_camera
from src.scene import CameraPreset


def _preset(name, pos, target=(0.0, 0.0, 0.0), up=(0.0, 0.0, 1.0), fov=45.0):
    return CameraPreset(name, pos, target, up, fov)


# --- TG-C1: interpolation + open path -------------------------------------

def test_interpolate_endpoints_return_keyframe_poses() -> None:
    a = _preset("a", (0.0, 0.0, 10.0), fov=40.0)
    b = _preset("b", (10.0, 0.0, 2.0), fov=60.0)
    p0 = interpolate_camera(a, b, 0.0)
    p1 = interpolate_camera(a, b, 1.0)
    assert isinstance(p0, CameraPose)
    assert p0.position == pytest.approx(a.position)
    assert p0.fov_deg == pytest.approx(40.0)
    assert p1.position == pytest.approx(b.position)
    assert p1.fov_deg == pytest.approx(60.0)


def test_interpolate_midpoint_is_component_average() -> None:
    a = _preset("a", (0.0, 0.0, 0.0), target=(0.0, 0.0, 0.0), fov=40.0)
    b = _preset("b", (10.0, 4.0, 2.0), target=(2.0, 2.0, 2.0), fov=60.0)
    m = interpolate_camera(a, b, 0.5)
    assert m.position == pytest.approx((5.0, 2.0, 1.0))
    assert m.target == pytest.approx((1.0, 1.0, 1.0))
    assert m.fov_deg == pytest.approx(50.0)


def test_open_path_hits_first_and_last_keyframes() -> None:
    a = _preset("a", (0.0, 0.0, 10.0))
    b = _preset("b", (10.0, 0.0, 5.0))
    c = _preset("c", (10.0, 10.0, 2.0))
    path = camera_path([a, b, c], steps_per_segment=5, loop=False)
    # (n-1) segments * steps + a closing pose on the final keyframe.
    assert len(path) == (3 - 1) * 5 + 1
    assert path[0].position == pytest.approx(a.position)
    assert path[-1].position == pytest.approx(c.position)


def test_camera_path_is_deterministic() -> None:
    a = _preset("a", (0.0, 0.0, 10.0))
    b = _preset("b", (10.0, 0.0, 5.0))
    p1 = camera_path([a, b], steps_per_segment=7)
    p2 = camera_path([a, b], steps_per_segment=7)
    assert p1 == p2


# --- TG-C2: loop, validation, up-normalization ----------------------------

def test_loop_path_is_seamless_no_duplicate_keyframe() -> None:
    a = _preset("a", (0.0, 0.0, 10.0))
    b = _preset("b", (10.0, 0.0, 5.0))
    path = camera_path([a, b], steps_per_segment=4, loop=True)
    # n keyframes * steps, wrapping back toward the start with no closing dup.
    assert len(path) == 2 * 4
    assert path[0].position == pytest.approx(a.position)
    # The last sample is on the way back to a, not a itself.
    assert path[-1].position != pytest.approx(a.position)


def test_up_vectors_are_normalized() -> None:
    a = _preset("a", (0.0, 0.0, 10.0), up=(0.0, 0.0, 2.0))
    b = _preset("b", (10.0, 0.0, 5.0), up=(0.0, 4.0, 0.0))
    path = camera_path([a, b], steps_per_segment=6)
    for pose in path:
        length = math.sqrt(sum(component * component for component in pose.up))
        assert length == pytest.approx(1.0)


def test_invalid_arguments_raise() -> None:
    a = _preset("a", (0.0, 0.0, 10.0))
    b = _preset("b", (10.0, 0.0, 5.0))
    with pytest.raises(CameraPathError):
        camera_path([a], steps_per_segment=4)
    with pytest.raises(CameraPathError):
        camera_path([a, b], steps_per_segment=0)
    with pytest.raises(CameraPathError):
        interpolate_camera(a, b, 1.5)
    with pytest.raises(CameraPathError):
        interpolate_camera(_preset("z", (0.0, 0.0, 0.0), up=(0.0, 0.0, 0.0)), b, 0.0)
