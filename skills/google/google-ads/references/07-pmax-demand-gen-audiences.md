# 07 — Performance Max, Demand Gen, audiences

Reviewed 2026-08-27. AI Max itself → `05-ai-max-and-ai-surfaces.md`. Campaign-type picker (Search vs
PMax vs Shopping vs Demand Gen vs App) → `01-account-architecture.md`. Retail feed eligibility →
`google-feed-ops`.

## PMax anatomy and limits

`Campaign → Asset group(s) → (retail) Listing group filters → Audience signals → Final URL expansion`

| Element | Limit |
|---|---|
| Asset groups per campaign | **100** max, 1 min |
| Headlines | 3–15, ≤30 chars, **≥1 must be ≤15 chars**. Recommend 11+ |
| Long headlines | 1–5, ≤90. Recommend 2+ |
| Descriptions | 2–5, ≤90. Recommend 4+ |
| Business name | ≤25, must match domain/legal name, no promo text |
| Images | Horizontal 1.91:1 **and** Square 1:1 both required, 4+ each, ≤20 total; Vertical 4:5 optional (2+ recommended). ≤5MB, "center 80%" safe zone |
| Logos | Square 1:1 required (1–5, min 128×128); Horizontal 4:1 optional. Transparent backgrounds may render on white |
| Videos | 1–15 per orientation, must cover 16:9, 1:1, 9:16, each ≥10s |
| Account-level negatives | 1,000 (applies to PMax) |
| **Campaign-level negatives (PMax)** | **10,000** — raised from 100 during the Jan–Apr 2025 rollout |
| Search themes | **50 per asset group** — raised from 25, confirmed Aug 2025 |
| Content Suitability exclusions | 20,000 per bulk entry, **65,000 total per account** |

**Budget must be non-shared, `DAILY` period.** PMax rejects shared budgets.

### Where the settings live (2026 UI)

- Brand exclusions → campaign **Settings → Content → Brand exclusions** (or account brand list under Tools)
- Campaign negatives → **Settings → Content → Negative keywords**
- Search themes + audience signals → **Asset group** edit screen
- Final URL expansion + URL rules → **Settings → Final URL expansion**
- Channel performance → Campaigns → **Insights and reports → channel performance**
- Placement exclusions → **Tools → Content suitability → Advanced settings → Excluded placements**
- Customer lifecycle → **Settings → Goals → Customer acquisition**

### API quick reference

`AssetGroup` · `AssetGroupAsset` (`field_type`: HEADLINE, DESCRIPTION, LONG_HEADLINE,
MARKETING_IMAGE, SQUARE_MARKETING_IMAGE…) · `AssetGroupListingGroupFilter` (retail tree) ·
`AssetGroupSignal` · `campaign_search_term_insight` · `performance_max_placement_view` ·
`campaign.advertising_channel_type = 'PERFORMANCE_MAX'`.

Segmentation `segments.ad_network_type`, `segments.ad_using_product_data`, `segments.ad_using_video`
are **v23+ only**.

**In non-retail PMax, `AssetGroup` and its `AssetGroupAsset` rows must be created in the same bulk
mutate request.** See `10-api-and-automation.md`.

## Controls — what each actually does

**Brand exclusions** block Search *and* Shopping inside PMax for your brand, common misspellings, and
related subsidiary brands automatically. **Shopping can keep serving on excluded brand terms while
Search is blocked** — a granular toggle most operators miss. Google: "the most precise and
comprehensive tool" for brand-term control, more complete than negatives.

**Negative keywords.** Google: *"a highly restrictive control that can harm performance by preventing
the AI from finding valuable traffic."* Use for brand-safety essentials and clearly irrelevant terms
only; prefer brand exclusions for own brand. Avoid heavy application in first weeks post-launch —
Optmyzr measured over-application during the learning window as a performance drag.

**Search themes are not keywords.** Google states they "provide a broader signal" and ads still serve
"based on several factors" — Google serves beyond your themes and this is by design. Use broad terms
("running shoes", not "red running shoes size 10"), skip duplicates of what the site/feed already
teaches, add event-specific themes to speed seasonal ramp. The 2025 update added **Source and
usefulness columns** telling you whether a theme actually drove incremental traffic — in Optmyzr's
24,702-campaign study 71% of advertisers used search themes with "mixed or flat" results, largely
*because* that visibility did not exist.

**URL expansion** is **on by default**. It replaces your final URL with a page it judges more relevant
and generates matching assets. Three tiers of control, in order of preference:

