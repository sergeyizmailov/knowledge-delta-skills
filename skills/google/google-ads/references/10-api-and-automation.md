# 10 — Google Ads API, Scripts, AI automation

Reviewed 2026-09-02 (service accounts, v25 fields, [R] pruning). API versions move monthly 🔺 — verify at request time. Errors →
`11-api-error-catalog.md`.

## Access

| Level | Ops/day | Scope | How | Time |
|---|---|---|---|---|
| Test account | 15,000 | Test accounts only | Automatic on signup via API Center | Instant |
| **Basic** | 15,000 | Test + production | API Center → set API Contact Email → Apply for Basic | ~5 business days |
| **Standard** | Unlimited (most services) | Unrestricted | From Basic → Apply for Standard. Requires **RMF** compliance; third-party tools must give a reviewer working demo access | ~10 business days |

**A manager account is required to obtain a developer token** — tokens are issued at MCC level, never
on a client account.

Rejection causes: incomplete Required Minimum Functionality (the reviewer cannot actually exercise
account/campaign/reporting functionality), no working demo login, unmonitored contact email, tool
description not matching what exists. **RMF applies only to Standard applications.**

### OAuth

- **Installed app (Desktop)** — supported. Refresh token is long-lived once the consent screen is in
  **Production**. In **Testing** status refresh tokens expire after **7 days** — the most common
  "it worked yesterday" bug.
- **Web application** — supported; needs a loopback redirect URI for local dev.
- **Service account — supported, no Workspace delegation needed** (verified 2026-09-02,
  `docs/oauth/service-accounts`): create a GCP service account + JSON key, then in Google Ads
  **Admin → Access and security → Users → +** add the service-account email like a human user
  (admin rights need a separate upgrade step; ≤20 accounts per email — link under an MCC beyond
  that). Config: `json_key_file_path` in `google-ads.yaml` / `GOOGLE_ADS_JSON_KEY_FILE_PATH`.
  Headless, no 7-day refresh-token death. Older docs (and most tutorials) said "unsupported" or
  "domain-wide delegation only" — both stale. Grey overlay: the SA is a GCP-project identity tied
  to a billing account; treat it as a linking signal (`google-grey-ops/01`). Data Manager API
  (`auth/datamanager`) takes a service account too — see `tracker-ops/04`.

Revocation triggers: user revokes app access · password change (some configs) · OAuth client deleted
or regenerated · 6 months unused · consent screen falling out of Production.

### `login-customer-id`

Required whenever you reach an operating account **through** a manager account. Not required when the
authenticated user has direct access. Value is the **manager account ID without hyphens**, normally
the topmost MCC — the first ID returned by `CustomerService.ListAccessibleCustomers`.

```python
client = GoogleAdsClient.load_from_storage("google-ads.yaml")
client.login_customer_id = "1234567890"   # MCC id, no dashes
```

**Getting this wrong is the most common cause of `USER_PERMISSION_DENIED` and `CUSTOMER_NOT_ENABLED`
on otherwise-valid requests.**

A developer token issued under MCC-A cannot query an account not linked into MCC-A's hierarchy, even if
the OAuth user personally has UI access elsewhere. **The API path and the human login path are separate
access checks.**

## Versions

As of 2026-08-27: **v25** latest, released **2026-07-22**; v25.1 minor **2026-08-19**. Monthly cadence
since Jan 2026, **4 majors/year**, each supported ~1 year. v20 sunset 2026-06-10; v21 sunset
2026-08-05. Cross-check `developers.google.com/google-ads/api/docs/sunset-dates` before pinning.

There is no "get current version" RPC. **Pin the client library version** and treat currency as a
dependency-upgrade problem, not a runtime query.

**Recent breaking changes worth knowing:**

- **v25** — removed `CustomerLifecycleGoal`/`CampaignLifecycleGoal` (unified goals schema);
  `customer_metrics` changed from generic `Metrics` to specialized `CustomerMetrics`, **which breaks
  code assuming the generic shape**; planning `search_brand` → `search_topics`;
  `plannable_location_id` → `plannable_location_ids`.
