# 08 — Benchmarks, unit economics, diagnostics

Reviewed 2026-08-27.

**Read first:** every benchmark here is a **prior for sizing a test or sanity-checking an outlier** —
never a target, never a KPI to report against. Account's own trailing 90-day baseline is always the
correct comparison. Industry medians only tell you whether a fresh account's numbers are plausible.

## Refuted — do not cite

**"Average Search CPC rose 12% YoY to $2.96 in Q1 2026, the steepest increase since 2021."** Traced to
its cited sources — WordStream Q1 2026, a "Google Ads Transparency Report", and Search Engine Journal
aggregate data. **None of the three publishes it.** WordStream's real 2026 report is annual with a
**$5.42** overall CPC on a different taxonomy; there is no Google Ads Transparency Report publishing
pricing (the Transparency Center discloses ad content and advertiser identity, not CPC); no matching
SEJ report exists.

Propagates across SEO content-farm sites (digitalapplied, solutionbyz, get-ryze, silverbackmarketing)
citing each other. Treat as fabricated/AI-hallucinated.

**Lesson:** a precise-sounding statistic with a vague source list is the 2026 failure mode. Trace
before citing.

## The best-sourced longitudinal data

**Optmyzr State of Google Ads, Q1 2026** — n=21,425 accounts, 5 consecutive quarters Q1 2025–Q1 2026,
geo/vertical mix undisclosed:

| Metric | Q1 2025 | Q1 2026 | Direction |
|---|---|---|---|
| Eligible auction impressions | 45.9B | 40.25B | **−12.3% YoY** (−5.65B) ⚠ Optmyzr's own report says "11%" next to these figures; 5.65/45.9 = 12.3%. **The arithmetic error is the publisher's.** Cite the absolutes, not their percentage |
| CTR blended | 1.83% | 2.22% | **+21% YoY** |
| CPA blended | ~$12.58–13.57 | $13.27 | modest increase |
| CVR blended | — | 6.20% | softening from a 6.79% Q3 2025 peak |
| ROAS blended | — | ~428–464% | Q4 seasonally strongest |

**Read as an auction-supply story, not an execution story.** Same targeting/creative producing fewer
impressions is a market-inventory signal. Never diagnose a platform-wide contraction as a campaign
problem — the single most common false positive in 2026 audits.

Q2 2026 report (n=20,000+ accounts / 250,000+ campaigns) is gated, but visible teasers: one of 20
tracked verticals posted a **44% YoY ROAS swing** (vertical unnamed), a metric reversed after three
quarters of gains, and branded search saw "a 20-year pricing norm break". Treat the last as a prompt
to pull branded-CPC trend data from the actual account, not as a finding.

## Industry benchmarks — current WordStream/LocaliQ, US Search

Fetched from `localiq.com/blog/search-advertising-benchmarks/`, updated 2026-06-01. WordStream and
LocaliQ are the same data and brand family. **Sample size and collection period are not disclosed on
the page** — that is a genuine methodology gap, not a fetch failure. A circulating "13,000 campaigns,
Apr 2025 – Mar 2026, 10th edition" claim could not be traced to WordStream. Geo is implied US-only.

| Industry | CTR | CPC | CPL |
|---|---|---|---|
| Arts & Entertainment | 12.75% | $1.63 | $26.84 |
| Restaurants & Food | 6.83% | $2.05 | $30.57 |
| Travel | 9.32% | $2.14 | $44.70 |
| Automotive — For Sale | 8.28% | $2.27 | $44.26 |
| Sports & Recreation | 8.75% | $2.77 | $44.26 |
| Real Estate | 7.61% | $3.22 | $102.51 |
| Finance & Insurance | 9.83% | $3.39 | $74.44 |
| Furniture | 6.57% | $3.97 | $106.70 |
| Animals & Pets | 7.49% | $4.06 | $31.50 |
| Shopping, Collectibles & Gifts | 8.28% | $4.14 | $49.40 |
| Automotive — Repair/Service/Parts | 5.56% | $4.35 | $29.96 |
| Apparel/Fashion & Jewelry | 6.64% | $4.44 | $97.51 |
| Beauty & Personal Care | 6.75% | $4.62 | $39.25 |
| Physicians & Surgeons | 6.61% | $4.76 | $40.04 |
| Education & Instruction | 7.56% | $4.81 | $77.48 |
| Career & Employment | 5.88% | $5.81 | $67.36 |
| Business Services | 6.10% | $5.87 | $93.69 |
| Industrial & Commercial | 6.57% | $5.87 | $75.19 |
| Health & Fitness | 5.81% | $6.17 | $67.36 |
| Personal Services | 7.16% | $7.17 | $54.60 |
| Dentists & Dental | 5.66% | $8.00 | $72.97 |
| Home & Home Improvement | 6.47% | $8.33 | $90.92 |
| Attorneys & Legal | 5.87% | $9.87 | $131.63 |
| **Overall** | **6.64%** | **$5.42** | **$66.69** |

