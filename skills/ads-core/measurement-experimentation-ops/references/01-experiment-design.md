# 01 — Experiment design (decision rules, not stats theory)

Math (power, p-values, CIs) assumed known. Only media-buying-specific application and traps below.

## Size it before launch (or don't call it a test)

- If the MDE you'd actually act on needs more conversions than the account produces before it
  fatigues/dies, the causal test is INFEASIBLE — screen instead and say so (SKILL gate). Price it
  in spend/days first.
- An underpowered "no difference" = INCONCLUSIVE, not negative (below).

### Worked sizing (the gate is arithmetic, not vibes)

Two-proportion rule of thumb at α=0.05, power 80%: `clicks/arm ≈ 16 · p(1−p) / δ²` (p = base rate,
δ = ABSOLUTE MDE).

- **Feasible:** 5,000 clicks/day, payout CVR 2%, act only on +20% relative (δ=0.004):
  16·0.0196/0.000016 ≈ 19,600 clicks/arm ≈ 392 conversions/arm. At 100 payout events/day 50/50 →
  ~8 days/arm + lag window → run it.
- **Infeasible:** same offer at 300 clicks/day (6 events/day, 3/arm): 392/3 ≈ 130 days/arm — account
  fatigues/dies first → say so, drop to geo holdout or screening, label directional (SKILL gate).
- p = matured PAYOUT-event rate, never front-end lead rate; window must cover the lag
  (tracker-ops/03). Halving the relative MDE quadruples the sample — that trade is the decision.

## SRM — check first, before the metric

SRM = RANDOMIZED-UNIT counts vs planned split, nothing else. 50/50 arriving materially off (chi-
square on unit counts flags it) → randomization/logging broken, comparison invalid regardless of
how good the winner looks. Do NOT call downstream divergence (spend, impressions, conversions
between cells) SRM — usually a legitimate delivery/auction effect. Meta's A/B tool randomizes
assignment (SRM-checkable); non-A/B parallel cells allocate unevenly by design — not SRM, why
parallel ABO cells are screening, not causal.

## Peeking & stopping

- Meta's "end test early if a winner is found" = automated peeking — leave off unless Meta's
  sequential rule is verified (unpublished, don't assume valid). Pre-set window + ONE decision
  metric tied to the payout event (secondary metrics = context, not tie-breakers).
- **DIY valid stopping (gambler's-ruin sequential test, Evan Miller — verified live 2026-08-27):**
  size as usual to N = TOTAL SUCCESSES of the decision metric across BOTH arms. Track T, C
  (successes/arm). Stop, declare winner when `|T − C| ≥ 2.25·√N` (two-sided 5%; `2·√N` one-sided).
  `T+C` reaches N first → no winner. Valid under constant peeking, ignores failure counts (runs on
  raw tracker postbacks), no free parameters. Trade-off: null test runs LONGER than fixed-sample;
  real wins land 25–50% earlier. Works when `1.5·p + lift < 36%` (p = baseline CVR); above that,
  fixed-sample wins.

## Comparing two assets on small counts (better, not just "bad")

Poisson ladder (senior-buyer-ops/04) answers "provably bad"; this answers "challenger vs control —
which wins". Closed form (Evan Miller, verified live 2026-08-27), α = successes+1, β = failures+1
per arm:

`Pr(p_B > p_A) = Σ_{i=0..α_B−1} B(α_A+i, β_B+β_A) / ((β_B+i)·B(1+i,β_B)·B(α_A,β_A))`

No log-beta available? Draw ~10⁵ samples from each Beta(α,β), count — same number. Decision use:
promote challenger at `Pr > 0.90–0.95`, chosen by cost of wrong promotion (same decision-parameter
logic as the ladder's confidence level). Changes the STOPPING rule, not validity requirements — no
contamination, matured cohorts, ONE decision metric still apply.

## Contamination (why two "isolated" cells aren't)

- Audience overlap: same users eligible for both cells → shared noise. A/B Test tool enforces
  non-overlapping groups; manual parallel cells don't. Advantage+ broad campaigns are worst
  offenders — expand into whatever you thought was a separate manual cell.
- Auction cannibalization: duplicating a winner to "scale the test" makes copies bid against each
  other; higher-value one starves the other → looks like the loser lost on merit (it lost on
  overlap). Scale in place or differentiate.
- Shared pixel/dataset + retargeting: retargeting audience feeds on prospecting cell's traffic —
  cells aren't independent.

## Conversion lag vs the window

Judging window must be ≥ click→payout lag (call-center confirm, deposit, KYC). Judge on the
CLICK-DATE cohort so late-maturing conversions land on the day/variant that caused them
(tracker-ops/03). Deciding on conversion-date volume mid-lag systematically punishes the newest
(still-maturing) variant.

## Invalid vs inconclusive vs negative (don't collapse these)

- INVALID (SRM, tracking break, policy pause mid-test, contamination): discard, re-run — not
  evidence either way.
- INCONCLUSIVE (underpowered/CI too wide): non-sig ≠ effect is small — only that you couldn't
  detect it. Decide by cost/prior; re-run powered if it matters.
- NO MEANINGFUL EFFECT: claimable only when CI sits inside pre-set equivalence bounds (TOST) — a
  non-sig result, even powered, is not proof of no effect. Then stop funding it.

## Cross-refs

Meta tool mechanics & incrementality options → 02. Cohort/nowcast math for the lag window →
tracker-ops/03. Infra-isolation designs → meta-grey-ops/06.