- **v24** — `videos` and `logo_images` became **mandatory** on `DemandGenVideoResponsiveAdInfo` and
  `VideoResponsiveAdInfo` (previously-working ad creation now fails `FieldError.REQUIRED`);
  campaign-level suitability controls removed, now customer-level; `ShareablePreviewService` no longer
  allows partial failure — one bad ID fails the whole request.
- **v23** — removed aggregate asset performance-label metrics for Search/Display (v22 had already
  removed them for PMax).

> **Silent migration trap:** minor versions are additive, major versions remove fields. A script
> hardcoded to a minor version's field set can start returning **200 OK with silently missing data**
> after a forced major bump rather than throwing. **Add field-presence assertions to report parsing,
> not just error handling.**

## GAQL

Non-obvious limits only: `IN` caps at **20,000** items; `DURING` takes the fixed literals
(`LAST_7_DAYS`, `LAST_WEEK_MON_SUN`, `THIS_WEEK_MON_TODAY`, …) — arbitrary ranges use `BETWEEN`.

**Not general SQL.** One resource in `FROM` fixes the row grain. You may select fields from
*attributed* resources (`campaign.name` when `FROM ad_group`) but cannot join two independent
resources. Compatibility is governed by each field's `selectableWith`, discoverable via
`GoogleAdsFieldService`; incompatible pairs are rejected at parse time.

### The segmentation trap — the single most common GAQL bug

- **Attributes** describe the entity — one value per row.
- **Metrics** are aggregates.
- **Segments** *split* metrics and **multiply row count**.

`SELECT campaign.id, metrics.clicks FROM campaign WHERE segments.date DURING LAST_30_DAYS` returns
**one row per campaign per day**, not one per campaign. Client-side `SUM()` without grouping produces
silently wrong totals; code expecting one row per campaign gets 30 and either double-counts or
crashes.

**Zero-impression rows** are generally omitted from metrics-joined queries. To enumerate full
inventory regardless of activity, query the **entity resource with no metrics fields** (e.g.
`FROM campaign WHERE campaign.status != 'REMOVED'`), then join in your own code on `resource_name`.

**`SearchStream` vs `Search`:** SearchStream needs no pagination, is faster for large sets, and counts
once against quota. **Default to it for reporting.** Use `Search` only when you need fixed-size pages
or the REST binding.

`search_stream` for reports; field compatibility via `GoogleAdsFieldService` (`SELECT name,
selectable_with FROM google_ads_field WHERE name = '…'`).

### Query library

Campaign / ad group / keyword performance, conversion-action stats, budget + Lost-IS, geo, and
hourly queries are cookbook-standard — write them from the schema (`GoogleAdsFieldService`) or the
official Query Cookbook; they are not reproduced here. What remains is the non-obvious set. Queries
not verbatim from the Cookbook are **dry-read with `LIMIT 1` before relying on them.**

