# Meta Ads Manager — Interface & Navigation

Reviewed 2026-07-22 to 2026-09-02 (see inline dates).

Outdated-UI tell: any guide/screenshot showing Power Editor or 11 objectives is stale (Power Editor merged 2017–18; objectives consolidated into ODAX 2021–22).

---

## 1. Layout

Editing pane opens via row checkbox + Edit [uncertain: exact pane behavior/placement varies by rollout].

## 2. Campaign / Ad set / Ad — fields per level

Over-segmentation (too many ad sets splitting budget) starves learning phase.

**Campaign**: Objective (ODAX, §3) · Buying type (Auction default; Reservation = predictable delivery, eligible accounts only) · Special Ad Categories (financial/employment/housing/social-political — targeting restrictions vary by category/country) · Advantage campaign budget (formerly CBO — `03-campaign-objectives-structure.md` §3) · A/B test toggle.

**Ad set**: Performance goal/conversion event (varies by objective) · Budget & schedule if CBO off — daily budgets average across a week, Meta may spend **~75% more** on high-opportunity days [uncertain, not guaranteed — Shopify] · Audience: Advantage+ (AI, inputs are "suggestions"), Custom, Lookalike (1–10% similarity), detailed targeting · Placements: Advantage+ (auto FB/IG/Messenger/Audience Network/Threads) or Manual — **ad-set placement exclusions being removed since 08/2026** (in-product notice, no formal announcement; replacement = value rules + account-level controls → `04` §3 box; verify live, Help Center lags) · Attribution: Meta's help page lists windows, not a default; **UI default reported as 7-day click/1-day engage-through/1-day view** [practitioner, 2026-09-25]; **API-built ad sets use the launch-tooling default 1d click/1d engaged/1d view** (meta-grey-ops SKILL.md → Launch defaults) — UI and API defaults diverge, don't assume one from the other.

**Ad**: Identity (Page+IG) · Format (single image/video, carousel, collection, flexible) · Creative (media, primary text, headline(s), description, CTA, destination+UTM; multiple text/headline options get rotated by Meta) · Tracking (pixel event/URL params).

## 3. Creation flow

Ads Manager → Campaigns → "+ Create". **Guided creation** (step-by-step) vs **Quick creation** (shell campaign + bulk table).

1. Objective — six ODAX: Awareness, Traffic, Engagement, Leads, App promotion, Sales. Advantage+ campaign = full automation (audience/placement/budget/creative/destination); claimed **~20%** better CPA for Advantage+ sales [vendor-reported, Shopify citing Meta, 2026]. "Single-step Advantage+" automates one component only.
2. Campaign settings (§2) + budget amount if CBO on.
3. Ad set fields (§2) + conversion location/pixel event.
4. Ad fields (§2) + live per-placement preview.
5. Review and publish — review typically minutes to hours; Help Center: "most ads reviewed within 24 hours, although may take longer" — no hard cap; approved ads can be re-reviewed later.

Gotchas: objective gates downstream destinations/goals/events — verify live. Some edits are "significant" and reset learning — check Delivery status, don't assume uniform effect. Special Ad Category campaigns restrict targeting/features by category+country — verify live.

## 4. Campaigns table controls

On/off toggle cascades downward (campaign off → ad sets/ads off). Duplicate can copy with/without results, into another campaign; A/B test = Duplicate → "New A/B test" [HubSpot 2025]. **Delete stops delivery, generally cannot be re-enabled** (historical data stays in reports) — turn off instead if reversibility matters. Delivery column values: Active/In review/Scheduled/Not delivering/Rejected/Completed/Learning/Learning limited — no official universal "50 weekly events" threshold; legacy heuristic, use live status.

## 5. Columns and metrics

Customize Columns: search/add/reorder/save-as-preset. Built-in presets vary by rollout.

