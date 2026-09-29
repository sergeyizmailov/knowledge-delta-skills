# 04 — Mass launch via API

Reviewed 2026-09-06; PBIA, placements, retries and re-moderation sections updated 2026-09-29.

**Execute every mutation through `metaops`** in the order defined by `00-launch-runbook.md`.
The files in `../scripts/` are internal implementations and debugging surfaces; their direct
writes are blocked. Everything below explains what the implementation encodes and cannot decide.
For a missing payload shape, extend `metaops` and its tests instead of issuing a one-off write.

Sections: Structures · Bid strategies · Objective/goal traps · Creative field
traps · Live-verified 2026-09-02 · Scheduling · DLO/multi-language · Media ·
Spend warm-up · Metric levers · Re-moderation · Collection/catalog quirks ·
Verification pass. Read only the section the task needs.

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
- `url_tags` scope: page-post ads, post messages, canvas app-install creatives only — and it can **replace** a colliding query key, not append. Six macros: `{{campaign.id/name}}`, `{{adset.id/name}}`, `{{ad.id/name}}`. The **`.name` ones resolve from a snapshot taken at first publish** — "we store the name values used in a snapshot... Facebook then pulls from the snapshot rather than the live value" [developers.facebook.com/docs/instagram/ads-api/guides/url-tags-for-tracking, 2026-09-18] — so renaming after launch never reaches the tracker. ID macros are unaffected (ids don't change). `{{placement}}`/`{{site_source_name}}` are absent from that page but listed in `meta-ads/08` §5 and used in production (the operator's Keitaro maps `{{placement}}` to sub11, e.g. `Facebook_Mobile_Feed`, 2026-09); they can come back empty in some ASC/catalog configs (`11`). Inside `asset_feed_spec`, `url_tags` is per-asset. Catalog/dynamic cards: click URL comes from the feed; override via `template_url_spec`, not `url_tags` ([unverified] whether url_tags reaches product links at all). Field-proven alternative (news→TG, 2026-09-01): bake the full macro tail into the FEED `link` itself (`?utm_campaign={{campaign.name}}&...&adset_id={{adset.id}}&...`) — survives swaps since it travels with the product row; must be in the feed BEFORE first black delivery, re-upload to change it.
- Catalog/template creatives skip image upload but need catalog asset access + prebuilt product sets. Inspect the live `catalog_management` grant and catalog visibility; availability varies by app/business relationship (see Catalog quirks below).
- **IG identity on farmed fan pages — fix the identity, never drop placements.** No IG placements without a PBIA → POST /ads fails **1772103** "Instagram Account Is Missing". Tempting fix `publisher_platforms=["facebook"]` makes the error vanish while silently killing IG + Audience Network + Messenger reach. The internal launcher resolves `instagram_user_id: "auto"`; a missing PBIA is created in the UI (Ads Manager → Identity → Use Facebook Page; `POST /{page_id}/page_backed_instagram_accounts` is deprecated for all versions since 2025-04-21, v22.0 changelog, verified 2026-09-29; the GET edge is dead too, `18`). Instagram placements are mandatory; `launch.py` rejects specs without them. Pin placements per ad set with `placements: "fb_ig_all" | "fb_ig_feeds"` (`SKILL.md`): omitting `publisher_platforms` means Meta's all-placements incl. Audience Network / Messenger / Threads; `plan` and `verify` WARN on it (FAIL under `lint: "strict"`), and `verify` FAILS any AN / Messenger / Threads on the read-back that the spec did not list. `fb_ig_all` also sets `device_platforms: ["mobile"]` (story/reels positions are mobile-only). PAGE-token requirement + dead `instagram_actor_id` field: meta-ads/13 §5.

## Live-verified 2026-09-02 (own BM, v26.0, System User token)

