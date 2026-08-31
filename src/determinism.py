"""Determinism verdict + golden-hash registry (roadmap #39, pure core).

The determinism verifier (``tools/verify_determinism.py``) renders a region
**twice** through the real GDAL-backed :class:`~src.pipeline.Pipeline` and needs
to answer two questions from the resulting ``svg_sha256`` digests:

1. **Run-to-run**: did the two renders on this machine produce the same bytes?
   (the deterministic-output invariant the whole epoch exists to make provable).
2. **Against golden**: does the render match the committed per-region golden hash
   (roadmap #40's fixture)? — this also catches drift introduced by a code
   change, not just run-to-run flakiness. A region with no recorded golden yet is
   a soft "record me" prompt, not a failure.

This module is the **pure** half of that: load/merge a ``{key: sha}`` golden
registry, evaluate the verdict, and format it for the CLI. It imports only stdlib
(plus :data:`src.config.SUPPORTED_REGIONS` for boundary validation), so it runs in
the offline suite; the double-render itself is the non-offline part in ``tools/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from src.config import SUPPORTED_REGIONS

__all__ = [
    "DeterminismError",
    "DeterminismVerdict",
    "registry_key",
    "load_registry",
    "lookup_golden",
    "evaluate",
    "record_golden",
    "format_verdict",
]

_HEX = set("0123456789abcdef")


class DeterminismError(ValueError):
    """A determinism registry/evaluation was called with invalid inputs."""


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(c in _HEX for c in value.lower())


def registry_key(region: str, county: str | None = None) -> str:
    """Return the registry key for a region (optionally a county within it).

    Region is validated against :data:`SUPPORTED_REGIONS` (case-insensitive,
    normalized to the canonical name) so a typo can't silently record a golden
    under a bogus key. The county is normalized to lowercase; the key is
    ``"<region>"`` or ``"<region>/<county>"``.
    """
    canonical = {r.lower(): r for r in SUPPORTED_REGIONS}
    key = region.strip().lower()
    if key not in canonical:
        raise DeterminismError(
            f"Unknown region {region!r}; expected one of "
            f"{', '.join(sorted(SUPPORTED_REGIONS))}."
        )
    base = canonical[key]
    if county:
        return f"{base}/{county.strip().lower()}"
    return base


def load_registry(path: str | Path) -> dict[str, str]:
    """Load a ``{key: svg_sha256}`` golden registry from JSON.

    A missing file is an empty registry (first run for the whole project), not an
    error. Every recorded value must be a 64-hex sha256.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeterminismError(f"Golden registry {p} is not valid JSON: {exc}.") from exc
    if not isinstance(data, dict):
        raise DeterminismError(f"Golden registry {p} must be a JSON object.")
    out: dict[str, str] = {}
    for key, sha in data.items():
        if not isinstance(sha, str) or not _is_sha256(sha):
            raise DeterminismError(
                f"Golden registry {p} entry {key!r} is not a 64-hex sha256."
            )
        out[str(key)] = sha.lower()
    return out


def lookup_golden(registry: Mapping[str, str], key: str) -> str | None:
    """Return the recorded golden sha for ``key``, or ``None`` if unrecorded."""
    return registry.get(key)


@dataclass(frozen=True)
class DeterminismVerdict:
    """The outcome of comparing repeated renders against each other + golden.

    Attributes:
        key: The registry key evaluated (region or region/county).
        run_shas: The ``svg_sha256`` of each render, in order.
        golden_sha: The recorded golden, or ``None`` if unrecorded.
        run_to_run_ok: True iff every run produced the same sha.
        golden_ok: True/False iff a golden exists and all runs match it;
            ``None`` when no golden is recorded yet.
    """

    key: str
    run_shas: tuple[str, ...]
    golden_sha: str | None
    run_to_run_ok: bool
    golden_ok: bool | None

    @property
    def needs_recording(self) -> bool:
        """The render is stable run-to-run but has no golden yet ("record me")."""
        return self.golden_sha is None and self.run_to_run_ok

    @property
    def ok(self) -> bool:
        """Overall pass: stable run-to-run and (matches golden or unrecorded)."""
        return self.run_to_run_ok and self.golden_ok is not False


def evaluate(
    key: str, run_shas: Sequence[str], registry: Mapping[str, str]
) -> DeterminismVerdict:
    """Evaluate repeated-render shas for ``key`` against each other and golden.

    Raises:
        DeterminismError: If fewer than two runs are supplied or any sha is not a
            64-hex digest (the caller must render at least twice to prove
            run-to-run determinism).
    """
    shas = tuple(run_shas)
    if len(shas) < 2:
        raise DeterminismError(
            "evaluate needs at least two render shas to check run-to-run determinism."
        )
    for sha in shas:
        if not _is_sha256(sha):
            raise DeterminismError(f"Render sha {sha!r} is not a 64-hex sha256.")

    run_to_run_ok = len(set(shas)) == 1
    golden_sha = registry.get(key)
    golden_ok: bool | None
    if golden_sha is None:
        golden_ok = None
    else:
        golden_ok = all(sha == golden_sha for sha in shas)
    return DeterminismVerdict(
        key=key,
        run_shas=shas,
        golden_sha=golden_sha,
        run_to_run_ok=run_to_run_ok,
        golden_ok=golden_ok,
    )


def record_golden(registry: Mapping[str, str], verdict: DeterminismVerdict) -> dict[str, str]:
    """Return a new registry with ``verdict``'s stable sha recorded for its key.

    Only a run-to-run-stable render may be recorded (recording a flaky render
    would bake in noise).

    Raises:
        DeterminismError: If the render is not run-to-run stable.
    """
    if not verdict.run_to_run_ok:
        raise DeterminismError(
            f"Refusing to record a run-to-run-unstable render for {verdict.key!r}."
        )
    updated = dict(registry)
    updated[verdict.key] = verdict.run_shas[0]
    return updated


def format_verdict(verdict: DeterminismVerdict) -> str:
    """Render a human-readable one-block report of the verdict."""
    lines = [f"determinism: {verdict.key}"]
    if verdict.run_to_run_ok:
        lines.append(f"  run-to-run: OK ({verdict.run_shas[0]})")
    else:
        lines.append("  run-to-run: DRIFT — renders differ:")
        for i, sha in enumerate(verdict.run_shas, start=1):
            lines.append(f"    run {i}: {sha}")
    if verdict.golden_sha is None:
        if verdict.run_to_run_ok:
            lines.append("  golden: none recorded — record this run with --record")
        else:
            lines.append("  golden: none recorded (fix run-to-run drift first)")
    elif verdict.golden_ok:
        lines.append(f"  golden: MATCH ({verdict.golden_sha})")
    else:
        lines.append("  golden: MISMATCH")
        lines.append(f"    expected: {verdict.golden_sha}")
        lines.append(f"    actual:   {verdict.run_shas[0]}")
    lines.append(f"  verdict: {'PASS' if verdict.ok else 'FAIL'}")
    return "\n".join(lines)
