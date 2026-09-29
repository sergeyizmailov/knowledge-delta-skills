# 04 — Automated rules that don't kill winners

Kill rules act on the smallest samples in the account, so a naive cost threshold measures luck,
not quality. This file is the decision math (vertical-agnostic) plus the platform reality that
constrains how it can be expressed. Applies to any paid channel and any payout event; only the
target price changes.

## The failure mode

Target $6/conversion. An asset spent $12 and produced 1 → "$12, over target, pause". But one more
conversion arriving five minutes earlier reads $6 and survives. The rule decided on arrival
timing, not on the asset.

## The question that fixes it

Not "what cost did it show" but: **could an asset that truly runs at target have looked this bad
by chance?** If yes, keep spending. If no, kill.

## Poisson ladder

Conversions are rare independent events → Poisson. One fact needed: if λ conversions were
expected, `P(zero) = e^-λ`. Spend S at target price T means `λ = S/T` expected conversions. Pause
once the observed count becomes implausible at the chosen confidence level.

Worked: T=$6, S=$18 → λ=3 → `e^-3 = 5%`. An on-target asset stays silent through $18 only 5 times
in 100 — silence is now a verdict, not bad luck. At S=$12, λ=2 → `e^-2 = 13.5%` — one in seven
honest assets does that. Too early.

For k>0 the same question uses `P(X ≤ k)`. The resulting multipliers are universal constants —
independent of vertical, GEO, channel, event:

| k conversions | multiplier (95%) | actual cost at trigger |
|---|---|---|
| 0 | 3.00 | — |
| 1 | 4.74 | 4.74× target |
| 2 | 6.30 | 3.15× |
| 3 | 7.75 | 2.58× |
| 4 | 9.15 | 2.29× |
| 5 | 10.51 | 2.10× |
| 6 | 11.84 | 1.97× |
| 7 | 13.15 | 1.88× |
| 8 | 14.43 | 1.80× |
| 9 | 15.71 | 1.75× |
| 10 | 16.96 | 1.70× |
| 15 | 23.10 | 1.54× |
| 20 | 29.06 | 1.45× |
| 50 | 63.29 | 1.27× |

`threshold_spend(k) = multiplier(k) × target_price`

Strictness is self-adjusting: on no data you must be ~3-5× over target to die; at 50 conversions,
27% over is enough. Nothing hand-tuned — tolerance shrinks because the sample grew.

Exact (chi-square/Poisson) intervals are standard at small counts; normal approximation only holds
at large ones — statsmodels, StatsDirect.

## Build it in three steps

1. Take the target price of the PAYOUT event from the operating contract (SKILL).
2. Multiply the column above by it → one spend threshold per conversion count.
3. Write one rule per rung (platform section below).

Other confidence levels — pick by what a wrong kill costs. Multipliers at k=0/1/3: 90% → 2.30 /
3.89 / 6.68 (kills sooner, more false kills); 95% → 3.00 / 4.74 / 7.75 (default); 99% → 4.61 / 6.64
/ 10.05 (patient, burns more before acting).

Bayesian reading: with a uniform prior on conversion rate, an asset crossing rung k has posterior
P(true cost > target | data) EXACTLY equal to the confidence level (uniform-prior Gamma posterior
and chi-square bound coincide). The confidence pick is a decision parameter, not a stats habit:
95% = "act when 95% sure it's worse".

## Why an on-target asset survives (per rung — not over a lifetime)

The multiplier always exceeds k. An asset whose REALIZED pace holds target has spent `k × target`
at k conversions; its rung sits at `multiplier(k) × target`, strictly higher — it can never trip a
rung on realized pace alone. But pace isn't what the rule sees: each rung is an exact 5% test on a
random arrival process, and rungs compound. Simulated (Poisson arrivals in spend-time, 1e6 runs,
kill at first rung crossed), lifetime false-kill rate:

| rungs armed | on target | 10% under target | 20% under |
|---|---|---|---|
| 5 (k=0..4) | 11.8% | 7.8% | 4.6% |
| 10 (k=0..9) | 15.5% | 9.6% | 5.3% |
| 20 | 19.5% | 11.2% | 5.7% |
| 50 | 24.8% | 12.5% | 5.8% |

At 99% confidence the 10-rung figure drops to 3.8%. Consequences: arming MORE rungs costs more
false kills, so stop the ladder where the asset stops needing supervision; the ladder protects
genuinely GOOD assets, not marginal ones — an asset merely at target gets killed roughly one time
in six. If a false kill costs more than the spend it saves, raise the confidence level rather than
tightening the rungs; treat a rule-paused asset as a candidate for review, not a verdict.

