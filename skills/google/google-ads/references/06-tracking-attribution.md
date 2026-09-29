# 06 — Conversion tracking, attribution, measurement

Reviewed 2026-08-27. The highest-leverage layer in the whole skill: bidding quality is capped by
signal quality. Counting money correctly → `tracker-ops`. Is-the-result-real →
`measurement-experimentation-ops`.

## OCI is closing to new adopters — check before building 🔺

**From 2026-06-15, `UploadClickConversion` fails unless the developer token has *previously* sent an
offline-conversion or enhanced-conversions-for-leads request.** Confirmed against
`developers.google.com/google-ads/api/docs/conversions/upload-clicks`. Google is steering click
conversion upload to the **Data Manager API**.

Consequence: **existing** integrations keep working; a **fresh developer token cannot onboard classic
gclid-based OCI**. Verify live status before committing engineering effort; plan new pipelines around
enhanced conversions for leads or Data Manager instead.
Implementation of the Data Manager hop (SA JWT, `{gclid}` cloak-forward trap) → `tracker-ops/04`.

## Conversion action anatomy

**Goal category** (Purchase, Submit lead form, Book appointment, Request quote, Contact, Sign-up, Add
to cart, Begin checkout, Subscribe, Import, Other) drives default optimization behavior. Some features
key off *category*, not just inclusion — PMax new-customer bidding, Demand Gen value rules. Custom
goals combine any mix of actions across categories into one bidding target.

**Primary vs secondary.** Primary reports in **"Conversions"** and feeds Smart Bidding. Secondary
reports only in **"All conversions"** and is excluded from bidding — **except** when added to a custom
goal, where it becomes biddable regardless of the flag.

> Over-marking actions as primary dilutes the bidding signal — algorithm averages dissimilar-value
> events (newsletter signup + purchase both primary), shifts budget toward the cheaper action.

**Count Every vs One.** Every = each conversion per interaction (sales/revenue). One = max one per
click (lead gen, blocks refresh/resubmit inflation). Per conversion action, **prospective only**. This
setting changes the *volume* Smart Bidding sees per click, which directly shifts the effective tCPA
the algorithm computes internally.

**Windows** — changes apply **prospectively only**, history is not reprocessed:

| Window | Range | Default |
|---|---|---|
| Click-through | 1–90 days | 30 |
| View-through | 1–30 days | 1 |
| Engaged-view | 1–30 days | — |
| App install / in-app action | 30 / 90 days | varies |

**"Include in Conversions" checkbox** (default ON) controls whether the action feeds the Conversions
column and therefore Smart Bidding. **This is the primary lever for stopping an analytics-only action
from silently corrupting tCPA/tROAS.** Set it explicitly at creation; never assume the default fits.

**Values.** Fixed, or dynamic from a parameter. "Use different values for each conversion" assigns
per-action monetary weight when several actions roll into one custom goal — required for tROAS parity
across heterogeneous events (value a call at $40 vs a purchase at true AOV). **Currency mismatch
between the value source and the account silently distorts ROAS** — confirm they match.

Smart Bidding trains **only** on actions that are primary **and** include-in-conversions **and** in the
campaign's selected goal. View-through and engaged-view do not feed tCPA/tROAS the way clicks do for
Search/PMax.

## Click IDs

| ID | Fires when |
|---|---|
| **GCLID** | Any ad click landing on web, including mobile web. Auto-appended by auto-tagging. |
| **GBRAID** | Web click → **iOS app** conversion, with ATT consent granted |
| **WBRAID** | iOS app click → **web** conversion, without full ATT. Coarse, aggregated, non-user-identifying |

Capture **all** of `gclid`, `gbraid`, `wbraid`, plus `gad_source` and `gad_campaignid` on every landing
page; store all, submit whichever is populated.

🔺 Unverified single-source claim (wickedreports.com): since Oct 2025 `gclid` and `gbraid` can be set
simultaneously on one upload row. Check API release notes before coding against it.

**ATT:** on restricted iOS traffic `gclid` often not appended — reported conversions drop, Google
substitutes **modeled conversions**. Search/Shopping less exposed than Meta; Display, Video,
App-promotion campaigns targeting web goals see real volatility.

**Auto-tagging vs manual UTMs.** With auto-tagging on, hardcoding UTMs into **Final URL** collides
with the appended `gclid` — **gclid wins attribution** regardless of intended UTM. Fix: never hardcode
UTMs in Final URL; use ValueTrack parameters via **tracking template** (or Final URL suffix).

