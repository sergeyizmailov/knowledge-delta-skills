# 06 — Monitoring, automated rules, webhooks, reporting at scale

Verified 2026-09-14 against TikTok's docs portal and the MCP tool inventory.

## Reporting

`/report/integrated/get/` — synchronous. Parameters that decide whether it works:

| Field | Notes |
|---|---|
| `report_type` | `BASIC`, `AUDIENCE`, `PLAYABLE_MATERIAL`, `CATALOG` |
| `data_level` | `AUCTION_ADVERTISER` / `AUCTION_CAMPAIGN` / `AUCTION_ADGROUP` / `AUCTION_AD` |
| `dimensions` | the ID dimension for the level, plus optional `stat_time_day` for a time series |
| `metrics` | ask for what you will use. A wide list is the usual cause of 40002 |
| `filtering` | ID lists, primary status. Default filter excludes deleted objects |

Facts that change how you read the output:

- **Rows are in the ad account's own timezone and currency.** Two accounts in one portfolio disagree
  about "yesterday". Always state the timezone next to a daily number.
- **Attribution window is not a report parameter.** It is fixed on the ad group at creation and
  cannot be changed afterwards. You cannot re-run a report "at 7-day click" — you can only compare
  ad groups that were built with different windows.
- **Sync reports silently truncate at ~20,000 ads.** A smaller-than-expected result set is not
  evidence of zero matches. Watch for the `x-tt-ads-throttle` response header.
- Data is not real-time. Fresh campaigns show nothing for 15–40 minutes.

**Async reports** (`/report/task/create/` → `/report/task/check/` → `/report/task/download/`) are
**allowlist-only** — you apply through the Allowlist Management page. Do not design a pipeline that
assumes they work; confirm first. The rate limit is 2 QPS / 60 QPM / **4,500 QPD at every level**,
which is the real ceiling on a large portfolio.

TikTok's own guidance: **the Reporting API is not meant to drive automation.** Polling reports to
decide kills and scales is the pattern they tell you to replace with Automated Rules.

## Automated Rules — real, API-exposed, with one disqualifying caveat

Contrary to a claim repeated widely (ported from Meta), TikTok exposes rules through the API:

```
/optimizer/rule/create/      /optimizer/rule/update/       /optimizer/rule/get/
/optimizer/rule/list/        /optimizer/rule/batch_bind/   /optimizer/rule/result/list/
/optimizer/rule/update/status/
```

Conditions, actions, scope and evaluation are all in the schema. MCP wraps these as
`optimizer_rule_*`.

**The caveat that decides whether you can use them:** rule notifications route to the **developer
app's own email**, not per-advertiser. For anyone operating several clients through one app this
breaks tenant isolation, and it is why agency tooling often keeps rules in the UI per account
instead. Decide this before building on rules, not after.

Rule design that survives small samples is platform-independent: gate every rule on a minimum spend
or conversion count before it can fire, and agree kill/scale thresholds in writing before launch. A
naive "CPA > target → pause" rule with no gate kills winners on day one, before the sample means
anything.

## Webhooks — TikTok has them

`/subscription/subscribe/`, `/subscription/get/`, `/subscription/unsubscribe/`. You register a
`callback_url` and TikTok POSTs events.

| Entity | Covers |
|---|---|
| Ad / ad group review status | Rejections and approvals — the highest-value subscription |
| Account suspension | **Allowlist / rep-gated** |
| Leads | Instant Form submissions in real time |
| Creative fatigue | Fatigue signals |
| `REPORT_DATA_CHANGE` | **Allowlist / rep-gated** |
| API incidents | Platform-side problems |

Three operational facts:

1. **Delivery is at-least-once.** Handlers must be idempotent — dedupe on the event's own ID.
2. **A revoked token stops delivery silently.** There is no "your subscription died" event. Treat
   prolonged silence as suspicious, not as calm, and heartbeat the subscription.
3. **There is no campaign-paused webhook.** A campaign auto-paused for budget or delivery reasons
   still requires polling. `ttops sweep` covers this gap.

## What to monitor, and how each is detected

| Condition | Detection |
|---|---|
| Ad rejected | Webhook (review status), or `ttops review` / `/ad/review_info/` |
| Account suspended | Webhook if allowlisted; otherwise `advertiser/info/` status in `ttops doctor` |
| Token dead | Any call returning 40105/40106. Fails as a *group* — check auth before chasing individual endpoints |
| MCP authorization expired | Tools fail together after ~30 days. Check the authorization date first (`01`) |
| Balance at zero | `/advertiser/balance/get/` in `doctor`. Prepay stops dead, no grace |
| Delivering but not converting | `ttops sweep` → `STALL` (impressions, zero clicks) |
| Live but not delivering | `ttops sweep` → `NO_DELIVERY`. Normal for 15–40 min after activation |
| Budget anomaly | Compare report `spend` against the plan's `total_daily`. **Pause first, diagnose second** |

## Custom audiences at scale

`dmp_custom_audience_*`. Limits that break naive sync jobs:

- **24 update operations per audience per 24 hours.**
- **One file-based REPLACE per day.**
- Processing can take up to **48 hours** — an audience is not usable the moment you upload it.
- An audience with a size of 0 (fewer than ~1,000 matches) is not editable and raises 40002.

Lookalikes: source audience minimum is **100** (not the 1,000 repeated in blogs — that figure is the
ad-group *usage* minimum), and lookalike creation is geo-gated to a subset of markets. Verify the
target GEO is on the list before designing around them.

## Split testing

`/split_test/create/`, `/split_test/update/`, `/split_test/result/get/`, `/split_test/end/`,
`/split_test/promote/`. A real platform A/B facility — prefer it to hand-rolled duplicate-and-compare
when the question is genuinely one variable, because it handles the split server-side.

Whether the difference it reports is real is a separate question — check the result's sample size
and confidence before acting on a declared winner; a split test can call one before the difference
is statistically meaningful.

## The no-code layer — mostly read-only

Verify before promising a client an integration:

- **Zapier**: lead-gen triggers only, not campaign management.
- **Airbyte / Fivetran / Supermetrics / Windsor.ai**: read-only ETL.
- **n8n**: no native TikTok Ads node.
- **Make.com**: the only real write path is a generic API-call module, not first-class actions.
- **Revealbot** rebranded to **Bïrch** — stale references to the old name are a dead brand.

Meta-parity is a bad assumption here. Several vendors that manage Meta campaigns only *read* TikTok.
