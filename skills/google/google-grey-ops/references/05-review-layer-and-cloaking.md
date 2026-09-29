# 05 — Review layer, cloaking, replacement

Reviewed 2026-08-27. Official destination/tracker mechanics → `03`. Policy taxonomy →
`google-ads/09`. Forensics tracks → `04`. Verification/selfie/BOV → `06`. This file is
the grey overlay: how the review layer is actually filtered, classifier tricks at the
ad/asset layer, and what happens after a burn.

Vendor recipes below are **vendor-reported**, not Google docs. Numbers/"bulletproof" claims have no
published methodology. Policy facts are official.

## What Google named (do not argue with this)

From Circumventing systems [official, answer 15938075]:

- **Cloaking** = "showing different content on your website to different people or to Google
  to try to hide things that might break Google Ads' rules." Egregious: **no warning,
  permanent, cascades**.
- Explicitly **allowed**: language variants, geo-specific offers, slower-connection variants —
  **the promoted product or service must be the same for everyone**.
- Explicitly **allowed**: "Using appropriate click trackers and redirecting users … as long as
  you're not doing these things to try to hide" a policy violation. Redirects are not the crime.
- Named violations: clothing-to-Google / guns-to-users · interstitial blocking Google from the
  destination · bait-and-switch topic · sending users to a **different violating site even on
  the same domain** · click tracker to prohibited content · **dynamic DNS to switch page/ad
  content** after review.
- **After a suspension, creating new accounts to re-enter** is its own named offense.
- **Spreading violating ads across 2+ accounts**, **variations of previously disapproved
  ads/domains/content**, **false verification**, **running uncertified restricted products
  across several accounts** — all named.

**Evasive ad content** (15938074) is a **separate** policy: manipulate text/image/video/domain/
subdomain to bypass detection. **Not egregious — 7-day warning.** Same creative variation can
be charged as CS if Google files it as interference with review. You don't pick the track.

Certified click trackers: `support.google.com/google-ads/answer/13707634` (fetched
2026-08-27). Certification is a **Tracking Template** rule (9481382), not a Final-URL
rule. Window: 1 Sep–30 Nov annually. Nested hops must **all** be certified.
Out of scope: DV360, Shopping/Hotel, YouTube Reservation. App **engagement**:
third-party trackers not supported.

**Keitaro, Binom, RedTrack, Voluum, FunnelFlux, Adspect are not on that list.** CPV
Lab / CPV One / Trackdesk / Trackier / Affise / Everflow are. Error codes:

| Where the uncertified host sits | Disapproval |
|---|---|
| Tracking template | `Click Tracker - Unsupported` |
| Nested hop template → Final URL | `Click Tracker - Destination Mismatch` |
| Missing transparency param | `Parameter Needed` |
| Uncertified domain as **Final URL** | Destination mismatch / cross-domain — **not** the cert program |

Custom tracking domain on the same registrable domain as the lander: mechanics → `03` (certified
trackers).

## AdsBot is not Facebook’s reviewer

| Fact | Source |
|---|---|
| Desktop quality crawler UA | `AdsBot-Google (+http://www.google.com/adsbot.html)` — **not** a Chrome UA |
| Mobile quality crawler UA | Nexus-5X Chrome template + `(compatible; AdsBot-Google-Mobile; +http://www.google.com/mobile/adsbot.html)`. `Chrome/W.X.Y.Z` is an **evergreen placeholder** — match with wildcards |
| AdSense crawler (different product) | `Mediapartners-Google` — do not treat as Ads LP review |
| `Google-Safety` | Malware / publicly-posted-link abuse crawler. **Ignores robots.txt entirely** |
| `Google-Ads-Quality` | **Not** in official crawler lists (2026-08-27). Do not filter on it |
| Retired | iPhone AdsBot-Google-Mobile UA · `AdsBot-Google-Mobile-Apps` |
| `*` in robots.txt | **Ignored** by AdsBot. Only `User-agent: AdsBot-Google` / `AdsBot-Google-Mobile` apply |
| Token spelling | Crawler docs: `AdsBot-Google`. Help 16428223 writes `GoogleAdsBot`. **Use the crawler-docs token** |
| IP range | `special-crawlers.json` — **not** `googlebot.json` / `common-crawlers.json`. Same ASN **AS15169**, different prefixes. rDNS: `rate-limited-proxy-***-***-***-***.google.com` |
| Googlebot rDNS | `crawl-*.googlebot.com` / `geo-crawl-*.geo.googlebot.com` — **do not** treat as AdsBot |
| AS396982 | Google Cloud **customer** workloads, not Googlebot |
| UA spoof | Official caution. Verify: reverse DNS → forward DNS → IP in the JSON |
| Egress geo | Crawlers egress **primarily from US IPs**. Geo-blocking the US = Destination not accessible |
| HTTP error to AdsBot | Destination-requirements (Track B, 7-day) **and** the review never sees the page. 429 from a WAF is the same class |
| What is fetched | **Final URL**. Tracking template / expanded URL must “lead to the same content” (`03`) |
| `<10` redirects | DSA troubleshooting 9229701. Click trackers can also exhaust crawl capacity |
| `<meta name="AdsBot-Google" content="noindex">` | Named as a Destination-not-crawlable cause. Do not set it on the white |

