# Tracking, Measurement & Optimization for Instagram/Meta Ads (2025–2026)

Reviewed 2026-07-22. UI reflects 2025–2026 interface (Business Portfolio + reworked Events Manager); older naming flagged inline.

---

## 1. Meta Pixel and datasets

- **Pixel remains the browser-side web data source.** Its events feed a **dataset**, which can group website/app/offline/other sources. IDs can match when an existing Pixel is represented as a dataset, but the concepts aren't interchangeable. [official]
- Events Manager UI reworked 2025–2026 — pre-2025 screenshots ("Data Sources" tab, green pixel icon) look different.
- Setup: Events Manager → Connect data → Web → name dataset → Create. Then: manually add base code to `<head>`; or partner integration (Shopify/WooCommerce/WordPress/Wix/Squarespace/GTM — most now also enable CAPI, §2); or CAPI Gateway (§2). **Event Setup Tool** = codeless point-and-click standard-event tagging, final step of creation and later under dataset Settings.
- Base code fires only `PageView` by itself; Events Manager is reporting/config only — events appear after firing once live or via **Test events**. An event that never fired shows inactive/red — expected, not broken.
- **Advanced Matching**: hashed customer data (email/phone/names/external ID) captured on-site improves attribution/lowers CPA. Enable in dataset Settings; normalize email/phone formats, combine automatic+manual matching, monitor match quality.
- **Scoped caveat — cloaked/compliance-sensitive funnels**: the line above assumes a lander you own end to end. Automatic Advanced Matching scans the DOM for email/phone/first-mid-last name/city/state/zip/gender and hashes+sends whatever it finds, client-side, no per-field opt-in — the pixel decides, not you [official: developers.facebook.com/docs/meta-pixel/advanced/advanced-matching, facebook.com/business/help/1993001664341800]. Manual Advanced Matching (an explicit customer-data object in the pixel init call) sends only named fields — leave Automatic off on a page you don't want self-reporting to Meta. Grey-side detail: `meta-grey-ops`.

---

## 2. Conversions API (CAPI)

- Server/platform/CRM/app → Meta. Less affected by load failures/connectivity/ad blockers than browser-only, but doesn't bypass consent or guarantee complete attribution.
- **Not a Pixel replacement** for most websites — Meta recommends combining both, deduplicated via matching `event_name` + `event_id`.
- Vendor claim: CAPI recovers 20–40% of conversions — **no account-independent loss rate established**; measure event coverage/dedup/matched events/backend reconciliation for the real number. [W: do not quote 20-40% as a guaranteed recovery rate]
- iOS 26 (2025-09-15) added Advanced Fingerprinting Protection to Safari + expanded Link Tracking Protection — further degrades browser-only tracking.

**Three setup routes (2026):**
1. **Meta-enabled CAPI ("one-click")** — announced 2026-04: free, no-code web setup in minutes; availability can exclude some data-source categories, verify in Events Manager. [official]
2. **Partner integration** — dataset → Settings → Conversions API → pick partner (Shopify, WooCommerce, WordPress, LeadsBridge, Zapier, Segment, sGTM/Stape). No code. Shopify's native channel defaults CAPI to "Maximum" sharing.
3. **Manual/developer** — Dataset ID + access token: Settings → Conversions API → "Generate access token" (developer-privilege only) → "Manage Integrations" auto-creates API app + system user (no App Review needed); or Business Settings → assign dataset to system user → Generate Token. Direct integration = you own retries/validation/monitoring/consent/version upgrades — check the live Meta for Developers version schedule, don't assume a fixed cadence.
4. **CAPI Gateway / Signals Gateway** — Meta's self-hosted server-side container (e.g. AWS). Middle ground, Meta-focused; enterprise teams often prefer sGTM instead for multi-platform flexibility.

**Testing/dedup**: Test events tab → grab test event code → include in CAPI payload → fire real actions → verify payload before going live. Dedup requires shared `event_name`+`event_id` between browser/server events, matched within Meta's window. Duplicate events and missing `value`/`currency` are the two most common Diagnostics warnings.

**Offline Conversions API is gone** — shut down **May 2025**; all offline events (in-store, phone, CRM stages) now go through standard CAPI. Unmigrated offline tracking silently stopped working.

