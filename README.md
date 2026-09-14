![Knowledge Delta Skills — missing expertise for already-capable AI](.github/assets/social-banner.jpg)

# knowledge-delta-skills

[![CI](https://github.com/sergeyizmailov/knowledge-delta-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/sergeyizmailov/knowledge-delta-skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skills standard](https://img.shields.io/badge/Agent%20Skills-open%20standard-8A2BE2)](https://agentskills.io)
[![Runtimes](https://img.shields.io/badge/runs%20on-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Cursor%20%C2%B7%20Gemini%20CLI%20%C2%B7%20opencode-555)](#install)

**Not knowledge for beginners. Missing expertise for already-capable AI.**

Scope: Meta, Google, and TikTok paid media (no Microsoft), affiliate trackers (Keitaro deep,
Binom partial), plus frontend/engineering/security skills. The media-buying set has a **clean
lane** (buy mechanics, feeds, measurement, and both TikTok skills) and an **opt-in grey lane**
(`*-grey-ops`, `senior-buyer-ops`) that teaches account-survival tactics for aggressive
verticals — install the grey lane only if that is your business; an agent with it in context
will propose those tactics as normal steps. TikTok has no grey-ops counterpart: `tiktok-ads`
and `tiktok-ops` are clean-lane only. Its iGaming playbook *describes* the grey market — account
supply, moderation enforcement, and the destination-GEO legal exposure the field literature omits
— so an agent working that vertical is not naive, but it implements none of it.

```text
baseline what the model already does  →  research only the gaps  →  distil  →  ship the delta
```

## Skills for models that already know

Claude, GPT, Gemini, Grok, DeepSeek, Qwen, Kimi, GLM — the 2026 generation already
holds most of the public internet. Restating documentation spends context teaching
what the model would produce unprompted; topically-adjacent-but-useless content
degrades its reasoning. The unit here isn't *the topic* — it's the **delta**: what the
model gets wrong, doesn't know, skips under pressure, or solves weaker than a stronger
option that exists.

Not tutorials. Not documentation summaries. Not generic best practice restated in Markdown.

## Not our idea alone

- **Anthropic**, [skill-authoring guidance](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — "Only add context Claude doesn't already have."
- **Microsoft**, [Waldek Mastykarz](https://developer.microsoft.com/blog/stop-overloading-your-skills/) — "How do you know what the model knows? You don't, unless you measure." And: "models don't need a textbook. They needed a cheat sheet."
- **ETH Zurich**, [*Evaluating AGENTS.md*](https://arxiv.org/abs/2602.11988) — repository context files did not generally improve task success rates, and raised inference cost by more than 20%.

## Three deltas, verbatim

A competent outsider wouldn't reliably know these — nor would a model with no skill
loaded.

> iOS 18 does NOT update `window.innerHeight` when address bar expands; `100vh` always
> equals `lvh` on iOS Safari.

— [`skills/responsive-adapter/references/platform-quirks.md`](skills/responsive-adapter/references/platform-quirks.md)

> Defense: resolve DNS, check IP, disable redirects, re-check on every socket connect.
> Production: dedicated egress proxy (Smokescreen, ssrfproxy) with connect-time IP
> validation — application-layer checks are racy.

— [`skills/secure-coding/ssrf.md`](skills/secure-coding/ssrf.md)

> Daily CPL (for BUYING) = click-date spend (account-tz day) ÷ that same click-date
> cohort's payout count. ... pairing click-date spend with conversion-date conversions
> is the classic apples-to-oranges CPL.

— [`skills/tracker-ops/references/03-metrics-and-math.md`](skills/tracker-ops/references/03-metrics-and-math.md)

## How they're built

Run real tasks with no skill → research only the confirmed gaps → keep only rules
traced to a prevented failure → rerun the draft and cut what didn't fix anything. Full
method: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Featured

| Skill | Adds |
|---|---|
| [**knowledge-delta-skill-architect**](skills/knowledge-delta-skill-architect) | Writes, audits, and compresses skills against this method. |
| [**meta-ads**](skills/meta-ads) | Meta ad accounts — ODAX objectives, budgets/bidding, pixel/CAPI, policy, error catalog. |
| [**secure-coding**](skills/secure-coding) | Secure defaults across JS/Node/HTML/API/auth/DB/upload, plus AI-code vulnerability patterns. |
| [**responsive-adapter**](skills/responsive-adapter) | Adapts an interface 320px→2560px+ without touching the design, then verifies it. |

Every skill, by domain: [`CATALOG.md`](CATALOG.md).

## Install

Copy the skill directories you want — nothing else to configure.

```bash
git clone https://github.com/sergeyizmailov/knowledge-delta-skills.git
mkdir -p ~/.claude/skills
cd knowledge-delta-skills/skills
cp -R meta-ads ~/.claude/skills/                                                    # one skill
cp -R meta-ads google-ads google-feed-ops tracker-ops measurement-experimentation-ops ~/.claude/skills/   # clean lane
cp -R meta-grey-ops google-grey-ops senior-buyer-ops ~/.claude/skills/              # + grey lane (opt-in)
cp -R tiktok-ads tiktok-ops ~/.claude/skills/                                       # TikTok (clean only, no grey lane)
```

Personal-scope directory by runtime, verified against each vendor's docs on
2026-08-29. Most also read a project-local equivalent.

| Runtime | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.agents/skills/` |
| Cursor | `~/.cursor/skills/` (also reads `~/.agents/skills/`) |
| Gemini CLI | `~/.gemini/skills/` (alias `~/.agents/skills/`) |
| opencode | `~/.config/opencode/skills/` (also reads `~/.claude/skills/`) |

Media-buying lanes (skills cross-reference each other by name — install a whole lane):

| Lane | Install | For |
|---|---|---|
| Clean | `meta-ads` `google-ads` `google-feed-ops` `tracker-ops` `measurement-experimentation-ops` | white ecom / lead-gen / SaaS buyers; no grey tactics enter context |
| Full | clean + `meta-grey-ops` `google-grey-ops` `senior-buyer-ops` | affiliate/grey portfolios; API launchers `metaops`/`googleops` live here with review-layer and account-survival playbooks |
| TikTok | `tiktok-ads` `tiktok-ops` | strategy (`tiktok-ads`) + execution via the official MCP server / Marketing API (`tiktok-ops`); no grey counterpart exists |

Pointers from clean skills into grey files degrade to "not installed"; nothing breaks. Playbook
numbers (CPL, kill thresholds, tags) are one team's priors — replace with your contract before
an agent acts on them.

## Nothing here is permanent

Base models absorb more of the internet every release, so a skill earns its place only
while its gap stays open — a re-baseline that finds a section already correct cuts
that section, and skills shrink or retire as their delta closes:
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Contributing

Quality bar, skill anatomy, local checks CI runs: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
