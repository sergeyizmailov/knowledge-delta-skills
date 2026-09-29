---
name: google-feed-ops
description: "Google Merchant Center (GMC) launch and operation plus the retail data layer: new-account launch sequence (site trust → ToS → verify+claim → business info → shipping/tax → data source → review → programs → Ads link → first campaign), Merchant API v1 mechanics and the gmcops CLI, feed spec and attributes, feed rules and supplemental sources, titles, custom_label schema, GTIN, suspensions and appeals, MC↔Ads link, free listings, CSS. Use for: 'set up Merchant Center for a new store', 'products not showing / disapproved', 'GMC suspended Misrepresentation', 'push products via API', 'link Merchant Center to Google Ads'. Campaign types and PMax bidding live in google-ads; grey cascade in google-grey-ops."
---

# Google Feed Ops

Reviewed 2026-09-02. Baseline: Sonnet 5 / Claude Code subagent / 2026-09-02; 2026-09-03 blind suspension task [R] — site-review and second-account rules already known.
The retail data layer. Google Ads buys the traffic; **the feed decides what is eligible, what it
costs, and what gets suspended** — and the Merchant Center account is reviewed on the *site*, not
the feed. No Facebook analogue at this depth.

Route: buy mechanics → `google-ads` · infra/survival/agency accounts and MC↔Ads cascade →
`google-grey-ops` (`12`) · counting → `tracker-ops` · portfolio decisions → `senior-buyer-ops`.

## Check first

| Need | Reference |
|---|---|
| **New account → products serving, in order; first campaign on a fresh pair** | `references/04-gmc-launch-runbook.md` |
| **Merchant API v1 facts, what the API cannot do, `gmcops` doctor gates** | `references/05-merchant-api-ops.md` |
| Attributes, limits, submission methods, titles, custom labels | `references/01-feed-spec-and-submission.md` |
| Suspensions, the gates that block review, required website elements, ratings | `references/02-merchant-center-suspensions.md` |
| Standard Shopping priority ladder, PMax retail structure, product-level reporting, CSS | `references/03-shopping-pmax-retail.md` |

`gmcops` lives in `google-grey-ops/scripts/` (one uv project with `googleops`); usage in
`google-grey-ops/10`. Read-only doctor first: `gmcops --account <id> --json doctor --country US`.

## Three things that break accounts

1. **The five review gates.** Shipping settings · a data source for the target country · website URL
   claimed and verified · business address verified · US tax settings. **Missing any one blocks review
   entirely.** This is the real cause of most "products not showing" tickets — check before diagnosing
   anything else.
2. **Feed vs live page mismatch on price and availability.** Google's automated crawl fires
   preemptive item disapproval. It is automated, so **the fix is a sync fix, never an
   appeal-and-argue.** Compare against the **checkout total**, not just the product page.
3. **Promotional text in titles or descriptions.** A policy trigger, not a soft ranking issue.

## Migration status 🔺

- **Content API for Shopping sunset 2026-08-18.** Only API integrations broke — manual upload,
  scheduled fetch, Sheets, and platform connectors were unaffected.
- **Merchant API v1beta discontinued 2026-02-28**, earlier than the Content API sunset.
- Current: `merchantapi.googleapis.com`, stable **v1**.
- **UCP** (in-Google checkout via `native_commerce(checkout_eligibility)`) is **early access, select
  merchants, US/CA/AU only**. It did **not** replace Buy on Google, which shut down 2023-09-26.

## Model

```text
Merchant Center account -> verification gates -> data source(s)
  primary feed (structured) -> feed rules / supplemental feeds (overlay)
    product -> id / title / price / availability / GTIN / custom_label_0-4
      listing group filter -> asset group (PMax) or product group (Shopping)
        -> bid strategy per segment
```

**The throughline: label schema → listing-group filter → divergent bid strategy per filter** — how
per-segment economics happen without per-SKU bidding.

## Workflow

1. Clear the five review gates before anything else.
2. Establish **one primary submission method per data source** — mixing causes silent
   last-write-wins conflicts.
3. Fix required attributes and GTIN coverage — a missing real GTIN costs visibility and disables
   price benchmarking.
4. Build the `custom_label` schema before campaign structure, since structure depends on it:
   margin tier, price band, bestseller rank, seasonality, stock lifecycle (canonical table in `01`,
   don't reinvent).
5. Optimize titles for the **~70-character cliff**, specs before adjectives, decision-driving
   attributes first.
6. Confirm destinations and listing-group **keys** are valid. PMax/Shopping campaign structure, feed-only
   vs assets, brand exclusions, and product-level reporting live in `google-ads` (`01`, `07`).

## Guardrails

- **`id` is the join key. Never reuse or recycle it.**
- Never fake a `gtin` or `mpn` with an internal SKU — set `identifier_exists=no`.
- Never submit a `sale_price` without the real non-sale `price`. That is a misrepresentation trigger.
- `shipping_label` and `custom_label_0-4` are unrelated. Conflating them is a common integration bug.
- Use the **test/preview mode** on attribute rules. It prevents catalog-wide breakage.
- Campaign priority does nothing unless two campaigns share the **same products in the same country and
  language** — and an under-budgeted high-priority campaign silently falls back to the low-priority one.
- **AI title generation belongs in a testing sandbox, not in production.** Codify winning patterns into
  templates with fallback chains.
- **CSS is EEA/Switzerland/UK only. The ~20% figure has zero US applicability** — never cite it to a US
  advertiser.
- Merchant Center and Google Ads suspensions are **separate systems with separate appeals, but a
  linked pair is one blast radius**: a suspended Ads account linked to the MC suspends the MC, and
  unlinking afterwards does not clear it (official). Fix the Ads side first, then request MC review.
- **Never open a second MC account to escape a suspension** — same domain/store/identity gets
  suspended again and reframed as Circumventing systems.
- **Fix everything before requesting review.** 1–3 attempts before the button locks; each denial
  adds a growing cool-down. `issueresolution.triggeraction` (programmatic appeal) is allowlist-gated.
- Products are only writable via API into API-type data sources; processed products appear after
  several minutes; the key is `contentLanguage~feedLabel~offerId`.
- US tax settings, phone/address verification, and identity documents have no API surface — UI.

## Output

Lead with which layer the problem sits in — gates, feed data, policy, or campaign structure. Most
"campaign" problems in retail are feed problems. Give the exact attribute or setting, the expected
review timeline (3–5 business days initial, up to 7 for account suspension, 24–48h for a re-crawl), and
what to verify after the next refresh.
