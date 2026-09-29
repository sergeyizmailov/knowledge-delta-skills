# 01 — Account supply, identity, session infrastructure

Reviewed 2026-08-27. Prices and vendor terms are volatile and vendor-reported 🔺. Every vendor named
here is a counterparty to evaluate, not an endorsement.

## What the terms mean on Google

Unlike Facebook, Google's grey-market infra runs almost entirely on **Google's own manager-account
and invoicing primitives**, not forged business verification.

| Term | What it actually is |
|---|---|
| **Agency account** | Client account inside a Google Ads **Manager Account (MCC)** owned by a Partner/reseller. Inherits MCC billing, often invoiced. **First-party MCC feature rented out** — not an emulation, the structural difference vs Facebook |
| **Invoiced / credit-line account** | Monthly invoicing instead of threshold billing; Google extends credit, no real-time card charge |
| **MCC** | Google's official multi-account layer. Grey use = renting a seat in someone else's vs building own trust history |
| **Self-farm** | Building own accounts from scratch. Higher control, higher time cost, **no shared-MCC blast radius** |
| **"Threshold account"** | Not a product — standard auto-payments billing whose threshold already ramped through clean cycles, sold/rented for the higher ceiling |

## Account types

| Type | Moderation tolerance | Notes |
|---|---|---|
| **Brand-new self-registered** | Lowest — thinnest trust graph, first campaigns get most scrutiny | Best for self-farm, full control; worst for immediate aggressive scaling |
| **Aged with billing history** | Higher — threshold ramps with clean payment cycles | **History *is* the credential** — the legitimate trust mechanic the grey market resells |
| **Partner / Premier Partner MCC** | Highest structural tolerance claimed | Product the agency-account market rents. Partner status needs spend/certification thresholds **on the agency's side** — client riding inside doesn't personally qualify |
| **Invoiced / credit-line** | High — no real-time decline risk | Chargebacks structurally impossible (no per-transaction charge), but **non-payment on an invoice hits the whole relationship**, worse than one declined card |

**Geo:** US/UK/EU/CA/AU/SG = most mature identity verification, highest scrutiny. OFAC vs serve-pause
vs payment friction are **three different lists** (`07`). Iran is OFAC; Russia is a serve-to pause;
Nigeria/Pakistan/Belarus are **not** on 6163740. 🔺 No official ranked "easiest AIV geo" list.

## Reseller economics 🔺

All vendor-reported list prices, not market clearing prices.

| Metric | Figure |
|---|---|
| Commission on spend | **3–7%** typical |
| Top-up fee (some resellers, separate from commission) | 5–10% per top-up |
| Flat monthly fee model | Exists; favors advertisers already over ~$10k/mo |
| Cited daily cap, self-serve account | $500–5,000/day initially |
| Cited daily cap, agency account | $5,000+/day; one cited case scaling to $15,000/day in week one |
| Onboarding | 24–72 hours signup to live |
| Fee to recover balance from a banned account | ~30% (one vendor) |

Google's 2024 Ads Safety Report: **12.7 million advertiser accounts suspended, 5.5 billion ads
removed** — verify against the report directly.

### Reading a reseller

Red flags, converged across sources:

- **"Unbannable accounts"** — definitionally false; every source flags this.
- **Crypto-only, anonymous, or Telegram-only contact**, no other channel — no recourse if they vanish.
- **Vagueness about who owns the MCC** — you inherit unknown compliance history; MCC-level
  enforcement cascades (`04`).
- **No written replacement policy** — no documented timeline / balance-migration terms, only a
  verbal "we'll take care of you".

**Tell worth reading:** one major vendor's explicit promise is **fund continuity on ban** —
"recover unused balance, transfer to another account" — *not* ban prevention. Vendor's own admission
of the base rate.

Roundup/comparison articles on this topic are frequently affiliate-monetized — ranking isn't
independent judgment.

## Signals Google associates accounts by

Converged from official policy language (names some explicitly) + practitioner consensus (fills in
the rest). **Google does not publish the full set, by design.** No single factor triggers linking;
threshold undisclosed.

- **Payment profile** — card BIN, cardholder name, billing address, bank details. Explicit anchor of
  the suspicious-payment/chargeback enforcement path.
