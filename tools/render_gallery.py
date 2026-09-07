#!/usr/bin/env python3
"""High-resolution marketing gallery renderer (Epoch 22, item #89 — NON-OFFLINE).

Renders the curated matrix in :mod:`src.gallery` to real, rights-clean artifacts and stamps a
provenance **rights ledger** (``hydro-art/gallery-ledger@1``) with per-file sha256s. It adds no
render recipe of its own: each selection is dispatched through the offline contract layer
(:func:`src.endpoints.dispatch_endpoint`) using the four real renderer factories authored in
``tools/render_endpoint.py``. With ``--web-variants`` it also emits web-optimized derivatives
next to each full-resolution file (svg via SVGO, rasters downscaled via Pillow), degrading
gracefully when those optional tools are absent.

Discipline: lives OUTSIDE the offline suite (its renderers need GDAL + staged NAS data) and is
never imported by ``src/`` or ``tests/``. The curation, Rights gate, ledger, and coverage check
it relies on are all offline-tested in ``tests/test_gallery.py``. Per the Generation-1 roadmap,
the real render is exercised on the GDAL+NAS machine; the child-tool CLI flags in the renderer
bodies should be verified during that run.

Exit codes: EndpointError -> 1 (config/rights), acquisition/render failure -> 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.endpoints import EndpointError, dispatch_endpoint  # noqa: E402
from src.gallery import GALLERY_MATRIX, gallery_ledger, selection_request  # noqa: E402
from tools.render_endpoint import _renderers  # noqa: E402

WEB_MAX_PX = 2048  # longest edge for web-optimized raster derivatives


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _web_variant(full: Path) -> None:
    """Best-effort web-optimized derivative next to ``full`` (skips what it can't handle)."""
    fmt = full.suffix.lstrip(".").lower()
    try:
        if fmt == "svg":
            from src.optimize import SvgoOptimizer

            optimized = SvgoOptimizer().optimize(full.read_text())
            full.with_suffix(".web.svg").write_text(optimized)
        elif fmt in {"png", "tiff"}:
            from PIL import Image  # lazy: optional dependency

            with Image.open(full) as im:
                im.thumbnail((WEB_MAX_PX, WEB_MAX_PX))
                im.save(full.with_suffix(".web.png"), format="PNG")
        # pdf / gif / mp4: no web derivative here (handled downstream).
    except Exception as exc:  # optional tool missing / unsupported -> skip, don't fail the run
        warnings.warn(f"web variant skipped for {full.name}: {exc}", stacklevel=2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render the curated marketing gallery + ledger.")
    ap.add_argument(
        "--item", action="append", default=None,
        help="Render only these item_ids (repeatable); default is the whole matrix.",
    )
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--web-variants", action="store_true",
                    help="Also emit web-optimized derivatives beside full-res files.")
    args = ap.parse_args(argv)

    wanted = set(args.item) if args.item else None
    selections = [s for s in GALLERY_MATRIX if wanted is None or s.item_id in wanted]
    if not selections:
        print(f"error: no gallery items matched {sorted(wanted or [])}.", file=sys.stderr)
        return 1

    out_root = Path(args.out_dir or (REPO / "output" / "gallery"))
    out_root.mkdir(parents=True, exist_ok=True)

    checksums: dict[str, dict[str, str]] = {}
    try:
        for selection in selections:
            request = selection_request(selection)  # Rights gate
            item_dir = out_root / selection.item_id
            item_dir.mkdir(parents=True, exist_ok=True)
            result = dispatch_endpoint(request, renderers=_renderers(item_dir))
            checksums[selection.item_id] = {
                d.filename: (item_dir / d.filename).exists()
                and _sha256(item_dir / d.filename)
                for d in result.plan.items
            }
            if args.web_variants:
                for d in result.plan.items:
                    full = item_dir / d.filename
                    if full.exists():
                        _web_variant(full)
    except EndpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # acquisition / render failure
        print(f"render failed: {exc}", file=sys.stderr)
        return 2

    ledger = gallery_ledger(selections, checksums=checksums)
    ledger_path = out_root / "gallery-ledger.json"
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True))
    total = sum(len(a["deliverables"]) for a in ledger["assets"])
    print(f"wrote {len(ledger['assets'])} asset(s) / {total} deliverable(s) + "
          f"{ledger_path.name} to {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
