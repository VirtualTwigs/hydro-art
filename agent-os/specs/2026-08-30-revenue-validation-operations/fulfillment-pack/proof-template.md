# Customer proof / approval template (roadmap #57-ops)

Send a proof and get explicit approval **before** running the full export and
releasing final files. This protects fulfillment time (no re-renders after
delivery) and sets clear revision expectations.

## What to send as the proof

- A **watermarked, low-resolution** render of the ordered county in `neon-basin`
  style (a downscaled PNG of the master SVG — do **not** send the full-res files
  or the editable SVG at proof stage).
- The stamped **title block** visible: title, subtitle, and the `Source: USGS NHD
  · USGS NHDPlus HR · USGS WBD` credit line.
- The ordered **size** and **format(s)**, restated.

## Proof message (fill the brackets)

> Hi [name] — here's the proof for your **[County] County** watershed print
> ([size], [formats]). Please check:
>
> 1. **County & spelling** — is this the right county, titled the way you want?
>    Current title: *"[title]"* / subtitle: *"[subtitle]"*.
> 2. **Framing** — the map fills the width you ordered; the height follows the
>    county's natural shape, so the proportions may differ slightly from a plain
>    [size] rectangle. Does the framing look right to you?
> 3. **Add-ons** — you ordered: [svg / commercial license / none].
>
> Reply **"approved"** and I'll render the final print-ready files and send them
> within the 24–48 h window. The image is watermarked and low-res until approval.

## Approval ask

- Require an explicit **"approved"** (or a listed revision) in writing before
  exporting finals.
- On approval, run `export-checklist.md` end to end and deliver.

## Revision policy

- **Up to one round** of minor revisions included: title/subtitle text edits, a
  size or format change, or add-on changes. These are re-runs of the same order
  JSON with edited fields — deterministic, cheap.
- **Not included / new order:** a different county or state, or the unsupported
  `elevation-tint` style (not sold yet).
- Log any non-converting proof (buyer declines) as a **demand signal** in the
  ledger per `instrumentation.md` — the requested county/style still counts even
  without a sale.
