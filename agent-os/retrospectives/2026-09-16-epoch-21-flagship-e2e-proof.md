# Retrospective — Epoch 21: Flagship end-to-end proof (#85-87)

_Closed 2026-09-06 (single commit `26e8aee`); retro written 2026-09-16. **No
pre-registered watch-list** — the spec folder
(`2026-09-06-flagship-endpoints-e2e`) carries `planning/raw-idea.md`,
`planning/requirements.md`, `spec.md`, `tasks.md`, and
`implementation/report.md`, but no `planning/pre-analysis.md`. This is a
narrative closeout rather than a graded one. Third epoch of Generation 1
(Epochs 19-23, #79-93)._

## What the epoch was

The Generation 1 headline deliverable: **one region, one path, all four
endpoints** — proving Washington/Wahkiakum County/neon-basin walks through
`digital_image`, `animation`, `print_image`, and `report` with contract
satisfaction, full deliverable coverage, and whole-flow determinism. Builds
directly on Epoch 19's contract layer (`src/endpoints.py`) and Epoch 20's
integration test pyramid. All three planned items (#85-87) shipped and the
epoch closed on #87.

## What shipped (`26e8aee`)

### `src/endpoints.py` (EDIT, additive/offline, +97 lines)

Two pure e2e provenance functions, reused by the offline test, the golden
fixture, and the real harness:

- **`combined_manifest(results, *, sources)`** — aggregates a sequence of
  `EndpointResult` (one per endpoint) into schema `hydro-art/e2e-manifest@1`.
  Validates the results share one region/county/style and that endpoints are
  unique (`EndpointError` otherwise). `endpoints` maps each endpoint to its
  per-file manifest (order-independent). Byte-identical under
  `json.dumps(sort_keys=True)` for equal inputs.
- **`e2e_contract_digest(requests, *, sources)`** — the **render-independent**
  skeleton (schema `hydro-art/e2e-contract@1`): per-endpoint
  filenames/kinds/formats/dims + attribution + sources. No checksums, so it
  depends only on validated requests — deterministic and safe to commit as a
  golden.
- New constants `E2E_MANIFEST_SCHEMA` / `E2E_CONTRACT_SCHEMA`; `__all__`
  extended. No existing function changed.

### `tests/test_endpoints_e2e.py` (NEW, offline, 156 lines) — #85

6 test functions covering 3 groups:

- **Group 1 (combined provenance core):**
  `test_combined_manifest_aggregates_all_four` (schema, all four endpoints
  present, region/county/attribution);
  `test_combined_manifest_is_byte_identical` (reversed result order yields
  identical JSON); `test_combined_manifest_rejects_inconsistent_identity`
  (mismatched county raises `EndpointError`).
- **Group 2 (contract digest):**
  `test_e2e_contract_digest_is_render_independent_and_byte_identical` (schema,
  no checksums in output, per-endpoint formats match `ENDPOINT_CONTRACTS`,
  reversed request order yields identical JSON).
- **Group 2 (flagship single-flow):**
  `test_one_flow_proves_all_four_endpoints` — the headline test: walks
  Washington/Wahkiakum/neon-basin through all four endpoints using fake
  renderers writing real bytes to `tmp_path`, asserts every contract satisfied,
  every deliverable present in the combined manifest, attribution stamped, and
  an independent second walk produces byte-identical combined-manifest JSON.
- **Group 4 (golden):**
  `test_e2e_contract_digest_matches_committed_golden` — recomputes the digest
  and asserts equality with `tests/fixtures/golden/e2e/washington-wahkiakum.json`.

### `tools/render_all_endpoints.py` (NEW, non-suite, 138 lines) — #86

Real-data harness: builds the four requests for Wahkiakum County (default),
injects the four REAL renderer factories from `tools/render_endpoint.py`,
dispatches each, stamps a combined manifest, and (with `--check-determinism`)
renders the set twice and compares per-file sha256s. Exit taxonomy:
`EndpointError` -> 1, render failure -> 2, determinism drift -> 3. Imports only
`src/` + `tools.render_endpoint`; outside the suite.

### `tools/render_endpoint.py` (EDIT, +4 lines) — bug fix

Added the standard `sys.path.insert(0, REPO)` so the Epoch 19 CLI actually runs
via `python tools/render_endpoint.py` (it previously failed to import `src` under
direct invocation, the documented usage). Same fix applied to the new harness.
This is the bug the real run surfaced that the offline suite could not — the
Epoch 19 tests imported `src.endpoints` through pytest's path setup, so the
missing `sys.path` was invisible until someone ran the CLI directly.

### `tests/fixtures/golden/e2e/washington-wahkiakum.json` (NEW, 94 lines) — #87

The committed `e2e_contract_digest` for the flagship county
(render-independent). Lists all four endpoints with their planned filenames,
kinds, formats, and pixel dims (print carries `width_px`/`height_px`; others
`null`). Schema `hydro-art/e2e-contract@1`. The in-suite golden-match test
(`test_e2e_contract_digest_matches_committed_golden`) regression-guards this.

### Commit totals

11 files changed, 827 insertions, 2 deletions. Full offline suite: **833
passed** (was 827; +6 new e2e tests, no regressions).

## Real-data findings

The `tools/render_endpoint.py` import-path bug is the one real-run finding.
The pattern is familiar: pytest adds the repo root to `sys.path` automatically,
so a missing `sys.path.insert` is invisible to the suite — only direct
invocation (`python tools/render_endpoint.py`) exposes it. This is a milder
cousin of the wall-clock PDF date (`SOURCE_DATE_EPOCH`) and SMB `chflags` bugs
from prior epochs: the real invocation path surfaces a boundary condition that
no offline fake exercises.

No real four-artifact render was run in this epoch by design. The full
`tools/render_all_endpoints.py --check-determinism` run against Wahkiakum
County is deferred to the GDAL+NAS machine, inheriting the Epoch 19 deferral.

## Invariants held

- **Offline suite:** 833 passed (+6 new), no regressions.
- **2D default output byte-identical:** yes. The `src/endpoints.py` change is
  purely additive (two new functions + two constants + `__all__` extension). No
  existing function's signature or body changed. Nothing enters
  `PIPELINE_STAGES`.
- **`PIPELINE_STAGES` untouched:** yes. The epoch adds e2e orchestration and
  provenance; no pipeline module was touched.
- **Rights gate:** enforced. `dispatch_endpoint` runs `assert_sellable` before
  renderer lookup (tested by Epoch 19's
  `test_dispatch_runs_rights_gate_before_renderer`); `combined_manifest`
  inherits the per-endpoint manifest's `attribution` field. The flagship
  path uses `neon-basin` (PRISM-free, sellable).

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no
pre-registered watch-list to grade against. The spec's design section
identified three concerns:

1. **Reuse vs. fork of Epoch 19 machinery.** Confirmed refuted — the epoch
   consumed the existing `EndpointResult`, `dispatch_endpoint`,
   `ENDPOINT_CONTRACTS`, `flagship_e2e_requests`, and `FLAGSHIP_E2E` from
   `src/endpoints.py` directly. Zero new request/plan/manifest machinery was
   invented; the two new functions (`combined_manifest`, `e2e_contract_digest`)
   aggregate existing outputs.
2. **Real execution deferred safely.** Confirmed as expected — the harness
   authored and compiles; the real run was explicitly deferred. The
   `render_endpoint.py` import-path bug was the only surprise, and it was fixed
   in this commit.
3. **Golden stability.** The render-independent `e2e_contract_digest` depends
   only on validated requests and `ENDPOINT_CONTRACTS`, not on rendered bytes.
   This means the golden is stable against renderer changes (intentionally) —
   a contract change is the only thing that can break it, and that would be a
   real regression.

## Carry-forwards (honestly open, not passed)

- **No real four-artifact run.** `tools/render_all_endpoints.py` is authored
  and compile-checked but has not been exercised against a real GDAL+NAS host.
  The child-tool CLI flags in the four renderer bodies need verification during
  that run. (This was subsequently closed by the Generation 1 close-out commit
  `3e8acf9`.)
- **Real artifact sha256s not recorded.** The golden fixture is
  render-independent (no checksums). Real per-artifact sha256s belong in the
  existing `tests/fixtures/golden/registry.json` via `src.determinism`, to be
  recorded during the real run — matching the standing carry-forward from
  Epochs 10/14/16/18/19.
- **No live `verify_determinism.py` double-render.** Byte-identity rests on the
  "no renderer change" invariant, not a fresh double-render.

## Lessons

- **The `sys.path` import-path bug is a recurring pattern.** Pytest's automatic
  path setup hides missing `sys.path.insert` in `tools/` scripts. Every new
  `tools/*.py` script should include the standard preamble and be
  compile-checked with `python tools/<name>.py --help` (not just
  `ast.parse`). This epoch's fix to `render_endpoint.py` retroactively closed a
  latent Epoch 19 bug.
- **Forward-looking API surface pays off across epochs.** `FLAGSHIP_E2E`,
  `flagship_e2e_requests`, `combined_manifest`, and `e2e_contract_digest` were
  all authored in Epoch 19 (forward-looking) and consumed here without change.
  The Epoch 21 implementation was a single commit with no rework because the
  API was already tested and stable.
- **Render-independent goldens are the right regression strategy for contract
  epochs.** The `e2e_contract_digest` golden depends only on request validation
  and `ENDPOINT_CONTRACTS` — not on rendered bytes, GDAL versions, or host
  environment. This means the golden is stable across machines and Python
  versions, unlike the SVG/DEM sha256 goldens which are same-host-regression-
  only. The trade-off is that the golden does not catch renderer drift, but
  that is the job of `verify_determinism.py`, not the contract layer.
- **Consider adding a pre-analysis even for "aggregation" epochs.** As with
  Epochs 16, 18, and 19, none was written. The risks were small and all
  refuted, but the retrospective would be stronger with a graded watch-list.
