# 01 — Feed spec, submission, titles, labels

Reviewed 2026-08-27. Attribute limits and enforcement dates are volatile 🔺.

## Merchant Center Next — current navigation

"Merchant Center Next" is now simply **Merchant Center**; classic is being phased out account by
account with no opt-in toggle remaining.

- **Diagnostics** → **Products & store → Products → Needs attention** (replaces classic "Diagnostics").
- **Analytics** (replaces Performance) → Summary · Popular products · Competitors · **Pricing** ·
  Audience insights · Shipping Analytics · AI performance insights.
- **Feed rules and supplemental sources** → **Products & store → rules for your product data sources**.
- New **Ask Advisor** conversational assistant.
- **Store Quality program / "Top Quality Stores" badge** — a trust layer surfaced in Analytics, used as
  a ranking-adjacent quality signal. Criteria: fast shipping, transparent returns, high-quality site,
  positive reviews. Google explicitly disclaims that it guarantees purchase protection.

## Universal Commerce Protocol 🔺

Open standard for AI agents/Google surfaces to complete checkout **inside Google**; expanded to main
Search Shopping results May 2026.

- **`native_commerce(checkout_eligibility)`** is the confirmed gating attribute. Official wording:
  *"Only product listings using the native_commerce(checkout_eligibility) product attribute will
  display the 'Buy' button for this checkout experience."*
- **Rollout: United States, Canada, Australia — still "early access… available for select merchants."**
  Not a general-availability requirement yet.
- `consumer_notice` (regulatory-warning disclosure) comes from a third-party source only; not
  officially confirmed.
- Full technical spec at `developers.google.com/merchant/ucp` — fetch before hardcoding feed logic.
- Exclude ineligible categories (subscriptions, pre-orders, age-restricted, digital goods, final-sale)
  via restriction rules, then verify no new Errors after refresh.

> **Correction: UCP did not replace Buy on Google.** Buy on Google for Search/Shopping **shut down
> 2023-09-26** (announced 2023-06-29); YouTube variant preserved. Three-year gap — separate
> initiatives, not sequential versions.

## Required attributes

| Attribute | Limit | Notes |
|---|---|---|
| `id` | 50 chars | Unique, stable, **never reuse or recycle** — it is the join key for every overlay mechanism |
| `title` | 150 chars | **Practical visible cutoff ~70** (see below) |
| `description` | 5,000 | Plain text, no HTML, no promo text |
| `link` | 2,000 | RFC-encoded, must match the landing page exactly |
| `image_link` | 2,000 | **Min 500×500px — enforcement date 2027-01-31** 🔺 |
| `availability` | — | `in_stock` / `out_of_stock` / `preorder` / `backorder`. **Must match the landing page and checkout** or the automated crawl fires "inaccurate availability" |
| `price` | — | Numeric + ISO 4217. Must match landing page **and checkout** |
| `brand` | 70 | Required for new products except media (books/movies/music/games) |

### Conditionally required

| Attribute | Trigger | Format |
|---|---|---|
| `availability_date` | `availability = preorder` | ISO 8601 `YYYY-MM-DDThh:mm` |
| `gtin` | A manufacturer GTIN exists | **8–14 numeric digits only**, no dashes or spaces. UPC=12, EAN=13, ISBN-13=13 (978/979). Avoid restricted prefixes ("2","02","04") and coupon ranges. Validate the check digit |
| `mpn` | No manufacturer GTIN | 70 chars, pair with `brand` |
| `identifier_exists` | Genuinely no UPI — store brand, custom-made, vintage, replacement part | `yes`/`no` |
| `condition` | Used/refurbished/open-box | `new` / `refurbished` / `used` |
| `item_group_id` | Variant product | 50 chars; required in some countries for variant grouping |

**Never put an internal SKU into `gtin` or `mpn` as a fake identifier.** Leave blank and set
`identifier_exists=no`.

Google softens GTIN to "recommended" but warns: *"Products with an assigned GTIN, but submitted
without one, may have limited visibility."* **Omitting a real GTIN is a self-inflicted ranking
penalty** and disables price-benchmark data (below).

