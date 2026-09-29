# 23 — Disabled ad account / "Spam" right after approval: triage

Written 2026-09-29. Reference case (n=1, cause not proven): tr-1 act_<ACCOUNT_ID> (USD, Europe/Istanbul),
one CBO campaign, 3 image ads. All 3 approved, then each DISAPPROVED "Spam" within 1-2 min
(13:32:50, 13:33:21, 13:38:42 UTC), account `status 2` / `disable_reason 1` at 13:40:52 UTC, ~$9
billed, $0 ad spend, code-17 throttle on the API right after. Enum and the reason-1 reading: `07`.

## Do not (operator rule)
- Do not edit, rename, re-upload or resubmit any ad of that account, and do not switch to
  `--allow-disapproved`. Switch ads off and leave them.
- No token re-mint, no Page/pixel/profile edits, no API retries (the account is on a ≥30 min cooldown,
  `metaops pace`). Freeze (`01`).

## Read (read-only, once)
1. `GET /act_<id>?fields=account_status,disable_reason,amount_spent,balance,currency,timezone_name`.
   `account_status` 3 = billing, not a ban (`05`, clears when the card charges). `account_status` 2 with
   `disable_reason` 1 = Account Integrity; `disable_reason` 3 = payment risk (worth resolving, `05`); other
   names in `07`.
2. Ads: `effective_status` and `ad_review_feedback` per ad (`metaops review`, exit 1 on rejects). "Spam"
   on ALL ads within minutes of approval, at $0 spend, points at the account/Page/domain, not the
   creative. Compare: one creative rejected "Online Gambling and Games" in one state and approved in
   another is content/state, not the account (`07`, `casino.md`).
3. Activity log of the account (`GET /act_<id>/activities`, used on 27/09 for la595) for who/what changed
   just before; and the Ads Manager dialog text (UI). Save the exact text, policy code, asset id, time.
4. Siblings sharing the card, Page, pixel, PWA domain, system user or proxy: list them and their status.
   Do not launch on them until the decision below.

## Options
- **Appeal (UI only):** Business Support Home → the account → Request review; only admins can file
  (`meta-ads/07` §8). Reason 1 appeals rarely succeed (`05`); at most one, evidence-based, no duplicates.
  Practitioner notes say two rejections are final (`the operator's research notes`, unverified).
- **Replace:** another account, minimal footprint → `26`. On an agency BM the TL decides
  "appeal or replace" (`03`); on the own BM the operator does.
- **Payment case (`account_status` 3, or `disable_reason` 3):** resolve billing, then re-check; the
  case most often worth fixing (`05`).

## Record
Survival log entry (`03`, `06`): account id, date/time, spend, reason, ads, Page, card (last 4 only),
pixel, launch method and pacing, names/headline used. Add the fingerprint to `06`.
