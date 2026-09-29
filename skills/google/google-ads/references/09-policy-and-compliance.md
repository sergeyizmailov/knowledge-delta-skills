# 09 — Policy, verification, certifications

Reviewed 2026-09-03. Compliance layer. Suspension survival, appeals under fire, and the grey lane →
`google-grey-ops`. **Gambling and financial policy are the fastest-moving surfaces in the manual —
re-fetch live pages before acting.**

## The one distinction that governs everything

Google runs **three enforcement tracks**. Misreading which track a violation sits on is the most
expensive mistake in this domain.

| Track | Behavior |
|---|---|
| **Egregious** | Suspension **on detection, no warning**, effectively permanent. Appeal exists but "accounts are only reinstated in compelling circumstances". **Propagates to related accounts and blocks new account creation.** |
| **Strike-track** | Warning → 3-day hold → 7-day hold → suspension. Recoverable at every stage. |
| **Limited Ad Serving** | Not a suspension. A partial impression throttle with its own appeals form. Recoverable via compliance + verification. |

**Egregious set:** Circumventing systems · Coordinated deceptive practices · Counterfeit ·
Malicious software · Prescription opioid painkillers · Unauthorized pharmacy promotion ·
**Unacceptable business practices** · Trade sanctions violation · Sexually explicit content · CSAE.

**Destination requirements are explicitly NOT egregious** — that page states "A warning will be issued
at least 7 days prior to any suspension." Broken landing pages recoverable; cloaking is Circumventing
systems. Grey execution of the review layer → `google-grey-ops/05`.

Minimum window to appeal from suspension date: **6 months**.

## Policy taxonomy

Four top-level categories. Each sub-policy has its own `support.google.com/adspolicy/answer/NNNNNN`.

| Category | Sub-policies (answer ID) |
|---|---|
| **Prohibited content** | Counterfeit goods (176017) · Dangerous products or services (6014299) · Enabling dishonest behavior (6016086) · Inappropriate content (6015406) |
| **Prohibited practices** | Abusing the ad network (6020954) · Data collection and use (6020956) · Misrepresentation (6020955) |
| **Restricted content and features** | Ad protections for children and teens (15416897) · Sexual content (6023699) · Alcohol (6012382) · Copyrights (6018015) · Gambling and games (15132179) · Healthcare and medicines (176031) · Political content (6014595) · Financial products (2464998) · Cryptocurrencies (14009787) · Dating and Companionship (15328393) · Trademarks (6118) · Legal requirements (6023676) · Other restricted businesses (6368711) · Restricted ad formats (9481382) · Limited ad serving (13889491) |
| **Editorial and technical** | Editorial (6021546) · Destination requirements (6368661) · Technical requirements (6088505) |

Healthcare decomposes further, each with its own page: prescription drug services (15598647) ·
restricted drug terms (15595717) · pharmaceutical manufacturers (15597836) · unauthorized pharmacies
(15596326) · unapproved substances (15595718) · opioid painkillers (15595821) · speculative/
experimental treatment incl. cell and gene therapy (15596627) · clinical trial recruitment (15598648)
· addiction services (15598649) · abortion (15597837) · birth control/fertility (15595719) · HIV home
tests (15596122) · health insurance (15597838).

**"Other restricted businesses" (6368711)** bundles the long tail, each with its own flag: government
documents (cert) · free desktop software (cert) · event ticket sales (cert) · **third-party consumer
tech support (not allowed)** · solicitation of funds (politicians/parties/tax-exempt charities only) ·
high fat/sugar/salt food (cert, **UK + EU only**) · local services (verification in some locations) ·
**call directory/forwarding/recording (not allowed)** · **bail bond services (not allowed)** · dating
in Japan (18禁 warning required).

## Named suspension strings

| String | What it actually means | Track |
|---|---|---|
| **Circumventing systems** | Cloaked ads or pages · ad-copy or domain variations of previously disapproved content · **creating a new account after a prior suspension** · spreading violating ads across 2+ accounts to dodge detection · **submitting false info during verification** | Egregious |
| **Unacceptable business practices** | Phishing · falsely claiming brand or government affiliation · offering what you cannot deliver · impersonation to extract money or PII · misrepresenting health/safety services · **non-fulfillment due to lack of qualifications** | Egregious |
| **Misrepresentation** | Parent policy. Sub-types: unclear/unavailable business information · **unreliable claims** ("improbable result as the likely outcome") · **dishonest pricing** (hidden fees, undisclosed recurring charges) · clickbait · unavailable offers | Egregious since the 2023 update |
| **Suspicious payment activity** | Mismatched billing name/address, stolen credentials, unusual charge patterns | Billing — **recoverable**, verify within 30 days |
| **Compromised site** | Destination code manipulated **without the owner's knowledge** | Disapproval tier, unless Google reads it as complicit |
| **Business operations verification** | Not a punishment — a **gate**. Failing it pauses; **lying during it is charged as Circumventing systems** |  |

