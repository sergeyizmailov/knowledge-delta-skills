# Creative Diagnostics and Account Audits

Last reviewed: 2026-07-22

"Hook rate"/"hold rate" are practitioner conventions, not standardized Meta thresholds.

## 1. Metric contract

Define every denominator in the report — different tools reuse the same label for different formulas.

| Metric | Formula | Indicates | Caveat |
|---|---|---|---|
| Hook/thumb-stop rate | 3-sec video plays / impressions | Whether opening earns 3s attention | Practitioner metric; autoplay/placement/duration/impression mix affect it |
| Hold rate | ThruPlays / 3-sec video plays | Whether hooked viewers reach 15s or completion (shorter videos) | Some teams use 15s-views or impressions as denominator — never compare without matching formula |
| 25/50/75/100% retention | plays at depth / starts or 3-sec plays | Where narrative loses viewers | Duration and placement must be comparable |
| Link CTR | link clicks / impressions | Ability to produce a click | Doesn't prove click quality or LP arrival |
| Outbound CTR | outbound clicks / impressions | Clicks leaving Meta, where available | Availability/definition vary by destination |
| Click-to-LPV rate | LPV / outbound clicks (or matching click type) | Redirect/load/browser/accidental-click loss | LPV measurement itself can be incomplete |
| LPV-to-result ratio | selected result / LPV | Diagnostic handoff ratio | Not page CVR — results can include view-through/modeled attribution; use click-only or analytics sessions for session CVR |
| CPA/CPL | spend / business results | Media cost per selected result | Raw lead or platform purchase may not equal backend outcome |
| ROAS | attributed conversion value / spend | Platform-attributed revenue efficiency | Not contribution profit or incrementality |
| Frequency | impressions / reach at chosen level | Repeated exposure | Reach can't be summed across overlapping rows |

Meta ThruPlay = completion (<15s videos) or ≥15s (longer). No official hook/hold benchmark exists — use account-relative cohorts matched on objective, placement, audience state, duration, period.

Account-relative baseline protocol: match objective/event/attribution/country/placement family/prospecting-vs-retention/offer/duration-band → sum raw numerators/denominators over a window covering conversion lag, never average daily row rates → compare candidate against both pooled baseline and its week/ad distribution → use attention metrics for screening, business outcome+guardrails for promotion → keep/rerun a control so seasonality/auction shifts aren't mistaken for creative lift.

## 2. Creative diagnostic sequence

Read the earliest broken stage: `delivery share → first-frame/3s capture → retention to message/proof → link intent → LP arrival → conversion → qualified/revenue outcome`.

1. Confirm the ad got enough delivery for the decision — low spend can be allocation, not concept failure.
2. Check placement rendering, safe zones, sound-off comprehension, destination, enabled creative enhancements.
3. Compare hook/retention against matched account cohorts, not public bands.
4. Compare link/outbound CTR and comment sentiment — did attention become relevant intent.
5. Inspect click-to-LPV loss before blaming the offer.
6. Inspect page/form/checkout CVR and device errors before changing targeting.
7. Use qualified/paid/retained/revenue outcomes to validate apparent media winners.

## 3. Diagnostic matrix

| Pattern | Likely hypotheses | First test | Do not conclude |
|---|---|---|---|
| Low hook, acceptable CPM | Opening frame, visual clarity, relevance, placement crop | New first frame/hook, same body/offer | The audience is wrong |
| High hook, low hold | Hook-body mismatch, slow proof, confusing story, duration | Shorter bridge to mechanism/proof; matched-duration compare | The hook is the overall winner |
| High hold, low link CTR | Entertaining but weak product relevance/offer/CTA/destination intent | Stronger product/offer connection + CTA | More watch time guarantees sales |
| High link CTR, low click-to-LPV | Slow page, redirects, consent layer, broken deep link, accidental clicks | Device/network QA, redirect/event audit | The creative is successful |
| Good LPV rate, low CVR | Message mismatch, price/offer, trust, form/checkout friction, availability | Page/offer test, stable traffic source | Meta targeting caused the entire loss |
| Good platform CPA, poor backend quality | Proxy optimization, spam, misleading promise, sales follow-up | Qualified/closed feedback, creative/form qualification | Cheaper leads are better leads |
| Strong ad-level ROAS, weak incrementality | Existing-customer concentration, view-through credit, branded demand | New-customer split, lift/geo holdout | Attribution equals causal lift |
| Rising frequency, falling outcome | Creative fatigue, audience saturation, demand/seasonality, spend shift | Compare creative-level vs audience-wide decline; introduce new concept | A generic frequency threshold was crossed |

