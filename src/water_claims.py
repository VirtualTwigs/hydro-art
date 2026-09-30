"""Water-claim extraction, public filtering, and generalization.

Pure, offline module for extracting claims from evidence, filtering to
public-eligible claims, and generalizing claims that omit exact
coordinates.  No database driver, no GIS imports, no network at module
load time.  Nothing enters ``PIPELINE_STAGES``.

See ``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
spec.md`` and task group 8 (#119).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime

from src.water_facility import (
    DISPLAY_ELIGIBILITIES,
    FacilityEvidence,
    WaterClaim,
    WaterFacilityError,
)

__all__ = [
    "ClaimExtractionError",
    "extract_claims",
    "generalize_claim",
    "public_claims",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ClaimExtractionError(Exception):
    """Raised for invalid claim extraction or generalization operations."""


# ---------------------------------------------------------------------------
# Eligibility sets
# ---------------------------------------------------------------------------

_PUBLISHABLE: frozenset[str] = frozenset({
    "publishable_precise",
    "publishable_generalized",
})


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------


def extract_claims(
    *,
    evidence: list[FacilityEvidence],
    facility_id: uuid.UUID,
    subjects: list[tuple[str, str, float | None, str, str, str]],
) -> list[WaterClaim]:
    """Extract claims from evidence for a facility.

    Each subject tuple is ``(subject, predicate, value, unit,
    measure_type, quantity_status)``.  All supplied evidence IDs are
    attached to every claim.  Extracted claims start as
    ``review_required``.

    The claim's ``valid_time_start`` is derived from the evidence
    ``publication_date`` (the fact's time), **not** ``retrieval_date``
    (the system's download time).

    Raises :class:`ClaimExtractionError` when no evidence is provided.
    """
    if not evidence:
        raise ClaimExtractionError(
            "Cannot extract claims without at least one evidence record"
        )

    evidence_ids = tuple(e.id for e in evidence)

    # valid_time is based on publication dates, not retrieval dates
    pub_dates = [e.publication_date for e in evidence]
    valid_start = min(pub_dates)
    valid_end = max(pub_dates)

    # system_time is the latest retrieval (when the system learned of it)
    system_time = max(e.retrieval_date for e in evidence)

    claims: list[WaterClaim] = []
    for subject, predicate, value, unit, measure_type, quantity_status in subjects:
        claim = WaterClaim(
            id=uuid.uuid4(),
            facility_id=facility_id,
            subject=subject,
            predicate=predicate,
            value=value,
            unit=unit,
            measure_type=measure_type,
            quantity_status=quantity_status,
            display_eligibility="review_required",
            confidence=0.0,
            valid_time_start=valid_start,
            valid_time_end=valid_end,
            system_time=system_time,
            reviewer=None,
            review_time=None,
            evidence_ids=evidence_ids,
        )
        claims.append(claim)

    return claims


# ---------------------------------------------------------------------------
# Public-view filter
# ---------------------------------------------------------------------------


def public_claims(claims: list[WaterClaim]) -> list[WaterClaim]:
    """Return only claims eligible for public display.

    Only ``publishable_precise`` and ``publishable_generalized`` claims
    pass.  ``internal_only``, ``review_required``, and ``excluded``
    claims are filtered out.
    """
    return [c for c in claims if c.display_eligibility in _PUBLISHABLE]


# ---------------------------------------------------------------------------
# Generalization
# ---------------------------------------------------------------------------


def generalize_claim(claim: WaterClaim) -> WaterClaim:
    """Strip exact coordinate values from a generalized claim.

    Only ``publishable_generalized`` claims may be generalized.
    Attempting to generalize a ``publishable_precise`` claim raises
    :class:`ClaimExtractionError` because the eligibility must be
    reclassified first.

    Returns a new :class:`WaterClaim` with ``value`` set to ``None``.
    """
    if claim.display_eligibility != "publishable_generalized":
        raise ClaimExtractionError(
            f"Cannot generalize a claim with eligibility "
            f"{claim.display_eligibility!r}; must be 'publishable_generalized'"
        )
    return replace(claim, value=None)
