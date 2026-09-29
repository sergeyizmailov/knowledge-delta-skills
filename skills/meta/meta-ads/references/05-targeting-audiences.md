# Audiences & Targeting in Meta Ads Manager (2025–2026)

Reviewed 2026-07-22. "Business Manager" → Business Portfolio; "ASC" folded into Advantage+ campaign setup (2025).

---

## 1. Controls vs Suggestions

- **Audience Controls** = hard constraints Meta won't violate: Locations, minimum age, excluded custom audiences, language (only if uncommon to location). No control for max age/gender under Advantage+ audience.
- **Suggestions** = soft inputs (custom audiences, lookalikes, age range/max, gender, detailed targeting) — delivery AI exceeds them for more performance-goal actions. Applies to Advantage+ audience and, via forced expansion under conversions optimization (§3), original audiences too.
- Meta's cited Advantage+ benchmark (vendor-relayed Mar–Jun 2023 experiment, still in UI warning dialog): 33% lower cost/result, 13% lower cost/catalog sale, 7% lower cost/website conversion, 28% lower cost/click-lead-LPV. [Meta-reported, vendor-relayed, 2023 — no newer official figure]

## 2. Advantage+ Audience (default since Aug 2023)

- 2025 UI: Advantage+ campaign setup merges controls/suggestions into one view with a **Campaign Score**. "Switch to original audiences" → "further limit the reach of your ads" → "Switch setup". Post-switch each input (age range, gender, custom audience, lookalike) stays a suggestion until its checkbox is unchecked — net control is unchanged vs the old flow, just relocated.
- **Use** when broad delivery has a reliable value signal, no demographic-control need (recorded purchase can still be low-quality — refunds/fraud/margin — feed the closest reliable signal anyway).
- **Avoid/switch** for top-of-funnel goals (link clicks, LPV, post engagement, ThruPlay) where low-quality actions mislead delivery, esp. with a narrow real customer age/gender.
- Don't split ad sets whose suggestions converge on the same broad pool without a real budget/geo/policy/test distinction — consolidate.
- Independent tests (directional, single-advertiser, [uncertain]): Thread Transfer May 2025 cross-account — Advantage+ CPM ~25% lower, conversion volume +20%, but manual won CPA ($31.85 vs $34.20), ROAS (3.4x vs 3.2x), CVR (2.4% vs 2.1%). RKX May 2025 (5 ecom campaigns/30d, small n) — Advantage+ CTR 2.3% vs manual 1.7%.

## 3. Original (Manual) Audiences

- Switch: Ad set → Audience → "Switch to original audience options" (Meta warns citing the 33% stat).
- Controls exposed depend on objective/performance goal/region/special category/rollout — verify live. Custom-audience inputs remain suggestions unless the setup exposes the hard control.
- **Expansion products still apply inside "original":**

| Expansion product | Applies to | Off switch? |
|---|---|---|
| Advantage custom audience | Custom audience inputs | Suggestion by default |
| Advantage lookalike | Lookalike inputs | **Forced ON under conversions optimization**; toggleable for other goals (link clicks, LPV, ThruPlay) |
| Advantage detailed targeting | Interest/behavior inputs | **Forced ON for conversions**; forced-on for link clicks/LPV announced but not fully rolled out |

- So "original" ≠ deterministic under a conversions goal: lookalike/detailed-targeting auto-expand, no opt-out. Advertisers targeting a nominal 1% lookalike may get delivery well beyond it.
- Right choice when: (1) top-of-funnel needs demographic guardrails; (2) **true remarketing** — message exclusive to an eligible custom audience; use a setup exposing the restriction and verify reach.

## 4. Detailed Targeting After the 2025 Consolidation

- **2025-03-31 (Ads Manager) → 2025-06-10 (boosts)**: Meta removed ad-set-level detailed targeting exclusions entirely (interest/behavior/demographic) [official, facebook.com/business/help/458835214668072, verified 2026-09-25]. Stated driver: 22.6% lower median cost/conversion without exclusions.
- **2025-06-10 / 2025-06-23**: niche sub-interests merged into broad groupings (e.g. CrossFit/powerlifting/bodybuilding → "Fitness & Exercise"); waves covered Interests then Behaviors/Demographics.
- **2026-01-15**: campaigns still referencing removed interests stop delivering. [timeline cross-confirmed 2026-09-24 across independent third parties (Brandwatch help center + 2+ practitioner blogs: 2025-06-23 consolidation start, 2025-12-15 selection cutoff, 2026-01-15 delivery cutoff) AND an official Meta Business Help Center page for the consolidation (facebook.com/business/help/458835214668072, located 2026-09-24) — treat the three dates as well-corroborated, the consolidation itself as official]
- Stated driver: unconstrained AI outperforms — ~5% more Instagram ad conversions, ~3% Facebook, Q2 2025. [Meta-reported via vendor blog, uncertain] The "~50% ATT opt-in" figure is AppsFlyer's, not Meta's — canonical statement and geo spread: `tracker-ops/03`.
- Remaining tabs: Demographics (age/gender/location/language/education/relationship/life events/work/financial/parents), Interests (11 broad groupings only, no niche sub-interests), Behaviors (purchase behavior, device, travel, digital activities, anniversaries, charitable giving — third-party behaviors reduced, first-party on-platform signals favored).
- Still useful for: new accounts, niche products, B2B, low-volume objectives — pair with a broad audience; don't stack uninterpretable combos, judge by downstream value not CPM/CTR.
- **Exclusions post-March 2025** — interest-exclusion has no replacement in Ads Manager. What still works: custom-audience exclusions at ad-set level (primary mechanism now), account-level controls (brand-protection only: placement/publisher/content exclusions, not audience), creative-based filtering, clean CRM seed/exclusion lists pre-upload.

