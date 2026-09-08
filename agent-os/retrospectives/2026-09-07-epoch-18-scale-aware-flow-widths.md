# Retrospective — Epoch 18: Scale-aware flow-width presets (#77, #78)

_Closed 2026-09-01 (single commit `85d238f`); retro written 2026-09-07. **No
pre-registered watch-list** — the spec folder
(`2026-09-01-scale-aware-flow-widths`) carries `planning/requirements.md`,
`spec.md`, `tasks.md`, and `implementation/report.md`, but no
`planning/pre-analysis.md`. Consistent with the Epoch 16 observation, this is a
narrative closeout rather than a graded one, and the missing pre-analysis is
itself a small process note (see below). This was a two-item epoch, so this is a
short closeout by design._

## What the epoch was

Turn the raw flow→width knobs (`width_min` / `width_max` / `width_gamma`) into
**named, scale-appropriate presets** and expose the previously-hidden
`scaled_widths` logarithmic knob as a real `Settings` field. One flow→width
mapping cannot serve every extent: discharge spans ~5 orders of magnitude across
a whole state, so only a logarithmic ramp keeps a Cascade trickle visible next to
the Columbia trunk, while a single basin or watershed has a small enough range
that a power-law mapping is both legible and geomorphologically honest. Before
this epoch the only way to get any of these was hand-tuning three numeric knobs
per run, and the `log` shape was unreachable from `Settings` at all
(`_resolve_stroke_widths` never passed `log=` to `scaled_widths`).

Both planned items shipped and the epoch closed on #78.

## What shipped (`85d238f`)

### #77 — Preset table, `width_log` knob, config expansion + pipeline wiring

`src/config.py` gained `WIDTH_PRESETS` + `SUPPORTED_WIDTH_PRESETS` (both exported
in `__all__`, placed near the other preset tables), a new `Settings.width_log:
bool` field (+ docstring, `DEFAULTS["width_log"] = False`), and — in
`build_settings` — top-level `width_preset` expansion with precedence
`defaults < preset < explicit`, `width_log` bool validation, and
`_CONFIG_DIRECTIVES = {"width_preset"}` so the consumed directive is not flagged
as an unknown YAML key. The three presets (verified against the landed
`WIDTH_PRESETS`):

| preset | width_by | width_min | width_max | width_gamma | width_log | mapping |
|---|---|---|---|---|---|---|
| `state` | flow | 0.35 | 3.5 | 1.0 | `True` | log, ~10:1 range |
| `basin` | flow | 0.35 | 2.1 | 0.45 | `False` | power-law `Q^0.45`, ~6:1 |
| `watershed` | flow | 0.35 | 1.4 | 0.5 | `False` | `√Q` — downstream hydraulic geometry, Leopold & Maddock `w ∝ Q^0.5`, ~4:1 |

`src/pipeline.py` is a **one-line** change: `_resolve_stroke_widths` now passes
`log=ctx.settings.width_log` into `scaled_widths(...)`. No other render behavior
was added — the epoch only reaches the existing `width_by=flow` seam.

### #78 — CLI flags

`src/cli.py` added `--width-preset {state,basin,watershed}`
(`choices=SUPPORTED_WIDTH_PRESETS`) and `--width-log` /
`--no-width-log` (`argparse.BooleanOptionalAction`), both `default=None` so unset
flags never clobber YAML, wired into `cli_overrides` with precedence
`defaults < config.yaml < CLI`.

## The reuse story (why this epoch was small)

The whole epoch is a **third reuse** of the Epoch-1.5 `WATERBODY_PRESETS` /
`_coerce_waterbodies` template — the same pattern Epoch 15 and Epoch 16 leaned on:
a preset table + allowlist tuple, fail-fast `ConfigError` on an unknown name,
`defaults < preset < explicit` precedence, and the preset **consumed at config
time and never stored on frozen `Settings`**. Because that seam already existed
and `scaled_widths(log=...)` already supported the log shape, there was no new I/O,
no new render code, and no new machinery to invent — just config plumbing plus one
pipeline line. The implementation report is explicit that the change is "pure
config + a one-arg pipeline wiring."

