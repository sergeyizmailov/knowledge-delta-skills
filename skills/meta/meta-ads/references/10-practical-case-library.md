# Practical Meta Ads Case Library

Last reviewed: 2026-07-22

Match a case by mechanism, measurement design, business model, conversion lag, and outcome definition — not headline percentage. Never convert a published lift into a benchmark.

## 1. How to use

1. Identify original constraint and business outcome.
2. Check whether the comparison was causal, directional, or merely attributed.
3. Compare country, funnel, value model, conversion delay, event volume, sales process with current account.
4. Reuse the decision rule, not the reported lift.
5. State what would invalidate transfer to the current account.

### Proof grades

| Grade | Meaning |
|---|---|
| **A — causal design reported** | Concurrent randomized, conversion-lift, or geo-holdout design identifies treatment + counterfactual. May still be an interested-party source without raw data/audit. |
| **B — structured comparison** | Comparator exists; allocation/power/timing/other material design details missing. |
| **C — attributed/pre-post** | No interpretable counterfactual; hypothesis or implementation example only. |

No case is an independently audited universal performance claim.

## 2. E-commerce and omnichannel

| # | Context → change → result | Grade / source |
|---|---|---|
| 1 | Mejuri (US DTC jewelry): attributed revenue missed incremental-ROAS goal → shifted 25% budget to upper-funnel acquisition, measured new-customer revenue (70/30 geo holdout, 3wk+post) → 11% then 12.9% incremental-sales lift, 57% iROAS gain. Decision: when revenue concentrates on existing buyers, test incremental new-customer revenue, don't scale off blended ROAS. 25% share is not portable. | A, vendor case: haus.io/case-studies/how-mejuri-discovered-what-was-really-driving-sales |
| 2 | HexClad (US premium cookware, ~$700 bundle): short read misjudged long-consideration purchase → 3-cell matched-geo holdout (BAU/increased/no-ads), 2wk treatment+3wk post → cost/incremental acquisition 56% (BAU) and 67% (increased) lower than the initial 2wk read. Decision: derive test/post windows from observed purchase lag before calling high-AOV media inefficient. | A, vendor case: haus.io/customer/hexclad |
| 3 | DSW (US footwear, meaningful store sales): online-only optimization missed store value → joined POS/offline events, simplified structure, omnichannel vs online-only BAU (30% no-ad holdout) → conflicting result blocks (23%/16%/29% vs 15%/18%) across sources. Decision: feed offline sales into measurement/optimization; separate incremental from attributed BAU; don't repeat either headline without resolving definition. | A-/B+, agency case: tinuiti.com/work/paid-social-case-study-dsw-meta |
| 4 | The Athlete's Foot (MX/LatAm sneakers): bundled Advantage+ investment, catalog diversity, offer/CTA, prospecting+retargeting → claimed Meta Conversion Lift vs BAU (allocation/window/confidence absent) → 165% incremental "ROAS" on AddToCart, 16.2x attributed AddToCart "ROAS", 1.79x incremental ROAS. Decision: require purchase/revenue outcome + equalized spend + defined value field before scaling off a lift result; AddToCart is not realized revenue. | B, Meta-partner case: adsmurai.com/en/case-studies/taf-meta |

## 3. Mobile-app

| # | Context → change → result | Grade / source |
|---|---|---|
| 5 | Blibli.com (Indonesia e-comm app): launched always-on Advantage+ app acquisition → baseline/control/attribution/MMP/duration undisclosed → 34% install lift, 2.4x purchase lift, 32.4x ROAS. Decision: treat as hypothesis only; graduate on MMP/backend purchase value, not this number. | C, Meta guide (cloudfront PDF) |
| 6 | Sephora Singapore (beauty app): Advantage+ app vs manual install ads, budgets/overlap/duration/confidence undisclosed → 23% higher reach, 45% more installs, 43% lower CPI; activation/purchases/retention/LTV not reported. Decision: use CPI as a screen only; require D7/D30 activation or value guardrails before shifting budget. | B-/C+, Meta guide (cloudfront PDF) |
| 7 | Century Games (mobile game): Advantage+ value optimization vs manual install, no randomization/equal-spend/cohort horizon disclosed → 70% more purchases, 50% lower cost/purchase, 65% higher ROAS; automation and optimization goal changed together, so effects unseparable. Decision: test purchase/value optimization holding market/spend/creative constant; decide on cohort ROAS. | B-/C+, Meta guide (cloudfront PDF) |
| 8 | Supersonic/Unity (hybrid-monetized games): fed impression-level ad revenue via AppsFlyer ROI360, optimized IAA separately from IAP → one title +42% D7 ROAS, another 4x installs; reached 53% of Meta spend in 6mo; results from different games, no disclosed randomization. Decision: send/optimize separate IAA/IAP values; require fixed-title/market cohort ROAS and non-cannibalization proof. | C, AppsFlyer case: appsflyer.com/customers/supersonic-unity |

## 4. Local/service lead-gen

