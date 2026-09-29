# 04 — Failure forensics, enforcement tracks, scaling posture

Reviewed 2026-08-27. Policy taxonomy and certifications → `google-ads/09`.

## Classify the track before you act

Every response decision follows from which track a failure sits on; wrong assumption wastes the
recovery window or destroys a recoverable account.

| Track | Behavior | Correct posture |
|---|---|---|
| **A — Egregious** | Suspension on detection, **no warning**, permanent. Appeal only in "compelling circumstances". **Propagates to related accounts and blocks new account creation** | Freeze. Do not self-farm a new Google identity — that is a separate offense. Reseller seat-swap is a different product (`05`). Appeal once with evidence, or exit |
| **B — Non-egregious** | **Minimum 7-day warning** before any suspension | You have a real window. Fix, then appeal or acknowledge |
| **C — Limited Ad Serving** | **Not a suspension.** Partial impression throttle with its own appeals form. Aug 2026: covers **all Ads**, phased through **2028** | Recoverable by compliance + verification. Do not panic-migrate |

**Track A**: Malicious Software · **Circumventing Systems** · Misrepresentation (hidden identity, false
claims, dishonest pricing, clickbait, manipulated media) · Counterfeit · Unacceptable business
practices · trade sanctions · sexually explicit · CSAE.

