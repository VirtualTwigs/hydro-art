# Requirements — Epoch 21 (Flagship end-to-end proof, #85–87)

## Goal
Prove the flagship claim — **one region, one path, all four endpoints** — at two layers: an
in-suite offline orchestration e2e (fakes) and an opt-in real-artifact harness (GDAL+NAS),
regression-guarded by a golden fixture. No new art feature; default build byte-identical.

## Functional requirements

### Combined e2e provenance (offline core, in `src/endpoints.py`)
- `E2E_MANIFEST_SCHEMA = "hydro-art/e2e-manifest@1"`.
- `combined_manifest(results, *, sources=DEFAULT_SOURCES) -> dict` — aggregate a sequence of
  `EndpointResult` into one provenance document: shared region/county/style (must be
  consistent across results, else `EndpointError`), per-endpoint sub-manifests keyed by
  endpoint (sorted), unique-endpoint coverage check, attribution + sources. Byte-identical
  under `json.dumps(sort_keys=True)` for equal inputs.
- `e2e_contract_digest(requests, *, sources=DEFAULT_SOURCES) -> dict` — the **render-
  independent** skeleton (schema `hydro-art/e2e-contract@1`): per-endpoint planned
  filenames/kinds/formats/dims + attribution + sources, derived purely from validated
  requests (no checksums). This is the committable golden content and the offline assertion
  target. Deterministic + byte-identical.

### #85 Offline all-endpoints e2e orchestration test
- New `tests/test_endpoints_e2e.py`: ONE flow builds four requests from a shared base
  (Washington/Wahkiakum/neon-basin + per-endpoint params), dispatches each through
  `dispatch_endpoint` with a fake renderer that writes real bytes to `tmp_path` and hashes
  them, aggregates via `combined_manifest`, and asserts:
  - all four endpoints present, each plan matches its `ENDPOINT_CONTRACTS` entry;
  - the combined manifest carries every endpoint's deliverables + attribution;
  - **determinism**: re-running the whole flow yields byte-identical combined-manifest JSON.
- Fully offline (fakes + `tmp_path`; no GDAL/network/datasets).

### #86 Real-data e2e harness (opt-in, non-suite)
- New `tools/render_all_endpoints.py`: argparse (region/county/style/out-dir) → build four
  requests → inject the four REAL renderers (reuse the factories in
  `tools/render_endpoint.py`) → dispatch each → `combined_manifest` → write combined manifest
  sidecar; a `--check-determinism` mode renders twice and compares per-file sha256s (and can
  record/verify the golden via `src.determinism`). Imports only `src/` + `tools/render_endpoint`;
  never imported by `src/` or the suite. Exit taxonomy: `EndpointError`→1, render→2,
  determinism drift→3.
- Real execution deferred to the GDAL+NAS machine (documented in the report).

### #87 E2E golden fixture
- Commit `tests/fixtures/golden/e2e/washington-wahkiakum.json` = the `e2e_contract_digest`
  for the chosen county (render-independent). An in-suite test asserts the freshly-computed
  digest equals the committed golden (regression guard on contracts/plans/provenance).
- Real artifact sha256s remain the province of the `--check-determinism` harness run on the
  GDAL machine (recorded into `registry.json` via `src.determinism`), deferred.

## Non-functional / discipline
- Offline suite stays green + offline; no new GDAL/network import in `src/` or `tests/`.
- Default 2D build byte-for-byte identical (no `PIPELINE_STAGES`/renderer byte change).
- `tools/render_all_endpoints.py` outside the suite.
- TDD: 2–8 focused tests first per group.

## Out of scope
- CI wiring of the harness (Epoch 23); the real four-artifact run itself (deferred to
  GDAL+NAS), new renderers or art features.

## Acceptance
- `tests/test_endpoints_e2e.py` green: all four endpoints in one flow, contract + determinism.
- `combined_manifest`/`e2e_contract_digest` byte-identical + coverage-checked.
- Golden fixture committed; the golden-match test is green.
- `tools/render_all_endpoints.py` authored, imports clean, compiles.
- Full offline suite green; default build byte-identical.
