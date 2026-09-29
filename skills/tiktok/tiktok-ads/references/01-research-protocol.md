# 01 — Research protocol: how to build a TikTok strategy you can defend

Reviewed 2026-09-14. This file is method, not platform fact; it does not expire with TikTok's UI.
Every platform fact it tells you to fetch expires — that is the point.

**This skill deliberately ships no default campaign strategy.** "Always run 3 ad groups at $50 with
Lowest Cost" is a 2023 artefact of one GEO, one vertical, one payout event. Anything shaped like a
universal TikTok launch template is folklore by construction, because the three inputs that decide
structure — the payout event, the conversion volume the account can feed, and the GEO's policy and
auction — vary more than the platform does.

What ships instead: an intake that pins the variables, a bounded research pass that dates its
sources, a strategy derived from those two, and a validation gate that must pass before spend.

```
A intake → B constraints gate → C bounded research → D derive strategy
  → E pre-mortem → F write the plan → G execute (tiktok-ops) → H review the derivation
```

Do not skip to D. A strategy proposed before B has to be thrown away when B fails, and B fails
often (vertical has no path in that GEO, tracking cannot carry the payout event, the account's
currency makes the budget math wrong).

---

## A. Intake — the eleven variables

Infer what you can from what the user gave you; ask only for what changes the decision. State every
assumption you made in the final plan so the operator can correct one cheaply.

| # | Variable | Why it changes the strategy | Where the answer lives |
|---|---|---|---|
| 1 | **GEO(s)** | Policy path, auction price, targeting granularity, currency, payment method, whether TikTok Ads even operates there | Operator; verify availability in `08` |
| 2 | **Vertical** | Whether a compliant path exists at all; which authorization is required and how long it takes | `08` — run its Q1/Q2 gate |
| 3 | **Offer + payout event** | Everything downstream is priced on this. "Lead" is not an event; *which tracker status pays* is | Operator, in writing — pin down which tracker status pays before pricing anything downstream |
| 4 | **Conversion lag** | Sets the judging window and whether you can optimize on the payout event at all | Operator / advertiser |
| 5 | **Break-even CPA/ROAS** | The only number that makes a CPM "good" or "bad" | Derive: margin × close rate, or payout − target margin |
| 6 | **Expected daily conversion volume at target CPA** | Decides optimization event depth, ad-group count, and whether value optimization is even available | Budget ÷ target CPA |
| 7 | **Account type & access level** | Decides what you can do at all: self-serve vs agency-provided, and your BC/ad-account role | `02`; confirm with `tiktok-ops` doctor |
| 8 | **Tracking stack** | Pixel only / Pixel + Events API / MMP / tracker + postback. Decides which optimization events can exist | `07` for the TikTok-side mechanics; the tracker's own counting rules are a separate discipline to confirm on its own |
| 9 | **Creative supply** | Volume and refresh rate available per week. TikTok's constraint is usually here, not in targeting | `06`; operator |
| 10 | **Budget and its horizon** | Test budget, daily cap, and how many days before a verdict is owed | Operator |
| 11 | **Account currency + timezone** | Set at ad-account creation and not editable — every budget minimum, every daily number, and the tracker join key depend on them | `/advertiser/info/` via `tiktok-ops` doctor |

Missing 3, 5, or 8 → you cannot judge a result. Get them before proposing anything.
Missing 1, 2, or 7 → you cannot know whether the campaign is legal to run. Get them before B.

**Record the intake verbatim** in the project's `.notes/` (gitignored) as the launch's control
plane. Re-read it before every later decision; drift between what you were told and what you
optimized for is the most common cause of a "successful" campaign the advertiser refuses to pay for.

---

## B. Constraints gate — three questions that can end the project

Run before any research into tactics. Each has a cheap answer and an expensive failure.

**B1. Does this vertical have a path in this GEO?**
`08` owns the list and the authorization matrix. Three outcomes:
- *Open* — proceed.
- *Restricted* — an authorization/whitelisting step exists. It is filed **before any ad object is
  created**, it binds to a specific verified entity and often a specific ad account, and a
  replacement account needs a new approval. Put its lead time in the plan as a dependency, not a
  footnote.
