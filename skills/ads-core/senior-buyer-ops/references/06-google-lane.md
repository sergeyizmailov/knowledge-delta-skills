# 06 — Google lane (Google-specific mechanics)

Read this when the platform is Google. Everything here was moved out of `SKILL.md` and
`references/05-automation-channels.md` because it does not apply to Meta; the anti-patterns
warning against porting it onto Meta stay in those files.

## Contract additions (on top of the day-1 operating contract)

Pin these too when the platform is Google — each silently redefines a number in the base contract:

9. **Which conversion actions are primary and include-in-conversions.** This, not the bid
   strategy, defines what Smart Bidding chases. An analytics-only action left included corrupts
   every target.
10. **Whether offline conversion import is even available** on this account's developer token —
    the 2026-06-15 cutoff blocks new adopters (`tracker-ops/04`). If closed, "optimize on the
    payout event" needs a different path — know before quoting a CPA target.
11. **Certification and verification state per target geo**, with expiry dates. Financial services
    and gambling both changed multiple times in 2026; a lapsed certificate stops serving without
    warning.

## Structure doctrine (why Google splits differently)

Google is explicit-search-intent driven (Ani: "every search query is a person telling you
something, not a demographic"). Consolidation itself is normal on Google (`google-ads/01`). The
operating discipline in `SKILL.md` is shared across platforms; the mechanics are not — see
`SKILL.md` for the anti-pattern this justifies ("do not port structure doctrine between
platforms").

## Automation channels (Google-only)

| Channel | Agent use | Human use | Documented in |
|---|---|---|---|
| **Google Ads API** | Primary write path. GAQL reads, atomic Mutate graphs, BatchJobService for mass launch | Owns developer token (MCC-level), RMF/Standard access | google-ads/10 |
| **Google Ads MCP** | Reporting only — strictly read-only at release; write-capable claims are unverified | — | google-ads/10 |
| **Google Ads Scripts** | In-account reporting/logging (QS history, pacing alerts); 30-min runtime cap | In-account guardrails where no API infra exists | google-ads/10 |
| **Google Sheets** | Feeds only (near-real-time small catalogs) + script outputs | Dashboards/leaderboards the TL actually reads | google-feed-ops/01, google-ads/10 |
| **BigQuery Data Transfer** | Reporting warehouse; fixed schemas, 7-day refresh | BI layer | google-ads/10 |

Google detail stripped from otherwise platform-neutral/Meta-anchored rows in `05`:
- **CSV / bulk files** — Google: Editor CSV for one-off migrations/pre-API. Documented in google-ads/10.
- **n8n / Zapier / Make** — Google leg of the orchestration glue is lead → OCI upload. Documented in google-ads/10.

## Composing rule — Google half

The `validate_only` → PAUSED → human enable composing rule (platform-neutral statement in `05`) is
implemented on Google via `validate_only=True` on the mutate. Adapter: google-ads/10.

## Decision-rule specifics — Google half

- **One spec format, two adapters** (rule in `05`): deterministic code emits `MutateOperation`
  (Google). Google adapter lives in google-ads/10.
- **Reads are cheap everywhere** (rule in `05`): GAQL SearchStream is Google's read path, feeding
  the same daily routine as Meta's Insights edge.
