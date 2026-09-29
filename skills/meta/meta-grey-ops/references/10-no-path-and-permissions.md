# 10 — Restricted verticals: permission, conditions, or no path

Reviewed 2026-09-03.

Fetched live from `transparency.meta.com/policies/ad-standards/...` 2026-08-27 (JS shell — must render). **[official]** unless labeled. 🔺 = revised multiple times a year, re-check before spend.

**Q1/Q2 below decide whether to build anything.**

## Q1 — Permission required BEFORE spend (else policy violation, not a rejected creative — counts against account)

| Vertical | What must exist first |
|---|---|
| Real-money gambling (casino, sportsbook, poker, 3rd-party lottery, DFS, sweepstakes casino, skill tournament) | A&V approval + per-jurisdiction licence proof + declared intent per new territory |
| Crypto exchanges/trading, lending/borrowing, buy·sell·swap·stake wallets, mining **software**, investment solicitation (incl. affiliate sites) | Written permission + recognized regulator licence per targeted country |
| Dating services (any monetized matchmaking/aggregator) | Prior written permission — separate form `facebook.com/help/contact/1060028634014002` |
| Prescription drugs, online pharmacy, Rx telehealth, pharma manufacturers | Active LegitScript certification (or Meta internal review) + Meta authorization |
| CBD | LegitScript CBD certification + Meta written authorization |
| Political/social-issue/electoral in a designated country | Identity authorization + verified "Paid for by" disclaimer, live before ad runs |
| Financial products requiring local licence (insurance, mortgages, loans, investment products, credit cards) | Regulator licence proof, subject to Meta review |

Everything else: **self-compliance** (conditions, no submission — alcohol, weight loss, supplements, weapon-adjacent gear, subscriptions, MLM) or **prohibited** (no permission exists).

## Q2 — No path, any geo, any permission. Stop; do not iterate creative

- Tobacco/nicotine/vapes incl. nicotine-free "wellness" vapes, pouches, paraphernalia, tobacco-brand promo. "Not allowed in any context."
- Firearms, ammunition, explosives, weapon-mod accessories (suppressors, optics); 3D-print/CAM firearm files "regardless of context or poster."
- Payday loans, paycheck advances, bail bonds, any loan term ≤90 days.
- Binary options, CFDs, penny/bidding-fee auctions, ICOs.
- THC/psychoactive cannabis, ingestible or not.
- Adult sexual arousal products/services — toys, erotic content/costumes, non-surgical genital enhancement, strip clubs, escort/prostitution-adjacent, tantric/"orgasmic therapy."
- Dating involving monetary transaction (mail-order-bride models) — unpermittable even with a dating grant.
- Political/social-issue/electoral into the EU — structural geo-block since Jul 2025; only election-authority voting-logistics ads survive.
- Gambling of any kind into the 19 unsupported markets, any authorization level.

## Master status table

| Vertical | Status | Geo | Date |
|---|---|---|---|
| Real-money gambling | permission | all but 19 below | 🔺 |
| Social casino / free-to-play gambling-style | conditions, no auth if genuinely $0 value | same 19-market exclusion | 🔺 |
| Crypto trading/lending/staking/mining SW/solicitation | permission | ~25 countries, named licence path | 🔺 |
| Crypto: NFTs, storage-only wallets, hardware wallets, education/news, tax services | allowed | all | |
| ICO | prohibited | — | |
| Loans/credit cards/insurance, term >90 days | conditions | all, local licensing | |
| Payday / ≤90-day loans, bail bonds | prohibited | — | |
| Binary options, CFDs, penny auctions | prohibited | — | |
| Credit repair / debt settlement | conditions + possible licence verification | all | |
| Nutra / supplements | conditions — Meta's sole discretion on "unsafe" | all | |
| Weight loss | conditions | all | 🔺 |
| Cosmetic products/procedures/surgery | conditions | all | |
| Rx drugs / online pharmacy / Rx telehealth | permission (LegitScript) | US, Canada, NZ only | 🔺 |
| Telehealth (non-Rx-specific) | allowed | all | |
| OTC drugs | conditions | all | |
| THC/cannabis | prohibited | — | |
| CBD <0.3% THC | permission (LegitScript CBD) | US only | 🔺 |
| Hemp, no CBD, ≤0.3% THC | conditions | Canada, Mexico, US only | |
| Adult arousal products/services | prohibited | — | |
| Reproductive/sexual health (ED, contraception, fertility, IVF, abortion consult, gender-affirming surgery) | conditions, 18+ | all | |
| Dating services | permission | all post-approval | |
| Dating w/ monetary transaction | prohibited | — | |
| Tobacco/vaping/nicotine | prohibited, no exceptions | — | |
| Smoking cessation, WHO/FDA-approved only | conditions | where approved | |
| Alcohol | conditions, no Meta submission | banned by local law in some countries | 🔺 |
| Firearms/ammo/explosives/weapon mods | prohibited | — | |
| Weapon-adjacent (holsters, safes, hunting gear, apparel, safety courses, toys) | conditions, 18+ | all | |
| MLM / business-opportunity | conditions, high discretionary enforcement | all | 🔺 |
| Subscriptions / negative-option billing | disclosure conditions | all | 🔺 |
| Political/social issue/electoral | permission | banned in EU; extra rules US/BR/IN/IL/MX/UK/Washington State | 🔺 |

## Gambling — details that decide the build

