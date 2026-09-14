# 04 — `ttops`: the guard rail around MCP (and a write path for bulk)

Reviewed 2026-09-14. Offline suite: 102/102 passing (`python3 -m ttops.selftest`).
Live-verified against a real ad account: **not yet** — every command below is exercised by the
offline suite and by dry runs; none has been run against a production advertiser at time of writing.
Treat the first live run as a test, on a throwaway campaign, with a small budget.

## What this is

**Not a replacement for the official MCP server.** MCP does the work (`01`). `ttops` is the guard
rail MCP does not have, plus a deterministic write path for the cases MCP is a bad fit for.

Two of its commands are the ones you will actually use every day, and **both run offline with no
token and no network**:

| Command | When | Catches |
|---|---|---|
| `preflight` | **before** you call any MCP create tool | invalid enums, Meta bid-strategy names, budget below the currency floor or with illegal decimals, CBO with ad-group budgets, filter-only goals, a `billing_event` that does not match the optimization goal, missing `pacing`/`promotion_type`/`schedule_start_time`, half-specified attribution windows — and emits the exact tool arguments with `operation_status: DISABLE` already set |
| `audit` | **after** MCP created objects, on the read-back JSON | anything **live that should not be**, budget violations, rejections, lost asset authorization, unbound pixels, objects missing from the read-back, and drift between spec and what TikTok actually stored |

**`audit` judges exactly what you paste in and says so.** Hand it one ad group and it reports on one
ad group — and marks the result incomplete rather than green, because a clean ad group tells you
nothing about a campaign that might be live. Read back all three levels before treating a pass as a
pass.

## What `ttops` refuses to build, and where to build it instead

Each of these has its own endpoints and its own activation semantics. `preflight` rejects them with
the reason rather than emitting a payload that creates a different product than the one planned.

| Shape | Why | Use instead |
|---|---|---|
| **Reach & Frequency** (`RF_REACH`) | TikTok requires `operation_status` `ENABLE` or omitted at create — incompatible with the create-paused guarantee. Ad groups use `/adgroup/rf/create/` with a reservation flow | Ads Manager, or MCP `rf_*` tools, with the spend approved **before** creation |
| **Smart+** (`campaign_type` `SMART_PERFORMANCE_CAMPAIGN`) | `/smart_plus/*` endpoints, separate review and preview flow, and a ≤1 write per 5 seconds per ad limit | MCP `smart_plus_campaign_create` / `_adgroup_create` / `_ad_create` |
| **GMV Max / TikTok Shop sales** (`PRODUCT_SALES` + `campaign_product_source: STORE`) | GMV Max is its own object with its own bidding; an ordinary Shop-sales payload is the wrong product | MCP `campaign_gmv_max_create`, `gmv_max_bid_recommend_get` |

For all three: build through MCP, then **read the objects back and run `ttops audit`** on them. The
audit has no spec to diff against in that case, but the danger checks — live when it should not be,
budget below the currency floor, rejections, lost asset authorization — all still apply.

Offline matters: an operator who cannot register a developer app (company domain + website required)
has MCP access and no token at all. These two still work for them.

The remaining commands need a token and exist for bulk, unattended runs, and operations MCP does not
wrap.

## If you only have MCP, this is your whole chapter

No install, no workspace, no token, no network. Stdlib-only Python ≥3.9:

```bash
SKILL=~/.claude/skills/tiktok-ops     # add tiktok/ before it if installed nested
alias ttops="PYTHONPATH=$SKILL/scripts python3 -m ttops"
```

```bash
# 0. before writing any budget for an unfamiliar currency
ttops budget-check --currency JPY --level adgroup

# 1. validate the spec and get the arguments for each MCP tool, in order
ttops --json preflight --spec specs/mine.json --currency JPY --advertiser-id 7123456789

# 2. …run campaign_create / adgroup_create / ad_create through MCP with those arguments…

# 3. read back with campaign_get / adgroup_get / ad_get, save to readback.json, then
ttops --json audit --spec specs/mine.json --actual readback.json --currency JPY
```

`--currency` replaces a workspace entirely — it is the only thing the offline checks need. With a
workspace present, drop it and pass `--profile`.

`audit` is liberal about input: paste a whole tool result, its `data`, a bare list, one object, or a
hand-assembled file holding all three levels. It works **without `--spec`** too — the danger checks
do not need one, which is the normal case when a campaign was built conversationally.

