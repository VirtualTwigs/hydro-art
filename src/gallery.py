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
    "GALLERY_MATRIX",
    "GALLERY_SCHEMA",
    "GallerySelection",
    "gallery_ledger",
    "selection_request",
]

GALLERY_SCHEMA = "hydro-art/gallery-ledger@1"


@dataclass(frozen=True)
class GallerySelection:
    """One curated marketing example: an endpoint deliverable + why it shows the range."""

    item_id: str
    region: str
    county: str | None
    style: str
    endpoint: str
    rationale: str
    size: str | None = None
    year: int | None = None
    huc: str | None = None
    formats: tuple[str, ...] | None = None


# The curated matrix — spanning regions, styles, and all four endpoints.
GALLERY_MATRIX: tuple[GallerySelection, ...] = (
    # ── Flagship pieces (original 6) ─────────────────────────────────────
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
    GallerySelection(
        item_id="conus-neon-hero",
        region="CONUS",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Continental hero — every major river basin in the contiguous US.",
    ),
    # ── State-level neon digital images ───────────────────────────────────
    GallerySelection(
        item_id="wa-neon-state",
        region="Washington",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Full Washington state neon-basin — the original flagship state.",
    ),
    GallerySelection(
        item_id="or-neon-state",
        region="Oregon",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Oregon state neon — Pacific Northwest companion piece.",
    ),
    GallerySelection(
        item_id="tx-neon-state",
        region="Texas",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Texas state neon — largest contiguous US state by river miles.",
    ),
    GallerySelection(
        item_id="ks-neon-state",
        region="Kansas",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Kansas state neon — Great Plains watershed structure.",
    ),
    GallerySelection(
        item_id="hi-neon-state",
        region="Hawaii",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Hawaii neon — island volcanic hydrology, unique among states.",
    ),
    GallerySelection(
        item_id="de-neon-state",
        region="Delaware",
        county=None,
        style="neon-basin",
        endpoint="digital_image",
        rationale="Delaware neon — compact Atlantic seaboard state.",
    ),
    # ── State-level elevation digital images ──────────────────────────────
    GallerySelection(
        item_id="wa-elev-state",
        region="Washington",
        county=None,
        style="elevation-tint",
        endpoint="digital_image",
        rationale="Washington elevation — Cascades summit-to-sea hypsometric gradient.",
    ),
    GallerySelection(
        item_id="ca-elev-state",
        region="California",
        county=None,
        style="elevation-tint",
        endpoint="digital_image",
        rationale="California elevation peak — Sierra Nevada headwaters white-to-blue.",
    ),
    GallerySelection(
        item_id="id-elev-state",
        region="Idaho",
        county=None,
        style="elevation-tint",
        endpoint="digital_image",
        rationale="Idaho elevation peak — mountainous Salmon River country.",
    ),
    GallerySelection(
        item_id="mn-elev-state",
        region="Minnesota",
        county=None,
        style="elevation-tint",
        endpoint="digital_image",
        rationale="Minnesota elevation — subtle Great Plains-to-Boundary Waters gradient.",
    ),
    # ── Cream palette state maps ─────────────────────────────────────────
    GallerySelection(
        item_id="ia-cream-state",
        region="Iowa",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Iowa cream — warm earth-tone palette on ivory, first cream render.",
    ),
    GallerySelection(
        item_id="co-cream-state",
        region="Colorado",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Colorado cream poster — Rocky Mountain headwaters in earth tones.",
    ),
    GallerySelection(
        item_id="ga-cream-state",
        region="Georgia",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Georgia cream poster — Southeastern Piedmont river density.",
    ),
    GallerySelection(
        item_id="in-cream-state",
        region="Indiana",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Indiana cream poster — Wabash/White River network in warm tones.",
    ),
    GallerySelection(
        item_id="me-cream-state",
        region="Maine",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Maine cream poster — Penobscot/Kennebec headwaters.",
    ),
    GallerySelection(
        item_id="mn-cream-state",
        region="Minnesota",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Minnesota cream poster — 10,000 lakes state in earth tones.",
    ),
    GallerySelection(
        item_id="nv-cream-state",
        region="Nevada",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="Nevada cream poster — Great Basin sparse hydrology.",
    ),
    GallerySelection(
        item_id="sd-cream-state",
        region="South Dakota",
        county=None,
        style="cream-basin",
        endpoint="digital_image",
        rationale="South Dakota cream poster — Missouri/James River plains.",
    ),
    # ── State-level animations ────────────────────────────────────────────
    GallerySelection(
        item_id="mn-neon-animation",
        region="Minnesota",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Minnesota year-cycle — spring snowmelt swell to frozen winter silence.",
    ),
    GallerySelection(
        item_id="wa-neon-animation",
        region="Washington",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Washington year-cycle — Cascades snowpack-driven seasonal flow.",
    ),
    GallerySelection(
        item_id="or-neon-animation",
        region="Oregon",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Oregon year-cycle — Coast Range rain vs. Cascades snowmelt.",
    ),
    GallerySelection(
        item_id="id-neon-animation",
        region="Idaho",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Idaho year-cycle — Salmon River snowmelt pulse.",
    ),
    GallerySelection(
        item_id="ga-neon-animation",
        region="Georgia",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Georgia year-cycle — subtropical rain-driven flow pattern.",
    ),
    GallerySelection(
        item_id="fl-neon-animation",
        region="Florida",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Florida year-cycle — wet/dry season tropical hydrology.",
    ),
    GallerySelection(
        item_id="oh-neon-animation",
        region="Ohio",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Ohio year-cycle — Great Lakes/Ohio River basin seasonality.",
    ),
    GallerySelection(
        item_id="tx-neon-animation",
        region="Texas",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2026,
        rationale="Texas year-cycle — arid west vs. humid east contrast.",
    ),
    # ── County-level digital images ───────────────────────────────────────
    GallerySelection(
        item_id="wa-clark-neon",
        region="Washington",
        county="Clark",
        style="neon-basin",
        endpoint="digital_image",
        rationale="Clark County — the original development testbed, dense suburban hydro.",
    ),
    GallerySelection(
        item_id="wa-pacific-neon",
        region="Washington",
        county="Pacific",
        style="neon-basin",
        endpoint="digital_image",
        rationale="Pacific County — coastal rain-fed river network.",
    ),
    GallerySelection(
        item_id="or-multnomah-neon",
        region="Oregon",
        county="Multnomah",
        style="neon-basin",
        endpoint="digital_image",
        rationale="Multnomah County (Portland) — urban/suburban river confluence.",
    ),
    GallerySelection(
        item_id="wa-clark-3d",
        region="Washington",
        county="Clark",
        style="elevation-tint",
        endpoint="digital_image",
        rationale="Clark County 3D elevation — terrain context for the flagship county.",
    ),
    # ── Museum/editorial series ───────────────────────────────────────────
    GallerySelection(
        item_id="wa-clark-specimen",
        region="Washington",
        county="Clark",
        style="museum-specimen",
        endpoint="digital_image",
        rationale="Museum specimen — botanical-plate style elevation study.",
    ),
    GallerySelection(
        item_id="wa-clark-almanac",
        region="Washington",
        county="Clark",
        style="museum-almanac",
        endpoint="digital_image",
        rationale="Museum almanac — seasonal flow narrative as editorial broadsheet.",
    ),
    GallerySelection(
        item_id="wa-clark-compass",
        region="Washington",
        county="Clark",
        style="museum-compass",
        endpoint="digital_image",
        rationale="Museum compass — watershed orientation and basin compass rose.",
    ),
    GallerySelection(
        item_id="wa-clark-divide",
        region="Washington",
        county="Clark",
        style="museum-divide",
        endpoint="digital_image",
        rationale="Museum divide — drainage divide and ridge-line anatomy.",
    ),
    GallerySelection(
        item_id="wa-clark-index",
        region="Washington",
        county="Clark",
        style="museum-index",
        endpoint="digital_image",
        rationale="Museum index — hydrographic index plate with named streams.",
    ),
    GallerySelection(
        item_id="wa-pacific-specimen",
        region="Washington",
        county="Pacific",
        style="museum-specimen",
        endpoint="digital_image",
        rationale="Pacific County specimen — coastal river system botanical plate.",
    ),
    GallerySelection(
        item_id="wa-pacific-almanac",
        region="Washington",
        county="Pacific",
        style="museum-almanac",
        endpoint="digital_image",
        rationale="Pacific County almanac — coastal seasonal flow editorial.",
    ),
    GallerySelection(
        item_id="wa-pacific-compass",
        region="Washington",
        county="Pacific",
        style="museum-compass",
        endpoint="digital_image",
        rationale="Pacific County compass — coastal basin orientation.",
    ),
    GallerySelection(
        item_id="wa-pacific-divide",
        region="Washington",
        county="Pacific",
        style="museum-divide",
        endpoint="digital_image",
        rationale="Pacific County divide — Willapa Hills drainage anatomy.",
    ),
    GallerySelection(
        item_id="wa-pacific-index",
        region="Washington",
        county="Pacific",
        style="museum-index",
        endpoint="digital_image",
        rationale="Pacific County index — named stream reference plate.",
    ),
    # ── Print editions ────────────────────────────────────────────────────
    GallerySelection(
        item_id="wa-clark-neon-print",
        region="Washington",
        county="Clark",
        style="neon-basin",
        endpoint="print_image",
        size="18x24",
        rationale="Clark County neon print — the signature wall piece at 18x24.",
    ),
    GallerySelection(
        item_id="wa-pacific-neon-print",
        region="Washington",
        county="Pacific",
        style="neon-basin",
        endpoint="print_image",
        size="18x24",
        rationale="Pacific County neon print — coastal river art at 18x24.",
    ),
    # ── Year-over-year flow sequences ─────────────────────────────────────
    GallerySelection(
        item_id="wa-neon-yoy",
        region="Washington",
        county=None,
        style="neon-basin",
        endpoint="animation",
        year=2023,
        rationale="Washington 10-year flow — decade of drought/flood visible as animation.",
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
