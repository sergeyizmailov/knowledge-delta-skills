---
name: senior-buyer-ops
description: "Senior media-buyer / team-lead operating layer (clean and grey portfolios alike): day-1 operating contract, portfolio allocation across accounts (test/scale/reserve), kill/watch/scale + marginal scaling, creative-intelligence pipeline, end-to-end funnel QA, cross-platform (Meta + Google) allocation. Orchestrates meta-ads / meta-grey-ops / google-ads / google-grey-ops / google-feed-ops / tracker-ops / measurement-experimentation-ops."
---

# Senior Buyer Ops

The layer above the four adapters (buy / survive / count / measure): they tell you HOW;
this tells you WHAT to decide as the person accountable for a portfolio and a
team's numbers. Call the adapters in order; this file owns the decisions between
them.

Route by platform, then by layer:

| Layer | Meta | Google | TikTok |
|---|---|---|---|
| Buy mechanics | `meta-ads` | `google-ads` | `tiktok-ads` |
| Infra / launch / execution | `meta-grey-ops` | `google-grey-ops` | `tiktok-ops` |
| Retail data layer | — | `google-feed-ops` | `tiktok-ads/10` |

**Scope: Meta (FB/IG) + Google Ads + TikTok Ads** — no Microsoft Ads or other networks.

Platform-agnostic: trackers/metrics → `tracker-ops` · is-a-result-real →
`measurement-experimentation-ops` · portfolio & cadence →
`references/01-portfolio-and-cadence.md` · creative production →
`references/02-creative-ops.md` · funnel QA → `references/03-funnel-ops.md` ·
automated kill/scale rules that survive small samples →
`references/04-automated-rules.md` · which automation pipe (API/MCP/CSV/Sheets)
for agent vs human → `references/05-automation-channels.md` · platform is Google → also read `references/06-google-lane.md` (contract additions, structure-doctrine rationale, channel detail).

**Do not port structure doctrine between platforms** — Google splits by intent and unit economics, not by campaign count; merging price tiers/funnel stages the way Meta rewards fails there (mechanics: `references/06-google-lane.md`). TikTok differs again: delivery is creative-led, the documented learning signal is ~25 results (not 50), objects are created **enabled** by default, and there are only two bid strategies. The widely repeated "3-5 ad groups x 3-5 creatives, ABO then CBO" TikTok doctrine is an untested Meta port (`tiktok-ads/11`).

Before you scale or kill on a difference, confirm it's real, not noise
(`measurement-experimentation-ops`): the kill/scale ladder and marginal-scaling
math below assume a MATURED, non-contaminated result.

## Operating contract (pin on day 1, in writing — before any spend)

The single most expensive mistake is optimising against the wrong definition.
Get these from the TL explicitly, don't infer:

1. Payout event — WHICH tracker status/measure pays (lead? reg? FTD? qualified
   FTD? confirmed COD?). Everything downstream is priced on this.
2. Downstream stages + conversion lag — how long until the payout event matures
   (call-center confirm / deposit / KYC). Sets your judging window.
3. Caps — daily/total offer caps; traffic past a cap is unpaid.
4. KPI + targets — target CPA/CPL, and the QUALITY metric the advertiser judges
   later (reg→FTD, confirm %, scrub rate).
5. Timezone **and currency** of every ad account — the tz used for every daily
   number and the sheet. Google serving-account tz/currency are **permanent**
   (`google-grey-ops/07`). Meta change **closes** the account and opens a new
   act ID (`meta-grey-ops/08`). A mismatch is overhead for the life of the seat.
6. Naming + mapping — the campaign-name convention and the Meta-macro→tracker-
   param mapping that makes it split (tracker-ops mapping contract).
7. Reporting source of truth — which sheet/dashboard is authoritative and by
   when each day.
8. Responsibility zones + escalation — who owns accounts/creatives/tracker/
   payments; who to ping on a ban wave, a tracking break, a billing hold.

Missing any of 1-8 = you are flying blind; resolve before launch.

When the platform is Google, the contract above gets three more items (conversion-action hygiene, offline-import availability, per-geo certification) — `references/06-google-lane.md`.

### Two 2026 facts that change portfolio decisions

Moved to `references/01-portfolio-and-cadence.md` (§ 2026 market facts) — they are the most
perishable claims in this skill; re-verify there by 2026-10-01 (post-Sept-1 AI Max migration).

## Cadence

- Daily: spend→cost sync (tracker-ops) → per-account CPL vs target → kill/watch/
  scale (01) → update watchlist → report before the deadline.
- Weekly: portfolio review — winner migration, replacement queue, creative
  backlog health, buyer/stock comparison (01).
