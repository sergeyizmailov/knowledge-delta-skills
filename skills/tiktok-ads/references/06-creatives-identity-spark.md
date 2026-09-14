# 06 — Creatives, identity, Spark Ads

Verified 2026-09-14. Several TikTok help pages return 403 to automated fetch; where a figure is
cross-sourced rather than pulled from a primary page it is marked. **Specs change without a
changelog** — re-check before a large production run.

`ads.tiktok.com/help/article/...` blocks automated fetches; `ads.tiktok.com/resources/help/article/...`
serves the same content and works for a live spec check.

## On TikTok, the creative is the targeting

This is the one framing worth importing. Delivery is creative-led to a degree Meta buyers
consistently underestimate, and the practical consequence is that an ad group with one creative
tests nothing. Treat creative count and refresh cadence as the plan's binding constraint (`01`
intake #9), not as an afterthought.

The stronger versions of this claim — specific decay curves, "TikTok needs 20 creatives a week" —
are practitioner consensus without a controlled test behind them. Design so you do not need them to
be true.

## Formats available in 2026

In-Feed · **Spark Ads** (a delivery mode on top of In-Feed/Carousel, not a separate creative unit) ·
Carousel (`CAROUSEL_ADS`, TikTok placement) · Video Shopping Ads / Catalog Ads · Playable ·
TopView / reservation formats (largely reservation-only; Q3 2026 introduced allowlisted self-serve
access in select markets under a purchase agreement).

**Collection Ads are gone** — deprecated and merged into Video Shopping Ads. They cannot be created,
edited or duplicated. **Dynamic Showcase Ads** is likewise not a current TikTok term; the current
name is **Catalog Ads** / Smart+ Catalog Ads. Catalog Listing Ads were folded into Video Shopping Ads
back in 2023. Any plan or script naming these formats is working from stale material.

`ad_format` enum: `SINGLE_IMAGE` · `SINGLE_VIDEO` · `CAROUSEL_ADS` · `LIVE_CONTENT` (live shopping
only). `CAROUSEL` (TopBuzz) and `image_mode` are deprecated.

## Video specs — and the placement branch people miss

**Core (In-Feed / Spark / standard auction):**

| Attribute | Spec |
|---|---|
| Aspect ratio | 9:16 (recommended), 1:1, 16:9 |
| Resolution | vertical ≥540×960 (1080×1920 recommended) · square ≥640×640 · horizontal ≥960×540 |
| Duration | 5 s minimum, up to 10 minutes. TikTok recommends 21–30 s; 9–15 s reported best for completion |
| File | ≤500 MB · .mp4 .mov .mpeg .3gp .avi · bitrate ≥516 kbps |

**Global App Bundle / Pangle is a different spec sheet** — branch on placement:

| Attribute | Spec |
|---|---|
| Resolution floors | vertical ≥**720×1280** · horizontal ≥**1280×720** · square ≥640×640 |
| Duration | 5–60 s (21–30 s recommended) — **no 10-minute allowance** |
| Profile image | 1:1, ≤**50 KB** |
| App / brand name | app 4–40 Latin or 2–20 Asian chars; brand 2–20 Latin or 1–10 Asian. **No emoji** |
| Ad description | 1–100 Latin / 1–50 Asian chars. **No emoji or special characters** |

A creative pipeline that assumes one spec will produce rejections the moment Pangle is added to an
existing ad group.

## Safe zones

**TikTok publishes no single pixel-exact safe zone.** The authoritative source is the downloadable
overlay template inside Ads Manager, and TikTok states the safe area **shrinks as the caption grows**
— there is no fixed box. Cross-sourced approximation at 1080×1920, directionally correct only:

| Edge | Approx. clearance | What sits there |
|---|---|---|
| Top | ~120–130 px | Logo, status bar, For You / Following tabs, search |
| Bottom | ~300–484 px | Caption, music ticker, account name, engagement rail |
| Right | ~120–140 px | Avatar, follow, like / comment / share |
| Left | ~44 px | Least constrained |

