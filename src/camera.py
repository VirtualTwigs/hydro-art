"""Animation camera paths (roadmap #22, experience-mode slice).

Turns a sequence of :class:`~src.scene.CameraPreset` keyframes into smooth camera
motion — a tuple of :class:`CameraPose` samples — by linearly interpolating
position, target, and field of view, with normalized-lerp of the up vector. Paths
may be *open* (start at the first keyframe, end exactly on the last) or *looping*
(seamlessly wrapping the last keyframe back to the first).

Part of the parallel elevation/terrain/3D subsystem: pure, deterministic, and
offline (imports only :mod:`math` + :class:`~src.scene.CameraPreset`). It carries
no browser/runtime state and is **not** wired into ``PIPELINE_STAGES`` — a later
web-delivery pass consumes these poses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from src.scene import CameraPreset

__all__ = [
    "CameraPathError",
    "CameraPose",
    "interpolate_camera",
    "camera_path",
]

Vec3 = tuple[float, float, float]


class CameraPathError(ValueError):
    """Raised for invalid camera-path inputs (bad ``t``, keyframes, or up)."""


@dataclass(frozen=True)
class CameraPose:
    """A single interpolated camera viewpoint along a path.

    Like :class:`~src.scene.CameraPreset` but without a name: it is one sampled
    frame of motion rather than a named viewpoint. ``up`` is always unit-length.
    """

    position: Vec3
    target: Vec3
    up: Vec3
    fov_deg: float


def interpolate_camera(a: CameraPreset, b: CameraPreset, t: float) -> CameraPose:
    """Interpolate between two camera presets at parameter ``t`` in ``[0, 1]``.

    Position, target, and ``fov_deg`` are linearly interpolated; the up vector is
    normalized-lerped (interpolate the unit endpoints, then renormalize) so the
    result stays unit-length. ``t == 0`` reproduces ``a`` (with a normalized up),
    ``t == 1`` reproduces ``b``.
    """
    if not 0.0 <= t <= 1.0:
        raise CameraPathError(f"t must be in [0, 1], got {t!r}.")
    return CameraPose(
        position=_lerp3(a.position, b.position, t),
        target=_lerp3(a.target, b.target, t),
        up=_nlerp_up(a.up, b.up, t),
        fov_deg=_lerp(a.fov_deg, b.fov_deg, t),
    )


def camera_path(
    keyframes: Sequence[CameraPreset],
    *,
    steps_per_segment: int,
    loop: bool = False,
) -> tuple[CameraPose, ...]:
    """Interpolate a sequence of keyframe presets into a smooth camera path.

    Each consecutive keyframe pair is a *segment* sampled at ``steps_per_segment``
    evenly spaced parameters ``i / steps_per_segment`` for ``i`` in
    ``[0, steps_per_segment)`` — the segment's start is included, its end excluded,
    so shared keyframes are never duplicated at segment joins.

    ``loop=False`` (open): visits ``keyframes[0] … keyframes[-1]`` and appends a
    closing pose on the final keyframe, so the path ends exactly there — length
    ``(n - 1) * steps_per_segment + 1``.

    ``loop=True``: adds a wrap segment from the last keyframe back to the first and
    omits the closing pose, giving a seamless cycle of length
    ``n * steps_per_segment``.
    """
    if len(keyframes) < 2:
        raise CameraPathError("camera_path needs at least 2 keyframes.")
    if steps_per_segment < 1:
        raise CameraPathError("steps_per_segment must be >= 1.")

    segments = list(zip(keyframes[:-1], keyframes[1:]))
    if loop:
        segments.append((keyframes[-1], keyframes[0]))

    poses: list[CameraPose] = []
    for start, end in segments:
        for i in range(steps_per_segment):
            poses.append(interpolate_camera(start, end, i / steps_per_segment))

    if not loop:
        poses.append(interpolate_camera(keyframes[-1], keyframes[-1], 0.0))

    return tuple(poses)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp3(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))


def _normalize(v: Vec3) -> Vec3:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length == 0.0:
        raise CameraPathError("up vector must be non-zero.")
    return (v[0] / length, v[1] / length, v[2] / length)


def _nlerp_up(a: Vec3, b: Vec3, t: float) -> Vec3:
    """Normalized lerp of two up vectors, renormalized to unit length."""
    return _normalize(_lerp3(_normalize(a), _normalize(b), t))
