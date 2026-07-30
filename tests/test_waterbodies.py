"""Tests for waterbody source classification (Item W1, Task Group 1).

Classification is by NHD source FType/FCode with name as secondary evidence,
never by display name alone. All tests run offline against hand-built
attribute dicts / :class:`~src.loading.Layer` objects.
"""

from shapely.geometry import Polygon

from src.loading import Layer
from src.waterbodies import (
    WATERBODY_CLASSES,
    WATERBODY_POLICY_VERSION,
    WaterbodyFeature,
    classify_layer,
    classify_waterbody,
)


def _classify(attributes, **kw):
    kw.setdefault("source_layer", "NHDWaterbody")
    kw.setdefault("dataset_id", "nhdplus_hr")
    kw.setdefault("huc4", "1709")
    return classify_waterbody(attributes, **kw)


def test_classify_lakepond_by_ftype():
    feat = _classify({"FType": 390, "FCode": 39004, "GNIS_Name": "Waldo Lake",
                      "Permanent_Identifier": "abc123"})
    assert isinstance(feat, WaterbodyFeature)
    assert feat.wb_class == "lake"
    assert feat.ftype == 390
    assert feat.fcode == 39004
    assert feat.name == "Waldo Lake"
    assert feat.source_id == "abc123"


def test_classify_reservoir_and_estuary_by_ftype():
    reservoir = _classify({"FType": 436, "FCode": 43600})
    estuary = _classify({"FType": 493})
    assert reservoir.wb_class == "reservoir"
    # Estuary is coastal water, not an inland lake.
    assert estuary.wb_class == "coastal"


def test_bayinlet_name_refines_bay_vs_inlet():
    bay = _classify({"FType": 312, "GNIS_Name": "Coos Bay"}, source_layer="NHDArea")
    inlet = _classify({"FType": 312, "GNIS_Name": "Hood Canal Inlet"}, source_layer="NHDArea")
    unnamed = _classify({"FType": 312}, source_layer="NHDArea")
    assert bay.wb_class == "bay"
    assert inlet.wb_class == "inlet"
    # Name is only secondary evidence; FType alone still classifies as bay.
    assert unnamed.wb_class == "bay"


def test_sea_ocean_excluded_under_conservative_coast_policy():
    feat = _classify({"FType": 445, "GNIS_Name": "Pacific Ocean"})
    assert feat.wb_class == "excluded"
    assert "445" in feat.inclusion_reason


def test_missing_ftype_is_excluded_with_qa_flag():
    feat = _classify({"GNIS_Name": "Mystery Lake"})
    assert feat.wb_class == "excluded"
    assert "missing_ftype" in feat.qa_flags
    assert feat.ftype is None


def test_classify_layer_preserves_source_and_iterates_features():
    poly_a = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    poly_b = Polygon([(2, 2), (2, 3), (3, 3), (3, 2)])
    layer = Layer(
        name="NHDWaterbody",
        dataset_id="nhdplus_hr",
        huc4="1709",
        geometries=(poly_a, poly_b),
        crs="EPSG:4269",
        attributes=(
            {"FType": 390, "Permanent_Identifier": "lake-1"},
            {"FType": 436, "Permanent_Identifier": "res-2"},
        ),
    )
    feats = classify_layer(layer)
    assert [f.source_id for f in feats] == ["lake-1", "res-2"]
    assert [f.wb_class for f in feats] == ["lake", "reservoir"]
    assert all(f.source_crs == "EPSG:4269" for f in feats)
    assert feats[0].geometry is poly_a


def test_policy_version_and_class_vocabulary_are_stable():
    assert isinstance(WATERBODY_POLICY_VERSION, str) and WATERBODY_POLICY_VERSION
    for expected in ("lake", "pond", "reservoir", "bay", "inlet", "coastal", "excluded"):
        assert expected in WATERBODY_CLASSES
