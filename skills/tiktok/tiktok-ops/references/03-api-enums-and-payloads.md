# 03 — Marketing API v1.3: enums, payloads, and the rules that decide success

Verified 2026-09-14 against TikTok's own docs portal. Every enum below is copied from TikTok's
`Enumerations`, `Advertising objective`, `Budget`, and `/campaign/create/` reference pages.

Base URL: `https://business-api.tiktok.com/open_api/v1.3/`
Auth header: `Access-Token: <token>` · `Content-Type: application/json`

## The four defaults that cost money

**1. `operation_status` defaults to `ENABLE`.**
Omit it and your campaign, ad group and ad are created **live and spending**. This is the opposite of
Meta's ergonomics and it is the single most expensive difference. Every create call this skill makes
passes `operation_status: "DISABLE"` explicitly, at every level, without exception.
(Exception that proves the rule: Reach & Frequency campaigns must be `ENABLE` or omitted — R&F does
not accept `DISABLE` at create.)

**2. `advertiser_id` is a string in v1.3.**
It was a number in v1.2. Sending an integer is a class of bug that fails in confusing ways. Quote it.

**3. A budget update must be ≥105% of current spend.**
Not 100%. Read `spend` from a report first, then compute the floor. Budget decreases below that line
are rejected, which reads as an unexplained error if you did not know the rule.

**4. Currency precision and the budget verification ratio.**
The minimum budget is not a dollar figure — it is `base_range × ratio` for the account's currency,
and some currencies take no decimals at all. Getting this wrong is a 100x budget. See § Budget math.

## Objectives (`objective_type`, campaign level, immutable after create)

| Value | Product name |
|---|---|
| `REACH` | Reach |
| `TRAFFIC` | Traffic |
| `VIDEO_VIEWS` | Video views |
| `ENGAGEMENT` | Community interaction |
| `LEAD_GENERATION` | Lead generation |
| `APP_PROMOTION` | App promotion (requires `app_promotion_type`) |
| `WEB_CONVERSIONS` | Website conversions |
| `PRODUCT_SALES` | Product sales (requires `campaign_product_source`; **allowlist-only**) |
| `RF_REACH` | Reach & Frequency (**allowlist-only**, separate `/adgroup/rf/*` endpoints) |

**The Sales objective is a virtual objective, not a new enum.** Website Conversions and Product Sales
merged into one product called "Sales". To create it you send `objective_type` as `WEB_CONVERSIONS`
*or* `PRODUCT_SALES` **plus** `virtual_objective_type: "SALES"` **plus** `sales_destination`
(`TIKTOK_SHOP` | `WEBSITE` | `APP` | `WEB_AND_APP`). An agent that goes looking for a `SALES` enum
will not find one and will pick the wrong objective.

`app_promotion_type`: `APP_INSTALL` | `APP_RETARGETING` | `APP_PREREGISTRATION` (last is allowlist).

## Optimization goals (`optimization_goal`, ad group level)

Current set: `CLICK` · `CONVERT` · `INSTALL` · `IN_APP_EVENT` · `SHOW` · `REACH` · `LEAD_GENERATION`
· `PREFERRED_LEAD` · `CONVERSATION` · `FOLLOWERS` · `PAGE_VISIT` · `VALUE` ·
`AUTOMATIC_VALUE_OPTIMIZATION` · `ENGAGED_VIEW` · `ENGAGED_VIEW_FIFTEEN` ·
`TRAFFIC_LANDING_PAGE_VIEW` · `DESTINATION_VISIT` · `MT_LIVE_ROOM` · `PRODUCT_CLICK_IN_LIVE`

Deprecated / to-be-deprecated: `VIDEO_VIEW`, `CONVERSION_LEADS`, `PROFILE_VIEWS` (use `PAGE_VISIT`).

**Read-only filter values, not creatable:** `GMV`, `PURCHASES`, `INITIATE_CHECKOUTS`. They are
combined filters for GET and reporting endpoints. Passing one to `/adgroup/create/` fails.