## Practitioner cross-check

Field guidance lands at ~2-3× target CPA before pausing (AnyTrack, 2026) plus a minimum-spend
floor so one early expensive conversion can't trip the rule. The k=0 rung at 3× target sits at the
patient end of that field range; the ladder extends the same logic to k>0, where vendor guidance
is silent and naive rules do their damage.

## Meta platform reality (Marketing API v26.0, 2026-08)

Two evidence tiers: **field-observed** = hit in production while arming a kill ladder;
**docs-tier** = from references, not re-verified.

- **Cost conditions are blocked by SCOPE, not by action** — error 2703, subcode 2490336, message
  "Rules that turn off ads can't have cost conditions" (misleading). Probed on v26.0
  (field-observed):

  | entity_type | PAUSE | NOTIFICATION | CHANGE_BUDGET / CHANGE_BID |
  |---|---|---|---|
  | CAMPAIGN | accepted | accepted | accepted |
  | ADSET / AD | rejected | **rejected** | accepted |

  Any cost or ratio field (`cpa`, `cost_per_*`, `website_purchase_roas`) is unusable at ad-set and
  ad level for anything except budget/bid changes — even a notify-only rule. `cost per result > X
  → pause the ad set` cannot be created at all; this is the fact that makes the ladder necessary.
  Campaign scope has no such limit, but campaign `cpa` measures the OPTIMIZATION event, rarely the
  event you want to price. (UI exposes cost-per-result conditions — meta-ads/02 §9 — consistent
  with campaign scope being allowed.)
- **Invert to count form:** `spend / conv > price` ⇔ `spend > price × conv`. Spend and conversion
  COUNT are both allowed, so each rung becomes `spent > threshold AND <conversion_count_field> <
  k+1` (field-observed). Rules OR together; conditions inside one rule AND together.
- `spent` values are in **cents** (account currency minor unit, field-observed).
- Every rule needs `entity_type` (CAMPAIGN|ADSET|AD) or `id` in filters. Ad-set scope also covers
  ad sets created later (relaunches inherit it), and pausing at ADSET triggers no creative
  re-review (field-observed).
- Usable filter fields: `spent`, `impressions`, `clicks`, `unique_clicks`, `cpc`, `cpm`, `ctr`,
  `frequency`, `reach`, `results`, `link_click`, `offsite_conversion.fb_pixel_lead` /
  `_complete_registration` / `_purchase`, plus cost/ratio fields `cpa`, `cost_per_link_click`,
  `cost_per_unique_click`, `cost_per_mobile_app_install`, `website_purchase_roas` — all four
  subject to the scope table above. Pick the count field matching the payout event and objective —
  pixel fields above are web; app objectives count differently, iOS AEM/SKAN counts arrive
  deferred (tracker-ops/03 ATT).
- `attribution_window` is **deprecated** — passing any value fails the whole call with error 11
  (field-observed).
- `time_preset`: LIFETIME, TODAY, YESTERDAY, LAST_3D/7D/14D/28D…; LIFETIME matches the cumulative
  ladder (field-observed). `schedule_type`: DAILY, HOURLY, SEMI_HOURLY, CUSTOM (SEMI_HOURLY
  field-observed). Cap 250 rules/account — ladder costs one rule/rung (10 rungs = 4% of cap; two
  event ladders on one account = 8%).
- **Dry run before arming** (field-observed): set `execution_spec` to `NOTIFICATION`, `POST
  /<rule_id>/execute`, then read `act_<id>/adrules_history` — `results` lists matched object ids. A
  DISABLED rule evaluates to an empty result set, so arm it first or the dry run reads as "matches
  nothing". History lags a minute or two.

## Smarter actions than a flat pause

The ladder says WHEN an asset is provably bad. WHAT the rule does is a separate choice — pause is
the bluntest:

- **Alert tier before the kill tier.** Duplicate the ladder at a looser confidence (90%) with
  action NOTIFICATION: early warning reaches a human, asset keeps spending, the 95% copy still
  kills. Spend+count rungs carry no cost condition, so the scope ban doesn't touch them — cost is
  another 10 rules of the 250 cap.
