# 03 — Metrics, math, markup, routine

Principles below port to any tracker (Voluum, RedTrack, BeMob, PeerClick...);
only the API surface differs (01/02).

## CPL that doesn't lie

Daily CPL (for BUYING) = click-date spend (account-tz day) ÷ that same
click-date cohort's payout count. "Same day" only holds once the cohort has
matured; while lagging, use the matured or nowcast cohort count (below), NOT
today's raw postback count — pairing click-date spend with conversion-date
conversions is the classic apples-to-oranges CPL. Conversion-date basis
(postback day) is for FINANCE/cashflow, not buying decisions.
- Spend truth: ad platform API per account/day. Field-observed gotcha: a plain
  `/me/adaccounts` pull can omit disabled accounts, silently dropping their
  spend from totals — verify what your edge+fields return, keep your own
  spend log (or agency billing) for history with dead accounts. Meta account
  `balance` = unbilled amount in cents, not prepaid funds; `account_status` 3 =
  unsettled billing, not a ban (FIELD 2026-09-27).
- Lead truth: tracker, the AGREED payout measure only (not "conversions" = all
  postback records; the excess over your leads is integration-specific, not a
  fixed multiple — SKILL metric rule). Keitaro reg payout = leads + sales, not
  `leads`; money = `sale_revenue`, not `revenue` (01).
