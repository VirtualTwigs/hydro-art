#!/usr/bin/env python3
"""Flagship real-data e2e harness — one county, ALL FOUR endpoints (Epoch 21, #86; NON-OFFLINE).

The headline production proof: take one small public-domain county and produce every
deliverable — digital image (SVG+PNG), animation (GIF/MP4), print image (raster), and
watershed report — through the same offline contract layer (:mod:`src.endpoints`), then stamp
one **combined provenance manifest** (``hydro-art/e2e-manifest@1``) and, optionally, run a
**double-render determinism check** over the real artifact bytes.

It adds no render recipe of its own: it reuses the four real renderer factories authored in
``tools/render_endpoint.py`` (each wrapping an existing GIS entry point) and the pure router in
:func:`src.endpoints.dispatch_endpoint`. Discipline: lives OUTSIDE the offline suite (its
renderers need GDAL + staged NAS data) and is never imported by ``src/`` or ``tests/``. The
routing/validation/plan/manifest/Rights-gate it relies on are all offline-tested in
``tests/test_endpoints.py`` and ``tests/test_endpoints_e2e.py`` via fakes. Per the
Generation-1 roadmap decision, the real four-artifact run is exercised on the GDAL+NAS machine;
the default parameters below target Wahkiakum County, WA (the golden-fixture county).

Exit codes: EndpointError -> 1 (config), acquisition/render failure -> 2, determinism drift -> 3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.endpoints import (  # noqa: E402
    ENDPOINTS,
    EndpointError,
    build_endpoint_request,
    combined_manifest,
    dispatch_endpoint,
)
from tools.render_endpoint import _renderers  # noqa: E402


def _build_requests(args) -> list:
    """Build one validated request per endpoint from the shared identity + per-endpoint params."""
    extras = {
        "digital_image": {},
        "animation": {"year": args.year},
        "print_image": {"size": args.size},
        "report": {"huc": args.huc},
    }
    requests = []
    for endpoint in ENDPOINTS:
        payload = {
            "request_id": f"{args.request_id}-{endpoint}",
            "region": args.region,
            "county": args.county,
            "endpoint": endpoint,
            "style": args.style,
            **extras[endpoint],
        }
        requests.append(build_endpoint_request(payload))
    return requests


def _render_all(requests, out_dir: Path) -> list:
    """Dispatch every request through its real renderer into ``out_dir``; return results."""
    out_dir.mkdir(parents=True, exist_ok=True)
    renderers = _renderers(out_dir)
    return [dispatch_endpoint(req, renderers=renderers) for req in requests]


def _file_shas(manifest: dict) -> dict[str, str]:
    """Flatten a combined manifest to ``{filename: sha256}`` across all endpoints."""
    shas: dict[str, str] = {}
    for sub in manifest["endpoints"].values():
        for d in sub["deliverables"]:
            shas[d["filename"]] = d["sha256"]
    return shas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Render all four production endpoints for one county + combined manifest."
    )
    ap.add_argument("--region", default="Washington")
    ap.add_argument("--county", default="Wahkiakum")
    ap.add_argument("--style", default="neon-basin")
    ap.add_argument("--request-id", default=None)
    ap.add_argument("--year", type=int, default=2015)
    ap.add_argument("--size", default="18x24")
    ap.add_argument("--huc", default="17080003")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument(
        "--check-determinism",
        action="store_true",
        help="Render the full set twice and compare real artifact sha256s.",
    )
    args = ap.parse_args(argv)
    if args.request_id is None:
        args.request_id = f"E2E-{args.region}-{args.county}".replace(" ", "-")

    try:
        requests = _build_requests(args)
    except EndpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    base = Path(args.out_dir or (REPO / "output" / "e2e" / args.request_id))

    try:
        results = _render_all(requests, base / "run1" if args.check_determinism else base)
        manifest = combined_manifest(results)
        if args.check_determinism:
            results2 = _render_all(requests, base / "run2")
            manifest2 = combined_manifest(results2)
            if _file_shas(manifest) != _file_shas(manifest2):
                print("determinism DRIFT: re-render produced different bytes.", file=sys.stderr)
                return 3
    except EndpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # acquisition / render failure
        print(f"render failed: {exc}", file=sys.stderr)
        return 2

    out_dir = base / "run1" if args.check_determinism else base
    manifest_path = out_dir / f"{args.request_id}_e2e_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    total = sum(len(sub["deliverables"]) for sub in manifest["endpoints"].values())
    det = " (determinism OK)" if args.check_determinism else ""
    print(
        f"wrote {len(manifest['endpoints'])} endpoints / {total} deliverable(s) + "
        f"{manifest_path.name} to {out_dir}{det}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
