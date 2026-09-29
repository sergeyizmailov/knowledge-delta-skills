# Methodology

How skills in this collection get built, what gets cut, and why. The full version of
this method — including the class table, the value gate, and the cut rules — lives in
[`skills/engineering/knowledge-delta-skill-architect`](../skills/engineering/knowledge-delta-skill-architect),
which is both a skill in this repo and the process this whole collection follows.

## The knowledge delta

A frontier model already knows most of the public internet. Writing a skill that
restates a framework's official docs, a well-known best practice, or a definition the
model produces fluently on its own adds tokens without adding capability — and every
loaded skill description, plus the full body once triggered, competes for context with
the user's actual files. Worse, content that is topically adjacent to the task but adds
nothing measurably degrades the model's reasoning on that task; it is not neutral
filler.

The only content worth shipping is the **delta**: what the model gets wrong, doesn't
know, skips under pressure, or solves in a weaker way than a stronger option that
exists. Everything else is cut, no matter how correct or well-written it is.

## The path

1. **Scope.** Name the concrete tasks the skill must make go right, taken from real
   work, not an invented benchmark or "everything about X."
2. **Baseline.** Run those tasks with no skill, in a clean session, against
   assertions written before the run. Record what breaks, what's skipped, and what's
   solved the weak way — not just pass/fail.
3. **Research the confirmed gaps**, then run one bounded discovery pass for unknown
   unknowns: what would a practitioner know that a competent outsider wouldn't think
   to ask? Primary sources and current practitioner material — postmortems, incident
   writeups, source code, issue trackers — over blog summaries and memory. On a broad
   domain, independent passes run over different search surfaces (official sources,
   source code, practitioner writing, postmortems) and are merged only after collecting
   independently, plus a separate pass whose only job is hunting contradictions between
   what the other passes found.
4. **Triage.** Every candidate rule has to name the failure it prevents or the action
   it unlocks. What the model already does right, and nothing stronger exists, is
   deleted — not softened, deleted.
5. **Package.** A short hub file that routes, reference files that hold the
   detail and load only when read, scripts for anything deterministic. Decision rules
   live at the top; a model that compacts a long session may only re-attach the head of
   a file.
6. **Rerun.** The draft skill runs against the same tasks in a new, clean session.
   Only rules that fixed an observed failure survive; a rule with no task pointing back
   to it is a cut candidate, and a rule that fixes one task while breaking another that
   already passed is a net loss.
7. **Ship check.** Frontmatter valid, every reference linked and read-when labeled,
   nothing restated twice, every volatile fact dated, every remaining rule traceable to
   a prevented failure or a capability it unlocked.

## Compression, not brevity

The goal isn't short files — it's a high ratio of decision-changing content to tokens.
A skill can be long if every line earns its place: a 12-file reference tree is fine
when each file is read only on the branch that needs it. What's cut is restated
definitions, tutorial framing, hedged "it depends" prose with no decision rule attached,
and anything a second section in the same skill already covers.

## Dating volatile facts

Anything that changes on a vendor's schedule — API limits, pricing, policy thresholds,
platform-specific quirks, benchmark figures from a third party — carries a date or a
live-lookup pointer inline, next to the fact, not just once at the top of the file. A
number without a date is either current knowledge stated as if timeless, or already
stale; both cost trust once a reader checks.

## Retirement

Skills are not maintained forever by default. The reason to write one — a gap between
what the base model reliably knows and what a task needs — closes over time as frontier
models absorb more of the public internet, including material that used to be scarce
practitioner knowledge. A skill whose delta has closed is not neutral to keep: it is
exactly the "topically adjacent, doesn't help" content the triage step exists to cut,
now sitting in a shipped file.

Practically, that means:

- A skill covering a fast-moving platform (ad platform APIs, a frontend runtime's
  quirks, a security landscape) should be re-baselined against a current model
  periodically, not left to age silently — the date stamp at the top of the file is the
  signal for when that last happened.
- When a rerun shows the base model now gets a section right unprompted, that section
  is cut, the same as it would have been cut at first-write time.
- A skill that has lost most of its delta should shrink toward its still-useful core
  or be retired outright, rather than kept whole out of inertia.

None of this is automated in this repo yet — it's a standard contributors and
maintainers are expected to apply by hand when they touch a skill, and a bar reviewers
should hold new submissions to as well.
