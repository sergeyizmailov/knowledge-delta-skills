# 10 — `googleops` / `gmcops`: agent-facing interface

Reviewed 2026-09-02. Wraps the official `google-ads` (Ads API v25) and `google-shopping-merchant-*`
(Merchant API v1) clients; no third-party launcher in the write path (`11`). Underlying modules
(`gads_spec`, `gads_build`, `gads_verify`) are implementation; agents call the CLI.

## Contract

- One result object on stdout with `--json`: `googleops.result/v1` — `ok`, `command`, `phase`,
  `artifacts`, `data`, `error`, `next_action`. Diagnostics on stderr. Exit 0 = ok, 1 = command
  failed, 2 = rejected locally (spec/workspace/credentials).
- Workspace discovered upward from cwd, or `--workspace`, or `GOOGLEOPS_WORKSPACE`. Refused inside
  the configured skills directory; `state_dir` may not escape the project.
- Plans bind: normalized-spec SHA-256, `workspace.json` SHA, doctor-receipt SHA, `api_version`.
  Any change refuses the command; re-plan. Doctor receipts expire after 24 h
  (`GOOGLEOPS_DOCTOR_MAX_AGE_SECONDS`).
- `apply` creates/resumes PAUSED only; `activate` needs literal `--confirm SPEND`,
  `--confirm-ui REVIEWED`, and an unexpired verification receipt whose state hash still matches.
- Per-state lock file (`<state>.json.lock`) — inspect PID/time before removing a stale one.

## Commands

| Command | Does | Spends? |
|---|---|---|
| `workspace validate` | schema + id checks, resolves profile | no |
| `doctor` | accessible customers, customer facts, billing setups, conversion actions, MC links/invitations, `validate_only` write probe → receipt | no |
| `plan --spec [--tag] [--merchant-receipt r.json]` | normalize (unknown keys rejected; image refs must be a file or numeric asset id) → build → `validate_only` → hash-bound plan; retail kinds **require** a fresh passing `gmcops doctor` receipt (`--allow-unverified-merchant` is the explicit opt-out) | no (validation consumes quota) |
| `apply --plan` | atomic create PAUSED (PMax: assets request first) | no |
| `verify --plan` | GAQL read-back diff → `.verified.json` | no |
| `activate --plan --confirm SPEND --confirm-ui REVIEWED [--refresh-start YYYY-MM-DD]` | enable ads → groups → campaign | **yes** |
| `status --plan [--bulk]` | state + live primary_status/serving/cost today | no |
| `bulk-plan --template --accounts --run` | per-profile `{tag}` stamping, doctor + validate each | no |
| `bulk-apply --plan [--verify] [--continue-on-error]` | build each PAUSED | no |
| `bulk-activate --plan --customer …` | one customer per call | **yes** |
| `report --gaql [--out]` | read-only GAQL (SearchStream) | no |
| `monitor [--profiles] [--range] [--jsonl]` | verdict sweep SUSPENDED/REJECTS/SPENDING/IDLE | no |
| `link status` / `link accept --merchant` | `product_link` read / accept MC invitation | no |

`accounts.json` for bulk: `[{"profile": "p1", "tag": "A1"}, …]`. Every profile needs its own
fresh doctor receipt.

## Spec → API mapping (what the launcher decides for you)

| Spec | API | Why |
|---|---|---|
| `daily_budget_major` | `campaign_budget.amount_micros`, `explicitly_shared=false`, DAILY | PMax rejects shared budgets; micros conversion validated per currency (no minor units on JPY/KRW/…) |
| `geo.positive_geo_target_type` (default PRESENCE) | `campaign.geo_target_type_setting` | Google's default PRESENCE_OR_INTEREST buys interest traffic from outside the geo |
| `eu_political_advertising` (required bool) | `campaign.contains_eu_political_advertising` | required declaration; omission fails create |
| `network` (defaults off) | `network_settings.target_partner_search_network/content_network` | Google's defaults are on |
| `final_url_expansion` (default false) | `campaign.asset_automation_settings[FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION]=OPTED_OUT` | `url_expansion_opt_out` **no longer exists** in v25 |
| `brand_exclusion_shared_set_id` | negative `campaign_criterion.brand_list.shared_set` | BRAND criteria are negative-only on PMax |
| `listing_filter` (PMax) | root SUBDIVISION → UNIT_INCLUDED units + UNIT_EXCLUDED others, `listing_source=SHOPPING`; omitted → single UNIT_INCLUDED root | the tree must be complete or the asset group is rejected |
| `listing_groups` (Shopping) | root SUBDIVISION → UNIT leaves with `cpc_bid_micros` or `negative`, explicit "others" leaf | missing "everything else" node fails the partition |
| ad group (Shopping) | `type=SHOPPING_PRODUCT_ADS`, ad = empty `ShoppingProductAdInfo` | the only valid type; all targeting lives in partitions |
| `tracking_url_template` | campaign-level, must contain `{lpurl}` | ads inherit; a template without lpurl breaks landing |
| locations / languages | `geoTargetConstants/<id>`, `languageConstants/<id>` | US 2840, English 1000 |
| PMax assets | text/image `asset_operation`s in a **prior request**, then `asset_group_asset` links (asset ops before link ops) | ordering is enforced server-side |

