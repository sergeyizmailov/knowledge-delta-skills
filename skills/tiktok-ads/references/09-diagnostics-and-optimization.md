# 09 — Diagnosis, optimization, and scaling

Verified 2026-09-14. The ordering and math here are media-buying discipline, not TikTok specifics;
what is TikTok-specific is flagged.

## Diagnose in order — never jump to the bottom

```
eligibility/billing → delivery → auction → attention → click quality
→ landing continuity → conversion → business value → attribution
```

Each stage can only be read once the one above it is healthy. A "bad CVR" diagnosed while the pixel
is double-counting is not a finding.

## No spend at all

| Check | Detail |
|---|---|
| Time since activation | **Insights are empty for 15–40 minutes.** Not a failure. Do not touch anything |
| Object status at all three levels | Campaign, ad group *and* ad each have their own status. Check separately |
| `schedule_start_time` | A future start is silent. A *past* start does not error — it starts immediately, often in dead hours |
| Review state | `ttops review`. A rejected ad cannot be enabled; build a new one |
| Balance | Prepay stops dead at zero with **no grace period** |
| Account status | Suspended or under review (`02`) |
| Budget vs market CPM | "Insufficient budget" means the budget cannot win auctions at that market's price, not that it is below the minimum |
| Audience size | `ad_audience_size_estimate`. Over-restricted targeting plus exclusions |

## Spending, not converting

Decompose before theorising:

```
CPM → CTR → click-to-landing-page-view → LP CVR → payout-event rate → value
```

The stage where your number diverges from the account's own history is the stage to work on. Most
"TikTok doesn't convert for us" cases are one of three things:

1. **Tracking is broken or double-counting** — check `07` before anything else. Mismatched `event_id`s
   and hash normalisation both fail silently.
2. **The optimization event is too deep for the volume.** TikTok's documented learning signal is
   **~25 results or 7 days** before volatility falls — while TikTok's own delivery-troubleshooting
   page tells you to allow 7 days to reach **50** conversions (`05` documents the conflict).
   An ad group that cannot reach roughly 25 of its optimization event stays volatile — TikTok
   describes a volatility curve, not a hard exit gate, so treat this as a signal that the event is
   too deep rather than a threshold that flips. Move to the nearest upstream event and name the
   switch condition.
3. **Click quality is fine and the landing page is not continuous with the creative.** TikTok traffic
   arrives from a different mental state than search or even Meta — the page has to answer the hook.

## STALL: impressions, no clicks

`ttops sweep` flags this. On TikTok it usually means the creative is being served and ignored, not
that delivery is broken. The fix is creative, not bid.

Check hold metrics before concluding: `video_watched_2s`, `video_watched_6s`, `video_views_p25/50/75/100`,
`average_video_play`. A 2-second hold that collapses tells you the hook failed; a strong hold with no
clicks tells you the creative entertained and did not sell.

**Define the denominator before comparing hook rates.** "3-second view rate" over impressions and
over plays are different numbers, and mixing them across ad groups produces confident nonsense.

## Creative fatigue

TikTok exposes a `fatigue_index` endpoint, but it is **allowlist-only, rep-gated**. Without it,
compute heuristically: frequency rising while CTR falls and CPC/CPA rises, over the ad's **own**
baseline, not against a portfolio average.

Field consensus is that TikTok's decay runs in **days rather than weeks** — 3–5 creatives per ad
group refreshed every 7–10 days. That is a practitioner prior, not a measured constant. Derive your
cadence from your own frequency and CTR curves; the number is a starting hypothesis (`06`).

There is also a creative-fatigue **webhook** entity (`tiktok-ops/06`).

## TikTok vs your tracker disagree

Expected, and partly structural (`07`):

1. TikTok is a **self-attributing network**.
2. It counts **engaged view-through** (≥6s, no click) — your tracker cannot see that at all.
3. Windows differ, and TikTok's window is **locked at ad-group creation**.

Reconciliation order: verify the event count and dedup first; then attribution window; then
conversion lag; then consent-driven loss; then refunds and qualification. Only then conclude anything
about performance.

