# Raw idea — Epoch 16 Item #68: Infrastructure QA and presets (epoch close)

From roadmap (`agent-os/product/roadmap.md`, Phase 16.4):

> 68. Infrastructure QA and presets — Fixture + real Oregon/Washington/Clark County
> validation (structure-on-network placement, duplicate suppression, canal/natural
> separation) and screen/print presets tuned so infrastructure enriches rather than
> clutters. `M`
>
> Epoch gate: a build can overlay source-traceable dams, weirs, locks, gaging stations,
> intakes, and distinctly-styled engineered channels on the water art, controllable by
> preset, with the default (infrastructure disabled) output byte-for-byte identical.

Closes Epoch 16. Builds on #65 (taxonomy + loader) and #67 (selection + rendering +
`HYDRO_STRUCTURE_PRESETS`). This item proves the render holds up on REAL data and tunes
the presets so infrastructure reads as enrichment, not clutter.

Precedent to mirror: the Epoch 1.5 waterbody QA close — `tools/waterbody_qa.py` runs the
SAME pipeline classification+selection code against real GDBs and prints a cross-check
report (non-offline), while the offline fixture suite proves the logic on hand-built
geometry. Real NHDPlus HR GDBs for OR/WA HUC4s (1701–1807) are available offline under
`datasets/nhdplus_hr/`.

Kicked off 2026-09-03 by user ("kick off #68").
