# 04 — Mass launch via API

Reviewed 2026-09-06.

**Execute every mutation through `metaops`** in the order defined by `00-launch-runbook.md`.
The files in `../scripts/` are internal implementations and debugging surfaces; their direct
writes are blocked. Everything below explains what the implementation encodes and cannot decide.
For a missing payload shape, extend `metaops` and its tests instead of issuing a one-off write.

## Structures

CBO is the default (~90% of current grey iGaming launches). ABO (~10%) is a rare even-split test — **do not kill an ABO campaign on its total spend**: spend is smeared across ad sets; each set may not have reached install price yet. Judge per ad set.

`N-M-K` = campaigns × ad sets × ads per ad set. **Same-file vs different-file is a separate choice** — mixing them silently invalidates the read.

| Shape | Creatives | Use |
|---|---|---|
| 1-1-3 | 3 ads, one ad set | Probe only — Meta dumps ~90% into ONE ad |
| 1-1-1 / 1-N-1 | **different** files | Angle test |
| 1-5-1 **different** | 5 files, 1 per ad set | Angle test, more cells |
| 1-5-1 **same** | one file in all 5 ad sets | CBO allocation of a **winner**, not a creative read |
| 1-3-1 | unique file per ad set | Directional screen; 3–5 ad sets; judge a 3-day window, not day-1 CPL (causal read → A/B tool, measurement-experimentation-ops). Field claim ~2× cheaper, unverified |
| 1-3-3 **same** | same files in each ad set, then dup ad sets | Proven combo — CBO baskets, not a test |

Auction overlap still applies: same creative across ad sets is **not** a clean test. Use same-file 1-5-1 / 1-3-3 only when the question is CBO allocation. CBO reallocates toward the early leader; ABO splits evenly but multiplies spend.

Scale **structure**: 1-1-3 at higher budget, or duplicate the **winning ad set into a NEW campaign** (not extra ad sets inside the same CBO). Step size → `senior-buyer-ops/01` (three modes). Horizontal = more accounts.

## Bid strategies

New CBO campaigns can default to `LOWEST_COST_WITH_BID_CAP` → adset create then rejects without `bid_amount` (**1815857**, field-observed). `launch.py` requires `bid_amount_minor` whenever `bid_strategy` is a cap strategy. `LOWEST_COST_WITH_MIN_ROAS` is value/purchase-funnel only.

## Objective/goal traps (not enforced by the script — spec author's job)