Pick one source of truth for money — platform or tracker — and hold to it; reconcile the other
against it rather than averaging them. Define what counts as one conversion (dedup rule, event
window) once, and apply it everywhere, so numbers from different systems are comparable rather than
coincidentally similar.

## Benchmarks — read this before quoting a CPM

The 2026 TikTok benchmark landscape is unusually polluted:

- **Reported CPMs disagree by more than 2× across "benchmark" sources published in the same week**
  ($4.08 vs $4.80 vs $9.00), with no reconciliation. There is no single trustworthy TikTok CPM.
- A significant share of 2026 "TikTok benchmark" content is **AI-generated content-farm output**. One
  heavily cited site attributes statistics to research firms that do not check out.
- The widely circulated "Nielsen 780-campaign Spark Ads study" traces, on direct fetch, to **TikTok's
  own help page** — a citation laundered into a fake third-party study.

Rules: a benchmark is a **prior with provenance**, never a target. Quote sample size, period, GEO and
method alongside it, or do not quote it. **The account's own history beats any benchmark**, and
break-even CPA from the offer's economics beats both.

The one adoption figure with real provenance found in this research: Tinuiti's Q3 2025 report, Smart+
going from 9% to 42% of US TikTok campaigns inside a year.

## Scaling

Documented: only the **105%-of-current-spend floor** on budget updates (`05`). Everything else is
convention.

- **Vertical** (raise the budget) re-enters volatility. TikTok warns against edits that retrigger
  learning without quantifying which or by how much. **The "±20% resets learning" rule is not in any
  TikTok document** — it is imported from Meta. Follow it if you like, but call it a convention.
- **Horizontal** (duplicate winners) is the field default — and **TikTok's own best-practice guidance
  advises against repeated daily ad-set duplication**, a direct conflict with a widely taught
  affiliate tactic (`11`). Worth knowing which side of that you are on and why.
- Once spend has accrued in a period you **cannot cut below 105% of it**. Plan reductions as pauses,
  not cuts.
- `AUTO_BUDGET_INCREASE` (allowlisted Smart+) can raise the daily budget **20% up to 10×/day** at
  ≥90% utilization — up to ~6.2× the stated daily figure before the nightly reset (`05`). If it is
  on, the budget you quoted the operator is not the ceiling. Say so.

Before scaling or killing on a difference, confirm it is real rather than noise: check the sample
size against the metric's normal variance before treating a swing as signal. The kill/scale ladder
and small-sample math are ordinary media-buying discipline, not TikTok-specific.

## TikTok's own diagnosis agent

`tiktok_ads_diagnosis_agent` (MCP, `tiktok-ops/01`) is TikTok's official Account Optimization Score
diagnosis agent, exposed agent-to-agent. Hand it an account, campaign or ad group and it returns
natural-language findings from TikTok's own models. **Does not support GMV Max objects.**

Treat it as a strong prior about what TikTok's system thinks is wrong — which is genuinely useful,
because delivery is its own black box — not as a measurement of your business. It does not know your
break-even CPA or your payout event.

`tool_diagnosis_get` and `tool_search_diagnosis_health_get` are the non-agent equivalents.

## Reporting mechanics that change conclusions

- Rows are in the **ad account's timezone and currency**. Two accounts in one portfolio disagree
  about "yesterday".
- **Attribution is not a report parameter** — it is fixed on the ad group. You cannot re-run a report
  at a different window.
- **Sync reports silently truncate at ~20,000 ads.** A small result set is not evidence of zero
  matches.
- Async reports are **allowlist-only**; do not design a pipeline assuming them (`tiktok-ops/06`).
- Data is not real-time.

## Weekly review

1. Reconcile platform vs tracker on the payout event. Diverging? Stop and fix before optimizing.
2. Re-derive break-even CPA if the offer, payout or margin moved.
3. Per-ad fatigue sweep against each ad's own baseline.
4. Creative backlog health — is the pipeline feeding the structure you built (`01` intake #9)?
5. Spark authorization expiry dates (`06`). A silently expired code looks exactly like a delivery
   collapse.
6. Which input from the original derivation turned out wrong (`01` § H)? That is the output that
   makes the next launch better — not the CPA number.