Severity ladder, worst first: `SPENDING` (live right now and you did not intend it — pause first,
diagnose second) · `MONEY` (budget violates the currency's floor or precision) · `BLOCKED`
(rejected, missing qualification, lost asset authorization, unbound pixel, transcoding failure) ·
`MISSING` · `DRIFT` (platform stored something else) · `UNCONFIRMED` (spec set it, read-back does not
report it — verified neither way) · `WARN` · `INFO`.

With a `--spec`, **every field the spec sent is compared, at all three levels** — including bid
fields, the four attribution windows, the engagement toggles, and the ad's destination URL, creative
asset and identity. A campaign whose ad points somewhere else is the failure this catches.

Post-activation, invert the expectation: `ttops audit --actual readback.json --expect-live` flags
anything that should be serving and is not.

```bash
ttops tools                                    # lifecycle step → MCP tool name
ttops explain AD_STATUS_ASSET_AUTHORIZATION_LOST   # decode a secondary_status
ttops explain 40100                                # decode a return code
```

`explain` takes either a numeric return code or a `secondary_status` string. The status table is the
one that matters at 2 a.m.: `AD_STATUS_AUDIT_DENY` is a **rejection** while `AD_STATUS_AUDIT` is a
pending review, and `AD_STATUS_ASSET_AUTHORIZATION_LOST` on an ad is usually an expired Spark code
killing a winning ad — on an ad *group* TikTok will not say which asset, so identify it before
acting. Full table: `05` § secondary statuses.

That is the entire MCP-only surface: `budget-check`, `preflight`, `audit`, `explain`, `tools`. All
offline, all tokenless.

---

# The token path — bulk, unattended, and operations MCP does not wrap

**Everything below needs a developer-app token.** An MCP-only operator can stop reading here.

## Why the full lifecycle exists at all

| Problem | What `ttops` does |
|---|---|
| TikTok's `operation_status` defaults to **ENABLE** — an omitted field creates a live campaign | Forces `DISABLE` at every level. No spec field overrides it |
| A successful create is not proof the object holds what you sent | `verify` / `audit` read back and diff |
| A dropped connection on a create may or may not have applied | Every create recorded **in state before the POST**; a killed run refuses to continue and asks you to reconcile instead of duplicating |
| A budget in the wrong currency spends 100× | Validates against TikTok's per-currency verification ratio and precision before any call |

Stdlib-only Python ≥3.9. No install, no virtualenv, no dependencies.

## Install and invoke

```bash
SKILL=~/.claude/skills/tiktok-ops     # add tiktok/ before it if installed nested

# No install — run it from anywhere:
PYTHONPATH=$SKILL/scripts python3 -m ttops --json <command>

# Or install the console script once:
uv tool install $SKILL      # then just: ttops --json <command>
```

Credentials come from the environment **only**. Never put a token on the command line — it lands in
shell history and in the process list.

```bash
export TIKTOK_ACCESS_TOKEN='...'      # Marketing API advertiser token; does NOT expire
```

## Workspace

`workspace.json` is the non-secret control plane: it binds one ad account to its currency, timezone,
pixel and identity. It lives in **your project directory, never in the skill directory** — `ttops`
refuses a workspace under the skill tree so an updated skill never carries someone's live bindings.

```bash
mkdir -p ~/work/tiktok-clientA && cd ~/work/tiktok-clientA
cp $SKILL/specs/example-workspace.json ./workspace.json
$EDITOR workspace.json
ttops --json workspace validate
```

`currency` and `timezone` must match the ad account exactly. `doctor` checks both against
`/advertiser/info/` and fails on a currency mismatch, because every budget bound derives from it.
`blocked_advertiser_ids` can never be selected — put accounts that must not be touched there.

Discovery order: `--workspace` > `TTOPS_WORKSPACE` > nearest `workspace.json` walking up from cwd.

## The lifecycle

```
doctor → plan → apply → verify → activate
```

Each step gates the next with a **receipt**: a timestamped record bound to the advertiser, the plan
hash and the state hash. Receipts expire — `doctor` after 24h, `verify` after 1h — because an hour-old
read is not evidence about what is live now. Override with `TTOPS_DOCTOR_TTL` / `TTOPS_VERIFY_TTL`
only when you can say why.

```bash
ttops --json doctor
ttops --json plan     --spec specs/mine.json
ttops --json apply    --plan .ttops/plans/<plan>.json
ttops --json verify   --plan .ttops/plans/<plan>.json
ttops --json activate --plan .ttops/plans/<plan>.json \
      --confirm-reviewed REVIEWED --confirm SPEND
```

**`doctor`** — read-only access preflight. Checks, each separately: the token is real; **this
advertiser is in the token's own advertiser list** (not merely readable); account currency and
timezone match the workspace; account status and balance; and that the pixel is **linked to this ad
account** — being shared to the Business Center is not the same thing. A successful GET proves none
of this.

**`plan`** — validates the spec, normalises it to exact payloads, and snapshots it with a hash.
Nothing reaches TikTok. Editing the source spec afterwards does not change a saved plan; run `plan`
again to adopt edits. The output prints every budget in **major units with the currency named** —
that string is what you put in front of the operator.

**`apply`** — creates campaign → ad groups → ads, all `DISABLE`. Resumable: re-running the same plan
creates only what is missing, never duplicates. If state holds an in-flight create (a POST whose
outcome is unknown), `apply` refuses until you reconcile against Ads Manager by hand. That refusal is
the feature.

**`verify`** — reads every object back and diffs objective, budget, bid, goal, placements, schedule,
pixel and status against what was sent. Any `operation_status` that is not `DISABLE` is flagged
`severity: SPENDING`. Writes the receipt `activate` requires.

**`activate`** — the only command that causes spend. Requires `--confirm-reviewed REVIEWED` and
literal `--confirm SPEND`, plus a verify receipt bound to this exact plan *and* this exact state.
Enables bottom-up — ads, then ad groups, then campaign — so nothing serves until every child is
deliberately on. Status updates batch at TikTok's 20-ID cap.

## Operate

```bash
ttops --json report --level ad --days 7 --csv day.csv
ttops --json report --level campaign --start 2026-09-01 --end 2026-09-13 --metric video_watched_6s
ttops --json sweep  --stall-impressions 50
ttops --json review --ids 17000...,17000...
ttops --json status --level adgroup --ids a,b --set DISABLE --confirm PAUSE
ttops --json status --level adgroup --ids a,b --set ENABLE  --confirm SPEND
ttops --json budget --level adgroup --id 17000... --amount 120 --confirm SPEND
```

`report` returns rows plus the account's **timezone and currency**, because a portfolio spanning GEOs
does not agree on what "yesterday" means. `budget` reads lifetime spend first and enforces TikTok's
**105%-of-spend floor** before writing — a cut below that line is rejected by TikTok, which otherwise
surfaces as an unexplained error. `sweep` flags `REJECTED`, `IN_REVIEW`, `STALL` (impressions with
zero clicks) and `NO_DELIVERY`.

## Offline commands

`budget-check`, `preflight`, `audit`, `explain` and `tools` need no token and no network — they are
documented above in the MCP-only chapter and work identically on the token path. Plus:

```bash
ttops --dry-run --json plan --spec specs/mine.json   # validate a plan, make no calls
```

## Result envelope

stdout carries exactly one object when `--json` is set; diagnostics go to stderr.

```json
{ "schema": "ttops.result/v1", "ok": true, "command": "verify", "data": { } }
```

Exit codes: `0` ok · `1` command-level failure (with detail in `data`) · `2` TikTok API error (with
cause and action from the catalog) · `3` workspace/spec rejected · `4` transport/runtime · `5`
unexpected.

## Failure contract

| Symptom | What it means and what to do |
|---|---|
| `Refusing to plan/apply: no doctor receipt` | Run `doctor`. It expired or was never run for this advertiser |
| `Refusing to activate: verify receipt …` | The state changed after `verify`, or the receipt aged out. Re-run `verify` immediately before activating |
| `state has in-flight creates` | A POST's outcome is unknown. Check Ads Manager, write the real IDs into the state file, then re-run `apply`. **Never delete the marker to force progress** |
| `Another ttops process owns this state` | A lock exists. Confirm no launcher is running before removing it — removing a live lock is how you get duplicates |
| `Plan targets advertiser X but profile is Y` | Wrong `--profile`, or a plan from another account |
| `spec.currency … != account currency` | The spec was written for a different account. Do not "fix" it by editing the currency field; re-derive the budgets |
| Write refused as read-only | A read-phase client tried to POST. That is a bug in calling code, caught at the transport |

## Transport behaviour worth knowing

- **TikTok signals throttling in the body: HTTP 200 with `code` 40100/40133/40016.** `ttops`
  branches on the body code and never on HTTP status. Rate-limit backoff starts at 20s and caps at 300s, because TikTok's QPM
  penalty window is five minutes and hammering makes it strictly worse.
- **Writes are never auto-retried.** A dropped connection on a create may have applied. The client
  raises with the outcome marked UNKNOWN and leaves reconciliation to you.
- Auth-dead codes (40102/40104/40105/40106) never retry — they escalate.
- A read-only client physically cannot POST to a write path, so a mistake fails loudly instead of
  spending.

## Extending it

New campaign shape → extend `spec.py` (validation + normalisation) and add a test to `selftest.py`.
Do **not** hand-assemble a payload at the call site: the whole point is that one module owns what
gets POSTed, and that its rules are tested offline before a token is ever involved.

```bash
PYTHONPATH=$SKILL/scripts python3 -m ttops.selftest   # must be green before you ship a change
```
