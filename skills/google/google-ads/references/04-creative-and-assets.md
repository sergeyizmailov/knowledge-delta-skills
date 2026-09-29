# 04 — Creative, assets, ad testing

Reviewed 2026-08-27. Specs are volatile; verify limits in the live UI before bulk building.

## The three findings that overturn common practice

1. **Ad Strength does not predict performance.** Optmyzr, ~20,000 accounts / 1M+ ads (Sept 2024,
   refreshed Apr 2026): "Excellent" ads averaged **$28.68 CPA / 4.97% CVR**; "Average" ads averaged
   **$12.43 CPA / 12.65% CVR**. "Poor" had the best ROAS (327.65%). Adalysis, >1M ads compared only
   within the same ad group: higher-strength ads had *lower* CTR in **51.5%** of cases — a coin flip.
   Ginny Marvin, verbatim: **"Ad Strength is not used in the auction."** No Ad Rank, Quality Score,
   eligibility, or serving-frequency effect. Adalysis: **"Ad strength does not gate any features."**
2. **Partial pinning beats both alternatives.** Same Optmyzr dataset: partial pin (1–3 assets)
   **$13.68 CPA / 365.15% ROAS**; full pin **$32.57 CPA** (~2.4× worse) with the worst CTR (8.49%).
   Pin H1 to your primary message, leave H2/H3 and descriptions open.
3. **Sentence case beats Title Case by ~3.7× on CPA** for RSAs and Demand Gen ($7.46 vs $27.47). The
   reverse held for legacy ETAs, so ETA-era style guides are now actively harmful.

Google's counter-claim — "15% more conversions on average" Poor → Excellent for RSAs + sitelinks
(data window Aug 15–20 2025; earlier pages said 12%) — is marketing statistics, asterisked by Google
itself, not a controlled experiment.

**Verdict: Ad Strength is a readiness/diversity gauge, not a KPI.** Never sacrifice testing rigor to
chase Excellent. The one place it functions as a checkpoint is PMax, where Excellent suppresses
auto-generated AI video — that is a workaround, not a feature unlock.

## RSA specs

| Field | Min | Max | Chars |
|---|---|---|---|
| Headlines | 3 | 15 | 30 |
| Descriptions | 2 | 4 | 90 |
| Path 1 / Path 2 | 0 | 2 | 15 each |
| Business name | 1 | 1 | 25 — must match domain or legal name for PMax |

Double-width languages (KR/JP/CN) count every character as 2, halving effective length.

**What renders:** minimum one headline + one description always. Up to 3 headlines and 2 descriptions.
**Headline 3 and Description 2 are not guaranteed** — shown only when predicted best or when space
allows. Google recommends ≥2 RSAs per ad group; no published maximum.

**Pinning:** pin points are H1/H2/H3 and D1/D2. Assets pinned to **H1, H2, or D1 always show**.
Assets pinned to **H3 or D2 are not guaranteed** — same as unpinned. Pinning removes the slot from the
combinatorial pool and mechanically suppresses Ad Strength.

**Combinations report** (Campaigns → ad → View asset details → Combinations) exposes **impressions
only** — no clicks, conversions, or cost at combination level. Deliberate restriction since a Nov 2022
Ads Developer Blog change. Click/conversion data exists only at individual asset level. PMax and App
have a separate "Top combinations" report capped at 6 per category. Serving is throttled by Google's
testing algorithm, never evenly rotated.

## Ad testing without ETAs

ETAs stopped serving 2022; every Search test since runs against a combinatorial black box — Google's
ML chooses which combination shows, to whom, when.

**Brad Geddes / Adalysis method:**

1. **One variable per test.** Never change multiple headlines between two RSAs in the same ad group —
   the delta is unattributable.
2. **Use partial pinning to force the comparison**, because fully unpinned RSAs let the algorithm pick
   combinations and contaminate the read:
   - *Pinned vs unpinned*: clone the RSA, pin the top combination in the clone, run both.
   - *Theme test*: pin Theme A headlines to RSA-1's H1, Theme B to RSA-2's H1, leave the rest open so
     the algorithm still works the remainder.
   - **Max 3 themes per ad group** — Geddes' ceiling for a legible test.
3. Challenger vs champion, continuously — test new RSAs against the current best, not in a vacuum.
4. ~100 impressions per combination is the floor to read *directionally* and is explicitly **not**
   enough for significance.

**Asset labels** (View asset details): Pending (still processing) · Learning (insufficient data) ·
**Low / Good / Best**. These are a **relative rank within the ad group**, not an absolute grade,
computed from the subset of combinations Google actually served.

Trap: pausing "Low" assets that would perform fine elsewhere — on a young/low-volume ad group "Low" is
often noise. Wait **4–6 weeks**, then **replace 1–2 assets at a time**, never a full refresh (a
simultaneous swap resets the baseline across every slot).

