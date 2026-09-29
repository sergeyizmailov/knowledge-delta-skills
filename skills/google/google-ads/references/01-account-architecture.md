# 01 — Account & campaign architecture

Reviewed 2026-08-27. UI labels, limits, and sunset dates are volatile — verify live before an
irreversible action. 🔺 = fast-moving, check first.

## Campaign type inventory (2026-08)

| Type | Status | Notes |
|---|---|---|
| Search | Primary | Being absorbed into AI Max (see below). |
| Performance Max | Primary | One budget across Search/Display/YouTube/Gmail/Discover/Maps/Shopping. **Cannot run App-install.** |
| Demand Gen | Active | Replaced Discovery (sunset Mar 2024) and absorbed Video Action Campaigns (creation blocked Mar 2025, auto-upgrade done Q2 2025). YouTube in-stream/Shorts/in-feed, Discover, Gmail, GDN. |
| Standard Shopping | Alive, marginalized | Since 2024-10-17 competes with PMax on **Ad Rank**, not campaign priority. |
| Video | Active | Drive conversions · Video views · Video reach (efficient / non-skippable) · Audio reach. |
| App | Active | ACi (installs), ACe (engagement), pre-registration (Android). Cap **100 ad groups/campaign** (same for Local; standard Search/Display allow 20,000) [official: answer/6372658]. |
| Local | Narrow | Store visits across Maps/Search/Display/YouTube. |
| Local Services Ads | 🔺 Migrating into PMax | Becomes a PMax pay-per-lead subtype. Phase 1 = US home/storefront verticals from **Aug 2026**; broader US late 2026; non-US 2027. Manual bidding and per-vertical tCPA die; one campaign-level tCPA replaces them. Standalone LSA dashboard disappears. |
| Smart campaigns | Legacy | SMB onboarding only. Not where a managed account should live. |
| Display (standalone) | 🔺 Sunsetting into Demand Gen | Migration tool ~Jun 2026; new-campaign creation ends ~Jan 2027; auto-migration through 2027. GDN inventory persists — only the buying vehicle dies. |
| Discovery · Video Action | Dead | Mar 2024 / Q2 2025. |

**Naming trap:** "Search Max" is not a Google product. The official name is **AI Max for Search**.
Treat "Search Max" as a synonym only when parsing older posts; using it signals stale research.

## Pick the campaign type

Google's promotional default is PMax. That is not the operator default.

| Job | Default | Do not |
|---|---|---|
| US e-com catalog | Hybrid PMax + Standard Shopping. Always a dedicated exact-match brand Search campaign. Feed-only PMax when the goal is Shopping bias. | PMax as the only campaign. PMax below ~50 conv/month or ~$2k/month — use Standard Shopping. |
| Lead gen | Search first. PMax only after qualified-lead OCI exists; use New Customer Only, not Value. | PMax on form-fill. AI Max on B2B/lead-gen without a pre-migration search-term baseline. |
| High-consideration B2B | Search-led. PMax at most a 20–30% supplement. | PMax as the primary. |
| App installs | App campaigns (ACi / ACe). | PMax — it cannot run app-install. |
| Visual/discovery, need channel control | Demand Gen. | PMax when Search/Shopping must stay out. |

Do not run PMax with no conversion-quality signal (no enhanced conversions, no CRM, no OCI) — it
optimizes whatever proxy you fed it. PMax mechanics → `07`. Feed eligibility → `google-feed-ops`.

## AI Max for Search — the forced migration 🔺

Add-on suite on Search: keywordless search-term matching, AI text customization, final URL expansion.
Full date table, migration mechanics, surviving controls, and the Google-claims-vs-independent-data
ledger → `05-ai-max-and-ai-surfaces.md`. Do not conflate **+14%** (2025 beta) with **+7%** (2026 GA) —
different scopes, both Google-internal/unaudited. 2027-02: full DSA sunset/auto-upgrade; call-only
creation ended Feb 2026, ads stop serving Feb 2027 — provisional, Google moved it once.

## Structure doctrine

**SKAGs are niche, not dead.** Reserve for top-volume, top-revenue terms where ad-copy control still
pays. Default is **STAG** — 5–15 closely related keywords per ad group sharing intent and landing page.
Mechanical reason SKAGs declined: close-variant and broad-match expansion mean an exact keyword no
longer guarantees an exact query — the entire premise of SKAG relevance control.

"Hagakure" (radically consolidated, broad-match-led, signal-rich structure for Smart Bidding) is a
community-coined philosophy, **not a Google framework** — no official source uses the term.

### Consolidation math

Smart Bidding needs a conversion-volume floor. Practitioner threshold: **~30–50 conversions per
campaign per month** to reliably hold out of learning. Below it, learning re-triggers on every
budget or strategy change.

Portfolio heuristic: if **>20% of campaigns sit in learning**, budget is fragmented and leaking.

