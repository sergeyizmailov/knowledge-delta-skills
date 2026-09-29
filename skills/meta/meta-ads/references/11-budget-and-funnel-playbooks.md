# Budget and Funnel Playbooks

Last reviewed: 2026-07-22

No currency-denominated budget tiers: the same amount buys a strong test in one market and near-zero decision-quality data in another.

## 1. Budget tiers by decision capacity

Capacity = results the test buys ÷ results needed per cell. `results_required_per_cell` is not a universal threshold — derive from baseline rate, minimum worthwhile effect, confidence, conversion delay, acceptable loss; pilot to estimate if unknown, call it directional.

| Tier | Definition | Design | Avoid |
|---|---|---|---|
| **Constrained** | Can't support >1 useful decision cell at target outcome | One consolidated delivery cell; screen materially different creative; validate measurement/funnel | Parallel audience/placement/bid/creative tests; treating an under-delivered ad as a completed test |
| **Controlled** | Supports a limited holdout or few adequately funded cells | One primary experiment + BAU delivery; rotate next question only after current read | Changing offer/page/audience/bid/creative simultaneously; scaling from attributed ROAS alone |
| **Portfolio** | Supports simultaneous prospecting/lifecycle/powered experiments without starving BAU | Separate exploration/validated-delivery/incrementality cells; geo or conversion-lift tests | Assuming scale makes attribution causal; ignoring marginal CPA/saturation |

Tier can change by country/season/objective/event without the currency budget changing.

## 2. Portfolio allocation

Allocate by job, not fixed %: (1) BAU baseline — best current config, (2) exploration — concepts/offers/pages/event-quality whose result can change a decision, (3) validation — randomized A/B, conversion lift, geo holdout for material claims, (4) lifecycle/retention — only where message/economics differ from acquisition, (5) measurement reserve — engineering/creative production/CRM feedback/analysis count as acquisition cost though not media spend.

No hard-coded `70/20/10` split. Fund baseline to protect current economics, then fund highest-value uncertainty.

## 3. E-commerce playbook

Required inputs: net AOV, contribution margin, refunds/discounts, payment/fulfillment cost · new-vs-returning value + repeat-purchase window · purchase event accuracy/value/currency/order ID/dedup · checkout success by device · inventory/geo availability.

Sequence: break-even/target CPA from contribution (not revenue) → reconcile order-ID sample across Meta/analytics/backend → optimize to closest reliable purchase/value event → consolidate redundant prospecting, keep retention cell only if offer/eligibility requires it → test concept/offer before micro-segments → read CPM→CTR→click-to-LPV→checkout CVR→paid/refunded CPA → scale on marginal new-customer contribution/inventory; lift design when incrementality changes the decision.

| Observation | Wrong | Better |
|---|---|---|
| High attributed ROAS, weak new-customer revenue | Scale because ROAS above target | Separate new/returning, test incremental new-customer revenue |
| Strong CTR, weak purchase CVR | Replace audiences | Check message/price continuity, mobile checkout, stock, delivery terms, event accuracy |
| Cheap AddToCart, weak purchases | Optimize permanently for AddToCart | Repair checkout/measurement; move to business outcome when data supports it |
| Good first-week CPA on high-AOV product | Declare final economics | Use observed purchase-lag distribution, mature delayed conversions |

## 4. Local lead-generation playbook

Required inputs: service radius/excluded areas/hours/capacity/response SLA · raw/contacted/qualified/appointment/show/sale/revenue definitions · close rate by source+cohort, no-show/cancellation/spam/duplicate rates · max CAC → max qualified/raw CPL.

Sequence: enforce serviceability in geo controls/creative/form/address validation → choose form/instant-form/messaging/calls by qualification+follow-up workflow, not CPL alone → add just enough qualification friction → route leads immediately, log first-contact latency, dedupe phone/email → send qualified/closed stages via CRM/CAPI when volume/consent/quality allow → compare campaigns on cost per contacted/qualified/booked/shown/closed → diagnose quality by geo/promise/form answers/time/placement/follow-up before narrowing interests.

| Observation | Wrong | Better |
|---|---|---|
| Instant-form CPL half of website CPL | Move all budget to instant forms | Compare qualified/closed CAC, response time, spam, sales capacity |
| Good lead volume, few appointments | Blame targeting | Audit contact latency, routing, scripts, qualification, availability, duplicates |
| Leads outside service area | Search for retired residents-only selector | Use supported geo inputs; validate postcode/address in form/booking flow |
| Cheap calls, low revenue | Optimize for call initiation | Measure connected/qualified calls and downstream sales |

## 5. SaaS and B2B playbook

