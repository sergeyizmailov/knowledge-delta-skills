# 05 — API errors: the grey survival response

Reviewed 2026-08-28; rows for disable / disapproval / retries updated 2026-09-29. Codes and canonical meaning are [official], live in
`meta-ads/14`. The freeze/replace/rotate mapping here is practitioner judgment
about what an error implies for account survival — no Meta source states it.

Matching rule: branch on `code` + `error_subcode`, never the message string —
`meta-ads/14` owns that rule (field-observed codes 1815857, 3858040, 2446814,
1815045, 3738001 are still safe to match numerically). Log `error_user_msg` as
evidence only.

| Trigger | Grey response |
|---|---|
| Auth 190, subcode 460 (password/security rotation), 463 (expired), 467 (invalid — still emits "user logged out" in the wild) | Mint new token, re-exchange (`meta-ads/14` auth; lifecycle `02`). Regenerate ONCE, exchange to long-lived, stop — every extra regen during a flag pokes the bear (`01`) |
| Subcode 460 specifically, or repeated token deaths in a short window | Persona under security pressure → freeze protocol (`01`): no re-logins, no profile edits, let it settle |
| 31 / 3858013 phone not verified (first ad on a new account) | Persona verifies phone in Ads Manager, then resume the same plan. Not an account flag; don't re-mint or rebuild |
| Access denied (10 / 200) | Not a code bug — check BM asset shares (pixel/pages to the ad account, `03`) and access tier (`02`: your own app on agency accounts sits at Limited). A write-probe (create one PAUSED object) proves write access; GET does not |
| Pixel "no access" (1815045) | Assign via BM Data Sources → Datasets, or ask the agency; ads recover automatically, no rebuild (`03`) |
| "Not delivering", no error | Future start_time (normal), review pending, billing hold, or spend cap — wait/verify before touching |
| Account "Disabled"/restricted | Routine in agency stock. Document (ID, date, spend at death, `disable_reason`). Agency/old-personal/log accounts are consumables: buyer doesn't appeal alone, asks TL/agency "appeal or replace". Payment/risk bans are worth resolving; Account Integrity/automation (reason 1) appeals rarely succeed (`03`). Step by step → `23` |
| `account_status` 3 UNSETTLED / "Payment needed" | Billing, not a ban — recovers once the card charges; `balance` = unbilled cents, not prepaid (FIELD 2026-09-27) |
| Ad DISAPPROVED (2490468 on enable) | Switch it off; operator rule: do not edit or resubmit; never re-upload the same creative/angle/PWA into that account — reads as circumvention (FIELD 2026-09-27). New ad = different creative (`07`) |
| Any transient error on a non-idempotent create (503, dropped connection) | `outcome_unknown=true`: raised once, never retried (`graph.py`, 2026-09-29). Reconcile via `status`/Ads Manager before repeating (`16` failure contract) |
| Code 200 "ads_management/ads_read" from a System User token, account missing from `client_ad_accounts` (field-observed 2026-09-22) | Reads like a scope gap but isn't — account disabled AND removed from the portfolio. Treat as dead stock: document, request replacement, don't burn time re-checking scopes/tokens (`03`) |
| CSV import blocked on fresh accounts (3738001) | Build via API/UI instead |
| Rate limits 17/4/32/613 (BUC/header-driven, detail in `meta-ads/14`) | Stop, don't retry — retries extend the block (Graph docs). Limited tier ≈300 calls/h per ad account, ~300s block: a single buyer DOES hit it (`04`). Record ≥30 min cooldown for that account; no polling loops. FIELD 2026-09-27: a 12-min sleep-retry storm preceded an Account Integrity disable (`06`, cause unproven) |
| Rising bot_share / domain-level flags (tracker-ops/03, not an API error) | Rotate the domain before it burns the account — don't wait for the ban |
- **100/2446289** "Ad Creative Is Incomplete — the post you selected is not available": seen 2026-09-26 on a DISAPPROVED (Spam) catalog ad after a set swap. Both `status=DELETED` and HTTP DELETE fail on the ad AND its ad set; `status=PAUSED` on the ad set works. Delete it in Ads Manager UI.

- **10803 / 1798073 "Product set with the same filters already exists"** on a set filter update: another set in the catalog already has that exact filter (e.g. two one-product sets swapped to the same SKU). Meta compares the filter literally: use an equivalent shape. `mutate_set.py` walks is_any → eq → `and`/`or` wraps automatically (field 2026-09-26: third set on one SKU needed the `and` wrap).
