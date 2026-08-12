# Tasks — Portable cache manifests (roadmap #21, offline-packaging slice)

## TG1 — Manifest model, build, (de)serialization (deterministic)

- [x] Write tests first (`tests/test_manifest.py`): `build_manifest` over a real
      `Cache` in `tmp_path` (write file → `cache.record` → build); un-recorded
      descriptor skipped; `strict=True` raises `ManifestError`; entries sorted by
      key; `manifest_to_dict`/`manifest_from_dict` round-trip; `write_manifest`/
      `read_manifest` round-trip; deterministic bytes (two writes byte-identical;
      insertion order irrelevant); `manifest_for_settings` over OR+WA `Settings`;
      malformed `from_dict` → `ManifestError`.
- [x] `src/manifest.py`: `ManifestError`, `ManifestEntry`, `CacheManifest`,
      `MANIFEST_VERSION`, `build_manifest`, `manifest_for_settings`,
      `manifest_to_dict`, `manifest_from_dict`, `write_manifest`, `read_manifest`
      (stdlib + `src.datasets`/`src.config`/`src.cache` only).
- [x] Run ONLY the new tests; green.

## TG2 — verify + diff

- [x] Write tests first: `verify_manifest` all-ok / missing (deleted file) /
      mismatched (truncated + same-size-different-bytes) / `is_complete`;
      `diff_manifests` added / removed / changed / unchanged / `is_synced`.
- [x] `src/manifest.py`: `ManifestVerification` + `verify_manifest`,
      `ManifestDiff` + `diff_manifests`.
- [x] Run ONLY the new tests; green.

## TG3 — Verify + docs

- [x] Confirm `manifest` imports offline (no numpy/GDAL pulled in); `ruff` if
      available.
- [x] Run the full Python suite (regression check).
- [x] Write `implementation/report.md`; tick this `tasks.md`.
- [x] Add a roadmap #21 progress note (offline-packaging slice shipped; region
      expansion / tile-budget / resume still open); update `HANDOFF.md` +
      `CLAUDE.md` module map. Report; STOP (commit is a separate explicit step).
