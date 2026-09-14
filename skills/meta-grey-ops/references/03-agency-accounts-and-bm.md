# 03 — Agency accounts, BMs, asset sharing

Reviewed 2026-09-09.

**New BM = 1 ad account cap** (UI, field-observed 2026-08-30): more only after
"several weeks of following policies." Second account today = create BM2, create
the account there, partner-share it to BM1 (BM2 Partners → share ad account →
BM1 ID), assign your System User on it — existing app/token keeps working.

Agencies issue "setups": FB profile + proxy + BM share + N ad accounts + pages
(sometimes catalog), billing topped via the agency (crypto). You're a TENANT: can't
make system users / change BM settings / assign some assets. Know your level
(BM → People → your user → assigned assets).

- Bans are routine: disabled → report → replacement → continue. A large share of
  fresh stock can be DOA (zero impressions from birth) — team/stock-specific prior,
  not a fixed rate; replace, don't "fix." Document every ban (account ID, date,
  spend at death); agencies replace against lists.

**Cross-account creative discipline (SKILL #6 mechanics):** never duplicate the
same campaign+creative across accounts — both hit the same users (two accounts
share one auction pool), audience freshness dies, auction overheats on your own TA
→ no leads + spam/reject flags. Per account: own creative + separated audiences
(exclusions on converted leads, refreshed ~weekly, restart campaigns on refresh).
Scale horizontally by NEW creatives per account, not clones.

## Asset sharing (order of operations)

Pixel/catalog/pages live at BM level; a NEW ad account does NOT inherit them.
Symptom: "Unassociated pixel" / "account does not have access to pixel ID" — ad
can't deliver. (Code 1815045 is field-observed, absent from Meta's published
reference, but a stable numeric code — branch on it like any other, `meta-ads/14`
owns the rule. Never condition on the message string; log `error_user_msg` as
evidence only.)

Fix, in order: (1) self-serve — business.facebook.com → Settings → Data Sources →
Datasets → pixel → Assign ad accounts → tick → Save (needs BM role); (2) agency —
send account IDs + pixel ID to the agents chat. Ads recover automatically after
assignment, no rebuild (toggle off/on only if delivery hasn't resumed within an
hour). Same for pages (creative fails without page access) and catalogs. Launch
errors on an asset → check shares first.

## BM-level bans & asset recovery

Distinguish the LEVEL of the hit — recovery differs sharply:

- Single ad account disabled: routine (above); BM-owned assets survive → replace it.
- Whole BM restricted/disabled: child accounts can all stop at once, BM-owned
  assets may go inaccessible — scope varies by restriction type, a Page/dataset
  can survive via another role. Check Business Support Home / Account Quality
  per asset before assuming it's lost.
- **Creation-link death chain** (practitioner prior, 2026 storm-era): accounts
  CREATED INSIDE one BM = one death chain — one flagged account killed all
  BM-created accounts (observed 6/6). Accounts created elsewhere and merely SHARED
  into a BM don't chain (observed 1/4 dead over 2 weeks); shared pixel+catalog+FBP
  was NOT the kill factor. Implication: create accounts with separate origins, add
  to a working BM, keep sharing pixel/catalog/FBP — but assume BM-created siblings
  fall together.
- **Lead-base uploads need a BM-owned account**: personal/legacy accounts can't
  host big uploaded custom-audience databases — keep 1-2 spare BM accounts per
  setup purely as the audience-holding core (exclusions/lookalike seeds), spend
  elsewhere.

Recovery (do NOT rebuild/farm to evade — replacement-to-evade is itself a
violation):

- An asset owned by a SURVIVING BM (or your own clean BM) can be re-shared into
  fresh accounts; owned by the dead BM = gone. Keep pixel/page on a cleaner,
  separate owner from the disposable ad-account BM where the agency allows it — a
  page/pixel outliving the ad accounts is the whole game.
- New pixel = cold: no event history, re-enters learning, audiences rebuild from
  zero — budget for the reset.
- Page: if it survives (owned elsewhere), re-share it — warmed page with history >
  any single ad account; if it dies with the BM, social proof resets too.
- Agency tenants can rarely appeal a BM ban or move assets themselves → request a
  fresh setup (new BM + accounts + re-shared page/pixel), give the agency the dead
  BM ID + asset IDs.
- Freeze during an active BM review (SKILL #3): repeated appeals/edits mid-
  restriction are widely held to extend it — field prior, not documented.

## Ban detection loop

Bans and silent stops are found by polling, not by noticing zero spend a day late.
Two cron-able sweeps:

- STATUS (daily, per account): `GET /act_<id>?fields=account_status,
  disable_reason` — 1=active, 2=disabled, 3=unsettled (unpaid balance, see billing
  below — topup fixes it, not a replacement). Log every change (date + spend at
  death) into the survival log (`06`) — feeds forensics and agency replacement
  lists. Per-ad rejects: `effective_status=DISAPPROVED` on the ads edge.
- SPEND (daily): yesterday's spend ≈0 on a live account = silent stop — ASL hit,
  unpaid balance, or a restriction not yet surfaced as status. All child accounts
  stopping at once = earliest BM-level signal.
- **Opportunity Score (0-100) is ADVISORY, not a signal.** Aggregates setup
  recommendations; restricted/grey verticals floor it to 0 because recommendations
  are unappliable. Official: "does not reflect actual or future performance." Not
  in Graph API. Real signals: account_status/disable_reason, per-ad DISAPPROVED,
  delivery-vs-budget gaps.

Detection (here) → attribution (`06`) → response (`05`). Feeds the daily
kill/watch/scale watchlist in `senior-buyer-ops/01`.

## Billing gotchas

- A "dead" account may just be an UNPAID BALANCE, not a ban: failed payment pauses
  delivery and restricts the account. On crypto-topup setups, confirm the balance
  before requesting a replacement.
- Account Spending Limit (ASL) is a LIFETIME cap across the account that pauses
  EVERY ad when hit — silent full-stop, distinct from ad-set budget and billing
  threshold, easy to forget.
- Meta location fees (DST) sit ON TOP of spend, on impressions — full table → `08`.
  Read the invoice line, don't hardcode.

## Bought spend accounts ("расходка") instead of agency seats 🔺

[practitioner, Praktichesky Arbitrazh 2026-09-08 — one team's storm-era answer to agency
supply drying up; a bought account is still someone else's farmed asset, same tenancy risk
as an agency seat, plus seller fraud. Not a Meta-sanctioned path.]

Storm-era motive: agencies can't fill demand, fresh agency stock ("автореги" — newly
created accounts) delivers weakly and dies. The trade is to buy AGED accounts with real
spend history and drive them from your own BM.

