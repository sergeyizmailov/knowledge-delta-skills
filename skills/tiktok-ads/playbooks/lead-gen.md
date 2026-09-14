# Lead generation (forms, calls, DMs, B2B, local services)

## Gate

Generally open. The gates that bite are **vertical-specific** — finance, health, education and legal
services each carry their own certification (`08`) — and **special ad categories**: an offer touching
housing, employment or credit must declare `special_industries`, which then **restricts targeting**
(`04`). Declaring nothing on a credit offer is a violation, not a shortcut.

## TikTok has more optimization locations than Meta — check before defaulting to a landing page

`promotion_type` options for lead gen:

| Location | Notes |
|---|---|
| **Instant Form** (`LEAD_GENERATION` + `INSTANT_PAGE`) | Native, fast-loading, highest volume, lowest intent |
| **Website** (`LEAD_GENERATION` + `EXTERNAL_WEBSITE`) | Your page, your tracking, lower volume |
| **TikTok direct messages** | GA across much of APAC and LATAM, allowlisted elsewhere |
| **Instant messaging apps** | Same regional pattern |
| **Phone call** | Allowlist-only |

If the offer is genuinely a conversation — high-consideration services, local trades, anything a form
underserves — the DM and IM locations are worth checking before defaulting to a form. Most Meta-
trained buyers never look.

## The payout-event problem, stated plainly

"Leads" is not an event. **Which tracker status pays** — raw form fill, contacted, qualified,
appointment held, closed — is the whole economics, and it must come from the operator in writing
(`01` intake #3).

The ladder:

```
Lead (form fill) → Contact/qualified → Appointment → Closed
```

Optimizing on form fills when payment is on qualified leads reliably buys volume nobody pays for.
This is the single largest source of wasted spend in the vertical.

**Close the loop.** Send the CRM disposition back via Events API with `event_source: "crm"`, or use
`PREFERRED_LEAD` as the optimization goal, so TikTok optimizes toward the event that actually pays
(`07`). Most lead-gen accounts never do this and leave the most money here.

## Lead retrieval

`lead_get` / `lead_field_get` via API · Leads Center → Connect CRM in the UI · TikTok **webhooks**
for real-time push to an arbitrary endpoint (`tiktok-ops/06`) · Zapier and LeadsBridge as middleware.

Webhook delivery is **at-least-once** — handlers must be idempotent — and a revoked token **stops
delivery silently** with no notification. Heartbeat it.

## Numbers to get from the operator

- Payout event, in writing, with the tracker status name.
- Lead-to-payout **conversion rate and lag** — this sets the judging window, and lead-gen lag is
  usually longer than the buyer assumes.
- Daily/total caps. Traffic past a cap is unpaid.
- The **quality metric the advertiser judges on later** (contact rate, show rate, scrub rate). It is
  rarely the same as the metric you optimize on.
- Who follows up, and how fast. Speed-to-lead dominates close rate and is outside your control but
  inside your reported CPA.

## TikTok-specific failure modes

- **Instant Form volume flatters CPL and hides quality.** Compare on the payout event, not on CPL.
- Form fields: every extra field cuts volume and raises quality. That is a trade to make
  deliberately, with the operator, not a default.
- `PREFERRED_LEAD` exists and is under-used — it optimizes toward leads matching your qualifications.
- Special ad category restrictions land at the **ad-group** level: no lookalikes, no zip targeting,
  no automatic targeting, gender unlimited, under-18 excluded (`04`). Plan targeting knowing this.

## Shape of the derivation

Payout event → optimization location (form / website / DM / call) → optimization event from weekly
payout-event volume → special category declared? → targeting under whatever restrictions that
imposes → structure from readable tests → measurement window from lead-to-payout lag.
