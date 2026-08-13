# Spec — Waterbody regional presets (roadmap W4, mechanism slice)

## Summary

Add a named waterbody-preset mechanism: `WATERBODY_PRESETS` in `src/config.py`
(provisional `screen`/`print` bundles), preset expansion inside `_coerce_waterbodies`
with `defaults < preset < explicit` precedence, and a `--waterbody-preset` CLI flag.
No new render behavior — a preset is a config-time convenience that expands to the
existing `WaterbodySettings` fields the W3 pipeline already consumes.

## Design

### `WATERBODY_PRESETS` (config.py)

A dict `name -> {waterbodies sub-field: value}`. Provisional values, marked in a
prominent comment as pending human review of real-region output (W4). The default
build corresponds to the `screen` intent; `print` diverges with a bolder stroke and
positive area thresholds to declutter tiny ponds for ink/large-format output.
`SUPPORTED_WATERBODY_PRESETS = tuple(WATERBODY_PRESETS)` is exported for the CLI
help/validation.

### `_coerce_waterbodies` expansion

```
provided = dict(value or {})
preset_name = provided.pop("preset", None)      # a directive, not a stored field
preset_values = WATERBODY_PRESETS[preset_name]  # ConfigError if unknown
merged = {**defaults, **preset_values, **provided}
```

So an explicit `stroke_width` passed alongside `preset` still wins. `preset` is
consumed and never lands on the frozen `WaterbodySettings` (kept unchanged), so a
build with no preset is byte-identical to before.

### CLI (cli.py)

- New `--waterbody-preset` with `choices=SUPPORTED_WATERBODY_PRESETS`, default
  `None`; when set, contributes `waterbodies["preset"]`.
- The nested `waterbodies` merge stops pre-seeding `DEFAULTS["waterbodies"]` (it
  starts from `{}` and layers only explicit YAML/CLI sub-keys). This is behavior-
  preserving — `_coerce_waterbodies` already fills every missing field from
  defaults — and is required so a preset isn't shadowed by pre-seeded default
  values indistinguishable from explicit ones.

## Tests

TG-WB1 (`tests/test_waterbody_config.py`): `screen`/`print` presets apply their
bundles; an explicit field overrides the preset while the preset's other fields
remain; an unknown preset raises `ConfigError`; no-preset default build unchanged.

TG-WB2 (`tests/test_waterbody_config.py`): `--waterbody-preset print` applies via
the CLI path (exercising the merge fix); an explicit `--waterbody-stroke-width`
beats the preset; YAML `waterbodies.preset` honored and overridable by CLI.

## Not in scope

Final tuned values (human art-direction), the Clark County run (needs mounted
Census data), and any render/pipeline change.
