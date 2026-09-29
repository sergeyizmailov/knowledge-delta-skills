# 03 — Shopping and PMax retail structure

Reviewed 2026-08-27. Feed attributes → `01`. PMax/Shopping **campaign** mechanics, feed-only vs
assets, brand exclusions, and product-level reporting → `google-ads/07`. PMax vs Shopping **who wins
an impression** → `google-ads/01` (Ad Rank since 2024-10-17). Do not treat this file as the buy skill.

## Standard Shopping still exists

Not deprecated despite years of speculation, but its **role has changed** — see PMax-dominant section
below.

### The priority ladder

Run two or more Shopping campaigns over the **identical product set**, differentiated only by priority
and negatives:

- `Shopping – Brand` — **Low priority**, no negatives. Catches brand queries cheaply because it is the
  only campaign eligible for them.
- `Shopping – Generic` — **Medium/High priority**, with the brand term as a campaign-level negative so
  it never competes for or dilutes brand-query data.

> **The caveat everyone misses: campaign priority only does anything when two or more campaigns
> advertise the SAME products in the SAME country and language.** If the product sets are disjoint,
> priority is a no-op. Copying this structure onto campaigns with separate catalogs accomplishes
> nothing.
>
> **The budget trap that silently defeats the whole structure:** if the higher-priority campaign
> exhausts its daily budget, **Google falls back to the lower-priority campaign** to keep serving. An
> under-budgeted "premium" campaign quietly reverts its spend to the cheap one. Use shared or generous
> budgets.

### Listing groups

Ad groups split by `google_product_category`, `product_type`, `brand`, or `custom_label_0-4` rather
than by keywords. This is where the label schema in `01` becomes actionable.

**No "bid to position" in Shopping** — no ad-rank-to-position table as for text ads. Ranking is
auction-based on bid × quality with no merchant-visible position lever, so the priority ladder and
Smart Bidding are the only two real levers.

Reporting exposes benchmark CTR and benchmark max CPC (peer comparison) plus the standard Lost IS
(budget) / Lost IS (rank) split. 🔺 Exact current column names not re-verified.

### The role of standard Shopping in a PMax-dominant account

**Most common structural mistake:** full-catalog standard Shopping parallel with no priority/negative
differentiation — duplicates PMax's eligibility without adding a control PMax lacks. Overlapping
impressions go to Ad Rank, not an old "PMax uber-priority" (`google-ads/01`).

Two roles that do work:

1. A deliberately **Low-priority, negative-heavy brand-isolation campaign** that fires only when PMax
   and Search both fail to cover a query — giving you a clean incremental-brand-cost baseline to
   measure PMax against.
2. A **segment-specific override** for products you want kept out of PMax's automated bidding — thin
   margin or clearance SKUs where you need hard manual bid caps Smart Bidding will not respect.

## PMax retail

### Feed-only first

Practitioner recommendation, verbatim: *"I recommend most stores start with feed-only. It forces your
budget into Shopping, which is almost always your highest-converting channel."* Full creative asset
groups open budget eligibility to Display, YouTube, and Discover — the leakage feed-only avoids
during early optimization. Add assets once the feed-only baseline exists and cross-network reach is
wanted deliberately.

**Caveat (`google-ads/07`):** feed-only does not guarantee zero Display/YouTube spend.

### Asset group structure

How many asset groups, and feed-only vs assets, is a **buy** decision — canonical in `google-ads/07`
(start 1–2, conversions-per-group, not a 3–7 rule). Here: split listing-group **filters** on the
`custom_label` schema in `01`. **Not by audience signal.**

> **Explicit 2026 caution:** *"Avoid product overlap or duplicating asset groups based on audience
> signals. This is a strategy that no longer works in 2026."* Audience-signal-based asset-group
> splitting was widely taught in 2023–24 and is now obsolete.

Each asset group's **listing group filter** scopes it to a product subset — PMax-native equivalent of
Shopping's product-group subdivision, and the mechanism that makes `custom_label` actionable.

### PMax vs standard Shopping — do not invent a priority dial

**There is no user-facing priority dial between PMax and Standard Shopping** the way there is between
two Shopping campaigns. Since **2024-10-17** they compete on **Ad Rank**, not an old PMax-wins-by-default
rule. Canonical write-up: `google-ads/01`.

