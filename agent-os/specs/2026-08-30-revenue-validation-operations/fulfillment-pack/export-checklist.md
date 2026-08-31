# Per-order export / QA checklist (roadmap #57-ops)

Run once per paid order, after the buyer's proof is approved (see
`proof-template.md`). The executor does the deterministic work; this checklist is
the human QA around it. Measure the clock from **order received → files sent** —
that number is the `fulfillment_time` logged in the ledger and gates #59.

## 1. Build the order JSON

- [ ] Transcribe the intake into `order.json` (fields per `intake-form.md`); map
      1:1, no invented values.
- [ ] Confirm `style` is `neon-basin` (the only wired path) and `region` is one of
      OR/WA/CA/ID.

## 2. Run the executor

```
python tools/fulfill_order.py --order order.json --huc4 <HUC4-for-the-county>
```

- [ ] Pick the right `--huc4` GDB for the county (e.g. Clark County, WA = `1708`).
- [ ] It writes to `output/orders/<order_id>/`: a `<order_id>_master.svg`, one
      file per planned deliverable, and `<order_id>.manifest.json`.
- [ ] Console prints each deliverable with its sha256 prefix — no errors, no
      "No flowlines fell inside the county boundary."

## 3. Verify the deliverable plan + manifest

- [ ] The files in `output/orders/<order_id>/` match the manifest's `deliverables`
      list exactly (one print per requested format, `.svg` iff the `svg` add-on,
      `_license.txt` iff `commercial_license`).
- [ ] `manifest.json` `attribution` reads **`USGS NHD · USGS NHDPlus HR · USGS
      WBD`** (see `attribution-line.md`).
- [ ] `title_block.title` / `subtitle` are correct (defaults or the buyer's custom
      text, within the 60/80 caps).

## 4. Visual QA of the print

- [ ] Open the master SVG / PNG: the **title block** is stamped bottom-left
      (title, subtitle, `Source: …` credit) and legible against the background.
- [ ] The **attribution line** is present and complete on the print.
- [ ] Spot-check the raster at **100%** — flowlines are crisp, glow is clean, no
      clipping at the county edge, no stray artifacts.
- [ ] **Aspect caveat:** the print takes the county's natural aspect at the ordered
      *width* (e.g. 18x24 → 5400 wide, height set by the county, not a forced
      5400×7200). Confirm the framing looks right for the size sold; note it to the
      buyer if the county is much wider/taller than the nominal ratio.

## 5. Reproducibility check

- [ ] Re-run the exact same command once. The manifest's per-file sha256 values
      must be **byte-identical** to the first run (`SOURCE_DATE_EPOCH=0` pins the
      PDF CreationDate; SVG/PNG are already deterministic). If any sha changes,
      stop and investigate before sending.

## 6. Deliver + log

- [ ] Send the approved formats + any add-ons to the buyer.
- [ ] Append the order row to `agent-os/product/revenue-ledger.md` and tally the
      requested county/style per `instrumentation.md`; record the measured
      `fulfillment_time`.