**Track B**: Enabling Dishonest Behavior · **Destination Requirements** · Technical Requirements ·
Editorial · Sexual Content (explicitly confirmed: "violations will not lead to immediate account
suspension without prior warning").

**Track C** triggers: prevalence of abuse · negative user-feedback signals · missing advertiser
verification or branding clarity. **Practitioners routinely misread this half-dead state as a
suspension** — ads keep running, reduced reach.

Google: enforcement is "a combination of Google AI and human evaluation", suspension reserved for
"repeat or egregious violations" — escalation on Track B, same-day jump to permanent on Track A.

## Death modes

| Mode | Track | Response |
|---|---|---|
| **Instant disapproval on upload** | B, ad-level | Static policy trigger, pre-serve automated review. Fix named flag, resubmit — auto re-review in 24–48h. **Cheapest failure mode; doesn't implicate the account** |
| **Approval → mass disapproval ~24h later** | B | Fast creative pass clears first, slower **AdsBot landing-page crawl** catches destination mismatch after. Isolate: domain-specific → rotate that domain per signal discipline (`03`). Account-wide across multiple domains → account-level signal problem, not content. 🔺 Inference from documented crawl architecture, not sourced practitioner claim |
| **Suspension on first payment or first charge** | Payment | Directly supported: verification fires on "initial billing setup"; first real charge = fraud model's first genuine transaction signal. **Do not re-submit a card immediately from the same session.** Freeze, review persona's full signal consistency, then verify. "Temporarily paused", often not dead |
| **Suspension at a spend threshold** | 🔺 Unconfirmed | Mechanistically plausible — threshold charge cycles create natural inspection checkpoints. **No source confirmed it.** Not established. Hedge: stagger spend ramps across a portfolio so failure timing isn't synchronized |
| **"Circumventing systems" wave across an MCC** | **A** | Named policy consequence: "creating new accounts to re-enter the system" and "spreading policy-violating ads across multiple accounts" are enumerated triggers; cascades to "linked accounts (both payment and email accounts)" and related Merchant Center accounts. **Shared-fate risk of renting a seat in someone else's MCC.** Reinstatement rare; "compelling circumstances" implies exit and rebuild, not fight every case. Replacement vs self-farm → `05` |
| **MCC third-party pause** | Manager | 2025-06-06: child accounts **paused while linked** to an MCC in third-party violation. **Unlink** to serve again. Isolation lever, not a creative problem |
| **Account frozen (cannot edit ads)** | A, Jun 2024 | Official `adspolicy/answer/14899401` (posted 2024-05-13). Allowed: pay, tax, add payment method, cancel/refunds, appeal, verification, reports. All else off. StubGroup: freeze applied **2024-06-19** to accounts suspended from that day. Appeal must describe **future** fixes |
| **Billing hold** | Payment | Three official triggers — unpaid balance, suspicious activity, chargeback. Read-only access preserved. Resolve at **payment-profile level**; not a creative problem |
| **Limited Ad Serving** | **C** | Half-dead, not dead. Fix compliance and verification, use the dedicated form |

Independent corroboration of MCC cascade, from the gambling policy (effective 2026-09-14): *"Manager
accounts (MCCs) with a pattern of revoked certificates or violations across managed accounts risk
losing the ability to apply at all."* Mechanism is real, documented in at least one vertical.

## What links accounts

See `01` for the full signal list. Operationally important points:

- **Ban evasion is charged as its own offense** on top of the original suspension cause.
- **Submitting false information during verification = Circumventing systems.** Failing honestly
  pauses; lying suspends permanently.
- No single signal triggers linking; threshold undisclosed by design.
- **GTM container ID and Merchant Center/Search Console/Analytics ownership** are the cross-links
  people forget — not thought of as "ad account" surfaces.

## Appeals under fire

Full appeal guidance in `google-ads/09`. Three points that matter most when an account is down:

1. **Identify the exact root cause before appealing.** Generic/repeated near-identical appeals
   *worsen* outcomes — reviewers read them as evasive.
2. **Re-review evaluates current state, not intent.** Issue still live when appeal is processed →
   auto-rejects. Fix first, appeal second.
3. **One appeal at a time.** Parallel submissions explicitly discouraged.
4. **In-account appeal for policy decisions >6 months old closed 2026-07-21.** Contact support. Still
   ≥6 months from suspension date to appeal; after that the in-product form is gone.
5. **After a first CS reject**, recovery shops report the form shrinks (no attachments, no real case
   ID), support can't escalate — StubGroup, their book. Don't burn the first CS appeal on a generic
   letter.

**Evasive ad content** (7-day warning) and **Circumventing systems** (no warning) can describe the
same creative-variation behavior — the charge is Google's classification. Cloak stacks/replacement →
`05`.

For strikes specifically, **acknowledging and fixing is often faster/more reliable than appealing**,
even believing you're compliant. Appeal only on a real factual disagreement.

🔺 Reseller claims of "85–90% appeal success with proper documentation vs <30% self-filed" are
single-source, no methodology — don't repeat as fact.

## Scaling posture

**No Google-specific day-1→day-7 warm-up curve, replacement-reserve ratio, dead-vs-slow criterion, or
batch-launch cadence exists in reachable public material** — far more of this exists for Facebook,
plausibly since Google's ecosystem skews legitimate agency/reseller vs pure burner-farming. What
follows is derived from confirmed mechanics, labeled as such.

- **Warm-up is structurally gated by Google's own threshold ramp** for any account not on an invoiced
  credit line — cannot spend past current threshold until paid and raised. *Involuntary* ramp
  discipline — slower, but real trust accruing.
- **Agency/invoiced accounts bypass that involuntary ramp** — warm-up discipline becomes
  **self-imposed or absent**. Scaling hard/fast on a brand-new sub-account skips the exact
  graduated-trust signal Google's system would otherwise require.
- **Concentration vs dispersion**: fewer, higher-spend accounts reach Smart Bidding's conversion floor
  faster (~30–50 conversions/campaign/month, `google-ads/01`) but concentrate failure risk. More,
  lower-spend accounts survive individual burns but each struggles to accumulate optimization signal —
  **dispersion only improves survivability if not all riding the same manager account, payment
  profile, domain pool.** Otherwise: cost of dispersion, risk of concentration.
- One concrete datapoint: antidetect vendor review cites affiliates running **15–20 Google Ads
  accounts** in parallel. Single source, vendor-adjacent.
- **Derived first-test structure** (inference, anchored on confirmed mechanics above): 1 campaign ·
  Search-only · pinned Final URL · 2–3 tight ad groups · Manual CPC until conversion floor (Smart
  Bidding off) · day-1 budget at current threshold headroom, not above · auto-apply off, no ACA, no
  AI Max. Probe prices the SEAT (delivery state, spend-without-conversion, verdict), not a winner —
  one variable at a time thereafter, so the next burn is attributable.

## Attribution method — turning dead accounts into a cause

**Ported from `meta-grey-ops/06`, adapted to Google's trust model — method is platform-agnostic, the
dimensions below are not.** No Google-specific practitioner consensus on hazard rates found — the
discipline transfers, the numbers do not.

**Log these from birth or you can attribute nothing:** supplier/batch · account age at first spend and
at death · antidetect profile + proxy cluster (**subnet/ASN**, not the single IP) · **payment
instrument and billing identity** · **MCC parent, if any** · domain(s) and their Safe Browsing state ·
certification/verification state per geo · launch method (API vs UI, day-0 spend jump) ·
spend-at-death · **which enforcement track fired** (egregious / 7-day warning / Limited Ad Serving —
top of file). A death without these fields is an anecdote.

**Rank by rate, not raw count.** The most-used domain shows the most deaths because it ran most.
Two different rates — don't conflate:
- `deaths ÷ accounts exposed` — cumulative share dead. Quick pass only; ignores survival time.
- `deaths ÷ account-days at risk`, censoring the still-alive — separates "dies fast" from "dies
  eventually." Kaplan–Meier or a discrete-time hazard once there's history.

Minimum-exposure floor first: 3 accounts at 100% death is noise next to a 200-account batch at 30%.
Survival **time** carries the same signal directionally — dead at $5 pre-spend = supply/identity
problem; dead at $400 after ten days = scaling/creative-heat problem. Opposite fixes.

**Google-specific pivots Facebook doesn't have.** Several accounts fail together → pivot on the shared
attribute; on Google the highest-yield pivots are billing-side, not session-side:
- **Same payment instrument or billing identity** → the card/identity is the burn, not the accounts.
  Single most likely shared cause on Google, no Facebook equivalent.
- **Same MCC parent** → check cascade; policy names "linked accounts (both payment and email
  accounts)" and related Merchant Center explicitly.
