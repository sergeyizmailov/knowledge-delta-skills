# 02 — Payments, billing, verification

Reviewed 2026-08-27. **On Google, billing is the trust spine** — official mechanics govern behavior.

## The mechanics that matter

- **Prepaid cards not accepted for automatic payments.** One-time-use/virtual cards **are** permitted
  for **manual** payments. Documented product constraint (not a workaround) — why buyers run
  manual/prepay billing with virtual cards.

- **Threshold billing**: charge fires when account cost reaches threshold **or** on the 1st of the
  month, whichever first. Google's example: threshold $500, $1,500 monthly spend → three separate
  $500 charges.

  🔺 **Google does not publish the escalation ladder.** Widely cited $50 → $200 → $350 → $500
  progression is industry lore, unconfirmed. Don't build a spend plan on it.

- **Monthly invoicing — official eligibility**: registered business **≥1 year** · account in good
  standing **≥6 months** · spend **≥$5,000/month in any 3 of the last 12 months** · MCC link + primary
  billing contact + payments-profile business-name match. Net-30; credit line = max balance across all
  invoiced accounts.

- **PayPal**: "temporarily unavailable for new automatic payment accounts". **Giropay** dead since
  2024-06-28. **Disbursement-only accounts (e.g. Payoneer) not accepted** as funding source.

## Suspension triggers — exact official language

> *"If we detect suspicious or unauthorized payment activity on your account, we may restrict how much
> the account can spend or suspend the account."*

Same page, three distinct causes:

1. **Unpaid balance** — "concerns about your ability to make future payments".
2. **Chargeback** — *"If you instruct your bank or credit card company to reverse a charge that was
   paid against a legitimate Google Ads balance, your account may be suspended."* Officially confirms
   chargeback is **account-level**, not merely a payment-method block — one of the fastest ways to
   lose an account permanently.
3. **Promotional code abuse** — multiple codes, reselling codes.

Suspended accounts stay **read-only**: reports/settings viewable, payments/appeals still possible, ads
stopped.

## Decline reasons

Bad card info · expired · insufficient funds · exceeded transaction limits · **bank restrictions on
internet or international transactions**.

Last one is the closest official language to a country/currency mismatch flag — framed as
**issuing-bank restriction, not a Google-side geo flag**. 🔺 Payments-profile page has **no** fraud/
mismatch language at all — "billing country must match card country or Google flags you" claim
**remains unconfirmed**. Consistency still worth maintaining for identity-graph reasons (`01`), but
not a documented Google rule.

## Verification

**Triggers**: initial billing setup · changing primary payment method · one-time payments · "unusual
activity or transactions" · legal/regulatory compliance.

**Methods**:

1. Temporary charge **≤$1.95**, descriptor's last 6 digits = the code.
2. Making a payment.
3. Document upload — government ID + payment-method image. **Current, legible, in color, all four
   corners visible.** Processing ≤5 business days.

Non-compliance: account **"may be temporarily paused"** — softer than suspended, recoverable.

**Payment-profile verification is separate from advertiser identity verification** — both can be
required at once, separate deadlines. Advertiser identity gates *serving*; payment profile gates
*billing*. See `google-ads/09` for identity side.

## The asymmetry that should drive every decision here

**Failing verification honestly is recoverable — the account pauses.**
**Submitting false information = Circumventing systems — permanent, propagating to linked accounts,
appealable only in "compelling circumstances".**

No version where fabricating documents is the lower-risk path.

## Virtual card and agency vendors 🔺

Vendor-reported. Counterparty risk, not endorsements.

| Vendor | Terms as reported |
|---|---|
| **Pay2.House** | Unlimited cards, per-card limit $100,000, Visa/Mastercard, USD/EUR, multi-country BINs. $5 issuance, $5/mo per active card, 4% reload, 4% refund, 20% discount at 100+ cards. Ships "Decline Analytics"; no decline-rate stats published |
| **AdsCard** | Marketed for Google (vendor also lists other networks; out of scope). From $1, **$500/month ad-spend requirement**. Issuance $2.50–$3.00, fee 4%, USDT top-up free. **BINs: USA, EU, Hong Kong.** Reviews report $50k+/month volumes but also **20-day fund hold, commission on failed transactions**, recurring processing delays |
| **PST.NET, XCards (ex-EPN), Mint Card** | General ad-platform virtual cards. **No Google-specific claims surfaced** — treat as unverified |
| **YeezyPay** | 2023-dated pricing, likely stale: 10% top-up commission, **30% fee to recover funds from a banned account**, $200 minimum deposit, up to $200,000/month. Live site shows no public pricing now |
| **Mega Digital** | Rents Google/Facebook seats (vendor also lists other networks; out of scope). Promise: **fund continuity on ban**, not ban prevention |

**Not confirmed by any source**: working BIN ranges, issuer names, crypto-funded-card acceptance
data, documented threshold escalation ladder. Anyone quoting specific BINs is guessing or selling.

## Operational reading

1. **Sequence payment events deliberately.** Highest-risk moment for identity inconsistency on Google
   is a billing event, not a login (`01`). No card add/method change/threshold charge from an
   inconsistent context.
2. **Never chargeback.** Officially named account-level suspension trigger; also burns the payment
   method's future usability.
3. **A declined card is not a policy event.** Read the decline reason before escalating — most are
   issuing-bank international-transaction restrictions, fixable at the bank.
4. **Invoiced accounts trade one risk for another.** No decline/chargeback surface, but non-payment
   damages the entire parent relationship, not one account.
5. **"Temporarily paused" ≠ "suspended".** Verification pauses recover by completing the task — don't
   panic-migrate.
6. **Watch card networks, not only the platform.** A network-side rule wave kills offer economics with
   clean accounts, no policy event — practitioner case: Nov 2025 Visa/Mastercard sweepstake
   tightening collapsed multiple teams' funnels at once. Funnel dies, accounts healthy = payment-network
   event, not moderation. [single source]
