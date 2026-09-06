# Implementation report — Production endpoint contracts & hardening (Epoch 19, #79–81)

**Status:** implemented (offline), not committed. First epoch of Generation 1.

## What shipped

- **`src/endpoints.py` (NEW, pure/offline)** — a four-endpoint contract + dispatch layer
  generalizing `src/fulfillment.py`:
  - `ENDPOINTS` + `ENDPOINT_CONTRACTS` documenting `digital_image` (svg/png),
    `animation` (gif/mp4), `print_image` (png/pdf/tiff), `report` (html/png) — each with
    ordered `(fmt, kind)` pairs, deliverable kinds, and a stem suffix.
  - `build_endpoint_request` — allowlist validation (region/endpoint/style/formats +
    endpoint-specific: print→size, report→huc, animation→year|months), fail-fast
    `EndpointError`, no payload mutation.
  - `endpoint_plan` — deterministic, order-independent `Deliverable` list (reuses
    `src.fulfillment.Deliverable`/`DeliverablePlan`; print carries pixel dims).
  - `endpoint_manifest` — schema `hydro-art/endpoint-manifest@1`, source+version+attribution
    +per-file sha256, exact checksum-coverage enforcement, byte-identical under `sort_keys`.
  - `assert_sellable` — PRISM Rights gate (raises `EndpointError`).
  - `dispatch_endpoint(request, *, renderers)` — pure router: Rights gate **before** renderer
    lookup/call → injected renderer seam → manifest → `EndpointResult`. Fully offline-testable.
- **`tools/render_endpoint.py` (NEW, non-offline, authored/run-later)** — thin CLI injecting
  the four real renderers (wrapping `build.py`, `render_state_yoy.py`, `render_terrain_print.py`,
  `build_watershed_report.py`) into `dispatch_endpoint`, writing a manifest sidecar. Imports
  only `src.endpoints` at top; GIS work is via subprocess. Exit taxonomy: `EndpointError`→1,
  render failure→2.
- **`tests/test_endpoints.py` (NEW)** — 24 offline tests across the 4 task groups.

## Verification

- `pytest tests/test_endpoints.py` → **24 passed**.
- Full offline suite `pytest -q` → **814 passed** (no regressions; warnings pre-existing).
- Offline discipline: `src/endpoints.py` imports only stdlib + `src.config` + `src.fulfillment`
  (grep-verified: no GDAL/numpy/network/`tools`/`web`). `tools/render_endpoint.py` compiles.
- Byte-identical default: no `PIPELINE_STAGES` / renderer change — this epoch only describes
  and routes.
- Lint: in-scope files clean except `RUF022` (unsorted `__all__`), left consistent with the
  `src/fulfillment.py` convention; the repo's ruff config sets only `line-length=88` and does
  not enforce default RUF rules (165-error repo-wide baseline).

## Deferred (per roadmap decision: author offline, run later)

- The **real four-artifact run** of `tools/render_endpoint.py` against **Wahkiakum County, WA**
  is exercised in **Epoch 21** on the GDAL+NAS machine. The child-tool CLI flags in the renderer
  bodies reflect the current entry points and should be verified during that run.

## Item gate

Each endpoint has a documented contract; a validated request yields a deterministic plan +
provenance manifest; dispatch routes through an injectable seam with the Rights gate enforced;
default build byte-identical; full offline suite green — ready for Epoch 20 (unit/integration
completion) and Epoch 21 (flagship e2e).
