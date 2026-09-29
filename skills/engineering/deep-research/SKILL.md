---
name: deep-research
description: Use when asked to research deeply, compare options or vendors, fact-check a claim, investigate an unfamiliar topic, prepare a report or briefing, build a knowledge base or reference doc, or trace a claim to its primary source.
---

# Deep Research

Verified: 2026-09-08

Primary sources over blog rewrites. Every claim traceable, every gap named. "Could not find X" is a valid result — never fabricate to close one.

## Workflow

Scope (question, audience, depth, query budget) → outline (items, fields, success criteria) → pick retrieval tool → gather tiers 1→4, never start at 4 → verify per protocol → date-check staleness/version → apply stop criteria → compile output format.

## Retrieval tool

| Need | Use |
|---|---|
| Library/API/framework docs | Docs-index tool (e.g. Context7-style MCP) — version-scoped, current, far fewer queries |
| Fetch returns empty/JS shell | Headless-browser fetch — plain HTTP misses client-rendered content |
| Many sources at once | Bulk-crawler — one dispatch vs. N fetches, spares budget |
| 403/challenge on a known-live site | Retry browser-capable before writing it off; fingerprinting blocks curl, not the site |
| Everything else | Web search + `search-techniques.md` |

## Query budget

Search tools are capped per session and the cap is shared across parallel subagents, not per-agent. Divide it up front, give each agent a fixed quota in its prompt, prefer few targeted queries to many broad ones. Budget thin → finish sequentially rather than adding agents.

## Source Tiers

| Tier | Sources |
|---|---|
| 1 Primary | Specs (RFC, W3C, WHATWG), source code, official docs, original papers, changelogs |
| 2 Secondary | Peer-reviewed papers, vendor threat intel, audits, MITRE ATT&CK |
| 3 Tertiary | Technical books, curated guides (awesome-*, OWASP Cheat Sheets), conference talks |
| 4 Community | Stack Overflow, Reddit, HN, dev.to/Medium — leads only, never ground truth |
| 5 Avoid | SEO farms, AI slop, "Top 10 X in <year>", marketing blogs |

Skip a source: no author, no dates/versions, "Updated for <year>!" over stale content, every question resolves to the same product.

## Verification

| Claim type | Required evidence |
|---|---|
| One canonical authority (spec, vendor's own docs, project source) | 1 primary source |
| High-impact: security, cost, breaking change, "recommended approach", perf numbers | 2+ independent, ≥1 Tier 1–2; only 1 → mark Tentative |
| Sources conflict | Present both, name the conflict, never silently pick |
| Routine metadata (release date, version, port) | 1 primary; recheck if it drives a decision |
| Community "best practice" | Trace to origin; single blog post → opinion, not fact |
| Any URL cited in output | Fetch it this session; dead or redirected → cite the resolved target or drop it |

Trace blog claims to the paper/RFC/commit behind them; match the version under discussion; run load-bearing snippets.

## Volatile by Default

Leaderboards, pricing/rate limits, annual surveys, aggregator front pages, live threat feeds, GitHub trending, model names/context windows/cutoffs, vendor names post-acquisition or rebrand. Cite with access date; cross-check high-impact claims against a non-volatile source. Prefer permanent IDs (DOI, arXiv ID, RFC number, git SHA, CVE ID) over URLs, and re-resolve the current canonical home rather than trusting a URL from memory or an earlier citation — these rename repeatedly.

## Output Format

Structure is the contract; length is not — short factual queries collapse to a ledger plus a summary.

```
# <Topic>
## 1. Executive Summary — the answer, tradeoffs, uncertainties (3–6 bullets)
## 2. Scope — questions answered · out of scope · assumptions · research date
## 3. Findings — prose grouped Confirmed / High confidence / Tentative / Disputed / Unknown; no URLs here
## 4. Claim Ledger — | # | Claim | Source(s) | Date | Tier | Confidence | Notes |
## 5. Sources — numbered, full URLs, access date, tier, [V] for volatile
## 6. Gaps — not found · contradictory · needs follow-up
## 7. Stale-Risk Notes — findings likely to expire, with half-life
```

## Stop When

All hold: every outline item has a Tier 1–2 source or sits in Gaps · last 1–2 loops yielded no new substantive claims · high-impact claims verified · Tentative/Disputed/Unknown explicit, not dropped · budget spent.

## Parallel Pattern (10+ independent items, subagents)

One self-contained prompt per agent — item, fields, schema, its share of the query budget — 3–5 concurrent, results to disk, skip completed items on retry; review each batch; mark uncertain findings `[uncertain]` for a second pass. Many sources at once → one bulk-crawler dispatch, not one fetch per agent. Below 10 items, sequential.

## References

- `search-techniques.md` — query syntax, finding originals, archives. Read before a search-heavy task.
- `sources-by-domain.md` — curated per-domain source lists (security, web, cloud, AI/ML, crypto).
- `sources-and-apis.md` — databases, APIs and their rate limits, docs-index and archive tools.
