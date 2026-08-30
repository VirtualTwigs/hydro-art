# Spec — Order fulfillment tooling (roadmap #56–#57, Epoch 11.5)

## Overview

A validated **order → deliverable plan → manifest** core that makes made-to-order
county watershed prints reproducible and rights-compliant. Pure statistics-free glue:
`src/fulfillment.py` is stdlib-only and offline-tested; `tools/fulfill_order.py`
does the heavy render/export by reusing the existing county-clip recipe
(`tools/render_common.py`, `tools/render_county_clip.py`, `src.export`). Nothing
enters `PIPELINE_STAGES`; the 2D default output stays byte-identical.

Two rules carried from prior epochs, enforced throughout:
- **Validate at the boundary, fail fast** (the `build_settings` precedent).
- **Injectable catalogs / seams** so the offline suite exercises everything —
  including the Rights-gate guard — with no real datasets.

> **Commercial framing (Epoch 11.5).** This is the reproducible-fulfillment core of
> #56/#57 only. Listing, funnel tracking (#58), and the revenue gate (#59) are
> operational and live in `agent-os/product/revenue-ledger.md`.

## `src/fulfillment.py` (new, stdlib-only, offline) — items #56, #57

### Catalogs (module constants, injectable)

```python
# Two approved art directions (#57). Each maps to existing render knobs; `renderer`
# tells the executor which path to drive; `uses_prism` gates the Rights gate.
ORDER_STYLES: dict[str, StyleSpec] = {
    "neon-basin":     StyleSpec(color_by="watershed", width_by="flow",
                                glow=True, renderer="pipeline", uses_prism=False),
    "elevation-tint": StyleSpec(color_by="elevation", width_by="flow",
                                glow=True, renderer="mono",     uses_prism=False),
}

# Print sizes → pixel dims at 300 DPI (portrait). Deterministic, human-tunable.
SIZES: dict[str, Size] = {
    "12x16": Size(w_in=12, h_in=16, dpi=300),   # 3600 x 4800
    "18x24": Size(w_in=18, h_in=24, dpi=300),   # 5400 x 7200
    "24x36": Size(w_in=24, h_in=36, dpi=300),   # 7200 x 10800
}

PRINT_FORMATS = ("png", "pdf")          # base deliverable formats
ADD_ONS       = ("svg", "commercial_license")
DEFAULT_SOURCES = (
    DataSource("USGS NHDPlus HR", version="…"),
    DataSource("USGS NHD",        version="…"),
    DataSource("USGS WBD",        version="…"),
)
TITLE_MAX, SUBTITLE_MAX = 60, 80
```

### Value objects (frozen)

```python
@dataclass(frozen=True) class StyleSpec:  color_by; width_by; glow; renderer; uses_prism
@dataclass(frozen=True) class Size:       w_in; h_in; dpi          # .px -> (w,h)
@dataclass(frozen=True) class DataSource: name; version
@dataclass(frozen=True) class Order:      order_id; region; county; style; size;
                                          formats: tuple[str,...]; add_ons: tuple[str,...];
                                          title: str|None; subtitle: str|None; buyer_ref: str|None
@dataclass(frozen=True) class Deliverable: kind; filename; fmt; width_px|None; height_px|None
@dataclass(frozen=True) class DeliverablePlan: order_id; items: tuple[Deliverable,...];
                                          includes_editable_svg; requires_license_doc
```

### Functions (pure)

```python
def build_order(payload, *, styles=ORDER_STYLES, sizes=SIZES) -> Order
    # region ∈ SUPPORTED_REGIONS (from src.config); county non-empty; style ∈ styles;
    # size ∈ sizes; formats non-empty ⊆ PRINT_FORMATS; add_ons ⊆ ADD_ONS;
    # order_id required; title/subtitle stripped + length-capped; then assert_sellable().
    # Any violation -> OrderError(user-facing message). Does not mutate payload.

def assert_sellable(order, *, styles=ORDER_STYLES) -> None
    # Rights gate: raise OrderError if styles[order.style].uses_prism is True.

def attribution_line(sources=DEFAULT_SOURCES, *, sep=" · ") -> str
    # Deterministic, sorted-by-name source-credit line; "Name vX" when version given.
    # Always non-empty (Rights gate requires it on every sold asset).

def title_block(order, *, sources=DEFAULT_SOURCES) -> dict   # {title, subtitle, credit}
    # title  = order.title    or default_title(order)     (e.g. "Clark County Watersheds")
    # subtitle = order.subtitle or default_subtitle(order) (e.g. "Washington · Hydrographic network")
    # credit = attribution_line(sources)
    # Rules: title-case defaults, collapse whitespace, cap length; deterministic.

def deliverable_plan(order) -> DeliverablePlan
    # one Deliverable per fmt in order.formats at Size.px; + "svg" add-on -> editable
    # SVG deliverable; + "commercial_license" -> a license-doc deliverable.
    # Filenames deterministic from order_id/region/county/style/size. Independent of
    # add-on input ordering.

def fulfillment_manifest(order, plan, *, checksums, sources=DEFAULT_SOURCES) -> dict
    # {schema, order{…}, title_block, attribution, sources[{name,version}],
    #  deliverables[{filename, fmt, sha256, width_px, height_px}]}.
    # checksums: {filename: sha256} must cover exactly plan filenames -> else OrderError.
    # json.dumps(manifest, sort_keys=True) is byte-identical for equal inputs.

class OrderError(Exception): ...   # boundary error, user-facing message
```