- Cross-check: pixel leads ≈ tracker leads (±tolerance set from a reconciled
  baseline, account-specific — SKILL rule #3). Bigger gap = wrong metric or
  broken tracking → stop and reconcile before reporting.
- 🔺 Two priors, **not laws** (one practitioner's observed baselines, unvalidated
  across accounts): fresh accounts pay ~2× CPM premium; judge click→lead CR on
  ≥100 clicks before reading a trend. Replace with your own reconciled numbers
  ASAP — quoting these to a TL as fact is the error this file exists to stop.

## Reconciliation tree (when Meta ≠ tracker)

Branch on DIRECTION — causes differ:
- Meta > tracker: tracking loss before tracker (click-ID/subid dropped in
  redirect/prelander, senior-buyer-ops/03; postback not firing, tracker-ops 01
  replay; pixel double-counting/dedup); or wrong tracker metric picked
  (deeper status than the pixel event); or view-through — tracker never sees
  view conversions (team default for casino Purchase 7d click / 1d view,
  meta-grey-ops/21); compare against Meta's click-only column (FIELD 2026-09-27).
- Tracker > Meta: pixel under-fires (WebView/in-app browser strips it,
  consent/ATT blocks it, CAPI not sending → prefer S2S truth, fix the pixel);
  attribution-window/timezone mismatch (Meta modeled vs tracker raw);
  bots/duplicate postbacks inflating tracker (check tid/overwrite, 01).

Either way: reconcile ONE clean day end-to-end (fire a test conversion, follow
both sides), set tolerance from that baseline, trust the delta — don't chase
noise day to day.

### iOS ATT & the Meta↔tracker gap

Meta backfills iOS with modeling + view-through, so its number can land
**EITHER side** of tracker/backend (same rule as meta-ads/08). Rule: segment
Meta-vs-tracker deltas by OS/GEO before reconciling (iOS-heavy gap is expected
noise, direction not assumed); on iOS-heavy traffic treat S2S/postback as
money-truth, Meta's iOS figure as modeled. PWA/web funnels don't use SKAN
(senior-buyer-ops/03) — this mainly bites native-app/store flows. ATT opt-in
rate figures/vendor comparisons: not owned by this file — verify current, do
not carry a stale number here.

## Multi-tracker sync & the conversion ledger

Two trackers in the chain (your Keitaro + network's tracker, or redirect
tracker + analytics one) will NOT agree by default — different click-id keys,
timezones, dedup, bot filters. Pick ONE as source of truth for money (usually
whichever holds the payout postback); treat the other as cross-check, never a
second total to add.

- Join key: reconcile only if a shared click id crosses both — carry your
  subid/external_id into the network as its sub param and back on the
  postback, so each conversion matches 1:1. No shared key → aggregates only,
  not rows.
- Align timezone/window to ad-account tz before comparing a day; a "gap" is
  often just a boundary/lag mismatch (reconciliation tree above).

Conversion ledger (raw, append-only): log every INCOMING postback verbatim —
timestamp, subid, status, payout, tid, raw query — separate from tracker's own
mutable state.
- Rebuild/replay: re-import conversions (Keitaro via subid+status+payout+tid;
  postback log is the source) if tracker breaks or a status scheme changes,
  instead of losing the period.
- Scrub disputes: proves exactly what the network sent, postback by postback.
- Dedup audit: distinct-tid vs overwrite verifiable against raw stream. Append,
  never rewrite; key each row by idempotency id (subid+tid+status) so replay
  can't double-count; REDACT tokens/PII from stored query.

## Cohort nowcasting (decide before the cohort matures)

Today's CPA looks terrible because today's conversions haven't posted back yet
(confirm/deposit/KYC lag). Project the mature number instead of waiting blind:

1. Build the completion curve from history: matured click-date cohorts,
   bucket each conversion by lag = conversion_time − click_time (Keitaro
   `/conversions/log`: postback_datetime − click_datetime; Binom: built-in
   `Time since click`, 02). p(d) = cumulative fraction of a cohort's eventual
   conversions arrived by age d days.
2. Nowcast: `predicted_mature ≈ observed_to_date ÷ p(age_so_far)`;
   `predicted_CPA = spend ÷ predicted_mature`. Decide kill/scale on the
   NOWCAST, not raw immature count (feeds senior-buyer-ops marginal scaling +
   team stop-loss — both require MATURE numbers).
3. Keep bases separate: click-date drives MEDIA decisions; conversion-date
   drives FINANCE/cashflow. Never mix in one figure.

Caveats: curve DRIFTS — new offer/GEO/season changes lag, refit on recent
cohorts. Low-volume cohorts → noisy nowcast, treat as directional. A
never-arriving conversion isn't lag — rule out a tracking break (01) before
trusting the projection.

## Anti-fraud / cloaking signals (read as a set)

- raw clicks >> unique: bot refresh/source re-fire — judge cost on payout
  count, not raw clicks.
- rising bot_share/proxies: moderation crawlers on the white page; some is
  normal on a cloaked funnel, a rising trend precedes domain/account bans.
  Signal only — response (domain rotation) is grey-ops: Meta `meta-grey-ops/01`,
  Google `google-grey-ops/03` + cloak stack `google-grey-ops/05`.
- near-zero LP CTR w/ normal clicks: cloaca over-filtering real users (or black
  page broken) — a tracking fault, not bad traffic; fix the filter, don't kill.
- empty_referrers spike: stripped/direct traffic — correlate with bot_share.
- unsubstituted `{{...}}` rows: exclude-then-classify (SKILL rule #5) — read
  alongside the signals above, not automatically as bots.

## Markup & the mapping contract

No automatic split — the tracker only knows what your campaign URL maps into
its parameters:

| Meta side (macro) | → tracker param | carries |
|---|---|---|
| `{{campaign.name}}` | ad_campaign_id (or a sub_id) | your campaign-name convention (= ad account) |
| `{{adset.id}}` / `{{ad.id}}` | sub_id_N | per-adset / per-ad split (only if mapped) |
| FB click id (fbclid / macro) | external_id / subid | click identity for the return postback |
| offer event (reg/FTD/sale) | postback `status` | which status = your PAYOUT metric |

- Tracker splits by `ad_campaign_id` ONLY because your URL feeds the campaign
  name into it (01). Per-ad splits need `{{ad.id}}`→sub_id_N mapped.
- FB naming discipline IS the tracking plan (meta-grey-ops/03): agency setups use campaign name =
  ad account; our Keitaro-id contract is campaign name `<keitaro id> US PWA … <buyer>` with the account in
  `act=`/sub10, ad name = creative. Names repeat and name macros are snapshots: key cost and joins on
  ids (`ad_campaign_id`, `sub_id_6`), not names. No casino names in FB names on the own BM.
- Pin the payout `status` in the contract too — optimization event, tracker
  status, and payout event must line up or CPL/ROI measures the wrong thing.

## Backend optimization contract (which status → which CAPI event)

Three events people conflate but are usually DIFFERENT — pin each separately;
optimizing the wrong one is the most expensive silent error:
- REPORTING event — what you call a "lead" to the team.
- PAYOUT event — tracker status you actually get paid on (senior-buyer-ops
  operating-contract #1).
- OPTIMIZATION event — the CAPI/Pixel event the ad set bids toward; drives who
  you get shown to.

Wiring: tracker/CRM status → CAPI event. Offline Conversions API discontinued
(~May 2025) — all CRM/backend stages now flow through standard CAPI. Set
`action_source` to where the conversion ACTUALLY happened (`website`, `app`,
`phone_call`, `chat`, `email`, `physical_store`, `business_messaging`,
`system_generated`, `other`) PER EVENT, not inherited from the original lead's
source; `system_generated` only for conversions with no customer interaction
(e.g. subscription auto-renewal). CAPI mechanics live in meta-ads/08; this file
is which status maps to what.

Choosing the optimization event = reliability × volume × correlation-with-payout:
- Deeper event (FTD/confirmed sale) aligns with revenue but LOW volume → may
  never clear learning-phase volume floor (Meta's ~50 optimization events/ad
  set/7d — verify live). Shallower event (reg/lead) is high-volume, easy to
  optimize, weakly correlated with payout → cheap junk that never converts.
- Rule: optimize the DEEPEST event that still clears the learning-volume bar.
  If payout event is too rare, optimize a reliable UPSTREAM proxy correlated
  with payout, and monitor that correlation (reg→FTD rate).
- VBO needs `value`+`currency` and a volume gate thin grey funnels often can't
  meet → optimize on conversion COUNT, control quality via which status you
  send back. (VBO + Conversion-Leads eligibility numbers: meta-ads/08.)
- Native lead forms: Meta's Conversion Leads goal takes CRM stage events via
  CAPI to optimize a down-funnel stage instead of raw form fills; eligibility
  gates in meta-ads/08.
- Only send events you can stand behind (deduped via event_id, real) — the
  signal also feeds Meta's quality modeling; noisy/fake events degrade
  delivery, not just reporting.

## Telegram Mini App / bot — CAPI without a pixel

Telegram WebView is not a reliable Pixel jar (senior-buyer-ops/03) → server
CAPI is the path. Failure mode: stuffing `fbclid` into the Telegram deep link
— it's case-sensitive, often >64 bytes, not `[\w-]`-safe. **Never put it in
`start`/`startapp`.** Store it on the tracker click; put the tracker click id
(or shorter alias) in the Telegram param instead (`t.me/<bot>/<app>?startapp=<token>`,
512-byte limit, vs `t.me/<bot>?start=<token>` at 64 bytes).

Contract: Meta ad URL → tracker (captures fbclid, issues token) → 302 to Mini
App with `startapp=<token>` → app reads `start_param`, looks up token → fbclid
- subids → on Lead/Purchase, fire CAPI. `action_source` = `website` when the
Mini App is on your HTTPS origin (`event_source_url` + `client_user_agent`
required then); `other`/`chat` for bot-only with no page. Never send
Telegram's webhook IP as `client_ip_address`, never invent `fbp` (omit if no
first-party cookie); server-built `fbc` without a cookie uses subdomainIndex 1
(`fb.1.<unix_ms>.<fbclid>`, no hash/case rewrite). `external_id` = same token
as `startapp` (hash recommended). No Pixel fire → no dedup pair, still send a
stable `event_id`.

```bash
curl -sS -X POST "https://graph.facebook.com/v26.0/${DATASET_ID}/events" \
  -d access_token="${CAPI_TOKEN}" \
  --data-urlencode data='[{
    "event_name": "Lead",
    "event_time": 1712248396,
    "event_id": "CLICKTOKEN-lead",
    "action_source": "website",
    "event_source_url": "https://app.example.com/",
    "user_data": {
      "fbc": "fb.1.1712248000123.IwAR2F4-dbP0l7Mn1IawQQGCINEz7PYXQvwjNwB_qa2ofrHyiLjcbCRxTDMgk",
      "external_id": ["CLICKTOKEN"],
      "client_ip_address": "203.0.113.10",
      "client_user_agent": "Mozilla/5.0 ... Telegram"
    }
  }]'
```

Pin the Graph version to the workspace pin (`v26.0` since 2026-07-29; `v24.0` stops on
2026-10-06 for Marketing API calls, so old copies of this curl with `v21.0`/`v24.0` need bumping). Use `test_event_code` until green. Purchase needs
`custom_data.value`+`currency`. Status→event mapping is the contract above,
not this curl.

## Daily routine (automate)

For YESTERDAY (account tz): pull Meta spend/impr/clicks per live account →
push real spend per FB ad (or campaign) per day (filter = the id params
`sub_id_6` / `ad_campaign_id`, not names, 01; idempotent; one entry per account tz/currency) → confirm readback + no spend lost on zero-click days →
pull tracker payout count (reg = leads + sales; money = `sale_revenue`) →
fill team report (raw columns, formulas compute) → read per-account CPL vs
target → kill/watch/scale → log snapshot. End of day: re-push the same days
after late conversions (mandatory if the campaign cost model is CPA/CPS auto,
01) (FIELD 2026-09-27). Missed days: re-run per date
(`metaops insights pull --since/--until`, or `meta-grey-ops/scripts/insights.py`). `metaops keitaro push`
(01) builds and sends the update_costs POST; re-push the trailing 2-3 days each run (its default).

## Reporting upward

Use the team's lead definition + their timezone (ask which the sheet uses).
Never report a metric not reconciled once against a second source.
