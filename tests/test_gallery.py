"""Tests for the curated marketing gallery + rights ledger (Epoch 22, #88-90).

Fully offline: ``src.gallery`` imports only stdlib + ``src.endpoints`` +
``src.fulfillment``. Every curated selection is validated through the endpoint Rights gate;
the ledger is deterministic and byte-identical. No datasets, GDAL, or network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.endpoints import ENDPOINTS, EndpointError, EndpointRequest
from src.fulfillment import ORDER_STYLES
from src.gallery import (
    GALLERY_MATRIX,
    GALLERY_SCHEMA,
    GallerySelection,
    gallery_ledger,
    selection_request,
)


def test_matrix_spans_regions_styles_endpoints():
    assert len(GALLERY_MATRIX) >= 6
    assert all(isinstance(s, GallerySelection) for s in GALLERY_MATRIX)
    ids = [s.item_id for s in GALLERY_MATRIX]
    assert len(ids) == len(set(ids))  # unique item_ids
    assert {s.region for s in GALLERY_MATRIX} >= {"Oregon", "Washington", "California", "Idaho", "CONUS"}
    assert {s.style for s in GALLERY_MATRIX} <= set(ORDER_STYLES)
    assert {s.style for s in GALLERY_MATRIX} == {"neon-basin", "elevation-tint"}
    assert {s.endpoint for s in GALLERY_MATRIX} == set(ENDPOINTS)
    assert all(s.rationale.strip() for s in GALLERY_MATRIX)


def test_every_selection_is_valid_and_sellable():
    for s in GALLERY_MATRIX:
        req = selection_request(s)
        assert isinstance(req, EndpointRequest)
        assert req.endpoint == s.endpoint
        # public-domain styles only -> never PRISM.
        assert not ORDER_STYLES[s.style].uses_prism


def test_ledger_skeleton_is_deterministic_and_byte_identical():
    a = gallery_ledger()
    b = gallery_ledger(list(reversed(GALLERY_MATRIX)))
    assert a["schema"] == GALLERY_SCHEMA
    assert a["attribution"]
    # one asset per selection, sorted by item_id, render-independent (null sha256).
    assert [x["item_id"] for x in a["assets"]] == sorted(s.item_id for s in GALLERY_MATRIX)
    assert all(x["sellable"] is True for x in a["assets"])
    for x in a["assets"]:
        assert x["deliverables"]
        assert all(d["sha256"] is None for d in x["deliverables"])
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_ledger_stamps_checksums_with_exact_coverage():
    skeleton = gallery_ledger()
    checksums = {
        x["item_id"]: {d["filename"]: "0" * 64 for d in x["deliverables"]}
        for x in skeleton["assets"]
    }
    stamped = gallery_ledger(checksums=checksums)
    for x in stamped["assets"]:
        assert all(d["sha256"] == "0" * 64 for d in x["deliverables"])


def test_ledger_rejects_incomplete_checksum_coverage():
    skeleton = gallery_ledger()
    first = skeleton["assets"][0]
    # drop one file from the first asset's coverage -> mismatch.
    bad = {
        x["item_id"]: {d["filename"]: "0" * 64 for d in x["deliverables"]}
        for x in skeleton["assets"]
    }
    bad[first["item_id"]].popitem()
    with pytest.raises(EndpointError):
        gallery_ledger(checksums=bad)


# --- CONUS hero entry (Item #111) -----------------------------------------

def test_conus_hero_in_gallery_matrix():
    """The CONUS hero entry is in the gallery matrix."""
    conus = [s for s in GALLERY_MATRIX if s.item_id == "conus-neon-hero"]
    assert len(conus) == 1
    entry = conus[0]
    assert entry.region == "CONUS"
    assert entry.county is None
    assert entry.style == "neon-basin"
    assert entry.endpoint == "digital_image"


def test_conus_selection_passes_rights_gate():
    """The CONUS gallery entry is valid and sellable (public domain)."""
    conus = next(s for s in GALLERY_MATRIX if s.item_id == "conus-neon-hero")
    req = selection_request(conus)
    assert isinstance(req, EndpointRequest)
    assert req.region == "CONUS"


def test_conus_in_ledger_with_null_county():
    """The gallery ledger includes the CONUS asset with county=null."""
    ledger = gallery_ledger()
    conus = next(a for a in ledger["assets"] if a["item_id"] == "conus-neon-hero")
    assert conus["county"] is None
    assert conus["sellable"] is True
    assert conus["deliverables"]


GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "gallery" / "ledger.json"


def test_ledger_matches_committed_golden():
    # render-independent skeleton; regenerate the golden if the curated matrix changes on purpose.
    recomputed = json.dumps(gallery_ledger(), indent=2, sort_keys=True) + "\n"
    assert recomputed == GOLDEN.read_text()