**Privacy**: CAPI isn't automatically compliant — apply jurisdiction law/consent, minimize data, use required hashing/normalization, honor opt-outs, document processors. [A 2026 German-court CAPI-consent interpretation is single-sourced — don't generalize into legal advice without checking the judgment/jurisdiction.]

---

## 3. Standard events & Event Match Quality (EMQ)

- Gotcha: Purchase without `value`/`currency` breaks value optimization + ROAS reporting — top Diagnostics warning. Fire Purchase on thank-you/confirmation page or server-side on payment success, **not** checkout page load.
- **EMQ**: 0–10 score per event, Events Manager → dataset Overview → event → Event Matching view; reflects hashed-parameter completeness, based on ~last 48h activity. Vendor score bands/event-specific ranges are descriptive heuristics, **not Meta eligibility thresholds** — no universal EMQ launch gate.
- [vendor-cited case data] Raising EMQ 8.6→9.3 correlated with 18% lower CPA, +24% match rate, +22% ROAS (AdLeaks 2025 case, relayed by DataCops/Trackbee).
- Biggest single lift: hashed email at the conversion point in the CAPI payload; email+phone+external ID+fbp/fbc cookies contribute most.
- **EMQ parameter checklist (practical floor 7.0; sweet spot 8–9):** email alone
  lands ~5.5–6.5; + phone → ~7.5–8; + `fbp` (read `_fbp` cookie, needs Pixel
  running in parallel) + `fbc` (from `fbclid` URL param / `_fbc` cookie) →
  ~8.5–9; name/address fields push toward 9+. All PII SHA-256 hashed, lowercased
  first. `action_source` must be `website` or EMQ isn't calculated. `event_time`
  in UTC Unix seconds — local-time payloads outside ±24h are silently rejected.
  EMQ is per event type (Purchase/AddToCart/Lead separately), ~last 48h.
  [practitioner-aggregated bands 2026 — directional, not Meta-published]
- **Optimization event choice**: delivery can optimize for custom conversion/custom event, not only standard events (ad set Optimization & Delivery dropdown). A brand-new event has no history — learning-phase target (~50 optimization events/ad set/7 days) is the practical floor, so a deep rare event (e.g. qualified sale) can leave an ad set permanently learning-limited. Optimize for the deepest event that still clears that volume, else use a reliable upstream proxy correlated with the paid outcome (tiering detail: `tracker-ops`).
- **Value optimization (VBO)** requires `value`+`currency` (ISO 4217). Custom conversions can use VBO, but Meta reportedly raised the bar for custom/non-purchase events to **~100 attributed conversions + ≥5 distinct values in the past 14 days** (higher than Purchase). [practitioner-reported, verify live] Thin funnels failing this should optimize on conversion count, not force VBO.
- **Conversion Leads** goal (Lead Ads/Instant Forms): send down-funnel CRM stage events via CAPI, optimize for a chosen stage. Official eligibility: **≥200 leads/month, upload ≥1×/day, target stage within 28 days of lead creation, target-stage conversion rate 1%–40%.** [official]

---

## 4. Domain verification & Aggregated Event Measurement (AEM)

- Domain verification: Business Settings → Brand safety and suitability → Domains → Add → DNS TXT / meta tag / HTML file. **No longer required for event configuration** post-AEM-change, but still useful for link ownership/editing control and some feature prerequisites.
- **AEM history (critical)**: 2021–2023 model — verify domain, rank **8 conversion events/domain** in AEM → Web Event Configuration; only highest-priority event per session reported for ATT opt-outs; VBO consumed 4 of 8 slots ("value sets"); non-prioritized-event ad sets couldn't reach iOS opt-outs; reordering triggered a **~72h cool-down** pausing affected ad sets.
- **2023-05**: Meta announced removal — no more 8-event prioritization/value sets, AEM tab removed, domain verification no longer required for event config, no conversion-domain selection at ad set level. Rolled out gradually.
- **By mid-2025**: removal broadly complete for web events — Meta aggregates all eligible web events automatically. Some accounts not yet migrated. **iOS app campaigns still use the prioritized-event model.**
- Practical rule: if an AEM tab still appears for an account, legacy model applies there; if not, nothing to configure (still keep event list clean — feeds Advantage+ signals). [account variance undocumented]
- **App campaigns**: AEM runs by default alongside SKAdNetwork for iOS; "SKAdNetwork only" at ad set level disables AEM postbacks. **Advanced data sharing** toggle: off = ATT-consenting users only, on = all users with masked signals — check privacy policy before enabling.

