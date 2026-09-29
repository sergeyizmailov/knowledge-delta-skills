# 05 — Return codes: cause → fix

Source: TikTok "Return Codes" appendix — doc `1737172488964097`,
https://business-api.tiktok.com/portal/docs?id=1737172488964097 — fetched 2026-09-14.

`ttops explain <code>` prints the same table offline.

## The three rules that make this catalog usable

1. **`code` is the truth, not the HTTP status.** TikTok returns HTTP 200 with a non-zero `code` on
   failure. Any error handling keyed on HTTP status is broken by construction.
2. **`code: 20001` is partial success, which means failure.** Some items in a batch failed.
   Inspect the per-item results — treating it as success loses half a launch silently. `ttops`
   raises `PartialSuccessError` on it rather than returning `data`.
3. **Keep `request_id` from every response.** It is the only handle TikTok support will act on.

## Authentication and access — usually a human problem

| Code | Cause | Fix |
|---|---|---|
| 40105 | Invalid access token | Wrong or revoked. Re-mint. **Do not retry** |
| 40104 | Access token empty | `TIKTOK_ACCESS_TOKEN` unset |
| 40102 | "Access token expired" | **Marketing API advertiser tokens do not expire.** So the first hypothesis is that you hold a TikTok-account/creator token (1 day) — wrong token type, not an expiry. Confirm how the token was minted before acting on it |
| 40107 | Invalid refresh token | You cannot refresh an advertiser token — it has no refresh flow |
| 40106 | Core user invalid | The token is not valid for *this* `advertiser_id`. Confirm with `/oauth2/advertiser/get/` |
| 40110 | Invalid authorization code | `auth_code` is single-use and lives 1 hour (Marketing API). Re-run authorization |
| 40101 | Invalid auth parameters | `app_id`/`secret` mismatch, or a reused `auth_code` |
| 40113 | App blocked or missing | Check App ID and secret in My Apps |
| 40124 | Developer profile not approved | Registration needs a company-domain email and a company website. **Individuals cannot register** (`02`) |
| 40125 | Developer lacks permission | Missing **app scope**. Re-authorize after adding it |
| 40001 | No permission for this operation | Insufficient **role on the asset**. Operator cannot touch pixels, identities or account settings. **Escalate to a BC Admin** |
| 40118 | Not on the allowlist | Feature is allowlist-only or unavailable in this country. Contact the TikTok rep. Do not engineer around it |
| 40119 | Developer and advertiser are different companies | Token belongs to another company's app |

**40125 vs 40001 is the distinction that saves an hour.** 40125 = the *app* lacks a scope; a
developer fixes it. 40001 = *you* lack a role on the asset; a BC Admin fixes it. They look identical
in a log and have different owners.

## Throttling — in the body, not the HTTP status

TikTok documents these as HTTP 200 with a non-zero body `code`. **Branch on the body code.** Do not
rely on HTTP 429; equally, do not assert it can never arrive — if one does, treat it as throttling.

| Code | Scope | Recovery |
|---|---|---|
| 40100 | Developer app | QPM breach → wait 5 min. QPD → wait until **00:00:00 UTC+0** |
| 40133 | Advertiser account | Serialize calls against this advertiser |
| 40016 | Specific endpoint, app level | Back off on that endpoint only |
| 40132 | A specific field value (usually `pixel_code`) | One pixel is being hammered — **or the token leaked and is being used maliciously.** Treat an unexplained one as a security question |

## Parameters and objects

| Code | Cause | Fix |
|---|---|---|
| 40002 | Parameter error | The message names the field. Common: audience size 0 (fewer than 1,000 matches), audience still processing, or a timestamp not in `%Y-%m-%d %H:%M:%S` |
| 40000 | Invalid parameters | Check the endpoint reference |
| 40007 | Object does not exist | Wrong ID, deleted, or belongs to another advertiser |
| 40011 | Too many IDs | Status updates cap at **20**; GET filters at **100** |
| 40006 | Version incompatible | A newer product on an older version. Use v1.3 |
| 40051 / 41001 | Invalid version / endpoint offline | Path retired for this version |
| 40010 | Domain not supported | Base URL must be `https://business-api.tiktok.com/open_api` |
| 40050 | Duplicate request | `request_id` deduplicates within **10 seconds**. Vary it or accept the earlier result |
| 40202 | Write/update conflict | Concurrent write on one object. Retry once, serialized |
| 40502 | Max ad limit reached | Create in another ad group, or delete unused ads |
| 40065 | US 13–17 targeting restriction | Exclude `AGE_13_17` or use only the supported options |
| 40300 / 40301 | Advertiser missing or unmatched | Wrong `advertiser_id` |

## Files and creatives

