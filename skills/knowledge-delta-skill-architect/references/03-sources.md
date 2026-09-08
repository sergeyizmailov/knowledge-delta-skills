# 03 — Sources: claim → evidence

Compiled 2026-08-28. Read when you need to re-verify a number, check whether it still holds, or judge
how far it transfers. Tiers: `[official]` vendor-published · `[peer]` peer-reviewed **with a named
venue** · `[preprint]` arXiv only, no venue found · `[measured]` counted directly from source files ·
`[practitioner]` · `[inference]` mine, not in any source.

## Skill contract and sizing

| Claim | Tier | Source |
|---|---|---|
| `name` ≤64 chars, lowercase/digits/hyphens | [official] | agentskills.io/specification; platform.claude.com/docs/en/agents-and-tools/agent-skills/overview. The "no anthropic/claude" ban is **Claude-docs only**, not in the portable spec |
| `description` ≤1024 chars, non-empty | [official] | same two. **Third person is Claude-docs only** — the portable spec has no such rule, and the Claude wording is "inconsistent point-of-view *can cause* discovery problems" |
| description + `when_to_use` truncated at 1536 in the listing — **Claude Code only** | [official] | code.claude.com/docs/en/skills |
| `allowed-tools`: space-separated **string** in the portable spec; string **or** YAML list in Claude Code; undocumented on platform.claude.com | [official] | agentskills.io/specification (+ its `skills-ref` validator: `allowed_tools: Optional[str]`); code.claude.com/docs/en/skills |
| `allowed-tools` pre-approves for the invoking turn only, does not sandbox | [official] | code.claude.com/docs/en/skills |
| Portable spec defines six frontmatter fields; extra keys are rejected **by the packaging script**, not universally | [official] | agentskills.io/specification; packaging error `Unexpected key(s) in SKILL.md frontmatter` |
| Level 1 ≈100 tokens per skill, loaded for every model-invocable skill; Level 2 target <5k tokens | [official] | agent-skills/overview, disclosure table |
| SKILL.md <500 lines | [official] ×3 | best-practices doc; code.claude.com/docs/en/skills; `anthropics/skills` skill-creator |
| TOC past **100** lines vs past **300** lines — unresolved | [official], conflicting | best-practices doc (100) vs skill-creator (300) |
| References one level deep; deeper chains **may** get partially read | [official] | best-practices doc |
| Compaction re-attaches first 5,000 tokens per skill, 25,000 shared — **Claude Code only** | [official] | code.claude.com/docs/en/skills |
| Personal skills documented at one level; category nesting not auto-loaded | [official] for the path, [measured] for the negative | code.claude.com/docs/en/skills; observed in-session (50 nested skills, only the top-level one listed) |

## Real-world skill shape

| Claim | Tier | Source |
|---|---|---|
| Median 209 lines, mean 242, 92% under 500 (n=39) | [measured] | `anthropics/skills`, `obra/superpowers`, `coreyhaines31/marketingskills`, counted with `wc -l`. **Snapshot revisions not recorded** — re-count before quoting; the repos move |
| `pdf` 314 lines vs `docx` 91 lines | [measured] | github.com/anthropics/skills, `wc -l`, revision not recorded |
| The longer file is mostly boilerplate and the shorter mostly gotchas, i.e. length tracked expertise inversely — on this pair | **[inference]** | mine, reading both files; a judgment about content, not a count, and n=2 |
| 50 files duplicated byte-identically across docx/pptx/xlsx (150 copies) | [measured] | same, verified by git blob SHA; **repo revision not recorded** |
| Description summarizing the workflow caused a skipped step | [practitioner] | `obra/superpowers` writing-skills, documented incident |
| Descriptions should be "a little bit pushy" | [official] | `anthropics/skills` skill-creator — conflicts with the row above |
| Volatile facts isolated + live-lookup + "unfamiliar strings are real" | [official] | `anthropics/skills` claude-api SKILL.md |
| Corpus audit of public skills: most score low on novelty | **[preprint]** | SkillsBench, arxiv.org/abs/2602.12670 — no venue found. Counts and quality scores are **not in the abstract** and move between versions; open the current PDF before quoting one |
| Benchmark, 87 tasks / 8 domains / 18 model-harness configs: curated skills lift pass rate 33.9%→50.5% (+16.6pp; per-config +4.1 to +25.7pp); focused Skills with ≤3 modules beat exhaustive bundles | **[preprint]** | same paper, abstract verified 2026-08-28 — do not conflate with the corpus figure above |
| A minority of tasks show negative deltas; self-generated skills do not beat the no-skill baseline, and the current version reports them below it | **[preprint]** | same paper. **Exact figures move between versions** (updated 2026-06-14) and secondary summaries disagree — read the current arXiv text, never quote a remembered number |

## Delta philosophy

| Claim | Tier | Source |
|---|---|---|
| "Good Skill = Expert-only Knowledge − What Claude Already Knows"; 8 dimensions / 120 points, D1 = 20 | [practitioner] | `softaworks/agent-toolkit` skills/skill-judge |
| "Skills don't add knowledge the model lacks. They add discipline." | [practitioner] | github.com/iliaal/ai-skills README |
| Measure baseline first; scope = failures left after subtracting it; "lift at 3× the tokens is a net loss"; baseline varies per model | [practitioner] | Mastykarz, "Stop overloading your skills", developer.microsoft.com/blog/stop-overloading-your-skills, 2026-06-18 (+ author's comment replies) |
| Novelty spreads independently of craft dimensions; low-novelty skills are "an expensive no-op" | [practitioner] | agentskillreport.com, 673 skills / 41 repos, Feb 2026 |

## Context degradation

| Claim | Tier | Source |
|---|---|---|
| GSM-IC: clean 95.0% → 80.7% with irrelevant context → 63.1% when topically adjacent; "ignore it" recovers 2–5pp | [peer] | Shi et al., ICML 2023, proceedings.mlr.press/v202/shi23a/shi23a.pdf. **Scope: one benchmark, code-davinci-002, CoT prompting, 2023** |
| Redundant *skill* prose acts as the same distractor | **[inference]** | mine — direction transfers, magnitude untested on skills |
| Premise order alone: 14.5pp (GPT-4-turbo) to 30.5pp (PaLM 2-L) | [peer] | ICML 2024, arxiv.org/abs/2402.08939 |
| Lost-in-the-middle: 75.8%→53.8% (GPT-3.5); Claude-1.3 nearly flat | [peer] | TACL, arxiv.org/abs/2307.03172. Position sensitivity is model-dependent |
| Attention cost is n² pairwise; "smallest possible set of high-signal tokens" | [official] | anthropic.com/engineering/effective-context-engineering-for-ai-agents, 2025-09-29 |
| "~3,000-token degradation threshold" | **folklore** | no traceable source; degradation is continuous, not a cliff |