> **2023-11-21, still governing today:** Misrepresentation's "non-fulfillment due to lack of
> qualifications" was reclassified into **Unacceptable Business Practices**, raising it from
> disapproval to immediate suspension. Easy to miss, expensive to learn.

**"Untrustworthy promotions"** is primarily a **Merchant Center** policy, not a distinct Ads
suspension string. 🔺 Do not use it verbatim as an Ads suspension reason without verifying.

## Three-strike system

Introduced 2021-09-21.

| Stage | Trigger | Consequence |
|---|---|---|
| Warning | First detected violation | Email only, ads keep running |
| Strike 1 | Violation persists | **3-day** ad hold |
| Strike 2 | Another within **90 days** | **7-day** hold — "the last and final notice" |
| Strike 3 | Another within 90 days | **Account suspension** |

Strikes **expire after 90 days**. Two resolution paths: **acknowledge** (remove the content + submit
the acknowledgment form → faster resume, strike still counts) or **appeal** (5+ business days, no
guarantee, but success removes the strike immediately).

**Egregious policies are excluded from the strike system entirely** — they suspend on first detection.

Covered policies (verify the live list, Google expands it in phases): enabling dishonest behavior ·
unapproved substances · guns/parts · explosives · other weapons · tobacco · compensated sexual acts ·
mail-order brides · clickbait · misleading ad design · bail bonds · call directories · **credit repair
services · binary options · personal loans**.

> **Counterintuitive finding** [John Horn / StubGroup]: a fully compliant ceremonial sword retailer got
> repeated strikes; every appeal rejected. Resolution came from **acknowledging** the strike plus site
> disclaimers. *"Ultimately, we had to 'acknowledge' the strike to Google so that the ads would resume
> serving."*
>
> **Acknowledge when the fastest path to serving matters. Appeal only with a real factual
> disagreement.** Being right ≠ serving.

## Verification

Two independent checks: **identity verification** (who you are, via documents) and **business
operations verification** (questions about how the business runs, cross-checked against documents).

Triggers: general transparency rollout · suspicious advertising behavior · flagged industry ·
brand-query complaints · feature misuse · **as a required step in a suspension appeal**.

**Timeline: 30 days to initiate, another 30 to complete.** Miss initiate → account **paused**. Miss
complete → risk of **suspension**. Ads can be restricted mid-verification before any deadline passes.

| Advertiser type | Required |
|---|---|
| All | Organization type, who pays, business-operations questionnaire, EU political-ads declaration |
| Billing | Payment history questions, payment-method verification (charge ≤**$1.95** + code, or make a payment), settle balance |
| Individuals | Government photo ID, 6-digit SMS confirmation, **SSN (US)**, video selfie matched to the ID |
| Organizations | D-U-N-S or equivalent, registration documents, affiliation via SMS or corporate email |
| Agencies | Agency info plus per-client information and documentation |

Document bar: **all four corners visible, legible, in color** — not black-and-white.

**Failing verification honestly is recoverable (pause). Lying during it is Circumventing systems
(permanent).** That asymmetry drives every decision here. Grey operational paths (org selfie-skip, BOV
as affiliate vs abandon, nominee vs fabrication) → `google-grey-ops/06`.

Google can force **re-verification** after material account changes.

**API:** `IdentityVerificationService.GetIdentityVerification` returns status and deadlines;
`StartIdentityVerification` (program `ADVERTISER_IDENTITY_VERIFICATION`) returns a time-limited action
URL the advertiser completes manually. Rate-limited — cache, poll infrequently.

**Do not conflate** advertiser identity verification (who you are, gates serving) with payment profile
verification (who controls the payment method, triggered by payment suspicion or a method change).
Both can run simultaneously on separate deadlines.

### Financial services — the fastest-moving surface

**2026-06-23:** expanded from 18 countries to **all remaining 24 EU/EEA member states**, with a
**30-day compliance window** from notification. Verification checks authorization credentials against
national regulator registries. **Australia, Singapore, Taiwan** named as next in line 🔺.

Google's disclosed scale: 1.6B EU ads blocked/removed in the prior year; 327.8M unauthorized financial
ads blocked cumulatively.

## Certifications by vertical

