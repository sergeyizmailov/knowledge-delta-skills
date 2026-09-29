# iGaming: casino, betting, lottery, social casino

Reviewed 2026-09-14 against TikTok's Gambling and Games policy plus RU/EN practitioner and legal
sources.

## Establish the mode before anything else

There are two operating modes in this vertical and they share almost no mechanics. Which one applies
is a **fact about the operator**, not a recommendation this skill makes — establish it at intake, in
one question:

> Does the advertiser hold a gambling licence for the target market, on the same legal entity that
> owns this ad account?

| | **Mode A — licensed operator** | **Mode B — everything else** |
|---|---|---|
| Who | The operator, or an agency whose certification is already granted | Affiliates, and operators unlicensed in this market |
| Path | Certification → Sales Rep. Self-serve still unavailable | No path through TikTok's front door |
| Real cost | **Certification lead time**, not CPM | Account mortality and legal exposure |
| Share of the market | Minority | The majority of what actually runs |

A plan that assumes Mode A for a Mode B operator is useless to them; a plan that assumes Mode B for a
licensed operator throws away the only durable path they have. **Ask first.**

## Mode A — the licensed path and what it actually costs

- a **licence for the target market**, on the entity that owns the ad account — a Curaçao or MGA
  licence for a different GEO does not transfer;
- certification through the **TikTok Industry Pilot Program**;
- **Sales Representative approval. There is no self-serve path**, before or after certification;
- age targeting, often **25+**, as a hard `age_groups` control — interest targeting is not an age
  control;
- creative and landing page carrying risk warnings, the market's mandatory disclaimers, a
  responsible-gambling link, and defined promotion terms;
- no minor-appeal in creative — cartoon styling and game-like framing are rejection triggers in a
  category already under scrutiny.

**Gambling is five classes, not one** (`08`): offline gambling, online gambling, non-casino games,
social casino games, gambling information. Each is gated separately per market. "Social casino is
easier" is a claim about a **class**, and it can be shut in a market where offline gambling is open.
The per-market matrix is login-gated and moves without a changelog — **look it up live, never from a
list, including this one.**

Authorization binds to the verified entity and usually to a specific ad account. **A replacement
account needs new certification, not a copy.** That lead time is the first dependency in the plan and
the honest answer to "when can we launch".

Where this works today per practitioner sources: licensed EU sportsbooks running through a Marketing
Partner that already holds approval, UK, and individual US states.

## Mode B — what the field does, and what this skill does about it

**The landscape, so nobody is naive about it.** RU practitioner material describes a standing stack:
farmed and warmed accounts, rented agency cabinets, cloaking with a white page for review, fabricated
tax identifiers, and synthetic Purchase/Install events to activate a fresh pixel. One documented
approach warms a farm account on a soft casual WebView game — moderated as "just a game" while the
creative stays soft — before running the real offer. Another builds a catalog of compliant products,
passes review, then swaps the product set.

**This skill does not implement any of it** — no cloaking, no synthetic events, no post-approval
asset swaps, and no maintained list of what currently gets past review. Deliberate boundary. What it
will do is price the failure, because that is what the field material leaves out.

**What TikTok's policy names as suspension triggers:** landing pages changed after approval, pages
targeted at reviewers, fabricated events. Editing an approved asset re-triggers review
(`AD_STATUS_REAUDIT`). Enforcement does not arrive as a rejected creative — it arrives as
`ADVERTISER_ACCOUNT_PUNISH`: **30 days to fix or appeal, then permanent and non-appealable**, and a
suspended agency account cannot create or fund other ad accounts. Balance and pixel die with it.

**TikTok reviews twice.** An initial pass, then a second review roughly 12 hours later that can
retroactively restrict creative already running. An early approval is not an approval.

### The part the field material never mentions: destination-GEO law

Platform policy and law are different problems, and **only one is solved by better technique.** None
of the RU sources surveyed discuss the buyer's legal exposure at all — every GEO recommendation is
written purely in CPA terms.

