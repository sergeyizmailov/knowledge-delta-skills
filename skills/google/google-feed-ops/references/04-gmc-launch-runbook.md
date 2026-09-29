# 04 — Merchant Center launch runbook (new account → products serving)

Reviewed 2026-09-02. Ordered path; `gmcops` (`05`) automates the readable parts. Feed spec → `01`,
suspension mechanics → `02`, campaign structure → `03`, grey lane → `google-grey-ops/12`.

```
0 site trust → 1 account + ToS → 2 homepage verify+claim → 3 business info → 4 shipping (+US tax)
→ 5 data source + products → 6 review → 7 programs → 8 link Ads → 9 first campaign → 10 monitor
```

## 0 — Site before Google (the review is of the site, not the feed)

Practitioner consensus 2025–26: a fresh store's first review outcome is decided by trust signals.
Check every item before the account exists:

- Business name identical across footer, About, MC business info, payments profile, domain WHOIS
  (formatting differences — "Co" vs "Company" — are reported triggers).
- Contact page with phone **and** physical address; About page with a real story.
- Returns policy with a stated window and procedure (no "case by case"); shipping policy with
  carriers, times, costs. The stated returns window must match what MC's return-policy setting says.
- Payment logos only for methods that actually work at checkout (stale icons → Misrepresentation,
  documented single-case fix).
- HTTPS everywhere, no placeholder/lorem text, no password/dev banner during review, no stock
  supplier images identical to dozens of other stores.
- Domain never previously tied to a suspended MC/Ads account or a different business.

Sequencing itself does not suspend — uploading products before gates only yields disapprovals;
suspension comes from the site/identity signals above.

## 1 — Account + Terms of Service

UI or API (`accounts.createAndConfigure` with `accountManagement`, or `accountAggregation` under an
advanced account — `05`). Accept ToS (`gmcops account accept-tos --region US`). Timezone,
language, adult-content flag are account fields.

## 2 — Homepage: verify, then claim

Two steps. **Verify** ownership (HTML tag / GA / GTM / Search Console — external mechanism),
then **claim** (`gmcops account claim-homepage`). "Already claimed by another account" →
`--overwrite` takes it and **breaks the other account's feeds**; that other account is either yours
(migrate deliberately) or a cascade risk (`google-grey-ops/12`).

## 3 — Business info

Address, phone (SMS/call verification — UI), customer service contact. Must equal the site.
Business identity verification (documents) happens only when Google asks; no API.

## 4 — Shipping, US tax

Shipping services configured (rate must be ≥ what checkout charges, incl. handling); **US: tax
settings** — UI-only, no Merchant API surface found 2026-09-02. Both are review gates (`02`).

## 5 — Data source + products

- Shopify: native Google & YouTube app is the default for one country/one currency; sync is
  periodic (price changes lag → "mismatched value" false positives), variant URLs must be the
  variant, Shopify Markets currency-by-IP vs crawler IP causes currency mismatch. Multi-market →
  a feed app or API source.
- API: `gmcops datasources create-api` (label + language for a targeted source; omit both for
  any-label) → `gmcops products insert --data-source … --file …`. Products are only writable in
  API-type sources; processed copy readable after "several minutes"; `id` = `lang~label~offerId`.
- Google Sheets source: Products → Add product source → Google Sheets → existing sheet (UI only;
  Merchant API cannot create it). Agent edits rows with `sheetfeed --target mc` via a service
  account shared as Editor (`GSHEETS_JSON_KEY_FILE`); MC fetches with its own identity, so a
  Workspace admin may need to allow external sharing. Full recipe: `meta-grey-ops/17`.
- Never mix write methods on one source (`01`). Price/availability in the feed must equal the
  landing page **and checkout total**.

## 6 — Review

Initial data-source review 3–5 business days; account review up to 7; re-crawl after a fix 24–48 h.
`gmcops doctor` shows account issues by severity (CRITICAL = nothing serves) and
`products status --status NOT_ELIGIBLE_OR_DISAPPROVED` the item side. Preemptive item disapproval
on price/availability is automated → sync fix, never argue. **Do not request review until every
issue is fixed** — 1–3 attempts before the button locks, cool-downs grow (`02`, `12`).

## 7 — Programs

`shopping-ads` and `free-listings` must be ENABLED (`gmcops doctor` lists state + unmet
requirements; `account enable-program`). NOT_ELIGIBLE names the missing gate.

## 8 — Link Google Ads

Propose from MC (`gmcops link propose --ads-customer <id>` or UI), accept in Ads
(`googleops link accept --merchant <mc-id>`). Handshake ESTABLISHED = linked. Linking makes the two
accounts one enforcement unit: a suspended Ads account suspends the MC, unlinking does not undo
it (`12`).

## 9 — First campaign on a fresh pair

Practitioners (Store Growers 2026, ppc.live, Optmyzr): **Standard Shopping first** below ~$1k/mo
or without conversion history; feed-only PMax after 2–4 weeks / when 30–50 conversions/month are
realistic; add PMax assets later. Budgets $30–50/day are the common starting point (forum
consensus, no study). Structure → `03`, campaign build → `google-grey-ops/00` with
`kind: shopping` or `pmax_retail`.

## 10 — Monitor

Daily: `gmcops doctor` (issues, programs, product counts) and `products status` diff; a rising
NOT_ELIGIBLE count or a new ERROR issue precedes suspension. Alert on any CRITICAL.

## When it fails

| Symptom | Go to |
|---|---|
| Gate false in `doctor` | this file §1–4; US tax in the UI |
| Item disapprovals | `01` attributes, `02` PID; checkout-total mismatch first |
| Account issue Misrepresentation | `02` website elements; fix all, then one review |
| "Website already claimed" | §2; `12` cascade |
| Products approved, no impressions | link (§8), programs (§7), then campaign (`03`, `google-ads/07`) |
| Ads suspended too | `google-grey-ops/04` track, `12` cascade order |