| # | Context → change → result | Grade / source |
|---|---|---|
| 9 | TECOBI/Medved Auto (CO auto dealer): A/B lead-volume vs conversion-leads optimization via CRM CAPI → 68% higher conversion rate, 8% lower cost/qualified lead ("qualified" undefined). Decision: keep capture/follow-up constant, test earliest reliable CRM event separating buyers from form-fillers. | A, Meta CRM guide + advertiser corroboration |
| 10 | Top Business Class (premium-flight agency, call-close sale): BAU mobile campaign vs same + call add-on, 2wk Meta conversion-lift study, desktop excluded → 22% more qualified leads, 24% lower cost/incremental qualified lead. Decision: when a live call is unavoidable, measure connected/qualified calls or bookings — not call-button taps. | A, agency + Meta lift material |
| 11 | Ortner's Resort (DE hospitality): native lead form + voucher + automated nurture vs website ads, destination randomization/attribution unclear → 3.7x qualified leads, 62% lower CPL, 206% more inquiries, 50% more bookings; offer/friction/creative/nurture changed together. Decision: judge native forms as a capture-and-nurture system, not a CPL tactic — form surface alone isn't credit-worthy. | A-, advertiser/Meta case |
| 12 | SumUp (EU payments): A/B tested one eligibility question ("business owner?") → 4x lower CPL after filtering; downstream revenue undisclosed. Decision: test one high-information disqualifier before a long questionnaire; more form friction isn't always better. | A-, Meta lead guide |
| 13 | Mira Clinic (TR cosmetic surgery): A/B standard lead vs conversion-leads optimization via CRM CAPI, "quality lead" undefined → 48% more "quality leads", 36% lower CPL. Decision: name the downstream event before launch; report booked/attended/paid separately — don't copy result without knowing which CRM event trained delivery. | C+, Meta case via implementation partner |
| 14 | AdEspresso (B2B software, $2,000 spend): sequential (not concurrent) landing-page-form vs native-form test → LP: 1,077 leads/50% visit-to-lead/$0.93 CPL; native: 1,057 leads/67% form conv/$0.95 CPL; fields/placement/reach/timing differed. Decision: compare destinations through the next business stage; near-equal CPL doesn't prove surface equivalence. | B+, transparent but confounded original case |

## 5. B2B/SaaS

| # | Context → change → result | Grade / source |
|---|---|---|
| 15 | Podium (US B2B AI-agent software, cold start): consolidated CBO screening, micro-persona creative, known-lead exclusion, booked-demo optimization → six-figure ACV month one, 3.98x pipeline ROI/60 days; spend/SQL counts/closed-won revenue absent, pipeline ≠ cash ROAS. Decision: for sparse B2B outcomes start on the closest event proven to predict pipeline, shift deeper only after reliable volume, keep pipeline and closed-won CAC separate. | B, named agency case: flighted.co/case-studies/from-zero-to-6-figure-meta-ads-acv-for-podium |

## 6. Cross-case post-mortem patterns

| Pattern | Symptoms | Cases | Action |
|---|---|---|---|
| A. Optimizer rewarded a proxy | CPI/raw CPL/AddToCart/purchase count improves, retained value or qualified/cohort revenue doesn't | Mejuri, Century Games, Supersonic, TECOBI, SumUp | Map P&L outcome to deepest timely event with reliable volume; keep downstream quality as guardrail |
| B. Measurement boundary excluded value | Media looks inefficient online/immediately post-treatment; store/marketplace/phone/delayed value appears later | DSW, HexClad, Top Business Class | Pre-register sales surfaces and conversion/post-treatment windows from backend behavior |
| C. Two campaigns ran, no causal test | Large lift claim, no allocation/equal spend/overlap control/confidence/reconciliation | Blibli, Sephora, Century Games, Supersonic, Podium, parts of Ortner's/TAF | Call it directional; rerun material decisions through Experiments/Conversion Lift/powered geo holdout |
| D. Form friction moved volume and quality together | Raw CPL/form CVR moves, qualification/revenue moves differently | SumUp, AdEspresso, Ortner's | Test smallest useful qualifier; compare cost at every CRM stage |
| E. Treatment was a package | Automation, budget, creative, offer, audience, page, nurture changed together | DSW, TAF, Ortner's, Podium | Describe conclusion at package level; don't credit an unisolated component |
| F. Platform economics ≠ contribution/incrementality | ROAS/pipeline ROI/platform CPA looks strong without refunds/margin/new-customer split/cash revenue/holdout | Mejuri, TAF, Blibli, Podium | Reconcile backend contribution; use lift measurement when causality changes investment |
| G. Technical readiness inferred from partial success | Assets visible, token reads account, but creative creation/delivery/billing still fails | Account-specific post-mortem, 2026-07-24 | Token scopes, System User asset tasks, Page/IG identity, app state, payment eligibility, restriction are independent gates — run minimal `PAUSED` write + identity probe before full build; inspect Billing/Account Quality separately; never use token regen/card swap/replacement assets as enforcement bypass. Full workflow: `13` |

## 7. Source and evidence limitations

Public case studies select positive results, commonly published by Meta/an agency/a vendor involved in the work. None of the 15 exposes an independently audited raw dataset. Absolute spend, sample size, MDE, confidence intervals, attribution settings rarely disclosed. "Qualified lead" usually undefined — require the actual CRM field/rule before transfer. App cases commonly omit ATT/SKAN/AEM state, OS mix, fraud controls, retention, payback, cohort LTV. Country/objective/naming/availability/measurement are volatile — recheck source date and live account. A case lift is evidence a treatment is worth testing under similar conditions, not a forecast.
