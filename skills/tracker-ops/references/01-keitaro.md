# 01 — Keitaro API

Base `https://TRACKER/admin_api/v1/`. Auth header `Api-Key: <key>` (also accepts
`Authorization: Bearer <key>`). Ref: admin-api.docs.keitaro.io (openapi.json).
Key: Account → API keys → Create (elevated tier; write-once — can't be edited,
only recreated).

## Reports: POST /report/build

Body: `{range:{from,to,timezone | interval}, dimensions:[], measures:[],
filters:[{name,operator,expression?}], sort:[{name,order}]}`. Always pass the
account tz.

- interval (9 tokens): today, yesterday, 7_days_ago, first_day_of_this_week,
  1_month_ago, first_day_of_this_month, 1_year_ago, first_day_of_this_year,
  all_time.
- `cpl` metric: version-dependent (not always in openapi.json). Production-
  verified = cost/leads exactly (170.95/9 = 18.9944). `leads` drops regs that
  already flipped to sale (below), so `cpl` overstates cost/reg once deps land —
  use it only if payout = status lead and nothing flips; else compute CPL =
  cost / (count of your payout status; reg payout = leads + sales). `cpa`/`cps` count
  acquisitions/sales, not necessarily your payout event.
- NO `domain` dimension — use `source`/`referrer`.
- sub_id range is `sub_id_1..30` (not 15). Also `extra_param_1..10`.
- Cloak-condition shape "Sub ID N not empty" where sub_id_N is the campaign's
  mapped param for `fbclid`: real ad clicks carry a genuine Meta-appended
  `fbclid` — never place it in the tracking URL or hand-add `&sub_id_N=...`;
  either satisfies the condition with junk and disables the bot filter
  entirely.
- `ad_campaign_id` = mappable source parameter, carries whatever token the
  campaign URL feeds it (id OR name) — NOT intrinsically utm_campaign, and
  distinct from Keitaro's internal `campaign_id`. `creative_id` = source
  creative id (may be banner/adset id), `external_id` = source click id.
  Per-account splitting by "campaign name" works only if your campaign URL
  actually maps the FB campaign name into this param (mapping contract, 03).
- Split by status via count metrics leads/sales/rejected (+ revenue variants,
  or flags is_lead/is_sale/is_rejected). `status` itself is a column only in
  conversion-scoped reports.
- One conversion per click changes status in place (lead → sale), so `leads`
  = regs that have NOT converted yet, not all regs. Reg→dep funnel: regs =
  leads + sales (= `conversions` when no tid repeats/rejects), deps = sales.
  Using `leads` as the reg count overstates reg→dep (FIELD 2026-09-27: 11 vs 17).
- `revenue` includes lead_revenue: if the network postback sends payout on
  `lead`, revenue/ROI is fake (FIELD 2026-09-27: $9,820 vs $1,650 real).
  Money = `sale_revenue`; check lead_revenue = 0.
- `range` without `interval` needs explicit `from`/`to` ("YYYY-MM-DD HH:MM");
  tokens like `last_30_days` are rejected (FIELD 2026-09-27).
- `sale_cr` is not a valid measure (errors); use `crs` (FIELD 2026-09-27).
- If a name errors, response lists valid columns. Fallback: build in UI →
  DevTools → Network → /report/build → copy payload.

## Cost push: POST /clicks/update_costs

Prefer per-entry (openapi `ClicksUpdateCostsPayload` requires timezone +
currency per entry; production-verified). Top-level `timezone`+`currency` also
works (FIELD 2026-09-27: `{"success":true}` with `only_campaign_uniques:false`,
filter `sub_id_1:"<FB campaign name>"` — use whichever param your URL maps).
`{campaign_ids:[ID], only_campaign_uniques:false,
costs:[{start_date,end_date,timezone,currency,cost, filters:{ad_campaign_id:"J41-16"}}]}`
- Idempotent (re-push overwrites matched clicks). Push per completed account-tz
  day.
- Filter keys: keyword, external_id, creative_id, ad_campaign_id, source,
  sub_id_1..30 (comma-lists ok).
- `currency` = the ad account's currency as-is (EUR, etc.); Keitaro converts to
  its base currency at its own rate (FIELD 2026-09-27: €102.71 → $116.99).
  No manual FX. `timezone` = the ad account tz; the UI "Обновить расходы" form
  defaults to the tracker tz (e.g. Europe/Moscow) and shifts the day.
- Cost is spread only over clicks that match range + filters. A day/campaign
  with spend but zero tracker clicks stores NOTHING (spend silently lost in
  ROI) — reconcile source spend vs tracker cost after each push (FIELD 2026-09-27).
- Readback lags: `{"success":true}` returns at once, report cost updates
  seconds-to-minutes later — poll until the value matches, don't re-push (FIELD 2026-09-27).
- 🔺 Campaign cost model CPA/CPS with "auto" ON adds the model's fixed cost per
  NEW conversion on top of the pushed cost (fake cost → wrong ROI; FIELD
  2026-09-27: $60/conv). Either
  re-push at end of day after late conversions, or set the campaign cost model
  to CPC 0 (`PUT /campaigns/{id}` `cost_type`/`cost_value`/`cost_auto`) with the
  campaign owner's OK so only pushed cost counts.
