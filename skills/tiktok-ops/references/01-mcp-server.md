# 01 — TikTok for Business MCP Server (official)

Verified 2026-09-14 against TikTok's own docs portal (`business-api.tiktok.com/portal/docs`,
section "TikTok for Business MCP Server"). This product is **new** — launched July 2026, MCP
authorization endpoints added August 2026 — so re-read the changelog before trusting any detail here.
Changelog doc: `tiktok-for-business-mcp-server-changelog`.

**An official TikTok MCP server exists and does full read *and* write.** Anything you read elsewhere
claiming "TikTok has no official MCP, use a third-party wrapper" is dated before July 2026. Check the
date on the source before acting on it.

## The two endpoints

| Mode | URL | Tools at connect | Use when |
|---|---|---|---|
| Full disclosure | `https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat` | ~400, full schemas | Large context window. **TikTok recommends this one for Claude.** |
| Progressive disclosure | `https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer` | ~40 core, rest loaded on demand | Token-constrained agents, or a client with a hard tool-count cap |

**Tokens are scoped per path.** A token minted for `tt-ads-mcp-layer` will not authenticate against
`tt-ads-mcp-flat`. Connecting to both means two separate OAuth flows.

## What it costs you to start: nothing

- **No developer app.** No app registration, no app review, no `app_id`/`secret`, no API key.
- **No permission application.** TikTok states the server is publicly available to all users.
- Authorization is a **browser OAuth against the user's existing TikTok for Business login**.

This inverts the usual handoff. When an operator says "I'll give you an API key," the correct answer
for MCP is that there is no key to give — **they** click Authorize in a browser once, and the agent
inherits whatever that login can reach. What the agent can do is exactly what that human's account
can do; the role matrix in `tiktok-ads/02` still governs everything.

## Setup — Claude Code

```bash
claude mcp add --transport http tiktok-ads https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat
```

Or in `.mcp.json` / the client's MCP config:

```json
{
  "mcpServers": {
    "tiktok-ads": {
      "url": "https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat"
    }
  }
}
```

The server alias (`tiktok-ads`) is local and free to rename. On first connect the client opens a
TikTok sign-in, shows the requested permissions, and waits for **Authorize**. Restart or reload the
agent after editing the config.

`/mcp` in Claude Code shows whether it connected. A server that is listed but has no tools is an
authorization that never completed, not a broken server.

**A non-interactive session cannot complete this flow.** The OAuth consent needs a human in a
browser. Plan the handoff: the operator authorizes once, interactively, before the agent's
unattended work begins.

## Authorization lifetime — the operational trap

**30 days.** Then the connection stops working and the same TikTok for Business account has to
reauthorize. There is no refresh that extends it past the window and no warning in the tool output.

Consequence for anything long-running: a monthly reauthorization is a **scheduled maintenance
task**, not an incident. Put the expiry date in the project's `.notes/` at authorization time. An
agent that silently loses MCP access mid-flight looks identical to an API outage — check
authorization age first when tools start failing as a group.

## Rate and concurrency limits

| Limit | Value |
|---|---|
| Per tool, per TikTok for Business user | **3 QPS** |
| Upgraded Smart+ ad writes (`smart_plus_ad_create` / `_update` / `_status_update`), per single ad | **≤1 operation per 5 seconds** |

The 3 QPS is per *tool*, not global: `smart_plus_ad_create` and `smart_plus_ad_update` each get 3/s.
The Smart+ rule is stricter and is about one ad object — exceeding it raises a concurrency error, not
a rate-limit error, and the two need different handling (back off vs serialize).

## Custom agents (building your own client)

Not needed for Claude Code — it is for products embedding TikTok Ads. The flow is OAuth 2.0 with
**Dynamic Client Registration** (runtime `client_id`, no manual registration) and **PKCE**. TikTok
ships dedicated MCP authorization endpoints: exchange an authorization code for tokens, refresh an
access token, revoke a token, plus a documented HTTP status-code table. Docs: `mcp-authorization`,
`exchange-an-mcp-authorization-code-for-tokens`, `refresh-an-mcp-access-token`, `revoke-an-mcp-token`.

## Tool surface — what is actually there

~400 tools, nearly all thin wrappers over Marketing API v1.3 endpoints, so the tool name predicts the
endpoint: `campaign_create` → `/v1.3/campaign/create/`, `report_integrated_get` →
`/v1.3/report/integrated/get/`. Full inventory: `02` § tool map.

Coverage that matters and that people wrongly assume is missing:

| Capability | Tools |
|---|---|
| Campaign / ad group / ad lifecycle | `campaign_create`, `adgroup_create`, `ad_create`, `*_update`, `*_status_update`, `*_get` |
| Upgraded Smart+ | `smart_plus_campaign_create`, `smart_plus_adgroup_create`, `smart_plus_ad_create`, + review/preview/report |
| GMV Max | `campaign_gmv_max_create/update/info`, sessions, `gmv_max_bid_recommend_get`, `gmv_max_report_get` |
| **Automated rules** | `optimizer_rule_create/update/get/list`, `optimizer_rule_result_*`, `optimizer_rule_batch_bind_get` |
| **Split tests** | `split_test_create/update/result_get/end_get/promote_run` |
| **Webhooks** | `subscription_subscribe_create`, `subscription_get`, `subscription_unsubscribe_cancel` |
| **BC money movement** | `bc_transfer`, `bc_billing_group_*`, `bc_invoice_*`, `payment_portfolio_credit_line_update` |
| BC admin | `bc_member_invite/update/delete`, `bc_partner_add/delete`, `bc_asset_assign/unassign`, `bc_advertiser_create` |
| Pixels & events | `pixel_create`, `pixel_event_create/update/delete`, `offline_create`, `crm_create`, `custom_conversion_*` |
| Creative | `file_video_ad_upload`, `file_image_ad_upload`, `file_music_upload`, `creative_ads_preview_create`, `creative_smart_text_get`, `video_fix_task_create` |
| Spark Ads | `tt_video_authorize_apply`, `tt_video_list_get`, `tt_video_info_get`, `tt_video_unbind`, `spark_ad_recommend_get` |
| Audiences | `dmp_custom_audience_*`, `dmp_custom_audience_lookalike_create`, `dmp_saved_audience_*` |
| Catalog | `catalog_create`, `catalog_feed_create`, `catalog_product_upload/update/delete`, `catalog_set_*`, `diagnostic_catalog_*` |
| Comments moderation | `comment_list_get`, `comment_status_update`, `comment_delete`, `blockedword_*` |
| Planning tools | `tool_bid_recommend`, `ad_audience_size_estimate`, `tool_targeting_*`, `tool_interest_*`, `tool_region_get`, `tool_timezone_get`, `tool_url_validate`, `tool_vbo_status_check` |

**Correct a widely repeated error:** TikTok's automated rules and BC balance transfers *are*
API-reachable. Sources that say rules are UI-only, or that an agent can never move money, are wrong
about TikTok — that is Meta's limitation, ported.

### `tiktok_ads_diagnosis_agent` — not an endpoint wrapper

TikTok's official Account Optimization Score diagnosis agent, exposed as an agent-to-agent tool.
Hand it an ad account, campaign or ad group and it returns natural-language findings from TikTok's
own diagnosis models. **Does not support GMV Max objects.** Treat its output as TikTok's opinion —
a strong prior about what TikTok's own system thinks is wrong, not a measurement of your business.

### Parameter schemas

TikTok does not publish the tool schemas as a document. Two consequences:

1. **Introspect at runtime.** Ask the connected server what a tool takes rather than hardcoding a
   payload from memory. TikTok's own documented method is to ask the agent: *"What parameters do I
   need for the `smart_plus_ad_create` tool?"*
2. For wrapper tools, the **v1.3 endpoint reference is the schema** — same fields, same enums. `03`
   holds the enums that decide a call succeeds or fails.

## MCP is the primary surface. `ttops` is the guard rail around it.

This is not two competing paths. MCP does the work; `ttops` checks it.

**What MCP does not give you**, because it is a faithful wrapper over endpoints that behave this way:

| Gap | Consequence | Covered by |
|---|---|---|
| `operation_status` defaults to **ENABLE** | Omit it in a `campaign_create` call and the campaign is **live and spending** | `ttops preflight` emits it set to `DISABLE` |
| No budget validation | 50 on a JPY account is syntactically fine and 100× wrong | `ttops preflight` / `budget-check` |
| A create returning `code: 0` does not prove the object holds what you sent | TikTok drops unknown keys and fills enum defaults silently | `ttops audit` diffs the read-back |
| Cryptic `secondary_status` strings | `AD_STATUS_AUDIT_DENY` is a rejection; `AD_STATUS_AUDIT` is a pending review | `ttops explain <status>` |
| No enum validation | A `SALES` objective or a Meta bid-strategy name fails at the call, after you built around it | `ttops preflight` |

**Both `ttops` commands run offline with no token** — deliberately, because an operator who cannot
register a developer app has MCP access and nothing else.

```bash
# before the MCP calls: validate, and get the exact arguments
ttops --json preflight --spec specs/mine.json --currency JPY --advertiser-id 7123456789

# after them: read objects back through MCP, save the JSON, then
ttops --json audit --spec specs/mine.json --actual readback.json --currency JPY
```

`ttops tools` prints the lifecycle-step → MCP-tool-name mapping.

**When to use the direct API instead of MCP at all** — only three cases:

- **Bulk across many accounts**, where a resumable state file beats a conversation.
- **Unattended or scheduled runs**, because MCP's authorization is browser-bound and expires in 30
  days while an advertiser token does not.
- **An operation MCP does not wrap** (§ known gaps).

Everything else goes through MCP.

## Known gaps

- Not every v1.3 endpoint is wrapped. `02` § tool map is the authoritative list; if a tool is not
  there, use the API.
- **Tool availability varies by region and account configuration.** A tool present for one advertiser
  may be absent for another. Check, do not assume.
- Schemas are unpublished (above).
- `tiktok_ads_diagnosis_agent` excludes GMV Max.
- No documented sandbox for MCP. Marketing API sandbox accounts are a developer-app feature (`02`) and
  do not cover this path — so the first MCP write you make is against production. Make it a paused
  object on a throwaway campaign.

## Third-party TikTok Ads MCP servers

They exist (read-only wrappers, self-hosted alternatives, varying maintenance). With an official
first-party server that needs no credentials and does full read/write, a third-party server is
justified only by a specific need the official one cannot meet — self-hosting, or a narrow read-only
surface enforced at the server. Never route an advertiser's credentials through an unaffiliated
third-party API when the first-party path is free.