## Failure contract

- `plan`/`apply` error payload: `{kind: google_ads_failure, request_id, errors[{code, message,
  path, trigger}]}`. Quote `request_id` to Google support. Map codes with `google-ads/11`.
- `apply` phase `reconcile_required`: state has `in_flight`; the outcome of the last request is
  unknown (timeout/5xx). Look for the campaign name in the UI; if absent, set `in_flight` to null
  and re-apply; if present, record its resource name in `objects.campaign` and run `verify`.
- `verify` exit 1 lists `problems`; DISAPPROVED anywhere → build a new ad/asset, do not enable.
  Verified per RSA: headlines, pins, descriptions, final URLs, path1/path2; per PMax asset group:
  asset counts by field type, listing-filter node count, search themes (not per-asset text).
- PMax `plan` may report `validation_scope: partial…` — only when every error is an asset-link
  error (assets must exist before `asset_group_asset` links); any other error fails the plan.
  `apply` for PMax is two requests: a graph failure after the asset request leaves unused assets
  (harmless, but visible in the asset library).
- PMax campaigns are created with `brand_guidelines_enabled=false` so logo/business name link per
  asset group; new PMax campaigns default to brand guidelines otherwise, which moves those assets
  to campaign level and rejects asset-group links.

## `gmcops` (Merchant Center)

`--account <id>` is the merchant account **being operated**; for a portfolio, call once per
sub-account — `accounts.issues.list` and MCQL refuse aggregate views from an advanced account.

| Command | Does |
|---|---|
| `doctor --country US [--ads-customer id] [--out receipt.json]` (ToS gate needs `--country`: it reads `MERCHANT_CENTER-<country>`) | gates (homepage claimed, address, phone verified, shipping services, ToS not required, data source for country), programs `shopping-ads`/`free-listings` state + unmet requirements, account issues by severity (CRITICAL = offers do not serve), Ads link handshake state, product counts by `aggregated_reporting_context_status` |
| `products status [--status X]` / `get --name lang~label~offer` / `insert --data-source … --file … [--wait s]` | MCQL `product_view` sweep; processed product read; `productInputs.insert` (API data source only; processed copy appears after "several minutes") |
| `datasources list` / `create-api --display-name … [--feed-label] [--language] [--countries]` | API-input primary source; omit label+language for an any-label source |
| `account claim-homepage [--overwrite --confirm OVERWRITE]` / `enable-program --program shopping-ads` / `accept-tos --region US` / `sub-accounts` | homepage claim (verification stays external); program enable; ToS accept via `retrieveLatest`; list sub-accounts |
| `link status` / `link propose --ads-customer id` | `accounts.services` with `campaigns_management` → then `googleops link accept` |
| `report --mcql "…"` | read-only Merchant Center Query Language |

Not exposed on purpose: suspension appeal (`issueresolution.triggeraction` is allowlist-gated,
actions opaque), business identity/phone/address verification, US tax settings (no API surface
found 2026-09-02), shipping settings insert (full-replace semantics; do it in the UI until a
spec exists).

## `sheetfeed` (Google Sheet as catalog)

`sheetfeed --sheet <url|id> [--tab products] --json info|init-header|validate --target mc|meta|both|pull|upsert --file|set --id --field --value`.
Service-account key via `GSHEETS_JSON_KEY_FILE` (falls back to `GMC_JSON_KEY_FILE`), shared on the
sheet as Editor; MC reads the sheet as a UI-created Google Sheets source. Recipe and traps:
`meta-grey-ops/references/17-catalog-via-google-sheets.md`.

## Offline checks

```bash
SKILL_ROOT=/path/to/google/google-grey-ops
uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/test_googleops.py"
uv run --isolated --with ruff ruff check --no-cache "$SKILL_ROOT/scripts"
uv lock --check --project "$SKILL_ROOT"
```

Live status 2026-09-02: offline tests pass (spec normalization, graph shapes for all three kinds,
rejections, workspace, client call shapes — added after an external review caught three
`TypeError`/`ValueError` crashes in activate / link accept / accept-tos). **No live account run
yet** — first `plan` on a real customer tests the composite temp-id paths
(`adGroupCriteria/-3~-5`, `assetGroupListingGroupFilters/-3~-7`) and PMax asset ordering; record
its result here.
