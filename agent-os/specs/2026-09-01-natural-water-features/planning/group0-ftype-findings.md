# Group 0 — NHD FType/FCode findings (real-data verification)

Verified against a real extracted GDB: `datasets/nhdplus_hr/1807/NHDPLUS_H_1807_HU4_GDB.gdb`
(HUC4 1807, Oregon coast), decoded via the authoritative `NHDFCode` domain table embedded in
the GDB (not from memory). Date: 2026-09-01.

## Confirmed codes

### Point families — source layer `NHDPoint` (NEW `load_point_features` seam)

| Class | FType | Domain description | 1807 NHDPoint count | Status |
|-------|-------|--------------------|--------------------:|--------|
| `spring`    | 458 | Spring/Seep | 1119 | confirmed, present |
| `waterfall` | 487 | Waterfall   | 15   | confirmed, present (spec's guess of 487 was correct) |
| `rapids`    | 431 | Rapids      | 0    | code confirmed via domain table; **absent from 1807** — real NHD code, untested against real point geometry in this sample |

Classified-but-excluded (present in taxonomy, off by default — accounted for, never guessed):

| Class | FType | Domain description | 1807 count |
|-------|-------|--------------------|-----------:|
| `well`     | 488 | Well      | 2610 |
| `sinkhole` | 450 | Sink/Rise | 126  |

Other `NHDPoint` FTypes present in 1807 that fall OUT of scope (Epoch 16 infrastructure or
non-water) → all classify to `excluded`: 441 Rock (434), 367 Gaging Station (313), 436
Reservoir-point (37), 485 Water Intake/Outflow (8), 369 Gate (2).

### Areal families — source layer `NHDWaterbody` (EXISTING `load_waterbody_layers` seam)

**CORRECTION to spec.md:** these are `NHDWaterbody` FTypes, NOT `NHDArea`. They are exactly the
three codes `src/waterbodies.py:FTYPE_CLASS` already maps to `excluded`, so the areal taxonomy is
genuinely complementary and needs **no new loader** — reuse `load_waterbody_layers` (already loads
`NHDWaterbody` + `NHDArea` with `FType`/`FCode`/`GNIS_Name`/`Permanent_Identifier`/`ReachCode`/
`AreaSqKm`).

| Class | FType | Domain description | 1807 NHDWaterbody count | Status |
|-------|-------|--------------------|------------------------:|--------|
| `wetland`       | 466 | Swamp/Marsh | 135 | confirmed, present |
| `playa`         | 361 | Playa       | 1   | confirmed, present |
| `perennial_ice` | 378 | Ice Mass    | 0   | code confirmed via domain table; **absent from 1807** (coastal, low-elevation) — expected in high-elevation HUC4s |

Note: NHD has a single `Ice Mass` (378) code — it covers glacier/snowfield/perennial ice; there is
no separate glacier or snowfield code.

## Pipeline-integration consequence

Because the areal families ride the existing waterbody loader, the `validate` stage must load
waterbody layers when **either** waterbodies **or** areal features are enabled (today it loads only
when waterbodies are enabled). The `NHDWaterbody` layer is then fed through BOTH taxonomies:
`src.waterbodies.classify_layer` (lake/pond/reservoir/bay/inlet) and the new
`src.areal_features.classify_areal_layer` (wetland/playa/perennial_ice) — non-overlapping by
construction (waterbody sends 466/361/378 → excluded; areal sends everything else → excluded).

## Out-of-scope items observed (future candidates, NOT in this spec's six families)

- `Wash` (FType 484, `NHDArea`) — ephemeral desert streambed, arguably a natural water feature;
  155 in 1807. Deliberately excluded from the agreed six-family first cut.

## Determinism / test-fixture guidance

Offline test fixtures should hardcode the confirmed codes above (458/487/431 points;
466/361/378 areals; 488/450 excluded points). The classification RULE (FType-driven,
name-only-refining, missing→excluded) is fixed regardless. `rapids` (431) and `perennial_ice`
(378) have confirmed codes but no real-geometry sample in 1807 — fixtures may synthesize them.
