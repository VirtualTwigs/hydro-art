"""Tests for the reproducibility release-gate core (Epoch 23, #92).

Fully offline: ``src.release`` recomputes the render-independent golden fixtures (gallery
ledger + flagship e2e contract digest) and aggregates ``src.determinism`` verdicts into a
ready/blocked release verdict. No GDAL/network/datasets; the real double-render is the
non-offline ``tools/release_gate.py`` / ``tools/verify_determinism.py`` half.
"""

from __future__ import annotations

from src.determinism import DeterminismVerdict
from src.release import (
    RELEASE_SCHEMA,
    FixtureCheck,
    ReleaseVerdict,
    check_render_independent_goldens,
    evaluate_release,
    format_verdict,
)

_SHA = "a" * 64


def _passing_verdict(key="Washington/wahkiakum"):
    return DeterminismVerdict(
        key=key,
        run_shas=(_SHA, _SHA),
        golden_sha=_SHA,
        run_to_run_ok=True,
        golden_ok=True,
    )


def _failing_verdict(key="Washington/wahkiakum"):
    return DeterminismVerdict(
        key=key,
        run_shas=(_SHA, "b" * 64),
        golden_sha=_SHA,
        run_to_run_ok=False,
        golden_ok=False,
    )


def test_render_independent_goldens_all_pass_on_committed_fixtures():
    checks = check_render_independent_goldens()
    assert checks
    assert all(isinstance(c, FixtureCheck) for c in checks)
    names = {c.name for c in checks}
    assert "gallery-ledger" in names
    assert "e2e-contract-digest" in names
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_render_independent_goldens_detect_a_mismatch(tmp_path):
    # point the recompute at an empty golden root -> the committed fixtures are absent/mismatched.
    checks = check_render_independent_goldens(root=tmp_path)
    assert checks
    assert any(not c.ok for c in checks)


def test_release_ready_when_fixtures_pass_and_determinism_passes():
    verdict = evaluate_release("1.0.0", determinism_verdicts=[_passing_verdict()])
    assert verdict.version == "1.0.0"
    assert verdict.fixtures_ok
    assert verdict.determinism_ok
    assert verdict.ready


def test_release_blocked_when_a_determinism_verdict_fails():
    verdict = evaluate_release("1.0.0", determinism_verdicts=[_failing_verdict()])
    assert verdict.fixtures_ok
    assert not verdict.determinism_ok
    assert not verdict.ready


def test_release_blocked_when_determinism_required_but_none_supplied():
    verdict = evaluate_release("1.0.0", determinism_verdicts=[], require_determinism=True)
    assert not verdict.ready
    # fixture-only mode is allowed to be ready when determinism isn't required.
    offline = evaluate_release("1.0.0", determinism_verdicts=[], require_determinism=False)
    assert offline.ready


def test_release_blocked_when_fixtures_mismatch(tmp_path):
    verdict = evaluate_release(
        "1.0.0", determinism_verdicts=[_passing_verdict()], root=tmp_path
    )
    assert not verdict.fixtures_ok
    assert not verdict.ready


def test_format_verdict_is_deterministic_and_names_the_state():
    verdict = evaluate_release("1.0.0", determinism_verdicts=[_passing_verdict()])
    text = format_verdict(verdict)
    assert text == format_verdict(verdict)
    assert RELEASE_SCHEMA in text
    assert "1.0.0" in text
    assert "READY" in text
    blocked = format_verdict(evaluate_release("1.0.0", determinism_verdicts=[_failing_verdict()]))
    assert "BLOCKED" in blocked
