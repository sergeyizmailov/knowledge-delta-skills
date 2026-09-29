# Instagram Placements & Ad Creatives

Reviewed 2026-07-22; Explore removal verified 2026-09-25.

**Naming**: "Automatic placements"→**Advantage+ placements** (ad-set level). "Automatic advanced matching/dynamic creative enhancements"→**Advantage+ creative** (ad level). "ASC"→**Advantage+ sales** (early 2025). ODAX is the only objective set now (Awareness/Traffic/Engagement/Leads/App promotion/Sales) — sources naming "Conversions"/"Reach"/"Video views"/"Catalog sales" describe pre-ODAX UI. Placement UI groups: Feeds / Stories and Reels / In-stream ads for videos and Reels / Search results / Messages / Apps and sites.

---

## 1. Where placements are selected

Ad set → Placements. Default **Advantage+ placements**; **Manual** exposes platform/placement checkboxes + device targeting. Meta recommends **6+ placements** when going manual so delivery isn't starved [Meta guidance via Topkee 2025]. Results per placement: Breakdown → Delivery → Placement.

Instagram placements in Manual mode:

| UI group | Instagram placements |
|---|---|
| Feeds | Instagram feed, profile feed, Explore home (Explore feed removed in v26.0) |
| Stories and Reels | Stories, Reels |
| In-stream ads for videos/Reels | Ads on Instagram Reels (overlay format) |
| Search results | Instagram search results |

## 2. Instagram placements in detail

- **Feed**: classic in-feed, most attention-dense and most competitive; supports image/video/carousel/collection. Dropped to **~26%** of IG ad impressions, behind Reels (~33%) and Stories [Tinuiti via Shopify 2026] — no longer the default volume placement.
- **Stories**: full-screen 9:16, ephemeral, land in the first second. Image auto-displays ~5–7s; video >60s auto-segments; native carousel = 3 cards max/unit; collection supported. More impressions than Feed. Only placement family (with Reels) where sound is a realistic expectation — design for sound-on AND captions for sound-off.
- **Reels**: full-screen 9:16, fastest-growing at **~33%** of IG ad impressions, all-time high. Native look (trending audio, fast cuts, UGC) outperforms polished TV-style. Boosted-Reels-as-ads restrictions [Strike Social]: no Reels published before 2021-10-15; no licensed music (original audio or Meta Sound Collection only); no face/camera effects; no GIFs; no product tags. Max duration 15 min (spec); real-world 5–30s.
- **"Ads on Instagram Reels"** (in-stream/overlay) ≠ "Instagram Reels" — appears as a banner/post-loop overlay on top of an existing organic Reel, not a standalone Reel; smaller, interruptive, different creative rules.
- **Explore (feed)**: removed as a placement in Marketing API v26.0 [official, 2026-09-25, developers.facebook.com/documentation/ads-commerce/marketing-api/marketing-api-changelog/version26.0]. Old specs/ad sets listing it need updating.
- **Explore home**: ad appears directly in the Explore grid before any tap (launched Oct 2022, opened via Marketing API Nov 2022) — still listed in v26.0. Square 1:1, must read at thumbnail size.
- **Profile feed**: ads inserted into a public profile's feed for non-followers (launched Oct 2022). Lower-intent, cheaper impressions, wider ratio range than Feed.
- **Search results**: appears in results list after a search-post tap (announced 2023); small/growing; image+carousel; no headline field in some configs [uncertain: spec coverage thin].

Each placement has its own format/dimension/truncation rules and cost dynamics; Audience Network/rewarded-video are the placements prone to accidental clicks/bots/forced views — Instagram placements themselves are comparatively clean.

## 3. Advantage+ placements vs manual

**Default (Advantage+)**: Meta distributes budget to eligible placements by historical data. Rule of thumb: for purchase/conversion goals leave it ON — the algorithm adjusts away from placements whose clicks don't convert, so weak-placement clicks don't matter [Jon Loomer]. Removing "low-performing" placements usually raises costs — cheap placements (e.g. right column) assist conversions without direct clicks. Meta's illustrative math [Meta Help Center via AdNabu]: with $27 and 11 impression opportunities at different costs/result ($3 FB/$5 IG/$1 AN), using all placements beats cherry-picking the "best."

**Override to Manual when**: (1) Traffic/link-click/LPV optimization — inspect Audience Network separately for click quality, exclude only on account-data evidence or brand-safety need, never infer fraud from placement alone; (2) ThruPlay/video-view optimization — consider removing AN rewarded video (forced views inflate metrics); (3) Reach with frequency caps — algorithm chases cheapest placements, force Feeds if action matters (costs rise, accept it); (4) creative-format constraints — 9:16-only assets should limit to Stories/Reels rather than auto-crop from landscape; prefer per-placement asset customization over restricting placements; (5) placement-level testing (e.g. Reels-only ad sets for clean creative data); (6) brand-safety/compliance in regulated verticals. **Do NOT remove placements just because they show few results** — remove only placements producing low-quality versions of the exact optimized event.

