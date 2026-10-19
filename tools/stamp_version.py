#!/usr/bin/env python3
"""Stamp web/version.json with the pyproject.toml version + current git short hash.

Run before deploy:  python tools/stamp_version.py
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    # Read version from pyproject.toml
    pyproject = (ROOT / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    version = m.group(1) if m else "0.0.0"

    # Read git short hash
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=ROOT,
    )
    build = result.stdout.strip() or "unknown"

    out = ROOT / "web" / "version.json"
    out.write_text(json.dumps({"version": version, "build": build}) + "\n")
    print(f"Stamped {out}: v{version} · {build}")


if __name__ == "__main__":
    main()
