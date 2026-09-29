# 02 — Access: app, scopes, tokens, MCP vs API vs CLI

Reviewed 2026-09-14 (scrape prefixes, Power Editor live scopes); 2026-09-29 (all five scraped classes probed live, token routing, `token import`); 2026-09-02 vs
developers.facebook.com (permissions, system-users, ads-ai-connectors); claude-code
issues #57191/#62376. API **v26.0** (2026-07-29); pin `/v26.0/` in every call — unversioned rejected.
Marketing API versions end ~12 months after release (v24.0 → 2026-10-06; v25/v26 TBD); Graph core
~2yr (v24 → 2028-02-18, v25 → 2028-07-29). Marketing calls follow the Marketing clock [official,
2026-09-25].

Versions re-checked 2026-09-29 against the Graph changelog: v24.0 2025-10-08 (available until 2026-10-06), v25.0
2026-02-18, v26.0 2026-07-29 (v25/v26 end dates TBD). `META_API_VERSION` must look like `vNN.N`.

Owner of every access fact in paid-media; `meta-ads/13` keeps clean-lane governance.

## 0. Which pipe

| Pipe | What | Use for | Not for |
|---|---|---|---|
| **Marketing API via `metaops`** (internal `scripts/`) | Workspace-bound Graph calls, System User or long-lived user token | **every agent launch and write.** Only surface with confirmed control of `attribution_spec`, `degrees_of_freedom_spec`, `contextual_multi_ads`, `asset_feed_spec`, catalog/template creatives, `validate_only`, batching | direct low-level script writes |
| **Meta Ads MCP** (`mcp.facebook.com/ads`) | Meta-hosted, 106 tools, bearer System User token w/ `ads_mcp_management` or OAuth; per-account rollout flag | reads: insights, anomaly/benchmarks, entity search, previews, catalog/pixel diagnostics, Ad Library; bounded edits (`ads_update_entity`) | launches — §6 |
| **Meta Ads CLI** (`pip install meta-ads`, `12`) | click CLI over `facebook-business` SDK, `ACCESS_TOKEN` | human-operator inspection/diagnosis | **all agent writes**: no workspace binding, spend gates, `validate_only`, multi-account, resume, read-back diff, currency guard, proxy; SDK video host deprecated (#701) |
| Third-party Meta MCP servers (pipeboard, hashcott, brijr, ScaleForge…) | community wrappers | nothing | shared dev apps + raw tokens + unsupervised writes = reported ban mechanism [practitioner-multiple]; never hand a work token to one |
| CSV bulk import | Ads Manager | human review of thousands of rows | agents: no validate_only; blocked on fresh accounts (3738001) |

Rule: **agent writes → workspace-bound `metaops`.** Skill-critical defaults (SKILL.md § Launch
defaults) are enforceable only via `launch.py`. If forced through MCP: build PAUSED, read every
ad set/creative back through API (`verify.py --state` accepts hand-written state) before
activation.

## 1. Operator handoff checklist (once, BM owner)

Agent needs **one token + ids**; the rest is BM-owner setup:

1. **Developer app** (Business type), golden use cases only (extras invite audits): `Create &
   manage ads with Marketing API` · `Measure ad performance data with Marketing API` · `Manage
   everything on your Page` · `Manage products with Catalog API` · `Create & manage ads with ads
   MCP server` (only for MCP). App **Live** (Privacy Policy URL 200) — dev mode blocks creative
   create (1885183). Contested: FIELD 2026-09-27 a BM-owned dev-mode app's System User token
   (Limited tier) created 10 ads on 3 own accounts without 1885183 — go Live anyway.
2. **Admin System User** whenever the agent must create a catalog or dataset/pixel, claim an
   asset, or assign assets in this portfolio (Employee only for least-privilege work on
   preassigned assets, §2). Assign **Full control** on every ad account, Page, IG account,
   pixel/dataset, catalog, and the app. Per-asset — portfolio membership assigns nothing. Before
   provisioning: `metaops --workspace . --profile <name> --json doctor --scope provisioning`.
3. **Generate token**, expiry Never (System User default; 60-day exists), scopes §3. Store once,
   gitignored.
4. **Pixel attached to every ad account** (Datasets → Add assets → ad account). Shared-to-BM ≠
   attached; fails 1815045.
5. Page: System User (or app) needs ≥ADVERTISER per Page — PBIA edge needs a Page token from that
   role.
6. EU geo: `default_dsa_beneficiary`/`default_dsa_payor` on account, or DSA fields per spec (`04`).
7. Recommended: **Require App Secret** + hand agent `META_APP_SECRET` — `appsecret_proof` on every
   call makes a leaked token useless elsewhere.

```
META_TOKEN=<system user token>      META_APP_SECRET=<optional>
ad accounts: act_..., act_...        pages: ...   pixel/dataset: ...   catalog: ...
currency/tz per account: USD / America/Los_Angeles ...
tracker campaign URL + macro mapping: ...
```

First command: `metaops --workspace . --profile <name> --json doctor --whoami` (runbook step 1).
Nothing else until exit 0.

### 1.1 Several BMs: one app per BM, one token per BM (docs-verified 2026-09-22)

- **An app has exactly ONE owning Business Portfolio**, chosen at creation; moving = transfer
  (facebook.com/business/help/236817717885919). Other BMs get non-owning access only.
- **Token = System User of one BM.** System User and app in the same BM; Generate-token lists only
  apps that BM owns/installed. No token spans several BMs.
- Another BM's ad account reaches your token only via partner share → assign to your System User
  (`03`); otherwise outside-BM assets need **Full** tier (App Review + Business Verification).
  Own-BM: Limited tier, no review.
- **Default: separate app + Admin System User + token per healthy BM** — a ban stays inside one
  BM. App fate on BM disable is undocumented; assume it dies.
- Never connect an app to a BM with `is_disabled_for_integrity_reasons: true`
  (`GET /{business_id}?fields=is_disabled_for_integrity_reasons`).
- "Don't connect a portfolio yet" is reversible but no System User token until connected. Cap: 15
  apps per developer not tied to a verified BM.

## 2. System User roles: Admin vs Employee

OAuth scopes and BM role are separate gates — `catalog_management` + `business_management` do
**not** make an Employee an admin.

| System User role | Can do | Cannot do |
|---|---|---|
| **Employee** | Operate ad accounts, existing catalogs, Pages, other assets explicitly assigned in Business Settings. Valid least-privilege choice for launching into preassigned accounts or maintaining a preassigned catalog. | Provision/reassign BM-owned assets: create catalog or dataset/pixel, claim, assign to others. `POST /{business_id}/owned_product_catalogs` fails before scopes help. |
| **Admin** | Above + provision/administer BM-owned catalogs, datasets/pixels, asset assignments. | Still needs app scopes, asset access, access tier. |

**[R, reported 2026-09-03] Catalog-creation trap:** Employee calling `POST
/{business_id}/owned_product_catalogs` → `OAuthException` code **10**, subcode **1690129**, even
with `catalog_management` + `business_management` ("not an admin of this business"; text is
localised — branch on code/subcode). Revalidate against the intended BM. Admin for autonomous
BM-level create/assign; don't over-privilege an operate-only agent.

`metaops doctor --scope provisioning` (read-only): compares `GET /me` with workspace
`system_user_id`, reads `GET /{business_id}/system_users?fields=id,name,role`, requires that
System User be `ADMIN`. Re-checked immediately before `catalog create` and every BM
create/asset-assignment command.

## 3. Scopes

Verify **granted** via `GET /me/permissions` (use-case bundling grants extras —
`facebook_branded_content_ads_brand`, `threads_business_basic`; requested ≠ granted).

| Scope | Why | Required |
|---|---|---|
| `ads_management` | create/update campaigns/ad sets/ads/creatives | yes |
| `ads_read` | reads + Insights + CAPI send (distinct permission) | yes |
| `business_management` | BM assets, System User mgmt, catalog dependency | recommended |
| `read_insights` | Page/app insights | recommended |
| `pages_manage_ads` | Page-backed ads, click-to-message (PBIA) | recommended |
| `pages_read_engagement`, `pages_show_list` | Page identity reads (dependencies) | recommended |
| `pages_manage_metadata`, `pages_manage_posts` | Page avatar/metadata edits (#283 without), posts | if job edits Pages |
| `instagram_basic` | IG professional identity reads | if real IG account used |
| `catalog_management` | product sets, feed swaps — granted on Business-type Live apps for own-BM catalogs without review (2026-08-30) | catalog launches |
| `leads_retrieval` | lead-form data; needs Full access tier | lead forms only |
| `ads_mcp_management` | MCP server scope | MCP pipe only |

Own-business assets: Limited tier + these scopes. Other businesses': Full tier (App Review with
screencasts). Docs: `developers.facebook.com/docs/permissions`.

## 4. Access tier (renamed 2026-05-04)

"Ads Management Standard Access" → **Marketing API Access Tier**; Standard→**Limited**,
Advanced→**Full**. Full after **≥500 calls in 15 days, <15% errors over last 500**, via App
Review upgrade (Marketing API → Ads Management Standard Access); Business Verification
prerequisite, Privacy Policy URL checked [doc-confirmed 2026-09-02]. Tier belongs to the **app**,
not the BM — a verified agency BM doesn't lift your app. Read `ads_api_access_tier` in
`X-Business-Use-Case-Usage` (`meta-ads/14`).

## 5. Token types and lifecycle

| Token | Lives | Dies when | Proxy rule |
|---|---|---|---|
| **System User** (preferred) | until revoked ("Never") or 60d if chosen | admin revokes, app secret rotated w/ proof enforced, System User removed | BM/operator's assigned egress; no proxy only when direct current-IP access is intentional: under `metaops` that is workspace `defaults.allow_no_proxy: true` (an exported `META_ALLOW_NO_PROXY=1` is dropped) |
| Long-lived user (~60d) | 60 days | **login session dies** — logout, password change, security rotation, multi-session flag | must exit antidetect profile's IP (`01`) |
| Short user (Explorer) | ~1–2h | expiry | exchange immediately |
| Page token | derived per call | parent dies | same as parent |
| Events Manager "Generate access token" | CAPI dataset only | — | **not an ads token; never launch with it**. Reverse works: System User token w/ Full control on dataset POSTs to `/{dataset_id}/events` |

`metaops` accepts every row except CAPI-only. `profiles.<p>.token_kind` (`system_user` | `user` |
`auto`, `16`) tells `assets verify` which credential acts; `auto` (default) inspects the token.
System User: every asset-ownership gate hard. User token (own-BM admin, third-party developer app,
or scraped EAAB): "app is BM-owned" and "`system_user_id` assigned" downgrade to warnings; account
access (`/me/adaccounts` ADVERTISE task), Page access, dataset attachment stay hard. So
`app_id`/`system_user_id` are optional for user-token profiles
(`scripts/specs/example-workspace-user-token.json`). Provisioning (`doctor --scope
provisioning`, `catalog create`, BM assignment) always requires a declared Admin
`system_user_id` — a user token cannot provision (§2).

### [W] User token — end-to-end (when System User token unavailable)

| Source | Lifetime | Exchangeable | appsecret_proof | Use |
|---|---|---|---|---|
| **EAAB… scraped from Ads Manager session** (`13`) | until logout / password change / checkpoint | **no** — Meta's own app (Power Editor 119211728144504) | no | needs the session's cookies (`META_COOKIES="c_user=...; xs=..."`, verified 2026-09-29: none → `code 1: Invalid request`); the User-Agent is not required on the same IP (default and another browser's UA passed); another IP untested, so keep the profile's `META_PROXY` |
| **User token from YOUR developer app** (Explorer or FB Login) | 1–2h → long-lived 60d | yes, with that app's id+secret | yes | preferred user-token path; no cookies |

**[K] First-party scrape prefixes — each a different Meta app, scopes fixed.** One login yields all
five (live 2026-09-29); they do not stack in one token. Another surface's token does **not** upgrade an
EAAB (Commerce Manager won't add `catalog_management`), so each lives in its own variable and serves
the capability it carries (matrix and routing below; `scripts/tokens.py` is the single table).
Identify with `GET /app` (same cookies+proxy): a 4-char prefix only encodes the magnitude of the app id,
so an own-app or System User token can start with the same letters. A class is **confirmed** only by the
app id. `GET /app` names (2026-09-29): EAAB "Power editor", EAAI "Ads Manager", EAAG "Business
Manager", EAAH "Products", EAAd "Ads Events Manager".

| Prefix | Where (view-source / F12) | What | Launch / catalog |
|---|---|---|---|
| **EAAB** | Ads Manager (`accessToken="` or `window.__accessToken`) | Power Editor **119211728144504**, autolaunch default (`13`). Live 2026-09-14: `ads_management`, `ads_read`, `business_management`, Page scopes; **no** `catalog_management` / `ads_mcp_management` / `instagram_basic`. Debugger `Valid: True` ≠ working: no cookies → code 1 (trace `opes_mids`); self-`debug_token` → 100. `validate_only` write hit **190/459** | ads yes with the cookies (2026-09-29: a real ad-set rename + restore, `validate_only` write); catalog **feeds/uploads no** (`#10`), catalog **content** yes without the scope — `POST /{catalog_id}/items_batch` (`item_type=PRODUCT_ITEM`), `POST /{catalog_id}/product_sets`, set `filter` edits (2026-09-22). Dead `/{catalog_id}/batch` returns a misleading `#10` |
| **EAAI** | Billing `facebook.com/ads/manager/account_settings/account_billing`, search `access_token:` | [practitioner, cpa.rip 2021] claimed "wider than EAAB"; dies on logout; Dolphin imports EAAB not EAAI. Scopes not live-verified | `META_TOKEN_RULES`. 2026-09-29: `GET act_ID` and `GET act_ID/adrules_library` answer (empty list); a **real** ad-set rename + restore worked (activity log: "via Ads Manager"); no cookies → code 1; rule create/execute not run |
| **EAAH** | Commerce Manager (`business.facebook.com/commerce/…`, F12 → `graph.facebook.com` request) | App **515496645328243 "Products"** (2026-09-26, two farm BMs). `/me/permissions` → **#10**, self-`debug_token` → 100. Needs cookies + egress | catalog content writes (`metaops catalog products batch`, `catalog set create`, 2026-09-26); ad account/campaign reads. `META_TOKEN_CATALOG`. 2026-09-29: `GET /me/businesses`, `GET {business}/owned_product_catalogs` and `GET act_ID` answer; a **real** ad-set rename + restore worked on the own BM, which contradicts the older "ads writes fail #10" report (another BM, 2026-09-26): it depends on the BM, works on the own one; no cookies → code 1. `/me/permissions` #10 is not re-probed: `doctor` skips the scope gate for this class |
| **EAAG** | BM Settings e.g. `business.facebook.com/settings/people`, search `EAAG`; FB Helper grabs it on `business.facebook.com` pages when no EAAB is present | App **436761779744620 "Business Manager"** (live 2026-09-27, `GET /app`). `/me/permissions` live 2026-09-27: **81 granted**, incl. `ads_management`, `ads_read`, `ads_mcp_management`, `ads_agentic`, `attribution_read`, `agentic_checkout_account_linking`, `business_creative_insights(_share)`, `business_creative_management`, `business_creative_transfer` (first 10 alphabetically seen; rest not recorded) — far wider than EAAB. BM-surface token; **not** the Events Manager CAPI token | `META_TOKEN_BUSINESS`. 2026-09-29: `GET /me/businesses` (own BM), `GET act_ID` answer; a **real** ad-set rename + restore worked (activity log: "via Business Manager"); one PAUSED create + delete worked earlier (extension notes); no cookies → code 1. As `META_TOKEN` only via `token import --as-ads` when no EAAB exists |
| **EAAd** | Events Manager (`business.facebook.com/events_manager2`, FB Helper) | App **2094176354154603 "Ads Events Manager"** (live 2026-09-29, `GET /app`). The pixel node reads and the ad account node reads, but reading the ad **set** node answers **code 10** "Permission Denied": no ad-object access. The empty-batch probe (`POST /{pixel}/events` with `data: []` answering "must be non-empty") passes = auth confirmed, and a real test event (`metaops business capi test --event ViewContent --test-code TEST…`) returned `events_received: 1` on 2026-09-29, so events are **verified** for EAAd (test events only; a production event was not sent). **The only scraped class that reads without cookies and without a User-Agent** (verified 2026-09-29). Not the manual CAPI dataset token below | `META_TOKEN_EVENTS`; ads writes with it are refused |

**Capability matrix** (evidence: **V** verified live with the date, **C** claimed by extension notes or a practitioner,
**U** unverified, — not evidenced). Live probes 2026-09-29 (the operator, one user, five fresh tokens, Mac, no proxy): round 1 read-only
plus `validate_only`; round 2 a **real reversible ad-set rename** (write, read back, restore), the no-cookies test, a UA test
and the empty-batch CAPI probe. Not probed: `/me/permissions`, a real CAPI event, any other IP.

| class | ads read | ads write | business read | catalog | events write | rules | cookies required |
|---|---|---|---|---|---|---|---|
| **EAAB** | V 09-14, 09-29 | V (launches; real rename 09-29) | V (`business_management` 09-14) | V content only: `items_batch`, sets (09-22); feeds/uploads #10 | C (empty-batch probe 09-29) | U | yes, V 09-29 (none → code 1) |
| **EAAI** | V 09-29 | V (real rename 09-29, "via Ads Manager") | — | — | — | C (`adrules_library` list reads 09-29; create/execute not run) | yes, V 09-29 |
| **EAAG** | V 09-29 | V (real rename 09-29, "via Business Manager"; PAUSED create + delete earlier) | V 09-29 | — | — | — | yes, V 09-29 |
| **EAAH** | V 09-29 | V on the own BM (real rename 09-29); older report: #10 on another BM | V 09-29 | V (content writes 09-26; `owned_product_catalogs` 09-29) | — | — | yes, V 09-26 and 09-29 |
| **EAAd** | account node only; ad set node → code 10 (09-29) | refused (cannot even read the ad set) | — | — | C (pixel node reads and empty-batch probe 09-29; no event posted) | — | **no**, V 09-29 (reads) |
| System User (own app) | V | V | V | V | V (`02` §5) | U | no |

The User-Agent is required by no class: EAAB works with the default UA and with another browser's UA on the same IP (no proxy);
a different IP is untested, and the extension exports no UA, which is fine.

`metaops` acts on this table (`scripts/tokens.py`): nothing is listed without evidence, and "U" rows are
reported as unverified in `doctor` and `token import` instead of being trusted.

**Routing: one variable per capability** (`scripts/graph.py` `resolve_token`; only `META_TOKEN` is required):

| capability | variable | used by |
|---|---|---|
| ads read/write | `META_TOKEN` (default) | launch, edit, clone, activate, insights, doctor |
| business read | `META_TOKEN_BUSINESS` | `business assets`, `business pixel shared` |
| catalog | `META_TOKEN_CATALOG` | `catalog *`, feed uploads, `assets set-products` / `swap` set reads |
| CAPI events | `META_TOKEN_EVENTS` | `business capi test`, doctor's dataset probe |
| rules | `META_TOKEN_RULES` | `rules *` (`rules.py`) |

A capability without its own variable uses `META_TOKEN` only when META_TOKEN's class carries it; otherwise
the command exits naming the missing variable and the class that fits (EAAB carries all six, at the
evidence levels above, so a single-EAAB setup behaves as before). Cookies: `META_COOKIES` is shared (same
login = same session); `META_COOKIES_<BUSINESS|CATALOG|EVENTS|RULES>` is optional and wins for that
token. `META_USER_AGENT` is shared. Workspace `defaults.token_envs` (`{business_read|catalog|events_write|rules: ENV_NAME}`)
renames a variable. `<VAR>_APP_ID` (written by `token import`) records the confirmed app id and beats the prefix
guess. `mcp.py` stays on `META_TOKEN`: the MCP needs `ads_mcp_management` (granted to an EAAG, MCP with it untested).

**Ads-write guard** (any non-GET on the ads slot): EAAd is **refused** (no ad-object access). EAAB, EAAI, EAAG and EAAH are
allowed, silently: a real write worked with each on the own BM (the slot convention stays: EAAB in `META_TOKEN`, the others in
their variables; a `warn` policy exists in `graph.py` for a class only partly proven, none uses it now). A System User token that only shares a prefix is
cleared by `token import --allow-unknown` (records `META_TOKEN_APP_ID`) or `METAOPS_ALLOW_TOKEN_CLASS=EAAd`.

**`metaops token import`** — `pbpaste | metaops token import --env-file PATH [--name VAR] [--profile P] [--no-verify]
[--allow-unknown] [--force] [--as-ads] [--cookies-suffix [S]] [--dry-run]`. Reads the FB Helper block (token, blank
line, cookie header; or `META_TOKEN=… META_COOKIES=… META_USER_AGENT=…`, a `User-Agent:` line, the extension's
cookie JSON). **One paste may hold the blocks of all five classes** (each with the same cookies): every token must be of a
different class (two EAAB, or two unknown, are refused); each is verified in order (2 calls each), the first failure of any kind
stops the run with nothing written, and the file is written once. The cookies and UA are shared; cookie blocks of different
logins (`c_user` differs) or different UAs are refused, differing sets of one login keep the last complete one with a warning.
`--name` and `--cookies-suffix` are single-token flags. An unknown-class token wants `META_TOKEN` like an EAAB: not together. Without `--env-file` it is a
dry run. Verification is `GET /me?fields=id,name` + `GET /app?fields=id,name` (2 calls, no retries, no `debug_token`)
through `META_PROXY` with the pasted cookies and UA; it refuses and writes nothing on 190 / 102 / 459 / 460 / 463 / 467,
code 1, a `c_user` cookie that is not the `/me` id, an unknown class (`--allow-unknown`), or a prefix that disagrees with
the app id (`--force`). Class → variable: EAAB `META_TOKEN`, EAAG `META_TOKEN_BUSINESS`, EAAH `META_TOKEN_CATALOG`, EAAd
`META_TOKEN_EVENTS`, EAAI `META_TOKEN_RULES`; a non-EAAB class into the ads variable needs `--force` (an EAAG: `--as-ads`,
only when the file holds no EAAB there). Shared cookies of another login are not replaced (`--cookies-suffix` or
`--force`). The write is atomic (temp file 0600 + `os.replace`), keeps unrelated lines, replaces only the managed keys
(`<VAR>`, `<VAR>_APP_ID`, `META_COOKIES[_<S>]`, `META_USER_AGENT`), leaves a 0600 `.bak`, and prints only class, app,
user, first 4 + last 4 characters, cookie **names** and the path. Then: `set -a; . <file>; set +a` and `metaops doctor`.

**Stays manual:** copying the block from the browser (FB Helper); `META_PROXY` (the proxy must be the profile's exit IP,
the import never sets it); the profile's proxy (the UA is optional); re-importing after 190/459-467
(dead tokens never revive); minting System User tokens and `debug_token` of a first-party token (both impossible from
here); deleting the `.bak` (it holds the previous secrets); keeping the env file out of git. Nothing refreshes a token. Log redaction masks every cookie value except `c_user` (the Facebook user id, an identifier, which is what makes the `c_user` == `/me` id check readable).

Runnable path for YOUR-app user token, inside persona's antidetect profile (same exit IP as
`META_PROXY`):
1. Graph API Explorer → *Meta App* = operator's app (Explorer's default can't be exchanged) →
   User token → tick `ads_management, ads_read, business_management, pages_show_list,
   pages_read_engagement, pages_manage_ads, instagram_basic, catalog_management` (+
   `ads_mcp_management` for MCP) → Generate → persona approves. Missing permission = app lacks
   that use case (§1 item 1).
2. Exchange (token never on command line):
   ```bash
   curl -s -G https://graph.facebook.com/v26.0/oauth/access_token \
     --data-urlencode grant_type=fb_exchange_token --data-urlencode client_id=$APP_ID \
     --data-urlencode client_secret=$APP_SECRET --data-urlencode fb_exchange_token=$SHORT
   ```
   400 = token minted under another app, or dev-mode app with persona not tester/admin.
3. `META_TOKEN=<long-lived>` (+ `META_PROXY=socks5h://…` if required), then `metaops
   --workspace . --profile <name> --json doctor --whoami` — expect `type=USER`, `expires_at`
   ~60d, proxy/lifetime verdict.
4. Store token + expiry; re-mint before day 55.

**Field 2026-09-29 (own BM "<BM name>", Mac, no proxy):** a scraped EAAB (app "Power editor"
119211728144504) passed `metaops doctor` (14 ok, incl. the `validate_only` write) with `allow_no_proxy`.
That contradicts the blanket "no cookies/proxy → code 1 / 190-459" above for this session. Second round the same day
settled the factors on that IP: **cookies decide** (without them EAAB, EAAI, EAAG and EAAH answer code 1, an EAAd does not); the
User-Agent does not; a different IP is untested. `debug_token` on a first-party token still returns
code 100. The token still dies with the session (`01`).

A user token can do nothing a System User can't — sees whatever the human sees (incl. client
accounts never shared to a BM). Every call is the persona's session (`01` proxy discipline); one
checkpoint kills automation mid-batch (state files make resume safe).

**Inspect:** `GET /debug_token?input_token=<token>`, caller = the System User token itself:
`type: SYSTEM_USER`, `application`, `expires_at: 0`=never, `data_access_expires_at`, granted
scopes (`probe.py` gate 2).

**[K] Death codes (190 subcodes):** 459 checkpoint ("log in to facebook.com and follow the
instructions"; 2026-09-14 on EAAB `validate_only`, later GETs died too), 460 session invalidated
(password/security rotation), 463 expired, 467 invalid ("user logged out"). Dead tokens never
revive — re-mint once, **freeze** if recurring (`01`, `05`). "Malformed access token" = copy
damage. Code 1 with `opes_mids` on EAAB = missing/invalid session cookies.

**[W] Access denials** are code 10/200 (capability missing / asset not assigned), not 100
(invalid parameter). GET success proves nothing about writes — `probe.py` runs a `validate_only`
create.

### Token transport (scripts)

`graph.py` sends `Authorization: Bearer <token>`, never `access_token=` in URL (logs).
`appsecret_proof` stays a query param (a hash). `graph.redact()` scrubs token, `META_COOKIES`,
proxy creds from all output.

## 6. Meta Ads MCP — live-verified 2026-09-02 (own BM, System User token)

- Endpoint `https://mcp.facebook.com/ads`, Streamable HTTP; send back `Mcp-Session-Id` from
  `initialize`. Errors: `result.isError=true` w/ `error_code`/`error_subcode` (Graph codes);
  messages localised to System User locale — branch on codes (`meta-ads/14`).
- **Auth:** `Authorization: Bearer <System User token>` with `ads_mcp_management`; scope offered
  only if the app has use case `Create & manage ads with ads MCP server`. Without scope → HTTP 401
  "restricted to certain users" on `initialize`. Claude Code OAuth: `claude mcp add --transport
  http --client-id <META_APP_ID> meta-ads https://mcp.facebook.com/ads` (without `--client-id`:
  "redirect_uris are not registered", #57191). Bearer needs no OAuth.
- **Per-account flag** `is_ads_mcp_enabled` via `ads_get_ad_accounts` (also `is_queryable`,
  `has_payment_method`, `min_daily_budget_cents`, `is_ads_mcp_disabled_reason`). Own account
  enabled; client/agency `false` ("gradually being rolled out") — wait.
- **106 tools** (docs show ~29): ads CRUD+activate, creatives (7 formats incl. single-video,
  static carousel, Advantage+ catalog carousel, boost post, partnership; `ads_creative_upload_media`),
  custom audiences, catalog (~40), datasets/pixel rules, experiments, insights/anomaly/benchmark,
  Ad Library, help, opportunity score. Parameter lookup → `15`.
- **Confirmed write params**: `ads_create_ad_set.attribution_spec` (JSON string),
  `dsa_beneficiary/payor`, `is_dynamic_creative`, `promoted_object`, `bid_strategy/bid_amount`,
  spend caps, budget schedule; `ads_create_creative.degrees_of_freedom_spec` (JSON **string**;
  83-key OPT_OUT list accepted and read back), `instagram_user_id`, `product_set_id`, `cards`,
  `placement_videos`; `ads_create_ad.tracking_specs`, `conversion_domain`.
- **[K] Why MCP is not the launch pipe:** no `contextual_multi_ads` in any schema → creative
  inherits account default **OPT_IN** (reads back `null`). No `validate_only`, batch, proxy,
  read-back diff; one account/call; `ads_get_ad_entities` can't return `attribution_spec`
  ("Unsupported fields") — verify via Graph. Prompts steer to Meta defaults ("Default: 7-day
  click + 1-day view", "ALWAYS use CBO", "Advantage+ Audience enabled by default").
- Verified writes (PAUSED, then deleted): campaign (CBO, `daily_budget` cents) → ad set
  (`targeting_automation.advantage_audience: 0` kept; `attribution_spec` honoured) → creative
  (all OPT_OUT) → ad; `ads_update_entity` rename+budget (`updated_fields`, `active_errors`);
  `ads_activate_entity` **not** run.
- **[W] Trap:** `attribution_spec` 1/1/1 on a **LINK_CLICKS** ad set → 100/1885501 "supported
  combination … is (1, 0)": non-conversion goals take 1d click only. `launch.py` sends click-only
  for them when spec is silent (`CLICK_ONLY_ATTRIBUTION_GOALS`).
- Governance: Business Settings → Integrations → Ads MCP Server (7 actions, all allowed by
  default; `…/ads_mcp_rules` edge unreachable from our BM).
- **[W] Failure** (#62376): agent set **TWD** budget in "cents" → 100x overspend. MCP has
  `min_daily_budget_cents` but no offset guard.

## 7. Ad account facts scripts read for you

`currency`+`timezone_name` — changing either **closes** the account, new act id (`08`).
`account_status` 1 active / 2 disabled / 3 unsettled (unpaid, not a ban) / 7 pending risk review /
9 grace period / 100–101 closing — never diagnose from it alone (full enum → `07`). 3 cleared by
itself once the card charged; `balance` = unbilled amount in cents, not prepaid (FIELD 2026-09-27).
The billing threshold can be neither read nor set via API (UI only; Meta rolled back an operator's
change, 2026-09-29): don't script it, see `22`.
Rate limits: BUC, header-driven (`meta-ads/14`); Limited ≈300 calls/h/account — on a limit stop,
don't retry (§8); no polling loops; `x-fb-ads-insights-throttle` is read too (pause at 85%).

## 8. Token choice vs "automation" Account Integrity bans (research 2026-09-27)

- Official Marketing API is an authorized route (Community Standards: scripting banned "unless ... through
  authorized routes"). The ban reason "created or used with an automation" is a broad bucket: it also hits
  fully manual advertisers and whole agency lines (BHW 2024 wave), and "created" covers account ORIGIN
  (farm/autoreg supply) — don't conclude "API = ban" from one death.
- What practitioners do tie to it [Reddit r/FacebookAds 2026, vendors]: burst writes (tens of ad sets in
  minutes) and retry loops after limits. Dev/Limited tier = 300 calls/h per ad account, 300s block; Graph docs
  say stop calling after a limit — retries extend it. Field 2026-09-27: heaviest-load account died, siblings
  on the same SU token lived (`06`).
- EAAB + profile cookies (Dolphin/FBTool autolaunch standard) vs System User: no source shows either is
  safer. EAAB rides the persona's session (a bad burst lands on the profile, dies on logout/checkpoint); SU
  is stable and sanctioned. Don't switch token type as a ban fix — fix pacing.
