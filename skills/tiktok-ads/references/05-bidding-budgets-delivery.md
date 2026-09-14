# 05 — Bidding, budgets, learning, delivery

Verified 2026-09-14 against TikTok's Marketing API docs and Ads Manager help centre.
Numbers here are the most perishable content in this skill — re-check before quoting one.

## Bidding: two strategies, plus a separate value axis

`bid_type` has **exactly two values**:

| `bid_type` | Ads Manager name | Mechanic |
|---|---|---|
| `BID_TYPE_NO_BID` | **Maximum Delivery** | No advertiser bid. Spend the budget, maximise volume of the optimization event |
| `BID_TYPE_CUSTOM` | **Cost Cap** | You set `bid_price` (impression/click) or `conversion_bid_price` (target CPA); TikTok optimises toward it and states plainly that actual CPA runs slightly above or below |

**Meta's bid vocabulary does not exist here.** There is no Lowest Cost, no separate Bid Cap strategy,
no `bid_strategy` field. An agent that reaches for `LOWEST_COST_WITH_BID_CAP` is porting.

**Value/ROAS bidding is a second axis**, on `deep_bid_type`, not a third `bid_type`:

| `deep_bid_type` | Name | Notes |
|---|---|---|
| `VO_HIGHEST_VALUE` | Maximum Value | No cap; maximise total predicted value |
| `VO_MIN_ROAS` | Minimum / Target ROAS | Requires `roas_bid`, valid range **0.01–10** |
| `MIN` | Double bid (app) | Holds install cost *and* target-event cost near target. Costs install volume |
| `PACING` | Automatic optimization (app) | Holds install cost near target, maximises target events; target-event cost runs higher than `MIN` |
| `AEO` | App Event Optimization | Standard, non-value |
| `DEFAULT` / `VO_MIN` | No deep bid / deprecated | |

Both value strategies require `optimization_goal: VALUE` and **force `bid_type` to
`BID_TYPE_NO_BID` underneath — you cannot combine Cost Cap with value optimization.** That
constraint kills a common plan ("target ROAS with a CPA cap as a safety net") before it is written.

**Bid ceilings scale by currency** the same way budgets do: `base limit × verification ratio`.
TikTok's own example: a CPC base limit of 30 on a JPY account (ratio 100) caps the bid at 3,000 JPY.

**Cost Cap behaves differently from Meta's, but be careful how you say it.** TikTok documents only
"actual CPA can be slightly higher or lower than the target" — no numeric tolerance band, no
published throttling rule. Practitioners consistently report TikTok's Cost Cap as *more*
delivery-limiting than Meta's at a low bid: it under-spends or stalls rather than overshoot,
especially during learning. That comparison has **no TikTok primary source** — treat it as a
practitioner prior, design so it does not have to be true, and check it against your own delivery.

## Value-Based Optimization: the unlock thresholds

VBO is not available until the account has fed enough valued events. These are documented:

| Destination | Unlock criteria |
|---|---|
| **Website (pixel)** | ≥**20 unique Complete Payment events with value + currency**, attributed to TikTok / Pangle / Global App Bundle, over **any consecutive 7 days** |
| **App (standard placements)** | ≥**30 unique Purchase events with value** over any consecutive 7 days |
| **App (Pangle-only)** | ≥**50 unique Purchase events with value**, **lifetime** (not rolling), plus separate allowlisting |

Placement eligibility is granular on web: ≥20 TikTok-attributed *and* ≥20 Pangle-attributed unlocks
any placement combination; only one side clearing the bar restricts you to that placement.

Once unlocked for a pixel or app, **VBO eligibility persists** — it does not have to be re-earned.
Default `vbo_window` is `SEVEN_DAYS`.

