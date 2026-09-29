# 03 — Objectives, campaign types, and account structure

Verified 2026-09-14 against TikTok's Marketing API docs and Ads Manager help centre.

**This file describes what exists, not what to pick.** The choice comes from the payout event, the
conversion volume the account can feed, and the tracking that actually works (`01` § D). A skill that
told you "use Website Conversions with Complete Payment" would be wrong for half the accounts that
read it.

## Objectives

| `objective_type` | Product name |
|---|---|
| `REACH` | Reach |
| `TRAFFIC` | Traffic |
| `VIDEO_VIEWS` | Video views |
| `ENGAGEMENT` | Community interaction |
| `LEAD_GENERATION` | Lead generation |
| `APP_PROMOTION` | App promotion (needs `app_promotion_type`) |
| `WEB_CONVERSIONS` | Website conversions |
| `PRODUCT_SALES` | Product sales (needs `campaign_product_source`; **allowlist-only**) |
| `RF_REACH` | Reach & Frequency (**allowlist-only**, separate `/adgroup/rf/*` endpoints) |

Objective is **immutable after creation**. Getting it wrong means a new campaign.

**There is no `SALES` enum.** TikTok merged Website Conversions and Product Sales into a product
called "Sales", created by sending `WEB_CONVERSIONS` *or* `PRODUCT_SALES` plus
`virtual_objective_type: SALES` plus `sales_destination` (`TIKTOK_SHOP` | `WEBSITE` | `APP` |
`WEB_AND_APP`). An agent hunting for a `SALES` objective will not find one and will pick wrong.

**There is no Store Traffic objective.** Meta has one; TikTok does not. The nearest things are
`PRODUCT_SALES` to a TikTok Shop, or O2O catalog ad types nested under App Promotion. Blogs using
"Store Traffic" as a TikTok category are using it as a loose label.

## Objective × optimization goal × billing event

The combination is constrained. Pick the goal; the billing event follows.

| `optimization_goal` | Valid objectives | `billing_event` |
|---|---|---|
| `REACH` | `REACH` | `CPM` |
| `SHOW` | `REACH`, `VIDEO_VIEWS` | `CPM` |
| `CLICK` | `TRAFFIC`, shopping ads | `CPC`, `CPM`, `OCPM` |
| `TRAFFIC_LANDING_PAGE_VIEW` | `TRAFFIC` only, `promotion_type: WEBSITE`, not Global App Bundle | `OCPM` |
| `DESTINATION_VISIT` | `TRAFFIC`, `PRODUCT_SALES` — allowlist | `OCPM` |
| `ENGAGED_VIEW` / `ENGAGED_VIEW_FIFTEEN` | `VIDEO_VIEWS` | `OCPM` |
| `FOLLOWERS` | `ENGAGEMENT` | `OCPM` |
| `PAGE_VISIT` | `ENGAGEMENT` only | `OCPM` |
| `LEAD_GENERATION` | `LEAD_GENERATION` | `OCPM`, `CPC` |
| `PREFERRED_LEAD` | `LEAD_GENERATION` | `OCPM` |
| `CONVERSATION` | `LEAD_GENERATION` (DM/IM) — allowlist | `OCPM` |
| `INSTALL` / `IN_APP_EVENT` | `APP_PROMOTION` | `OCPM` |
| `CONVERT` | `WEB_CONVERSIONS`, `PRODUCT_SALES` | `OCPM` |
| `VALUE` | `WEB_CONVERSIONS`, `APP_PROMOTION`, `PRODUCT_SALES` | `OCPM` |
| `AUTOMATIC_VALUE_OPTIMIZATION` | `WEB_CONVERSIONS` — allowlist | `OCPM` |
| `MT_LIVE_ROOM` / `PRODUCT_CLICK_IN_LIVE` | `PRODUCT_SALES` + `promotion_type: LIVE_SHOPPING` | `OCPM` |

Deprecated: `VIDEO_VIEW`, `CONVERSION_LEADS`, `PROFILE_VIEWS` (use `PAGE_VISIT`).

**Filter-only, not creatable:** `GMV`, `PURCHASES`, `INITIATE_CHECKOUTS`. They are combined filters
for GET and reporting. Passing one to `/adgroup/create/` fails.

Goals that **lock or own their event**: `ENGAGED_VIEW` cannot be changed after ad-group creation.
`ENGAGED_VIEW`, `ENGAGED_VIEW_FIFTEEN`, `CONVERSATION`, `DESTINATION_VISIT` and
`TRAFFIC_LANDING_PAGE_VIEW` each set `optimization_event` themselves — passing one is ignored or
errors.

## Optimization location (`promotion_type`)

Where the conversion happens, and it is a separate axis from the objective:
`WEBSITE` · `APP_ANDROID` / `APP_IOS` · `LEAD_GENERATION` (then `promotion_target_type`:
`INSTANT_PAGE` for a TikTok Instant Form, or `EXTERNAL_WEBSITE`) ·
`LEAD_GEN_CLICK_TO_TT_DIRECT_MESSAGE` · `LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE` ·
`LEAD_GEN_CLICK_TO_CALL` · `TIKTOK_SHOP` · `VIDEO_SHOPPING` · `LIVE_SHOPPING` · `MINI_APP` /
`MINI_GAME` · `WEBSITE_OR_DISPLAY` (Reach/Video views/Engagement only, where the URL is optional).

**Lead generation on TikTok is richer than on Meta.** Instant Form is the obvious one, but
direct-message, instant-messaging-app and phone-call optimization locations exist too — the DM and IM
variants are generally available across much of APAC and LATAM and allowlisted elsewhere. If the
offer is a conversation rather than a form, this is worth checking before defaulting to a landing
page.

## Smart+ — two generations, and an API/UI gap

