# 16 — `metaops`: agent-facing launch interface

Reviewed 2026-09-29 (edit / rules / monitor / clone / core fixes, verified by the offline tests, not
all by live Graph); ACTIVE-default change 2026-09-25.

`metaops` is the preferred orchestration surface for an agent. It wraps the proven
`probe.py`, `launch.py`, `bulk.py`, `verify.py`, and `activate.py` implementations; it does not
reimplement Graph payloads. Underlying scripts are internal/debugging surfaces; their Graph
writes are rejected unless a workspace-bound `metaops` process launched them.

## Why this exists

- One stable command surface and JSON result schema for agents.
- Absolute paths and a child working directory fixed to the workspace project.
- Immutable input snapshots bound to the saved plan by SHA-256.
- Account/Page/dataset-specific `doctor` receipts bound to each plan.
- A per-state lock that prevents two launcher processes from creating against one state.
- `apply`/`bulk-apply` create/resume objects ACTIVE by default and spend on success — both
  refuse without the literal `--confirm SPEND`. A spec's top-level `"create_status": "PAUSED"`
  keeps creation and activation separate the old way, for a run that needs a review window.
- Default path creates the campaign PAUSED internally and flips it ACTIVE after the whole tree
  builds — a half-built tree never spends. ACTIVE creates refuse a past/offsetless `start_time`
  (re-date the spec, re-plan).
- Existing verification receipts remain the activation authority for a `create_status: PAUSED`
  run; the CLI cannot bypass them.

The official `meta-ads` CLI is proprietary and optional. The unrelated open-source
`meta-ads-cli` is also optional. Neither owns launches (`12`).

## Workspace contract

