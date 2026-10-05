"""Water-facility evidence ranking and relevance determination.

Pure, offline module for ranking evidence types, determining water
relevance, and validating quantity claims against evidence.  No database
driver, no GIS imports, no network at module load time.

Evidence types are ordered from strongest (metered_volume) to weakest
(naics_only).  The ranking drives water-relevance determination and
quantity-claim validation.
"""

from __future__ import annotations

from collections import OrderedDict

from src.water_facility import WaterFacilityError

__all__ = [
    "EVIDENCE_RANK",
    "determine_relevance",
    "rank_evidence",
    "validate_quantity_claim",
]


# ---------------------------------------------------------------------------
# Evidence ranking (lower rank = stronger evidence)
# ---------------------------------------------------------------------------

EVIDENCE_RANK: OrderedDict[str, int] = OrderedDict([
    ("metered_volume", 0),
    ("withdrawal_permit", 1),
    ("discharge_permit", 2),
    ("utility_agreement", 3),
    ("operator_disclosure", 4),
    ("naics_only", 5),
])

# Evidence types that can never support a measured quantity claim
_WEAK_EVIDENCE: frozenset[str] = frozenset({
    "naics_only",
    "wue_estimate",
    "campus_size_estimate",
})

# Evidence types that can reach "confirmed" relevance
_CONFIRMABLE: frozenset[str] = frozenset({
    "metered_volume",
    "withdrawal_permit",
    "discharge_permit",
})


def rank_evidence(evidence_type: str) -> int:
    """Return the ordinal rank of an evidence type (lower = stronger).

    Raises :class:`WaterFacilityError` for unrecognized types.
    """
    if evidence_type in EVIDENCE_RANK:
        return EVIDENCE_RANK[evidence_type]
    raise WaterFacilityError(
        f"Unknown evidence type {evidence_type!r}; "
        f"allowed: {list(EVIDENCE_RANK)}"
    )


# ---------------------------------------------------------------------------
# Relevance determination
# ---------------------------------------------------------------------------


def determine_relevance(evidence_types: list[str]) -> str:
    """Determine the water-relevance level from available evidence types.

    Returns one of the ``WATER_RELEVANCE_LEVELS``:
    - ``"confirmed"`` — at least one confirmable evidence type present.
    - ``"permitted_or_committed"`` — utility agreement or operator disclosure
      but no confirmable evidence.
    - ``"candidate"`` — only weak evidence (NAICS, WUE, campus size).
    - ``"unknown"`` — no recognized evidence.
    """
    if not evidence_types:
        return "unknown"

    types = set(evidence_types)

    # Any confirmable evidence → confirmed
    if types & _CONFIRMABLE:
        return "confirmed"

    # Utility agreement or operator disclosure → permitted_or_committed
    if types & {"utility_agreement", "operator_disclosure"}:
        return "permitted_or_committed"

    # Only weak evidence → candidate
    if types & (_WEAK_EVIDENCE | {"naics_only"}):
        return "candidate"

    return "unknown"


# ---------------------------------------------------------------------------
# Quantity-claim validation
# ---------------------------------------------------------------------------


def validate_quantity_claim(
    *,
    measure_type: str,
    quantity_status: str,
    evidence_type: str,
) -> None:
    """Validate that a quantity claim is supportable by its evidence.

    Raises :class:`WaterFacilityError` when:
    - ``authorized_capacity`` is paired with ``measured`` status.
    - A weak evidence type (WUE, NAICS, campus size) claims a volume
      (withdrawal/delivered/consumed/discharged) as measured/reported.
    - An unrecognized evidence type is used for a measured claim.
    """
    # Rule 1: authorized_capacity can only be "authorized" or "unavailable"
    if measure_type == "authorized_capacity" and quantity_status == "measured":
        raise WaterFacilityError(
            "authorized_capacity cannot have quantity_status 'measured'; "
            "use 'authorized' instead"
        )

    # Rule 2: weak evidence cannot support measured/reported volume claims
    volume_types = {"withdrawal", "delivered", "consumed", "discharged"}
    if (evidence_type in _WEAK_EVIDENCE
            and measure_type in volume_types
            and quantity_status in {"measured", "reported"}):
        raise WaterFacilityError(
            f"Evidence type {evidence_type!r} cannot support "
            f"{quantity_status} {measure_type}"
        )

    # Rule 3: unrecognized evidence cannot support measured claims
    all_known = set(EVIDENCE_RANK) | _WEAK_EVIDENCE
    if evidence_type not in all_known and quantity_status == "measured":
        raise WaterFacilityError(
            f"Unrecognized evidence type {evidence_type!r} cannot support "
            f"a measured claim"
        )
