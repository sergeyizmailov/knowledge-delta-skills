# 16 — `metaops`: agent-facing launch interface

Reviewed 2026-09-03; ACTIVE-default change 2026-09-25.

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
selected. `instagram_user_id` defaults to `"auto"` (resolve the Page's PBIA; none → blocked, create it in the UI, `18`). 🔺 A dead/blocked account already sitting in the
selected profile disables metaops entirely — including read-only commands like `business assets`
and `workspace validate` — every command refuses with `profiles.X uses blocked account act_Y`
(field-observed 2026-09-22). There is then no metaops path to discover the replacement account
id; get it from the UI or a separate read-only Graph call and put it in `workspace.json`.
Credentials stay in the environment.
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
300 s, one watcher per account; on a throttle code it stops like every other command (§ Pacing). Per set:

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

`doctor` must pass first; its account/Page/dataset-specific receipt is checked by every later command and
expires after 24 hours by default (`METAOPS_DOCTOR_MAX_AGE_SECONDS` overrides the TTL).
The separate read-back receipt written by `verify` expires after one hour by default
(`METAOPS_VERIFY_MAX_AGE_SECONDS` overrides it): re-run `verify` immediately before activation if UI
review or scheduling took longer. This is a live GET-only check, not a rebuild.
Media upload and product-set repair also require that fresh receipt. Product-set repair performs
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
metaops … edit budget  --ids … (--budget-minor N | --budget-pct ±N) [--force-step] [--confirm SPEND]   # ±20%/late-day guard from edit.py
metaops … edit rename  --ids … --prefix P [--suffix S]
metaops … edit ramp    --ids … --step 20 --confirm RAMP                              # exactly one rung; wait 48–72h before the next call
metaops … edit targeting (--ids … | --state run.json | --all) [--user-os …] [--publisher-platforms facebook,instagram] [--facebook-positions feed,story,facebook_reels] [--instagram-positions stream,story,reels] --confirm TARGETING [--dry-run]   # read-modify-write: GETs current targeting, merges only the given field(s), POSTs the whole object back — a delta POST wipes the rest (04). --dry-run prints before/after, no write. More scalar fields: extend TARGETING_SCALAR_FLAGS/SCALAR_FIELDS.
metaops … edit tags (--ids … | --state run.json | --all) (--url-tags STR | --template-url URL) --confirm TAGS [--dry-run]   # url_tags is CREATE-only on AdCreative — clones the ad's creative with the tag changed, then swaps the ad onto it; old creative left unused, and if the swap fails after the clone the orphaned creative's id is reported so it can be found and cleaned up manually. Catalog/product creatives (product_set_id set) skip url_tags and take --template-url instead, or are skipped with a reason — same treatment for any creative carrying a field the clone cannot faithfully reproduce (a disclosure/disclaimer, a reference to an existing post, per-placement customization, …): SKIPPED, field named, never guessed at — refuses rather than ships a silently degraded ad. Every run warns: NAME macros ({{campaign.name}}/{{adset.name}}/{{ad.name}}) resolve from a first-publish snapshot (04) — renaming an object later never reaches an already-set tag; ID macros ({{campaign.id}}/{{adset.id}}/{{ad.id}}) are unaffected, ids are immutable.
metaops … clone campaign|adset|ad <id> [--times N] [--prefix/--suffix] [--start ISO] [--into-campaign/--into-adset] [--dry-run]   # /copies, level by level, PAUSED; skips deleted/archived children
metaops … rules ladder --target-minor N --event E --level ADSET|AD [--rungs 0-6] [--mode notify|pause] [--ids] [--prefix] [--confirm RULES]
metaops … rules list | history [--since] | execute --rule-id ID --confirm EXECUTE | delete --prefix P --confirm DELETE
```

`edit status --all` also catches in-review objects (`IN_PROCESS`/`PENDING_REVIEW`/…), so a
pause-all stops ads that would start delivering on approval. ACTIVE / budget raise →
`--confirm SPEND`; PAUSED → `--confirm PAUSE`; `--mode pause` →
`--confirm RULES`; manual rule execution → `--confirm EXECUTE`; targeting change → `--confirm
TARGETING`; tag rewrite → `--confirm TAGS` (both required even under `--dry-run`, unlike the
others). For opaque IDs, the child reads back `account_id` and refuses an object outside the
profile. Children print a final `*.result/v1` JSON line that lands in `data`.

🔺 `edit tags` swaps the ad onto a new creative. Whether that re-opens ad review is unconfirmed —
no source found either way (2026-09-18). Treat it as if it does: apply the `04` swap gate (every
affected ad out of review; no delivery wait), and re-check `effective_status` after the run.
A silent return to review stalls delivery on a live ad with no error.

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
metaops … monitor --accounts accounts.json [--stall-impressions 40] [--telegram] [--log] [--out-json rows.json]   # global `--json` remains before `monitor`; TG_BOT_TOKEN + TG_CHAT_ID env only; this IS the live spend/status sweep across accounts
metaops … comments list [--ads a,b | --all]                                               # Page token, read-only
metaops … comments hide --ads a,b|--all (--matching REGEX | --all-comments) --confirm HIDE
metaops … comments delete --ads a,b|--all --matching REGEX --confirm DELETE
metaops … page show | set --avatar f --cover f --about "…" --website URL --confirm PAGE | list-pages
metaops … insights pull --level ad (--date-preset yesterday | --since --until) [--csv]
metaops … insights leaderboard --accounts accounts.json [--date-preset] [--top N] [--csv]            # joins on ad_name only when all rows have one currency
metaops … insights fatigue [--days 14] [--min-spend 20] [--event offsite_conversion.fb_pixel_lead]   # per ad, own baseline half vs recent half: ROTATE-CANDIDATE (freq +20% ∧ CTR −20% ∧ CPC/CPA +20%) / WATCH / OK / NO-DATA; reach/frequency/POSSIBLE-SATURATION come from a second ad-set-level pull per half (time_increment=all_days, one row per half) — never summed from the daily ad rows, since reach is unique users; never pauses
```

Live-verified 2026-09-03 on an own BM (System User, Admin): workspace validate, assets verify (core/all),
doctor, business assets/pixel shared/capi test, catalog list/access/set list/feed list/uploads/products
list, rules ladder (notify) → list → history → delete, review (+previews), clone --dry-run, edit status,
insights pull/fatigue, page show, comments list, monitor, feed sync (`POST /{feed_id}/uploads` on a public
Google Sheet: 4 items persisted in 11 s). catalog products batch (UPDATE, handle returned; status `started` = in progress). Not yet live:
catalog/business/set/feed *create*, clone without --dry-run, edit budget/ramp, edit targeting/tags,
comments hide/delete, page set, feed swap.

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
- `metaops pace` = cooldowns + last create per account (no API call); `--clear-cooldown act_…` only
  when the operator asks. `METAOPS_PACE_OVERRIDE=1` bypasses both — only to pause a bleeding campaign or
  on the operator's explicit ask.

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

## Failure contract

- Non-zero child exit: `ok=false`, child exit code preserved, redacted diagnostics on stderr.
- Timeout or unknown POST outcome: inspect the state `in_flight` entry and reconcile before a
  retry. Do not remove the lock or marker merely to force progress.
- Throttle (17/2446079 …): no retry; ≥30 min per-account cooldown (§ Pacing).
- A saved snapshot or bound doctor receipt changed after `plan`: command refuses; create a new
  doctor receipt and plan. Editing the original source does not mutate an existing plan.
- Existing `.metaops.lock`: another process owns that state. Inspect its PID/timestamp; only
  remove a stale lock after confirming no launcher process is running.
- API version changed: old plan is refused; create a new plan under the pinned version.

Offline checks:

```bash
SKILL_ROOT=/path/to/meta/meta-grey-ops
PYTHONDONTWRITEBYTECODE=1 uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/test_metaops.py"
PYTHONDONTWRITEBYTECODE=1 uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/test_workspace.py"
PYTHONDONTWRITEBYTECODE=1 uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/selftest.py"
uv run --isolated --project "$SKILL_ROOT" ruff check --no-cache "$SKILL_ROOT/scripts"
uv lock --check --offline --project "$SKILL_ROOT"
```
