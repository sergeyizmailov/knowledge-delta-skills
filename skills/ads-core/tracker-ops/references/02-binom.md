# 02 — Binom API

Binom v2 is the current major. Two surfaces coexist — know which you're on:
- LEGACY v1: URL-param API (docs.binom.org/api.php). Auth = `api_key` query/POST
  param. Reports = append `&api_key=` to a UI report URL.
- v2 REST: JSON (docs.binom.org/api-v2.php). Auth = `api-key` HTTP HEADER.
  Swagger at `https://<tracker>/api/doc` (mirror v2.api.binom.org); paths under
  `public/api/<resource>/...`. Exact paths/payloads UNVERIFIED here — read off
  your own /api/doc (no public raw openapi.json).
Legacy URL-param calls work on both; use them when unsure.

Key (legacy): Settings → API section → copy `api_key=XXXX`.

## Legacy reports

- date: 1 today, 2 yesterday, 3 last7d, 4 last14d, 5 this month, 6 last month,
  7 this year, 8 last year, 9 all time, 10 custom time
  (date_s/date_e incl `+%7C+HH%3AMM`), 11 this week, 12 custom date.
- group1/2/3: 2 paths, 3 offers, 4 landers, 5 rules, 6 ISP, 7 IP, 10 device,
  15 browser, 17 OS, 19 country, 21 language, 22 aff network, 23 referrer URL,
  24 referrer domain, 25 weekday, 26 hour, 27 token1, 29 device name,
  30 connection, 31 by days, 282-290 tokens 2-10.
- `&val_page=all`, `&fid=N` (saved filter), order_name/order_type.
- Fields: clicks, leads, cr, lp_ctr, epc, cpc, cost, rev, profit, ROI. Binom
  "leads" = conversions (all-events vs first-per-click NOT stated in docs —
  verify per setup; contrast Keitaro, where `leads` = conversions still in
  status lead, regs = leads + sales, 01).

## Conversions report (per-conversion rows — enables nowcasting)

Conversions view (docs.binom.org/conversions.php) lists raw per-conversion rows:
`Clickid, Time click, Time conversion, Time since click, Payout, Offer, GEO,
Traffic source`. **`Time since click` is a BUILT-IN click→conversion lag
column** (Keitaro makes you compute it from click_datetime/postback_datetime).
CSV export via `.csv` button. Source for completion-curve/lag-cohort analysis
(03). Aggregate reports above are click-date based; per-conversion timing lives
here.

Replay/rebuild (Binom's equivalent of Keitaro import — conversion ledger, 03):
update/add conversions for existing clicks via postback, conversion pixel, or
manual update (docs.binom.org/update-conv.php), keyed by `cnv_id` + `cnv_status`
(+ payout). Use to restore a period from your raw ledger.

## Legacy cost update

`?page=save_update_costs&camp_id=ID&date=12&date_s=&date_e=&timezone=-7&cost=170.95&api_key=KEY`
- order_type 1=total cost, 2=CPC (amount field `cost` or `cpc`). timezone =
  TRAFFIC-SOURCE offset (-12..12) — v1/legacy form only. token_number/
  token_value for per-token splits.
- Binom v2 timezone is a tracker-wide NAMED timezone set by the superadmin
  (changing it retroactively shifts old clicks/conversions); the numeric
  offset is not the v2 model. Reconcile which timezone the tracker is on
  before trusting day boundaries.

## Legacy objects (index.php, action=)

offer_get/getall/add/edit/delete/restore; landing_ same set; source_getall only
(read). No legacy campaign/source create-edit — use v2 REST or UI.

## v2 REST + discovery workflow

Full CRUD on campaigns/offers/landings/sources/paths/rotations with per-user
permissions confirmed to exist; exact paths are per instance, not public.
Required once per tracker before any v2 automation:
1. Open `https://<tracker>/api/doc`; capture the OpenAPI spec its Swagger UI
   loads (network tab → the `.json` it fetches). Auth = `api-key` header.
2. Extract path+method+schema for ONLY the ops you need (report pull, cost
   update, the CRUD you use).
3. CACHE that schema in gitignored notes, tagged with tracker version;
   re-verify on a version bump. Never guess paths from another instance.

## Postback / S2S (both)

Path differs by version, params identical:
- v1: `https://TRACKER/click.php?cnv_id={clickid}&payout={amount}&cnv_status={status}`
- v2: `https://TRACKER/click?cnv_id={clickid}&payout={amount}&cnv_status={status}` (no `.php`)
- `cnv_id` = Binom click id (put `{clickid}` token in the value) — this is the
  param name, not `clickid`. Optional: cnv_status2, cnv_currency, to_offer,
  `disable_postback=1`.
- Statuses are user-defined via Status Schemes (if-then-else, first match).
  Templates: E-commerce (lead/sale/reject), Subscription.
- Click-id flow: place `{clickid}` in the offer URL via network's param (e.g.
  `&sub1={clickid}`); network returns it in `cnv_id`. Onward to source via
  `{externalid}` + `{cnv_status}`.

## Gotchas

- Drill-down JSON formats numbers with separators/percent — parse as strings,
  strip before math. Multi-level reports carry a `level` field per row.