- `/campaigns/{id}/update_costs` exists but docs say "VERY SLOW" — use the
  clicks endpoint.
- `/integrations/facebook` (native auto cost sync) may be blocked for
  limited-permission users — manual push is the fallback.

## Postback / S2S

`https://TRACKER/{POSTBACK_KEY}/postback?subid={subid}&status={status}&payout={payout}`
- Path segment = FIXED postback key (Settings → Postback URL), NOT the subid.
  `subid` is a query param (Keitaro click id). Required: subid + status only.
- Optional: payout, cost, currency, `tid` (records repeat conversions without
  overwriting), sub_id_1..30. Aliases: clickid=subid, type=status, profit=payout.
- Statuses: `lead` (first event/pending), `sale` (confirmed), `rejected`, plus
  registration/deposit/trash/custom. Network "hold" → send `lead` (no native
  hold). `rebills` is a metric, not a status (repeat via tid).
- Dedup: same subid+status → OVERWRITES existing conversion. A unique `tid`
  creates a SEPARATE record (upsells/rebills) — multiple conversions per click
  are intentional (distinct tid), not accidental inflation; this is why
  "conversions" is not a CPL denominator (SKILL metric rule).
- Click-id flow: source id → Keitaro → offer via `{external_id}`; network
  returns it as `subid`. sub_id_1..30 = extra markup pass-through.

## Postback drill (verify before trusting any conversion number)

Before scaling a new funnel/offer/tracker link, fire a REAL test conversion
end-to-end — don't assume the postback works because the URL looks correct.

- Fire it: trigger the offer's conversion (or ask network for a test fire), OR
  hit the postback URL manually with a real click's `subid` + agreed `status`
  (+payout, +tid).
- Confirm on tracker: conversion on the RIGHT click (subid), status mapped to
  YOUR payout metric, correct payout, correct campaign/sub_id split. Read the
  incoming-postback log for what arrived vs expected.
- Catches: subid dropped/renamed (invisible conversions), status-string
  mismatch (network `deposit` vs your scheme), missing/zero payout, missing
  `tid` (rebills overwrite instead of stacking).
- Do it safely: test click/campaign + unique test `tid`, disable downstream
  forwarding (no CAPI/optimization/network payout pollution), confirm after.
- Re-drill after ANY change to redirect chain, offer link, status scheme, or
  tracker. Complement to the funnel click-through test (senior-buyer-ops/03).

## Conversion lifecycle (what breaks daily numbers)

- Report date mode: CHECK INSTANCE SETTING FIRST — `Settings → System → Report
  display conversion date` toggles reporting basis between `By Click Date` and
  `By Conversion Date` globally (recalculates existing stats too); no per-request
  override. Automation must read/pin this before trusting a pull's basis. Raw
  per-conversion rows come from `POST /conversions/log` (range, columns[],
  filters[], sort[], limit/offset): `click_datetime`, `postback_datetime`,
  `sale_datetime`, `status`/`previous_status`/`original_status`, `conversion_id`,
  `tid`, `sub_id_N`, revenue. No built-in lag measure — derive lag =
  postback_datetime − click_datetime per row (`sale_period` = coarse bucket).
- MEDIA optimization → click-date (a lead posting back today lands on
  YESTERDAY's row → re-pull a trailing 3-7d window each run, don't freeze after
  one pull). FINANCIAL/payout reporting → conversion-date (`postback_datetime`).
  Don't mix bases in one CPL number; know which mode/endpoint a pull used.
- Delayed status changes: lead→sale/deposit can flip days later (same subid) —
  report leads now, quality on a lag, re-pull the cohort when it matures.
- Offer caps: once daily cap is hit, further conversions may be
  rejected/unpaid though tracker still logs clicks — watch cap state before
  scaling spend into a capped offer.
- Failed postbacks: missing (not delayed) if network's postback never arrived.
  Check incoming-postback log, have network re-fire (or import via
  subid,payout,tid,status) before concluding a funnel is dead.
- Reconcile against advertiser/backend periodically — tracker leads are your
  count, advertiser's approved count is what pays; widening gap = scrub or a
  tracking break.

## Gotchas

- Bot clicks inflate `clicks` (not `campaign_unique_clicks`); cost spreads over
  all matching clicks → CPC looks diluted on bot days, but daily CPL vs your
  payout-status count stays correct.
- Geo on mobile IPv6 resolves to carrier hubs, not the user's city
  (FIELD 2026-09-27: Louisiana-only targeting, deps showed Texas cities) — not
  a targeting/cloak leak; don't geo-kill on tracker city/region.
- 🔺 DIAGNOSTIC TRAP: with an `fbclid`-keyed cloak condition (above), a manual
  browser walk (hand-typed URL, no ad click) can NEVER carry a genuine
  `fbclid` and so can NEVER reach the money lander. The white page on a
  hand-typed visit is CORRECT behaviour, not a broken funnel — this produced a
  wrong "funnel is broken" conclusion and cost real debugging time
  (field-observed 2026-09-21). Verify by the click log, not by walking it.
