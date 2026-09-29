# Playbook — US e-commerce (white)

Reviewed 2026-08-27. Feed mechanics → `google-feed-ops`. Structure → `../references/07`.

## Structure

Feed-driven, not keyword-driven. The structural unit is the **product group**, not the ad group.

**Custom labels are the primary profitability lever**, not a reporting convenience. Canonical schema
is in `google-feed-ops/01` — do not invent a second one: label 0 = margin tier · 1 = price band ·
2 = bestseller rank · 3 = seasonality · 4 = stock lifecycle.

**Build separate PMax campaigns per margin tier.** A single blended tROAS either underbids your most
profitable SKUs or keeps overspending on SKUs never profitable at that rate — the single
highest-leverage structural decision in the vertical.

## Target derivation

```
Break-even ROAS = 1 / gross margin        # 40% margin → 2.5 (250%)
Target ROAS     = break-even + profit buffer, then layered per margin tier
```

Low-margin SKUs get a **higher** tROAS floor; high-margin SKUs are allowed to spend more aggressively
at a **lower** tROAS.

> **Frequent silent error:** most agency guidance treats "margin" loosely. Verify the input includes
> **landed COGS + shipping + payment processing**, not wholesale cost. Everything downstream inherits
> this mistake.

## New-customer acquisition

Two modes: "bid higher for new customers" (blends, weights new higher) and "only bid for new
customers" (hard restriction).

Google's default detection scans **540 days** of account conversion history — anyone without a purchase
in that window counts as new.

> **Assign an explicit incremental value to new-customer conversions, not just the flag.** The toggle
> alone does nothing — the single most common misconfiguration of the feature.

## Refunds and returns

Use the **Conversion Adjustments API** — `RETRACTION` for a cancelled order, `RESTATEMENT` for a
partial return.

Restatements accepted up to **54 days** post-conversion [official: answer/7686280]. Google documents a
**7-day "autobidding readability"** window generally — 🔺 but the explicit statement that later
adjustments are **ignored by autobidding** appears **only in the Hotel Ads note** (answer/7686447).
Generalizing to Search/Shopping/PMax is practitioner inference, not documented. Restate inside 7 days
where possible; don't assume a day-8 restatement is worthless for bidding.

**Unadjusted refunds silently inflate reported revenue and corrupt tROAS bidding** — a top-tier
scale-capping failure that never surfaces in-platform.

## Seasonality and Q4

Seasonality adjustments are for **short windows — days, not weeks**. Base the uplift on the prior
year's actual CVR delta for the same window, not a guess.

> **Applying a seasonality adjustment across the whole of Q4 instead of just the BFCM days is a known
> misuse that distorts Smart Bidding calibration for the rest of the quarter.**

Lock total Q4 budget first, then explicitly reserve incremental spend for Cyber Five and the final
pre-Christmas week rather than letting daily budgets auto-cap mid-surge. Monitor pacing hourly on
BFCM, accounting for conversion lag when reading same-day numbers.

## Benchmarks — priors only

US all-industry Search averages [WordStream/LocaliQ 2026, US]: **CTR 6.64% · CPC $5.42 · CVR 8.18% ·
CPL $66.69**. CPC rose YoY for 87% of industries.

Product-category-specific CPC/CVR/ROAS splits were **not** found broken out in a current source —
apply category CVR direction qualitatively rather than inventing per-category numbers.

## DTC unit economics

| Metric | Range | Source note |
|---|---|---|
| AOV | $85–$92 global Shopify; top merchants >$109 | Vendor benchmark |
| CAC | **Contested** — $45 (Klaviyo 2024, US) vs median $156 / avg $242 premium (2026) | The 2024→2026 jump reflects iOS tracking loss and auction inflation. **Treat $45 as stale, the higher figures as directional and methodology-unverified.** Do not average them |
| LTV:CAC | 3:1–5:1 at 12 months, **scale-dependent** — a $100M brand can run 2:1 on spread overhead; a $2M brand needs ~4:1 | |
| CAC payback | 6–12 months standard; <3 cash-efficient; >12 unsustainable without capital | |
| Contribution margin | >35% is the healthy threshold | |

## The five mistakes that cap scale

1. Blended tROAS across a mixed-margin catalog instead of per-tier campaigns.
2. Fragmenting PMax/Shopping below the ~30–50 conversions/month floor.
3. Enabling new-customer bidding **without assigning a real incremental value**.
4. Never wiring refund and return conversion adjustments.
5. Treating seasonality adjustments as a quarter-long setting.

## What breaks first

**PMax's cross-channel black box misattributes existing brand-search demand as incremental wins while
simultaneously corrupting tROAS via unadjusted refund data.** The account looks like it's scaling
profitably in-platform while blended true margin quietly erodes — by the time it reaches the P&L, the
structure has already been scaled on the false signal.

Both halves are fixable and both are usually missing together: brand exclusions plus an exact-match
brand campaign (`../references/07`), and conversion adjustments within the 7-day bidding window.
