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
    "FLOWLINE_ATTRIBUTE_FIELDS",
    "HYDRO_LAYER_ALLOWLIST",
    "LINE_ATTRIBUTE_FIELDS",
    "LINE_LAYER_ALLOWLIST",
    "POINT_ATTRIBUTE_FIELDS",
    "POINT_LAYER_ALLOWLIST",
    "WATERBODY_ATTRIBUTE_FIELDS",
    "WATERBODY_LAYER_ALLOWLIST",
    "GeometryError",
    "Layer",
    "LayerLoader",
    "PyogrioLayerLoader",
    "discover_layers",
    "discover_line_layers",
    "discover_point_layers",
    "discover_waterbody_layers",
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

#: Areal-water polygon layers (Item W1). Kept separate from
#: :data:`HYDRO_LAYER_ALLOWLIST` so waterbody polygons never leak into the
#: flowline/graph load path; classification lives in :mod:`src.waterbodies`.
WATERBODY_LAYER_ALLOWLIST: tuple[str, ...] = (
    "NHDWaterbody",
    "NHDArea",
)

#: Source attribute columns needed to classify waterbodies by type/code and to
#: retain provenance (name + stable source id). Loaded case-insensitively.
WATERBODY_ATTRIBUTE_FIELDS: tuple[str, ...] = (
    "FType",
    "FCode",
    "GNIS_Name",
    "Permanent_Identifier",
    "ReachCode",
    "AreaSqKm",
)

#: NHDPoint natural-feature layer (Epoch 15, Item 61). Kept separate from the
#: flowline and waterbody allowlists so point features never leak into the
#: flowline/graph or polygon load paths; classification lives in
#: :mod:`src.point_features`.
POINT_LAYER_ALLOWLIST: tuple[str, ...] = ("NHDPoint",)

#: Source attribute columns needed to classify point features by type/code and
#: retain provenance. No ``AreaSqKm`` — points have no area. Case-insensitive.
POINT_ATTRIBUTE_FIELDS: tuple[str, ...] = (
    "FType",
    "FCode",
    "GNIS_Name",
    "Permanent_Identifier",
    "ReachCode",
)

#: NHDLine engineered-water structure layer (Epoch 16, Item 65). Kept separate
#: from the flowline, waterbody, and point allowlists so line structures never
#: leak into the flowline/graph, polygon, or point-feature load paths;
#: classification lives in :mod:`src.hydro_structures`.
LINE_LAYER_ALLOWLIST: tuple[str, ...] = ("NHDLine",)

#: Source attribute columns needed to classify line structures by type/code and
#: retain provenance. No ``AreaSqKm`` — lines have no area. Case-insensitive.
LINE_ATTRIBUTE_FIELDS: tuple[str, ...] = (
    "FType",
    "FCode",
    "GNIS_Name",
    "Permanent_Identifier",
    "ReachCode",
)

