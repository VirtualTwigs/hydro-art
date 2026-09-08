# Pre-analysis watch-list — Tooling debt corrections (Track C2)

Restoring the pre-analysis step the last four closeouts dropped (corrections roadmap C1.1).
"What can only be verified on real data / what will offline-green hide?"

- **The offline suite never runs a tool as `__main__`.** That is *why* the shim bug survived — a
  passing suite is structurally blind to it. The regression guard therefore has to be either a
  static source-analysis test or a subprocess that actually invokes the script. Both are used here.
- **Subprocess e2e is limited to GDAL-free tools.** Only `detect_unfinished.py` and
  `update_status.py` import purely from `src` (`src.unfinished`, `src.status` — stdlib-only). The
  other five (`acquire_dem`, `cache_manifest`, `migrate_storage`, `monthly_flow`, `package_cache`)
  pull `pyogrio`/`numpy`/heavy `src` seams at import and cannot `--help` in a bare offline env — they
  are covered by the *static* invariant test only, not the subprocess test.
- **C2.3 cannot be verified offline end-to-end.** The nbconvert cache-miss only manifests with real
  WBD data + a notebook host. Offline we can only assert (statically) that the paths are REPO-anchored
  and (by reasoning) that repo-root runs are byte-identical. The real nbconvert confirmation is a
  Track-C4 host-gated follow-up, noted honestly in the report — do not claim it here.
- **Byte-identity risk:** anchoring cache paths to REPO must leave the repo-root-CWD case
  bit-for-bit unchanged (same files read/written). Verify `REPO / "output/..."` resolves to the same
  location as `Path("output/...")` when CWD == REPO. It does; the change only fixes foreign-CWD.
- **`tools/` is outside the suite.** New tests must not `import` the heavy tools at collection time
  (that would drag GDAL/numpy into the offline run). Read their source as text / spawn subprocesses.
