# Order presets — fulfillment pack (#56/#57, Epoch 11.5)

The two **approved, PRISM-free art directions** the near-term offer sells. Both pass
the Rights gate (`uses_prism=False`) and credit only public-domain USGS hydrography
(`DEFAULT_SOURCES` → the stamped attribution line), so they are sellable today.

Run either with:

```bash
python tools/fulfill_order.py --order <preset>.json
```

Deliverables land in `output/orders/<order_id>/` alongside a byte-reproducible
`<order_id>.manifest.json` (a re-run of the same order regenerates identical files).

## 1. `neon-basin` — watershed-colored river network (default offer)

Basin-colored, flow-scaled, glowing county river art via the 2D county-clip pipeline
(`renderer="pipeline"`). This is the flagship SKU and the only style wired into the
county fulfillment path today.

```json
{
  "order_id": "ORD-1001",
  "region": "Washington",
  "county": "Clark",
  "style": "neon-basin",
  "size": "18x24",
  "formats": ["png", "pdf"],
  "add_ons": ["svg", "commercial_license"],
  "title": null,
  "subtitle": null,
  "buyer_ref": "sample-buyer"
}
```

(This is the shipped `sample_order.json` in this folder.)

## 2. `elevation-tint` — hypsometric river network

Every flowline painted by its NHDPlus smoothed elevation (white summit → deep-blue
sea), flow-scaled width. Maps to the hypsometric `render_state_mono` path
(`renderer="mono"`). The reproducible **core** (order → plan → manifest) is fully
tested, but the executor's `mono` render dispatch is not yet wired — `tools/fulfill_order.py`
fails fast with a clear message pointing at `neon-basin`. Listed here as the second
approved direction so a future executor slice can turn it on without a catalog change.

```json
{
  "order_id": "ORD-2001",
  "region": "Oregon",
  "county": "Deschutes",
  "style": "elevation-tint",
  "size": "18x24",
  "formats": ["png", "pdf"],
  "add_ons": [],
  "title": null,
  "subtitle": null,
  "buyer_ref": "sample-buyer"
}
```

## Catalog knobs (all human-tunable in `src/fulfillment.py`)

- **Sizes** (`SIZES`, 300 DPI portrait): `12x16` (3600×4800), `18x24` (5400×7200),
  `24x36` (7200×10800).
- **Formats** (`PRINT_FORMATS`): `png`, `pdf`.
- **Add-ons** (`ADD_ONS`): `svg` (editable vector), `commercial_license` (license doc).
- **Regions** (`src.config.SUPPORTED_REGIONS`): Oregon, Washington, California, Idaho.

Absent `title`/`subtitle` default to `"<County> County Watersheds"` /
`"<Region> · Hydrographic river network"`; both are whitespace-collapsed and capped
(60 / 80 chars).
