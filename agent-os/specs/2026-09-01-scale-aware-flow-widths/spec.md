# Specification: Scale-aware flow-width presets (Epoch 18)

## Goal
Add named, scale-appropriate flow→width presets (`state`/`basin`/`watershed`) and expose the
`scaled_widths` logarithmic knob via a new `Settings.width_log`, reusing the `WATERBODY_PRESETS`
template exactly and staying byte-for-byte identical when no preset is named.

## User Stories
- As an art buyer/operator, I want to pick a `state`, `basin`, or `watershed` flow-width preset so
  the channel taper looks right for the extent without hand-tuning three numeric knobs.
- As a builder, I want the logarithmic mapping reachable from config/CLI (not only from `tools/`),
  and I want the default (no preset) build to remain byte-identical.

## Specific Requirements

**Preset table & log knob — `src/config.py`**
- Add `WIDTH_PRESETS: dict[str, dict[str, Any]]` and `SUPPORTED_WIDTH_PRESETS = tuple(WIDTH_PRESETS)`
  near `WATERBODY_PRESETS`; export both in `__all__`.
- Preset values (art direction; human-tunable, not a hard contract):

  | preset | width_by | width_min | width_max | width_gamma | width_log | mapping |
  |---|---|---|---|---|---|---|
  | `state` | flow | 0.35 | 3.5 | 1.0 | `True` | log, ~10:1 range |
  | `basin` | flow | 0.35 | 2.1 | 0.45 | `False` | power-law `Q^0.45`, ~6:1 |
  | `watershed` | flow | 0.35 | 1.4 | 0.5 | `False` | `√Q` hydraulic geometry, ~4:1 |

- Add `Settings.width_log: bool` (documented in the class docstring, placed after `width_gamma`) and
  `DEFAULTS["width_log"] = False`.
- In `build_settings`: read a top-level `width_preset`; if present and not in `WIDTH_PRESETS`, raise
  `ConfigError` listing `SUPPORTED_WIDTH_PRESETS`. Resolve each width field with precedence
  `defaults < preset < explicit` where "explicit" = the key is present in the incoming `values`
  mapping. Consume `width_preset` (never construct `Settings` with it).
- Validate `width_log` to a bool. Keep existing `width_min`/`width_max`/`width_gamma` validation
  (all `> 0`, `width_max >= width_min`) applied to the resolved (post-preset) values.

**Pipeline wiring — `src/pipeline.py`**
- `_resolve_stroke_widths` passes `log=ctx.settings.width_log` to `scaled_widths(...)`. No other
  change; `width_by=uniform` still returns `None` (byte-identical).

**CLI — `src/cli.py`**
- Add `--width-preset` (`choices=SUPPORTED_WIDTH_PRESETS`, `default=None`) → `overrides["width_preset"]`.
- Add `--width-log` via `argparse.BooleanOptionalAction` (`default=None`) → `overrides["width_log"]`
  when not `None`. Precedence `defaults < config.yaml < CLI`; unset flags never clobber YAML.

## Existing Code to Leverage
- `WATERBODY_PRESETS` / `SUPPORTED_WATERBODY_PRESETS` / `_coerce_waterbodies` — exact template for
  the preset table, allowlist, fail-fast validation, and `defaults < preset < explicit` precedence
  (with preset consumed, not stored).
- `SUPPORTED_WIDTH_MODES` and the existing `width_min/width_max/width_gamma` validation block in
  `build_settings` — reuse; feed it the resolved values.
- `src/rendering.scaled_widths(metric, *, width_min, width_max, gamma, log)` — already supports
  `log`; this spec only reaches it.
- `--waterbody-preset` and `--elevation` (`BooleanOptionalAction`) flag wiring in `src/cli.py`.

## Determinism / invariants
- No preset + `width_by=uniform` + `width_log=False` → **byte-for-byte identical** output.
- No new GDAL/network/`web/`/`tools/` imports in `src/`.

## Out of Scope
- True EROM/QAMA discharge in the offline pipeline; any `tools/` or `web/` change; per-extent
  auto-selection of a preset; any new render behavior beyond exposing `log` + bundling knobs.
