"""Canonical internal coordinate reference system for the project.

The whole pipeline (and the parallel elevation/terrain subsystem) works in a
single projected CRS so geometry, rasters, and area measurements share one
metric frame. That CRS is defined here, once, as :data:`INTERNAL_CRS` so no
module hard-codes the raw EPSG string. It is a plain stdlib-only string constant
(no GDAL/pyproj import), safe to import anywhere including the offline suite.

``EPSG:5070`` is NAD83 / Conus Albers, an equal-area projection in metres — the
PRD's internal CRS, chosen so planar area/length are meaningful nationwide.
"""

from __future__ import annotations

#: The project's internal horizontal CRS (per PRD / config). Every module that
#: needs the internal projection string imports this rather than repeating the
#: literal, so there is a single source of truth.
INTERNAL_CRS = "EPSG:5070"
