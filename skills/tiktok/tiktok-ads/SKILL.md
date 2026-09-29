---
name: tiktok-ads
description: "TikTok Ads strategy and diagnosis: research-first intake, objectives and optimization events, account structure, targeting, bidding and budgets, creative and Spark Ads, tracking and attribution design, policy and restricted verticals, catalogs and TikTok Shop. Executing launches via MCP/API = tiktok-ops."
---

# TikTok Ads

Reviewed **2026-09-14** against TikTok's full official documentation plus RU/EN practitioner
sources. UI, eligibility, policy, pricing and benchmarks are volatile — verify the current primary
source when the answer depends on current behaviour (`00`).

Operate as a senior practitioner who has not worked this account before: derive, do not assume.

## This skill ships no default strategy — on purpose

The three inputs that decide structure — the payout event, the conversion volume the account can
feed, and the GEO's policy and auction — vary more than the platform does. Anything shaped like a
universal launch template is an artefact of one GEO and one vertical.

**Read `references/01-research-protocol.md` before proposing anything.** It owns the intake, the
constraints gate, the bounded research pass, and the derivation. The rest of this skill is the
material that protocol draws on.

Diagnosing an existing account rather than planning a new one? Go straight to `09` (diagnosis order)
and the reference the symptom names — but come back to `01` § H before you change the strategy,
because "which input was wrong" is a derivation question, not a reporting one.

```
intake → constraints gate → bounded research → derive → pre-mortem → plan → execute → review
```

## Guardrails — these fire before any reference is read

1. **TikTok's `operation_status` defaults to `ENABLE`.** An object created without it is live and
   spending. Opposite of Meta.
2. **`bid_type` has exactly two values** — `BID_TYPE_NO_BID` (Maximum Delivery) and
   `BID_TYPE_CUSTOM` (Cost Cap). Meta's bid vocabulary does not exist. Value/ROAS bidding is a
   separate axis (`deep_bid_type`) and **cannot be combined with Cost Cap**.
3. **TikTok publishes two learning numbers and they disagree** — "~25 results or 7 days" before
   volatility falls, and "7 days to reach 50 conversions" for an underperforming ad group. Use 25
   to decide when a number is readable and 50 to decide whether a structure can be fed (`05`).
   Porting Meta's hard 50-conversion exit gate makes you
   over-consolidate and mis-time every verdict.
4. **The "±20% budget change resets learning" rule appears in no TikTok document.** The one
   documented budget rule is that an update must be **≥105% of current spend**.
5. **There are no location exclusions.** You positively select. Rewrite any exclusion-based plan.
6. **Attribution window locks at ad-group creation** and is not a reporting parameter. Two windows
   means two ad groups, decided up front.
7. **Currency, timezone and country are permanent at ad-account creation**, and budget minimums are
   `base × per-currency ratio`. A USD template on a JPY (×100) or IDR (×10,000) account is wrong by
   orders of magnitude, upward.
8. **There is no `SALES` objective enum** (it is `WEB_CONVERSIONS`/`PRODUCT_SALES` +
   `virtual_objective_type`), **no Store Traffic objective**, and **Collection Ads can no longer be
   created**.
9. **Tracking fails silently.** Hash mismatches, `event_id` mismatches and dropped `ttclid` throw no
   error anywhere. Fire one real test conversion and watch it arrive before launching.
10. **A rejected ad cannot be enabled into life** — build a new one. And an appeal re-reviews the
    **whole ad group**, with **one appeal allowed**.

## Minimum context

Infer what you can; ask only for what changes the decision, and state your assumptions.

GEO · vertical · offer and **which tracker status pays** · conversion lag · break-even CPA/ROAS ·
expected daily conversions at target CPA · account type and **your role on it** · tracking stack ·
creative supply per week · budget and decision horizon · **account currency and timezone**.

Missing the payout event, break-even, or tracking → you cannot judge a result.
Missing GEO, vertical, or access → you cannot know the campaign is legal to run. `01` § A.

## Model

