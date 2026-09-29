# 00 — Launch runbook (MCP-first)

Ordered path from "I have access" to "it is spending". Every other file in this skill is an exception
handler for one step here. Do not read ahead; if a step passes, move on.

Reviewed 2026-09-14.

**The default execution surface is the official TikTok MCP server.** It covers essentially every
operation you need. `ttops` is not a second way to do the same thing — it is the guard rail that MCP
does not have, and it runs **offline, with no token**, so it works even when you only have MCP.

```
0 strategy → 1 access → 2 tracking proof → 3 media → 4 spec
  → 5 ttops preflight → 6 MCP creates (DISABLED) → 7 ttops audit
  → 8 human review → 9 enable → 10 first hour → 11 daily → 12 rules
```

## 0 — Strategy gate

**Do not launch a strategy this skill invented.** `tiktok-ads/01` owns the intake, the constraints
gate and the derivation. Arrive with: objective, optimization event, structure, budgets, targeting,
creative plan, measurement window, and written stop/scale conditions.

Two blockers that must already be cleared:

- **The vertical has a path in this GEO**, and any authorization is filed and attached to *this* ad
  account (`tiktok-ads/08`). Authorization binds to a verified entity; a replacement account needs a
  new approval.
- **The payout event is defined in writing.** Not "leads" — which tracker status pays.

## 1 — Access

Connect the MCP server once (`01` has the full setup):

```bash
claude mcp add --transport http tiktok-ads \
  https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat
```

A human authorizes in a browser. **This cannot complete in a non-interactive session**, and the
authorization lasts **30 days** — put the renewal date in the project's `.notes/` now.

Then prove access with reads, each separately:

| Check | Tool |
|---|---|
| Which advertisers does this authorization actually cover | `auth_advertiser_get` |
| Account currency, timezone, status, country | `advertiser_info_get` |
| Balance — prepay stops dead at zero, no grace | `advertiser_balance_get` |
| **Pixel linked to THIS ad account** (shared to the BC is not the same) | `pixel_list_get` |
| Identity present and usable | `identity_get` |

**Write down the currency and timezone.** Both are permanent, and every budget bound and daily number
derives from them. A read that succeeds proves nothing about write permission or your role — the role
matrix is `tiktok-ads/02`, and an Operator cannot install a pixel or attach an identity.

Have a developer-app token as well? `ttops doctor` runs all of the above in one call and writes a
receipt. Not required.

## 2 — Tracking proof

Skip only for objectives with no conversion event (Reach, Video views).

**Fire one real test conversion end to end and see it in Events Manager before building anything.**
Not "the pixel is installed" — one event, through the real funnel, visible in TikTok.
`tiktok-ads/07` owns the mechanics: dedup keys on `event_source_id` + `event` + `event_id`, first
received wins for 48 hours, and a duplicate within 5 minutes has its extra PII **merged** into the
first — so send both legs immediately rather than spacing them. Hash mismatches fail silently.

Check Event Match Quality while you are there (`tool_vbo_status_check` answers the value-optimization
question directly). Below roughly 5.0, value-based optimization is restricted — which can invalidate a
strategy that assumed it.

## 3 — Media

`file_video_ad_upload` → `video_id`, then **poll `file_video_ad_info_get` until the video is ready.**
Error 40901 "transcoding in progress" is not a failure — it means you did not wait. **Media IDs are
per-advertiser**: a `video_id` from another ad account will not work here.

