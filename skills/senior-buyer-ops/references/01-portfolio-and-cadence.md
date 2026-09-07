# 01 — Portfolio & cadence (the TL decisions)

Single-account diagnosis lives in meta-ads; this is the layer above: allocating a finite pool of
accounts + budget + creative across testing and scaling.

## 2026 market facts (perishable — re-verify by 2026-10-01)

- **Auction supply contracted ~12.3% YoY** (45.9B → 40.25B) across 21,425 accounts (Optmyzr, Q1
  2025 → Q1 2026; their text misstates it as 11%). Flat impressions at flat spend is not
  necessarily degradation. Do not kill on it.
- **Since 2026-08-17, budget-limited tCPA/tROAS campaigns drive toward the literal target**
  (`google-ads/02`). An account that was quietly overperforming a loose target is now exposed.
  Audit targets before setting scale expectations with a TL.

## Budget allocation (test / scale / reserve)

Split the daily pool into buckets, not one blob: TESTING (new accounts/creos hunting for delivery
- a winner), SCALING (proven account+creo, ramp), RESERVE (unlaunched accounts held against ban
rate). Common starting split ~50/40/10 — a lever, not a law; shift toward scaling as winners
stabilise, toward testing after a ban wave **if new-campaign hook-rate is still usable**. When
hook-rate has collapsed (~1/10), exploit hooked campaigns (prune + resume) rather than flooding
8–10 new lotteries per day. 50–100 campaigns/account is a reject-wave response, not a default —
`meta-grey-ops/13` still treats >50/day as unmanageable ops. Never launch the whole account stock
at once — the ban rate means no replacements; reserve keeps scaling uninterrupted.

## Account prioritisation & replacement queue

- Rank live accounts by CPA-vs-target AND stability, not best single day. Feed scaling budget to
  the top; hold mid; queue bottom for kill.
- Replacement queue: report dead/DOA accounts in batches to the agency; keep reserve topped so a
  ban never stalls a winner. Track ban rate as a metric — a spike has SEVERAL possible causes:
  infra (IP/persona/device), a bad account batch from the agency, a creative/policy pattern
  tripping review, a burned domain, a billing/asset issue, or the whole bundle. Attribute the
  cause before reacting — hazard-rate forensics in meta-grey-ops/06 (reactions in 01/05).

## Kill / watch / scale ladder

Automating any of the three: `04-automated-rules.md` (thresholds that hold at small counts, and
platform constraints on expressing them).

- KILL **ad sets**, not cabinet totals. A losing day with hooked sets inside is a prune — panic-
  stopping everything and relaunching from zero is the common minus. Threshold from the operating
  contract — "no payout event after ~1.5-2× target CPA" is a starting heuristic, the contract
  sets the real number; plus account verdict (agreed $ with CPA over target, zero delivery in
  2-3d, or any disable). Next day: resume what already printed **regs or deps**; clicks/installs-
  only do not earn a second day by default; regs-without-dep do (dep may land on the 3rd–4th
  reg). One lucky dep does not license holding a dead campaign: if uniques/installs/regs died
  after it, kill or keep **only** the dep ad set (duplicate it into a new campaign —
  `meta-grey-ops/04`). Do not X2 the whole CBO.
- WATCH: provisional — inside target but thin volume, or a winner whose quality metric hasn't
  matured yet (judge on click-date cohort, tracker-ops/01).
- SCALE — pick the mode by **how long the asset will live**, not by habit. Meta publishes no
  universal safe % (`meta-grey-ops/04` warm-up: +200% evening on a fresh BM froze delivery).
  1. **Gradual** (T3 / account lives days): small steps. A jump to 5× on a $15–20 T3 start kills
     winners.
  2. **X2 after 1st dep** (T1, campaign often dies in hours): if unique/install/reg hold, wait
     3rd dep and X2 again until optimization breaks. After X2, CPC/install getting more expensive
     is expected briefly — judge regs/deps. If those die, kill despite the dep.
  3. **Same-day x5–x10** (ban-rate of accounts/FPs/ads is high): squeeze a hooked campaign today;
     roll back to midpoint if it was a fluke. Textbook +20–30%/48–72h still applies on **stable**
     accounts.
  Horizontal: duplicate the winner **into a new campaign** or onto reserve accounts. Migrate
  winners to fresh accounts before the old one fatigues/dies. Tz-midnight leftover reset →
  `meta-grey-ops/04`.

## Marginal scaling (never scale on blended CPA)

Blended CPA averages over already-cheap early spend; stays green while the NEXT dollar is already
unprofitable. Decide scale on the margin:

- `incremental_CPA = Δspend / Δmature_conversions` between two comparable windows (same account,
  same tz-day basis). Two setup rules or the number is garbage: compare a MEANINGFUL step (tiny
  day-to-day Δspend dominated by daily variance — use a real budget jump or multi-day window), and
  count only MATURE conversions (newest cohort lags, raw Δ fakes saturation — nowcast it,
  tracker-ops/03).
- Read the response curve: while incremental_CPA ≤ target, keep ramping; rising with spend at
  fixed creative/audience = saturation — fix is new angle/audience/account (horizontal), not more
  budget into the same set.
- Rule out FALSE saturation before declaring the account tapped: an OFFER/traffic cap (spend past
  cap is unpaid → incremental_CPA explodes but it's a payout ceiling, not auction fatigue), a
  learning reset from too big a step, or an immature cohort (above).
- Rollback: pre-set step-down (e.g. revert to last budget where incremental_CPA was in target) and
  trigger (N days of mature incremental_CPA over target). Log the step so a revert is one action.

## Team stop-loss

Define a portfolio-level daily loss cap with the TL (not just per-account). Do NOT trigger on
same-day CPA alone — a bad-looking day is usually immature cohorts (FTD/confirm lag,
tracker-ops/01); confirm the cohort has matured AND tracking isn't broken first. Only freeze new
spend when a MATURED cohort is genuinely X% over target — otherwise you'll freeze on normal lag.

## Comparing buyers (normalise, don't rank raw)

Buyers get different stock and GEOs — raw CPA isn't comparable. Compare on CPA-vs-target ratio
within the same GEO/offer, and on winner-hit-rate per $ tested. Otherwise you reward the buyer who
got the good stock.

## Watchlist / review

- Daily: accounts near a kill/scale threshold, winners whose quality cohort is maturing, any
  delivery anomaly.
- Weekly: winner migration plan, replacement queue depth, creative backlog vs test throughput
  (02), buyer comparison, ban-rate trend.
