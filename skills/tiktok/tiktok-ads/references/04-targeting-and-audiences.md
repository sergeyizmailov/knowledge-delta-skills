# 04 — Targeting, audiences, and why TikTok punishes Meta habits

Verified 2026-09-14 against TikTok's audience-targeting guide and Marketing API enumerations.

## The one structural difference that changes how you plan

**TikTok has no location exclusions.** You cannot exclude a country, region or zip code — you
positively select what you want. A plan written as "target US, exclude these 12 states" does not
translate; it becomes "select the states you want", up to the **3,000 location selections per ad
group** cap.

That is a concrete, verifiable difference. The larger claim — that targeting matters less on TikTok
than creative — is a practitioner consensus with no TikTok source behind it. It is a defensible
starting position, not a fact: start broad, let the creative do the selecting, and add restriction
only where you can name what it prevents. Then check it against your own data rather than repeating
it.

## Targeting fields

| Category | Field | Values / notes |
|---|---|---|
| Gender | `gender` | `GENDER_MALE`, `GENDER_FEMALE`, `GENDER_UNLIMITED` |
| Age | `age_groups` | `AGE_13_17`, `AGE_18_24`, `AGE_25_34`, `AGE_35_44`, `AGE_45_54`, `AGE_55_100` |
| Location | `location_ids`, `zipcode_ids` | Country → region → DMA → city → postal code, via `/tool/region/`. **Zip targeting: US only.** Postal codes: Canada, Brazil, Indonesia, Thailand, Vietnam (the last four allowlisted) |
| Household income | `household_income` | `TOP5`, `TOP10`, `TOP10_25`, `TOP25_50`. **US only** |
| Spending power | `spending_power` | `ALL`, `HIGH` |
| Language | `languages` | Lookup via `/tool/language/`; no fixed enum |
| Interests | `interest_category_ids`, `interest_keyword_ids` | Categories and keyword categories are **separate taxonomies** |
| Purchase intention | `purchase_intention_keyword_ids` | A third, distinct taxonomy |
| Behaviour | `actions` (+ `action_scene`, `action_category_ids`, `action_period`, `video_user_actions`) | Recency-based: video interactions, creator interactions, hashtag interactions |
| Smart interests | `smart_interest_behavior_enabled` | Boolean |
| Smart audience | `smart_audience_enabled` | Expands beyond your Audience settings when it helps — **never touches age, gender or location** |
| Connection | `network_types` | `WIFI`, `2G`, `3G`, `4G`, `5G` |
| OS | `operating_systems` | `ANDROID`, `IOS` (`PC` deprecated) |
| OS version | `min_android_version`, `min_ios_version`, `ios14_targeting` | A floor, not a range |
| Device | `device_model_ids`, `device_price_ranges` | Model list via `/tool/device_model/`; price as a numeric range in local currency |
| Carrier / ISP | `carrier_ids`, `isp_ids` | Separate fields, separate lookups |
| Audiences | `audience_ids`, `excluded_audience_ids` | Custom and lookalike |

**Interests, interest keywords, and purchase intention are three different taxonomies**, each with
its own lookup. Searching one will not surface the others — `/targeting/search/`,
`/tool/interest_category/`, `/tool/interest_keyword/recommend/`,
`/tool/targeting_category/recommend/`.

**Device price targeting is real and useful** in GEOs where handset price proxies for purchasing
power far better than income brackets (which are US-only anyway). Underused outside app UA.

## Smart / automatic targeting

TikTok uses automatic targeting by default. Smart Targeting (smart audience + smart interests) lets
delivery go beyond your Interest/Behaviour and Audience selections when it improves performance —
**but it never overrides age, gender or location.** Those three are hard.

That matters for compliance: if a vertical requires 18+ or 25+, setting `age_groups` is a real
control, not a hint. Interest targeting is not.

## Special ad categories restrict targeting, by design

Declaring `special_industries` (`HOUSING` / `EMPLOYMENT` / `CREDIT`) forces ad groups to:

- disable zip-code targeting, automatic targeting, device-price targeting and targeting expansion;
- disable interest **keywords** (categories still allowed);
- disable lookalike, challenge and preferred-population audiences — **in both include and exclude**;
- exclude under-18 age groups;
- set gender to unlimited;
- disable household income.

