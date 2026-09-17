# Tasks: CONUS region alias (Item #109)

## Task Group 1: CONUS alias + tests

- [x] 1.1 Define `CONUS_STATES` tuple (48 contiguous states) in `src/config.py`, export in `__all__`
- [x] 1.2 Expand `CONUS` alias in `build_settings` before `_normalize_region` — replace CONUS with all 48 states
- [x] 1.3 Write tests: CONUS expands to 48 states, case-insensitive, string form, CONUS+county raises ConfigError
- [x] 1.4 Run focused tests — 5/5 pass
- [x] 1.5 Run full suite — 1099 passed, no regressions
