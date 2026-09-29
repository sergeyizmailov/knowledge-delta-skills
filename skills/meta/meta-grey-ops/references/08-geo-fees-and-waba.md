# 08 — Geo fees, account locks, WABA

Reviewed 2026-08-27. Session/IP → `01`. Agency billing → `03`. CTM/CTWA as LP-skip → `07`.
Google geo/OFAC → `google-grey-ops/07`. Meta-only facts below.

## Location fees (DST pass-through)

[facebook.com/business/help/1238737454289085]

- Fee on **impressions in the jurisdiction**, not business location. **Added on top of delivery** ($100 Italy + 3% = $103, not taken from budget). Invoice line by country.
- Live rates: Austria 5% · France 3% · Italy 3% · Spain 3% · Türkiye 5% · United Kingdom 2%. Can change.
- Agency tenant: billed party pays; fold into break-even (`03`). Ads Manager CPL **excludes** this line.
- Three separate money lines, don't collapse: location fee (DST) · VAT/tax (billed-party jurisdiction) · agency markup (reseller).
- [Adsuploader 2026-08, secondary] WA marketing messages invoiced with ads pick up the fee in the same six markets — re-check before treating WA Cloud API as exempt.

## Timezone / currency / country lock

[754049591334898] Changing account timezone → account **closes** permanently, new account created. Default for new accounts: PST.
[291404291014138] Currency changeable once/60 days if no current balance; changing currency **or** timezone → new ad account, old stays visible but closed. Monthly invoicing: currency locked, cannot change post-creation.
Brazil / India / Poland: business country and currency must match; pick a non-Brazil country at create → cannot switch to Brazil (or BRL) later.

**RULE — account timezone = target-geo timezone, set at creation, always.** Skip the dropdown → budget day resets at PT midnight (mid-morning local, e.g. TR 10:00) → starves evening peak, front-loads dead hours. daily_budget/day-parting/insights boundaries all follow ACCOUNT tz, not geo; delayed-start launches timed by geo hours (`04`) fire wrong. Tracker joins must match tz too (tracker-ops). Verify at setup: `GET /{act_id}?fields=timezone_name,currency`. Example: a TR account, `timezone_id: 134` (Europe/Istanbul) for TR.

**Grey: a "settings fix" = new act ID.** Pixel/page shares don't follow automatically (`03`).

## Sanctioned targeting (not Google's OFAC list)

[365561350785642] Cannot target: Cuba, Iran, North Korea, **Russia (country)**, **Sudan**, Crimea, Donetsk, Luhansk, Sevastopol.
Google's 6163740 does not list Russia/Sudan as OFAC — Meta does list them untargetable. Don't copy Google's RU-pause framing onto Meta.
Country-group pages (Europe / CISFTA [1155157871341714]) still **name** Russian Federation — group membership only, not a serve grant.

## WABA quality ≠ ad-account health

[896873687365001] — WhatsApp Business Platform (Cloud API), not the consumer app.

- Two scores: phone number (7d, Green/Yellow/Red) and template (GREEN/YELLOW/RED/UNKNOWN). Template Flagged → 7d to recover or Disabled.
- Phone rating from blocks/reports/mutes (no longer needed / didn't sign up / spam / offensive / no reason), recency-weighted.
- **Flagged/Restricted phone statuses discontinued 2025-10-07.** Messaging limits now portfolio-wide from that date (start 250 unique users outside 24h window).
- Cloud API 24h customer-service window: free-form only while open; after close, templates only (error 131047). API behavior, **not** an ads-review skip.
- WA Commerce Policy bans gambling, dating, adult, drugs, supplements, crypto-as-currency **in the thread**. CTWA dest still WhatsApp.
- **WABA ban does not officially cascade to Ads CID** (or reverse). Shared BM can still cut `whatsapp_business_management`. Replace the **number**, not the ad account, for a red WABA.
- CTWA = thread-level checkpoint + ad review. `page_welcome_message`/prefill is a creative field (default "Hello! Can I get more info on this?"). Green WABA doesn't pass a violating greeting.

## Cannabis / CBD

[5356017181162381]

- THC / psychoactive cannabis: **no ads.**
- CBD/similar cannabinoids: **US only**, 18+, LegitScript + written authorization, THC not >0.3%, no disease claims. Standards do **not** split ingestible vs topical (unlike Google); Help says LegitScript certifies non-ingestible. Domain can't also sell prohibited products.
- Hemp, no CBD, ≤0.3% THC (seed/fiber): US, Canada, Mexico; no written auth needed.
- THC = **no path**. Don't copy Google's topical-only rule onto Meta.

## Adult

Ads nudity policy stricter than Community Standards (no overlay-covered nudity). Dating: written permission, 18+; no paid dating, affairs, sexually-suggestive emphasis.
