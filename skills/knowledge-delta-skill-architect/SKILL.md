---
name: knowledge-delta-skill-architect
description: "Writes, audits, and compresses agent skills so they earn their tokens. Covers include-vs-cut, real expertise vs what the model already knows, sizing and progressive disclosure, description/trigger design, multi-file skills. For: write a skill for X, improve/shrink this skill, is this skill worth its tokens, my skill never triggers, port domain expertise into SKILL.md, split one into references."
---

# Knowledge-Delta Skill Architect

`01` `02` `03` = the numbered files under `references/`; read triggers in the table at the end.
Sources and their limits: `03`.

The method here is model- and vendor-independent. What is not — numbers, runtime behavior — is confined
to `02`: §0 for the numbers, inline flags wherever behavior is runtime-specific. When a spec or a
runtime changes, refresh `02`.

**Spend context only where the model's behavior changes.**

Write for the target model, not as a human tutorial. Omit orientation, motivation, definitions,
examples and spelled-out reasoning **unless the baseline showed they prevent a failure**; the gap is
sometimes a missing definition. Keep decision rules, conditions, thresholds, discriminators, and the
rationale that makes a rule generalize. Your default register is documentation; override it on purpose.

## Classes

| Class | What you saw | Content | Budget |
|---|---|---|---|
| **[W]** | States it wrong, confidently, and never asks | Overwrite the prior | Highest value per token |
| **[K]** | Doesn't know, hedges, or invents plausibly | The fact | Scale to blast radius |
| **[A]** | Knows it, skips it under task pressure | One imperative line | Only if you saw the skip |
| **[O]** | Solves it acceptably, never considers the stronger option | That option + when it wins | High — most lore lands here |
| **[R]** | Gets it right unprompted, and nothing better exists | — | Delete |

[R] is a correctness bug, not waste: irrelevant context degrades reasoning, and content *topically
adjacent* to the task degrades it most — telling the model to ignore it barely helps. A redundant
paragraph inside your own domain is the most expensive token you can spend `[inference]`. Numbers: `03`.

## The path

| # | Step | Detail |
|---|---|---|
| 1 | **Scope.** Name the concrete tasks this skill must make go right, and the phrasings a user would arrive with. A topic is not a scope | below |
| 2 | **Baseline.** Run those tasks with no skill. Record what breaks | below |
| 3 | **Research** the confirmed gaps, then one bounded discovery phase | below |
| 4 | **Triage** into a keep-list where every rule names what it prevents or unlocks | `01` |
| 5 | **Package** — hub that routes, references that hold detail; folder name = `name` field, placed in the runtime's skills directory | `02` |
| 6 | **Rerun** the build tasks *and held-out variants* with the draft. Keep only what fixed an observed failure or unlocked a validated capability | below |
| 7 | **Ship check** | below |

### Scope, then baseline

A skill makes specific tasks go right; it does not cover a subject. Write down 5–15 tasks — a working
range, not a measured threshold — from work that actually happened: past requests, tickets, the session
that made you want the skill. Invented tasks produce a benchmark you were always going to pass;
"everything about X" produces a textbook. Include the edges you expect to be fragile. Asked for a skill
with no tasks attached, ask for them; if the user has none, say the skill will be unmeasured and build
the set from the domain's own failure literature instead.

**Write the expected end state per task before running anything** — 2–4 checkable assertions. Reserve
2–3 of the tasks, or unseen variants of them, as a held-out set: written now, never looked at during
research or triage, run only at step 6. Written
afterwards, a rubric only ratifies what happened. Where the correct answer is what you are about to
research, assert the observable end state (*did it reach X, did it check Y*), record what the model
actually did, and settle right-from-wrong after the research. Collect trigger phrasings at the same
time, including near-miss ones that must **not** fire (`02`).