| Vertical | Body / process | Geo notes | Pitfall |
|---|---|---|---|
| **Gambling & games** | Google's own team, per-jurisdiction license verification. Forms: `support.google.com/google-ads/contact/gambling`; social casino via the APAC casino-games form | Cert-eligible incl. AR, AU, AT, BE, BR, CA, CO, DK, FI, FR, DE, NL, ES, SE, UK, US. **BY from 2026-01-22** [16776280]: poker/sports/casino = Ministry of Taxes and Duties; state lotteries = Office of the President or Ministry of Sport and Tourism. **Prohibited outright** incl. AF, DZ, CN, EG, IN, ID, IQ, KR, MY, PK, PH, QA, SA, SG, TH, AE (verify live). DFS needs separate cert in US, BR, Nigeria (Lagos only) | **Separate application per country AND per category.** One account **cannot hold both online-gambling and social-casino certs**. Recertify on any material change or lose it |
| **Financial services** | National regulator cross-check (FCA, ASIC, MAS…) + Google application | **High-APR personal loans (≥36% APR) banned outright in the US.** Credit repair banned everywhere. **Binary options banned everywhere, including educational content.** CFDs/forex/spread betting cert-gated | EU/EEA-wide verification live since Jun 2026 |
| **Crypto / digital assets** | Google cert + local licensing (MiCA in EU, FCA, FinCEN…) | Permitted incl. EU (under MiCA), CH, UK, US, CA, JP, KR, AR, BH, ID, IL, PH, ZA, TH, AE, HK, IS, LI, NO | **No cert path at all**: ICOs, DeFi trading protocols, crypto loans, unhosted-wallet promotion, NFT gambling, crypto aggregator/comparison sites. **Cert required**: exchanges, software wallets, coin trusts, hardware wallets (private-key-storage framing only). Moving to **per-location application** 🔺 |
| **Healthcare / pharma** | **LegitScript** (primary) or **NABP** (US alternative), then link the cert in the healthcare flow | 40+ countries with distinct rules; some **prohibit online pharmacy advertising entirely (e.g. Poland)** | Unauthorized-pharmacy promotion and opioid painkillers are **egregious — no warning** |
| **Alcohol** | No universal cert — compliance is **location-targeting based** | **Poland**: brand/informational limited to **beer only**, separate application | Do not confuse with the EU/UK **AVMSD** legal-requirements policy restricting alcohol ads targeting minors |
| **Political** | Google Election Ads verification | Required in AR, AU, CL, IN, IL, MX, NZ, ZA, UK, US. **India** needs Election Commission pre-certificates per ad. **Mexico: only agencies may run election ads** | Targeting restricted to **geography, age, gender, context only**. Mandatory "Paid for by" disclosure |
| **Addiction services** | Healthcare application, per location | **Approved only in AU, CA, FR, IE, NZ, US** | Excludes impulse-control, behavioral, and nicotine addiction from this gate |
| **Dating** | Two tiers: **General Certificate** vs **Restricted Certificate** (racy/sexual themes, limited serving). Form needs Customer ID, app IDs or domains, working test credentials if login-gated | Cannot serve in DZ, BH, LK, PS, IQ, JO, KW, LB, LY, MA, OM, NP, PK, QA, SA, TN, EG, YE. **Japan** needs separate cert + 18禁 warning | Serving further gated by user age, SafeSearch state, and sexual-content signals in the query itself |
| **Weight loss / supplements** | **No certification exists** | — | Governed indirectly via **Misrepresentation → Unreliable claims** (15936857). "Lose 20lbs in a week" is a suspension risk you **cannot certify away** |
| **Legal services** | No cert. General editorial + local-law responsibility | Policy explicitly disclaims completeness | The advertiser bears the full local-law burden. No Google pre-clearance safety net |
| **CBD / hemp** | Recreational-drugs page [16489299]. Topical hemp CBD **THC ≤ 0.3%** allowed (creams/sprays/lotions). FDA-approved pharma CBD: apply; **CA, CO, Puerto Rico** only. Retailer: LegitScript + CBD Ads Certification form. Canada Search-only licensed **pilot through 2026-12-31** [16851502] | Marijuana / pipes / ingestible CBD **not** in the allowed examples | Grey no-path table → `google-grey-ops/08` |

### Gambling — three rule changes in six months

2026-03-23 EMEA-managed account tightening · Jul 2026 further eligibility update · **2026-08-26 forms
and standards revised globally — all new applicants must use the revised forms** [confirmed 2026-09-03,
support.google.com/adspolicy/answer/17258294] · **2026-09-14 the March requirements expand to all
categories under the policy (good-policy-health gate, all gambling/games categories)** [confirmed
2026-09-03, support.google.com/adspolicy/answer/17199930 — not yet effective as of this review].

