# 06 — Portfolio forensics (why accounts die, attributed)

Reviewed 2026-08-28; tr-1 fingerprint added 2026-09-29. **Method, not measurement.** Standard survival analysis; no
figure here is Meta-sourced or benchmarked, none is meant to be quoted as one.

`senior-buyer-ops/01` says "diagnose which cause" for a ban-rate spike. HOW: turn
dead accounts into an attributed hazard, fix the real driver instead of changing
everything at once.

## Log the survival dimensions (or nothing is attributable)

Per account, from birth: supplier/batch, account age at first spend and at death,
antidetect profile + proxy cluster (subnet/ASN, not just IP), domain(s), creative
family (`senior-buyer-ops/02` attribute bundle), launch method (API vs manual,
schedule, day-0 spend jump), spend-at-death, death signal (checkpoint / disable /
restriction / soft throttle). Death without these fields = an anecdote.

## Failure rate, not raw count

Rank each dimension by RATE — the most-used domain/proxy/creative shows the most
deaths simply from running most. Two rates, don't conflate:

- `deaths ÷ accounts exposed` = cumulative failure rate. Quick, but ignores
  survival time and censors nothing.
- `deaths ÷ account-days at risk` (exposure-adjusted, censoring accounts still
  alive) — separates "dies fast" from "dies eventually." For shape over account
  age: Kaplan–Meier or discrete-time hazard once enough history exists.

Set a minimum-exposure floor: 3 accounts at 100% death outranks a 200-account
batch at 30% but is noise. Survival TIME is directional too: died at $5 pre-spend
= DOA supply problem; died at $400 after 10 days = scaling/creative-heat problem —
opposite fixes.

## Confounding is the trap → balanced designs

New domain + new creative + new batch launched together → ban wave can't be pinned
on any one. Vary ONE infra axis at a time across an otherwise-balanced set: same
proven creative across accounts differing only in the tested axis (domain A vs B;
proxy cluster A vs B; supplier batch A vs B), balanced counts — divergent
death/CPM/delivery isolates that axis. Infra-fixed inversion of a creative test
(third testing mode, `measurement-experimentation-ops`). Never move two axes at
once when something is dying; a multi-change launch should at least stagger them.

## Cross-account anomaly detection

Bans cluster by shared cause. When several fail close together, pivot on the
shared attribute: same subnet/ASN (proxy cluster burned), same domain (rotate,
`tracker-ops/03` signal), same supplier batch (bad shipment, stop launching it),
same creative family (pull it everywhere, not just the banned account), same
launch script/timing (automation fingerprint). One account dying is background
rate; three sharing an attribute makes it the PRIME SUSPECT — confirm with a
balanced/controlled check above, not a proven cause (can be a confounder;
clustered deaths can be coincidence at low counts).

## Incident fingerprints

Keep a short library: {symptom + timing + shared attribute → confirmed cause →
fix}. A new wave usually rhymes with an old one — matching the fingerprint skips
re-diagnosis. FIELD 2026-09-27: single account disabled ~6h after its heaviest API day (4 CBO campaigns over 24/09 +
26/09, two an hour apart, 10 ad sets/10 ads, + a code 17/2446079 storm the tool sleep-retried 60→300s for ~12 min),
weakest account in the set ($43 lifetime, $2 billing threshold, 21 micro-charges); UI reason = Account Integrity
"created or used with an automation that doesn't follow our rules" (`disable_reason` 1). Sibling accounts on the
same SU token/page/domain with lighter API load survived. Cause NOT proven (same reason hits manual advertisers and
whole agency lines, `02` §8) → pacing adopted anyway (`00` §5). FIELD 2026-09-29 (n=1, cause not
proven): tr-1 (own BM, 30-day-old account, ~$360 lifetime) — 1 CBO campaign, 3 image ads approved, then each
DISAPPROVED "Spam" within 1-2 min, account `status 2` / `disable_reason 1` 2 min after the third, ~$9 billed,
$0 ad spend; API load was light (one campaign, then a code-17 throttle after the disable). This is not the
la595 burst-plus-retry-storm shape; suspects (none tested): shared origin (card/Page/pixel with
siblings), campaign name and headline carrying the casino name, a Page with 0 fans. Distinct fingerprints: instant day-0 disable across a batch
(supply/verification); gradual CPM climb then death (creative heat/policy drift);
simultaneous checkpoint across one subnet (proxy cluster/geo-mismatch);
single-domain collapse to ~0 LP CTR (domain/SSL/cloak fault, not a ban —
`senior-buyer-ops/03`).

## Boundary

Diagnosis/attribution METHOD only. Reactions (freeze, rotate domain, replace
batch, kill creative) → `01`/`05`/`tracker-ops`; portfolio-level decision (shift
budget after a wave) → `senior-buyer-ops/01`.