Specs, safe zones and the TikTok-specific rejection reasons (silent audio, letterboxing, another
platform's watermark): `tiktok-ads/06`.

## 4 — Write the spec

The spec is what makes step 5 possible. Start from `specs/example-traffic-abo.json` or
`specs/example-web-conversions-cbo.json` — **shape references, not recommended strategies.**

```json
"currency": "USD"         // the ACCOUNT's currency. A mismatch is rejected.
"special_industries": []  // explicit. Omitting it on a credit/housing offer is a violation.
"schedule_start_time"     // deliberate, in the account timezone. A past time starts NOW.
```

Unfamiliar currency? `ttops budget-check --currency IDR --level adgroup` before you write a number.

## 5 — Preflight (offline, no token)

```bash
ttops --json preflight --spec specs/mine.json \
      --currency JPY --advertiser-id 7123456789
```

This validates the spec against TikTok's real enums and per-currency budget rules, then **emits the
exact arguments for each MCP tool call, in order**, with `operation_status: "DISABLE"` already set.

It catches, before anything reaches TikTok: a `SALES` objective that does not exist · Meta bid-strategy
names · a budget below the currency floor or with illegal decimals · CBO with ad-group budgets · a
filter-only optimization goal · a missing `schedule_start_time` · an ad group whose lifetime budget
conflicts with the campaign mode.

Read the `total_daily` line. That is the number you will confirm with the operator at step 8.

## 6 — Create through MCP, everything DISABLED

Hand the emitted arguments to the tools, in order:

```
campaign_create  → campaign_id
adgroup_create   → adgroup_id     (repeat per ad group)
ad_create        → ad_ids
```

**`operation_status` defaults to `ENABLE`. MCP will not add `DISABLE` for you.** Pass it at campaign,
ad group *and* ad — preflight already put it in the arguments; do not drop it.

Concurrency: MCP allows **3 QPS per tool**, and Upgraded Smart+ ad writes are capped at **one
operation per 5 seconds per ad**. Serialize rather than fanning out.

If a create fails, read `05` or `ttops explain <code>` before retrying. **A create whose connection
dropped may still have applied** — read back before you retry, or you get duplicates.

## 7 — Audit what MCP actually created (offline, no token)

Read every object back — `campaign_get`, `adgroup_get`, `ad_get` — save the responses to a file, then:

```bash
ttops --json audit --spec specs/mine.json --actual readback.json --currency JPY
```

**A successful create is not proof the object holds what you sent.** TikTok ignores unknown keys and
fills enum defaults silently, so the only way to know is to read it back and diff it.

`audit` flags, by severity:

| | |
|---|---|
| `SPENDING` | Something is **live right now** and you did not intend it. Pause first, diagnose second |
| `MONEY` | Budget violates the currency's floor or precision |
| `BLOCKED` | Rejected, missing qualification, lost asset authorization, unbound pixel, transcoding failure |
| `DRIFT` | The platform stored something other than what you asked for |
| `MISSING` | In the spec, absent from the read-back |
| `UNCONFIRMED` | The spec set it; the read-back does not report it. Not verified either way — check the permanent ones (attribution windows, `video_download_disabled`) in Ads Manager |

Every field the spec sends is compared, at all three levels — including the ad's destination URL,
creative asset and identity, which is where the money actually points.

It works without `--spec` too — the danger checks do not need one, which is the normal case when a
campaign was built conversationally.

## 8 — Human review, while paused

The API cannot prove these. Do them with everything still paused:

- **Ad preview** on real placements (`creative_ads_preview_create`). Truncation and safe-zone
  collisions are visible nowhere else.
- **Destination URL**, clicked, in an incognito window, from the target GEO if you can
  (`tool_url_validate` catches the mechanical failures only).
- **Review status** — `ad_review_info_get`. A rejected ad cannot be enabled into life.
- **Balance** against the daily budget.
- **Identity** renders as intended, and any Spark authorization has not expired.

Then confirm with the operator, in writing: total daily spend **in major units with the currency
named**, the schedule, the destination, and the stop conditions from step 0.

## 9 — Enable, bottom-up

```
ad_status_update       → ENABLE   (ads first)
adgroup_status_update  → ENABLE
campaign_status_update → ENABLE   (campaign last)
```

Bottom-up means nothing serves until every child is deliberately on. Status updates cap at **20 IDs**
per call.

Working from a `ttops` plan with a token instead? `ttops activate --confirm-reviewed REVIEWED
--confirm SPEND` does the same ordering behind a verify receipt (`04`).

## 10 — First hour

- **Insights are empty for 15–40 minutes.** Not a delivery failure. Do not touch anything.
- Then check delivery status, spend, the tracker receiving clicks, and balance.
- No spend and no error → future `schedule_start_time`, still in review, zero balance, or an audience
  too narrow to serve. `ttops explain <secondary_status>` translates the cryptic string.
- **Any budget or billing anomaly: pause first, diagnose second.**

Re-run `ttops audit --actual readback.json --expect-live` to confirm everything that should be
serving is, and nothing else is.

## 11 — Daily

`report_integrated_get` at ad level. Rows are in the **ad account's timezone and currency** — say so
when you report them. Push spend into the tracker as cost, or CPL is fictional. Cohort on click date.
Reconcile one day by hand before trusting the pipeline.

Judge against the window written at step 0, not against how day one feels.

## 12 — Kill and scale rules

Agreed in writing before launch: spend-without-conversion cap, CPA cap, account verdict threshold.

TikTok exposes **automated rules through the API** (`optimizer_rule_create` and friends) — not a
UI-only feature. One caveat before building on them: rule notifications route to the developer app's
own email, which breaks per-advertiser isolation for multi-client operators (`06`).

Budget changes must be **≥105% of current spend** — TikTok's one documented budget rule. Plan
reductions as pauses, not cuts.

## When a step fails

| Symptom | Go to |
|---|---|
| Any return code | `05`, or `ttops explain <code>` |
| A cryptic `secondary_status` | `ttops explain AD_STATUS_...` |
| MCP tools all failing together | Authorization expired (30 days) — `01` |
| "No permission" on an asset | `tiktok-ads/02` role matrix — a human escalation |
| Creative rejected | `tiktok-ads/08` |
| Vertical looks blocked in this GEO | `tiktok-ads/08`, then back to `tiktok-ads/01` B1 |
| Numbers disagree with the tracker | `tiktok-ads/07` |
| CPA is up and you want to know why | `tiktok-ads/09`, or the `tiktok_ads_diagnosis_agent` tool |
