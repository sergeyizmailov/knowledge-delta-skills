# 10 — Catalogs, Shop, and commerce reporting

Verified 2026-09-14. Read only when the offer is product commerce.

## The attribution fact that invalidates most Shop reporting plans

> TikTok, on Shop Ads: **"We do not use a product ID for attribution."**

An ad for Product A that drives a Product B purchase **counts as a conversion for that ad**. There is
**no SKU-level ROAS for Shop or GMV Max campaigns**, at all. Not "hard to get" — not available.

SKU-level reporting exists only on the **non-Shop path**: the Catalog Product Performance report,
with Product ID / SKU ID dimensions, against an external-store catalog. That is a separate reporting
system from Shop Ads attribution.

Settle this at intake. A client expecting per-product ROAS from TikTok Shop ads is expecting
something the platform does not produce, and finding out in week three is a credibility problem.

## Catalog types are mutually exclusive

TikTok maintains at least five catalog types — **E-commerce, Generic/services, O2O, Travel,
Automotive, Mini Drama** — and **a catalog cannot cross types.** Picking wrong means rebuilding, not
editing. **O2O is gated behind an account manager**, not self-serve.

Endpoints: `catalog_create` · `catalog_update` · `catalog_delete` · `catalog_product_upload` ·
`catalog_product_file_upload` · `catalog_product_update` · `catalog_product_delete` ·
`catalog_feed_create` / `_update` / `_log_get` / `_switch_update` · `catalog_set_*` (product sets) ·
`catalog_eventsource_bind` / `_unbind` · `diagnostic_catalog_*` · `catalog_available_country_get` ·
`catalog_location_currency_get`.

Both `/catalog/product/upload/` and `/catalog/product/file/` exist — the first for direct product
payloads, the second for file-based upload. Rate limits differ (`tiktok-ops/02`).

## Feed quality

The feed field set is roughly 9 required and 27 optional. **GTIN is nominally optional but TikTok's
own product diagnostics flags its absence** — it functions as a de facto quality signal, not a true
optional field. Supply it where you have it.

Run `diagnostic_catalog_product_task_create` → `_get` after a feed load. Product-level statuses and
rejection reasons live there, and catalog product policy is **not** the same as ad policy — a product
can be catalog-rejected while an equivalent ad passes.

## `content_id` matching — a silent quality problem, not an error

Catalog product IDs must match the `content_id` / `content_ids` your pixel and Events API send. A
mismatch **does not reject events**. It degrades dynamic personalisation and produces a low "catalog
match rate".

TikTok recommends **>90%** match rate. The usual causes are multi-catalog or multi-country binding —
the same SKU living under different IDs in different catalogs.

Check the match rate explicitly; nothing will tell you it is bad. Parameter naming traps (`content_ids`
plural at the pixel level, singular inside `contents[]`) are in `07`.

## Ad products, and the names that no longer exist

Current: **Video Shopping Ads (VSA)** and **Catalog Ads** / Smart+ Catalog Ads, under the
`PRODUCT_SALES` objective (or the Sales virtual objective) with `campaign_product_source` of `CATALOG`
or `STORE`.

**Retired names still circulating:** "Dynamic Showcase Ads" (DSA) is not a current TikTok term;
"Collection Ads" are deprecated and cannot be created; **Catalog Listing Ads were folded into Video
Shopping Ads in January 2023**; Product Shopping Ads are to be deprecated. Material using these names
is stale, and a plan built on them will not survive contact with the API.

**There is no Store Traffic objective on TikTok.** Confirmed by absence from the objective enum. The
nearest analogue is O2O catalog, which is App-Promotion-only and aimed at delivery and ride-hailing —
not brick-and-mortar footfall.

## TikTok Shop and GMV Max

Shop availability, Shop Ads availability and Product Shopping Ads availability are **three different
GEO lists** and are routinely conflated: Shop Ads reported in ~15 markets, Product Shopping Ads in
~8, Seller Center registration in ~24 (the last practitioner-sourced). Check the specific surface you
need, not "is TikTok Shop live here".

**GMV Max is effectively mandatory for TikTok Shop sales campaigns.** Since July 2025, Video /
Product / LIVE Shopping Ads can no longer be manually created against a Shop destination — only
against Showcase (non-Shop) or a Shop-less identity. If the offer is a TikTok Shop, GMV Max is the
path, not an option.

Its exclusivity rules are in `03` and they matter more than its performance claims: one ad account
authorized per Shop at a time, re-authorizing **auto-pauses** the previous account's GMV Max
campaigns, and a shop-wide Product GMV Max **auto-pauses conflicting legacy shopping ads regardless
of which ad account created them**. In a multi-buyer setup this is how one person silently kills
another's campaigns.

**Target ROI mode behaves like a cost cap**: it will not spend the full budget unless it can roughly
hit the target. **Low budget utilization means the target is too high, not that delivery is broken.**
People misdiagnose this constantly. Max Delivery is a separate add-on with its own budget, minimum
$10/day.

Shop campaign budget minimums are lower: **10 base units** at both campaign and ad-group level for
`PRODUCT_SALES` + `STORE`, against 50/20 for standard (`05`).

## Platform integrations

Shopify (official app, auto-installs the pixel via Shopify's Web Pixels API and can sync a catalog),
WooCommerce (official plugin), Magento, BigCommerce via Events Manager → Partner Platform.

These auto-configure pixel and events — which is convenient and also means **you did not choose the
event names or parameters**. Verify what actually fires (`07`) rather than trusting the integration;
a plugin firing `CompletePayment` with no `content_ids` will look installed and match nothing.

Google Merchant Center feed reuse: not confirmed as supported. Do not promise it.

## Commerce checklist

1. Catalog **type** correct for the offer — it cannot be changed later.
2. Feed loaded, diagnostics run, product-level rejections cleared.
3. GTIN supplied where available.
4. **Catalog match rate >90%** — `content_id` values agree with what the pixel sends.
5. Shop offer → GMV Max is the path; confirm who holds the Shop's ad-account authorization **before**
   anyone launches.
6. SKU-level ROAS expectation corrected at intake if this is Shop or GMV Max.
7. Budget minimums use the Shop floor (10 base) where `campaign_product_source` is `STORE`.
