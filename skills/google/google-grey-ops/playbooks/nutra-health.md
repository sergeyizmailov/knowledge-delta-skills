# Playbook — Nutra, supplements, weight loss, health

Reviewed 2026-08-27. Policy context → `google-ads/09`.

## Prohibited regardless of local legality

Governed by the **Healthcare & medicines** policy and the narrower **Unapproved pharmaceuticals and
supplements** policy. Flatly prohibited no matter what a jurisdiction permits:

- Products containing **ephedra**.
- **DHEA and melatonin** products, unless a specific country carve-out applies.
- Herbal or dietary supplements containing **active pharmaceutical or dangerous ingredients**.
- Any supplement, drug, or product that has been the subject of a **government or regulatory warning or
  action**.

That last one is the trap: a formulation can be perfectly legal to sell and still be permanently
ineligible because a regulator issued a warning about it.

## Claims — the concrete disapproval triggers

Non-government-approved products **cannot be marketed to imply safety or efficacy for preventing,
curing, or treating a specific disease or ailment.** Google separately prohibits **"unreliable claims
or misrepresentative information."**

**Outside Canada, New Zealand, and the US, prescription-drug terminology is banned entirely** — from
ads, landing pages, **and keywords**.

Concrete triggers: **"cure," "miracle," "treat [disease]," "prevent [disease]"** and disease-name-
adjacent phrasing.

> **Before/after imagery implying drug-like transformation carries the same unreliable-claims risk even
> with no banned word present.** The image is evaluated, not just the text.

**There is no certification that makes an aggressive claim safe.** Weight loss and supplements have no
gated cert path — this is enforced through Misrepresentation → Unreliable claims, which is on the
**egregious track**. You cannot certify your way out of it.

## LegitScript

Required for **online pharmacy** (all forms — mail-order, brick-and-mortar with remote dispensing,
veterinary, sterile compounding), **telemedicine**, **addiction treatment**, and **CBD**. NABP is the
US alternative for pharmacy.

🔺 Multiple practitioner sources cite it as required for **dietary supplements** too, but **whether that
is category-wide or triggered only by specific risk-flagged ingredients or sub-claims was not resolved
to an authoritative statement.** Verify per-SKU against live LegitScript and Google policy pages before
assuming a blanket requirement.

**Unauthorized-pharmacy promotion is on the egregious track** — immediate suspension, no warning.

## Billing model

🔺 No Google page naming "negative option" or "COD" explicitly was found. The governing framework is the
**FTC's finalized Negative Option Rule (2024)**: negative-option offers — including free-trial-to-paid
conversions — require **unambiguously affirmative consent separate from the rest of the transaction**,
plus clear pre-trial-end price disclosure.

Google's general unreliable-claims standard would apply to any funnel obscuring trial-to-rebill terms,
but **that is inference from the policy pattern, not a cited Google rule.**

**COD dominates Tier 2/3 geos** specifically because it sidesteps card-consent and billing-disclosure
complexity where card penetration is low anyway.

## Geo

AdCombo's nutra/COD focus concentrates on **EU and Asian markets**; Dr.cash spans **242 geos across 55
health/beauty niches**.

🔺 Affiliate-industry folk knowledge holds that claim-language enforcement tracks review density —
strictest in US/EU/CA/AU, looser in LATAM/SEA. **No Google source confirms differential enforcement by
geo.** Treat as folklore. Planning a funnel around assumed leniency is how domains burn.

## Payouts

🔺 Network figures: nutra **CPL $5–$30+**; **CPA/sale $30–$100+**, skewed high for COD and
subscription-rebill funnels.

## The compliant path — which is genuinely viable here

1. **Structure/function claims only** — "supports", "helps maintain" — never disease claims.
2. **FTC-adequate substantiation** for every claim made.
3. **No before/after imagery** implying drug-like results.
4. **Avoid ephedra/DHEA/melatonin formulations entirely** if Google eligibility matters at all.
5. **Make trial-to-rebill terms explicit and affirmatively consented pre-conversion.**

Point 5 satisfies FTC negative-option requirements and Google's unreliable-claims standard
simultaneously. **This is the only path that survives both regimes at once** rather than picking one and
hoping the other does not notice — and the FTC side carries consequences Google cannot appeal away.

## What breaks first

**A single disapproved landing-page claim — one banned word, or one implied-cure image — triggers a
domain-level policy flag that cascades disapprovals across unrelated campaigns sharing that domain.**

Practitioners consistently report the blast radius is the whole domain's account presence, not the one
flagged ad. This is why per-funnel domain separation matters more in nutra than in any other vertical,
and why the signal-driven rotation discipline in `03` applies here most sharply.
