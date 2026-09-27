# Evidence and Maintenance Guide

Last reviewed: 2026-07-24

Meta changes product names, UI paths, defaults, eligibility, regional availability continuously — a dated screenshot/workflow is evidence of one account state, not a universal contract.

## 1. Evidence labels

| Label | Meaning | Use |
|---|---|---|
| **Official behavior** | Meta policy, Help Center, dev docs, in-product state | Product rules, availability, policy, required setup |
| **Meta-reported** | Result/benchmark published by Meta, often selected studies | Directional context with study scope stated |
| **Independent benchmark** | Aggregated data, disclosed sample/period/geo/objective/methodology | Planning ranges for a comparable account |
| **Practitioner heuristic** | Derived from experience or a vendor article | Starting hypothesis to validate against account data |
| **Unverified** | Single-source, stale, inaccessible, conflicting, rollout-dependent | Explicit uncertainty only; never present as requirement |

Case studies also need a proof grade, separate from source ownership: causal design reported / structured comparison / attributed or pre-post. Meta, an agency, or a vendor can report a real experiment while still being an interested-party publisher — never turn a positive case-study lift into an expected result for another account.

Do not convert "best practice," "optimal," "must," or "Meta recommends" into official guidance unless the primary Meta source supports it.

## 2. Source priority

1. Live in-product state for the exact account/country/objective/placement/data source.
2. Current Meta Advertising Standards, Help Center, Business Help Center, dev docs.
3. Meta newsroom/product announcement with date and rollout scope.
4. Independent benchmark with visible methodology.
5. Practitioner/vendor source with date and account context.
6. Undated summaries, search snippets, screenshots — discovery leads only.

Conflicts: state the conflict, prefer higher-priority/newer evidence, advise checking the live account. Never infer universal availability from one screenshot.

An agent/support reply is **official account-specific evidence**, not a public platform contract. Preserve case text and affected asset IDs. If it conflicts with live UI/public docs, operate conservatively for that account and escalate to human/manual review.

## 3. Verification protocol

1. Identify claim type: policy, product behavior, UI path, benchmark, heuristic.
2. Record market, objective, optimization event, placement, account type.
3. Check an official source + its publication/update date.
4. Check the live account when access exists — account state overrides generic navigation instructions.
5. Use independent sources only when official docs are unavailable/ambiguous.
6. Label confidence; give a concrete verification step for unresolved rollout variance.

Include the evidence label inline for high-impact recommendations. Prices, thresholds, reporting delays, learning requirements, feature defaults: presumed volatile unless verified.

## 4. Confirmed corrections and retired concepts