CVR overall **8.18%**, from Finance & Insurance 2.64% (lowest) to Animals & Pets 16.22% (highest).
The page notes cost per lead "decreased overall for the first time in five years" without naming the
baseline.

> **Do not use the older 16-category WordStream table** (Advocacy / B2B / Consumer Services /
> E-Commerce / Legal…) still circulating via secondary sites. It is a different taxonomy vintage with
> roughly **2–5× lower CPC and CTR**, and presenting it as current 2026 data is wrong.

🔺 Shopping, Display, and YouTube breakdowns were **not** re-verified against a current primary page.
Any Shopping/Display table from secondary sources should be treated as older, uncertain vintage.

**Databox live panel** (n>4,700 companies, monthly, geo/industry unsegmented, 2026-08-26): median CTR
4.70%, CPC $1.53, CVR 2.55%, cost/conversion $52.08, median monthly cost $2,827, median monthly
conversions 62.3. Useful for a plausible *range* rather than a point estimate.

**CAC / LTV:CAC** (FirstPageSage, Jan 2022 – Aug 2025, 29 B2B + 22 SaaS industries): B2B blended CAC
$86–$1,143; inorganic (PPC + paid social) CAC alone $81–$1,985, lowest in e-commerce, highest in
education. SaaS CAC $274–$1,450, lowest e-commerce SaaS, highest fintech SaaS. Source is an SEO firm
weighted toward SEO-heavy B2B clients and excludes email/events/direct mail — **not representative of
pure-PPC e-commerce**.

## The economics stack

Let `m` = gross margin fraction, `x` = desired post-ad contribution margin fraction.

```
Break-even CPA   = contribution margin in dollars per unit (price − COGS − variable fulfillment)
Break-even ROAS  = 1 / m
Target ROAS      = 1 / (m − x)
CPA              = CPL / (lead→sale rate)        # multi-stage: product of every stage rate
CAC payback (mo) = CAC / (monthly ARPU × m)
Contribution after ads = R − COGS − S − other variable
ROAS             = CVR × AOV / CPC
CPC              ≈ CPM / (1000 × CTR)
```

Worked: 40% margin → break-even ROAS 2.5. Want to keep 15% of revenue after ads → target ROAS
1/(0.40−0.15) = **4.0**.

**Gross margin must be after COGS, shipping, payment processing, discounts, returns.** Feeding a markup
number instead is the most common error, overstates headroom.

**LTV:CAC ≥3:1** is a sanity floor, not a target. **Always pair with payback period** — 3:1 at
24-month payback can starve a business worse than 2.5:1 at 4 months.

**Lag rule:** never judge a lead-gen cohort's CPA until the account's average sales cycle has elapsed.
At a 45-day cycle, the last 45 days of leads are structurally incomplete data, not poor performance.

### Funnel decomposition — which lever, and what not to touch

| Symptom | Lever | Do NOT touch |
|---|---|---|
| High CPM, CTR normal | Auction competitiveness, bidding into pricier inventory | Creative — not the bottleneck |
| Low CTR, CPC normal for the auction | Copy, headline relevance, asset coverage | Bid — raising it burns budget on the same weak ad |
| High CPC, CTR/QS fine | Ad Rank thresholds, competitive density, bid strategy | Landing page — CPC is set before the click |
| Good CTR, bad LPV rate | Page speed, broken redirect, mobile rendering, tag failure | Ad copy — the destination is the issue |
| Good LPV, CVR = 0 | **Tracking config first**, then offer/page mismatch | The bidding algorithm — it cannot optimize a broken signal |
| Good CVR, weak AOV | Pricing, bundling, upsell, product mix | Targeting — right buyers, cheap item |
| All green, ROAS still weak | AOV structurally too low vs CPA — shift budget to higher-AOV segments | Stop "optimizing" a structurally unprofitable SKU |

### Impression share math

`IS + Lost IS(budget) + Lost IS(rank) ≈ 100%` (Google notes these are estimates; the sum can be
inexact).

**Closing Lost IS (budget)** — a resource constraint. You are eligible and choosing not to spend, so
the withheld impressions resemble your current traffic and the multiplication holds:

```
extra impressions ≈ eligible × Lost IS(budget)%
extra clicks      ≈ extra impressions × current CTR
extra conversions ≈ extra clicks × current CVR
extra spend       ≈ extra clicks × current avg CPC
```

