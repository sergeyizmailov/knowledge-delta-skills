# 07a — Vendor cloaking recipes & unverified submission hypotheses

Split out of `07-review-layer-and-cloaking.md` 2026-09-24: vendor-reported tool
configs and single-source hypotheses live here so the core `07` file stays
official-first. Everything below is **vendor-reported or unverified** — build
nothing load-bearing on it without a `06`-style one-axis test.

**Not authorization.** Using any recipe below to disguise a destination is
Circumventing Systems (named: cloaking · unicode/symbol obfuscation · obscure
images — live UI 2026-08-27; Meta 2026-02-26 lawsuit definition). Clean taxonomy
→ `meta-ads/07`. Survival response on detection → freeze/replace/rotate (`07`
failure signatures, `05`), never self-farmed evasion assets. `🔺` = do not
build on this; hypothesis, not rule.

## Vendor tool recipes (same AND-stack as `07` filter stack, different config surface)

Binom — Website URL = bare tracker, `utm_code` lives in URL Parameters (attaches
post-moderation, so reviewer hits untagged URL); Protect-FB rule = referrer
facebook + language EN/not-empty + not-Bot (headers+IP) + country=buy geo;
expect tracker clicks ≈2× FB clicks (bot traffic), offer discrepancy 3–5%.
Keitaro — `Bots IS → white`, `country=geo AND Bots IS NOT AND {{ad.name}}/utm not
empty → money`, default white; bot DB is generic, update Geo-DBs/Bots regularly.
Adspect — safe page must have no redirect; submit On-Review + blacklist all
Review IPs, switch to Filtering only after approval; Cloudflare yellow-cloud;
self-hosted only (Shopify/Wix/Tilda pre-banned by networks); never alter a live
white; JS-integration variant (visitor starts white, ajax.php swaps) is weaker —
a JS-capable reviewer sees money.

## Delivery-cloaking (steers targeting, not review) 🔺

Different goal: bot-differentiated content to manipulate Andromeda's audience-
expansion signal, not to pass review. Product still matches (not the named
substitution pattern) but is bot-vs-user differentiation — risk-bearing.
[practitioner, n=1, Partnerkin 2026-01, unverified, +30% ROI]: serve crawler UAs
content structured for a different audience signal than users see → delivery
explores audiences the user lander never attracted; readout = frequency at
scale, not CTR. Attribute with `06`'s balanced designs, one axis at a time.

## Submission-shape tricks (cheap, no cloak) 🔺

[practitioner, Praktichesky Arbitrazh 2026-09-08, no attribution design — one team's habits,
all changed together in one session. Hypotheses for `06`-style one-axis tests, not rules.]

- **Publish sequentially, one campaign at a time.** Mass-publishing (their example: 100
  accounts / 100 ad sets in one go) was blamed for a reject wave on bought spend accounts.
  Cheap to comply with and consistent with the burst-behaviour logic already in `01`.
  Adopted as pacing FIELD 2026-09-27: ≤1 campaign create per ad account per ~3h (`00` §5).
  `bulk-apply` creates all rows in one run; to publish sequentially, one
  `bulk-plan --only act_X` per wave (`16`).
- **Reject-recovery by duplicate-and-swap.** When part of a batch is approved and part
  rejected: duplicate an APPROVED ad set and swap the not-yet-used creatives into the copy,
  rather than editing or resubmitting the rejected one. Same logic as `04` Re-moderation: a
  rejected ad can't be re-enabled (2490468) → new object; never re-upload the rejected creative.
  They also changed domain and Page in the same recovery — so the swap alone is unattributed.
