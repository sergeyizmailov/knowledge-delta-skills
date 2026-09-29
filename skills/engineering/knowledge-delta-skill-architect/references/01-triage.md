# 01 — Triage: what survives

Reviewed 2026-08-28. Input: what the model got wrong without the skill, plus researched claims.
Output: a keep-list where every line names the failure it prevents or the capability it unlocks.

Contents: 1 keep test · 2 what expertise reads like · 3 contradictions · 4 provenance · 5 volatile vs
stable · 6 dedup · 7 compression · 8 anti-patterns

## 1. Keep test

**Which observed failure does this prevent, or which action does it unlock that was unavailable at
baseline?** No answer → cut. Opportunity knowledge counts — the [O] class: an undocumented endpoint
the model never considered changes behavior as surely as a corrected error.

This test outranks §2's "took me years to learn": lore the baseline never needed is cut — unless it is
the stronger option the model passed without ([O]), which the end-state grade will not show you.

Keep-list line format — one row per kept item, so nothing loses its reason:
`task → what went wrong (or what was impossible) → the rule → source (if the claim is contested)`

Ranked by value per token: wrong prior overwritten · failure mode with its trigger condition ·
threshold that changes the decision · decision rule between two defensible options, with the
discriminator · platform quirk not derivable from the spec · postmortem (symptom → confirmed cause →
fix) · imperative line for an observed skip.

Never keep — **unless the baseline failed without it**; the gap is sometimes a missing definition:
definitions · "what is X" · tutorial sequences for standard operations · generic best practice
("handle errors", "write clean code") · explanation that changes neither application nor
generalization. The keep test in this section outranks the list: an observed failure beats the ban.

## 2. What expertise reads like

Test: would a domain expert say *"this took me years to learn"*?

Restated docs — model already has it:
> Use `PdfWriter()` and `PdfReader()` to merge and split. Call `add_page()` for each page.

Encoded expertise — exists only because someone hit it, and not derivable from the spec:
> Table shading: use `ShadingType.CLEAR`, never `SOLID` (renders black).
> `pandoc --track-changes=accept` never joins the paragraphs; the LibreOffice path joins them
> correctly, except when the deleted paragraph is followed by an empty spacer paragraph.

## 3. Contradictions

| Situation | Action |
|---|---|
| Primary source vs blog | Primary wins. If the blog is a *common* wrong belief, that's [W] content worth keeping |
| Both credible, different contexts | Keep both + name the discriminating condition. High value |
| Both credible, unresolved | State the disagreement and both positions. Never fabricate a resolution |
| Repeated number, no traceable source | Mark folklore. A debunked number is [W] and earns its tokens |

Hunt for row 3: a live disagreement stated as such beats a confident wrong answer, and unprompted the
model tends to resolve it to one side.

## 4. Provenance

Keep a source only where it lets the reader **act differently**: contested claim · volatile number ·
vendor's own limit (checkable, and it moves) · expensive to be wrong about. Everything else: no
citation.

Tier the labels only when sourcing is mixed and load-bearing — official · measured · peer-reviewed ·
preprint · practitioner · inference · unverified. Uniformly sourced skill → no labels.

## 5. Volatile vs stable

**Anything that changes faster than you will edit the skill does not belong inline.**

| Volatility | Home |
|---|---|
| Stable — principles, failure modes, domain math | SKILL.md body |
| Slow — platform behavior, structural limits | Reference file + review date at top |
| Fast — prices, model IDs, API versions, quotas | Isolated file **+ live-lookup pointer** |

- **Date travels with the fact**, never in a changelog: `Max hashtags | 5 (since August 2025)`.
- **Ban recall explicitly.** Strongest real example: use only the exact IDs in this file, never guess
  or construct one — unfamiliar-looking strings are real, just post-cutoff. Without that line the model
  silently "corrects" fresh data back to its prior, which is what makes the split fail.

## 6. Dedup

One fact, one owner; cross-reference by name, never restate. Three exemptions: the hub may state a rule
whose mechanism a reference owns, a source map necessarily repeats the claims it cites, and a
non-negotiables tail restates on purpose — it is what survives skimming and compaction.

Deliberate exception: a skill shipped **standalone** must be self-contained even at the cost of
cross-package duplication — Anthropic's `docx`/`pptx`/`xlsx` shipped 150 byte-identical copies of 50
files when counted (2026-08-28, revision not recorded — treat as a historical observation, not a
current count); whatever the motive, that is the standalone trade-off. Duplicate *across* separately-shipped
packages; never *within* one.

## 7. Compression

After triage, never before — you cannot compress your way out of keeping the wrong content.

- Table > prose for >2 parallel cases. Fragment > sentence. Drop articles, transitions, restated
  context.
- Cut every sentence explaining *why the topic matters*; keep the ones explaining *why the rule is what
  it is* — the second generalizes to unseen cases, the first is throat-clearing.
- One canonical example beats three. Same example in three languages is dilution, not coverage.
- **Never compress away:** numbers, thresholds, failure conditions, provenance on volatile facts, the
  discriminator in a decision rule.

## 8. Anti-patterns

| Name | Symptom | Fix |
|---|---|---|
| The Tutorial | Teaches the domain from first principles | Start at the expert's first non-obvious decision |
| The Dump | Everything found, unfiltered | Triage against the failure inventory |
| Orphan Reference | Files nothing points at, or a bare link | Annotate every pointer with its trigger |
| Invisible Skill | Correct content, never fires | Confirm the model was shown the description before rewriting it — listing budget, truncation and visibility overrides can deliver a bare name (`02 §0`). Then: description = trigger conditions, not workflow |
| Checkbox Procedure | Generic steps fitting any domain | Domain-specific decision points |
| Vague Warning | "Be careful with X" | Name condition, symptom, fix |
| Freedom Mismatch | Rigid script for a judgment call, or loose prose for a fragile op | Match freedom to fragility |
| Stale Pin | Version facts, no date, no live pointer | §5 |
| Near-Miss | Adjacent-but-inapplicable, kept "for completeness" | Cut — worst distractor class |
