# 05 — Merchant API v1: operating facts and `gmcops`

Reviewed 2026-09-02, primary reference pages (raw HTML) unless marked. Content API for Shopping gone
(2026-08-18, errors escalate from 2026-09-01); v1beta gone 2026-02-28. Base
`https://merchantapi.googleapis.com/{sub-api}/v1/…`. CLI: `google-grey-ops/scripts/gmcops.py` (usage
table in `google-grey-ops/10`).

## Facts that change what you build

| Topic | Fact |
|---|---|
| Auth | OAuth scope is still `https://www.googleapis.com/auth/content`. Service accounts work for the MC account they are added to as a user; other merchants' accounts need their OAuth consent or `accounts.users` add |
| Aggregate views | **None.** `accounts.issues.list` and MCQL reports refuse advanced-account (parent) aggregation — enumerate `accounts.listSubaccounts`, call per sub-account. Quota is charged to whichever account you authenticate as |
| Product key | `contentLanguage~feedLabel~offerId` (3 segments; v1beta had 4 with a leading channel); legacy local products `local~…`. Base64url-encode the segment when it contains `/` |
| Write vs read | `productInputs` (insert/patch/delete, `dataSource` param required, **API-type sources only**) vs `products` (processed; appears after "several minutes"). Same lang+offerId+source → insert replaces |
| `updateMask` | omitted = merge of populated fields; a masked attribute with no value = **delete that attribute**; `*` unsupported |
| Issue enums | `ItemLevelIssue.severity`: NOT_IMPACTED / DEMOTED / DISAPPROVED; `resolution` is a free string. `AccountIssue.severity`: CRITICAL (offers do not serve) / ERROR / SUGGESTION; issue ids are readable slugs (`misrepresentation-of-self-or-products-…`). Suspension has no field — it is a CRITICAL account issue |
| Bulk status | Reports `product_view` (`aggregated_reporting_context_status`, `item_issues`, `status_per_reporting_context`) — not paginated `products.list` |
| Batching | No custombatch RPC; `multipart/mixed` at `/batch/{sub-api}/v1`, max 2,000 (100 recommended), **counts N against quota** |
| Quotas | per-minute + daily, reset 12:00 UTC; product quota ≈ 2× offers, account quota ≈ sub-account cap; `quota.quotas.list`; 429 `request_rate_too_high` / `daily_limit_exceeded` |
| Data sources | any-label primary source = omit `feedLabel`+`contentLanguage` (API input only); `feedLabel` ≤20 chars `[A-Z0-9-]`, has no effect on targeting; sources do not namespace products — distinct labels or offerIds; supplemental sources/rules unsupported for advanced accounts; delete a supplemental only after unlinking it from every primary's rule |
| Account creation | `accounts.createAndConfigure`: `account{accountName, adultContent, timeZone, languageCode}`, `user[]` (singular key in v1), `service[]` = `accountManagement` (standalone) **or** `accountAggregation` (sub-account under advanced; cannot combine). Relationship auto-ESTABLISHED at creation |
| Homepage | verify (external) → `homepage:claim` (`overwrite` steals a claim and kills the other account's feeds). Errors: PERMISSION_DENIED, FAILED_PRECONDITION |
| ToS | `accounts/{a}/termsOfServiceAgreementState/MERCHANT_CENTER-{country}` → `accepted`/`required` (`retrieveForApplication` = application-data ToS, a different agreement); accept via `termsOfService:retrieveLatest?kind=MERCHANT_CENTER` + `:accept {account, regionCode}`. Whether it blocks inserts vs only serving: unknown |
| Programs | `accounts.programs` list/get/enable/disable; states NOT_ELIGIBLE / ELIGIBLE / ENABLED with `unmetRequirements[].affectedRegionCodes`; ids `shopping-ads`, `free-listings`, `product-ratings`, `checkout` |
| Shipping | `shippingSettings.insert` only — full replace, no patch |
| Ads link | must be **proposed from MC** (`accounts.services.propose`, `campaignsManagement`, provider `providers/<customerId>`); Ads accepts via `ProductLinkInvitationService.UpdateProductLinkInvitation(ACCEPTED)`; read `product_link` / `product_link_invitation` in GAQL. Legacy `MerchantCenterLinkService` is gone from v25 |
| Appeals | `issueresolution:renderaccountissues` shows actions; `:triggeraction` is **allowlist-gated** (support form) with opaque `actionContext` — no generic programmatic appeal |
| Notifications | push to your HTTPS endpoint (`notifications` sub-API), product status change + account service change; payload base64 in `message.data` |
| Clients | Python `google-shopping-merchant-{accounts,products,datasources,reports,issueresolution,inventories}` 1.4–1.8, py3.9–3.14; discovery doc exists for REST via `google-api-python-client` |
| Not in the API | US tax settings, phone/address verification, business identity documents, suspension appeal without allowlist |

## Unknowns (2026-09-02)

Exact default quota numbers · whether deleting a data source removes its processed products
(support doc says they stop serving) · ToS gating of inserts · "Merchant Center for Agencies"
(GA 2026-03/05, 1,000 linked clients) vs classic advanced account (50 sub-accounts default) — how
the caps interact · literal notification enum tokens.

## `gmcops` doctor gates → API source

| Gate | Read from |
|---|---|
| homepage claimed | `accounts.homepage.claimed` |
| business address / phone verified | `accounts.businessInfo.address`, `phoneVerificationState == VERIFIED` |
| shipping | `accounts.shippingSettings.services` non-empty |
| ToS | `termsOfServiceAgreementState/MERCHANT_CENTER-<country>`: `accepted` set, `required` empty (`retrieveForApplication` is the *application-data* ToS, not this) |
| data source for country | a `primaryProductDataSource` whose `countries` is empty or contains the target |
| US tax | **not readable** — doctor reports it as a manual check when `--country US` |
| programs / issues / link / product counts | `accounts.programs`, `accounts.issues`, `accounts.services` handshake, `product_view` |
