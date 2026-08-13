# Tasks — Waterbody regional presets (roadmap W4, mechanism slice)

## TG-WB1 — Preset catalog + config expansion

- [x] Write tests first (`tests/test_waterbody_config.py`): `screen` preset applies
      its bundle; `print` preset applies bolder stroke + positive area thresholds;
      an explicit `stroke_width` passed with `preset` wins while the preset's other
      fields remain; an unknown preset raises `ConfigError` (match "preset"); a
      no-preset default build is unchanged.
- [x] `src/config.py`: add `WATERBODY_PRESETS` (provisional `screen`/`print`,
      clearly marked) + `SUPPORTED_WATERBODY_PRESETS`; export both. In
      `_coerce_waterbodies`, pop a `preset` directive and layer
      `defaults < preset < provided`; raise `ConfigError` on unknown preset.
      `WaterbodySettings` unchanged (preset expands away).
- [x] Run ONLY the new tests; green.

## TG-WB2 — CLI flag + merge fix

- [x] Write tests first (`tests/test_waterbody_config.py`): `--waterbody-preset
      print` applies through the CLI path; an explicit `--waterbody-stroke-width`
      beats the preset; YAML `waterbodies.preset` is honored and CLI overrides it.
- [x] `src/cli.py`: add `--waterbody-preset` (`choices=SUPPORTED_WATERBODY_PRESETS`,
      default `None`) → `waterbodies["preset"]`; change the nested `waterbodies`
      merge base from `dict(DEFAULTS["waterbodies"])` to `{}` so a preset isn't
      shadowed by pre-seeded defaults (behavior-preserving — `_coerce_waterbodies`
      fills defaults).
- [x] Run ONLY the new tests; green.

## TG-WB3 — Verify + docs

- [x] Full Python suite (regression check).
- [x] Write `implementation/report.md`; tick this `tasks.md`; update the roadmap W4
      note, `HANDOFF.md`, and the `CLAUDE.md` conventions/module notes. Report; STOP
      (commit is a separate explicit step).