`workspace.json` is the portable, non-secret control plane. A profile binds one ad account to
its BM, Page/PBIA, dataset, catalog, product-set aliases, currency, and timezone. `app_id` and
`system_user_id` are OPTIONAL — declare them for a System User token (they gate the BM-ownership
checks and are hard-required for provisioning, below); a plain user token (own-BM admin, a
third-party developer app, or a scraped browser token, `02`) needs neither. `token_kind`
(`system_user` | `user` | `auto`, default `auto`) tells `assets verify` how to treat them: `auto`
inspects the token itself (`/debug_token`, falling back to `/me` vs. `/{business}/system_users`);
an explicit value skips that inspection. For a System User token every existing hard gate is
unchanged. For any other kind, `app_owned`/`system_user_assigned` become warnings (reported,
non-blocking) — BM ownership of a third-party app or a stale `system_user_id` isn't something a
plain user token can prove — while account access (`/me/adaccounts` with an ADVERTISE task on the
selected account), Page access (minting a Page token), and dataset attachment stay hard gates for
every kind. The asset receipt and `assets verify`'s JSON both record the resolved `token_kind`.
`doctor --scope provisioning`, `catalog create`, and every Business Manager
create/asset-assignment command still hard-require `system_user_id` and an Admin System User
token — they refuse with a clear message naming the missing key or the wrong role, never a bare
`/me` mismatch, when the profile has no declared System User. `blocked_accounts` can never be
selected. `instagram_user_id` defaults to `"auto"` (resolve the Page's PBIA; none → `doctor` WARNs, `launch.py` aborts; create it in the UI, `18`). 🔺 A dead/blocked account already sitting in the
selected profile disables metaops entirely — including read-only commands like `business assets`
and `workspace validate` — every command refuses with `profiles.X uses blocked account act_Y`
(field-observed 2026-09-22). There is then no metaops path to discover the replacement account
id; get it from the UI or a separate read-only Graph call and put it in `workspace.json`.
Credentials stay in the environment.
**Proxy under metaops:** the only way to run without `META_PROXY` is `workspace.json`
`defaults.allow_no_proxy: true` (must be a boolean); an exported `META_ALLOW_NO_PROXY=1` is dropped.
An in-process `SystemExit` (missing `META_TOKEN` / `META_PROXY`) becomes a JSON envelope under `--json`.
The CLI discovers the nearest `workspace.json` from the current directory upward; explicit
`--workspace` wins, followed by `METAOPS_WORKSPACE`.
Every lifecycle command requires a workspace; workspace-free legacy plans are not executable.
Account-agnostic: `workspace.json` lives in a per-launch project directory outside the skills
directory (one per BM/agency setup — holds `workspace.json`, `.metaops/`, `.notes/` with the
token env file). CLI rejects skill-store workspaces and state directories escaping the project.
Start from `scripts/specs/example-workspace.json`.
`workspace.json.api_version` must fall inside the launcher's supported window
(`graph.SUPPORTED_VERSIONS`, currently `v26.0` + `v25.0`; N-1 warns on stderr),
not merely match the `vNN.N` shape. Outside the window `metaops` rejects before
any Graph call; after a launcher-version upgrade, update the workspace and
re-plan and re-verify its receipts.

```bash
metaops --workspace . --profile <profile> --json workspace validate
metaops --workspace . --profile <profile> --json assets verify --scope core
# Catalog specs require: assets verify --scope all
metaops --workspace . --profile <profile> --json doctor
# Before any BM create/asset assignment: read-only Admin-System-User preflight
metaops --workspace . --profile <profile> --json doctor --scope provisioning
```

`--scope core` checks BM/app/System User/account/Page/PBIA/dataset; `--scope all` adds catalog +
every declared product set. A successful check writes a workspace-hash, profile, scope,
API-version, and timestamp-bound receipt; catalog specs require `all`, other specs accept `core`
or `all`. `plan` and every later lifecycle command refuse stale or changed receipts. Verification
makes no changes; generated state lives under workspace `.metaops/`.

If a product set is empty, inspect valid catalog IDs without leaving the interface:

```bash
metaops --workspace . --profile <profile> --json assets products --limit 100
metaops --workspace . --profile <profile> --json assets set-products \
  --set <workspace-alias> --retailer-ids <id1>,<id2> --confirm SET
metaops --workspace . --profile <profile> --json assets verify --scope all
metaops --workspace . --profile <profile> --json assets swap --map a1=<rid>,b1=<rid>[+<rid>] --watch --confirm SWAP
```

**Plan the swap in the spec:** `creative.swap_to: "T01"` (or a list for multi-product sets) on each
catalog ad. `plan` checks those SKUs exist with name/description/image (refuses otherwise, phase
`swap_targets_invalid`); `apply` prints the exact `assets swap --map … --watch` command to start at once
(`data.swap_map`). A catalog ad without `swap_to` is warned at plan and apply.

**`assets swap` = the white→target swap, one verdict per set** (`scripts/swapgate.py`). Start it with
`--watch` right after `apply` (background): it polls review every `--interval` s (300) up to
`--max-wait` (12 h) and swaps EACH set the moment its own ads turn ACTIVE. Never waits for delivery
(operator 2026-09-26: white must not spend). Keep it low-frequency: never lower `--interval` below
300 s (enforced: `--interval` below 300 is refused unless `METAOPS_PACE_OVERRIDE=1`), one watcher per account; on a throttle code it stops like every other command (§ Pacing). Per set:

| verdict | when | action |
|---|---|---|
| `ready` | every live ad on the set ACTIVE (rejected ones only warn) | swapped now |
| `waiting` | an ad on the set PENDING_REVIEW / IN_PROCESS / PREAPPROVED | polled (`--watch`), else exit 2 |
| `blocked` | headline/description not product macros, primary text not neutral (`--allow-message`), target item missing / empty name/description/image / rejected, set unused, every ad on it rejected, PAUSED ad with unknown review (`--paused-ok`), COLLECTION ad with < 4 items | exit 1, fix first |
| `done` | set already holds exactly the target | nothing (safe to re-run) |

Other sets never hold a set: a reject or a review elsewhere in the account is irrelevant.
`a1=T01+T02+T03` puts several products in one set (carousel/collection). `--revert` = target → white
(before a review request or a creative edit): no review wait, no text gate. `--dry-run` prints the
table with lifetime impressions. Exit: 0 swapped/done, 2 still waiting, 1 blocked. A duplicate filter
on another set (10803/1798073) is retried with an equivalent filter; the mutator fails unless the set's
members equal the requested ids (a wrong id would empty the set). `assets set-products` (repair) now
refuses while an ad on that set is in review (`--force`).

## Single-account lifecycle

From the package directory, install with `uv tool install .`. Without installation, use
`uv run --project /path/to/meta/meta-grey-ops metaops` before every argument shown below, or install
once with `uv tool install /path/to/meta/meta-grey-ops` (Python ≥3.11; deps from `uv.lock`).
Global flags precede the command. Put `--json` before the subcommand when an agent consumes it.
Child diagnostics go to stderr; stdout contains exactly one `metaops.result/v1` object.

```bash
metaops --workspace . --profile <profile> --json doctor
metaops --workspace . --profile <profile> --json media --image creative.jpg --video creative.mp4 [--manifest PATH]   # default .metaops/media/<profile>.json, overwritten each run
metaops --workspace . --profile <profile> --json plan --spec launches/mine.json
metaops --workspace . --profile <profile> --json apply --plan .metaops/plans/<plan>.json --confirm SPEND [--refresh-start <future ISO+offset>]   # --refresh-start: resume a partial build whose start_time passed; re-dates only not-yet-created ad sets, spec/plan unchanged
metaops --workspace . --profile <profile> --json verify --plan .metaops/plans/<plan>.json
metaops --workspace . --profile <profile> --json status --plan .metaops/plans/<plan>.json

# Only for a spec with "create_status": "PAUSED" (re-activating a later pause = edit status --status ACTIVE --confirm SPEND):
metaops --workspace . --profile <profile> --json activate --plan .metaops/plans/<plan>.json \
  --confirm-ui REVIEWED --confirm SPEND
```

`apply` creates every object ACTIVE by default — the create spends the moment it succeeds,
so `apply` requires the literal `--confirm SPEND` (same literal `activate` uses) and prints
the budget in major units and currency before the first create. Put `"create_status":
"PAUSED"` at the top of the spec to keep the old paused build + separate `activate` instead.

`doctor` must pass first; its account/Page/dataset-specific receipt is checked by every later command, but
the 24 h TTL (`METAOPS_DOCTOR_MAX_AGE_SECONDS` overrides) is enforced only by `apply`, `bulk-apply`,
`activate`, `bulk-activate` and `assets set-products`; `media`, `edit status`, `verify`, `review`,
`insights` still check the binding and ignore age. A DEFINITE failure of `doctor` deletes its receipt; a
definite failure of `assets verify` deletes the same-scope receipt (core too on a core failure). A local
cooldown, a throttle (17/613/4/32/80xxx) or an unknown-outcome error does NOT delete a passing receipt.
`apply` refuses an account with `account_status` != 1 (`plan` / `--dry-run` only WARN). The `plan` JSON
envelope carries `data.warnings`.
`activate --refresh-start` writes `start_overrides` into the state: re-run `verify` before a second `activate`.
The separate read-back receipt written by `verify` expires after one hour by default
(`METAOPS_VERIFY_MAX_AGE_SECONDS` overrides it): re-run `verify` immediately before activation if UI
review or scheduling took longer. This is a live GET-only check, not a rebuild.
Media upload needs a bound receipt (age ignored); product-set repair (`assets set-products`) needs a fresh (<24 h) one. Product-set repair performs
a live System User/catalog/set ownership check that permits an empty set, then invalidates any
old `all` asset receipt; rerun `assets verify --scope all` after repair.
`plan` snapshots the normalized spec, then runs the existing API `validate_only` path before
writing the artifact. Later source-file edits don't alter the saved plan; run `plan` again to
adopt them. As with `launch.py --dry-run`: campaign and creative payloads reach Meta; ad-set and
ad payloads are local-only until their parent IDs exist during `apply`.

Before `activate` (create_status: PAUSED runs only), complete every UI-only
check in `00` §6–7.5. The command requires `--confirm-ui REVIEWED`, the spec-bound verification
receipt, and literal `--confirm SPEND`. For the default ACTIVE flow those same UI-only checks
move before `apply --confirm SPEND` instead — there is no later paused gate.

## Feed (catalog as Google Sheet, `17`)

```bash
metaops --workspace . --profile <p> --json feed sync  --sheet <url> [--gid N] [--update-only] --confirm FEED   # POST /{feed_id}/uploads url=<csv export> → poll end_time
metaops --workspace . --profile <p> --json feed swap  --sheet <url> --file items.json --confirm FEED             # validate prospective rows → upsert → sync → prove no ad re-entered review
```

`feed_id` comes from `profiles.<p>.feed_id`; `--feed-id` is accepted only when the profile has no
declared feed. Sheet CSV export needs a public link; tab
gid resolves via `GSHEETS_JSON_KEY_FILE` or `--gid`. `swap` refuses while an ad that SHOWS the edited rows is
`PENDING_REVIEW`/`IN_PROCESS`/`PREAPPROVED`: ads on sets holding those ids, plus every rule-based set
(its membership can shift). Unrelated ads never hold it (`--force` overrides, `--paused-ok`); exit 1 + phase `re_review`
lists ads whose status flipped into review after the fetch. Result `data.upload`:
`num_persisted_items`, `num_invalid_items`, `error_count`, `errors[]`. `finished=false` = still
running after `--wait` (default 120 s); re-check `GET /{upload_id}`.

## Edit / clone / rules (wrap `edit.py`, `clone.py`, `rules.py`)

```bash
metaops … edit status  (--ids a,b | --state run.json --level adset | --all --level campaign) --status PAUSED|ACTIVE|DELETED --confirm PAUSE|SPEND|DELETE   # DELETED works with spend too; irreversible
metaops … edit budget  --ids … (--budget-minor N | --budget-pct ±N) [--force-step] [--confirm SPEND]   # only RAISES are capped at +20% (0.1% tolerance, rounding-safe) and get the late-day guard; a CUT up to -50% needs no --force-step, a deeper cut in one edit does; a budget below 1 minor unit is never posted (stop delivery with `edit status --status PAUSED`); --budget-pct must be numeric and > -100
metaops … edit rename  (--ids … --prefix P [--suffix S] | --name ID-NAME (one id) | --set ID=NAME [--set …])   # EXACT names (400 chars); --set ids must be numeric and inside the resolved ids, else it fails; a rename does not open a review, no confirm
metaops … edit bid     --ids <adsets> --bid-minor N --confirm BID [--dry-run]   # bid_amount (bid/cost cap); AD SETS only (probes optimization_goal), a non-ad-set id is refused before any POST
metaops … edit schedule --ids <adsets> [--start-time ISO] [--end-time ISO] --confirm SCHEDULE [--dry-run]   # AD SETS only; ISO with UTC offset required; a past --end-time is refused (pause instead)
metaops … edit ramp    --ids … --step 20 --confirm RAMP                              # exactly one rung; wait 48–72h before the next call
metaops … edit targeting (--ids … | --state run.json | --all) [--user-os …] [--publisher-platforms facebook,instagram] [--facebook-positions feed,story,facebook_reels] [--instagram-positions stream,story,reels] [--device-platforms mobile] [--age-min N] [--age-max N] [--genders 1,2] [--geo-regions 3879,…] [--advantage-audience 0|1] --confirm TARGETING [--dry-run]   # read-modify-write: GETs current targeting, merges only the given field(s), POSTs the whole object back — a delta POST wipes the rest (04). --dry-run prints before/after, no write. `--geo-regions` REPLACES the whole geo selection (keeps only regions + location_types) and is refused with `--all`. Advantage+ coupling is refused (advantage_audience 1 with age_min>25 or age_max<65). Empty values are rejected. A read-back that differs is reported `not_applied`, ok=false. `publisher_platforms` without instagram is refused (operator rule). More scalar fields: extend TARGETING_SCALAR_FLAGS/SCALAR_FIELDS.
metaops … edit tags|creative (--ids … | --state run.json | --all) [--url-tags STR] [--template-url URL] [--headline T] [--cta TYPE] [--message T | --message-file PATH] [--description T|""] [--caption DOMAIN|""] [--link URL] [--image-hash H] [--enhancements-off] [--allow-disapproved] --confirm TAGS [--dry-run]   # `creative` = alias of `tags`. `--enhancements-off` = clone WITHOUT `creative_sourcing_spec`, which switches off Ads Manager's default enrolments (e.g. `featured_offering_spec` "Show spotlights", which pulls website text into the ad); it is a new creative, so review re-opens. Clone-and-swap now works on Ads Manager-built creatives: their all-OFF defaults (`applink_treatment=web_only`, `destination_spec`, `creative_sourcing_spec`, `format_transformation_spec`, `media_sourcing_spec`) are treated as inert and omitted from the clone; an active flag or real content still blocks. An unreadable / foreign id is a clean per-id failure row (no traceback). Not yet applied live (2026-09-29): a real edit re-opens review, the operator decides. Empty strings are rejected except `--description ""` / `--caption ""`, which REMOVE the field. Ads that are DISAPPROVED or carry `ad_review_feedback` are skipped unless `--allow-disapproved` (do not pass it: operator rule). A no-op edit (identical link_data / url_tags / template_url_spec) is skipped. `--all` = ACTIVE ads only. The clone-and-swap probably creates a new post, so likes/comments of the old post are not carried over (unverified). url_tags is CREATE-only on AdCreative — clones the ad's creative with the tag changed, then swaps the ad onto it; old creative left unused, and if the swap fails after the clone the orphaned creative's id is reported so it can be found and cleaned up manually. Catalog/product creatives (product_set_id set) skip url_tags and take --template-url instead, or are skipped with a reason — same treatment for any creative carrying a field the clone cannot faithfully reproduce (a disclosure/disclaimer, a reference to an existing post, per-placement customization, …): SKIPPED, field named, never guessed at — refuses rather than ships a silently degraded ad. Every run warns: NAME macros ({{campaign.name}}/{{adset.name}}/{{ad.name}}) resolve from a first-publish snapshot (04) — renaming an object later never reaches an already-set tag; ID macros ({{campaign.id}}/{{adset.id}}/{{ad.id}}) are unaffected, ids are immutable.
metaops … clone campaign|adset|ad <id> [--times N] [--prefix/--suffix] [--start ISO] [--into-campaign/--into-adset] [--dry-run]   # /copies, level by level, PAUSED; skips deleted/archived children AND DISAPPROVED / WITH_ISSUES ads (listed under `skipped`; `clone ad` on one exits 1); `clone campaign --times N` enforces the 3 h create pacing (stops within the gap unless METAOPS_PACE_OVERRIDE=1)
metaops … rules ladder --target-minor N --event E --level ADSET|AD [--rungs 0-6] [--mode notify|pause] [--ids | --all-adsets] [--prefix] [--time-preset P] [--impressions-floor N] [--confidence X] [--schedule S] [--confirm RULES]   # `--mode pause` needs --ids or --all-adsets. Rule names carry a scope hash (level, event, ids, time_preset, currency, confidence, mode): the same name with different filters aborts, identical = idempotent skip
metaops … rules list | history [--since] | execute --rule-id ID [--live] --confirm EXECUTE | delete --prefix P --confirm DELETE   # `execute` refuses non-NOTIFICATION rules without --live
```

`edit status --all` keeps the wide kill-switch status list (also catches in-review objects
`IN_PROCESS`/`PENDING_REVIEW`/…), so a pause-all stops ads that would start delivering on approval;
`edit tags|creative --all` and `edit targeting --all` use ACTIVE only. ACTIVE / budget raise →
`--confirm SPEND`; PAUSED → `--confirm PAUSE`; `--mode pause` →
`--confirm RULES`; manual rule execution → `--confirm EXECUTE`; targeting change → `--confirm
TARGETING`; tag rewrite → `--confirm TAGS` (both required even under `--dry-run`, unlike the
others). For opaque IDs, the child reads back `account_id` and refuses an object outside the
profile. Children print a final `*.result/v1` JSON line that lands in `data`.

🔺 `edit tags|creative` swaps the ad onto a new creative. Whether a tag-only swap re-opens ad
review is unconfirmed (2026-09-18). A change to the visible copy — primary text, headline,
description, CTA, destination, image — is a new creative and Meta reviews it again (the ad goes back to
`PENDING_REVIEW`); treat every swap as a re-review: apply the `04` swap gate and re-check
`effective_status` after the run. `edit tags|creative` skips ads that are `DISAPPROVED` or carry
`ad_review_feedback` (operator rule: on a disapproval do not edit or resubmit) unless `--allow-disapproved`.

Edits and review: **text / image / link / headline / CTA edits re-open review; a rename does not**
(`rename`, field-checked 2026-09-29 on 3 approved ads: ACTIVE → IN_PROCESS → ACTIVE within ~15 s, no
review wait). **Targeting is NOT review-safe**: field 2026-09-22 a targeting edit put a live ad back through
review and it came back DISAPPROVED (`19` §4, `04`); treat placement / geo / age / device edits on a live
ad set the same way. Budget, bid and schedule: no review seen, schedule/bid not yet checked live. What an
`{{ad.name}}`/`{{campaign.name}}` url_tag macro records is a first-publish snapshot, so a rename never
reaches the tracker; `{{ad.id}}`/`{{adset.id}}` always follow the object — keep sub-ids on ids.

Coverage map (one command per lever): names `rename` · budget `budget`/`ramp` · bid `bid` · dates
`schedule` · status `status` · audience/placements/devices/geo `targeting` · ad copy, image, links,
tags `tags|creative` · `creative_sourcing_spec` / enhancements (Ads Manager default enrolments) only via `edit creative --enhancements-off` (clone-and-swap, re-review). Things with no command (UI or spec at create time): attribution window
(immutable after create, 1504040), optimisation goal, conversion event, pixel, billing threshold
(the threshold can be neither read nor set via API, UI only; Meta rolled back an operator change).

## Catalog lifecycle (`17`)

```bash
metaops … catalog create --name N [--vertical commerce] --confirm CREATE          # POST /{business}/owned_product_catalogs → put id in workspace.json
metaops … catalog list | access                                                   # owned catalogs; SU assigned_product_catalogs + business match
metaops … catalog feed create --name N --url <csv/sheet export> --schedule hourly|daily|weekly [--hour H] [--update-only] --confirm CREATE
metaops … catalog feed list | uploads [--feed-id]
metaops … catalog set create --name N (--filter f.json | --retailer-ids a,b) --confirm CREATE   # filter sent as dict, encoded once
metaops … catalog set list · products list [--set-id] [--limit]
metaops … catalog products batch --file items.json --method UPDATE|DELETE|CREATE [--wait s] [--force] [--paused-ok] --confirm BATCH   # items_batch item_type=PRODUCT_ITEM → check_batch_request_status; each item needs `id` (= retailer id; `retailer_id` is mapped). Same item gate as feed swap: refuses while an ad on a set holding these ids (or on a rule-based set) is in review
```

`catalog create` requires a token for an **Admin-role System User**. An Employee System User can
maintain a catalog explicitly assigned to it, but cannot create one at the BM edge; see `02` §2.
`workspace.json.api_version`: see the canonical Workspace contract above.
Run `doctor --scope provisioning` first. It verifies the token identity equals the profile's
`system_user_id` and its current BM role is `ADMIN`; `catalog create` repeats that read-only check
immediately before POST.

`schedule` is a JSON string (`interval HOURLY|DAILY|WEEKLY|MONTHLY, hour, minute, day_of_week,
timezone, url`). items_batch takes feed-format `price` "9.99 USD"; `/products` takes integer
minor units — the command passes the file through verbatim. Unverified: `status` strings of
`check_batch_request_status` (polled case-insensitively).

## Business Manager setup (no billing surface exists)

`business adaccount create`, `business pixel create`, `business pixel share`, `business user
invite|assign`, and `business partner share` are provisioning operations. They require the same
Admin System User check and repeat it immediately before their write. `business capi test` and
read-only listing do not require Admin.

```bash
metaops … business assets                                                          # owned/client accounts, pages, pixels, catalogs, system users
metaops … business adaccount create --name N --currency USD --timezone-id 1 [--end-advertiser B] --confirm CREATE   # new-BM cap = 1 (`03`)
metaops … business pixel create --name N [--is-crm] --confirm CREATE · pixel share --account act_X --confirm SHARE · pixel shared
metaops … business capi test --event Lead --test-code TESTxxxx [--url …]           # /{dataset}/events, hashed dummy user_data → Events Manager "Test events"
metaops … business user invite --email E --role EMPLOYEE|ADMIN --confirm SHARE
metaops … business user assign --user-id U --asset adaccount|page|pixel --tasks … --confirm SHARE   # /assigned_users {user,tasks}; pixel: ADVERTISE,ANALYZE,EDIT,UPLOAD
metaops … business partner share --partner-business B --asset adaccount|page|pixel --tasks … --confirm SHARE       # /agencies {business,permitted_tasks}
```

## Operate

```bash
metaops … review [--state run.json | --ids a,b | --all] [--previews --format DESKTOP_FEED_STANDARD,MOBILE_FEED_STANDARD]   # ad_review_feedback, issues_info; exit 1 on DISAPPROVED/WITH_ISSUES
metaops … review --tree [--campaign ID] [--statuses A,B]   # read-only campaign > ad sets > ads in one call (see Inspect below); exit 1 on DISAPPROVED/WITH_ISSUES
metaops … monitor --accounts accounts.json [--stall-impressions 40] [--telegram] [--log] [--out-json rows.json]   # global `--json` remains before `monitor`; TG_BOT_TOKEN + TG_CHAT_ID env only; this IS the live spend/status sweep across accounts; a mid-sweep GraphError adds an `ERROR` verdict (non-zero exit); a stale `--out-json` is deleted before the child runs
metaops … comments list [--ads a,b | --all]                                               # Page token, read-only
metaops … comments hide --ads a,b|--all (--matching REGEX | --all-comments) --confirm HIDE
metaops … comments delete --ads a,b|--all --matching REGEX --confirm DELETE
metaops … page show | set --avatar f --cover f --about "…" --website URL --confirm PAGE | list-pages
metaops … insights pull --level ad (--date-preset yesterday | --since --until) [--csv] [--breakdown publisher_platform,platform_position] [--time-increment 1|7|monthly|all_days] [--action-attribution-windows 7d_click,1d_view | --click-window 1|7|28] [--fields reach,outbound_clicks]   # default: 1d click / 1d view, one row per day, rows in the account tz; the flags are validated locally (see Inspect below)
metaops … insights leaderboard --accounts accounts.json [--date-preset] [--top N] [--csv]            # joins on ad_name only when all rows have one currency
metaops … insights fatigue [--days 14] [--min-spend 20] [--event offsite_conversion.fb_pixel_lead]   # per ad, own baseline half vs recent half: ROTATE-CANDIDATE (freq +20% ∧ CTR −20% ∧ CPC/CPA +20%) / WATCH / OK / NO-DATA; reach/frequency/POSSIBLE-SATURATION come from a second ad-set-level pull per half (time_increment=all_days, one row per half) — never summed from the daily ad rows, since reach is unique users; never pauses
metaops … activity --since D [--until D] [--event-types A,B] [--limit N]   # read-only account activity log, newest first (see Inspect below)
metaops … images list [--since D] [--unused] [--limit N]                    # read-only adimages joined to the ads that use each hash
```

Live-verified 2026-09-03 on an own BM (System User, Admin): workspace validate, assets verify (core/all),
doctor, business assets/pixel shared/capi test, catalog list/access/set list/feed list/uploads/products
list, rules ladder (notify) → list → history → delete, review (+previews), clone --dry-run, edit status,
insights pull/fatigue, page show, comments list, monitor, feed sync (`POST /{feed_id}/uploads` on a public
Google Sheet: 4 items persisted in 11 s). catalog products batch (UPDATE, handle returned; status `started` = in progress). Not yet live:
catalog/business/set/feed *create*, clone without --dry-run, edit budget/ramp, edit targeting/tags,
comments hide/delete, page set, feed swap.

## Inspect: account tree, placement pulls, activity log, image library (read-only)

Added 2026-09-29. Offline tests with a mocked `graph.get` (`scripts/test_inspect_features.py`). Live smoke
on CF1 the same day (coordinator): `activity`, `images list` and `insights pull --breakdown
publisher_platform,platform_position` worked; the first `review --tree` (nested expansion) was wrong and was
rebuilt on flat edges, which has NOT been run live yet. The unverified list below is what no live call
has covered. GET only:
`cmd_inspect.py` imports no write path (a test pins it). `--profile` is the global flag and goes before
the command; `--json` prints one envelope, without it the handler prints a text table/tree first.

**`review --tree [--campaign ID] [--statuses A,B]`.** Three FLAT paged edges, `act_…/campaigns`,
`act_…/adsets`, `act_…/ads` (100/50/100 rows per page, each with the `effective_status` filter and its
own cursor), joined in Python on `campaign_id` / `adset_id`. **No nested `adsets{ads{}}` expansion:**
live on CF1 (2026-09-29) it returned an empty `ads` list for 4 of 5 ad sets whose ads were all ACTIVE,
with or without an `effective_status` modifier, while flat `/ads` returned all five. Guards: a page that
fails to load fails the command (no partial success); a load that hits its cap (1000/3000/5000 rows) or a
repeated cursor is `complete=false`, ok=false, phase `incomplete`, and the "no blocking" message is
never printed; a row whose parent is not in the loaded set goes under `unattached` (JSON `unattached`,
text `U UNATTACHED`) instead of vanishing; header counts are what was loaded, with `loaded` alongside
when `--statuses` pruned; an ACTIVE ad set with no ads gets a warning. With `--campaign`: the campaign
node plus `{id}/adsets` and `{id}/ads`. Graph code 1 "reduce the amount of data": the same request once
more with 25/15/25 rows for the rest of the run, a second one raises.
Fields per object: `id, name, status, effective_status, configured_status`; campaign `daily_budget,
lifetime_budget, bid_strategy, objective`; ad set `daily_budget, lifetime_budget, bid_amount, bid_strategy,
optimization_goal, billing_event, start_time, end_time, learning_stage_info, attribution_spec` (null =
account default: this is "the ad set's own window") and a targeting summary (geo, age, genders,
publisher_platforms, positions, device_platforms, advantage_audience); ad `issues_info,
ad_review_feedback, creative{id,name}, updated_time`. JSON keeps money as minor-unit ints plus `currency`
/ `currency_offset` (read from `act_…?fields=currency`); text is an indented tree, one line per object,
amounts in the account currency, `!! DISAPPROVED`, `!! WITH_ISSUES`, `!! FEEDBACK {…}`, `!  ISSUES`. Exit 1
(kind `ad_review`) when any ad is DISAPPROVED/WITH_ISSUES, same as flat `review`. `--statuses` (default:
everything except DELETED) filters the ads server-side and keeps campaigns/ad sets that carry one of the
values themselves plus the parents of every shown object (so `DISAPPROVED,WITH_ISSUES` still reaches a
rejected ad under an ACTIVE campaign). `--campaign` reads that node and refuses one whose
`account_id` is not the profile's. Excludes `--state/--ids/--all/--previews`.

**`insights pull` flags.** All validated locally, before any call:
- `--breakdown`: allow-list `country, region, dma, age, gender, publisher_platform, platform_position,
  device_platform, impression_device, hourly_stats_aggregated_by_advertiser_time_zone|audience_time_zone`
  (names read from the SDK 26.0.1 enum). Unknown or repeated names are rejected. Which combinations Meta
  forbids is not documented in this repo, so none is rejected locally: Graph answers a bad one with code
  100 on a GET; the only local hint is an advisory for `platform_position` without `publisher_platform`.
- `--time-increment 1|7|monthly|all_days`: `all_days` for a placement/geo read (reach then deduplicated by Graph).
- `--action-attribution-windows 7d_click,1d_view` (allowed `1d_click, 7d_click, 28d_click, 1d_view, 1d_ev`)
  or the shorthands `--click-window 1|7|28` / `--view-window 1`. `7d_view`/`28d_view` are refused: Meta dropped
  them on 2026-01-12 and the API returns a silent empty set (meta-ads/08 §12). The CSV gets one
  `actions:<type>:<window>` column per window.
- `--fields a,b`: extra columns added to the default set, allow-list `insights.EXTRA_FIELDS`.
- Transport is unchanged: sync GET + cursor paging through `graph.call`, so the `x-fb-ads-insights-throttle`
  / usage headers are read on every page (sleep at 85 %), a throttle code sets the cooldown and is never
  retried. Extra: code 1 is retried once with `limit` 500 -> 100.
- Placement join with Keitaro: pull `--breakdown publisher_platform,platform_position --time-increment
  all_days` at ad level, report Keitaro by `sub11` (`placement={{placement}}`, `25`), same days and
  currency. Meta returns two columns, the macro one string; the only macro value documented here is
  `Facebook_Mobile_Feed`, so the **mapping of `platform_position` names to `{{placement}}` values is
  unverified**: build the key by hand and check one day. Breakdown rows are for reading, never a cost push.

**`activity --since D [--until D] [--event-types A,B] [--limit N]`.** `GET act_…/activities`, fields
`event_time, event_type, translated_event_type, object_id, object_name, object_type, actor_id, actor_name,
extra_data, application_name`. `YYYY-MM-DD` is a UTC day (`--until` day inclusive), ISO datetimes work;
`since`/`until` go to Graph as unix seconds and are enforced again locally. Pages of 200 (50 after a code
1), scan cap 5000 events (`truncated` + warning). Sorted newest first locally, `--limit` (default 200, max
2000) keeps the newest. `--event-types` filters client-side (the edge has no such filter; a typo matches
nothing and the warning lists the types seen). `extra_data` is parsed into `extra` when it is JSON. Summary
counts by event type, actor and application. Use: who touched the account before/after a disable (`23`).

**`images list [--since D] [--unused] [--limit N]`.** `act_…/adimages` (`name, hash, created_time, status,
width, height, original_width, original_height, permalink_url`; the signed `url` is never requested)
joined to `act_…/ads{id,name,effective_status,creative{id,name,image_hash,object_story_spec,asset_feed_spec}}`
on every hash found in the creative. Per image: `used, ad_count, active_ad_count, ads[]`; `--since` filters
`created_time`, `--unused` keeps hashes no scanned ad references. Costs about ceil(images/100) + ceil(ads/50)
GETs (ad scan cap 5000, warning when hit). UNUSED is not "safe to delete": an ad on an existing Page post
carries no hash and DELETED ads are not scanned. `metaops media` stays the upload command.

Unverified (names below exist in the SDK 26.0.1 enums; not covered by the CF1 smoke):
- payload size vs code 1 on a large account (if
  Graph tags that code 1 `is_transient`, `graph.call` re-sends the same request up to 4 times before the
  smaller retry runs);
- `configured_status` on campaigns/ad sets, `learning_stage_info`, `attribution_spec`, `permalink_url` on
  `adimages` (dropped once on a code 100 naming it), `application_name` and `extra_data` (JSON with
  old/new value is assumed) on `activities`;
- `activities`: unix-seconds `since`/`until`, whether the edges are inclusive, order, log retention;
- which statuses the edges return when no filter is sent (we always send an explicit list, ARCHIVED included);
- `1d_ev` as the engaged-view window token; combination rules for breakdowns; the placement mapping above.

## Keitaro (cost push + per-ad join)

```bash
metaops … keitaro push   [--days 3 | --since D --until D] [--keitaro-campaign ID] [--keitaro-currency USD] [--readback-wait 45] [--confirm PUSH]   # no --confirm = dry run
metaops … keitaro report [--days 3 | --since D --until D] [--keitaro-campaign ID] [--by ad|adset|day]
```

- Workspace-bound: the ad account is the profile's (`--profile` works before or after `keitaro`). The Keitaro campaign
  is `--keitaro-campaign` or the OPTIONAL profile field `keitaro_campaign_id` (numeric string; workspaces without it
  stay valid). Env only: `KEITARO_URL` (base, https), `KEITARO_API_KEY` (`Api-Key` header), optional
  `KEITARO_CURRENCY` (Keitaro base currency). Missing variables give an envelope naming them (exit 2).
- `--days N` = trailing N days in the AD ACCOUNT tz, today included (partial day, overwritten by the next run).
- `push`: 1 account read (tz, currency) + ad-level insights (`time_increment=1`, all effective statuses via
  `filtering`) + an account-level total for the same days (a third, campaign-level pull only when there is a gap).
  Sends `POST /clicks/update_costs`, one request per day, one entry per (ad, day) `filters:{sub_id_6:"<ad_id>"}`
  in account tz/currency; then reads Keitaro cost back and prints FB spend vs Keitaro per day. The dry run also
  reads the campaign cost model and what Keitaro stores now, and writes the exact bodies to
  `<state>/keitaro/push-<act>-<stamp>.json` (artifact `payload`); `--json` inlines `data.entries`.
- Flags per day: `no_clicks` (spend on an ad with zero Keitaro clicks: lost), `not_stored`, `delta` (> 3%).
  `unattributed` = account total minus sum of ad rows: reported loudly, never pushed (`data.unattributed`,
  `remainder_candidates`, `partial_gaps`; why: `tracker-ops/01`). Readback lag or a bounded poll that does not
  settle is a warning, exit 0; do not re-push, re-read with the dry run.
- Warns when the campaign cost model is CPA/CPS with auto ON (fake cost); the campaign is only ever read.
- `report`: FB spend per ad joined with Keitaro `sub_id_6`: clicks, leads, sales, cost, `sale_revenue`; regs =
  leads + sales, deps = sales, cost/reg, cost/dep, ROI on `sale_revenue`. `conversions` is never requested,
  `lead_revenue` is printed as a sanity check (must be 0), `{{…}}` macro and empty `sub_id_6` rows are excluded
  and counted apart. `cost` is Keitaro's (base currency), `fb_spend` the account's.
- Transport: `urllib`, 20 s timeout, ambient proxy variables ignored, redirects refused, no retry on 4xx/5xx or
  timeout, ONE retry after a connection reset before any response (an update_costs overwrite is repeatable). A
  failed push stops, names the pending days and is safe to re-run. Facebook calls keep the Graph pacing/cooldown.
- **Verified live 2026-09-29:** `report/build` accepts the dimensions `day`, `sub_id_6`, `sub_id_11` and the measures
  `clicks`, `leads`, `sales` (rows returned). Observed `sub_id_11` (placement) for FB feed clicks: `Facebook_Mobile_Feed`;
  unsubstituted `{{placement}}` and `{sn_placement}` values appear on test/bot clicks, so a literal macro in `sub_id_11` is a
  test click, not a placement.
- Not live-tested (built offline): `update_costs` date format, deleted-ad rows on
  the account edge, bot-click skipping, readback lag, campaign cost-model field names. List and first-use routine:
  `tracker-ops/01` Cost push.

## Bulk lifecycle

```bash
metaops --workspace . --json bulk-plan \
  --template specs/mine.json --accounts accounts.json --run wave-1 [--only act_X,act_Y]
metaops --workspace . --json bulk-apply --plan .metaops/plans/<bulk-plan>.json --confirm SPEND --verify
metaops --workspace . --profile <profile> --json status --plan .metaops/plans/<bulk-plan>.json
```

`bulk-apply` creates every tree ACTIVE by default and spends per account on success, so it
requires the same literal `--confirm SPEND` as `apply`. A template's top-level
`"create_status": "PAUSED"` keeps every tree paused instead; per-row `overrides` may not set
`create_status`. Bulk rows select their own profile (no `--profile`). `bulk-apply` creates every
row in one run — to publish in waves, one `bulk-plan --only act_X` per wave.

## Pacing (FIELD 2026-09-27; enforced in code)

One account with the heaviest write load (4 CBO launches, two an hour apart, 10 ad sets/10 ads, then a
~12-min 17/2446079 retry storm at 60→300 s, $43 lifetime) was disabled "automation that doesn't follow
our rules"; siblings on the same System User token/Page/domain lived. Cause not proven (`02` §8).
Limited/dev tier ≈ 300 calls/h per ad account, ~300 s block; Graph docs: stop calling after a limit.

- Max **one new campaign create per account per ~3h**. Several trees for one account = several windows,
  not one `apply` burst or `clone --times N`.
- After a create: **one** read-back (`verify`/`status`), no polling loop. Monitoring sweeps (`monitor`,
  `insights`) at ≥15 min spacing.
- Throttle code (17 / 2446079 / other rate-limit codes, `05`) → stop, **≥30 min per-account
  cooldown**, no retry loop.
- Weak/new account (thin spend history): smaller first tree; optionally the first launch in the UI.

Code (`graph.py`, state `~/.metaops/pacing.json`, shared by every workspace/process):
- Any throttle (17/613/80xxx per account; 4/32 app/user → global) raises at once, no sleep-retry, and
  sets a cooldown of max(30 min, BUC `estimated_time_to_regain_access`). Every later call touching that
  account (path `act_…`, or the last account seen in the process) raises `CooldownError` locally —
  code 17, nothing sent, outcome known. Env: `METAOPS_THROTTLE_COOLDOWN_MIN`.
  Account context = the `--profile` ad account (exported to child scripts as `METAOPS_ACCOUNT_CONTEXT`);
  with no context an account-level throttle on an object path cools only that object, never every account.
- 613/**4841018** "1 calls per 30 seconds" is per OBJECT (live 2026-09-27: DELETE right after create): one
  35 s wait + one retry, no cooldown.
- `launch.py` refuses a NEW campaign (`PacingError`, before anything is created) if the account got one
  < 3 h ago; resumes of an existing state are not blocked. Env: `METAOPS_CREATE_GAP_HOURS`.
- `metaops pace` = cooldowns + last create per account (no API call); `--clear-cooldown act_…` (ids
  are normalised; `"*"` clears all; the state is printed afterwards) only when the operator asks.
  `METAOPS_PACE_OVERRIDE=1` bypasses both, and the `assets swap --interval` floor and the
  `clone campaign --times N` gap — only to pause a bleeding campaign or on the operator's explicit ask.
  `pacing.json` is written via a per-process tmp file + flock.

For a multi-account DLO/catalog template, prove one real tree first, then pass `--dlo-tested`
to `bulk-apply`. For a `create_status: PAUSED` template, activate one reviewed account at a
time; there is deliberately no activate-all command:

```bash
metaops --workspace . --profile <profile> --json bulk-activate \
  --plan .metaops/plans/<bulk-plan>.json --account act_123 \
  --confirm-ui REVIEWED --confirm SPEND
```

`bulk-activate` revalidates fresh doctor and asset receipts for the selected account only;
an unrelated sibling's expired receipt does not block it. The complete batch input, workspace,
item identities, and state bindings remain hash-validated.

## Risk snapshot, token classes and `token import`

**`doctor --risk`** (read-only; needs a workspace profile, not `--whoami`) appends an account / pixel / Page / ads
snapshot and `risk_findings` to the doctor output and to `data.risk` / `data.risk_findings` (`--json`). It adds 5-10 reads
(account, account "unverified" fields in a separate GET, pixel, Page, `act_X/ads` pages of 200, at most `ads_max_pages`),
stops at the first throttle, and can never change the doctor verdict or the receipt. Findings are `{level: info|warn|high,
code, message}`. Defaults, overridable in a `risk` block (workspace top level, then `profiles.<p>.risk`; unknown keys are
refused): account under 14 days (`min_account_age_days`), lifetime `amount_spent` under 50 in the account currency, no FX
(`min_amount_spent`), pixel never fired or under 3 days old (`min_pixel_age_days`), Page followers under 100
(`min_page_followers`), disapproved ratio of ads created in the last 30 days at or above 20% (`max_disapproved_ratio`; 50%
= high; under `min_ads_for_ratio` ads it is only info), `account_status` != 1 (high, with the `disable_reason` name), unpublished
Page (high), `spend_cap` at 90% of `amount_spent` (warn) or reached (high), no funding source (high). **These are the
operator's own priors; no Meta source ties them to Spam disables; a clean snapshot proves nothing.** The billing threshold has no API
field and is not evaluated (UI only). Fields never read live by this codebase (SDK-declared only: `created_time`,
pixel `creation_time` / `last_fired_time` / `is_unavailable`, Page `followers_count`, ad `created_time`; `age` and
`min_daily_budget` in their own GET) are listed in `data.risk.unverified_fields`, together with the assumed minor-unit
offsets. Ads are counted client-side from `created_time`; which statuses the default read of the edge omits is unverified.

**Token routing** (`02` §5 has the matrix): `META_TOKEN` (ads, default), `META_TOKEN_BUSINESS`, `META_TOKEN_CATALOG`,
`META_TOKEN_EVENTS`, `META_TOKEN_RULES`; cookies shared in `META_COOKIES`, per token `META_COOKIES_<BUSINESS|CATALOG|EVENTS|RULES>`;
workspace `defaults.token_envs` renames a variable. A capability with no variable of its own uses `META_TOKEN` only if its
class carries it, else the command exits naming the variable and the class that fits. Ads writes refuse an EAAd (no ad-object access); EAAB, EAAI, EAAG and EAAH are allowed, a real ad-set
rename + restore worked with each on the own BM 2026-09-29 (EAAH: #10 on another BM, so it depends on the BM). `METAOPS_ALLOW_TOKEN_CLASS=EAAd,…`
overrides; `<VAR>_APP_ID` records a confirmed own-app token.
`doctor` prints a **token class** row (warns when an EAAB has no `META_COOKIES` / `META_USER_AGENT`, or the `c_user`
cookie is not the `/me` id), asks `GET /app` instead of `debug_token` for first-party prefixes (which answer #100), skips the
scope gate for an EAAH (`/me/permissions` #10), and with several token variables set prints a **token table** (variable,
class, app, user, valid, provides, still missing for this profile, `NO-COOKIES` on a class that needs them; 2 calls per extra token, `data.tokens`).
Cookie facts (live 2026-09-29): EAAB / EAAI / EAAG / EAAH answer code 1 without `META_COOKIES`, an EAAd reads without them, no class needs a
User-Agent (the extension exports none), so `doctor` and `token import` warn only about missing cookies and never for an EAAd.
`assets verify` recognises a scraped prefix as a user token with one `GET /app`.

**`token import`** (`pbpaste | metaops token import --env-file PATH`, details `02` §5): takes one block or the five FB Helper blocks
in one paste (one token per class, shared cookies; first failure stops everything, nothing written), verifies each with `/me` + `/app`,
gates by class (unknown → `--allow-unknown`), routes each class to its variable, writes once, atomically at 0600 with a `.bak`,
prints only class, app, user, `EAAB…wxyz`, cookie names and the path; without `--env-file` it is a dry run. `token` is not a
workspace lifecycle command and needs no workspace (`offline_ok`: it runs before any token exists). Log redaction keeps `c_user`
(the user id) readable and masks every other cookie value.

## Failure contract

- Non-zero child exit: `ok=false`, child exit code preserved, redacted diagnostics on stderr.
  An in-process `GraphError` is kind `graph` with exit 1 (was 2); `graph_error` carries the LAST error,
  int `code`, and `outcome_unknown`. A `SystemExit` (missing `META_TOKEN` / `META_PROXY`) is turned into
  a JSON envelope under `--json`.
- Timeout or unknown POST outcome: inspect the state `in_flight` entry and reconcile before a
  retry (`outcome_unknown=true`: a non-idempotent create is raised once, never retried; GETs and
  `idempotent=True` calls are retried on transient errors). Do not remove the lock or marker merely to
  force progress. Graph paths containing `.`, `..`, empty segments, `% ? # \`, whitespace or control
  characters are rejected before any request.
- Throttle (17/2446079 …): no retry; ≥30 min per-account cooldown (§ Pacing).
- A saved snapshot or bound doctor receipt changed after `plan`: command refuses; create a new
  doctor receipt and plan. Editing the original source does not mutate an existing plan.
- Existing `.metaops.lock`: another process owns that state. Inspect its PID/timestamp; only
  remove a stale lock after confirming no launcher process is running.
- API version changed: old plan is refused; create a new plan under the pinned version.
  `META_API_VERSION` must look like `vNN.N` (a warning outside v25/v26).
- Header `x-fb-ads-insights-throttle` is read like the other usage headers (pause at 85%).

Offline checks:

```bash
SKILL_ROOT=/path/to/meta/meta-grey-ops
PYTHONDONTWRITEBYTECODE=1 uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/test_metaops.py"
PYTHONDONTWRITEBYTECODE=1 uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/test_workspace.py"
PYTHONDONTWRITEBYTECODE=1 uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/selftest.py"
uv run --isolated --project "$SKILL_ROOT" ruff check --no-cache "$SKILL_ROOT/scripts"
uv lock --check --offline --project "$SKILL_ROOT"
```
