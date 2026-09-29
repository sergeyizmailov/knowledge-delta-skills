# Catalog

Every skill, grouped by domain for browsing. On disk each skill sits in a category
folder (`skills/<category>/<name>`); install copies the skill directory itself, so it
lands one level deep in the runtime's skills directory (see the README).

## Media buying — Meta, Google & TikTok

Layered by concern, not platform: buy mechanics (`meta-ads`, `google-ads`) → survival
infrastructure (`meta-grey-ops`, `google-grey-ops`) → retail data layer
(`google-feed-ops`) → counting (`tracker-ops`) → experiment validity
(`measurement-experimentation-ops`) → portfolio orchestration (`senior-buyer-ops`) on
top. TikTok layers differently: strategy and diagnosis (`tiktok-ads`) sit above execution
against the official TikTok MCP server and Marketing API, guarded by the `ttops` CLI
(`tiktok-ops`) — both clean-lane, no grey counterpart. Two lanes for Meta/Google: **clean**
(`meta-ads`, `google-ads`, `google-feed-ops`, `tracker-ops`,
`measurement-experimentation-ops`) and **grey opt-in** (`meta-grey-ops`, `google-grey-ops`,
`senior-buyer-ops`) — see README § Install. Skills cross-reference by name; install a whole lane.

| Skill | Adds |
|---|---|
| [**meta-ads**](skills/meta/meta-ads) | Plans, launches, audits, and diagnoses Meta ad accounts — ODAX objectives, budgets/bidding, targeting, pixel/CAPI, policy, and a Marketing API error catalog. |
| [**meta-grey-ops**](skills/meta/meta-grey-ops) | Launches and runs Meta ads through the Marketing API with the `metaops` CLI (workspace → doctor → plan → apply → verify, bulk across ad accounts; `apply` creates ACTIVE and spends, `create_status: PAUSED` opts out), guarded live edits with a Meta `--validate-only` mode (names, bid, schedule, targeting, ad copy), read-only inspection (`review --tree`, `activity`, placement breakdowns, `doctor --risk`), the five scraped browser token classes routed by capability (`token import`), Facebook-to-Keitaro spend push, catalogs as an agent-edited Google Sheet (`sheetfeed`), plus grey-vertical survival: antidetect/proxy setups, agency accounts, token death, cloaking/review-layer filters, verification gates, per-vertical playbooks. |
| [**google-ads**](skills/google/google-ads) | Plans, launches, audits, and scales a single Google Ads account across Search, PMax, Demand Gen, and Shopping, with AI Max, Smart Bidding, RSA, and OCI tracking. |
| [**google-grey-ops**](skills/google/google-grey-ops) | Launches Google Ads through the API with the `googleops` CLI (validate_only → PAUSED → GAQL read-back → activate, bulk under an MCC) and `gmcops` for Merchant Center, plus grey-vertical survival: MCC account supply, identity/payment infra, AdsBot cloaking, verification gates, geo isolation, MC↔Ads cascade, per-vertical playbooks. |
| [**google-feed-ops**](skills/google/google-feed-ops) | Launches and operates Google Merchant Center: new-account sequence, Merchant API v1 mechanics, feed spec, feed rules, GTIN/`custom_label` schema, suspensions and appeals, MC↔Ads linking. |
| [**tracker-ops**](skills/ads-core/tracker-ops) | Operates affiliate trackers (Keitaro, Binom): postback/S2S wiring, payout-vs-all-conversions metric discipline, timezone/CPL math, daily spend-sync (`metaops keitaro push` for Meta), and the gclid-to-offline-conversion chain. |
| [**measurement-experimentation-ops**](skills/ads-core/measurement-experimentation-ops) | Decides whether a media-buying result is real before scaling it: test-mode selection, validity traps (SRM, peeking, contamination), and the platforms' own measurement tools. |
| [**senior-buyer-ops**](skills/ads-core/senior-buyer-ops) | Orchestrates a portfolio across Meta and Google: day-1 operating contract, budget allocation, kill/watch/scale rules, creative-intelligence pipeline (with a Tyver ad-library CLI), funnel QA. |
| [**tiktok-ads**](skills/tiktok/tiktok-ads) | Plans and diagnoses TikTok ad accounts through research-first intake and derivation instead of a default template — objectives and optimization events, account/BC roles, targeting, bidding and per-currency budget minimums, creative/identity/Spark Ads, Pixel/Events API and attribution, policy and restricted verticals, catalogs and TikTok Shop — plus vertical playbooks (e-commerce, app promotion, lead gen, finance/investment, iGaming) that are shapes, not recipes. |
| [**tiktok-ops**](skills/tiktok/tiktok-ops) | Executes TikTok Ads through the official TikTok for Business MCP server (browser OAuth, no developer app or API key, ~400 tools), with Marketing API v1.3 as a deterministic fallback, guarded by the stdlib-only `ttops` CLI: `preflight` forces `operation_status: DISABLE` on every create, `audit` diffs the read-back before activation — both offline, no token. Doctor → plan → apply (paused) → verify → activate on the token path, per-currency budget safety across all 56 currencies, a return-code/secondary-status catalog, reporting, automated rules and webhooks. 102 offline tests; never yet run against a live advertiser. |

## Frontend

| Skill | Adds |
|---|---|
| [**responsive-adapter**](skills/frontend/responsive-adapter) | Adapts an existing web interface from 320px to 2560px+ without touching the visual design, then verifies across a device matrix. |
| [**design-stack-picker**](skills/frontend/design-stack-picker) | Picks compatible fonts, icons, components, imagery, and motion for a UI build with a reuse-first approach. |
| [**normcore-web**](skills/frontend/normcore-web) | Builds sites that read as ordinary long-running commercial web instead of freshly art-directed product design, across five genre archetypes. |

## Security

| Skill | Adds |
|---|---|
| [**secure-coding**](skills/security/secure-coding) | Applies secure defaults across JS/Node/HTML/API/auth/DB/upload code paths and flags AI-generated-code vulnerability patterns. |
| [**js-obfuscation**](skills/security/js-obfuscation) | Obfuscates JavaScript and adds anti-automation/anti-debugging layers for authorized testing and software protection. |

## Research

| Skill | Adds |
|---|---|
| [**deep-research**](skills/engineering/deep-research) | Runs traceable multi-source research with primary-source prioritization, verification, and explicit confidence labels. |
| [**web-scraping**](skills/engineering/web-scraping) | Crawls and scrapes at scale past anti-bot defenses (Cloudflare, Akamai, DataDome, PerimeterX) using Crawl4AI and Camoufox. |

## Engineering

| Skill | Adds |
|---|---|
| [**knowledge-delta-skill-architect**](skills/engineering/knowledge-delta-skill-architect) | Writes, audits, and compresses agent skills against the baseline-then-cut methodology this collection follows — see [Methodology](docs/METHODOLOGY.md). |
