"""Fulfill a made-to-order county watershed print (roadmap #56-#57, Epoch 11.5).

Non-offline executor for the Revenue Validation fulfillment pack: it turns a
validated customer order into the exact set of deliverables the sale promised —
title/subtitle/attribution stamped in, print-ready rasters at the ordered size, an
optional editable SVG and commercial-license doc — plus a provenance manifest so a
re-order regenerates byte-for-byte.

The reproducible, rights-compliant *logic* lives in the offline-tested
:mod:`src.fulfillment` (order validation, title/attribution rules, deliverable plan,
manifest). This tool is the thin, heavy driver: it reuses the shared county-clip art
recipe in :mod:`tools.render_common` and imports GIS libs eagerly, so — like every
``tools/`` script — it runs only in a full (non-offline) environment and is outside
the test suite.

    python tools/fulfill_order.py --order order.json
    python tools/fulfill_order.py --order-id ORD-1001 --region Washington \
        --county Clark --style neon-basin --size 18x24 --formats png pdf \
        --add-ons svg commercial_license --huc4 1708

``order.json`` mirrors the CLI flags (order_id/region/county/style/size/formats/
add_ons/title/subtitle/buyer_ref).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.counties import state_fips_for_region  # noqa: E402
from src.fulfillment import (  # noqa: E402
    ORDER_STYLES,
    SIZES,
    build_order,
    deliverable_plan,
    fulfillment_manifest,
    title_block,
)
from tools.render_common import (  # noqa: E402
    assign_subwatersheds,
    build_inputs,
    clip_flowlines,
    flow_scaled_widths,
    load_county,
    rasterize,
    render_art_svg,
)


def _load_payload(args) -> dict:
    if args.order:
        return json.loads(Path(args.order).read_text())
    return {
        "order_id": args.order_id,
        "region": args.region,
        "county": args.county,
        "style": args.style,
        "size": args.size,
        "formats": args.formats,
        "add_ons": args.add_ons or [],
        "title": args.title,
        "subtitle": args.subtitle,
        "buyer_ref": args.buyer_ref,
    }


def _stamp_title(svg: str, tb: dict, width_px: int, height_px: int) -> str:
    """Append a title / subtitle / source-credit text block to the SVG."""
    x = int(width_px * 0.04)
    y0 = int(height_px * 0.94)
    fs_title = max(24, int(width_px * 0.035))
    fs_sub = int(fs_title * 0.5)
    fs_credit = max(12, int(fs_title * 0.28))
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    block = (
        f'<g id="title-block" font-family="Helvetica,Arial,sans-serif" fill="#e8eef6">'
        f'<text x="{x}" y="{y0}" font-size="{fs_title}" font-weight="700">{esc(tb["title"])}</text>'
        f'<text x="{x}" y="{y0 + fs_sub + 6}" font-size="{fs_sub}" fill="#93a1b5">{esc(tb["subtitle"])}</text>'
        f'<text x="{x}" y="{y0 + fs_sub + fs_credit + 14}" font-size="{fs_credit}" fill="#5c6b7d">'
        f'Source: {esc(tb["credit"])}</text>'
        f'</g>'
    )
    return svg.replace("</svg>", block + "</svg>", 1)


def _license_text(order, tb) -> str:
    return (
        "COMMERCIAL LICENSE\n"
        "==================\n\n"
        f"Order: {order.order_id}\n"
        f"Artwork: {tb['title']} — {tb['subtitle']}\n"
        f"Licensee: {order.buyer_ref or '(purchaser of record)'}\n\n"
        "Grant: a non-exclusive, worldwide, perpetual license to reproduce, display, "
        "and sell physical prints of this artwork.\n\n"
        f"Data provenance: {tb['credit']}. Underlying hydrography is U.S. federal "
        "public-domain data (USGS NHDPlus HR / NHD / WBD).\n"
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _render_svg(order, width_px: int, huc4: str, min_order: int) -> str:
    """Neon-basin county clip via the shared art recipe -> SVG string."""
    state_fp = state_fips_for_region(order.region)
    print(f"loading {order.county} County (STATEFP {state_fp}) ...")
    boundary = load_county(state_fp, order.county)
    print(f"clipping flowlines from HUC4 {huc4} (min_order={min_order}) ...")
    geoms, orders, flows, _basins = clip_flowlines(boundary, huc4, min_order)
    if not geoms:
        raise SystemExit("No flowlines fell inside the county boundary.")
    codes, _names = assign_subwatersheds(geoms, 10)
    geometries, segment_colors, watersheds, _cc = build_inputs(geoms, codes)
    widths, base_units, _upp, _qmax = flow_scaled_widths(
        geometries, flows, width_px, 0.6, 5.0
    )
    return render_art_svg(geometries, segment_colors, watersheds, base_units, widths)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--order", help="Path to an order JSON (mirrors the flags).")
    ap.add_argument("--order-id")
    ap.add_argument("--region")
    ap.add_argument("--county")
    ap.add_argument("--style", default="neon-basin")
    ap.add_argument("--size", default="18x24")
    ap.add_argument("--formats", nargs="+", default=["png", "pdf"])
    ap.add_argument("--add-ons", nargs="*", default=[])
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--buyer-ref")
    ap.add_argument("--huc4", default="1708",
                    help="HUC4 GDB to scan (Clark County, WA = 1708).")
    ap.add_argument("--min-order", type=int, default=1)
    ap.add_argument("--out-dir", default=None,
                    help="Deliverables dir (default output/orders/<order_id>).")
    args = ap.parse_args()

    order = build_order(_load_payload(args))
    tb = title_block(order)
    plan = deliverable_plan(order)

    width_px, height_px = SIZES[order.size].px

    out_dir = Path(args.out_dir or f"output/orders/{order.order_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    style = ORDER_STYLES[order.style]
    if style.renderer != "pipeline":
        raise SystemExit(
            f"Style {order.style!r} uses the {style.renderer!r} renderer, which is not "
            "yet wired into the county fulfillment path — use 'neon-basin' for now."
        )

    svg = _stamp_title(_render_svg(order, width_px, args.huc4, args.min_order),
                       tb, width_px, height_px)
    master_svg = out_dir / f"{order.order_id}_master.svg"
    master_svg.write_text(svg)
    print(f"rendered master SVG: {master_svg} ({len(svg)} bytes)")

    checksums: dict[str, str] = {}
    for d in plan.items:
        dest = out_dir / d.filename
        if d.kind == "print" and d.fmt == "png":
            rasterize(str(master_svg), str(dest), width_px, 5.0)
        elif d.kind == "print" and d.fmt == "pdf":
            # Pin SOURCE_DATE_EPOCH so cairo/librsvg stamps a fixed PDF
            # CreationDate/ModDate — otherwise the wall-clock timestamp makes a
            # re-order's PDF (and its sha256 in the manifest) differ each run.
            subprocess.run(
                ["rsvg-convert", "-f", "pdf", "-w", str(width_px),
                 "-o", str(dest), str(master_svg)],
                check=True,
                env={**os.environ, "SOURCE_DATE_EPOCH": "0"},
            )
        elif d.kind == "vector":
            dest.write_text(svg)
        elif d.kind == "license":
            dest.write_text(_license_text(order, tb))
        checksums[d.filename] = _sha256(dest)
        print(f"  wrote {d.filename} ({d.kind}/{d.fmt}) sha256={checksums[d.filename][:12]}…")

    manifest = fulfillment_manifest(order, plan, checksums=checksums)
    manifest_path = out_dir / f"{order.order_id}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {manifest_path}")
    print(f"DONE — {len(plan.items)} deliverable(s) in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