- 🔺 `LEAD_GENERATION` is the lead-**forms** goal (promoted_object `{product_set_id, page_id}`, no `pixel_id`/`custom_event_type`), not the website goal. Any funnel optimized on site events (plain or catalog) needs `optimization_goal: OFFSITE_CONVERSIONS` + `promoted_object {pixel_id, custom_event_type}`. Field-observed 2026-09-01: a handoff spec paired `LEAD_GENERATION` with `pixel_id`+`SUBMIT_APPLICATION` — wrong goal even where Graph accepts it.
- `OUTCOME_SALES` reportedly blocks Lead/Submit Application events (**2446814**, field-observed) → use `OUTCOME_LEADS` for lead funnels.
- EU DSA (`dsa_beneficiary`+`dsa_payor`, SKILL.md) falls back to the ad account's `default_dsa_beneficiary`/`default_dsa_payor` if both are absent; with no defaults either, adset fails **3858152**. `launch.py` requires the pair unless `dsa_from_account_defaults: true` is set. Taiwan/Australia/Singapore financial disclosure is a DIFFERENT mechanism: `regional_regulated_categories: ["TAIWAN_UNIVERSAL"|"AUSTRALIA_FINSERV"|"SINGAPORE_UNIVERSAL"]` + `regional_regulation_identities` on the adset [sdk-source].
- Restricted verticals must declare the real `special_ad_categories` (HOUSING, FINANCIAL_PRODUCTS_SERVICES [replaced CREDIT 2025-01-14], EMPLOYMENT, ISSUES_ELECTIONS_POLITICS) — false/empty is a violation, not a bypass. `launch.py` requires the key present.
- `is_adset_budget_sharing_enabled` ≠ CBO. It's ad-set budget *sharing* (≤20% shared across adsets in a campaign), separate from CBO's 100%. Rule: required when NOT setting budget at campaign level (else **4834011**); not needed if using a campaign budget. `launch.py`'s 3-step create (campaign w/o budget → PATCH budget+bid → budget-less adset) exists because of this — sending budget+bid_strategy at campaign create instead is an untested simplification, not used.
- Targeting POSTs REPLACE the whole object (field-observed) — never send one field. `launch.py build_targeting` always sends the full object.
- **Currency: no minor-unit offset** on TWD, JPY, KRW, HUF, CLP, ISK, PYG, VND, COP, IDR, UGX, XAF, XOF (Marketing API Currencies page). `TWD 300/day` is `daily_budget=300`, not 30000. Verified incident (claude-code#62376, 2026): an agent assumed cents on a TWD account → NT$30,000/day, 100x overspend. `launch.py NO_OFFSET_CURRENCIES` gates this and fails when `spec.currency` ≠ account currency.

## Creative field traps (script builds these; know them to read/debug specs)

- `image_hash` XOR `picture`, never both. `description` ignored on Instagram. Carousel: 2–5 `child_attachments`, `link`+`message` become required.
- 🔺 `video_data` has **no `link` field** — destination is `call_to_action.value.link`. Fields: `video_id`, `image_hash`/`image_url` (thumbnail), `title`, `message`, `link_description` (needs a CTA to render).
- 🔺 `standard_enhancements` in `creative_features_spec` is **REJECTED on create** — live `validate_only` 2026-09-02, code 100/**3858504** "no longer supported, set individual features instead". Live v26.0 read-back = 83 feature keys; `launch.py DEFAULT_OPT_OUT` is that list minus the dead key. No single off-switch exists; each key needs `enroll_status: OPT_IN|OPT_OUT` under `degrees_of_freedom_spec.creative_features_spec`.
  - `adapt_to_placement` is OPT-IN BY DEFAULT — omit it, it stays on.
  - Music not controlled via `creative_features_spec` — use `asset_feed_spec.audios: []`. (`music_generation` key exists on read but has no documented write recipe.)
  - `media_type_automation` OPT_IN needs a catalog → OPT_OUT for plain images (**3858040**).
  - Meta's own docs disagree on writable keys (v26.0 table vs Advantage+ guide; guide even mismatches `image_template` vs `image_templates`). `--dry-run` tells you if your account rejects one.
  - OPT_IN-but-ineligible keys are silently dropped; OPT_OUT keys may still show on GET — harmless. Verify via read-back.
  - 2026-06-28 added `image_animation`, `video_filtering`, `video_uncrop` out-of-cycle.
  - Account-level A+ AI feature test auto-enrollment (14/14 practitioner-audited, no opt-in) is NOT covered by per-ad OPT_OUT — kill switch is account-level toggle + "test new optimizations" checkbox (UI only). Advantage+ audience made detailed-targeting inputs advisory for most goals (Andromeda = retrieval stage, announced engineering.fb.com 2024-12-02); separately Jan 2026 removed DT exclusions for most objectives — Meta's stated reason is a CPA test (~22.6% lower without exclusions), not Andromeda — broad + creative volume is the real lever now.
- 🔺 `advantage_audience` must be explicit on ad-set CREATE (v23+; defaults to 1 only for default/relaxed targeting, else errors). Update path doesn't require it, any version. v26+: Housing/Employment/Financial ads with relaxable targeting also error without it. When enabled: age_min limited 18–25, age_max forced 65; location/min-age/language/custom-audience exclusions never expanded. `launch.py` requires it in the spec.
  - The choice is about which demographics you keep, not about performance alone. **ON destroys an age floor above 25** (the clamp above) — `age_min` is capped at 25 and `age_max` forced to 65, so a 35–55 funnel cannot be expressed at all. **OFF keeps age and gender as real targeting specs**: the forced lookalike/detailed-targeting expansion under conversions goals widens *interests*, and "does not change your targeting specifications for location, demographic targeting, such as age or gender, or exclusions" [developers.facebook.com/docs/marketing-api/audiences/reference/targeting-expansion, 2026-09-04]. So: any hard demographic requirement → `false`, no exceptions. Otherwise ON once the pixel has volume on the optimized event and the offer is broad.
- `url_tags` scope: page-post ads, post messages, canvas app-install creatives only — and it can **replace** a colliding query key, not append. Macros `{{campaign.id/name}}`, `{{adset.id/name}}`, `{{ad.id/name}}` resolve from a **snapshot at first publish** — renaming after launch doesn't update the tracker. Inside `asset_feed_spec`, `url_tags` is per-asset. Catalog/dynamic cards: click URL comes from the feed; override via `template_url_spec`, not `url_tags` ([unverified] whether url_tags reaches product links at all). Field-proven alternative (news→TG, 2026-09-01): bake the full macro tail into the FEED `link` itself (`?utm_campaign={{campaign.name}}&...&adset_id={{adset.id}}&...`) — survives swaps since it travels with the product row; must be in the feed BEFORE first black delivery, re-upload to change it.
- Catalog/template creatives skip image upload but need catalog asset access + prebuilt product sets. Inspect the live `catalog_management` grant and catalog visibility; availability varies by app/business relationship (see Catalog quirks below).
- **IG identity on farmed fan pages — fix the identity, never drop placements.** No IG placements without a PBIA → POST /ads fails **1772103** "Instagram Account Is Missing". Tempting fix `publisher_platforms=["facebook"]` makes the error vanish while silently killing IG + Audience Network + Messenger reach. The internal launcher resolves `instagram_user_id: "auto"`; create a missing PBIA with workspace-bound `metaops doctor --create-pbia`, not by changing placements. PAGE-token requirement + dead `instagram_actor_id` field: meta-ads/13 §5.

## Live-verified 2026-09-02 (own BM, v26.0, System User token)

- Attribution valid only for conversion goals; LINK_CLICKS (and the non-conversion family) rejects any view/engaged window — 100/**1885501** "(1, 0)". `launch.py` defaults those to 1d click only.
- Fresh objects read `effective_status: IN_PROCESS` for minutes at every level (not a defect, `verify.py` accepts it). Copying an IN_PROCESS object fails bare **code 1** (adset: 1/99) — wait for PAUSED.
- `/copies deep_copy=true` capped: 100/**1885194** "must be less than 3" objects at once. `clone.py` copies level-by-level (campaign → adsets w/ campaign_id → ads w/ adset_id) — no cap that way.
- Enhancement read-back is NOT a default-state oracle: a creative with no `degrees_of_freedom_spec` read back all 83 features OPT_OUT (incl. `adapt_to_placement`) on this account — account-level Advertising Settings evidently drives read-back, so "OPT_IN by default" can't be confirmed/refuted via API. Keep sending explicit OPT_OUT — it's the only thing that's yours. `contextual_multi_ads` reads `null` when unsent (doc default OPT_IN), `OPT_OUT` when sent — that one IS verifiable.
- `attribution_spec` 1d click / 1d view / 1d `ENGAGED_VIDEO_VIEW` accepted on image-only adset, reads back intact.
- `validate_only` on `/adcreatives` catches a dead key (3858504) and creates **nothing** — confirmed absent from `/adcreatives` after a validate_only call with a unique name.
- Rate limit real at buyer pace on Limited tier: ~150 calls/~40min on one account (probe+launch+verify+clone+reads) hit code 17/**2446079** "too many calls" — recovery took minutes. `graph.py` waits ≥60s per throttled retry. Budget: clone of 1-1-1 ≈ 6 writes+reads; verify ≈ 4 reads/adset.
- Ad account fields that exist: `default_dsa_beneficiary`, `default_dsa_payor`, `attribution_spec` (null), `is_attribution_spec_system_default`, `offsite_pixels_tos_accepted`, `business_country_code`, `capabilities`, edge `/minimum_budgets`. Do NOT exist: `is_ads_mcp_enabled`, `min_daily_budget_imp` on account node, `dsa_*` on account. `/debug_token` accepts a System User token as its own app token (type SYSTEM_USER, `expires_at: 0` = never).
- Meta Ads MCP with System User bearer → **HTTP 401 "restricted to certain users"** on `tools/list`/`initialize`; `.../ads_mcp_rules` unknown on graph, 404 on ads-api. This BM not enrolled (`is_ads_mcp_enabled` is server-side, not a field).
- Meta Ads CLI 1.1.0: `creative create --no-contextual-multi-ads` → creative reads `contextual_multi_ads: OPT_OUT` correctly; `--status PAUSED` on creative is **ignored** (reads ACTIVE — irrelevant for spend).

## Scheduling — one rule, keyed on optimization goal

| optimization_goal | `start_time` (account tz = geo tz) |
|---|---|
| Conversions (`OFFSITE_CONVERSIONS`, `VALUE`) | **06:00–08:00 geo-time**, or 1–2h before the geo's evening window. NEVER 00:00 |
| Reach/impressions/traffic/awareness (`LINK_CLICKS`, `IMPRESSIONS`, `REACH`) | next **00:00** — full uniform delivery day |

Always PAUSED → verify → ACTIVE. Review runs at submission regardless of `start_time` — approval lands before first spend; no documented minimum lead time.

Why: a cold CBO adset opening at 00:00 burns learning-phase impressions into the 00:00–06:00 dead window. Field corroboration 2026-08-30: 5 campaigns launched ~21:30–21:40 TR; by 00:03 three had ZERO delivery. [practitioner, not Meta docs]

Two converting windows/geo-day: ~06:00–08:00 and evening (~16:00+) — pick one, hold per geo. Both avoid dead hours AND the 12:00–18:00 auction peak (brand bid-caps inflate CPM). Never judge a campaign on midday numbers.

## DLO / multi-language via API

Whether the language layer clears review is a `07` question — this is only what `launch.py build_dlo_feed` enforces and why. [doc-confirmed 2026-08-31]

- Accepts only `SINGLE_IMAGE`/`SINGLE_VIDEO` — narrower than `asset_feed_spec` generally.
- 🔺 Locales are **numeric IDs**, not language codes: `customization_spec.locales: [9, 44]`, from `GET /search?type=adlocale&q=en` (English US=6, UK=24). No `language` field — a string locale code is the classic silent miss.
- A rule missing its media label (`image_label`/`video_label`) is rejected; one image/video may omit its label to serve all languages.
- 🔺 `descriptions` is **REQUIRED** — a single-space string for blank; an omitted key or empty list is rejected.
- Exactly one rule carries `is_default: true` (the "Default" slot in `07`'s language trick). Docs conflict on rule count: asset-customization-rules page wants ≥2, autotranslate example ships one — assume two.
- Adset must explicitly set `is_dynamic_creative: false` for a rule-based feed; `load_spec` rejects a missing or true value before any Graph call.
- Autotranslate (`asset_feed_spec.autotranslate: [...]` + `optimization_type: "LANGUAGE"`): manual edits to a locale also autotranslate-listed are dropped.
- Limits: ≤49 assets/type, title ≤255, body ≤4096, description ≤10000 chars.
- Objective support documented against LEGACY names only, excludes Messenger. Whether ODAX `OUTCOME_*` works is [unverified] and **a dry run won't tell you** — `validate_only` can't validate an ad without a real parent adset id, rejection lands at `POST /ads` on the real create. Build one live DLO ad before scheduling a launch. Hard constraint: Website destination only, no Instant Experience, no Messaging Apps (`07`).
- Not the same thing: "Flexible ads" use top-level `creative_asset_groups_spec` on `POST /act_X/ads`, only under `OUTCOME_SALES`/`OUTCOME_APP_PROMOTION`. Placement Asset Customization reuses the rules machinery with `optimization_type: "PLACEMENT"`.

## Media

Run `scripts/media.py`; notes below are why. [doc-confirmed 2026-08-31 unless marked]

**Images** — `POST /act_X/adimages`, multipart. Multipart FIELD NAME is the filename; needs a real extension (`sample.jpg` works, `sample`/`sample.tmp` rejected). Response keyed by that name: `{"images": {"<name>": {"hash", "url", "width"}}}` — `hash` nested. Returned `url` is temporary, don't reuse in creative creation. Hashes account-scoped in practice (`copy_from={source_account_id, hash}` moves one) — re-upload per account. Use independently produced source creatives for any legitimate creative-test variance; local re-encoding changes file bytes only and is not evidence of platform-level uniqueness.

**Videos** — `POST /act_X/advideos`. Small files: `source`/`file_url`. Anything real: chunked session (resumes).

- 🔺 `graph-video.facebook.com` is **DEPRECATED** — upload to `graph.facebook.com`. Meta's own facebook-python-business-sdk still hardcodes the dead host (`video_uploader.py`, issue #701, open since 2025-04) → 500s.
- Phases: `upload_phase` = `start`→`transfer`→`finish` (`cancel` aborts), carrying `upload_session_id`, `start_offset`, `end_offset`, `video_file_chunk`, `file_size`. **Server dictates chunk boundaries** — each `transfer` returns NEXT offsets; loop until `start_offset==end_offset`. Subcode **1363037** = offsets desynced; payload carries correct ones, resync and retry.
- `start` returns `video_id` immediately — not usable yet.
- Readiness gate: `GET /{video_id}?fields=status` → `status.video_status` ∈ `ready`|`processing`|`error`, + `processing_progress` 0-100. Building an ad against a processing video fails "Video not ready" (100/**1885252**, community-sourced [unverified-official]). Poll to `ready`. No official processing-time figure.
- Upload errors: 351 video file problem, 352 unsupported format, 382 too small, 389 cannot fetch from URL, 6000/6001 upload failure.
- Resumable Upload API (`POST /{app_id}/uploads`) is documented for `/{page_id}/videos`, **not** in v26 `/act_X/advideos` params — whether ad accounts accept it [unverified]. Use the `upload_phase` flow above (still in v26 endpoint ref).

**Video thumbnails** — `GET /{video_id}/thumbnails` → `{id, uri, width, height, scale, is_preferred}`.
- Sanctioned: fetch preferred `uri`, re-upload via `/adimages`, put hash in `video_data.image_hash` (AdCreativeVideoData ref says don't feed FB CDN URLs into `image_url`). `media.py` does this automatically.
- Workaround: pass `uri` directly as `image_url` — must be **WHOLE**, every query param (~500 chars); truncating fails creation (**2446603**) [inference from signed params, unverified as sole cause].
- Custom thumbnail: `POST /{video_id}/thumbnails` with `source`+`is_preferred`. Max 10MB, only on videos already tied to a Page.

Review is async — don't rebuild on first-hour silence. **CSV bulk import** (Ads Manager): blocked on fresh accounts (**#3738001**, field-observed, needs history). Budgets in cents, clear IDs, imports PAUSED.

## Spend warm-up (fresh accounts, ~d0-3)

A high day-0 budget on a fresh/low-history account triggers review and tanks delivery. Open conservative, step up as the account proves stable — exact ramp is account/GEO/vertical-specific, a TL-set prior, not a rule.

- Organic limit ramp (practitioner, unverified): fresh BM accounts often open at ~$150/day; hitting the cap 1-2 days running raises it organically (~$250-300, then ~$600). Ramp by spending into the cap — don't request increases.
- Billing warm-up (practitioner): run $1-3 campaigns until 1-2 SUCCESSFUL charges post on the FBP before real spend — charged accounts flagged for payment failure far less.
- **Budget-raise step protocol** (practitioner; Meta only says "small edits don't reset learning, large do", no %): ≤20%/edit, 48-72h between steps, never near end of geo-day (doubled budget at 10pm = 2h to spend it — official troubleshoot doc). Same rule for CBO campaign budget as adset. FIELD-VERIFIED 2026-08-31: +200% on 5 CBO campaigns at once, evening, fresh BM → account-wide silent delivery freeze for hours (all ACTIVE, zero impressions, even brand-new probe campaigns, no API-visible flag). Remedy: revert to last good budget, touch NOTHING 48-72h — new-account spend throttles are real, undocumented, API-invisible. **Tz-midnight leftover** (practitioner, Admatrix 2026): if you scaled during the day (budget $10k, spent $5k), **reset the campaign budget to start size before the account-tz day rolls**. FB can dump yesterday's unspent remainder into the new day → walk-in −$2k. Distinct from the evening +200% freeze: leftover *capacity*, not a learning reset. Aggressive same-day steps (X2 / x5–x10) → `senior-buyer-ops/01`.
- Trade-off: too-timid start STARVES the optimization event, keeps adset learning-limited — warm-up caution vs clearing the learning-volume floor is the real tension, not "low = safe".

## Metric levers (grey application; theory in meta-ads/06 & 12)

Account selection + creative volume move CPL more than any budget trick (03, playbooks).

- **Pixel eats only what you feed it.** Send CAPI/pixel ONLY the quality event (deposit/CRM-qualified lead), never raw leads. Displayed CPL can inflate massively (practitioner: $737/lead displayed = $35 real across 21 raw leads; events lag 7-10 days) — do CPL math from CRM/tracker counts, not Ads Manager. Tag campaigns by subid for 1:1 CRM↔postback matching.
- SIGNIFICANT edit (bid_strategy, optimization_goal, promoted_object event/pixel, targeting, large budget change) re-enters learning; renames/pause-resume/small nudges don't. No universal threshold ("~20-30% budget" is a heuristic). Batch harmless edits, stage resetting ones.
- If the deep event is too sparse to exit learning on a fresh account, optimize higher-funnel first, switch down once volume builds. Keep OPTIMIZATION event upstream of PAYOUT event.
- Consolidate: few adsets fed enough budget/day to clear learning beat many starved ones.
- Cost-cap ramp: start ~15-30% above target CPA, tighten as it stabilizes.

## Re-moderation: which edits trigger a new review (field-observed, 2026-08)

Review attaches to the CREATIVE, not the adset:
- SAFE at adset level: geo, devices, age, placements, budget, bid, schedule, audience — 45 adsets edited 3x in one day, zero status changes.
- TRIGGERS at ad/creative level: CTA, display link, copy, Multi-advertiser ads, swapping the video.
- Ad created PAUSED still goes to review; before first approval, swapping the creative restarts first-pass review (safe, not re-moderation). Rejected ad cannot be enabled (**2490468**, meta-ads/14) — create a new ad.
- 🔺 Vendor MagicClick 2026: flipping ad-level Branding ON↔OFF requeues Rejected/stuck-In-Review without a new creative (5-20 min claimed), hidden if all Advantage+ enhancements OFF; if enable still fails, create a new ad. Schedule-delay is NOT a softer reviewer.

## Collection/catalog launch quirks (field-observed 2026-08-30, own BM, v26.0)

- Omitting `instagram_user_id` on a collection creative → **1772103**. Retry once before diagnosing (one create failed, succeeded unchanged on retry — propagation lag).
- Dead paths: `video_data`+`product_set_id` → **1487832** "invalid repost"; `template_data.retailer_item_ids` on a regular catalog → **1443180** (retailer_item_ids = localized catalogs only).
- **Product set minimum = 4 items — COLLECTION format ONLY** (**2490457** at build; docs: "at least four elements"). Catalog carousel/single-card has NO minimum (`force_single_link: true`+`product_set_id`; `format_option: carousel_images_single_item`/`show_multiple_images` = one card, verified 2026-08).
  - VIDEO without Collection: attach video to the PRODUCT (feed `video[0].url` per product) + creative `product_set_id` + `format_option:"single_video"` (Dynamic Media path, documented, v25). ⚠ CONTESTED 2026-09-02: business-SDK `format_option` enum doesn't list `single_video` — guide-only. Dry-run one creative before a batch; fall back to `single_image`+Dynamic Media if rejected.
  - `media_type_automation` OPT_IN (default) ADDS video alongside images, can't force video-only; OPT_OUT strips video.
  - Manual carousels need 2-5 `child_attachments`. Drives white→slot swap math: review set = 4 white → post-approval mutate to 4 slot (or 3 slot + 1 white if only 3 arts).
- **Set mutation via API** works on UI-created (filter-based) sets: `POST /{product_set_id}` with `filter`. 🔺 Rule is ENCODE EXACTLY ONCE — Meta's own PHP example passes a single-encoded string, that's official. What silently no-ops is **double** encoding: a client that JSON-encodes every complex value re-encodes an already-JSON string, Meta gets escaped quotes, returns id 200, filter unchanged, no error. `metaops assets set-products` invokes the internal mutator, re-reads the set, and fails loudly if the filter didn't change — never trust the 200.
- **UI product edit recreates the item under a NEW `product_item_id`** (old id → "does not exist"). Set filters referencing it silently drop → set shrinks. After ANY manual Commerce Manager fix: re-verify `product_count` and refresh filter ids via API.
- **Catalog product create** (`POST /{catalog_id}/products`): `price` = integer minor units. `image_url` must be crawler-stable — adimages fbcdn signed URLs FAIL ("Image fetch failed" → Not eligible). UI upload is the reliable path (subject to the recreate-gotcha above).
- **Catalog Management access**: field-observed 2026-08-30, `catalog_management` was GRANTED on a Business-type Live app, Limited tier, for an own-BM catalog without a separate review. Treat that as account-specific evidence: inspect the live token grant and asset access; App Review/advanced-access requirements can differ for external businesses and app configurations (`02`).
- **Sheet-sourced catalog**: when the catalog is a Google Sheet scheduled feed (`17`), edit the sheet (`sheetfeed`) — the next fetch overwrites batch-API edits; new image = new URL (Meta caches by URL). `metaops feed swap` = upsert + immediate fetch + swap gate + re-review check (`16`).
- **Auction stall** (practitioner heuristic 2026-09): ACTIVE ad set with ≥40 impressions today and 0 clicks → eCTR read as zero, delivery freezes with no API issue. `monitor.py` verdict `STALL` (`--stall-impressions`). Swap the creative angle; raising budget does nothing.
- **Feed-level item swap — two shapes, don't mix**: `POST /{catalog_id}/batch` (top-level `retailer_id`+`method`+`data`) vs `POST /{catalog_id}/items_batch` (requires `item_type: PRODUCT_ITEM`, omitting → code 100). Both return `handles` — confirm via `/{catalog_id}/check_batch_request_status`, don't trust the 200. Swap gate (field 2026-09-01): run the batch only when EVERY ad referencing the catalog is out of review AND has first delivery — a reject on white stops the swap outright (catalog is shared by all its campaigns; report, don't proceed).
- **template_data catalog creative**: `link` REQUIRED even though cards click via feed — omitting fails **2061015**. Set `caption` to final value at create — later edit restarts review.
- **Pixel pre-flight** — a pixel shared to the BM is NOT on the accounts. Bot-share → accepted on BM → still absent from every ad account until attached by hand (Business Settings → Data sources → Connected assets → Add assets, Full control). Adset create fails **1815045** until then. Gate: `GET /act_{id}/adspixels` must list the pixel on EVERY account before building adsets (field-hit 2026-09-01: px32 on BM, absent on all 3 fresh accounts).
- `targeting_automation: {"advantage_audience": 0}` goes INSIDE `targeting`, not top-level adset field — misplaced → misleading **1870227**.
- **`contextual_multi_ads`** default OPT_IN since 2024-08-19, every objective/format/placement [doc-confirmed, verified 2026-09-02]. `launch.py` sends OPT_OUT everywhere. Read-back differs by shape: `template_data` carousel reads `OPT_OUT` correctly; FORMAT_AUTOMATION collection creative read fails ("nonexisting field") — NOT proof it's off, check UI checkbox **while PAUSED**. Post-approval toggle = re-moderation.
- 🔺 Attribution IMMUTABLE post-create (**1504040**: "attribution window update no longer supported"). UI's middle "Engaged view" row is `attribution_spec` event_type **`ENGAGED_VIDEO_VIEW`** (not ENGAGED_VIEW) — must be included AT CREATE or stuck with two windows.
- SU token doubles as CAPI dataset token (Full access on pixel/dataset). Clean write probe: `"data": []` → "#100 param data must be non-empty" = auth OK, no events created.
- 🔺 Attribution sub-field is `window_days`, **NOT** `event_window_days` [doc-confirmed, v26.0 ad set reference, verified 2026-08-31]. For `attribution_spec` Graph ignores an unknown sub-key instead of rejecting it (field-confirmed for this param only, not a Graph-wide rule) — a call built with `event_window_days` succeeds, silently keeps the account default (7d click), and every CPL computed against a believed 1-day window is wrong. If any ad set was built with that key, re-read `attribution_spec` before trusting its numbers. No ad-account field reliably reports the account default (live account exposes `attribution_spec: null` + `is_attribution_spec_system_default: true`) — read the AD SET back after create (`verify.py`). Documented windows: click 1 or 7, view 1, engaged-video-view 1; 7d/28d VIEW windows removed from Insights 2026-01-12.
- Insights on fresh campaigns return empty for 15-40 min — not a delivery failure.

## Verification pass

Re-read campaign (budget, bid_strategy), one adset (start_time, promoted_object, bid), one ad (renders, right page). Activate only on match. Resume-safe: every created object ID logged to per-account JSON so a failed run continues, not dupes.
