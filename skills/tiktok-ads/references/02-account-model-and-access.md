# 02 — Account model, roles, asset sharing, agency accounts

Verified 2026-09-14 against `ads.tiktok.com/help` and `business-api.tiktok.com/portal/docs`.
Limits and role tables are the most perishable rows here — re-check before quoting a number to an
operator. Open unknowns are flagged inline as `UNVERIFIED`.

## The object model, and what it means for you

```
TikTok for Business login
└─ Business Center (BC)  [bc_id]            org + asset container; Standard or Enterprise
    ├─ Members            Admin | Standard   (+ Finance Manager | Finance Analyst overlay)
    ├─ Partners           other BCs granted access to named assets
    └─ Assets
        ├─ Ad account / advertiser  [advertiser_id]   billing + campaign unit
        ├─ TikTok account (Identity)[identity_id]     AUTHORIZED, never owned
        ├─ Pixel                    [pixel_id/pixel_code]
        ├─ Catalog                  [catalog_id]
        └─ TikTok Shop
```

Three distinctions that cause real failures:

- **BC ≠ ad account.** Your role in the BC and your role on the ad account are separate grants. You
  can be a BC Standard member with Admin on one ad account, or a BC Admin with no ad-account role.
- **Authorized ≠ owned.** A TikTok organic account (your Identity source for Spark Ads) is
  authorized by its owner via QR code and is revocable by them unilaterally, at any time, from the
  app. Your Spark ads die with it. Never build a campaign whose only identity is a creator account
  you do not control without a written authorization term.
- **Shared ≠ transferred.** Sharing grants access; transfer moves ownership and is **not
  self-serve** — TikTok gates true ad-account transfer behind a rep consultation. Assume you will
  never own a shared account.

## Roles — the matrix that decides whether you can do the job

**BC level**

| | Admin | Standard |
|---|---|---|
| Add/remove members, manage partners | yes | no |
| Create ad accounts, request access, transfer assets | yes | no |
| Share assets with partners | yes | no |
| Manage BC verification, 2-step verification | yes | no |
| Create Account Groups, share audiences across advertisers | yes | no |
| Billing | only with a Finance role | only with a Finance role |

Finance is an **overlay**, not a level: *Finance Manager* manages balance/payment methods/billing
groups, pays invoices, applies for a credit line; *Finance Analyst* is read-only over the same.

**Ad-account / asset level — this is the role a shared buyer actually receives**

| | Admin | Operator | Analyst |
|---|---|---|---|
| View ads, performance, reports | yes | yes | yes |
| Create & edit campaigns/ad groups/ads (incl. their budgets) | yes | yes | no |
| Manage audiences | yes | yes | no |
| Ad-account finance | yes | no | no |
| Ad-account settings: install pixel, connect TikTok account, config | yes | **no** | no |

**The trap.** *Operator* is the default grant and it is enough to build and run campaigns, but it
cannot install a pixel, connect an identity, or change account settings — and that is discovered at
launch. Resolve it at intake: if the job includes wiring tracking or attaching an identity, you need
**ad-account Admin**, not Operator. `tiktok-ops` `doctor` answers this against the live account; a
successful read proves nothing.

Catalog access is its own pair: *Catalog management* (edit products and catalogs) vs *Ad promotion*
(build ads from the catalog only).

`UNVERIFIED`: the exact minimum role that can authorize a developer app / mint an OAuth token
against an `advertiser_id`. TikTok does not state it on a help page. Treat ad-account Admin as the
working requirement and confirm on the live authorize screen.

## Asset sharing — the rules that bite

- **One hop only.** A pixel or catalog shared BC→BC can be re-shared by the recipient to *its own ad
  accounts*, but never onward to a third BC. Sharing chains do not exist by design; a "sub-share"
  you were promised is either a lie or a partner relationship you have not been told about.
- **A pixel links to at most 100 ad accounts within one BC.** No stated cap on how many BCs it can
  be shared to.
- **Ad-account access requests are approved by that account's Admin**, not by the BC that wants it.
- Owning BCs can revoke a partner's access to any asset at any time, with no notice.
- `UNVERIFIED`: whether a cross-BC-shared pixel keeps firing and reporting after revocation, and how
  fast. **Operate as if revocation breaks reporting immediately.** Treat "access lost" as an
  expected failure mode with a detection path, not an anomaly.

## Hard limits (verified 2026-09-14 — re-check before quoting)

| Limit | Value |
|---|---|
| Business Centers per user | 30 |
| Ad accounts per BC | 150 |
| Members per BC | 1,000 (20 Admin + 980 Standard) |
| TikTok organic accounts a BC may hold authorization for | 200 |
| BCs one organic account may authorize | unlimited (no stated cap) |
| Ad accounts per pixel, within one BC | 100 |
| Catalogs per BC / per user / users per catalog | 2,000 / 100 / 100 |
| Enterprise BC depth | ≤5 tiers (1–4 Enterprise + 1 bottom Standard) |

**Account Groups exist only in Standard BC, not Enterprise** — counterintuitive, and it changes how
you plan permissioning for a large portfolio.

Standard BCs cannot be upgraded to Enterprise; Enterprise is a separate structure you build above
them. Enterprise comes "with finance" (consolidated billing against legal entities) or "without"
(org structure only).

## Permanent-at-creation fields — the constraint that shapes a portfolio

**Timezone, currency, and country/region are set when the ad account is created and cannot be
changed.** TikTok's own guidance is to create a new ad account rather than try to edit them. BC
creation carries a similar warning that business information may not be editable afterwards.