### Load-bearing optional attributes

`additional_image_link` (up to 10) · `sale_price` + `sale_price_effective_date` (ISO 8601 range —
**never submit a sale without the real non-sale `price` present; that is a misrepresentation
trigger**) · `custom_label_0-4` (100 chars each) · `google_product_category` (**set explicitly for
anything Google might misclassify**) · `product_type` (750, your own taxonomy) · `product_highlight`
(150, 2–100 short benefit bullets) · `video_link` (6–240s, 720p min) · `expiration_date` (**must be
<30 days out**) · `energy_efficiency_class` (**Switzerland/Norway/UK only**) · `certification`
(`EC:EPREL:code`, EU energy) · `ads_redirect` (alternate landing URL for ad clicks only) ·
`loyalty_program` / `subscription_cost` / `installment` · `structured_title`/`structured_description`
paired with `digital_source_type` to disclose AI-generated content.

**Two attributes that get conflated constantly:**

- **`shipping_label`** is a merchant-defined string joined against **shipping settings' rate rules**.
- **`custom_label_0-4`** are for marketing and bidding segmentation.

They are unrelated. Conflating them is a common integration bug.

Also: `shipping` can come from the **feed per item** *or* from account-level **shipping settings**.
Mixing both is the usual source of "conflicting shipping data" warnings. `min_handling_time` /
`max_handling_time` combine with transit time to compute the displayed delivery estimate — a stale
`max_handling_time` is a quieter version of the availability-mismatch problem.

`excluded_destination` / `included_destination` control which surface a product is eligible for —
useful to keep clearance SKUs out of paid Shopping while allowing free listings.

🔺 Field-level sub-structure and limits for `shipping[]`, `tax[]`, `canonical_link`, and
`promotion_id` were **not** verified this pass. Cross-reference
`support.google.com/merchants/answer/7052112` before hardcoding a schema.

### Format rules that cause silent disapprovals

English attribute **names and enum values** even on non-English feeds · underscore-separated
multi-word attributes · **periods not commas** for decimals · ISO 4217 only · fully RFC-encoded URLs ·
no ALL CAPS · no placeholder images · **no promotional text anywhere in title or description**.

## Submission

**Content API for Shopping sunset 2026-08-18.** The successor is **Merchant API**, stable **v1**.

> **Scope correction — the sunset is an API-integration event, not "all feeds break."** Only
> integrations calling `content.googleapis.com` (Content API v2.1) stopped. **Manual upload, scheduled
> fetch, Google Sheets, and platform connectors were unaffected** — they never routed through Content
> API.

**Merchant API v1beta was discontinued 2026-02-28** — earlier than the Content API sunset. Anything
still on v1beta broke months ago.

Base URL `https://merchantapi.googleapis.com`, path pattern
`{sub-api}/v1/{resource}:{method}` — e.g.
`GET https://merchantapi.googleapis.com/products/v1/accounts/{id}/products/{productId}`.

Sub-APIs: products, accounts, data sources, reports, promotions, etc. — the base URL + pattern above is what matters.

**Extended access** to Content API exists as a request mechanism
(`developers.google.com/merchant/api/support/get-help#request-extension`) but approval criteria are
undocumented. Treat it as an exception process, not a grace period.

| Method | Latency | Custom attributes | Fit |
|---|---|---|---|
| Automatic extraction / crawl | Uncontrolled, opaque | **None** — on-page data only | Very small catalogs, gap-filling |
| Scheduled fetch | You control it | Full | **The standard professional default beyond a few hundred SKUs** |
| Manual upload | On demand | Full | One-off corrections, testing |
| Google Sheets | Fetch every 24 h default (configurable), UI-only source; MC fetches with its own identity | Full; agent-editable via service account (`google-grey-ops/scripts/sheetfeed.py`, `--target mc`) | Small catalogs, one sheet shared with a Meta catalog (availability enum differs: `in_stock` vs `in stock`) |
| Merchant API push | Real-time | Full, programmatic | High-velocity catalogs, custom feed layers |
| Platform connector | Platform-dependent | **Often lossy for custom labels** | Shopify-native stores wanting zero maintenance |

