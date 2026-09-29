# 08 — Surfaces and no-path verticals

Reviewed 2026-08-27. Cloak/Search pin → `05`. App SKAN bits → `playbooks/dating-loans-apps.md`.
Cert taxonomy → `google-ads/09`. Only facts with a live official page.

## App campaigns: cloak does not apply

Official hybrid-apps playbook + ACe deep-link help [16413616]:

- **ACi destination is the Play / App Store listing.** No web Final URL choice. PHP white/money irrelevant.
- **ACe: "Third-party trackers aren't supported."** [16428019]. Change campaign type or remove the tracker. ACi: a 3P tracker must still land on the **correct store**.
- **ACe Final URL must be a non-redirecting App Link / Universal Link.** App Attribution Partner links (Branch, AppsFlyer OneLink) that **redirect** are **not supported** as Final URL [16413616].
- Tracking templates: "most campaign types, **excluding App campaigns**" [7382504].
- **PMax cannot run an app-install goal.** App campaigns remain mandatory for installs (`dating-loans-apps`).

Do not port `05` onto UAC.

## The WebView-app vehicle (grey offers on App campaigns without cloaking)

No-cloak path — moderation sees the Play listing, not the offer [vendor-reported, Partnerkin 2026-03;
not a Google-documented use; Play-policy risk sits on the app side, and ACe tracker restrictions above
still apply]:

1. Android wrapper with a **neutral function** (calculator / feed / casual game) — that function is
   what review evaluates; the Play listing is the destination, so `05`'s destination stack is moot.
2. The Play listing IS the "landing page" for moderation: real screenshots, no aggressive claims,
   ratings grown slowly.
3. The offer renders in an in-app **WebView conditionally** — by GEO, by traffic source, and with a
   delay after install. Conditional display is the load-bearing discipline: content that openly
   violates Play policy kills the developer account, not just the campaign.
4. Conversions via Firebase or tracker postback; budget **50–100 installs** before optimizing on
   in-app events (training volume).
5. **The Play developer account is a separate blast radius** — keep backups; a dev-account ban takes
   the whole app portfolio, independent of any ad account.

Claimed 2–4× funnel lifespan vs cloaked Search [vendor, no methodology]. This does not make App
campaigns a cert path: regulated verticals still need the certification they need (`google-ads/09`).

## Gambling UAC launch (vendor MagicClick 2026, 3P-event lane)

This lane is **not** generic app UA (`dating-loans-apps` tCPI-first). Do not install-opt here.

- Empty CID: dummy App-install campaign → publish → **pause** to unlock 3P app-analytics linking.
  Existing CID: accept 3P analytics and skip dummy.
- Events >6h after share may never land — swap app.
- Optimize **Third-party app analytics** only. `in_app_purchase` = CPA; `sign_up` = CPL. Do **not**
  bid Play default install (budget drain). If the GEO has no organic: Play-install **secondary**,
  `first_open` **primary**.
- Campaign **name is the in-app casino router**. Wrong name submitted → recreate (name caches).
- tCPA from payout $P is a network heuristic — replace with live data. Budget floor they quote:
  2× tCPA (CPA) / 5× (CPL).
- YouTube asset: Not for kids **and** still allow 18+ or reach dies.

## Demand Gen — sensitive inventory

Official Demand Gen help [13695777], fetched 2026-08-27:

- Inventory: YouTube (incl. Shorts), Discover, Gmail, Maps, GDN.
- **Sensitive categories: generally YouTube only; not eligible on Gmail or GDN.**
- Exception in the same paragraph: most sensitive categories **except gambling, alcohol, and political** **may** serve on **Discover** if they do **not** target personalized audiences or predefined Google audiences.
- Next bullet: sensitive campaigns **must exclusively target predefined Google audiences** (Affinity / In-Market).
- Personalized ads [143465]: promoting sensitive → **cannot** use Customer Match, lookalikes, **Custom Segments**, or audience expansion. Custom Intent was **renamed Custom Segments** [9805516] — still live on Display/Gmail/DG/Video; **not** PMax hard targeting.
- Customer Match is **first-party only** [6299717]. Affiliate/bought PII lists are a policy fail. Sensitive products cannot run CM campaigns.

Those two bullets conflict. Operational: don't expect Gmail/GDN for grey/sensitive. Discover is **not** a given. Channel controls are **ad-group** level (`google-ads/12`). Display Ads → Demand Gen migration (Jun 2026) **opts GDN in by default**, cannot unselect during migration [17051545] — a grey Display leftover becomes GDN inventory you didn't pin.

Alcohol: **no product feeds** on Demand Gen.

PMax for grey remains: **don’t** (`05`). Search with pinned Final URL is still the only surface where AdsBot fetches the URL you declared.

## No-path vs cert-path (2026-08-27)

| Offer | Google | Notes |
|---|---|---|
| **Sexually explicit / hardcore / deepfake-porn tools** | **No path.** Egregious, no warning [16490050] | Graphic acts, underage/non-consensual, synthetic explicit |
| **Compensated sexual acts / sugar / escort** | **No path** + strike-track [10922738] | Dating [15328393] |
| **Mail-order spouse** | **No path** | Dating policy |
| **Sexual merchandise, strip, suggestive livestream, partial nudity** | **Restricted, Search only** [6023699] | 7-day warning, not CS. **Cannot** YouTube, Display, Gmail, image, TrueView, **app ads**. Strong-restricted geos include CN, DE, ID, MY, PH, RU, SG, KR, TH, … MENA full sexual-content block |
| **Hookup / fetish / racy livestream dating** | Restricted Dating **cert** | Post-login content is in the cert crawl (`dating-loans-apps`) |
| **Mainstream dating** | General Dating cert | Banned geos on that page |
| **Marijuana / pipes / “legal highs”** | **No path** [16489299] | Recreational drugs. 7-day warning family (not CS) |
| **Topical hemp CBD, THC ≤ 0.3%** | **Allowed** (creams, sprays, lotions, bath bombs, candles) | FDA-approved **pharma CBD**: apply; target **CA, CO, Puerto Rico** only. Retailer: LegitScript + CBD Ads Certification form |
| **Ingestible CBD** | **Not in the allowed examples** | Do not treat gummies/tinctures as the topical carve-out |
| **Canada cannabis (licensed)** | **Search-only pilot** through **2026-12-31** [16851502] | Health Canada / provincial operators only. Not a US path |
| **Weight-loss / nutra claims** | **No cert** | Unreliable claims (`09`) |
| **Credit repair / binary options** | **No path** | |
| **Personal loans US ≥36% APR or term <61 days** | **No path** | Lead-gen in scope |
| **CBD Merchant Center** | Separate from Ads | Do not assume the Ads topical carve-out clears Shopping |

## Quiz / bridge pages

Official Insufficient original content [16427718]: destinations “where the **only purpose is to send users to another site**” — named **bridge / doorway / gateway**. No official “quiz” token. A quiz whose only job is to forward is that clause. White must still be a real site (`05`).

Merchant Center is a **separate** no-path: marijuana on MC [6150004]; **no CBD cert page found** on MC this pass — do not assume the Ads topical CA/CO/PR cert clears Shopping.
