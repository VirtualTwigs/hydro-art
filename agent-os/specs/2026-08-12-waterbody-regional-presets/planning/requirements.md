# Requirements — Waterbody regional presets (roadmap W4, mechanism slice)

## Context

Roadmap W4 ("Waterbody QA and regional presets") is mostly done: offline fixture
QA (`tests/test_waterbody_qa.py`) and the real-region harness (`tools/waterbody_qa.py`,
run against Oregon/Washington 2026-07-30) all pass. Two pieces remain:

1. The Clark County, WA county-level QA run — **blocked**: needs the Census county
   shapefile mounted locally (not available in this environment).
2. The actual print/screen **preset values** — an art-direction decision on
   stroke/size/detail thresholds, deferred pending human review of real-region output.

## This slice

Deliver the **preset *mechanism*** (offline, tested) so that "establish print and
screen presets" has first-class plumbing, decoupling the *mechanism* from the
*values* (which stay human-tunable). A named preset is a convenience directive that
expands to a bundle of existing `waterbodies` fields; it invents no new render
behavior.

Per the user's decision (2026-08-12): ship provisional, clearly-marked default
preset values that can be tuned later after human review of real output.

## Functional requirements

- A named-preset catalog `WATERBODY_PRESETS` in `src/config.py` with at least
  `screen` and `print`, each mapping to a subset of `waterbodies` fields
  (`color`, `stroke_width`, `min_inland_area_m2`, `min_coastal_area_m2`,
  `coastal_mode`, `render_order`). Values are **provisional** and marked as such.
- `build_settings({"waterbodies": {"preset": "print"}})` expands the preset with
  precedence **defaults < preset < explicit fields** — an explicit sub-key the
  caller also passes still wins over the preset.
- An unknown preset name raises `ConfigError` naming the valid presets.
- A `--waterbody-preset {screen,print}` CLI flag, honoring `defaults < YAML < CLI`
  and `preset < explicit --waterbody-*` flags.
- No preset ⇒ existing builds byte-identical (the `preset` directive is opt-in and
  is not stored on `WaterbodySettings`).

## Non-functional / constraints

- Deterministic, offline-testable; no new render code, no pipeline changes.
- `WaterbodySettings` stays a plain frozen dataclass of concrete fields (the preset
  expands away at config time), so reproducibility is unchanged.

## Out of scope

- The real Clark County run (needs mounted Census data).
- Final tuned preset values (human art-direction, pending real-region review).
