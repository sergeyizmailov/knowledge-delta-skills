# Playbook — Finance, trading, crypto

Reviewed 2026-08-27. **The fastest-moving certification surface in the whole policy manual — re-fetch
live pages before launching any geo.** Full policy context → `google-ads/09`.

## Certification by geo

| Geo | Regime | Requirement | Mechanism |
|---|---|---|---|
| **US** | Financial Services Verification + product certs | FinCEN registration, state money-transmitter licenses, documented KYC/AML | Moved to **in-account application** (Admin → Policy → Account) from **Feb 2026**, expanded **May 2026** to all eligible advertisers for exchange/software wallet, hardware wallet, coin trust, and complex speculative product certs |
| **EEA — 24 new markets** | FSV expansion | Country-specific licensing proof | **Rolling enforcement from 2026-07-23.** Advertisers not certified for a newly-added market are blocked there |
| **UK** | FCA-aligned financial promotions | FCA authorization under the general FSV umbrella | 🔺 No UK-specific Google page isolated — verify live |
| **AU** | Australian FSV | ASIC license | Third-party verification via Google's vendor **G2RS**; approved advertisers get an account-level certificate |
| **SG** | FSV Singapore | MAS license, or listed on the Ministry of Law's Licensed Moneylenders / Registered Dealers lists, or exempt | In force since 2022-08-30 |
| **CA** | 🔺 Not isolated this pass | — | Verify before launching Canadian finance campaigns |

## Crypto — what changed and what did not

Certification is required for **exchanges and software wallets, hardware wallets, coin trusts, and
"complex speculative financial products."**

**As of May 2026 all advertisers can apply** — previously a pre-approved subset. The Feb 2026 update
moved the application surface **inside the Ads account UI**, replacing the Help-Center-only form.

> **What requires certification did not change. Only where you apply.** Read announcements about this
> carefully — several secondary sources misreported it as a scope expansion.

**No certification path exists at all for:** ICOs · DeFi trading protocols · crypto loans ·
unhosted-wallet promotion · NFT gambling · crypto aggregator and comparison sites. These are not
"hard to certify" — they are prohibited.

## CFD and forex by regulator

- **EU (ESMA):** binary options marketing to retail **prohibited outright**. CFD, rolling-spot forex,
  and spread-bet marketing to retail **restricted** — mandatory risk warnings, deposit bonuses banned.
  Current EU-wide rule effective **2026-04-01**.
- **UK (FCA):** aligned via its own financial-promotions and authorization regime. **30:1 leverage
  ceiling.**
- **AU (ASIC):** standing CFD product-intervention order since 2021 plus design-and-distribution
  obligations forcing a defined target market. Same 30:1 cap.
- **Binary options are banned everywhere by Google, including educational content.**

Enforcement is not theoretical: the FCA fined multiple firms in 2024–25 for third-party
financial-promotion failures, and **CySEC fines exceeded €200,000** in individual cases for inadequate
affiliate-marketing supervision. Affiliate supervision is a regulated obligation, not just a Google
policy question.

## Claims

Google's financial-products policy prohibits unrealistic-earnings and guaranteed-return claims under
the same **unreliable claims / misrepresentative information** standard applied across regulated
verticals. Misrepresentation is on the **egregious track** — no warning, permanent, propagates
(`04`).

## Funnel and payouts

**registration → deposit/FTD → qualified FTD** — a deposit above a network-defined minimum (commonly
$250+) that also shows real trading or funding activity.

🔺 All figures below are **affiliate-program marketing pages — best-case ceilings, not typical realized
payouts.**

| | Tier-1 CPA/FTD |
|---|---|
| Forex, regulated brokers (FCA/CySEC) | Median ~$600, range $200–$1,200+. Priced on expected deposit size and Q1 trading volume, not a flat any-FTD number |
| Forex, offshore, small deposits | $200–$400 |
| Named program ceilings | Exness up to $1,850 · Vantage $1,200 · FXPro $1,100 · XM $1,000 — **advertised maximums** |
| Crypto exchange/broker CPA | $500–$1,200 per qualified lead, geo and traffic-quality dependent |
| FTD hold period | 14–30 days typical; >45 days described as hard to justify on risk grounds |

Optimize on the **qualified FTD**, not registration — via offline conversion import
(`google-ads/06`). Bidding on registrations teaches Smart Bidding to find people who register.

## Enforcement traps

1. **Certification lag** of days to weeks between application and approval. **Running before it lands
   risks account-level suspension.**
2. **The July 2026 EEA expansion catches advertisers who hold a valid cert for older EEA markets but
   never re-applied for the 24 newly added ones.** This is the highest-probability current failure.
3. **G2RS** third-party verification in Australia adds an external-vendor dependency and delay outside
   Google's own queue — plan the timeline accordingly.
4. Complaint-driven claims enforcement means a single competitor complaint about earnings language can
   trigger review **long after** a campaign is live and scaling.

## What breaks first

**Launching in a newly-certification-required geo before the account-level certificate is actually
approved** — instant geo-level or account-level suspension. Because financial-services violations are
treated as high-severity, repeat incidents **burn trust across the whole MCC, not just the offending
campaign** (`04`).

The discipline that prevents it: maintain a per-geo certificate register with expiry and re-application
dates, and treat any policy announcement touching your geos as a re-application trigger by default.
