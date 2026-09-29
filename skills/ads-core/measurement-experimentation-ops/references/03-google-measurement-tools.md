# 03 — Google measurement tools

Reviewed 2026-08-27. Mode selection and validity traps are in SKILL.md and `01` and apply
identically. This file covers only Google-specific instruments and their limits.

Evidence classes (same scheme as `02`): thresholds/limits below without a tag are [PRACTITIONER]
— vendor blogs/help-centre snapshots at review time, not re-verified since; only [OFFICIAL] items
name a Google help page inline. Re-check any number before it drives a budget decision.

## Native Experiments — self-serve, no rep required

Unlike Meta's Conversion Lift, Google's campaign experiments need no account team.

- Built from a **draft**; splits traffic between original and draft over a defined range.
- **Max 25 drafts per account** — a new draft silently fails to publish at the ceiling.
- Supports geo-based splits (holdout vs test regions) and budget-level A/B at campaign level.

**PMax experiments**: explicit Google warning — do not run multiple experiments simultaneously
(they interfere, degrade the read). Run sequentially, minimize changes to the campaign under test.
You *can* change budgets mid-experiment; doing so undermines the read.

## Conversion Lift

Requires a **Google account team** to request — not self-serve for all account types. More
available for Video/Demand Gen than Search.

- Minimum 7 days, maximum 56 recommended. Studies under 14 days risk up to a 17% drop in measured
  accuracy for products with long conversion lag.
- **"Study Power"** = Google's own pre-check (conversion action, daily budget, expected lift size,
  volume, duration, holdout %) — tells you whether a conclusive result is possible before you
  spend anything. Run it first, always.
- Search Lift states a $10,000 minimum spend. Conversion Lift's threshold is unpublished, varies.

## Brand-search incrementality

eBay (Blake/Nosko/Tadelis 2015): pausing branded SEM by DMA → ROAS ≈ −63%, nearly all lost paid
clicks recaptured organically; Coviello et al. (2017) replicated on Edmunds.com (smaller, less
organically dominant brand) and found materially less-negative results. **Brand incrementality is
brand-position dependent — never apply "brand search isn't incremental" without a brand-specific
test.**

Cheap version: brand-exclusion holdout in PMax for ≥4 weeks while keeping a dedicated brand Search
campaign live, comparing **total account** conversions/revenue — not the PMax line item. Track
organic branded clicks in Search Console as secondary signal: real incrementality loss shows up as
organic brand clicks *not* recovering when paid brand spend is cut.

## PMax cannibalization measurement

PMax auto-bids into brand auctions you'd win anyway → its reported ROAS is systematically inflated
by conversions it didn't cause. Measure with a holdout on **account totals**, never the campaign's
own metrics. State the trap explicitly first: excluding brand makes PMax's own ROAS look worse, and
judged on that number the correct change gets reverted.

Overlap evidence: 67% of PMax campaigns overlap Search on search terms; Search wins CVR 84% of the
time on the identical query (Adalysis).

## Meridian — the MMM

`github.com/google/meridian`, PyPI `google-meridian`. Google's current OSS Bayesian MMM, successor
to LightweightMMM (now effectively legacy).

Advances: reach-and-frequency modeling · geo-level modeling · Search query-volume signal ·
**experiment calibration** (feeding Conversion Lift/geo-experiment results in to calibrate channel
coefficients) — the bridge between causal and modeled lanes: an MMM calibrated by a real
experiment is a different evidence class from one fitted to observational data alone.

🔺 Meridian GeoX reported announced May 2026, testing later in 2026. Single secondary source, no
official page located. Verify before depending on it.

## What you cannot measure

- **AI Overview placement performance** — AIO-placed ads fold into "Top Ads" with no segmented
  metric. Any claim about "our AI Overview performance" from standard reporting is unfounded
  (`google-ads/05`).
- **PMax and Demand Gen competitive overlap** — not exposed through Auction Insights like Search.
- **Search-term performance below Google's privacy threshold** — a quarter to half of click volume
  has no visible term, hidden queries skew worse (higher CPC, lower CTR). The visible report is
  systematically more flattering than reality.
- **Match-type-level attribution under AI Max** — structurally impossible; n-gram and asset-level
  analysis are the only viable lenses.
- **Per-combination RSA performance** — combinations report exposes impressions only.

Naming an unmeasurable thing as unmeasurable is a result. Do not substitute a proxy and present it
as the answer.

## Feasibility gate — Google edition

SKILL.md gate applies, with Google-specific reasons causal measurement is often unavailable:

- Conversion Lift needs a rep and, for Search Lift, $10k minimum.
- Low-volume accounts can't power a holdout — below ~30 conversions/month the underlying Smart
  Bidding is itself unstable, so the treatment is not stationary.
- The 2026-06-15 OCI cutoff may mean backend truth can't reach the platform at all on a new token,
  capping what any in-platform experiment can measure.
- Certification/geo gating in regulated verticals can make a clean geo holdout illegal, not merely
  impractical.

When causal is unavailable, say so and drop to the best affordable proxy — geo holdout, pre/post
against tracker truth, screening — **labeled directional.** The honest weaker method beats a
"causal" test that's silently contaminated.

## Two 2026 confounders that invalidate naive reads on Google

Check both before attributing any Google result to your own change:

1. **Market-level auction supply.** Optmyzr measured eligible auction impressions −12.3% YoY across
   21,425 accounts (Q1 2025 → Q1 2026). A pre/post spanning that shift measures the market, not
   your treatment.
2. **The 2026-08-17 budget-limited target enforcement.** Every tCPA/tROAS campaign flagged
   "Limited by budget" changed behavior on that date. A test straddling it has a structural break
   in the middle.

Neither surfaces as anything but a performance change. See `google-ads/02` and `/08`.
