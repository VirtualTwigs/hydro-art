"""Deterministic facility matching and scoring.

Pure, offline module for entity resolution between normalized source
facilities and a registry of known facilities.  No database driver,
no GIS imports, no network at module load time.

Scoring components:
- Authority ID exact match (automatic link, bypasses scoring).
- Normalized name similarity (SequenceMatcher ratio).
- Jurisdiction equality (binary).
- Geographic proximity (exponential decay on distance).

Thresholds are caller-configurable; defaults follow the spec:
``auto_threshold=0.85``, ``review_threshold=0.60``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from typing import Sequence

from src.water_source import NormalizedFacility

__all__ = [
    "MatchCandidate",
    "match_by_authority_id",
    "resolve_matches",
    "score_candidate",
]


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchCandidate:
    """A scored pairing of two facilities with a resolution decision."""

    source_facility: NormalizedFacility
    target_facility: NormalizedFacility
    score: float
    component_scores: dict[str, float]
    decision: str  # "auto_link" | "review" | "no_match" | "pending"


# ---------------------------------------------------------------------------
# Authority-ID matching
# ---------------------------------------------------------------------------


def match_by_authority_id(
    sources: Sequence[NormalizedFacility],
    registry: Sequence[NormalizedFacility],
) -> list[MatchCandidate]:
    """Return automatic matches where authority + external_id are identical.

    Only non-empty authority/external_id pairs are considered.
    """
    # Build lookup: (authority, external_id) -> first registry entry
    lookup: dict[tuple[str, str], NormalizedFacility] = {}
    for r in registry:
        if r.authority and r.external_id:
            key = (r.authority, r.external_id)
            if key not in lookup:
                lookup[key] = r

    results: list[MatchCandidate] = []
    for s in sources:
        if s.authority and s.external_id:
            key = (s.authority, s.external_id)
            target = lookup.get(key)
            if target is not None:
                results.append(MatchCandidate(
                    source_facility=s,
                    target_facility=target,
                    score=1.0,
                    component_scores={"authority_id": 1.0},
                    decision="auto_link",
                ))
    return results


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

# Weights for composite score
_W_NAME = 0.45
_W_JURISDICTION = 0.30
_W_PROXIMITY = 0.25

# Distance decay: at this many km the proximity score = ~0.37
_DISTANCE_DECAY_KM = 5.0


def _name_similarity(a: str, b: str) -> float:
    """Normalized name similarity using SequenceMatcher."""
    na = a.strip().lower()
    nb = b.strip().lower()
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _jurisdiction_score(a: str, b: str) -> float:
    """Binary jurisdiction match."""
    return 1.0 if a.strip().upper() == b.strip().upper() else 0.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate great-circle distance in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _proximity_score(
    a: NormalizedFacility, b: NormalizedFacility
) -> float:
    """Exponential-decay proximity score; 1.0 when co-located."""
    if (a.latitude is None or a.longitude is None
            or b.latitude is None or b.longitude is None):
        return 0.0
    d = _haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
    return math.exp(-d / _DISTANCE_DECAY_KM)


def score_candidate(a: NormalizedFacility, b: NormalizedFacility) -> float:
    """Compute a deterministic composite match score in [0, 1].

    Components: name similarity, jurisdiction equality, geographic proximity.
    The score is symmetric: ``score_candidate(a, b) == score_candidate(b, a)``.
    """
    ns = _name_similarity(a.name, b.name)
    js = _jurisdiction_score(a.jurisdiction, b.jurisdiction)
    ps = _proximity_score(a, b)
    return _W_NAME * ns + _W_JURISDICTION * js + _W_PROXIMITY * ps


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_matches(
    candidates: Sequence[MatchCandidate],
    *,
    auto_threshold: float = 0.85,
    review_threshold: float = 0.60,
) -> list[MatchCandidate]:
    """Assign decisions based on score thresholds.

    - score >= auto_threshold and no rival with score within 0.05 → auto_link
    - score >= review_threshold → review
    - otherwise → no_match

    When multiple candidates share the same source facility and more than
    one is above the auto threshold, all are demoted to ``review`` to avoid
    ambiguous auto-links.
    """
    # Group by source facility identity (source_key + snapshot_id)
    from collections import defaultdict
    groups: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(candidates):
        key = f"{c.source_facility.source_key}:{c.source_facility.snapshot_id}"
        groups[key].append(i)

    results: list[MatchCandidate] = []
    for _key, indices in groups.items():
        group = [candidates[i] for i in indices]
        # Sort by score descending for ambiguity check
        group_sorted = sorted(group, key=lambda c: c.score, reverse=True)

        # Count how many are above auto threshold
        auto_eligible = [c for c in group_sorted if c.score >= auto_threshold]

        for c in group_sorted:
            if c.score >= auto_threshold and len(auto_eligible) == 1:
                decision = "auto_link"
            elif c.score >= review_threshold:
                decision = "review"
            else:
                decision = "no_match"
            results.append(replace(c, decision=decision))

    return results
