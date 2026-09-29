# 02 — Bidding, auction mechanics, Quality Score

Reviewed 2026-08-27. Verify targets/minimums live — Google revises them.

## THE 2026-08-17 CHANGE — check this first on any post-August audit

Google now enforces closer adherence to the **stated** target for **budget-limited** tCPA/tROAS
campaigns. Official example: *"If your campaign's Target CPA is $10, but your recent actual CPA
performance is $5, your campaign will deliver more closely to a $10 actual CPA."*

Previously a budget-limited campaign could overperform its target indefinitely — algorithm optimized
inside the budget constraint rather than driving toward the literal number.

- **Affected:** Search, Shopping, PMax, Demand Gen, Travel (Google Ads, SA360, DV360).
- **Exempt:** App, Video Reach, Video View. Display and Hotel already worked this way.
- **Only campaigns flagged "Limited by budget."** Unconstrained campaigns are unchanged.

Practitioner reaction: Joey Bidner — accounts that *intentionally* ran artificially low tROAS/high tCPA
to farm old overperformance are now exposed. Nils Rooijmans — efficiency loss wherever stale targets
sit untouched. Xavier Mantica — open question whether the enforced CPA gets hit via inflated CPCs, with
knock-on auction effects.

Google shipped a **Bid Target Adjustment Tool** (2026-07-06) that one-click applies recent actual
performance as the new target.

**Required audit sequence after 2026-08-17:**

1. Find Search/Shopping/PMax/Demand Gen/Travel campaigns flagged "Limited by budget" on tCPA/tROAS.
2. Compare actual CPA/ROAS over a full conversion cycle against the literal target.
3. A large gap (target $50, actual $35) is **expected drift, not a tracking bug**. Do not chase it as
   a measurement problem.
4. Fix by either resetting the target to the performance that was actually the business goal, **or**
   raising budget so the campaign leaves "Limited by budget" and enforcement stops applying.
5. Optmyzr's guidance: observe days 1–3 without touching anything; make corrections in weeks 2–4 on
   post-change data; never chain adjustments.

## Ad Rank

`Ad Rank = f(bid, auction-time ad quality, competing bids/ads, search context, expected impact of
assets and formats)`

Auction-time quality is a **real-time recomputation** of expected CTR / ad relevance / landing page
experience — not the cached 1–10 QS in the UI. Most misunderstood point in the platform: visible QS is
a diagnostic snapshot; what Google actually bids on is richer and more current.

Assets feed Ad Rank **independent of bid** — that is the official mechanism behind asset coverage
lowering effective CPC.

### Thresholds

Set **dynamically per auction**, not fixed per account. Raised by:

1. **Low ad quality** — the bar rises specifically for you.
2. **Higher position** — top and absolute-top have separately higher bars. This is why outbidding
   position 4 does not buy you position 1.
3. User/context signals (location, device).
4. Nature of the query (commercial intent, specificity).

**Reserve price:** if yours is the only ad clearing the threshold, you pay **the threshold**, rounded
up — not a discount. A zero-competitor auction can still be expensive.

### Diagnosing a threshold block

Signature: **impression share does not respond to bid increases.** $5 → $8 with no IS movement means
the constraint is quality, not bid or budget — further bidding is pure waste. Check status "Eligible
(limited)" and the "rarely shown due to low ad rank" keyword message.

Fix order: expected CTR (copy, asset relevance) → ad relevance (tighter keyword↔ad↔ad-group theme) →
landing page experience. You generally cannot bid past a threshold block, because the threshold rises
as quality falls.

## Quality Score

1–10, **keyword level only**, three components each scored vs other advertisers over a trailing
**90 days**: expected CTR (normalized for position), ad relevance, landing page experience.

Official, verbatim: **"Quality Score is not an input in the ad auction"** and **"should not be
optimized or aggregated with the rest of your data."** Omits device, location, time of day, and asset
signals — all of which *do* feed real auction quality, which is why a keyword can sit at QS 4 and
still perform profitably under Smart Bidding.

**Component weighting** [Adalysis, reverse-engineered, not Google-confirmed]: expected CTR ≈39%,
landing page experience ≈39%, ad relevance ≈22%. Landing-page work carries ~1.8× the leverage of
ad-relevance tightening — the opposite of most people's instinct, since ad relevance is the easiest
thing to edit.

**CPC impact** [Adalysis, directional only — magnitude varies by vertical and auction density]:
QS 3→6 swings CPC roughly 84 percentage points (from ~67% above baseline to ~17% below). QS 8 ≈ 37%
discount vs QS 5; QS 4 ≈ 25% premium. Non-linear and asymmetric — 7→8 moves more than 5→6.

**Does it still pay?** Use QS to **triage**, never to optimize toward. Jyll Saskin Gales (ex-Google):
*"Stop trying to get a 10/10. A 7 is a really good score. Even a 6 is fine."* Optmyzr reports the
common disconnect — accounts hitting ROAS targets while broad-match keywords show red QS, because
broad match deliberately expands into individually-low-scoring queries that convert in aggregate.