**Closing Lost IS (rank)** — a competitiveness constraint. **The multiplication does NOT hold.** Those
impressions are auctions you were losing, often on quality signals correlated with CTR — current
CTR/CVR will not transfer. Fix bids and quality components, not budget.

Budget against a rank problem wastes spend (you still will not win); bids while budget-constrained do
nothing (you already win what you can afford).

### Marginal vs average ROAS — the scaling rule most people get backwards

As budget rises, campaigns bid into progressively lower-intent inventory; revenue curve is concave.
**Average ROAS** is backward-looking, blended. **Marginal ROAS** = ΔRevenue / ΔSpend for the next
increment, always ≤ average once diminishing returns start.

**Profit-maximizing rule: keep raising budget while marginal ROAS ≥ break-even ROAS. Stop where equal.**

That spend level is **higher** than "maximize average ROAS" logic suggests — average ROAS is typically
highest at smallest spend, which is why optimizing toward it systematically under-scales profitable
accounts.

Google reports no marginal ROAS. Estimate it: raise budget by a known increment, hold everything else,
measure ΔConversion value / ΔSpend over a stable 2–4 week window long enough to clear learning
volatility. Budget experiments or a clean pre/post on a stable campaign are the practical tools.

### Blended vs platform-reported

Platform conversions use Google's own model, generous windows, cross-device modeling, dedup against
nothing. **Blended CAC = total marketing spend across all channels / backend-verified deduplicated new
customers.** Ground truth.

Reconcile by matching backend orders to channel via UTM/order-source/promo code, then compute
`attribution inflation = platform-reported / backend-verified`. Ratios of ~1.3–1.5× are commonly
reported, but this varies enormously by business model and window settings — **re-derive per account,
never assume the constant.** Use "Conversions (by conversion time)" so both sides are date-of-event.

## Test sizing

Standard two-proportion z-test. Inputs: baseline CVR, minimum detectable effect, α (0.05), power
(0.80).

Worked example (Evan Miller calculator): baseline CVR 10.2%, MDE to 13.2% (≈30% relative lift) →
**≈2,545 visitors per arm**. Smaller effects or lower baselines need dramatically more. This is why
testing on a sub-1% CVR account at typical budgets takes months for anything but large effects.

```
Required test spend per arm ≈ required sample per arm × current CPC
```

Practitioner triage rules — explicitly less rigorous, for triage not final judgment:

- Don't judge before ~30–50 conversions **per arm** (tracks Smart Bidding's own volume needs).
- Never judge before the campaign has exited Learning status.
- Never judge before one full conversion-lag cycle has elapsed — a campaign can show 50 conversions
  that are still revising upward.

Full validity treatment (SRM, peeking, contamination, multiple testing) →
`measurement-experimentation-ops`.

## Diagnostic decision tree

### Campaign not spending
1. Status — paused, ended, pending review, disapproved.
2. Lost IS(rank) high while Lost IS(budget) ≈ 0 → bids/quality, not budget.
3. Bid strategy ceiling — target set below what the auction requires.
4. Targeting too narrow; **check negative keyword conflicts — a broad negative silently kills a whole
   campaign.**
5. Billing holds or failed payments.

### Spending, no conversions
1. Conversion tracking status per action; confirm the tag actually fires.
2. Landing page reachability — click the real ad on the real device; redirect loops, geo-blocking.
3. LPV rate vs clicks — if LPVs ≪ clicks it is technical, not demand.
4. Attribution window — check "by conversion time" before concluding zero.

### CPA suddenly doubled
1. Decompose `CPA = CPC / CVR` and trend each separately — different fixes entirely.
2. Auction Insights for a new competitor around that date.
3. Change history — bid strategy edits, budget cap hits, new negatives, Merchant Center disapprovals.
4. Conversion action changes or a new value rule silently shifting the optimization target.
5. **Compare like-for-like periods**, not raw week-over-week, before declaring an anomaly.
6. **After 2026-08-17: check whether it is the budget-limited target enforcement** (`02`).

### Impressions collapsed overnight
1. Policy/disapproval sweep — many ads going "Limited" or disapproved at once.
2. Budget lowered, or a shared budget reallocated.
3. A tightened target collapsing rank-driven volume with no policy issue.
4. **Market-level auction supply** — Optmyzr shows double-digit quarterly swings platform-wide. Check
   before concluding it is account-specific.
5. Change History for a rule or script misfire, with exact timestamp.

**CTR fine, CVR zero** — almost always tracking. Re-run the tracking checks first. Then landing page /
offer mismatch. Then break CVR down by device and geo — CTR can be driven by a segment that
structurally cannot convert.

### Conversions reported, no backend revenue
1. Fixed placeholder value instead of dynamic value.
2. Test/internal traffic not excluded.
3. Double-counting across conversion actions.
4. Definition mismatch — Google counting a micro-conversion in "all conversions" while backend counts
   only paid orders. Check cost/conv vs cost/all conv.

