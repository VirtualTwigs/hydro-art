#!/usr/bin/env python3
"""Offline coverage gate & reporting (Epoch 20, item #84 — NON-SUITE).

Thin wrapper that runs the offline test suite under ``coverage`` and prints a per-module
report, scoped to ``src/`` by the ``[tool.coverage.*]`` config in ``pyproject.toml``. It is
the repeatable "base of the pyramid" gate: report-only by default, or pass ``--fail-under N``
to make it exit non-zero when total coverage drops below ``N`` (CI wiring enforces a number
in Epoch 23).

Discipline: lives OUTSIDE the offline suite and imports only stdlib (it shells out to the
project's own interpreter), so it is never imported by ``src/`` or ``tests/``.

Exit codes: 0 = suite passed and (if given) coverage >= threshold; 1 = suite failed;
2 = suite passed but coverage below ``--fail-under``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=REPO, check=False).returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the offline suite under coverage.")
    ap.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit non-zero (2) if total coverage is below this percentage.",
    )
    ap.add_argument(
        "--quiet", action="store_true", help="Run pytest quietly (-q)."
    )
    args = ap.parse_args(argv)

    pytest_cmd = [PY, "-m", "coverage", "run", "-m", "pytest"]
    if args.quiet:
        pytest_cmd.append("-q")
    if _run(pytest_cmd) != 0:
        print("coverage_report: test suite failed.", file=sys.stderr)
        return 1

    report_cmd = [PY, "-m", "coverage", "report", "--sort=cover"]
    if args.fail_under is not None:
        report_cmd.append(f"--fail-under={args.fail_under:g}")
    rc = _run(report_cmd)
    if rc != 0 and args.fail_under is not None:
        print(
            f"coverage_report: total coverage below --fail-under={args.fail_under:g}.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