Name the target model and runtime first: the gap is per-model, a smaller model's gap is *differently
shaped* rather than larger, and a baseline on one model is not evidence about another. Stamp the
finished skill `Baseline: <model> / <runtime> / <date>` as one line at the top of the body — **not** a
frontmatter key, which is a closed field list (`02` §0).

**Run it in a clean context** — same ladder as the rerun below: a harness, else a subagent handed the
tasks and no skill. The session you are in is not a baseline; it is primed by this skill and by
whatever the user said.

Grade each result against its assertions, and record *how* it got there, not only pass/fail — a pass
reached the weak way is [O], and pass/fail alone erases it. One pass shows presence, not reliability;
re-run the ones where consistency is the point. What the model gets right unprompted, with no stronger
option available, needs no skill. What it gets wrong, skips, invents, or solves the weak way is the
**initial measured scope** — discovery may add validated opportunity gaps, nothing else may. Redo this
the next time you touch the skill, not on every model release, and treat a section whose gap has
closed as dead weight.

**Last resort — self-probe.** Answer each task from your own defaults before reading any source. Valid
only when *you are the target model*; measuring yourself says nothing about a different one — write
that in the skill rather than implying it was tested. The probe reads your priors, it never writes
content. On a post-cutoff or proprietary domain the honest result is "knows nothing here": record it
and go straight to research. Fluent nonsense is a [W] finding, not a pass; fluent but second-best is
[O]. What you produced fluently and could not improve on *is* the baseline — it is [R], and it stays
out. Keep what you had to look up, got wrong, or nearly
skipped, then label the skill unverified: a hypothesis about the model, not a measurement.

## Research the gaps, then discover unknown unknowns

Never write from memory: your own recall of a domain shares the model's blind spots.

| Fact type | Where it comes from |
|---|---|
| Local or proprietary — this repo, this account, this workflow | Repo files, user-supplied material, the behavior you just observed |
| External and changeable — APIs, specs, platform behavior, limits, prices | Current primary sources. Vendor docs and source code over blog rewrites |
| Contested, or a number that drives a decision | Cross-check. No reliable source → mark it unverified rather than guess |

Enough is: one primary source, or two independent non-derivative ones agreeing. Neither available →
keep it with the disagreement stated, or drop it. Absence of contradiction is not corroboration.

**Then one bounded discovery phase for unknown unknowns** — the baseline only surfaces gaps you thought
to test. Ask: what would a practitioner in this domain know that a competent outsider would not think
to ask? Hunt where that lives — postmortems, incident writeups, migration guides, issue trackers,
practitioner threads, source code. Time-box it; everything found still passes the gate.

**Parallelising** (worth it once the domain is broad):

- Give each agent a **different search surface**, not the same question — official sources, source
  code, practitioner writing, postmortems, community edge cases.
- Collect independently, merge afterwards; merging early makes every agent converge on the first
  framing it saw.
- Run a separate pass whose only job is hunting contradictions and checking claims against sources.
- **Agent consensus is not evidence.** Three agents repeating one blog post is one source.

Extract decision-changing rules and facts; never paste documentation wholesale — the skill owes the
model what breaks and what it could not otherwise do. Triage (`01`) before anything reaches the file.

## Gate

```
Value ≈ (Δbehavior × frequency × longevity × source_reliability) / tokens
```

Not a computable score — a gate. Novel-but-inert is trivia; actionable-but-known is [R]. Multiplicative
because any zero cuts the line; never average a zero away.

Every model-invocable skill's description is loaded on every request whether or not it fires
(manual-only opts out — `02` §2), and a triggered body then competes for the window with the user's
files. Oversizing costs both. Practitioner opinion with no cost function behind it: lift bought at
several times the tokens may not be worth it — judge per task, not by the ratio (`03`).

## Budgets

| Layer | Loaded | Rule |
|---|---|---|
| `name` + `description` | **every request**, triggered or not, unless manual-only | Shortest text that still fires |
| SKILL.md body | on trigger, in full | Routes; holds only what applies every time |
| Reference file | only when read | One domain each; TOC once it is long |
| Script | never — stdout only | Deterministic work belongs here |