- Same subnet/ASN · same domain · same supplier batch · same creative family · same launch script.
- **Deaths clustered around a billing event** (card added, threshold charge, chargeback) rather than
  logins → confirms billing-identity hypothesis over session hypothesis.

Three accounts sharing an attribute = **prime suspect**, not proven cause — confirm with a balanced
check before acting.

**Balanced designs — confounding is the whole trap.** New domain + new creative + new batch launched
together, and a wave pins on nothing. Vary **one** infra axis across an otherwise-balanced set,
creative fixed: domain A vs B, proxy cluster A vs B, batch A vs B, **payment method A vs B**.
Divergent death/CPC/delivery isolates that axis (infrastructure testing mode,
`measurement-experimentation-ops`). Several things must change at once → stagger them so the timeline
separates effects.

Google-native version of the one-variable rule in `03`: a **fresh domain on an existing clean account**
still mass-disapproved implicates the **account or its payment identity**. A **new domain clearing
review** on an account that just had another domain mass-disapproved means the **prior domain** was
the burn.

**Incident fingerprints** — keep {symptom + timing + shared attribute → confirmed cause → fix}.
Distinct Google shapes: instant day-0 suspension across a batch (supply/verification) ·
**suspension on the first threshold charge** (billing identity) · gradual disapproval creep then
account-level action (policy drift / AdsBot re-crawl on destination) · **Limited Ad Serving with no
notification** (trust, not violation — impressions quietly capped) · single-domain collapse to ~0 LP
CTR with ads still serving (funnel fault, not enforcement — `senior-buyer-ops/03`).

**Boundary:** this is diagnosis method. Reactions live in `01`/`03`; the portfolio decision after a wave
is `senior-buyer-ops/01`.

## Google vs Facebook — the operational differences

| Dimension | Google | Facebook |
|---|---|---|
| **Trust anchor** | **Billing history** — threshold ramp is a literal disclosed product feature | Behavioral/social-graph signals; no equivalent billing trust ramp |
| **Destination review** | **AdsBot actively fetches/re-crawls the landing page** as ongoing enforcement, explicit crawlability/same-content requirements | Post-approval destination re-crawling less central |
| **Cascade** | **Explicitly named in policy** — suspends "linked accounts (both payment and email accounts)" and related Merchant Center accounts | More session/profile-scoped, no equivalent explicit cascade language |
| **Highest-risk moment** | **A payment event** — adding a card, threshold charge, chargeback | Login-adjacent |
| **Domain burn radius** | **Cross-Google-product** — Safe Browsing affects organic Search visibility too | Platform-scoped |
| **Moderation timing** | Two windows: fast pre-serve automated check (minutes), slower AdsBot re-crawl (~24h+) | — |
| **Appeal posture** | Appeals exist and matter on Tracks B and C; Track A near-terminal | `meta-grey-ops` treats fresh agency-account restrictions as not worth appealing — request replacement |

**Practical translation:** on Facebook you protect the session; on Google you protect the **billing
identity and the destination**. Porting Facebook's playbook wholesale gets the risk model wrong both
ways — over-investing session hygiene, under-investing payment consistency and landing-page integrity.
