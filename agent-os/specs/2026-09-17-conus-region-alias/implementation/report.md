# Implementation Report: CONUS region alias (Item #109)

## Summary

Added `CONUS` as a pseudo-region alias in `src/config.py` that expands to all
48 contiguous US states (all 50 minus Hawaii and Alaska). Users can now write
`--region CONUS` instead of listing 48 states.

## Changes

| File | Change |
|------|--------|
| `src/config.py` | `CONUS_STATES` constant (48 contiguous states derived from `SUPPORTED_REGIONS`); CONUS expansion in `build_settings` before `_normalize_region`; added to `__all__` |
| `tests/test_config.py` | 5 new tests: 48 states, case-insensitive, string form, county conflict |

## Design

- `CONUS_STATES` is derived from `SUPPORTED_REGIONS` at module load time,
  filtering out Hawaii and Alaska. This ensures it stays in sync automatically.
- The expansion is a single check in `build_settings`: if any region in the
  raw list matches `"CONUS"` (case-insensitive), the entire list is replaced
  with `CONUS_STATES`. This keeps `CONUS` out of `SUPPORTED_REGIONS` — it's
  an alias, not a region.
- `settings.regions` is a 48-element tuple of real state names, transparent
  to every downstream module.

## Test results

- CONUS-specific: **5/5 passed**
- Full suite: **1099 passed**, 0 failures