- *No path* — say so plainly and stop. Do not design a campaign that cannot legally run, and do not
  route around review. If the operator wants the nearest compliant adjacent offer, that is a new
  intake, not an edit to this one.

**B2. Can the tracking carry the payout event?**
Walk the chain end to end before designing anything: click → destination → event fires →
event reaches TikTok with a usable identity → TikTok attributes it → your tracker agrees.
Break any link and the optimization event you were going to choose does not exist.
`07` owns the TikTok-side mechanics; the tracker's own counting rules (dedup window, what counts as
a conversion) are a separate discipline — verify both, do not assume TikTok's attribution and the
tracker's count agree.

**B3. Does the access level permit the operation?**
An operator handed a shared ad account frequently cannot install a pixel, attach an identity, or
mint a token — and discovers this at launch. Resolve at intake: `02` for the role matrix,
`tiktok-ops` `doctor` for the live answer on this specific account. A successful read proves
nothing about write access.

Fail any of B → report the blocker and what would unblock it. Do not proceed to C.

---

## C. Bounded research — what to fetch, and when not to

The purpose is to refresh the volatile facts this specific launch depends on, not to re-survey
TikTok. Time-box it. Three to six fetches is a normal pass.

### C1. Decide whether you need to research at all

| Situation | Action |
|---|---|
| The fact is in a reference here **and** dated within ~60 days **and** is not a policy/eligibility/price claim | Use it. Do not re-fetch |
| The fact is a policy, eligibility, availability, limit, minimum, or price | **Always re-fetch.** These are the facts TikTok changes without notice and the ones that cost money when stale |
| The fact is a benchmark (CPM, CTR, CVR) | Fetch a current one *and* treat it as a prior, never a target. `00` § benchmarks |
| The fact is a structural/mechanical claim ("CBO learns faster") | It is a practitioner claim. Look for a source that measured it; if none, label it and design so it does not matter |
| You are about to state a number that drives a spend decision and cannot name its source | Stop and fetch, or drop the number |

### C2. Source ladder — in this order, and label what you take

1. **TikTok official** — `business-api.tiktok.com/portal/docs` (API truth), `ads.tiktok.com/help`
   (product + policy truth), TikTok for Business blog/newsroom (launches), Creative Center (trends).
   Official docs win every conflict about how the platform behaves.
2. **The live account** — a read call through `tiktok-ops` against the real advertiser ID beats any
   doc about what *this* account can do. Eligibility is per-account.
3. **Independent measured writeups** — agency/tooling case studies that publish sample size, period,
   GEO and method. Usable as priors with their provenance attached.
4. **Practitioner communities** — RU and EN both; `11` lists where they are. These are where you
   learn what breaks, which is not in docs. They are **single anonymous data points** until two
   independent ones agree.

Agent consensus is not evidence. Three sources repeating one blog post is one source.

### C3. Parallelise by surface, not by question

When the pass is genuinely broad (new GEO + new vertical + new tracking stack at once), split by
*where the answer lives*, never by asking several agents the same thing:

- official docs & policy pages
- the live account (read-only calls)
- EN practitioner writing and measured case studies
- RU practitioner writing (`11` — the field knowledge on account supply, agency cabinets and
  enforcement reality is disproportionately RU-language)
- a dedicated contradiction-hunting pass whose only job is to check claims against sources

Collect independently, merge afterwards. Merging early makes every agent converge on the first
framing it saw.

### C4. Write down what you found, with dates

Each fact gets: the claim, the source URL, the date you fetched it, and an evidence label from
`00`. A fact without a date is not reusable next month, and next month is when it will be wrong.

---

## D. Derive the strategy — in this order

Each step consumes the one above. Where a step has several defensible answers, say which you chose
and what would change your mind — that sentence is what makes the plan reviewable.

