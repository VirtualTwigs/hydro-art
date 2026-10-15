"""Offline tests for water-claim extraction and public-view filtering.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``).

Covers: one evidence source can support multiple reviewed claims; one claim
may cite multiple documents; only reviewed publishable_precise/generalized
claims enter the public view; generalized eligibility omits exact
coordinates; changing a source retrieval time does not rewrite a claim's
valid time.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_facility import (
    DISPLAY_ELIGIBILITIES,
    FacilityEvidence,
    WaterClaim,
    WaterFacilityError,
)
from src.water_claims import (
    ClaimExtractionError,
    extract_claims,
    generalize_claim,
    public_claims,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
_EARLIER = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_FACILITY_ID = uuid.uuid4()


def _make_evidence(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        facility_id=_FACILITY_ID,
        source_url="https://example.gov/doc/123",
        file_key="snapshots/tx/2026/doc123.pdf",
        row_locator="row:42",
        publisher="Texas CEQ",
        publication_date=_EARLIER,
        retrieval_date=_NOW,
        review_status="reviewed",
        content_checksum="sha256:abc123",
    )
    defaults.update(overrides)
    return FacilityEvidence(**defaults)


def _make_claim(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        facility_id=_FACILITY_ID,
        subject="water_use",
        predicate="withdraws",
        value=1500.0,
        unit="m3/day",
        measure_type="withdrawal",
        quantity_status="measured",
        display_eligibility="publishable_precise",
        confidence=0.9,
        valid_time_start=_EARLIER,
        valid_time_end=_NOW,
        system_time=_NOW,
        reviewer="analyst_a",
        review_time=_NOW,
        evidence_ids=(uuid.uuid4(),),
    )
    defaults.update(overrides)
    return WaterClaim(**defaults)


# ---------------------------------------------------------------------------
# 1. One evidence source can support multiple reviewed claims
# ---------------------------------------------------------------------------


def test_one_evidence_multiple_claims():
    """A single evidence document may back multiple claims."""
    ev = _make_evidence()
    claims = extract_claims(
        evidence=[ev],
        facility_id=_FACILITY_ID,
        subjects=[
            ("water_use", "withdraws", 1500.0, "m3/day", "withdrawal", "measured"),
            ("water_use", "discharges", 800.0, "m3/day", "discharged", "measured"),
        ],
    )
    assert len(claims) == 2
    # Both cite the same evidence
    for c in claims:
        assert ev.id in c.evidence_ids
        assert c.display_eligibility == "review_required"


# ---------------------------------------------------------------------------
# 2. One claim may cite multiple documents
# ---------------------------------------------------------------------------


def test_one_claim_multiple_documents():
    """A claim may cite multiple evidence documents."""
    ev1 = _make_evidence(id=uuid.uuid4())
    ev2 = _make_evidence(id=uuid.uuid4())
    claims = extract_claims(
        evidence=[ev1, ev2],
        facility_id=_FACILITY_ID,
        subjects=[
            ("water_use", "withdraws", 2000.0, "m3/day", "withdrawal", "reported"),
        ],
    )
    assert len(claims) == 1
    assert ev1.id in claims[0].evidence_ids
    assert ev2.id in claims[0].evidence_ids


# ---------------------------------------------------------------------------
# 3. Only reviewed publishable claims enter public view
# ---------------------------------------------------------------------------


def test_public_claims_filters_review_required():
    """review_required claims are not public."""
    c1 = _make_claim(display_eligibility="review_required")
    c2 = _make_claim(display_eligibility="publishable_precise")
    result = public_claims([c1, c2])
    assert len(result) == 1
    assert result[0].display_eligibility == "publishable_precise"


def test_public_claims_filters_internal_only():
    """internal_only claims are not public."""
    c = _make_claim(display_eligibility="internal_only")
    result = public_claims([c])
    assert len(result) == 0


def test_public_claims_filters_excluded():
    """excluded claims are not public."""
    c = _make_claim(display_eligibility="excluded")
    result = public_claims([c])
    assert len(result) == 0


def test_public_claims_allows_publishable_generalized():
    """publishable_generalized claims pass the public filter."""
    c = _make_claim(display_eligibility="publishable_generalized")
    result = public_claims([c])
    assert len(result) == 1


# ---------------------------------------------------------------------------
# 4. Generalized eligibility omits exact coordinates
# ---------------------------------------------------------------------------


def test_generalize_claim_strips_coordinates():
    """generalize_claim strips exact coordinate value from a claim."""
    c = _make_claim(
        display_eligibility="publishable_generalized",
        subject="location",
        predicate="located_at",
        value=47.123456,
        unit="degrees",
    )
    gc = generalize_claim(c)
    assert gc.value is None
    assert gc.display_eligibility == "publishable_generalized"
    # Other fields preserved
    assert gc.facility_id == c.facility_id
    assert gc.evidence_ids == c.evidence_ids


def test_generalize_claim_rejects_precise():
    """Cannot generalize a publishable_precise claim — must re-classify first."""
    c = _make_claim(display_eligibility="publishable_precise")
    with pytest.raises(ClaimExtractionError):
        generalize_claim(c)


# ---------------------------------------------------------------------------
# 5. Changing source retrieval time does not rewrite claim valid time
# ---------------------------------------------------------------------------


def test_retrieval_time_change_preserves_claim_valid_time():
    """A claim's valid_time is independent of source retrieval_date."""
    ev_old = _make_evidence(
        retrieval_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    ev_new = _make_evidence(
        id=ev_old.id,
        retrieval_date=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    claims_old = extract_claims(
        evidence=[ev_old],
        facility_id=_FACILITY_ID,
        subjects=[
            ("water_use", "withdraws", 100.0, "m3/day", "withdrawal", "measured"),
        ],
    )
    claims_new = extract_claims(
        evidence=[ev_new],
        facility_id=_FACILITY_ID,
        subjects=[
            ("water_use", "withdraws", 100.0, "m3/day", "withdrawal", "measured"),
        ],
    )
    # valid_time_start/end come from the evidence publication, not retrieval
    assert claims_old[0].valid_time_start == claims_new[0].valid_time_start
    assert claims_old[0].valid_time_end == claims_new[0].valid_time_end