---

## 5. UTM parameters

- Ad level → Destination → **URL Parameters** field (not Website URL field), no leading `?`. Minimum viable: `utm_source`+`utm_medium`+`utm_campaign`; add `utm_content` for ad-level reporting.
- 8 dynamic tokens: `{{campaign.id}}`, `{{campaign.name}}`, `{{adset.id}}`, `{{adset.name}}`, `{{ad.id}}`, `{{ad.name}}`, `{{placement}}`, `{{site_source_name}}` (fb/ig/msg/an) — resolved at click time.
- Recommended template: `utm_source={{site_source_name}}&utm_medium=paid_social&utm_campaign={{campaign.id}}&utm_term={{adset.id}}&utm_content={{ad.id}}&placement={{placement}}`. Use IDs as stable join keys; add separate name params if analysts need readability, but preserve IDs.
- Rules: static taxonomy values consistently cased (name tokens fragment reporting if renamed/re-cased); align `utm_medium` to the analytics property's channel-group rules (`paid_social` is common GA4 convention, verify custom groups); tag every ad incl. boosted posts; never edit UTMs mid-campaign (splits before/after buckets); never PII in UTMs (GA ToS); `fbclid` auto-appends but does NOT populate GA campaign reports — UTMs still needed; test on a live ad before big launches. Meta/analytics/backend totals will differ — identity, attribution windows, time zones, consent, conversion-time logic all diverge; a stable gap is normal, a sudden change needs investigation.

---

## 6. iOS14+ reporting reality

- Conversion reporting isn't always immediate, esp. for modeled/privacy-preserving app attribution — use the account's observed delay distribution, not a universal 72h wait.
- Modeled conversions fill opt-out gaps statistically — Ads Manager totals exceed analytics tools' counts; attribution counted at conversion time; SKAN postbacks arrive on Apple's timer.
- ATT opt-out means a real share of iOS conversions never reaches Meta — meaningful CPA/ROAS distortion vs. backend truth reported; triangulate with UTM/GA4 + backend revenue.
- SKAdNetwork: Apple's privacy-safe app attribution, postbacks delayed 24–72h+, limited conversion values; AEM runs alongside it (§4). [single source] Apple reportedly replaced SKAN with **AdAttributionKit (AAK)** as primary framework at iOS 26 (Sept 2025) — custom attribution rules, regional postback data; verify against Apple docs if app tracking matters.
- Mitigations: Pixel+CAPI redundancy, stable UTM joins, backend outcome reporting, evaluation windows long enough for the account's lag/weekly pattern.

---

## 7. A/B testing: Experiments tool vs manual splits

- **Meta Experiments**: Ads Manager → All tools → Experiments → A/B Test → pick two existing campaigns/ad sets/ads or duplicate as the variable. Ensures **no audience overlap between cells** — core advantage over manual splits.
- Reports "% confidence this will be a winner." The commonly repeated "90% default" is likely the **Lift-study** threshold; Meta's A/B framework appears to flag a winner at a lower bar (**~65%+ cited**) — an A/B "winner" is directional, not lift-grade. [official help page geo-blocked at last check — verify live figure in the results view] "End test early if a winner is found" exists — leave off; sequential-decision methodology unpublished, early stops carry peeking risk. Key-metric selection is mostly "Cost per …" — conversion rate isn't native (workaround: custom metric = Purchases/Link clicks).
- Best for validating big bets (offers, landing pages, funnels) where overlap-free delivery matters; clunky for high-volume creative iteration (one test at a time per setup).
- **Manual splits**: ABO can hold budgets equal but isn't randomized/overlap-free — use Experiments when causal confidence matters, ABO cells for directional operational tests (check overlap/delivery/spend balance manually).
- **Advantage+ creative screening**: multiple variants in one ad set can surface promising combos but allocation is unequal — not a clean angle test.
- Flexible/ad-creative combinations and legacy Dynamic Creative discover combinations but don't isolate component effects — use a controlled A/B test when the learning must be causal.
- Set required confidence before launch; directional creative screening can use a lower bar than a landing-page/pricing/budget decision — don't present an early platform prediction as statistically validated.

---

