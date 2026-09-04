"""Tests for the layer loading seam (Item #3, Task Group 1)."""

import warnings

from shapely.geometry import LineString, Point

from src.loading import (
    HYDRO_LAYER_ALLOWLIST,
    POINT_ATTRIBUTE_FIELDS,
    POINT_LAYER_ALLOWLIST,
    WATERBODY_LAYER_ALLOWLIST,
    Layer,
    LayerLoader,
    PyogrioLayerLoader,
    discover_layers,
    discover_point_layers,
    discover_waterbody_layers,
)


class FakeLoader:
    """In-memory loader used to exercise the load path offline."""

    def load_layers(self, dataset_dir, dataset_id, huc4):
        return [
            Layer(
                name="NHDFlowline",
                dataset_id=dataset_id,
                huc4=huc4,
                geometries=(LineString([(0, 0), (1, 1)]),),
            )
        ]


def test_discover_filters_to_known_layers():
    available = ["NHDFlowline", "ExternalCrosswalk", "wbdhu8", "NHDArea"]
    assert discover_layers(available) == ["NHDFlowline", "wbdhu8"]


def test_fake_loader_satisfies_protocol_and_yields_layer():
    loader = FakeLoader()
    assert isinstance(loader, LayerLoader)
    layers = loader.load_layers("/anything", "nhdplus_hr", "1707")
    assert len(layers) == 1
    layer = layers[0]
    assert layer.name == "NHDFlowline"
    assert layer.dataset_id == "nhdplus_hr"
    assert layer.huc4 == "1707"
    assert len(layer.geometries) == 1


def test_pyogrio_loader_warns_and_returns_empty_when_no_source(tmp_path):
    loader = PyogrioLayerLoader()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        layers = loader.load_layers(tmp_path, "nhdplus_hr", "1707")
    assert layers == []
    assert any("No .gdb/.shp source" in str(w.message) for w in caught)


def test_allowlist_includes_flowline_and_wbd():
    assert "NHDFlowline" in HYDRO_LAYER_ALLOWLIST
    assert any(name.startswith("WBDHU") for name in HYDRO_LAYER_ALLOWLIST)


def test_waterbody_allowlist_is_separate_from_flowline_discovery():
    # Waterbody polygon layers must not leak into the flowline load path.
    assert "NHDWaterbody" in WATERBODY_LAYER_ALLOWLIST
    assert "NHDArea" in WATERBODY_LAYER_ALLOWLIST
    assert "NHDWaterbody" not in HYDRO_LAYER_ALLOWLIST
    assert "NHDArea" not in HYDRO_LAYER_ALLOWLIST


def test_discover_waterbody_layers_filters_case_insensitively():
    available = ["NHDFlowline", "NHDWaterbody", "nhdarea", "WBDHU8"]
    assert discover_waterbody_layers(available) == ["NHDWaterbody", "nhdarea"]


class FakePointLoader:
    """In-memory loader exposing the point-feature seam without GDAL."""

    def load_point_features(self, dataset_dir, dataset_id, huc4):
        return [
            Layer(
                name="NHDPoint",
                dataset_id=dataset_id,
                huc4=huc4,
                geometries=(Point(0, 0), Point(1, 1)),
                crs="EPSG:4269",
                attributes=(
                    {"FType": 458, "Permanent_Identifier": "sp-1"},
                    {"FType": 487, "Permanent_Identifier": "wf-2"},
                ),
            )
        ]


def test_point_allowlist_is_separate_from_flowline_and_waterbody_paths():
    # NHDPoint features must not leak into the flowline/graph or waterbody loads.
    assert "NHDPoint" in POINT_LAYER_ALLOWLIST
    assert "NHDPoint" not in HYDRO_LAYER_ALLOWLIST
    assert "NHDPoint" not in WATERBODY_LAYER_ALLOWLIST


def test_point_attribute_fields_carry_provenance_but_not_area():
    # Points have no area; the field set carries id/name/code provenance only.
    assert "FType" in POINT_ATTRIBUTE_FIELDS
    assert "Permanent_Identifier" in POINT_ATTRIBUTE_FIELDS
    assert "AreaSqKm" not in POINT_ATTRIBUTE_FIELDS


def test_discover_point_layers_filters_case_insensitively():
    available = ["NHDFlowline", "nhdpoint", "NHDWaterbody", "NHDArea"]
    assert discover_point_layers(available) == ["nhdpoint"]


def test_fake_point_loader_seam_preserves_geometry_and_attributes():
    loader = FakePointLoader()
    layers = loader.load_point_features("/anything", "nhdplus_hr", "1807")
    assert len(layers) == 1
    layer = layers[0]
    assert layer.name == "NHDPoint"
    assert len(layer.geometries) == len(layer.attributes) == 2
    assert layer.attributes[0]["FType"] == 458


class FakeLineLoader:
    """In-memory loader exposing the line-structure seam without GDAL."""

    def load_line_features(self, dataset_dir, dataset_id, huc4):
        return [
            Layer(
                name="NHDLine",
                dataset_id=dataset_id,
                huc4=huc4,
                geometries=(LineString([(0, 0), (1, 1)]),
                            LineString([(2, 2), (3, 3)])),
                crs="EPSG:4269",
                attributes=(
                    {"FType": 343, "Permanent_Identifier": "dam-1"},
                    {"FType": 455, "Permanent_Identifier": "spill-2"},
                ),
            )
        ]


def test_line_allowlist_is_separate_from_other_paths():
    # NHDLine structures must not leak into the flowline/graph, waterbody, or
    # point-feature load paths.
    from src.loading import LINE_LAYER_ALLOWLIST

    assert "NHDLine" in LINE_LAYER_ALLOWLIST
    assert "NHDLine" not in HYDRO_LAYER_ALLOWLIST
    assert "NHDLine" not in WATERBODY_LAYER_ALLOWLIST
    assert "NHDLine" not in POINT_LAYER_ALLOWLIST


def test_line_attribute_fields_carry_provenance_but_not_area():
    from src.loading import LINE_ATTRIBUTE_FIELDS

    assert "FType" in LINE_ATTRIBUTE_FIELDS
    assert "Permanent_Identifier" in LINE_ATTRIBUTE_FIELDS
    assert "ReachCode" in LINE_ATTRIBUTE_FIELDS
    assert "AreaSqKm" not in LINE_ATTRIBUTE_FIELDS


def test_discover_line_layers_filters_case_insensitively():
    from src.loading import discover_line_layers

    available = ["NHDFlowline", "nhdline", "NHDWaterbody", "NHDArea", "NHDPoint"]
    assert discover_line_layers(available) == ["nhdline"]


def test_fake_line_loader_seam_preserves_geometry_and_attributes():
    loader = FakeLineLoader()
    layers = loader.load_line_features("/anything", "nhdplus_hr", "1807")
    assert len(layers) == 1
    layer = layers[0]
    assert layer.name == "NHDLine"
    assert len(layer.geometries) == len(layer.attributes) == 2
    assert layer.attributes[0]["FType"] == 343
    # The line seam does not overload the point/waterbody loaders.
    assert not hasattr(loader, "load_point_features")
    assert not hasattr(loader, "load_waterbody_layers")
