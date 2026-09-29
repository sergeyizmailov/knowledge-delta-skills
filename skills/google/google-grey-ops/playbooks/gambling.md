# Playbook — Gambling, casino, betting, sweepstakes

Reviewed 2026-09-03. **Three rule changes landed between March and September 2026. Anything built from
this file must re-fetch the live policy pages first.** Policy context → `google-ads/09`.

## The change that invalidates old playbooks

**Sweepstakes casinos lost the social-casino certification path on 2025-10-28.**

Google reclassified dual-currency sweeps-coin models — where sweeps coins are redeemable for real-world
value — as **functionally real-money gambling**, not simulated gambling. Sweepstakes operators must now
complete **full online-gambling certification**: operator licensing, country-specific certification,
responsible-gambling messaging.

> This flipped a previously cert-light acquisition channel into a fully regulated one overnight. **Any
> account or playbook still targeting the old social-casino pathway for a sweeps-coin product is running
> on a dead assumption**, and the replacement path is materially slower and stricter.

**Social casino** — simulated gambling with **no opportunity to win anything of value** — remains
certifiable under the lighter track, in two country tiers:

- **Group 1**: Australia, Austria, Brazil, Bulgaria, Canada, Colombia, Czech Republic, and others.
- **Group 2**: Hong Kong, India, Korea, Malaysia, Taiwan, Thailand, Vietnam, and others — **social
  casino only, no real-money certification.**

🔺 The full current lists exist only on the live policy page.

## Certification

Per-country **online gambling application** in the Help Center; submit the website URL or app ID.
**A separate application is required for each individual country targeted.**

**2026-08-26: a revised, stricter certification process took effect** for online gambling,
gambling-related content, and certain non-casino games. All new applicants must use the revised forms.
**Treat this as the current baseline, not a legacy process.** [confirmed 2026-09-03,
support.google.com/adspolicy/answer/17258294]

**2026-09-14: the March 2026 EMEA tightening expands to all categories** under the policy — good-policy
-health gate applies globally across online gambling, social casino, and skill-based/prize games.
[confirmed 2026-09-03, support.google.com/adspolicy/answer/17199930 — date not yet reached, not yet
effective as of this review]

Structural rules from the 2026 changes:

- **One account cannot hold both an online-gambling and a social-casino certificate.**
- **Recertification is required on any material change** — new license, ownership change, expired
  authorization — or the certificate lapses.
- **"Good policy health" is a prerequisite before licensing proof is even reviewed.**
- **Manager accounts with a pattern of revoked certificates or violations across managed accounts risk
  losing the ability to apply at all.** This is the documented MCC cascade (`04`) — in this vertical it
  is explicit policy, not inference.

## Geo runnability

| Region | Status |
|---|---|
| **US** | State-by-state complexity for real-money online casino and sports betting. Social-casino cert is Group-1 listed but now **excludes sweeps-model products** |
| **UK** | Regulated; certification available for UKGC-licensed real-money operators |
| **EU majors** | Per-country national licensing feeds the country-by-country Google application |
| **LatAm** | Expanding — Brazil regulated 2025, Colombia established. Both Group-1 for social casino |
| **Belarus** | **Open from 2026-01-22** [16776280]: poker / sports betting / online casino with Ministry of Taxes and Duties licence; state lotteries = Office of the President or Ministry of Sport and Tourism. Google cert still required. Not a “CIS grey” free-fire geo |
| **Asia** | Mostly closed for real money. Group-2 permits **social casino only** |

**Prohibited outright** (non-exhaustive, verify live): Afghanistan, Algeria, China, Egypt, India,
Indonesia, Iraq, Korea, Malaysia, Pakistan, Philippines, Qatar, Saudi Arabia, Singapore, Thailand, UAE.

Note the tension: India, Korea, Malaysia, and Thailand appear on the Group-2 **social casino** list
while being prohibited for real-money gambling. The distinction is the product, not the country.

Daily fantasy sports needs separate certification in the **US**, **Brazil** (the ad must promote DFS
exclusively — no other gambling form in the same creative) and **Nigeria** (eligible state: **Lagos**).
[official: support.google.com/adspolicy/answer/15132179, 2026-08-27]

## Creative and landing page

Certified real-money ads must avoid guaranteed-win and odds-implying language, and must carry
**responsible-gambling messaging plus age-restriction disclosure on the landing page**. Same
unreliable-claims enforcement pattern as finance and health.

## Funnel and payouts

**click → registration → FTD.** Qualified-FTD definitions vary by network and geo exactly as in finance.

🔺 Network marketing figures, not realized averages:

| Program | Model | Payout |
|---|---|---|
| Right Partners | CPA | from **$35/FTD**, selected EU (Italy, Spain) |
| BigBetty Partners | RevShare / CPA / hybrid | RevShare to 60%, CPA to **€600** |
| Moon Partners | CPA | **€400** for PPC traffic specifically |

General tiering: higher-GDP geos command higher CPA; Tier 1 (Europe, North America, Australia) pays
best.

Optimize on FTD via offline conversion import, not registration (`google-ads/06`).
App/UAC gambling (3P events, never install-opt, name-as-router) → `08`.

## What breaks first

**Running sweepstakes-casino funnels under the pre-October-2025 social-casino assumption.** The
reclassification is recent enough that legacy accounts and playbooks built before it are actively
non-compliant right now, and remediation is a full online-gambling certification — slow, strict, and
per-country.

Second most common: applying for one country and serving several. **Each country is a separate
application**, and serving uncertified geos is a policy violation regardless of holding a valid
certificate elsewhere.
