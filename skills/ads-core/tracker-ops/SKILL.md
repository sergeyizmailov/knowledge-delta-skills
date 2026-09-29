---
name: tracker-ops
description: "Tracker ops for affiliate/media buying: Keitaro + Binom APIs (keys, reports, cost push), postback/S2S, metric discipline (payout event vs all-conversions, timezones, CPL math), daily spend-sync, gclid/OCI chain for Google. Principles port to other trackers."
---

# Tracker Ops

Count money correctly and automate tracker work. Keitaro + Binom specifics
below; the metric rules and daily sync port to any tracker.
Baseline 2026-09-03 (Sonnet 5 blind, CPL cohort task): [R] — click-date cohort and pinned attribution window already known; do not expand that section.

## Metric rule (NEVER violate)

1. "conversions" (Keitaro) can exceed your payout-lead count, but that is
   INTEGRATION-SPECIFIC, not an inherent 3.5-4x: the same subid+status
   OVERWRITES; extra records come only from distinct `tid`s or a genuine
   multi-step funnel. Never do CPL math on "conversions" — the payout metric is
   ONE event/status; get it from the TL in writing. (Any "3.5-4x" is one
   setup's ratio, not a law.) Exception: statuses flip in place, so a REG
   payout counts leads + sales (rule 2).
2. Metric names aren't portable: Keitaro `leads` = conversions STILL in status
   lead (lead→sale flips in place): regs = leads + sales, deps = sales —
   `leads` as reg count overstates reg→dep (FIELD 2026-09-27: 11 vs 17).
   Binom "leads" ≈ all conversions. Verify semantics per tracker per setup.
3. Cross-check: platform-reported lead count ≈ tracker lead count. A big divergence = wrong
   metric or broken tracking; stop and reconcile before reporting. The "±20%"
   tolerance is an account-specific baseline you set from a reconciled day, not
   a universal constant. Meta counts view-through the tracker never sees —
   compare Meta click-only (03).
4. Compute daily CPL in the AD ACCOUNT timezone for both spend and leads. Google's account
   timezone is permanent (senior-buyer-ops contract #5) — reconcile in the tracker, never by eye.
5. Rows with unsubstituted `{{...}}` macros: exclude from performance analysis,
   then classify the cause — bots/crawlers, yes, but also a broken URL template,
   an unsupported/misspelled macro, or manual/direct traffic. Fix the template
   if it's yours before blaming traffic.
6. Money = `sale_revenue`, never `revenue` (includes lead_revenue; payout on
   lead postbacks fakes ROI — FIELD 2026-09-27: $9,820 lead_revenue vs $1,650
   real sale_revenue). Check lead_revenue = 0.

## Route references

| Need | Reference |
|---|---|
| Keitaro: key, report/build, measures, update_costs, postback/S2S, postback drill, gotchas | `references/01-keitaro.md` |
| Binom: legacy URL-param + v2 REST, reports, cost, postback/S2S | `references/02-binom.md` |
| CPL math, funnel + anti-fraud metrics, cohort nowcasting, backend optimization contract (status→CAPI event), TMA/bot CAPI without pixel, multi-tracker sync + conversion ledger, ATT asymmetry, mapping, daily routine | `references/03-metrics-and-math.md` |
| Google lane: gclid/gbraid/wbraid, ValueTrack chains, Keitaro/RedTrack Google config, OCI windows + dedup, the 2026-06-15 cutoff, Data Manager `events:ingest` for new tokens | `references/04-google-lane.md` |

Platform lanes are not interchangeable — Meta counts through CAPI, Google through gclid → OCI, with different windows, a different dedup key, and a hard onboarding cutoff. Read `04` before wiring anything on Google traffic.

## Non-negotiables

- Work only on YOUR campaign IDs; every call carries a campaign filter. Other
  buyers' campaigns are read-never-touch.
- No cost push = no CPL/ROI (report cost is 0 — or fake: CPA/CPS cost model
  with auto ON adds fixed cost per conversion, 01). Push daily, keyed on ids
  (`ad_campaign_id` / `sub_id_6`), in the ad account's tz and currency: `metaops keitaro push` (dry run first,
  then `--confirm PUSH`; 01). Overwriting a period is
  idempotent, but cost lands only on clicks matching range+filters — reconcile
  source spend vs tracker cost after each push.
- API keys are write-once; store verbatim in gitignored notes.
