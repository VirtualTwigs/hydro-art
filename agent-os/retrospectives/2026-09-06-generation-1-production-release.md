# Retrospective — Generation 1: Production Release (Epochs 19–23, #79–93)

_Closed 2026-09-06. **No pre-registered watch-list** — as with Epoch 16, none of the five
Generation 1 spec folders (`2026-09-05-production-endpoint-contracts`,
`2026-09-06-test-pyramid-completion`, `2026-09-06-flagship-endpoints-e2e`,
`2026-09-06-marketing-gallery`, `2026-09-06-release-packaging-ci`) carries a
`planning/pre-analysis.md` (only `raw-idea.md` / `requirements.md`). This is a narrative
closeout rather than a graded one; the missing pre-analysis is again a process observation
(see Lessons)._

## What the generation was

Generation 1 was explicitly **not** an art-feature generation. No new water layer, no new
symbology, nothing added to `PIPELINE_STAGES`. The goal was to harden the existing engine
into a **documented, tested, reproducible v1.0** — turn "it renders" into "it ships with a
contract, a determinism guarantee, a rights ledger, a CI pyramid, and a release gate."
Every epoch rode seams that already existed (`src/fulfillment`'s request→deliverable seam,
the Rights gate `assert_sellable`, `src/determinism`'s golden-hash registry), so the work
was contracts + tests + goldens + packaging rather than new machinery. The generation
closed on #93 with the offline release gate reporting **READY** (v1.0.0), pending the two
deferred real-host steps below.

## What shipped

### Epoch 19 (#79–81) — Production endpoint contracts & hardening (`d3f4e78`)

`src/endpoints.py` — versioned output contracts + a `dispatch_endpoint(request, *,
renderers)` seam over the four production endpoints (`digital_image`, `animation`,
`print_image`, `report`). Rather than forking four renderers, it **reuses** the
`src/fulfillment` request→deliverable seam and the Rights gate: each endpoint stamps source
version + attribution + checksum, and `assert_sellable` still governs what may ship.
Non-offline real-artifact renderer factories live in `tools/render_endpoint.py` (outside
the suite). Pure/offline contract logic in `src/`, real rendering in `tools/` — the
generation's first clean application of the split.

### Epoch 20 (#82–84) — Unit & integration test completion (`f7f1c6d`)

`tests/test_endpoints_integration.py` drives all four orchestrators **offline** with an
injected disk-writing fake renderer — the four contracts exercised end-to-end without GDAL
or network. `src/optimize.py` raised to 100%. Added `[tool.coverage.*]` to `pyproject.toml`
plus a non-suite `tools/coverage_report.py`; coverage settled at a **94% baseline**. The
residual ~6% is deliberate: legitimate GDAL/network I/O seam bodies (`pyogrio`/`urllib`
reads) that are covered by injected fakes at their call sites, not by executing the real
I/O — exactly the offline discipline, not a gap to paper over.

### Epoch 21 (#85–87) — Flagship all-four-endpoints e2e proof (`26e8aee`)

`src/endpoints.py` gained `combined_manifest` + `e2e_contract_digest` — a
**render-independent skeleton** that captures the contract shape without depending on
rendered bytes. `tests/test_endpoints_e2e.py` proves one region / one path
(**Washington / Wahkiakum / neon-basin**) flows through all four endpoints with contract +
determinism assertions, pinned by committed golden
`tests/fixtures/golden/e2e/washington-wahkiakum.json`. Opt-in real harness
`tools/render_all_endpoints.py --check-determinism` for the GDAL-host double-render. The
render-independent digest is the key idea: it lets an **offline** test meaningfully guard
against contract regression on a real path it cannot itself render.

### Epoch 22 (#88–90) — High-resolution marketing gallery (`db42655`)

`src/gallery.py` — a curated matrix across **all 4 regions × both public-domain styles ×
all 4 endpoints** plus a rights ledger (schema `hydro-art/gallery-ledger@1`) with
exact-coverage sha256 stamping (every matrix cell accounted for, no orphan/no gap).
Non-suite `tools/render_gallery.py` produces the real high-res artifacts; self-contained
`web/gallery.html` presents them; golden `tests/fixtures/golden/gallery/ledger.json` pins
the ledger. The ledger is the sellability audit trail — every gallery asset traces to a
public-domain source with attribution.

### Epoch 23 (#91–93) — Release packaging, CI & reproducibility gate (`f233773`)

Pure/offline `src/release.py` (schema `hydro-art/release-gate@1`) recomputes the
render-independent goldens (gallery ledger + e2e contract digest) **and** aggregates
`src/determinism` verdicts into a single ready/blocked verdict. `src/changelog.py`
generates `CHANGELOG.md` from the roadmap epochs. Two GitHub workflows:
`.github/workflows/ci.yml` (the offline pyramid — runs anywhere, no GDAL) and
`reproducibility.yml` (gated real-data determinism on a self-hosted GDAL runner). CLIs:
`tools/release_gate.py` + `tools/build_changelog.py`. `pyproject.toml` bumped to
**1.0.0**; `CHANGELOG.md` generated. To avoid drift, `FLAGSHIP_E2E` /
`flagship_e2e_requests` were added to `src/endpoints.py` as the **single source** shared by
both the e2e proof (#85–87) and the release gate (#91–93) — the gate and the test cannot
disagree about what the flagship path is.

## Real-data findings

Unlike a layer epoch, Generation 1's "real run" is the **release gate itself**, run offline
against the committed goldens (`tools/release_gate.py --offline-only`):

```
hydro-art/release-gate@1: v1.0.0
  render-independent goldens:
    OK   gallery-ledger: matches gallery/ledger.json
    OK   e2e-contract-digest: matches e2e/washington-wahkiakum.json
  determinism: skipped (--offline-only)
  verdict: READY
```

Both render-independent goldens match; the only line the offline gate **cannot** turn green
is `determinism`, which it honestly reports as skipped — the real double-render lives in
`reproducibility.yml` / `tools/render_all_endpoints.py --check-determinism` on a GDAL host.
The verdict is therefore **READY-pending-real-determinism**, which is exactly what the gate
reports rather than overclaiming. The flagship path (Washington/Wahkiakum/neon-basin) is
the one concrete "all four endpoints agree" proof; broadening to more region/style paths is
a carry-forward.

## The bug the real (direct-run) invocation surfaced

The recurring project lesson this generation is not a resolution/CRS/topology bug — it is a
**packaging** bug that offline pytest could not surface: several of the new `tools/` scripts
(`release_gate.py`, `build_changelog.py`, `render_gallery.py`, `render_endpoint.py`,
`render_all_endpoints.py`) are meant to be run directly (`python tools/foo.py`), but the
suite always imports `src.*` with the repo root already on `sys.path`. Run directly from a
different cwd, `import src.endpoints` fails — the exact failure the offline suite is
structurally blind to, because the suite never invokes a `tools/` script as `__main__`. The
fix is the now-uniform `sys.path.insert(0, str(REPO))` shim at the top of each direct-run
tool (confirmed present in all five new Generation 1 tools). It is minor, but it is the
generation's instance of the standing lesson: **the thing offline fakes can't verify is the
real invocation path**, and here that path was "a human runs the CLI," not "GDAL reads a
GDB."

## Invariants held

- **Offline suite:** **850 passing** (grew across all five epochs; +60 warnings are the
  pre-existing `svgo`-absent notices, not failures). No network / GDAL / real datasets; no
  GDAL-backed imports leaked into `src/` or `tests/`. `src/endpoints.py`, `src/gallery.py`,
  `src/release.py`, and `src/changelog.py` are all pure/offline; every real artifact and
  double-render lives in an opt-in `tools/` harness.
- **2D default output byte-identical:** yes — trivially. Nothing in this generation touched
  the render path, the layers, or the config defaults; it added contracts, tests, goldens,
  and packaging *around* the unchanged engine. The default `build.py` render is unchanged
  from Epoch 18.
- **`PIPELINE_STAGES` untouched:** yes — no stage added, removed, or reordered. This was a
  hard non-goal of the generation and it held completely.
- **Rights gate:** honored and, importantly, **reused rather than re-implemented**. Every
  endpoint routes through `fulfillment.assert_sellable`; the gallery rights ledger stamps
  each asset's public-domain source (USGS NHDPlus HR / NHD / WBD, nClimGrid) + attribution.
  No PRISM-derived asset is sellable, consistent with the Epoch 14 close. Only
  public-domain sources appear in shippable assets.

## What went well

- **The offline / non-offline split scaled cleanly across all five epochs.** Every epoch
  put pure contract/ledger/gate logic in `src/` (offline-tested) and every real render or
  double-render in `tools/` (opt-in). The split that started as a testing discipline turned
  out to be exactly the right seam for a *release* generation: the gate can run READY-checks
  anywhere, and only the genuinely-real determinism check is deferred to a GDAL host.
- **Reusing the contract + Rights gate instead of forking renderers.** `dispatch_endpoint`
  over the existing `fulfillment` seam meant four endpoints without four renderers, and the
  Rights gate governs all of them by construction. No sellability logic was duplicated.
- **Render-independent goldens are the quiet win.** `e2e_contract_digest` and the gallery
  ledger let an offline test guard a real render path it cannot execute — a meaningful
  regression guard without GDAL. This is what makes `tools/release_gate.py --offline-only`
  a real signal rather than a stub.
- **Single-source `FLAGSHIP_E2E`.** Sharing one definition between the e2e proof and the
  release gate removed a whole class of "the test and the gate disagree" drift before it
  could happen.

## Gotchas found

- **Direct-run `tools/` scripts need the `sys.path` shim** (detailed above) — the offline
  suite cannot catch this because it never runs a tool as `__main__`.
- **`--offline-only` READY is not a full READY.** The offline gate structurally cannot turn
  the `determinism` line green; treat its READY as "offline preconditions met," and read the
  skipped line as the outstanding requirement, not a pass.
- **No pre-analysis / watch-list for any of the five specs** — the Epoch 8/9/12/14 practice
  of pre-registering risks before implementation was skipped again (as in Epoch 16). For a
  packaging generation the cost was low, but the `sys.path` direct-run risk is precisely the
  kind of "offline suite is blind to this path" item a watch-list is meant to force.

## Carry-forwards

- **Tagging `v1.0` is a deferred, explicit user step — do not tag from this close.** It
  additionally requires the **real** double-render reproducibility gate to pass on a
  GDAL + NAS machine (`reproducibility.yml` / `tools/render_all_endpoints.py
  --check-determinism`), which the offline suite cannot run. Until that green exists, v1.0 is
  **READY-pending**, not released. Open, not passed.
- **Real all-four-endpoints double-render.** The e2e proof and gallery are validated offline
  against goldens; the actual GDAL-host render of Washington/Wahkiakum through all four
  endpoints (and the gallery matrix) has not been produced in this session. This is the same
  standing "full `build.py` byte-compare needs a GDAL host" carry-forward inherited since
  Epoch 9/10/14 — now also covering the endpoint/gallery artifacts.
- **Flagship path is one region/style/path.** The e2e determinism proof covers
  Washington/Wahkiakum/neon-basin only. Broadening `flagship_e2e_requests` to more
  region/style combinations would strengthen the gate; deferred deliberately to keep the
  golden small.
- **Coverage residual is I/O seam bodies.** The 94% baseline's remaining misses are real
  GDAL/network read paths covered by fakes at call sites; closing them would require running
  real I/O in the suite, which the offline discipline forbids. Recorded as intentional, not
  as debt to erase.

## Lessons

- **Restore the pre-analysis/watch-list step** (third generation running without it). Even a
  packaging generation has an "offline can't verify this" risk — here the direct-run
  `sys.path` path — and a pre-registered watch-list is the cheapest way to smoke for it.
- **A READY verdict must name what it can't check.** The offline gate's honest
  `determinism: skipped` line is the model: a release gate earns trust by reporting the
  boundary of its own evidence, not by rounding up to READY.
- **Reuse the seam before writing a renderer.** Four endpoints over one `fulfillment` seam +
  one Rights gate is why the generation stayed small — the same lesson as Epoch 16's reuse of
  the Epoch 15 seams, now applied to contracts instead of taxonomy.
- **Render-independent goldens are how offline tests guard real paths.** When the artifact
  is too expensive/GDAL-bound to produce in the suite, pin its render-independent skeleton
  and check *that* offline — it caught contract drift here and it will again.
