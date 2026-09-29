# 00 — Evidence rules and maintenance

Research reviewed **2026-08-27**. Every consequential claim in this skill carries its own evidence
label and source inline — this skill depends on no file outside itself and its seven sibling skills.

## Evidence labels

Label material claims when the label changes what the reader should do with them:

| Label | Meaning |
|---|---|
| **official** | Google docs, Help Center, developer docs, or Google's blog |
| **google-reported** | A number Google states about its own products, unaudited |
| **independent-benchmark** | Third-party measurement — name the study, sample size, and period |
| **practitioner** | A named person or agency's observation. Name them |
| **unverified** | Single source, or a claim that could not be traced |
| **refuted** | Traced and found false. Say so loudly |

Preserve **source, date, geography, vertical, sample size, methodology** on every number. Never convert
a benchmark or a case lift into a platform rule or a forecast.

## Known-false claims — never repeat these

- **"Search CPC rose 12% YoY to $2.96 in Q1 2026."** Traced to three cited sources, none of which
  publish it. Content-farm propagation. See `08-benchmarks-diagnostics.md`.
- **The older 16-category WordStream benchmark table** (Advocacy / B2B / E-Commerce / Legal…) presented
  as current 2026 data. It is a different taxonomy vintage with 2–5× lower CPC and CTR.
- **PMax cannibalization statistics from ad-times.com** (22%→38% of industry spend; 31 of 47 accounts).
  Named quotes are from people not otherwise findable; reads as AI-generated.
- **"Search Max"** as a product name. It is **AI Max for Search**.
- **"The 30–50 conversions/month floor applies per asset group."** Category error, verified 2026-08-27:
  that is a campaign-level Smart Bidding benchmark, and every asset group in a PMax campaign shares one
  bid strategy. Google publishes no per-asset-group volume threshold (`01`, `07`).
- **"Conversion adjustments have a 55-day window."** The general window is **54 days**
  (answer/7686280). 55 days is the **Hotel Ads** carve-out (answer/7686447) (`06`).
- **"Adjustments after day 7 are ignored by Smart Bidding."** Documented **only** for Hotel Ads. The
  7-day "autobidding readability" window is general; the "ignored" consequence is not (`06`).
- **Optmyzr's own "11%" auction-supply figure.** Their published absolutes (45.9B → 40.25B, −5.65B) give
  **12.3%**. Cite the absolutes; the publisher's percentage is wrong (`08`).

## Claims that are folklore, not mechanism

State these as rules of thumb and never as documented triggers:

- The **15–20% per-change rule** for tCPA/tROAS/budget. Converged across practitioners, never
  confirmed by Google, no verifiable originator.
- **"~20 conversions/month per asset group, merge under 5."** Traces to a single vendor blog (Dotidot,
  2026-03-20) recirculated by content farms. No named practitioner with a stated sample publishes a
  per-asset-group number (`07`).
- **"Hagakure"** as a structure framework — community-coined, no official Google source uses it.
- The **"competitor URL as a custom segment"** trick — no official documentation endorses or mentions
  it.
- **`mobileappcategory::69500`** placement exclusion — widely cited, unverified as still functional.
- The **$50 → $200 → $350 → $500** billing threshold ladder — Google does not publish an escalation
  ladder.

## Volatile surfaces — re-verify before acting

Ranked by how fast they move:

1. **AI Max migration mechanics** — the 2026-09-01 window, and what controls survive it.
2. **Gambling certification** — three rule changes between March and September 2026.
3. **Financial services verification** by country — EU/EEA completed June 2026, AU/SG/TW pending.
4. **Google Ads API versions** — monthly releases, 4 majors/year, ~1-year support.
5. **Merchant API and feed attributes** — Content API sunset 2026-08-18.
6. UI labels and navigation paths generally.

## Minimum context before advising

Infer what you can; ask only for inputs that change the decision:

- Country, currency, vertical, and whether the vertical is **certification-gated** per geo.
- **Conversion lag** and conversion-window/attribution setup.
- Account timezone, and whether the **tracker's timezone matches it**.
- **Backend revenue, margin, lead quality, refunds** — without these, ROAS advice is guesswork.

**State assumptions and continue** rather than blocking, unless proceeding under any assumption would
be unsafe or make the work useless.

## Two questions to ask before any 2026 diagnosis

1. **Is this a market-supply effect rather than an account problem?** Optmyzr measured eligible auction
   impressions down **12.3%** YoY across 21,425 accounts (45.9B → 40.25B; Optmyzr's text says "11%" — its
   own arithmetic slip, see `08`). The same campaign producing fewer impressions is
   often the market, not the work.
2. **Is this the 2026-08-17 budget-limited target enforcement?** Any tCPA/tROAS drift on a
   "Limited by budget" campaign after that date is expected behavior, not a bug.

## Maintenance

When refreshing this skill:

- Re-run the volatile list first — decays fastest, carries most consequence.
- Keep the refuted list current — a dead statistic that keeps recirculating is worth more to flag than
  a new one to add.
- When a gap closes, move the claim out of unverified explicitly, note what closed it.
- When Google contradicts a practitioner source, **record both and name the conflict** rather than
  silently picking. Support replies are account-specific evidence, not universal rules.