## 8. Creative testing frameworks

- Structure by angle in CBO: one campaign, ad sets per angle (same targeting across sets for fairness), 2–3 creatives/set per angle.
- Volume framework (ecom): Week 1 define 3–4 angles → 5–10 variations/angle (vary format/hook/visual style) → 20–40 variations → test 2 weeks → iterate.
- Challenger cadence: enough creative candidates to replace declining concepts without fragmenting delivery — count/threshold depend on spend, volume, test question.
- Variable priority order: creative concept → format → copy → audience → placement.
- Vendor reports describe faster fatigue in some high-spend accounts — no universal 2–3-week lifespan or YoY CPM uplift applies; refresh when account-relative distribution/outcomes deteriorate, not on a calendar.

---

## 9. Kill & scale decisions

**Kill**: no universal seven-day hold — define minimum data requirement from conversion delay, expected CVR, spend risk, test purpose; stop immediately for policy/tracking/brand-safety/severe funnel failures. "3× target CPA with zero conversions" is a pre-registered risk limit, not proof of significance — also compare CTR/LPV rate/CVR/lead quality/backend outcomes vs. the account's own baseline. No universal current requirement of exactly 50 events/7 days for every setup — use live Delivery status; don't downgrade to a low-quality proxy event just to satisfy the legacy heuristic.

**Scale**: Vertical — measured budget steps, monitor marginal CPA/ROAS/delivery/lag; 10–20% or 1%-nightly are practitioner heuristics, not guaranteed learning-safe thresholds. Horizontal — new audiences, broader lookalikes (1%→3–5%), new placements/geos. **Duplicate-and-scale caution**: duplicating a winner with identical ads+audience causes **Auction Overlap** — higher-total-value ad wins, the other starves; prefer scaling in place or genuinely differentiating the duplicate. Budget-split heuristic: 60% proven winners/30% testing/10% refreshing past winners; 60–80% on prospecting for growth accounts. With Advantage Campaign Budget (CBO), avoid ad-set spend min/max except rarely (e.g. forcing delivery in a new state) — they defeat the algorithm's allocation.

---

## 10. Frequency management & ad fatigue

- Benchmarks (context only): fatigue onset ~4 exposures; conversion likelihood −45% after 4 repeats; CTR −40–55% at 5–8 exposures; costs +50–80% at 5+. Prospecting <2.5–3.0, retargeting ~4–6 are starting points only — interpret with objective/window/audience size/purchase cycle/reach/creative mix/trend. Median account frequency ~2.4–2.5; ~80% of an ad's impact happens in the first 2 impressions.
- Fatigue signals: compare CTR/hook-hold/CPA-ROAS/frequency/reach/CPM/creative spend vs. the account's own baseline — deterioration across several signals beats any single fixed threshold. Separate creative fatigue from auction seasonality/audience saturation/spend reallocation/offer or LP changes/conversion lag. "Creative limited"/"Creative fatigue" diagnostics are inputs to validate against outcome trends, not auto-triggers.
- Controls: **Frequency caps** only on Awareness/Reach objective; **Target frequency** on Sales/Awareness/Engagement with lifetime budgets. Conversion campaigns manage frequency indirectly (budget, audience size, creative rotation). Automated rules: prefer notification rules tied to frequency + a performance-deterioration signal, don't auto-pause on frequency alone.
- Responses: new hook/thumbnail, different format, new concept, broader delivery, or budget change — diagnose creative-specific vs. audience-wide first. Pausing an ad set stops delivery; whether it returns to learning on restart depends on Meta's significant-edit handling and live status. Distinguish creative fatigue (one ad declining) from **audience saturation** (reach declining at stable budget, new creatives fail immediately) — fix is audience expansion, not more creative.

---

Tooling: `metaops insights fatigue` (`meta-grey-ops/16`) applies these rules per ad against its own baseline and only notifies.

## 11. Launch-day & weekly checklists

**Launch**: verify events in Test events (value/currency, dedup) — EMQ is diagnostic, not a launch gate; verify domain only if the feature requires it, check legacy AEM only if it exists for the account; UTM template on every ad, click-test GA4 realtime; naming conventions finalized (name tokens lock at publish); budget sized to the decision being made; objective/performance goal matches the tracked event; purchaser/customer exclusions only if matching objective/retention strategy; test landing page on representative mobile/connections; **no AEM/event-config changes within 72h of launch** if on legacy AEM (cool-down pauses delivery); record launch time + expected conversion delay, keep explicit emergency-stop conditions.

