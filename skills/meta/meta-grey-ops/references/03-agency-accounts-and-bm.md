# 03 — Agency accounts, BMs, asset sharing

Reviewed 2026-09-09; naming section updated 2026-09-29.

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
  not a fixed rate; replace, don't "fix" — the buyer never appeals alone: ask TL/agency "appeal
  or replace" (payment/risk bans are worth resolving, `05`); an appeal (where even possible) puts a
  human reviewer on the BM, the exact scrutiny this doctrine exists to avoid
  `[unverified mechanism]`. Document every ban (account ID, date, spend at death);
  agencies replace against lists. Dated prior, one supplier pack, this team
  (2026-09-21): 5 of 5 autoregs died — two at first login, three after card bind;
  not a general mortality rate, a signal on that pack/supplier.
- 🔺 Reading a supplier's autoreg dump: blank and footer lines mean **a persona's row number is
  not its file line number** — address by parsed record, never by raw line, or you pour the
  wrong identity into a profile. Records also ship with fields legitimately empty (e.g. no
  profile URL, so no FB id for that persona); that is supplier data, not a parse bug, and the
  profile still works off email + password + cookies + 2FA (field-observed 2026-09-22).

**Cross-account creative discipline (SKILL #7 mechanics):** never duplicate the
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

For the pixel↔account edge specifically, `12`/`13` already document the API path —
check there before clicking through Settings: `POST /{pixel_id}/shared_accounts`
with `account_id=<id WITHOUT the act_ prefix>` and `business=<bm_id>` →
`{"success": true}`, no manual "Connected assets" click needed (field-verified
2026-09-21).

**Portfolio cleanup via API** (field-verified 2026-09-27, System User token):
- Stuck "Request Sent" ad accounts the UI won't cancel: `DELETE /{bm_id}/ad_accounts`
  `adaccount_id=act_<id>` → `{"success":true}`, gone from `pending_client_ad_accounts` on
  read-back. `pending_client_ad_accounts` has no DELETE; `DELETE /{bm_id}/client_ad_accounts` → #100/33.
- Empty partner BMs: `DELETE /{bm_id}/clients business=<partner_bm_id>` is the call, but a
  partner BM flagged for policy returns **#10 / 2446325** ("business account didn't comply with
  Advertising Policies") — the same block the UI shows. Not a token/scope problem, no workaround;
  an empty partner has zero access, leave it. `DELETE /{bm_id}/agencies` is deprecated.

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
- **Run from the autoreg's own cabinet, or share it into a BM?** Both work; the pixel decides.
  🔺 [first-party, verified 2026-09-24] `POST /{pixel-id}/shared_accounts` is rejected unless
  "a business account has access to **both** pixel and ad account" (Sept-2024 change; the docs
  point at `/{pixel-id}/agencies` or `/{ad_account}/agencies` otherwise, which is the same
  business relationship by another door). So a cabinet outside the BM **cannot** use a
  BM-owned pixel. It can create and use its own — a Page, by contrast, shares to an outside
  advertiser fine, so the Page is never what forces the decision.
  Consequence for a server-side-tracked funnel: every extra pixel is a new dataset, a new CAPI
  token, and an edit to the tracker link that carries `pixel_fb`/`token_fb`. At an autoreg
  lifespan of 1-5 days that means rebuilding tracking every couple of days. Sharing the
  cabinet into the BM exists to avoid exactly that, not to make the account survive longer.
  The RU-practitioner default is the lighter variant — **king added as admin on the autoreg's
  own cabinet**, cabinet never entering a BM — which keeps accounts isolated but accepts the
  per-account pixel. Stated ceiling 2-9 linked cabinets per king, and >3 is itself named as a
  restriction trigger.
  Unverified, and it gates the whole direct route: whether a bare autoreg with no business can
  create a web pixel at all, given the Pixel-Terms-of-Service gate (code 10 / 1784018) is
  business-scoped. Check this before planning around the direct route.
- **Assigning a human admin to that autoreg-owned account**: must be assigned to
  the ad account itself, inside the BM — BM membership alone grants nothing (same
  per-asset rule as `02` §1 step 2: "Per-asset — portfolio membership assigns
  nothing"). Do it via Ad account settings → Ad account roles in the UI; the deep
  link `/ads/manage/account_settings/account_roles/` does NOT work (field-observed
  2026-09-21).
- A card-verification/3DS challenge on one of these accounts is unsurvivable: no
  seller-linked profile sits behind an autoreg with access to the card vendor's own
  statement to read the code from (unlike the bought-account flow below, where that
  profile exists) — the attempt burns the card AND the account, not a retry.
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
- Freeze during an active BM review (SKILL #4): repeated appeals/edits mid-
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
  before requesting a replacement. FIELD 2026-09-27: `account_status` 3 ("Payment needed")
  recovered by itself once the card charged; `balance` = unbilled amount in cents, not prepaid.
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
$30-50 of your own spend (SKILL #6).

Timezone/currency are **fixed per account** (change = new act id; currency once/60 days, `08`) and pre-set by the seller — they are a
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
campaign-name macro into a tracker param — not automatic (`tracker-ops` mapping
contract, 03); ad-level splits likewise need ad macros mapped. Two conventions:
- **Agency/generic**: campaign name = the ad account (e.g. J41-16), one
  campaign/account/test wave; ad set = structure+creative (`S1-creoName`); ad =
  creative name.
- **Our team (Keitaro id contract, 2026-09)**: campaign name starts with the Keitaro campaign id +
  geo (`1234 US PWA <ST> Longread<n> <buyer>`), ad = creative name `EN<seq>-<buyer>-<ver>`; the
  ACCOUNT travels in the link (`act=` → sub10), not in the campaign name. **Own BM: no casino name
  in campaign / ad set / ad names.** Names repeat (four ads once shared EN0038; a campaign name can
  recur on two accounts) and name macros are first-publish snapshots (`04`), so the tracker key is
  the id: `ad_campaign_id` = FB campaign id, `sub_id_6` = FB ad_id (`tracker-ops/01`).
Rename legacy campaigns before scaling — renames are safe, don't reset learning (`metaops edit
rename`: ACTIVE → IN_PROCESS → ACTIVE in ~15 s, 2026-09-29).

## Supply quality: what to demand, and what a burned batch looks like

Practitioner consensus, numerically incoherent (30% / 50% / 70% / 99% all appear; no source
defines its denominator) but directionally consistent:

- **30-50% loss across a cheap autoreg batch's whole lifecycle** — dead on arrival, plus first
  login, plus first campaign — is unremarkable cost of goods. Autoreg lifespan 1-5 days is the
  only figure two independent sources agree on. A high loss rate is therefore NOT by itself
  evidence of a bad pack, and saying so to a TL will not survive contact with them.
- 🔺 The signal is the **shape, not the rate**. Death concentrated *before* first login, or
  several ad accounts dying identically at $0 with zero impressions on the same day, is the
  signature of a registration batch caught as a group — shared registration IP pool or
  fingerprint template. Scattered failures across different modes and days are ordinary
  attrition. Judge a supplier on clustering.
- **Pre-login replacement is a market standard**: 2h to 72h, 24h most commonly quoted, and it
  voids the moment a login *succeeds*. So dead-on-first-login units are the clean, defensible
  claim; anything after login is negotiated case by case. Claim inside the window or lose it.
- "30-day" or "lifetime" warranty claims are a red flag, not a benefit.
- Test **3-5 accounts** from a pack before accepting the whole batch — the cheapest way to
  catch a burned batch before committing to it.

## Replacement pipeline

- Hold unused accounts in reserve; don't launch on all at once.
- Each account attempt burns one autoreg and draws on a card. Whether it also burns a proxy is
  the contested question in `01`.
  🔺 **Accounts per card is unsettled, and so is the failure mode.** One practitioner says ~10,
  after which the card silently stops binding — no ban, nothing to chase (2026-09-22). External
  sources converge on **1-5**, and describe the opposite mechanism: the card is blacklisted and
  the flag cascades to every account it ever touched, with a card previously used on a banned
  account called near-100% block risk (two independent sources). Nobody tested either. Size the
  reserve on 1-5 unless the operator's own data says otherwise, since that is the assumption
  that fails safe. Do not move a card from a disabled account onto its replacement (2026-09-29:
  CF1 went live on the same card, Page and pixel as tr-1, disabled 2 h earlier; outcome not yet
  known, so this is a risk, not a finding): `26`.
  Separately, single-source but mechanistically plausible: adding or removing cards more than
  ~3 times in a short window can lock an account on stolen-card suspicion — churning cards is
  itself a signal, independent of reuse.
- Verdict (with TL): trash after ~$50 with CPL over target, or zero delivery in
  2-3 days, or any disable. Report in batches.
- On new accounts: check asset shares (pixel!), timezone, currency BEFORE building.
