---
name: google-ads
description: "Senior Google Ads, single-account layer: plan, launch, audit, diagnose, scale one account. Search, PMax, Demand Gen, Shopping, AI Max, Smart Bidding, RSA, tCPA/tROAS, tracking/OCI, GAQL and API mechanics. Use for: 'why is CPA up', 'PMax cannibalizing brand', 'structure a Search account', 'which conversion action is primary', 'GAQL for search terms'. Executing an API launch (googleops) and grey infra/survival is google-grey-ops, feeds/Merchant Center is google-feed-ops, trackers/metrics are tracker-ops, portfolio/multi-account allocation is senior-buyer-ops. Not organic SEO."
---

# Google Ads

Operate as a senior Google Ads practitioner. Treat UI labels, eligibility, policy, API behavior,
prices, and benchmarks as volatile. Research reviewed **2026-08-27**; hub dates re-verified 2026-09-03.
Baseline 2026-09-03 (Sonnet 5 blind, 4 tasks): 3 [W] (AI Max opt-out, Search-vs-PMax rule, MC link services), 1 [R] (API mutate basics); rerun with skills fixed 6/6 flagged items. Verify primary sources whenever
the answer depends on current behavior.

Cross-platform note: this pairs with `meta-ads`/`meta-grey-ops`. **Do not port Meta structure doctrine
to Google.** Google is explicit-search-intent driven — Menachem Ani: "every search query is a person
telling you something, not a demographic."

**The rule is not "don't consolidate" — it is "never merge different intent or different economics."**
Consolidation is how you clear Smart Bidding's volume floor (`01`); Hagakure-style consolidated
structures are standard on Google. What fails is Meta-style consolidation *across* price tiers,
margins, funnel stages, because Google can read the intent Meta cannot. Ani prescribes segmentation by
**economic/price tier**, isolated retargeting, product-theme grouping — not fewer campaigns. See `05`.

## Check these two things first on any 2026 account

1. **The AI Max forced migration** (`05`). Campaign-level broad match and Automatically Created Assets
   auto-convert 2026-09-01 → 09-30, no rollback; migration is in progress as of this review (confirmed
   2026-09-03). The opt-out window (disabling the legacy setting before Sep 1) has closed.
2. **The 2026-08-17 budget-limited target enforcement** (`02`). Any tCPA/tROAS drift on a "Limited by
   budget" campaign since that date is **expected behavior, not a tracking bug** [confirmed 2026-09-03].

## Route references

Read only what the task needs.

| Need | Reference |
|---|---|
| Evidence rules, refuted claims, volatile list, intake | `references/00-evidence-and-maintenance.md` |
| Campaign types, Search vs PMax vs Shopping vs Demand Gen vs App picker, MCC, arbitration | `references/01-account-architecture.md` |
| Bid strategies, Ad Rank, Quality Score, budgets, Auction Insights | `references/02-bidding-auction-quality.md` |
| Match types, prioritization, search terms, negatives, n-grams, competitive intel | `references/03-keywords-and-negatives.md` |
| RSA specs, Ad Strength, pinning, assets, ad testing, dynamic text, auto-assets | `references/04-creative-and-assets.md` |
| **AI Max migration, AI Overviews, what survives September** | `references/05-ai-max-and-ai-surfaces.md` |
| Conversion actions, click IDs, enhanced conversions, OCI, consent, sGTM, attribution | `references/06-tracking-attribution.md` |
| PMax, Demand Gen, audiences, cannibalization, failure modes | `references/07-pmax-demand-gen-audiences.md` |
| Benchmarks, unit economics, impression-share math, diagnostic tree, columns | `references/08-benchmarks-diagnostics.md` |
| Policy taxonomy, enforcement tracks, verification, certifications, destination rules | `references/09-policy-and-compliance.md` |
| API access, GAQL, mutates, mass launch, Scripts, AI pipelines | `references/10-api-and-automation.md` |
| API errors: code → cause → fix | `references/11-api-error-catalog.md` |
| Operator edge — ratcheting, signal engineering, wasted-spend hunts, dead techniques | `references/12-operator-edge.md` |

Always read `00` before making a numerical claim or citing a benchmark. Read `10` before any API
automation, and `09` before touching a regulated vertical.

## Playbooks

Vertical worked examples: `playbooks/b2b-saas.md`, `playbooks/local-leadgen.md`,
`playbooks/us-ecommerce.md`.

## Boundaries

