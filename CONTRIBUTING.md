# Contributing

This collection ships expertise packs, not tutorials. The bar for a new or changed
skill: every rule in it has to name the failure it prevents or the capability it
unlocks in a model that didn't have the skill. If you can't say what breaks without a
line, cut the line before you open the PR. Full method:
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) and
[`skills/engineering/knowledge-delta-skill-architect`](skills/engineering/knowledge-delta-skill-architect).

## What gets rejected

- **Restated documentation.** If a competent frontier model already produces the
  content correctly from its own training, or would get it right by reading the
  vendor's docs, it doesn't belong here — that's a [R] finding (right, nothing
  stronger exists), not a contribution.
- **Tutorials, definitions, and "learn X" framing.** This isn't a place to teach a
  human the domain; every file is written for the model that will read it under task
  pressure, not for onboarding.
- **Unverified or undated volatile claims.** A number that changes on a vendor's
  schedule (a rate limit, a policy threshold, a benchmark figure) needs a date next to
  it or a live-lookup pointer. No date, no merge.
- **Invented measurements.** Don't claim a skill was "tested" or "evaluated" unless
  you ran the tasks against a clean-session baseline and can describe what you saw.
- **Padding.** A skill that restates itself across two files, or pads its body to look
  thorough, loses to a shorter one that only holds what changes model behavior.

## What a contribution should show

For a new skill, come with:

- **5–15 concrete tasks** the skill has to make go right, drawn from work that
  actually happened (a past request, a ticket, the session that made you want the
  skill) — not an invented benchmark.
- **What broke without the skill.** Ideally a baseline run in a clean session; at
  minimum, a clear description of the gap you observed.
- **Sources for anything external or contested** — vendor docs and source code over
  blog rewrites; cross-checked where a number drives a decision.

For a change to an existing skill: say which task it fixes, or which section you're
cutting because a rerun showed the model already handles it.

## Anatomy of a skill

Each skill is one directory inside a category folder under [`skills/`](skills/)
(`ads-core`, `engineering`, `frontend`, `google`, `meta`, `security`, `tiktok`). The
categories exist for browsing the repository only: agent runtimes discover skills
one level deep (`~/.claude/skills/<name>/SKILL.md`), so the install commands copy the
skill directories, never a category folder:

```text
skills/<category>/<name>/
├── SKILL.md        # required — the playbook
├── references/     # optional — deep-dive docs loaded on demand
└── scripts/        # optional — helper scripts the skill calls
```

A new skill goes into an existing category, or a new category folder with a line for
it in [`skills/README.md`](skills/README.md).

`SKILL.md` starts with YAML frontmatter:

```yaml
---
name: my-skill              # lowercase-hyphenated, matches the directory
description: >-             # what it does AND when to use it — loads on every request
  One or two sentences, specific and trigger-rich, so an agent reaches
  for it at the right moment, and stays quiet on tasks it doesn't cover.
---
```

Then the body: the delta only, front-loaded — decision rules and thresholds first,
never buried mid-file. Push anything read only on a specific branch into
`references/`, one topic per file.

## Guidelines

- **One skill per PR.** Easier to review, easier to revert.
- **Specific over generic.** "Make a page responsive across the device matrix" beats
  "help with CSS."
- **Self-contained.** Don't depend on private tooling; name portable alternatives
  (e.g. "Playwright or an equivalent browser tool").
- **Verify, don't assert.** If a skill produces output, it should check that output.
- **English only** in all files.

## Before opening a PR

CI runs frontmatter schema validation, Markdown lint, and shellcheck. Run them
locally:

```bash
npx --yes markdownlint-cli2 "**/*.md"
shellcheck skills/**/scripts/*.sh   # if your skill ships scripts
```

Then update the catalog table in the [README](README.md) if you added, renamed, or
retired a skill.
