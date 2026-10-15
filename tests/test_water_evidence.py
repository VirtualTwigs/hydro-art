"""Offline tests for water-facility evidence ranking and relevance.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``).

Covers: evidence-ranking order, candidate-to-confirmed transition rules,
site-level evidence requirement, no inferred consumption from NAICS,
campus size, or WUE alone.
"""

from __future__ import annotations

import pytest

from src.water_evidence import (
    EVIDENCE_RANK,
    determine_relevance,
    rank_evidence,
    validate_quantity_claim,
)
from src.water_facility import WaterFacilityError


# ---------------------------------------------------------------------------
# 1. Metered evidence outranks permits and agreements
# ---------------------------------------------------------------------------


def test_metered_outranks_permits():
    """metered_volume has a lower (stronger) rank than all others."""
    metered = rank_evidence("metered_volume")
    permit = rank_evidence("withdrawal_permit")
    discharge = rank_evidence("discharge_permit")
    agreement = rank_evidence("utility_agreement")
    assert metered < permit
    assert metered < discharge
    assert metered < agreement


def test_evidence_rank_ordering():
    """Full ordering: metered < withdrawal < discharge < utility < operator < naics."""
    ranks = [rank_evidence(k) for k in EVIDENCE_RANK]
    assert ranks == sorted(ranks)


# ---------------------------------------------------------------------------
# 2. A generic operator claim cannot confirm a site
# ---------------------------------------------------------------------------


def test_operator_disclosure_cannot_confirm():
    """operator_disclosure alone yields at most permitted_or_committed,
    never confirmed."""
    level = determine_relevance(["operator_disclosure"])
    assert level != "confirmed"


# ---------------------------------------------------------------------------
# 3. NAICS 518210 creates only candidate (never confirmed)
# ---------------------------------------------------------------------------


def test_naics_only_yields_candidate():
    """NAICS classification alone creates only candidate relevance."""
    level = determine_relevance(["naics_only"])
    assert level == "candidate"


def test_naics_plus_metered_can_confirm():
    """NAICS plus metered evidence can reach confirmed."""
    level = determine_relevance(["naics_only", "metered_volume"])
    assert level == "confirmed"


# ---------------------------------------------------------------------------
# 4. Authorized capacity cannot be reported as measured withdrawal
# ---------------------------------------------------------------------------


def test_authorized_capacity_not_measured_withdrawal():
    """authorized_capacity + measured + any evidence must be rejected."""
    with pytest.raises(WaterFacilityError):
        validate_quantity_claim(
            measure_type="authorized_capacity",
            quantity_status="measured",
            evidence_type="metered_volume",
        )


def test_authorized_capacity_as_authorized_ok():
    """authorized_capacity + authorized status is valid."""
    # Should not raise
    validate_quantity_claim(
        measure_type="authorized_capacity",
        quantity_status="authorized",
        evidence_type="withdrawal_permit",
    )


# ---------------------------------------------------------------------------
# 5. Unsupported WUE cannot create water volume
# ---------------------------------------------------------------------------


def test_wue_cannot_create_volume():
    """WUE-derived evidence alone cannot support a withdrawal claim."""
    with pytest.raises(WaterFacilityError):
        validate_quantity_claim(
            measure_type="withdrawal",
            quantity_status="reported",
            evidence_type="wue_estimate",
        )


def test_naics_only_cannot_confirm_site():
    """naics_only evidence cannot support a confirmed (measured) claim."""
    with pytest.raises(WaterFacilityError):
        validate_quantity_claim(
            measure_type="withdrawal",
            quantity_status="measured",
            evidence_type="naics_only",
        )
