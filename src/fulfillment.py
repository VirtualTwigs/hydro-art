"""Order-fulfillment tooling (roadmap #56-#57, Epoch 11.5).

Turns a validated customer **order** for a made-to-order county watershed print into
a deterministic **deliverable plan** + provenance **manifest**, with title/subtitle
rules and the required source-attribution line baked in. This is the reproducible,
rights-compliant core of the Revenue Validation fulfillment pack — *not* a new
renderer: the heavy render/export lives in the non-offline ``tools/fulfill_order.py``
executor that reuses the existing county-clip recipe.

Pure and stdlib-only (imports only stdlib + ``src.config`` for ``SUPPORTED_REGIONS``),
so the whole surface is offline-testable — no GDAL / numpy / network / datasets, and
nothing enters ``PIPELINE_STAGES``. Identical order -> identical plan -> byte-identical
``sort_keys`` manifest, which is what makes a re-order reproducible.

Rights gate (enforced here): every order carries an :func:`attribution_line` built
from its data sources, and :func:`assert_sellable` refuses any style whose
``uses_prism`` is set — the two approved art directions are PRISM-free, so the
near-term offer is clear and a future PRISM style cannot be sold by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import SUPPORTED_REGIONS

__all__ = [
    "ADD_ONS",
    "DEFAULT_SOURCES",
    "ORDER_STYLES",
    "PRINT_FORMATS",
    "SIZES",
    "SUBTITLE_MAX",
    "TITLE_MAX",
    "DataSource",
    "Deliverable",
    "DeliverablePlan",
    "Order",
    "OrderError",
    "Size",
    "StyleSpec",
    "assert_sellable",
    "attribution_line",
    "build_order",
    "default_subtitle",
    "default_title",
    "deliverable_plan",
    "fulfillment_manifest",
    "title_block",
]


class OrderError(Exception):
    """Raised for an invalid or non-sellable order (user-facing message)."""


# --- value objects --------------------------------------------------------

@dataclass(frozen=True)
class StyleSpec:
    """An approved art direction, mapped to existing render knobs.

    ``renderer`` selects the executor path (``"pipeline"`` = the 2D ``Pipeline`` /
    county clip; ``"mono"`` = the hypsometric ``render_state_mono`` path).
    ``uses_prism`` gates the Rights gate.
    """

    color_by: str
    width_by: str
    glow: bool
    renderer: str
    uses_prism: bool


@dataclass(frozen=True)
class Size:
    """A print size in inches at a fixed DPI. ``px`` -> (width, height) pixels."""

    w_in: int
    h_in: int
    dpi: int

    @property
    def px(self) -> tuple[int, int]:
        return (self.w_in * self.dpi, self.h_in * self.dpi)


@dataclass(frozen=True)
class DataSource:
    """A public data source credited on every sold asset (Rights gate)."""

    name: str
    version: str | None = None


@dataclass(frozen=True)
class Order:
    """A validated, immutable customer order."""

    order_id: str
    region: str
    county: str
    style: str
    size: str
    formats: tuple[str, ...]
    add_ons: tuple[str, ...]
    title: str | None = None
    subtitle: str | None = None
    buyer_ref: str | None = None


@dataclass(frozen=True)
class Deliverable:
    """One file the fulfillment run must produce."""

    kind: str  # "print" | "vector" | "license"
    filename: str
    fmt: str
    width_px: int | None = None
    height_px: int | None = None


@dataclass(frozen=True)
class DeliverablePlan:
    """The deterministic set of files a fulfilled order yields."""

    order_id: str
    items: tuple[Deliverable, ...]
    includes_editable_svg: bool
    requires_license_doc: bool


# --- catalogs (module constants, injectable via `styles=` / `sizes=`) -----

ORDER_STYLES: dict[str, StyleSpec] = {
    "neon-basin": StyleSpec(
        color_by="watershed", width_by="flow", glow=True,
        renderer="pipeline", uses_prism=False,
    ),
    "elevation-tint": StyleSpec(
        color_by="elevation", width_by="flow", glow=True,
        renderer="mono", uses_prism=False,
    ),
}

SIZES: dict[str, Size] = {
    "12x16": Size(w_in=12, h_in=16, dpi=300),
    "18x24": Size(w_in=18, h_in=24, dpi=300),
    "24x36": Size(w_in=24, h_in=36, dpi=300),
}

PRINT_FORMATS: tuple[str, ...] = ("png", "pdf")
ADD_ONS: tuple[str, ...] = ("svg", "commercial_license")

DEFAULT_SOURCES: tuple[DataSource, ...] = (
    DataSource("USGS NHDPlus HR"),
    DataSource("USGS NHD"),
    DataSource("USGS WBD"),
)

TITLE_MAX = 60
SUBTITLE_MAX = 80


# --- validation -----------------------------------------------------------

def _clean_text(value, *, cap: int) -> str | None:
    """Collapse internal whitespace, strip, and length-cap. ``None`` stays None."""
    if value is None:
        return None
    collapsed = " ".join(str(value).split())
    if not collapsed:
        return None
    return collapsed[:cap]


def build_order(payload, *, styles=ORDER_STYLES, sizes=SIZES) -> Order:
    """Validate ``payload`` against the allowlists and return a frozen :class:`Order`.

    Raises :class:`OrderError` (single, user-facing message) on any violation. Does
    not mutate ``payload``.
    """
    order_id = str(payload.get("order_id", "")).strip()
    if not order_id:
        raise OrderError("order_id is required.")

    region = payload.get("region")
    if region not in SUPPORTED_REGIONS:
        valid = ", ".join(SUPPORTED_REGIONS)
        raise OrderError(f"Unsupported region {region!r}. Choose one of: {valid}.")

    county = str(payload.get("county", "")).strip()
    if not county:
        raise OrderError("county must be a non-empty name.")

    style = payload.get("style")
    if style not in styles:
        valid = ", ".join(sorted(styles))
        raise OrderError(f"Unknown style {style!r}. Choose one of: {valid}.")

    size = payload.get("size")
    if size not in sizes:
        valid = ", ".join(sorted(sizes))
        raise OrderError(f"Unknown size {size!r}. Choose one of: {valid}.")

    formats = tuple(payload.get("formats") or ())
    if not formats:
        raise OrderError("At least one print format is required.")
    bad = [f for f in formats if f not in PRINT_FORMATS]
    if bad:
        valid = ", ".join(PRINT_FORMATS)
        raise OrderError(f"Unknown format(s) {bad}. Choose from: {valid}.")

    add_ons = tuple(payload.get("add_ons") or ())
    bad = [a for a in add_ons if a not in ADD_ONS]
    if bad:
        valid = ", ".join(ADD_ONS)
        raise OrderError(f"Unknown add-on(s) {bad}. Choose from: {valid}.")

    order = Order(
        order_id=order_id,
        region=region,
        county=county,
        style=style,
        size=size,
        formats=formats,
        add_ons=add_ons,
        title=_clean_text(payload.get("title"), cap=TITLE_MAX),
        subtitle=_clean_text(payload.get("subtitle"), cap=SUBTITLE_MAX),
        buyer_ref=_clean_text(payload.get("buyer_ref"), cap=120),
    )
    assert_sellable(order, styles=styles)
    return order


def assert_sellable(order, *, styles=ORDER_STYLES) -> None:
    """Rights gate: refuse any style flagged ``uses_prism`` (needs PRISM licensing)."""
    spec = styles.get(order.style)
    if spec is not None and spec.uses_prism:
        raise OrderError(
            f"Style {order.style!r} derives from PRISM data and cannot be sold until "
            "PRISM Climate Group licensing is documented (see roadmap Rights gate)."
        )


# --- title / attribution --------------------------------------------------

def attribution_line(sources=DEFAULT_SOURCES, *, sep: str = " · ") -> str:
    """A deterministic, name-sorted source-credit line ("Name vX" when versioned)."""
    parts = [
        f"{s.name} v{s.version}" if s.version else s.name
        for s in sorted(sources, key=lambda s: s.name)
    ]
    return sep.join(parts)


def default_title(order) -> str:
    """A default headline, e.g. ``"Clark County Watersheds"``."""
    county = order.county
    if not county.lower().endswith("county"):
        county = f"{county} County"
    return f"{county} Watersheds".title()


def default_subtitle(order) -> str:
    """A default subtitle, e.g. ``"Washington · Hydrographic river network"``."""
    return f"{order.region} · Hydrographic river network"


def title_block(order, *, sources=DEFAULT_SOURCES) -> dict:
    """The stamped text block: ``{title, subtitle, credit}`` (all deterministic)."""
    title = order.title or default_title(order)
    subtitle = order.subtitle or default_subtitle(order)
    return {
        "title": _clean_text(title, cap=TITLE_MAX),
        "subtitle": _clean_text(subtitle, cap=SUBTITLE_MAX),
        "credit": attribution_line(sources),
    }


# --- deliverable plan -----------------------------------------------------

def _stem(order) -> str:
    """A filesystem-safe, deterministic stem from the order identity."""
    county = order.county.lower().replace(" ", "-")
    return f"{order.order_id}_{order.region.lower()}-{county}_{order.style}_{order.size}"


def deliverable_plan(order, *, sizes=SIZES) -> DeliverablePlan:
    """The deterministic list of files this order yields (add-on-order-independent)."""
    stem = _stem(order)
    w, h = sizes[order.size].px
    items: list[Deliverable] = []

    # Base prints, one per requested format (in the canonical PRINT_FORMATS order).
    for fmt in PRINT_FORMATS:
        if fmt in order.formats:
            items.append(
                Deliverable(kind="print", filename=f"{stem}.{fmt}", fmt=fmt,
                            width_px=w, height_px=h)
            )

    includes_svg = "svg" in order.add_ons
    if includes_svg:
        items.append(Deliverable(kind="vector", filename=f"{stem}.svg", fmt="svg"))

    requires_license = "commercial_license" in order.add_ons
    if requires_license:
        items.append(
            Deliverable(kind="license", filename=f"{stem}_license.txt", fmt="txt")
        )

    return DeliverablePlan(
        order_id=order.order_id,
        items=tuple(items),
        includes_editable_svg=includes_svg,
        requires_license_doc=requires_license,
    )


# --- manifest -------------------------------------------------------------

def fulfillment_manifest(order, plan, *, checksums, sources=DEFAULT_SOURCES) -> dict:
    """A provenance manifest for a fulfilled order (reproducible re-order record).

    ``checksums`` maps each planned filename -> sha256 and must cover the plan
    **exactly** (no missing, no strangers) or :class:`OrderError` is raised.
    ``json.dumps(..., sort_keys=True)`` is byte-identical for equal inputs.
    """
    planned = {d.filename for d in plan.items}
    provided = set(checksums)
    if planned != provided:
        missing = sorted(planned - provided)
        extra = sorted(provided - planned)
        raise OrderError(
            f"Checksum coverage mismatch (missing={missing}, unexpected={extra})."
        )

    tb = title_block(order, sources=sources)
    return {
        "schema": "hydro-art/fulfillment-manifest@1",
        "order": {
            "order_id": order.order_id,
            "region": order.region,
            "county": order.county,
            "style": order.style,
            "size": order.size,
            "formats": list(order.formats),
            "add_ons": list(order.add_ons),
            "buyer_ref": order.buyer_ref,
        },
        "title_block": tb,
        "attribution": tb["credit"],
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
