# 07 — Geo isolation (billing vs serve vs MCC)

Reviewed 2026-08-27. Identity graph → `01`. Payments → `02`. Gambling MCC cert-kill → `05`.
Lock-in surface: country, currency, timezone, OFAC vs voluntary pause.

## Three different “countries”

| Layer | What it is | If wrong |
|---|---|---|
| **Payments-profile / billing country** | Who pays. Individual AIV: ID **must be issued in this country** (`06`) | Verification fail / pause |
| **Serve / targeting country** | Who sees ads | Policy/cert is **per target geo**. Uncertified geo = violation even with a cert elsewhere (`playbooks/gambling`) |
| **Physical presence at login** | Where the operator sits | OFAC: **cannot sign in** to Google Ads while physically in an embargoed territory, even if the CID is based elsewhere [6163740] |

They do **not** have to be the same. Official dest-not-accessible still requires the LP to work
in the **US** (AdsBot egress) plus targeted geos (`03`).

## OFAC embargo vs voluntary pause

Official Ads country restrictions [6163740], fetched 2026-08-27. Google Ads **isn’t available to advertisers in**:

Crimea (21120) · Cuba (2192) · DNR (21113) · Iran (2364) · LNR (21111) · North Korea (2408).

- MCC **based in** those places: suspended; **managed accounts may also be suspended**.
- Those geos **cannot be targeted**.
- Physical presence there: **cannot sign in**. Help Center still loads.
- No grace period.

**"All countries & territories" does not auto-skip OFAC.** Official: those campaigns "show up
globally without geographic limitations." You **can** exclude embargoed geos — if you don't, you
are targeting them.

**Russia is not on that OFAC list.** Changelog [11940285, 2022-03-03]: Google **temporarily
paused ads from serving to users located in Russia**. Serve-to pause, not advertiser-existence
ban. Sign-up/billing from RU is **not** on 6163740 — don't invent a "foreign entity always works"
rule.

**Syria was removed** from the Ads OFAC list in **August 2025** [16489352, posted 2025-08-13].
Live 6163740 has no Syria. SDN/entity sanctions still exist outside Ads Help — "can target Syria"
≠ every Syrian counterparty is clear.

**Not OFAC (do not cite 6163740):** Nigeria, Pakistan, Belarus, Sudan. Payment/KYC friction is a
different surface (`01`, `02`). Meta's untargetable list is **not** this list (`meta-grey-ops/08`).

## Timezone and currency — locked

Official [1704358 / 17006726]:

- **Serving-account timezone: permanent.** Change = **new CID**. Historical data does not copy.
- **Currency: permanent.** Change = **new CID**. Options depend on registration country.
- **MCC timezone:** Google can reset **once**, **eastward only**, Admin request. After that, never.
- Timezone does **not** change where ads show. Billing page timestamps stay **PST**.
- Default if unset: Pacific.

Grey implication: a reseller seat in the wrong tz/currency is not "settings" — it's a **new
seat**. Copying campaigns into the new CID is the named CS pattern if the old CID was suspended
(`05`).

## Isolation that actually follows from policy

- **One gambling-cert MCC is a cert-kill surface** for siblings (2026-03-23 / 2026-09-14) —
  isolate gambling from everything else, not "one MCC per team."
- **OFAC-based MCC poisons children.** Don't park grey seats under a manager whose billing
  country is embargoed.
- **AIV docs country = payments-profile country.** A US-billed seat with a non-US individual ID
  fails. Org path: authorized-rep ID may be any country; org docs cannot (`06`).
- **Mixing serve-geos in one CID** is allowed. Mixing **uncertified** serve-geos with a
  single-country cert is the named fail (`playbooks/gambling`: one application per country).

No official page says "two geos in one MCC increases review." Don't write that as a rule.