TikTok maintains **Legacy Smart+ (to be deprecated)** and **Upgraded Smart+** (current, at
`/smart_plus/*`). Upgraded Smart+ folds automation into one flow where budget, placement, targeting,
catalog and creative can each be automatic, partial, or fully manual.

**The API supports fewer objectives than the marketing copy says.** The help centre lists Traffic,
Sales, Lead Generation and App Promotion; the live `/smart_plus/campaign/create/` reference states
only `APP_PROMOTION`, `WEB_CONVERSIONS` and `LEAD_GENERATION`. **No `TRAFFIC`.** If a Traffic Smart+
campaign is needed, assume UI-only until a live call proves otherwise.

Two dated facts:
- From **end of September 2026**, non-CBO App Install VBO Smart+ campaigns can no longer be created
  via API — TikTok says those configurations delivered significantly worse than their CBO
  equivalents. Direct evidence of the platform steering toward CBO.
- Smart+ App also covers **TikTok Minis** (`app_promotion_type: MINIS` — mini series, mini games),
  a 2026 sub-product absent from most third-party guides.

**When Smart+ wins is an open question, not a rule.** The one adoption figure with real provenance:
Tinuiti's Q3 2025 report put Smart+ at 9% → 42% of US TikTok campaigns inside a year. Performance
claims ("29% CPA improvement") trace to TikTok's own marketing, not an audited study, and a widely
cited "50% for Ray-Ban" traces to nothing. Practitioner reading, consistent across sources: Smart+
does better where there is high creative volume and enough historical conversion signal to seed the
model; manual keeps an edge for tight B2B/niche audiences, strict frequency or exclusion
requirements, and placement-level brand-safety control. Test it; do not assume it.

## GMV Max — and the mutual-exclusion rules that break portfolios

Automated campaign type optimizing total channel ROI for a TikTok Shop. Two sub-types: **Product GMV
Max** (auto-selects products, creative and placements) and **LIVE GMV Max** (drives a livestream).
Fully API-creatable at `/gmv_max/*` — not UI-only.

Exclusivity rules that matter more than the performance claims:

- A TikTok Shop can authorize **one ad account at a time** for GMV Max. Re-authorizing a new account
  **automatically pauses existing GMV Max campaigns on the old one.**
- A product can be in **one enabled Product GMV Max campaign** at a time.
- Enabling a shop-wide Product GMV Max campaign **auto-pauses conflicting legacy Video Shopping and
  Product Shopping Ads on the same shop or products — regardless of which ad account created them.**
- LIVE GMV Max is mutually exclusive with Live Shopping Ads on the same identity.

In a multi-buyer or agency setup, one person enabling GMV Max can silently pause another's campaigns.
Establish who owns the Shop authorization before anyone launches.

**Target ROI mode behaves like a cost cap**: it will not spend the full budget unless it can roughly
hit the target. Low budget utilization means the ROI target is too high, **not** that delivery is
broken — a diagnosis people get wrong repeatedly. Max Delivery is an optional add-on with its own
budget, minimum $10/day.

Practitioner reports (unconfirmed against an official deprecation notice) say GMV Max became the
default for TikTok Shop ads in July 2025 and mandatory by September 2025. "30% more GMV than manual"
comes from TikTok's own materials, not an independent audit.

## Structure: what to derive, not copy

**The "3–5 ad groups × 3–5 creatives, ABO then CBO" doctrine you will find everywhere is a
near-verbatim port of Meta convention.** No controlled test supports it on TikTok, and none of the
sources repeating it cites one. Do not encode it as a rule.

What actually constrains structure:

1. **Conversion volume.** TikTok documents **~25 results or 7 days** before volatility falls, and
   separately tells an underperforming ad group to allow 7 days to reach **50** conversions —
   its own two pages disagree (`05`). For structure, plan against the larger number: splitting
   budget across more ad groups than the account can feed is
   the most common self-inflicted wound. Derive the ad-group count from expected conversions/day at
   target CPA (`01` intake #6), not from a template.
2. **The number of genuinely different tests you are running.** One ad group per hypothesis you can
   actually read. A second cell that differs in three ways teaches nothing.
3. **CBO vs ABO.** CBO if you want TikTok to allocate and you have no per-cell budget guarantee to
   protect; ABO if a specific test must be funded regardless of early performance. That is the whole
   decision — it is not a maturity ladder.
4. **Creative supply.** On TikTok the creative is the targeting (`04`, `06`). An ad group with one
   creative is a plan to learn nothing, and a structure that outruns the creative pipeline stalls.

Structural facts that are fixed rather than doctrinal:
- Objective is immutable; so is `ENGAGED_VIEW` once set.
- Attribution window is set **at ad-group creation and locked** (`07`). Two windows means two ad
  groups, decided up front.
- Currency and timezone are fixed at ad-account creation (`02`).
- Campaign `BUDGET_MODE_DAY` forbids an ad-group lifetime budget (`05`).

## Split testing

`/split_test/create/`, `_update/`, `_result/get/`, `_end/`, `_promote/`. A real platform A/B
facility — prefer it to hand-rolled duplicate-and-compare when the question is genuinely one
variable, because the split is handled server-side. Whether the reported difference is statistically
real is a separate question from whether the split ran cleanly — check significance and sample size
before acting on the result.

## Reach & Frequency

`RF_REACH`, allowlist-only, separate endpoints (`/adgroup/rf/create/`, `/rf/inventory/estimate/`,
`/rf/contract/query/`). Reservation buying with `FIXED_SHOW` or `FIXED_REACH` purchase types. Note
R&F campaigns **cannot be created with `operation_status: DISABLE`** — the one exception to
create-paused, so the pre-flight review has to happen before the call, not after.
