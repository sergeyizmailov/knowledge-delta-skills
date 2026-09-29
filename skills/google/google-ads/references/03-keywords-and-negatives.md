# 03 — Keywords, match types, search terms, negatives

Reviewed 2026-08-27. Redaction thresholds and negative-list caps are volatile 🔺.

## Match types — what actually matches

| Type | Reaches | Close variants |
|---|---|---|
| Exact `[kw]` | Same **meaning or intent**, not the same string | Yes, no opt-out |
| Phrase `"kw"` | Everything exact reaches, plus searches including the phrase's meaning | Yes |
| Broad `kw` | Everything phrase reaches, plus related searches using signals beyond the text | Yes |

Broad additionally uses account-level signals: landing pages, other keywords in the ad group, session
and search history, plus an LLM semantic layer per Google's 2025–26 messaging [google-reported, not
independently benchmarked].

**Close-variant categories** (official, all match types): misspellings · singular/plural · stemming
(`floor`↔`flooring`) · abbreviations · accents · word reordering (`[shoes mens]` → "mens shoes") ·
added/dropped function words · implied words (`[daydream vr headset]` → "daydream headset") ·
synonyms (`[bathing suits]` → "swimming suits") · same intent, different wording
(`[images royalty free]` → "free copyright images").

Documented non-identical exact match: `[digital marketing services]` serves on "google ads agency".

**Exact match is not literal.** Treat as tightly-scoped *intent* match. No setting in UI or API disables
close-variant expansion on positive keywords. The only lever is negatives — which do not get close
variants.

**2021 BMM merger aftermath:** BMM (`+word +word`) retired Feb–Jul 2021, its behavior folded into
phrase. Phrase is now slightly more expansive than pre-2021 phrase, slightly less than BMM was. The
lasting effect visible in accounts: more query overlap between phrase and broad, more duplicate search
terms across match types, and the irrelevant-query complaints that eroded phrase efficiency 2021–23.

## Prioritization — the four-tier waterfall

Neither "most specific" nor pure Ad Rank:

1. **Identical exact match** wins first.
2. **Identical phrase/broad** (text identical to the query) second.
3. **AI relevance scoring** across ad groups / asset groups when nothing is identical. Google's
   documented example: query "skydiving certifications near me" → ad group "Skydiving License" beats
   "Advanced Skydiving Courses" because "license" scores closer to "certifications" than "courses".
4. **Ad Rank** only as tiebreaker when relevance ties.

**Only one keyword enters the auction per search event.** Consequences:

- Duplicate keywords across ad groups do **not** bid against each other. The 2015-era "competing with
  yourself" fear is obsolete.
- But duplicates create **unpredictable serving** — you cannot force an ad group to own a query by
  keyword text. The relevance model decides, and it shifts as landing pages and sibling keywords change.
- Google's own guidance: do not duplicate the same keyword+match-type across ad groups to test
  creative or landing pages. Use campaign experiments or ad variations, because you cannot control
  which ad group wins.

## Broad match + Smart Bidding

Works only with **all four** conditions present: 30–50 conversions/month/campaign · value-based
conversion tracking (enhanced conversions / offline import materially improve precision) · tight
negatives · healthy conversion volume. Missing any one, it hemorrhages spend chasing cheaper
lower-value demand.

**Optmyzr, Feb 2026, n=30,000 Search accounts** (geo/vertical unspecified):

- Exact match lost ~9.5 percentage points of non-brand spend share since 2022; broad is now dominant
  by budget.
- **Exact match leads on efficiency across the board** (CPA, ROAS).
- E-commerce: exact wins ROAS/CPA; **phrase has the highest conversion rate** of the three; broad and
  phrase near-level on ROAS.
- Lead gen without revenue tracking: phrase dominates spend and conversion share; broad is noticeably
  worse than in e-commerce.
- **Brand campaigns**: exact leads CTR, conversion share, ROAS. Phrase CVR ties exact (8.22% vs
  8.18%). Broad on brand terms = more spend, fewer conversions — weak performer, not merely a
  contamination risk.

NoGood e-commerce test: broad returned about **a third** of exact's ROAS. Broad's job is finding
incremental demand the exact list misses at a structurally lower average value — not replacing exact.

Ignore the widely circulated "$47.80 → $38.20 CPA, 2.1% → 3.4% CVR, 47% fewer irrelevant queries"
figures — they circulate with no traceable primary source.

## Search terms redaction

Official framing: terms without "enough query activity" are omitted for privacy; below-threshold
queries are bucketed into Search terms insights subthemes. **Redaction is identical in the API
(`search_term_view`) — there is no bypass.**