Do not hardcode these. Preview on real placements while the ad is paused — it is the only way to see
truncation and collisions (`tiktok-ops/00` step 8).

## Text and CTA

- Ad description: ~100 characters technically accepted; the UI truncates at about **4 lines** (~50–60
  chars) behind "See more". Write the load-bearing part first.
- Display name: 1–40 half-width characters.
- **Spark Ads copy is not editable** — it is pulled verbatim from the original organic post. If the
  caption is wrong, the creator has to change the post.
- `call_to_action` is a **preset enum, no custom text**. Pull the live list rather than hardcoding
  one; TikTok updates it without a changelog. `creative_cta_recommend_get` /
  `/creative/cta/recommend/` returns recommendations for the context.

## Identity — and the choice that gives away TikTok's main advantage

| `identity_type` | What it is | Consequence |
|---|---|---|
| `CUSTOMIZED_USER` | A display name + avatar, no real TikTok account | **No comments, no profile clicks, no organic halo** |
| `TT_USER` | A TikTok account linked to the ad account | Ad carries a real account; engagement accrues to it |
| `AUTH_CODE` | Identity from a creator's authorization code | Ad appears from the creator's real account; **engagement accrues to the creator's organic post** |
| `BC_AUTH_TT` | A TikTok account authorized at Business Center level | As above, scoped to the BC. Requires `identity_authorized_bc_id` |

**`CUSTOMIZED_USER` is the default an agent reaches for because it needs nothing set up, and it is
usually the wrong choice.** It strips the social proof, the comment section and the profile path that
make TikTok work. Use it deliberately — when you specifically do not want an organic surface — not
by default.

Endpoints: `/identity/get/` (list, filter by type), `/identity/info/`, `/identity/video/get/`,
`/identity/live/get/`, `/identity/music/authorization/`.

Remember from `02`: an organic account is **authorized, never owned**, and the owner can revoke from
the app at any moment. Your ads die with it.

## Spark Ads — mechanism and the failure mode that costs winners

Spark boosts an **existing organic post** instead of uploading a standalone creative. All
paid-driven engagement — views, comments, shares, likes, follows — accrues to the original post and
**persists after the campaign ends**. That is the actual argument for Spark, and it is structural
rather than a performance claim.

Two sourcing paths: your own account's post, or a creator's post via an authorization code.

**Creator authorization flow:** creator opens the video in the app → three-dot menu → **Ad settings**
→ **Generate** next to "Video code" → picks a duration → **Authorize** → **Save** → sends the code.
The advertiser applies it via `/tt_video/authorize/` (MCP: `tt_video_authorize_apply`) or pastes it
in Ads Manager.

Durations reported: **7, 30, 60, 365 days** (some sources also report a no-expiry option). Cross-
sourced, not confirmed on a directly fetched primary page.

Limits: Ads Manager can pull **up to 20 video codes at once**; an ad account supports **up to 10,000
Spark Ads**; a video must be **un-authorized before it can be deleted** from the organic account.

**When authorization expires mid-flight, delivery stops immediately. There is no grace period and no
auto-renewal.** The ad cannot be revived on the old code — you need a fresh one from the creator.

For an agent, this means **expiry dates are a first-class scheduling concern**, not metadata. Record
every Spark code's expiry in the project's `.notes/` at launch, and check it before every scale
decision. A silently expired code on a winning ad is one of the most commonly reported costly
mistakes in the field, and it looks exactly like a delivery collapse.

Practitioner mitigation: request the longest available window (60 or 365 days) for anything you
intend to scale.

`spark_ad_recommend_get` / `/spark_ad/recommend/` surfaces high-performing organic posts eligible for
boosting — worth calling before hand-picking.

Spark performance claims deserve care. The widely cited "Nielsen 780-campaign study" showing Spark
lift traces, on direct fetch, back to **TikTok's own help centre page** — a citation laundered into a
fake third-party study. Use the structural argument (engagement persists, comments live on a real
post), not the fabricated number.

## Upload via API

```
POST /file/video/ad/upload/   → video_id
POST /file/image/ad/upload/   → image_id
GET  /file/video/ad/info/     → poll until ready (up to 60 video_ids per call)
GET  /file/video/ad/suggestcover/ → cover candidates (preview URLs expire after 1 hour)
```

