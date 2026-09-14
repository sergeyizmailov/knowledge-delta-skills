# 00 — Evidence rules, source map, and maintenance

Read this whenever a claim drives spend, or when something in this skill disagrees with what you are
seeing in the account.

## Evidence labels

Label material claims. The label tells the reader what happens if the claim is wrong.

| Label | Meaning | How far it travels |
|---|---|---|
| **OFFICIAL** | Stated on a current TikTok page or API reference | Authoritative until TikTok changes it. Date it |
| **LIVE ACCOUNT** | A read call against this advertiser | Authoritative **for this account only** |
| **MEASURED CASE** | A published study with sample size, period, GEO, method | A prior with provenance. Never a forecast |
| **BENCHMARK** | An industry aggregate | A prior. State the source, sample and period, or drop it |
| **PRACTITIONER** | What buyers report | A hypothesis. Useful where docs are silent |
| **UNVERIFIED** | Could not confirm | Say so explicitly rather than rounding to a fact |

Two rules that matter more than the taxonomy:

- **Never convert a benchmark or a case-study lift into a forecast.** "This agency saw −29% CPA" is
  not "you will see −29% CPA".
- **A live-account reading beats a doc about what should be possible.** Eligibility, allowlisting and
  feature availability are per-account, and TikTok says so repeatedly ("tool availability may vary by
  region and account configuration").

## Source precedence

1. **TikTok API reference** — `business-api.tiktok.com/portal/docs`. Authoritative for field names,
   enums and limits.
2. **TikTok help centre** — `ads.tiktok.com/help/article/…`. Authoritative for product behaviour and
   policy. It blocks automated fetch; **`ads.tiktok.com/resources/help/article/…` serves the same
   content** and is fetchable.
3. **The live account** — a read call through MCP or `ttops`.
4. **TikTok for Business blog / newsroom** — launches and dated changes.
5. Independent measured writeups.
6. Practitioner communities (`11`).

When 1 and 2 disagree — and **they do** — say so rather than silently picking. Known live conflicts:

| Conflict | Resolution |
|---|---|
| Campaign minimum budget: Budget guide says 20, per-currency table and Ads Manager say 50 | Use **50**. Two sources, and it matches the UI |
| Click-through attribution options | **Resolved, no longer a conflict:** `/adgroup/create/` does list `FOURTEEN_DAYS` and `TWENTY_EIGHT_DAYS`. Which values an ad group may use depends on the objective — separate doc `1777694366654465` |
| Smart+ objectives: help centre lists Traffic, API reference does not | Trust the **API reference** for what the API will accept |

## Fetching the docs: the portal is a SPA, the gateway behind it is not

`business-api.tiktok.com/portal/docs` is a JavaScript SPA — WebFetch cannot read it. It is backed by
an **unauthenticated gateway API**, so the docs are fetchable programmatically instead of by hand:

```
tree: https://business-api.tiktok.com/gateway/api/doc/client/platform/tree/get/
      ?identify_key=<key>&language=ENGLISH&is_need_content=false
node: https://business-api.tiktok.com/gateway/api/doc/client/node/get/v2/
      ?language=ENGLISH&identify_key=<key>&doc_id=<id>
```

The tree endpoint returns the doc-id tree for the whole reference; the node endpoint returns one
page's content by `doc_id`. Walking the tree and fetching each id reproduces the full reference —
roughly 1,214 pages as of 2026-09-14. `identify_key` was
`c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b` as of that date; if it has
rotated, open the portal and read it off any of its own network requests.

For the help centre (not the API reference): `ads.tiktok.com/help/article/…` returns 403 to
automated fetch, but `ads.tiktok.com/resources/help/article/…` serves the same content and does not.

Anything you fetch this way is **a snapshot that ages**. It is authoritative for *shape* — field
names, enums, payload structure — and only indicative for *numbers* — policy, eligibility, price,
limits — which must be re-fetched at use time, not read from a snapshot, when they drive a decision.

## Volatility: what expires, and how fast

| Half-life | Content |
|---|---|
| **Weeks** | Per-GEO vertical eligibility · allowlist gates · Smart+/GMV Max behaviour · benchmark figures · third-party tool support |
| **Months** | Enum additions and deprecations · budget minimums · rate-limit tiers · MCP tool surface · creative specs |
| **Years** | Object model · auth model · dedup and attribution mechanics · the media-buying math |

**Everything in the "weeks" row must be re-checked at use time.** That is not a caution, it is the
operating procedure in `01` § C1.

## Dated claims with a short fuse

Re-verify these before repeating them:

| Claim | As of | Why it will move |
|---|---|---|
| Official MCP server, two endpoints, 30-day authorization | 2026-09-14 | Launched July 2026, auth endpoints August 2026. Actively changing — read the changelog |
| Smart+ API supports only `APP_PROMOTION`, `WEB_CONVERSIONS`, `LEAD_GENERATION` | 2026-09-14 | The help centre already claims more |
| Non-CBO App Install VBO Smart+ blocked via API | end of Sept 2026 | Dated change, in force imminently |
| ~~Social casino: Guatemala only~~ | **Retracted 2026-09-14** | Guatemala does not appear anywhere on TikTok's current Gambling and Games policy page. The per-market matrix is login-gated — look it up live, never quote a country from memory |
| GMV Max mandatory for TikTok Shop sales campaigns | July 2025 onward | Practitioner-dated, not confirmed against a deprecation notice |
| `ClickButton` / `PlaceAnOrder` sunset | 2027 | Dated deprecation |
| Legacy MMP postback flow discontinued | 31 March 2025 | Already in force; stale tutorials still teach it |
| US divestiture closed, TikTok USDS JV | 22 January 2026 | Ownership settled; algorithm/moderation details still opaque |
| EU DSA preliminary findings, fines up to 6% of global turnover | Feb & July 2026 | Preliminary, not final. Design changes may follow |

## Numbers this skill deliberately does not give you

- A TikTok CPM, CTR or CVR benchmark. The published figures disagree by more than 2×, and a large
  share of 2026 benchmark content is fabricated (`09`, `11`). Use the account's own history and
  break-even math.
- A per-country gambling or finance eligibility table. Sources contradict each other, and TikTok
  changes it silently. **Verify live** (`08`).
- A recommended campaign structure. Derive it (`01`, `03`).
- A creative refresh cadence as a rule. Derive it from the account's own fatigue curve (`06`, `09`).

If a user asks for one of these, give the method and the reason, not a number you cannot defend.

## Maintaining this skill

**Refresh when:** TikTok publishes an API version or a deprecation; the MCP changelog moves; a
GEO/vertical gate changes for a market you work; a reference's dated claims pass their fuse; or a
live account contradicts a stated rule.

**How:**
1. Re-fetch the affected docs via the gateway API (above).
2. Diff the enums against `tiktok-ops/03` and `scripts/ttops/spec.py`.
3. Re-run the offline suite — `PYTHONPATH=scripts python3 -m ttops.selftest`. A changed enum that
   breaks a test is the point.
4. Update the dated table above, and the `Reviewed` line at the top of each reference touched.
5. Record account-specific contradictions in the **project's** `.notes/`, not in the skill — they are
   evidence about one account, not a platform rule.

**Date every reference individually** so staleness is visible per file rather than per skill.

## Known gaps, stated plainly

- `ttops` has **not been run against a live advertiser**. 102/102 offline tests pass; that is not the
  same evidence.
- The official MCP tool **schemas are unpublished** — introspect at runtime (`tiktok-ops/01`).
- **Business Center suspension blast radius is undocumented** by TikTok (`02`, `08`).
- **Reddit and the major practitioner forums were unreachable** during research; the EN field picture
  comes from agency blogs and case studies, not forum primaries (`11`).
- Exact safe-zone pixel values are not published by TikTok; only the in-product overlay is
  authoritative (`06`).
- Whether a cross-BC-shared pixel keeps firing after revocation is unverified (`02`).
- The minimum role required to authorize a developer app against an advertiser is unstated by TikTok
  (`02`, `tiktok-ops/02`).
