---
name: measurement-experimentation-ops
description: "Gatekeeper for 'is this result real before scaling': SRM, peeking, contamination, lag and multiple-testing checks; picks causal, screening or infrastructure test mode plus Meta/Google lift tools. When no volume, dying accounts or no rep allow a lift study, prescribes the honest weaker method instead of a fake lift."
---

# Measurement & Experimentation Ops

The other skills act on measured differences; this decides whether a difference
is real or noise before they do.
Status: unmeasured — no baseline task has been run for this skill; treat sections as unvalidated until one is.

## Pick the testing mode by the decision at stake

Three modes, different evidence bars — match to the cost of being wrong:

1. **Causal**: estimates incrementality (no design *proves* causality without
   assumptions). Two sub-modes — a randomized experiment (one treatment vs a
   non-overlapping control/holdout, pre-sized) is the strongest; quasi-experimental
   causal estimation (GeoLift synthetic control, pre/post) is the fallback when you
   can't randomize. Use for expensive, hard-to-reverse bets: offer, funnel, landing
   page, "does this channel even lift sales." Cost: volume + discipline + often a
   Meta rep.
2. **Screening** (directional): many concepts in one ad set / parallel ABO cells;
   delivery is UNEQUAL by design, so a "winner" is a hypothesis, not a proof.
   Use for high-throughput creative hunting where being fast beats being certain.
   Never present a screen result as validated.
3. **Infrastructure** (isolate infra variance): hold the CREATIVE fixed, vary one
   infra axis (domain / proxy cluster / account batch) across a balanced set to
   attribute delivery/ban/CPM differences to infra, not creative. The grey
   inversion of a normal test — see meta-grey-ops/06.

## Feasibility gate (grey reality — check BEFORE promising a clean test)

Causal measurement often isn't available on grey/small-account buys: too little
volume to power a holdout, accounts die mid-test, no clean pixel signal, no rep
for a sandboxed Conversion Lift. When you can't run causal, SAY SO and drop to
the best affordable proxy (geo holdout, pre/post with tracker truth, screening)
— label it directional, don't dress a screen up as a lift study. Choosing the
honest weaker method beats a "causal" test that's silently contaminated.

## Validity traps (each one silently flips a conclusion)

- **SRM:** check the RANDOMIZED-UNIT split (a 50/50 arriving 55/45 = broken
  randomization/logging → invalid) — on assignment counts, NOT on
  spend/impressions/conversions (those diverging is a delivery effect, not SRM).
- **Peeking:** Meta's A/B "end test early if a winner is found" — leave off and run
  the pre-set window unless Meta's sequential rule is verified (unpublished) (02).
- **Contamination:** overlapping audiences between cells — Advantage+ broad
  bleeding into manual cells; duplicated winners cannibalizing in the auction →
  not clean groups. Use the A/B tool's non-overlapping split, or geo separation.
- **Conversion lag:** judging before the payout event matures counts spend against
  unripe conversions → every fresh cohort looks like a loser. Window ≥ lag; nowcast
  if you must decide early (tracker-ops/03).
- **Multiple testing:** screening tolerates chance winners (you re-test anyway); a
  causal decision needs the bar corrected for the number of comparisons.
- **Underpowered:** "no significant difference" ≠ "no effect" — size first (01).

## Route references

| Need | Reference |
|---|---|
| Sizing (MDE/power as decision rules), SRM, peeking, contamination, lag, inconclusive handling | `references/01-experiment-design.md` |
| Meta tools: A/B Test, `ad_study` API, Conversion Lift, Brand Lift, GeoLift, Robyn/MMM, Andromeda implication | `references/02-meta-measurement-tools.md` |
| Google tools: Experiments/drafts, PMax experiments, Conversion Lift, Meridian MMM, brand-search incrementality, plus two 2026 confounders — read before attributing any Google result to your own change | `references/03-google-measurement-tools.md` |

Buy mechanics → meta-ads (its /09 owns single-account diagnosis & test-design
intake) or google-ads (its /08 owns the diagnostic tree and unit economics); this
skill owns the validity/incrementality layer above both. Counting &
cohort truth → tracker-ops. Portfolio decisions on the result → senior-buyer-ops.