## `tools/fulfill_order.py` (new, non-offline executor — outside the suite)

Thin CLI: `--order order.json` (or flags) → `build_order` → dispatch on
`StyleSpec.renderer` (`pipeline` → county-scoped `Settings` + `Pipeline`/
`render_county_clip`; `mono` → `render_state_mono`-style hypsometric path) → stamp
`title_block` (title/subtitle/credit as SVG text) → export each `deliverable_plan`
item at `Size.px` (reuse `src.export` / `rasterize_layered`) → write `license.txt`
for the license add-on → compute sha256 → `fulfillment_manifest` →
`<order_id>.manifest.json`. Imports GIS libs eagerly; smoke-tested only.

## Unit test design — `tests/test_fulfillment.py` (offline, stdlib only)

TDD, written first, ~4–6 assertions per group. Hand-built payloads; no datasets.

**Group 1 — order model & validation (`build_order`, `assert_sellable`)**
- valid payload (each of OR/WA/CA/ID) → frozen `Order`; fields normalized
  (formats/add_ons as tuples, title stripped).
- rejects region ∉ `SUPPORTED_REGIONS` → `OrderError`.
- rejects empty/whitespace county, missing `order_id`, empty `formats`, a format ∉
  `PRINT_FORMATS`, style ∉ catalog, size ∉ catalog, add-on ∉ `ADD_ONS`
  (parametrized) → `OrderError` each.
- title/subtitle longer than `TITLE_MAX`/`SUBTITLE_MAX` → capped; absent → `None`.
- purity: input `payload` dict is unchanged after the call; `Order` is frozen
  (assigning raises).
- **Rights gate:** injecting a `styles=` table with a `uses_prism=True` entry and
  ordering it → `OrderError` (both via `build_order` and direct `assert_sellable`).

**Group 2 — title block & attribution (`attribution_line`, `title_block`)**
- `attribution_line()` default → exact expected string (sorted names, `" · "` sep);
  a source with a version → `"Name vX"`; shuffling input order → identical output
  (sorted/stable); never empty.
- `title_block` with explicit title/subtitle → those, whitespace-collapsed, length-
  capped; `credit == attribution_line(...)`.
- `title_block` with `title=None`/`subtitle=None` → deterministic defaults derived
  from county + region (title-cased).
- identical order → identical `title_block` (determinism).

**Group 3 — deliverable plan (`deliverable_plan`)**
- png+pdf @ `18x24` → two print `Deliverable`s, `width_px/height_px == (5400, 7200)`,
  deterministic filenames; `includes_editable_svg` False, `requires_license_doc`
  False.
- `svg` add-on → adds one SVG deliverable (no px dims); `includes_editable_svg` True.
- `commercial_license` add-on → adds a license-doc deliverable; `requires_license_doc`
  True.
- add-on **input ordering** `("svg","commercial_license")` vs reversed → identical
  plan (order-independent, deterministic).

**Group 4 — manifest (`fulfillment_manifest`)**
- manifest carries order fields, `title_block`, `attribution`, and one
  `deliverables[]` entry per plan item with its injected `sha256`.
- `sources[]` records every `DataSource` name+version (Rights-gate provenance).
- `json.dumps(m, sort_keys=True)` byte-identical across two calls with equal inputs
  (reproducible re-order).
- `checksums` missing a planned filename (or containing an extra one) → `OrderError`.

## Non-goals / deferred
- Actual marketplace/listing integration, payment, and the intake-form UI.
- Style-catalog growth beyond the two approved directions (gated on the revenue
  outcome, per the roadmap Revenue gate).
- Wiring fulfillment into `serve.py`/`web/studio.html` (could follow if the gate
  passes).