- **Buy well** → here.
- **Don't get killed / agency accounts / billing+destination survival** → `google-grey-ops`.
- **API mechanics** (GAQL, mutate graph, quotas, OCI) → here (`10`). **Executing a launch** →
  `google-grey-ops/00` + the `googleops` CLI (spec → `validate_only` → PAUSED → read-back →
  activate); never hand-write mutate code when the CLI covers the shape.
- **Feed, Merchant Center, product eligibility** → `google-feed-ops`. Shopping/PMax *campaigns* stay
  here (`01`, `07`).
- **Count money, tracker sync, gclid postbacks** → `tracker-ops`.
- **Is this difference real** → `measurement-experimentation-ops`.
- **Portfolio and team decisions** → `senior-buyer-ops`.

## Model

```text
MCC -> account -> billing/verification/conversion actions/account-level negatives
  Campaign -> type/budget/bid strategy/geo/language/conversion goals/networks
    Ad group / Asset group -> keywords or signals/audiences/URLs
      Ad / Asset -> creative/copy/final URL/tracking
```

Diagnose at the level owning the setting. Campaign, ad group, ad statuses are separate — check all
three.

## Workflow

1. Derive break-even CPA/ROAS from true landed margin before touching anything (`08`).
2. Verify conversion tracking **before** judging performance. A bidding algorithm cannot optimize a
   broken signal, and most "bad performance" is bad measurement (`06`).
3. Confirm which conversion actions are primary and include-in-conversions. This silently defines what
   Smart Bidding chases.
4. Check policy and certification eligibility for the vertical and every target geo (`09`).
5. Choose campaign type by intent, not by what Google is promoting (`01`, `07`).
6. Consolidate to reach the conversion-volume floor. Fragmentation is the most common self-inflicted
   wound.
7. Launch new campaigns on Maximize Conversions/Value to build a real baseline, then layer a target
   (`02`).
8. Protect exact-match intent from PMax with brand exclusions plus a tight exact-match brand campaign
   (`07`).
9. Predefine the judging window from the conversion-lag distribution, not from the calendar.
10. Reconcile Google against backend/CRM before drawing any optimization conclusion.

For API launch: build the full mutate graph, run `validate_only=true`, create everything **PAUSED**,
then enable deliberately. A successful read proves nothing about write access.

## Diagnose in order

```text
eligibility/policy/billing -> delivery -> auction -> click quality -> landing continuity
-> conversion tracking -> business value -> attribution
```

- **No spend**: status, then Lost IS(rank) vs Lost IS(budget), then bid-strategy ceiling, then
  targeting, then **negative keyword conflicts**, then billing.
- **High CPA**: decompose `CPA = CPC / CVR` and trend each separately — different causes, different
  fixes. Then check change history and the Aug-17 enforcement.
- **Impressions collapsed**: disapproval sweep, budget, tightened target, then **market-level supply**
  before concluding it is account-specific.
- **Google vs backend mismatch**: enumerate the causes in `06`. A 20–30% Ads/GA4 variance is expected.
- **Restriction**: identify the exact track (egregious / strike / limited serving) before responding —
  the correct action differs completely (`09`).

## Guardrails

- **Quality Score is not an auction input** and Ad Strength is not used in the auction. Neither is a
  KPI. Optimizing toward them directly is wasted work.
- **Exact match is not literal.** Negatives get no close variants. Both surprise people constantly.
- **Only an exact-match keyword guarantees Search keeps a query from PMax.**
- A quarter to half of click volume has no visible search term. The report you see is systematically
  more flattering than reality.
- Daily budget is an average: up to 2× on a day, capped at 30.4× monthly.
- Benchmarks size a test. They are never targets.
- **Google's defaults are set in Google's interest**, not the advertiser's — Search Partners, Display
  expansion, presence-or-interest, auto-apply, auto-generated assets. Audit each deliberately.
- Never accept a budget recommendation without computing cost per additional conversion. Google does
  not lower a budget it raised.
- Do not chase optimization score at campaign level — within one account it predicts nothing.
- System User and OAuth credentials are bearer secrets. Never expose them in chat, URLs, screenshots,
  repos, or logs.

## Output

Lead with the decision. Include the evidence level and assumptions, the exact action at the correct
level, the measurement window derived from conversion lag, stop/rollback conditions, and the remaining
uncertainty. Use cases as mechanism analogies, never as outcome promises.

For regulated verticals, verify current Google policy and local law. Cloaking, post-suspension
re-entry, and review-layer filters are Circumventing systems (egregious, cascade). This skill does
not own that lane — operational grey execution is `google-grey-ops/05`.