**gclid stripping.** Any redirect hop that does not forward the query string silently strips `gclid`
and UTMs. Survival:

1. Every internal redirect must append `location.search` to the target, not redirect to a static URL.
2. Fire the **Conversion Linker** tag on the **very first page load**, before any redirect, persisting
   `gclid` into a first-party cookie (`_gcl_aw` client-side, `FPGCLAW` server-side). The cookie
   survives later hops that lose the param.
3. Cross-domain checkout (Shopify subdomain → custom domain): enable cross-domain linking so the ID
   rides `_gl` cookie decoration rather than the raw URL.

## Enhanced Conversions

**Web**: augments click-based conversion with hashed first-party data matched against signed-in Google
accounts. **For Leads**: matches hashed lead-form data captured at submission against later offline
imports, closing form-fill-to-sale loop.

**Hashing/normalization — exact:**

1. Trim leading/trailing whitespace.
2. Lowercase everything.
3. Email: strip dots before `@` **only** for `gmail.com`/`googlemail.com`. Do not strip for other
   domains.
4. Phone → **E.164**: `(800) 555-0200` → `+18005550200`.
5. **SHA-256**, output **lowercase hex** (not base64), 64 chars.
6. You may send raw values and let Google normalize+hash server-side, or pre-hash client-side.
   Pre-hash if raw PII must never leave your server.
7. **Do not hash** country/state/city/zip.

**GCLID nuance:** required only if you are *not* using a tag to auto-collect user data. Google matches
on **GCLID first**, falling back to hashed identifiers only when GCLID is absent or unmatched — so
importing GCLIDs still strengthens accuracy even with the tag active.

**Lift:** Google's own marketing figure is ~10–15% (treat as a ceiling). Workshop Digital measured
**16% average lift in measurable leads** across accounts.

**Silent breakages** — none of these surface an error:

- Wrong client-side hashing (case, whitespace, phone format) → non-match.
- **Consent Mode `ad_user_data` denied → enhanced conversions are not sent at all**, regardless of tag
  config. This one signal gates the entire feature.
- CSS-selector auto-collection breaks after a landing-page redesign changes field IDs.
- EC for Leads: failing to upload the **full universe** of qualified events, including those that did
  not originate from Ads clicks — Google requires it for correct modeling.

**Verify:** Tools → Conversions → conversion action → **Diagnostics** tab shows "Not verified" /
"Recording user-provided data" / "…(verified)". Also Tag Diagnostics account-wide, and DevTools →
Network for the `em`/`pn` params on the request to `googleads.g.doubleclick.net`.

## Offline Conversion Import

**`ClickConversion` required fields:** `conversion_action` (resource name),
`conversion_date_time` (`yyyy-mm-dd HH:mm:ss+|-HH:mm` — **space not `T`, explicit offset mandatory**),
`conversion_value`, `currency_code` (ISO 4217). `gclid` optional-but-recommended. `order_id`
recommended for later adjustments. `consent` highly recommended.

**Backdate limits:**

| Scenario | Max |
|---|---|
| Standard gclid OCI | **90 days** after the click — beyond this the row is silently dropped |
| Enhanced Conversions for Leads | **63 days** |
| Conversion adjustments (restatement/retraction) | **54 days** from first recording [official: answer/7686280]. The **55-day** figure is **Hotel Ads only** (answer/7686447) — do not apply it elsewhere |

Any pipeline with a sales cycle longer than ~2–3 months **cannot** feed true backend revenue via
standard OCI. Upload an in-window proxy milestone, then true up value with adjustments.

**Dedup:** the key is **gclid + conversion action + conversion date/time**. Re-uploading the identical
triple is a no-op. **`order_id` is NOT a supported dedup key for standard gclid imports** — dedup on
`order_id` in your own system before sending. For tag+API hybrid flows, using a consistent
`order_id`/transaction ID across both is Google's own recommendation to prevent double-firing.

**Always set `partial_failure = true`** so one malformed row does not fail the batch. Inspect
`partial_failure_error` → `GoogleAdsFailure.errors[]` for `EXPIRED_CLICK`,
`CONVERSION_PRECEDES_CLICK`, `TOO_RECENT_CONVERSION_ACTION`, `DUPLICATE_CLICK_CONVERSION`. Reconcile
accepted vs rejected against the CRM export nightly.

