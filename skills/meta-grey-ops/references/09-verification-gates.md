# 09 — Verification gates (Meta)

Reviewed 2026-09-03.

Researched 2026-08-27. Labels: **[official]** with article ID · **[practitioner]** · **[unverified]** · 🔺 = re-verify before acting. **Meta publishes no SLA for any gate** — every day-count below is a practitioner estimate unless [official], and estimates conflict with each other.

## Gate summary — trigger → unlocks → order

| # | Gate | Trigger | What it unlocks | Order |
|---|---|---|---|---|
| 1 | Business Verification | Prerequisite, not event-fired | Higher spend limits, dev/WhatsApp features, Commerce/Shops eligibility, most category authorizations | 1st — everything else assumes it |
| 2.1 | Identity ("Confirm your identity") | Unpublished — new payment instruments, spend surges, policy flags [practitioner] | Account recovery / integrity clearance | Fires opportunistically, front-load if vertical is financial |
| 2.2 | SIEP identity confirmation | Country-selector gated | Political/social-issue/elections ads | Start day 1 (postal mail = long pole) |
| 2.3 | Financial-advertiser check | Meta's discretion, "ongoing review" | Financial-products ads | Parallel with 1 |
| 3 | Beneficial owner | ≥10% share ownership | Commerce/Shops eligibility (same rule, not a separate revenue gate) | With 1, if Commerce in scope |
| 4.1 | SIEP (politics) | Self-serve; broader than politics — healthcare/climate/immigration copy catches it | Political/social-issue ad serving | Day 1, parallel |
| 4.2 | Financial products auth | Insurance/mortgages/loans/investment/credit cards | Ad serving for these verticals | Regulator number is usually the blocking dependency |
| 4.3 | Gambling & games auth | Any monetary-value entry/prize mechanic | Ad serving for that territory/portfolio/account | Parallel with 1, file before any ad exists |
| 4.4 | Crypto auth | Trading/lending/enhanced wallets/mining SW/solicitation | Ad serving for that country | Parallel with 1, file before any ad exists |
| 5 | Payment method verification | New billing instrument | Spend capacity (not itself a policy hold) | Before heavy spend |
| 6 | Ad-level review | Every ad, every time | Independent of all gates above — authorization never immunizes a creative | Last, always |

## 1. Business Verification

Path: Business Suite → Security Center. [official 1095661473946872]. NOT the paid "Meta Verified" badge.

| Document | Validates | Note |
|---|---|---|
| Articles/Certificate of Incorporation | Legal name | |
| Business registration/license | Legal name | |
| Government business tax document | Legal name | Self-filed tax docs rejected |
| Business bank statement | Legal name + address | |
| Utility bill | Address/phone only | Cannot validate legal name |

[159334372093366] Must show legal entity name **as entered in BM** (not DBA), plus registered address/phone. Not expired. Redact unrelated personal IDs. 19 accepted languages, else stamped translation.
Alternate: business bank account verification via 3rd-party vendor, marked deposit, re-enter amount, max 3 attempts then resubmit. [561730264791590] 🔺 source article was China-locale variant — treat deposit-match as shape, not universal flow.
**Official rejection reasons** [2342133782492969]: false/misleading info · verifying a business you don't own/represent · circumventing review · **website fails to load / no HTTPS / broken links** (cheapest to pre-clear, most often missed).
No published attempt cap or cooldown for resubmission. Failed business verification blocks the gated feature only — does not auto-suspend. False info/impersonation → permanent denial or suspension [1095661473946872].
🔺 [unverified, mutually inconsistent]: domain verification 1–2 biz days · doc review 3–7 days (up to 10) · ~24h cooldown before resubmit · throttling after ~4 rejections · "file Request Review instead of 3rd resubmission." None confirmed.

## 2. Identity / selfie — two separate programs, do not conflate

