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
costs:[{start_date,end_date,timezone,currency,cost, filters:{ad_campaign_id:"<FB campaign id>"}}]}`
- Idempotent (re-push overwrites matched clicks). Push per account-tz day and re-push the trailing days
  (the current day is partial). Date format of `start_date`/`end_date`: copy a working call; `report/build` uses
  `YYYY-MM-DD HH:MM` (unverified for this endpoint; `metaops keitaro push` sends that shape). Timezone is an IANA name, so DST days are the
  tracker's problem, but the day boundary must be the AD ACCOUNT's, one entry per account.
- Filter keys: keyword, external_id, creative_id, ad_campaign_id, source,
  sub_id_1..30 (comma-lists ok).
- **Key on ids, not names.** FB names repeat (four ads once shared one name; a campaign name can recur on
  two accounts, and a re-push then overwrites the other account's cost), and `{{…name}}` url_tag macros
  are first-publish snapshots (`meta-grey-ops/04`), so a renamed object no longer matches. In the operator's
  Keitaro 1234 link the FB campaign id lands in `ad_campaign_id` and the FB ad id in `sub_id_6` (check
  the mapping of your own campaign): push per ad,
  `filters:{sub_id_6:"<ad_id>"}` (finest key; campaign cost = sum), or per campaign,
  `filters:{ad_campaign_id:"<campaign_id>"}`. Do not push both levels for the same days: the later
  push overwrites the same clicks. Name-keyed (`sub_id_1:"<campaign name>"`) worked on 2026-09-27 but is
  the fragile option.
- Script: `metaops keitaro push` (`meta-grey-ops/16` § Keitaro). Dry run without `--confirm PUSH`. It pulls ad-level
  daily insights over every effective status (deleted/archived too; account tz, account currency), sends one
  entry per (ad, day) with `filters:{sub_id_6}`, one request per day (<= 100 entries), re-pushes the trailing
  3 days (today included, partial), then reads cost back (`/report/build` by day + `sub_id_6`) and prints FB
  spend vs Keitaro cost per day. Flags: `no_clicks` (ad-day with spend and zero Keitaro clicks: the cost is
  dropped), `not_stored` (Keitaro cost 0), `delta` (> 3%). Not settled after the bounded poll (45 s) = warning,
  not failure; re-read with the dry run, don't re-push. `metaops keitaro report` = per-ad FB spend x Keitaro
  clicks/regs/deps/`sale_revenue` (regs = leads + sales, never `conversions`; `{{…}}` macro rows excluded).
- Spend that the ad rows do not explain (account total minus sum of ad rows; ads Graph did not return) is reported
  as `unattributed`, NOT pushed: a campaign-level entry matches the same clicks as the per-ad entries and would
  overwrite them. Only a campaign with no ad row at all that day is safe on `ad_campaign_id`; the script lists it
  as a candidate and leaves the decision to a human.
- Verified live 2026-09-29 (dry run + report on campaign 1234): `report/build` accepts the `EQUALS` campaign filter, `limit`/`offset`, dimensions `day`, `sub_id_6`, `sub_id_11`, measures `clicks`/`leads`/`sales`; `GET /campaigns/{id}` exposes the cost model fields the script warns on (CPA 60, auto ON on 1234). `sub_id_11` values seen for FB feed traffic: `Facebook_Mobile_Feed` (159 clicks, 7 deposits in 7 days); test/bot clicks carry an unsubstituted `{{placement}}` or `{sn_placement}`; other placements (stories, reels) have not landed yet.
- Still unverified: the `start_date`/`end_date` format for `update_costs` itself (script sends `YYYY-MM-DD 00:00` / `23:59`; the last minute of the day may fall outside; no real push yet), whether Graph returns deleted/archived ads' rows on the account edge with the `ad.effective_status` filter (`unattributed` exposes a miss), whether `update_costs` skips bot-marked clicks (docs say the UI does), and how long the readback lags. First live use: one
  completed day, dry run, `--confirm PUSH`, compare in the UI.
- Keitaro converts at its own rate: with an account currency different from Keitaro's base (set `KEITARO_CURRENCY`
  or `--keitaro-currency`), the script judges days by the consistency of the implied rate, not by delta vs 1.0.
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
  campaign owner's OK so only pushed cost counts. `metaops keitaro push|report` read the model
  (`GET /campaigns/{id}`, never PUT) and warn when it is CPA/CPS with auto ON.
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
  matching clicks → CPC looks diluted on bot days, but daily CPL vs your
  payout-status count stays correct. Conflict to test on one day: the Keitaro docs (manual cost update
  page) say bot-marked clicks are skipped by default when updating costs; whether the API endpoint
  does the same is unverified. The same page calls the update "a heavy operation, 10-20 minutes", vs
  seconds-to-minutes read-back seen here: poll, don't re-push.
- Geo on mobile IPv6 resolves to carrier hubs, not the user's city
  (FIELD 2026-09-27: Louisiana-only targeting, deps showed Texas cities) — not
  a targeting/cloak leak; don't geo-kill on tracker city/region.
- 🔺 DIAGNOSTIC TRAP: with an `fbclid`-keyed cloak condition (above), a manual
  browser walk (hand-typed URL, no ad click) can NEVER carry a genuine
  `fbclid` and so can NEVER reach the money lander. The white page on a
  hand-typed visit is CORRECT behaviour, not a broken funnel — this produced a
  wrong "funnel is broken" conclusion and cost real debugging time
  (field-observed 2026-09-21). Verify by the click log, not by walking it.