- **Phone number** — creation and verification challenges.
- **Recovery email + underlying Google account.** Circumventing-systems policy targets "creating new
  accounts to re-enter the system" — only deters if Google ties the *person*, not just the account.
- **Browser/device fingerprint** — canvas, WebGL, fonts, timezone/locale consistency.
- **IP/ASN** — exit IP type and consistency across sessions for one identity.
- **GTM container / Google Tag / Analytics property IDs** — shared tagging across "different"
  accounts is a strong cross-link. Frequently overlooked.
- **Merchant Center** — business name, address, domain tie into MC's own verification.
- **Domain WHOIS registrant** reused across otherwise-unrelated properties.
- **Search Console property ownership** — multiple domains verified under one identity ties them.
- **Business name and address** reused across Merchant Center, invoicing, WHOIS, landing page's
  About-us content.

**Consistency required *within* one persona; separation required *between* personas.** Both halves
matter.

### Where Google differs from Facebook

Full comparison table + practical translation — protect the **billing identity and destination**,
not the session — canonical in `04`. Operating consequence here: a payment event, not a login, is the
highest-risk identity-mismatch moment — sequence a persona's activity around its payment events (`02`).

## Antidetect and proxies 🔺

**No rigorous, methodology-backed comparison of antidetect vendors' Google-specific detection
resistance exists in reachable public material** — a genuine gap. Found: vendor marketing and
competitor-authored reviews, structurally unreliable.

- **Dolphin{anty}** — positioned for Facebook/TikTok; Google support present but technically
  demanding per users. Free plan cut from 10 to **5 profiles in Sept 2025**. Flagged *detected* in
  one third-party fingerprint check — **competitor-authored review**, treat as marketing.
- **GoLogin, AdsPower, Octo Browser, Multilogin, Undetectable** — all market Google multi-accounting.
  No Google-specific config docs retrievable this pass.
- **Linken Sphere** — one review cites affiliates running **15–20 Google Ads accounts**. Only
  concrete N-accounts figure found for Google specifically.

**Proxies:**

- **Static residential = reported norm** for an account-holding persona — exit IP behaves like a real
  home connection, stable for the persona's life.
- **Datacenter** — cheap/fast but flagged non-residential by IP-reputation systems, raises baseline
  suspicion before any behavioral signal.
- **Mobile** — carrier-grade reputation, higher cost; shared/rotating CGNAT ranges can cause
  **cross-persona collisions** if reused uncontrolled.
- **Rotating residential is wrong for the account-holding persona** — breaks IP consistency, resets
  the model each rotation. Fine only for scraping unrelated to the persona's own session.

Vendor docs for Bright Data, IPRoyal, Proxy-Seller, 922proxy not retrievable for Google-specific
guidance.

## The compliant path for each grey practice

| Grey practice | Compliant alternative reaching a similar goal |
|---|---|
| Renting a seat in an unknown reseller's MCC for spend headroom | Apply for **Google Partner** status directly, or qualify for **direct monthly invoicing** — same flexibility, no shared-fate MCC risk |
| Buying aged "threshold accounts" to skip the trust ramp | Run a real account through Google's own threshold progression, compliant spend. Slower, but trust is **yours, not revocable by a third party** |
| Cloaking | Build one page simultaneously compliant and converting — fix the actual policy friction (missing product/company info, absent disclosures) instead of hiding it from the crawler |
| Domain-hopping to dodge a disapproval | Fix the specific policy trigger named in the notice, use the real appeal path. Domain cycling to evade detection = policy's **Evasive ad content** |
| Payment-identity fragmentation | Consolidate onto one verified invoiced business relationship where scrutiny is expected |
| Antidetect session separation to hide multi-account operation | Use the **MCC hierarchy** — first-party feature for exactly this, no fingerprint-evasion risk |
| Buying stolen or synthetic-identity accounts | Register a real entity, complete Advertiser Identity Verification **proactively** — removes the "account collapses when verification catches up" failure class |

**Google does not ban multiple accounts per business.** Agencies/multi-brand companies run many
under one MCC routinely. Circumventing systems = creating an account **to re-enter after a
suspension**, or spreading violating content across accounts to evade detection. **Violation is the
evasion pattern, not the account count.**
