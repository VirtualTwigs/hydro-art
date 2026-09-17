# Spec: CONUS region alias (Item #109)

## Overview

Add `"CONUS"` as a pseudo-region alias in `src/config.py` that expands to
all 48 contiguous US states. This lets a user write `--region CONUS` instead
of listing 48 states. The expansion happens at config time (in `build_settings`),
so every downstream module sees a normal tuple of state names.

## Scope

1. **`src/config.py`** — define `CONUS_STATES` (48 contiguous states, all 50
   minus Hawaii and Alaska). In `build_settings`, before normalizing regions,
   expand any occurrence of `"CONUS"` (case-insensitive) to the 48 states.
   Export `CONUS_STATES` for tests and tools.

2. **`src/cli.py`** — no changes needed; `--region CONUS` passes through as
   a string and is expanded in `build_settings`.

3. **Tests** — CONUS expands to 48 states, CONUS + county raises
   ConfigError, default builds are byte-identical.

## Design

The expansion is a pure string replacement before `_normalize_region` runs:

```python
if "CONUS" in (name.strip().upper() for name in regions_raw):
    # Replace CONUS with all 48 contiguous states
    regions_raw = list(CONUS_STATES)
```

This keeps `CONUS` out of `SUPPORTED_REGIONS` (it's not a region, it's an
alias). The expansion is transparent — `settings.regions` is a 48-element
tuple of real state names.

## Non-goals

- Continental coloring (#110) — separate item
- CONUS hero render (#111) — separate item
- CONUS boundary simplification for clip stage — the existing `region_boundary`
  (unary_union of WBD) works; optimization deferred to real render time
