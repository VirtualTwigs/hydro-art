"""Tests for areal natural-feature classification (Epoch 15, Item 62).

Areal families come from the SAME ``NHDWaterbody`` layer as waterbodies but are
a COMPLEMENTARY taxonomy: SwampMarsh (466), Playa (361), and Ice Mass (378) are
mapped to ``excluded`` in :mod:`src.waterbodies`, and are the in-scope classes
here (wetland/playa/perennial_ice). Classification is by NHD source FType/FCode;
a feature whose FType is missing or unknown is ``excluded`` with a QA flag,
never guessed. FType codes are the real values confirmed against a live 1807 GDB
(see planning/group0-ftype-findings.md).
"""

from shapely.geometry import Polygon

from src.loading import Layer
from src.waterbodies import FTYPE_CLASS as WATERBODY_FTYPE_CLASS
from src.areal_features import (
    AREAL_CLASSES,
    AREAL_FTYPE_CLASS,
    AREAL_POLICY_VERSION,
    ArealFeature,
    classify_areal_feature,
    classify_areal_layer,
)


def _classify(attributes, **kw):
    kw.setdefault("source_layer", "NHDWaterbody")
    kw.setdefault("dataset_id", "nhdplus_hr")
    kw.setdefault("huc4", "1807")
    return classify_areal_feature(attributes, **kw)


def test_classify_wetland_playa_ice_by_ftype():
    wetland = _classify({"FType": 466, "FCode": 46600, "GNIS_Name": "Big Marsh"})
    playa = _classify({"FType": 361, "FCode": 36100})
    ice = _classify({"FType": 378, "FCode": 37800})
    assert isinstance(wetland, ArealFeature)
    assert wetland.ar_class == "wetland"
    assert wetland.name == "Big Marsh"
    assert playa.ar_class == "playa"
    assert ice.ar_class == "perennial_ice"


def test_missing_ftype_is_excluded_with_qa_flag():
    feat = _classify({"GNIS_Name": "Mystery Polygon"})
    assert feat.ar_class == "excluded"
    assert "missing_ftype" in feat.qa_flags
    assert feat.ftype is None


def test_open_water_ftype_is_excluded_here():
    # LakePond (390) is a waterbody class, not an areal natural feature.
    feat = _classify({"FType": 390, "FCode": 39000})
    assert feat.ar_class == "excluded"
    assert "390" in feat.inclusion_reason


def test_areal_taxonomy_is_complementary_to_waterbodies():
    # The three areal FTypes are explicitly excluded by the waterbody taxonomy,
    # so a feature is classified by exactly one taxonomy, never double-counted.
    for ftype in AREAL_FTYPE_CLASS:
        assert WATERBODY_FTYPE_CLASS.get(ftype) == "excluded"


def test_classify_areal_layer_preserves_source_and_iterates():
    poly_a = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    poly_b = Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    layer = Layer(
        name="NHDWaterbody",
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometries=(poly_a, poly_b),
        crs="EPSG:4269",
        attributes=(
            {"FType": 466, "Permanent_Identifier": "we-1"},
            {"FType": 361, "Permanent_Identifier": "pl-2"},
        ),
    )
    feats = classify_areal_layer(layer)
    assert [f.source_id for f in feats] == ["we-1", "pl-2"]
    assert [f.ar_class for f in feats] == ["wetland", "playa"]
    assert all(f.source_crs == "EPSG:4269" for f in feats)
    assert feats[0].geometry is poly_a


def test_policy_version_and_class_vocabulary_are_stable():
    assert isinstance(AREAL_POLICY_VERSION, str) and AREAL_POLICY_VERSION
    for expected in ("wetland", "playa", "perennial_ice", "excluded"):
        assert expected in AREAL_CLASSES