| Source | Date | Sample | Finding |
|---|---|---|---|
| Seer Interactive | Sep 2020 (the baseline event) | Multi-client | Cost visibility 98.7% → 71.0%, clicks 98.3% → 77.9% in one day. ~$27K of unseen search-term data per $100K spend. |
| Taikun Digital (Collin Slattery) | Jul 2025 | 933 campaigns, ~14M clicks, >$20M spend | ~51% of clicks from hidden terms. Hidden queries cost **52% more CPC** and deliver **44% lower CTR**. |

Do not average these — different methodologies and dates. Practical reading: **a quarter to half of
click/cost volume has no visible search term**, worse for small and long-tail accounts, hidden queries
skew worse. **The report you can see is systematically more flattering than reality.** Say this
whenever presenting search-term analysis as evidence.

The widely quoted "85 cents of value wasted per ad dollar" is a worst-case keyword-level figure from
the Taikun study, not an account average.

Getting more visibility: Search terms insights subthemes (category-level when the string is withheld)
· GA4 secondary dimension "Search term" under Acquisition → Google Ads → Campaigns (partial, depends
on linking + consent mode) · cumulative logging via scripts or Optmyzr/Adalysis so terms that cross
the threshold later get caught · n-gram analysis on the visible portion. No method forces disclosure
below the threshold — treat it as a hard floor.

## Negatives

### They do NOT get close variants — the biggest gotcha in the topic

- Negative broad `flowers` blocks "red flowers" but **not** "red flower".
- Negative exact `[running shoes]` blocks only that literal phrase — "running shoe", "shoes running",
  "blue running shoes" all still serve.
- No stemming, plurals, synonyms, or reordering tolerance. Enumerate every form manually.

### Symbols

Only three are recognized: **&** (distinct from "and") · **accents** ("cafe" ≠ "café", add both) ·
**\*** (matching significance). Periods are **ignored** — "Fifth Ave." = "Fifth Ave";
"powerrangers.com" parses as "powerrangers com". Plus signs are usually ignored except sometimes
word-final (C++).

### Limits

| Scope | Limit |
|---|---|
| Per campaign | 10,000 |
| Applied to Display/Video campaigns | 1,000 |
| Account-level | 1,000 |
| Per shared negative list | **5,000** |
| Shared lists per manager / per child account | 20 each |
| Per negative keyword | 80 characters, 16 words |

🔺 Sept 2025: reports of a list exceeding 5,000 sparked talk of a raised cap. Ginny Marvin (Google Ads
Liaison) clarified: *"The threshold remains 5,000 keywords per negative keyword list, but there may be
some cases in which lists a bit over the limit are accepted."* Soft overrun tolerance, not a policy
change. **Never build automation assuming >5,000 works.** Split lists by theme, not alphabetically.

### Where to apply what

- **Account-level** (1,000): absolute brand-safety terms that must never serve anywhere, and the one
  negative mechanism guaranteed to reach PMax without per-campaign setup.
- **Shared lists** (5,000 × 20): the scalable mechanism — one themed list across many campaigns.
- **Campaign level**: campaign-specific exclusions not worth a shared list.
- **Ad group level**: finest grain, to stop one ad group's broader keyword straying into another's
  territory inside the same campaign.

### Negatives always win — audit before you push

A negative at **any** level suppresses the ad before the auction, silently — the most common root
cause of "why did my exact-match keyword stop getting impressions."

Invisible without dedicated auditing: Adalysis "Keyword conflicts", Nils Rooijmans' conflict script,
or the GAQL pull-both-sides-and-diff audit in `10` (query 7). **Run the
conflict audit before every large negative push, not after.**

### Brand exclusions vs negatives on AI surfaces

| Mechanism | Applies to | Notes |
|---|---|---|
| **Brand exclusions** (campaign list) | PMax Search **and** Shopping surfaces | Blocks a whole brand — auto-covers misspellings, variants, and per Google subsidiary brands. **Google's own recommendation over negative keywords.** |
| **PMax negative keywords** | PMax Search/Shopping only — **not** Display/YouTube/Discover within PMax | Google explicitly flags heavy negative use in PMax as harmful to its matching. Reserve for essential brand safety or clearly irrelevant terms. |
| **Account-level negatives** | All Search/Shopping-eligible inventory incl. PMax | The guaranteed-reach option. |
| **Demand Gen** | Content/inventory suitability settings | Does not run on Search inventory; query negatives are not the control surface. |

**Decision rule: brand → brand exclusion list; specific query pattern or irrelevant term → negative
keyword.** Blocking a whole competitor brand with a growing negative list in PMax is a maintenance
trap.

**The 2025–26 pattern:** brand exclusions are primary; negatives are increasingly *advisory* as AI
matching expands. Under AI Max, Google states negatives are respected, but practitioners report cases
where URL expansion overrides a negative it judges relevant. Treat negatives on AI surfaces as
strong-but-not-absolute and audit search terms more often than on standard Search.