1. **Exact URL exclusions** — individual non-commercial pages.
2. **Page feeds** — curated include/exclude lists via custom labels at asset-group level.
3. **URL-contains rules** — whole sections (`/blog`, `/careers`). Google warns these "can
   significantly limit the AI's ability to find relevant traffic". **Use last, not first.**

A 2024 in-campaign A/B reported **+9% conversions at similar CPA/ROAS** with expansion on.

**Audience signals are seed, not targeting.** Official: *"Performance Max may show ads to relevant
audiences outside of your signals."* Contrast with "audience segments" (hard targeting criteria
elsewhere). **Signals cannot restrict PMax delivery.** Confusing the two is a common, expensive error.

**Customer lifecycle goals** — five modes: New Customer Value (bid higher, still serves existing;
needs a purchase goal; works with tROAS/Max Conv Value) · High Value New Customer (PMax+Search only) ·
**New Customer Only** (excludes existing entirely; works with any bid strategy; right for lead gen and
strict acquisition budgets) · Re-engagement and High Value Re-engagement (PMax only).

"New customer" identified **only** via past online purchase conversions and/or an uploaded Customer
Match list labeled in the Conversions Summary Acquisition panel — no other ground truth. Store Goals
PMax supports **only** New Customer Only. Google's own testing: New Customer Value gives +9% ROAS,
+5% new-customer ratio.

**Gender targeting is still beta** as of the 2025 year-end recap; device and age are fully available.

**Store Goals PMax: do not add extra geo-targets** — Google auto-applies a dynamic radius per store
and layering manual geo on top is explicitly discouraged.

Search Partner exclusion lists can be sourced through **DoubleVerify, IAS, and Zefr** — a rare case of
third-party brand-safety verification wired into PMax.

## Reporting — what is exposed and what is hidden

**Channel performance report** breaks out Google Search, GDN, YouTube, Discover, Maps, Gmail, Search
partners with a status column (Eligible / Eligible (Limited) / Not eligible / Missing required assets),
issue-level diagnostics. **Hard limits:** no per-channel budget control, no per-store-location
conversion breakdown, no data before 2025-06-06.

**`campaign_search_term_insight`** — real, API-queryable through v25, now surfaced in the UI for all
PMax campaigns. Caveats from Frederick Vallaeys: **no cost data** (clicks/impressions/category only,
so no CPA per category — relevance triage only) · data only back to ~Mar 2023 · **high-volume terms
are sampled**, so long-tail and small-account data is unreliable.

**Asset-level metrics are attributed per instance served** — Google's own docs warn they "may not
directly match the corresponding metrics at the asset group level". Ratio metrics (CTR, CPC, ROAS) at
individual-asset level officially **"directional indicators only"**. Evaluate at asset-group/campaign
level. **Combinations report** shows top 6 text/image/video combinations per category.

Google's FAQ: PMax campaigns with **at least one video saw an average 12% conversion uplift**.

**Third-party transparency tooling:**

- **Mike Rhodes' PMax Script** (mikerhodes.com.au/scripts/pmax) — free, ~3,200 lines, pastes into a
  template Sheet. Surfaces spend-by-channel over time, a search-term categorizer (brand / close-to-brand
  / non-brand / blank with a direct link into the exclusions form), a 6-bucket product matrix (zombies,
  zero-conversion, meh, flukes, costly, profitable) across both PMax and Standard Shopping, placement
  lists with a min-spend threshold, asset-group and video performance **flagging user-uploaded vs
  Google-auto-generated**, and a change-history log. Tested on 6M+ product accounts. A companion MCC
  script exists for multi-account rollups. **This is the single highest-value free tool in the PMax
  stack.**
- **Optmyzr** — cross-channel reporting plus a Products-overlap report catching the same SKU running in
  both Standard Shopping and PMax.
- **smec / Mike Ryan** — the 3,000-campaign "State of Performance Max" analysis.

## Cannibalization

**The official priority rule** (applies to Search + PMax, explicitly **not** Shopping):

1. An **exact-match keyword identical to the search term** wins outright over PMax.
2. A PMax **search theme identical to the term** outranks a **non-identical phrase-match** keyword.
3. Below that, AI ad-group relevance decides between Search and PMax.
4. Ad Rank breaks ties.
5. **Shopping is exempt** and can serve alongside Search even when an exact-match keyword exists.

**Practical consequence: only an exact-match keyword for that exact term guarantees Search keeps the
query.** Phrase and broad get no guaranteed priority over PMax — the entire mechanism behind "PMax
steals my brand traffic even though I have a Search campaign": that campaign was running phrase/broad,
not tight exact.

