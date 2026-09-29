# 05 — AI Max, AI Overviews, and the September 2026 forced migration

Reviewed 2026-09-03. **The most time-critical file in this skill.** Everything here is 🔺 volatile.

## What auto-converts and when

| Trigger | Migrates to | Window | Reprieve |
|---|---|---|---|
| Campaign-level Broad Match setting | AI Max search term matching | **Migrating now, 2026-09-01 → 09-30** [confirmed 2026-09-03: rollout is live, progressive across the month — a campaign untouched on Sep 2 may still convert on Sep 24] | None |
| Legacy Automatically Created Assets (ACA) | AI Max asset optimization | Same window, in progress | None |
| Dynamic Search Ads | AI Max | **Delayed to Feb 2027** [confirmed 2026-09-03] | Yes — 8-month extension announced 2026-06-11 by Ginny Marvin, attributed to advertiser feedback about Q4 planning risk. DSA creation was restored 2026-06-15, then removed again Jan 2027; automigration runs Feb 2027 for anything not voluntarily migrated |

Since **2026-08-03** Google blocks *creating* new campaign-level Broad Match or legacy ACA configs
across UI, Editor, API. Existing config survives until swept; no opt-back-in. Mechanics published Ads
Developer Blog 2026-08-12; advertisers emailed 2026-08-05. Brand inclusions/exclusions carry over
automatically.

**The only real opt-out was disabling campaign-level Broad Match / ACA *before* September 1** — that
window has closed as of this review. Google does not auto-migrate a campaign that no longer uses the
legacy feature; for campaigns still on it, the sweep is now running. **There is no rollback once
auto-migration executes.**

## Controls that survive — the actual steering wheel

The campaign-level AI Max switch is not the lever. These are:

- **Search term matching toggle at ad-group level.** Campaign AI Max must be on for the control to
  exist, but each ad group can opt back out, reverting to strict keyword + match-type behavior.
  Path: Campaigns → Ad groups → select → Search term matching → off. **This is the real control.**
- **Brand controls** — inclusions at campaign *and* ad-group level; exclusions campaign-level only.
- **Locations of interest** — ad-group level, governs geographic-intent keywordless matching.
- **URL expansion exclusion lists** — page-level, to stop AI Max routing clicks to help/FAQ/blog/
  deprecated pages.
- **Text guidelines / term exclusions** on auto-generated assets — brand voice, pricing, promo, legal.
- **Negative keywords remain fully enforced** — the one legacy control practitioners repeatedly
  confirm still works as before. (Caveat in `03-keywords-and-negatives.md`: some report URL expansion
  overriding a negative it judges relevant. Audit search terms more often than on standard Search.)
- **New URL parameter for search-term visibility** — term-level attribution across all match types,
  positioned as the replacement for the match-type reporting AI Max removes.

## The evidence — Google's claims vs independent data

**Google's own uplift figures have moved four times in 14 months and are never reconciled:**

| When | Claim |
|---|---|
| May 2025 (beta) | +14% |
| Apr 2026 (GA) | +7% for the full feature suite — retail explicitly excluded |
| May 2026 | +27% more conversions for exact/phrase-heavy campaigns |
| Jul 2026 (earnings call) | +15% average "at similar ROAS" |

**Independent datasets:**

| Source | Method | Result |
|---|---|---|
| **smec / Mike Ryan** | 383M impressions, EMEA e-commerce Search, Jan 2025 – Jul 2026 | By Jul 2026 only ~71% of exact-match impressions stayed truly exact — **~29% broadened by AI Max**, and two-thirds of that expansion happened in the final four months. The leak accelerates. Ryan: search term matching is *"basically broad match."* Separate smec study, 250+ retail campaigns (Nov 2025): AI Max conversions carried **~35% lower ROAS**. |
| **HBT Digital** | 14-month controlled A/B, one account, US home services, same budget and goals | Manual: 12,121 terms matched, 1,579 clicks, $10,299 spend, 36 conv, **$286 CPA**, 2.3% CVR. AI Max: 993 terms, 30 clicks, $158 spend, 0.5 conv, **$316 CPA**, 1.7% CVR. **964 of AI Max's 993 matched terms produced zero clicks.** Irrelevant matches included "build a house online for fun", "Etsy home plans", "interior AI". |
| **Monks** | ~30,000 AI Max-matched search terms audited | **99% had zero conversions.** |
| **Lunio** | 414M retail ad clicks | Invalid traffic on AI Max-enabled retail search rose **2.46% (Q4 2025) → 5.28% (Q2 2026)**. Modeled cost at a $10M/yr retail advertiser: ~$500K/yr wasted, ~$1.25M lost revenue opportunity. Separately, in one AI Max campaign a **single competitor's brand terms took 69% of total impressions**; all competitor terms combined exceeded 80%. |
| **Adriaan Dekker** | LinkedIn poll, self-selected PPC professionals | Only **16%** reported good AI Max performance. Self-selection caveat applies. |

**Reading:** independent evidence is consistent in direction, contradicts Google's marketing. Never
present Google's uplift numbers without this counter-evidence.

## Where it helps and where it destroys accounts

**Relatively helps:** e-commerce, clear intent, fast conversion cycle — clean signal for the algorithm.
Still shows ROAS drag per smec, just less catastrophically.

**Hurts:**

- **Local / home-services lead gen** — the sharpest documented failure (HBT Digital above).
- **B2B lead gen** — long cycles, CRM-disconnected form-fill optimization; scales low-intent content
  downloads while pipeline quality craters. Does not know your ICP.
- Regulated verticals needing strict message control.
- **Budget-constrained accounts** — AI Max expands into *additional* budget-funded reach; if
  impression share is already lost to budget, it diverts spend from working keywords instead of
  adding incremental volume.