Shopping is exempt from the exact-match-beats-PMax Search rule (`google-ads/07`) — a Shopping campaign
can serve alongside Search even when an exact keyword exists. That is not the same as "PMax always
beats Shopping."

### Cannibalization

> *"Check where PMax conversions come from before declaring victory: brand cannibalization flatters
> PMax numbers."*

PMax auto-bids into brand-term auctions winnable organically or via a cheap dedicated brand campaign,
so **its reported ROAS is systematically inflated by conversions it did not cause.**

Mitigation: dedicated **exact-match** Search brand campaign to keep brand traffic segregated/
measurable, and/or **brand exclusion lists inside PMax** forcing it onto non-brand discovery.

**Measurement trap to state when recommending this:** excluding brand makes PMax's own ROAS look
worse, so the correct change gets reverted for the wrong reason (canonical statement →
`measurement-experimentation-ops`). Holdout methodology → `google-ads/07`.

### Getting product-level data out of PMax

Two API resources, joined:

- **`asset_group_listing_group_filter`** — a resource **without metrics**. Gives the structural mapping
  of which listing-group filter belongs to which asset group.
- **`shopping_performance_view`** — a resource **with metrics**. Product-level impressions, clicks,
  cost, conversions, segmentable by product attributes, across both standard Shopping and PMax.

**Join them to reconstruct true per-product, per-asset-group performance** — the standard workaround
for PMax's UI reporting opacity; the same join commercial tooling performs internally.

Mike Rhodes' PMax script does this natively, including a **6-bucket product matrix** (zombies,
zero-conversion, meh, flukes, costly, profitable) spanning both PMax and standard Shopping — see
`google-ads/07`.

## Retail levers

### Promotions

`promotion_id` (≤50 chars, case-sensitive, no spaces or symbols) is mandatory and unique. The feed must
declare product applicability, offer type (no-code vs generic-code), title (≤60 chars), start/end dates
with timezone, redemption channel, and destination. Formats: XML, tab-delimited, Google Sheets.

**2026 expansion:**

- **Subscription promotions** — free trials and recurring-billing discounts, via "Subscribe and save"
  or the `subscribe_and_save` redemption-restriction field.
- **Retail abbreviations now whitelisted** in promo text without disapproval risk: **BOGO, B1G1, MRP,
  MSRP**.
- **Brazil only**: payment-method-specific promotions (`forms_of_payment`) including digital-wallet
  cashback. No confirmed plans to globalize.

Availability: AU, BR, CA, FR, DE, IN, IT, JP, KR, ES, NL, UK, US.

### Price competitiveness

**Analytics → Pricing.** Shows products with price-comparison data and how many sit above/below the
**benchmark price**, computed across all retailers selling the same GTIN — **GTIN required for this
feature.**

Separate **AI sale-price suggestion** engine: 7-day simulations across price points factoring
elasticity and comparable-business performance, predicting click/conversion uplift per price.
**Requires conversion tracking, not GTIN.**

Legal restriction: internal-use only — *"can't be resold, publicly displayed, advertised, or
aggregated across businesses."*

### Local inventory ads

Available in **80+ regions**. Google-reported lift for retailers combining LIA with standard
Shopping: **+21% store visits, +9% online conversions** for products also available in-store.
Undated standing Google claim, not a fresh study.

Setup paths: "Pickup today" · "Pickup later" · "Automated inventory" (auto-sync from online stock).

### CSS — real, but EU-only

**Confirmed real — a margin-removal mechanic, not a platform discount.**

Origin: **EU's 2017 Google Shopping antitrust decision** forced Google to open Shopping inventory to
competing Comparison Shopping Services on equal terms with Google's own. Google's default CSS bakes a
margin on top of base CPC; third-party/self-service CSS providers don't add that layer — that
differential is the "~20%".

**Not a visible line-item discount or account rebate** — manifests as more competitive effective
bidding headroom. Marketed as "up to 20%": a ceiling, not a flat rate, varying by provider/vertical.

**Mandatory CSS markets:** Austria, Belgium, Czech Republic, Denmark, Finland, France, Germany, Greece,
Hungary, Ireland, Italy, Netherlands, Norway, Poland, Portugal, Romania, Slovakia, Spain, Sweden,
Switzerland, UK.

> **US applicability: none.** There is no CSS program, requirement, or CPC-margin mechanic in the US.
> **Never cite the 20% figure to a US-focused advertiser** — the antitrust remedy it descends from has
> no US analog.