```text
Business Center -> members / partners / assets / billing
  Ad account   -> currency + timezone (permanent), balance, role
    Campaign   -> objective, special categories, CBO
      Ad group -> optimization goal, event, bid, budget, placements, targeting, ATTRIBUTION (locked)
        Ad     -> identity, creative, text, CTA, destination
```

Diagnose at the level that owns the setting. Campaign, ad group and ad each carry their own status —
check all three separately.

## Route references

Read only what the task needs.

| Need | Reference |
|---|---|
| Evidence labels, source precedence, doc conflicts, what expires | `references/00-evidence-and-maintenance.md` |
| **The research-first workflow — read before proposing anything** | `references/01-research-protocol.md` |
| BC, roles, asset sharing, agency accounts, billing, suspension deadlines | `references/02-account-model-and-access.md` |
| Objectives, goal×billing matrix, Smart+, GMV Max, structure | `references/03-objectives-and-structure.md` |
| Targeting fields, custom audiences, lookalike limits and GEO gate | `references/04-targeting-and-audiences.md` |
| Bidding, VBO unlock thresholds, budgets and currency math, learning, pacing | `references/05-bidding-budgets-delivery.md` |
| Creative specs, safe zones, identity types, Spark Ads and expiry, rejections | `references/06-creatives-identity-spark.md` |
| Pixel, Events API, dedup, attribution, EMQ, trackers and macros, consent | `references/07-tracking-pixel-events-api.md` |
| Policy, restricted verticals, per-GEO gates, review and appeals | `references/08-policy-verticals-geo.md` |
| Diagnosis order, fatigue, benchmarks, scaling, reporting mechanics | `references/09-diagnostics-and-optimization.md` |
| Catalogs, TikTok Shop, GMV Max exclusivity, commerce reporting | `references/10-ecommerce-catalog-shop.md` |
| RU/EN field knowledge, agency cabinets, transcript extraction, evidence quality | `references/11-practitioner-field-notes.md` |
| Vertical shapes — **templates for the derivation, not strategies** | `playbooks/` |
| **Execution**: official TikTok MCP server (the default surface), preflight/audit guard rails, error and status codes | skill `tiktok-ops` |

Always read `00` before stating a policy, an eligibility, a limit, or a benchmark.
Always read `08` before touching a regulated vertical — **before any ad object exists.**

## Do not port Meta

Universal media-buying principles **do** port: break-even math, sample size, one-variable tests,
cohorting on click date, the operating contract. Platform mechanics **do not**.

Ported assumptions that are wrong here: objects create paused · bid-strategy names · a hard
50-conversion learning *exit gate* (TikTok has no exit gate; it publishes 25 and 50 for different
questions, `05`) · ±20% budget rule · location exclusions · attribution as a reporting setting ·
Collection Ads · Store Traffic · silent-autoplay creative (TikTok **requires audio** as policy) ·
"3–5 ad groups × 3–5 creatives, ABO then CBO" as doctrine (`11` — it is Meta convention with no
TikTok test behind it).

Where a rule came from Meta practice, say so and check it against a TikTok source before it reaches
a plan.

## Output

Lead with the decision. Then: evidence level and assumptions · exact actions at the correct level ·
budgets in **major units with the currency named** · the measurement window and attribution basis ·
stop/scale/rollback conditions · what you did not verify.

Use cases and benchmarks as mechanism analogies, never as forecasts. If you cannot name a number's
source and date, do not state the number.

## Boundary

Strategy and diagnosis live here. **Execution lives in `tiktok-ops`**, whose default surface is the
**official TikTok MCP server** — it covers essentially every operation, needs no API key, and the
operator authorizes it once in a browser. Nothing in this skill authorizes spend.

Before any MCP create call, `tiktok-ops` runs `ttops preflight` (validates the plan and emits the
exact tool arguments with `operation_status: DISABLE`); after it, `ttops audit` (diffs the read-back
and flags anything live). Both run offline with no token.

For regulated or sensitive verticals, verify current TikTok policy and local law (`08`). This skill
documents the compliant path and what it costs; it does not implement cloaking, review-layer
filtering, fabricated events, or landing-page swaps after approval.
