# 02 — Architecture: packaging the delta

Reviewed 2026-08-28. Every expiring number is isolated in §0; runtime-specific behavior is flagged
inline. The method in `SKILL.md` does not move with either.

Contents: 0 runtime limits · 1 frontmatter · 2 disclosure · 3 description · 4 layout ·
4b scaling across references · 5 freedom · 6 scripts · 7 portability

## 0. Runtime limits and runtime behavior — what expires first

Verified 2026-08-28, listing/visibility rows 2026-09-08; frontmatter semantics changed several times
through 2025–26. When a runtime changes, re-check **this table and every inline runtime flag in
§§1–7** — numbers are isolated here, behavior is not, and a behavior change (how the listing is
budgeted, how visibility is overridden) lands outside this table.

Live sources: `agentskills.io/specification` · `code.claude.com/docs/en/skills` ·
`platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices`

| Limit | Value (dated per row; undated = 2026-08-28) | Scope |
|---|---|---|
| `name` max length | 64 chars, lowercase/digits/hyphens | Portable + Claude |
| `description` max length | 1024 chars | Portable + Claude |
| Reserved words in `name` | no "anthropic" / "claude" | **Claude only** |
| Portable frontmatter fields | `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` | Portable |
| `allowed-tools` type | space-separated string | Portable |
| `allowed-tools` type | string **or** YAML list | **Claude Code** |
| description + `when_to_use` truncation in the listing | 1536 chars combined | **Claude Code** |
| Skill-listing budget | 1% of the model's context window; raise with `skillListingBudgetFraction` or a fixed char count in `SLASH_COMMAND_TOOL_CHAR_BUDGET` (2026-09-08) | **Claude Code** |
| Listing overflow behavior | Every skill **name** always ships; **descriptions are shortened, then dropped**, least-invoked first, so a real skill can reach the model as a bare name (2026-09-08) | **Claude Code** |
| Visibility override | `skillOverrides` in settings: `on` (name+description) · `name-only` · `user-invocable-only` (hidden from the model, still in `/`) · `off`. Absent key = `on` (2026-09-08) | **Claude Code** |
| Listing diagnostics | `/doctor` (listing cost + top contributors), `/skill-doctor` (candidates to disable), `Skills` row in `/context` (post-budget size), overflow warning in `--debug` (2026-09-08) | **Claude Code** |
| Level-1 metadata cost | ~100 tokens per installed skill | Claude |
| Level-2 body target | <5k tokens | Claude |
| SKILL.md body guidance | <500 lines | Claude docs, 3 sources |
| Reference TOC threshold | 100 lines (best-practices) vs 300 (skill-creator) — unresolved; use 100 | Claude |
| Compaction re-attach | first 5,000 tokens per skill, 25,000 shared, most-recent-first | **Claude Code** |
| Personal skill path | `~/.claude/skills/<name>/SKILL.md`, one level; deeper nesting not auto-loaded | **Claude Code** |

## 1. Frontmatter

Lengths, reserved words and field lists live in §0. The rules that outlast them:

| Field | Rule |
|---|---|
| `name` | Lowercase/digits/hyphens, no XML tags, matches the folder. Gerund (`processing-pdfs`) or noun phrase; never `helper`, `utils`, `data` |
| `description` | Non-empty, no XML tags. **Third person** — a Claude rule, not portable; it is injected into the system prompt, and mixed point-of-view can break discovery |
| `allowed-tools` | **Pre-approves** for the invoking turn only; does **not** sandbox — every other tool stays callable. Treating it as a security boundary is a misreading. **Claude Code behavior**; other runtimes may scope it differently |

**`allowed-tools` type differs by surface** (§0): write the string form for anything portable; a YAML
list is runtime-only. A CI schema demanding an array is stricter than the portable spec, and
incompatible with it.

**Packaging trap:** a runtime's own extra fields sit outside the portable field list, and rejection is
**surface-specific, not universal** — a packaging script errors on unknown keys while other consumers
ignore them. Assume rejection if the skill will ever be packaged or uploaded; use extras freely in
runtime-only skills.

Two surfaces disagree: the cross-product spec mandates `name`+`description`; Claude Code marks both
optional (falls back to dir name + first paragraph). Write both regardless.

## 2. Progressive disclosure

| Level | Loaded | Cost |
|---|---|---|
| 1 — `name` + `description` | Every request, every model-invocable skill | Small but permanent (§0) |
| 2 — SKILL.md body | On trigger | The whole body at once (§0) |
| 3 — bundled files | When read | Zero until read |
| 4 — scripts | On execution | stdout only |

Manually-invoked skill → disable model invocation so it stops paying discovery tax it cannot use
(a runtime-only frontmatter key — outside the portable field list, §1).

Loaded skill content **stays in context and is not re-read** on later turns — standing instructions,
not one-shot. A runtime that compacts long sessions may re-attach only the **head** of each skill
(Claude Code does — §0), which is why front-loading matters and why a long tail is unreliable.

## 3. Description — the highest-leverage field

The only thing deciding whether it fires on its own; explicit invocation bypasses it. Sources
genuinely disagree; the resolution:

- **Include:** what it does, concrete trigger conditions, the exact terms a user would type, symptom
  phrasing ("403 on scrape", "my skill never triggers").
- **Exclude the workflow.** A description that summarized the process caused a documented failure — the
  agent read the summary as the procedure and skipped a required second step. Describe *when*, not *how*.