**Ad variations** (Campaigns → Ads → Ad variations) bulk-swaps text across many campaigns but is
**not** a controlled A/B — no split, no holdout. **Experiments** (Drafts & Experiments) is the
controlled mechanism. Practitioner floors for a usable read: ~1,000 clicks per arm, 30–50 conversions
per arm, 3–4 weeks minimum to smooth day-of-week variance. Pre-commit to duration; peeking bias is
real. Statistical significance is not commercial significance — check lead quality downstream.

Design validity (sizing, SRM, contamination, lag) → `measurement-experimentation-ops`.

## Copy that empirically wins

From Optmyzr's 1M-ad dataset:

- **Headlines under 20 characters**: $9.35 CPA / 11.77% CTR / 10.39% CVR. **21–30 chars**: $18.27 CPA
  / 10.52% CTR / 8.61% CVR. Nearly **2× cheaper CPA for short headlines** — do not max out the field.
- **Descriptions have a sweet spot at 61–70 characters** (12.33% CTR, 307.58% ROAS, 9.21% CVR),
  beating both 0–50 chars and 81–90 chars ($20.11 CPA, worst).
- **Sentence case over Title Case** — see above.

Directional, methodology unverified: message match (ad headline echoed near-verbatim in the landing
page H1) reported at 2.5–3× conversion lift. Landing page experience is one of the three QS
components and mismatch is the most commonly cited fixable driver.

Standard doctrine with no large-N isolated study found: search term/intent in Headline 1;
price/qualifier headlines ("From $49/mo", "Same-Day Shipping") to pre-qualify clicks.

**Competitor ads:** competitor trademark in ad copy/headline/display URL **not allowed** except four
exceptions (reseller · components/compatible-with · informational comparison · purely descriptive).
**Bidding on competitor trademarked keywords fully allowed.** Feb 2025: proactive trademark-protection
submission form removed; enforcement now reactive/complaint-driven per ad.

## Assets

| Asset | Limits | Min to show |
|---|---|---|
| Sitelinks | Link text 25 chars; 2 description lines 35 chars each. Up to 20 created; 6 desktop / 8 mobile / 4 video / 4 Demand Gen shown | **2** |
| Callouts | 25 chars, unlimited created, up to 10 shown | **2** |
| Structured snippets | 25 chars/value, min 3 values (4+ best practice). Desktop shows 2 headers, mobile 1 | 3 values |
| Call | Phone + call reporting/forwarding number for tracking | — |
| Lead form | Header 30, description 200, submission message 200. **Max 5 qualifying questions** | — |
| Location / Affiliate location | From Business Profile or feed. Affiliate = reseller case | — |
| Price | Header 25, description 25. **3–8 offerings required** | 3 |
| Promotion | Promo text 20 chars. **6 schedules/day, 42 total** | — |
| Image (Search) | Square 1200×1200 (min 300×300); horizontal 1200×628 (min 600×314). 1–20 | 1 |
| Business logo | 1200×1200, min 128×128 | 1 |
| Business name | 25 chars, must match domain/legal name for PMax | 1 |

Structured snippets have **13 fixed headers only** — Amenities, Brands, Courses, Degree programmes,
Destinations, Featured hotels, Insurance coverage, Models, Neighbourhoods, Service catalogue, Shows,
Styles, Types. No custom headers.

**Incremental impact** [WordStream aggregate, methodology unverified, directional]: sitelinks alone
+10–20% CTR, +20–50% on branded queries — most lift from **filling the sitelink description lines**
(most advertisers leave blank). Sitelinks + callouts + snippets together >20%. Official mechanism: Ad
Rank includes expected impact of assets, so assets lift Ad Rank at no incremental CPC.

## PMax asset group specs

Text: headlines 3–15 (30 chars, include ≥1 at ≤15) · long headline 1–5 (90 chars, aim ≥30) ·
descriptions 2–5 (90) · business name 1 (25) · paths 0–2 (15).

| Image | Recommended | Min | Count |
|---|---|---|---|
| Horizontal 1.91:1 | 1200×628 | 600×314 | 4–20 |
| Square 1:1 | 1200×1200 | 300×300 | 4–20 |
| Vertical 4:5 | 960×1200 | 480×600 | 2–20 |
| Square logo | 1200×1200 | 128×128 | 1–5 |
| Horizontal logo 4:1 | 1200×300 | 512×128 | 1–5 |

.jpg/.png, ≤5MB.

**Video:** three orientations (16:9, 1:1, 9:16), **each min 10 seconds**, 1080p recommended, SD
explicitly not recommended. At least one vertical 10–60s for Shorts eligibility. Up to 15 per
orientation.

### The auto-generated video problem

Upload zero video and Google auto-generates it from your images/text, or from Merchant Center feed
data for retail. Officially acknowledged failure mode: auto-generated video **"may show customers who
visit your landing page a different product than the one featured in your video"** — the SKU in the
video does not match the Final URL.

