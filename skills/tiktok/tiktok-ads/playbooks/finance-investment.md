# Finance, investment, crypto, lending, insurance

## Gate — read this before anything else

**Some of this vertical is prohibited outright, not restricted.** The distinction decides whether
there is a project at all.

**Prohibited globally** (`08`): CFDs · spread betting · binary options · penny stocks · mini-bonds ·
payday loans · pawnbroker loans · penny auctions · bail bonds · unlicensed or "unaccredited" digital
banks · pyramid and MLM schemes · "get-rich-quick" and "too good to be true" offers.

**Forex and CFDs are prohibited, not restricted.** That is stronger than the framing common in
affiliate discussion, and it is the most consequential single fact in this playbook.

**Restricted, with certification** — securities, trading platforms, investment consultation, funds,
credit cards, loans (mortgage/consumer/P2P/BNPL), virtual currencies, exchanges, custody wallets,
NFTs, insurance, deposit accounts, fintech:

- advertiser **licensed by the local or regional financial authority** for the target market;
- **18+** targeting (**20+** for crypto in Japan);
- APR, fees and repayment terms disclosed **on the landing page**;
- **crypto exchange services in most developed markets require the TikTok Sales Representative
  application process with licensing proof — explicitly not self-serve.**

Authorization binds to the **verified entity** and usually a specific ad account. A replacement
account needs a new approval. This is the structural reason finance buyers use agency-provided
accounts (`02`): the agency already holds the certification.

**Run `08` Q1/Q2 live before designing anything.** Per-country lists in blogs contradict each other
and TikTok changes markets silently. Some markets are "promote only" with no paid financial ads at
all.

## Credit offers are also a special ad category

Credit cards, loans, long-term financing → declare `special_industries: ["CREDIT"]`. That
**restricts ad-group targeting**: no zip targeting, no automatic targeting, no device-price
targeting, no targeting expansion, no interest *keywords*, **no lookalikes** (include or exclude),
under-18 excluded, gender unlimited, household income disabled (`04`).

Generally available to advertisers registered in the US or Canada; others targeting those countries
need an extra allowlist. An empty `special_industries` on a credit offer is a violation.

Design the targeting knowing lookalikes are off the table — that removes the default scaling lever
most buyers reach for.

## Payout event and the ladder

Long funnels with long lag — the defining property of this vertical.

```
Registration → KYC / verified → Funded account (FTD) → Qualified deposit / trade
```

The payout is usually deep (FTD or qualified FTD); the volume at that depth is usually far below what
TikTok needs to learn (**~25 results per ad group per week, and 50 by TikTok's own delivery advice**, `05`).

The standard resolution: start on the shallowest event that still correlates with payout —
`CompleteRegistration` — and **write the switch condition into the plan up front**: *"move to the
deposit event at N/week"*. Do not improvise it later.

`StartTrial`, `SubmitApplication` and `ApplicationApproval` (added May 2025) exist and map neatly
onto application funnels — most buyers still use generic events (`07`).

## Numbers to get from the operator

- Payout event, by tracker status name, in writing.
- **Registration → funded conversion rate and its lag.** This sets the judging window, and in finance
  it is commonly weeks, not days.
- Break-even CPA at the payout event, and CPA at each upstream step.
- Caps, and whether unqualified registrations are scrubbed.
- Which licence covers which market, and the **certification lead time** — this is a project
  dependency, not a footnote.

## TikTok-specific failure modes

- **Judging on registrations when payment is on deposits.** The registration CPA will look excellent.
- **Income claims and "get-rich-quick" framing in creative** — a rejection trigger regardless of how
  licensed the advertiser is. This is where compliant advertisers lose ads.
- Landing page missing mandatory APR/fee/risk disclosure — a policy problem, not a CRO problem.
- **Changing the landing page after approval is a documented suspension trigger** (`08`). Finance
  funnels get iterated constantly; put a change-control rule in the plan.
- Age floor must be a hard `age_groups` control. Interest targeting is not a control (`04`).

## Shape of the derivation

Is the specific product prohibited or restricted **in this market**, verified live → licence and
certification in hand, attached to *this* account → credit category declared? → payout event and lag
→ optimization event from weekly volume at depth, with the switch condition written → targeting under
special-category restrictions → creative screened against income-claim policy → judging window from
the lag.