Desktop AdsBot's UA is a short non-browser string. Mobile AdsBot **is** Chrome-shaped.
**UA-only filters catch the desktop crawler and miss a lot else.** Human policy specialists on
residential IPs — vendor claim, no Google confirmation. Treat UA-only as a first sieve, never
the stack.

**GGC is not AdsBot.** Google Global Cache is an **ISP-hosted inbound CDN** (mostly YouTube).
Official: `redirector.googlevideo.com/report_mapping`, rDNS `rN---sn-….googlevideo.com`, ASN
**AS36040** (ARIN: YOUTUBE / "Google (Global Cache)"), WHOIS `GOOGLE-GLOBAL-CACHE` on **the ISP's
prefixes** — not AS15169. No official GGC IP JSON (`goog.json` is Google-operated space, not
ISP-hosted cache). Cloaker pitch "whitelist GGC = whitelist reviewers" is a **category error**:
GGC IPs are users fetching YouTube inside an ISP, not crawler egress — misclassifies real
YouTube/Display viewers on those ISPs. AdsBot remains `special-crawlers.json` + US egress.

JS rendering: Google Search's WRS executes JS (evergreen Chromium; non-200 may skip render).
AdsBot's own JS-execution is **not** documented on the AdsBot page. Vendors/SEO shops 2025–26
treat Chrome-class review as live (hence JS challenges + IP/ASN, not JS-hide-the-DOM). Don't bet
an account on "AdsBot cannot run JavaScript" in 2026.

**Do not 403/429 AdsBot and do not `Disallow` it in robots.txt.** Crawler infra says special-case
crawlers *may ignore* robots.txt; Ads policy still disapproves the block — blocking AdsBot is a
destination fail even if the crawler still hits you.

## How review is actually layered

Not one crawler, not one pass:

1. **Pre-serve editorial / Gemini.** End-2025 Ads Safety Report: majority of **RSAs
   reviewed instantly at submission**. This is copy/keyword/asset, not the LP.
2. **AdsBot destination crawl** of the Final URL. Separate layer. Shows up as
   **approval → mass disapproval ~24h later** (`04`). No official recrawl SLA.
3. **Ongoing re-review.** Official: continuous. A **minor edit to ad text or Final URL
   forces a new crawl**. Tracking-template change at **ad / keyword / sitelink**
   auto-reviews; change at **ad group / campaign / account** needs an appeal.
4. **Human specialists** on Dispute / complex cases. **No official human-reviewer UA
   or IP class.** Vendor “residential proxy reviewers” is unverified. A human who
   **clicked the live ad has `gclid`** and looks like a user — that is why gclid-only
   is a leak.
5. **UI “Test landing page”** is URL-resolution only. Official: **does not check
   policy**, **does not support redirects including JS**. Green test ≠ policy pass.
6. **Editor policy colors** (red/yellow/green) “don’t flag all editorial violations.”
   Policy Manager is an **appeal tracker**, not a crawler.

App campaigns: destination is the **store listing**. `AdsBot-Google-Mobile-Apps` is retired;
store-policy violations are a Destination-requirements subtype — fix Play/Chrome Web Store
first. ACe: third-party trackers not supported.

PMax/Demand Gen/YouTube share destination policy. PMax **Final URL expansion** crawls **other
pages on the same domain**, auto-generates assets. YouTube LAS is a **serving throttle**, not a
different crawler. **Do not cloak PMax.** Search with a pinned Final URL is the only surface
where the review fetch is the URL you declared.

Display/GDN/app-webview clicks often have **no `google.com` referrer**. A Search-only
referrer-whitelist (`google\\.com`) whites a lot of real Display users. Split recipes by
campaign type.

## Filter stack for Google (layers, in order)