Definition wide: "anything of monetary value as part of a method of entry and prize" — betting, lotteries, raffles, casino, fantasy sports incl. DFS, bingo, poker, skill tournaments, sweepstakes, trial-then-pay games.

**19 unsupported markets** (no gambling/social-casino ads, authorization irrelevant): Azerbaijan · Bangladesh · Cambodia · Egypt · Hong Kong · India · Indonesia · Korea · Kyrgyzstan · Malaysia · Mongolia · Myanmar · Pakistan · Philippines · Saudi Arabia · Singapore · Taiwan · Thailand · Vietnam. 🔺 List confirmed live 2026-08-27 (`meta-ads/07` §3 dates it 2026-09-25; not re-fetched 2026-09-29, unverified); "Feb 2026 expansion" date cited by practitioners not tied to a dated official announcement.

Allowed without permission: brick-and-mortar venue ads not facilitating online play · state/govt lotteries where advertiser is direct operator · retail prize promotions where gambling isn't core business · genuinely free-to-play non-simulating games.

Social casino carve-out: no auth needed if (a) no payout of monetary value ever, (b) 18+ targeting, (c) not the 19 markets.

Affiliates/aggregators not exempt — LP counts as gambling ad even with no on-page mechanic. 18+ floor everywhere. Article: `.../restricted-goods-services/gambling-games/`, Help Center 345214789920228.

## Crypto — exemption boundary

Permission: exchanges/trading (spot/margin/futures) · lending/borrowing · buy·sell·swap·stake wallets · mining **software** · investment solicitation and aggregator/affiliate sites.
No permission: tax services · education/news/events · NFTs/non-currency blockchain products · storage-only wallets · mining **hardware**.
~25 jurisdictions have named regulator/licence path (US: FinCEN MSB or NY BitLicense · UK: FCA · Singapore: MAS DPT under Payment Services Act…). 🔺 Whether unlisted countries are silently unsupported or merely undocumented is **not stated** — treat as unsupported until Meta publishes a path. Changelog: Apr 2026 / Nov 2025 / Jul 2024 / Mar 2023 — revised repeatedly. Article: `.../restricted-goods-services/cryptocurrency-products-and-services/`, Help Center 438252513416690.

## Health, weight loss, pharma

18+ mandatory: weight loss/gain, cosmetic. Banned outright: physical-appearance inferiority statements · close-up fat-pinching imagery · "results from a wearable alone" · permanent skin-colour-change claims · cure/heal claims for diabetes, herpes, thyroid, psoriasis, Ebola, cancer, autism, Alzheimer's, Parkinson's, ALS, HIV (symptom-management claims fine — that's the line) · clickbait/exaggerated timeframes without qualifiers.
Before/after imagery **explicitly allowed** for general cosmetic procedures. 🔺 For weight loss specifically, policy states neither yes nor no — negative-self-perception ban is what bites. Treat as high-risk, not carve-out.
Supplements: operative text = "unsafe substances, products or supplements, as determined by Meta at its sole discretion." No published rubric, no bright line to engineer against.

## Financial — prohibited vs conditional

Prohibited by name: payday/paycheck-advance/bail-bond/≤90-day loans · binary options · CFDs · penny/bidding-fee auctions · misleading student-loan consolidation/forgiveness claims.
Conditional: credit cards, insurance, loans >90 days — 18+, statutory disclosures, no PII/financial-info capture inside the ad itself (bank/card/routing numbers banned under Privacy Violations). US extra: investment-product ads may not invite DM interaction on/off platform.
No authorization needed: bank/insurer brand ads · news not offering the product · educational content · mere mention with no way to obtain.
Credit repair/debt relief (no dedicated article) — banned claims: erase/reduce debt by set amount/timeframe · stop all collections/lawsuits · "new government program" · delete credit-report entries · "new credit identity."
🔺 Forex and non-binary options: practitioner blogs claim a licence-authorization path; official Financial Services / Prohibited Financial Products pages name only binary options and CFDs, **silent on forex**. Restricted-pending-verification, neither confirmed prohibited nor permission-gated — check live before advising.

## Subscriptions

Ads collecting PII **prohibited** if any: no opt-in checkbox · pre-checked one · no clear cancellation instructions · price/billing interval not clearly shown (fine print/privacy statement/separate link). No submission — self-compliance + review-time detection. 🔺 Page's changelog showed only "Today" at fetch — new or just revised.

## Political — beyond authorization

EU: not allowed at all since Jul 2025, except election-authority voting-logistics ads.
US, Brazil, India, Israel, Mexico, UK: additional ban on vote discouragement, questioning election legitimacy, premature victory claims.
Washington State: total ban on WA state/local election content and Seattle legislation, authorization or not.
AI-generated realistic media must be self-disclosed; **from 2026-06-01 Meta auto-detects and labels** undisclosed AI media. Ads stored in Ad Library 7 years.

## 🔺 Legend / Gaps — do not guess

🔺 = revised multiple times a year, re-check before spend.

1. Full alcohol ad-ban country list (fetch truncated after Afghanistan, Brunei, Bangladesh, Egypt).
2. Forex/non-binary options — distinct authorization path or not: official pages silent.
3. Credit-repair/debt-settlement licence verification intake flow: undocumented.
4. Meta's "sole discretion" rubric for unsafe supplements: none published.
5. Weight-loss before/after imagery — allowed or banned: neither stated.
6. SIEP advertiser residency requirement beyond "located in or targeting": unclear.
7. Effective date of current 19-market gambling list.
8. Crypto-unlisted countries — unsupported or merely undocumented: unresolved.
