# 08 — Policy, restricted verticals, GEO eligibility, review and appeals

Verified 2026-09-14 against TikTok's advertising policy hub.

**Do not hardcode a country list from this file into a plan.** TikTok changes per-market eligibility
without notice, and the third-party sources that publish per-country tables **contradict each other**
— two independent 2026 sources disagree on whether Saudi Arabia permits gambling ads at all. Every
per-GEO claim below that is not marked OFFICIAL must be verified live in Ads Manager or with a
TikTok rep before it reaches a plan.

Fetch note: `ads.tiktok.com/help/article/...` returns 403 to automated fetch;
`ads.tiktok.com/resources/help/article/...` serves the same content. Use the mirror path when
verifying a policy live.

## The three-layer structure

| Layer | Question it answers | Where |
|---|---|---|
| **Industry Entry policy** | May your *business category* advertise at all, in which markets, under what authorization | `tiktok-advertising-policies-industry-entry` |
| **Ad creative & landing page policy** | Is this specific ad and destination acceptable | Creative policy articles |
| **Community Guidelines** | Baseline content rules | Community Guidelines |

Clearing one layer says nothing about the others. A licensed gambling operator with Industry Pilot
approval still gets ads rejected for creative that appeals to minors.

## The gate: run this before designing anything (`01` § B1)

**Q1 — Is the category prohibited globally?** Then there is no path. Say so and stop.

**Q2 — Is it restricted?** Then the requirement is (a) certification through the **TikTok Industry
Pilot Program** — licences
and regulatory proof for the *specific target market* — and, for several categories, (b) **direct
contact with a TikTok Sales Representative.** Those categories are **not reachable through
self-serve Ads Manager even after certification.**

**Q3 — Is authorization attached to *this* ad account?** Authorization binds to the **verified
entity** and usually a specific account. A replacement account needs a new approval. This is why
agency-provided accounts matter for regulated verticals (`02`): the agency already holds the
certification.

**File the gate before any ad object exists.** Discovering it after building is expensive; after
spending, worse.

## Prohibited globally

Drugs and paraphernalia · weapons, ammunition, explosives, fireworks, tasers, pepper spray, blades
(narrow 18+ knife exception in some EU markets) · counterfeit goods · adult content and services ·
human trafficking · endangered species · hate and discrimination · deceptive and fraudulent
practices · **complex speculative financial instruments: CFDs, spread betting, binary options, penny
stocks, mini-bonds** · **payday loans, pawnbroker loans, penny auctions, bail bonds, unlicensed
digital banks, pyramid/MLM schemes, "get-rich-quick" offers**.

**Forex and CFDs are prohibited, not merely restricted.** That is stronger than the "restricted"
framing common in affiliate discussion, and it is the single most consequential correction in this
file for anyone arriving from a finance vertical.

## Gambling, casino, betting, lottery

Official text: *"Gambling ads are only allowed in specified markets where gambling is legal and when
all local certifications and requirements are met."*

Requirements: local licences for the target market · age-appropriate targeting (25+ in several
markets) · creative must not feature or appeal to minors · **clear risk warnings**, legally mandated
disclaimers and taglines, links to gambling-addiction resources where possible, and clearly defined
promotion terms.

Access is via **certification plus a TikTok Sales Representative** — there is no self-serve path.

## Gambling is five classes, not one — and the class decides the rules

TikTok's Gambling and Games policy (verified 2026-09-14) splits it two levels deep:

| Group | Class | TikTok's definition |
|---|---|---|
| **Gambling** | Offline gambling | "promotion of brick-and-mortar gambling venues" |
| | Online gambling | "promotion of online wagering or betting" |
| **Gambling-like activities** | Non-casino games | "online games where participants can enter themselves into the game through payments" |
| | Social casino games | "Virtual games that simulate traditional casino games… without monetary prizes" |
| | Gambling information | "Content that provides insights, stats, or betting strategies" |

A market can permit one class and refuse the next. **"Social casino is easier" breaks on the class,
not the country** — it is its own gate, per market, and being open for offline gambling says nothing
about it. The per-market matrix is **login-gated and changes without a changelog**, so it cannot be
quoted from any document, this one included.

`UNVERIFIED`, and previously stated here as fact: a June 2026 opening of social casino for Guatemala.
**Guatemala does not appear anywhere on the current policy page.** Retracted 2026-09-14. Look the
market up live, every time.

Per-country lists circulating in blogs are unreliable and mutually contradictory. **Verify live.**

## Financial services

Scope: securities, trading platforms, investment consultation, funds, credit cards, loans
(mortgage / consumer / P2P / BNPL), virtual currencies, exchanges, custody wallets, NFTs, insurance,
deposit accounts, fintech.

Where permitted: advertiser **licensed by the local or regional financial authority** · **18+**
targeting (20+ for crypto in Japan) · APR, fees and repayment terms disclosed **on the landing page**.

**Crypto exchange services in most developed markets require the Sales Representative application
process with licensing proof** — explicitly not self-serve.

Regional notes (directionally official, verify per market): EU generally permits BNPL, debt
consolidation and investment services with licensing · Gulf states permit crypto under specific trade
licences · APAC is gated per regulator (MAS, SBV, BOT) · a set of markets is reduced to "promote
only" with no paid financial ads. Spot-check individual countries — that list came through a
summariser, not a verbatim page.