Method: find the sub-component that is "Below average" across a *cluster* of keywords, fix that root
cause (usually LPE or a mismatched ad-group theme), stop. Context: ~78% of Google Ads spend now runs
on Smart Bidding or PMax [google-reported via Optmyzr, directional].

## Bid strategies

**Rename, June 2026:** "Maximize conversions with a Target CPA" → **Target CPA**; "Maximize
conversion value with a Target ROAS" → **Target ROAS**. Mechanics unchanged; old and new names are
the same strategy.

| Strategy | Official minimum data | Failure mode |
|---|---|---|
| **Maximize Conversions** | None stated; usable from launch | Most forgiving. Under ~20 conv/mo expect erratic swings. |
| **Maximize Conversion Value** | Demand Gen: ≥50 conv w/ value in 35d incl. ≥10 in last 7d, **or** ≥100 across all DG campaigns in 35d | Degenerates into Maximize Conversions plus noise if values are a flat placeholder. |
| **Target CPA** | Officially usable with **no conversion history**; evaluate over 30d with **≥30 conversions** | Under 30 conv/30d the target is a soft goal, not a controlled outcome. Subject to the Aug-17 enforcement. |
| **Target ROAS** | Search/Shopping **≥15 conv/30d** · Display ≥15 w/ values · App ≥10/day or 300/30d · Demand Gen ≥50/35d · Hotel ≥50/week | Below minimum it will not stabilize. Needs *differentiated* values or "average ROAS" is meaningless. |
| **Maximize Clicks** | None | Bootstrap strategy for zero-history campaigns. Cap too low starves delivery. |
| **Target Impression Share** | None (position goal) | Without a Max CPC cap it optimizes for *share*, so it will bid arbitrarily high. |
| **Manual CPC** | — | Legacy. eCPC retired for Search/Display in **late March 2025** (sources vary between the weeks of Mar 24 and Mar 31 — treat as late March 2025); unmigrated campaigns silently became plain Manual CPC. **eCPC survives for Shopping only.** |
| **vCPM / tCPM / CPV** | — | Awareness and video only. Never for direct-response Search/Shopping. |

## Operational rules

### The 15–20% rule — folklore-grade

Convention: change a live tCPA/tROAS by **≤15–20% per step**, then wait one to two full conversion
cycles (not calendar days). Same ceiling commonly applied to daily budget changes.

**No Google documentation states any numeric threshold for a "significant" change.** Converged across
independent practitioner sources, never confirmed. Present it as a rule of thumb, never as a
mechanical trigger. The "Vallaeys origin" attribution is unconfirmed.

### Learning period

No official numeric duration exists. The UI "Learning" label commonly clears in ~7 days, but real
stabilization often takes **2–4 weeks**, longer when the conversion action has multi-day delay — the
algorithm cannot evaluate a bid until the delayed conversion lands, so effective learning outlasts
the label.

Better stability signals than the label: CPA/ROAS holds a consistent band ≥7 consecutive days ·
daily conversion volume stops swinging · impression share settles.

Resets/extends learning: bid strategy type change · target change beyond ~15–20% · large budget
change · adding/removing/reweighting a primary conversion · a data exclusion over a large window.

### Portfolio strategies

Pool multiple campaigns' conversion data under one goal. The distinct capability: a portfolio can
carry a **Max CPC cap while running Smart Bidding**, which a standalone tCPA/tROAS campaign cannot.

Use for: campaigns chasing the same real-world goal (same product line split by geo) · low-volume
campaigns needing pooled learning · new launches inheriting a learned bid distribution instead of
cold-starting.

Risk: pooling dissimilar campaigns (different margin, different funnel stage) pushes spend toward the
easiest-to-convert campaign at the expense of strategically important ones.

Google-reported +13% conversions for Shared Budgets + Portfolio Bid Strategies together on Search —
vendor-reported average, measures the *combination*, not either alone.

### Seasonality adjustments vs data exclusions

| | Seasonality adjustment | Data exclusion |
|---|---|---|
| Purpose | Pre-warn of an **expected future** conversion-rate spike/dip (flash sale, launch, conference) | Stop **broken historical** data (tag outage, bulk erroneous conversions) corrupting the model |
| Direction | Forward-looking, set before | Backward-looking |
| Duration | Ideal 1–7 days; official warning it "may not work as well" beyond **14 days** | No cap, but frequent/long use "could negatively impact" performance |
| Support | Search/Shopping/Display on tROAS & tCPA; PMax and App on all strategies. **Not Travel.** | Account/bid-strategy level, any strategy |

Official warning: use seasonality adjustments **only** for major expected changes — Smart Bidding
already handles routine weekday/weekend seasonality. Applying an exclusion causes bids and spend to
drop temporarily before readjusting.

Combined pattern: seasonality adjustment *during* a known spike so bidding doesn't under-bid into it;
data exclusion *after* if the event produced non-representative data.

### Bid strategy report

