#!/usr/bin/env python3
"""Reproducibility release gate CLI (Epoch 23, item #92 — NON-SUITE).

Blocks the ``v1.0`` tag unless (1) the render-independent goldens recompute-match and (2) the
real double-render is byte-identical run-to-run and against golden. The pure fixture-match +
verdict aggregation live in the offline :mod:`src.release`; this wrapper adds the non-offline
double-render by shelling out to ``tools/verify_determinism.py`` (which needs GDAL + staged
data) once per requested region.

Modes:
- ``--offline-only``: run the fixture-match preflight only (no GDAL). Runnable anywhere; a
  green result means "goldens are consistent", not "release-ready".
- default: fixture-match **and** determinism. Pass ``--region`` (repeatable, optional
  ``--county``) for each region the release must prove deterministic.

Discipline: lives OUTSIDE the offline suite; imports ``src/`` + stdlib only. Never imported by
``src/`` or ``tests/``.

Exit codes: 0 = READY; 1 = BLOCKED (fixtures and/or determinism); 2 = usage error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.determinism import DeterminismVerdict, registry_key  # noqa: E402
from src.release import evaluate_release, format_verdict  # noqa: E402

PY = sys.executable


def _determinism_verdict(region: str, county: str | None, golden: str) -> DeterminismVerdict:
    """Run the real double-render for one region; a passing exit → a passing verdict."""
    key = registry_key(region, county)
    cmd = [PY, str(REPO / "tools" / "verify_determinism.py"), "--region", region,
           "--golden", golden]
    if county:
        cmd += ["--county", county]
    ok = subprocess.run(cmd, cwd=REPO, check=False).returncode == 0
    # The real sha comparison happens inside verify_determinism against the registry; here we
    # only carry its pass/fail into the aggregate verdict (run_shas are irrelevant to .ok).
    return DeterminismVerdict(
        key=key,
        run_shas=(),
        golden_sha=None,
        run_to_run_ok=ok,
        golden_ok=True if ok else False,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reproducibility release gate for v1.0.")
    ap.add_argument("--version", default="1.0.0", help="Release version being gated.")
    ap.add_argument("--offline-only", action="store_true",
                    help="Fixture-match preflight only (skip the real double-render).")
    ap.add_argument("--region", action="append", default=None,
                    help="Region to prove deterministic (repeatable).")
    ap.add_argument("--county", default=None, help="Optional county scope for --region.")
    ap.add_argument("--golden", default=str(REPO / "tests" / "fixtures" / "golden" / "registry.json"),
                    help="Determinism golden registry path.")
    args = ap.parse_args(argv)

    if args.offline_only:
        verdict = evaluate_release(args.version, require_determinism=False)
    else:
        if not args.region:
            print("error: --region is required unless --offline-only.", file=sys.stderr)
            return 2
        verdicts = [_determinism_verdict(r, args.county, args.golden) for r in args.region]
        verdict = evaluate_release(args.version, determinism_verdicts=verdicts)

    print(format_verdict(verdict))
    return 0 if verdict.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
