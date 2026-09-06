# Requirements — Production endpoint contracts & hardening (Epoch 19, #79–81)

## Goal

Give each of the four production endpoints a **documented, versioned output contract** and
a **single, offline-testable dispatch seam**, so Epoch 20 (unit/integration) and Epoch 21
(flagship e2e) have concrete, stable behaviour to assert against — without adding any art
feature or changing default rendered bytes.

## The four endpoints (single source of truth to encode)

| Endpoint | Deliverable kinds | Formats | Renderer path (real, run later) |
| --- | --- | --- | --- |
| `digital_image` | vector, raster | svg, png | `build.py` (2D `Pipeline`) |
| `animation` | motion | gif, mp4 | `tools/render_monthly.py` / `render_state_yoy.py` |
| `print_image` | raster | png, pdf, tiff | `tools/render_terrain_print.py` |
| `report` | document, figures | html, png | `tools/build_watershed_report.py` |

## Functional requirements

1. **Contracts.** A pure, offline `src/endpoints.py` defines an `EndpointContract` value
   object and an `ENDPOINT_CONTRACTS` table covering all four endpoints: deliverable kinds,
   allowed formats, filename/stem naming rule, whether a provenance manifest is required,
   and the success/failure signal shape. Mirrors `src/fulfillment.py` conventions.
2. **Request validation.** `build_endpoint_request(payload)` validates a request against
   the allowlists (region ∈ `SUPPORTED_REGIONS`, endpoint ∈ contracts, style, endpoint-specific
   params) and fails fast with a single user-facing `EndpointError`. No payload mutation.
3. **Deliverable plan.** `endpoint_plan(request)` returns a deterministic, add-on-order-independent
   list of expected `Deliverable`s per endpoint (reuses the `deliverable_plan` pattern).
4. **Provenance manifest.** `endpoint_manifest(request, plan, *, checksums, sources)` stamps
   source name+version, a name-sorted attribution line, and per-file sha256; schema is versioned
   (`hydro-art/endpoint-manifest@1`); byte-identical (`sort_keys`) for equal inputs; checksum
   coverage must match the plan exactly or raise.
5. **Rights gate + failure taxonomy.** The Rights gate (`assert_sellable`, reused/extended)
   runs before any asset is marked deliverable; validation failures use `EndpointError`,
   mapping to the existing `ConfigError`(exit 1)/`AcquisitionError`(exit 2) taxonomy at the CLI.
6. **Dispatch seam.** `dispatch_endpoint(request, *, renderers)` — a pure function taking an
   injectable mapping of endpoint → renderer callable — routes to the correct renderer and
   returns an `EndpointResult`. This keeps dispatch **offline-testable with fakes**.
7. **CLI wrapper (authored, run later).** `tools/render_endpoint.py` injects the real
   renderers into `dispatch_endpoint`, extends `render_common.py` (no duplicated recipe), and
   stamps the manifest. Real execution is deferred to the GDAL+NAS machine.

## Non-functional / discipline constraints

- **Offline suite:** `src/endpoints.py` and all its tests import only stdlib + `src.config`;
  no GDAL/numpy/network. `tools/render_endpoint.py` is outside the suite.
- **Byte-identical default:** no `PIPELINE_STAGES` change; the default 2D build stays
  byte-for-byte identical (verify via `tools/verify_determinism.py` / golden).
- **CRS/constants:** never inline `EPSG:5070`; reuse `src.crs.INTERNAL_CRS` where needed.
- **Rights:** public-domain sources only for anything flagged sellable.

## Out of scope (later epochs)

- Filling unit/integration coverage (Epoch 20); the in-suite all-endpoints e2e and real-data
  harness (Epoch 21); marketing gallery (Epoch 22); CI + release tag (Epoch 23).

## Acceptance

Each endpoint has a documented contract; a validated request produces a deterministic plan +
provenance-stamped manifest; dispatch routes correctly through injected fakes; the Rights gate
runs; the default build is byte-identical; the full offline suite is green.