## 4. Account audit workflow

| Stage | Check |
|---|---|
| A. Freeze the question | Business goal/target economics; date + comparison range; attribution setting, timezone, conversion delay; reporting level (campaign/ad set/ad/time series); change log (budget/bid/event/audience/placement/creative/LP/offer/tracking) |
| B. Validate account state | Delivery status (campaign/ad set/ad); billing, schedule, account limits, review/restriction, disapprovals; objective/conversion location/performance goal/event/bid strategy/budget level; special category, geo, age, placements, rollout-dependent controls |
| C. Validate measurement | Event timing/value/currency/order-lead ID/dedup; UTMs with stable IDs; Meta vs analytics/CRM/backend reconciliation by event/order ID; raw→contacted→qualified→booked→paid/closed stages; refund/cancellation/retention/IAP-IAA/new-customer adjustments |
| D. Review history, decompose | Check Activity history so an edit isn't mistaken for market/creative change; analyze totals/distributions by campaign/ad set/ad/placement/country/device/age(where permitted)/day/week/new-vs-returning; require sufficient sample before interpreting a narrow breakdown |
| E. Rank hypotheses | Per hypothesis: evidence, disconfirming evidence, mechanism, action, risk, success metric, stop condition, review date — separate fact from practitioner prior |

## 5. Ads Manager export schema

Export a stable English custom column view. Never mix rows whose `Results` represent different actions. Preserve raw counts, recompute weighted rates — never average row-level CTR/CPA/ROAS/CVR/frequency. Create separate fact files: (1) unbroken totals export for reconciliation, (2) daily breakdown for trend/edit/fatigue, (3) publisher-platform/placement breakdown for delivery quality. Never join breakdown files in a way that multiplies spend/actions; never sum reach across rows.

| Group | Columns |
|---|---|
| Identity/config | Reporting start/end; Campaign/Ad set/Ad name+ID; objective, buying type, attribution setting (where exportable); delivery status, bid strategy (where exportable) |
| Delivery/cost | Amount spent + currency; impressions, reach, frequency; CPM; link/outbound clicks, LPV; link/outbound CTR, CPC |
| Video creative | 3-sec plays; ThruPlays; plays at 25/50/75/100%; avg play time where available |
| Business outcomes | One explicitly named result column (not unexplained mixed `Results`); cost per selected result; conversion value/ROAS when valid; backend-qualified/paid/closed result joined by stable IDs outside Ads Manager |
| Context joins | Creative concept/angle/hook/format/duration/creator/offer/LP version; campaign/ad set/ad IDs in analytics+CRM; new/returning + gross/contribution margin where available; edit log, experiment cell |

## 6. CSV analyzer

`scripts/analyze_ads_export.py` — Python stdlib only, applies no benchmark thresholds.

```bash
python3 scripts/analyze_ads_export.py export.csv \
  --result-column "Purchases" \
  --value-column "Purchase conversion value" \
  --top 20 > audit-summary.md
```

For lead gen, pass a joined column (e.g. `Qualified leads`, `Closed won`) after enriching the export with CRM outcomes. Use `--name-column` when the entity isn't auto-detected. Flags: `--name-column`, `--result-column`, `--value-column`, `--top` (default 15).