Facebook's cheap trick (empty `{{ad.name}}` until macros fire) does not port. Google always has
a click-id on a **real paid click** (`gclid` / `wbraid` / `gbraid`). Build **AND** across layers
— one layer failing is a leak.

Architecture first. Filters are worthless on a cross-domain 302.

0. **Same-registrable-domain, zero-redirect PHP** for the review fetch. Tracker as
   `trk.example.com` if a 302 is required. **Do not put a raw Keitaro/RedTrack/Binom
   host in Final URL.**
1. **Official crawler identity** — UA ∈ AdsBot / AdsBot-Mobile / Googlebot /
   Google-InspectionTool / Google-Safety / Mediapartners-Google **and** IP ∈
   `special-crawlers.json` **and** rDNS `rate-limited-proxy-*.google.com`. Serve
   white **200**. Never 403 these.
2. **ASN / ISP** — AS15169, AS396982 (GCP **customers**, not Googlebot), AS36040
   (YouTube/GGC — **users**, not AdsBot), AS19527, plus AWS/Azure/DO/Hetzner/OVH
   as datacenter. Keitaro has **ISP, not a first-class ASN filter** (official
   filter page 2026-07). Matching ISP name “Google” is the stock path. A
   datacenter-only blocklist is the 2019 cloak; it is not GGC-as-reviewer. Do
   not allowlist AS36040/`sn-*.googlevideo.com` as AdsBot.
3. **IPv6** — Keitaro legacy cloak notes: Google/Meta hold large IPv6 space. Real
   users also use IPv6. High false-positive leftover. Optional, not load-bearing.
4. **Datacenter / hosting / antivirus / brand-safety** — VirusTotal / Safe Browsing /
   Confiant / GeoEdge class. Keitaro Bot filter is **generic**, not Google-specific
   — forced white, then add ISP/UA.
5. **Click-shaped vs crawl-shaped** — money AND: `gclid` (or `gbraid`/`wbraid`)
   present, geo ∈ targeting, `Accept-Language` ∈ targeting, device ∈ targeting.
   AdsBot quality crawl of the Final URL typically has **no gclid**. **Soft gate:**
   a human reviewer who clicked the live ad **has gclid**. Do not use this alone.
6. **Referrer** — AdsBot often empty. Search users usually `google.com` /
   `googleadservices`. Empty-referrer → white is correct for crawls and wrong for
   some Display/app/webview. Search-only: whitelist `google\\.com`. Display: do not.
7. **Headless / JS / TLS fingerprint** — **second stage only**, after 0–6. Adspect
   JS FP + VLA; Binom ADVANCED JS. Primary JS cloak = AdsBot-Mobile/WRS executes it
   and sees money. Binom JS methods insert a **local redirect** (extra hop, extra
   signature). Binom TLS/TCP/VPN **break behind Cloudflare**. Adspect claims
   Cloudflare proxy is supported for IP hiding.
8. **First-N / review mode** — submit with cloak **off**. Adspect On Review +
   “blacklist all IPs in Review”; delayed-start first N clicks white. Binom FIRST.
   Keitaro: watch click log, then turn filters on. **Do not click your own On-Review
   link** — that IP is then blacklisted and your own tests lie.

**Do not enable the cloak on day 0.** Adspect warmup 7–14 days on white, low budget:
🔺 vendor ritual, not a Google SLA. Then enable filtering on the **same URL**.
Post-approval Final-URL or DNS swap is how static cloaking dies on recrawl.

## Keitaro — Google recipe

Keitaro documents cloaking as a **forced** stream (always evaluated first). This is
the **2022 CIS default**. Treat as **layer-1, insufficient alone in 2026** without
§0 and official-crawler IP/UA (not a GGC allowlist).

```text
Forced (white), OR:
  Bot IS
  Empty referrer IS
  Proxy IS
  UserAgent regex /AdsBot-Google|Googlebot|Google-Safety|Google-InspectionTool|Mediapartners-Google|HeadlessChrome/
  Parameter gclid IS @empty
  Country IS NOT {buy geo}
  Language IS NOT {buy lang}
  ISP IS {Google, Google LLC, Google Cloud, Amazon, Microsoft, DigitalOcean, Hetzner, …}
  (optional, leftover) IPv6 IS

Regular (money), AND:
  Bot IS NOT
  Parameter gclid IS NOT @empty
  Country IS {buy geo}
  Language IS {buy lang}
  Device type IS {targeted}

Default: WHITE (fail-closed)
White scheme: CURL / Show HTML / KClient Do-nothing  (200, same host)
Money: local lander / same-domain path, offer behind a button
```