Allowlist-gated at time of writing: `CONVERSATION`, `DESTINATION_VISIT`,
`AUTOMATIC_VALUE_OPTIMIZATION`, `TRAFFIC_LANDING_PAGE_VIEW` in Shopping Ads.

Goals that **lock** on create or override `optimization_event`:
- `ENGAGED_VIEW` cannot be changed to another goal after ad group creation.
- `ENGAGED_VIEW`, `ENGAGED_VIEW_FIFTEEN`, `CONVERSATION`, `DESTINATION_VISIT`,
  `TRAFFIC_LANDING_PAGE_VIEW` each auto-populate `optimization_event`. Setting a conflicting
  `optimization_event` is either ignored or an error depending on the goal — do not set it.

`optimization_goal` and `billing_event` are a **locked pairing**, not two independent choices. Pick
the goal; the billing event follows.

## Bidding (`bid_type`) — only two values

| Value | Ads Manager name |
|---|---|
| `BID_TYPE_NO_BID` | **Maximum Delivery** — no bid control, spend the budget, take the results |
| `BID_TYPE_CUSTOM` | **Cost Cap** — manual bid; TikTok recommends it when cost stability matters more than volume |

**Do not port Meta's bid vocabulary.** There is no `LOWEST_COST_WITH_BID_CAP`, no separate Bid Cap
strategy, no `bid_strategy` field. Two values. `bid_type` is deprecated *at campaign level* in v1.3 —
it lives on the ad group.

Value optimization uses `deep_bid_type` instead: `VO_MIN_ROAS` (ROAS goal), `VO_HIGHEST_VALUE` (no
cap), with `optimization_goal: VALUE`. App event bidding: `AEO`, `MIN` (double bid), `PACING`
(automatic), `DEFAULT`. `VO_MIN` is deprecated.

## Billing events (`billing_event`) — fixed by the optimization goal

`CPC` · `CPM` · `CPV` · `OCPM` · `GD` (guaranteed delivery). `OCPC` is deprecated.

`billing_event` is **required**, and it is **not a bidding choice** — TikTok fixes one billing event
per optimization goal and rejects any other pairing:

| `optimization_goal` | `billing_event` |
|---|---|
| `CLICK`, `PAGE_VISIT` | `CPC` |
| `CONVERT`, `INSTALL`, `IN_APP_EVENT`, `TRAFFIC_LANDING_PAGE_VIEW`, `LEAD_GENERATION`, `CONVERSATION`, `FOLLOWERS`, `VALUE`, `AUTOMATIC_VALUE_OPTIMIZATION`, `PRODUCT_CLICK_IN_LIVE`, `MT_LIVE_ROOM`, `DESTINATION_VISIT` | `OCPM` |
| `SHOW`, `REACH` | `CPM` |
| `ENGAGED_VIEW`, `ENGAGED_VIEW_FIFTEEN` | `CPV` |

`ttops preflight` enforces the table offline.

## Required ad-group fields that are easy to omit

These are marked Required or Conditional in the reference and have no useful default:

| Field | When | Note |
|---|---|---|
| `billing_event` | always | See the table above |
| `pacing` | whenever CBO is **off** | `PACING_MODE_SMOOTH` spreads the budget across the schedule; `PACING_MODE_FAST` spends as fast as it can. Under CBO, TikTok overrides it to SMOOTH and your value is ignored |
| `promotion_type` | every objective except `REACH`, `VIDEO_VIEWS`, `ENGAGEMENT` | The optimization location: `WEBSITE`, `LEAD_GENERATION`, `APP_IOS`, `APP_ANDROID`, `TIKTOK_SHOP`, `VIDEO_SHOPPING`, `LIVE_SHOPPING`, `PSA_PRODUCT`, the `LEAD_GEN_CLICK_TO_*` family, `WEBSITE_OR_DISPLAY` (Reach/Video Views/Engagement only) |
| `schedule_start_time` | always | A past time does not error — it starts now |

## Engagement surface (ad group level)