1. **Objective** — from the payout event (#3) and what the tracking can actually report (#8),
   not from what the vertical "usually" uses. The objective determines which optimization goals and
   billing events are even selectable (`03`).
2. **Optimization event** — aligned with the payout event, or the nearest upstream event the account
   can feed at the volume from #6. A deep event the account cannot feed keeps delivery starved; a
   shallow event buys volume the advertiser will not pay for. Name the switch condition now:
   *"move to <deeper event> at N conversions/week"*.
3. **Account structure** — campaign/ad-group count derived from the volume in #6 and the number of
   genuinely different *tests* you are running, not from a template. Budget mode (campaign-level vs
   ad-group-level) follows from whether you need to protect a specific test's budget. `03`.
4. **Targeting** — start from the broadest setting the tracking and policy allow, and add
   restriction only where you can name what it prevents. TikTok's delivery is creative-led far more
   than Meta's; narrow targeting usually buys you a worse CPM and no better quality (`04`, and the
   evidence for that claim is in `11` — check it is still supported).
5. **Bidding and budget** — bid strategy from the objective and from how much CPA volatility the
   operator will tolerate; daily budget from the minimums (`05`, verify per currency) and from #6.
   The budget must be able to buy enough conversions to judge within the horizon in #10, or the test
   is unreadable before it starts.
6. **Creative plan** — number of concepts, variants per concept, and what distinguishes them, from
   the supply in #9. On TikTok the creative is the targeting; a plan with one creative is a plan to
   learn nothing. `06`.
7. **Measurement plan** — the KPI, the attribution window you will judge on (state it explicitly,
   it is not the platform default in your tracker), the observation window given the lag in #4, and
   the reconciliation step against the tracker.
8. **Stop / scale / rollback conditions** — numeric, written before launch. Spend-without-conversion
   cap, CPA cap, and the account-level verdict threshold. Agreed with the operator in writing.

---

## E. Pre-mortem — before you write the plan down

Assume it is three weeks later and the launch failed. Write the three most likely causes and the
check that would have caught each. Then add those checks to the plan. Typical top causes, in rough
order of how often they are the real one:

| Failure | The check that catches it |
|---|---|
| Event never fired / fired wrong | Fire a test conversion end to end and see it in Events Manager **before** launch (`07`) |
| Optimization event too deep for the volume | Compute expected conversions/day at target CPA; if it is low, start shallower and name the switch condition |
| Policy rejection or authorization not filed | B1, and confirm the authorization is attached to *this* ad account |
| Budget in wrong units / wrong currency | Read `/advertiser/info/` and state the budget in major units and currency in the plan |
| Creative volume too low to find a winner | Count the concepts in #9 against the test design in D6 |
| Result judged on a window the advertiser does not use | D7 — state the window; reconcile before concluding |
| Access insufficient at the moment of launch | `tiktok-ops` doctor, with a write probe, not a read |

---

## F. Write the plan

One document, in the project directory, containing: the intake with assumptions flagged; the B-gate
outcomes; the research findings with URLs and dates; the derivation in D with the reason for each
choice; the pre-mortem checks; and the stop/scale conditions. It must be readable by the operator
without asking you a question.

State what you did **not** verify. A plan that hides its unverified assumptions is worse than one
that lists three of them.

---

## G. Execute

Hand off to `tiktok-ops`. It owns access, the create→verify→activate sequence, and the rule that
every object is created paused and activated only behind an explicit confirmation. Nothing in this
file authorizes spend.

---

## H. Review the derivation, not only the result

After the first readable window, re-run D with the observed numbers in place of the estimates. The
useful question is not "did it work" but **which input was wrong** — #5 break-even, #6 volume, #9
creative supply, or the optimization event. That is what makes the next launch better; a post-mortem
that only records CPA teaches nothing.

Update the dated facts you fetched in C if the account contradicted them. An account-specific
contradiction is evidence about that account, not a platform rule — record it as such (`00` §2).

---

## Non-negotiables

- **No strategy before B.** A plan for a vertical with no path in that GEO is wasted work at best.
- **Never state a number that drives spend without a source and a date.**
- **Never convert a benchmark or a case-study lift into a forecast.** It is a prior with provenance.
- **The payout event is defined by the operator in writing, not inferred.**
- **Do not port Meta doctrine.** Where a rule came from Meta practice, say so and check it against a
  TikTok source before it reaches a plan. Universal media-buying principles (break-even math,
  sample size, cohorting on click date, one-variable tests) do port. Platform mechanics do not.