**Plan around this at intake.** "Optimize for ROAS" on an account with 8 purchases a week is not a
strategy, it is a wish. Compute expected valued events per week at the target CPA
(`01` intake #6) and, if it is under the threshold, say so and name the event you will optimize on
until it clears.

`tool_vbo_status_check` / `/tool/vbo_status/` answers this for a live account — check rather than
estimate when you can.

## Budgets: the real minimums

Minimum = **base × the currency's budget verification ratio**.

**Do not carry a ratio table in your head or into a plan.** `tiktok-ops/03` owns the full table, and
`ttops budget-check --currency X --level adgroup` computes the real bounds and decimal rules from
TikTok's own published figures. Run it before writing a budget for any currency you have not used
this week — it is the cheapest step in the whole workflow.

| | Campaign (non-Shop) | Campaign (Shop) | Ad group (non-Shop) | Ad group (Shop) |
|---|---|---|---|---|
| **Base** | **50** | 10 | **20** | 10 |
| ratio ×1 (USD, EUR, GBP, BRL…) | 50 | 10 | 20 | 10 |
| ratio ×100 (JPY, INR, RUB…) | 5,000 | 1,000 | 2,000 | 1,000 |
| ratio ×10,000 (IDR) | 500,000 | 100,000 | 200,000 | 100,000 |

Those three rows are the shape, not the lookup — across 56 currencies the ratios are **1, 4, 10, 50,
100, 1,000, 10,000 and 100,000**, and **nine of them take no decimals at all**: CLP, HUF, IDR, ISK,
JPY, KRW, PYG, TWD, VND. Three ratios have exactly one member each and are easy to miss — PLN ×4,
PHP ×50, VEF ×100,000. Ask `ttops budget-check`; do not infer.

"Shop" = `objective_type: PRODUCT_SALES` with `campaign_product_source: STORE`, or an ad group whose
`product_source` is `STORE`/`SHOWCASE`.

**TikTok's docs contradict themselves on the campaign floor** — the Budget guide says 20, the
per-currency table and the Ads Manager help centre say 50. Two sources beat one, and 50 matches the
UI. Use 50; flag the conflict rather than silently picking.

**Simplified Mode** ad groups (built in the UI's simplified flow) sit below the API floor: Traffic 5,
Community interaction / Lead generation / Conversions 10, everything else 20. Do not infer the API
minimum from a number you saw in the UI.

Maximum is `10,000,000 × ratio` in every currency. Lifetime budget = minimum daily × scheduled days.

## The one documented budget-change rule

> "If you are updating the budget at the ad group level or campaign level, the new budget should be
> at least **105% of the current spend**."

That is a floor on **decreases relative to spend already accrued**, and it is the only concrete
budget-change threshold TikTok publishes. `ttops budget` reads spend first and enforces it.

**The popular "changing the budget by more than 20% resets the learning phase" rule does not appear
in any TikTok document.** TikTok warns against "edits that retrigger the learning phase status"
without naming a field or a percentage. Treat the 20% figure as folklore imported from Meta. If you
follow it anyway, say that you are following a convention, not a documented rule — the distinction
matters when someone asks why the plan is shaped that way.

## Learning phase: TikTok contradicts itself, and you need both numbers

Two current TikTok help-centre pages, both verified 2026-09-14:

> **Learning Phase:** "Volatility starts to decline after about **25 campaign results or 7 days**
> from when the campaign enters the learning phase."

> **Troubleshooting auction ad delivery:** "give your ads a full **7 days to reach 50 conversions**".

**Do not quote one and suppress the other.** They are answering different questions and the gap
between them is the whole practical problem:

| | 25 results / 7 days | 50 conversions / 7 days |
|---|---|---|
| What it describes | When *volatility* starts to fall | What TikTok tells you to feed an ad group that is *underperforming* |
| What it is good for | Deciding when a number is worth reading at all | Deciding whether a structure can be fed at all |

Operationally, that resolves cleanly:

- **Do not judge anything before 7 days or ~25 results.** Earlier than that you are reading noise,
  and this is the number that kills premature verdicts.
- **Do not build a structure you cannot feed at ~50 events per ad group per week** if you want
  stable delivery. This is the number that kills over-splitting.
- State which one you are using when you justify a plan. "TikTok says 25" is half the record.

What is *not* true either way is Meta's framing — TikTok never describes a hard 50-conversion exit
gate, and porting Meta's rule wholesale makes you over-consolidate and mis-time verdicts.

TikTok names three things to avoid during learning: pausing the campaign or ad group; edits that
retrigger learning; and "unreasonable budget setting or creative volumes". None of the three is
quantified.

`skip_learning_phase` is a **real boolean field on the ad group object** — direct evidence that
learning is a formal backend state, not a UI narrative. Its eligibility conditions and effect are not
documented in prose. Do not set it because it sounds useful.

## Budget modes and CBO

`budget_optimize_on` (boolean, campaign level) is CBO — TikTok uses Meta's term verbatim.

- CBO on → the campaign carries the budget; **ad-group budgets are ignored**.
- CBO off → every ad group carries one.
- Campaign `BUDGET_MODE_DAY` forbids an ad-group **lifetime** budget.
- Continuous delivery (`SCHEDULE_FROM_NOW`) forbids an ad-group lifetime budget.

`BUDGET_MODE_DYNAMIC_DAILY_BUDGET` is an average daily over a week: daily spend ≤125% of the average,
weekly ≤ average × 7. Partly allowlisted.

**`AUTO_BUDGET_INCREASE` — the mechanic almost nobody knows.** On `BUDGET_MODE_DYNAMIC_DAILY_BUDGET`
Smart+ campaigns (allowlist-only), `budget_auto_adjust_strategy: AUTO_BUDGET_INCREASE` lets the daily
budget rise **20%, up to 10 times a day**, when utilization hits **≥90%**, resetting to the base each
night. Theoretical intraday ceiling ≈ 1.2^10 ≈ **6.2× the stated daily budget**. Documented only in
the Smart+ API reference. If you enable it, the number you told the operator is not the number that
can be spent — say so explicitly.

TikTok is actively steering toward CBO: from end of September 2026, non-CBO App Install VBO Smart+
campaigns can no longer be created via API, because TikTok says those configurations delivered
significantly worse.

## Delivery and pacing

`pacing`: `PACING_MODE_SMOOTH` (Standard — spread across the window) or `PACING_MODE_FAST`
(Accelerated — spend as fast as possible).

**Dayparting is a 336-character binary string**: 7 days × 48 half-hour slots. Granularity is **30
minutes**, not hourly. Blogs claiming hourly are wrong, and a 168-character string will be rejected.

`frequency` (cap) and `frequency_schedule` (window in days) are separate ad-group fields.

**Delivery diagnostics** ("Not delivering", "Insufficient budget", "Audience too narrow") are UI-only
labels with no published threshold. The practitioner reading: *not delivering* = inactive, rejected,
or outside schedule; *insufficient budget* = budget too low to win auctions at that market's CPM;
*audience too narrow* = targeting and exclusions have cut reach below a viable floor. No TikTok
source defines "too narrow" numerically — do not quote a number for it.

## Scaling

Nothing about scaling is documented by TikTok beyond the 105% floor. What is known:

- Vertical (raise the budget) re-enters volatility; TikTok says so without quantifying it.
- Horizontal (duplicate winners) is the field default, but **TikTok's own best-practice guidance
  advises against repeated daily ad-set duplication** — a direct conflict with a widely taught
  affiliate tactic (`11`).
- The 105% floor means you cannot cut a budget below 105% of what has already been spent in the
  period. Plan reductions as pauses, not as cuts, once spend has accrued.

Derive the ladder from the account's own conversion volume rather than a fixed percentage, and
confirm a difference is statistically real — bigger than normal day-to-day noise at that sample
size — before acting on it. That kill/scale math for small samples is the same on every ad
platform; nothing about it is TikTok-specific.

## What to check before writing budget numbers into a plan

1. Account currency from `/advertiser/info/` — never assume USD.
2. `ttops budget-check --currency X --level adgroup` for the real floor and decimal rules.
3. Expected conversions/day at target CPA — can the budget buy a readable result inside the horizon?
4. If value optimization is in the plan: does the account clear the VBO unlock threshold?
5. State the total daily spend to the operator in **major units with the currency named**.