- Update **Maintenance → Geo-DBs / Bots** on a cadence. Stale bot DB is a silent leak.
- **Settings → Enable tracking cookies = No.** Unique-by-cookie is a moderation tell (`03`).
- CURL/Show HTML keeps the response on **your** host — no extra hop for AdsBot.
- Money page via 302 to an **external** offer is the leak Google named. Prefer: white +
  prelander on the **same registered domain** (path or subdomain), offer behind a button
  **after** the first 200 — that button-click is a user action AdsBot doesn't have to take.
- Test: UA switcher (Keitaro's own doc) **and** datacenter VPS **and** residential IP in-geo
  with a real `gclid=` query. Same page on both = stack not filtering. Self-click of the live
  ad = human-reviewer analogue (gclid present).

Keitaro Google integration is **cost + conversion sync**, not a cloak. MCC unsupported.
Conversions only if `gclid` present.

## Dedicated cloaker (Adspect class) — Google recipes

Two official vendor paths [docs.adspect.ai, fetched 2026-08-27]:

**Search / GDN (zero-redirect):**

1. Stream use-case = Google Ads.
2. Money page = **local file**, long random filename, **zero redirect**. If the offer
   is external, a **local prelander with a button** is mandatory — “the money page
   configured in Adspect must be displayed without redirect.”
3. Reverse-PHP integration on the **white**. Safe action = No Action.
4. **Strip the integration** (`require`) before submission so review sees only the
   white.
5. Submit the **white URL** as Final URL.
6. Warm 7–14 days on the white, low budget. 🔺 Vendor number, not a Google SLA.
7. Re-insert the integration, switch stream to **Filtering**. Level **High** (vendor
   default advice). Medium+ queries **12 competing cloakers** + VLA.
8. URL rule: `gclid` **does not exist** → block (white). ASN blacklist:
   `AS15169 AS396982 AS19527`. **Do not** blacklist AS36040 as AdsBot — that is
   YouTube/GGC **users**. Referrer: blacklist `^$` or Search-only whitelist
   `google\\.com`.

**Tracking-template path:**

1. Use-case = Google Ads (Tracking Template).
2. Both actions = HTTP 302.
3. Forward PHP.
4. Tracking template carries `url={lpurl}` (see `03` for escaping).

Vendor hard rules that match Google’s destination text:

- PHP integration on Google: **safe page without redirect**. 302-the-white is the FB-portable
  mistake.
- **Iframe = considered a redirect** by many networks. Don't iframe the money page.
- Never reuse domain/creative/white in the same traffic source unmodified.
- Filters (country, OS, browser, language) **match campaign targeting**.
- White must look like a real site: unique, mobile, terms/privacy/cookies, `robots.txt` +
  `sitemap.xml`, no Wix/Tilda/Shopify constructors (vendor: networks now pre-ban those).
- Don't change a live white (extra `<script>` can re-trigger review).
- One stream per campaign (vendor won't inspect mixed traffic after a ban).
- `.com`/`.net`/`.org`; no stop-words in the domain (`diet`, `date`, `xxx`, …).

Domain pre-flight, per NEW domain before any seat touches it (log the result with the seat — an
unlogged pre-flight cannot explain a wave later): Safe Browsing status
(`transparencyreport.google.com/safe-browsing/search` — a flag is a **cross-product** kill, `04`) ·
VirusTotal domain report (any relevant engine flagging → drop) · Wayback history (prior grey use =
pre-burned) · WHOIS age + registrant (fresh registration ties into `01`'s linking signals; keep one
registrar pattern per persona, not per domain).
- Cloudflare in front; no `index.html` sitting next to `index.php`.
- High spend + many campaigns on one account = “stands out” → human review that no
  cloak survives. That is the real ceiling, not the filter DB.

JS-only cloaks and “safe page = redirect to google.com” are how accounts die in the
first 24h, not how they scale.

## Tracker-native filters are not the cloak

| Tool | What the vendor actually documents | Use as Google cloak? |
|---|---|---|
| **Adspect PHP reverse** | Written Google SOP, GGC claim, TLS, JS FP as second stage | Engine. Tracker sits **behind** it |
| **Keitaro** Forced+Bot+CURL | Generic bot DB; ISP not ASN; Google integration = cost/sync | Layer-1 backup, not the cloak |
| **Binom Protect** | Server ~1–3ms (APP/BOT/CORP/CRAWL/DC/FAKE/FB/FIRST/RATE/TLS/TCP/VPN). JS methods add a **local redirect**. FIRST = first N clicks white. No Google-specific Protect recipe; tracker mechanics + GSB cadence → `03` | FB-shaped. Usable as extra DC/VPN net, not Google SOP |
| **RedTrack** funnel filters | Quote: filtering “won’t be useful for campaigns with such traffic sources as Google Ads, Facebook…” because it needs **redirect** tracking | **Do not.** Measurement only |
| **FunnelFlux** | Same-domain workaround: lander `example.com`, tracker `trk.example.com` → TEST green. Fluxify serves lander HTML **under the tracker URL**. Direct-to-offer: condition on UA matching Google bot so TEST returns the same URL as Final URL. Observed TEST UA contained `google-adwords` | Same-domain 302 / Fluxify only |
| **Voluum** Anti-Fraud Kit | Datacenter / fast-click / bad-UA metrics; known bots **enter the funnel**. No Google cloak playbook | Anti-fraud, not cloak |
| **HideClick** | Practitioner (CIS, 2025-05, n=1): Google cloaking policy in **2–3h** | Dead for Google on that report |
| **Cloaking Master / CloackMaster** | Marketing pages; Google as paid add-on; no public filter schema comparable to Adspect | Insufficient docs |
| **ClearTrust / ClearClick** | ClearTrust is a **certified click tracker** (Botman). ClearClick is NoScript anti-clickjacking. Neither is a cloaker | Do not confuse |

## White page that actually passes destination review

AdsBot is checking a **destination**, not a screenshot of an ad. Minimum mapping onto official
destination + misrepresentation language:

- 200 OK on AdsBot desktop **and** mobile, **including from US IPs** even if you buy EU/ASIA. Do
  not geo-block US.
- `robots.txt` **Allow** `AdsBot-Google` and `AdsBot-Google-Mobile`. They ignore `*`.
- Same registrable domain as Display URL / Final URL.
- Company name, physical address, contact — prominent. A fake NAP contradicting verification
  docs is a **verification** landmine, not a destination checkbox.
- Working nav, original text, no "page solely designed to send users elsewhere."
- Pricing/offer on the white **matches the ad**. Clothing-ad / gun-site is the example Google
  wrote down.
- No interstitial in front of the content. Works **without user interaction** (Googlebot WRS
  doesn't click/scroll).
- HTTPS, no AdsBot-specific error, no `AdsBot-Google` noindex meta.
- `<10` hops on the review path.

Vendor extras **not** in Destination Requirements but treated as load-bearing: privacy/ToS/
cookies (also EU cookie law), sitemap.xml, no Shopify/Wix/Tilda (vendor High), Core Web Vitals
(QS folklore — unverified as cloak-survival).

The white is a **real site**, not an empty HTML file. Empty whites pass a UA check, fail a human
re-review. **Insufficient original content** (doorways, scraped, templates) kills a white even if
the cloak "works."

Do not optimize Quality Score via the cloak. QS is landing-page experience of **what users and
crawlers see** — if they diverge, QS on white is real until the cloak is pierced, then the
account is dead.

## Same-domain constraint

```text
OK:     example.com/           white (AdsBot, no gclid)
        example.com/a/         prelander (gclid present, in-geo)
        example.com/go         button → offer  (user click)
        trk.example.com        tracker 302 → example.com/a   (same registrable)

NOT OK: Final URL example.com  → 302 tracker.io  →  offer-network.com
        (cross-domain off the Final URL is named)

NOT OK: example.com white for AdsBot, example.com/offer guns for users
        (same-domain content split is still cloaking if the product differs)

NOT OK: subdomain “not clearly distinguishing” vs parent
        (blogspot.com vs mycompany.blogspot.com is Google’s own mismatch example)
```

ValueTrack through a tracker is the **supported** measurement path (`03`). The
tracker hop must still satisfy “same content as the final URL” for the **review
fetch**. That is why zero-redirect whites exist: AdsBot never leaves your host.

Parallel tracking (mandatory Search/Shopping/Display/Video/PMax) sends the **user**
to Final URL while the template fires in the background. That is click serving, not
the crawler’s documented fetch. Content review is Final URL.

## What actually dies (ban list)

1. **Content substitution** — different product to Google vs users. CS, no warning,
   linked accounts.
2. **JS-primary cloak** — AdsBot-Mobile/WRS runs the script, sees money. Hours
   (HideClick n=1) to ~24h.
3. **Cross-domain Final URL / uncertified tracker hop** — Destination mismatch.
4. **Post-approval Final URL or DNS swap** — recrawl. Adspect SOP: **do not change
   the URL**; toggle the PHP include.
5. **403 / 429 / robots Disallow AdsBot** — Destination not working / not crawlable.
   Desktop AdsBot UA is **not** Chrome-like; Cloudflare Bot Fight / “non-browser
   10 rpm” returns 429 (Adelaide Socials 2025-09, 3 days dark). 2026-07-01:
   Cloudflare **verified bots are no longer default-allow** — category policy
   applies. Allow the Advertising & Marketing verified-bot category for AdsBot.
6. **White is a doorway or constructor template** — Insufficient original content,
   even if filters “work.”
7. **Standing out** — high volume, many campaigns, no tracker macros. Manual review
   pierces any cloak.
8. **False advertiser verification** — separate egregious clause.
9. **Safe Browsing** on money or a linked download — domain-level, Search + Ads.
   `Google-Safety` ignores robots.txt.
10. **PMax + cloak** — URL expansion sends AdsBot to a path you did not pin.

## Replacement after a burn

Official: creating a new account **to re-enter after a suspension** is Circumventing systems.
Linked payment **and** email accounts, plus Merchant Center, are named cascade surfaces. Billing
FAQ is more absolute than the policy-overview "may": related accounts using **same email or
payment method, or linked to the same MCC, will be suspended; any new accounts will be
suspended**.

Identity-document graph is official: if this CID was suspended because **other accounts verified
with the same docs** were suspended, reinstating those others auto-reinstates this one. Reverse:
don't verify a grey seat with docs already on a burned CID.

Google does **not** publish GAIA/GTM/fingerprint/IP/phone as Ads CS detectors. Practitioner
consensus still uniques those. Naming them as *official* Ads link keys is an overclaim.

| Move | What it actually is |
|---|---|
| New Gmail + new card + new ads.google.com signup from the **same** persona after *your* ban | The named offense. Do not |
| Reseller swaps you onto a **different seat** in **their** MCC, new billing on **their** invoice | Their product. Not your GAIA re-entering. Cascade risk remains if you reuse **GTM, domain, payment profile, phone, Search Console**. Unique those four or the new seat inherits the old graph |
| Invoiced agency billing (no buyer card in Google Payments) | Hides the **buyer PAN**. Does **not** hide MCC, email, identity docs, domain, BM/MC. Sequential liability **re-attaches** an advertiser payments profile. Unlink of a **paying** invoiced manager **stops serving** until the next billing setup |
| Frozen CID (cannot edit ads) | Official `adspolicy/answer/14899401`; allowed-actions list and StubGroup dates are canonical in `04`. Appeal must describe **future** fixes |
| Appeal Circumventing systems | Compelling circumstances official gloss: **“such as in the case of a mistake.”** Self-audit first (`google-ads/09`). If the cloak is still live at re-review, the appeal is **evidence**. Previously linked accounts still count. Too many appeals → 7-day processing freeze |
| Limited Ad Serving | **Not a ban.** Keep the account, fix, dedicated LAS form. Aug 2026: LAS covers **all Ads**, phased through **2028**. Replacing an LAS account wastes a seat |
| Unique RSA + unique Final URL per account at launch | Hygiene against a **named** CS pattern (“variations of previously disapproved content”), not a proven detector-bypass. Cloning one violating RSA via Editor across CIDs **is** the named offense. Meta `image_hash` uniquely IDs a file **inside an ad account** (API `copy_from`). **Identical bytes as a cross-CID Ads/Meta enforcement linker remains unverified** — do not treat hash uniquify as a documented graph break |
| MCC in third-party violation | Child accounts **paused** while linked (2025-06-06). **Unlink** to serve again. Isolation lever, not a cloak |
| Gambling buyer in a mixed MCC | From 2026-03-23: MCC with significant revoked gambling certs / violating cert-using children **loses new gambling-cert applications** and existing certs revoked. Shared MCC is a **cert-kill** surface. Expand 2026-09-14 |

Self-farmed re-entry from a burned payments profile is how one dead account becomes a dead MCC.
Reseller replacement is survivable only if the **identity graph is actually new**. Ask: whose
MCC, whose invoice, whose GTM, whose domain.

"Unbannable agency accounts" is a vendor lie. Real SLA is **replacement + leftover handling**.
Vendor-stated, no methodology: YeezyPay hours + **~30%** leftover; Uproas free ~3–24h (whitehat
Google); SpeedX transfers leftover, **1 domain per CID**, new CID needs a new domain; Mega Digital
refunds unspent 5–20d **no published haircut**; Threasury does **not** promise CS replacement.

**Closest operator SOP with numbers — Mega Digital TOS (2025-09-24), vendor rule
not Google’s threshold:** unique destination URL including **undeleted history on
other CIDs**; **>90% URL similarity** treated as associated; **1 email ≤ 3 accounts**;
**1 CID : 1 URL : 1 email**; ≥3h wait after pause/suspend before a new seat. SpeedX
same: one domain per account. Destination URL/domain reuse is the seat-swap killer
Google actually named (CS: variations of ads/domains/content).

Same-BIN auto-kill of the next CID: Traffic Ultras 2026-03, **no independent log**.
Do not repeat 85–90% vs <30% appeal rates as fact.

GTM / GA4 / Search Console / conversion-action IDs / developer token are **not**
on any live Ads policy page as CS edges. Reusing an old `AW-XXXXXXXXX` from a
burned CID is a telemetry ping to the dead account — stupid, not a published
linker. Developer token is MCC-tied; GCP project permanently paired
(`DEVELOPER_TOKEN_PROHIBITED`) — burns automation, not proven as a CID linker.

PMax for grey: extra crawl + auto assets + YouTube/Discover already under LAS +
Merchant Center cascade on Shopping. Default: **Search-only with locked Final URL**
until the destination survives AdsBot. Demand Gen / App / adult-CBD no-path → `08`.
Do not cloak UAC. Sensitive DG is generally **YouTube-only** (not Gmail/GDN).

## Creative-classifier tricks (unicode, RSA, path, format)

Two tracks, one payload. Unicode / misspell / clone is **Evasive ad content
(15938074, 7-day)** *or* **Circumventing systems** if Google files it as variations
of previously disapproved ads / obfuscated sexual content / abuse of product
features. You do not pick the track. US 15938074 is stripped of examples;
localized AU + parent 6020954 archive still name **invisible UNICODE**, misspell
of prohibited words, hiding violations in image/video.

**RSA is pre-serve.** End-2025: majority of RSAs reviewed **instantly at
submission** (Gemini). Combination-dilution and “hide it in H15/D4” are dead on
Search text — **each asset is reviewed independently**. Pinning is SERP control,
not a classifier skip. Sensitive verticals are excluded from RSA-headline-as-sitelink
sharing.

| Trick | Mechanic | 2026 status |
|---|---|---|
| Invisible ZW / bidi / ZWSP | Hide tokens from string match | **Named, dead as a plan** (Editorial spacing + EAC) |
| Homoglyph **digits** (Cherokee/Osage/Bengali) | Evade brand/phone filters | **LIVE** Feb 2026 forensic (Emirates/Lufthansa support ads). n=small |
| Cyrillic–Latin mix in RSA headlines | Policy-word hide | **Unverified live.** Assume Gemini catches policy tokens |
| Decorative `【】❱‣™` | Aged-CID garnish | **Still passing on aged accounts** (May 2026). New CIDs unpredictable. Crackdown was on claims *inside* the brackets |
| Punycode IDN Display URL | Homograph domain | Not re-confirmed 2025–26 on Search RSA |
| `sites.google.com` Display URL | Same-registrable-domain impersonation | **LIVE** Jan 2025 (Malwarebytes). Mismatch checks **domain**, not product |
| Bid restricted, copy clean | Keyword classifier ≠ copy | **Still the architecture.** Rx US/CA/NZ (Oct 2025): terms **OK in ads+LP without cert; cert required to keyword-target.** Gambling: keyword list is the cert gate. Dirty **query** still hits AdsBot later |
| Bid clean, copy dirty | Inverse | **Dead on Search.** Instant Gemini at submit |
| DKI as injector | `{KeyWord:}` pulls the query into H/D/path | Healthcare + Sexual: **feature-blocked**. Restricted TMs: **will not insert**. DKI in TLD/2LD of Display URL = Destination mismatch. **Allowed in path fields** |
| DSA / AI Max / ACA auto-assets | Headlines from LP + domain + current ads | Advertiser **liable**. Auto-assets can scrape a violating LP claim into an RSA Google then disapproves. ACA → AI Max Sep 2026. DSA delayed Feb 2027. Grey: **do not enable** URL expansion / auto-assets |
| Path fields (`example.com/Free-Trial`) | 2×15; **need not match** Final URL path; not a live URL | **Structurally open.** Instant RSA + dishonest-pricing (Oct 2025: free trial without period/auto-charge) make claim words in path as hot as headlines |
| Language targeting laundering | Cert-light language, serve another geo | **Dies Sep 2026 on Search / PMax Search inventory.** Ads match **ad language**. Other PMax channels keep the setting. Cloaking carve-out: language/geo variants OK **iff the product is the same** |
| Call-only as LP skip | No Final URL | **Dying.** No new ads Feb 2026; impressions stop **Feb 2027**. Replacement RSA + call assets → **Final URL required** |
| Lead forms / message assets | Native capture | **Do not skip** destination policy. Lead form: Final URL + privacy URL still reviewed. Message assets: verification URL **same domain as Display URL** (Oct 2025) |
| Display/GDN baked-in image text | OCR skip | **Still serving** Mar 2026 community. Search/PMax image assets are stricter (overlay limits Jul 2026). Shopping overlay lag ≠ permission |
| YouTube: clean first seconds / thumbnail mismatch | Review window folklore | **No official “first N seconds.”** Thumbnail + title + tags are in advertiser-friendly scope. ASR 2025: Gemini on digital assets in milliseconds |
| Demand Gen / Gmail / Shopping as weaker copy | Format shopping | **Tentative rank:** Display image ≥ YT skippable > DG carousel > Search RSA > Shopping titles > PMax. Instant review **expanding to more formats in 2026**. Gambling **restricted** in Gmail/Shopping/reservation. DG sensitive: often YouTube-only, barred Gmail+GDN (Jun 2026). Masthead Sep 2026: gambling = sports betting + DFS US/CA only |
| `custom_label` stuffing | Hide claim in feed | **Not user-facing, not a review bypass.** Products still classified off title/description/image/LP |
| Editor unicode-delta of a disapproved RSA | Clone until one lands | **Named CS example.** Editorial-only clones (`!`, Title Case) are **not** CS. Instant Gemini now catches many at paste-time — iterating deltas until one lands **is** the CS pattern |
| GBP overlay sideload | Re-upload overlay-disapproved assets via Business Profile | 2025-01 single-source. Treat **stale** unless re-verified |

**Operator translation (asset layer only):** Search RSA is a pre-serve Gemini wall.
Remaining open surfaces: (1) official keyword-vs-copy splits, (2) path/sitelink/
callout as secondary text — still reviewed, combinatorially less visible,
(3) Display/Shopping image lag, (4) format-shopping away from Search text into
YouTube/DG with sensitive-category traps, (5) auto-assets generating the claim
**for you** — liability stays on the CID. Unicode-delta clones of disapproved
RSAs are the sentence CS was written to catch.

Verification / selfie / BOV → `06`.

## Failure signatures (read with `04`)

| Signature | Likely cause | Move |
|---|---|---|
| Instant disapproval | Copy/keyword, Gemini pre-serve — not the cloak | Edit ad, 24–48h re-review |
| Approved, then mass-disapprove ~24h | AdsBot saw a different destination than the creative pass | Domain-scoped → that domain. Account-wide → identity, not LP |
| Circumventing systems on first charge | Payment graph + cloak in the same window | Freeze. Do not swap cards from the same session |
| Cloaking policy in hours | JS-only / UA-only cloud cloak (HideClick-class) | Stack is pierced. Do not re-upload the same URL |
| Destination not crawlable / not working | robots.txt, WAF 429, `<meta AdsBot-Google noindex>`, AdsBot 403 | Allow AdsBot, 200 the white, fix WAF |
| Safe Browsing on the domain | Malware/unwanted-software, **cross-product** | Rotate domain; do not reuse it on the next seat |
| Bot share in tracker spikes | Filter is working **or** review is hammering the white | Watch for the 24h disapproval wave before scaling |
| LAS, ads still serving thin | Track C | Stay. Do not “replace” |
| MCC-wide pause, this CID otherwise clean | Manager on third-party violation | Unlink. Do not self-farm |

## Gaps

- No official AdsBot JS-execution spec. Stack assumes Chrome-class review exists.
- No official GGC IP list. GGC ≠ AdsBot (architecture confirmed). Vendor “GGC
  reviewer” lists remain a category error.
- Human-reviewer residential UA/IP: vendor assertion, not a Google page.
- Warm-up 7–14 days: Adspect, not a Google hold period.
- Whether invoiced agency MCC severs the buyer’s payment-identity graph: vendors
  say yes; Google does not.
- PAN/BIN independent burn after CS: practitioner-only.
- BHW / afflift Google cloak threads: HTTP 403 / paywall this pass — not “doesn’t
  exist.”
- Cloakist: not found. ClearClick-as-cloaker: not found.
- Replacement for retired `AdsBot-Google-Mobile-Apps`: not documented.