## Health, supplements, weight loss, pharma

- **Prescription medicines: prohibited in most markets.** Narrow exceptions in **Canada** (Health
  Canada) and **New Zealand** (25+ for Rx audiences) — most people assume a global ban.
  Prescription ads require Sales Rep permission where allowed at all.
- OTC medicines, medical devices, supplements: market-specific regulatory certification, **18+**, and
  **no treat/cure claims**.
- Cosmetic clinics and non-invasive treatments: generally allowed with certification and 18+ —
  **Botox is explicitly prohibited in most markets** even where other injectables pass.
- Condoms and lubricants: 18+, no focus on sexual pleasure.
- **CBD has no certification path at all**, even for legal hemp-derived ingestibles. The only opening
  is topical/cosmetic hemp marketed on a cosmetic — not medical — benefit.

The nutra failure mode is creative, not entry: a compliant supplement advertiser gets rejected for
before/after imagery, body-image framing, or an implied cure.

## Dating

Verified Business Account plus **Sales Representative** approval; **18+ mandatory**; available in a
limited market set. Prohibited creative: models appearing 21 or younger, sexually explicit content,
excessive skin exposure or provocative posing, "sugar dating" or compensated-relationship framing,
infidelity themes, mail-order-bride framing. Adjacent "live chat" apps carry the same requirements.

## Alcohol, tobacco, vape

Tobacco and vape: prohibited. Alcohol: market-dependent with age gating — must not appeal to
under-legal-drinking-age users, and **must not feature people appearing 25 or younger, or pregnant
individuals**, in creative *or on the landing page*.

## Political and issue ads

Prohibited. The EU's political advertising regulation adds a further layer. Do not treat
issue-adjacent advocacy as a workaround.

## Special ad categories: housing, employment, credit

Declared on the campaign as `special_industries` (`HOUSING` / `EMPLOYMENT` / `CREDIT`). Declaring one
**restricts ad-group targeting** to comply with anti-discrimination law — full restriction list in
`04`. Generally available to advertisers registered in the US or Canada; others targeting those
countries need an extra allowlist.

**Declare the real category.** An empty `special_industries` on a credit or housing offer is a
violation, not a bypass. You can later remove a category but not change it, and cannot add one to an
existing campaign that has none.

## Landing page policy — the trap that suspends accounts

**Changing the landing page after campaign creation is a documented account-suspension trigger.**

The subtlety: editing *content on* an already-approved landing page **does not automatically trigger
re-review** — but non-compliant content found later still causes rejection or enforcement. So the
silent-drift risk is real: an agency swapping landing-page content post-approval is running an
unreviewed page under an approved ad.

The page must match the ad, disclose what policy requires for the vertical (APR and fees for lending,
risk warnings for gambling), and be reachable. Redirect chains, link shorteners and mismatched
destinations are policy problems as well as tracking ones (`07`).

## Review, rejection, appeals

- Review happens at ad and ad-group level. A rejected ad **cannot be enabled into life** — build a
  new one.
- **Ad rejection ≠ account suspension.** Suspension is a separate mechanism driven by complaints,
  qualification or content problems, undisclosed post-launch landing-page changes, suspected
  malicious intent, or severe/repeated violations.
- **Severe violations suspend immediately.** Otherwise there is a **30-day** window to remediate or
  appeal before suspension becomes **permanent and non-appealable**.
- A **180-day** appeal window is widely repeated in third-party writing but does **not** appear on
  TikTok's suspensions page. Plan against the 30 days (`02`); treat 180 as `UNVERIFIED`.
- **"One Click Appeal"** requests re-review of a fully or partially rejected ad or ad group.
- **An appeal re-reviews the entire ad group, not just the flagged ad, and only one appeal per ad
  group is allowed.** Fix everything before you file — you get one shot, and a second bad ad in the
  group burns it.
- **Fix the violation before appealing.** Reviewers check whether it still exists. Repeated appeals
  for the same issue delay processing.

## Blast radius

TikTok's own suspension article **does not address whether one suspended ad account affects siblings
in a Business Center.** That is a genuine documentation gap, not a fetch failure. Treat it as a
high-severity unknown: do not concentrate a portfolio's pixels, catalogs and identities under a
single BC you do not control (`02`).

## What this skill will not do

It documents what the policy is and what the compliant path costs. It does not implement cloaking,
review-layer filtering, or landing-page swapping after approval, and it does not route around ad
review. Those are the mechanisms TikTok's suspension policy names directly, and the exposure lands on
the operator's accounts and the advertiser's entity.

Where the field diverges from the compliant path — and it does, substantially, in gambling and nutra
— `11` records what practitioners report and what it costs them, as landscape rather than method.

## Before a plan for a regulated vertical leaves your hands

1. Category: prohibited, restricted, or open **in this specific market**? Verified live today.
2. If restricted: which licence, which certification, and **does it require a Sales Rep**?
3. Is the authorization attached to **this ad account**, and what is its lead time?
4. Age floor set as a hard `age_groups` control (`04` — interest targeting is not a control).
5. Landing page carries the vertical's mandatory disclosures, and **will not be changed post-approval**.
6. Creative checked against the vertical's specific prohibitions, not just general policy.
7. Replacement-account plan: a new account needs a **new authorization**, not a copy.
