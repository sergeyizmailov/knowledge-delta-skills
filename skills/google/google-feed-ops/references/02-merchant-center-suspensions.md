# 02 — Merchant Center suspensions and diagnostics

Reviewed 2026-08-27. Ads-account policy is a **separate system** — see `google-ads/09` and
`google-grey-ops`. A Merchant Center suspension and an Ads suspension are different events with
different appeals.

## The gates that block review entirely

Before Google will even review a data source, all of these must be true:

1. **Shipping settings configured.**
2. **A data source exists for the target country.**
3. **Website URL claimed and verified.**
4. **Business address verified.**
5. **US only: tax settings configured.**

Missing any one blocks review completely. **Actual root cause of most "why are my products not
showing" tickets that aren't policy violations.** Check these before diagnosing anything else.

## Issue mechanics

Google structures these as **Warnings → Disapprovals → Preemptive item disapproval (PID)** — not as a
flat list of named suspension strings. PID specifically covers price and availability mismatches.

Most issues carry a **warning period first**. **Egregious account-level issues suspend immediately
with no warning.**

| Stage | Timeline |
|---|---|
| Initial data-source review | **3–5 business days** (can run longer) |
| Account suspension review | **up to 7 days** |
| Re-review after a fix + appeal | **fresh crawl, 24–48 hours** |

To trigger the re-crawl: fix the underlying issue, then either make a small edit or click Appeal.

**Dispute/mediation:** a formal external mediation path exists but is **EU/UK only** and voluntary on
both sides. **US merchants have no equivalent — the only path is Google support escalation.**

## Misrepresentation — the one that matters

Definition: offers inducing purchase without complete information/explicit consent, or representing
the product as anything other than "accurate, realistic, and truthful."

**Triggers:**

- **False claims of affiliation** — fake brand or government endorsement, impersonation, using a name
  or contact info that is not genuinely yours.
- **Missing licenses / non-existent inventory** — selling what you are not licensed to sell, or
  promoting stock you do not have.
- **Deceptive claims** — false health or "miracle cure" claims, improbable results presented as
  typical, false endorsements, claims contradicting scientific consensus.
- **Material omission** — undisclosed total cost or payment model, missing shipping/returns/refund
  policy, hidden T&Cs, missing charity registration numbers for donation asks.
- **Phishing-style data collection.**
- **Unavailable offers** — advertising out-of-stock products or expired deals.

**Required trust elements to fix it** (official) = the **Required website elements** checklist below.

**Consequence structure: egregious → immediate suspension with no warning. Standard → a 7–28 day
warning window.**

## Verbatim strings — what is actually confirmed

Google does **not** publish one canonical list of UI/email suspension strings. Confirmed sub-labels:

From "Fixing Merchant Center warnings and account suspensions for policy violations"
(`answer/13693195`): **"Missing return and refund policy"** · **"Insufficient contact information"** ·
**"Misrepresentation of self or products"**.

From "Editorial & professional requirements" (`answer/6150244`, cross-referenced as "Website needs
improvement"): **"Website that is not fully functional"** · **"Website that has incomplete or difficult
to understand business information"** · **"Not all customers are able to complete their purchase"** ·
**"Website that is using generic placeholders or templated content"**.

🔺 **"Policy violation: Prohibited content", "Untrustworthy promotions", "Insufficient shipping/returns
info", and "Suspicious account activity" were NOT confirmed as verbatim strings.** Treat them as
topic-structure paraphrases. Capture the live string from an actual account rather than quoting these.

## Other suspension surfaces

- **Inaccurate availability / price** — driven by Google's **automated landing-page crawl**
  cross-checking submitted values against on-page structured data and rendered price. A feed saying
  `in_stock` against a live "Out of Stock" page, or a feed price not matching the checkout total
  (tax/shipping-inclusive mismatch is a common false positive), fires this.

  > **It is automated, not manually reviewed. The fix is a feed-vs-page sync fix, never an
  > appeal-and-argue.** Arguing with an automated crawl wastes the review window.

- **Untrustworthy promotions** — promo codes that do not work, expired promotions still live in the
  feed, discounts not reflecting a real price change.
- **Insufficient shipping/returns info** — direct product of the website checklist below.
- **Website not claimed/verified** — a hard gate, not a policy issue.
- **Suspicious account activity** — payment-method fraud signals, account-linking abuse, rapid
  mass-account creation. **Least documented and hardest to appeal**, because Google rarely shares the
  specific triggering data point.

## Required website elements

Canonical checklist — also the Misrepresentation fix list. Visible contact info · working About us /
business info page · **explicit returns policy with a stated refund window** · secure checkout
(HTTPS + a real payment processor) · complete, non-hidden T&Cs · pricing clear about tax and shipping
**before** the final checkout step · **original branding** with no impersonation · clear, supportable
disclosure of any claimed partnership or endorsement.

## Product and store ratings

- **Minimum 50 reviews.** Verbatim: *"You must have a minimum of 50 reviews across all of your
  products."* Applies whether submitting directly or via an aggregator. Below 50, ratings simply do not
  display.
- **Country availability inherits Shopping/free-listings eligibility** — there is no separate restricted
  list. A third-party "~104 countries" figure is directional only.
- **Two opt-in lanes:** (a) work with a supported reviews aggregator — Google fetches on your behalf,
  no Merchant Center upload needed; or (b) direct submission via Google's Product Ratings interest form
  (`troubleshooter/10994881`), then upload a reviews data source under **Products → Product Reviews**
  keyed to GTIN or Brand+MPN.
- **Must be a standalone or sub-account — not a Multi-Client Account.**
- **Monthly re-upload required** to stay eligible. Onboarding lag **2–4 weeks** before ratings go live.
- 🔺 Google's official approved-aggregator list was not retrievable. Third-party context names
  Trustpilot, Judge.me, Loox, Yotpo, Stamped.io — **do not present this as Google's official list.**

## Audit sequence that finds the money

1. **The five review gates above.** Half of "not showing" cases end here.
2. **Products → Needs attention** — separate item-level issues from account-level ones. Account-level
  issues suppress everything; item-level ones only affect their SKUs.
3. **Disapproved vs "expiring soon"** — expiration is a stale-feed problem
  (`expiration_date` must be <30 days out and the feed must refresh), not a policy problem.
4. **"Limited performance due to missing value"** — recommended attributes absent. Not a violation, but
  a direct volume cap.
5. **Feed vs live page diff on price and availability** for a sample of SKUs, including the checkout
  total, not just the product page.
6. **GTIN coverage** — missing GTINs where one exists cost visibility and disable price benchmarking.
7. **Promotional text in titles and descriptions** — a policy trigger hiding in plain sight.
8. **The website element checklist** — the cheapest fix with the largest blast radius, since it clears
   several Misrepresentation sub-types at once.
