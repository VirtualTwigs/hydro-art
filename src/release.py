"""Reproducibility release gate — pure/offline core (Epoch 23, #92).

Final epoch of Generation 1. The release tag (``v1.0``) may only be cut when two things hold:

1. **Golden fixtures match** — the render-independent goldens recompute byte-for-byte from the
   current code (the marketing-gallery rights ledger and the flagship all-four-endpoints e2e
   contract digest), and every committed golden JSON still parses.
2. **Determinism holds** — the real double-render is byte-identical run-to-run and against its
   recorded golden (:mod:`src.determinism`).

This module is the **pure** half: it recomputes the render-independent goldens offline and
aggregates :class:`~src.determinism.DeterminismVerdict`s (produced by the non-offline
double-render) into a single ready/blocked :class:`ReleaseVerdict`. It imports only stdlib +
:mod:`src.gallery` + :mod:`src.endpoints` + :mod:`src.determinism`, so it runs in the offline
suite; the real double-render lives in ``tools/release_gate.py`` / ``tools/verify_determinism.py``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from src.determinism import DeterminismVerdict
from src.endpoints import e2e_contract_digest, flagship_e2e_requests
from src.gallery import gallery_ledger

__all__ = [
    "GOLDEN_ROOT",
    "RELEASE_SCHEMA",
    "FixtureCheck",
    "ReleaseVerdict",
    "check_render_independent_goldens",
    "evaluate_release",
    "format_verdict",
]

RELEASE_SCHEMA = "hydro-art/release-gate@1"

GOLDEN_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "golden"


@dataclass(frozen=True)
class FixtureCheck:
    """One render-independent golden recompute-vs-committed result."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ReleaseVerdict:
    """Aggregated release readiness: fixture recomputes + determinism verdicts."""

    version: str
    fixture_checks: tuple[FixtureCheck, ...]
    determinism_verdicts: tuple[DeterminismVerdict, ...]
    require_determinism: bool = True

    @property
    def fixtures_ok(self) -> bool:
        return bool(self.fixture_checks) and all(c.ok for c in self.fixture_checks)

    @property
    def determinism_ok(self) -> bool:
        if not self.require_determinism:
            return True
        return bool(self.determinism_verdicts) and all(
            v.ok for v in self.determinism_verdicts
        )

    @property
    def ready(self) -> bool:
        return self.fixtures_ok and self.determinism_ok


# The render-independent goldens: a name -> (relative path, recompute callable) map. Each
# callable returns the current in-code value; the gate compares it (parsed-JSON) to the file.
_RENDER_INDEPENDENT: dict[str, tuple[str, Callable[[], object]]] = {
    "gallery-ledger": ("gallery/ledger.json", gallery_ledger),
    "e2e-contract-digest": (
        "e2e/washington-wahkiakum.json",
        lambda: e2e_contract_digest(flagship_e2e_requests()),
    ),
}


def check_render_independent_goldens(
    *, root: str | Path = GOLDEN_ROOT
) -> tuple[FixtureCheck, ...]:
    """Recompute each render-independent golden and compare to its committed file.

    Comparison is parsed-JSON (formatting-insensitive). A missing file, a JSON parse error, or a
    value mismatch each yields a failing :class:`FixtureCheck` (never raises), so the caller gets
    a full punch list rather than the first failure.
    """
    root = Path(root)
    checks: list[FixtureCheck] = []
    for name, (rel, recompute) in _RENDER_INDEPENDENT.items():
        path = root / rel
        try:
            recomputed = recompute()
        except Exception as exc:  # noqa: BLE001 — any recompute bug is itself a gate failure
            checks.append(FixtureCheck(name, False, f"recompute failed: {exc}"))
            continue
        if not path.exists():
            checks.append(FixtureCheck(name, False, f"missing golden {path}"))
            continue
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append(FixtureCheck(name, False, f"golden not valid JSON: {exc}"))
            continue
        if committed == recomputed:
            checks.append(FixtureCheck(name, True, f"matches {rel}"))
        else:
            checks.append(FixtureCheck(name, False, f"recompute differs from {rel}"))
    return tuple(checks)


def evaluate_release(
    version: str,
    *,
    determinism_verdicts: Sequence[DeterminismVerdict] = (),
    root: str | Path = GOLDEN_ROOT,
    require_determinism: bool = True,
) -> ReleaseVerdict:
    """Aggregate fixture recomputes + determinism verdicts into a release verdict.

    ``require_determinism`` (default True) means at least one determinism verdict must be
    supplied and all must pass; set it False for a fixture-only preflight that can run anywhere
    (the ``--offline-only`` mode of the CLI).
    """
    return ReleaseVerdict(
        version=version,
        fixture_checks=check_render_independent_goldens(root=root),
        determinism_verdicts=tuple(determinism_verdicts),
        require_determinism=require_determinism,
    )


def format_verdict(verdict: ReleaseVerdict) -> str:
    """Render a human-readable one-block release-gate report."""
    lines = [f"{RELEASE_SCHEMA}: v{verdict.version}"]
    lines.append("  render-independent goldens:")
    for c in verdict.fixture_checks:
        lines.append(f"    {'OK  ' if c.ok else 'FAIL'} {c.name}: {c.detail}")
    if verdict.require_determinism:
        lines.append("  determinism (double-render):")
        if not verdict.determinism_verdicts:
            lines.append("    FAIL none supplied (run the real double-render)")
        for v in verdict.determinism_verdicts:
            lines.append(f"    {'OK  ' if v.ok else 'FAIL'} {v.key}")
    else:
        lines.append("  determinism: skipped (--offline-only)")
    lines.append(f"  verdict: {'READY' if verdict.ready else 'BLOCKED'}")
    return "\n".join(lines)