Metric gotchas:
- **Results** = different event per campaign (purchase/lead/link-click/ThruPlay by objective) — check meaning per row.
- **Frequency**: fatigue risk above ~5–8 [AdManage: risk >8–9, "optimal" 3–7, campaign-length dependent].
- **CPM** driven by targeting breadth/competition/seasonality (Q4 spikes **50–100%** commonly reported).
- **"CPC (all)"/"CTR (all)"** include reaction/comment clicks, look deceptively cheap — use LINK-click variants for creative eval. Placement CTR [AdManage 2025-11]: FB Feed ~0.9%, IG Feed ~0.5%, Stories ~0.3%.
- **ROAS** needs conversion-value measurement matched to conversion location (web=Pixel/CAPI; app/shop differ); "Purchase ROAS" ≠ "Website purchase ROAS".
- Large click→LPV drop = landing-page problem, not creative.
- Quality/Engagement/Conversion-rate rankings are per-ad vs competitors on the same audience (Above/Average/Below).

Benchmarks [WordStream/LocaliQ 2025, US, Apr 2024–Jun 2025, medians]: Traffic (n=554) CTR 1.71%/CPC $0.70; Leads (n=726) CTR 2.59%/CPC $1.92/CVR 7.72%/CPL $27.66. Industry spread (traffic): Shopping/Collectibles CTR 4.13%/CPC $0.34 (best); Travel CTR 2.76%/CPC $0.51; Finance CTR 0.98%/CPC ~$1.22 (expensive). Alt cross-source averages [Birch via Shopify 2026]: CPM $13.86, CPC $0.74, CPE $0.07, CPL $13.39, CPI $2.30 — methodology differs, don't blend. Never compare traffic-objective CPC to leads-objective CPL.

## 6. Breakdowns and filters

Seven categories [Jon Loomer 2025-12]: Time · Demographics (Age/Gender/Age+Gender, Audience segments — Sales campaigns only, needs defined segments) · Geography · Delivery (Placement, Placement+device, Platform, Time of day) · Action (conversion device, destination, carousel card, reaction type, video view/sound, brand, category, messaging source/outcome) · Dynamic creative element · Creative · bonus: Value rules, Attribution (First conversions vs All other conversions).

High-value uses [Loomer]: Placement breakdown exposes junk distribution (Audience Network inflating cheap link clicks; AN Rewarded Video inflating ThruPlays — results>reach is the tell; Reels soaking Awareness-reach budget). Age/Gender exposes cheap-action over-spend on non-purchase goals (example: 70% of budget on 55+ for registration optimization, value rules cut to 17%). Country breakdown: Meta allocates multi-country budget by cheapest results, not evenly.

Only one breakdown at a time in main table (Ads Reporting allows cross-segmentation, e.g. Age×Gender); breakdowns don't backfill cleanly across all metrics [uncertain]. Filters only hide rows, don't alter data.

## 7. Date presets and charts

Compare toggle shows % change per metric. Default "Last 7 days" view is a classic misread — judge on **≥2 weeks** before decisions [Shopify 2026].

## 8. Custom reports (Ads Reporting)

All tools → Ads Reporting. Combines two breakdowns (cross-segmentation), unlike main table. Save/reload/share (recipients need ad-account access). Export CSV/Excel/chart images. Scheduled recurring email delivery [AdManage 2025-11].

## 9. Automated rules

Path: All tools → Automated Rules (direct `facebook.com/ads/manager/rules`) or table → Rules → Create.

Rule = scope + action + condition(s) + schedule + notification subscriber. **One level per rule** — campaigns OR ad sets OR ads; mixing needs separate rules [Netpeak 2025-03]. Actions: campaign (off/on/notify); ad set (off/on/notify, budget %/absolute change, bid change, scale-by-target-field). Conditions: any metric threshold (cost per result, results, CPC/CPM/CTR, frequency, ROAS, spend, impressions, per-pixel-event costs) plus dayparting ("Current time between…"); ANDed only — OR needs separate rules. Schedule: Continuous (~every 30 min [uncertain]), Daily, Custom.

**Max 250 rules/ad account, including inactive** [Netpeak]. Not available for social-issues/elections/politics ads. Uncapped budget-increase rules can spiral — set ceilings + minimum impressions/spend guards (e.g. Frequency>2 AND CTR<x AND Impressions>8,000). Rules log actions — check history before blaming Meta for budget changes.

