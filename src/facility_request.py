"""Customer facility-request options and review gate.

Pure, offline module for building immutable facility-request manifests,
filtering claims through a review gate, and producing customer-safe
exclusion records.  No database driver, no GIS imports, no network at
module load time.  Nothing enters ``PIPELINE_STAGES``.

See ``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
spec.md`` and task group 7 (#118).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.water_facility import WaterClaim

__all__ = [
    "PRODUCT_SURFACES",
    "TREATMENTS",
    "FacilityExclusion",
    "FacilityRequestError",
    "FacilityRequestManifest",
    "FacilitySelection",
    "build_facility_manifest",
    "review_gate",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class FacilityRequestError(Exception):
    """Raised for invalid facility-request operations."""


# ---------------------------------------------------------------------------
# Closed enum sets
# ---------------------------------------------------------------------------

PRODUCT_SURFACES: frozenset[str] = frozenset({"image", "report"})

TREATMENTS: frozenset[str] = frozenset({
    "visual_context",
    "evidence_backed_report",
    "water_evidence_overlay",
    "named_facility_research_note",
    "water_infrastructure_context",
})

# Eligibilities that pass the review gate into public output
_PUBLISHABLE: frozenset[str] = frozenset({
    "publishable_precise",
    "publishable_generalized",
})


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FacilitySelection:
    """Immutable customer selection of facility classes/search for a product.

    Validates ``product_surface`` and ``treatment`` at construction time.
    """

    product_surface: str
    scope: str
    facility_classes: tuple[str, ...]
    named_search: str | None
    treatment: str

    def __post_init__(self) -> None:
        if self.product_surface not in PRODUCT_SURFACES:
            raise FacilityRequestError(
                f"Invalid product_surface {self.product_surface!r}; "
                f"allowed: {sorted(PRODUCT_SURFACES)}"
            )
        if self.treatment not in TREATMENTS:
            raise FacilityRequestError(
                f"Invalid treatment {self.treatment!r}; "
                f"allowed: {sorted(TREATMENTS)}"
            )


@dataclass(frozen=True)
class FacilityExclusion:
    """Customer-safe exclusion record for a facility that did not pass review."""

    facility_id: uuid.UUID
    reason: str
    detail: str


@dataclass(frozen=True)
class FacilityRequestManifest:
    """Immutable, snapshot-pinned manifest of resolved facility selections."""

    selection: FacilitySelection
    snapshot_versions: dict[str, str]
    resolved_facility_ids: tuple[uuid.UUID, ...]
    exclusions: list[FacilityExclusion]
    reviewer: str | None
    review_time: datetime | None
    display_status: str


# ---------------------------------------------------------------------------
# Review gate
# ---------------------------------------------------------------------------


def review_gate(
    claims: list[WaterClaim],
) -> tuple[list[WaterClaim], list[FacilityExclusion]]:
    """Filter claims through the review gate.

    Returns ``(approved, excluded)`` where *approved* contains only
    ``publishable_precise`` or ``publishable_generalized`` claims and
    *excluded* contains a :class:`FacilityExclusion` for every rejected
    claim with a customer-safe reason string.
    """
    approved: list[WaterClaim] = []
    excluded: list[FacilityExclusion] = []

    _REASON_MAP = {
        "review_required": "Pending review — not yet approved for publication",
        "internal_only": "Restricted to internal use only",
        "excluded": "Excluded from publication — restricted or unavailable",
    }

    for claim in claims:
        if claim.display_eligibility in _PUBLISHABLE:
            approved.append(claim)
        else:
            reason = _REASON_MAP.get(
                claim.display_eligibility,
                f"Ineligible for publication ({claim.display_eligibility})",
            )
            excluded.append(FacilityExclusion(
                facility_id=claim.facility_id,
                reason=reason,
                detail=f"display_eligibility={claim.display_eligibility!r}",
            ))

    return approved, excluded


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------


def build_facility_manifest(
    *,
    selection: FacilitySelection | None,
    resolved: list[WaterClaim],
    snapshot_versions: dict[str, str],
    reviewer: str | None = None,
    review_time: datetime | None = None,
) -> FacilityRequestManifest | None:
    """Build an immutable facility-request manifest.

    Returns ``None`` when *selection* is ``None`` (no facility overlay
    requested).  Otherwise pins resolved facility IDs and snapshot
    versions into a frozen manifest.
    """
    if selection is None:
        return None

    approved, exclusions = review_gate(resolved)

    facility_ids = tuple(dict.fromkeys(c.facility_id for c in approved))

    # Display status is the lowest-privilege eligibility among approved claims,
    # or the first exclusion reason if nothing was approved.
    if approved:
        if any(
            c.display_eligibility == "publishable_generalized" for c in approved
        ):
            display_status = "publishable_generalized"
        else:
            display_status = "publishable_precise"
    else:
        display_status = "no_publishable_claims"

    return FacilityRequestManifest(
        selection=selection,
        snapshot_versions=dict(snapshot_versions),
        resolved_facility_ids=facility_ids,
        exclusions=exclusions,
        reviewer=reviewer,
        review_time=review_time,
        display_status=display_status,
    )