**Weekly**: review spend/results per ad not just per campaign (aggregation hides fatigued ads); check Delivery column for Creative limited/fatigue + learning-phase status; review frequency with reach/audience size/creative distribution/trend vs. baseline; review CTR/click-to-LPV/CVR/CPA-ROAS/backend outcomes over windows matched to volume and lag; apply pre-registered stop/scale rules, log changes; maintain a creative pipeline sized to spend/fatigue evidence; clear Diagnostics warnings (value/currency, dedup, EMQ drops), re-test after site/funnel changes; review placements, check audience overlap before scaling duplicates; **reconcile Meta-reported conversions with analytics/backend — either side can be higher** depending on identity, attribution, consent, event loss, duplicates, refunds, reporting time; investigate unexplained/sudden deltas; scale in measured increments, percentage rules are optional starting points.

---

## 12. Attribution windows & settings (2026)

- **Ads Insights API dropped 7-day and 28-day view-through windows on 2026-01-12** (announced 2025-10-16). `action_attribution_windows=7d_view`/`28d_view` stop returning data — reported as silent empty result sets rather than an API error [official removal + date: developers.facebook.com/blog/post/2025/10/16/ads-insights-api-metric-availability-updates/, corroborated developers.facebook.com/documentation/ads-commerce/marketing-api/out-of-cycle-changes/occ-2025 (2025-10-13 entry); "empty not error" behavior is practitioner-reported (ppc.land, dataslayer.ai 2026), not verbatim Meta text — verify live before trusting a silent-zero read]. Remaining supported windows, quoted from the official post: **1-day click, 7-day click, 28-day click, 1-day engaged view, 1-day view**. Meta's attribution help page lists these windows but names no default; the UI default is reported as **7-day click/1-day engage-through/1-day view** [practitioner, 2026-09-25] (`02`§Ad set row). Same 2026-01-12 change set breakdown retention: unique-count and hourly breakdowns **13 months**, frequency breakdowns **6 months**, totals **37 months** [official, same blog post, verified 2026-09-25].
- **Since 2025-06-10, the `action_report_time`/`use_unified_attribution_setting` Insights API parameters are ignored** — API responses now always mirror the ad set's own attribution setting instead of letting a query override reporting time [official: developers.facebook.com/documentation/ads-commerce/marketing-api/out-of-cycle-changes/occ-2025, 2025-03-10 entry, "applies to all versions on June 10, 2025"]. Net effect under the resulting `mixed`-style behavior: on-Meta actions (link clicks, on-Facebook Instant Form leads, Messenger conversations) report by **impression time**; off-Meta actions (website purchases via Pixel/CAPI) report by **conversion time** [on/off-Meta split corroborated by windsor.ai practitioner writeup — Meta's own changelog entry doesn't spell out the on/off-Meta split in those words, only "mimic Meta Ads Manager settings"]. Expect a one-time reporting discontinuity (spikes/gaps vs pre-2025-06-10 pulls) in any dashboard that hardcoded `action_report_time`.
- **Incremental Attribution** exists as a distinct attribution *model*, not just a window choice — separate from Standard attribution. Standard credits any ad that appeared before a conversion (correlation). Incremental is Meta's ML estimate of causal lift, trained on Meta's own Conversion Lift studies, with an **Optimization mode** (shifts delivery toward people the model thinks are incrementally reachable) and a **Measurement mode** (reporting-only column, no delivery change); selecting it locks out manual attribution-window edits on that ad set. Graph API field: `is_incremental_attribution_enabled` on ad set create/update (confirmed live in `meta-grey-ops`'s MCP tool schema and CLI `--incremental-attribution` flag, mutually exclusive with `attribution_spec`). [official Meta Business Help Center pages, confirmed live 2026-09-24: facebook.com/business/help/2366718460372682 "About Incremental Attribution", facebook.com/business/help/644554008179419 "How to Use Incremental Attribution", facebook.com/business/help/1271619100603114 "How to View Results for Incremental Attribution" — page body text wasn't fetchable through available tools this session, so eligibility/rollout detail (available since ~2025-04, widest for Sales/Leads + Website conversion location as of mid-2026, Incremental numbers reading lower than Standard by design) is corroborated via independent practitioner sources (bir.ch, workmagic.io, adsuploader.com 2026) rather than quoted verbatim — re-verify the live help pages before citing eligibility specifics to an advertiser]
- **Custom attribution model** — a third model alongside Standard and Incremental ("About custom attribution", facebook.com/business/help/1521407946215030 [official, title only fetched 2026-09-25 — body renders client-side]); read the live page for setup/eligibility before citing detail.
- **Click-through / engage-through redefinition (rolled out from 03.2026, official: facebook.com/business/news/click-attribution):** click-through attribution for website/in-store conversions now counts **link clicks only** — likes, shares, saves, comments no longer trigger it. Those move to **engage-through** (renamed + broadened from engaged-view; now covers all formats, not just video). Video engaged-view threshold cut **10s → 5s**. Net effect: click-through totals drop by reclassification, not by performance — do NOT optimize against the drop for 2–3 weeks; track click-through and engage-through as separate columns; YoY comparisons crossing 03.2026 are broken unless both series are restated. Billing unchanged. [official announcement + practitioner corroboration 03.2026 — verified live 2026-09-24]