`upload_type`: `UPLOAD_BY_FILE` · `UPLOAD_BY_URL` (public http(s)) · `UPLOAD_BY_FILE_ID` ·
`UPLOAD_BY_VIDEO_ID`. Useful flags: `auto_fix_enabled`, `flaw_detect`, `auto_bind_enabled`.

**Video processing is asynchronous.** Error 40901 "transcoding in progress" means you did not wait,
not that something failed. Poll `/file/video/ad/info/` until ready before creating the ad.

**Media IDs are per-advertiser.** A `video_id` from one ad account is not usable in another — upload
per account. Duplicate names raise 40911; check with `/file/name/check/` first.

`video_fix_task_create` / `_get` repairs videos that fail spec checks.

## Creative automation

- **Smart Creative / ACO** — TikTok assembles combinations from your assets. Turn it off when you
  need to read which creative won, because attribution across auto-generated combinations is what
  you lose.
- **Automatic Enhancements** (`creative_auto_enhancement_strategy_list`, ad level) — TikTok's Symphony
  AIGC rewrites of the asset you uploaded: translate and dub into 50+ languages, swap in currently
  trending music, upscale video or image quality, resize to full screen. Availability depends on
  objective, promotion type and placements. **Decide explicitly.** Two reasons to leave it off: the
  ad that serves is no longer the ad you approved, which matters for a regulated vertical where
  wording was signed off; and a music swap can pull a track that is not licensed for every placement.
  Reasons to leave it on: you are scaling one proven asset across languages and do not need
  per-variant attribution.
- `creative_smart_text_get` — AI ad text generation.
- `creative_portfolio_*` — creative portfolios for organised asset management.
- `creative_ads_preview_create` — generate a preview. **Use it before activation, always.**
- **Creative Center** (`ads.tiktok.com/business/creativecenter`) — Top Ads library, trends, keyword
  and creative insights. **UI-only, no API**, roughly a 6-month historical window, with regional
  gaps. A "check trends" step needs a human or accepts scraping risk; do not promise it as automated.

## Creative fatigue

TikTok exposes a dedicated **creative fatigue endpoint** returning a `fatigue_index` — but it is
**allowlist-only, gated behind a TikTok rep**. Most integrations must compute fatigue heuristically
from frequency plus CTR decay instead. There is also a creative-fatigue **webhook** entity
(`tiktok-ops/06`).

Practitioners report TikTok's creative decay in **days rather than weeks**, with 3–5 creatives per ad
group refreshed every 7–10 days. That is field consensus, not a measured platform constant — a
Meta-tuned refresh schedule will under-refresh here, but derive your cadence from your own frequency
and CTR curves rather than from the number.

## Music

TikTok's **Commercial Music Library** covers standard placements. It does **not cover Pangle / Ad
Network placements** — carousel and other creatives running on off-platform inventory need separately
licensed or original audio even when CML would be fine on TikTok itself. Using a non-commercial track
is a rejection and a rights exposure, not a grey area.

`file_music_upload`, `file_music_get`, `identity_music_authorization_get`.

## Rejections that are TikTok-specific

These pass on Meta and fail here:

- **Missing or muffled audio.** TikTok requires audio as a policy matter, independent of
  licensing. Meta's silent-autoplay design makes this a blind spot for Meta buyers, and it is the
  single most common cause of a straight port failing review.
- Letterboxed or pillarboxed 16:9 repurposed from another platform — black bars read as low quality.
- **Another platform's watermark** (a TikTok export with the TikTok watermark used as a Meta-style
  asset, or vice versa).
- Low-resolution, pixelated or heavily compressed footage.
- Static images presented as video.
- Fake UI elements — simulated comments, notifications, buttons or player chrome.
- Before/after imagery and body-image framing (`08`).

**Porting a Meta creative to TikTok is not a crop.** Re-cut to 9:16, add clean audio, re-shoot the
first two seconds for a TikTok hook, and remove any platform-native chrome.
