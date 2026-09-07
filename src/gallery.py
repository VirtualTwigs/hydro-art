"""Curated marketing gallery + rights ledger (Epoch 22, items #88-90).

Fourth epoch of Generation 1. Defines the **curated style matrix** — a small, rights-clean set
of examples spanning every region, both public-domain styles, and all four endpoints — and a
pure/deterministic **rights ledger** describing each asset's provenance (source version,
attribution, planned deliverables, per-file checksum, sellable flag).

Pure and offline: imports only stdlib + :mod:`src.endpoints` (contract layer + Rights gate) and
:mod:`src.fulfillment` (value objects, ``attribution_line``, ``DEFAULT_SOURCES``). No GDAL /
numpy / network / datasets, and nothing enters ``PIPELINE_STAGES``. The real high-resolution
image bytes are produced by the non-offline ``tools/render_gallery.py`` harness (deferred to the
GDAL+NAS machine); this module only curates + describes. Identical inputs -> byte-identical
(``sort_keys``) ledger.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.endpoints import (
    EndpointError,
    EndpointRequest,
    build_endpoint_request,
    endpoint_plan,
)
from src.fulfillment import DEFAULT_SOURCES, attribution_line

__all__ = [
    "GallerySelection",
    "GALLERY_MATRIX",
    "GALLERY_SCHEMA",
    "selection_request",
    "gallery_ledger",
]

GALLERY_SCHEMA = "hydro-art/gallery-ledger@1"


@dataclass(frozen=True)
class GallerySelection:
    """One curated marketing example: an endpoint deliverable + why it shows the range."""

    item_id: str
    region: str
    county: str
    style: str
    endpoint: str
    rationale: str
    size: str | None = None
    year: int | None = None
    huc: str | None = None
    formats: tuple[str, ...] | None = None


# The curated matrix — every region, both public-domain styles, all four endpoints.
GALLERY_MATRIX: tuple[GallerySelection, ...] = (
    GallerySelection(
        item_id="or-neon-digital",
        region="Oregon",
        county="Deschutes",
        style="neon-basin",
        endpoint="digital_image",
        rationale="Flagship neon-basin river art (SVG + PNG) — the signature look.",
    ),
    GallerySelection(
        item_id="wa-elev-print",
        region="Washington",
        county="Wahkiakum",
        style="elevation-tint",
        endpoint="print_image",
        size="24x36",
        rationale="Archival hypsometric terrain print at gallery size (24x36).",
    ),
    GallerySelection(
        item_id="ca-neon-animation",
        region="California",
        county="Shasta",
        style="neon-basin",
        endpoint="animation",
        year=2015,
        rationale="Year-in-motion seasonality — flow disaggregated across the calendar year.",
    ),
    GallerySelection(
        item_id="id-elev-digital",
        region="Idaho",
        county="Blaine",
        style="elevation-tint",
        endpoint="digital_image",
        rationale="Elevation-mono treatment carried to a fourth region — range across styles.",
    ),
    GallerySelection(
        item_id="wa-neon-report",
        region="Washington",
        county="Wahkiakum",
        style="neon-basin",
        endpoint="report",
        huc="17080003",
        rationale="Watershed analytics report — the data-story deliverable.",
    ),
)


def selection_request(selection: GallerySelection) -> EndpointRequest:
    """Validate a curated selection into an :class:`EndpointRequest` (Rights gate enforced).

    Delegates to :func:`src.endpoints.build_endpoint_request`, so an invalid or non-sellable
    (PRISM-derived) selection raises :class:`EndpointError` here rather than at render time.
    """
    payload = {
        "request_id": selection.item_id,
        "region": selection.region,
        "county": selection.county,
        "endpoint": selection.endpoint,
        "style": selection.style,
        "formats": list(selection.formats) if selection.formats else None,
        "size": selection.size,
        "year": selection.year,
        "huc": selection.huc,
    }
    return build_endpoint_request(payload)


def gallery_ledger(
    selections=GALLERY_MATRIX, *, checksums=None, sources=DEFAULT_SOURCES
) -> dict:
    """A per-asset rights + provenance ledger for the curated gallery.

    Schema ``hydro-art/gallery-ledger@1``. Each asset carries its identity, rationale, a
    ``sellable`` flag (True — every selection passed the Rights gate in
    :func:`selection_request`), and its planned deliverables. ``checksums`` (optional) maps
    ``item_id -> {filename: sha256}`` and, when given, must cover each asset's plan **exactly**
    (missing/extra -> :class:`EndpointError`); when absent, ``sha256`` is ``None`` (the render-
    independent skeleton). Assets are sorted by ``item_id`` and the document is byte-identical
    under ``json.dumps(sort_keys=True)`` for equal inputs.
    """
    assets = []
    for selection in sorted(selections, key=lambda s: s.item_id):
        request = selection_request(selection)  # Rights gate
        plan = endpoint_plan(request)
        item_sums = None if checksums is None else (checksums.get(selection.item_id) or {})
        if checksums is not None:
            planned = {d.filename for d in plan.items}
            provided = set(item_sums)
            if planned != provided:
                missing = sorted(planned - provided)
                extra = sorted(provided - planned)
                raise EndpointError(
                    f"Checksum coverage mismatch for {selection.item_id!r} "
                    f"(missing={missing}, unexpected={extra})."
                )
        deliverables = [
            {
                "filename": d.filename,
                "kind": d.kind,
                "fmt": d.fmt,
                "width_px": d.width_px,
                "height_px": d.height_px,
                "sha256": item_sums[d.filename] if item_sums else None,
            }
            for d in plan.items
        ]
        assets.append(
            {
                "item_id": selection.item_id,
                "region": selection.region,
                "county": selection.county,
                "style": selection.style,
                "endpoint": selection.endpoint,
                "rationale": selection.rationale,
                "sellable": True,
                "deliverables": deliverables,
            }
        )
    return {
        "schema": GALLERY_SCHEMA,
        "attribution": attribution_line(sources),
        "sources": [{"name": s.name, "version": s.version} for s in sources],
        "assets": assets,
    }