```sql
-- 1. Search terms (feeds negative mining)
SELECT search_term_view.search_term, segments.keyword.info.match_type,
  search_term_view.status, campaign.name, ad_group.name,
  metrics.clicks, metrics.impressions, metrics.ctr, metrics.average_cpc, metrics.cost_micros,
  campaign.advertising_channel_type
FROM search_term_view
WHERE segments.date DURING LAST_7_DAYS

-- 2. RSA asset-level detail
SELECT asset.id, asset.type, ad_group_ad_asset_view.field_type,
  ad_group_ad_asset_view.performance_label, metrics.impressions, metrics.clicks
FROM ad_group_ad_asset_view
WHERE segments.date DURING LAST_30_DAYS

-- 3. PMax asset group performance
SELECT asset_group.id, asset_group.name, campaign.name,
  metrics.clicks, metrics.impressions, metrics.cost_micros, metrics.conversions
FROM asset_group
WHERE segments.date DURING LAST_30_DAYS

-- 4. PMax listing group filters
SELECT asset_group_listing_group_filter.asset_group,
  asset_group_listing_group_filter.type,
  asset_group_listing_group_filter.case_value,
  asset_group_listing_group_filter.parent_listing_group_filter
FROM asset_group_listing_group_filter
WHERE asset_group.campaign = 'customers/1234567890/campaigns/111'

-- 5. Change history — the forensic query after an unexplained performance drop
SELECT change_event.change_date_time, change_event.change_resource_type,
  change_event.client_type, change_event.user_email, change_event.old_resource,
  change_event.new_resource, change_event.resource_change_operation
FROM change_event
WHERE change_event.change_date_time DURING LAST_14_DAYS
  AND change_event.change_resource_type IN
    ('CAMPAIGN','AD_GROUP','AD_GROUP_AD','AD_GROUP_CRITERION','CAMPAIGN_BUDGET')
ORDER BY change_event.change_date_time DESC
LIMIT 1000

-- 6. Account hierarchy under an MCC
SELECT customer_client.id, customer_client.descriptive_name, customer_client.level,
  customer_client.manager, customer_client.status, customer_client.currency_code,
  customer_client.time_zone
FROM customer_client
WHERE customer_client.status = 'ENABLED'

-- 7. Negative-keyword conflict audit (`03` — "Negatives always win"). GAQL cannot join:
--    pull both sides, diff in code. The match test is LITERAL (negatives get no close
--    variants): negative exact == keyword string; negative phrase = contiguous substring
--    of the keyword; negative broad = every negative token present in the keyword.
SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type
FROM ad_group_criterion
WHERE ad_group_criterion.negative = TRUE
  AND campaign.status != 'REMOVED' AND ad_group.status != 'REMOVED'

-- 7b. Campaign-level negatives
SELECT campaign.name, campaign_criterion.keyword.text, campaign_criterion.keyword.match_type
FROM campaign_criterion
WHERE campaign_criterion.negative = TRUE
  AND campaign_criterion.keyword.text IS NOT NULL

-- 7c. Account-level negatives (1,000 cap) — these reach PMax and are invisible in
--     campaign-level views
SELECT customer_negative_criterion.keyword.text, customer_negative_criterion.keyword.match_type
FROM customer_negative_criterion

-- 7d. Traffic-bearing actives to diff against
SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
  campaign.name, ad_group.name, metrics.clicks
FROM keyword_view
WHERE segments.date DURING LAST_30_DAYS AND metrics.clicks > 0
```

## Mutates — building a campaign atomically

One `GoogleAdsService.Mutate` accepts a repeated `MutateOperation` list spanning different resource
types in **one atomic request** — all succeed or all fail.

**Temporary resource IDs:** use a **negative integer** in the resource_name
(`customers/123/campaigns/-1`). Each must be **unique within the request across all resource types**.
A temp ID can only be referenced **after** the operation defining it — order matters. **Temp IDs do
not survive across separate calls.**

Worked graph (budget → campaign → ad group → keywords → RSA, all PAUSED, partners/content off)
is encoded in `google-grey-ops/scripts/gads_build.py`; run `googleops plan` instead of retyping it.

### `validate_only` — the zero-spend write probe

Full server-side validation (field, policy, criterion errors) **without persisting anything or
spending**. This is the correct guardrail for an agent: build the graph, run with `validate_only=True`,
fix errors, then re-run for real. Validation requests still consume operation quota.

```python
request = client.get_type("MutateGoogleAdsRequest")
request.customer_id = cid
request.mutate_operations = ops
request.validate_only = True
client.get_service("GoogleAdsService").mutate(request=request)
# no exception => graph is valid
```

### `partial_failure`

**Never combine with cross-operation temp-ID references.** If an earlier operation defining a temp ID
fails, partial failure leaves dangling references. Google's guidance: partial failure for
**independent** operations only; plain atomic mutate for interdependent graphs like a campaign build.