| Field | Effect | Note |
|---|---|---|
| `comment_disabled` | Turns comments off on ads in this ad group | Reversible |
| `video_download_disabled` | Stops users downloading the video ad | **Cannot be updated once created.** Decide before the create call, not after |
| `share_disabled` | Blocks sharing the ad to third-party platforms | Conditional — valid only for certain objectives; check the reference |

There is no default that is right for every account: comments are social proof on a consumer offer
and a liability on a regulated one. The only wrong move is inheriting them by accident, which is what
happens when the fields are omitted. `creative_auto_enhancement_strategy_list` (ad level) is the same
kind of decision — see `tiktok-ads/06`.

`is_hfss` and `is_lhf_compliance` are UK food-advertising declarations. They are compliance answers,
not settings: if the offer is food or drink and you are running in the UK, someone must answer them.

## Attribution windows — set at create, permanent afterwards

`click_attribution_window` · `view_attribution_window` · `engaged_view_attribution_window` ·
`attribution_event_count`. Three rules, all from the ad-group reference:

1. **`click_` and `view_` must be passed together.** One without the other is rejected.
   `engaged_view_` additionally requires both.
2. **Omit them and TikTok silently applies account defaults.** That is how a strategy specifying a
   7-day click window ends up measured on whatever the account happened to be set to. Read the ad
   group back to see what you actually got.
3. **Once set, they cannot be updated.** A wrong window means rebuilding the ad group, not editing it.

Enums: click `OFF`/`ONE_DAY`/`SEVEN_DAYS`/`FOURTEEN_DAYS`/`TWENTY_EIGHT_DAYS` · view
`OFF`/`ONE_DAY`/`SEVEN_DAYS` · engaged view `ONE_DAY`/`SEVEN_DAYS` · event count
`UNSET`/`EVERY`/`ONCE`. Which combinations are legal depends on the objective — TikTok keeps that in
a separate table (doc `1777694366654465`); verify before locking one in.

## Placements (`placements`)

| Value | What it is |
|---|---|
| `PLACEMENT_TIKTOK` | TikTok |
| `PLACEMENT_PANGLE` | Pangle (formerly TikTok Audience Network) |
| `PLACEMENT_GLOBAL_APP_BUNDLE` | CapCut and Fizzo. Geo-gated; does **not** support `TRAFFIC_LANDING_PAGE_VIEW` |
| `PLACEMENT_TOPBUZZ`, `PLACEMENT_HELO` | Deprecated |

`placement_type`: `PLACEMENT_TYPE_AUTOMATIC` | `PLACEMENT_TYPE_NORMAL` (then supply `placements`).

## Budget modes (`budget_mode`) and CBO

| Value | Meaning |
|---|---|
| `BUDGET_MODE_DAY` | Daily budget |
| `BUDGET_MODE_TOTAL` | Lifetime budget |
| `BUDGET_MODE_DYNAMIC_DAILY_BUDGET` | Average daily over a week; daily spend ≤125% of average, weekly ≤ average×7. Partly allowlisted |
| `BUDGET_MODE_INFINITE` | Unlimited (campaign level, CBO off, only) |

**CBO is `budget_optimize_on` (boolean) in v1.3.** The v1.2 name `budget_optimize_switch` is
deprecated — a payload carrying it silently fails to enable CBO. Likewise `industry_types` →
`special_industries`.

Campaign × ad-group budget mode compatibility:

| Campaign ↓ / Ad group → | `TOTAL` | `DAY` | `DYNAMIC_DAILY` |
|---|---|---|---|
| `INFINITE` | ok | ok | ok |
| `TOTAL` | ok | ok | ok |
| `DAY` | **rejected** | ok | ok |
| `DYNAMIC_DAILY` (CBO on) | ignored | ignored | ignored |

With CBO on, ad-group `budget_mode` is ignored entirely. With `schedule_type:
SCHEDULE_FROM_NOW`, ad-group budget must be `BUDGET_MODE_DAY` or `BUDGET_MODE_DYNAMIC_DAILY_BUDGET`.