Evidence: in Optmyzr's 24,702-campaign study, 51% of advertisers put >50% of budget into PMax; those
accounts showed a 652% ROAS headline with "mixed" CVR/CPA underneath — consistent with PMax harvesting
easy branded conversions rather than generating incremental ones.

🔺 A widely circulated 2026 article (ad-times.com) claiming PMax grew 22% → 38% of industry spend and
that 31 of 47 audited accounts showed PMax suppressing brand impression share **could not be
corroborated — its named quotes are from people not otherwise findable and it reads as AI-generated
SEO content. Do not cite it.**

### Measuring it properly

1. **Brand-exclusion holdout**: add brand exclusions to PMax for **≥4 weeks** while keeping a dedicated
   brand Search campaign live. Compare **total account** conversions/revenue/spend before vs during —
   **not the PMax line item**. If account totals hold, PMax was over-crediting demand it did not create.
2. **Geo or time holdout**: pause or cut PMax in a subset of regions, hold everything else constant.
3. **Native Experiments** for a structured split.
4. Track **organic branded clicks in Search Console** as a secondary signal — real incrementality loss
   shows up as organic brand clicks *not* recovering when PMax brand spend is cut.

Design validity → `measurement-experimentation-ops`.

## Launch and optimization

**Budget floor — official API guidance:** average daily budget **≥3× target CPA**. Below that, "slower
ramp-up or fewer conversions".

**Volume floor — practitioner consensus:** 30–50 conversions/month account-wide before PMax has enough
signal. Optmyzr's rule: **"30 conversions in 30 days"** before you judge or pause a campaign. One
source translates this to roughly a **$3,000/month** spend floor at typical CPAs.

**Ramp is 2–6 weeks**, shorter at high volume. During ramp: do not toggle target checkboxes, do not
restructure asset groups, do not add aggressive URL rules, go easy on new negatives.

**Sequencing:** start on **Maximize Conversions / Max Conversion Value with no target**, let it find
natural efficiency, then layer tROAS/tCPA once stable. A tight target from day one starves exploration.

**Asset group count:** no official threshold — Google publishes only structural caps (**100 asset
groups/campaign**, **1,000 listing groups/asset group**). The load-bearing signal is **conversions per
asset group**, not group count. 🔺 The common "start with 1–2, ~20 conversions/month each, merge under
5/month" heuristic traces to **one vendor blog (Dotidot, 2026-03-20)** recirculated by content farms —
not Optmyzr, Adalysis, Rhodes, Ani or smec, none of whom publish a per-asset-group number. Use it as a
rule of thumb, not settled guidance. The **30–50/month** figure is campaign-level Smart Bidding, not
per-group (`01`).

**Feed-only ("assetless") PMax** — zero uploaded text/image/video so the campaign leans on the
Merchant Center feed, biasing delivery toward Shopping surfaces over YouTube/Discover.

> **2026 caveat: feed-only does NOT guarantee zero Display/YouTube spend.** Since late 2023 Google
> auto-generates video and display creative directly from feed images and text even with no manual
> assets. Feed-only reduces, never eliminates, non-Shopping delivery.

Use **Standard Shopping instead** when you need zero tolerance for non-Shopping spend, under 50
conversions/month, lead gen without offline conversion tracking, new accounts under ~$2,000/month, or
granular per-product bid control.

## Failure modes