#: NHDFlowline attribute columns needed for channel-type classification
#: (Item #66). Minimal set — only ``FType`` and ``FCode`` — because flowline
#: attributes are used solely for classification, not provenance.
FLOWLINE_ATTRIBUTE_FIELDS: tuple[str, ...] = (
    "FType",
    "FCode",
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


def discover_waterbody_layers(layer_names: list[str]) -> list[str]:
    """Filter available layer names to the areal-water polygon layers.

    Convenience wrapper over :func:`discover_layers` using
    :data:`WATERBODY_LAYER_ALLOWLIST`, so waterbody discovery is explicit and
    independent of the flowline/WBD load path.
    """
    return discover_layers(layer_names, WATERBODY_LAYER_ALLOWLIST)


def discover_point_layers(layer_names: list[str]) -> list[str]:
    """Filter available layer names to the NHDPoint natural-feature layer.

    Convenience wrapper over :func:`discover_layers` using
    :data:`POINT_LAYER_ALLOWLIST`, so point discovery is explicit and
    independent of the flowline/WBD and waterbody load paths.
    """
    return discover_layers(layer_names, POINT_LAYER_ALLOWLIST)


def discover_line_layers(layer_names: list[str]) -> list[str]:
    """Filter available layer names to the NHDLine structure layer.

    Convenience wrapper over :func:`discover_layers` using
    :data:`LINE_LAYER_ALLOWLIST`, so line-structure discovery is explicit and
    independent of the flowline/WBD, waterbody, and point-feature load paths.
    """
    return discover_layers(layer_names, LINE_LAYER_ALLOWLIST)


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

    def load_layers(
        self,
        dataset_dir: Path,
        dataset_id: str,
        huc4: str,
        *,
        include_attributes: bool = False,
    ) -> list[Layer]:
        """Load flowline/WBD vector layers.

        Parameters:
            dataset_dir: Extracted dataset directory containing a ``.gdb``.
            dataset_id: Dataset identifier (e.g. ``"nhdplus_hr"``).
            huc4: HUC4 region code.
            include_attributes: When ``True``, read
                :data:`FLOWLINE_ATTRIBUTE_FIELDS` from each flowline frame and
                populate :attr:`Layer.attributes` as a parallel tuple of dicts.
                Default ``False`` preserves the existing behavior (no
                attributes).
        """
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
            attrs: tuple[dict, ...] | None = None
            if include_attributes:
                wanted = {
                    field.lower(): field
                    for field in FLOWLINE_ATTRIBUTE_FIELDS
                }
                present = {
                    col: wanted[col.lower()]
                    for col in frame.columns
                    if col.lower() in wanted
                }
                attrs = tuple(
                    {
                        canonical: row[col]
                        for col, canonical in present.items()
                    }
                    for _, row in frame.iterrows()
                )
            layers.append(
                Layer(
                    name=name,
                    dataset_id=dataset_id,
                    huc4=huc4,
                    geometries=tuple(frame.geometry.values),
                    crs=(
                        str(frame.crs) if frame.crs is not None else None
                    ),
                    attributes=attrs,
                )
            )
        return layers

    def load_waterbody_layers(
        self, dataset_dir: Path, dataset_id: str, huc4: str
    ) -> list[Layer]:  # pragma: no cover - requires GDAL + real data
        """Load areal-water polygon layers with classification attributes.

        Unlike :meth:`load_layers`, this discovers only
        :data:`WATERBODY_LAYER_ALLOWLIST` layers and preserves the per-feature
        source attributes (:data:`WATERBODY_ATTRIBUTE_FIELDS`) needed to
        classify features by type/code in :mod:`src.waterbodies`.
        """
        try:
            import geopandas as gpd
            from pyogrio import list_layers
        except ImportError as exc:
            raise GeometryError(
                "geopandas/pyogrio are required to load GIS data; install the "
                "GIS dependencies from requirements.txt."
            ) from exc

        source = self._find_source(dataset_dir)
        if source is None:
            warnings.warn(
                f"No .gdb/.shp source found under {dataset_dir}; skipping "
                f"waterbodies for {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        available = [str(row[0]) for row in list_layers(source)]
        selected = discover_waterbody_layers(available)
        if not selected:
            warnings.warn(
                f"No known waterbody layers in {source} "
                f"(saw {available}); skipping {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        wanted = {field.lower(): field for field in WATERBODY_ATTRIBUTE_FIELDS}
        layers: list[Layer] = []
        for name in selected:
            frame = gpd.read_file(source, layer=name)
            present = {
                col: wanted[col.lower()]
                for col in frame.columns
                if col.lower() in wanted
            }
            attributes = tuple(
                {canonical: row[col] for col, canonical in present.items()}
                for _, row in frame.iterrows()
            )
            layers.append(
                Layer(
                    name=name,
                    dataset_id=dataset_id,
                    huc4=huc4,
                    geometries=tuple(frame.geometry.values),
                    crs=str(frame.crs) if frame.crs is not None else None,
                    attributes=attributes,
                )
            )
        return layers

    def load_point_features(
        self, dataset_dir: Path, dataset_id: str, huc4: str
    ) -> list[Layer]:  # pragma: no cover - requires GDAL + real data
        """Load NHDPoint natural-feature layers with classification attributes.

        Unlike :meth:`load_layers`, this discovers only
        :data:`POINT_LAYER_ALLOWLIST` layers and preserves the per-feature
        source attributes (:data:`POINT_ATTRIBUTE_FIELDS`) needed to classify
        features by type/code in :mod:`src.point_features`. Independent of the
        waterbody load path so point features never leak into it.
        """
        try:
            import geopandas as gpd
            from pyogrio import list_layers
        except ImportError as exc:
            raise GeometryError(
                "geopandas/pyogrio are required to load GIS data; install the "
                "GIS dependencies from requirements.txt."
            ) from exc

        source = self._find_source(dataset_dir)
        if source is None:
            warnings.warn(
                f"No .gdb/.shp source found under {dataset_dir}; skipping "
                f"point features for {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        available = [str(row[0]) for row in list_layers(source)]
        selected = discover_point_layers(available)
        if not selected:
            warnings.warn(
                f"No known point layers in {source} "
                f"(saw {available}); skipping {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        wanted = {field.lower(): field for field in POINT_ATTRIBUTE_FIELDS}
        layers: list[Layer] = []
        for name in selected:
            frame = gpd.read_file(source, layer=name)
            present = {
                col: wanted[col.lower()]
                for col in frame.columns
                if col.lower() in wanted
            }
            attributes = tuple(
                {canonical: row[col] for col, canonical in present.items()}
                for _, row in frame.iterrows()
            )
            layers.append(
                Layer(
                    name=name,
                    dataset_id=dataset_id,
                    huc4=huc4,
                    geometries=tuple(frame.geometry.values),
                    crs=str(frame.crs) if frame.crs is not None else None,
                    attributes=attributes,
                )
            )
        return layers

    def load_line_features(
        self, dataset_dir: Path, dataset_id: str, huc4: str
    ) -> list[Layer]:  # pragma: no cover - requires GDAL + real data
        """Load NHDLine engineered-water structure layers with attributes.

        Unlike :meth:`load_layers`, this discovers only
        :data:`LINE_LAYER_ALLOWLIST` layers and preserves the per-feature source
        attributes (:data:`LINE_ATTRIBUTE_FIELDS`) needed to classify features by
        type/code in :mod:`src.hydro_structures`. Independent of the point and
        waterbody load paths so line structures never leak into them.
        """
        try:
            import geopandas as gpd
            from pyogrio import list_layers
        except ImportError as exc:
            raise GeometryError(
                "geopandas/pyogrio are required to load GIS data; install the "
                "GIS dependencies from requirements.txt."
            ) from exc

        source = self._find_source(dataset_dir)
        if source is None:
            warnings.warn(
                f"No .gdb/.shp source found under {dataset_dir}; skipping "
                f"line features for {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        available = [str(row[0]) for row in list_layers(source)]
        selected = discover_line_layers(available)
        if not selected:
            warnings.warn(
                f"No known line layers in {source} "
                f"(saw {available}); skipping {dataset_id}/{huc4}.",
                stacklevel=2,
            )
            return []

        wanted = {field.lower(): field for field in LINE_ATTRIBUTE_FIELDS}
        layers: list[Layer] = []
        for name in selected:
            frame = gpd.read_file(source, layer=name)
            present = {
                col: wanted[col.lower()]
                for col in frame.columns
                if col.lower() in wanted
            }
            attributes = tuple(
                {canonical: row[col] for col, canonical in present.items()}
                for _, row in frame.iterrows()
            )
            layers.append(
                Layer(
                    name=name,
                    dataset_id=dataset_id,
                    huc4=huc4,
                    geometries=tuple(frame.geometry.values),
                    crs=str(frame.crs) if frame.crs is not None else None,
                    attributes=attributes,
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