## N-gram analysis

1. Pull search terms over a long-enough window (1–12 months by volume).
2. Tokenize into overlapping 1–4 grams.
3. Aggregate cost, clicks, conversions, value per n-gram.
4. Sort by **spend with zero conversions** (negative candidates) and separately by high-CVR fragments
   (expansion candidates).
5. Threshold is context-dependent, no official number. Common: flag any n-gram at ≥2–3× target CPA in
   spend with 0 conversions, or a fixed floor ($50–100, 0 conv) for small accounts. A 1-gram at $500
   spend / 0 conv is noise in a $50K/mo account and a priority cut in a $2K/mo account.
6. **Segment by campaign/ad group/match type before cutting.** An n-gram toxic on broad may be a
   legitimate exact term elsewhere — a blanket negative silently kills live keywords.

Tooling: Brainlabs-lineage n-gram script (maintained by Nils Rooijmans) outputs to Sheets · Python +
`search_term_view` for custom thresholds and cross-account rollups · Optmyzr/Adalysis ship n-gram plus
the conflict layer.

## Research and competitive intel

**Keyword Planner** shows logarithmic volume buckets (10 / 100 / 1K–10K…) to accounts with no active
spend; real spend unlocks precise volumes. Deliberate, not a bug. Workarounds: run a minimal live
campaign ($5–10/day cited as the practical floor) · browser extensions surfacing the same underlying
data (verify ToS before scaling) · cross-reference GSC impressions if the domain ranks organically ·
Ahrefs/Semrush as an independently modeled sanity check.

**Google Ads Transparency Center** (adstransparency.google.com): free, searchable by advertiser
domain, shows every Search/YouTube/Display/Gmail ad served for roughly the past year. 2025 update
lists individual Search Partner domains for PMax. Since **April 2025** it shows the payer/payment
profile name whenever it differs from the advertiser name — useful for unmasking agency-run or
holding-company structures.

It does **not** show spend, triggering keywords, or performance. Two reliable heuristics: headlines
rotating competitor-brand mentions ("[Rival] alternative") signal competitor-keyword bidding; **ad
longevity** is the standard proxy for "this creative works", since advertisers kill losers fast.

**SpyFu / Semrush / Similarweb**: none see auction data; all model from clickstream panels and ad
crawling. SpyFu has the broadest raw keyword coverage (useful for discovery breadth) but degraded
reliability for spend inference. Semrush is more reliable for mid-to-large domains. Similarweb is
better for share-of-voice than PPC archaeology. Spend estimates are commonly ±15–25% for large
advertisers and worse for small ones — use for relative positioning, never as a budget figure.

**Seasonality**: Insights page → "Trending now" and "Trending in the next 90 days", plus demand
forecasts. Practitioner heuristic: start ramping 2–6 weeks before forecast peak; ramping late is
commonly said to cost 30–40% of available volume [unverified figure, directionally consistent].

## Search themes and AI Max matching

**Search themes (PMax)**: advertiser-supplied, **additive**, phrase/broad tier, brand exclusions
respected, limit **50 per asset group** — limits and failure modes → `07`.

**AI Max for Search** is a Search campaign *setting*:

- An ad group with **at least one broad match keyword** gains keywordless recall — broad match
  presence is the on-ramp.
- **Text customization is fully automated when on.** RSA pinning is honored only if **both** text
  customization and final URL expansion are off.
- **Manual CPC is incompatible** — search term matching does nothing without Smart Bidding.
- Branded search controls (specify brands to associate with or avoid, campaign and ad group level)
  rolling out from ~2026-05-29. 🔺 Check live availability.
- Editor and API coverage lagged the beta — verify current API field support before automating.

See `01-account-architecture.md` for the 2026-09-01 forced migration window.

## Operator patterns

**Single-keyword-broad as a research instrument.** SKAG is dead as a scaling structure — duplicate
exact keywords across ad groups just create unpredictable serving. The replacement: one broad keyword
in an isolated cell with tight negatives and its own budget, run ~4 weeks to harvest which queries a
theme actually pulls, then discard the cell. A research instrument, never a production structure.

**Exact-match harvesting loop.** Broad/phrase feeds the search terms report → n-gram and query review
→ converging high-intent converters get promoted to their own exact keyword in a tightly relevant ad
group → the source query is **excluded via negative exact** from the broad/phrase campaign that
discovered it, so it stops serving there once it has a dedicated home. Broad funds discovery; exact
captures proven winners.

**Cross-campaign negative automation.** Maintain a small set of themed shared lists (job seekers,
free/DIY, competitor brands, generic informational) applied uniformly across non-brand Search and
PMax-Search campaigns, plus a recurring conflict audit to catch a shared negative killing a legitimate
exact keyword elsewhere.