## 5. Custom Audiences

Ads Manager → Audiences → Create Audience → Custom Audience. 5 sources: Website, Customer list, App activity, Engagement, Offline activity.

- **Website (Pixel)**: rules = all visitors / specific-page (URL contains) / time-spent / pixel events. Retention: 30d default, up to 180d standard events, **730d for purchase events** (raised from 180d, 2026-05). Requires Pixel firing; CAPI recommended post-ATT.
- **Customer list**: CSV, 15 identifier types (email, phone, fn, ln, ct, st, zip, country, dob, birth year, gen, mobile advertiser ID, FB app/Page user ID, external ID). **UI: do NOT pre-hash** (Meta hashes client-side). **Marketing API: MUST pre-hash** (normalize, SHA-256 hex) — inverse rule, common failure point. Match rate 30–60%, improves with multiple identifiers/row + fresh (<12mo) data. Min 100 matched, aim 1,000+. Requires Custom Audience Terms acceptance per ad account. Static — re-upload monthly or sync via CRM/CAPI.
- **App activity**: SDK or App Events API, standard/custom in-app events, retention up to 180d.
- **Engagement** (max retention): Video 25/50/75/95%+ watched — 365d. Lead form opened/submitted — 90d. Instant Experience — 365d. Shopping (view/cart/purchase in shop) — 365d. Instagram account engagement — 730d. Facebook Page engagement — 730d. Events (Interested/Going) — 365d. On-Facebook listings — 365d. Message senders may be unavailable in some EU markets.
- **Offline activity**: in-store/phone/CRM via Conversions API or partner integration. Separate Offline Conversions API discontinued 2025-05 — migrate to datasets.
- **Sizing/hygiene**: 1,000–50,000 sweet spot (below ~1,000 struggles, above ~50k decays); naming `[Brand]_[Source/Event]_[Window]`; never sensitive-trait names (policy violation); refresh CRM monthly; audit pixel firing via Audience Overlap tool. Special Ad Categories (housing/employment/credit/social-political) restrict available features.

## 6. Lookalike Audiences

- Still available (unlike Google Similar Audiences, phased out by 2025) but now raw material for Advantage+, not a hard boundary — under conversions optimization inside original audiences, Advantage lookalike auto-expands beyond the chosen %.
- Creation: Audiences → Create → Lookalike (or from existing custom audience). Choose source (value-based preferred — e.g. Purchase event with value); location (≥1 country); count (up to 6 at once); **percentage 1–10%** (1% = smallest/most similar; start 1–3%, expand 3–5% when scaling exhausts pool). Population takes hours–1 day. Source minimum 100/country (Meta hard rule); 1,000+ for stability.
- Seed quality hierarchy: (1) customer purchase lists, repeat/high-value, 50–70% match — gold standard; (2) pixel purchase events, ideally 1,000+/90d; (3) value-based (LTV-weighted) lists. Weaker: site visitors, engagers. Seed from top 10–20% LTV or 3+ repeat purchasers, refresh monthly — stale seeds → "audience decay."
- **Overlap trap**: nested 1/3/5% lookalikes run in parallel can overlap — no universal CPM penalty; don't fix by multiplying campaigns. Consolidate unless tiers answer a real test question.
- [uncertain, agency-relayed via Madgicx] Advantage+ ~18% lower CPA than classic lookalikes; lookalikes 1–3% ~32% better CPA than interest targeting; Advantage+ Shopping ~17% lower CPA / +16% ROAS vs manual.

## 7. Retargeting Structure

Standard tiers:
- **Warm**: website visitors 90d; catalog/product viewers 90d; Instagram engagers 90d (up to 730d); email-list non-buyers (CRM).
- **Existing customers** (exclusion + upsell): website purchasers 180d; customer-file purchasers (CSV, monthly refresh); IG Shop purchasers.
- **Hot**: cart/checkout abandoners 7–14d; pricing-page visitors; 95% video viewers; lead-form openers who didn't submit (90d cap).