**Every numeric limit lives in `02` §0** — one dated table, the only part of this skill that expires.

**Front-load.** Decision rules at the top, never mid-file: ordering alone measurably changes what the
model follows (effect size is model-dependent — `03`), and a runtime that compacts long sessions may
re-attach only the head of each skill (Claude Code does — `02` §0).

## Cut rules

Cut on **any**: the model already did it right without you **and nothing stronger existed** · you
cannot name the failure it prevents or the action it unlocks · it is a definition or a tutorial **that
no observed failure called for** · it restates docs the model demonstrably recalls · another section
owns the fact · it is volatile and undated · removing it changes nothing **and** you cannot say why it
should have helped.

Test the last one by deleting the section and rerunning. It needs both halves: a handful of tasks only
reveals large effects, so no visible change is not proof on its own.

## Rerun (step 6)

With a harness: install at the runtime's skills path, start a **new session**, run the same tasks.

Without one: spawn a subagent with a clean context and give it the draft plus the tasks — install the
folder if it can read one, since pasting the body tests the content but never the description or the
disclosure. Your own session holds the research and the drafting, so testing in it proves nothing; if
you cannot spawn one, run the tasks anyway and record the result as contaminated, not as evidence.

Diff each result against the failure you recorded. Re-check the tasks that already passed: a rule that
fixes one and breaks another is a net loss.

**Rerunning the build set proves the known cases are fixed, not that the skill generalizes** — those
tasks selected the content. Hold out 2–3 unseen variants of the same failure modes, written before the
draft and never used during triage, and run them too. Fixed on the build set but not the held-out set
= fitted to the examples; the rule is too specific, or it encodes the instance instead of the
condition.

Log which rule fixed which task as a **cut heuristic** — a rule no task points back to is a cut
candidate. It is not causal attribution: several rules changed at once, so only the package is
measured. Where one rule's contribution actually matters, ablate it alone and rerun.

## Ship check

- Frontmatter valid: `name` matches the folder, `description` is triggers not workflow, within the
  current length limit (`02` §0).
- Every reference is linked from the hub, exactly one level deep, and each pointer says when to read it.
- Nothing restated in two places — grep your own distinctive phrasings across the tree.
- Every volatile fact carries a date or a live-lookup pointer.
- Every remaining **rule** names a failure it prevents **or an action it unlocks** that was
  unavailable at baseline. If you cannot say which, it was never triaged.
- Trigger test in a **new session**: ask in the phrasings a user would arrive with and confirm it
  fires; ask the near-miss ones and confirm it does not. No way to start one → check each phrasing
  against the description's own terms, hand the list to the user, and record the test as unverified.
- Read it once as the agent: could you act on it without asking a question the file should have answered?

## Auditing an existing skill

No task set to hand? Then it is a **structural** review, not a measured one: size against the budgets,
description triggers, tag each section [W]/[K]/[A]/[O]/[R], flag undated volatile facts, name the top
three fixes. Say plainly that nothing was measured — tagging a section [R] without running the task is
a hypothesis, not a finding.

## References

| Need | File |
|---|---|
| Keep/cut triage, contradictions, volatile vs stable, compression, anti-patterns | `references/01-triage.md` |
| Frontmatter, progressive disclosure, description design, layout, **scaling past one file**, scripts, portability | `references/02-architecture.md` |
| Claim → source map, scope limits, what is folklore | `references/03-sources.md` |

## Non-negotiables

- **Look before you write.** A skill written without watching the model attempt the task is a guess.
- **Skills can hurt.** A curated skill lifts the average and still makes a minority of tasks *worse*
  `[preprint]`, so ship only what you saw help. Figures and their caveats: `03`.
- **Grade the outcome, not the path** — against the assertions you wrote before baselining, not
  against whether it followed your steps.
