# Raw idea — Epoch 22 (High-resolution marketing gallery)

From the Generation 1 roadmap (Epoch 22, items #88–90): a curated, rights-clean, high-
resolution set of examples per style/endpoint for the website — the visual proof of the
engine's range. Public-domain sources only.

- **#88 Curated style matrix** — select regions × styles × endpoints that show the range
  (neon basin, elevation mono, year-in-motion, terrain print, watershed report); record the
  selection + rationale.
- **#89 High-res render & export** — render each at marketing/print resolution; export web-
  optimized and full-resolution variants; all from public-domain sources.
- **#90 Gallery provenance & rights ledger** — a per-asset ledger (source version,
  attribution, checksum, sellable flag) via the Rights gate; wire the gallery into the
  marketing web surface (`web/` foundation).

Available public-domain styles: `neon-basin` (pipeline) and `elevation-tint` (mono) — both
`uses_prism=False`, so both are sellable. Regions: Oregon, Washington, California, Idaho.

Discipline: the actual high-res images need GDAL + staged NAS data, so #89 is an opt-in
`tools/` render harness whose real run is deferred to the GDAL+NAS machine (like the Epoch 21
harness). The **offline** deliverables are the curated matrix, a pure/deterministic rights-
ledger builder (reusing the endpoint contract + Rights gate), a render-independent golden, and
a self-contained `web/gallery.html` surface that reads the ledger JSON. Default 2D output
stays byte-identical.
