"""Tests for the determinism verdict + golden registry (roadmap #39, pure core).

Offline: the pure comparison/registry/formatting half of the determinism
verifier. The GDAL-backed double-render lives in ``tools/verify_determinism.py``
and is verified on a GDAL host, not here.
"""

from __future__ import annotations

import json

import pytest

from src.determinism import (
    DeterminismError,
    evaluate,
    format_verdict,
    load_registry,
    lookup_golden,
    record_golden,
    registry_key,
)

_A = "a" * 64
_B = "b" * 64


def test_registry_key_normalizes_region_and_county() -> None:
    assert registry_key("oregon") == "Oregon"
    assert registry_key("Washington", "Clark") == "Washington/clark"


def test_registry_key_rejects_unknown_region() -> None:
    with pytest.raises(DeterminismError):
        registry_key("Atlantis")


def test_load_registry_missing_file_is_empty(tmp_path) -> None:
    assert load_registry(tmp_path / "nope.json") == {}


def test_load_registry_rejects_non_sha_values(tmp_path) -> None:
    p = tmp_path / "golden.json"
    p.write_text(json.dumps({"Oregon": "not-a-hash"}), encoding="utf-8")
    with pytest.raises(DeterminismError):
        load_registry(p)


def test_evaluate_run_to_run_match_and_golden_match() -> None:
    verdict = evaluate("Oregon", [_A, _A], {"Oregon": _A})
    assert verdict.run_to_run_ok is True
    assert verdict.golden_ok is True
    assert verdict.ok is True
    assert verdict.needs_recording is False


def test_evaluate_run_to_run_drift_fails() -> None:
    verdict = evaluate("Oregon", [_A, _B], {"Oregon": _A})
    assert verdict.run_to_run_ok is False
    assert verdict.ok is False
    assert "DRIFT" in format_verdict(verdict)


def test_evaluate_golden_mismatch_fails() -> None:
    verdict = evaluate("Oregon", [_B, _B], {"Oregon": _A})
    assert verdict.run_to_run_ok is True
    assert verdict.golden_ok is False
    assert verdict.ok is False
    report = format_verdict(verdict)
    assert "MISMATCH" in report and _A in report and _B in report


def test_evaluate_unrecorded_golden_is_soft_record_me() -> None:
    verdict = evaluate("Idaho", [_A, _A], {})
    assert verdict.golden_ok is None
    assert verdict.needs_recording is True
    assert verdict.ok is True  # unrecorded is not a failure
    assert "record" in format_verdict(verdict).lower()


def test_evaluate_requires_two_runs() -> None:
    with pytest.raises(DeterminismError):
        evaluate("Oregon", [_A], {})


def test_record_golden_records_stable_run_and_refuses_flaky() -> None:
    stable = evaluate("Idaho", [_A, _A], {})
    updated = record_golden({}, stable)
    assert lookup_golden(updated, "Idaho") == _A

    flaky = evaluate("Oregon", [_A, _B], {})
    with pytest.raises(DeterminismError):
        record_golden({}, flaky)
