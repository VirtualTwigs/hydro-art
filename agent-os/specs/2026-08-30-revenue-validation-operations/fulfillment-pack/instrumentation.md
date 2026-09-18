# Instrumentation procedure (roadmap #58)

_How and when to update `agent-os/product/revenue-ledger.md`. The ledger tables
are the single source of truth for the #59 gate decision — not marketplace
impressions, not memory. This procedure ensures the data is clean when the
60-day window closes._

## Weekly: funnel snapshot

**When:** every Monday (or the first working day of the week).

**Source:** Etsy Shop Manager → Stats (or equivalent marketplace analytics).

**Update the "Funnel snapshot" table in `revenue-ledger.md`:**

| Field | Where to read |
|---|---|
| Listing views | Shop Manager → Listings → this listing → Views |
| Favorites / saves | Shop Manager → Listings → this listing → Favorites |
| Inquiries | Count of new message threads referencing this listing since last snapshot |
| Paid orders | Running total from the order ledger (below) |
| Refunds | Running total of refunded orders |
| Gross revenue | Sum of `Gross` column in the order ledger |
| Marketplace + payment fees | Sum of `Fees` column in the order ledger |
| Net revenue | Gross − Fees |
| Median fulfillment time | Median of `Fulfillment time` column in the order ledger |

Overwrite the "To date" column each week — the ledger is a running total, not
a time series. Git history preserves the weekly snapshots.

## Per order: order ledger row

**When:** immediately after delivering the final files to the buyer.

**Append one row to the "Order ledger" table:**

| Column | Value |
|---|---|
| `#` | Next sequential number |
| `Date` | Delivery date (YYYY-MM-DD) |
| `Location requested` | `<County>, <State abbrev>` (e.g. `Clark, WA`) |
| `Style` | `neon-basin` (the only listed style) |
| `Add-ons` | `svg` / `commercial_license` / both / none |
| `Gross` | Listing price + add-on charges |
| `Fees` | Etsy listing fee + transaction fee + payment processing fee |
| `Net` | Gross − Fees |
| `Fulfillment time` | Minutes from order received to files sent (measure the clock) |
| `Refund?` | `no` (update to `yes` + reason if refunded later) |
| `Notes` | Revision requests, buyer feedback, anything unusual |

**Also update the "Requested locations / styles" demand table:** increment the
count for the ordered county+style, or add a new row.

## Per inquiry (non-converting)

**When:** a buyer messages about the listing but does not order.

**Update the "Requested locations / styles" demand table only:**

| Column | Value |
|---|---|
| `Location / watershed` | What they asked about (e.g. `Deschutes County, OR` or `"rivers near Bend"`) |
| `Style` | `neon-basin` or whatever they described |
| `Count` | +1 |

Non-converting inquiries are demand signal — they inform which counties/styles
to prioritize if the gate passes, and which objections to address if it fails.

**Also note in the weekly funnel snapshot:** increment the `Inquiries` count.

## Per refund

**When:** a refund is issued for a previously fulfilled order.

1. Update the original order row: set `Refund?` to `yes — <reason>`.
2. Increment `Refunds` in the funnel snapshot.
3. Adjust `Gross revenue` and `Net revenue` in the funnel snapshot.

## Monthly decision note

**When:** end of each calendar month during the experiment window.

**Append a section to "Monthly decision notes" in the ledger:**

```markdown
### YYYY-MM
- Observed: X paid orders, $Y gross, $Z net, median fulfillment Nm.
  Inquiries: N. Top requested locations: [list]. Refunds: N.
- Decision: continue / iterate / gate passed / stop.
  [One sentence on why.]
```

The monthly note is a checkpoint, not the gate itself — the gate evaluation
happens at 60 days per `gate.md`.
