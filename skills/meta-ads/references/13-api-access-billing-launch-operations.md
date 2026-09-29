# Meta Marketing API, Billing, and Launch Operations

Last reviewed: 2026-09-02 (§2, §6, §7 reduced to clean-lane rules; mechanics moved to `meta-grey-ops/02`). §10.0 verified 2026-08-31. PBIA subsection corrected 2026-09-29.

Marketing API/MCP automation, System User tokens, Page/Instagram identity, payment readiness, restrictions, final activation. UI labels, Graph versions, permissions, app-mode rules, support availability change — verify live account/current docs before irreversible or spend-producing action.

## Contents

1. Ownership model
2. System User and token setup
3. Token security
4. Readiness tests
5. Page and Instagram identity
6. App state and access levels
7. Ads MCP governance
8. Billing and payment diagnosis
9. Restriction and support flow
10. Safe automation launch sequence
11. Failure map
12. Observed post-mortem
13. Sources and uncertainty

## 1. Ownership model

```text
Personal or managed login
  Business Portfolio
    Ad account
    Facebook Page
    Instagram professional account
    Dataset / Pixel
    Developer app
    System User -> token -> assigned assets
```

- Portfolio owns/receives partner access to assets; a person/System User then receives tasks per asset — adding them to the portfolio does NOT auto-assign the ad account, Page, Instagram account, dataset, or app.
- Prefer business ownership/partner access over shared personal credentials. A "warmed" portfolio is not a documented guarantee of faster moderation, lower restriction risk, or transferable trust.
- Before spend, audit `People`, `Partners`, `System Users` — an unknown full-control identity can manage people/settings/assets and may delete the portfolio. Confirm recovery/ownership before removing an unfamiliar owner; secure legitimate admins with 2FA first.

## 2. System User and token setup

Mechanics (app use cases, scope table, assignment order, token generation, tier rename Standard→Limited/Advanced→Full, upgrade criteria, death codes) → `meta-grey-ops/references/02-access-tokens-and-mcp.md`.

## 3. Token security

Generic hygiene (never paste/print/expose tokens; secret manager) is in SKILL.md guardrails. Non-generic: generate separate tokens per integration so one can be rotated without breaking everything; if exposed, revoke/rotate before spend — check dependencies first, `Revoke tokens` can affect more than the visible token.

## 4. Readiness tests

Separate gates:

1. **Token identity** — inspect via token debugger/debug endpoint; verify app, type, expiry, data-access expiry, user.
2. **Granted scopes** — query `/me/permissions`; requested ≠ granted.
3. **Readable assets** — list expected ad account, Page, Instagram account, data source by stable ID.
4. **System User tasks** — inspect assigned assets in Business Settings; visible in one list ≠ every required task.
5. **Zero-spend write probe** — prefer `execution_options: ["validate_only"]` (§10.0): exercises the write path, creates nothing to clean up. Fall back to a disposable `PAUSED` campaign + read-back where validate_only unsupported. Do this before uploading the full creative set.
6. **Identity probe** — create a paused creative with the intended Page/Instagram identity; a generic campaign write does not validate identity.
7. **Delivery gate** — inspect Account Quality, Billing, effective status, live UI; API object creation ≠ proof of deliverability.

Never activate a probe. Delete only after confirming no useful audit evidence/dependency remains; otherwise keep paused with a clear test name.

Read succeeds, write fails — check: `ads_management` granted (not just requested); System User has write tasks on the exact ad account; app has supported relationship with the business; token belongs to the expected app/System User; Page/Instagram assets assigned where creative requires; account/business/user/Page/payment unrestricted; API version and fields current.

Don't infer meaning from a numeric `account_status` alone — combine with effective statuses, Account Quality, Billing, live product message.

## 5. Page and Instagram identity

Verify: Instagram account is professional and linked to the intended Page; portfolio owns it or has valid partner access; operator/System User has advertising access to Page and Instagram; ad account allowed to use those identities; identity appears in the live ad creation flow; a paused creative using both identities succeeds.

An account appearing in `/instagram_accounts` doesn't prove it's valid as creative identity — the creative is the authoritative probe. `Param instagram_user_id must be a valid Instagram account id` usually points to linkage, asset assignment, ID type, token/app relationship, or unsupported creative config — not audience targeting.