Gotchas: not all objectives support all placements (Messages only for sponsored-message campaigns); Advantage+ sales historically locked placement control, 2025 restored some — expect fewer manual options inside Advantage+ campaign types; placement selection lives at **ad set** level only (can't vary per ad); duplicated ad sets carry old placement choices — verify after duplicating.

**Placement exclusions removal (in-product notice from ~20.08.2026, practitioner-confirmed 24.09.2026 — Loomer, ppc.land, Social Samosa, mgrowtech; NO formal Meta announcement, NO dated rollout plan, Help Center still describes the old UI):** ad sets lose the ability to exclude individual placements, platforms, devices, and operating systems. Replacement levers: **value rules** (bid multipliers +1000%/−90% — suppression, never true exclusion; only 7 eligible placements) and **account-level Placement Controls** (Advertising Settings → Account Controls). Performance-driven exclusions are arguable with data; **brand-suitability / compliance exclusions have no automated replacement** — escalate contractual/regulatory ones to the Meta rep in writing before the field disappears. Manual-checkbox guidance elsewhere in this file (§1, §3) is pre-removal — verify live per account before relying on it. Field 2026-09-29 (operator's CF1 account): Manual placements with individual placements unticked (Threads feed, Messenger Stories, WhatsApp Status, Apps and sites) still worked in the UI, next to an "Allow limited spending to excluded placements" checkbox (lets Meta spend up to ~5% per excluded placement — secondary source, unverified), so the removal is progressive/account-dependent, not universal. API behaviour of `publisher_platforms`/position edits after the removal: unverified.

## 4. Creative specs per placement

Primary refs: Strike Social (2026-05) and Sprout Social (2025-08) mirrors of Meta's spec sheet; discrepancies flagged.

Ratio cheat sheet: **1:1** — Feed safe default, Explore home grid, carousel cards. **4:5 (1080×1350)** — recommended for Feed. **9:16 (1080×1920)** — Stories/Reels. **1.91:1** — supported in Feed/profile feed but weak, avoid IG-first. Design **4:5 + 9:16** per concept; use per-placement asset customization rather than auto-crop.

### Image ads

| Placement | Ratio | Min. resolution | Max file | Primary text | Headline |
|---|---|---|---|---|---|
| Feed | 1:1 (4:5–1.91:1 ok) | 1080×1080 (Sprout: 1440×1440 rec.) | 30 MB | 125 ch | 40 ch |
| Profile feed | 1:1 (1.91:1–4:5) | 1080×1080 | 30 MB | 125 ch | 40 ch |
| Stories | 9:16 | 1080×1920 (Sprout: 1440×2560) | 30 MB | 125 ch | — |
| Reels | 9:16 | 1440×2560 rec. | 30 MB | **72 ch** | — |
| Explore home | 1:1 | 1080×1080 | 30 MB | 125 ch | 40 ch |
| Search results | Explore-style [uncertain] | 1080×1080 | 30 MB | 125 ch | — |

File types JPG/PNG, min width 500px, ratio tolerance ~1–3%, max 30 hashtags.

### Video ads

| Placement | Ratio | Min. resolution | Duration | Max file |
|---|---|---|---|---|
| Feed | 4:5 | 1080×1080 (Sprout: 1440×1880) | 1s–60min | 4 GB |
| Profile feed | 4:5 (1.91:1–9:16) | 1080×1080 | 1s–60min | 4 GB |
| Stories | 9:16 | 1080×1080 min | 1s–60min (15s+ segments) | 4 GB |
| Reels | 9:16 | 500×888 min | up to 15min (spec) — target 5–30s | 4 GB |

MP4/MOV (GIF ok in Feed/Stories); codec H.264, square pixels, fixed frame rate, progressive scan, AAC stereo 128kbps+. Design for sound-off comprehension; test whether audio materially helps the outcome.

**Safe zones**: Stories — clear top 14% (~250px) and bottom 20% (~340px) of 1080×1920 (profile icon/swipe-up/message bar render there). Reels — top ~14% (250px), bottom up to 35% (~340–670px, UI-version dependent), ~6% each side (username/caption up to 4 lines/like-comment-share-save/audio attribution overlay bottom+right); 350px is the practical floor, burned-in captions below it get covered. Feed image ads: keep ~13% right/10% bottom clear. Ads Manager's yellow safe-zone overlay in preview — check every placement before publishing.

## 5. Formats

Single image — fastest, strong for retargeting/offers, works everywhere. Single video — best for Reels/Stories/prospecting, needs hook discipline (§7). Carousel — 2–10 cards, 1:1 (4:5 in Feed per Sprout), 30MB image/4GB video per card, Stories carousel video ≤15s/card; each card own headline (40ch)+link; best for multi-product/feature breakdowns. Collection — cover image/video + catalog grid opening an Instant Experience (required); cover 1.91:1–1:1 (Feed/Stories), 9:16 cover with 1:1 product images for Reels; commerce/catalog accounts only. **Flexible ads** (replaced most of Dynamic Creative 2024–25) — up to 10 images/videos in one ad, Meta assembles per-user variations; use for variation testing without DCO overhead.

## 5.1 Catalog creative pre-launch check

- **Right catalog selected** — accounts often hold more than one; a spec pointing at the wrong
  `catalog_id` builds real, deliverable ads against the wrong inventory silently.
- **One product set per creative** — sharing a set across creatives blocks per-creative product
  control and per-card ROAS (`content_id`) attribution.
- **No unintended carousel** — a single-card spec (`force_single_link` + matching
  `format_option`) collapses correctly; verify the built creative renders as one card, not a
  carousel, when that was the intent.
- **White vs target products in separate sets** — a cover/white product set and the real offer's
  product set must not share items, or the review-layer split has nothing to split
  (`meta-grey-ops/07`).

## 6. Advantage+ creative enhancements

Ad level → "Advantage+ creative" → Edit. Defaults/account-level controls vary by feature/rollout — inspect every ad, preview every placement; don't assume a universal on/off switch.

**AI-labeled (generative, highest brand risk)**: Text improvements/generation (rewrites primary text/headline/description per placement — disable when exact wording/disclosures/isolated testing matter). Expand image (generative fill for 9:16 — test, warps edges/logos, or upload true 9:16). Generate background (catalog — test per product, avoid for premium brands). Image/3D animation (Ken Burns/parallax — disable on composed product photography, crops edges as it zooms). Enhance CTA (test). Add overlays (auto text overlay from headline — usually ugly, "looks pretty awful" per Loomer, test rarely).

**Standard (rule-based)**: Visual touch-ups (low risk, disable only under strict color governance). Music (adds Meta library track to silent Stories/Reels — preview every placement, disable for regulated/governed creative or supply approved audio). Relevant comments (social proof — enable, monitor quality). Adapt to placement/Dynamic media/description (catalog — enable). Site links (up to 4 extra links under CTA — use when useful, disable when they fragment a single conversion path, validate with a controlled test). Dynamic overlays/Info labels (catalog price badges — enable only with accurate pricing data).

Bulk edit exposes only some toggles. API: Marketing API v22.0 (Jan 2025) deprecated the single `enable_standard_enhancements` field — per-feature flags now required (`text_optimization_enable`, `enhance_cta_enable`, etc.) via `creative_features_spec`. Meta claims ~4% lower cost per result on average from enhancements [Meta-reported, directional]. Failure case (2025): True Classic ran unintended AI enhancements — Meta generated images of a grandma holding a product the brand doesn't sell [Ads Uploader]. Enhancements modify creative mid-flight — can't isolate variant performance while on; standardize enhancement state across test/control.

## 7. Copy limits

| Field | Recommended visible | Hard limit |
|---|---|---|
| Primary text | 50–125 ch | ~2,200 stored (truncated behind "…more" after ~125 most placements; **72 ch on Reels**) |
| Headline | 27–40 ch | 40 UI practical / 255 technical [sources conflict; plan for 40] |
| Description | 20–30 ch | 30 practical / 125 technical [sources conflict; plan for 30] |
| Hashtags | — | 30 max |
| Carousel card headline | — | 40 ch/card |

Front-load value in the first ~125 characters. Don't repeat headline in description; description doesn't show on all placements — never put critical info there. Text-improvements enhancement can reorder copy (§6) — disable if order matters. The old 20%-text-on-image rule is dead; low text still correlates with cheaper delivery. Seasonal: explicit problem-solution copy beat product-description copy by 28% CTR in December campaigns [WordStream 2025].

## 8. Reels hooks & UGC — evidence status

Hook-archetype and UGC-lift figures are Meta-blog/vendor marketing quotes — priors, not benchmarks. Durable facts only: Reels truncates primary text at 72 chars (§7); audio-on lifts are Meta-reported, not independent.

## 9. Creatives per ad set

Treat `≤6` active and the `3–5` practitioner range as starting heuristics, not hard limits — Meta recommends limiting active ads/ad set so delivery can allocate enough impressions, but newer automated formats support more combinations. Learning status is evaluated at **ad-set level**, not per ad — don't multiply the legacy `50 events` heuristic by ad count, and the former `ads ≤ weekly budget ÷ (CPA×50) × 7` formula is dimensionally incorrect. Select creative count from budget, audience size, concept diversity, and the question being tested; reduce variants that get too little delivery to evaluate. Testing frameworks: 3-2-2 method (3 audiences × 2 creatives × 2 copy = 12 variants) only with budget to match; Meta's built-in Creative testing/A-B tool forces even budget splits for clean reads. **Diversification > volume**: near-duplicate assets add little info — vary angle/persona/offer/format, not just captions; no documented algorithmic penalty for volume. Advantage+ sales/Flexible ads tolerate higher variation counts — system assembles combinations internally without the same per-ad learning penalty. Refresh on account-relative fatigue evidence (declining attention/efficiency at comparable delivery, rising frequency, control-vs-challenger comparison) — calendar cadence and frequency thresholds are heuristics, not universal limits.

## 10. Common mistakes

1. One 1:1 asset auto-cropped/letterboxed into Reels — white bars flag repurposed creative; upload native 9:16.
2. Burned-in captions in bottom 350px of Reels — hidden behind UI chrome.
3. Leaving Music enhancement on — random library tracks on brand creative.
4. Leaving Text improvements on during creative tests — invalidates attribution of what worked.
5. Removing placements because "they don't convert" while optimizing for traffic — usually should remove Audience Network only, and only for traffic objectives.
6. Restricting placements without a format/policy/quality/experimental reason — just reduces auction opportunities.
7. Still sending the Explore feed position in v26+ specs — removed in v26.0; only Explore home remains.
8. Ignoring per-placement previews — the yellow safe-zone overlay exists precisely to catch §2/§4 problems.
9. Assuming Ads Manager > Preview shows what users saw — preview shows the unenhanced original; use Inspect per placement for enhancement-applied previews.
10. Counting on >125 characters of primary text being read — write for truncation.

---

## Sources

1. jonloomer.com/a-guide-to-meta-ads-placements — placement inventory, Advantage+ vs manual rules (practitioner, 2026-07-22).
2. sproutsocial.com/insights/instagram-ad-sizes — per-placement specs/safe zones/char limits (practitioner, 2025-08-22).
3. strikesocial.com/blog/instagram-ad-specs — full spec sheet incl. Explore home/profile feed/Reels restrictions/safe zones (practitioner, 2026-05).
4. socialmediatoday.com — Meta's Reels hook types, +13% incremental conversions from audio, Andromeda stats (practitioner reporting official Meta blog, 2026-07-22).
5. adsuploader.com/blog/advantage-plus-creative-enhancements — enhancement matrix, API v22.0 deprecation, True Classic case (practitioner, 2026-06).
6. hyperfx.ai — per-toggle disable paths/override levels (practitioner, 2026-05).
7. withblip.com — ≤6 ads/ad set rule, learning-phase budget math (practitioner, 2026-04).
8. blog.adnabu.com — Advantage+ placement budget-efficiency example, cites Meta Help Center (practitioner, 2025-07).
9. shopify.com/blog/instagram-ads — placement impression shares (Reels 33%/Feed 26%) via Tinuiti (benchmark, 2026-07).
10–11. digiday.com, searchenginejournal.com — Explore home + profile feed launch, Oct/Nov 2022 (practitioner/news).
12–13. billo.app — creator Reels 38% CTR (Zebracat 2025), UGC 2× CTR, AppsFlyer 70–80% creative-share-of-performance (benchmark, 2026).
14. paceads.com — WordStream/LocaliQ 2025 medians (benchmark aggregator, 2026-07-22).
15–17. digitalmarketinginstitute.com, ugcera.com, getkoro.app — UGC CTR/CVR/CPA stats, methodology practitioner/vendor (2025-08 to 2026-02).
18. screensnap.pro — Reels safe zone detail (practitioner, 2026-04).
19. metalla.digital — creative testing phases, CTR healthy range (practitioner, 2025-07).
20. admakeai.com — Advantage+ naming, ASC rename Q1 2025 (practitioner).

## Gaps

- Meta's official Ads Guide not fetchable (HTTP 400/JS-gated) — specs sourced via Strike/Sprout mirrors; conflicts flagged inline.
- Instagram search results specs thin across all secondary sources — ratio/field support [uncertain].
- "89% higher engagement from first-3-second hooks" is a secondary citation of Meta's 2025 Creative Best Practices report — primary not retrieved.
- Global account-level off-switch for Advantage+ creative enhancements: sources conflict (HyperFX says Business Settings sets defaults; mbadv.agency says per-ad only) — verify live.
- Safe-zone pixel values vary slightly by source/UI version; Meta publishes percentages, not hard pixels.
- UGC performance stats (4× CTR, 50% lower CPC) trace to pre-2024 aggregate studies recirculated by vendors — no rigorous 2025–2026 Meta-published benchmark found.