**Pre-buy QC — read these four fields before paying** (Ads Manager account overview, or
ask the seller): `Total Spend` > 0 and material (examples cited: $624 / $1.2k / $3.6k);
`Creation Time` years back (2017 / 2023 vintages cited, up to ~8y); current spend limit
($145 / $250 / $1050 / no-limit); timezone and currency. Zero-spend accounts ("пустышки")
were reported to die at a higher rate than spent ones even inside the same batch — spend
history, not age alone, is the claimed survival factor. Cross-check against the farmed-account
tells in `01` (ADS_TRUST_TIER, Off-Facebook activity, feed ads) and still judge after
$30-50 of your own spend (SKILL #5).

Timezone/currency are **60-day locked** (`08`) and pre-set by the seller — they are a
selection criterion, not something to fix later. Buying a spread of timezones is deliberate:
it staggers geo-day rollover and start windows across the portfolio.

**Binding order (the one real trap here).** Bind the card FIRST, from the seller-shared
personal profile, in that account's Billing — THEN request the account into your BM. Binding
after the BM transfer makes the payment method a BM-level attachment and was reported to
trigger payment-risk review on the whole setup. Full order:

1. Seller shares the ad account to your social profile (ad account Roles → Admin).
2. You kick the seller's profile, share to a second profile of your own (needs the two
   profiles friended; the role dialog asks for the profile's name).
3. Billing → add card, **as the profile**, before any BM involvement. 3DS codes arrive in
   the card vendor's statement, not by SMS.
4. Copy the account id from the `act=` URL param — the Business ID is a different number and
   pasting it is the usual failed-request cause.
5. BM → Ad accounts → Request access (never Add — the seller's portfolio still owns it,
   `meta-ads/01`) → accept the pending request → assign users.

Keep ≥2 profiles per setup purely for access diversification: when one profile hits a
quality flag, permission assignment silently fails (button active, account invisible) and
the fix is to grant the role from the other profile, not to retry on the flagged one.

Legacy payment methods sometimes survive on an aged account. Do not spend on a stranger's
card left in the account — that is card fraud, not a lifehack, whatever the seller implies.

## Card / topup vendors (Meta) 🔺

Agency crypto-topup is default; for own-BM setups (directory pricing,
vendor-reported, Partnerkin tools index, 2026-08-27, counterparty risk, not
endorsements):

| Vendor | As listed |
|---|---|
| Pay2.House | multi-currency, from $5 |
| AdsCard | Classic $2.5 / VIP $1 per card |
| Combo Cards / flexcard | from $1-2/card, "ADS BINs" |
| Capitalist / 4×4.io | $2.95 flat / $2+5% on charges |
| Getsby | €3.99 + 3% + €0.99/mo |
| PST.NET / XCards (ex-EPN) | from $10/card |
| ADVcash / Wallester / Soldo / Linkpay / Adpos | wallet/licensed-issuer or on-request, from €0 / 2%+ |

"Ad-friendly BIN" claims have no methodology — judge vendors on replacement/refund
terms and fund recovery (same test as Google-side resellers), not BIN marketing.
The card is a linking signal to the ad account (`07`).

Recurring example of exactly that marketing: an AdsCard BIN pitched as no-freeze plus
"binds to a $50-limit account and the limit jumps to $500-600" [Praktichesky Arbitrazh
2026-09-08, affiliate promo — the video states the BIN inconsistently across three mentions,
so even the digits are unreliable]. Treat limit jumps as Meta's own trust scoring on the
account, not a property of the BIN. Keep the vendor balance funded: an empty card reads as a
failed payment and stops delivery account-wide (see billing gotchas above), which the same
source hit mid-flight.

## Naming (decide before first launch, never change mid-flight)

Tracker splits by campaign name ONLY because the campaign URL maps the FB
campaign-name macro into a tracker param (`ad_campaign_id`) — not automatic
(`tracker-ops` mapping contract, 03); ad-level splits likewise need ad macros
mapped. Given that mapping: campaign name = the ad account (e.g. J41-16), one
campaign/account/test wave; ad set = structure+creative (`S1-creoName`); ad =
creative name. Gives exact per-account tracker CPL, readable Ads Manager,
unambiguous kills. Rename legacy campaigns before scaling — renames are safe,
don't reset learning.

## Replacement pipeline

- Hold unused accounts in reserve; don't launch on all at once.
- Verdict (with TL): trash after ~$50 with CPL over target, or zero delivery in
  2-3 days, or any disable. Report in batches.
- On new accounts: check asset shares (pixel!), timezone, currency BEFORE building.