### Field rename (doc-confirmed, enforced)

`instagram_actor_id` GONE from v22.0 (2025-01):

| legacy | current |
|---|---|
| `instagram_actor_id` | `instagram_user_id` |
| `instagram_story_id` | `source_instagram_media_id` |
| `effective_instagram_story_id` | `effective_instagram_media_id` |

Migration deadline cut to 2025-09-09 — no supported version accepts legacy names now. A snippet/Postman example/SDK wrapper still passing `instagram_actor_id` is pre-v22 and will reject a valid ID — **rejection is not evidence the ID is bad.** Older docs pages still show the legacy name.

### Page-backed Instagram accounts (PBIA) (corrected 2026-09-29)

A Page with **no** Instagram account can still run Instagram placements: the Page's PBIA is an auto-derived IG identity (name+picture from the Page) — what the Ads Manager identity picker means by "Use Facebook Page".

**API create is deprecated.** `POST /{page_id}/page_backed_instagram_accounts` was deprecated in the v22.0 changelog and stopped working for all versions on 2025-04-21 (re-verified 2026-09-29; returns #10 Permission Denied in the field); the `GET` edge was removed from the Page schema (returns #100 "nonexisting field"). An earlier revision of this section presented both calls as doc-confirmed: wrong. Create the PBIA in the UI (Ads Manager → new ad draft → Identity → Instagram account → **Use Facebook Page** → discard the draft) and check existence with `GET /{page_id}?fields=instagram_business_account,connected_instagram_account,connected_page_backed_instagram_account` (`meta-grey-ops/18`).

- Page-level reads and writes need a **PAGE access token** (`GET /{page_id}?fields=access_token`), ≥ADVERTISER role. A user/System-User token returns `190 "must be called with a Page Access Token"` — wrong token type, NOT missing PBIA.
- One PBIA per Page.
- Pass the PBIA id as **`instagram_user_id`** in `object_story_spec`.
- Ads-only identity: no organic posts/comments/likes, cannot log in. In-feed the profile name renders black/non-clickable, not a blue link — ad comment-reply workflows have no account to reply from. Irrelevant for pure direct-response; disqualifying if the plan needs organic IG presence or comment moderation.

Destination-specific flows (e.g. Instagram Direct) can additionally require matching promoted object, destination, CTA, messaging eligibility.

EU: account-level personalized/less-personalized ad choices can affect creation eligibility — it's the user's privacy choice; explain the effect and open the exact Accounts Center screen, don't choose on their behalf. Re-test the paused creative after they complete the choice.

## 6. App state and access levels

Detail → `meta-grey-ops/02` §3.

## 7. Ads MCP governance

Facts (tools, auth, Claude Code syntax, rules API, verified failures) → `meta-grey-ops/02` §0 and §6. Clean-lane governance:

1. Agent writes go through the Marketing API; MCP is for reads and bounded edits. No published MCP tool schema exposes attribution/enhancement/multi-advertiser controls; `ads_create_creative` is single-image only (doc-confirmed 2026-09-02).
2. Distinguish Meta's connector (`mcp.facebook.com/ads`) from third-party MCP servers and direct API — different operators/credentials/trust boundaries. Never send a Marketing API token to a third-party MCP provider; shared-app + raw-token + unsupervised writes is the reported ban mechanism [practitioner-multiple, no Meta statement].
3. When MCP used: start read-only; enable write categories per task via Business Suite ads MCP rules (or `POST …/ads_mcp_rules`); set a budget cap (`edit_budget` max_amount_cents/max_percentage); keep new objects PAUSED and read IDs/identity/targeting/placements/destination/schedule/budget **in major units and currency** back through the API before activation; keep activation and budget increases human-approved.
4. Any billing anomaly during agent activity: pause first, diagnose second (claude-code #62376: 100x TWD overspend while the agent debated units).

## 8. Billing and payment diagnosis

The Marketing API doesn't replace the trusted Meta UI for card entry, 3DS, temporary-hold codes, payment-method verification — user must do those; never ask them to share full card data in chat.

| State | Meaning | Action |
|---|---|---|
| Failed transaction | One charge/top-up attempt failed | Inspect that transaction and card response |
| Current amount due | Meta shows a payable balance | Pay through the displayed billing flow |
| Card verified/default | Card passed verification, selected | Continue checking account eligibility |
| Payment method ineligible | Meta won't accept that method for the shown flow | Use supported alternative or support path |
| Ad account restricted | Delivery/write access blocked at account level | Resolve in Business Support Home/Account Quality |

`Current balance = 0`/`No payment due` can coexist with a failed transaction AND an account restriction. Don't pay an arbitrary amount to "unlock" when no real amount is due.

Virtual/prepaid/crypto-linked cards: no documented universal ban, but more issuer/verification/risk failures in practice. Prefer a conventional bank-issued, verifiable credit/debit card with consistent legal name/billing country/currency/funds; avoid rapid card swaps/retries.

A default/verified replacement card does NOT automatically clear a restriction from an earlier failed payment — confirm restoration separately in Account Quality and via a paused write probe.

## 9. Restriction and support flow

1. Personal-profile/Page feature restriction → Facebook **Account Status**. Advertising/business assets → Business Support Home/Account Quality. Check Meta Status first if multiple unrelated accounts/surfaces fail at once.
2. Select the exact affected person/portfolio/ad account/Page/payment asset.
3. Save displayed reason, transaction/payment ID, policy/error code, timestamps, screenshots. Record only card's last 4 digits.
4. Correct the underlying issue before requesting review.
5. Use the review/contact path shown for that asset; avoid duplicate requests.
6. If support calls it final, preserve the case. Clean lane: do not bypass from this skill — replacement/cloaking/asset hopping is `meta-grey-ops`.

Lane caveat: this section is the clean-lane (fix, then request review) path. **On the operator's own BM the rule is: on an ad disapproval do not edit or resubmit** — switch the ad off, leave it, report (`meta-grey-ops/23`).

Treat support replies as official for the named account, not universal product documentation — automated/first-line replies can conflict with live UI. Preserve transcript/case ID; ask for manual escalation + exact affected asset/rule/date/duration/review path when ambiguous.

Concise billing appeal template:

> Please review ad account [AD_ACCOUNT_ID]. It was restricted after failed
> transaction [PAYMENT_ID] on the previous card ending [LAST4]. A verifiable
> replacement card ending [LAST4] is now default, and Billing shows
> [BALANCE/NO PAYMENT DUE]. Please restore access or provide the exact remaining
> remediation and affected asset.

Never include token, app secret, full card number, CVV, verification code, or ID document unless the official secure upload flow explicitly requests it.

## 10. Safe automation launch sequence

Build for reversibility. Composing rule: **`validate_only` → PAUSED → human enable**, in that order, on every object. Note: a PAUSED ad created via API is still submitted for review immediately (`meta-grey-ops/04`), so "zero-spend probe" does not mean "no review"; `meta-grey-ops` creates ACTIVE by default.

Limit: an object referencing a parent that doesn't exist yet (ad set needs `campaign_id`; ad needs `adset_id`+`creative_id`) can't be validated ahead of the run — fails on the missing parent, not the payload. Campaigns and creatives have no such dependency, validate any time. Pre-flight covers campaign+creative; ad sets/ads validate in sequence during the real build, immediately before each create.

### 10.0 `execution_options` — the zero-cost dry run

Meta validates a payload without mutating anything — use before every create; costs no spend, no account risk. [doc-confirmed, v26.0 reference, verified 2026-08-31]

| Endpoint | Accepted values |
|---|---|
| `POST /act_X/campaigns`, `POST /{campaign_id}` | `validate_only`, `include_recommendations` |
| `POST /act_X/adsets`, `POST /{adset_id}` | `validate_only`, `include_recommendations` |
| `POST /act_X/ads`, `POST /{ad_id}` | `validate_only`, **`synchronous_ad_review`**, `include_recommendations` |
| `POST /act_X/adcreatives` | `validate_only` only |
| `POST /{adcreative_id}` (update) | **not supported** — validate a creative at create time or not at all |

- `validate_only`: "will not perform the mutation but will run through the validation rules against values of each field." Pass → `{"success": true}`; fail → normal error envelope whose **`error_data.blame_field_specs`** names the exact field path at fault — read that first, fastest payload debugger Meta ships.
- `synchronous_ad_review`: must pair with `validate_only`. Adds Ads Integrity checks (message language, image text rule, …) **before the object exists**. Ad endpoints only. Cheapest read on whether a creative survives review.
- `include_recommendations`: cannot be used alone.
- Catches bad values/wrong types/missing required fields. Whether it catches wrong *nesting* is [unverified] — `blame_field_specs` encodes a field's spec location, implying yes, but no doc confirms. Not a policy verdict — full ad review still happens post-creation.
- Inside a batch: [unverified]; don't mix with chained creation — a validate-only op returns no `id`, breaking every `{result=…:$.id}` reference.

### 10.1 Sequence

1. Confirm ownership, privileged users, 2FA, Account Quality, Billing, currency, time zone, payment type, spending limits, Page/Instagram linkage.
2. Validate measurement/destination and applicable policy/special category.
3. Run token, asset, write, and identity probes.
4. Create campaign, ad set, creatives, ads with every level `PAUSED`.
5. Read back stable IDs and all critical fields: budget units, bid strategy, objective, promoted object, optimization event, geo, age, schedule, attribution, placements, Page/Instagram identity, CTA, destination, URLs, UTMs, creative enhancements.
6. Preview each placement — 4:5 to feeds, 9:16 to Stories/Reels; verify safe zones, no unintended cropping.
7. Refresh start/end times immediately before activation — a paused build can invalidate or shorten its lifetime while access/billing issues resolve.
8. Recheck effective statuses and account restrictions after publication/review.
9. Activate deliberately, respecting object dependencies; immediately read back delivery — a successful mutation ≠ spend started.
10. Monitor first hour/day for rejection, delivery, spend, destination, tracking, messaging/lead receipt, billing anomalies. Pause on any identity/destination/measurement/budget mismatch.

Activation is spend-producing, must follow the user's explicit approval of final budget/schedule/destination/creative set. "Do everything" authorizes setup within scope, not hidden changes to privacy choices, card details, legal declarations, or unrestricted spend.

## 11. Failure map

| Symptom | First checks |
|---|---|
| Token works for `GET`, fails on `POST` | Granted scopes, System User write tasks, exact account restriction |
| Asset visible to person, absent to token | Assign to System User and app; inspect business relationship |
| Instagram visible but creative fails | Page link, actor ID type, Page/IG assignments, paused identity probe |
| Token generation fails | Same-business app/System User, admin rights, app installation, app-secret proof |
| App asks to go Live | Exact API error, use case, own vs third-party asset, dashboard requirements |
| Card verified but account restricted | Failed transaction vs amount due vs payment eligibility vs account review |
| Campaign created but no delivery | Effective statuses, review, billing, schedule, bid, audience, identity, creative |
| Old paused campaign cannot start | Refresh dates, budget period, policy/review state, creative availability |

## 12. Observed post-mortem

Full post-mortem → `10-practical-case-library.md` §6G (technical-readiness pattern; that section's workflow pointer returns here).

## 13. Sources and uncertainty

[Marketing API overview](https://developers.facebook.com/docs/marketing-apis/) · [official Postman collection](https://www.postman.com/meta/facebook-marketing-api/documentation/0zr4mes/facebook-marketing-api-mapi) · [Business SDKs/App Secret Proof](https://github.com/facebook/facebook-python-business-sdk) · [Advertising Standards](https://transparency.meta.com/policies/ad-standards/) · [Account Status](https://www.facebook.com/help/1392616391875085/) · [ad-review/restriction/support guide](https://www.facebook.com/business/ads/review-policy-guidelines) · [Business Support Home](https://business.facebook.com/business-support-home/) · [Meta Status](https://metastatus.com/) · Ads MCP controls report (secondary, verify live): https://fbki.la/v-business-suite-upravljat-servera-ads-mcp — superseded by public Ads MCP docs (`developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/*`, fetched 2026-09-02).

Business Help Center often requires live login — verify exact billing/support click paths in-product. Error subcodes, app-mode requirements, permission combinations, Accounts Center privacy prompts are rollout/account-specific unless a current primary source says otherwise.
