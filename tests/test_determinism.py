"""Tests for the determinism verdict + golden registry (roadmap #39/#40, pure core).

Offline: the pure comparison/registry/formatting half of the determinism
verifier. The GDAL-backed double-render + DEM-mosaic checksum live in
``tools/verify_determinism.py`` and are verified on a GDAL host, not here.

#40 grows a golden entry from a bare SVG sha to a small structure carrying the
SVG sha (cross-host invariant) plus an optional DEM mosaic sha (same-host
regression fingerprint of the real warp/mosaic path).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.determinism import (
    DeterminismError,
    Golden,
    dump_registry,
    evaluate,
    format_verdict,
    load_registry,
    lookup_golden,
    record_golden,
    registry_key,
)

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64


def test_registry_key_normalizes_region_and_county() -> None:
    assert registry_key("oregon") == "Oregon"
    assert registry_key("Washington", "Clark") == "Washington/clark"


def test_registry_key_rejects_unknown_region() -> None:
    with pytest.raises(DeterminismError):
        registry_key("Atlantis")


def test_load_registry_missing_file_is_empty(tmp_path) -> None:
    assert load_registry(tmp_path / "nope.json") == {}


def test_load_registry_parses_object_form(tmp_path) -> None:
    p = tmp_path / "golden.json"
    p.write_text(
        json.dumps({"Oregon": {"svg_sha256": _A, "dem_mosaic_sha256": _B}}),
        encoding="utf-8",
    )
    reg = load_registry(p)
    assert reg == {"Oregon": Golden(svg_sha256=_A, dem_mosaic_sha256=_B)}


def test_load_registry_accepts_bare_string_as_svg_only(tmp_path) -> None:
    # A #39-era flat entry (or a hand-authored svg-only entry) still loads.
    p = tmp_path / "golden.json"
    p.write_text(json.dumps({"Oregon": _A}), encoding="utf-8")
    assert load_registry(p) == {"Oregon": Golden(svg_sha256=_A, dem_mosaic_sha256=None)}


def test_load_registry_rejects_non_sha_values(tmp_path) -> None:
    p = tmp_path / "golden.json"
    p.write_text(json.dumps({"Oregon": "not-a-hash"}), encoding="utf-8")
    with pytest.raises(DeterminismError):
        load_registry(p)

    p.write_text(
        json.dumps({"Oregon": {"svg_sha256": "nope"}}), encoding="utf-8"
    )
    with pytest.raises(DeterminismError):
        load_registry(p)

    # An entry with no svg sha at all is invalid.
    p.write_text(json.dumps({"Oregon": {"dem_mosaic_sha256": _B}}), encoding="utf-8")
    with pytest.raises(DeterminismError):
        load_registry(p)


def test_dump_registry_roundtrips(tmp_path) -> None:
    reg = {
        "Oregon": Golden(svg_sha256=_A, dem_mosaic_sha256=_B),
        "Idaho": Golden(svg_sha256=_C),
    }
    p = tmp_path / "golden.json"
    p.write_text(json.dumps(dump_registry(reg), sort_keys=True), encoding="utf-8")
    assert load_registry(p) == reg
    # svg-only entries serialize without a null dem key.
    assert "dem_mosaic_sha256" not in dump_registry(reg)["Idaho"]


def test_evaluate_svg_run_to_run_match_and_golden_match() -> None:
    verdict = evaluate("Oregon", [_A, _A], {"Oregon": Golden(_A)})
    assert verdict.run_to_run_ok is True
    assert verdict.golden_ok is True
    assert verdict.ok is True
    assert verdict.needs_recording is False


def test_evaluate_svg_run_to_run_drift_fails() -> None:
    verdict = evaluate("Oregon", [_A, _B], {"Oregon": Golden(_A)})
    assert verdict.run_to_run_ok is False
    assert verdict.ok is False
    assert "DRIFT" in format_verdict(verdict)


def test_evaluate_svg_golden_mismatch_fails() -> None:
    verdict = evaluate("Oregon", [_B, _B], {"Oregon": Golden(_A)})
    assert verdict.run_to_run_ok is True
    assert verdict.golden_ok is False
    assert verdict.ok is False
    report = format_verdict(verdict)
    assert "MISMATCH" in report and _A in report and _B in report


def test_evaluate_unrecorded_svg_golden_is_soft_record_me() -> None:
    verdict = evaluate("Idaho", [_A, _A], {})
    assert verdict.golden_ok is None
    assert verdict.needs_recording is True
    assert verdict.ok is True  # unrecorded is not a failure
    assert "record" in format_verdict(verdict).lower()


def test_evaluate_requires_two_runs() -> None:
    with pytest.raises(DeterminismError):
        evaluate("Oregon", [_A], {})


def test_evaluate_dem_match_passes() -> None:
    verdict = evaluate(
        "Oregon", [_A, _A], {"Oregon": Golden(_A, dem_mosaic_sha256=_B)}, dem_sha=_B
    )
    assert verdict.dem_sha == _B
    assert verdict.golden_dem_sha == _B
    assert verdict.dem_ok is True
    assert verdict.ok is True
    assert "MATCH" in format_verdict(verdict)


def test_evaluate_dem_mismatch_fails() -> None:
    verdict = evaluate(
        "Oregon", [_A, _A], {"Oregon": Golden(_A, dem_mosaic_sha256=_B)}, dem_sha=_C
    )
    assert verdict.dem_ok is False
    assert verdict.ok is False
    report = format_verdict(verdict)
    assert "dem" in report.lower() and "MISMATCH" in report


def test_evaluate_dem_unrecorded_is_soft_record_me() -> None:
    # A DEM sha supplied but no DEM golden recorded yet is a soft "record me".
    verdict = evaluate("Oregon", [_A, _A], {"Oregon": Golden(_A)}, dem_sha=_B)
    assert verdict.dem_ok is None
    assert verdict.needs_recording is True
    assert verdict.ok is True


def test_evaluate_dem_not_supplied_is_not_checked() -> None:
    verdict = evaluate(
        "Oregon", [_A, _A], {"Oregon": Golden(_A, dem_mosaic_sha256=_B)}, dem_sha=None
    )
    assert verdict.dem_ok is None
    assert verdict.ok is True


def test_record_golden_records_both_halves() -> None:
    stable = evaluate("Idaho", [_A, _A], {}, dem_sha=_B)
    updated = record_golden({}, stable)
    assert lookup_golden(updated, "Idaho") == Golden(svg_sha256=_A, dem_mosaic_sha256=_B)


def test_record_golden_merges_missing_half() -> None:
    # Recording only a new SVG must not clobber an existing DEM golden.
    existing = {"Oregon": Golden(_A, dem_mosaic_sha256=_B)}
    verdict = evaluate("Oregon", [_C, _C], existing)  # no dem_sha this run
    updated = record_golden(existing, verdict)
    assert updated["Oregon"] == Golden(svg_sha256=_C, dem_mosaic_sha256=_B)


def test_record_golden_refuses_flaky() -> None:
    flaky = evaluate("Oregon", [_A, _B], {})
    with pytest.raises(DeterminismError):
        record_golden({}, flaky)


# --- Committed golden registry shape-check (#40) ---


_GOLDEN_REGISTRY = Path(__file__).parent / "fixtures" / "golden" / "registry.json"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_committed_golden_registry_exists_and_loads() -> None:
    """The committed golden registry is valid JSON that load_registry accepts."""
    assert _GOLDEN_REGISTRY.exists()
    reg = load_registry(_GOLDEN_REGISTRY)
    assert len(reg) >= 1  # at least one region


def test_committed_golden_hashes_are_hex64() -> None:
    """Every hash in the committed registry is a 64-char lowercase hex string."""
    reg = load_registry(_GOLDEN_REGISTRY)
    for key, golden in reg.items():
        assert _HEX64.match(golden.svg_sha256), f"{key} svg_sha256 not hex64"
        if golden.dem_mosaic_sha256 is not None:
            assert _HEX64.match(golden.dem_mosaic_sha256), f"{key} dem_mosaic_sha256 not hex64"
