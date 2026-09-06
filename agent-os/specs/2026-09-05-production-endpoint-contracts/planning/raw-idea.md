# Raw idea — Production endpoint contracts & hardening (Epoch 19, items #79–81)

First epoch of **Generation 1 — Production Release**. The engine is feature-complete
across four deliverable kinds (digital image, animation, print image, watershed report),
but each is reached by its own `tools/` script with an informal, undocumented output
shape. Before we can build the full test pyramid (Epoch 20) or the flagship all-endpoints
end-to-end proof (Epoch 21), each endpoint needs a **documented, versioned output
contract** and a **single dispatch seam** so tests have something concrete to assert.

User direction (2026-09-05):
- Roadmap a 1st-generation complete system at production level with unit, integration,
  and end-to-end testing; use Agent OS for all epochs.
- One end-to-end test must show a complete path to all major endpoints: animation,
  digital image, print image, report generation.
- Use high-res style examples for marketing (Epoch 22, later).

Decisions taken at roadmap time:
- Epoch structure approved as-is; build **Epoch 19 first** (foundation).
- **Author offline, run later:** all real-artifact/GDAL work is written and offline-verified
  in-repo, then run on the GDAL+NAS machine. This session stays fully offline.
- Anchor region for e2e + marketing: **Wahkiakum County, Washington** — already carries
  golden SVG + DEM hashes in `tests/fixtures/golden/registry.json`.

Constraints inherited (must not break):
- Offline suite discipline — no GDAL/network in `src/` or `tests/`; heavy reads live in `tools/`.
- Default 2D pipeline output stays **byte-for-byte identical**.
- Rights gate — only public-domain sources ship in any sellable/marketing asset.
