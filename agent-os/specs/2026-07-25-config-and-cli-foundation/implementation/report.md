# Implementation Report: Configuration & CLI Foundation

**Date:** 2026-07-25
**Status:** Complete — all task groups done, 19/19 tests passing

## What was built

| File | Purpose |
|------|---------|
| `src/config.py` | Immutable `Settings` dataclass, `DEFAULTS`, allowlists (`SUPPORTED_REGIONS`/`SUPPORTED_PROJECTIONS`/`SUPPORTED_OUTPUTS`), `ConfigError`, `load_yaml`, and boundary validation (`build_settings`). |
| `src/cli.py` | argparse parser, explicit-only CLI override extraction, precedence merge, and `resolve_settings` entry point. |
| `src/pipeline.py` | `Stage`/`Pipeline` skeleton with 12 no-op stub stages in PRD §8 order; stages receive `Settings` by DI. |
| `build.py` | CLI entry point: resolve → rich-log settings → run pipeline; returns exit code (0 success, 1 on `ConfigError`). |
| `config.yaml` | Example config matching PRD §25. |
| `requirements.txt`, `pyproject.toml` | pyyaml + rich (+ pytest); GIS deps deferred to later items. |
| `tests/test_config.py`, `test_cli.py`, `test_build.py`, `test_integration.py` | 6 + 6 + 3 + 4 = 19 tests. |

## Key decisions

- **Precedence via `default=None` flags:** argparse flags default to `None` so "not provided" is distinguishable from an explicit value — this is what lets omitted flags leave YAML values intact (verified by `test_unset_flag_does_not_clobber_yaml`).
- **Allowlist validation at the boundary** (`build_settings`), per the validation standard; region names normalized case-insensitively; unsupported values raise `ConfigError` with the list of valid options.
- **No global state:** `Settings` is a frozen dataclass constructed once and injected into `Pipeline`.
- **Unknown YAML keys warn, not fail** — surfaces typos without blocking a run.

## Acceptance criteria met

- `python build.py` runs end-to-end as a no-op and exits 0.
- CLI overrides YAML, YAML overrides defaults; unset flags never clobber YAML.
- Config errors produce readable messages and a non-zero exit code.
- Stages invoked in PRD §8 order with `Settings` injected.
- Reproducibility: identical inputs produce identical `Settings` (`test_identical_inputs_produce_identical_settings`).

## Notes for next feature (roadmap #2: dataset acquisition)

- `Settings.regions` and the `SUPPORTED_REGIONS` registry are the seam for region-specific downloads.
- Pipeline stub `download`/`extract` in `src/pipeline.py` are the insertion points.
- GIS dependencies (geopandas, pyogrio, gdal, shapely, fiona, networkx, svgwrite, svgo) still need adding to `requirements.txt` when those stages are implemented.
