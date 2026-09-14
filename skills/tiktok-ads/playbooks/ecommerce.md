# E-commerce (DTC, dropshipping, TikTok Shop, catalog)

## Gate

Open vertical — but the **destination** decides everything downstream.

| Destination | Consequence |
|---|---|
| **TikTok Shop** | **GMV Max is the only path.** Manual Video/Product/LIVE Shopping Ads can no longer be created against a Shop destination (since July 2025). Confirm who holds the Shop's ad-account authorization *before* anyone launches — re-authorizing another account auto-pauses the incumbent's campaigns (`10`, `03`) |
| **External website** | Full manual control, `WEB_CONVERSIONS` or the Sales virtual objective, catalog optional |
| **Showcase (non-Shop)** | Manual shopping ads still available |

Regional product restrictions still apply (supplements, cosmetics with claims, devices) — `08`.

## The attribution correction to make at intake

**TikTok Shop Ads do not attribute by product.** An ad for Product A that drives a Product B purchase
counts for that ad. **There is no SKU-level ROAS for Shop or GMV Max campaigns** (`10`).

SKU-level reporting exists only on the non-Shop catalog path. If the client expects per-product ROAS,
correct it now — not in week three.

## Payout event and the optimization ladder

Payout is usually `Purchase` with value. The ladder to derive:

```
ViewContent → AddToCart → InitiateCheckout → Purchase        (+ value for VBO)
```

Choose the deepest event the account can feed at **~25 results per ad group per week — 50 if you want TikTok's own delivery advice met** (`05`). A store
doing 15 purchases a week cannot optimize on Purchase across three ad groups — that is the single
most common self-inflicted wound in this vertical.

**Value-Based Optimization needs ≥20 unique Complete Payment events with value + currency in any
consecutive 7 days** (website). Compute expected weekly purchases at target CPA before promising
ROAS bidding. Once unlocked, it persists.

## Numbers to get from the operator

- Margin per order and target ROAS, or break-even CPA. Without it, no CPM is good or bad.
- Refund and chargeback rate — and **whether refunds are sent back as events.** If not, the model
  optimizes toward reversed buyers and builds lookalikes from them (`07`).
- AOV, and whether it varies enough that value optimization beats a CPA target.
- Shipping SLA and returns policy — TikTok Shop enforces these at the account-health level.

## Catalog

Type is **mutually exclusive and unchangeable** — E-commerce vs Generic vs O2O vs Travel vs
Automotive. Pick right the first time (`10`).

Then: run product diagnostics, supply GTIN (nominally optional, flagged by TikTok's own diagnostics),
and verify **catalog match rate >90%** — `content_id` in the feed must equal `content_ids` from the
pixel. A mismatch degrades personalisation silently, with no error.

## TikTok-specific failure modes

- **GMV Max Target ROI mode under-spends when the target is too high.** Low budget utilization is a
  target problem, not a delivery problem. Misdiagnosed constantly (`10`).
- Shopify/WooCommerce plugins auto-configure the pixel — **you did not choose the event names or
  parameters.** Verify what actually fires (`07`).
- Product creative ported from Meta: static images, letterboxed 16:9, no audio. TikTok **requires
  audio** as policy and rejects statics-as-video (`06`).
- Retired format names in the brief — "Collection Ads", "Dynamic Showcase Ads" — mean the plan was
  written from stale material.

## Shape of the derivation

Destination (Shop vs web) → objective and whether GMV Max is forced → optimization event from weekly
purchase volume → VBO eligible or not → catalog needed or not → structure from the number of readable
tests → creative plan from supply → measurement window from purchase lag.