### The highest-leverage move in lead gen and affiliate

Front-end leads frequently 30–70% junk. Bidding on them teaches Smart Bidding to find **more junk**,
not more revenue. Fix:

1. Set the front-end form-fill action to **secondary**, or uncheck include-in-conversions.
2. Create a **primary** action of category **Import** representing the backend-qualified event
   (Qualified Lead, Sale Confirmed, FTD), fed exclusively via OCI/API from the CRM or tracker.
3. Point tCPA/tROAS at that action. The algorithm now trains on revenue quality.
4. Respect the 90/63-day windows — use an in-window proxy plus value adjustments if qualification
   runs longer.

Tracker wiring and the postback chain → `tracker-ops`.

## Consent Mode v2

**Basic**: tags do not fire at all before consent. Denied means nothing sent, and modeling falls back
to Google's general model — lower accuracy. **Advanced**: tags fire in cookieless-ping mode when
denied — no PII, no cookie, but a signal that an ad-relevant event of some shape occurred, which lets
Google build an **advertiser-specific** model.

Signals: `ad_storage`, `analytics_storage` (v1) · **`ad_user_data`** (gates Enhanced Conversions and
PII matching), **`ad_personalization`** (v2).

**Modeling threshold**: ~**700 ad clicks/rolling 7 days**, domain-by-country granularity, before
advertiser-specific modeling activates. Below it, general modeling — a *correct* implementation can
still show no lift purely from low volume.

Timeline: 2024-03-06 hard requirement for EU/EEA/UK targeting. 2025-07-21 active enforcement began —
non-compliant accounts had personalized advertising, remarketing, and conversion tracking restricted
in-region. 🔺 Verify current status; Google adjusts these quietly.

**Modeled conversions blend into standard reporting columns with no separate "modeled" column.** This
is a frequent source of "conversions jumped/dropped with no campaign change" — the swing is in the
consent/modeling mix, not performance.

## Server-side GTM

**Mechanism:** JS-set first-party cookies capped at **7 days** under Safari ITP. A server-side
Conversion Linker writing the cookie via a real `Set-Cookie` header from a true first-party domain is
not subject to that cap — extends attribution cookie lifetime to **up to 90 days**, matching the max
click window.

Requires **two chained server tags**: Conversion Linker (writes on first hit) → Google Ads Conversion
Tracking (reads on conversion hit).

**The most common implementation failure:** mapping the domain by **CNAME to a third-party IP**. ITP
then treats it exactly like a third-party cookie and the 7-day cap still applies. You need **A/AAAA
records to your own IP range**.

Ad blockers commonly blocklist `googletagmanager.com`; a first-party subdomain looks like same-site
traffic.

**Cost** [2026 vendor comparisons, approximate and volatile]: Stape free tier ~10K req/mo, ~$20/mo at
500K, ~$100/mo at 5M. Self-hosted GCP Cloud Run ~$50–150/mo at moderate volume. Break-even is around
**3–5M requests/month**; below that, DevOps time erases the sticker saving.

Other pitfalls: sGTM does **not** bypass consent — a container ignoring `ad_user_data` denial is a
compliance violation, not a workaround. Bot traffic hitting the endpoint burns request quota; rate
limit at the edge.

## Attribution

Timeline: Jun 2023 first-click/linear/time-decay/position-based blocked for new actions → Sep 2023
existing actions auto-migrated to DDA → **mid-July 2026 all four fully removed** from the product.
**Only Data-Driven Attribution (default) and Last Click remain.** Google's stated rationale: under 3%
of web conversions used the removed models.

### Why Ads and GA4 never match — enumerate these, don't hand-wave

1. **Different attribution logic** — Ads credits when its ad is anywhere in the path; GA4 distributes
   across channels. Ads virtually always reports **higher**.
2. **Different counting units** — GA4 counts a key event across every session/source touching the
   property; Ads counts only what its model credits to an ad interaction. "100 GA4 purchases vs 35 Ads
   conversions" can both be correct answers to different questions.
3. **Timing basis** — Ads defaults to **click date**; GA4 records on **event date**.
4. **Timezone mismatch** between property and account shifts near-midnight conversions across days.
5. **Currency mismatch** distorts revenue even when unit counts agree.
6. **Consent modeling** — the two platforms model consent-denied cohorts independently.
7. **Conversion window** differences.
8. **Bot/invalid filtering** rules differ.
9. **Dedup logic** — Every/One has no GA4 equivalent; GA4 dedups on `transaction_id`.

