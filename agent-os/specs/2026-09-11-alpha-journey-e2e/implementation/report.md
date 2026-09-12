# Implementation report — Alpha customer-journey e2e (Epoch 24)

## #94 — Draft render tier (2026-09-11)

**What shipped (the only pre-commit code change; offline suite).**
- `src/config.py` — `SUPPORTED_PNG_SIZES` extended to `(512, 1024, 2048, 4096, 8192, 16384, 32768,
  65536)`, kept sorted ascending; docstring notes the small tiers are draft/preview sizes for fast
  design + e2e iteration. `DEFAULTS["png_size"]` unchanged at `4096`, so default output is unchanged.
  Validation is unchanged — `build_settings` already rejects any value not in the tuple.
- `src/cli.py` — `--png-size` help lists the new sizes and marks 512/1024/2048 as draft (default 4096).
  Still `type=int` with no `choices`; validation stays in `build_settings`.
- `tests/test_export_config.py` — added `test_png_size_draft_tiers_present_and_sorted` and
  `test_png_size_accepts_draft_tiers`. Existing `test_png_size_defaults_to_4096` and
  `test_png_size_rejects_unsupported` (1234) unchanged and still pass — no regression.

**Verification.**
- `tests/test_export_config.py` — 8 passed.
- Full offline suite — **892 passed**. No `PIPELINE_STAGES` edit; default 2D output byte-identical.

**Committed with:** the Epoch 24 roadmap entry (#94–#98), this spec (`spec.md`,
`planning/requirements.md`, `tasks.md`), per the "commit before development of tests" instruction.

## #95–#98 — Playwright browser harness

Specified in `spec.md` / `tasks.md`; developed after the foundation commit. Non-offline, opt-in
(needs a live `serve.py` + a pre-extracted county), lives under `tests/e2e/`, never in the offline
Python suite. Renders use the #94 draft tier so the e2e loop is fast.
