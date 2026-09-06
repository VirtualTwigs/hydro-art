# Raw idea — Epoch 20 (Unit & integration test completion)

From the Generation 1 roadmap (Epoch 20, items #82–84): close the base of the test
pyramid. Coverage-audit every `src/` module, fill genuine offline unit gaps, add offline
integration tests that drive each of the four endpoint orchestrators end-of-path with
injected fakes, and wire a coverage measurement into the suite run (report-only first, then
an enforced threshold).

Constraints (inherited): offline suite only (no GDAL/network/real data), `src/` never
imports `web`/`tools`, default 2D build byte-for-byte identical, public-domain sources only.

Baseline measured 2026-09-06: `coverage run --source=src -m pytest` → **94% total, 814
passed**. Residual misses concentrate in I/O seam bodies that are offline-untestable by
design (`counties.load`, `download` fetch, `loading` GDAL read, `server` handlers,
`optimize` subprocess branches). The epoch's job is to (a) make that distinction explicit
and machine-checkable, (b) add integration coverage of the endpoint layer built in Epoch 19,
and (c) provide a repeatable coverage gate.
