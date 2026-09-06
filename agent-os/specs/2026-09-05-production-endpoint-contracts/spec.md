# Spec: Production endpoint contracts & hardening (Epoch 19, items #79–81)

## Summary

First epoch of **Generation 1 — Production Release**. Introduce a pure, offline
`src/endpoints.py` that gives the four production endpoints (`digital_image`, `animation`,
`print_image`, `report`) a documented, versioned **output contract**, a fail-fast **request
validator**, a deterministic **deliverable plan**, a provenance **manifest**, and an
injectable **dispatch seam**. Add a thin, non-offline `tools/render_endpoint.py` CLI that
injects the real renderers (authored now, executed later on the GDAL+NAS machine). Adds no
art feature and no `PIPELINE_STAGES` change — the default 2D build stays byte-for-byte
identical. This is the foundation the Epoch 20 test pyramid and Epoch 21 flagship e2e assert
against.

## Context & templates to mirror (parallel exactly — do not duplicate)

- **`src/fulfillment.py`** is the template: frozen value objects, allowlist validation →
  single `OrderError`, `deliverable_plan`, a versioned `sort_keys` manifest
  (`hydro-art/fulfillment-manifest@1`), `attribution_line`, and the Rights gate
  `assert_sellable`. `src/endpoints.py` generalizes this from the print order to all four
  endpoints. **Reuse** `attribution_line`, `DataSource`, `DEFAULT_SOURCES`, `Size`/`SIZES`,
  and the checksum-coverage check rather than re-implementing them (import from
  `src.fulfillment`).
- **`tools/render_common.py`** is the shared art-quality recipe; the CLI wrapper extends it,
  never duplicates render logic.
- Offline discipline: stdlib + `src.config`/`src.fulfillment` only in `src/endpoints.py`.
- Anchor region for downstream epochs: **Wahkiakum County, WA** (`tests/fixtures/golden/registry.json`).

## Design

### `src/endpoints.py` (NEW — pure/offline)

Value objects (frozen dataclasses):

- `EndpointError(Exception)` — single user-facing validation message.
- `ENDPOINTS = ("digital_image", "animation", "print_image", "report")`.
- `EndpointContract`: `endpoint`, `deliverable_kinds: tuple[str,...]`,
  `formats: tuple[str,...]`, `requires_manifest: bool = True`, `stem_suffix: str`
  (documented naming rule). `ENDPOINT_CONTRACTS: dict[str, EndpointContract]` covers all four
  per the requirements table.
- `EndpointRequest`: `region`, `county`, `endpoint`, `style`, and endpoint-specific optional
  params (`size` for print, `year`/`months` for animation, `huc` for report). Frozen.
- `EndpointResult`: `endpoint`, `plan`, `manifest`, `ok: bool`, `message: str | None`.

Functions:

- `build_endpoint_request(payload, *, styles=ORDER_STYLES) -> EndpointRequest` — validate
  against allowlists (region ∈ `SUPPORTED_REGIONS`; endpoint ∈ `ENDPOINT_CONTRACTS`; style ∈
  styles; formats ⊆ contract.formats; endpoint-specific param presence rules), fail fast with
  `EndpointError`; no mutation.
- `endpoint_plan(request) -> DeliverablePlan` — deterministic, order-independent
  `Deliverable` list per the endpoint's contract (reuse `src.fulfillment.Deliverable` /
  `DeliverablePlan`; a documented `_stem(request)` mirrors fulfillment's).
- `endpoint_manifest(request, plan, *, checksums, sources=DEFAULT_SOURCES) -> dict` — schema
  `hydro-art/endpoint-manifest@1`; includes endpoint, request identity, `attribution_line`,
  per-file sha256; enforces exact checksum coverage (raise `EndpointError` on mismatch);
  `json.dumps(sort_keys=True)` byte-identical for equal inputs.
- `assert_sellable(request, *, styles=ORDER_STYLES)` — reuse the PRISM Rights gate for endpoint
  styles (delegates to `src.fulfillment.assert_sellable` semantics).
- `dispatch_endpoint(request, *, renderers) -> EndpointResult` — pure router: look up
  `renderers[request.endpoint]` (a callable seam), run the Rights gate first, call the renderer
  to obtain `checksums`, build the manifest, return `EndpointResult(ok=True, ...)`; on a
  renderer/validation failure return/raise per taxonomy. **No real I/O** — the renderer is
  injected, so this is fully offline-testable with fakes.

### `tools/render_endpoint.py` (NEW — non-offline, authored/run-later)

Thin CLI: parse args → `build_endpoint_request` → inject real renderer callables (wrapping
`build.py`'s pipeline, `render_monthly`/`render_state_yoy`, `render_terrain_print`,
`build_watershed_report`; each extends `render_common.py`) into `dispatch_endpoint` → write the
manifest sidecar next to the artifacts. Maps `EndpointError`→exit 1 (`ConfigError` taxonomy),
acquisition failures→exit 2. Not imported by `src/` or the suite.

## Acceptance criteria

- `ENDPOINT_CONTRACTS` documents all four endpoints (kinds, formats, naming, manifest flag).
- `build_endpoint_request` validates each endpoint's payload and fails fast with `EndpointError`;
  no mutation.
- `endpoint_plan` is deterministic and add-on-order-independent per endpoint.
- `endpoint_manifest` stamps source+version+attribution+sha256, is schema-versioned, enforces
  exact checksum coverage, and is byte-identical for equal inputs.
- `dispatch_endpoint` routes to the correct injected renderer, runs the Rights gate before
  marking deliverable, and returns a well-formed `EndpointResult`; PRISM style → refused.
- `tools/render_endpoint.py` wires the four real renderers (authored; real run deferred) and
  imports only from `src/` + `tools/render_common.py`.
- `src/endpoints.py` + tests import no GDAL/numpy/network; default 2D build byte-for-byte
  identical; full offline suite green; lint clean.

## Risks / notes

- **Scope creep into rendering.** This epoch must not touch `PIPELINE_STAGES` or renderer
  bytes; it only *describes and routes*. Keep all real render logic in `tools/` behind the
  injected seam.
- **Duplication risk.** Reuse `src.fulfillment` value objects/helpers instead of copying;
  `src/endpoints.py` is a generalization layer, not a fork.
- **Real execution deferred.** Per the roadmap decision, `tools/render_endpoint.py` is authored
  and offline-reasoned here; its real four-artifact run is exercised in Epoch 21 on the
  GDAL+NAS machine against Wahkiakum County.