**2.1 General "Confirm your identity"** — account recovery/integrity risk. One government ID (licence/national ID/passport/birth cert, name+DOB or name+photo) **or** two non-government docs (student/library/refugee card, employment letter, diploma, loyalty card — one must carry DOB/photo, names match). Physical redaction OK, digital alteration not. [159096464162185]. Notary-form backup path exists [346296532662771]. Trigger logic unpublished, no fixed recurrence [practitioner].
Selfie/liveness video: matched against profile photos or submitted ID; Meta says not used for face recognition, deleted after "a limited period" — no number published [unverified].

**2.2 SIEP identity confirmation** (§4.1) — govt photo ID issued by country you advertise in + residential address confirmed by a physical postal code Meta mails. 🔺 Country-selector gated, exact per-country text not extractable live.

**2.3 Financial-advertiser check** (§4.2) — live selfie/video vs submitted ID, business and/or individual level at Meta's discretion, "subject to ongoing review" [unverified, no primary article; recurrence claim directional].

## 3. Beneficial owner

**≥10% of total shares** = beneficial owner, must be documented [193400874040813]. Per owner: govt photo ID front+back (passport preferred) · formation doc naming owner · company TIN · possible extra tax form by residence.
🔺 **No "$50k lifetime Shops revenue" trigger exists** — two independent passes found none. Commerce eligibility gates on Business Verification + trustworthiness [1627591223954487] = same ≥10% rule, not a second threshold. Practitioner-cited triggers (~$5k lifetime ad-spend) are a different metric. Not completing it: Commerce/Shops "Ineligible," non-Commerce ads keep running.

## 4. Category authorizations

### 4.1 SIEP
Self-serve, not written permission. US proof: govt photo ID + address via mailed postal code. Mandatory "Paid for by" disclaimer matching campaign-finance-registered entity name. Ads stored in Ad Library **7 years** [208949576550051, transparency.meta.com].
**EU: Meta stopped serving political/social-issue/electoral ads entirely from Oct 2025** — do not build an EU flow, it's moot [official, about.fb.com 2025-07].
🔺 Postal mail = slowest gate, ~5–10 biz days for code alone, 2–3 weeks total [practitioner, no SLA]. Start day 1.
🔺 2026: AI-content disclosure required when a real person/place/event is generated/materially altered [paraphrase, unverified wording].
🔺 "60 days reconfirm identity / 21 days location" claim untraceable to any primary article — do not repeat.

### 4.2 Financial products
In scope: insurance, mortgages, loans, investment products, credit cards. Meta: advertisers "may be required to verify business and/or individual identity and demonstrate authorization by the relevant regulatory authority," reviewable any time.

| Geo | Proof | Note |
|---|---|---|
| UK | FCA firm reference number | Cross-checked vs FCA register via email domain/phone |
| Australia | AFSL number or declared exemption | Plus beneficiary/payer verification 🔺 |
| Taiwan | Beneficiary + payer | Mandatory for ALL ads targeting TW once financial toggle on [vendor-sourced] |
| Singapore | Beneficiary/payer verification | [vendor-sourced] |

🔺 Country-count sources conflict hard (one lists 10: AU/HK/IN/IE/IL/ES/TW/TH/UK/US, another claims 38) — neither verified live. Never quote a count; check live list per geo, surface expands over time.
Beneficiary/payer fields asked inside Ads Composer at ad-set level — have regulator number in hand before campaign build.

### 4.3 Gambling and games
Definition wide: "anything of monetary value as part of a method of entry and prize" — casinos, sportsbooks, poker, bingo, lotteries, fantasy sports, sweepstakes casinos, skill-prize contests.
Route: Authorizations and Verifications tab, Business Suite — declare operator/aggregator/affiliate role, target territories, exact destination URLs (not free-text email). Proof: current regulator licence per targeted territory. **Approvals attach to specific business portfolio + ad account** — new account needs new approval.
**Affiliates get no exemption** — a LP referencing real-money play/bonuses/promo codes or redirecting to an operator is a gambling ad; Meta crawls the redirect path.
Min 18+ (or local legal age), strict geo-fencing. **19 unsupported markets** (no gambling ads, any authorization level) — official, current, named list in `10`. 🔺 [single practitioner source, unverified]: move to A&V tab Jul 2025; 2026-02-23 date for the 19-market list. List confirmed, date not. (`meta-ads/07` §3 labels the same list [official 2026-09-25]; the transparency page did not render in the 2026-09-29 docs review, so the list is unverified there and the label difference is unresolved.)