Computes weighted totals and top-spend rows for CPM, outbound/link CTR, CPC, click-to-LPV, LPV-to-result ratio, CPA, ROAS, hook rate, hold rate. It intentionally: requires an explicit result column for CPA/CVR; never sums reach or infers cross-row frequency; never labels a metric good/bad; never claims causal significance; warns when key columns are absent.

For true LP CVR use click-only conversion data or join analytics/backend converted sessions — don't read an Ads Manager purchase-to-LPV ratio as session CVR when view-through/modeled results are included.

## 7. Scenario drills

| # | Data | Diagnosis | Action |
|---|---|---|---|
| 1. Cheap CTR, expensive purchase | CPM/CTR improved; click-to-LPV stable; LPV CVR fell; refunds rose | Creative expanded clicks by changing promise/buyer mix; page/product economics worsened | Compare promise/offer, device, new-customer share, paid orders, refunds — don't call it a winner from CPC |
| 2. Video "winner" gets most spend | One ad best CPA + most spend; challengers starved | Allocation and selection confounded | Treat as operational winner only; use overlap-free experiment if causal difference matters |
| 3. Strong hook, weak body | Hook above cohort; hold + link CTR below | Pattern interrupt works, message/proof doesn't hold attention/intent | Keep opening, replace bridge/mechanism, test same offer+duration |
| 4. Weak hook, strong conversion among clickers | Low hook/CTR; click-to-LPV + page CVR strong | Downstream offer works for a small self-selected group; reach is the constraint | Create clearer variants of the same proposition before changing the page |
| 5. Instant-form CPL falls, sales don't rise | Raw CPL halves; contact/qualified rates fall; closed CAC rises | Form completion optimized while friction/promise changed buyer intent | Restore qualification, audit response time, feed qualified/closed events |
| 6. Meta ROAS rises after CAPI launch | Meta-attributed purchases rise; backend flat; browser/server duplicates appear | Measurement coverage/duplication changed, not necessarily demand | Reconcile event/order IDs + dedup before claiming lift |
| 7. App CPI falls, D7 value falls faster | Installs rise, CPI falls; activation/retention/D7 ROAS decline | Optimization found cheaper installers, not valuable users | Test downstream activation/value event; keep cohort payback as guardrail |
| 8. High-AOV campaign looks inefficient after 1 week | Spend matures faster than purchases; assisted/delayed orders appear later | Evaluation window shorter than purchase-lag distribution | Define post-treatment window from observed lag; use lift/geo design when material |

## 8. Reporting template

```text
Business question and target economics:
Date range, comparison range, attribution, time zone:
Data sources and known gaps:
Earliest broken funnel stage:
Creative-level observation:
Backend/CRM/app-cohort observation:
Ranked hypotheses with evidence labels:
Recommended action and mechanism:
Test design and primary metric:
Guardrails and stop/rollback condition:
Decision date after conversion lag:
What requires live-account or country-policy verification:
```

## 9. Sources and gaps

Official: [creative overview](https://www.facebook.com/business/ads/ad-creative) · [Reels ads/split-test](https://www.facebook.com/business/ads/facebook-instagram-reels-ads) · [awareness/video-view defs](https://www.facebook.com/business/ads/ad-objectives/awareness) · [traffic objective/LPV](https://www.facebook.com/business/ads/ad-objectives/traffic) · [delivery status](https://www.facebook.com/help/messenger-app/650774041651557/) · [Ads Manager levels](https://www.facebook.com/help/messenger-app/621956575422138/) · [Activity history](https://www.facebook.com/help/messenger-app/289211751238030) · [practitioner hook/hold formulas](https://win.varos.com/en/articles/8055146-how-video-facebook-ads-benchmark-metrics-are-calculated).

Gaps: no universal hook/hold benchmarks published; export labels vary by locale/objective/rollout/reporting level; public exports lack full config history and backend outcome quality — join separately, preserve privacy controls.
