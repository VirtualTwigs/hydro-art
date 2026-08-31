# Attribution line (roadmap #57-ops, Rights gate)

The deterministic USGS source credit stamped on **every** sold asset — the
print's title block, the editable SVG, and the commercial-license doc. It is
produced by `src.fulfillment.attribution_line()` from `DEFAULT_SOURCES`
(name-sorted, ` · ` separated), so it is auditable and identical on every re-order.

## The exact string

```
USGS NHD · USGS NHDPlus HR · USGS WBD
```

As stamped in the title block it reads:

```
Source: USGS NHD · USGS NHDPlus HR · USGS WBD
```

## Why it's fixed

- **Rights gate.** The underlying hydrography (NHDPlus HR / NHD / WBD) is U.S.
  federal **public-domain** data; the credit is the condition under which the art
  is sellable. No PRISM-derived asset may ship — `assert_sellable` refuses any
  style with `uses_prism=True`, so only the two approved PRISM-free directions
  (`neon-basin`, `elevation-tint`) are sellable, and the near-term listing sells
  only `neon-basin`.
- **Deterministic.** The sources are name-sorted, so the string never varies
  order-to-order; it is part of the byte-identical manifest that makes a re-order
  reproducible.

If a future source is added to `DEFAULT_SOURCES`, regenerate this file from
`attribution_line()` — do not hand-edit the string.