```python
if response.partial_failure_error and response.partial_failure_error.details:
    for detail in response.partial_failure_error.details:
        failure = type(client.get_type("GoogleAdsFailure")).deserialize(detail.value)
        for error in failure.errors:
            idx = error.location.field_path_elements[0].index
            print(f"op {idx}: {error.error_code} — {error.message}")
```

### PMax object graph

```
CampaignBudget (-1)                       # non-shared, DAILY period — mandatory for PMax
  └─ Campaign (-2, advertising_channel_type=PERFORMANCE_MAX, e.g. maximize_conversion_value.target_roas)
       ├─ CampaignCriterion (location, language)
       └─ AssetGroup (-3, campaign=-2)
            ├─ Asset (-4, -5, … TEXT/IMAGE/VIDEO/LOGO, created inline)
            ├─ AssetGroupAsset (field_type: HEADLINE / DESCRIPTION / MARKETING_IMAGE / LOGO / …)
            ├─ AssetGroupSignal (audience.audience resource_name, or search_theme.text)
            └─ AssetGroupListingGroupFilter (retail only — UNIT_INCLUDED / SUBDIVISION tree)
```

**Non-retail PMax asset groups and their assets must be created in a single bulk mutate** to satisfy
minimum-asset requirements. A partial creation not meeting minimums is rejected outright.

v25 field facts that break old code (verified against the installed client 2026-09-02):
`campaign.url_expansion_opt_out` **no longer exists** — final URL expansion is
`campaign.asset_automation_settings[]` with `asset_automation_type =
FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION` and status `OPTED_OUT`/`OPTED_IN`; brand exclusion is a
negative `campaign_criterion.brand_list.shared_set`; `contains_eu_political_advertising` is a
required campaign field; `asset_operation`s must precede `asset_group_asset_operation`s in the same
request and text assets are created in a **prior** request; retail listing-group root is
`type=UNIT_INCLUDED, listing_source=SHOPPING`; Standard Shopping ad groups are `SHOPPING_PRODUCT_ADS`
with an empty `ShoppingProductAdInfo`. **Merchant Center linking:** `ProductLinkService` /
`ProductLinkInvitationService` (`product_link`, `product_link_invitation` in GAQL); the
`merchant_center_link` resource and `MerchantCenterLinkService` are gone — the link must be
proposed from Merchant Center, Ads only accepts. All of this is encoded in
`google-grey-ops/scripts/gads_build.py`; prefer `googleops` over rewriting it.

```python
# audience signal
op = client.get_type("MutateOperation")
s = op.asset_group_signal_operation.create
s.asset_group = client.get_service("AssetGroupService").asset_group_path(cid, "-3")
s.audience.audience = f"customers/{cid}/audiences/{audience_id}"
ops.append(op)

# search theme signal
op = client.get_type("MutateOperation")
t = op.asset_group_signal_operation.create
t.asset_group = client.get_service("AssetGroupService").asset_group_path(cid, "-3")
t.search_theme.text = "trail running shoes"
ops.append(op)
```

## Mass launch

**`BatchJobService`** — create job → add operations (paged via `sequence_token`) → run (returns an
LRO) → poll → list results.

| Constraint | Value |
|---|---|
| Recommended ops per `AddBatchJobOperations` | ≤1,000 |
| Hard cap per add call | 10,000 |
| Max ops per job | ~1,000,000 |
| Concurrent active jobs per account | 100 |
| Max single operation payload | ~10.48 MB |

**Order operations by type** (all campaigns, then all ad groups, then criteria, then ads) rather than
interleaved — it reduces server-side dependency resolution. Fewer, larger jobs beat many small ones.

**Google Ads Editor bulk CSV** is the right tool when a human must review thousands of rows in a
spreadsheet first, for one-off migrations, or before API access is approved. **The API wins** when the
launch is triggered programmatically, when you need `validate_only` safety, or when you need atomicity
across entities — Editor's CSV has no equivalent to a single atomic `Mutate`.

