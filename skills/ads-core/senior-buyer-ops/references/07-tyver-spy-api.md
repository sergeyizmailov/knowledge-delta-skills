# Tyver spy — public API (FB/IG ad library)

CLI: `scripts/tyver.py` (stdlib). Auth env `TYVER_KEY` = `tyv_…` token from the Tyver dashboard → API.
Verified live 2026-09-26 against spec `https://api.tyver.io/public/v1/openapi.json` (docs UI `app.tyver.io/api-docs`).

## Contract
- Base `https://api.tyver.io/public/v1`, header `X-Tyver-Authorization: tyv_…` (not `Authorization`).
- Endpoints (the whole public API): `GET /info/me` (tariff, `remainder_views`), `GET /creatives/` (search),
  `GET /creatives/{provider_id}`, `GET|POST|DELETE /blacklist/?fan_page_id=` (hide a page from results).
- **Quota = 1 view per creative returned.** A search page is fixed at 60 items = 60 views; `/info/me` is free.
  Counter updates within ~10 s. PRO quota seen: ~59k. Free plan → 403 on everything.
- Pagination: opaque `cursor` from the response; results always sorted DESC by `sort`
  (`creation_time` default | `activity_days_amount` | `impressions_from` | `id`). `total` = all matches.
- Array filters = repeated keys (`countries=KG&countries=KZ`); a comma list is a 422.
  Errors: `{"detail":"Validation error","data":[…enum list…]}`.
- The internal app API (`api.tyver.io/openapi.json`, JWT login) is a different surface — folders, presets,
  webmasters, translate. Not reachable with the `tyv_` token; don't build on it.

## Filters worth using
`countries` + `countries_limit=1` (ads targeting ONLY that GEO — kills global multi-GEO junk) ·
`recent_activity_gte` (seen live on/after date) · `activity_days_amount_gte` (longevity) ·
`search` (full-text on body; `"exact phrase"` in quotes) · `in_link` / `domain` / `domain_zones` / `fan_page`
(`|` = OR) · `media_types` CAROUSEL|IMAGE|VIDEO · `cta` ("Play game", "Download"…) · `vertical`
GAMBLING|APPS|ECOMMERCE + `vertical_subcategories` (slot names: GATES_OF_OLYMPUS, TOWER_RUSH, COIN_STRIKE…).
Gender/age/impressions are EU-only (Ad Library data) — 0/null elsewhere.

## Data traps (field-checked, KG 2026-09-26)
- **`vertical=GAMBLING` misses most grey casino ads.** Catalog-camouflage ads carry white product text, so
  ~96% of KG casino creatives found by text/domain search had no vertical tag; the tag also labels
  e-com/nutra/taxi as gambling. Build the set from `search` + `domain_zones` + `in_link`, then filter yourself.
- `languages` came back empty on every record → detect language from `bodies` yourself
  (Kyrgyz = Cyrillic + `ң ө ү`).
- `target_url` holds the ad's real destination with macros intact (`sub_id_1={{campaign.name}}&pixel=…`) →
  tracker/PWA builder and pixel id are readable. For catalog ads `captions` lists the product-link hosts
  (amazon.fr, …) and `link_descriptions` is `{{product.description}}` — that's the catalog signature.
- `activity_days_amount` is short even for winners (grey ads are relaunched daily under new ids); longevity
  ranks survivors, not profit. Pair with a results source (below) before copying anything.
- Lines inside bodies contain ` `: split JSONL on `"\n"`, never `str.splitlines()`.
- Media URLs (Backblaze) are direct `mp4`/`jpg`; download promptly, they rotate per month-bucket.
- Your own ads are indexed too (seen: ours within days, with `sub_id_6=<buyer>` exposed). Anything in the URL is public.

## Best use: join with a results source
Spy shows WHAT runs; it never shows profit. When teammates share a PWA builder / tracker, match
`host(target_url)` against your team's per-host stats (PWA Partners `statistics/report` grouped by `host`)
→ creatives + copy next to real installs/regs/deps. Project example: Improve-Team `scripts/kg_winners.py`.

## CLI
```
tyver.py me
tyver.py search --country KG --countries-limit 1 --search MPlay --active-since 2026-09-23 --pages 5 --out kg.jsonl
tyver.py summary kg.jsonl --top 20       # advertisers, landing hosts, CTA, formats, longest runners
tyver.py media kg.jsonl --dir media/ --min-days 3 --limit 30
tyver.py get <provider_id> · tyver.py blacklist list|add|rm <fan_page_id>
```
`search` refuses when `pages*60` exceeds the remaining quota or `--max-views` (default 1200); appends + dedupes.