| Topic | Current interpretation | Evidence |
|---|---|---|
| Location presence selector | "Living in or recently in" removed for new ad sets (2023). Check current behavior/exceptions in-product. | [Reporting](https://searchengineland.com/new-update-to-meta-ads-location-targeting-404124) |
| Special Ad Audiences | Unavailable for housing/employment/credit since 2022. Not a current lookalike substitute. | [Official](https://about.fb.com/news/2022/06/expanding-our-work-on-ads-fairness/) |
| Pixel vs dataset | Pixel = browser-side web data source; a dataset can group events from multiple sources. Related, not interchangeable. | [Official](https://www.facebook.com/help/messenger-app/952192354843755) |
| Closed ad account | Reactivable; not inherently irreversible. Distinct from restricted/disabled. | [Official](https://www.facebook.com/help/messenger-app/331993756945799/) |
| 2FA | May be required for certain portfolios/workflows; not a uniform product requirement. | Check in-product; [context](https://support.chatarchitect.com/books/meta-business-portfolio-setup/page/turn-on-the-two-factor-authentication-requirement-in-your-business-portfolio) |
| Offline event ingestion | Separate Offline Conversions API references can be stale; design around current CAPI routes. | [CAPI overview](https://www.facebook.com/business/help/AboutConversionsAPI) |
| Meta-enabled CAPI | No-code option announced April 2026; availability account-dependent. | [Official](https://about.fb.com/ltam/news/2026/04/eliminar-barreras-tecnicas-para-ayudar-a-empresas-de-todos-los-tamanos-a-aprovechar-mas-sus-anuncios/amp/) |
| Detailed targeting exclusions | Removed: Ads Manager 2025-03-31, boosts 2025-06-10. Custom-audience exclusions remain. [verified 2026-09-25] | [Official](https://www.facebook.com/business/help/458835214668072) |
| EU political/electoral/social-issue ads | No longer delivered in EU from Oct 2025; confirm current scope. | [Official](https://about.fb.com/news/2025/07/ending-political-electoral-and-social-issue-advertising-in-the-eu/) |

## 4.1 Marketing API version anchor (2026-08)

Graph API majors ship ~2×/year; a version number goes stale within months — check changelog (§7) before asserting "current".

A Marketing API version is available **~12 months TOTAL** (v24.0 ran 2025-10-08 → 2026-10-06) — shorter than Graph API's 2-year core guarantee (v24 stays callable on Graph core until 2028-02-18, `meta-grey-ops/02`); two independent clocks, don't conflate. The "90 days" on the versions page is the **minimum overlap after a new version ships**, not extra grace time and not the lifetime. Marketing API rejects unversioned calls outright. Pin the version in every script. Per-version dates exist only in the Graph API changelog's Marketing API table — the `marketing-api/versions` page carries none. [verified 2026-08-31]

| Version | Released | Status (2026-08-31) | Notes |
|---|---|---|---|
| v22.0 | 2025-01-21 | expired | `instagram_actor_id`→`instagram_user_id`; `enable_standard_enhancements`→`creative_features_spec`. See `13` §5, `04`, `14` |
| v23.0 | 2025-05-29 | expired | — |
| v24.0 | 2025-10-08 | ends 2026-10-06 — calls pinned to v24 fail after | `marketing-api/versions` page lags (still names v25 current, no dates) — use changelog |
| v25.0 | 2026-02-18 | supported, TBD | — |
| **v26.0** | **2026-07-29** | **current, no expiry** | Reference for `14`/`02`§9. Removed `delivery_estimate.daily_outcomes_curve`/`budget_guardrail`/`estimate_dau`; HEC-F campaigns require explicit `targeting_automation.advantage_audience`; IG Explore placement gone; Messenger `story` position removed; poll ads unsupported |

Any version named in a reference is version-bound — re-verify against current major before automating.

## 4.2 Hard limits (cross-file)

Live account overrides any row here.

| Limit | Value | Note | Source |
|---|---|---|---|
| Automated rules/ad account | 250 | Includes inactive rules | `02`§9 |
| Ads per ad set | 50 max; Meta discourages >~6 active | Legacy ASC 150-ad cap gone; total-campaign cap [uncertain] | `03`§2.1 |
| Primary text | ~2,200 stored; ~125 shown; 72 on Reels | Write for truncation | `04`§7 |
| Headline | 40 UI practical / 255 technical | Sources conflict; plan for 40 | `04`§7 |
| Description | 30 practical / 125 technical | | `04`§7 |
| Lookalike range | 1–10% similarity | Suggestion, not a hard control, under conversions optimization | `05` |
| Learning-phase volume | "~50 events/7 days per ad set" | Meta-published guideline (Help Center "About the learning phase"), not a guarantee; exit depends on delivery status | SKILL, `06`§4 |
| Stories safe zone | top ~14% (~250px), bottom ~20% (~340px) | 1080×1920 canvas | `04`§4 |
| Reels safe zone | top ~14%, bottom ~350px practical | UI-version dependent | `04`§4 |

## 5. Claims that always need context

Cost benchmarks (currency/country/period/objective/event/attribution/placement/sample) · learning status (Delivery status/result volume/delay/event quality/fragmentation — no universal event-count formula) · budget changes (marginal economics/delivery response; % limits are heuristics) · frequency/fatigue (objective/window/audience size/reach/creative distribution/outcome trend) · EMQ (diagnostic signal, not a launch/optimization gate) · attribution gaps (identity/consent/click-view windows/timezones/timestamps/dedup/refunds/backend defs) · feature paths/defaults (rollout/objective/country/placement/interface version).

## 6. Maintenance checklist

Review quarterly and after any major Meta announcement:

| # | Action |
|---|---|
| 1 | Recheck official policy/product links |
| 2 | Search for removed product names, retired APIs, legacy objectives, hard-coded years |
| 3 | Reclassify every new benchmark; record scope/methodology |
| 4 | Replace dead sources; never silently preserve a claim whose evidence disappeared |
| 5 | Re-run contradiction searches: `must`, `always`, `never`, exact learning counts, fixed edit %, fixed reporting delays, fixed frequency limits |
| 6 | Update review date only after facts/links/gaps actually checked |

## 7. Official knowledge map

Route the question to the current primary surface — do not copy Meta's help corpus here.

| Question | Check first |
|---|---|
| Exact account/asset restriction | Live error, [Account Status](https://www.facebook.com/help/1392616391875085/), [Business Support Home](https://business.facebook.com/business-support-home/), Support Inbox |
| Ad rejection / prohibited content | [Advertising Standards](https://transparency.meta.com/policies/ad-standards/), [ad-review guide](https://www.facebook.com/business/ads/review-policy-guidelines) |
| Profile/Page conduct | [Community Standards](https://transparency.meta.com/policies/community-standards/), Account Status |
| Portfolio/Page/Instagram/billing UI | [Business Help Center](https://www.facebook.com/business/help), live Business Settings/Billing |
| Campaign ops / official training | [Meta Blueprint](https://www.facebookblueprint.com/student/catalog/list), [Ads Manager learning](https://www.facebookblueprint.com/student/collection/507792-meta-ads-manager-learning) |
| Creative format/placement availability | [Ads Guide](https://www.facebook.com/business/ads-guide), live placement preview |
| Competitor/market creative discovery | [Meta Ad Library](https://www.facebook.com/ads/library/) |
| Marketing API objects/permissions | [Marketing API docs](https://developers.facebook.com/docs/marketing-apis/), [Postman collection](https://www.postman.com/meta/facebook-marketing-api/collection/0zr4mes/facebook-marketing-api-mapi) |
| Breaking API changes | [Graph API versioning](https://developers.facebook.com/docs/graph-api/guides/versioning/), [changelog](https://developers.facebook.com/docs/graph-api/changelog/) |
| SDK implementation | [Business SDK repos](https://github.com/facebook/facebook-python-business-sdk) |
| Pixel/CAPI/data duties | [CAPI overview](https://www.facebook.com/business/help/AboutConversionsAPI), [Business Tools Terms](https://www.facebook.com/legal/terms/businesstools) |
| Contract/billing/delivery obligations | [Commercial Terms](https://www.facebook.com/legal/commercial_terms), [Self-Serve Ad Terms](https://www.facebook.com/legal/self_service_ads_terms) |
| Suspected platform outage | [Meta Status](https://metastatus.com/) before rebuilding/changing campaigns |
| Announced rollout | [Meta newsroom](https://about.fb.com/news/); verify in the exact account |

Search snippets are discovery aids only — logged-in Help Center pages, live UI, country eligibility, and API version can differ from indexed copies.