### Quotas

| Constraint | Value | Error |
|---|---|---|
| Basic access daily ops | 15,000 | `RESOURCE_EXHAUSTED` |
| Mutate ops per request | 10,000 | `TOO_MANY_MUTATE_OPERATIONS` |
| "Action" ops per request | 100 | `TOO_MANY_ACTION_OPERATIONS` |
| Conversions per upload | 2,000 | `TOO_MANY_CONVERSIONS_IN_REQUEST` |
| Adjustments per request | 2,000 | `TOO_MANY_ADJUSTMENTS_IN_REQUEST` |
| gRPC max response | 64 MB | `RESOURCE_EXHAUSTED` |
| Keyword Planning ideas/forecast | 1 QPS | throttled |
| Audience Insights | ~200 req/day | throttled |
| UserData identifiers per object | 20 | `RequestError` |
| Offline user-data job identifiers | 100,000 | `RequestError` |

Paginated page fetches and network failures do not count against daily quota; **a failed request that
returns a `GoogleAdsFailure` does count.** Throttle with a token bucket per developer token; back off
exponentially on `RESOURCE_EXHAUSTED` rather than hot-looping.

## Offline conversion upload

```python
cc = client.get_type("ClickConversion")
cc.conversion_action = conversion_action_resource_name
cc.conversion_date_time = "2026-08-27 14:30:00-05:00"   # timezone offset REQUIRED
cc.conversion_value = 99.99
cc.currency_code = "USD"
cc.order_id = "order_123"
cc.gclid = "Cj0KCQiA..."                                 # or gbraid / wbraid

req = client.get_type("UploadClickConversionsRequest")
req.customer_id = cid
req.conversions = [cc]
req.partial_failure = True
req.job_id = 123456                                      # optional, for diagnostics
client.get_service("ConversionUploadService").upload_click_conversions(request=req)
```

**Adjustments** (`ConversionAdjustmentUploadService`): `RESTATEMENT` corrects value/date (refund) ·
`RETRACTION` invalidates a conversion (fraud, duplicate) · `ENHANCEMENT` adds user-identifying data
without changing value or date.

Hash rule for enhanced conversions: lowercase, trim whitespace, **gmail.com/googlemail.com: remove
dots in the local part**, then SHA-256 hex. Phone numbers E.164 before hashing.

Failure enums: `INVALID_EMAIL` · `INVALID_PHONE_NUMBER` (not E.164) · `MISSING_CONVERSION_ACTION` ·
`CONVERSION_ALREADY_EXISTS` · `INVALID_CONVERSION_DATE_TIME` (missing offset) ·
`TOO_RECENT_CONVERSION_ACTION` (uploaded before the action finished propagating) ·
`CLICK_CONVERSION_ALREADY_EXISTS`.

**Windows, dedup rules, and the 2026-06-15 new-adopter cutoff** → `06-tracking-attribution.md`.
New tokens that cannot onboard classic OCI: Data Manager `events:ingest` → `tracker-ops/04`.

## Google Ads Scripts

| | Scripts | API |
|---|---|---|
| Auth | None — runs as the account | OAuth2 + developer token |
| Scheduling | Built-in | You own it |
| Runtime | **30 min** (60 for MCC with `executeInParallel`) | Uncapped |
| Reach | One account, or MCC fan-out | Anything you have access to |
| Best for | In-account monitoring, alerting, pacing with no external infra | Bulk launches, cross-account pipelines, LLM mutate flows |

**Changes made before a timeout are still applied — not rolled back.** Iterator limit 50,000 results;
10,000 IDs per selector.

`AdsApp.report()` with GAQL replaced AWQL in 2020 and is **materially faster than object-selector
iterators** for read-heavy work.

