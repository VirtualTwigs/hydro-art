# Requirements — Order fulfillment tooling (roadmap #56–#57, Epoch 11.5)

## Problem

Epoch 11.5 (Revenue Validation) sells a **personalized county watershed print**
made-to-order (roadmap #56) and needs a **repeatable fulfillment pack** (#57): the
same order must always yield the same print-ready, correctly-titled, correctly-
attributed deliverable, so a solo operator can fulfill in minutes and re-generate a
past order byte-for-byte on a re-order or complaint.

Today that recipe exists only in the operator's head and in ad-hoc `tools/`
renderer flags. That is:

1. **Not reproducible.** No single record captures "what was sold" (region, county,
   style, size, title, add-ons, source versions) — so a re-order or a determinism
   check has nothing to re-run against.
2. **Rights-exposed.** The roadmap Rights gate requires a USGS/NHD/WBD source-credit
   line on *every sold asset*, and forbids selling any PRISM-derived asset until
   licensed. Nothing enforces either today.
3. **Error-prone.** Region/county/style/size are free-text; a typo produces a bad
   render halfway through fulfillment instead of a fast, clear rejection.

## Goal

A small, **offline-testable** core that turns a validated customer **order** into a
deterministic **deliverable plan** + **fulfillment manifest**, with title/subtitle
rules and the required attribution line baked in — plus a thin non-offline
`tools/` executor that actually renders and exports it by reusing the existing
county-clip render recipe. No new rendering capability; this is validated glue over
the pipeline that already ships.

## Scope

**In scope (this spec):**
- `src/fulfillment.py` — pure, stdlib-only order model + validation, style/size
  allowlists, title/attribution rules, deliverable plan, and manifest serializer.
- `tools/fulfill_order.py` — non-offline executor (order → render → stamped,
  attributed print-ready files + manifest). Smoke-tested only, outside the suite.
- `tests/test_fulfillment.py` — the offline unit suite (this spec's TDD target).

**Out of scope (operational, tracked in `agent-os/product/revenue-ledger.md`, not
code):** publishing the marketplace listing (#56), the intake form UI, funnel
instrumentation (#58), and the revenue-gate decision (#59).

## Constraints (inherited invariants — do not break)

- **Offline discipline.** `src/fulfillment.py` imports **stdlib only** (like
  `src/jobs.py` / `src/packaging.py`) — no GDAL/numpy, no `web/`, no `tools/`. The
  heavy render/export lives in `tools/fulfill_order.py`, eagerly importing GIS libs
  and reusing `render_common` / `src.export`; it stays out of the test suite.
- **Validate at the boundary, fail fast.** `build_order` validates every field
  against allowlists (reusing `SUPPORTED_REGIONS` from `src/config.py`) and raises a
  single user-facing `OrderError`, mirroring `build_settings` /
  `settings_from_payload`.
- **Determinism.** Identical order → identical deliverable plan → byte-identical
  `sort_keys` manifest. This is what makes a re-order reproducible (and dovetails
  with the Epoch 10 determinism verifier used as fulfillment QA).
- **Injectable seams for testability.** The style and size catalogs are module
  constants but injectable (`styles=`, `sizes=` params) so tests can exercise the
  Rights-gate guard with a fabricated PRISM-using style without shipping one.
- **The 2D default output stays byte-identical.** Nothing here enters
  `PIPELINE_STAGES`.

## Rights gate (enforced in code)

- Every order's title block carries an **attribution line** built from its data
  sources (default: USGS NHDPlus HR / NHD / WBD); the manifest records each source +
  version. No deliverable plan is produced without it.
- Each style declares `uses_prism`. `build_order` / `assert_sellable` **raises
  `OrderError`** for any `uses_prism=True` style — the two approved art directions
  (`neon-basin`, `elevation-tint`) are PRISM-free, so the near-term offer is clear,
  and a future PRISM-based style cannot be sold by accident.