Plan the targeting knowing this, rather than discovering it when the ad group is rejected. And
declare the real category: an empty `special_industries` on a credit or housing offer is a violation,
not a workaround.

## Custom audiences

Types: customer file, engagement, app activity, website traffic (pixel), lead generation, TikTok Shop
activity, business account engagement.

Operational limits that break naive sync jobs:

- **24 update operations per audience per 24 hours.**
- **One file-based REPLACE per day.**
- Processing can take **up to 48 hours** — an audience is not usable the moment you upload it.
- An audience with size 0 (fewer than ~1,000 matches) **is not editable** and raises error 40002.
- Minimum size to use an audience in an ad group: **1,000**.

Customer-file matching needs hashed identifiers; normalisation rules are the same discipline as the
Events API (`07` — lowercase and trim email, E.164 phone, SHA-256). Get it wrong and it fails
silently: a low match rate, no error.

## Lookalikes — two constraints people get wrong

**Source audience minimum is 100, not 1,000.** TikTok's API reference states plainly: "the size of
source audience should be no less than 100." The 1,000 figure repeated across blogs is the *ad-group
usage* minimum for a custom audience, conflated. A source audience cannot itself be a lookalike.

**Lookalike creation is geo-gated to 38 markets:**

> AE, AU, AZ, BG, BO, CA, CY, DE, DZ, EE, EG, ES, FR, GB, HR, ID, IL, IN, IT, JP, KE, KR, LK, LT, LV,
> MY, PL, PR, PY, RS, RU, SA, SI, SK, TH, TR, TW, US, VN

Materially narrower than TikTok's advertising footprint. **Absent:** most of LATAM except Bolivia and
Paraguay, most of Southeast Asia except ID/MY/TH/VN, and all of sub-Saharan Africa except Kenya. A
media plan for Mexico, Colombia, Brazil, the Philippines or Nigeria that leans on lookalikes has a
hole in it. Check this list before promising one.

Other fields: `system` (`ALL` / `IOS` / `ANDROID`) restricts the matching pool; `include_source`
controls whether the seed is folded in.

## Audience overlap and estimation

- `ad_audience_size_estimate` — reach estimate before you commit.
- `audience_insight_overlap_get` — overlap between audiences. Worth running before building parallel
  ad groups you believe are distinct; overlapping cells bid against each other and make the test
  unreadable.
- `audience_insight_info_get` — composition.

Use these in the plan (`01` § D4), not after the result confuses you.

## Placements

`PLACEMENT_TIKTOK` · `PLACEMENT_PANGLE` (formerly TikTok Audience Network) ·
`PLACEMENT_GLOBAL_APP_BUNDLE` (CapCut, Fizzo — geo-gated, and **does not support** the
`TRAFFIC_LANDING_PAGE_VIEW` goal). `PLACEMENT_TOPBUZZ` and `PLACEMENT_HELO` are deprecated.

`placement_type` is `PLACEMENT_TYPE_AUTOMATIC` or `PLACEMENT_TYPE_NORMAL` (then list `placements`).

**Pangle is off-platform inventory with different economics and different creative rules.** Cheap
CPMs there can flatter a blended number while contributing nothing. If Pangle is in the mix, break
reporting out by placement before judging anything — and note the commercial music library does not
cover Pangle (`06`).

## Brand safety and inventory

`tiktok_inventory_filters_get/update`, `tool_content_exclusion_get`, `tool_contextual_tag_get`,
`tool_brand_safety_partner_authorize_status_get`. Relevant when a client demands inventory controls;
they narrow delivery, so name what they prevent before adding them.

## Checklist before writing targeting into a plan

1. Does this GEO support the granularity you assumed (zip = US only; postal = 5 markets)?
2. Are you relying on exclusions? **They do not exist for locations.** Rewrite as inclusions.
3. Lookalikes in the plan — is the GEO in the 38?
4. Does the account clear the 1,000-match floor for the custom audience you are planning on?
5. Special ad category declared — and does the plan still work under its restrictions?
6. Age floor set as a hard control where the vertical demands one (`08`)?
7. Overlap checked between cells you intend to compare?