## Budget math — the 100x guard

```
allowed_daily_range = base_range × budget_verification_ratio(currency)
```

Base daily ranges (per TikTok's per-currency table):

| Level | Standard | `PRODUCT_SALES` + `campaign_product_source: STORE` / ad-group `product_source` `STORE`/`SHOWCASE` |
|---|---|---|
| Campaign | **[50, 10,000,000)** | [10, 10,000,000) |
| Ad group | [20, 10,000,000) | [10, 10,000,000) |

**TikTok's own docs contradict each other on the campaign floor:** the Budget guide says 20 USD,
the per-currency table says base range starts at 50. The per-currency table is the one the
verification logic is described against. **Use 50 for a standard campaign** and expect the lower
number only if a live call proves it. Flag the conflict rather than silently picking.

Verification ratios — **all 56, not an excerpt**, because a partial table is how someone lands on
PHP or VEF and misses it. `*` = **no decimals accepted** (nine of them). Source doc
`1737585839634433`; the same data is `scripts/ttops/currencies.json`, and `ttops budget-check
--currency X` reads it so you never have to.

| Ratio | Currencies |
|---|---|
| 1 | AED, ARS, AUD, BRL, CAD, CHF, EUR, GBP, HUF\*, ILS, MYR, NZD, PEN, QAR, RON, SAR, SGD, USD |
| 4 | PLN |
| 10 | BOB, CNY, CZK, DKK, EGP, GTQ, HKD, HNL, MOP, MXN, NIO, NOK, SEK, THB, TRY, TWD\*, UAH, UYU, ZAR |
| 50 | PHP |
| 100 | BDT, DZD, INR, ISK\*, JPY\*, KES, NGN, PKR, RUB |
| 1,000 | CLP\*, COP, CRC, KRW\* |
| 10,000 | IDR\*, PYG\*, VND\* |
| 100,000 | VEF |

The singletons are the trap: **PLN ×4, PHP ×50, VEF ×100,000.** Each has exactly one member, so a
mental model built on "1, 10, 100, 1000" silently misses all three.

Precision: most currencies take 2 decimals; the **nine** marked above — CLP, HUF, IDR, ISK, JPY,
KRW, PYG, TWD, VND — **take integers only**.

Worked example: a JPY account (ratio 100) has an ad-group daily floor of `20 × 100 = 2,000 JPY` and
a ceiling of 1,000,000,000 — and accepts no decimals. A USD-shaped template landing on it is wrong
by two orders of magnitude in the direction that spends.

**Always read `/advertiser/info/` for the account's real currency before computing any budget, and
state budgets to the operator in major units with the currency named.**

Ads-Manager **Simplified Mode** ad groups can sit below the API floor (Traffic 5, Community
interaction / Lead generation / Conversions 10). Do not infer the API minimum from a number you saw
in the UI.

## Schedule, status, ad format

`schedule_type`: `SCHEDULE_FROM_NOW` | `SCHEDULE_START_END`.
`operation_status`: `ENABLE` | `DISABLE` (see § defaults).
`ad_format`: `SINGLE_IMAGE` | `SINGLE_VIDEO` | `CAROUSEL_ADS` (TikTok placement) | `LIVE_CONTENT`
(live shopping only). `CAROUSEL` (TopBuzz) is deprecated; `image_mode` is deprecated entirely.

Primary statuses for filtering: `STATUS_DELIVERY_OK`, `STATUS_DISABLE`, `STATUS_NOT_DELIVERY`,
`STATUS_TIME_DONE`, `STATUS_DELETE`, `STATUS_NOT_DELETE` (default in sync reports), `STATUS_ALL`.

## Special ad categories (`special_industries`)

`HOUSING` | `EMPLOYMENT` | `CREDIT`. Declaring one **restricts ad-group targeting** to comply with
anti-discrimination law. Generally available to advertisers registered in the US or Canada; others
targeting those countries need an extra allowlist. You can remove a category later but cannot change
it, and cannot add one to an existing campaign that has none. Declare the real one — an empty field
on a credit or housing offer is a violation, not a workaround.

## Idempotency

`request_id` on `/campaign/create/` is a **string of a 64-bit integer**. It does two jobs: it lets
you create campaigns with duplicate names, and it deduplicates retries **within a 10-second window**.
It is not a general idempotency key — a retry 30 seconds later creates a second campaign. This is why
`ttops` records every create in state *before* the POST and never blind-retries (`04`).

## Batch limits

- Status updates: **1–20 IDs** per call.
- GET filters: up to **100 IDs**.
- **There is no bulk create.** Only status changes and reads batch. Mass launch is N sequential
  creates with your own concurrency control — which is what `ttops` bulk does.

## Rate limits

Per **developer app**, four levels; all apps start at Basic. Raise one level at a time via
My Apps → App Detail → Authorization.

| Level | QPS | QPM | QPD |
|---|---|---|---|
| Basic | 10 | 600 | 864,000 |
| Advanced | 20 | 1,200 | 1,728,000 |
| Premium | 30 | 1,800 | 2,592,000 |
| Ultimate | 50 | 3,000 | 4,320,000 |

Endpoint-specific limits override the global one. Notable at Basic: `/ad/create/` 5 QPS / 150 QPM /
86,400 QPD · async report creation 2 QPS / 60 QPM / 4,500 QPD (same at every level) ·
`/catalog/product/upload/` 5 QPS · creative generation endpoints 1 QPS / 30 QPM / 5,000 QPD.
**Events API (`/event/track/`) is 1,000 QPS at every level** and needs no rate-limit application.

**Throttling does not arrive as HTTP 429.** TikTok returns HTTP 200 with `"code": 40100` in the JSON
body. Code-based, not status-based — an HTTP-status-only retry layer will loop forever without
noticing. QPM breach: wait 5 minutes. QPD breach: wait until 00:00:00 **UTC+0**.

## Response envelope

```json
{ "code": 0, "message": "OK", "request_id": "20260914...", "data": { } }
```

`code: 0` is success. **Any non-zero `code` is a failure even though HTTP was 200.** Never branch on
the HTTP status alone. Keep `request_id` in logs — it is what TikTok support asks for. Error catalog:
`05`.

## Minimal create sequence

```bash
POST /campaign/create/   { advertiser_id, objective_type, campaign_name,
                           budget_mode, budget, operation_status: "DISABLE" }
POST /adgroup/create/    { advertiser_id, campaign_id, adgroup_name, promotion_type,
                           placement_type, optimization_goal, billing_event, bid_type,
                           budget_mode, budget, schedule_type, schedule_start_time,
                           targeting…, operation_status: "DISABLE" }
POST /file/video/ad/upload/  → video_id     (async: poll /file/video/ad/info/ until ready)
POST /ad/create/         { advertiser_id, adgroup_id, creatives: [ { ad_name, identity_type,
                           identity_id, ad_format, video_id, image_ids, ad_text,
                           call_to_action, landing_page_url } ],
                           operation_status: "DISABLE" }
```

Then read every object back and diff it against what you sent before enabling anything (`04`
§ verify). **A successful create is not proof the object holds what you sent** — unknown keys are
ignored and enums get filled with defaults silently.

## Version and deprecation posture

v1.3 is current. Deprecated-but-alive surfaces you will meet in older code and blog posts:
Collection Ads (**removed** — cannot be created), Dynamic Showcase Ads (deprecated), Catalog Listing
Ads and Product Shopping Ads (to be deprecated), legacy Smart+ endpoints (`/campaign/create/` with
Smart+ flags) superseded by **Upgraded Smart+** at `/smart_plus/*`.

**The official Python SDK covers legacy endpoints only** — no GMV Max, no `/smart_plus/*`, no split
testing. Anything TikTok shipped recently needs raw HTTP. That is why `ttops` speaks HTTP directly
rather than wrapping the SDK.