| GEO | Advertising exposure | Status |
|---|---|---|
| **Bangladesh** | **Gambling Prevention Act 2026**, in force **1 July 2026**: promoting gambling via ads, sponsorship, affiliate marketing or referral campaigns — **up to 3 years and BDT 5 million**. Operating a platform: up to 7 years | Four independent outlets converge. Bangladesh is simultaneously named a favoured low-competition GEO by arbitrage sources, **none of which mention this** |
| **India** | **Promotion and Regulation of Online Gaming Act, 2025** outlaws online money gaming and its advertisement. Earlier MIB advisories: 2 years and ₹50 lakh, **5 years and ₹2 crore for repeat offenders** | Enacted |
| **Russia** | Advertising illegal gambling is currently **administrative only** — roughly 2,000–2,500 RUB for an individual, to 500,000 for an organisation | In force |
| **Egypt** | Gambling contracts void under Civil Law No. 131 (1948); **no advertising-penalty provision found** | Gap, not an all-clear |

**Correction to a claim this skill previously carried.** "Up to 6 years for advertising casinos in
Russia" is **misattributed**. The 6-year maximum is real but sits in **Art. 171.2 of the Criminal
Code, which covers *organising* illegal gambling — not advertising it**; a buyer sending traffic to
someone else's casino is not the organiser. The 6-years-for-advertising figure traces to **bill
№ 799753-8 (Dec 2024), which has not passed.** The bill actually moving toward passage — its sponsor
said autumn 2026, as of September 2026 — is **administrative only, no prison**: fines to 500,000 RUB
for individuals, 7 million for legal entities, 90-day business suspension.

Give an operator the accurate version. The inaccurate one is alarmist and wrong about who is exposed.

## Is TikTok even the right source here?

The honest answer from RU field material: **not as a paid channel, mostly.**

- A 2026 gambling-promotion trends piece built around channel recommendations weights push networks
  and Facebook, and mentions TikTok **once, in passing**.
- A 12-case gambling roundup: **one case in twelve used TikTok**, through a PWA wrapper rather than
  native paid creative.
- Recurring 2026 framing: running gambling on TikTok "has become almost as difficult as on Facebook"
  — a decline from an easier period, not an easy option.
- TikTok is described as having **the longest path-to-conversion of any channel** for casino
  affiliates: view → follow → bio click → external → signup → deposit, shedding most of the audience
  at each step.
- Where used seriously it is **organic/UBT at volume feeding one destination** — one described
  operation runs ~30 TikTok accounts plus 20 Instagram and 10 YouTube Shorts into a single Telegram
  channel or preland.

Anecdote convergence, not measurement — no source produced a spend-share or CPA comparison. Still
consistent enough that "we will scale casino on TikTok paid" deserves a challenge at intake.

**GEO recommendations contradict each other outright**, which is itself the finding:

| Source date | Named good | Named dead or problematic |
|---|---|---|
| 2024 | US, DE, ES, IT, NL, BR, MX | — |
| 2026-06 | Tier-1 US/UK/FR; Tier-2 BR/TR; Tier-3 IN/CL | — |
| 2026-07 | LATAM, CIS, IT, PT, ES, BR, CA, GR, IN, AU, UA | **TR, DE, PL, NL, US (state-dependent)** |
| 2026-08 | **BD, NG, EG**; BR "gambling mecca" but crowded | Tier-1 broadly, saturation |

Germany and the Netherlands are "hot" in 2024 and "problematic" in 2026. Do not carry a GEO list
between years.

## Funnels

| Funnel | What it is | Pairs with | Weakness |
|---|---|---|---|
| Direct-to-landing | Ad → offer page | Traffic / Web conversions | Highest review exposure |
| Preland (прокладка) | Bridge page before the offer | Web conversions | Adds a drop-off step |
| **PWA** — spelled **ПВА** in RU, the same thing, not a separate type | Installable web app, no store review | App Promotion / Web conversions | Install friction on iOS |
| WebView app | Native shell around one page | App Promotion | Store review, short life |
| Rented gambling app | Network-supplied | App Promotion | You do not control its lifespan |
| White app (store-listed) | Real listing, real review | App Promotion | Slow and expensive to replace |
| Telegram bot | TikTok reach → TG does the pitch | Traffic | TikTok is only top-of-funnel |
| TikTok LIVE | Streamed play | Organic | Enforcement risk to the account |

**PWA is claimed to convert at least 2× better than a WebView app** by a practitioner running both —
their example: an Egypt deposit near $2 on PWA versus the WebView figures below.

## Payout, optimization and the volume problem

```
Registration → Deposit (FTD) → Qualified FTD (minimum amount / retained)
```

Reported ranges, all `INDUSTRY` and mostly network self-published: **CPA $25–200+ per FTD**, Tier-2
$10–50, Tier-1 $150+; **RevShare 40–60%**. Hold periods disagree wildly — 3–7 days in some sources,
8–10 months in others. **Assume ambiguity is the default; get the number in writing.**

