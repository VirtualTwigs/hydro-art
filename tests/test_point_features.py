"""Tests for NHDPoint natural-feature classification (Epoch 15, Item 61).

Classification is by NHD source FType/FCode (a versioned policy table); a
feature whose FType is missing or unknown is ``excluded`` with a QA flag,
never guessed. All tests run offline against hand-built attribute dicts /
:class:`~src.loading.Layer` objects. FType codes are the real values confirmed
against a live GDB (see planning/group0-ftype-findings.md): spring 458,
waterfall 487, rapids 431, well 488, sink/rise 450.
"""

from shapely.geometry import Point

from src.loading import Layer
from src.point_features import (
    POINT_CLASSES,
    POINT_POLICY_VERSION,
    PointFeature,
    classify_point_feature,
    classify_point_layer,
)


def _classify(attributes, **kw):
    kw.setdefault("source_layer", "NHDPoint")
    kw.setdefault("dataset_id", "nhdplus_hr")
    kw.setdefault("huc4", "1807")
    return classify_point_feature(attributes, **kw)


def test_classify_spring_by_ftype():
    feat = _classify(
        {"FType": 458, "FCode": 45800, "GNIS_Name": "Cold Spring",
         "Permanent_Identifier": "sp-1"}
    )
    assert isinstance(feat, PointFeature)
    assert feat.pt_class == "spring"
    assert feat.ftype == 458
    assert feat.fcode == 45800
    assert feat.name == "Cold Spring"
    assert feat.source_id == "sp-1"


def test_classify_waterfall_and_rapids_by_ftype():
    waterfall = _classify({"FType": 487, "FCode": 48700})
    rapids = _classify({"FType": 431, "FCode": 43100})
    assert waterfall.pt_class == "waterfall"
    assert rapids.pt_class == "rapids"


def test_well_and_sinkhole_are_classified_but_excluded():
    # Present in the taxonomy (accounted for, named in the reason), but excluded
    # by default policy — never silently dropped, never guessed into an in-scope
    # class.
    well = _classify({"FType": 488, "FCode": 48800})
    sink = _classify({"FType": 450, "FCode": 45000})
    assert well.pt_class == "excluded"
    assert sink.pt_class == "excluded"
    assert "Well" in well.inclusion_reason
    assert "Sink" in sink.inclusion_reason
    # A known-but-excluded code is not flagged as missing/unknown data.
    assert "missing_ftype" not in well.qa_flags


def test_unknown_infrastructure_ftype_is_excluded():
    # Gaging Station (367) is Epoch-16 infrastructure, out of scope here.
    feat = _classify({"FType": 367, "FCode": 36700})
    assert feat.pt_class == "excluded"
    assert "367" in feat.inclusion_reason


def test_missing_ftype_is_excluded_with_qa_flag():
    feat = _classify({"GNIS_Name": "Mystery Point"})
    assert feat.pt_class == "excluded"
    assert "missing_ftype" in feat.qa_flags
    assert feat.ftype is None


def test_classify_point_layer_preserves_source_and_iterates():
    pt_a = Point(0, 0)
    pt_b = Point(2, 3)
    layer = Layer(
        name="NHDPoint",
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometries=(pt_a, pt_b),
        crs="EPSG:4269",
        attributes=(
            {"FType": 458, "Permanent_Identifier": "sp-1"},
            {"FType": 487, "Permanent_Identifier": "wf-2"},
        ),
    )
    feats = classify_point_layer(layer)
    assert [f.source_id for f in feats] == ["sp-1", "wf-2"]
    assert [f.pt_class for f in feats] == ["spring", "waterfall"]
    assert all(f.source_crs == "EPSG:4269" for f in feats)
    assert feats[0].geometry is pt_a


def test_policy_version_and_class_vocabulary_are_stable():
    assert isinstance(POINT_POLICY_VERSION, str) and POINT_POLICY_VERSION
    for expected in ("spring", "waterfall", "rapids", "excluded"):
        assert expected in POINT_CLASSES
