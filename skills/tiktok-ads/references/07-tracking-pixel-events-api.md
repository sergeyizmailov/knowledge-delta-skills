# 07 — Pixel, Events API, attribution, and trackers

Verified 2026-09-14. TikTok's API portal is a JS-rendered SPA; where a schema detail came from a
high-fidelity mirror (Tealium, Adobe Experience Platform, Stape) rather than a directly fetched
TikTok page, it is marked. **Re-confirm exact field names against the live portal before wiring
production.**

## The governing property: this stack fails silently

Almost every tracking failure on TikTok produces **no error anywhere**. A wrongly normalised phone
number, a mismatched `event_id`, a `ttclid` dropped across a redirect — none of them throw. You
discover them as "the campaign doesn't convert", weeks later, after spending.

So the rule is: **fire one real test conversion end to end and watch it arrive before you launch
anything.** Not "the pixel is installed". One event, through the real funnel, visible in Events
Manager.

## Pixel and Events API are one system

TikTok treats the browser pixel and the server-side Events API as two legs of one connection.
"Pixel 2.0" is practitioner shorthand, not a TikTok product name.

**Event Source ID** is the umbrella term: a Pixel ID (web), an App ID (app), or an Offline Event Set
ID. `pixel_id` and `pixel_code` refer to the same value in current docs.