The direction: mandatory per-jurisdiction, per-category certification with **"good policy health" as a
prerequisite before licensing proof is even reviewed**. Any gambling workflow built from this file must
re-fetch live pages first.

## Destination requirements

| Disapproval reason | Trigger |
|---|---|
| Destination not working | Broken functionality or HTTP errors on common browsers/devices |
| **Destination mismatch** | Display-URL domain does not match final URL, or redirect to a different domain than shown |
| Destination not crawlable | Inaccessible to AdsBot — robots.txt named `Disallow`, `<meta name="AdsBot-Google" content="noindex">`, auth walls, crawl capacity exhausted by click-tracker hops. **JS-only rendering is not a named official example** (16428929); DSA 9229701 names errors, login walls, >10 redirects |
| Destination not accessible | Unavailable in the targeted geography |
| Destination experience | Frustrating navigation, abusive UX, **Better Ads Standards** non-compliance |
| Insufficient original content | Pages built primarily to host ads, scraped/duplicated content, pages that merely redirect |
| Unacceptable URL | Non-standard syntax, bare IP addresses, disallowed characters |
| Phone number issues | Unverified, inactive, premium-rate, virtual, or non-local numbers |

**The cloaking test, stated precisely:** the operative question is a **content mismatch between what
AdsBot and reviewers see and what a live visitor sees** — not "did you use a redirect". Redirects are
not themselves the violation. Manipulating ad components (text, image, video, domain, subdomain) "in
an attempt to bypass detection" is.

**E-commerce required elements** — assembled from Destination requirements + Misrepresentation, not
one canonical list: company name, physical address, and contact details prominently displayed ·
all-in pricing with full cost disclosure · refund/return policy · visible license or registration
numbers for regulated verticals.

## How enforcement actually behaves

- **Fast approval, later sweep.** Initial review is largely automated pattern-matching. Ads approved
  for weeks get disapproved in a later re-review pass with no advertiser-side change. Google: "a
  combination of Google AI and human evaluation" with escalation to "specially-trained experts" for
  complex cases — deep review happens *after* the money starts moving.
- **Linked-account propagation is real, multi-signal.** Google: "Accounts related to the suspended
  account may be suspended" and "any new accounts that the advertiser tries to create may also be
  suspended." Practitioner-consensus signals (no official list): shared payment profile · phone · IP ·
  domain · **GTM container ID** · business name · verification documents. No single factor alone
  triggers it; threshold undisclosed.
- **Ban evasion is charged as its own offense** on top of whatever caused the original suspension.

## Appeals

1. In-account banner → **Contact Us** → appeal form, which surfaces the relevant policy inline.
2. **Billing suspensions** require payment-method verification within 30 days before Google will even
   process the appeal.
3. Policy suspensions: "only reinstated in compelling circumstances". Review 5+ business days.

**What works** [StubGroup and forum consensus]:

- **Identify the exact root cause before appealing.** Generic "please review my account" appeals and
  repeated near-identical submissions reported to *worsen* outcomes — reviewers read them as evasive.
- **Evidence, not argument** — contracts, licenses, credentials, proof of operations.
- Circumventing systems: run a **full self-audit** of account, site, campaigns for redirects,
  mismatched destinations, injected code, cloaking artifacts *before* writing, then address findings
  explicitly.

**Why appeals auto-reject:** the appeal restates general compliance instead of addressing the specific
sub-policy · **the underlying issue is still live at re-review time** (re-review evaluates current
state, not intent) · multiple parallel appeals (guidance is explicitly one at a time) · an
egregious-track appeal with no new evidence.

🔺 No official documented phone or chat escalation path was confirmed this pass. Practitioners
reference in-product Help/chat for accounts with active spend and an assigned strategist for large
spenders — both spend-gated and changing over time.

## Preventive posture

- **The pre-suspension window is the real appeal opportunity.** Destination requirements give 7 days;
  strikes give a warning plus two hold periods. Egregious policies give nothing by design.
- **Keep the payment profile exactly matched** to registration documents and profile country.
  Mismatches independently trigger business-operations-verification failure, outside any suspension.
- **Multiple accounts per business are not banned.** Agencies and multi-brand companies do this
  routinely under one MCC. What crosses into Circumventing systems is creating a new account **to
  re-enter after a suspension**, or spreading the same violating content across accounts to evade
  detection. **The violation is the evasion pattern, not the account count.**
- 🔺 **Policy Manager** is referenced across secondary sources as the pre-flight tool, but no official
  page or current navigation path was confirmed this pass. Verify in a live account before stating a
  menu path.