One genuine design nuance was worth the care it got: production always calls
`build_settings` on a **DEFAULTS-spread mapping**, so "was this field explicitly
set?" cannot be answered by key presence. The landed `_width_value` helper treats
a width field as an explicit override **iff its value differs from
`DEFAULTS[field]`**, otherwise the named preset supplies it. Documented corner
case: explicitly setting a width field to its exact default value while also
naming a preset lets the preset win for that field. This mirrors why the
waterbody block starts from `{}` in `cli.py`.

## Invariants held (verified against code + report)

- **Offline suite:** target tests (`test_config.py` / `test_pipeline.py` /
  `test_cli.py`) → **76 passed (13 new)**; full offline suite **737 passed**, no
  regressions. No new GDAL / network / `web/` / `tools/` imports in `src/` — the
  change is pure config plus one pipeline arg.
- **2D default output byte-identical:** yes. With no preset named,
  `width_by=uniform`, and `width_log=False` (the defaults), `_resolve_stroke_widths`
  still returns `None` and output is byte-for-byte identical. Guarded by the
  golden-fixture tests and the explicit default-build smoke.
- **`PIPELINE_STAGES` untouched:** yes. The commit touches `src/pipeline.py` only
  inside `_resolve_stroke_widths`; the two `PIPELINE_STAGES` references in the diff
  are both in `tests/test_pipeline.py` — an import and an assertion that
  `tuple(s.name for s in PIPELINE_STAGES) == CANONICAL_ORDER`, i.e. the stage list
  is guarded, not edited. No stage added or reordered.
- **Rights gate:** N/A — this epoch changes only stroke-width shaping, adds no data
  source, and does not touch `fulfillment.assert_sellable`.

## Graded against pre-analysis

No `planning/pre-analysis.md` exists for this spec, so there is no pre-registered
watch-list to grade against. As a two-item, template-reuse epoch touching only
config plumbing and one pipeline line, the risk surface was small; still, the
recurring project lesson (a metric/behavior green on offline fakes can diverge on
the real path) applies here in exactly one place — see the carry-forward on the
stream-order proxy.

## Carry-forwards (honestly open, not passed)

- **Presets shape the offline stream-order proxy, not true QAMA/EROM discharge.**
  The offline pipeline feeds `width_by=flow` a stream-order proxy, so the
  log/power-law *character* of these presets is faithful in shape but only fully
  honest against real per-reach discharge in the `tools/` renderers. Wiring
  `--width-preset` into `tools/render_state_svg.py` operating on real QAMA is an
  explicit, still-open follow-up (out of scope here by design). Until then, no live
  real-data smoke has confirmed the ~10:1 / `Q^0.45` / `√Q` dynamic ranges on
  actual discharge — that needs a GDAL/NAS host.
- **No live byte-identical `verify_determinism.py` double-render was run for this
  epoch.** Byte-identity rests on the default-disabled invariant (`width_by`
  defaults to `uniform`, `width_log` to `False`) plus the golden-fixture tests, not
  a fresh `--region Oregon` double-render — matching the standing Epoch 9/10/14/16
  carry-forward that a full `build.py` byte-compare still needs a GDAL host.

## Lessons

- **Reuse is what kept this epoch a single small commit.** The
  `WATERBODY_PRESETS` / `_coerce_waterbodies` template has now been reused three
  times (Epoch 15, 16, 18) — a validated pattern for "add named art-direction
  bundles without new machinery." When the next set of named knobs appears, start
  from this template rather than inventing a parallel expansion path.
- **The DEFAULTS-spread precedence trap is real and recurring.** Because
  `build_settings` never sees a sparse mapping, "explicit iff differs from default"
  is the correct test, and the "explicit == default alongside a preset" corner is
  worth documenting every time the pattern is reused.
- **Consider restoring the pre-analysis step even for small epochs.** As with
  Epoch 16, none was written. It costs little and would have named the one honest
  gap up front: presets validated on the offline proxy still owe a real-QAMA smoke.