TikTok needs roughly **25 results per ad group per week** before volatility falls, while its own
delivery-troubleshooting page says allow 7 days for **50** conversions (`05` documents the conflict).
Most new gambling accounts produce neither at FTD depth.

Standard resolution: **open on `CompleteRegistration`, with the switch to the deposit event written
into the plan as a numeric condition**, then hold to it. Judging registrations while payment is on
FTD is the classic way to scale a loss.

### Numbers from one documented live session

Egypt, WebView funnel, farm account, June 2026. Take the **shape**, not the numbers:

- optimize on the in-app **Purchase** event, never Install, on this funnel — contrasted with PWA,
  where the same operator does split-test Install-optimized delivery;
- leave TikTok's suggested **$30/day**; pushing to $100–150 on a fresh unwarmed account is avoided
  deliberately as a review trigger;
- one campaign, one ad group, three creatives on a fresh account; 3–5 accounts in parallel;
- **kill rule: no click by $1 spent, stop the ad set**;
- sanity targets: install ≈3–4% of the offer's CPA, registration ≈8–10%;
- upload statics **one at a time** — three at once auto-merge into a Carousel;
- two rejections in a row on a zero-spend account is usually fatal for it;
- result: ≈$400 spend → ≈$600, about 50% ROI against a stated norm of ~100%, blamed on World-Cup
  auction inflation. Their off-camera benchmarks for the same offer: install $0.15–0.20, registration
  ≈$0.70, deposit $3–4.

**Stale in that session:** the Adjust MMP postback flow it demonstrates was **discontinued 31 March
2025**, replaced by SAN direct integration (`07`). Any tutorial still showing classic MMP postback
setup is wrong on that point.

## Creative

Video, not static — the consistent RU claim is that static does not convert here. Keep minors and
minor-appeal out entirely, and expect fast burnout. A creative rejected on one account can pass on
another and vice versa; practitioners describe the outcome as unpredictable, with no reliable rule.

## What to ask the affiliate network before taking the offer

Assembled from documented disputes, not a generic template:

1. **Licensing basis per GEO** — licensed, or merely "not blocked"? Bangladesh and India carry named
   criminal advertising liability the offer page will not volunteer.
2. **Exact qualification rules for a valid FTD** — minimum deposit, retention or wagering
   requirement, any repeat-deposit-rate threshold used to reject later. One documented $1,800
   non-payment dispute turned entirely on an undisclosed repeat-deposit threshold.
3. **Hold period in writing**, and whether it matches the public offer page.
4. **Withdrawal and conversion fees**, disclosed before payout rather than on the statement.
5. **Which traffic-quality metrics can shave or reject a batch after the fact**, and whether there is
   an appeal or the network's retroactive call is final.
6. **Independent tracking/postback validation** — shave disputes turn on whose numbers are trusted.
7. **Who owns the ban risk** — your account, a rented agency account (recovery then depends on the
   reseller's standing, not TikTok), or network-supplied apps with their own replacement terms.
8. **Cascading ban terms** — if a BC or device group is flagged, who replaces the funnel assets.
9. **Does the network publish creative guidance** for its own offers — many do; ask before, not after.
10. **Track record** — search the network's name with «шейв», «не платит», «кинули» before committing
    meaningful spend.

## TikTok-specific failure modes

- Minor-appeal creative in a category already under scrutiny.
- Missing mandatory disclaimers and responsible-gambling links — a policy failure even with a licence.
- Age floor not set as a hard `age_groups` control (`04`).
- Landing page changed after approval — a **named** suspension trigger (`08`).
- Judging on registrations while payment is on FTD.
- Treating an early approval as final — the second review lands hours later.

## Shape of the derivation

Establish the mode → **Mode A:** market and class verified live → licence on this entity → Industry
Pilot + Sales Rep on *this* account → age floor as a hard control → payout event and FTD lag →
optimization event from weekly volume at depth, switch condition written → creative screened against
minor-appeal and disclaimer rules → judging window from FTD lag → replacement-account plan that
budgets re-certification.

**Mode B:** say plainly there is no path through TikTok's front door, price the account mortality and
the destination-GEO legal exposure, and let the operator decide with both numbers in front of them.
The nearest legal neighbours — social casino, gambling information, land-based — are a **new intake**,
not an edit to the current offer.