Rules: match retention window to purchase cycle (subscription/replenishable → 28–30d, not 180d). No universal 180-day purchaser-exclusion rule — depends on one-time vs. repeat-offer economics. Optimizing for purchases often needs no separate remarketing ad set — Advantage+ already prioritizes converters/engagers before going broad; isolate true remarketing only when the message must be exclusive.

## 8. Recommended Audience Sizes

- 2–10M = Meta's general prospecting guidance, not a universal limit (depends on geo/objective/budget/CVR/service area).
- Diagnose delivery from reach/frequency/delivery status/auction cost/conversion volume/control-vs-suggestion status, not population size alone.
- Custom audiences: 100 hard min, ~1,000 effective min, 1,000–50,000 sweet spot. Lookalike seeds: ≥100/country required, 1,000+ recommended.
- No universal "50 conversions/week" or "$50/day" threshold makes manual targeting categorically better than automation.

## 9. Location, Language, Age, Gender

### 9.1 Location
Meta removed the residents/recent-visitors/travelers dropdown for new ad sets — delivery now generally targets people living-in-or-recently-in the location; legacy/isolated surfaces may still show old wording. Don't assume `People living in this location` exists unless the live account shows it.
- Radius min ~1 mi/km [uncertain, exact current minimum]; prefer radius over city polygons for hyper-local.
- Location is one of the few remaining hard Audience Controls — Advantage+ won't override it.
- Multi-country e-commerce: split high-spend countries into separate ad sets/campaigns so CPMs/learning don't blend.

### 9.2 Language
Control only when uncommon to the selected location — don't select a geo-dominant language (restricts nothing).

### 9.3 Age and gender
Advantage+ audience: min age only is a control (§1). Original audiences / "further limit the reach": full age range + gender become controls by unchecking suggestion boxes. Platform/legal minimums vary by country/product (alcohol, gambling, financial products can require >18). Special Ad Categories can remove age/gender controls. Common mistake: tight age/gender "for brand fit" while optimizing for purchases — unnecessary, reserve demographic controls for top-of-funnel goals.

---

## 10. Gotchas

1. Treating Advantage+ suggestions as constraints.
2. Non-distinct ad sets fragmenting delivery — consolidate.
3. Assuming every "original audience" input is a fixed constraint — inspect live UI.
4. Trying to exclude by interest post-Mar–Jun 2025 — use custom-audience exclusions.
5. Ad sets referencing removed interests stopped delivering after 2026-01-15.
6. Assuming the removed residents-only location selector still exists.
7. Universal purchaser exclusion ignoring replenishment/upsell/acquisition strategy.
8. Retention window mismatched to purchase cycle (180d for a 30-day replenishment product).
9. Pre-hashing customer lists before **UI** upload (breaks matching); **Marketing API** requires the opposite (pre-hash SHA-256).
10. Parallel 1%/3%/5% lookalike ad sets in one campaign → self-competition, CPM inflation.
11. Sensitive-trait audience names → policy risk.
12. Comparing audience approaches before sufficient delivery/conversion lag — define required sample/window from the account, not a fixed 7–14 days.

---

## Sources

Jon Loomer (Advantage+ audience mechanics/UI/benchmarks; Advantage vs original expansion rules; 730d purchase retention) · AdAmigo (interest consolidation timeline, custom audience creation, engagement retention table) · Conversios (2025-06-23 consolidation date) · Madgicx (lookalike creation, seed LTV, CPA comparisons) · Balistro (seed quality hierarchy) · ivanmana/getkoro (lookalike % mechanics) · Thread Transfer / RKX Advertising (Advantage+ vs manual test data, May 2025) · adenslab/coinis (location/engagement UI detail) · mbadv/adsuploader/audiencelab/leadsbridge (setup walkthroughs, sizing heuristics). All practitioner-sourced, accessed 2026-07-22. Exact source URLs were not preserved with this file — re-verify any cited figure live before quoting it.

## Gaps

- Official Meta Business Help Center pages inaccessible to automated fetch (HTTP 400) — all UI/flow detail here is practitioner-sourced, not primary Meta docs.
- Exact current min radius and available location controls vary by country/objective/special category/rollout — verify live.
- Engagement-audience historical backfill vs forward-only accumulation not verified per subtype.
- 2026-01-15 stop-delivery deadline for removed interests: three dates vendor-corroborated; the consolidation itself now has an official Meta Help Center page (facebook.com/business/help/458835214668072, located 2026-09-24) — re-check it live for the exact cutoff wording.
- Advantage+ 33/28/13/7% benchmarks are vendor-relayed from a 2023 experiment; no newer official figure.
- §6 CPA/ROAS comparisons are agency stats relayed by Madgicx, not primary sources.
