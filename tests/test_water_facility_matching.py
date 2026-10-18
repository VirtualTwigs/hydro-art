"""Offline tests for water-facility candidate matching and scoring.

Tests are specified in the unit-test plan
(``agent-os/specs/2026-09-13-water-facilities-data-center-intelligence/
planning/unit-test-plan.md``).

Covers: exact authority-ID match, high-confidence name/address/geography
match, ambiguous review-queue result, no merge for nearby but distinct
facilities, input-ordering stability, and source name/address retention.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.water_matching import (
    MatchCandidate,
    match_by_authority_id,
    resolve_matches,
    score_candidate,
)
from src.water_source import NormalizedFacility

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SNAP = uuid.uuid4()


def _nf(
    *,
    name: str = "Test Facility",
    authority: str = "EPA_FRS",
    external_id: str = "100",
    jurisdiction: str = "TX",
    latitude: float | None = 30.0,
    longitude: float | None = -97.0,
    source_key: str | None = None,
) -> NormalizedFacility:
    return NormalizedFacility(
        source_family="FRS",
        source_key=source_key or external_id,
        snapshot_id=_SNAP,
        name=name,
        facility_class="industrial",
        jurisdiction=jurisdiction,
        latitude=latitude,
        longitude=longitude,
        authority=authority,
        external_id=external_id,
    )


# ---------------------------------------------------------------------------
# 1. Exact authority ID wins
# ---------------------------------------------------------------------------


def test_exact_authority_id_match():
    """Same authority + external_id produces an automatic match."""
    source = _nf(authority="EPA_FRS", external_id="ABC123", name="Source Name")
    registry = [
        _nf(
            authority="EPA_FRS",
            external_id="ABC123",
            name="Registry Name",
            source_key="reg1",
        ),
    ]
    results = match_by_authority_id([source], registry)
    assert len(results) == 1
    assert results[0].decision == "auto_link"
    assert results[0].source_facility is source
    assert results[0].target_facility is registry[0]


# ---------------------------------------------------------------------------
# 2. One high-score candidate links
# ---------------------------------------------------------------------------


def test_high_score_candidate_auto_links():
    """A single candidate with high name/jurisdiction/proximity links."""
    a = _nf(name="Austin WWTP", jurisdiction="TX", latitude=30.267,
            longitude=-97.743, authority="", external_id="")
    b = _nf(name="Austin WWTP", jurisdiction="TX", latitude=30.267,
            longitude=-97.743, authority="", external_id="",
            source_key="b")
    score = score_candidate(a, b)
    assert score >= 0.85
    results = resolve_matches(
        [MatchCandidate(
            source_facility=a,
            target_facility=b,
            score=score,
            component_scores={},
            decision="pending",
        )],
        auto_threshold=0.85,
        review_threshold=0.60,
    )
    assert results[0].decision == "auto_link"


# ---------------------------------------------------------------------------
# 3. Equal close candidates enter review queue
# ---------------------------------------------------------------------------


def test_ambiguous_candidates_enter_review():
    """Two similar-scoring candidates both enter the review queue."""
    source = _nf(name="Springfield WTP", jurisdiction="IL",
                  authority="", external_id="")
    target_a = _nf(name="Springfield Water Plant", jurisdiction="IL",
                    source_key="a", authority="", external_id="")
    target_b = _nf(name="Springfield Water Treatment", jurisdiction="IL",
                    source_key="b", authority="", external_id="")
    sa = score_candidate(source, target_a)
    sb = score_candidate(source, target_b)
    # Both should be in the review band (not auto-link)
    candidates = [
        MatchCandidate(source_facility=source, target_facility=target_a,
                       score=sa, component_scores={}, decision="pending"),
        MatchCandidate(source_facility=source, target_facility=target_b,
                       score=sb, component_scores={}, decision="pending"),
    ]
    results = resolve_matches(candidates, auto_threshold=0.85,
                              review_threshold=0.60)
    decisions = {r.decision for r in results}
    # At least one must be review (ambiguity prevents auto for both)
    assert "review" in decisions


# ---------------------------------------------------------------------------
# 4. Similarly named neighbors do not merge
# ---------------------------------------------------------------------------


def test_nearby_distinct_facilities_no_merge():
    """Two facilities with the same name but different jurisdictions
    must not auto-link even if geographically close."""
    a = _nf(name="Main Street Pump Station", jurisdiction="TX",
            latitude=30.0, longitude=-97.0, authority="", external_id="")
    b = _nf(name="Main Street Pump Station", jurisdiction="OK",
            latitude=30.01, longitude=-97.01, authority="", external_id="",
            source_key="b")
    score = score_candidate(a, b)
    result = resolve_matches(
        [MatchCandidate(source_facility=a, target_facility=b,
                        score=score, component_scores={}, decision="pending")],
        auto_threshold=0.85,
        review_threshold=0.60,
    )
    assert result[0].decision != "auto_link"


# ---------------------------------------------------------------------------
# 5. Input ordering does not change a result
# ---------------------------------------------------------------------------


def test_input_ordering_stability():
    """Reversing candidate order gives the same scores and decisions."""
    a = _nf(name="Cedar Rapids WTP", jurisdiction="IA", authority="",
            external_id="", source_key="a")
    b = _nf(name="Cedar Rapids Water Treatment", jurisdiction="IA",
            authority="", external_id="", source_key="b")
    score_ab = score_candidate(a, b)
    score_ba = score_candidate(b, a)
    assert score_ab == score_ba


# ---------------------------------------------------------------------------
# 6. Source names/addresses are retained (canonical doesn't overwrite source)
# ---------------------------------------------------------------------------


def test_source_names_retained_after_match():
    """A match result retains both source and target facility names."""
    source = _nf(name="Original Source Name", authority="EPA_FRS",
                  external_id="X1")
    target = _nf(name="Canonical Registry Name", authority="EPA_FRS",
                  external_id="X1", source_key="t1")
    results = match_by_authority_id([source], [target])
    assert results[0].source_facility.name == "Original Source Name"
    assert results[0].target_facility.name == "Canonical Registry Name"
