#!/usr/bin/env python3
"""Single-dispatch endpoint executor (Epoch 19, item #80 — NON-OFFLINE).

Thin CLI over the offline contract layer in :mod:`src.endpoints`: validate a request,
inject the four **real** renderers into :func:`src.endpoints.dispatch_endpoint`, and
write a provenance manifest sidecar next to the produced artifacts. It adds no render
recipe of its own — each renderer wraps an existing entry point (``build.py`` for the
2D digital image, ``tools/render_monthly.py`` / ``render_state_yoy.py`` for animation,
``tools/render_terrain_print.py`` for the print image, ``tools/build_watershed_report.py``
for the report) and reuses ``tools/render_common.py``.

Discipline: this file lives OUTSIDE the offline suite (imports GIS-backed tools that need
GDAL + staged datasets) and is never imported by ``src/`` or ``tests/``. The routing,
validation, plan, manifest, and Rights gate it relies on are all offline-tested in
``tests/test_endpoints.py`` via injected fakes. Per the Generation-1 roadmap decision, the
real four-artifact run is exercised in Epoch 21 against Wahkiakum County, WA on the
GDAL+NAS machine; the renderer bodies below are authored here and validated there.

Exit codes mirror the pipeline taxonomy: EndpointError -> 1 (config), acquisition/render
failure -> 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from src.endpoints import (
    ENDPOINTS,
    EndpointError,
    build_endpoint_request,
    dispatch_endpoint,
)

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str]) -> None:
    """Run a child renderer, surfacing failures as an acquisition/render error."""
    proc = subprocess.run(cmd, cwd=REPO, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"renderer failed ({proc.returncode}): {' '.join(cmd)}")


def _finalize(produced: dict[str, Path], out_dir: Path, plan) -> dict[str, str]:
    """Copy each produced file to its planned filename and return sha256s.

    ``produced`` maps output format -> the file a child renderer actually wrote. Every
    planned deliverable must have a matching produced file (the manifest's coverage
    check will otherwise reject the run).
    """
    checksums: dict[str, str] = {}
    for d in plan.items:
        src = produced.get(d.fmt)
        if src is None or not src.exists():
            raise RuntimeError(f"renderer did not produce a {d.fmt!r} artifact for {d.filename}")
        dest = out_dir / d.filename
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        checksums[d.filename] = _sha256(dest)
    return checksums


# --- real renderers (authored; executed on the GDAL+NAS machine) -----------
#
# Each returns {filename: sha256} for the plan. Child-tool CLI flags reflect the current
# entry points; verify/adjust during the Epoch 21 real run against Wahkiakum County.

def _render_digital(out_dir: Path):
    def renderer(request, plan):
        _run([
            PY, "build.py", "--region", request.region, "--county", request.county,
            "--palette", "neon", "--glow", "--output", "svg", "png",
            "--output-dir", str(out_dir),
        ])
        produced = {"svg": out_dir / f"{request.county}.svg",
                    "png": out_dir / f"{request.county}.png"}
        return _finalize(produced, out_dir, plan)
    return renderer


def _render_animation(out_dir: Path):
    def renderer(request, plan):
        cmd = [PY, "tools/render_state_yoy.py", "--region", request.region,
               "--county", request.county, "--out-dir", str(out_dir)]
        if request.year is not None:
            cmd += ["--year", str(request.year)]
        _run(cmd)
        produced = {"gif": out_dir / f"{request.county}.gif",
                    "mp4": out_dir / f"{request.county}.mp4"}
        return _finalize(produced, out_dir, plan)
    return renderer


def _render_print(out_dir: Path):
    def renderer(request, plan):
        _run([PY, "tools/render_terrain_print.py", "--region", request.region,
              "--county", request.county, "--size", request.size or "18x24",
              "--out-dir", str(out_dir)])
        stem = request.county
        produced = {"png": out_dir / f"{stem}.png", "pdf": out_dir / f"{stem}.pdf",
                    "tiff": out_dir / f"{stem}.tiff"}
        return _finalize(produced, out_dir, plan)
    return renderer


def _render_report(out_dir: Path):
    def renderer(request, plan):
        _run([PY, "tools/build_watershed_report.py", "--region", request.region,
              "--huc", request.huc or "", "--out-dir", str(out_dir)])
        produced = {"html": out_dir / f"{request.huc}.html",
                    "png": out_dir / f"{request.huc}.png"}
        return _finalize(produced, out_dir, plan)
    return renderer


def _renderers(out_dir: Path) -> dict:
    return {
        "digital_image": _render_digital(out_dir),
        "animation": _render_animation(out_dir),
        "print_image": _render_print(out_dir),
        "report": _render_report(out_dir),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render one production endpoint deliverable.")
    ap.add_argument("--request-id", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--county", required=True)
    ap.add_argument("--endpoint", required=True, choices=ENDPOINTS)
    ap.add_argument("--style", default="neon-basin")
    ap.add_argument("--formats", nargs="*", default=None)
    ap.add_argument("--size", default=None)
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--huc", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    try:
        request = build_endpoint_request({
            "request_id": args.request_id,
            "region": args.region,
            "county": args.county,
            "endpoint": args.endpoint,
            "style": args.style,
            "formats": args.formats,
            "size": args.size,
            "year": args.year,
            "huc": args.huc,
        })
    except EndpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir or (REPO / "output" / "endpoints" / args.request_id))
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = dispatch_endpoint(request, renderers=_renderers(out_dir))
    except EndpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # acquisition / render failure
        print(f"render failed: {exc}", file=sys.stderr)
        return 2

    manifest_path = out_dir / f"{request.request_id}_manifest.json"
    manifest_path.write_text(json.dumps(result.manifest, indent=2, sort_keys=True))
    print(f"wrote {len(result.plan.items)} deliverable(s) + {manifest_path.name} to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
