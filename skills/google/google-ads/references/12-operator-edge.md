# 12 — Operator edge

Reviewed 2026-08-27. What separates elite operators from competent ones. Nothing here appears in
Google's Help Center or a beginner listicle. Named practitioners throughout — attribution matters,
because much of this is contested.

## Steering Smart Bidding

### Target ratcheting — the cadence that works

SavvyRevenue's framework, the most concrete "how much, how often" found anywhere:

| Change vs **Projected ROAS** | Label | Effect |
|---|---|---|
| 10% | Nudge | Subtle, reaction over multiple weeks |
| 20% | Action | Clear instruction, noticeable shift |
| 30%+ | Urgent | Forces an immediate hard reset |

**Insight most people miss: measure the percentage against Projected ROAS, not the currently-set
target.** Moving a 500% target to 550% does nothing if Projected ROAS is already 520% (~6% real gap).
Moving to 600% against the same projection creates the ~15% distance needed to force a response.

Rules: **never change a target more than once per week**; after a change, often correct to not touch
it the following week. Exceptions only for setup errors, runaway spend, tracking break.

### The 2026-08-17 change and how to respond

Full mechanics in `02-bidding-auction-quality.md`. The operator response, from **Andrew Lolk**
(SavvyRevenue):

1. **Raise targets sequentially, not preemptively.** Wait for the change to land, observe 1–2 weeks,
   then raise ROAS target ~10% and budget ~20% in the same pass. Repeat until stable. Reacting early
   wastes a cycle.
2. **Switch to Maximize Conversion Value** where a ROAS floor is not essential — favors best auctions
   while holding spend steady, at the cost of losing ROAS as a guardrail.
3. **Guardrail triangle**: realistic ROAS target + realistic budget + bid cap, not any single lever.
4. **Lolk's contrarian read**: the change may *decrease* competition in the very best auctions, since
   budget-limited spend distributes more evenly instead of concentrating — net positive for anyone who
   does not overreact.

**Fred Vallaeys:** *"Let Google fly the plane but keep control of the flight plan."* Define objectives,
supply clean conversion data, run an independent external monitoring loop. Warns against **knee-jerk
control-adding** the moment behavior shifts.

Use the **Bid Target Adjustment Tool** to compare actuals against entered targets — but **do not
accept its recommendation if targets were deliberately set loose to encourage exploration.** Matching
recent actuals blindly locks in an accidental floor.

### Smart Bidding Exploration

Introduced GML May 2025, called by practitioners the most significant bidding update in a decade. For
tROAS campaigns the algorithm may bid **above** the literal target on specific high-potential segments
rather than uniformly loosening. You set a **tolerance band of 5–30%**.

Requires active tROAS and **budget headroom** — a budget-constrained campaign cannot explore. Test
protocol: run 6–8 weeks, watch the bid-strategy report's **traffic diversity** section, not blended
ROAS.

### When to abandon Smart Bidding

Below roughly **50 conversions per rolling 30 days** it optimizes toward low-intent proxy signals
rather than viable outcomes. Three documented failure modes: low-volume B2B · products where value and
margin vary wildly so the algorithm cannot perceive LTV or deal size · budget-certainty risk.

A named advertiser, verbatim: *"Google will just start running out of control. I want reins and
controls that make sure spending is just not infinite."* A $400K/month outdoor-products advertiser:
PMax produced volume but the wrong mix — *"too many low-value orders, not enough of the
$15,000–$20,000 project-scale customers"* — until value signals and manual guardrails were added.

**The hybrid structure that follows:** Manual CPC with hard caps for the long tail, Smart Bidding only
where conversion volume clears ~50/month, conversion-value signals layered wherever tracking permits.

### Portfolio strategies — the silent drag

A portfolio pools conversion data across every attached campaign, speeding learning for low-volume
campaigns — but **one underperforming campaign silently drags the shared target's behavior for every
other campaign in the group**, with no per-campaign visibility into which one.

**Discipline: never add a campaign to an existing portfolio without first checking that its standalone
CPA/ROAS is in the same order of magnitude.** A 3×-worse campaign degrades the whole group.

Portfolio min/max bid limits also throttle silently — a cap set too tight pushes the algorithm out of
winnable auctions with **no warning in the UI**. Only tell: impression-share-lost-to-rank climbing on
a campaign that should be performing.

### Two schools on restarting learning — unresolved

- **Batch the change**: make one large deliberate change and accept a full new learning period, on the
  theory that it stabilizes faster than a string of smaller changes that each partially reset the clock
  without completing it.