- Thin/disorganized content sites — URL expansion has nothing good to match against.

## Pre-migration checklist

Synthesized from Brad Geddes (Adalysis) and Austin Sellers (ZATO), both published within a month of
the deadline.

1. **Audit and catalogue** every campaign running DSA, ACA, or campaign-level broad match before
   touching anything.
2. **Baseline first.** Export current performance and the full search terms report **before**
   migrating, so post-migration drift is measurable rather than anecdotal. This is the step people
   skip and cannot recover.
3. **Conversion tracking must be accurate and deduplicated.** Geddes: *"AI Max optimizes toward what
   you have defined as success."* Garbage-in applies harder here than to ordinary Smart Bidding,
   because AI Max drives query *expansion*, not just bid level.
4. **Bid strategy must already be conversion-focused.** tCPA/tROAS is more predictable than the
   maximization variants under AI Max specifically (Geddes).
5. **Conversion-volume gate** [Geddes, tested]: **<30/month = highly erratic · 30–100/month =
   inconsistent · 100+/month with prior broad-match success = best results.** Start on non-brand ad
   groups already clearing 30/month.
6. **Confirm the campaign is not budget-constrained** before enabling — see above.
7. **Apply text guidelines and term exclusions defensively before enabling.** Auto-generated RSA
   assets have "a poor track record" (Geddes). Do not wait to see what gets generated.
8. **Sellers adds:** fix landing pages and strip irrelevant page content *before* migration, because
   URL expansion crawls and matches against exactly what is there. Pre-load sitelinks/callouts/
   snippets as extra context signals. **Download and archive historical DSA search-term and
   landing-page data now** — that diagnostic history becomes hard to reconstruct once the campaign
   type disappears in Feb 2027.
9. **Migrate DSA voluntarily weeks ahead of Feb 2027** rather than letting the forced migration pick
   your learning-period timing.

## AI Overviews and AI Mode

**Ads in AI Overviews are existing Search/Shopping/PMax ads made eligible for a new placement** — no
AI Overview campaign type exists. Placement decided by **both the query and the content of the
generated Overview** — a dual relevance bar beyond ordinary matching.

**Advertisers cannot target or opt out of AI Overview placements** (confirmed early 2026). Eligibility
is automatic once existing ads clear the relevance threshold.

**Reporting gap:** AIO-placed ads are folded into "Top Ads" with **no segmented metric**. You cannot
pull AIO-specific CTR/CPC/CVR from the UI at all. Any claim about "our AI Overview performance" from
standard reporting is unfounded.

Ads appear in an estimated **25.5% of AI Mode results in 2026**.

### CTR — two datasets that tell opposite stories

- Jun 2024 – Sep 2025: paid CTR on AIO-present queries collapsed **19.70% → 6.34%**, bottoming at
  3.26% in Jul 2025.
- Jan 2025 – Feb 2026: paid CTR on AIO-present queries **rose 14.64% → 16.21%**, while CTR on
  *non*-AIO queries **fell 25.98% → 21.85%**.

Read together: early AIO shock crushed paid CTR; Google re-optimized ad placement inside Overviews
enough to partially recover it; ordinary SERPs now lose CTR instead — plausibly AI Mode siphoning
easier low-funnel queries out of the traditional pool.

**Never quote a single AIO CTR number without naming which dataset and window it came from.** They
tell opposite stories.

The comparison that actually matters is **same-query before/after**, not absolute CTR against a
generic benchmark: 9.87% paid CTR "may appear healthy against broad benchmarks" but is far below the
**21.27%** the same queries earned pre-AIO.

**Refuted — do not cite:** the widely recirculating "Search CPC rose 12% YoY to $2.96 in Q1 2026"
traces to three cited sources (WordStream Q1 2026, a "Google Ads Transparency Report", Search Engine
Journal), **none of which contain the figure**. Treat as content-farm/AI-hallucinated propagation.

### The tradeoff nobody surfaces

Google is positioning AI Max as the mechanism qualifying campaigns for AI Overview / AI Mode ad
placement (reported in travel-vertical coverage — [single-practitioner, contested], not confirmed as
universal). If true, disabling AI Max to dodge the migration may also forfeit AIO/AI Mode eligibility.
Flag this as an open risk when advising, not as an established fact.

**Aaron Levy** (Optmyzr, ex-Tinuiti VP Paid Search), from Optmyzr's aggregate account base: click and
traffic volume down **15–20% YoY** while revenue, conversion rate, and conversion volume were *up*.
His read: AI is pre-qualifying users upstream and Search is becoming a true bottom-of-funnel
catch-all. On cannibalization: PMax and AI Max *"heavily overindex on competitive queries — on one
side you're paying higher CPCs to bid on a competitor's brand name, and on the other side you're
getting your own brand CPCs inflated as well."*

## Practitioner positions worth carrying

- **Menachem Ani** (JXT Group): the Meta-style consolidation model **actively fails on Google**,
  because the platforms run on different targeting logic — Google is explicit-search-intent driven
  ("every search query is a person telling you something, not a demographic"). Consolidating the way
  you would on Meta destroys the signal Google's algorithm needs. Prescribes clean product
  segmentation by economic/price tier, isolated retargeting, staged rollouts, and product-theme (not
  generic) PMax asset groups. **This is the single most important cross-platform warning for anyone
  running both Meta and Google.**
- **Julie Bacchini** (Neptune Moon): names **"algorithm drift"** — a campaign slowly expanding into
  irrelevant terms "because it thinks it's being helpful", which is exactly what the HBT and Monks
  datasets document numerically. Holds that AI can execute but cannot strategize, that SKAGs have run
  their course, and is publicly skeptical of Google's **Ads Adviser** output.