## Columns that decide things

| Column | Why it matters |
|---|---|
| Search lost IS (rank) vs (budget) | The single most actionable split in the platform — different fixes |
| Search top IS / abs top IS | Position-specific competitiveness; abs top is the literal "am I ad #1" |
| **Click share** | IS can look fine while click share lags — a CTR-relative-to-position problem |
| **Search exact match IS** | The IS you would get if all keywords were exact at current bids. Isolates whether broad/phrase is diluting win-rate on core queries or genuinely expanding reach |
| **Conversions (by conversion time)** | Judge a past period honestly — the default column keeps revising upward |
| Conversions (current model) | Retroactive recount under the current attribution model; explains "numbers changed and nothing happened" |
| **Cost/conv vs cost/all conv** | Mixing these when setting tCPA is a classic error — an "all conv" denominator padded with cheap micro-actions makes CPA look artificially good |
| Value/conv | Catches AOV drift before it surfaces as a ROAS problem |
| Interaction / engagement / view rate | The Demand Gen and YouTube equivalents of CTR |

### Optimization score — the nuance that reconciles two studies

Official: "an estimate of how well your Google Ads account is set to perform", 0–100%. Google **makes
no claim that a higher score causes better performance.** Ginny Marvin: **"OptiScore has no influence
on the auction."**

Two studies, apparently contradictory, actually measuring different things:

- **Across accounts** — Optmyzr, n=17,380 accounts, global, presented GML 2024-08-23: accounts scoring
  90–100 show **+186% ROAS** vs sub-70 accounts, and lower CPA despite higher CPCs. The authors
  themselves attribute this to **confounding** — high-scoring accounts are more actively and
  competently managed, and that management drives the gap.
- **Within one account** — TheDoctorAds, n=6,071 campaigns across 29 accounts, $85.3M spend, 2026:
  median rank correlation of score vs CTR = **0.05**, vs CVR = **−0.05**. Effectively zero.

**Reconciled: chronically low account-level score is a weak general red flag; campaign-level score
differences predict nothing.** Never rank/prioritize campaigns by optimization score — rank by share
of zero-conversion spend and cost-per-conversion vs account median.

## Budget and pacing

```
Monthly cap        = 30.4 × average daily budget      (Google will not exceed it)
Daily overdelivery = up to 2 × average daily budget   (expected, not a bug)
Linear pacing target = monthly budget × (elapsed days / 30.4)
Pacing ratio = actual to date / expected to date
```

Weight the pacing target by a day-of-week index where the vertical is weekday- or weekend-heavy, or a
flat line will flag normal accounts as off-pace. Ratio >1.1 → tighten before the month-end cap forces
a shutoff. <0.9 → check Lost IS budget, disapprovals, or under-bidding.

**Fragmentation cost:** splitting near-identical intent across many campaigns pushes each below the
volume Smart Bidding needs to leave Learning. Symptoms: many campaigns permanently in limited-data
states, higher account-wide CPA variance, and any A/B inside the fragmented structure taking
proportionally longer to resolve.

## Seasonality

**Seasonality adjustments** are for short, sharp, known-in-advance conversion-rate events the algorithm
has no history for — **not** slow-building seasonal ramps, which Smart Bidding learns from the
account's own history.

**Resolved: there is no enforced hard cap on percentage or duration.** Google's page frames **1–7 days
as ideal** and warns effectiveness degrades **beyond 14 days**; a secondary source cites a −90% to
+900% UI range. Google's own guidance is to start at 10–15% and avoid exceeding 50% unless the data
strongly supports it. These are best-practice guardrails, not system limits.

Eligible: **Search, Standard Shopping, Display** — but only on tCPA or tROAS. **PMax and App (beta)
support any bid strategy. Travel is unsupported.**

**Q4/BFCM figures 🔺 — best available, all caveated:** Skai reports Cyber 5 2025 paid search spend +9%
YoY with CPCs **+9% YoY** (cross-platform, not Google-exclusive, sample undisclosed), with Black
Friday the highest-CPC day of the window and Thanksgiving the lowest. Tinuiti's BFCM recap was fetched
and **confirmed not to publish** Google Search or Shopping CPC/CPM at all (it does report YouTube CPM
−6% YoY on +27% spend). Do not cite the Lebesgue month-over-month figure as a YoY benchmark.

**Ramp method:** index last year's daily CPC/CVR curve around the event to this year's baseline, then
pre-build a daily budget ramp starting 1–2 weeks before the event so Smart Bidding is not hit with a
same-day step change. Apply the seasonality adjustment only to the specific peak days, not the ramp.