---

## Sources

Official: facebook.com/help (Pixel/dataset relationship), facebook.com/business/help/AboutConversionsAPI, about.fb.com (Meta-enabled CAPI announcement, 2026-04) — reviewed 2026-07-22. §12 added 2026-09-24: developers.facebook.com/blog/post/2025/10/16/ads-insights-api-metric-availability-updates/, developers.facebook.com/documentation/ads-commerce/marketing-api/out-of-cycle-changes/occ-2025 (2025-03-10 and 2025-10-13 entries), facebook.com/business/help/2366718460372682, facebook.com/business/help/644554008179419, facebook.com/business/help/1271619100603114. Practitioner (§12 corroboration): ppc.land, dataslayer.ai, windsor.ai, bir.ch, workmagic.io, adsuploader.com — all accessed 2026-09-24. Practitioner (rest of file): LeadsBridge (CAPI/dataset rename/Offline API shutdown/iOS 26), Segwise (AEM 2026 state, app AEM settings), Jon Loomer (AEM 2023 announcement, event taxonomy, scaling/auction-overlap/CBO-limits QVT series), Conversios/DEPT (AEM removal confirmation), admanage.ai/metricfixer/wevion (UTM setup+mechanics), DataCops/PixelFlow/MB Adv Agency (EMQ scoring, CAPI gateway options), BestEver/AGrowth (Events Manager, advanced matching), adsmurai (iOS14+ delays), Convert/GoStellar/AdStellar/InsightIQ (A/B and creative-testing frameworks), AdAmigo/Atria/Revel Marketing (frequency/fatigue benchmarks), growwithba (kill-criteria, testing budget), datahash/adsmaa (CAPI gateway docs, versioning), Search Engine Journal (original AEM model). All accessed 2026-07-22; exact source URLs were not preserved with this file — re-verify any cited figure live.

## Gaps

- AdAttributionKit replacing SKAdNetwork for Meta app ads is single-sourced (LeadsBridge); Apple's own docs not checked, current SKAN-vs-AAK support state unverified.
- Exact completion date of AEM 8-event-limit removal is fuzzy (announced 2023-05, confirmed removed by mid-2025 in practitioner sources); some accounts reportedly still see the legacy tab; no official Meta changelog found.
- EMQ→CPA/ROAS impact numbers (18%/24%/22%) trace to one AdLeaks 2025 case relayed by vendors — directional, not Meta-published.
- Fatigue/frequency benchmarks are vendor aggregates without disclosed methodology — planning heuristics, not Meta-published thresholds.
- No Instagram-specific (vs. general Meta) tracking differences found — infrastructure is account-level, shared across placements.
- German-court CAPI-consent ruling (2026) cited only by LeadsBridge — case details unverified.
- §12: "empty data not error" for removed Insights attribution windows, and the on-Meta/off-Meta impression-vs-conversion-time split, are practitioner phrasings of an official change — Meta's own changelog text doesn't use those exact words. Incremental Attribution eligibility/rollout detail is practitioner-sourced; the three official Help Center pages exist and are cited, but their body text wasn't fetchable this session — re-check live before quoting eligibility numbers.
