# Implementation report — Unit & integration test completion (Epoch 20, #82–84)

**Status:** implemented (offline), not committed. Second epoch of Generation 1.

## What shipped

- **`tests/test_endpoints_integration.py` (NEW, offline) — #83.** Offline integration
  coverage of the four endpoint orchestrators. A realistic fake renderer writes REAL bytes to
  `tmp_path` for every planned filename, sha256s them, and returns `{filename: sha256}`,
  driving the full `endpoint_plan → renderer seam → coverage check → endpoint_manifest →
  EndpointResult` chain in `src.endpoints.dispatch_endpoint`. 10 tests:
  - parametrized over all four endpoints — result ok/endpoint, plan formats/kinds in canonical
    contract order, manifest schema/endpoint/attribution + real per-file sha256s;
  - parametrized byte-identical determinism (same request twice → identical
    `json.dumps(manifest, sort_keys=True)`);
  - print endpoint carries pixel dims (18×24 @ 300dpi);
  - Rights gate precedes the renderer at the integration level (PRISM style → `EndpointError`,
    renderer wrote no file).
- **`tests/test_optimize.py` (EDIT) — #82 gap closure.** +3 offline tests via a monkeypatched
  `subprocess.run` for the previously-missed `SvgoOptimizer` branches: svgo present-but-failing
  (`CalledProcessError` → unoptimized SVG + warning), svgo success (`return result.stdout`),
  and success-with-empty-stdout fallback. `src/optimize.py` now measures 100%.
- **`pyproject.toml` (EDIT) — #82/#84.** Added `[tool.coverage.run]` (`source=["src"]`) and
  `[tool.coverage.report]` (`exclude_lines`: `pragma: no cover`, `if TYPE_CHECKING:`,
  `raise NotImplementedError`, `...`). Scopes the number to offline-testable `src/` code and
  honors the existing `# pragma: no cover` convention.
- **`tools/coverage_report.py` (NEW, non-suite) — #84.** Thin stdlib-only CLI: runs
  `coverage run -m pytest` + `coverage report --sort=cover`, with `--fail-under N` (report-only
  when omitted) and `--quiet`. Exit taxonomy: suite fail → 1, coverage below threshold → 2,
  else 0. Not imported by `src/` or the suite.

## Coverage audit (#82) — conclusion

Baseline (2026-09-06, scoped by the new config): **94% total**. `src/optimize.py` raised to
100% by the new tests. The residual misses are concentrated in **injectable I/O seam bodies
that require real external state and are offline-untestable by design**:

- `counties.py` `CensusCountyProvider.load` — geopandas `read_file` on a real Census shapefile.
- `download.py` — `urllib` network fetch.
- `loading.py` `PyogrioLayerLoader.load_layers` — GDAL `gpd.read_file`.
- `server.py` — live `http.server` request handlers.

These are covered instead by **injected fakes at their call sites** (the seam pattern the whole
suite depends on). Chasing them with real GDAL/network would break the offline discipline, so
they are intentionally left to the opt-in real-data harness (Epoch 21) rather than the unit
suite.

## Verification

- `pytest tests/test_endpoints_integration.py` → **10 passed**; `pytest tests/test_optimize.py`
  → **5 passed**.
- Full offline suite `pytest -q` → **827 passed** (was 814; +13 new; no regressions).
- `python tools/coverage_report.py --fail-under 90 --quiet` → exit 0 (**94% total**);
  `--fail-under 99` → exit 2 (gate proven both ways).
- Offline discipline: new tests + tool import only stdlib + `src.*` (grep-verified: no
  GDAL/numpy/network).
- Byte-identical default: no `src/` behavior/byte change (only a `pyproject.toml` config block
  + new tests/tool); default 2D build unaffected.

## Agreed threshold

Report-only by default; recommended gate `--fail-under 90` (current 94%). Epoch 23 wires this
into CI and may raise/enforce the number.

## Item gate

The base of the pyramid is documented and gated: every genuinely offline-testable branch in the
audited low-coverage modules is closed (`optimize` → 100%), residual misses are documented I/O
seams excluded by config, all four endpoint orchestrators have offline integration coverage with
contract + determinism + Rights-gate assertions, and a repeatable coverage gate tool exists —
ready for Epoch 21 (flagship e2e).