Consequences you must design around, not discover:

- A multi-GEO portfolio needs **at least one ad account per (country × currency × timezone)**. You
  cannot repoint one account at a new GEO by changing targeting if the currency or reporting
  timezone has to differ.
- Every daily number, every budget minimum, and the join key against your tracker are in the
  account's timezone and currency. Read them from `/advertiser/info/` and put every number in the
  plan in **major units with the currency named** — an unlabeled number is unusable to whoever
  reconciles it later.
- Not every country supports direct ad-account creation. Check TikTok's "available regions for ad
  account creation in Business Center" page for the target GEO before promising a launch date.

## Billing — and the hard wall for an agent

Three models: **Manual/prepay** (deposits; delivery stops at zero balance with no grace),
**Automatic payment** (charge at a spend threshold or bill date), **Monthly invoicing** (net-30,
eligibility-gated). Self-serve defaults to prepay.

*Billing Sharing* lets one bill-to party cover another account's spend — **the original bill-to
party stays liable for all of it** regardless of which account receives the bill.

**The agent can read balance, spend and transactions via the BC API. It cannot add funds, change a
payment method, move balance, or request a refund — those are UI-only and Finance-role-gated.**
Design every runbook so a funding step is an escalation to a human, never a blocked automation.
`UNVERIFIED` as an absolute, but no billing-write endpoint surfaced in a full research pass.

Payment methods differ by region (NA: cards + PayPal, USD/CAD · EMEA: cards + PayPal, GBP/EUR ·
APAC: bank transfer, PayPal, local wallets, cards). New-method verification withdraws ~$10 USD and
refunds within ~15 days. Per-transaction top-up caps exist; verify live rather than hardcoding.

## Agency accounts — what is real and what is grey

**Official structures:**
- *Marketing Partners* directory; the **Channel Sales Partner** tier (launched Jan 2026) gives
  API-driven templated account provisioning and requires supporting ≥1,000 active advertisers.
- *Agency Advantage* ad-credit matching for qualifying agencies (figure is third-party sourced —
  verify before quoting).
- A BC created with business type **Agency**. No official page enumerates a feature delta beyond the
  flag itself.

**Why buyers want agency-shared accounts:** new self-serve accounts sit under probationary daily
spend caps, and agency-backed accounts are reported to be exempt. More importantly, regulated
verticals need authorization that attaches to the **verified entity**, so an agency that already
holds gambling or financial-services authorization in a market can host campaigns a fresh self-serve
account cannot. Both claims are practitioner-sourced, structurally consistent with the documented
verification model, and not stated by TikTok as such.

**The reseller market** — leasing "agency cabinets" from third parties, typically against a minimum
daily spend commitment — is active and is **not a TikTok program**. It is arbitrage on top of a real
agency relationship. Risks that are yours, not the reseller's: ToS exposure on access resale, funds
held on a balance you do not control, and no recourse when the account dies. Vet by asking which
listed Marketing Partner the account actually belongs to; if there is no answer, price the risk
accordingly. Field detail on the RU-language reseller market: `11`.

## Suspension, appeals, and blast radius

Documented suspension triggers: complaints about the account, problems with content/qualifications/
services advertised, **changing the landing page after campaign creation**, suspected malicious
behavior during ad creation, general guideline violations.

Effects: all ads stop immediately; the account loses some features including transferring and
accessing pixels; a suspended agency account cannot create or fund other ad accounts.

**The deadline to remember is 30 days.** TikTok's own suspensions page, verified 2026-09-14: *"If
this is your first violation, you'll have 30 days to address the issues with your ads or ad account
or submit an appeal."* After that window *"the suspension will be permanent. You won't be able to
appeal this decision."*

A **180-day appeal window** is widely repeated in third-party writing. It does **not** appear on that
page. Treat 30 days as the number you plan against and 180 as `UNVERIFIED` — planning against the
longer figure is how an account becomes permanently dead while someone waits. Fix the underlying violation *before* appealing — reviewers check whether it still
exists. Repeated appeals for the same issue delay processing.

`UNVERIFIED` and high-severity: whether an owning BC's suspension cascades to partner-shared assets
beneath it. Assume it can. Do not concentrate a portfolio's pixels and catalogs under one BC you do
not control.

## Surfaces: what has an API and what does not

| Surface | API? |
|---|---|
| Ads Manager (campaigns, ad groups, ads, reporting, audiences) | **Yes** — this is the Marketing API |
| Business Center | **Partial** — some read/manage endpoints (balance, transactions, partner add, pixel link). Member/role management, verification, payment methods: UI-only |
| TikTok One (creator discovery, production, project reporting) | No public Marketing API surface found |
| "TikTok Business Suite" | Not an official product name — blog terminology. Do not build against it |

**Design consequence.** The agent's write surface is the Marketing API against one `advertiser_id`.
BC administration — sharing, revoking, verification, funding, appeals — is human-Admin work. Build
runbooks that *detect* BC-side state and escalate, never ones that assume the agent can fix it.

## Non-negotiables

- Confirm the **role**, not the invitation, before promising an operation. Read access proves nothing.
- Treat timezone, currency and country as permanent. Getting them wrong is a new account, not an edit.
- Treat every shared asset as revocable without notice, and detect loss of access explicitly.
- Never let the agent assume it can fund an account. Funding is an escalation.
- An authorization for a regulated vertical binds to a verified entity and usually a specific ad
  account. A replacement account needs a new authorization (`08`).
