# Retrospective — Epoch 19: Production endpoint contracts & hardening (#79-81)

_Closed 2026-09-06 (single commit `d3f4e78`); retro written 2026-09-16. **No
pre-registered watch-list** — the spec folder
(`2026-09-05-production-endpoint-contracts`) carries `planning/raw-idea.md`,
`planning/requirements.md`, `spec.md`, `tasks.md`, and
`implementation/report.md`, but no `planning/pre-analysis.md`. This is a
narrative closeout rather than a graded one. First epoch of Generation 1
(Epochs 19-23, #79-93)._

## What the epoch was

Introduce a pure, offline `src/endpoints.py` that gives the four production
endpoints (`digital_image`, `animation`, `print_image`, `report`) a documented,
versioned **output contract**, a fail-fast **request validator**, a deterministic
**deliverable plan**, a provenance **manifest**, and an injectable **dispatch
seam**. Adds no art feature and no `PIPELINE_STAGES` change — the default 2D
build stays byte-for-byte identical. This epoch generalizes `src/fulfillment.py`
from the single print order to all four endpoints and is the foundation the
Epoch 20 test pyramid and Epoch 21 flagship e2e assert against.

All three planned items (#79-81) shipped and the epoch closed on #81.

## What shipped (`d3f4e78`)

### `src/endpoints.py` (NEW, pure/offline, 339 lines)

- **`ENDPOINTS`** tuple + **`ENDPOINT_CONTRACTS`** dict documenting all four
  endpoints — each with ordered `(fmt, kind)` pairs, a `stem_suffix` for
  filename disambiguation, and `requires_manifest: bool`. The contracts:

  | endpoint | formats | kinds | stem_suffix |
  |---|---|---|---|
  | `digital_image` | svg, png | vector, raster | `digital` |
  | `animation` | gif, mp4 | motion | `motion` |
  | `print_image` | png, pdf, tiff | raster | `print` |
  | `report` | html, png | document, figures | `report` |

- **`build_endpoint_request(payload, *, styles, sizes)`** — allowlist validation
  against `SUPPORTED_REGIONS`, `ENDPOINT_CONTRACTS`, `ORDER_STYLES`, and
  endpoint-specific param rules (print requires `size`; report requires `huc`;
  animation requires `year` or `months`). Fail-fast `EndpointError`, no payload
  mutation, returns a frozen `EndpointRequest`.

- **`endpoint_plan(request)`** — deterministic, order-independent `Deliverable`
  list per the endpoint's contract. Reuses `src.fulfillment.Deliverable` /
  `DeliverablePlan`; a documented `_stem(request)` mirrors fulfillment's naming.
  Print carries pixel dims from `SIZES`.

- **`endpoint_manifest(request, plan, *, checksums, sources)`** — schema
  `hydro-art/endpoint-manifest@1`; stamps endpoint + request identity +
  `attribution_line` + per-file sha256. Enforces exact checksum coverage (raise
  `EndpointError` on missing or unexpected files). Byte-identical under
  `json.dumps(sort_keys=True)` for equal inputs.

- **`assert_sellable(request)`** — PRISM Rights gate, mirroring
  `src.fulfillment.assert_sellable` semantics; raises `EndpointError` for any
  `uses_prism` style.

- **`dispatch_endpoint(request, *, renderers)`** — pure router: Rights gate
  **before** renderer lookup/call, then injected renderer seam obtains checksums,
  builds manifest, returns `EndpointResult(ok=True, plan, manifest)`. No real
  I/O — fully offline-testable with fakes.

- Also added in this commit but forward-looking for Epochs 21/23:
  `combined_manifest`, `e2e_contract_digest`, `flagship_e2e_requests`, and
  `FLAGSHIP_E2E` (the canonical Wahkiakum County, WA all-four-endpoints path,
  single source of truth shared by the e2e proof and release gate).

### `tools/render_endpoint.py` (NEW, non-offline, 189 lines)

Thin CLI: parse args, `build_endpoint_request`, inject four real renderer
callables (wrapping `build.py`, `render_state_yoy.py`, `render_terrain_print.py`,
`build_watershed_report.py`) into `dispatch_endpoint`, write manifest sidecar.
Exit taxonomy: `EndpointError` -> exit 1, render failure -> exit 2. Imports only
`src.endpoints` at top level; GIS work deferred to subprocess calls. Not imported
by `src/` or the suite.

### `tests/test_endpoints.py` (NEW, 228 lines)

13 test functions (some parametrized, expanding to **24 collected tests**) across
the 4 task groups:

- TG1 (contracts + validation): `test_all_four_endpoints_have_contracts`,
  `test_build_accepts_valid_request_per_endpoint` (parametrized x4),
  `test_build_rejects_invalid_request` (parametrized x6),
  `test_build_does_not_mutate_payload`.
- TG2 (plan + manifest + Rights): `test_plan_is_deterministic_and_order_independent`,
  `test_print_plan_carries_pixel_dims`, `test_manifest_versioned_and_byte_identical`,
  `test_manifest_enforces_exact_checksum_coverage`,
  `test_rights_gate_refuses_prism_style`.
- TG3 (dispatch): `test_dispatch_routes_to_correct_renderer`,
  `test_dispatch_runs_rights_gate_before_renderer`,
  `test_dispatch_enforces_checksum_coverage`.
- TG4 (gap-filling): `test_every_contract_round_trips_build_plan_manifest`.

### Commit totals

10 files changed, 1250 insertions. Full offline suite: **814 passed** (+24 new
endpoint tests, no regressions).

## Real-data findings

No real-data run in this epoch by design. The spec explicitly scoped this as
"author offline, run later" — the real four-artifact run of
`tools/render_endpoint.py` against Wahkiakum County, WA was deferred to
Epoch 21 on the GDAL+NAS machine. No bug-the-real-run-surfaced to report here;
the expected pattern (resolution drift, silent truncation, wall-clock PDF dates,
SMB chflags) would apply to the renderers injected at Epoch 21, not to the
pure contract layer.

## Invariants held

- **Offline suite:** 814 passed (24 new), no regressions.
- **2D default output byte-identical:** yes. No `PIPELINE_STAGES` change, no
  renderer change — the epoch only describes and routes.
- **`PIPELINE_STAGES` untouched:** yes. The commit adds `src/endpoints.py` and
  `tools/render_endpoint.py` but touches no pipeline module.
- **Rights gate:** enforced. `assert_sellable` refuses any `uses_prism` style
  before the renderer is looked up or called; tested by
  `test_dispatch_runs_rights_gate_before_renderer` (a fake records that the
  renderer was never invoked for a PRISM-flagged style).

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no pre-registered
watch-list to grade against. The spec's "Risks / notes" section flagged three
concerns:

1. **Scope creep into rendering.** Confirmed refuted — zero `PIPELINE_STAGES`
   change, zero renderer bytes touched. The epoch stayed purely in the
   "describes and routes" lane.
2. **Duplication risk (forking `src/fulfillment`).** Confirmed refuted —
   `src/endpoints.py` imports `Deliverable`, `DeliverablePlan`,
   `attribution_line`, `DEFAULT_SOURCES`, `ORDER_STYLES`, and `SIZES` from
   `src.fulfillment` rather than re-implementing them. The module is a
   generalization layer, not a fork.
3. **Real execution deferred.** Confirmed as expected — `tools/render_endpoint.py`
   is authored and compiles but its real run was intentionally deferred to
   Epoch 21.

## The reuse story (why this epoch was clean)

This epoch is the most direct reuse of `src/fulfillment.py`'s architecture in
the project. The pattern — frozen request value object, allowlist validation at
the boundary, deterministic deliverable plan, provenance manifest with exact
checksum coverage, injectable renderer seam — was already proven in Epoch 11.5.
`src/endpoints.py` generalizes it from one print order to four endpoints without
inventing new machinery, which is why the implementation was a single commit with
no rework. The fulfillment seam's `ORDER_STYLES` and `SIZES` catalogs are
imported and reused directly, not shadowed.

## Carry-forwards (honestly open, not passed)

- **No real four-artifact run.** `tools/render_endpoint.py`'s subprocess-based
  renderer callables were authored against the current `tools/` entry points but
  have not been exercised against a real GDAL+NAS host. The child-tool CLI flags
  need verification during the Epoch 21 real run. (This was closed by Epoch 21
  commit `26e8aee`.)
- **Lint baseline.** `RUF022` (unsorted `__all__`) was left consistent with the
  `src/fulfillment.py` convention; the repo's ruff config (`line-length=88`)
  does not enforce default RUF rules (165-error repo-wide baseline). Not a
  regression, but the baseline is large.
- **No live byte-identical `verify_determinism.py` double-render was run for
  this epoch.** Byte-identity rests on the "no renderer change" invariant, not a
  fresh double-render — matching the standing carry-forward from Epochs 9/10/14/16/18.

## Lessons

- **Generalize, don't fork.** The `src/fulfillment.py` template was directly
  importable and reusable for the four-endpoint generalization. The discipline of
  exporting value objects (`Deliverable`, `DeliverablePlan`) and pure functions
  (`attribution_line`) with stable signatures paid off here — `src/endpoints.py`
  is a thin consumer, not a parallel implementation.
- **"Author offline, run later" is a valid scope cut for a contract epoch.** By
  deferring real rendering to Epoch 21, this epoch stayed fast and clean (one
  commit, 24 tests, no rework). The key discipline is that the deferred work is
  **named and scheduled**, not silently dropped.
- **Forward-looking API surface is worth the cost.** `FLAGSHIP_E2E`,
  `flagship_e2e_requests`, `combined_manifest`, and `e2e_contract_digest` were
  authored in this epoch for Epochs 21 and 23. This meant those downstream epochs
  consumed a stable, tested API rather than inventing their own — a deliberate
  front-loading that kept the Generation 1 close-out clean.
- **Consider adding a pre-analysis even for "pure contract" epochs.** As with
  Epochs 16 and 18, none was written. The risks were small and all refuted, but
  naming them up front in a pre-analysis would have cost little and made this
  retrospective a graded one rather than a narrative one.
