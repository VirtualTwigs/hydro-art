# Implementation report — Waterbody regional presets (roadmap W4, mechanism slice)

## What shipped

The **preset *mechanism*** for W4 ("establish print and screen presets"),
decoupling the mechanism from the art-direction *values* (which stay human-tunable).
A named preset is a config-time convenience directive that expands to a bundle of
existing `WaterbodySettings` fields — no new render behavior, no pipeline change.

Scope confirmed with the user on 2026-08-12: ship provisional, clearly-marked
preset values now; tune them later after human review of real-region output.

## Changes

- `src/config.py`
  - `WATERBODY_PRESETS` — `screen` (mirrors the default on-screen build) and
    `print` (bolder `stroke_width=0.9`, positive area thresholds `100k`/`250k` m²
    to declutter tiny ponds for ink/large-format). Values carry a prominent
    **provisional-placeholder** note pointing at the W4 human-review deferral.
  - `SUPPORTED_WATERBODY_PRESETS = tuple(WATERBODY_PRESETS)`. Both exported.
  - `_coerce_waterbodies` pops a `preset` directive and layers
    `defaults < preset < explicit provided fields`, raising `ConfigError` on an
    unknown name. `preset` is consumed, never stored on the frozen
    `WaterbodySettings`, so a build without a preset is byte-identical to before.
- `src/cli.py`
  - `--waterbody-preset` (`choices=SUPPORTED_WATERBODY_PRESETS`, default `None`) →
    `waterbodies["preset"]`. Argparse rejects unknown names (exit 2).
  - The nested `waterbodies` merge now starts from `{}` instead of
    `dict(DEFAULTS["waterbodies"])`. This is behavior-preserving —
    `_coerce_waterbodies` fills every missing field from defaults — and is required
    so a preset bundle isn't shadowed by pre-seeded defaults that are
    indistinguishable from explicit values.

## Precedence (verified)

`defaults < YAML < CLI`, and within the block `defaults < preset < explicit
--waterbody-* / explicit YAML sub-keys`. A CLI preset overrides a YAML preset. An
explicit `--waterbody-stroke-width` beats the preset while the preset's other fields
still apply.

## Tests (`tests/test_waterbody_config.py`, +8)

TG-WB1: `screen`/`print` bundles apply; explicit field overrides the preset but its
other fields remain; unknown preset → `ConfigError`; no-preset default unchanged.
TG-WB2 (CLI path, exercises the merge fix): `--waterbody-preset print` applies;
explicit `--waterbody-stroke-width` beats it; YAML `preset` honored and CLI-overridable.

## Verification

- `tests/test_waterbody_config.py`: **16 passed** (8 new).
- Full suite: **443 passed** (was 435), no regressions — the CLI merge-base change
  is behavior-preserving.
- CLI smoke: default `stroke=0.45`; `print` → `0.9` + `100k/250k` thresholds;
  `print --waterbody-stroke-width 0.5` → `0.5` with the print thresholds retained;
  `--waterbody-preset poster` → argparse exit 2.
- `ruff` not installed in this `.venv`; code follows repo conventions.

## Not done / follow-ups (remain open on roadmap W4)

- **Final preset values** — the numbers here are provisional; the print/screen
  thresholds await human art-direction after reviewing real Oregon/Washington/
  Clark-County output. Tune them in `WATERBODY_PRESETS`.
- **Clark County run** — the county-level QA harness (`tools/waterbody_qa.py`)
  still needs the Census county shapefile mounted; not runnable in this offline env.