- **Ratchet, never reset**: never deliberately trigger a reset; use the weekly cadence exclusively,
  because any reset discards real accumulated signal for a hard-to-measure benefit.

**No published head-to-head test resolves this.** Depends on how broken the pre-change state already
was — a portfolio producing garbage has less to lose from a hard reset than a stable one being
fine-tuned.

## Signal engineering

**The ground-truth audit for any value manipulation** [Kirk Williams, ZATO]: compare **"Original conv.
value"** (raw) against **"Conv. value"** (post-rules) side by side. Identical = nothing is being
inflated. Divergent = some value rule (NCA, conversion value rules, import shrinkage) is actively
steering bidding. **Generalizes to any value-rule audit** and takes seconds.

**New Customer Acquisition trap** [Kirk Williams]: since a 2023 change, NCA tracking decoupled from
bidding. **The New Customer Lifetime Value column populates in reports even when the bidding checkbox
is off** — hypothetical value, not an active signal, which fools people mid-audit into believing
new-customer bidding is live when it isn't. Lever is the campaign-level "Adjust your bidding to help
acquire new customers" checkbox, not the account-level goal.

**Conversion value rules as a quality lever.** Assign different synthetic values by geography, device,
audience list, or first-party match so Max Conversion Value chases the *segment*, not the raw count.
Repeated practitioner line: *"Smart Bidding will optimize toward whatever value you feed it, and it
does that quickly and relentlessly."* **The technology is not the constraint. Data quality is.**

**Stale-value decay is the most common failure here.** Value rules degrade silently — no alert fires
when a value assigned in a hurry two years ago stops reflecting real profit. Fix is not better
tooling; it's a recurring calendar review tied to CRM-confirmed revenue.

**Downstream optimization for lead gen** [Adalysis]: do not optimize on form-fill. Layer MQL → SQL →
closed-revenue as separate value-weighted actions, feeding the higher-fidelity signal back via offline
import. Stated threshold: **≥15 conversions/month minimum, 30+ performs meaningfully better.**

**Multiple conversion actions as a deliberate steering set.** Define a small set (form-fill low, phone
call mid, closed-won high), mark only what should influence bidding as primary, demote diagnostics to
secondary. **Adding or removing an action from the primary set is a bidding lever independent of any
bid-strategy change.**

**Micro-conversion laddering.** Where primary conversions cannot clear ~50/month, bid on the
closest-to-bottom-funnel event that *does* clear volume, then migrate the target down-funnel as volume
grows.

## Query and intent control

**Counter-intuitive one — pausing exact match** [Brad Geddes, explicitly the exception not the rule]:
for **high-volume, non-specific terms** ("EHR software"), an exact-match keyword that initially
converted can start spending heavily without results once isolated from broader signal context. Broad
match under a conversion bid strategy uses signals the exact keyword loses access to — search history,
sibling keywords, landing page.

Diagnostic: compare CPAs for the same search term surfacing across multiple ad groups. If similar,
pause the exact keyword or negative it out of the underperforming group. Geddes is explicit: *"in most
cases, the right step is to turn a search term that consistently converts into an exact match
keyword."*

**n-gram over individual query review** for broad match and AI Max accounts — volume makes
query-by-query review impossible to keep current.

**AI Max makes match-type-level evaluation structurally impossible.** Cannot cleanly attribute
performance to a match type — precisely why n-gram-level and asset-level analysis are the only viable
lenses.

**Account-level negative lists as the enforcement layer.** Campaign-level-only lists are a recurring
audit failure — **every new campaign starts without them unless a human remembers to attach the list.**

**The conflict audit is a cadence, not a cleanup.** Match-type behavior drifts even with no account
change, so a negative list that did not conflict six months ago can silently block active keywords
today purely because Google's matching interpretation shifted. Schedule it.

**Use tCPA gaps to separate intent tiers** rather than forcing the distinction through negatives.
Where two campaigns share nearly identical themes but different intent ("buy X" vs "X reviews"),
materially different targets let Smart Bidding do the separation via its own signal weighting —
query-level intent is exactly what it models better than a static negative list can enforce.

**Competitor-name bidding as demand capture, not defense.** Run as a distinct channel with its own
landing pages built around direct comparison, **measured against its own CPA target** — folded into
blended brand performance, its naturally worse CVR looks like a brand-campaign problem.

**Audience-segment exclusion as architecture** [ZATO]: build a standing exclusion layer across every
prospecting campaign — existing customers, non-converting repeat visitors, churned users, employees.
*"Who you don't target is just as important as who you do."* Brand-search volume from existing users
logging into a portal is a common silent leak.