| Code | Cause | Fix |
|---|---|---|
| 40901 | Video transcoding in progress | **Not an error.** Poll `/file/video/ad/info/` until ready |
| 40053 | Invalid video ID | The video is still processing, or belongs to another advertiser. Media IDs are per-advertiser |
| 40911 | Duplicate material name | Check with `/file/name/check/`, rename |
| 40907 / 40915 | Too large / fails specs | Check the endpoint's format, ratio and duration limits (`tiktok-ads/06`) |
| 40900 | Signature mismatch | Recompute the hash for the file you are actually sending |
| 40902, 40903, 40913 | Cannot fetch URL/image | Transient. Retry |
| 40904, 40908 | Illegal content / unsupported type | Wrong format |

## Tasks and reports

| Code | Cause | Fix |
|---|---|---|
| 40201 | Task not ready | Poll again. Async reports and batch jobs are not instant |
| 40200 | Task error | Check the task parameters |

## Sandbox-only

40008 (endpoint not implemented), 40009 (parameter unsupported in sandbox), 40013 (sandbox account
missing), 40014 (feature unsupported in sandbox). If you meet these outside a sandbox, the path is
simply wrong.

## Triage order

1. **`code` in the auth/access block?** Stop. Retrying cannot fix a permission. Identify whether a
   developer or a BC Admin owns it, and say so.
2. **Throttled?** Back off on the documented schedule. Do not parallelise harder.
3. **40002?** Read the message — it names the field. Fix the spec, not the transport.
4. **A write whose connection dropped?** Outcome is UNKNOWN. Reconcile against Ads Manager before any
   retry. This is the one case where retrying is worse than doing nothing.
5. **Unknown code?** `ttops explain` will say so. Check the appendix rather than inventing a meaning.

## Secondary statuses — the errors that return `code: 0`

A create can succeed and the object still never serve. The reason is in `secondary_status`, and the
strings are cryptic and easy to confuse:

| Status contains | Severity | Meaning |
|---|---|---|
| `AUDIT_DENY` | **BLOCKED** | **Rejected.** Cannot be enabled into life — build a new ad. Appeal re-reviews the whole ad group; you get one |
| `AUDIT` (without `DENY`) | REVIEW | In review. Normal for a new ad |
| `REAUDIT` | REVIEW | Back in review after an edit. Stop editing |
| `ASSET_AUTHORIZATION_LOST` | **BLOCKED** | An asset's authorization lapsed. **On a Spark Ad this is the creator's video code expiring** — delivery stops immediately, no grace period, the old code cannot be revived |
| `INDUSTRY_QUALIFICATION_MISSING` / `_DENY` / `_EXPIRED` | **BLOCKED** | Vertical certification absent, refused, or expired. Not fixable by editing the ad |
| `ADVERTISER_AUDIT_DENY` | **BLOCKED** | The **advertiser** failed review, not the ad. Account-level — escalate |
| `ADVERTISER_ACCOUNT_PUNISH` | **BLOCKED** | Account penalised/suspended. **30 days** to fix or appeal, then permanent and non-appealable. A suspended *agency* account also cannot create or fund other ad accounts |
| `BALANCE_EXCEED` | MONEY | Out of money. Prepay stops dead. **The agent cannot top up** — escalate |
| `PIXEL_UNBIND` | **BLOCKED** | Pixel no longer bound. Shared to the BC ≠ linked to this ad account |
| `MUSIC_AUTHORIZATION_MISSING` | **BLOCKED** | Track not licensed. CML does not cover Pangle |
| `TRANSCODING_FAIL` | **BLOCKED** | Re-encode; `video_fix_task_create` repairs some files |
| `PARTIAL_AUDIT_NO_DELIVERY` | REVIEW | Partially approved and **not** delivering |
| `DELIVERY_OK` | LIVE | Serving |

**`AD_STATUS_AUDIT_DENY` contains `AUDIT`.** Substring-matching on "AUDIT" reads a rejection as a
pending review and you wait for something that is never coming. Match the longest key first, or just
use the tool:

```bash
ttops explain AD_STATUS_AUDIT_DENY
ttops explain AD_STATUS_ASSET_AUTHORIZATION_LOST
```

TikTok's own enum ships a typo — `AD_STAUS_PIXEL_UNBIND` (sic). `ttops explain` normalises it.

Full enum: doc `1737174886619138`, https://business-api.tiktok.com/portal/docs?id=1737174886619138.

## Other failures that return `code: 0`

- A create that succeeds but stores something else (unknown keys dropped, enum defaults filled).
  **Only `ttops verify` catches this.**
- An ad created fine and then rejected in review. Check `secondary_status` / `ttops review`.
- A campaign that is live and simply not delivering. `ttops sweep`, then `tiktok-ads/09`.
