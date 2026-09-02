# Implementation Report: Scale-aware flow-width presets (Epoch 18)

## Outcome
Added named scale-aware flow→width presets (`state`/`basin`/`watershed`) and exposed the
`scaled_widths` logarithmic knob via a new `Settings.width_log`, reusing the existing `width_by=flow`
seam. Default (no preset, `width_by=uniform`, `width_log=False`) output is unchanged.

## Changes
- **`src/config.py`**
  - `WIDTH_PRESETS` + `SUPPORTED_WIDTH_PRESETS` (near the other preset tables); exported in `__all__`.
  - `DEFAULTS["width_log"] = False`; `Settings.width_log: bool` field + docstring; passed in the
    `Settings(...)` construction.
  - `build_settings` resolves a top-level `width_preset` directive with precedence
    `defaults < preset < explicit`, then validates `width_log` to a bool.
  - `_CONFIG_DIRECTIVES = {"width_preset"}` subtracted in `load_yaml` so the consumed directive is
    not flagged as an unknown config key.
- **`src/pipeline.py`** — `_resolve_stroke_widths` passes `log=ctx.settings.width_log` to
  `scaled_widths`.
- **`src/cli.py`** — `--width-preset {state,basin,watershed}` and `--width-log`/`--no-width-log`
  (both `default=None`), wired into `cli_overrides`.

## Preset values
| preset | width_by | width_min | width_max | width_gamma | width_log | mapping |
|---|---|---|---|---|---|---|
| `state` | flow | 0.35 | 3.5 | 1.0 | True | log, ~10:1 |
| `basin` | flow | 0.35 | 2.1 | 0.45 | False | `Q^0.45` |
| `watershed` | flow | 0.35 | 1.4 | 0.5 | False | `√Q` |

## Key design note — precedence detection
Production always calls `build_settings(merge_values(dict(DEFAULTS), yaml, overrides))` — a
DEFAULTS-spread mapping — so "was this field explicitly set?" cannot be answered by key presence.
`build_settings` therefore treats a width field as an explicit override **iff its value differs from
`DEFAULTS[field]`**; otherwise the named preset (if any) supplies it. Documented corner case:
explicitly setting a width field to its exact default value while also naming a preset lets the
preset win for that field. This mirrors why the waterbody block starts from `{}` in `cli.py`.

## Verification
- Target tests: `tests/test_config.py tests/test_pipeline.py tests/test_cli.py` → 76 passed
  (13 new).
- Full offline suite: `.venv/bin/python -m pytest -q` → **737 passed**, no regressions.
- Smoke: default build stays `uniform`/`False`; `state`/`basin`/`watershed` expand as tabled;
  explicit `width_max` beats a preset; `width_preset` not stored on `Settings`; YAML
  `width_preset: basin` applies with no unknown-key warning.

## Context note
Implemented on top of the (then-uncommitted) Epoch 15 natural-water-features working tree. Verified
Epoch 15 did not conflict: `_resolve_stroke_widths` was untouched, and the new `_coerce_preset`
helper is for nested blocks only (width fields are top-level, so the directive is handled inline).

## Follow-ups / notes
- The offline pipeline shapes the **stream-order proxy** (not true QAMA discharge); real
  EROM-discharge scaling remains a `tools/` capability, so the log/power-law character is most
  faithful in the `tools/` renderers. A future task could add `--width-preset` to
  `tools/render_state_svg.py` operating on real QAMA.
