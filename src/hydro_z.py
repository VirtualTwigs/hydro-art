"""River elevation attribution & QA (Item 15, Epoch 3 Phase 3.2).

Attaches ground elevation sampled from a normalized DEM to river flowlines,
while keeping the source Z immutable and auditable:

- :func:`attribute_line` densifies a flowline (item 14) and samples every vertex,
  producing an :class:`ElevatedLine` that carries the source-derived Z per vertex,
  the *original* 2D geometry path (preserved verbatim), the DEM identifier, the
  interpolation method, and a nodata count.
- :func:`profile_qa` inspects the downstream elevation profile and reports
  implausible **inversions** (Z rising in the downstream direction) — it flags,
  never silently alters.
- :func:`repair_monotonic` produces an explicitly opt-in, **render-only**
  monotonic (non-increasing downstream) water surface, governed by
  :class:`RepairPolicy`. It returns a new surface; the source Z on the
  :class:`ElevatedLine` is never mutated.
- :func:`render_z` is the display transform ``source_z * exaggeration + lift``;
  exaggeration and river lift are display-only and never overwrite source Z.

Vertices are oriented downstream (first -> last), matching the directed graph's
edge orientation, so "downstream" is simply vertex order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.terrain import Coord, TerrainSampler

__all__ = [
    "ElevatedVertex",
    "ElevatedLine",
    "ProfileQA",
    "RepairPolicy",
    "attribute_line",
    "profile_qa",
    "repair_monotonic",
    "render_z",
]


@dataclass(frozen=True)
class ElevatedVertex:
    """A densified vertex with its source-derived ground elevation.

    Attributes:
        x: Projected x (EPSG:5070 meters).
        y: Projected y (EPSG:5070 meters).
        z: Source-derived ground elevation in meters, or ``None`` at nodata /
            outside coverage. This is immutable source Z — never a repaired or
            exaggerated value.
    """

    x: float
    y: float
    z: float | None


@dataclass(frozen=True)
class ElevatedLine:
    """A flowline attributed with source elevation at every densified vertex.

    Attributes:
        segment_id: The originating river segment id (from the graph).
        vertices: Ordered, densified :class:`ElevatedVertex`s (downstream order).
        geometry_2d: The original, undensified 2D path, preserved verbatim.
        dem_id: Identifier of the DEM the elevations were sampled from.
        interpolation: Sampling method used (e.g. ``"bilinear"``).
    """

    segment_id: int
    vertices: tuple[ElevatedVertex, ...]
    geometry_2d: tuple[Coord, ...]
    dem_id: str
    interpolation: str = "bilinear"

    @property
    def nodata_count(self) -> int:
        return sum(1 for v in self.vertices if v.z is None)


@dataclass(frozen=True)
class ProfileQA:
    """Downstream elevation-profile diagnostics for an :class:`ElevatedLine`.

    Attributes:
        n_vertices: Total vertices inspected.
        n_nodata: Vertices with no elevation (nodata / uncovered).
        inversion_indices: Vertex indices where Z rises above the previous
            valid downstream vertex by more than the tolerance (an inversion).
        max_inversion_m: Largest such rise in meters (0.0 if none).
    """

    n_vertices: int
    n_nodata: int
    inversion_indices: tuple[int, ...]
    max_inversion_m: float


@dataclass(frozen=True)
class RepairPolicy:
    """Policy for the opt-in, render-only monotonic water-surface repair.

    Attributes:
        enabled: When ``False`` (default), no repair is applied and the source
            surface is returned unchanged.
        tolerance_m: A downstream rise up to this many meters is tolerated
            before being clamped.
    """

    enabled: bool = False
    tolerance_m: float = 0.0


def attribute_line(
    coords: Sequence[Coord],
    sampler: TerrainSampler,
    *,
    spacing: float,
    segment_id: int,
    dem_id: str,
    interpolation: str = "bilinear",
) -> ElevatedLine:
    """Densify ``coords`` and attach sampled source elevation to each vertex.

    The original 2D path is preserved in ``geometry_2d``; the elevated vertices
    are the densified path so no DEM cell between vertices is skipped.
    """
    sampled = sampler.sample_line(coords, spacing)
    vertices = tuple(
        ElevatedVertex(p.x, p.y, p.sample.value_m) for p in sampled.points
    )
    return ElevatedLine(
        segment_id=segment_id,
        vertices=vertices,
        geometry_2d=tuple((float(x), float(y)) for x, y in coords),
        dem_id=dem_id,
        interpolation=interpolation,
    )


def profile_qa(line: ElevatedLine, tolerance_m: float = 0.0) -> ProfileQA:
    """Report nodata and downstream inversions in ``line``'s elevation profile.

    An inversion is a vertex whose Z exceeds the most recent valid upstream
    (earlier) vertex by more than ``tolerance_m``. Nodata vertices are skipped
    for the comparison (they neither cause nor mask an inversion).
    """
    inversions: list[int] = []
    max_rise = 0.0
    prev_z: float | None = None
    for i, v in enumerate(line.vertices):
        if v.z is None:
            continue
        if prev_z is not None and v.z > prev_z + tolerance_m:
            inversions.append(i)
            max_rise = max(max_rise, v.z - prev_z)
        prev_z = v.z
    return ProfileQA(
        n_vertices=len(line.vertices),
        n_nodata=line.nodata_count,
        inversion_indices=tuple(inversions),
        max_inversion_m=max_rise,
    )


def repair_monotonic(
    line: ElevatedLine, policy: RepairPolicy
) -> tuple[float | None, ...]:
    """Return a render-only, non-increasing-downstream water surface.

    When ``policy.enabled`` is ``False`` the source Z is returned unchanged.
    Otherwise each valid vertex is clamped to at most the previous valid
    surface value (allowing a ``policy.tolerance_m`` rise), so the surface never
    flows uphill. Nodata vertices are preserved as ``None`` gaps and carry the
    last valid surface forward. The source Z on ``line`` is never mutated.
    """
    source = tuple(v.z for v in line.vertices)
    if not policy.enabled:
        return source

    out: list[float | None] = []
    prev: float | None = None
    for z in source:
        if z is None:
            out.append(None)
            continue
        if prev is not None and z > prev + policy.tolerance_m:
            z = prev
        out.append(z)
        prev = z
    return tuple(out)


def render_z(
    source_z: float | None,
    *,
    vertical_exaggeration: float,
    river_lift: float = 0.0,
) -> float | None:
    """Display transform: ``source_z * vertical_exaggeration + river_lift``.

    Returns ``None`` when ``source_z`` is ``None`` (nodata). This never mutates
    stored source Z; it computes a display value on demand.
    """
    if source_z is None:
        return None
    return source_z * vertical_exaggeration + river_lift