Budget floors below are unattributed practitioner numbers — starting points for sizing a test, never
targets: daily budget ≥ 10× target CPA during initial learning · DTC $300–500/day per ad group ·
competitive verticals break below ~$30–50/day.

The repeated rule: *10 campaigns at $10/day underperforms 2 campaigns at $50/day.* Fragmentation
dilutes both pacing and per-auction signal.

### When a campaign split is structurally forced

These are campaign-level settings, so any difference mandates a separate campaign: budget · bid
strategy type (unless a portfolio strategy) · geo · language · campaign type · conversion goals ·
customer-acquisition mode.

Vallaeys (Optmyzr): different ROAS/CPA targets → different PMax campaigns, since one PMax campaign
optimizes toward one target only. Also flags over-combining distinct locations into one campaign as
a common error.

## Campaign settings that silently ruin accounts

| Setting | Mechanics | Gotcha |
|---|---|---|
| **Search Partners** | Toggle under Networks. Survived Google's 2023–24 attempt to hide it. | Un-auditable at placement level for Search. Many practitioners disable by default and test deliberately. Parked-domain inventory was permanently removed 2026-02-10. |
| **Display Expansion on Search** | Spends "unused" Search budget on Display. | It fires exactly when you are least prepared to audit placements. Off by default for intent-sensitive verticals. |
| **Location: Presence / Presence-or-interest** | Default is **Presence or interest** — serves to people who merely *searched about* the location, from anywhere. Pure interest-only targeting was removed in 2023. | The single most common local-budget leak. Switch to **Presence** for anything locally fulfilled. |
| **Ad rotation** | Only "Optimize" and "Do not optimize" remain. "Rotate evenly" and "Optimize for conversions" are gone. | "Do not optimize" has a narrow legitimate use: gathering even data across new variants before letting the algorithm pick. |
| **Ad schedule** | Hard eligibility constraint — ads do not serve outside the window. | Under Smart Bidding, day-part **bid adjustments** are ignored. Justify dayparting by business constraint (staffing, call coverage), never as bid shading. |
| **Device bid adjustments** | Under Smart Bidding only **-100%** works. | +20% mobile on top of tROAS does nothing. Reserve for full exclusions. |
| **Campaign vs account-default conversion goals** | Account-default enables **cross-campaign learning**. | Google's own guidance: overriding to campaign-specific goals *loses* that learning and can reduce performance. Override only with a stated reason. |
| **New Customer Acquisition** | Goals → Customer acquisition. "Bid higher for new" (blend) vs "new customers only" (hard exclusion). Needs an audience of **≥1,000 active members**. | "New customers only" is exclusionary, not additive — Google recommends a separate campaign to still reach existing customers. PMax for Store Goals supports *only* this mode. |
| **Enhanced CPC** | Retired for Search and Display week of **2025-03-24**. | Unmigrated campaigns silently became plain Manual CPC. Audit legacy accounts for orphaned Manual CPC. |
| **Tracking template / URL options** | Final URL kept separate from tracking template and custom parameters. | `{feeditemid}` is deprecated for asset-based extensions — replace with `{extensionid}` or attribution on asset clicks silently breaks. |
| **IP exclusions** | Now **account level**, applying across Search/Shopping/Display/Demand Gen/PMax/Discover/YouTube. Cannot be removed from inside a campaign. 🔺 ~500 IP cap cited in secondary sources, unconfirmed officially. | Exclusions always beat inclusions. An account-level exclusion cannot be overridden by any campaign targeting. |

## MCC hierarchy

- Depth: sources conflict between "6 levels total" and "5 managers stacked above an account" — 🔺
  verify in a live MCC before designing deep sub-MCC structures.
- A manager account cannot be directly managed by more than one other manager (no diamond hierarchies).
- A client account cannot link to more than one manager within the same hierarchy; max 5 managers total.
- A manager can link up to **85,000** non-manager accounts (active + inactive + canceled all count).
- **Shared negative lists** (MCC Shared Library) propagate to every linked account. Cap **20 lists per
  account, 5,000 keywords per list**.
- **Account-level negative keywords** are a separate mechanism: apply to Search, PMax, App, Shopping,
  Smart, Local. Cap **1,000 per account**. They do **not** match close variants — account-negative
  "flowers" will not block "red flowers". A separate "Exclude content keywords" tool (also 1,000)
  covers YouTube/Display content targeting under Suitability Settings.
- **Cross-account conversion tracking** routes through the manager. Conversion actions cannot be
  shared directly between two client accounts.
- **Asset hierarchy**: a more granular asset blocks a higher-level one. A single ad-group callout
  suppresses the entire account-level callout set for that ad group.

## Campaign arbitration — the exact rule

Since **2024-10-17** (rolled out through Jan 2025), PMax and Standard Shopping compete on **Ad Rank**,
not the old PMax "uber-priority". Practitioner-observed (ProductHero, 700+ accounts); never confirmed
in Google's own words.

