# 02 — Direct API access: developer app, tokens, scopes, sandbox

Verified 2026-09-14 against TikTok's docs portal (Get Started → Authorization / Authentication /
Rate limits / App permissions / Sandbox accounts).

**Read `01` first.** The official MCP server needs none of this — no developer app, no API key, just
a browser OAuth. Go through this file only when you need the deterministic write path (`04`), an
unattended run, or an operation MCP does not wrap.

## The gate nobody mentions: you may not be able to register at all

TikTok's developer registration requires a **company-domain email** and a **company-owned, publicly
accessible website**. No shortened links, no third-party-hosted domains, no social profiles.
**Individuals cannot register a developer app.**

This is decisive for a freelance buyer working on shared agency cabinets: you will often have no
route to your own app, and therefore no route to your own advertiser token. Three real options, in
order of how often they apply:

1. **Use the official MCP server** (`01`). No app, no token. This is the default answer.
2. **Be handed an advertiser access token** minted under the agency's existing developer app. It
   does not expire, so this is a one-time handoff.
3. **Have the agency authorize their app against your ad account** and operate through their tooling.

Error 40124 is this gate: "developer profile is not filled in and approved".

## Token types — the conflation that wastes hours

| Token | Endpoint | Expiry |
|---|---|---|
| **Marketing API advertiser token** | `/oauth2/access_token/` | **Never expires.** Invalidate with `/oauth2/revoke_token/` |
| TikTok account / creator token | `/tt_user/oauth2/token/` | **1 day**, refresh via `/tt_user/oauth2/refresh_token/` |
| TTCM / TTO account token | `/oauth2/access_token/` | Never expires |

**The "TikTok tokens expire in 24 hours" claim you will find everywhere — including in TikTok's own
SDK docs — is about the TikTok-*account* token, not the advertiser token.** They get conflated
constantly. If you are managing ad accounts, your token is the non-expiring one.

Consequence: error **40102 "access token expired" on a Marketing API call is first evidence that you
are holding the wrong kind of token**, not that your advertiser token aged out. Check how the token
was minted before concluding it. There is no refresh flow for an advertiser token, which is why
40107 exists.

`auth_code` from the advertiser authorization flow is **valid one hour and single-use**. (The TikTok-
account flow's code is 10 minutes.) Burn it promptly or restart the flow.

## Authorization flow (advertiser)

1. Register as a developer, create an app in **My Apps**, get it approved.
2. Send the advertiser the app's **Advertiser authorization URL** from My Apps.
3. They sign in and approve. You receive `auth_code` on your redirect URL.
4. Exchange it at `/oauth2/access_token/` with `app_id` + `secret` + `auth_code`.
5. Confirm coverage with `/oauth2/advertiser/get/` — it lists the advertisers this token actually
   covers. `ttops doctor` does exactly this and fails if your target is not in the list.

**Who can authorize:** TikTok does not state a minimum role on a help page. Ad-account **Admin** is
the working assumption — an Operator cannot change account settings, and app authorization sits in
that bucket. Confirm on the live authorize screen rather than promising it.

## Scopes

Scopes are chosen per app in My Apps and shown on the authorization screen. The groups that matter:
Ads Management (campaign/ad group/ad writes), Reporting, Creative Management (file uploads,
identities), Audience Management, Business Center management, Events. **A token minted before a
scope was added does not gain it** — re-authorize after changing an app's permissions.

Error **40125** is a missing app scope. Error **40001** is an insufficient *role on the asset*.
Different problems, different people fix them.

## Rate limits

Per **developer app**, four levels, all apps start at Basic. Raise one level at a time from
My Apps → App Detail → Authorization, with a stated reason.

| Level | QPS | QPM | QPD |
|---|---|---|---|
| Basic | 10 | 600 | 864,000 |
| Advanced | 20 | 1,200 | 1,728,000 |
| Premium | 30 | 1,800 | 2,592,000 |
| Ultimate | 50 | 3,000 | 4,320,000 |

Endpoint-specific limits override the global figure. At Basic: `/ad/create/` 5 QPS / 150 QPM /
86,400 QPD · async report create 2 QPS / 60 QPM / **4,500 QPD at every level** ·
`/catalog/product/upload/` 5 QPS · creative-generation endpoints 1 QPS / 5,000 QPD.
**Events API `/event/track/` is 1,000 QPS at every level** and needs no rate-limit application.

**Throttling arrives as HTTP 200 with `code` 40100 (app), 40133 (advertiser), 40016 (endpoint), or
40132 (a specific field value such as a hammered `pixel_code`).** TikTok is not documented to send HTTP 429 — branch on the body code, and if a 429 does arrive from
something in front of TikTok, treat it as throttling too. The
`X-RateLimit-*` headers people cite belong to a different TikTok API. A retry layer keyed on HTTP
status will spin forever. Recovery: QPM breach → wait 5 minutes; QPD breach → wait until **00:00:00
UTC+0**, when the daily counter resets.

40132 has a second reading worth taking seriously: TikTok names token leakage and malicious use as a
cause. An unexplained per-pixel throttle is a reason to check who holds the token.

## Sandbox

Sandbox accounts are created from My Apps and are a **developer-app feature** — they do not exist for
the MCP path. They support a subset of endpoints and reject unsupported parameters (errors 40008,
40009, 40013, 40014).

The honest limitation: a sandbox is useful for payload shape, not for proving a launch. Delivery,
review, billing and eligibility are not simulated. The realistic rehearsal is `ttops --dry-run` plus
a real campaign created `DISABLE` with a floor budget, verified, then deleted.

## SDKs

TikTok publishes an official Business API SDK (Python/JS, actively released). **It covers legacy
endpoints only** — no GMV Max, no Upgraded Smart+ (`/smart_plus/*`), no split testing. Anything from
roughly the last 18 months of TikTok's product expansion requires raw HTTP.

That is why `ttops` speaks HTTP directly. Wrapping the SDK would inherit its blind spots and add a
dependency for no benefit.

## Handoff checklist — what to ask the operator for

Into gitignored `.notes/`, verbatim:

- [ ] `advertiser_id` (string) — and confirm it appears in `/oauth2/advertiser/get/`
- [ ] Access token, by a channel that is not chat. Confirm it is the **advertiser** token
- [ ] `bc_id`, if Business Center operations are in scope
- [ ] `pixel_id` — and confirm it is **linked to this ad account**, not merely shared to the BC
- [ ] `identity_id` + `identity_type` for the creative identity
- [ ] Account **currency and timezone** — permanent, and every budget bound derives from them
- [ ] Your **role** on the ad account (Admin / Operator / Analyst) — `tiktok-ads/02`
- [ ] Who funds the account, and how to reach them. The agent cannot top up

Then run `ttops doctor` before believing any of it. Every item above has a failure mode where the
operator is sincerely wrong.

**A token is a bearer secret.** Never put it in chat, a URL, a screenshot, a repo, a log, or argv.
