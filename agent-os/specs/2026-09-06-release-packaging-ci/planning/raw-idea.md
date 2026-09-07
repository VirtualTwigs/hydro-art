# Raw idea — Epoch 23: Release packaging, CI & reproducibility gate (#91–93)

Turn "green suite + artifacts" into a tagged, reproducible **v1.0** — the close of Generation 1.

- **#91 CI for the full test pyramid** — Run offline unit+integration+e2e on every change; run
  the opt-in real-data e2e + determinism as a scheduled/gated job.
- **#92 Reproducibility release gate** — Block the release tag unless double-render is
  byte-identical and golden fixtures match (extends `tools/verify_determinism.py`).
- **#93 Version, changelog & distribution packaging** — Tag `v1.0`, generate a changelog from the
  epoch history, and package the CLI + docs for distribution.

Epoch gate: `v1.0` is tagged only when the full pyramid is green, determinism holds, and the
marketing gallery + docs ship — a reproducible Generation 1 production release.

Discipline carried forward: offline suite stays fully offline; the pure halves of the release
gate + changelog live in `src/` (tested), the GDAL/real-data/double-render halves stay in
`tools/`; default 2D output byte-for-byte identical; public-domain sources only.

The actual `git tag v1.0` is an explicit, user-authorized step (like "commit item #N") — this
epoch prepares everything so the tag is a one-command finish, but does not tag autonomously.