Install paths: manual base code (`analytics.tiktok.com/i18n/pixel/events.js` → `ttq.load(<id>)` →
`ttq.page()`); **Google Tag Manager** via TikTok's own GTM template, connected from Events Manager →
Partner Platform; Shopify through the official app (auto-installs via Shopify's Web Pixels API);
WooCommerce, Magento, BigCommerce via their partner integrations.

**Always use the account-generated snippet**, never one copied from a forum — it carries the right ID
and the current loader.

**Pixel Helper 2.0** (Chrome extension, published by TikTok) verifies installation, shows the
detected pixel ID and fired events, and flags errors. Use it before believing an install.

## Standard events — renamed, with legacy names still live

Two renames took effect **1 May 2025** for Web/Offline/CRM:

| Legacy | Current | Status |
|---|---|---|
| `CompletePayment` | **`Purchase`** | Renamed; legacy still fires, TikTok auto-maps on the backend |
| `SubmitForm` | **`Lead`** | Same |
| `ClickButton` | — | Being retired, **supported until 2027** |
| `PlaceAnOrder` | — | Same sunset |

Added in the same update: `StartTrial`, `SubmitApplication`, `ApplicationApproval`.

Current web set: `AddPaymentInfo` · `AddToCart` · `AddToWishlist` · `ApplicationApproval` ·
`CompleteRegistration` · `Contact` · `CustomizeProduct` · `Download` · `FindLocation` ·
`InitiateCheckout` · `Lead` · `Purchase` · `Schedule` · `Search` · `StartTrial` ·
`SubmitApplication` · `Subscribe` · `ViewContent`. In-app events are a separate, larger list.

`SearchLead` does not exist — it is a conflation of `Search` and `Lead`.

**Because legacy names keep working, a stack can run mixed names for years and look fine.** That is
the debugging trap: reporting shows the new name while the code says the old one.

## Parameter names that silently fail

- **`content_ids` (plural)** at the pixel/JS level — a single ID or an array. **`content_id`
  (singular) is a documented common mistake** that silently fails to match catalog items.
- `contents` — array of objects, each with singular `content_id`, `content_name`, `quantity`,
  `price`, `content_category`, `brand`.
- Server-side `properties` uses top-level `content_type`, `currency`, `value`, `description`,
  `order_id`, and singular names **inside** each `contents[]` object.
- `content_type`: `product` | `product_group`.

Getting this wrong degrades dynamic personalisation and catalog matching without raising anything.

## Events API

```
POST https://business-api.tiktok.com/open_api/v1.3/event/track/
Access-Token: <token>
```

Access tokens for Events API are generated **per pixel** in Events Manager → pixel → Events API
setup. The older `v1.2 /pixel/track/` path is deprecated.

Batch limit: **1,000 event objects per request**. More than 1,000 and **the entire request is
rejected**, not truncated. TikTok's own recommendation is to skip batching and **send each event in
real time** as the server sees it; `event_time` is a Unix timestamp in seconds, **UTC+0**.

```json
{
  "event_source": "web",
  "event_source_id": "C9XXXXXXXXXXXXXXXXXX",
  "test_event_code": "TEST12345",
  "data": [{
    "event": "Purchase",
    "event_time": 1757865600,
    "event_id": "order_98213_purchase",
    "user": {
      "email": "<sha256 of lowercased, trimmed email>",
      "phone": "<sha256 of E.164 phone>",
      "external_id": "<sha256 of your user id>",
      "ttclid": "C9XXXXXXXX.tt.1",
      "ttp": "<value of the _ttp cookie>",
      "ip": "203.0.113.45",
      "user_agent": "Mozilla/5.0 …"
    },
    "properties": {
      "content_type": "product",
      "currency": "USD",
      "value": 129.99,
      "order_id": "ORD-98213",
      "contents": [
        {"content_id": "SKU-001", "content_name": "Wireless Mouse", "price": 59.99, "quantity": 1}
      ]
    },
    "page": {"url": "https://example.com/thank-you", "referrer": "https://example.com/checkout"}
  }]
}
```

`event_source`: `web` | `app` | `offline` | `crm`.

**`event_time` format is a reported trap.** TikTok's API canonically wants **Unix epoch seconds**;
some SDKs accept ISO 8601, and practitioners report ISO values being stamped with the *arrival* time
instead of the event time — which quietly destroys attribution windows. Send epoch seconds. Verify
against the live reference before shipping.

Rate limit: **1,000 QPS at every app level**, no application needed.

`test_event_code` comes from Events Manager → Test Events. Events tagged with it are **sandboxed and
not stored**, and the code **rotates per Events Manager session** — re-copy it when you return.

## Identity signals

| Signal | Notes |
|---|---|
| **`ttclid`** | TikTok's click ID, **auto-appended by TikTok to every ad click**. You do not configure it and must not hand-add it to a URL template. The strongest matching signal |
| `_ttp` cookie → `user.ttp` | First-party visitor ID on your domain (a mirrored third-party copy exists on `.tiktok.com`) |
| `ttcsid` / `ttcsid_<pixel>` | First-party session/click identifiers |
| `external_id` | Your own user ID, SHA-256 |
| `ip`, `user_agent` | Network-level |
| IDFA / GAID | App-side; `__IDFA__` / `__GAID__` macros in MMP links |

All pixel cookies carry a **13-month expiry from last use**.

**Hashing rules.** Email: lowercase, trim whitespace, then SHA-256 — *no other normalisation*. Phone:
normalise to **E.164** (`+15551234567`, no spaces, dashes or parentheses), then SHA-256. Output is
64-char lowercase hex.

**A hash mismatch produces zero errors.** `(555) 123-4567` hashed as typed simply never matches. This
is the most common silent failure in the whole stack.

## Deduplication — send both legs immediately, with the same `event_id`

Source: TikTok "Event Deduplication" (doc `1771100965992450`), verified 2026-09-14.

**The dedup key is `event_source_id` + `event` + `event_id`.** All three must match between the
pixel event and the Events API event for the same user action.

- **First received wins.** Later duplicates are discarded for **48 hours** from the first event.
- **A duplicate arriving within 5 minutes has its extra data merged into the first.** If the browser
  leg had no `user.email` and the server leg does, that email is merged in. The 5 minutes is a
  **merge window, not a required gap.**
- **Send both legs as soon as the action happens.** TikTok explicitly recommends real-time sending
  over batching. Deliberately delaying the server leg gains nothing and loses the merge.

**If you have read anywhere that the two legs must arrive at least 5 minutes apart, that is wrong**
and it is expensive: the delay costs you the PII merge, which is the thing that raises Event Match
Quality.

Generate `event_id` **once, at the moment of the user action, before any tag fires**, and reuse the
identical string on both legs. Generating it separately in the browser and on the server (a
`Math.random()` on each side) is the classic double-count.

### The cookie fallback, and when it bites

If you do **not** send `event_id` from the Events API but do send the `_ttp` first-party cookie in
`user.ttp`, TikTok deduplicates on `[pixelCode, event, _ttp]` with a **5-minute window** instead.
Three things about it that matter:

- It **only ever drops Events API events**, never browser pixel events.
- It only applies when `event_id` is **absent** from the Events API payload. Sending `event_id`
  disables it — so pick one mechanism, do not half-configure both.
- It needs first-party cookies enabled in the pixel settings.

`event_id` is the recommended path. Use the cookie path only when you genuinely cannot produce a
shared ID across the two legs.

Verify in Events Manager: each event type shows as **"browser only"**, **"server only"**, or
**"server & browser"**. The last confirms both legs are firing and being deduplicated.

## Attribution — set at ad-group creation, then locked

Three types: **Click-through (CTA)**, **Engaged view-through (EVTA)** — the user watched **≥6
seconds** without clicking — and **View-through (VTA)**.

Documented enums on `/adgroup/create/` (doc `1739499616346114`):

| Field | Values |
|---|---|
| `click_attribution_window` | `OFF` · `ONE_DAY` · `SEVEN_DAYS` · `FOURTEEN_DAYS` · `TWENTY_EIGHT_DAYS` |
| `view_attribution_window` | `OFF` · `ONE_DAY` · `SEVEN_DAYS` |
| `engaged_view_attribution_window` | `ONE_DAY` · `SEVEN_DAYS` |
| `attribution_event_count` | `UNSET` · `EVERY` · `ONCE` |

**Which of those the account may actually use depends on the objective** — TikTok keeps the
per-objective matrix in a separate document (`1777694366654465`). The enum tells you what the field
accepts; it does not tell you what this ad group is eligible for. Check before locking one in,
because it cannot be changed afterwards.

Two co-requirements TikTok enforces: `click_` and `view_` must be passed **together**, and
`engaged_view_` requires both of them. `ttops preflight` checks this offline.

Default: **7-day click + 1-day view.**

**The window is chosen at ad-group creation and cannot be changed afterwards.** Two consequences:
comparing windows means building two ad groups, decided up front; and you cannot re-run a report "at
a different window" — attribution is not a reporting parameter.

**TikTok explicitly states the in-platform window does not affect MMP reporting.** Changing it does
not retroactively change what an external tracker recorded. The two systems must be reconciled
manually, forever.

**Why TikTok and your tracker will never agree:**

1. TikTok is a **self-attributing network** — it attributes using its own logic and window, whatever
   your tracker's model says.
2. TikTok counts **EVTA**, which a click-ID-based tracker cannot observe at all. This alone produces
   a systematic gap that is not a bug.
3. Window mismatches mechanically produce different totals for identical traffic.

Pick one source of truth for money — platform or tracker — and reconcile the other against it
rather than averaging or blending the two into one number.

**Attribution Portfolio** adds Attribution Analytics (first vs last touch), Performance Comparison
across windows, Time to Conversion, and Touchpoints to Conversion.

## Event Match Quality

A **0–10** score per pixel measuring whether TikTok can match events to real users. Ads Manager →
Events → pixel → Event Quality, with a Diagnostics tab naming issue, severity, affected dataset and
impacted ads.

Practitioner-reported thresholds (secondary, not primary-sourced): a floor near **5.0** below which
value-based optimization access is restricted; browser-pixel-only tends to cap around 6.5;
pixel + Events API can reach 8+; Events API alone reportedly adds 2–3 points.

**Check EMQ during the B2 gate in `01`.** If the plan assumed value optimization and EMQ is below the
floor, the plan is wrong before it launches — and this is cheap to check.

## App tracking

SKAN 4.0: **Fine-grained schema** usually auto-copied from SKAN 3 on migration ("not guaranteed —
must be confirmed"); **coarse schema must be configured manually** and materially reduces null rates
while unlocking the 2nd and 3rd postback windows.

App attribution windows under SKAN 4 are **2, 7 and 35 days** — do not conflate with the web CTA/VTA
numbers.

Supported MMPs: Adjust, Airbridge, AppsFlyer, Branch, Kochava, Singular. Activate via Events Manager
or one-click in Ads Manager after upgrading the MMP SDK and configuring the conversion-value schema.

**The legacy MMP postback flow was discontinued 31 March 2025** in favour of mandatory SAN direct
integration. Material describing token-based MMP postback setup (including some 2026 video tutorials)
is stale on this point.

## Offline and CRM

Offline event sets ingest by **CSV upload** (`.csv` only, ≤10 MB, **email or phone only** — no name
or location matching) or by **Events API** with `event_source: "offline"`. Results appear in
reporting within ~24 hours; daily uploads are the recommended cadence. Creating an offline event set
needs Admin or Operator in Events Manager.

Lead generation: Ads Manager → Tools → **Leads Center** → Connect CRM, or TikTok's **webhook** for
arbitrary endpoints (`/subscription/subscribe/`, `tiktok-ops/06`), or middleware (Zapier,
LeadsBridge). `lead_get` / `lead_field_get` retrieve leads via API.

**Close the loop.** Send the CRM disposition back with `event_source: "crm"` so campaigns optimize
toward qualified or closed leads instead of raw form fills. This is where lead-gen accounts usually
leave the most money — the payout event from `01` intake #3 is rarely "form submitted".

## Third-party trackers

**Macro syntax is `__NAME__`** (double underscore both ends):

| Macro | Expands to |
|---|---|
| `__CAMPAIGN_ID__` / `__CAMPAIGN_NAME__` | Campaign |
| **`__AID__` / `__AID_NAME__`** | **Ad group** — not "ad" |
| **`__CID__` / `__CID_NAME__`** | **Ad / creative** — not "campaign" |
| `__PLACEMENT__` | Placement |
| `__IDFA__` / `__GAID__` | Device IDs (app/MMP) |
| `__IP__` / `__UA__` | Click IP, user agent |
| `__CALLBACK_PARAM__` / `__CALLBACK_URL__` | MMP postback wiring |

**`__AID__` = ad group and `__CID__` = ad.** Both read as the opposite of what an experienced buyer
expects, and getting them backwards silently mislabels every row in the tracker. Verify on the first
real click, always.

**`ttclid` is auto-appended by TikTok** — never insert it manually into a URL template.

Put macros in the ad's **URL parameter** field, not the "Tracking URL(s)" field — that one is
reserved for third-party impression/click pixels.

**Keitaro:** conversions fire when `ttclid` is present. Integrations → TikTok → authorize → enter
Advertiser ID → assign campaigns → map statuses. Costs backfill 5 days on first connect then update
hourly; conversions push to TikTok's S2S endpoint hourly with `event`, `timestamp`, `ttclid`,
`value`, `currency`. Keitaro requires the traffic source set to TikTok.com and clicks carrying
`__CID__`, or cost attribution breaks.

**RedTrack:** recommends the no-redirect method (Universal Script) for TikTok. Its own click-ID
placeholder is `{ref_id}` — a RedTrack mechanism, not a TikTok macro.

Gotchas: every redirect hop is a chance to **drop `ttclid`** — capture it server-side at first touch
and persist it rather than trusting it to survive the funnel. And send refund/cancellation events
back, or the model keeps optimizing toward reversed buyers and builds lookalikes from them.

**Counting discipline matters as much as instrumentation.** Decide which metric pays — platform-
attributed, tracker-attributed, or a named blend — before anyone reports a number. Align tracker and
platform reporting to the same timezone. Cohort conversions by click date, not conversion date, so a
late-arriving sale credits the day that earned it. Exclude rows where a macro like `__CID__` never
substituted — a literal, un-replaced token in a report row means the macro failed, not that the value
is genuinely blank.

## Consent

**Limited Data Use (LDU) is a CCPA/CPRA mechanism, not GDPR consent.** It restricts TikTok's
downstream processing. It does **not** stop the pixel firing and does **not** stop the `_ttp` cookie
being set. For a GDPR user who declined, the pixel must be **blocked from loading**, via a CMP.

**Gate the server-side call with the same consent signal as the browser pixel.** Blocking the pixel
while the Events API fires unconditionally is a false sense of compliance and a common gap.

No TikTok-native Consent Mode equivalent (analogous to Google's) surfaced in research — current
practice is CMP-conditional loading plus LDU flags. Marked unverified; check TikTok's privacy docs
before asserting it does not exist.

## Pre-launch tracking checklist

1. Pixel installed and confirmed with Pixel Helper 2.0.
2. **One real test conversion fired end to end and seen in Events Manager.**
3. Event name is current (`Purchase` / `Lead`), and the same name on both legs.
4. `event_id` generated once per action, identical on the browser and server legs, both sent as close together as possible.
5. Events Manager shows **"server & browser"** for the optimization event.
6. Email/phone normalised exactly (lowercase+trim, E.164) before SHA-256.
7. EMQ checked — and above the floor if value optimization is planned.
8. `ttclid` survives every redirect to the final destination.
9. `__AID__` / `__CID__` mapped the right way round in the tracker, verified on a real click.
10. Attribution window chosen deliberately — **it locks at ad-group creation**.
11. Consent gating applied to **both** legs.