- **Soft kill — cut budget instead of pausing.** Scope table allows cost conditions at ADSET for
  CHANGE_BUDGET/CHANGE_BID, so `cpa > 1.3-1.5× target → decrease daily budget ~20%` builds directly
  in cost form, no inversion. Check what you're pricing first: `cpa` is cost per RESULT, i.e. per
  the ad set's OPTIMIZATION event, often not the event the ladder prices — optimise on purchase
  while pricing installs and this rule silently guards a different number. Among the API filter
  fields there's no per-event cost field (UI lists per-pixel-event costs — meta-ads/02 §9; API-side
  availability unverified), so when the two differ, soft kill can only run on the optimization
  event; ladder stays the instrument for everything else. Field pattern: gated on ~48h over target.
  A bleeding asset slows and keeps learning instead of dying; if lagged conversions land there's
  nothing to relaunch — no LIFETIME stickiness, no lost history. Daily cadence, not SEMI_HOURLY:
  budget steps re-enter learning (traps below).
- **Kill the cause, not the symptom.** A fatiguing creative reads as expensive only after the
  damage; `frequency > X AND ctr < Y → pause` fires earlier. Calibrate X/Y off the account's own
  winner baseline, not a blog number; fatigue diagnosis lives in 02.
- **Gate the verdict on delivery existing.** Add an `impressions` floor to each rung so a
  CPM-spike night or a starved asset isn't read as a quality verdict. A separate CPM-spike ALERT
  (notify at ~2× baseline) routes auction anomalies to manual review instead of letting the ladder
  price them.
- **External engine as the ceiling.** The field's favourite qualifier — "over target for N
  CONSECUTIVE days" (field range 48h–3d) — isn't expressible in native rules: no consecutive-check
  memory, no tracker-truth counts, no cohort-maturity adjustment (exactly the fixes for the
  undercount and lag traps below). A cron script over the Insights API can do all three (nowcasting:
  tracker-ops/03); keep native rules as the always-on guardrail, let the script be the brain.
  Vendor platforms sell this layer if building isn't an option (15-min checks, per-rule
  attribution windows, relative period comparisons); the stack here already has the API tooling
  (meta-grey-ops/04).

## Traps that void the math

- **Learning phase.** CPA is volatile by design while an asset is learning; a rule pausing on
  day-1-3 cost resets the clock and wastes accumulated spend (Adamigo, Wevion 2026). The ladder's
  early rungs are deliberately loose for this reason — don't tighten to "act faster".
- **Conversion lag.** Judging before the payout event matures counts spend against unripe
  conversions, so every fresh cohort reads as a loser. Build the ladder on the FASTEST reliable
  event in the funnel, not the payout event, when the payout event lags hours-days; carry the
  payout judgement on cohorts instead (tracker-ops/03). With 7-day windows, extend the evaluation
  window.
- **LIFETIME sticks on relaunch.** With `time_preset: LIFETIME` a paused ad set keeps its lifetime
  spend/counts — relaunch it and the rule re-fires on the next evaluation even after the cause is
  fixed. Reset by duplicating the ad set (fresh lifetime), or use a LAST_N_DAYS window instead.
- **Event undercount kills good assets.** The rule believes the counter. Pixel-only web tracking
  loses events browsers block (CAPI recovery ~20-30% of lost events — third-party figure,
  directional; meta-ads/03 flags it unverified); in-app/WebView strips browser events. Reconcile
  pixel vs tracker BEFORE arming (tracker-ops reconciliation tree).
- **Event overcount is the mirror.** "All conversions" counts duplicate submissions, so the rule
  keeps assets it should kill.
- **Clustered arrivals break the independence assumption.** Batch-confirmed payouts (call-center
  confirm, COD waves, KYC batches) clump in time; a Poisson silence window reads clumping as
  failure and over-kills the early rungs. Run the ladder on an event that arrives one-by-one
  (front-end), carry the payout verdict on cohorts — or loosen k=0/1 below 95% on batch-confirmed
  funnels (negative-binomial territory).
- **Rule conflicts.** Overlapping rules fight — one owner per decision, review the whole set
  together.
- **Budget-step rules.** Large budget jumps CAN re-enter learning — Meta publishes no universal %
  (01, meta-ads/06); practitioner cap is ~20% per step, evaluated daily not continuously. Scaling
  rules and kill rules run on different cadences on purpose.
- **Not a scaling tool.** This ladder answers "is it provably bad". Scaling decisions need the
  marginal-CPA math in 01 plus `measurement-experimentation-ops`.

## Porting

Only `target_price` changes between verticals — multipliers are fixed. Nutra $20/confirmed lead →
k=0 at $60. iGaming $6/install → k=0 at $18. Crypto $150/FTD → k=0 at $450. What actually ports:
the event must be tracked completely, fast relative to the evaluation window, one row per real
outcome. If any of the three fails, fix measurement before arming any rule.
