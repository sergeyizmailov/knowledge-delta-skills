---
name: tiktok-ops
description: "Execute TikTok Ads through the official TikTok for Business MCP server and Marketing API v1.3, with the ttops CLI as an offline guard rail: access and tokens, paused launch, verify-before-activate, budget and currency safety, reporting, automated rules, error codes. Strategy and creative decisions = tiktok-ads."
---

# TikTok Ops

Reviewed 2026-09-14, against TikTok's own docs portal (business-api.tiktok.com/portal/docs).

> **STATUS.** `ttops` passes 102 offline tests and has **never been run against a live advertiser.**
> Its offline commands (`preflight`, `audit`, `budget-check`, `explain`) need no token and are safe
> to trust; its live commands are a paper guarantee until you prove them. Make the first real run a
> throwaway campaign at a floor budget, reviewed by a human before anything is enabled.

## Start here

| You are… | Read | Then |
|---|---|---|
| Connecting an agent to TikTok Ads for the first time | `references/01-mcp-server.md` | official MCP: no app, no API key, browser OAuth |
| About to create anything through MCP | `references/00-launch-runbook.md` § 5–7 | `ttops preflight` → MCP → `ttops audit`; both offline |
| Handed a token / asked to launch via API | `references/00-launch-runbook.md` | create a workspace in a project dir, `ttops doctor`, then follow the runbook |
| In a directory with `workspace.json` | `references/04-ttops-cli.md` | `ttops --json doctor` before anything else |
| Hit an error code, a gate, a rejection | `references/05-error-catalog.md` or `ttops explain <code>` | the file it names |
| Asked "can the API even do X" | `references/01` § tool surface, then `references/03` | |

## The four facts that cost money if you don't know them

1. **`operation_status` defaults to `ENABLE`.** Omit it and your campaign is created **live and
   spending**. This is the opposite of Meta. Pass `DISABLE` at campaign, ad group *and* ad, every
   time. `ttops` forces it and offers no override.
2. **A successful create is not proof the object holds what you sent.** TikTok drops unknown keys and
   fills enum defaults silently. Read every object back and diff it before activating.
3. **Budget minimums are `base × per-currency ratio`, and nine currencies take no decimals.** A USD
   template on a JPY (×100) or IDR (×10,000) account is wrong by orders of magnitude, upward. Run
   `ttops budget-check --currency X` before writing a spec.
4. **Throttling arrives in the response body, as HTTP 200 with `code` 40100/40133/40016.** Branch on
   the body code, never on HTTP status — TikTok is not documented to send 429 and handling keyed on
   status will loop forever without noticing. If a 429 ever does arrive, treat it as throttling too;
   the rule is "always read the body code", not "429 cannot happen".

Plus one that costs a day: **Marketing API advertiser tokens never expire.** So error 40102 "token
expired" on a Marketing API call is a strong signal that you are holding a TikTok-*account* token
(1 day) rather than an advertiser token — the two are conflated constantly, including in TikTok's
own SDK docs. Check the token's origin before concluding it; it is the first hypothesis, not a
certainty.

## MCP is the default. `ttops` is the guard rail.

TikTok ships an **official MCP server** (July 2026) that covers essentially the whole job — campaign
creation, budgets, targeting, creative upload, catalogs, audiences, reporting, automated rules,
webhooks, Business Center operations. ~400 tools. **No developer app, no API key**: the operator
authorizes once in a browser.

```bash
claude mcp add --transport http tiktok-ads \
  https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat
```

**Use MCP for the work.** It is not a fallback and not read-only.

What it does not give you is *guarantees* — it is a faithful wrapper over endpoints whose defaults
are dangerous. That is what `ttops` supplies, and **both of its guard commands run offline with no
token**, which matters because an operator who cannot register a developer app has MCP and nothing
else:

```bash
ttops --json preflight --spec specs/mine.json --currency JPY   # before the MCP calls
ttops --json audit --spec specs/mine.json --actual readback.json --currency JPY   # after them
```

| Gap in MCP | What `ttops` does |
|---|---|
| `operation_status` defaults to **ENABLE** — omit it and the campaign spends | `preflight` emits every create with `DISABLE` |
| No budget validation; 50 on a JPY account is 100× wrong | `preflight`, `budget-check` |
| `code: 0` ≠ the object holds what you sent | `audit` diffs the read-back and flags anything live |
| `AD_STATUS_AUDIT_DENY` (rejected) reads like `AD_STATUS_AUDIT` (in review) | `explain <status>` |
| No enum validation — a `SALES` objective fails at the call | `preflight` |

