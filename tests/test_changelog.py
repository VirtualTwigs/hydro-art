"""Tests for the pure/offline changelog generator (Epoch 23, #93).

``src.changelog`` is pure string/data transforms (stdlib only) over structured epoch data or
roadmap Markdown → a deterministic CHANGELOG document. No fs/network in ``src`` — the file
reads live in ``tools/build_changelog.py``.
"""

from __future__ import annotations

from src.changelog import Epoch, parse_roadmap_epochs, render_changelog

SAMPLE_ROADMAP = """
# Generation 1 — Production Release

## Epoch 22 — High-resolution marketing gallery · proposed

Curated, rights-clean examples.

88. [ ] Curated style matrix — Select regions × styles × endpoints that show the range. `S`
89. [ ] High-res render & export — Render each at marketing resolution. `M`

## Epoch 23 — Release packaging, CI & reproducibility gate · proposed

Turn green suite into a tagged v1.0.

91. [ ] CI for the full test pyramid — Run offline unit+integration+e2e. `M`
92. [ ] Reproducibility release gate — Block the release tag. `S`
93. [ ] Version, changelog & distribution packaging — Tag v1.0. `M`
"""


def test_parse_roadmap_epochs_extracts_epochs_and_items():
    epochs = parse_roadmap_epochs(SAMPLE_ROADMAP)
    assert [e.number for e in epochs] == ["22", "23"]
    assert epochs[0].title == "High-resolution marketing gallery"
    assert [i[0] for i in epochs[0].items] == ["88", "89"]
    assert epochs[0].items[0][1] == "Curated style matrix"
    assert [i[0] for i in epochs[1].items] == ["91", "92", "93"]
    assert epochs[1].title == "Release packaging, CI & reproducibility gate"


def test_render_changelog_is_deterministic_and_byte_identical():
    epochs = parse_roadmap_epochs(SAMPLE_ROADMAP)
    a = render_changelog("1.0.0", "2026-09-06", epochs)
    b = render_changelog("1.0.0", "2026-09-06", epochs)
    assert a == b
    assert a.startswith("# Changelog")
    assert "## v1.0.0 — 2026-09-06" in a
    assert "High-resolution marketing gallery" in a
    assert "#88" in a and "#93" in a
    assert a.endswith("\n")


def test_render_changelog_accepts_notes():
    epochs = [Epoch(number="1", title="Foundations", items=(("1", "Do the thing"),))]
    out = render_changelog("1.0.0", "2026-09-06", epochs, notes=["Public-domain sources only."])
    assert "Public-domain sources only." in out
    assert "Foundations" in out


def test_roundtrip_parse_then_render_stable():
    epochs = parse_roadmap_epochs(SAMPLE_ROADMAP)
    once = render_changelog("1.0.0", "2026-09-06", epochs)
    twice = render_changelog("1.0.0", "2026-09-06", parse_roadmap_epochs(SAMPLE_ROADMAP))
    assert once == twice