### 4.4 Crypto
Prior written permission, same A&V tab.
Needs permission: trading/exchange (spot/margin/futures) · lending/borrowing · enhanced wallets (buy/sell/swap/stake) · mining **software** · investment solicitation incl. affiliate sites.
Exempt: tax services for crypto firms · educational/news content · NFTs/non-currency blockchain products · storage-only wallets · mining **hardware**. 🔺 Exemption boundary flagged uncertain even in source material — check live.
Meta recognizes 25+ jurisdictional licences (FCA, MAS, NY BitLicense, AUSTRAC/ASIC, FINTRAC, FinCEN, FSA…) [practitioner, no primary list captured].
**Permission does not immunize a creative** — every ad still reviewed independently against Advertising Standards, LP included.

## 5. Payment method verification

| Method | Mechanism | Failure |
|---|---|---|
| Card | Temp auth hold, auto-reversed. 🔺 "$1–3 + descriptor code" figure **unverified** — article login-gated, sources disagree ($1.01 vs 4-digit code) | Hold expires; not itself a disablement |
| Bank via online-banking login | Instant [260929950658464] | — |
| Bank manual deposit | Meta deposits $0.01–$0.99, re-enter exact amount. Completes ≤3 biz days, max 3 attempts [260929950658464] | Resubmit bank details from scratch |

Statement descriptors seen (cosmetic, changes 🔺 [practitioner]): `METAPAY` · `META PAY` · `METAADS` · `FACEBKADS` · `FACEBK MENLO PARK` · `FBMARKETPLACE` · `FACEBOOK PAYMENT` · `FACEBK*`+10 chars.
Billing "disabled" ≠ policy "disabled" — notification should name billing specifically. Repeated failed charges → suspension after retry cycle (🔺 24–72h, unverified). Card/account name mismatch = documented risk trigger. Chargebacks freeze billing + trigger review; permanent ban possible, not automatic.
🔺 Circulating "7-day disablement → guaranteed learning-phase reset" tier table with dollar-cost model = one vendor blog's construction, not Meta-sourced. Same for "invoice billing needs 3 months $10k+/month" [unverified].

## 6. Pre-clear order for a restricted vertical (operational inference, not Meta-published)

1. Business Verification — pre-clear website first (loads/HTTPS/no broken links).
2. Beneficial owner docs — same round-trip if ≥10% owner exists and Commerce in scope.
3. Payment method — before heavy spend, so billing suspension never compounds a policy hold.
4. Identity/selfie — opportunistic, not schedulable; front-load if vertical is financial.
5. Category authorization — **parallelize with 1, don't sequence after**: gambling/crypto file in A&V before any ad exists; financial needs externally-sourced regulator number (usually blocking); SIEP starts day 1 (postal mail = long pole).
6. Ad-level review — independent of every gate above; authorization never immunizes a creative.

## Gaps — do not fill with plausible guesses

1. No primary SLA for business-verification review (2–5 / 3–7 / ≤10 days conflict).
2. No published attempt cap before permanent denial.
3. No published selfie/ID video retention period or re-verification cadence.
4. No Commerce-specific beneficial-owner threshold separate from ≥10%.
5. Financial-products country list: 10 vs 38, unresolved.
6. Australia AFSL beneficiary/payer rollout date ambiguous ("early February," year unstated).
7. Jul 2025 gambling move to A&V tab — single practitioner source.
8. Crypto exemption boundary — uncertain in source material itself.
9. JS-rendered/login-gated pages, re-fetch live before quoting: `transparency.meta.com/policies/ad-standards/restricted-goods-services/financial-services/`, `facebook.com/business/help/208949576550051`, `facebook.com/business/help/2992964394067299`.
