# Task Breakdown: Configuration & CLI Foundation

## Overview
Total Tasks: 4 task groups

## Task List

### Settings Model Layer

#### Task Group 1: Settings model, defaults & validation
**Dependencies:** None

- [x] 1.0 Complete the settings model layer (`src/config.py`)
  - [x] 1.1 Write 2-8 focused tests for the settings model
    - Defaults produce a valid `Settings` object (regions Oregon+Washington, EPSG:5070, `#000000`, 0.35, neon, glow off, svg-only)
    - Validation rejects an unsupported region, a bad hex background, and a non-positive line width
    - Settings object is immutable / has no global state
  - [x] 1.2 Define an immutable, typed `Settings` dataclass (frozen) with fields: `regions: tuple[str,...]`, `projection: str`, `stream_order: str`, `background: str`, `line_width: float`, `palette: str`, `glow: bool`, `outputs: frozenset[str]`
    - Type hints + docstrings on all fields
  - [x] 1.3 Add a `DEFAULTS` source of truth reflecting PRD §19/§25
  - [x] 1.4 Add a `SUPPORTED_REGIONS` registry (Oregon, Washington) and supported projections/output formats as allowlists (single place to extend)
  - [x] 1.5 Implement validation: normalize region names case-insensitively, check allowlists, validate hex color, positive line width, known output formats; raise a specific `ConfigError` with actionable messages
  - [x] 1.6 Ensure the 2-8 tests from 1.1 pass (run ONLY those)

**Acceptance Criteria:**
- The 2-8 tests written in 1.1 pass
- Building `Settings` from defaults yields a valid object
- Invalid region / color / line width raise `ConfigError` with clear messages
- No global state; `Settings` is immutable

### Config & CLI Layer

#### Task Group 2: YAML loading, CLI parsing & precedence merge
**Dependencies:** Task Group 1

- [x] 2.0 Complete config loading + CLI parsing (`src/config.py`, `src/cli.py`)
  - [x] 2.1 Write 2-8 focused tests for loading & merge precedence
    - Missing `config.yaml` falls back to defaults
    - Malformed YAML raises `ConfigError`
    - Merge precedence: defaults < YAML < CLI (a CLI `--region` overrides YAML; an unspecified flag does NOT clobber a YAML value)
    - `--glow` sets glow true; `--output svg png` sets those outputs
  - [x] 2.2 Implement `load_yaml(path)` using PyYAML → plain mapping; missing file returns empty mapping; malformed YAML raises `ConfigError`; warn on unknown keys
  - [x] 2.3 Build the argparse CLI: `--config`, `--region` (1+), `--palette`, `--glow` (flag), `--output` (1+ of svg/pdf/png); capture only explicitly-provided flags
  - [x] 2.4 Implement `build_settings(defaults, yaml_values, cli_overrides) -> Settings` applying precedence, then validate via Task Group 1
  - [x] 2.5 Ensure the 2-8 tests from 2.1 pass (run ONLY those)

**Acceptance Criteria:**
- The 2-8 tests written in 2.1 pass
- Precedence defaults < YAML < CLI works, and unset flags never clobber YAML
- Missing config is tolerated; malformed config fails clearly

### Entry Point Layer

#### Task Group 3: `build.py` no-op pipeline & rich logging
**Dependencies:** Task Group 2

- [x] 3.0 Complete the CLI entry point and pipeline skeleton
  - [x] 3.1 Write 2-8 focused tests for the entry point
    - `build.py` with defaults exits 0
    - Invalid config (bad region) exits non-zero with a clear message
    - Resolved settings are logged / pipeline stubs run in PRD §8 order
  - [x] 3.2 Create `build.py` entry point: parse CLI → load YAML → merge → validate → construct `Settings`
  - [x] 3.3 Add a `Pipeline` skeleton (`src/pipeline.py`) with stub stages in PRD §8 order (download→extract→validate→repair→reproject→clip→graph→watersheds→color→svg→optimize→export), each a no-op that logs its name; stages receive `Settings` via dependency injection
  - [x] 3.4 Use `rich` to print resolved settings and a stage summary; map config/validation errors to a non-zero exit code with a user-friendly message
  - [x] 3.5 Add a root `config.yaml` example matching PRD §25 and a `requirements.txt`/`pyproject.toml` entry for `pyyaml` and `rich`
  - [x] 3.6 Ensure the 2-8 tests from 3.1 pass (run ONLY those)

**Acceptance Criteria:**
- The 2-8 tests written in 3.1 pass
- `python build.py` runs end-to-end as a no-op and exits 0
- Config errors produce readable messages and non-zero exit
- Stages are invoked in PRD §8 order with `Settings` injected

### Testing

#### Task Group 4: Test review & gap analysis
**Dependencies:** Task Groups 1-3

- [x] 4.0 Review existing tests and fill critical gaps only
  - [x] 4.1 Review the 2-8 tests from each of Task Groups 1-3 (~6-24 tests)
  - [x] 4.2 Identify critical gaps for THIS feature only (focus on the end-to-end config→settings→pipeline flow)
  - [x] 4.3 Write up to 10 additional strategic tests maximum (e.g., a full CLI+YAML integration run producing a resolved `Settings` and exit code)
  - [x] 4.4 Run ONLY this spec's tests (approx 16-34 total); verify the critical workflow passes

**Acceptance Criteria:**
- All feature-specific tests pass (~16-34 total)
- The end-to-end config resolution workflow is covered
- No more than 10 additional tests added
- Testing focused exclusively on this spec

## Execution Order

1. Settings Model Layer (Task Group 1)
2. Config & CLI Layer (Task Group 2)
3. Entry Point Layer (Task Group 3)
4. Test Review & Gap Analysis (Task Group 4)