| Mode | Detection | Fix |
|---|---|---|
| Spend drifting to Display/YouTube | Channel report shows disproportionate share; stalled ROAS as spend migrates | Feed-only structure (with caveat), tighter URL rules, negatives on non-commercial patterns, video audit |
| Branded traffic inflation | `campaign_search_term_insight` categorized brand vs non-brand (Rhodes' script does this natively); compare to Search Console organic brand clicks | Brand exclusions + holdout test |
| Low-quality / MFA placements | Placement report — **officially labeled a brand-safety tool, not a performance-evaluation tool.** Do not judge ROI from it | **Account-level Content Suitability exclusions are the only placement-blocking mechanism confirmed to apply to PMax.** The placement report itself has no in-report exclusion action |
| Auto-generated video quality | Asset reporting "Added by" column marks Google AI | Upload ≥1 real 9:16 video per asset group. A single source claims a 25–40% gap vs manual video — unverified but directionally consistent with the SKU-mismatch problem in `04` |
| URL expansion to wrong pages | Final URL expansion assets report shows exactly which URLs were substituted, individually removable | Exact-URL exclusions first, broad rules last |
| Asset group starvation | Conversions/asset group under ~5–20/month | Merge groups |
| Over-restrictive exclusions | Compare pre/post | Optmyzr: only 58% saw flat-to-slightly-better results from exclusions — restrictive filters were frequently **net negative** |

## Demand Gen

**Lineage.** VAC: new creation blocked Apr 2025 → auto-upgrade began Jul 2025 → end-date extension past
2026-01-31 blocked from Dec 2025 → final forced migration Apr 2026. Originals retained as
Removed/Paused with history intact. Reported: accounts uploading **both video and image** assets saw
**+20% conversions at the same CPA** vs video-only.

**Display → Demand Gen** is a separate, newer migration: voluntary tool phased from Jun 2026, then
new Display creation only inside Demand Gen, then auto-migration. Migrated campaigns gain Discover,
Maps (beta), YouTube, Gmail on top of GDN, plus carousel and generative-image formats. **Similar
Audiences become Lookalike segments. Manual CPC, Viewable Impressions, and Pay-for-Conversions bidding
are discontinued in favor of Target CPC.** Originals retained 5 years; migrated campaigns are named
"[Original] #2" and **retain 42 days of history** to shorten re-learning.

**Surfaces:** YouTube (in-stream, in-feed, home, watch-next, search, **Shorts**), Discover, Gmail, GDN,
Maps (beta, needs a non-affiliated location extension).

**Channel controls sit at ad-group level**: "All Google Channels" (Google's recommendation) vs "Let me
choose". **YouTube Engagement campaigns run YouTube-only regardless of selection.**

**Learning phase:** ~50 conversion events or 3 conversion cycles, targeted within 2 weeks. Enabling
**view-through conversion optimization** speeds ramp, reduces fluctuation (cited).

**Lookalike segments:** historical tiers were narrow/balanced/broad ≈ **2.5% / 5% / 10%**. 🔺 **2026
change:** lookalike becomes a *suggestion* — the seed list is a signal to the model rather than a
strict targeting boundary, for **Demand Gen specifically** (not Video brand campaigns or DV360). The
**100-user minimum seed is no longer a hard requirement**. Seed with high-intent lists (recent
converters, off-platform brand engagers), not broad site visitors.

### The Demand Gen measurement trap

- **View-through conversions**: counted when any pixel is on-screen for any duration and a conversion
  follows within (typically) 24h, **with no click**. VTC bidding is supported **only on YouTube and
  Discover Feed** (video-only on Discover) and **does not support offline conversions, store visits, or
  OCI**.
- **Engaged-view conversions**: require ≥10s watched (or a completed bumper). Video only.
- Attribution hierarchy: **click > engaged-view > impression.**
- **"Conversions (Platform Comparable)"** is a reporting-only column that does **not** feed bidding. It
  gives full last-interaction credit including VTCs specifically so you can compare against Meta's
  last-click methodology. **Google's own caveat: never use it to compare Demand Gen against Search or
  PMax** — external platforms only, with matched audience/creative/attribution setups.

## Audiences

**Customer Match** — minimum **100 members**, added or updated within the trailing **540 days**
[official: support.google.com/google-ads/answer/7474166, 2026-08-27]. The **1,000 → 100** cut applied to
**Search** (other networks were already lower). 🔺 Google never announced it: the 2025-05-23 date comes
from trade press reporting a help-doc change spotted by practitioners (Navah Hopkins / Boris Beceric),
not from a Google changelog. Trust the current minimum, not the date.

Upload via UI, Google Ads Editor, or the API's `OfflineUserDataJobService`. 🔺 Sensitive-category
restrictions (health, financial hardship) exist but were not re-verified against a current 2026 policy
page — check before using Customer Match in a regulated vertical.

**Data Manager** — unified first-party ingestion layer: connect a source once, activate across
destinations. Objects: **data source** (BigQuery, HubSpot, file) → **connection** → **destination**
(Customer Match, Enhanced Conversions for Leads, offline conversion import). Own **Data Manager API**.
Where Google is steering OCI → `06`.

**Custom segments** (Display/Gmail/Demand Gen/Video — **not directly usable in PMax**, only via
audience signals): keyword/phrase interest · **URL-based** ("people who browse websites *similar to*
the URLs you enter" — explicitly **not** placement targeting on those URLs) · app-based.

> **The "competitor URL as a custom segment" trick is practitioner folklore.** Google's docs frame
> URL-based segments around your ideal customer's browsing, and no official documentation endorses or
> mentions feeding competitor domains. It may work as a proxy in-market audience; present it as
> unverified, never as documented.

Custom segments are not shareable between accounts, unavailable in manager accounts, and default
estimates assume US/English regardless of actual campaign geo.

**Standard segments** feeding PMax signals and Demand Gen targeting: in-market, affinity, detailed
demographics, life events, plus remarketing via the Google tag or linked GA4 audiences.