**Why crawl-only degrades at scale:** crawl-derived price/availability drift from a structured feed's
precision; **custom attributes cannot be crawled — they don't exist on-page**; refresh cadence
opaque. Pattern: **structured primary feed + supplemental/rules layer for enrichment**, crawl for
gap-filling only.

> **Mixing methods on one data source causes silent "last write wins" conflicts** — a scheduled
> fetch overwrites a manual UI correction next cycle. One primary method per source; supplemental
> feeds/rules for overlays.

**Feed rules and supplemental feeds** both live under Products & store → rules for your product data
sources. Attribute rules have a **test/preview mode — use it**, it prevents catalog-wide breakage.
Supplemental feeds are supported for multi-client accounts.

🔺 **Unverified:** precedence when a feed rule and a supplemental feed target the same attribute on the
same product, and the definitive list of attributes supplemental feeds cannot override. `id` is
generally understood to be unchangeable (it is the join key) but this was not re-verified.

## Titles

**Visible cutoff ~70 characters**, field allows 150. Google: *"Google will show as much of your
product title as possible, but probably no longer than 70 characters."* **Put decision-driving
attributes before character 70** — per-category templates (Brand + attribute order per vertical,
e.g. Apparel: Brand + Gender + Type + Color) are secondary to this cliff.

- **Cliff is empirically real** — DataFeedWatch, 20,000-SKU, 30-day paid+organic Shopping A/B:
  performance drops materially once the load-bearing keyword falls past ~char 70.
- **"Specs over descriptions"** — leading with hard data (pack qty, spec, model number) beats
  generic marketing adjectives on both CTR and CVR.
- Second cohort (7,000 SKUs, 60 days, organic-weighted): AI-rewritten titles → **fewer but
  higher-quality clicks** (better post-click conversion, not more raw clicks). Judge title tests on
  conversion, not click volume.

**Never in a title:** price · sale price · sale dates/time-limited language · shipping/delivery-date
claims · store name · ALL CAPS · promo text ("SALE", "% OFF", "FREE SHIPPING", "BEST PRICE") ·
non-universal foreign terms. **Promotional text in title or description is a policy violation
trigger, not a soft ranking issue** — evaluated on the same surface as landing-page violations.

**Testing at scale:** (1) 50/50 split-test AI-generated vs control titles on a large SKU sample; (2)
once winning **patterns** (not individual titles) emerge, codify into **repeatable templates with
attribute substitution and fallback chains**. Unbounded live LLM generation across a whole catalog
"risks ruining feed quality" — **AI as testing sandbox; rule-codified templates as production.**

## `custom_label_0-4`

Five slots, 100 chars each. The standard professional schema:

| Slot | Use | Drives |
|---|---|---|
| 0 | Margin tier / profit band | ROAS target divergence — high-margin SKUs sustain a lower target |
| 1 | Price band | AOV-segmented messaging, bid ceilings |
| 2 | Bestseller rank / sales velocity | Budget aggressiveness on proven winners |
| 3 | Seasonality (core / seasonal / clearance) | Seasonal ramp scoping |
| 4 | Stock lifecycle (new / in-stock / low-stock / clearance) | Pause-on-stockout logic |

Bestseller labeling is the one narrowly confirmed pattern: compute trailing 30-day revenue rank,
bucket into "Top 10 / 25 / 50 / 100", write via feed rule, then split listing groups on it.

**The mechanical throughline: label schema → listing-group filter → divergent bid strategy per
filter.** Worked example:

- `custom_label_2 = Top 10` → own asset group, tROAS set meaningfully **below** account average to
  protect volume on proven winners.
- `custom_label_4 = clearance` → Maximize Conversion Value with **no tROAS floor** to liquidate.
- `custom_label_0 = low-margin` → **excluded from PMax entirely** via a negative listing-group filter
  and confined to a manually-capped standard Shopping campaign, so Smart Bidding cannot chase volume
  at a loss.

This is what makes per-segment strategy possible without per-SKU manual bidding.
