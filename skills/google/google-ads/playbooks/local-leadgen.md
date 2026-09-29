# Playbook — Local services and lead gen (white)

Reviewed 2026-08-27.

## LSA is migrating into PMax 🔺

Local Services Ads become a **Performance Max subtype with pay-per-lead goals**. Phase 1 from **August
2026** for US home/storefront verticals (plumbing, HVAC, electrical, appliance repair, house cleaning,
lawn care, roofing, pest control, moving); broader US late 2026; non-US and remaining verticals 2027.

**Manual bidding and per-vertical Target CPA caps consolidate into one campaign-level Target CPA.**
Standalone LSA dashboard disappears; BBB callouts dropped.

Any budget or bid model built today should anticipate this consolidation.

## Eligibility and verification

Screening varies by category and location: **background checks** (business, owner, certain employees,
plus any field agent performing in-home services) · business registration · insurance · license
verification · minimum review requirements.

**Badge change:** Google retired the separate **Google Guaranteed** and **Google Screened** badges
**October 2025**, replacing both with a unified **"Google Verified"** checkmark. Update client material
still using old names. Legacy Guaranteed backing still offers up to **$2,000** in dissatisfied-customer
compensation.

## The dispute lever is gone

LSA is **pay-per-lead**, not pay-per-click.

**Google removed manual lead disputing August 2024**, replacing it with an **automated credit system**:
every lead reviewed within **72 hours**, auto-credited if identified as spam, wrong number, or obvious
misdial — no advertiser action required.

For leads that do not auto-credit, the only remaining lever is the **Lead Feedback Survey** (mark
"Dissatisfied" within 30 days). **That is feedback, not a guaranteed credit.**

🔺 Reported lead costs run roughly **$15–30** for home-service trades and **$50–150+** for legal and
some healthcare categories — vendor estimates, no official Google pricing table exists. Directional
only.

## Call tracking

Google's **forwarding number** dynamically swaps the displayed number for ad-driven traffic, reports
call length, answer status, rough caller location. A call counts as a conversion once it clears an
advertiser-set minimum duration (commonly 30s+).

Two types: **Calls from Ads** (call-only ads and call assets, no site changes) and **Calls to a website
number** (requires the Google tag plus a JS snippet swapping the number for ad-clickers).

Note the sunset in `../references/01`: call-only ad **creation** was removed Feb 2026, with full sunset
slated Feb 2027. Call **assets** on standard ads are unaffected.

## The lead-quality loop — the thing that actually decides outcomes

Capture the **GCLID at form submission**, map it to CRM lifecycle stages, upload **offline conversions**
back into Google Ads. **Daily upload cadence** for Smart Bidding responsiveness.

Check the 2026-06-15 OCI new-adopter cutoff before building this (`../references/06`).

🔺 One vendor-cited case reports **23% lower cost per qualified lead** versus optimizing on raw
form-fills. Single-source, no methodology. The *direction* is well-established; the number is not.

## Benchmarks — priors only

[WordStream/LocaliQ, US]

| Industry | CPC | CPL | CTR |
|---|---|---|---|
| Attorneys & Legal | $8.58–$9.87 | $131.63 | 5.30% |
| Home & Home Improvement | $7.85 | — | 5.59% |
| Dentists & Dental | $7.85 | — | 5.38% |
| All-industry avg | $5.26–$5.42 | $66.69–$70.11 | 6.64% |

CPL rose for 69% of home-services advertisers, averaging **+10.51% YoY** against an overall +5.13%.

🔺 HVAC is bucketed inside Home & Home Improvement in WordStream's taxonomy — no standalone HVAC line
exists in the source. Do not invent one.

## Geo and dayparting

LSA service area is set in the Local Services dashboard's own radius targeting, **distinct from standard
Search geo-targeting**.

For standard Search: pair a geo radius around the service area with **negative-geo exclusions for
adjacent competitor territory**, and set location targeting to **Presence**, not presence-or-interest —
that default is the classic local budget leak (`../references/01`).

🔺 Dayparting economics were not covered by a hard current source. The reasoned default: keep 24/7
bidding live with a lower after-hours modifier for genuinely emergency verticals (plumbing, HVAC, PI
legal) where an after-hours lead still converts; daypart to business hours for non-emergency services
where an after-hours call burns lead cost with no answer capacity. **This is inference from vertical
economics, not a benchmark.** Note also that under Smart Bidding, dayparting **bid modifiers** are
inert — only the schedule itself is a hard control.

## What breaks first

**Losing the manual-dispute lever combined with running Smart Bidding without an offline-conversion
feedback loop.** Bad leads that don't auto-qualify for credit get paid at full price, and with no
CRM-stage data flowing back, Smart Bidding has no way to learn which sources were garbage — so it buys
more of the same, efficiently.
