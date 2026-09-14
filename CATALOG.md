# Catalog

Every skill, grouped by domain for browsing — each folder sits directly under
`skills/` (no category subfolders on disk), so a single `cp` installs any of them.

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
| [**meta-ads**](skills/meta-ads) | Plans, launches, audits, and diagnoses Meta ad accounts — ODAX objectives, budgets/bidding, targeting, pixel/CAPI, policy, and a Marketing API error catalog. |
| [**meta-grey-ops**](skills/meta-grey-ops) | Launches and runs Meta ads through the Marketing API with the `metaops` CLI (workspace → doctor → plan → apply PAUSED → verify → activate, bulk across ad accounts), catalogs as an agent-edited Google Sheet (`sheetfeed`), plus grey-vertical survival: antidetect/proxy setups, agency accounts, token death, cloaking/review-layer filters, verification gates, per-vertical playbooks. |
| [**google-ads**](skills/google-ads) | Plans, launches, audits, and scales a single Google Ads account across Search, PMax, Demand Gen, and Shopping, with AI Max, Smart Bidding, RSA, and OCI tracking. |
| [**google-grey-ops**](skills/google-grey-ops) | Launches Google Ads through the API with the `googleops` CLI (validate_only → PAUSED → GAQL read-back → activate, bulk under an MCC) and `gmcops` for Merchant Center, plus grey-vertical survival: MCC account supply, identity/payment infra, AdsBot cloaking, verification gates, geo isolation, MC↔Ads cascade, per-vertical playbooks. |
| [**google-feed-ops**](skills/google-feed-ops) | Launches and operates Google Merchant Center: new-account sequence, Merchant API v1 mechanics, feed spec, feed rules, GTIN/`custom_label` schema, suspensions and appeals, MC↔Ads linking. |
| [**tracker-ops**](skills/tracker-ops) | Operates affiliate trackers (Keitaro, Binom): postback/S2S wiring, payout-vs-all-conversions metric discipline, timezone/CPL math, daily spend-sync, and the gclid-to-offline-conversion chain. |
| [**measurement-experimentation-ops**](skills/measurement-experimentation-ops) | Decides whether a media-buying result is real before scaling it: test-mode selection, validity traps (SRM, peeking, contamination), and the platforms' own measurement tools. |
| [**senior-buyer-ops**](skills/senior-buyer-ops) | Orchestrates a portfolio across Meta and Google: day-1 operating contract, budget allocation, kill/watch/scale rules, creative-intelligence pipeline, funnel QA. |
| [**tiktok-ads**](skills/tiktok-ads) | Plans and diagnoses TikTok ad accounts through research-first intake and derivation instead of a default template — objectives and optimization events, account/BC roles, targeting, bidding and per-currency budget minimums, creative/identity/Spark Ads, Pixel/Events API and attribution, policy and restricted verticals, catalogs and TikTok Shop — plus vertical playbooks (e-commerce, app promotion, lead gen, finance/investment, iGaming) that are shapes, not recipes. |
| [**tiktok-ops**](skills/tiktok-ops) | Executes TikTok Ads through the official TikTok for Business MCP server (browser OAuth, no developer app or API key, ~400 tools), with Marketing API v1.3 as a deterministic fallback, guarded by the stdlib-only `ttops` CLI: `preflight` forces `operation_status: DISABLE` on every create, `audit` diffs the read-back before activation — both offline, no token. Doctor → plan → apply (paused) → verify → activate on the token path, per-currency budget safety across all 56 currencies, a return-code/secondary-status catalog, reporting, automated rules and webhooks. 102 offline tests; never yet run against a live advertiser. |

## Frontend

| Skill | Adds |
|---|---|
| [**responsive-adapter**](skills/responsive-adapter) | Adapts an existing web interface from 320px to 2560px+ without touching the visual design, then verifies across a device matrix. |
| [**design-stack-picker**](skills/design-stack-picker) | Picks compatible fonts, icons, components, imagery, and motion for a UI build with a reuse-first approach. |
| [**normcore-web**](skills/normcore-web) | Builds sites that read as ordinary long-running commercial web instead of freshly art-directed product design, across five genre archetypes. |

## Security

| Skill | Adds |
|---|---|
| [**secure-coding**](skills/secure-coding) | Applies secure defaults across JS/Node/HTML/API/auth/DB/upload code paths and flags AI-generated-code vulnerability patterns. |
| [**js-obfuscation**](skills/js-obfuscation) | Obfuscates JavaScript and adds anti-automation/anti-debugging layers for authorized testing and software protection. |

## Research

| Skill | Adds |
|---|---|
| [**deep-research**](skills/deep-research) | Runs traceable multi-source research with primary-source prioritization, verification, and explicit confidence labels. |
| [**web-scraping**](skills/web-scraping) | Crawls and scrapes at scale past anti-bot defenses (Cloudflare, Akamai, DataDome, PerimeterX) using Crawl4AI and Camoufox. |

## Engineering

| Skill | Adds |
|---|---|
| [**knowledge-delta-skill-architect**](skills/knowledge-delta-skill-architect) | Writes, audits, and compresses agent skills against the baseline-then-cut methodology this collection follows — see [Methodology](docs/METHODOLOGY.md). |
