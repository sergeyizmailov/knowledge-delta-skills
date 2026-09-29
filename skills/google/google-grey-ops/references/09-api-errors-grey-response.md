# 09 — API errors: the grey survival response

Canonical code → cause → fix is `google-ads/11` (the API-owner skill). **This file is the response
layer only**: what an error means for account survival and whether to freeze, replace, or rotate.
Look codes up in `11`; act here. Structure mirrors `meta-grey-ops/05`.

**The Google inversion:** on Meta, an API error usually reports a *token/session* problem. On
Google, the same shapes usually report a **customer-state or billing** problem — the API is often
the **first** place a suspension surfaces, before any email arrives. Read errors as account
telemetry, not bugs.

## `AuthorizationError.CUSTOMER_NOT_ENABLED` → the account is gone or was never live

Not a code bug. Three distinct realities behind one code, and they need opposite responses:

| Reality | How to tell | Response |
|---|---|---|
| Suspended | Account visible in UI with a policy banner | Classify the enforcement track (`04`) **before** touching anything. Track A = do not appeal, replace |
| Never completed setup | No billing profile, no first payment | Finish setup; nothing is wrong |
| Cancelled / dormant | Prior spend, now closed | Reactivate via UI, not API |

Never retry the call in a loop — a hot-loop against a suspended customer is an automation
fingerprint on an account already under review.

## `USER_PERMISSION_DENIED` → check `login-customer-id` before assuming a ban

Most common cause: a **wrong or missing `login-customer-id` header**, not a lost account. Verify
the header, then the MCC link, then account status. Only after all three point the same way is
this an enforcement signal.

**Grey caveat:** also the signature of **being unlinked from an MCC mid-flight** — an agency
pulling the account back. Commercial event, not a policy one; fix is a conversation, not a
rotation.

## `DEVELOPER_TOKEN_NOT_APPROVED` → a supply problem, not a code problem

Test-tier token against a production account. On grey infra this usually means the **token's own
MCC** is under review, not the child account — every account under that token blocks at once.
Keep a **second developer token on an unrelated identity** — highest-value redundancy in Google
API grey ops, must exist *before* you need it.

🔺 The **2026-06-15 cutoff** blocks new tokens from classic gclid OCI (`tracker-ops/04`). A
replacement token is **not** a like-for-like restore of measurement capability. Plan the second
token now or accept the fallback loses offline conversions.

## OAuth token death → regenerate once, then stop

`OAUTH_TOKEN_INVALID` / `OAUTH_TOKEN_EXPIRED`: re-run consent. Two grey-specific traps:
- **Consent screen still in Testing status = refresh tokens expire after 7 days.** Recurring
  weekly death with no other symptom = this, not enforcement. Publish the app.
- Repeated token death in a short window on a *published* app = the **Google identity** is under
  security pressure. Switch to freeze protocol (`01`): no re-logins, no profile edits, no new OAuth
  grants until it settles. Every extra regeneration is another signal.

## `PolicyViolationError` / `PolicyFindingError` → decide before you exempt

API returns the matched policy topic and, where exemptible, the key to request an exemption.
Before requesting: **an exemption request is an explicit claim to a reviewer that your ad is
compliant.** On a Track A vertical it draws human attention to an account you'd rather leave
un-looked-at. Edit the text instead unless the finding is a genuine false positive. Exemption
mechanics → `google-ads/11`.

Repeated findings **across accounts on the same creative family** = pull the creative
portfolio-wide, not just where it fired (`04`, cross-account pivots).

## `QuotaError` / `RESOURCE_EXHAUSTED` → back off, and read it as a fingerprint

Exponential backoff, never hot-loop. **Sustained quota exhaustion is itself an automation
signature** — a grey portfolio hammering the cap looks unlike a normal advertiser. Spread
operations across time and tokens rather than maximizing throughput on one.

Basic tier is 15k operations/day. Applying for Standard means **more scrutiny of the MCC** — a
real trade-off on grey infra, not an automatic upgrade.

## Billing-adjacent errors → the highest-risk class on Google

Anything failing around a payment event needs different handling, because Google's trust anchor
is the billing identity (`04`). A mutate failing immediately after adding a card or crossing a
threshold charge is **not** a coincidence to retry through. Stop writes, verify account state in
the UI, treat as a possible identity flag until proven otherwise.

## Silent failure — the case that throws nothing

Major versions **remove** fields. A query hardcoded to an older field set returns **200 OK with
silently missing data**. On grey portfolios this shows as accounts that look healthy in your
dashboard because the death signal stopped being fetched. **Assert field presence in report
parsing, not only in error handling** — otherwise your forensics log (`04`) quietly fills with
nulls and attribution dies with it.

## Triage order

1. Is it billing-adjacent in timing? → stop, verify state, do not retry.
2. Is it customer-state (`CUSTOMER_NOT_ENABLED`)? → classify the enforcement track (`04`) first.
3. Is it header/permission (`login-customer-id`, MCC link)? → fix and continue; not an enforcement signal.
4. Is it token? → regenerate **once**; recurring = freeze protocol (`01`).
5. Is it schema/quota/policy? → mechanical, fix in `google-ads/11` — but log it, because rate and
   clustering are forensic input (`04`).