**A 20–30% variance is expected, not evidence of broken tracking.**

**Which source feeds bidding:** the **native Google Ads tag**, not GA4-imported conversions. GA4
imports carry a reported **24–48h delay** that degrades Smart Bidding responsiveness; GA4's event-date
semantics mismatch the bidding loop's click-date expectation. Use GA4 key events for cross-channel
analytics/audiences. **Never mark both a native action and its GA4-imported twin as
include-in-conversions** — classic double-count.

**Conversion lag.** Default reporting is by **interaction/click date**, so a given day's numbers keep
rising for days as delayed conversions land. Use **"Conversions (by conv. time)"** / "Conversion value
(by conv. time)" / "ROAS (by conv. time)" to evaluate a period without look-back noise. The
**Conversion Lag Report** (Tools → Attribution → Lag report) shows the click-to-conversion delay
distribution per action — use it to pick a correct window and to know how final a day's numbers are.

## Diagnosis

| Symptom | Likely cause | Where to check |
|---|---|---|
| Conversions drop to zero | Consent/CMP change blocking `ad_storage`/`ad_user_data`; tag removed on redesign; action paused; broken GTM trigger | Tag Diagnostics; GTM preview; Network tab for the pixel |
| "No recent conversions" status | Action <48h old (informational); campaigns paused; low traffic; tag not fired in 7 days | Conversions → action status; Tag Assistant |
| Duplicate/inflated | Same tag from 2+ places; missing `transaction_id` allowing refresh re-fire; GA4-imported **and** native action both include-in-conversions | Count pixel fires per purchase; audit every action's include flag |
| "(not set)" / unattributed | `gclid` stripped by a redirect; cross-domain checkout without linking; ITP truncating a JS cookie | Trace the full click→landing→checkout chain for query-string loss; verify Conversion Linker fires first |
| EC "Not verified" / no lift | Bad hashing; `ad_user_data` denied; CSS selectors broken after redesign | Action → Diagnostics; DevTools `em`/`pn` params |
| OCI rows silently missing | Past 90/63-day window; malformed `conversion_date_time`; timestamp precedes the click | `partial_failure_error` codes |

Tools: **Tag Assistant** (live step-through of what fires and what params go out) · **Tag
Diagnostics** (Tools → Conversions → Google tag → Tag Diagnostics, buckets pages Excellent → Urgent) ·
enhanced-conversions troubleshooter.

🔺 **2026-08-24:** Google announced unifying **Google tag and Tag Manager** with no-code event
tracking — measurement-layer consolidation. Expect the gtag-vs-GTM setup friction around Enhanced
Conversions to keep shifting; verify the current tagging path before prescribing one.
[trade press, single source]

## Incrementality

**Brand search — the study everyone cites and the replication nobody does.** eBay (Blake, Nosko,
Tadelis, 2015): pausing branded SEM by DMA produced **ROAS ≈ −63%** — nearly all lost paid clicks were
recaptured organically. **But Coviello et al. (2017) replicated the design on Edmunds.com, a smaller,
less organically dominant brand, and found materially different, less-negative results.**

Brand incrementality is **brand-position dependent** — never apply "brand search isn't incremental" to
a client without a brand-specific test; quoting eBay at a non-dominant brand is a serious error.

**Conversion Lift**: needs a Google account team to request; more readily available for
Video/Demand Gen. Minimum 7 days, max 56 recommended; under 14 days risks up to a **17% drop in
measured accuracy** for long-lag products. Google's **"Study Power"** pre-check tells you whether a
conclusive result is even possible before you run it. Search Lift states a **$10,000** minimum spend;
Conversion Lift's threshold is unpublished.

**Geo and budget experiments** are self-serve in the native Experiments feature — no rep needed.

**MMM: Meridian** (`github.com/google/meridian`, PyPI `google-meridian`) is Google's current
open-source Bayesian MMM, successor to **LightweightMMM** which is now effectively legacy. Advances:
reach-and-frequency modeling, geo-level modeling, Search query-volume signal, and **experiment
calibration** — feeding Conversion Lift or geo-experiment results in to calibrate channel
coefficients. 🔺 **Meridian GeoX** was reported announced May 2026 with testing later in 2026; single
secondary source, no official page located. Verify before depending on it.

Design validity for any of the above → `measurement-experimentation-ops`.
