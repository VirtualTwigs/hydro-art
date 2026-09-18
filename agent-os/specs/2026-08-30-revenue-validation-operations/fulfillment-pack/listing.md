# Etsy listing — Riverglyph County Watershed Print (roadmap #56)

_Made-to-order listing for the Epoch 11.5 revenue experiment. Single listing,
single style, narrow geography. Sell a service, not a platform._

## Listing title

> Riverglyph Custom County Watershed Art Print — Neon River Map — OR WA CA ID

_(≤ 140 chars; keywords: watershed, river, map, custom, neon, county, state abbrevs)_

## Listing description

> **Your county's rivers, creeks, and watersheds — rendered as glowing neon art.**
>
> Every line in this print is a real stream or river, mapped from USGS
> hydrographic data and colored by watershed. No two counties look the same.
>
> **How it works:**
> 1. Tell me your **state** and **county** (Oregon, Washington, California, or Idaho).
> 2. I render a print-quality image of every mapped waterway in that county,
>    colored by watershed basin, with a soft neon glow on a dark background.
> 3. You receive **print-ready files (PNG and/or PDF at 300 DPI)** within
>    **24–48 hours**.
>
> **Sizes (portrait, 300 DPI):**
> - 12 x 16 in (3600 x 4800 px)
> - 18 x 24 in (5400 x 7200 px)
> - 24 x 36 in (7200 x 10800 px)
>
> The print follows your county's natural shape at the ordered width — height
> may differ slightly from the nominal size ratio. You'll see a proof before
> I render the finals.
>
> **Included:**
> - Print-ready PNG and/or PDF
> - Title block with county name, state, and source credit
> - One round of minor revisions (title/subtitle text, size or format change)
>
> **Add-ons (select at checkout):**
> - **Editable SVG** — the layered vector source file, suitable for further
>   editing in Illustrator / Inkscape / Figma
> - **Commercial license** — use the artwork in products, merchandise, or
>   client work
>
> **Custom title / subtitle:** by default, the print reads
> *"[County] County Watersheds"* over *"[State] · Hydrographic river network"*.
> You can substitute your own text (title ≤ 60 chars, subtitle ≤ 80 chars).
>
> **Data source:** U.S. Geological Survey NHDPlus HR / NHD / WBD — federal
> public-domain hydrographic data. Every print carries the source attribution
> line: *Source: USGS NHD · USGS NHDPlus HR · USGS WBD*.
>
> **Digital delivery only.** This listing is for print-ready files, not a
> physical print. You can print at home, at a local shop, or through any
> online print service.
>
> Questions? Message me with your county and I'll confirm availability.

## Listing details

| Field | Value |
|---|---|
| Category | Art & Collectibles > Prints > Digital Prints |
| Item type | Digital (made to order) |
| Processing time | 1-3 business days |
| Personalization | Required — buyer specifies state + county |
| Variations: Size | 12x16 / 18x24 / 24x36 |
| Variations: Format | PNG / PDF / Both |
| Add-ons | Editable SVG; Commercial license |
| Tags | riverglyph, watershed art, river map, county map, hydrography, neon art, custom map, Oregon, Washington, California, Idaho, waterway print, topographic art |
| Shipping | Digital download (no physical shipping) |

## Image set

Listing images should show the product at its best. Produce via
`tools/fulfill_order.py` on sample counties.

| Slot | Image | Source |
|---|---|---|
| 1 (hero) | Clark County, WA — full print with title block | `fulfill_order.py` sample |
| 2 | Multnomah County, OR — full print | `fulfill_order.py` sample |
| 3 | Close-up crop — flowline detail + glow | crop from slot 1 or 2 |
| 4 | Title block close-up — title, subtitle, attribution | crop from slot 1 |
| 5 | Size comparison mockup (12x16 / 18x24 / 24x36) | optional; frame mockup tool |

**Status:** image set blocked on GDAL host — produce samples via
`tools/fulfill_order.py` when a GDAL+NAS session is available.

## Pricing (owner decision)

Pricing is a business decision, not a spec artifact. Considerations:

- **Cost floor:** near-zero marginal cost (compute time only; data is free).
- **Fulfillment time target:** < 45 min median (the #59 gate).
- **Comparable Etsy custom map prints:** $25-$75 for digital, $40-$120+ for
  physical; SVG/commercial add-ons are uncommon and can carry a premium.
- Set size-tiered pricing in the listing variations. Add-ons priced separately.

## Rights checklist

- [x] Style is `neon-basin` (`uses_prism=False`) — clears the Rights gate.
- [x] Data sources are U.S. federal public domain (USGS NHDPlus HR / NHD / WBD).
- [x] Attribution line stamped on every deliverable: `USGS NHD · USGS NHDPlus HR · USGS WBD`.
- [x] No PRISM-derived art listed or sold.
- [ ] Listing published — record the go-live date in `revenue-ledger.md` to
      start the 60-day measurement window (#59).
