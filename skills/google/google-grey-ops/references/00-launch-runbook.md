# 00 — Launch runbook (start here for any API launch)

Ordered path "have credentials" → "spending". Every other file is an exception handler for one
step below. Reviewed 2026-09-02. `googleops` (`10`) is the only agent-facing write interface;
never hand-assemble a `MutateOperation`.

```
0 gate → 1 access → 2 tracking → 3 spec → 4 plan (validate_only) → 5 apply PAUSED (one or bulk)
→ 6 verify → 7 review layer → 8 activate → 9 first hour → 9.5 daily sync → 10 kill rules
```

## 0 — Path exists?

Vertical certification per geo (`google-ads/09`) before any object exists; gambling changed three
times in 2026, financial services verification is per country. No-path surfaces: `08`. Regulated →
certification is account-bound, a replacement account needs a new one.

## 1 — Access

Operator hands over, verbatim into gitignored notes: developer token (MCC-level), MCC id, client
customer ids, OAuth client + refresh token **or** a service-account key, Merchant Center id, tracker
campaign URL, proxy. Then:

```bash
export GADS_DEVELOPER_TOKEN=… GADS_CLIENT_ID=… GADS_CLIENT_SECRET=… GADS_REFRESH_TOKEN=…
export GADS_PROXY='http://…' # or GADS_ALLOW_NO_PROXY=1
googleops --workspace . --profile <p> --json workspace validate
googleops --workspace . --profile <p> --json doctor
```

`doctor` exit 0 or don't launch. Gates, each separate: credential lists the MCC ·
customer reachable through `login_customer_id` · currency/timezone match the profile · status
ENABLED and not a manager · auto-tagging on · an APPROVED billing setup · at least one conversion
action counted in Conversions · Merchant Center linked when the profile names one ·
`validate_only` write probe. **A successful GAQL read proves none of the write gates.**

Access facts that decide the setup (verified 2026-09-02, primary docs):

- **Service accounts work without Workspace delegation**: add the service-account email as a
  user in the MCC (Admin → Access and security), point `GADS_JSON_KEY_FILE` at the key. Admin
  rights on a service account need a separate upgrade step. Headless, no refresh-token expiry.
- OAuth refresh tokens die after **7 days** while the consent screen is in **Testing**; the
  `adwords` scope has no exemption. Publish to Production before minting the token.
- Developer token access level is not queryable; Basic = 15,000 ops/day shared across every
  account the token touches. Test-account-only tokens fail on production customers with
  `DEVELOPER_TOKEN_NOT_APPROVED` (`09`).
- **Google Ads API client = PyPI `google-ads` (31.4, py3.9–3.14)**. `googleads` (v50+) is the
  dead AdWords/DFP library; baseline agents reach for v17-era code — the current graph shapes
  differ (`10`).

Credential errors → `09` and `google-ads/11`. Doctor problems on billing/verification → `02`, `06`.

## 2 — Tracking before spend

`tracking_url_template` with `{lpurl}` + `{gclid}` (spec rejects a template without `{lpurl}`),
tracker campaign mapping, conversion action that Smart Bidding will chase (`doctor` lists them),
and whether this developer token can still onboard offline conversion import (2026-06-15 cutoff,
`google-ads/06`; new tokens → Data Manager, `tracker-ops/04`). Name campaigns so the tracker can
split on them; `{tag}` in the spec is stamped per customer by `bulk-plan`.

## 3 — Write the spec

Copy the nearest `scripts/specs/example-*.json`. `currency` must equal the profile currency
(stops a USD template landing on a JPY account at 100×); `daily_budget_major` above the profile
`budget_cap_major` is rejected — raise the cap in `workspace.json` deliberately.

| `campaign.kind` | Shape | Notes |
|---|---|---|
| `search` | ad groups → keywords + RSA (3–15 headlines, 2–4 descriptions) + optional sitelinks | Partners/Display off unless `network` says otherwise |
| `pmax_retail` | asset groups → text + images + optional `listing_filter` on one dimension | `merchant_id` from profile; `final_url_expansion` default false; brand exclusion via shared-set id |
| `shopping` | ad groups → `listing_groups` partition on one dimension with explicit `others` | `campaign_priority` 0–2; only matters when campaigns share products+country+language |

Defaults every campaign gets: PAUSED at every level · `positive_geo_target_type` PRESENCE
(Google's default is presence-or-interest) · EU political advertising declared (required field,
spec forces an explicit boolean) · non-shared daily budget · negative geo PRESENCE.

## 4 — Plan

```bash
googleops --workspace . --profile <p> --json plan --spec launches/x.json [--tag T1]
```

