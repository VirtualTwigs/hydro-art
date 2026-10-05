"""Offline tests for customer facility-request options.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``).

Covers: default request has no facility overlay; valid selections serialize
to an immutable manifest; invalid, unavailable, or restricted selections
yield an explicit exclusion; candidate data centers retain their candidate
label; a facility selection cannot change the base render recipe.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
_EARLIER = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _make_claim(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        facility_id=uuid.uuid4(),
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
# Import the module under test (deferred so test file is parseable first)
# ---------------------------------------------------------------------------

from src.facility_request import (
    FacilityExclusion,
    FacilityRequestError,
    FacilityRequestManifest,
    FacilitySelection,
    build_facility_manifest,
    review_gate,
)


# ---------------------------------------------------------------------------
# 1. Default image/report request has no facility component
# ---------------------------------------------------------------------------


def test_default_request_has_no_facility_component():
    """A None selection means the request has no facility overlay."""
    manifest = build_facility_manifest(
        selection=None,
        resolved=[],
        snapshot_versions={},
    )
    assert manifest is None


# ---------------------------------------------------------------------------
# 2. Valid optional selection serializes an immutable manifest
# ---------------------------------------------------------------------------


def test_valid_selection_produces_immutable_manifest():
    """A valid selection with resolved IDs produces a frozen manifest."""
    fid = uuid.uuid4()
    sel = FacilitySelection(
        product_surface="image",
        scope="state",
        facility_classes=("data_center",),
        named_search=None,
        treatment="visual_context",
    )
    snaps = {"SDWIS": "snap-2026-09-01", "FRS": "snap-2026-09-01"}
    claim = _make_claim(facility_id=fid, display_eligibility="publishable_precise")
    manifest = build_facility_manifest(
        selection=sel,
        resolved=[claim],
        snapshot_versions=snaps,
    )
    assert manifest is not None
    assert isinstance(manifest, FacilityRequestManifest)
    # Frozen
    with pytest.raises(AttributeError):
        manifest.reviewer = "someone_else"  # type: ignore[misc]
    # Snapshot versions pinned
    assert manifest.snapshot_versions == snaps
    # Resolved facility IDs captured
    assert fid in manifest.resolved_facility_ids


# ---------------------------------------------------------------------------
# 3. Unavailable/ambiguous/restricted produce customer-safe exclusion
# ---------------------------------------------------------------------------


def test_restricted_claim_excluded():
    """A claim with 'excluded' eligibility is filtered out with a reason."""
    claim = _make_claim(display_eligibility="excluded")
    approved, excluded = review_gate([claim])
    assert len(approved) == 0
    assert len(excluded) == 1
    assert isinstance(excluded[0], FacilityExclusion)
    assert excluded[0].facility_id == claim.facility_id
    assert "excluded" in excluded[0].reason.lower() or "restricted" in excluded[0].reason.lower()


def test_review_required_claim_excluded():
    """A claim still in 'review_required' cannot reach public output."""
    claim = _make_claim(display_eligibility="review_required")
    approved, excluded = review_gate([claim])
    assert len(approved) == 0
    assert len(excluded) == 1
    assert "review" in excluded[0].reason.lower()


def test_internal_only_claim_excluded():
    """An internal_only claim is excluded from public output."""
    claim = _make_claim(display_eligibility="internal_only")
    approved, excluded = review_gate([claim])
    assert len(approved) == 0
    assert len(excluded) == 1


def test_publishable_claims_pass_review():
    """publishable_precise and publishable_generalized pass the gate."""
    precise = _make_claim(display_eligibility="publishable_precise")
    general = _make_claim(display_eligibility="publishable_generalized")
    approved, excluded = review_gate([precise, general])
    assert len(approved) == 2
    assert len(excluded) == 0


# ---------------------------------------------------------------------------
# 4. Candidate data centers retain their candidate label
# ---------------------------------------------------------------------------


def test_candidate_data_center_retains_label():
    """A data center with only candidate evidence keeps 'candidate' status
    and the manifest records it without promoting to confirmed."""
    fid = uuid.uuid4()
    sel = FacilitySelection(
        product_surface="report",
        scope="county",
        facility_classes=("data_center",),
        named_search=None,
        treatment="evidence_backed_report",
    )
    claim = _make_claim(
        facility_id=fid,
        display_eligibility="publishable_generalized",
        quantity_status="authorized",
    )
    manifest = build_facility_manifest(
        selection=sel,
        resolved=[claim],
        snapshot_versions={"FRS": "snap-1"},
    )
    assert manifest is not None
    # The manifest does not change the claim's status or eligibility
    assert manifest.display_status == "publishable_generalized"


# ---------------------------------------------------------------------------
# 5. A facility selection cannot change the base render recipe
# ---------------------------------------------------------------------------


def test_selection_is_frozen():
    """FacilitySelection is immutable — cannot change base render recipe."""
    sel = FacilitySelection(
        product_surface="image",
        scope="state",
        facility_classes=("drinking_water",),
        named_search=None,
        treatment="visual_context",
    )
    with pytest.raises(AttributeError):
        sel.treatment = "evidence_backed_report"  # type: ignore[misc]


def test_manifest_does_not_alter_selection():
    """The manifest preserves the original selection unchanged."""
    sel = FacilitySelection(
        product_surface="image",
        scope="state",
        facility_classes=("wastewater",),
        named_search=None,
        treatment="water_infrastructure_context",
    )
    claim = _make_claim(display_eligibility="publishable_precise")
    manifest = build_facility_manifest(
        selection=sel,
        resolved=[claim],
        snapshot_versions={"SDWIS": "v1"},
    )
    assert manifest is not None
    assert manifest.selection is sel


def test_invalid_treatment_rejected():
    """An invalid treatment value raises FacilityRequestError."""
    with pytest.raises(FacilityRequestError):
        FacilitySelection(
            product_surface="image",
            scope="state",
            facility_classes=("data_center",),
            named_search=None,
            treatment="magic_overlay",
        )


def test_invalid_product_surface_rejected():
    """An invalid product_surface raises FacilityRequestError."""
    with pytest.raises(FacilityRequestError):
        FacilitySelection(
            product_surface="poster",
            scope="state",
            facility_classes=("data_center",),
            named_search=None,
            treatment="visual_context",
        )
