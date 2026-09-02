# Requirements: Scale-aware flow-width presets (Epoch 18)

## Raw idea
Turn the scale-dependent flow→width recommendations into concrete presets alongside the existing
waterbody presets:
- **state** → logarithmic mapping, ~10:1 dynamic range (Cascade trickle → Columbia).
- **basin** → power-law `w ∝ Q^0.45`.
- **watershed** → `√Q` (Leopold & Maddock downstream hydraulic geometry `w ∝ Q^0.5`).

Also **expose the `scaled_widths` `log` knob** that `Settings` currently hides.

## Why
One flow→width mapping cannot serve every extent. Discharge spans ~5 orders of magnitude across a
whole state, so only a logarithmic mapping keeps headwaters visible next to the trunk. For a single
basin/watershed the range is small enough that a power-law mapping is both legible and
geomorphologically honest. Today the only way to get these is by hand-tuning
`width_min`/`width_max`/`width_gamma` per run, and the `log` shape is unreachable from `Settings` at
all (`_resolve_stroke_widths` never passes `log=` to `scaled_widths`).

## Scope decisions (confirmed)
- **Layer: `src/config.py` (Option 1).** Presets live in config, work in the offline pipeline on the
  stream-order flow proxy, and are fully unit-tested. True EROM/QAMA-discharge scaling remains a
  `tools/` capability (unchanged) — the presets shape whatever metric `width_by=flow` feeds
  `scaled_widths`.
- **Expose `width_log`.** Add a validated `width_log: bool` to `Settings`, default `False`, wired
  through `_resolve_stroke_widths` into `scaled_widths(log=...)`.
- **Template: `WATERBODY_PRESETS` / `_coerce_waterbodies`.** Reuse the exact preset pattern:
  fail-fast validation, precedence `defaults < preset < explicit`, preset consumed at config time and
  NOT stored on frozen `Settings`.
- **Invocation:** a top-level `width_preset` config key (the width fields are top-level, not nested
  like `waterbodies`) and a `--width-preset {state,basin,watershed}` CLI flag. Also add
  `--width-log`/`--no-width-log` so the newly-exposed knob is reachable from the CLI.

## Functional requirements
1. `WIDTH_PRESETS: dict[str, dict[str, Any]]` with keys `state`, `basin`, `watershed`; each bundles
   `width_by`, `width_min`, `width_max`, `width_gamma`, `width_log`. `SUPPORTED_WIDTH_PRESETS` is the
   allowlist tuple. Both exported in `__all__`.
2. `Settings.width_log: bool` (default `False`); `DEFAULTS["width_log"] = False`.
3. `build_settings` expands a top-level `width_preset` with precedence `defaults < preset < explicit`
   (an explicit `width_*` value passed alongside a preset still wins). Unknown preset name →
   `ConfigError`. `width_preset` is consumed, never stored on `Settings`.
4. `width_log` validated as a bool.
5. `_resolve_stroke_widths` passes `log=ctx.settings.width_log` to `scaled_widths`.
6. CLI `--width-preset` (choices = `SUPPORTED_WIDTH_PRESETS`) and `--width-log`/`--no-width-log`,
   both `default=None` so unset flags never clobber YAML; precedence `defaults < config.yaml < CLI`.

## Non-functional / invariants
- **Byte-identical default.** With no preset and `width_by=uniform`, `width_log=False`, rendered
  output is byte-for-byte identical to today (verifiable via Epoch 10 determinism tooling).
- Offline-safe: no new GDAL/network imports; all logic is pure config + a one-arg pipeline wiring.
- Every changed `src/<name>.py` keeps its matching `tests/test_<name>.py`.

## Out of scope
- True EROM/QAMA discharge in the offline pipeline (stays a `tools/` capability).
- Any `tools/` render-recipe change (`render_common.py`, `render_state_svg.py`).
- Any `web/` studio / recipe / mapping change.
- New render behavior beyond exposing `log` and bundling existing knobs.
- Per-extent auto-detection (choosing a preset from the region/county automatically).
