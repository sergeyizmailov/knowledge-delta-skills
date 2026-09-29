# Playbook — Dating · Loans and debt · Mobile app UA

Reviewed 2026-08-27. Three verticals with little overlap but each too small for its own file. Policy
context → `google-ads/09`.

---

## Dating and companionship

**Restricted, not prohibited — but certification is mandatory before running any dating ad.**

Two tiers:

- **General Dating and Companionship Certification** — mainstream dating.
- **Restricted Dating and Companionship Certification** — required for hookup/fling/swinger sites,
  affair or infidelity dating, sexual fetish dating, and livestream or chat apps featuring nudity or
  suggestive content.

**Banned outright, no tier permits them:** underage dating promotion · **compensated
companionship/dating/sexual acts** · exploitative or deceptive dating services · **mail-order spouse
services**.

### The operational subtlety

**Certification review examines existing ads, the landing page, AND post-login content.**

That last item is what catches people. A funnel can drift after certification is granted — post-login
UX, matching mechanics, monetization prompts — and **Google's ongoing enforcement catches the drift,
not just the initial submission.** Certification is not a one-time gate.

**Serving cannot happen in:** Algeria, Bahrain, Sri Lanka, Palestine, Iraq, Jordan, Kuwait, Lebanon,
Libya, Morocco, Oman, Nepal, Pakistan, Qatar, Saudi Arabia, Tunisia, Egypt, Yemen. **Japan** requires a
separate certification plus an 18禁 / 18+ warning on ads.

Serving is further gated by user age, SafeSearch state, and whether the query itself carries
sexual-content signals — so eligible inventory is narrower than the geo list implies.

### Funnel and payouts

**click → signup → profile completion → paid conversion.**

🔺 Network figures: CPL (valid lead) $1–$6 · SOI/DOI registration $2–$8 (Tier 2 $2–$5, Tier 3 $1–$3) ·
paid-subscription CPA $40–$100 Tier 1 · RevShare 25–50% lifetime, up to 75% for high volume.

### What breaks first

**Running Restricted-tier creative angles on a General certification**, or letting post-login content
drift toward explicit material after certification was granted on cleaner content. Both are caught by
ongoing content review.

---

## Loans, debt, financial products (US)

### Personal loans — hard numeric thresholds

Google **does not allow** personal-loan ads with an **APR of 36% or higher** in the US, and only allows
loans requiring **repayment in full in 61 days or longer**. This structurally bans short-term and
balloon-style payday products **regardless of how they are labeled**.

> **The policy follows the funnel, not the entity.** It applies to direct lenders, **lead generators,
> and advertisers connecting consumers to third-party lenders** alike. Being one step removed from the
> lender is not a defense.

Advertisers must **prominently disclose APR**, calculated consistently with **Truth in Lending Act**
methodology.

### Debt services

- **Credit repair services are banned outright.** No certification path exists. Standing policy since
  **November 2019**.
- **Debt settlement and debt management** are allowed **only with Google certification**, and
  certification requires the advertiser to be registered, licensed, or approved by the relevant
  regulatory authority or recognized professional body **in each targeted country**. Certification
  availability is **geo-gated to select countries**.

**Personal loans is also one of the policies covered by the three-strike system** (`google-ads/09`) —
so violations here escalate through warning → 3-day → 7-day → suspension rather than suspending
immediately.

### What breaks first

Promoting a product whose real APR or term crosses the threshold while the ad copy describes it
differently. The thresholds are numeric and non-negotiable, and lead generators are explicitly in
scope, so "we just send traffic" does not survive review.

---

## Mobile app UA

### What you actually control

Budget · the bidding target (**tCPI / tCPA / tROAS**) · **asset groups** (text, image, video, HTML5).

**There is no keyword-level control.** Google auto-combines assets across placements from signals.

**Cloak stacks do not apply.** ACi destination is the **store listing**, not a web Final URL (`08`). ACe Final URL must be a non-redirect App Link / Universal Link — MMP redirect links are unsupported.

**Sequencing:** launch on a **tCPI/install goal first** to accumulate a critical mass of labeled
conversion events, then switch optimization to an in-app value event or tCPA/tROAS. The model needs
volume before it can distinguish a likely installer from noise.

**Treat each asset group as one controlled creative test** — one clear hook (feature benefit, emotional
angle, lifestyle context, or offer) — not a dumping ground.

App **and Local** campaigns cap at **100 ad groups/campaign**, versus **20,000** for standard Search/Display. [official: support.google.com/google-ads/answer/6372658, 2026-08-27] PMax **cannot** run an
app-install goal; App campaigns remain mandatory for installs.

### iOS measurement 🔺

**SKAdNetwork 4.0** remains operational, but the **conversion-value schema has a tight bit budget**.

> **The schema must be deliberately prioritized around your highest-spend markets. Low-value markets
> consuming schema bits directly costs signal fidelity in your best markets.** This is a zero-sum
> allocation most teams never consciously make.

Apple is transitioning toward **AdAttributionKit**, which received major updates at WWDC 2025 and is
positioned to replace the SKAN 5.0 that never materialized. Actively evolving — **re-verify before
locking measurement architecture.**

### MMP integration

Requires **Google Analytics for Firebase** or an approved third-party MMP SDK — AppsFlyer, Adjust,
Branch — relaying in-app event postbacks into Google Ads for optimization. 🔺 Verify the current
approved-integration list in-account.

### Benchmarks 🔺

Sources conflict; both readings shown rather than silently reconciled.

| Metric | Value |
|---|---|
| Global CPI, iOS | $2.24 |
| Global CPI, Android | $1.12 |
| Mobile gaming CPI blended | $0.56, +30% YoY — **materially below the Android figure above; likely a different measurement base. Unreconciled** |
| iOS gaming | $2–$5 |
| Android gaming | $1.5–$4 |
| Casual game, Android, Tier 1 | $2–$4 |
| Subscription health app, iOS | $5–$8 |
| Neobank app, iOS | $10–$15 (acceptable given per-user LTV) |

Tier 1 = US/UK/AU/DE/JP — used to validate monetization before scaling, expect the highest CPI.
Tier 2 = BR/MX/ID/TH/PH — used to scale install volume cheaply once monetization is proven.

**iOS CPIs run 2–5× Android** in most verticals.

### What breaks first

**SKAdNetwork's conversion-value bits get mis-mapped** — encoding low-value-market events instead of the
highest-spend geo's real signal. UAC then optimizes blind on iOS in your best market while Android looks
fine, **and the problem hides inside a healthy blended account-level ROAS** until someone splits
reporting by OS.

The fix is a reporting discipline, not a bidding one: **never read app performance blended across OS.**