**PMax asset groups follow creative strategy, not bidding logic** [Andrew Lolk]: don't ask "how many
asset groups" — ask "can I create meaningfully differentiated creative for this group." Treat PMax as
"Shopping + DSA-style expansion + retargeting", not a full-funnel campaign; build creative
retargeting-first (product explainers, bestsellers, UGC, trust signals), not brand storytelling.

## Wasted-spend hunts that reliably find money

| Audit | What to check |
|---|---|
| **Search Partners** | Segment → Network. "For some advertisers it brings a lot of extra traffic, for others it does more harm than good." Not a blanket kill — but **Google's default is not the advertiser's interest here.** Never leave unaudited |
| **Display expansion on Search** | Legacy setting some accounts still carry. *"Either doesn't show, or it wastes a lot of money."* Keep off, full stop |
| **Geo presence-or-interest** | The classic silent leak in local and regional campaigns |
| **Stale device bid adjustments** | "+50% for Computers" set once and never revisited — and inert anyway under Smart Bidding |
| **Odd dayparting rules** | "Tuesdays 3–4PM, +7%" is a tell for reflexive rule accumulation, not strategy. Audit every one for a real reason |
| **PMax/Search overlap** | **67% of PMax campaigns overlap Search on search terms; Search wins CVR 84.18% of the time on the identical query** [Adalysis, 2024-12-12, n=3,300+ non-retail PMax campaigns / ~1.2M search terms] — PMax frequently wins auctions Search would have converted better |
| **Disapproved ads and keywords** | Silently zero out delivery with no alert beyond a small icon |
| **Duplicate keywords** | Dilute signal and create unpredictable serving (`03`) |
| **Conversion double-counting** | Same person submitting a form repeatedly with no dedup inflates the very count driving bidding — upstream of every other decision |
| **Low-QS keyword purge** | Kill persistent QS 1–3 keywords with real spend and no conversions rather than waiting for the algorithm |

**Budget-recommendation math that stops a bad decision.** Before accepting any Google budget increase,
compute the **actual cost per additional conversion promised**, not the headline delta. Cited example:
doubling a daily budget for a projected **+0.75 conversions/week** — a 14× weekly cost increase for a
fractional gain.

> **"Once Google increases a budget, it doesn't lower it again."** Reversal is manual. Treat every
> accepted budget recommendation as requiring a calendared follow-up review.

🔺 **The `mobileappcategory::69500` mobile-app placement exclusion** is widely cited in older PPC
writeups but **could not be verified as still functional** this pass, and PMax placement controls have
changed since. **Do not apply it blind** — check current placement-exclusion options first.

## Reading Auction Insights like an operator

- **Segment by campaign. Never read account-level blended data** — masks a competitor dominating
  branded search while barely appearing in category search. Account number is not actionable.
- **Overlap Rate alone is not a signal.** "High overlap just means you and a competitor are targeting
  the same searches. That's expected." Contextualizes; doesn't drive action.
- **Outranking Share is the actionable metric.** Losing more than half of head-to-head matchups with a
  specific competitor is worth attention.
- **Position Above Rate is more often a bid signal than a quality signal** — check own bid levels
  before concluding "they must have better Quality Score."
- **Check "limited by budget" before drawing any competitive conclusion** from low impression share —
  the single most common misread.
- **Hard limit:** cannot reveal competitor profitability, whether testing or scaling, or margin
  structure. **A competitor outranking you might be losing money on that exact keyword.**

## Change-history forensics

Real value is the **user-type filter**, not the change log. Segment by "Google Ads recommendation"
(auto-applied) vs a specific logged-in human vs API/script changes — an ambiguous "something changed
and performance dropped" becomes an attributable cause in minutes.

Auto-applied changes carry a distinct **"recommendations auto apply-beta"** actor string. **But the
current opt-in state lives on a separate settings surface Change History does not show — a two-surface
audit.** Checking one and not the other produces a wrong conclusion.

Cross-reference the change timestamp against the performance timeseries rather than eyeballing "around
when it dropped" — otherwise a drop gets misattributed to a change that merely coincided with a market
shift. GAQL query → `10`.

## Working the system

**The structural incentive conflict, on record.** Nils Rooijmans, PPC Town Hall 2026-08-03: *"Google
needs them to spend money on the clicks that it uses to train its model."* Both speakers referenced
**Jerry Dischler's "shaking the cushions" testimony** about artificially elevated CPCs — this has
surfaced in sworn testimony, not just community suspicion.

