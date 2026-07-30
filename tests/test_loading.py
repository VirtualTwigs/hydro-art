"""Tests for the layer loading seam (Item #3, Task Group 1)."""

import warnings

from shapely.geometry import LineString

from src.loading import (
    HYDRO_LAYER_ALLOWLIST,
    WATERBODY_LAYER_ALLOWLIST,
    Layer,
    LayerLoader,
    PyogrioLayerLoader,
    discover_layers,
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