- **Push on coverage, not process.** More trigger phrasings fights under-triggering, and the asymmetry
  favours it: under-triggering costs the whole skill, over-triggering costs a wasted read plus
  inapplicable instructions in an unrelated task — cheaper, and not free at all if the skill takes
  external actions.
- Front-load the primary use case — **Claude Code only:** description + `when_to_use`
  truncate at 1536 combined.

## 4. Layout

```
<skill-name>/
├── SKILL.md          # routing + rules that fire every time
├── references/       # one level deep, on demand
└── scripts/          # deterministic operations
```

**Exactly one level deep.** A file reached *from* another reference may be read partially — the agent
may preview it (`head -100`) instead of reading it whole, leaving the tail unseen. Every reference
links directly from SKILL.md. A rule belongs in the file that needs it at decision time — if two
references both need it there, the split is wrong, not the rule. Cross-reference by name for
orientation, never as the only path to a rule the reader is about to act on. Conflict worth knowing:
skill-creator advises *adding* a layer of hierarchy as a skill nears 500 lines; prefer more files at
one level over a second level.

TOC threshold: sources disagree (§0). Use the lower one — the stated purpose is that a partial read
still reveals full scope, which only the lower number achieves.

Annotate every pointer with its trigger — `references/01-triage.md — read when deciding what to cut`.
A bare link is an orphan. One annotated index plus a shorthand declared in the same file covers
the whole skill; repeat citations may then stay short. Undeclared shorthand is still an orphan.
Never force-load references with `@`-style syntax; that defeats disclosure.

Split **by domain, not by depth**, so an irrelevant domain's tokens never load. The benchmark finding
is that focused Skills with at most three modules beat exhaustive bundles `[preprint]` — read it as
"stay focused", not as a file count for your `references/`.

### The shape that recurs

Doctrine, not a measured result — the order that makes a skill usable at the moment of need:

1. One-line statement of the core principle — the thing every later rule serves.
2. A decision table or router: which situation → which rule or which file.
3. The rules themselves, sequenced in execution order.
4. Reference pointers, each annotated with when to read it.
5. Non-negotiables last — the short list that must survive skimming and compaction.

No introduction, no scope statement, no summary of what the domain is. Open at the first non-obvious
decision.

**When to split at all.** Start in one file. Move a block out the moment it is needed only in *some*
runs — conditional detail is exactly what references are for. Anything that fires every time stays in
the hub. If the hub no longer reads end to end on its own, you split the wrong block.

## 4b. Scaling across references

- **SKILL.md routes; references own the conditional detail.** If a rule cannot be stated in the hub
  without the reference's detail, it belongs in the reference and the hub gets a pointer.
- **One owner per fact inside the package**; every other file links to it. Grep your own distinctive
  phrasings across the tree before shipping — restatement hides well across files.
- **Stable semantic filenames** (`tracking.md`, `feed-spec.md`). Number only when sequence matters, and
  then never renumber — a gap in the sequence is cheaper than repointing every reference.
- **Date volatile references individually**, so staleness is visible per file rather than per skill.
- **Split into separate skills only when each has independent triggers and is useful installed alone.**
  No source sets a numeric threshold — this is a judgement about triggers, not a file count.

**Cross-skill references — the discriminator** (the exception to §7's portability rule, not a violation
of it). Shipping as one unit is **necessary but not sufficient**: installing a sibling does not load
it. A cross-skill reference is safe only when all three hold —

1. the target runtime can discover and invoke the sibling (category nesting often defeats this, §7);
2. the reference **routes an independent task** to that sibling;
3. the current skill can finish its own task without the sibling's rules in context.

Use them for routing, never as the only home of a rule this skill's task depends on. If your ads skill
cannot complete its job without the tracker skill's content, duplicate that rule **across the two
packages** — one-owner-per-fact governs files inside a package, not separate packages. Never create a
cross-skill dependency merely to avoid duplication.

## 5. Freedom calibration

| Freedom | When | Form |
|---|---|---|
| High | Multiple valid approaches, context decides | Principles, heuristics |
| Medium | Preferred pattern, variation fine | Pseudocode, parameterized examples |
| Low | Fragile, error-prone, consistency critical | Exact commands: "run exactly this, do not add flags" |

Mismatch either way is a failure: rigid scripts for judgment calls produce brittle compliance; loose
prose for a fragile operation produces confident breakage.

## 6. Scripts

Bundle one when the operation is deterministic, reusable, and would otherwise be regenerated each run.

- State explicitly **execute** vs **read as reference** — ambiguity here is a documented failure mode.
- `run validator → fix → repeat` is the pattern worth bundling a script for.
- Only stdout costs context — deterministic checks belong here, not in prose.

Writing a script to hold prose means you wanted a reference file.

## 7. Portability

Assume standalone installation by someone whose layout differs from yours.

- No absolute paths — resolve relative to the skill directory.
- No references to sibling skills that **ship separately** — self-contained beats DRY across packages.
  Sibling references are allowed only inside a set that installs as one unit (§4b).
- No dependency on a router, category folder, or naming convention outside the skill.
- **Unknown runtime:** the package does not change. Only the install directory and which extra
  frontmatter keys are tolerated do — look both up (personal, project and plugin locations differ per
  runtime; §0 has Claude Code's), never copy one runtime's path onto another, and assume the portable
  field list for everything else.
- **Claude Code:** nesting deeper than the documented one level (`<category>/<name>/`) is undocumented
  and **observed not to auto-load** — in a session with 50 category-nested skills, only the single
  top-level one appeared in the available-skills list. Category layouts need an explicit entry point
  the runtime *can* see.
