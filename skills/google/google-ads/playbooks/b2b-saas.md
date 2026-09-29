# Playbook — B2B and SaaS (white)

Reviewed 2026-08-27.

## The whole vertical hinges on one thing

**Optimizing Smart Bidding on MQL or form-fill count with no SQL or pipeline value flowing back.**

Over a 3–6 month sales cycle the algorithm buys cheap low-intent form-fills that never close — **the
in-platform metrics look healthy the entire time** while the real CAC-to-revenue ratio blows out. CPL
falls, conversion volume rises, pipeline dies. Everything else in this file is secondary.

## The fix

Capture the **GCLID at form submission**, map CRM lifecycle stages (Lead Created → MQL → SQL →
Closed-Won), and upload conversions at each stage **with a value proportional to that stage's real
worth** — not a binary converted flag.

Upload **at minimum daily**. Delivery via the API, Zapier, or a Salesforce integration.

**Two hard constraints to check before designing this** (`../references/06`):

- The **2026-06-15 cutoff** — a fresh developer token cannot onboard classic gclid OCI. Plan around
  Data Manager or enhanced conversions for leads.
- **Backdate windows: 90 days (gclid), 63 days (EC for Leads), 54 days (adjustments).** A 3–6 month B2B
  cycle **exceeds all of them** — cannot upload the terminal Closed-Won event directly. Upload an
  in-window qualified-lead milestone, true up value with adjustments.

## Low-volume survival

Google's own guidance: measure over windows with **≥30 conversions/month** (**≥50** for tROAS) before
trusting the read.

Below that: **under ~15 conversions/month favors manual bidding over Smart Bidding.** One cited case
reverting tCPA→manual cut cost-per-conversion **30–40%** — single case, not a guarantee.

Smart Bidding also performs worst when budget-constrained — a capped daily budget in a low-volume
account actively prevents the algorithm from bidding into its best available auctions. If you cannot
fund it properly, don't use it.

Micro-conversion laddering (`../references/12`) is the alternative: bid on the closest-to-bottom-funnel
event that clears volume, migrating down-funnel as volume grows.

## Competitor bidding

**Bidding on a competitor's brand term as a keyword is settled as legal** in all major markets —
precedent traces to *1-800 Contacts v. Lens.com* (2004) and *Rescuecom v. Google* (2011).

**Google's restriction is in ad copy, not keyword targeting.** Cannot use a competitor's trademarked
name/logo in headline/description, or imply you are them. Enforcement **complaint-driven** — Google
does not proactively investigate trademark-as-keyword use, only ad text when the owner complains.
Since **Feb 2025** the proactive trademark-protection submission form is gone; enforcement reactive
per ad.

"vs" pages, "alternative to" pages, and factual competitor mentions **on the landing page** are
permitted.

Economics: competitor-term CPCs run **2–4× category-keyword CPCs** (~$10–25/click in B2B), but
cost-per-SQL from that traffic is often **20–40% lower** because intent is already bottom-funnel.

**Run it as its own campaign measured against its own CPA target** (`../references/12`) — folded into
blended performance its naturally worse CVR reads as a problem rather than a deliberate trade.

## Channel split

🔺 A cited 2026 "industry standard" split — 41% LinkedIn / 46% Google Network / 8% Meta / 5% other — is
vendor-published with no disclosed methodology. Directional at best. One real implementation ran 65%
Google Search / 35% LinkedIn Message Ads for a procurement-software client. **The right allocation
depends on sales-cycle length, not a fixed ratio.**

| Metric | Google Ads | LinkedIn |
|---|---|---|
| CPL | $50–150 (avg $70.11) | $150–300 |
| Lead→customer CVR (one cited case) | 4% | 12% |

**Central lesson — the inversion:** LinkedIn's higher CPC can still net a **lower final CAC** because
the close rate was 3× in that case. **Never pick a channel on CPL alone** — pipe every lead through
offline conversion import to see real CAC-to-close. Same failure mode as the top of this file, one
level up.

## AI Max warning

**B2B lead gen is the worst-documented case for AI Max** (`../references/05`). Does not know your ICP,
does not care about job titles or deal stages, efficiently scales low-intent content-download
conversions while pipeline quality craters. HBT Digital home-services case (964 of 993 matched terms
producing zero clicks) is the sharpest documented failure and the dynamics transfer.

If the account clears the ≥30 conversions/month gate and you test it anyway, baseline the search terms
report **before** September and use the **ad-group-level search term matching toggle** as the real
control.