**Reach for the direct API only in three cases:** bulk across many accounts, unattended/scheduled runs
(MCP's authorization is browser-bound and expires in 30 days; an advertiser token does not), or an
operation MCP does not wrap. Then the full `ttops` lifecycle below applies.

## Lifecycle

**Through MCP** (the normal case) — full detail in `references/00-launch-runbook.md`:

```
doctor-by-hand (auth_advertiser_get, advertiser_info_get, pixel_list_get)
  → ttops preflight            validate + emit exact tool arguments
  → MCP creates, all DISABLED  campaign_create → adgroup_create → ad_create
  → read back                  campaign_get / adgroup_get / ad_get → readback.json
  → ttops audit                diff + danger flags
  → human review while paused  preview, destination, review status, balance
  → enable bottom-up           ad → adgroup → campaign
```

**Through the API** (bulk / unattended), receipt-gated at every step:

```bash
export TIKTOK_ACCESS_TOKEN='...'          # never on argv
cd ~/work/tiktok-<account>                # project dir, NOT the skill dir
ttops --json doctor
ttops --json plan     --spec specs/mine.json
ttops --json apply    --plan .ttops/plans/<plan>.json
ttops --json verify   --plan .ttops/plans/<plan>.json
ttops --json activate --plan .ttops/plans/<plan>.json \
      --confirm-reviewed REVIEWED --confirm SPEND
```

`doctor` receipts expire after 24h, `verify` after 1h — an hour-old read is not evidence about what
is live now.

Run without installing: `PYTHONPATH=<skill>/scripts python3 -m ttops …` (stdlib only, no deps).

## Non-negotiables

1. **Nothing is created enabled.** Creation and activation are separate commands, and activation
   carries an explicit `--confirm SPEND`.
2. **Verify before activate, always.** A create returning `code: 0` proves the call was accepted, not
   that the object is what you designed.
3. **Never hand-assemble a payload from memory.** The agent writes a spec; `ttops preflight`
   turns it into the arguments — which you then hand to the MCP tool, or which `ttops apply` posts
   directly on the token path. Either way the arguments come from validated normalisation, not from
   improvising JSON at the call site. A new campaign shape means extending `spec.py` and its tests.
4. **A dropped connection on a write is an UNKNOWN outcome, not a failure.** Never blind-retry a
   create. Reconcile against Ads Manager first; that is how duplicates happen.
5. **The token is a bearer secret.** Not in chat, URLs, screenshots, repos, logs, or argv.
6. **Any budget or billing anomaly: pause first, diagnose second.** Debating units while a campaign
   spends is how a units error becomes an incident.
7. **The agent cannot fund an account.** Balance top-ups, payment methods and refunds are UI-only and
   Finance-role-gated. Funding is an escalation to a human, never a blocked automation.
8. **Access problems are human problems.** 40125 is a missing *app scope* (a developer fixes it);
   40001 is an insufficient *role on the asset* (a BC Admin fixes it). Retrying fixes neither.

## References

| Need | File |
|---|---|
| **Official MCP server — the default surface**: URLs, setup, 30-day authorization, full tool surface, what it does not guarantee | `references/01-mcp-server.md` |
| **Ordered launch path (MCP-first) — start here for any launch** | `references/00-launch-runbook.md` |
| Developer app gate, token types and expiry, scopes, rate limits, sandbox, SDK limits, handoff checklist | `references/02-api-access-and-tokens.md` |
| Enums, create payloads, CBO, budget/currency math, batch limits, idempotency, deprecations | `references/03-api-enums-and-payloads.md` |
| **`ttops` command contract**: workspace, lifecycle, receipts, failure contract, extending it | `references/04-ttops-cli.md` |
| Return codes: cause → fix, triage order, and the errors that return `code: 0` | `references/05-error-catalog.md` |
| Reporting at scale, automated rules via API, webhooks, audience limits, split tests, no-code layer | `references/06-monitoring-rules-webhooks.md` |
| Strategy, objectives, targeting, creative, policy, tracking, diagnosis | skill `tiktok-ads` |

Scripts live in `scripts/ttops/`; example workspace and specs in `specs/`. Offline suite:
`PYTHONPATH=scripts python3 -m ttops.selftest` (102 tests) — green before shipping any change.

## Boundary

Owns access, payload correctness, create→verify→activate, and error response. Owns **no opinion
about what to launch**: objective, optimization event, structure, targeting, budgets and creative
come from `tiktok-ads`. Picking an objective here means a step was skipped.

For regulated verticals the authorization gate is cleared **before any ad object exists** and binds
to a specific verified entity and ad account (`tiktok-ads/08`). This skill does not route around ad
review and does not implement cloaking or review-layer filtering.