```javascript
var report = AdsApp.report(`
  SELECT campaign.name, metrics.clicks, metrics.cost_micros
  FROM campaign WHERE segments.date DURING LAST_7_DAYS`);
var rows = report.rows();
while (rows.hasNext()) { var row = rows.next(); Logger.log(row['campaign.name']); }
```

**Public scripts worth knowing:** n-gram (Brainlabs lineage, maintained by Nils Rooijmans) · budget
pacing · anomaly detection · **Mike Rhodes' PMax Insights script** (the most thorough public PMax
visibility solution — see `07`) · disapproval alerting · broken-URL checker · **Quality Score tracker**
(Google retains no QS history natively, so logging it daily to a Sheet is the only way to have it).

## AI-assisted pipelines

**The load-bearing pattern:** an LLM produces a **structured JSON campaign spec** validated against a
schema; a **deterministic code layer** translates it into `MutateOperation` objects; **the LLM never
emits API calls directly.** Then `validate_only=True`, then real mutate with statuses forced
`PAUSED`, then human approval to enable.

### Guardrails — apply all five

1. `validate_only=true` first, always, on any new mutate shape.
2. Force `status = PAUSED` on every newly created campaign, ad group, and ad. Nothing spends until an
   explicit separate enable step.
3. **Hard budget caps enforced in your own code** — reject any spec whose `amount_micros` exceeds a
   configured ceiling. Never trust the model's number without a deterministic check.
4. Human approval gate between spec and real mutate, except for narrowly-scoped pre-approved recurring
   actions (routine negatives under an agreed threshold).
5. Log every mutate's `request_id` and full payload. This is also what Google support will ask for.

**Official Google Ads MCP server** (`github.com/googleads/google-ads-mcp`, shipped 2026-04-28) 🔺 —
tools: `list_accessible_customers`, `search` (arbitrary GAQL), `get_resource_metadata`. **Strictly
read-only at release** — it cannot modify bids, pause campaigns, or create assets. Treat any claim of
a write-capable Google Ads MCP as unverified. Auth via developer token + GCP project + OAuth or ADC;
runs over stdio, deployable locally or on Cloud Run. Third-party servers exist (e.g. GoMarble's) —
evaluate write capability and data handling before granting live account access.

**Google Ads API Developer Assistant v4.0.0** (2026-08-26) — Google's own API tooling restructured
as a plugin for AI coding workflows (explicitly including Claude Code): GAQL validation against the
live schema before execution, schema/field discovery scoped to the active API version, natural-
language reporting. Prefer it over hand-writing GAQL from training-data memory of an old API version
when available. [trade press 2026-08-26, single source — verify install path]

**n8n** ships a native Google Ads node and is self-hostable, so there is no per-execution pricing
ceiling for high-frequency pipelines. Zapier/Make cover simple trigger→action flows (new lead →
upload offline conversion) but require a custom HTTP step for anything resembling a full campaign
graph. **No no-code connector matches direct API access for atomic multi-entity creation.**

**The two most-automated workflows in 2025–26:** search-term → LLM → themed negative list → mutate
(query 1 above, with "propose negatives only for terms with N+ clicks and 0 conversions"); and RSA
generation from landing-page content plus existing `performance_label = BEST` assets, created PAUSED.

## Reporting infrastructure

**BigQuery Data Transfer Service** — fixed, non-customizable schemas; you get the full predefined
table set, no field selection. Default **7-day refresh window** per run (to catch late conversions),
configurable to 30. Data is date-partitioned and re-running **overwrites that date's partition**
without duplicating.

**Daily spend sync pattern:** scheduled job runs query 1 with `segments.date DURING YESTERDAY` via
`SearchStream`, upserts keyed on `(campaign.id, segments.date)`, plus a periodic **7-day backfill
re-pull** to absorb Google's own attribution adjustments — the same reason DTS defaults to 7 days.
Building it yourself gives field-level control DTS's fixed schema does not. Tracker side →
`tracker-ops`.
