# Group 0 — NHDLine / NHDArea structure FType findings (real-data verification)

Verified against a real extracted GDB:
`datasets/nhdplus_hr/1807/NHDPLUS_H_1807_HU4_GDB.gdb` (HUC4 1807, Oregon coast),
decoded via the authoritative `NHDFCode` domain table embedded in the GDB (join
each feature's `FCode` to its domain `Description`, not from memory).
Date: 2026-09-03. A real GDB WAS available offline (pyogrio present), so codes
below are domain-confirmed except where noted UNCONFIRMED.

## Confirmed codes

### Line structures — source layer `NHDLine` (NEW `load_line_features` seam)

| Class | FType | Domain description | 1807 NHDLine count | Status |
|-------|-------|--------------------|-------------------:|--------|
| `dam_weir` | 343 | Dam/Weir | 146 | confirmed, present (fcode 34301/34306, "Dam/Weir") |

Other `NHDLine` FTypes present in 1807 that fall OUT of the structure taxonomy
(non-engineered-water or non-water) → all classify to `excluded`: 362 Flume (31),
411 Nonearthen Shore (634), 434 Reef (119), 478 Tunnel (86), 483 Wall (1),
487 Waterfall (1 — a natural point/line feature owned by `point_features`),
503 Sounding Datum Line (112).

### Area structures — source layer `NHDArea` (EXISTING `load_waterbody_layers` seam)

| Class | FType | Domain description | 1807 NHDArea count | Status |
|-------|-------|--------------------|-------------------:|--------|
| `dam_weir`             | 343 | Dam/Weir             | 29  | confirmed, present |
| `canal_ditch`          | 336 | Canal/Ditch          | 52  | confirmed, present |
| `spillway`             | 455 | Spillway             | 15  | confirmed, present |
| `water_intake_outflow` | 485 | Water Intake/Outflow | 1   | confirmed, present |

Other `NHDArea` FTypes present in 1807 → `excluded`: 307 Area to be Submerged (1),
364 Foreshore (139), 403 Inundation Area (399), 445 Sea/Ocean (20),
460 Stream/River areal (81), 484 Wash (155).

### Point structures — source layer `NHDPoint` (EXISTING `load_point_features` seam)

Already domain-verified against 1807 in the Epoch 15 Group 0 findings
(`agent-os/specs/2026-09-01-natural-water-features/planning/group0-ftype-findings.md`):

| Class | FType | Domain description | 1807 NHDPoint count | Status |
|-------|-------|--------------------|--------------------:|--------|
| `gaging_station`       | 367 | Gaging Station       | 313 | confirmed (Epoch 15) |
| `water_intake_outflow` | 485 | Water Intake/Outflow | 8   | confirmed (Epoch 15) |
| `gate`                 | 369 | Gate                 | 2   | confirmed (Epoch 15) |

## UNCONFIRMED codes (real-GDB verification pending)

- **369 Gate** — confirmed on `NHDPoint` (Epoch 15) but ABSENT from `NHDLine`/
  `NHDArea` in 1807; the FType carries the same meaning across layers (per NHD
  domain design), so the rule maps 369 → `gate` regardless of source layer. The
  literal 369 code is domain-confirmed; its appearance on a line/area geometry is
  untested against real geometry in this sample.
- **398 LockChamber** — ABSENT from `NHDLine`, `NHDArea`, AND `NHDPoint` in 1807
  (coastal HUC4 with no navigation locks). The `398 → lock_chamber` mapping uses
  the standard NHD code from documentation and is flagged UNCONFIRMED in the
  module docstring; a later run against a lock-bearing HUC4 (e.g. a Columbia/
  Snake navigation reach) should confirm it. The classification RULE is unchanged
  regardless.

## Reservoir policy note

`436 Reservoir` is intentionally NOT in the structure table — `src/waterbodies.py`
owns 436 (maps it to the `reservoir` waterbody class). A reservoir is a body of
water, not an engineered line/point structure; keeping 436 out preserves the
non-overlapping (complementary) taxonomy invariant.

## Complementarity cross-check (confirmed codes vs. other taxonomies)

Structure included codes: {336, 343, 355→no, 367, 369, 398, 455, 485}
(actual: 336, 343, 367, 369, 398, 455, 485). Cross-checked against the included
(non-`excluded`) codes of the other three taxonomies:

- `src/waterbodies.py` included: 390, 436, 493, 312 — no overlap. (336 is
  `excluded` in waterbodies, so no collision on canal/ditch.)
- `src/point_features.py` included: 458, 487, 431 — no overlap.
- `src/areal_features.py` included: 466, 361, 378 — no overlap.

No collision: every structure code is owned by the structure taxonomy alone.

## Determinism / test-fixture guidance

Offline fixtures hardcode the confirmed codes above (343 line/area; 336/455/485
area; 367/369/485 point). `369` on line/area and `398` lock chamber have no real
geometry sample in 1807 — fixtures may synthesize them. The classification RULE
(FType-driven, name-only-for-provenance, missing→excluded) is fixed regardless of
which literal codes appear in any given HUC4.
</content>
</invoke>
