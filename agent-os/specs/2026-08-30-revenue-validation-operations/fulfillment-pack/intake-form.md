# Buyer intake form (roadmap #57-ops)

The fields a buyer supplies, mapping **1:1** onto the `tools/fulfill_order.py`
order JSON so intake → `order.json` is mechanical. Validation mirrors the
boundary allowlists in `src/fulfillment.py` (`build_order`) — anything outside an
allowlist is rejected fast with a single user-facing message, so collect exactly
these values.

## Fields

| Intake question | order.json key | Required | Allowed values / rule |
|---|---|---|---|
| Your reference / name | `buyer_ref` | no | free text, whitespace-collapsed, capped 120 chars |
| Order ID | `order_id` | yes (assigned by us) | non-empty string, e.g. `HA-2026-0001` |
| State (region) | `region` | yes | **Oregon, Washington, California, Idaho** (`SUPPORTED_REGIONS`) |
| County | `county` | yes | non-empty county name within the state, e.g. `Clark` |
| Style | `style` | yes | **`neon-basin`** only (see note) |
| Print size | `size` | yes | `12x16`, `18x24`, `24x36` (inches, 300 DPI portrait) |
| Print format(s) | `formats` | yes (≥1) | any of `png`, `pdf` |
| Add-ons | `add_ons` | no | any of `svg` (editable vector), `commercial_license` |
| Custom title | `title` | no | free text; house rules below |
| Custom subtitle | `subtitle` | no | free text; house rules below |

**Style note.** Only `neon-basin` is sold today: it is the sole county path wired
in `tools/fulfill_order.py` (its `renderer="pipeline"`), and it is **PRISM-free**
(`uses_prism=False`) so it clears the Rights gate. `elevation-tint` is an approved
future direction but its `mono` executor dispatch isn't wired — **do not list or
accept it** (it fails fast with "use 'neon-basin' for now").

**Size → pixels (300 DPI, portrait).** The rasterized print takes the county's
natural aspect at the ordered *width*, so the height below is the plan/manifest
canvas ceiling, not necessarily the delivered pixel height:

| size | canvas px (w × h) |
|---|---|
| `12x16` | 3600 × 4800 |
| `18x24` | 5400 × 7200 |
| `24x36` | 7200 × 10800 |

## Example `order.json`

```json
{
  "order_id": "HA-2026-0001",
  "region": "Washington",
  "county": "Clark",
  "style": "neon-basin",
  "size": "18x24",
  "formats": ["png", "pdf"],
  "add_ons": ["svg"],
  "title": null,
  "subtitle": null,
  "buyer_ref": "jane-doe"
}
```

## Title / subtitle house rules

Defaults are encoded in `src/fulfillment.py`; custom text is optional and is
cleaned the same way (internal whitespace collapsed, stripped, length-capped).

- **Default title** (`default_title`): `"<County> County Watersheds"`, title-cased.
  `"County"` is appended only when the name doesn't already end in it — so both
  `Clark` → **"Clark County Watersheds"** and `Multnomah County` →
  **"Multnomah County Watersheds"**.
- **Default subtitle** (`default_subtitle`): `"<Region> · Hydrographic river
  network"`, e.g. **"Washington · Hydrographic river network"**.
- **Custom title**: capped at **60** chars (`TITLE_MAX`). Keep it a headline —
  place name + subject; no marketing copy.
- **Custom subtitle**: capped at **80** chars (`SUBTITLE_MAX`). Keep the
  `Region · descriptor` shape so the credit line below it still reads.
- Empty/whitespace-only custom text falls back to the default (never blank).

## Attribution (non-negotiable, stamped on every asset)

Every sold asset carries the deterministic USGS source credit — see
`attribution-line.md`. Buyers cannot opt out; the hydrography is U.S. federal
public-domain data and the credit is part of the Rights gate.
