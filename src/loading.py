"""Hydrography layer loading behind an injectable seam.

Reading vector layers from an extracted ``.gdb``/shapefile requires GDAL, so
the concrete :class:`PyogrioLayerLoader` lazily imports geopandas/pyogrio and
is the only place GIS I/O happens. Tests inject a fake :class:`LayerLoader`
that yields in-memory :class:`Layer` objects, so the load path is exercised
offline without GDAL or real multi-GB datasets.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.datasets import AcquisitionError

__all__ = [
    "GeometryError",
    "Layer",
    "LayerLoader",
    "PyogrioLayerLoader",
    "HYDRO_LAYER_ALLOWLIST",
    "discover_layers",
]


class GeometryError(AcquisitionError):
    """Raised when a hydrography layer cannot be loaded or repaired."""


#: Vector layer names we care about across the supported datasets. NHDPlus HR
#: ships ``NHDFlowline`` (the render target); WBD ships HUC boundary layers.
HYDRO_LAYER_ALLOWLIST: tuple[str, ...] = (
    "NHDFlowline",
    "NHDFlowline_NonNetwork",
    "WBDHU4",
    "WBDHU8",
    "WBDHU12",
)


@dataclass(frozen=True)
class Layer:
    """An in-memory hydrography layer.

    Attributes:
        name: The source layer name (e.g. ``"NHDFlowline"``).
        dataset_id: The dataset the layer came from (e.g. ``"nhdplus_hr"``).
        huc4: The HUC4 region code the layer covers.
        geometries: The layer's shapely geometries.
        crs: The layer's coordinate reference system (e.g. ``"EPSG:4269"``),
            or ``None`` if unknown.
        attributes: Optional per-geometry attribute dicts, parallel to
            ``geometries``.
    """

    name: str
    dataset_id: str
    huc4: str
    geometries: tuple[Any, ...] = ()
    crs: str | None = None
    attributes: tuple[dict, ...] | None = None


def discover_layers(layer_names: list[str], allowlist: tuple[str, ...] = HYDRO_LAYER_ALLOWLIST) -> list[str]:
    """Filter available layer names to those in the allowlist (case-insensitive)."""
    wanted = {name.lower() for name in allowlist}
    return [name for name in layer_names if name.lower() in wanted]


@runtime_checkable
class LayerLoader(Protocol):
    """Anything that can load hydrography layers from an extracted dataset dir."""

    def load_layers(self, dataset_dir: Path, dataset_id: str, huc4: str) -> list[Layer]:
        ...


@dataclass
class PyogrioLayerLoader:
    """Real loader that reads vector layers via geopandas/pyogrio.

    GIS libraries are imported lazily inside :meth:`load_layers` so importing
    this module (and the whole pipeline) never requires GDAL to be present.
    """

    allowlist: tuple[str, ...] = HYDRO_LAYER_ALLOWLIST

    def load_layers(self, dataset_dir: Path, dataset_id: str, huc4: str) -> list[Layer]:
        try:
            import geopandas as gpd
            from pyogrio import list_layers
        except ImportError as exc:  # pragma: no cover - env-specific
            raise GeometryError(
                "geopandas/pyogrio are required to load GIS data; install the "
                "GIS dependencies from requirements.txt."
            ) from exc

        source = self._find_source(dataset_dir)
        if source is None:
            warnings.warn(
                f"No .gdb/.shp source found under {dataset_dir}; skipping "
                f"{dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        available = [str(row[0]) for row in list_layers(source)]
        selected = discover_layers(available, self.allowlist)
        if not selected:
            warnings.warn(
                f"No known hydrography layers in {source} "
                f"(saw {available}); skipping {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        layers: list[Layer] = []
        for name in selected:
            frame = gpd.read_file(source, layer=name)
            layers.append(
                Layer(
                    name=name,
                    dataset_id=dataset_id,
                    huc4=huc4,
                    geometries=tuple(frame.geometry.values),
                    crs=str(frame.crs) if frame.crs is not None else None,
                )
            )
        return layers

    @staticmethod
    def _find_source(dataset_dir: Path) -> Path | None:
        """Return the first ``.gdb`` directory or ``.shp`` file under the dir."""
        dataset_dir = Path(dataset_dir)
        for gdb in sorted(dataset_dir.rglob("*.gdb")):
            return gdb
        for shp in sorted(dataset_dir.rglob("*.shp")):
            return shp
        return None
