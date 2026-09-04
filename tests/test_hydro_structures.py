"""Tests for engineered-water structure classification (Epoch 16, Item 65).

Classification is by NHD source FType/FCode (a versioned policy table); a feature
whose FType is missing or unknown is ``excluded`` with a QA flag, never guessed.
All tests run offline against hand-built attribute dicts / :class:`Layer`
objects. FType codes are the real values confirmed against a live GDB (HUC4 1807)
in planning/group0-findings.md: dam/weir 343, canal/ditch 336, spillway 455,
water intake/outflow 485, gaging station 367, gate 369; lock chamber 398 uses the
standard NHD code (UNCONFIRMED — absent from 1807).
"""

from shapely.geometry import LineString, Point

from src.areal_features import AREAL_FTYPE_CLASS
from src.hydro_structures import (
    HYDRO_STRUCTURE_CLASSES,
    HYDRO_STRUCTURE_FTYPE_CLASS,
    HYDRO_STRUCTURE_FTYPE_LABELS,
    HYDRO_STRUCTURE_POLICY_VERSION,
    HydroStructure,
    classify_hydro_structure,
    classify_hydro_structure_layer,
)
from src.point_features import POINT_FTYPE_CLASS
from src.waterbodies import FTYPE_CLASS as WATERBODY_FTYPE_CLASS


def _classify(attributes, **kw):
    kw.setdefault("source_layer", "NHDLine")
    kw.setdefault("dataset_id", "nhdplus_hr")
    kw.setdefault("huc4", "1807")
    return classify_hydro_structure(attributes, **kw)


def test_classify_each_in_scope_ftype():
    cases = {
        343: "dam_weir",
        369: "gate",
        398: "lock_chamber",
        367: "gaging_station",
        485: "water_intake_outflow",
        455: "spillway",
        336: "canal_ditch",
    }
    for ftype, expected in cases.items():
        feat = _classify({"FType": ftype, "FCode": ftype * 100})
        assert isinstance(feat, HydroStructure)
        assert feat.struct_class == expected
        assert feat.ftype == ftype


def test_missing_ftype_is_excluded_with_qa_flag():
    feat = _classify({"GNIS_Name": "Mystery Structure"})
    assert feat.struct_class == "excluded"
    assert "missing_ftype" in feat.qa_flags
    assert feat.ftype is None


def test_out_of_scope_ftypes_are_excluded():
    # 436 Reservoir stays a waterbody; 458 Spring is a natural point feature.
    reservoir = _classify({"FType": 436, "FCode": 43600})
    spring = _classify({"FType": 458, "FCode": 45800})
    assert reservoir.struct_class == "excluded"
    assert "436" in reservoir.inclusion_reason
    assert spring.struct_class == "excluded"
    # A known-but-unmapped code is not flagged as missing/unknown data.
    assert "missing_ftype" not in reservoir.qa_flags


def test_provenance_fields_populated():
    geom = LineString([(0, 0), (1, 1)])
    feat = _classify(
        {"FType": 343, "FCode": 34306, "GNIS_Name": "Big Dam",
         "Permanent_Identifier": "dam-1"},
        geometry=geom,
        source_crs="EPSG:4269",
    )
    assert feat.name == "Big Dam"
    assert feat.source_id == "dam-1"
    assert feat.geometry is geom
    assert feat.source_layer == "NHDLine"
    assert feat.dataset_id == "nhdplus_hr"
    assert feat.huc4 == "1807"
    assert feat.source_crs == "EPSG:4269"
    assert feat.fcode == 34306


def test_classify_layer_iterates_in_source_order():
    a = LineString([(0, 0), (1, 1)])
    b = Point(2, 3)
    from src.loading import Layer

    layer = Layer(
        name="NHDLine",
        dataset_id="nhdplus_hr",
        huc4="1807",
        geometries=(a, b),
        crs="EPSG:4269",
        attributes=(
            {"FType": 343, "Permanent_Identifier": "dam-1"},
            {"FType": 455, "Permanent_Identifier": "spill-2"},
        ),
    )
    feats = classify_hydro_structure_layer(layer)
    assert [f.source_id for f in feats] == ["dam-1", "spill-2"]
    assert [f.struct_class for f in feats] == ["dam_weir", "spillway"]
    assert feats[0].geometry is a
    assert all(f.source_crs == "EPSG:4269" for f in feats)


def test_policy_version_and_class_vocabulary_are_stable():
    assert isinstance(HYDRO_STRUCTURE_POLICY_VERSION, str)
    assert HYDRO_STRUCTURE_POLICY_VERSION
    for expected in (
        "dam_weir", "gate", "lock_chamber", "gaging_station",
        "water_intake_outflow", "spillway", "canal_ditch", "excluded",
    ):
        assert expected in HYDRO_STRUCTURE_CLASSES


def test_included_codes_disjoint_from_other_taxonomies():
    def included(table):
        return {ft for ft, cls in table.items() if cls != "excluded"}

    structure = included(HYDRO_STRUCTURE_FTYPE_CLASS)
    waterbody = included(WATERBODY_FTYPE_CLASS)
    point = included(POINT_FTYPE_CLASS)
    areal = included(AREAL_FTYPE_CLASS)

    assert structure & waterbody == set()
    assert structure & point == set()
    assert structure & areal == set()
    # 436 Reservoir is owned by waterbodies, never a structure.
    assert 436 not in structure
    assert 436 in waterbody


def test_same_ftype_classifies_alike_across_source_layers():
    # One FType code carries the same meaning on every source layer: 343 DamWeir
    # is a dam_weir whether it arrives as an NHDLine or an NHDPoint geometry.
    line = _classify({"FType": 343}, source_layer="NHDLine")
    point = _classify({"FType": 343}, source_layer="NHDPoint")
    assert line.struct_class == point.struct_class == "dam_weir"
    assert line.source_layer == "NHDLine"
    assert point.source_layer == "NHDPoint"


def test_labels_table_names_every_included_code():
    included = {ft for ft, cls in HYDRO_STRUCTURE_FTYPE_CLASS.items()
                if cls != "excluded"}
    missing = included - set(HYDRO_STRUCTURE_FTYPE_LABELS)
    assert missing == set(), f"included codes with no label: {sorted(missing)}"
