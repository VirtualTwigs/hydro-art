"""Production endpoint contracts & dispatch (Epoch 19, items #79-81).

First epoch of Generation 1. Generalizes :mod:`src.fulfillment` from the single print
order to the **four production endpoints** — ``digital_image``, ``animation``,
``print_image``, ``report`` — giving each a documented, versioned *output contract*, a
fail-fast *request validator*, a deterministic *deliverable plan*, a provenance
*manifest*, and an injectable *dispatch seam*.

Pure and offline: imports only stdlib + ``src.config`` (for ``SUPPORTED_REGIONS``) and
``src.fulfillment`` (reusing its value objects, ``attribution_line``, and Rights-gate
semantics). No GDAL / numpy / network / datasets, and nothing enters ``PIPELINE_STAGES``.
The real renderers live in the non-offline ``tools/render_endpoint.py``, injected into
:func:`dispatch_endpoint` so routing stays fully offline-testable. Identical request ->
identical plan -> byte-identical (``sort_keys``) manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import SUPPORTED_REGIONS
from src.fulfillment import (
    DEFAULT_SOURCES,
    ORDER_STYLES,
    SIZES,
    Deliverable,
    DeliverablePlan,
    attribution_line,
)

__all__ = [
    "EndpointError",
    "ENDPOINTS",
    "EndpointContract",
    "ENDPOINT_CONTRACTS",
    "EndpointRequest",
    "EndpointResult",
    "build_endpoint_request",
    "endpoint_plan",
    "endpoint_manifest",
    "assert_sellable",
    "dispatch_endpoint",
    "MANIFEST_SCHEMA",
]

MANIFEST_SCHEMA = "hydro-art/endpoint-manifest@1"


class EndpointError(Exception):
    """Raised for an invalid or non-sellable endpoint request (user-facing message)."""


# --- contracts ------------------------------------------------------------

ENDPOINTS: tuple[str, ...] = ("digital_image", "animation", "print_image", "report")


@dataclass(frozen=True)
class EndpointContract:
    """The documented output contract for one production endpoint.

    ``formats`` is an ordered tuple of ``(fmt, kind)`` pairs — canonical output order
    and the deliverable ``kind`` each format maps to. ``stem_suffix`` disambiguates
    filenames across endpoints for the same region/style.
    """

    endpoint: str
    formats: tuple[tuple[str, str], ...]
    stem_suffix: str
    requires_manifest: bool = True

    @property
    def format_names(self) -> tuple[str, ...]:
        return tuple(fmt for fmt, _ in self.formats)

    @property
    def deliverable_kinds(self) -> tuple[str, ...]:
        kinds: list[str] = []
        for _, kind in self.formats:
            if kind not in kinds:
                kinds.append(kind)
        return tuple(kinds)

    def kind_for(self, fmt: str) -> str:
        for name, kind in self.formats:
            if name == fmt:
                return kind
        raise KeyError(fmt)


ENDPOINT_CONTRACTS: dict[str, EndpointContract] = {
    "digital_image": EndpointContract(
        endpoint="digital_image",
        formats=(("svg", "vector"), ("png", "raster")),
        stem_suffix="digital",
    ),
    "animation": EndpointContract(
        endpoint="animation",
        formats=(("gif", "motion"), ("mp4", "motion")),
        stem_suffix="motion",
    ),
    "print_image": EndpointContract(
        endpoint="print_image",
        formats=(("png", "raster"), ("pdf", "raster"), ("tiff", "raster")),
        stem_suffix="print",
    ),
    "report": EndpointContract(
        endpoint="report",
        formats=(("html", "document"), ("png", "figures")),
        stem_suffix="report",
    ),
}


# --- request --------------------------------------------------------------

@dataclass(frozen=True)
class EndpointRequest:
    """A validated, immutable request for one endpoint deliverable."""

    request_id: str
    region: str
    county: str
    endpoint: str
    style: str
    formats: tuple[str, ...]
    size: str | None = None
    year: int | None = None
    months: tuple[int, ...] = ()
    huc: str | None = None


def build_endpoint_request(payload, *, styles=ORDER_STYLES, sizes=SIZES) -> EndpointRequest:
    """Validate ``payload`` against the allowlists and return a frozen request.

    Raises :class:`EndpointError` (single user-facing message) on any violation. Does
    not mutate ``payload``.
    """
    request_id = str(payload.get("request_id", "")).strip()
    if not request_id:
        raise EndpointError("request_id is required.")

    region = payload.get("region")
    if region not in SUPPORTED_REGIONS:
        valid = ", ".join(SUPPORTED_REGIONS)
        raise EndpointError(f"Unsupported region {region!r}. Choose one of: {valid}.")

    county = str(payload.get("county", "")).strip()
    if not county:
        raise EndpointError("county must be a non-empty name.")

    endpoint = payload.get("endpoint")
    if endpoint not in ENDPOINT_CONTRACTS:
        valid = ", ".join(ENDPOINTS)
        raise EndpointError(f"Unknown endpoint {endpoint!r}. Choose one of: {valid}.")
    contract = ENDPOINT_CONTRACTS[endpoint]

    style = payload.get("style")
    if style not in styles:
        valid = ", ".join(sorted(styles))
        raise EndpointError(f"Unknown style {style!r}. Choose one of: {valid}.")

    formats = tuple(payload.get("formats") or contract.format_names)
    bad = [f for f in formats if f not in contract.format_names]
    if bad:
        valid = ", ".join(contract.format_names)
        raise EndpointError(
            f"Unknown format(s) {bad} for {endpoint}. Choose from: {valid}."
        )

    size = payload.get("size")
    year = payload.get("year")
    months = tuple(payload.get("months") or ())
    huc = payload.get("huc")

    if endpoint == "print_image" and size not in sizes:
        valid = ", ".join(sorted(sizes))
        raise EndpointError(f"print_image requires a size in: {valid}.")
    if endpoint == "report":
        if not (huc and str(huc).strip()):
            raise EndpointError("report requires a non-empty 'huc'.")
        huc = str(huc).strip()
    if endpoint == "animation" and year is None and not months:
        raise EndpointError("animation requires 'year' or a non-empty 'months'.")

    request = EndpointRequest(
        request_id=request_id,
        region=region,
        county=county,
        endpoint=endpoint,
        style=style,
        formats=formats,
        size=size if endpoint == "print_image" else None,
        year=int(year) if year is not None else None,
        months=tuple(int(m) for m in months),
        huc=huc if endpoint == "report" else None,
    )
    assert_sellable(request, styles=styles)
    return request


# --- rights gate ----------------------------------------------------------

def assert_sellable(request, *, styles=ORDER_STYLES) -> None:
    """Rights gate: refuse any style flagged ``uses_prism`` (needs PRISM licensing).

    Mirrors :func:`src.fulfillment.assert_sellable` but raises :class:`EndpointError`.
    """
    spec = styles.get(request.style)
    if spec is not None and spec.uses_prism:
        raise EndpointError(
            f"Style {request.style!r} derives from PRISM data and cannot be sold until "
            "PRISM Climate Group licensing is documented (see roadmap Rights gate)."
        )


# --- deliverable plan -----------------------------------------------------

def _stem(request) -> str:
    """A filesystem-safe, deterministic stem from the request identity."""
    county = request.county.lower().replace(" ", "-")
    suffix = ENDPOINT_CONTRACTS[request.endpoint].stem_suffix
    return (
        f"{request.request_id}_{request.region.lower()}-{county}"
        f"_{request.style}_{suffix}"
    )


def endpoint_plan(request, *, sizes=SIZES) -> DeliverablePlan:
    """The deterministic, order-independent files this request yields."""
    contract = ENDPOINT_CONTRACTS[request.endpoint]
    stem = _stem(request)
    items: list[Deliverable] = []
    for fmt in contract.format_names:  # canonical contract order
        if fmt in request.formats:
            w = h = None
            if request.endpoint == "print_image" and request.size in sizes:
                w, h = sizes[request.size].px
            items.append(
                Deliverable(
                    kind=contract.kind_for(fmt),
                    filename=f"{stem}.{fmt}",
                    fmt=fmt,
                    width_px=w,
                    height_px=h,
                )
            )
    return DeliverablePlan(
        order_id=request.request_id,
        items=tuple(items),
        includes_editable_svg="svg" in request.formats,
        requires_license_doc=False,
    )


# --- manifest -------------------------------------------------------------

def endpoint_manifest(request, plan, *, checksums, sources=DEFAULT_SOURCES) -> dict:
    """A provenance manifest for a produced endpoint deliverable.

    ``checksums`` maps each planned filename -> sha256 and must cover the plan
    **exactly** (no missing, no strangers) or :class:`EndpointError` is raised.
    ``json.dumps(..., sort_keys=True)`` is byte-identical for equal inputs.
    """
    planned = {d.filename for d in plan.items}
    provided = set(checksums)
    if planned != provided:
        missing = sorted(planned - provided)
        extra = sorted(provided - planned)
        raise EndpointError(
            f"Checksum coverage mismatch (missing={missing}, unexpected={extra})."
        )

    return {
        "schema": MANIFEST_SCHEMA,
        "endpoint": request.endpoint,
        "request": {
            "request_id": request.request_id,
            "region": request.region,
            "county": request.county,
            "endpoint": request.endpoint,
            "style": request.style,
            "formats": list(request.formats),
            "size": request.size,
            "year": request.year,
            "months": list(request.months),
            "huc": request.huc,
        },
        "attribution": attribution_line(sources),
        "sources": [{"name": s.name, "version": s.version} for s in sources],
        "deliverables": [
            {
                "filename": d.filename,
                "kind": d.kind,
                "fmt": d.fmt,
                "sha256": checksums[d.filename],
                "width_px": d.width_px,
                "height_px": d.height_px,
            }
            for d in plan.items
        ],
    }


# --- dispatch -------------------------------------------------------------

@dataclass(frozen=True)
class EndpointResult:
    """The outcome of a dispatched endpoint render (plan + stamped manifest)."""

    endpoint: str
    plan: DeliverablePlan
    manifest: dict = field(default_factory=dict)
    ok: bool = True
    message: str | None = None


def dispatch_endpoint(
    request, *, renderers, sources=DEFAULT_SOURCES, styles=ORDER_STYLES
) -> EndpointResult:
    """Route ``request`` to its injected renderer and stamp a provenance manifest.

    ``renderers`` maps ``endpoint -> callable(request, plan) -> {filename: sha256}``.
    The Rights gate runs **before** the renderer is looked up or called, so a
    non-sellable request never triggers I/O. Pure: all real work is in the injected
    renderer seam, keeping dispatch fully offline-testable.
    """
    assert_sellable(request, styles=styles)  # Rights gate first — before any renderer.

    renderer = renderers.get(request.endpoint)
    if renderer is None:
        raise EndpointError(
            f"No renderer registered for endpoint {request.endpoint!r}."
        )

    plan = endpoint_plan(request)
    checksums = renderer(request, plan)
    manifest = endpoint_manifest(request, plan, checksums=checksums, sources=sources)
    return EndpointResult(endpoint=request.endpoint, plan=plan, manifest=manifest)