Official account-wide rule:

1. Highest **Ad Rank** wins when multiple campaign types are eligible for the same impression.
2. **Exception — exact match beats Ad Rank.** A Search keyword that exactly matches (or is
   spell-corrected to) the query is preferred over PMax regardless of Ad Rank.
3. With no exact-match keyword, PMax competes with Search broad/phrase purely on Ad Rank. Google
   documents **PMax search themes as the same tier as phrase/broad**, below exact.
4. **The leak:** PMax still wins branded exact-match traffic when the Search campaign is
   budget-constrained or too narrowly targeted to serve. Practitioners report this as real.
5. **Shopping campaign priority (Low/Med/High)** still arbitrates *between Standard Shopping
   campaigns* on the same product — priority outranks bid there. Irrelevant to Shopping-vs-PMax.

### Brand cannibalization

Brand queries convert 3–10× non-brand in most e-commerce categories, so PMax's value scoring always
favors them. Cited estimate: unrestrained PMax absorbs **10–30%** of what should be non-brand budget.

Mitigation: account-level negative list for your own brand terms (protecting a dedicated exact-match
Brand Search campaign) + campaign-level brand exclusion lists inside PMax for competitor terms.

**Measurement trap — state this whenever recommending the exclusion:** pulling brand out of PMax makes
PMax's own ROAS/CPA look worse (loses its cheapest converting queries). If judged on PMax's isolated
ROAS rather than blended account performance, the correct change gets reverted for the wrong reason.

### PMax negative keywords

Self-service since **Dec 2024**; cap **100 → 10,000** (**Mar 2025**); apply to **Search and Shopping
inventory only** — no Display/YouTube/Discover suppression. **No asset-group-level negatives exist.**

## Standard Shopping — bidding and the PMax cutover

Bid options (2026-08): Manual CPC · Enhanced CPC (retired for Search/Display 2025-03, `02` — the
Shopping surface is what kept it) · Maximize conversion value, no target · Maximize conversion value
**with a tROAS target**. No Maximize Clicks, no tCPA on Standard Shopping.

- **Bidding is campaign-level.** Per-segment economics come from listing-group segmentation on
  `custom_label` tiers, not item bids — feed-ops owns the label schema (`google-feed-ops/01`) and the
  priority ladder (`google-feed-ops/03`).
- **tROAS eligibility needs conversion history** — commonly cited at ≥15 conversions/30 days per
  campaign [uncertain: Google publishes no hard number; check the bid-strategy dropdown in-account].
  Below the floor, Maximize conversion value without a target is the only value-bidding option.
- Under the 2026-08-17 budget-limited enforcement (`02`), a "Limited by budget" tROAS Shopping
  campaign drives toward the literal target — audit the target before judging the account.

**Choose Standard over PMax when any of these hold:**

- You need query-level visibility or negative-keyword control (PMax offers neither; its negatives
  cover Search/Shopping inventory only, `03`).
- Feed quality is weak (GTIN gaps, price/availability mismatches) — PMax amplifies feed problems
  across more surfaces.
- Conversion volume sits below the PMax floor (~50 conv/month or ~$2k/month, table above).
- Brand protection needs the exact-match arbitrage: dedicated brand campaign + account-level
  negatives + PMax brand exclusions (above).

**Choose PMax when** the feed is clean, value tracking is complete, and the goal is incremental
volume beyond Standard's reach. Hybrid (both live) is the US e-com default — the 2024-10-17 Ad Rank
arbitration governs, and Shopping campaign priority only arbitrates *between* Standard campaigns.

## Experiments

- Max **25 drafts** per account; a new draft fails to publish at the ceiling.
- Campaign experiments split traffic between original and draft over a defined range.
- PMax experiments: Google explicitly says **do not run multiple experiments simultaneously** — they
  interfere and degrade the read. Run sequentially, and minimize changes to the campaign under test.
- Validity layer (sizing, SRM, peeking, contamination) → `measurement-experimentation-ops`.

## PMax asset groups (no feed attached)

Specs live in `04-creative-and-assets.md` (RSA + PMax images/video) and
`07-pmax-demand-gen-audiences.md` (asset-group limits). Headlines are **3–15**, not 3–5; at least one
must be **≤15 chars**.

Treat asset-group count like ad-group count: too few dilutes relevance across a diverse catalog, too
many fragments the conversion volume each needs. **The 30–50 conversions/month floor does NOT apply per
asset group** — it's a campaign-level Smart Bidding benchmark; every asset group in a PMax campaign
shares one bid strategy, so there's no per-group target to gate. Structural caps: **100 asset
groups/campaign**, **1,000 listing groups/asset group** [official: answer/6372658 + Google Ads API
docs]. Per-group heuristics → `07`.

## Naming

Each level names only what is unique to it. The name must carry whatever the tracker splits on — the
mapping is not automatic → `tracker-ops` (multi-account case → `google-grey-ops`).
