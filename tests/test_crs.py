"""Offline tests for the canonical internal-CRS constant (roadmap #34).

``src/crs.py`` is the single source of truth for the pipeline's internal
projection string; every module that needs it imports :data:`INTERNAL_CRS`
rather than repeating the ``"EPSG:5070"`` literal. These tests pin the value and
assert that each downstream default is wired to the shared constant, so a future
change to the internal CRS is a one-line edit that these tests would catch if a
module drifted back to a hard-coded literal.
"""

from __future__ import annotations

import inspect

from src.crs import INTERNAL_CRS


def test_internal_crs_is_conus_albers():
    assert INTERNAL_CRS == "EPSG:5070"


def test_raster_reexports_the_same_constant():
    from src import raster

    assert raster.INTERNAL_CRS is INTERNAL_CRS
    assert "INTERNAL_CRS" in raster.__all__


def test_config_defaults_use_the_constant():
    from src.config import DEFAULTS, SUPPORTED_PROJECTIONS

    assert DEFAULTS["projection"] == INTERNAL_CRS
    # The allowlist still enumerates several CRSes, but its internal entry is the
    # shared constant (first position).
    assert SUPPORTED_PROJECTIONS[0] == INTERNAL_CRS


def test_mesh_default_crs_uses_the_constant():
    from src.mesh import TerrainMesh

    assert TerrainMesh.__dataclass_fields__["crs"].default == INTERNAL_CRS


def test_waterbody_selection_default_target_crs_uses_the_constant():
    from src.waterbody_selection import process_waterbodies

    default = inspect.signature(process_waterbodies).parameters["target_crs"].default
    assert default == INTERNAL_CRS