Required inputs: ICP/disqualifiers/contract value/gross margin/sales-cycle length/stage conversion/pipeline capacity · distinction between content leads/sign-ups/qualified meetings/opportunities/closed-won · CRM identity+stage timestamps, opportunity value, offline/CAPI plan.

Sequence: define the business event (qualified meeting / activated workspace / SQO / other economically meaningful stage) → map lead-to-stage conversion, derive allowable CPL from max CAC backward → match offer to intent (educational/diagnostic/demo/trial/direct sales) → use creative for problem/role/proof/disqualifier, not job-title targeting alone → reconcile cohort pipeline by campaign/ad+stage date, preserve long lag → feed qualified stages/values back when volume/privacy allow → evaluate pipeline/revenue lift before scaling cheap top-of-funnel leads.

| Observation | Wrong | Better |
|---|---|---|
| Low content-download CPL | Treat downloads as pipeline | Track qualified meeting/opportunity/closed-won rates by cohort |
| Narrow job-title audience, high CPM | Add adjacent interests | Test broader delivery with ICP-specific creative + form qualification |
| Few closed-won during media window | Optimize daily on platform CPA | Use leading stages with known stage-to-revenue value; mature cohorts separately |
| Demo page converts poorly | Increase retargeting frequency | Check offer/ICP fit, proof, scheduling friction, sales availability |

## 6. Mobile-app playbook

Required inputs: OS/country mix, Meta SDK/CAPI or MMP config, ATT/SKAN/AEM+attribution settings · install/activation/retention/subscription/ad-revenue/refund/cohort-LTV definitions · IAP vs IAA monetization, payback horizon, fraud filtering.

Sequence: validate event names/value/currency/dedup/MMP-backend reconciliation → establish install-to-activation and activation-to-value funnels by OS/country/cohort → optimize to deepest reliable event for the business model, keep downstream guardrails if using an upstream proxy → for hybrid apps keep IAA/IAP value definitions explicit, test cannibalization between paths → test creative on both media outcomes and D1/D7/D30 quality → compare automated vs manual with fixed market/creative/event/spend/cohort window → scale on cohort contribution/payback, not CPI alone.

| Observation | Wrong | Better |
|---|---|---|
| CPI falls sharply | Scale immediately | Check activation, retention, payer/ad-revenue value, fraud, cohort payback |
| Purchase count rises | Assume total app value rose | Check purchase value, IAA value, retention, cannibalization |
| Meta and MMP differ | Pick the larger number | Reconcile attribution rules, event time, consent, dedup, SKAN/AEM coverage |
| Creative wins on install CTR | Promote it as control | Require downstream quality guardrail for the same install cohort |

## 7. Test backlog and operating cadence

| Field | Meaning |
|---|---|
| Decision | What changes if result is positive/negative/inconclusive |
| Constraint | Current earliest broken funnel stage |
| Hypothesis | Mechanism expected to move the outcome |
| Treatment | One material variable, or a clearly defined package |
| Primary metric | Business-aligned decision metric |
| Guardrails | Quality, policy, spend, refund, retention, sales-capacity limits |
| Evidence requirement | Directional screen / randomized A/B / conversion lift / geo holdout |
| Minimum data | Baseline, MDE, confidence, lag, acceptable loss |
| Owner and date | Who acts, when result matures |

No calendar cadence ("3 new creatives/week") without reference to spend/delivery — keep the next candidate ready before the current control deteriorates, without queuing more than delivery can serve.

## 8. Post-mortem template

```text
Decision being tested:
Business and account context:
Economics and target:
Treatment and counterfactual:
Dates, attribution, and conversion-lag window:
Primary metric and guardrails:
Observed funnel movement:
Backend/CRM outcome:
What changed besides the intended variable:
Result: positive / negative / inconclusive / invalid
Mechanism supported or rejected:
What would reproduce or falsify the conclusion:
Next action and rollback condition:
Transfer limits: country, objective, placement, audience, season, scale
```

Invalid/inconclusive ≠ losing ad — record why the design couldn't answer the question (tracking failure, overlap, unequal spend, offer change, insufficient sample, lag, external shock) so the mistake isn't repeated.

## 9. Sources and gaps

Official: [budget](https://www.facebook.com/business/ads/pricing) · [auction](https://www.facebook.com/business/ads/ad-auction) · [campaign structure](https://www.facebook.com/help/messenger-app/621956575422138/) · [CAPI](https://www.facebook.com/business/help/AboutConversionsAPI) · [Advantage+ leads](https://www.facebook.com/business/ads/meta-advantage-plus/leads) · [Advantage+ app](https://www.facebook.com/business/ads/meta-advantage-plus/app-campaigns).

Gaps: no universal sample-size rule, currency tier, or result volume guarantees a stable decision — power calcs need account-specific baselines; country prices, sales processes, app attribution, regulated-category controls remain volatile.
