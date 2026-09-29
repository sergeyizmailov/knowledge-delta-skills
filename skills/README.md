# Skills

Skills are grouped in category folders, the same way as on the author's machine:
`ads-core/` · `engineering/` · `frontend/` · `google/` · `meta/` · `security/` · `tiktok/`.
The folders only organise the repository. Agent runtimes discover skills one level deep
(`~/.claude/skills/<name>/SKILL.md`), so install the skill directories, never a category
folder — a nested copy silently loads nothing.

Install one, or all of them:

```bash
cp -R knowledge-delta-skills/skills/meta/meta-ads ~/.claude/skills/   # one
cd knowledge-delta-skills/skills && cp -R */* ~/.claude/skills/       # everything
```

Other runtimes use their own directory — see the table in the [root README](../README.md#install).

## Media buying — Meta & Google

Layered by concern, not by platform. These eight reference each other by skill name, so
install the set together.

| Skill | Layer |
|---|---|
| [meta-ads](meta/meta-ads) · [google-ads](google/google-ads) | Buy mechanics — objectives, budgets, bidding, targeting, tracking |
| [meta-grey-ops](meta/meta-grey-ops) · [google-grey-ops](google/google-grey-ops) | Account infrastructure and survival in grey verticals |
| [google-feed-ops](google/google-feed-ops) | The retail data layer — feed spec, Merchant API, suspensions |
| [tracker-ops](ads-core/tracker-ops) | Counting — Keitaro/Binom, postbacks, timezone and CPL math |
| [measurement-experimentation-ops](ads-core/measurement-experimentation-ops) | Whether a result is real before it gets scaled |
| [senior-buyer-ops](ads-core/senior-buyer-ops) | Portfolio orchestration on top of the seven above |

## TikTok

| Skill | Purpose |
|---|---|
| [tiktok-ads](tiktok/tiktok-ads) | Strategy — structure, creative, bidding, tracking and policy for TikTok Ads |
| [tiktok-ops](tiktok/tiktok-ops) | Execution through the official TikTok for Business MCP server or the Marketing API, guarded by the offline `ttops` CLI |

## Frontend

| Skill | Purpose |
|---|---|
| [responsive-adapter](frontend/responsive-adapter) | Adapt an existing interface 320px→2560px+ without touching the design |
| [design-stack-picker](frontend/design-stack-picker) | Pick fonts, icons, components, imagery and motion that fit together |
| [normcore-web](frontend/normcore-web) | Build sites that read as ordinary commercial web, not art-directed product design |

## Security

| Skill | Purpose |
|---|---|
| [secure-coding](security/secure-coding) | Secure defaults across JS/Node/HTML/API/auth/DB/upload paths, plus AI-generated-code patterns |
| [js-obfuscation](security/js-obfuscation) | JavaScript protection, anti-automation and anti-debugging for authorized testing |

## Research

| Skill | Purpose |
|---|---|
| [deep-research](engineering/deep-research) | Traceable multi-source research with primary sources and confidence labels |
| [web-scraping](engineering/web-scraping) | Crawling and scraping past Cloudflare, Akamai, DataDome and PerimeterX |

## Skill authoring

| Skill | Purpose |
|---|---|
| [knowledge-delta-skill-architect](engineering/knowledge-delta-skill-architect) | Write, audit and compress skills against the method this collection follows |