**API-side**: cost/ratio conditions (`cpa`, `cost_per_*`, `website_purchase_roas`) are **rejected on ADSET/AD-scoped rules for every action except CHANGE_BUDGET/CHANGE_BID — even NOTIFICATION** (error 2703/subcode 2490336, field-observed 2026-08 on v26.0); campaign scope accepts them, which is why the UI can offer cost conditions at all. Ad-set "cost per result > X → pause" must instead be built as `spent > price × k AND <conversion count> < k+1`. Threshold choice for small samples + field/unit gotchas: `senior-buyer-ops/references/04-automated-rules.md`.

## 10. Drafts/review/publish

Unpublished work = draft; bulk uploads/imports also land as paused drafts [Ads Uploader 2026]. Edit → Review and publish → itemized change list → Publish; Discard reverts. [uncertain: auto-save/review behavior shifted 2024–2025 — some accounts see minor edits auto-applied without a drafts step]. Post-publish: review minutes to hours, officially up to 24h; status In review → Active/Rejected (policy reason, appeal from ad or Account Quality). Creative Hub = separate tool for preview links/client approval pre-launch.

## 11. Billing, spending limit, account quality

Billing: All tools → Billing → Payment settings (also `business.facebook.com/billing_hub`).

**Account spending limit** → `01-business-portfolio-setup.md` §7 (Payments and spending limits).

**Account quality**: `business.facebook.com/accountquality` (or Business Support Home) — shows restrictions/rejected ads/reasons/Request review per asset. Check here first if ads won't run with no visible ban. Common triggers [practitioner consensus]: repeated policy-violating rejections, payment/risk flags (method-country mismatch, suspicious activity), sudden activity spikes on new accounts, ads from restricted Pages.

---

## Sources

1. admanage.ai/blog/facebook-ads-dashboard (2025-11-10, practitioner).
2. shopify.com/blog/facebook-ads-manager (2026-03-22, practitioner).
3. jonloomer.com/essential-breakdowns-meta-ads-manager (2025-12-01, practitioner).
4. netpeak.us/blog/how-to-set-up-automated-rules-in-meta-ads (2025-03-14, practitioner).
5–7. hawky.ai / sepia-lab.com / mbadv.agency — WordStream/LocaliQ 2025 benchmark, three independent secondaries agreeing (n=554/726, Apr 2024–Jun 2025).
8. mbadv.agency/meta-ads/meta-ads-account-structure (practitioner).
9. graphed.com — spending-limit click-path (2025-12-21, practitioner).
10. agrowth.io — ASL definition quoting Meta Help Center (2026-01-11, practitioner).
13. cropink.com/meta-automated-rules — direct rules URL (2026-06-02, practitioner).
14. blog.hubspot.com — A/B test via Duplicate (2025-07-10, practitioner).
15. get-ryze.ai — A/B test toolbar (2026-05-07, practitioner).
16. jonloomer.com/new-facebook-ads-manager — cited only as an example of outdated UI (~2015).
17. adsuploader.com — bulk uploads land as drafts (2026-05-25, practitioner).
18. blackpropeller.com — six ODAX objectives (2026-07-16, practitioner, fetch 403).
19. lobehub.com — CAPI recovers 20–30% conversion data, Advantage+ ~22% ROAS claim (2026-07-03, practitioner).

## Gaps

- Official Help Center articles not directly fetchable; click-paths are practitioner-sourced snapshots, may drift by rollout.
- Editing-pane placement and current auto-save/drafts behavior unverified [§1, §10].
- Exact daily-budget overspend allowance (~75%) not verified against Meta's own wording.
- Continuous-rule check interval (~30 min) unverified.
- Date-preset/column-preset lists vary by rollout, not exhaustively confirmed.
- A/B test statistical methodology (confidence thresholds, min runtime) not covered.
- WordStream 2025 report itself not fetched directly — via three agreeing secondaries.
- Advantage+ performance claims (20–22%) are Meta/vendor-reported, not independently verified.
