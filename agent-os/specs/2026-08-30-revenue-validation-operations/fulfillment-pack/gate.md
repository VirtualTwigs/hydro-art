# Revenue gate evaluation procedure (roadmap #59)

_The decision procedure that determines whether hydro-art expands beyond the
initial four-state county print or iterates. Evaluate at 60 days from listing
go-live (or earlier if a threshold is clearly met/missed). The ledger
(`agent-os/product/revenue-ledger.md`) is the only evidence — not impressions,
not hopes._

## When to evaluate

- **Primary trigger:** 60 calendar days after the listing goes live on Etsy
  (record the go-live date in the ledger when publishing).
- **Early pass:** if both pass criteria are met before 60 days, the gate can
  close early — record the evaluation date and proceed.
- **Early fail signal:** if views are high but conversion is zero after 30 days,
  note it in the monthly decision but do not close the gate early — the full
  window may surface late converters or inform the iteration.

## Pass criteria (both required)

Read from the ledger's funnel snapshot and order ledger at evaluation time:

1. **Demand:** ≥ 8 paid orders **or** ≥ $500 gross revenue within the window.
2. **Operational feasibility:** median fulfillment time < 45 minutes
   (measured across the order ledger's `Fulfillment time` column).

**Both** must be true to pass. High revenue with slow fulfillment means the
product is desirable but the process isn't scalable — fix the bottleneck first.

## Decision paths

### Pass — proceed to expansion

If both criteria are met:

1. Record in the ledger's monthly-decision section:
   ```
   - Decision: **gate passed**.
     N paid orders, $X gross, median fulfillment Ym.
     Proceed to catalog/POD, self-serve, and Utah (#47).
   ```
2. **Unlock the deferred surface:**
   - Catalog/POD expansion (Epoch 25+)
   - Self-serve storefront (web order form already built, Epochs 28–30)
   - Utah as a fifth region (roadmap #47)
   - Epoch 12 commercialization track
3. Keep the listing live and continue logging.

### Fail — iterate once

If either criterion is not met:

1. Record in the ledger's monthly-decision section:
   ```
   - Decision: **iterate**.
     N paid orders, $X gross, median fulfillment Ym.
     [Which criterion failed and by how much.]
   ```
2. **Interview 10 non-buyers** (people who viewed/favorited/inquired but did
   not order). Identify objections: price, geography, style, trust, delivery
   time, format, or "didn't know what I was looking at."
3. **Revise the listing** based on interview findings — adjust one variable at
   a time (visual, copy, price, or geography emphasis).
4. **Run one further 60-day test** with the revised listing. Log under a new
   monthly-decision heading.
5. **Do not:**
   - Build subscriptions.
   - Expand region scope (no Utah #47).
   - Build catalog/POD or self-serve.
   - Add new styles or endpoints to the listing.

### Second fail — stop or pivot

If the iteration also fails both criteria:

1. Record the verdict: `stop` or `pivot`.
2. Assess whether the product has a viable market at all, or whether the
   channel (Etsy made-to-order) is the wrong fit.
3. Do not invest further engineering in commercialization — focus on the art
   engine and portfolio until a credible demand signal emerges.

## What the gate does NOT unlock

Regardless of outcome, these remain gated on their own criteria:

- **PRISM-derived products** — blocked by the Rights gate (not revenue).
  Selling PRISM art requires a written PRISM Climate Group arrangement.
- **Water-facility intelligence (Epoch 27)** — blocked on source-rights audit
  and revenue-priority review, independent of #59.

## Recording the verdict

The verdict lives in `agent-os/product/revenue-ledger.md` under "Monthly
decision notes." Also update the roadmap (`agent-os/product/roadmap.md`):

- On **pass:** tick `#59 Revenue gate` as `[x]` and mark Epoch 11.5 complete.
- On **iterate:** leave `#59` open; note the iteration window dates.
- On **stop:** close Epoch 11.5 with a "stopped" note; do not tick `[x]`.
