# Tasks: Promote `--min-order` to the pipeline (Item #107)

## Task Group 1: Config + CLI + Pipeline integration

- [x] 1.1 Add `"min_order": 1` to `DEFAULTS` in `src/config.py`
- [x] 1.2 Add `min_order: int` field to `Settings` dataclass
- [x] 1.3 Add validation in `build_settings`: coerce to int, raise `ConfigError` if ≤ 0
- [x] 1.4 Add `--min-order` argument to `src/cli.py` (type=int, default=None)
- [x] 1.5 Filter segments in `_compute_watersheds_stage` after `assign_stream_order`: drop segment IDs with order < `settings.min_order` from `stream_orders`; also filter watersheds so downstream stages only see kept segments
- [x] 1.6 Remove the `xfail` marker from `tests/test_min_order.py`
- [x] 1.7 Run `tests/test_min_order.py` — all 8 tests pass
- [x] 1.8 Run full suite — 1091 passed, no regressions; recipe roundtrip 11 green