Google's mitigation: narrow the asset group via product filters so fewer, more consistent products
feed generation. **Actual fix:** upload real video in all three orientations — also the condition for
Excellent PMax Ad Strength, and it suppresses the AI fallback entirely.

🔺 **Gemini Omni video creation landed in-platform 2026-08-25** — native AI video asset generation,
not a bolt-on tool. Shipped days before this review: no performance comparison exists, so treat it
as a production option to A/B against uploaded video, not a default. [trade press, single source]

## Demand Gen and Video specs

**Demand Gen** — images: landscape 1200×628, square 1200×1200, portrait 960×1200 (recommended for
Shorts), ≤5MB. Text: headlines up to **40 chars** (≥1 at ≤30 recommended), descriptions 90, business
name 25. **Carousel: 2–10 cards, all sharing one aspect ratio**, each with its own 40-char headline,
URL, and optional CTA. Video: 16:9 and 1:1 standard, 9:16 for Shorts, min 10s, ≥15s recommended.

**Video** — in-feed ~15s · video action ≥10s · video reach 15s · **bumper 6s fixed non-skippable** ·
Masthead 16:9 1920×1080, headline 40 / description 60 / CTA 15.

## URL layers

- **Final URL** — the destination.
- **Display URL** — derived from the Final URL domain + 2×15-char paths. Need not equal the Final URL.
- **Tracking template** — wrapper using `{lpurl}`. Works with **Parallel Tracking**: the user goes
  straight to the Final URL while the template fires in the background, so it no longer adds latency.
- **Final URL suffix** — appends query params without rewriting the URL. **Google's own
  recommendation when you only need to append parameters** — simpler and less error-prone. Note PMax
  requires the suffix field, not the tracking template (see `06-tracking-attribution.md`).

## Dynamic text

**DKI** — `{KeyWord:Default Text}`. Capitalization of the token controls output: `{keyword:}`
lowercase · `{Keyword:}` sentence case · `{KeyWord:}` title case. If the matched keyword exceeds the
field limit Google **silently falls back to the default** — always write a strong standalone default.

Dangers: broad match + DKI makes a robust negative list mandatory · misspellings in your keyword list
get inserted verbatim · **disallowed for Healthcare and Sexual Content** · **DKI on a list containing
competitor brand terms auto-inserts those trademarks** into copy, a fast path to disapproval and legal
exposure — scrub brand terms from any DKI-eligible list · never use DKI twice in one ad.

**Countdown** — `{=COUNTDOWN("2026/12/25 12:00:00","en-US",5)}` (target datetime, locale, days-before
to start; default 5). `{=GLOBAL_COUNTDOWN(...)}` fires simultaneously worldwide rather than per-viewer
local time — use it for a hard global deadline, plain `COUNTDOWN` for user-local ones. Copy
auto-escalates day → hour → minute.

**IF functions** — `{=IF(device=mobile,"Mobile text"):"Default text"}` ·
`{=IF(audience IN(list1,list2),"Text"):"Default"}`. Multiple customizer types can combine in one ad.

**Business data feeds** (Tools → Business data) drive per-row dynamic content. Each row is an entity,
each column an attribute; requires `target_campaign`, `target_ad_group`, or `target_keyword` columns.
**Attribute headers must stay in English even in non-English feeds** — documented gotcha.

## Automation Google turns on for you

**Auto-apply recommendations**: ~17 types across Bidding & budgets, Keywords & targeting, Ads &
assets. Path: **Recommendations → gear icon → toggle per category.**

Never auto-apply **Bidding & budgets** — silently raises CPA targets/budgets on Google's own logic when
a strategy under-delivers. Review Ads & assets manually before enabling — Google-authored headlines
drift from brand voice and compliance.

**Account-level automated assets** — eight types Google generates without your copy: dynamic sitelinks
· dynamic structured snippets · automated locations · seller ratings · dynamic callouts · dynamic
business information · dynamic images · automated promotions.

Opt-out path: **Campaigns → Assets → Associations tab → ⋮ → "Account level automated assets" → ⋮ →
"Advanced settings" → uncheck each "Allow Google Ads to automatically create…" → give a reason →
Save.**

- Auto-generated copy surfaces **stale promos, wrong pricing, irrelevant page fragments** scraped from
  the landing page — most common complaint.
- **Practitioners report Google silently re-enabling these after opt-out.** Re-audit the Advanced
  settings screen on a schedule; never treat an opt-out as permanent.
- Account-level automated assets, campaign/ad-group manual assets, and PMax's own automatically
  created assets are **three separate layers**. Disabling one does not touch the others.

🔺 **AI-generated product-title reporting (2026-08-26):** first visibility layer into how much of
PMax/Shopping product-title text is machine-written vs merchant-supplied. Use it to audit how much
of your titles Google now authors — title optimization mechanics live in `google-feed-ops/01`.
[trade press, single source]
