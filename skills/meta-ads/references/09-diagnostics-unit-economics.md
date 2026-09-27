# Diagnostics, Unit Economics, and Test Design

Last reviewed: 2026-07-22

Sequence: validate measurement → locate funnel constraint → compare against account-specific economics → design smallest useful intervention.

## 1. Minimum intake

| Area | Required context |
|---|---|
| Outcome | Business goal, conversion definition, revenue or qualified-lead outcome |
| Economics | Price/AOV, refunds, discounts, taxes, fulfillment, payment fees, variable cost, gross/contribution margin |
| Funnel | Impression → click → LPV → lead/cart → qualified lead/checkout → purchase/closed sale |
| Delivery | Market, objective, performance goal, optimization event, attribution setting, placements, audience controls |
| Measurement | Pixel/dataset, CAPI/CRM ingestion, dedup, UTMs, analytics, backend source of truth |
| History | Spend, dates, CPM, CTR, CPC, click-to-LPV, CVR, CPA/CPL, ROAS, frequency, reach, qualified rate |
| Constraints | Policy category, geography, age, inventory, sales capacity, privacy/consent, creative/LP limits |

Missing inputs: separate facts from assumptions, request only variables that change the decision.

## 2. Unit economics

Derive targets from contribution margin (standard break-even math assumed).

- Don't treat aspirational LTV as allowable CAC — if counting repeat purchases, state observation window, retention evidence, discount rate, cash-flow constraint.
- Lead gen: allowable raw-lead CPL = max CAC × raw→qualified rate × qualified→customer rate. Optimize against qualified/closed outcomes when volume/data flow allow, not raw-lead count.

## 3. Metric decomposition

Decompose CPA to locate the constraint: CPM → link CTR → click-to-LPV → CVR. Judge each factor against a comparable account baseline — level AND change, never one blended number.

## 4. Symptom-first diagnostic tree

| Symptom | First checks | Likely constraint | Next test/action |
|---|---|---|---|
| No/very low spend | Delivery status, schedule, payment, policy, audience size, bid/cost controls, event eligibility | Account/policy issue, overly restrictive controls, bid constraint, fragmented setup | Resolve blocking status; broaden one constraint at a time; verify optimization event |
| CPM increased | Auction seasonality, market, audience saturation, placements, quality ranking, spend change | Auction pressure, constrained audience, creative quality, placement mix | Compare breakdowns/prior periods; test broader delivery or new concepts |
| Low link CTR | Hook, message-market match, visual clarity, offer, placement crop | Creative/offer problem | Test materially different concepts; inspect placement-level delivery/comments |
| High CPC, acceptable CPM | Link CTR, click intent | Creative/offer or unclear CTA | Improve promise/proof/CTA — not audience micro-targeting |
| Large click-to-LPV loss | Page speed, redirects, consent layer, broken URL, in-app browser, accidental clicks | Technical funnel or low-intent click | Test on real devices/connections; inspect analytics events/redirect chain |
| Low LP CVR | Message continuity, load speed, trust, price, form/checkout friction, device errors | Offer, page, or checkout problem | Session/device QA; isolate LP or offer with controlled test |
| Cheap leads, poor sales | Lead definition, form friction, incentive, geo, spam, response time, CRM routing | Qualification/sales-process problem | Feed qualified/closed stages back; tighten questions; audit follow-up SLA |
| **Upstream cost far BELOW the GEO band, downstream CVR far below band** | The paid unit price vs published/peer bands for that GEO+placement+event; whether the optimizer ever exited learning | **Winning only the cheapest inventory** — low-intent users the rest of the auction declines. A downstream CVR collapse with a healthy upstream CVR is its signature | Do NOT treat a below-band CPA/CPI/CPC as an efficiency win. Feed the optimizer enough of the deep event to leave learning, then re-read the downstream rate at the higher unit price before touching the landing page |
| Meta conversions exceed backend | Attribution windows, view-through credit, duplicate events, refunds, time zones | Definition/attribution mismatch | Reconcile by event/order ID + conversion date; audit dedup |
| Backend exceeds Meta | Consent loss, event failure, missing identifiers, unsupported browser/server flow | Coverage/match problem | Review Diagnostics, event coverage, EMQ inputs, CAPI delivery |
| Performance fell after edit | Edit log, delivery status, spend allocation, creative distribution, conversion lag | Learning/reallocation, demand change, coincident external factor | Compare pre/post cohorts/breakdowns; revert only when evidence supports causality |

Never diagnose from one blended metric — break down by time, placement, geography, device, age (where allowed), creative, LP, new-vs-returning when sample is sufficient.

## 5. Measurement validation

1. Confirm the intended event fires once at the correct business moment.
2. Validate `value`, `currency`, item/order identifiers, event time.
3. Confirm browser/server dedup via matching `event_name`/`event_id` where both routes used.
4. Test UTMs and stable entity IDs through redirects into analytics and backend.
5. Reconcile a sample of event/order IDs across Meta, analytics, CRM, backend.
6. Record attribution window, time zone, and whether reports use impression or conversion time.
7. Monitor sudden changes in event coverage, matched events, duplicates, qualified-outcome imports.

Source of truth is per-decision: Meta for delivery optimization and platform-attributed outcomes; backend is authoritative for paid, refunded, qualified, closed results.

## 6. Test design

Generic experiment hygiene assumed; Meta/vertical-specific decisions:

- Allocation: randomized Meta Experiments when causal confidence matters. Parallel/operational splits are directional SCREENING only (audiences overlap, auction differs) — route causal reads to the measurement layer.
- Window ≥ conversion lag; judge on click-date cohort (tracker-ops), not conversion-date volume mid-lag.

## 7. Stop, scale, and rollback logic

- Fixed days, fixed event counts, "3× CPA," fixed budget-edit percentages: optional priors to validate, not rules.
- Stop immediately for policy violations, broken tracking, wrong geography, incorrect offer, runaway spend, damaged funnel.
- Normal variance: wait for the pre-specified evidence threshold and observed conversion lag.
- Scale while marginal results remain acceptable — blended historical ROAS can hide deteriorating marginal economics.
- Keep an edit log; define a rollback condition before high-impact changes.

## 8. Reporting contract

State: (1) observed facts + date range, (2) data-quality limitations + attribution settings, (3) unit-economic target + assumptions, (4) funnel location of primary constraint, (5) ranked hypotheses with evidence labels, (6) recommended action + mechanism + risk, (7) test design/success metric/stop condition/review date, (8) what must be verified live because availability/policy is rollout-dependent.