**Auto-apply is not all-or-nothing.** Opt into specific recommendation *types* individually. Disable
entirely for regulated industries needing manual copy review and accounts with strict CPA targets.
Never auto-apply "Improve Your Responsive Search Ads" or automated-bidding recommendations.

> **Reported pattern: Google reps pressure advertisers to enable auto-apply without explaining the
> performance impact.** Treat any rep push toward broader auto-apply as requiring independent
> verification, not compliance.

**Network controls sit at levels people do not expect.** Demand Gen placement controls (Gmail,
YouTube, GDN, Discover) are at **ad-group level, not campaign level** — a common source of accidentally
inherited Display inventory dragging blended performance.

Route access, disputes, credit issues through the **MCC and documented change history** rather than a
single rep relationship. Change-history export is the evidence trail.

## Dead techniques — and their date of death

| Technique | Died | Replaced by |
|---|---|---|
| **SKAG** | Effectively obsolete once close variants (2018–19) then broad + Smart Bidding (2021–22) made keyword granularity irrelevant to matching | Theme-based ad groups of 5–15 keywords feeding RSAs |
| **Modified broad match** | Retired **July 2021** | Folded into phrase match |
| **Expanded Text Ads** | No creation or editing from **2022-06-30** | RSAs |
| **First-click / linear / time-decay / position-based** | Blocked for new actions 2023, **fully removed mid-July 2026** | DDA and Last Click only |
| **Device bid adjustments as multipliers** | Neutered 2019–20 under Smart Bidding | Diagnostic input only; -100% exclusion still works |
| **Dayparting bid modifiers** | Same mechanism | Ad-schedule *pausing* still works as a hard control |
| **The QS-optimization playbook (SKAG-for-QS)** | Died with SKAGs; further undercut by Ad Strength being confirmed non-ranking | Theme-level relevance; **Ad Strength is an asset checklist, not a ranking signal — gaming it moves nothing** |
| **tCPA vs Max Conversions as separate strategies** | UI collapsed the duality into one strategy with an optional constraint | Sequencing: Max Conversions to build a baseline, then layer the target |
| **"Average Position"** | Removed **September 2019** | Top IS% / Absolute Top IS%; Target Impression Share as the bid strategy |
| **"Broad match is low-precision, avoid by default"** | Reversed 2021–23, accelerating through AI Max | Broad is now a first-class default under Smart Bidding; exact is increasingly reserved for defensive/brand terms and known high-value converters |

## Emerging 2026 edge

**AI agents managing accounts — the honest state of the art** [Fred Vallaeys × Nils Rooijmans, PPC
Town Hall 2026-08-03]:

- **"Interns with terrifying confidence."** Generate well-reasoned-sounding output from incomplete or
  generic knowledge, miss fundamentals. Rooijmans' example: an agent recommending changes while missing
  a bid limit already set inside a portfolio strategy, never flagging the conflict.
- **Concrete mechanic worth copying:** an LLM intent-classifier flags irrelevant search terms for
  negation immediately, instead of waiting for a fixed spend threshold — example: waiting for 100
  clicks at $70 CPC means **$7,000 of accumulated waste** before acting. **A confidence score above 85%
  triggers autonomous action; below that it queues for human review.**
- **Infrastructure reality, against the hype:** real agentic management needs explicit SOPs the agent
  can interpret, deliberate context engineering (a maintained client knowledge file), complete action
  logging, an inbound-email loop keeping that file current — not a thin prompt wrapper.
- **Where the moat actually is:** both agreed technical agent setups are replicable within 1–2 years.
  Durable edge is asking better strategic questions, understanding the client's business model,
  surfacing contradictions in client thinking an AI cannot independently identify.

**PMax channel-prioritization controls** (alpha, first spotted Aug 2026 by Heidi Sturrock): per-channel
positive/negative **CPA adjustments** across Search, YouTube, Display, Discover, Gmail, Maps — not
fixed budget percentages, but relaxing or tightening the CPA threshold PMax uses per channel. The first
crack in PMax's budget-allocation opacity. Caveat flagged in the reporting itself: *"channel-level
performance isn't necessarily the same thing as channel-level value"* — do not over-steer off
last-click channel performance.

**Google Ads API Developer Assistant v4.0.0** — live-schema GAQL validation. Canonical write-up:
`10` (AI-assisted pipelines). Do not hand-write GAQL from memory when it is available.

**BigQuery as the loop-closer.** Export Ads data, join against CRM, margin, and inventory data the UI
cannot join natively, then use that analysis to set conversion values fed back into Smart Bidding — the
actual mechanism by which value-based bidding stops being guesswork, closing the stale-value-decay
problem above.
