"""Regression guards for direct-run `tools/` scripts (corrections roadmap Track C2).

These tests are pure/offline: they read tool source as *text* and spawn subprocesses.
They never import the heavy `tools/` modules at collection time (that would drag GDAL/
numpy into the offline suite), so they run in the standard `pytest` run and in CI.

Guards:
- C2.1 — every tool that runs as ``__main__`` and imports ``src`` puts the repo root on
  ``sys.path`` *before* that import, so ``python tools/x.py`` works (not only ``-m``).
- C2.2 — the configured linter ``ruff`` is declared in the ``dev`` optional-dependencies.
- C2.3 — the watershed-report caches are anchored to a REPO root, not the CWD.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"

_MAIN_RE = re.compile(r'if __name__ == ["\']__main__["\']')
_SRC_IMPORT_RE = re.compile(r"^\s*(?:from src[.\s]|import src\b)", re.MULTILINE)
_SHIM_RE = re.compile(r"^\s*sys\.path\.insert", re.MULTILINE)


def _first_line(pattern: re.Pattern[str], text: str) -> int | None:
    """1-based line number of the first ``pattern`` match, or ``None``."""
    m = pattern.search(text)
    if m is None:
        return None
    return text.count("\n", 0, m.start()) + 1


def _direct_run_src_tools() -> list[Path]:
    """Tools that define ``__main__`` and import ``src`` (need the shim)."""
    out = []
    for path in sorted(TOOLS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if _MAIN_RE.search(text) and _SRC_IMPORT_RE.search(text):
            out.append(path)
    return out


def test_direct_run_tools_have_src_import_shim() -> None:
    """C2.1 — a ``sys.path.insert`` must precede the first ``src`` import."""
    offenders = []
    for path in _direct_run_src_tools():
        text = path.read_text(encoding="utf-8")
        src_line = _first_line(_SRC_IMPORT_RE, text)
        shim_line = _first_line(_SHIM_RE, text)
        if shim_line is None or (src_line is not None and shim_line > src_line):
            offenders.append(path.name)
    assert not offenders, (
        "these direct-run tools import `src` with no sys.path shim before it "
        f"(ModuleNotFoundError when run as `python tools/<x>.py`): {offenders}"
    )


@pytest.mark.parametrize("rel", ["report_common.py", "render_state_yoy.py"])
def test_report_caches_are_repo_anchored(rel: str) -> None:
    """C2.3 — no bare CWD-relative cache/figure literal; paths reference REPO."""
    text = (TOOLS / rel).read_text(encoding="utf-8")
    bare = re.findall(
        r'Path\(\s*f?["\'](?:notebooks|output)/[^"\']*["\']\s*\)', text
    )
    assert not bare, (
        f"{rel} has CWD-relative cache/figure literals (break under nbconvert): {bare}"
    )
    assert "REPO" in text, f"{rel} should anchor its paths to a REPO constant"


def test_ruff_pinned_in_dev_extras() -> None:
    """C2.2 — the configured linter is declared in the dev optional-dependencies."""
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    assert any(req.split()[0].split(">")[0].split("=")[0].strip() == "ruff"
               for req in dev), f"ruff missing from dev extras: {dev}"


@pytest.mark.parametrize("tool", ["detect_unfinished.py", "update_status.py"])
def test_pure_tools_run_as_script_from_foreign_cwd(tool: str, tmp_path: Path) -> None:
    """C2.1 e2e — direct-run from a foreign CWD works (the exact reported bug).

    Only the two GDAL-free tools (`src.unfinished` / `src.status`, stdlib-only) are
    exercised as subprocesses; the rest are covered by the static invariant above.
    """
    result = subprocess.run(
        [sys.executable, str(TOOLS / tool), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "ModuleNotFoundError" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
