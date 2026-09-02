# Tasks: Scale-aware flow-width presets (Epoch 18)

TDD: write the tests in each group first (they should fail red), then implement to green. Run only
the group's tests during the group; run the full offline suite at the end.

## Group 1 — Config: `width_log` + `WIDTH_PRESETS` (roadmap #77)

- [x] 1.1 Tests (`tests/test_config.py`):
  - `width_log` defaults to `False` and round-trips through `build_settings`.
  - `width_log` accepts truthy/falsey and is stored as a bool on `Settings`.
  - `WIDTH_PRESETS` has exactly `state`/`basin`/`watershed`; `SUPPORTED_WIDTH_PRESETS` matches keys.
  - `width_preset="state"` expands to `width_by=flow`, `width_log=True`, `width_max=3.5`, `gamma=1.0`.
  - `width_preset="basin"` → `gamma=0.45`, `width_log=False`; `watershed` → `gamma=0.5`, `max=1.4`.
  - Precedence: explicit `width_gamma`/`width_max` alongside a preset still wins (`defaults < preset
    < explicit`).
  - Unknown `width_preset` → `ConfigError`.
  - `width_preset` is NOT an attribute of the returned `Settings`.
  - Default build (no preset) leaves `width_by="uniform"`, `width_log=False` (byte-identical guard).
- [x] 1.2 Implement in `src/config.py`: `WIDTH_PRESETS`, `SUPPORTED_WIDTH_PRESETS`, `__all__`
  exports, `DEFAULTS["width_log"]`, `Settings.width_log` field + docstring, `width_preset` expansion
  + `width_log` validation in `build_settings`, `_CONFIG_DIRECTIVES` for the `load_yaml` allowlist.
- [x] 1.3 Run `tests/test_config.py`; green.

## Group 2 — Pipeline log wiring (roadmap #77)

- [x] 2.1 Tests (`tests/test_pipeline.py`):
  - With `width_by="flow"`, `width_log=True`, `_resolve_stroke_widths` produces widths equal to
    `scaled_widths(stream_orders, ..., log=True)` (differs from `log=False` for a non-degenerate
    order set).
  - `width_by="uniform"` still returns `None` regardless of `width_log`.
- [x] 2.2 Implement: `_resolve_stroke_widths` passes `log=ctx.settings.width_log`.
- [x] 2.3 Run the group's tests; green.

## Group 3 — CLI flags (roadmap #78)

- [x] 3.1 Tests (`tests/test_cli.py`):
  - `--width-preset watershed` resolves to `gamma=0.5` through `build_settings`.
  - `--width-log` → `width_log=True`; `--no-width-log` → `width_log=False`; unset → YAML survives.
  - Invalid `--width-preset bogus` is rejected by argparse `choices`.
- [x] 3.2 Implement `--width-preset` + `--width-log` in `src/cli.py` and the override wiring.
- [x] 3.3 Run the group's tests; green.

## Group 4 — Regression + smoke

- [x] 4.1 Full offline suite: `.venv/bin/python -m pytest -q` → 737 passed.
- [x] 4.2 Byte-identical default guard: default build stays `width_by=uniform`, `width_log=False`;
  golden-fixture tests pass.
- [x] 4.3 Smoke: preset expansion, precedence, and YAML directive (no unknown-key warning) verified.
