#!/usr/bin/env python3
"""Changelog builder CLI (Epoch 23, item #93 — NON-SUITE).

Reads the Agent-OS roadmap, parses its epochs via the pure/offline :mod:`src.changelog`, and
writes a deterministic ``CHANGELOG.md`` for the ``v1.0`` release. The parsing/rendering is
offline-tested in ``tests/test_changelog.py``; this wrapper only does the fs read/write.

Discipline: lives OUTSIDE the offline suite; imports ``src/`` + stdlib only.

Exit codes: 0 = wrote (or, with ``--check``, up to date); 1 = ``--check`` found drift.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.changelog import parse_roadmap_epochs, render_changelog  # noqa: E402

DEFAULT_NOTES = [
    "Generation 1 production release: four stable customer endpoints (digital image, animation, "
    "print image, watershed report), a full test pyramid, a flagship all-four-endpoints e2e "
    "proof, a rights-clean marketing gallery, and a reproducibility release gate.",
    "Default 2D pipeline output is byte-for-byte deterministic; only public-domain sources "
    "(USGS NHDPlus HR / NHD / WBD, nClimGrid) ship in any sellable asset.",
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate CHANGELOG.md from the roadmap epochs.")
    ap.add_argument("--version", default="1.0.0", help="Release version.")
    ap.add_argument("--date", default="2026-09-06", help="Release date (YYYY-MM-DD).")
    ap.add_argument("--roadmap", default=str(REPO / "agent-os" / "product" / "roadmap.md"),
                    help="Roadmap Markdown to parse.")
    ap.add_argument("--out", default=str(REPO / "CHANGELOG.md"), help="Output path.")
    ap.add_argument("--check", action="store_true",
                    help="Compare generated output to --out without writing; exit 1 on drift.")
    args = ap.parse_args(argv)

    epochs = parse_roadmap_epochs(Path(args.roadmap).read_text(encoding="utf-8"))
    content = render_changelog(args.version, args.date, epochs, notes=DEFAULT_NOTES)

    out = Path(args.out)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != content:
            print(f"build_changelog: {out} is out of date (run without --check).", file=sys.stderr)
            return 1
        print(f"build_changelog: {out} is up to date.")
        return 0

    out.write_text(content, encoding="utf-8")
    print(f"wrote {out} ({len(epochs)} epoch(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
