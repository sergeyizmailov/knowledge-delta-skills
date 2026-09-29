# 04 — Google lane

Reviewed 2026-08-27. Meta lane is the rest of this skill; metric discipline in SKILL.md applies
identically. This file covers only what differs when the traffic source is Google Ads.

## The chain

```
click -> Google appends gclid -> tracking template ({lpurl} + {gclid}) -> tracker stores gclid
-> offer/LP -> conversion -> network S2S postback -> tracker -> upload back to Google (OCI)
```

Google Ads mechanics for the last hop → `google-ads/06`. Redirect/review-layer constraints →
`google-grey-ops/03`.

## Check this before building anything

**From 2026-06-15, `UploadClickConversion` fails unless the developer token has previously sent an
offline-conversion or enhanced-conversions-for-leads request.** A fresh developer token **cannot
onboard classic gclid-based OCI at all.** Existing integrations keep working. New ones must go
through **Data Manager API** or enhanced conversions for leads — hard blocker, verify live status
before committing engineering effort.

## Post-cutoff path: Data Manager API [practitioner, MagicClick 2026-08]

Classic `UploadClickConversion` stays for tokens that already onboarded. New tokens:
`POST https://datamanager.googleapis.com/v1/events:ingest`.

- Conversion action: Tools → Conversions → Import → **Clicks** → Website. Address-bar `ctId=` =
  `conversion_action_id` / `productDestinationId`.
- GCP: enable **Data Manager API**; service-account JSON; invite `client_email` as **Standard**
  user on the CID (hyphens stripped). JWT-bearer scope `.../auth/datamanager`. SA path is **Data
  Manager only** — Google Ads API still has no SA auth (`google-ads/10`).
- `{gclid}` expands **only** in the Final URL Google Ads actually stores — a cloak/intermediary
  must forward the already-substituted value, not put `{gclid}` in its own redirect.
- Capture **gbraid/wbraid too** — gclid-only silently drops iOS. Windows/dedup/`partial_failure`
  still apply.
- Send **Approved/payout events only**. 🔺 Vendor: 14-day trial before the action feeds bidding
  (visible in reports immediately) — verify in-product.

## Click IDs — three, not one

| ID | When |
|---|---|
| `gclid` | Any web click, including mobile web |
| `gbraid` | Web click → iOS **app** conversion, ATT consent granted |
| `wbraid` | iOS app click → **web** conversion, without full ATT. Aggregated, non-user-identifying |

Capture all three plus `gad_source`/`gad_campaignid` on every landing page; store all, submit
whichever is populated. gclid-only silently loses iOS traffic entirely.

## ValueTrack — the escaping ladder

Google explicitly designs ValueTrack around multi-hop tracker redirects — supported path, not a
workaround.

| Token | Behavior |
|---|---|
| `{lpurl}` | Final URL. Escaped unless placed at the very start of the template |
| `{lpurl+2}` / `{lpurl+3}` | Double/triple-escaped for 2- or 3-hop chains |
| `{unescapedlpurl}` / `{escapedlpurl}` | Never escaped / escapes `: / ? = %` |
| `{ignore}` | Drops tracking elements from final URL, cuts crawl load. Final-URL only |
| `{campaignid}` `{adgroupid}` `{creative}` `{matchtype}` `{device}` `{keyword}` `{targetid}` | Mapping/segmentation |

Syntax: `{lpurl}` at template start uses literal `?`; anywhere else `%3F` (double-escaped
`%253F`, triple `%25253F`). Tracking-template changes take **24–48h** to propagate — don't judge
a broken chain sooner. Parallel tracking sends the user straight to Final URL while template
fires in background (no latency); RedTrack discourages it unless Google approved it for your setup.

## The mapping contract

Same rule as Meta lane: split is not automatic — campaign name must encode whatever the tracker
needs, tracking template carries it into a tracker parameter. Google-specific: **`{campaignid}`
is the reliable key**, not the name string (names change, IDs don't) — map ID→account/campaign in
the tracker.

## Tracker configuration

### Keitaro
- Maintenance → Integrations → Google Ads → OAuth → Customer ID without hyphens → select campaigns.
- **`{campaignid}` must be in the tracking template** or cost never attributes.
- **Conversions post back only when `gclid` is present — no gclid, no postback, silently.** The
  single most common "missing conversions" cause on Google traffic.
- Cost sync every 12h; conversion postback every 6h — plan the daily routine around these, not Meta's.
- **MCC/manager accounts explicitly unsupported.** Vendor guidance: disable cookie tracking to
  reduce moderation risk.

### RedTrack
- Requires a custom tracking domain via CNAME+SSL — not raw redtrack.io.
- Protected macro roles: `{creative}`→Aid, `{adgroupid}`→Gid, `{campaignid}`→Cid.
- **PMax puts parameters in the Final URL suffix field, not the Tracking template.** All other
  types use the tracking template. YouTube is ad-level only.
- Google's "count one conversion per click" setting breaks GBRAID/WBRAID upload.
- Retries upload every 4h up to 36h. Latency ~24h standard, **~48h for iOS conversions with no
  clickid** — don't judge iOS cohorts on day-one numbers.
- Connected account must be the account running the campaigns — MCC-to-subaccount doesn't work.

🔺 Voluum markets API S2S postback + Automizer cost sync; docs unreachable. Binom has no located
Google-specific traffic-source doc. Verify against current vendor docs before writing operational
steps for either.

## Timezone — the failure mode

`conversion_date_time` must be `yyyy-mm-dd HH:mm:ss+|-HH:mm` (space not `T`, offset mandatory).
Normalize every tracker/network timestamp to one explicit offset before building the payload —
mixing local-server time with offer-network time produces `CONVERSION_PRECEDES_CLICK` and
`EXPIRED_CLICK` partial failures. Reporting tz: same as Meta lane — daily CPL/CPA in ad-account
timezone for both spend and conversions; Google's account timezone is permanent (SKILL rule 4) —
reconcile in the tracker, never by eyeballing.

## Backdate windows

| Path | Max |
|---|---|
| Standard gclid OCI | **90 days** after click — beyond this, silently dropped |
| Enhanced conversions for leads | **63 days** |
| Conversion adjustments | **54 days** from first recording (55 is Hotel Ads only) |

Any funnel with a payout event maturing beyond ~2–3 months can't feed the terminal event back
directly — upload an in-window proxy milestone, true up value with adjustments.

## Dedup

Key = `gclid` + conversion action + conversion date/time. Re-uploading the identical triple is a
no-op. **`order_id` is NOT a dedup key for standard gclid imports** — dedup on it yourself before
sending (differs from what most tracker docs imply).

## Non-negotiables for this lane

- Always set `partial_failure = True`, iterate `partial_failure_error`, reconcile accepted vs
  rejected counts against the tracker export nightly. Rows past the window drop silently.
- Optimize on the payout event, not the front-end lead (frequently 30–70% junk; bidding on it
  teaches Smart Bidding to find more junk). Set front-end action secondary, create a primary
  **Import**-category action fed from the tracker (`google-ads/06`).
- Cross-check tracker conversion count against Google's reported conversions, same window/tz.
  Divergence = wrong metric or broken chain — stop and reconcile, exactly as in the Meta lane.
- A 20–30% variance between Google Ads and GA4 is expected, not evidence of breakage
  (`google-ads/06` enumerates all nine causes).