Normalizes the spec, builds the whole graph with temp ids, runs it with `validate_only=true`,
writes a hash-bound plan under `.googleops/plans/`. Editing the spec afterwards does not change
the plan — re-plan. PMax: text/image assets must exist before the asset group links them, so the
plan validates the asset request separately; `validation_scope` in the result says whether the
graph itself validated fully or only after asset creation.

## 5 — Apply

```bash
googleops --workspace . --profile <p> --json apply --plan .googleops/plans/<plan>.json
```

One atomic mutate (PMax: assets first, then the graph). Resume-safe: an existing state with a
campaign resource returns immediately. `in_flight` set and no response → the request outcome is
unknown; check the UI for the campaign name before clearing it. Failure returns the flattened
`GoogleAdsFailure` (code, message, field path, trigger) → `google-ads/11`, then `09`.

Bulk: `bulk-plan --template --accounts accounts.json --run wave-1` validates every customer's
doctor receipt and graph before anything is created; `bulk-apply --verify` builds and reads back
each; failures stop the wave unless `--continue-on-error`.

## 6 — Verify

```bash
googleops --workspace . --profile <p> --json verify --plan .googleops/plans/<plan>.json
```

Reads back and diffs: status, budget micros and non-shared flag, bidding strategy type, geo type,
EU declaration, tracking template, networks, merchant id / feed label / priority, final-URL
expansion, locations, languages, negatives, brand exclusion, ad group types and bids, keywords,
RSA headlines, listing partitions / filters node counts, asset group asset counts, search themes,
and every `policy_summary.approval_status`. Exit 0 writes `<state>.verified.json`; activate
refuses without it or after any state change. Facts it cannot diff (ad review pending,
`primary_status` NOT_ELIGIBLE reasons) are returned for you to judge.

## 7 — Review layer (grey only)

`05`: Final URL is the white, same registrable domain, cloak **off** until serving. Search only —
do not PMax, do not cloak App campaigns (`08`). Confirm tz/currency and OFAC vs serve-geo (`07`).
Ads enter policy review the moment they exist even while PAUSED; a DISAPPROVED ad cannot be
enabled — build a new one (`verify` flags it).

## 8 — Activate

```bash
googleops --workspace . --profile <p> --json activate --plan .googleops/plans/<plan>.json \
  --confirm-ui REVIEWED --confirm SPEND [--refresh-start 2026-09-04]
```

Ads → ad groups / asset groups → campaign last; stops on first failure. Before `SPEND`, confirm
with operator: budget in **major units and currency**, destination, tracker receipt, `verify` exit 0
on this exact state, approval status not DISAPPROVED. Bulk: `bulk-activate --customer <id>` per
reviewed account — no activate-all, deliberately.

## 9 — First hour

- `googleops status --plan …` → `primary_status` + reasons, `serving_status`, cost today.
  `NOT_ELIGIBLE` with `PENDING_REVIEW`/`BUDGET_CONSTRAINED`/`MISSING_ASSETS` are the usual reasons.
- Search/Shopping metrics lag ~3 h; PMax asset-group data longer. Zero impressions in hour one
  is not a delivery failure.
- **Any budget or billing anomaly: pause first, diagnose second.**
- Payment events are the highest-risk moment on Google (`02`): do not add or change a card in the
  same session as activation.

## 9.5 — Daily sync

```bash
googleops --workspace . --json monitor --range YESTERDAY --jsonl survival.jsonl
googleops --workspace . --profile <p> --json report --out day.json --gaql \
  "SELECT campaign.name, segments.date, metrics.cost_micros, metrics.clicks, metrics.conversions
   FROM campaign WHERE segments.date DURING YESTERDAY"
```

Cost in micros, account timezone. Push into the tracker (`tracker-ops/01`); re-pull the last
7 days weekly to absorb conversion adjustments. Verdicts: SUSPENDED / REJECTS / SPENDING / IDLE.

## 10 — Kill rules, in writing

Spend-without-conversion cap, CPA cap, account verdict threshold, who decides on a ban wave.
Judge after the conversion-lag window, not the calendar (`google-ads/08`, `senior-buyer-ops/04`).

## When a step fails

| Symptom | Go to |
|---|---|
| Any API error code | `google-ads/11` cause+fix, then `09` survival response |
| `USER_PERMISSION_DENIED`, `CUSTOMER_NOT_ENABLED`, token dead | `09` |
| Verification/BOV demanded, "temporarily paused" | `06` |
| Billing hold, threshold charge, payment declined | `02` |
| Policy disapproval, suspension wording | `04` track first, then `05` / `google-ads/09` |
| Spec rejected locally | message names the field; shapes in `scripts/specs/` |
| Merchant Center not linked / products not eligible | `google-feed-ops/04`, `gmcops doctor` |
| Numbers disagree with tracker | `tracker-ops` metric rule |