- Attribution valid only for conversion goals; LINK_CLICKS (and the non-conversion family) rejects any view/engaged window — 100/**1885501** "(1, 0)". `launch.py` defaults those to 1d click only.
- Fresh objects read `effective_status: IN_PROCESS` for minutes at every level (not a defect, `verify.py` accepts it). Copying an IN_PROCESS object fails bare **code 1** (adset: 1/99) — wait for PAUSED.
- `/copies deep_copy=true` capped: 100/**1885194** "must be less than 3" objects at once. `clone.py` copies level-by-level (campaign → adsets w/ campaign_id → ads w/ adset_id) — no cap that way.
- Enhancement read-back is NOT a default-state oracle: a creative with no `degrees_of_freedom_spec` read back all 83 features OPT_OUT (incl. `adapt_to_placement`) on this account — account-level Advertising Settings evidently drives read-back, so "OPT_IN by default" can't be confirmed/refuted via API. Keep sending explicit OPT_OUT — it's the only thing that's yours. `contextual_multi_ads` reads `null` when unsent (doc default OPT_IN), `OPT_OUT` when sent — that one IS verifiable. **Ads Manager-built creatives carry a second block** (field 2026-09-29, all five CF1 ads): `creative_sourcing_spec.featured_offering_spec` ("Show spotlights", pulls website text into the ad) reads back OPT_IN while `degrees_of_freedom_spec` shows nothing OPT_IN, and social-feedback preservation is on; API-built creatives read back OPT_OUT. `verify` now FAILS an ad whose `creative_sourcing_spec` has an OPT_IN unless `creative.opt_in_features` lists it; to clear it on a live ad use `edit creative --enhancements-off` (`16`, re-opens review).
- `attribution_spec` 1d click / 1d view / 1d `ENGAGED_VIDEO_VIEW` accepted on image-only adset, reads back intact.
- `validate_only` on `/adcreatives` catches a dead key (3858504) and creates **nothing** — confirmed absent from `/adcreatives` after a validate_only call with a unique name.
- Rate limit real at buyer pace on Limited tier: ~150 calls/~40min on one account (probe+launch+verify+clone+reads) hit code 17/**2446079** "too many calls" — recovery took minutes. Docs: Limited ≈300 calls/h per ad account, ~300s block (Full 100k/h, 60s); retries extend the block. FIELD 2026-09-27: 60→300s sleep-retries for ~12 min preceded an Account Integrity disable (`06`) → `metaops` no longer sleep-retries: on 17/4/32/613 it stops and records a ≥30 min per-account cooldown (`00` §5). Budget: clone of 1-1-1 ≈ 6 writes+reads; verify ≈ 4 reads/adset. Retries (2026-09-29): transient errors are retried only for GETs and `idempotent=True` calls; a non-idempotent create raises once with `outcome_unknown=true` (reconcile, don't repeat).
- Ad account fields that exist: `default_dsa_beneficiary`, `default_dsa_payor`, `attribution_spec` (null), `is_attribution_spec_system_default`, `offsite_pixels_tos_accepted`, `business_country_code`, `capabilities`, edge `/minimum_budgets`. Do NOT exist: `is_ads_mcp_enabled`, `min_daily_budget_imp` on account node, `dsa_*` on account. `/debug_token` accepts a System User token as its own app token (type SYSTEM_USER, `expires_at: 0` = never).
- Meta Ads MCP with System User bearer → **HTTP 401 "restricted to certain users"** on `tools/list`/`initialize`; `.../ads_mcp_rules` unknown on graph, 404 on ads-api. This BM not enrolled (`is_ads_mcp_enabled` is server-side, not a field).
- Meta Ads CLI 1.1.0: `creative create --no-contextual-multi-ads` → creative reads `contextual_multi_ads: OPT_OUT` correctly; `--status PAUSED` on creative is **ignored** (reads ACTIVE — irrelevant for spend).

## Scheduling — one rule, keyed on optimization goal

| optimization_goal | `start_time` (account tz = geo tz) |
|---|---|
| Conversions (`OFFSITE_CONVERSIONS`, `VALUE`) | **06:00–08:00 geo-time**, or 1–2h before the geo's evening window. NEVER 00:00 |
| Reach/impressions/traffic/awareness (`LINK_CLICKS`, `IMPRESSIONS`, `REACH`) | next **00:00** — full uniform delivery day |

Created ACTIVE by default → verify (spend already started); an ACTIVE create refuses a past/offsetless `start_time` (re-date spec, re-plan); `create_status: PAUSED` keeps the old create → verify → activate order for a run that needs a review window first. Review runs at submission regardless of `start_time` — approval lands before first spend; no documented minimum lead time.

Why: a cold CBO adset opening at 00:00 burns learning-phase impressions into the 00:00–06:00 dead window. Field corroboration 2026-08-30: 5 campaigns launched ~21:30–21:40 TR; by 00:03 three had ZERO delivery. [practitioner, not Meta docs]

Two converting windows/geo-day: ~06:00–08:00 and evening (~16:00+) — pick one, hold per geo. Both avoid dead hours AND the 12:00–18:00 auction peak (brand bid-caps inflate CPM). Never judge a campaign on midday numbers.

## DLO / multi-language via API

Whether the language layer clears review is a `07` question — this is only what `launch.py build_dlo_feed` enforces and why. [doc-confirmed 2026-08-31]

- Accepts only `SINGLE_IMAGE`/`SINGLE_VIDEO` — narrower than `asset_feed_spec` generally.
- 🔺 Locales are **numeric IDs**, not language codes: `customization_spec.locales: [9, 44]`, from `GET /search?type=adlocale&q=en` (English US=6, UK=24). No `language` field — a string locale code is the classic silent miss. Locale **groups expand on read-back**: English (All) 1001 → [6, 24]; Spanish (All) 1002 → [7 Spain, 23 LatAm, Chile included]; Portuguese (All) 1005 → [16, 31]. Vietnamese = 27. A raw id-set diff against the sent spec then shows a false mismatch — expand groups before diffing. Not documented on the multi-language-ads or asset-customization-rules reference pages as of 2026-09-22 — `[unverified]`.
- A rule missing its media label (`image_label`/`video_label`) is rejected; one image/video may omit its label to serve all languages.
- 🔺 `descriptions` is **REQUIRED** — a single-space string for blank; an omitted key or empty list is rejected.
- Exactly one rule carries `is_default: true` (the "Default" slot in `07`'s language trick). Docs conflict on rule count: asset-customization-rules page wants ≥2, autotranslate example ships one — assume two. Field-confirmed 2026-09-21: two rules under `OUTCOME_SALES` (`optimization_goal: OFFSITE_CONVERSIONS`, `promoted_object.custom_event_type: PURCHASE`) launched and read back intact. Second combination now field-confirmed 2026-09-23: `OUTCOME_LEADS` + `OFFSITE_CONVERSIONS` + `COMPLETE_REGISTRATION`, CBO, `SINGLE_VIDEO`, two rules — accepted at POST /ads and activated. Rules read back with `age_min: 13`/`age_max: 65` injected into `customization_spec` even when only `locales` was sent — another false-mismatch source on read-back diffs. Four rules field-confirmed 2026-09-25: `OUTCOME_SALES`+`OFFSITE_CONVERSIONS`+`PURCHASE`, `SINGLE_VIDEO`, default vi 27/az 53/kk 73 + en 1001 + es 1002 + pt 1005. Ads Manager preview always renders the DEFAULT slot first — seeing the white/exotic creative there is correct, not a misconfiguration; switch the preview language to inspect the target slot.
- Adset must explicitly set `is_dynamic_creative: false` for a rule-based feed; `load_spec` rejects a missing or true value before any Graph call.
- 🔺 **The default rule is the CATCH-ALL, and its locale list is decoration.** Every impression
  that matches no added rule renders the default slot — including users whose UI language is not
  in the default rule's own `locales`. So widening the exotic list changes nothing about delivery;
  it only widens what the reviewer-facing slot looks like. What DOES change delivery is the added
  rule: any language you leave out of it gets the white creative and you pay for that impression.
  Field-reasoned 2026-09-23 from the rule semantics, not read off an API response — `[unverified]`.
- 🔺 **`asset_feed_spec` cannot be edited on a live creative.** To widen locales, change a slot's
  copy or swap a slot's video after launch: build a NEW adcreative with the amended feed and
  repoint the ad — `POST /{ad_id}` with `creative={"creative_id": "<new>"}` → `{"success":true}`.
  The ad id, its ad set and the ad set's learning all survive; only review restarts. Rebuild the
  feed from a `GET` of the live creative (`object_story_spec`, `url_tags`,
  `degrees_of_freedom_spec` carried over verbatim) but STRIP the read-back-only noise before
  POSTing it: adlabel `id`s (keep `name`), `thumbnail_url`, `reasons_to_shop`, `shops_bundle`,
  `additional_data`, and the injected `age_min: 13`/`age_max: 65`. Use the ORIGINAL upload
  `video_id`s, never the re-mapped ids the GET returns. Verified 2026-09-23 on four ads.
- Autotranslate (`asset_feed_spec.autotranslate: [...]` + `optimization_type: "LANGUAGE"`): manual edits to a locale also autotranslate-listed are dropped.
- Limits: ≤49 assets/type, title ≤255, body ≤4096, description ≤10000 chars.
- Objective support documented against LEGACY names only, excludes Messenger. ODAX field-confirmed for two combos: `OUTCOME_SALES`+`OFFSITE_CONVERSIONS`+`PURCHASE` (2026-09-21, 2026-09-25) and `OUTCOME_LEADS`+`OFFSITE_CONVERSIONS`+`COMPLETE_REGISTRATION` (2026-09-23). Any other combo is [unverified] and **a dry run won't tell you** — `validate_only` can't validate an ad without a real parent adset id, rejection lands at `POST /ads` on the real create. Build one live DLO ad before scheduling a launch. Hard constraint: Website destination only, no Instant Experience, no Messaging Apps (`07`).
- Not the same thing: "Flexible ads" use top-level `creative_asset_groups_spec` on `POST /act_X/ads`, only under `OUTCOME_SALES`/`OUTCOME_APP_PROMOTION`. Placement Asset Customization reuses the rules machinery with `optimization_type: "PLACEMENT"`.

## Media

Run `scripts/media.py`; notes below are why. [doc-confirmed 2026-08-31 unless marked]

**Images** — `POST /act_X/adimages`, multipart. Multipart FIELD NAME is the filename; needs a real extension (`sample.jpg` works, `sample`/`sample.tmp` rejected). Response keyed by that name: `{"images": {"<name>": {"hash", "url", "width"}}}` — `hash` nested. Returned `url` is temporary, don't reuse in creative creation. Hashes account-scoped in practice (`copy_from={source_account_id, hash}` moves one) — re-upload per account. Use independently produced source creatives for any legitimate creative-test variance; local re-encoding changes file bytes only and is not evidence of platform-level uniqueness.

**Videos** — `POST /act_X/advideos`. Small files: `source`/`file_url`. Anything real: chunked session (resumes).

- 🔺 `graph-video.facebook.com` is **DEPRECATED** — upload to `graph.facebook.com`. Meta's own facebook-python-business-sdk still hardcodes the dead host (`video_uploader.py`, issue #701, open since 2025-04) → 500s.
- Phases: `upload_phase` = `start`→`transfer`→`finish` (`cancel` aborts), carrying `upload_session_id`, `start_offset`, `end_offset`, `video_file_chunk`, `file_size`. **Server dictates chunk boundaries** — each `transfer` returns NEXT offsets; loop until `start_offset==end_offset`. Subcode **1363037** = offsets desynced; payload carries correct ones, resync and retry.
- `start` returns `video_id` immediately — not usable yet.
- 🔺 **The chunked path stalls on large files.** Field-observed 2026-09-23 (`metaops media`, home
  uplink): a 43 MB mp4 uploaded in ~40 s, a 66 MB one hung ~14 min, silently restarted and
  produced a SECOND video object, and the 41 MB file queued behind it never started. No error,
  no progress output — the run just never returns. Cheapest fix, in this order: `ffmpeg -crf 26`
  the file down (66 MB → 29 MB, no visible quality loss at 1080x1920), then a plain multipart
  `POST /act_*/advideos -F name=... -F source=@file` — it returned `{"id":...}` in seconds for
  21 MB where the chunked session had failed. Keep ad videos under ~30 MB as a rule.
- 🔺 The video id **changes on read-back**: the id inside the created creative differs from the id `POST /advideos` returned. Field-observed 2026-09-21: uploaded `1611970353672353`/`1562484555031094`, read back as `1087181073702776`/`1071951112416652` — adlabels stayed correctly bound. Breaks any script that matches assets by `video_id` after creation; re-confirmed 2026-09-25 — match by `length` instead. Mechanism (Meta re-encoding into an ad-scoped copy) is inference — `[unverified]`; not stated on the AdCreativeVideoData reference page as of 2026-09-22.
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
- Billing warm-up (practitioner): run $1-3 campaigns until 1-2 SUCCESSFUL charges post on the FBP before real spend — charged accounts flagged for payment failure far less. Not integrity protection: FIELD 2026-09-27 an account with 21 micro-charges ($2 threshold) still got an Account Integrity disable (n=1).
- **Budget-raise step protocol** (practitioner; Meta only says "small edits don't reset learning, large do", no %): ≤20%/edit, 48-72h between steps, never near end of geo-day (doubled budget at 10pm = 2h to spend it — official troubleshoot doc). Same rule for CBO campaign budget as adset. FIELD-VERIFIED 2026-08-31: +200% on 5 CBO campaigns at once, evening, fresh BM → account-wide silent delivery freeze for hours (all ACTIVE, zero impressions, even brand-new probe campaigns, no API-visible flag). Remedy: revert to last good budget, touch NOTHING 48-72h — new-account spend throttles are real, undocumented, API-invisible. **Tz-midnight leftover** (practitioner, Admatrix 2026): if you scaled during the day (budget $10k, spent $5k), **reset the campaign budget to start size before the account-tz day rolls**. FB can dump yesterday's unspent remainder into the new day → walk-in −$2k. Distinct from the evening +200% freeze: leftover *capacity*, not a learning reset. Aggressive same-day steps (X2 / x5–x10) → `senior-buyer-ops/01`.
- **Day-1 target** (practitioner, multi-source, no source recommends a large day-1 budget): $10-25/day typical open, $50-100 called a real test — this is the buyer's chosen campaign budget, distinct from the account's own spend cap in the ramp line above. Structure: 1-1-1 and one unique domain per ad account both stated near-universally for day 1. Same sources cite a +15-30%/day scaling ceiling and name a 200-300% jump as a trigger — close to, not identical to, the ≤20%/edit protocol above, and consistent with the +200%-freeze already field-verified here.
- Trade-off: too-timid start STARVES the optimization event, keeps adset learning-limited — warm-up caution vs clearing the learning-volume floor is the real tension, not "low = safe".

## Metric levers (grey application; theory in meta-ads/06 & 12)

Account selection + creative volume move CPL more than any budget trick (03, playbooks).

- **Pixel eats only what you feed it.** Send CAPI/pixel ONLY the quality event (deposit/CRM-qualified lead), never raw leads. Displayed CPL can inflate massively (practitioner: $737/lead displayed = $35 real across 21 raw leads; events lag 7-10 days) — do CPL math from CRM/tracker counts, not Ads Manager. Tag campaigns by subid for 1:1 CRM↔postback matching.
- SIGNIFICANT edit (bid_strategy, optimization_goal, promoted_object event/pixel, targeting, large budget change) re-enters learning; renames/pause-resume/small nudges don't. No universal threshold ("~20-30% budget" is a heuristic). Batch harmless edits, stage resetting ones.
- If the deep event is too sparse to exit learning on a fresh account, optimize higher-funnel first, switch down once volume builds. Keep OPTIMIZATION event upstream of PAYOUT event.
- Consolidate: few adsets fed enough budget/day to clear learning beat many starved ones.
- 🔺 **Derive the ad-set COUNT from the budget, never the reverse.** The floor is per ad set, not
  per campaign, and CBO does not exempt you — CBO splits one budget across every ad set, so N ad
  sets on a CBO budget B each effectively run at B/N and each still needs its own ~50 events/7d
  (`meta-ads/06`: illustrative daily budget = `Target CPA x 50 / 7`). Compute that per ad set
  FIRST, then set N = floor(campaign budget / that number). Usually N is 1 or 2, not 4-6.
  FIELD FAILURE 2026-09-23 (TR iGaming, CBO): $30/day across 4 ad sets optimizing
  `COMPLETE_REGISTRATION` at ~5 regs/day TOTAL = ~1 reg/ad-set/day = 7/week against a 50/week
  floor. No ad set ever left learning across four days; CPI drifted +83% ($0.67 -> $1.23) at flat
  spend while impressions halved. A parallel $50/day 6-ad-set campaign behaved the same.
  The published `1-4-1` / `1-5-1` shapes above are CREATIVE-TEST geometries. They are only
  affordable once the per-ad-set floor is covered; at low budget they silently become a
  no-learning setup that reads as a creative or funnel failure.
- 🔺 **Do not downgrade the optimization event just to escape learning.** The tempting fix —
  swapping a sparse deep event (registration) for a plentiful shallow one (install/Lead) — buys
  volume by telling the optimizer to find installers, including those who never register. The
  correct lever is budget concentration onto fewer ad sets, keeping the deep event. Downgrade only
  when consolidation to ONE ad set still cannot clear the floor, and treat it as temporary: it
  contradicts the standing rule two bullets up (`keep OPTIMIZATION event upstream of PAYOUT`) only
  in the sense of moving further upstream, which costs quality. Field consensus for iGaming PWA is
  to hold `CompleteRegistration` (`playbooks/casino.md`).
- Cost-cap ramp: start ~15-30% above target CPA, tighten as it stabilizes.

## Re-moderation: which edits trigger a new review (field-observed, 2026-08)

Review attaches mostly to the CREATIVE, but ad-set edits are NOT reliably safe:
- No status change seen (2026-08, 45 adsets edited 3x in one day): geo, devices, age, placements, budget, bid, schedule, audience. **Contradicted by the 2026-09-22 field case** (`19` §4, `casino.md`): a targeting edit on a live ad set put a live ad back through review and it came back DISAPPROVED ("Spam") within a minute. Treat targeting / placement / geo edits on a live ad set as a possible re-review; budget, bid, schedule stay the low-risk edits. A rename does not review (ACTIVE → IN_PROCESS → ACTIVE in ~15 s, field 2026-09-29).
- TRIGGERS at ad/creative level: CTA, display link, copy, headline, image/link, Multi-advertiser ads, swapping the video.
- An ad still goes to review at create regardless of status (PAUSED or ACTIVE); before first approval, swapping the creative restarts first-pass review (safe, not re-moderation). Rejected ad cannot be enabled (**2490468**, meta-ads/14) — switch it off; a new ad needs a different creative/angle/PWA, never a re-upload of the rejected one into the same account (reads as circumvention, FIELD 2026-09-27).
- 🔺 **The API has no draft buffer.** The API half is [first-party, re-verified 2026-09-24]; the UI half is [help-centre, body renders client-side and could not be fetched — taken from the help article's indexed summary and from meta-ads/02 §10]. An unpublished Ads Manager draft is not submitted for review until Publish (facebook.com/business/help/2198347886909401); creating an ad object via API as PAUSED submits it to review immediately (Ad node reference: new ads enter `PENDING_REVIEW` and don't run until approved/rejected — developers.facebook.com/docs/marketing-api/reference/adgroup/). So the UI lets you build now and let a cold account sit for hours before review ever sees it — advice RU practitioners give for a fresh account — and the API gives that up: there's no way to create-but-not-submit. Trade-off, not a reason to avoid the API — Meta's own rule permits scripting through authorized routes, and the Marketing API is that route.
- 🔺 Vendor MagicClick 2026: flipping ad-level Branding ON↔OFF requeues Rejected/stuck-In-Review without a new creative (5-20 min claimed), hidden if all Advantage+ enhancements OFF; if enable still fails, create a new ad. On a Rejected ad this resubmits the rejected creative — **operator rule: on a disapproval do not edit or resubmit**, so do not use this on a Rejected ad; stuck-In-Review only, and unverified. Schedule-delay is NOT a softer reviewer.

## Collection/catalog launch quirks (field-observed 2026-08-30, own BM, v26.0)

- Omitting `instagram_user_id` on a collection creative → **1772103**. Retry once before diagnosing (one create failed, succeeded unchanged on retry — propagation lag).
- Dead paths: `video_data`+`product_set_id` → **1487832** "invalid repost"; `template_data.retailer_item_ids` on a regular catalog → **1443180** (retailer_item_ids = localized catalogs only).
- 🔺 **`catalog_carousel` is rewritten by Meta** (field 2026-09-27, 238, v26): the template_data carousel creative reads back `asset_feed_spec {optimization_type: FORMAT_AUTOMATION, ad_formats: [CAROUSEL, COLLECTION]}` whether asset_feed_spec was omitted or pinned to `[CAROUSEL]`, and `template_data.description` is not stored. So it may serve as a collection grid; only `catalog_single` (`force_single_link`) stays one card. `swapgate` reads it as `carousel_auto` (collection min 4 applies).
- **One card per ad = `catalog_single` + a ONE-product set.** `catalog_collection` (FORMAT_AUTOMATION carousel/collection) renders a multi-product grid, e.g. 4 tiles in Stories (field 2026-09-26).
- **Research 2026-09-26 (v26 reference + SDK, `metaops` follows it):** ad `effective_status` enum =
  ACTIVE, PAUSED, DELETED, PENDING_REVIEW, DISAPPROVED, PREAPPROVED, PENDING_BILLING_INFO,
  CAMPAIGN_PAUSED, ARCHIVED, ADSET_PAUSED, IN_PROCESS, WITH_ISSUES. A new ad is PENDING_REVIEW "before it
  finishes review and reverts back to your selected status of ACTIVE or PAUSED" → ad-level PAUSED =
  reviewed. PREAPPROVED / IN_PROCESS and ADSET_/CAMPAIGN_PAUSED-during-review are undocumented → the
  swap gate treats them as review / unknown. `ad_review_feedback` = rejection reasons only; no field
  says "approved". Whether a set-filter or item change re-reviews the AD is undocumented (field:
  no re-review seen on set swaps 26.09); item edits DO send the ITEM through item review
  (`review_status` "", pending, rejected, approved, outdated) — the gate refuses a rejected target, warns on
  pending. An empty set stops delivery ("ads tied to this product set will not deliver"): the mutator
  checks members. Set filter ops: and, or, eq, neq, is_any, is_not_any, contains, not_contains, lt, lte,
  gt, gte, starts_with (i_* accepted); 10803 = duplicate filter (documented; subcode 1798073 not).
  Template tags: `{{product.name|description|brand|price|current_price|retailer_id|url|custom_label_0..4}}`;
  `description` is not shown on Instagram. `/{ad}/previews` renders a chosen `product_item_ids`, so it
  cannot prove a swap: read the set members + item `review_status` instead.
- **Product set minimum = 4 items — COLLECTION format ONLY** (**2490457** at build; docs: "at least four elements"). Catalog carousel/single-card has NO minimum (`force_single_link: true`+`product_set_id`; `format_option: carousel_images_single_item`/`show_multiple_images` = one card, verified 2026-08).
  - VIDEO without Collection: attach video to the PRODUCT (feed `video[0].url` per product) + creative `product_set_id` + `format_option:"single_video"` (Dynamic Media path, documented, v25). ⚠ CONTESTED 2026-09-02: business-SDK `format_option` enum doesn't list `single_video` — guide-only. Dry-run one creative before a batch; fall back to `single_image`+Dynamic Media if rejected.
  - 🔺 Catalog card headline: with no `template_data.name`, Meta fills it from the LINK's scraped `<title>` (2026-09-26: PWA white page
    "Your Little Hero: Kids Stories" under a swapped casino card). `launch.py` now sends `name={{product.name}}`,
    `description={{product.description}}` (override: creative.headline / creative.description). `message` is creative-level and never follows a swap.
  - Field evidence 2026-09-26 (Tyver, KG): teammates' depositing catalog ads render as CAROUSEL with product
    VIDEOS — card 1 = casino video (9:16, 13-53 s), cards 2-5 = one white product (kettle) with FR/IT/PL/UA
    descriptions, primary text `-----`, `link_descriptions` `{{product.description}}`. So product-video
    catalogs serve in carousel; exact creative fields not visible from spy — still dry-run first.
  - `media_type_automation` OPT_IN (default) ADDS video alongside images, can't force video-only; OPT_OUT strips video.
  - Manual carousels need 2-5 `child_attachments`. Drives white→slot swap math: review set = 4 white → post-approval mutate to 4 slot (or 3 slot + 1 white if only 3 arts).
- **Set mutation via API** works on UI-created (filter-based) sets: `POST /{product_set_id}` with `filter`. 🔺 Rule is ENCODE EXACTLY ONCE — Meta's own PHP example passes a single-encoded string, that's official. What silently no-ops is **double** encoding: a client that JSON-encodes every complex value re-encodes an already-JSON string, Meta gets escaped quotes, returns id 200, filter unchanged, no error. `metaops assets set-products` invokes the internal mutator, re-reads the set, and fails loudly if the filter didn't change — never trust the 200.
- 🔺 **`promoted_object` is immutable** — “set on creation and cannot be changed”; the only exceptions are adding `application_id`/`product_catalog_id` when absent and changing `pixel_id`/`pixel_rule`/`custom_event_type` — and that only on `CONVERSIONS`/`PRODUCT_CATALOG_SALES`/`OFFSITE_CONVERSIONS`, not on every conversion goal. **`product_set_id` is not an exception**, so an ad set can never be repointed at another product set — that needs a NEW ad set, whose ads re-enter review. Post-approval product changes therefore happen inside the catalog (items, or the set `filter`), never on the ad set [developers.facebook.com/docs/marketing-api/reference/ad-promoted-object, verified 2026-09-20]. `product_set_id` is set on BOTH `adset.promoted_object` and the creative, same value; `boosted_product_set_id` is ad-set-only (cross-sell) and has no creative counterpart — don't mirror it.
- **UI product edit recreates the item under a NEW `product_item_id`** (old id → "does not exist"). Set filters referencing it silently drop → set shrinks. After ANY manual Commerce Manager fix: re-verify `product_count` and refresh filter ids via API.
- **Catalog product create** (`POST /{catalog_id}/products`): `price` = integer minor units. `image_url` must be crawler-stable — adimages fbcdn signed URLs FAIL ("Image fetch failed" → Not eligible). UI upload is the reliable path (subject to the recreate-gotcha above).
- **Catalog Management access**: field-observed 2026-08-30, `catalog_management` was GRANTED on a Business-type Live app, Limited tier, for an own-BM catalog without a separate review. Treat that as account-specific evidence: inspect the live token grant and asset access; App Review/advanced-access requirements can differ for external businesses and app configurations (`02`).
- **Sheet-sourced catalog**: when the catalog is a Google Sheet scheduled feed (`17`), edit the sheet (`sheetfeed`) — the next fetch overwrites batch-API edits; new image = new URL (Meta caches by URL). `metaops feed swap` = upsert + immediate fetch + swap gate + re-review check (`16`).
- **Auction stall** (practitioner heuristic 2026-09): ACTIVE ad set with ≥40 impressions today and 0 clicks → eCTR read as zero, delivery freezes with no API issue. `monitor.py` verdict `STALL` (`--stall-impressions`). Swap the creative angle; raising budget does nothing.
- **Feed-level item swap — two shapes, don't mix**: `POST /{catalog_id}/batch` (top-level `retailer_id`+`method`+`data`) vs `POST /{catalog_id}/items_batch` (requires `item_type: PRODUCT_ITEM`, omitting → code 100). Both return `handles` — confirm via `/{catalog_id}/check_batch_request_status`, don't trust the 200. Swap gate (field 2026-09-01): run the batch only when EVERY ad referencing the swapped items is out of review (a shared item swapped under a pending ad shows the reviewer casino). Do NOT wait for first delivery: swap right at approval [operator 2026-09-26: swap RIGHT AFTER APPROVAL, never wait for first delivery; every white impression is wasted spend]. One-product sets (`assets swap`): only the ads on the swapped sets gate it.
- **template_data catalog creative**: `link` REQUIRED even though cards click via feed — omitting fails **2061015**. Set `caption` to final value at create — later edit restarts review.
- **Pixel pre-flight** — a pixel shared to the BM is NOT on the accounts. Bot-share → accepted on BM → still absent from every ad account until attached by hand (Business Settings → Data sources → Connected assets → Add assets, Full control). Adset create fails **1815045** until then. Gate: `GET /act_{id}/adspixels` must list the pixel on EVERY account before building adsets (field-hit 2026-09-01: px32 on BM, absent on all 3 fresh accounts).
- `targeting_automation: {"advantage_audience": 0}` goes INSIDE `targeting`, not top-level adset field — misplaced → misleading **1870227**.
- **`contextual_multi_ads`** default OPT_IN since 2024-08-19, every objective/format/placement [doc-confirmed, verified 2026-09-02]. `launch.py` sends OPT_OUT everywhere. Read-back differs by shape: `template_data` carousel reads `OPT_OUT` correctly; FORMAT_AUTOMATION collection creative read fails ("nonexisting field") — NOT proof it's off, check UI checkbox **before it spends** (immediately after create by default, or while PAUSED under the `create_status` override). Post-approval toggle = re-moderation.
- 🔺 Attribution IMMUTABLE post-create (**1504040**: "attribution window update no longer supported"). UI's middle "Engaged view" row (renamed "engage-through" 2026-03-03, 5s video threshold — secondary sources, unverified in API, `21`) is `attribution_spec` event_type **`ENGAGED_VIDEO_VIEW`** (not ENGAGED_VIEW) — must be included AT CREATE or stuck with two windows.
- SU token doubles as CAPI dataset token (Full access on pixel/dataset). Clean write probe: `"data": []` → "#100 param data must be non-empty" = auth OK, no events created.
- 🔺 Attribution sub-field is `window_days`, **NOT** `event_window_days` [doc-confirmed, v26.0 ad set reference, verified 2026-08-31]. For `attribution_spec` Graph ignores an unknown sub-key instead of rejecting it (field-confirmed for this param only, not a Graph-wide rule) — a call built with `event_window_days` succeeds, silently keeps the account default (7d click as read here; `21` gives the 2026 UI default as 7d click + 1d engage + 1d view), and every CPL computed against a believed 1-day window is wrong. If any ad set was built with that key, re-read `attribution_spec` before trusting its numbers. No ad-account field reliably reports the account default (live account exposes `attribution_spec: null` + `is_attribution_spec_system_default: true`) — read the AD SET back after create (`verify.py`). Documented windows: click 1 or 7, view 1, engaged-video-view 1; 7d/28d VIEW windows removed from Insights 2026-01-12.
- Insights on fresh campaigns return empty for 15-40 min — not a delivery failure.

## Verification pass

Re-read campaign (budget, bid_strategy), one adset (start_time, promoted_object, bid), one ad (renders, right page). Default ACTIVE create: on mismatch pause first (`edit status --ids … --status PAUSED --confirm PAUSE`), then diagnose. `create_status: PAUSED` override: activate only on match. Resume-safe: every created object ID logged to per-account JSON so a failed run continues, not dupes.