Available for tCPA, Max Conversions, tROAS, Max Conversion Value. Surfaces the dimensions the
algorithm bids up/down on (device, location, day, hour, keyword, remarketing/Customer Match list) —
green = more likely to convert, red = less.

Also exposes **conversion delay** — check this number before judging whether a strategy has
stabilized. Empty report on a low-volume campaign is diagnostic of insufficient data density, not a
bug.

## Target mathematics

```
Break-even ROAS = 1 / gross margin
Target ROAS     = 1 / (gross margin − target net margin)
ROAS            = AOV / CPA        CPA = AOV / ROAS
```

Gross margin must be **after COGS, shipping, payment processing, discounts, and returns**. The most
common error is feeding a "40% markup" number instead of true landed gross margin, which overstates
headroom. Break-even ROAS run as a target produces zero profit by definition — put the *target* ROAS
in the field, not break-even.

Initial tCPA: take trailing 30–90d actual CPA from Maximize Conversions or Manual CPC, set the target
**at or slightly above** it. Setting it below current actual on day one produces exactly the
budget-limited enforcement volatility above.

### Conversion value rules

Multiply reported conversion value at auction time, conditioned on audience, device, location, or
travel itinerary. Constraints: **at most two condition types per rule**, and **every value rule in
the account must share the same primary condition type** — you cannot mix a location-primary rule
with an audience-primary rule.

Because tROAS and Max Conversion Value bid directly off reported value, an active rule changes
bidding immediately with no separate opt-in. **Gotcha:** value rules shift the average reported
conversion value, so a tROAS target calibrated before the rules drifts from real-world ROAS after
them. Re-derive the target; do not leave it.

## Budget mechanics

- Daily budget is an **average**, not a ceiling.
- **2× rule**: up to 2× the daily average on a single high-demand day.
- **30.4× monthly cap**: monthly spend will not exceed 30.4 × daily budget. Excess is refunded as
  overdelivery credits.
- Never flag a single 2× day as a pacing bug — check the trailing-30-day total against 30.4× first.

**Shared budgets** reallocate dynamically toward whichever campaign has the strongest demand, not
evenly. Failure mode: one strong campaign eats the pool and starves valuable weaker ones. Use only
across campaigns of genuinely interchangeable priority.

### Budget-limited vs bid-limited

- **Lost IS (budget)** = eligible searches missed because budget ran out. Spend-capacity problem.
- **Lost IS (rank)** = Ad Rank didn't clear the threshold. Bid/quality problem.

**Fix rank-driven loss first.** Better quality lowers effective CPC, which frees real budget headroom
without adding spend; then re-measure remaining Lost IS (budget).

Misdiagnosis wastes the whole next cycle in both directions: raising budget against a rank constraint
burns spend faster at a losing position; raising bids against a budget constraint does nothing,
because you already win everything you can afford.

**The clearest "add budget" signal in the platform:** CPA/ROAS at or better than target **and**
meaningful Lost IS (budget).

Scaling budget: apply the same ≤15–20%-per-step, wait-a-cycle discipline rather than 2–3× jumps.

## Auction Insights

Impression share · overlap rate · outranking share · position above rate (Search) · top of page rate
(Search) · absolute top of page rate (Search). Shopping exposes only the first three.

Limits:

- **No rows populate below 10% impression share** — that absence is itself informative.
- Impression-weighted and directional; reflects the keyword/campaign set in view, not the account.
- **PMax and Demand Gen competitive overlap is not exposed** — a known blind spot when auditing
  PMax-heavy accounts.
- "Top of page" can still sit below an AI Overview block on the modern SERP.

Use it as a diagnostic for *why performance changed* — cross-reference a CPC spike against a rising
overlap rate and position-above rate from a named competitor to decide between bidding up, working
quality, or waiting out a time-boxed competitor push.

## Edge cases

- **Brand defense pattern**: dedicated brand campaign on Target Impression Share (absolute top,
  90–95%) with a Max CPC cap, kept out of the non-brand tCPA/tROAS portfolio. Brand economics
  (near-100% relevance, low CPC ceiling) dilute a shared non-brand target in both directions.
- **Bid simulators**: Smarter Ecommerce finds they project off only the trailing **7 days**, ignore
  seasonality, trend, and competitor moves, and can deviate **±50%**. A countervailing +18% CTR /
  −15% CPC claim exists but is vendor-reported with no published methodology. Directional sanity
  check only; disregard entirely if conversion tracking changed in the last 14 days.
- **Zero-conversion campaigns**: with no history, Smart Bidding has no baseline for what a conversion
  or a realistic bid looks like — expect erratic swings and spend on tangential queries. Launch on
  **Maximize Clicks** with a sane Max CPC cap (or Manual CPC), accumulate real conversions, then
  switch. Never start a no-history campaign directly on tCPA/tROAS.
- **"Bid strategy stacking"** as a named methodology is unconfirmed — no authoritative source found.
  What is real and functionally similar: a Max CPC cap layered on Target Impression Share, or a
  portfolio Max CPC ceiling over a pooled tCPA/tROAS goal.
