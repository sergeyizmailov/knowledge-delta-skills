# 07 — Review layer, cloaking, creative-classifier tricks

Reviewed 2026-09-09. Session/IP → `01`. Agency/BM → `03`. API launch / re-moderation
→ `04`. Policy taxonomy (clean lane) → `meta-ads/07`. Grey overlay: how Meta's
review fetch is filtered, which creative/format tricks still move the classifier.

Vendor recipes = **vendor-reported**. Policy facts = official. Live Circumventing
Systems page redirects to Account Integrity this pass — cloaking still named in
Meta's 2026-02-26 lawsuit.

## What Meta named (official, live-fetched 2026-08-27)

- Ad product/service **must match landing page**. Helping anyone **evade/circumvent
  enforcement** is prohibited. Restriction grounds include evading review.
- 2024 Circumventing Systems (URL now redirects, Loomer-quoted): named **cloaking**
  (limiting Meta's destination access), **unicode/symbol obfuscation**, **obscure
  images**. Evading Enforcement: don't recreate violating ads across assets; don't
  spin new assets after restriction.
- 2026-02-26 newsroom: cloaking = "webpage shows one version to ad review, different
  content to real users." AI cloaking detection; faster reject on redirect chains.
- **Display URL must match Website URL's domain.** 🔺 "~25 char truncation" figure
  has no official source — likely conflated with Link Description (30-char cap,
  Marketplace/search/AN only). Measure in preview, don't design to 25. [unverified]
- Mar 2026: single-media + A+ catalog collection ads on FB Feed **no longer show
  footer URL** — mismatch less visible, not less enforced.
- **Domain block**: restricted/suspicious LP domain → all ads to it rejected, 60-day
  block, repeats if linked accounts keep violating. Fix = **change domain**, never
  appeal the domain.

## Crawlers (official page, `developers.facebook.com/docs/sharing/webmasters/crawler/`)

| UA | Job | Ad review? |
|---|---|---|
| `facebookexternalhit/1.1` | OG link-preview | Not stated |
| `meta-externalads/1.1` | ad/business products | Closest named; not labeled "review" |
| `meta-externalagent/1.1` | AI training/indexing | No |
| `meta-externalfetcher/1.1` | user-requested; may bypass robots.txt | No |
| `meta-webindexer/1.1` | Meta AI search | No |

Retired/unlisted (not on current page): `Facebot`, `FacebookBot`, IG crawler,
`facebookcatalog/1.0`.

`facebookexternalhit`: gzip+deflate, OG in first 1MB, `Range: bytes=0-524288`,
crawls in seconds, may ignore robots.txt for malware/integrity checks. Simulate:
`curl -v --compressed -H "Range: bytes=0-524288" -H "Connection: close" -A
"facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)" "$URL"`.
IP check: `whois -h whois.radb.net -- '-i origin AS32934'` + AS63293; IPv6
`2a03:2880::/32`; 2026 logs add **57.141.0.0/24**.

WhatsApp preview UA = link-preview, not ad review. **JS execution by ad review:
undocumented** — `facebookexternalhit` is a static scrape but vendors assume a
second Chrome-class/residential path exists. Don't bet on "review can't run JS."

## Review layering (order)

1. Automated pre-serve on create/edit, "In review" ~24h (often minutes). Ad **may
   deliver before all policy checks finish**.
2. Destination fetch of Website URL + redirect path (official: LP is reviewed; no
   published fetcher UA for this step).
3. Re-review any time, including post-live.
4. Re-review triggers (official): targeting, creative, optimization, billing event.
   Field test (`04`, 2026-08, 45 ad sets): geo/device/age/placement/budget/bid/
   schedule did **not** change status — review attaches to the **creative**. Treat
   official as "can" trigger, field as what "usually" does.
5. **Click-to-Messenger**: thread-level checkpoint on top of ad review — welcome
   message reviewed instead of a web LP. Second gate, not a skip.
6. **Instant Experience**: Meta-hosted, button URLs still crawlable. Jun 2025: IX no
   longer counts as landing-page view.
7. Ads Library `ad_snapshot_url` = archived creative, not the money page; CTA click
   from Library is a normal browser to the advertised URL.

No official human-reviewer UA/IP exists. Account-restriction review ~48h
(expectation, not SLA).

## Filter stack (build AND, architecture-first: zero-redirect PHP white; JS-only/
Tilda-Shopify/IP-only die)

0. **Same-host PHP reverse/local file** — safe page must display **without
   redirect** (Adspect: mandatory for FB PHP). 302-the-white is the leak.
1. **Named crawler identity** — UA ∈ facebookexternalhit/meta-externalads/(hist.)
   Facebot AND IP ∈ AS32934/AS63293/57.141 → serve white 200. Never 403 these.
2. IPv6 reject (optional/leftover — real users also use v6).
3. **Unsubstituted macros / missing url_tags/fbclid** — money AND: `{{ad.name}}`
   (or utm) not `@empty`. Works only if review fetches the **declared** Website URL
   without url_tags (official conflict: macros "replaced when rendered" — if Meta
   fetches expanded href, this gate dies). Still vendor-documented (Binom 2025-05,
   CPA.RIP). Keitaro: don't put `fbclid={fbclid}` in URL Parameters — Meta
   auto-appends fbclid; a source placeholder blocks capture.
4. Referrer contains facebook (Binom money-path requirement).
5. Language + geo match campaign targeting (empty/unknown language = common white).
6. First-N-clicks white (Binom `FIRST`; Adspect On Review + blacklist-all-IPs-in-
   Review — never click your own On-Review link).
7. JS/TLS fingerprint (second stage). Binom TLS/TCP/VPN die behind Cloudflare;
   Adspect requires Cloudflare. Pick CF+PHP or Binom-TLS-without-CF, not both.
8. **Pixel on money**: no standard FB JS pixel (Referer leaks money URL) — use
   `<meta name="referrer" content="no-referrer">` or noscript/`fetch` with
   `referrerPolicy: "no-referrer"`.

Don't enable the cloak day 0 — watch click log (bot flag/geo/UA/macros present)
first, then turn filters on.

**Vendor tool recipes** (same AND-stack, different config surface): Binom —
Website URL = bare tracker, `utm_code` lives in URL Parameters (attaches
post-moderation, so reviewer hits untagged URL); Protect-FB rule = referrer
facebook + language EN/not-empty + not-Bot (headers+IP) + country=buy geo;
expect tracker clicks ≈2× FB clicks (bot traffic), offer discrepancy 3–5%.
Keitaro — `Bots IS → white`, `country=geo AND Bots IS NOT AND {{ad.name}}/utm not
empty → money`, default white; bot DB is generic, update Geo-DBs/Bots regularly.
Adspect — safe page must have no redirect; submit On-Review + blacklist all
Review IPs, switch to Filtering only after approval; Cloudflare yellow-cloud;
self-hosted only (Shopify/Wix/Tilda pre-banned by networks); never alter a live
white; JS-integration variant (visitor starts white, ajax.php swaps) is weaker —
a JS-capable reviewer sees money.

**White bar**: official is thin (product match, working destination, not
restricted domain) — no AdsBot-style checklist. Vendor practice treats FB white
like Google white: real site, unique, mobile, legal pages, self-hosted, 200, no
redirect, not a bare affiliate link. Empty-HTML whites pass `facebookexternalhit`
OG, fail human re-review.

## What actually kills an account

1. **Content substitution** (Meta's 2026 lawsuit definition) → account/BM/domain
   cascade.
2. JS-primary/Tilda-Shopify white — constructor pre-ban; JS reviewer sees money.
3. IP-only allowlist — misses new ranges (57.141) + any residential reviewer.
4. 302-the-white — Adspect mandates no-redirect on FB PHP.
5. Standard FB pixel on money — Referer leak.
6. Restricted domain — 60-day, all ads, don't appeal the domain.
7. Recreating similar violating ads across Pages/BMs — named Evading Enforcement.
8. CTM/IX used as a cloak — second gate exists, not a skip.
9. Direct link to offer, no catalog/landing/dynamic layer — practitioner prior
   (2026 storm-era): ~1 in 10 accounts survives even nominally-white verticals.
   Catalog/landing layer is baseline survival gear, not optional camouflage.

## Failure signatures

| Signature | What it is | Move |
|---|---|---|
| Ad rejected, account live | Creative/destination | Edit creative, new ad (`04`); rejected ad can't re-enable (2490468) |
| Approved → later reject | Official re-review | Isolate creative vs domain vs account |
| Ad account restricted | Asset-level | Fresh agency: replace, don't appeal (`01`) |
| User restricted from advertising | Other admins may still run | Freeze the persona |
| BM/portfolio restriction | "Connected abusive assets" | Isolate; don't attach clean Pages |
| Domain restricted 60d | Meta-specific | Rotate domain; don't reuse on next seat |
| Pixel/event domain blocked | Events Manager, separate | New dataset; don't share across risk tiers (`01`) |
| Page unpublished | Community Standards + ads | New Page, uniquify |
| Tracker clicks ≈2× FB clicks | Bots on white | Normal; watch for domain/account wave |
| Instant copy reject | Classifier, not cloak | Image-baked text/new copy — see tricks table |
| Circumventing/evading | 2024 named; page moved 2026 | Freeze; replacement is `03`, not a self-farmed BM |

## Creative-classifier tricks

Named Circumventing (live UI 2026-08-27): cloaking · unicode/symbol obfuscation ·
obscure images (blur/pixelate/object-cover) · emoji-as-numbers/prices. Named
Evading Enforcement: clone violating ads across assets; new assets post-restriction.

| Trick | Mechanism | 2026 status |
|---|---|---|
| **DLO Default-exotic + Added-GEO** (`04`→DLO) | Default=VI/AZ/KY+white URL; Added=ES/PT/ID+grey+money URL; bot scores Default, users follow UI language | Split ~50/50 by seat/batch, not dead. Unavailable for IX/Messaging (needs Website dest). Fails if EN leaks into exotic slot or target language common in GEO |
| Soft-language copy, no DLO | Non-EN vs US/EU targeting | Degraded — OCR is multilingual |
| RTL/U+202E bidi override | Reverse displayed text | Unknown on Meta ads; treat as named obfuscation |
| Homoglyphs/ZWSP/ZWNJ/BOM | Cyrillic а, Greek ο, U+200B/C/D, U+FEFF | Live vs keyword filters, dead vs CV/OCR. Named Circumventing |
| Emoji as the claim | 💰💊🎰, 9️⃣9️⃣9️⃣ for prices | Named trip, not a bypass |
| Image-baked headline + empty ad text | — | Live as copy-field skip; dead if baked string is the violation (OCR). Blank text may pull from Website URL. A+ can rewrite baked text — opt out |
| Blur/pixelate/object-cover | Hide slot UI/body | Dead for gambling/nutra icons; video covers on porn called adversarial |
| Collection/A+ catalog | Innocent cover + grey product set; click→feed link unless Override deep links set | Live as structure — cover isn't the only review object (Commerce Manager rejects products independently, link crawled) |
| Catalog feed-swap post-review | Change images/links after approval | Circumventing if destination disguised; high ban on re-crawl |
| Catalog set-membership mutate | Pass review on white set, swap members to grey SKUs after | Claimed no re-moderation [MagicClick 2026] — still Circumventing risk; pixel must be attached or catalog invisible |
| 3-min white tail | 10-15s grey + 2-3min neutral | Live/degraded; confuses length scoring; CPM hit |
| 10-min tail | ~2min creative + 8min filler loop | Unverified 2026 claim: review pass + retention; larger CPM hit |
| Crop-from-white-collage | ~3000×3000 collage, ~95% white + grey corner, crop in-UI; FB feed only (Stories/Reels render full asset) | Live claim, uncorroborated. Meta retains original file → re-review on any post-approval edit; risk deferred not removed |
| Flexible/dynamic mix | 4-5 white sources + 1 grey | Live [MagicClick 2026]; dilution, not causal proof |
| Branding toggle flip on stuck ad | ON↔OFF, no new creative | Unverified requeue 5-20min; if still fails (2490468) → new ad |
| Instant Experience first hop | White IE canvas, CTA to money | Live; button URLs crawled; DLO off; IE≠LPV since Jun 2025 |
| Display URL ≠ Website URL | e.g. news domain vs tracker | Official: must match; masking still at scale; 60-day block risk |
| CTM/WhatsApp/IG Direct | No web LP | Live LP-skip; greeting/creative still reviewed; DLO off |
| Instant Forms | No offer LP; privacy-policy URL required | Live LP-skip; 2026 default buries Single-form (Website+Forms) — accidental website dest re-enables LP review |
| Carousel: grey card1 + white 2-n | Disable card optimization | Live; per-card review |
| Placement mix (grey Feed/IG, white Messenger/Search) | Dilute | Dying — Aug 2026 placement-control removal |
| Split claim across headline+description | Neither string trips | Degraded; A+ can swap headline↔primary |
| Video: no captions/clean first 3s/white thumbnail | Skip ASR/OCR | No-captions ≠ no ASR (audio reviewed); first-3s is a view metric not a review window |
| SAC undeclared | Avoid Financial targeting tax | Kill — may reject if uncategorized (US Financial, 2025-01-14); correct move is declare Financial |
| Dark posts/multi-Page clone | Hide from Ad Library | Dark posts still appear when active; multi-Page clone = named Evading |
| PostID reuse of approved post | Port cleared creative | Evading if same violation |
| A+ gen-bg/expand/text-gen | Camouflage | Trip, not camouflage — crops disclaimers, invents claims; grey default OPT_OUT |
| Page name/IG bio as the pitch | Ad stays clean | Unknown/weak, no sourced playbook |

**Replacement stack if unicode/blur died:** UGC lifestyle (no slot UI, no
before/after) + DLO language layers (still try, ~50/50) + empty ad-level copy +
image-baked non-keyword headline + CTWA/forms if funnel allows + Collection/IE as
first hop + declare SAC if finance-shaped. Cloak stack (PHP white) still required
for a grey web dest — format tricks are the classifier layer, not a substitute for it.

Organic Reels farm (not ads) [MagicClick 2026]: unique video + non-offer caption
- neutral cover, dest = bio/Highlights. Adult-arousal dest = no-path (`10`).
Flashing/25th-frame on **paid** ads = official video-disruptive trip, don't port.

**Catalog camouflage** [Rentacc 2025-05]: budget spread across many product cards
blurs arbitrage footprint vs one mono-creative link — update feed daily, segment
via product sets, track per-card ROAS via `content_id`. Commerce Manager still
rejects products independently (cover-pass ≠ feed-pass); post-approval swaps
disguising destination = Circumventing.

## Delivery-cloaking (steers targeting, not review)

Different goal: bot-differentiated content to manipulate Andromeda's audience-
expansion signal, not to pass review. Product still matches (not the named
substitution pattern) but is bot-vs-user differentiation — risk-bearing.
[practitioner, n=1, Partnerkin 2026-01, unverified, +30% ROI]: serve crawler UAs
content structured for a different audience signal than users see → delivery
explores audiences the user lander never attracted; readout = frequency at
scale, not CTR. Attribute with `06`'s balanced designs, one axis at a time.

## Submission-shape tricks (cheap, no cloak) 🔺

[practitioner, Praktichesky Arbitrazh 2026-09-08, no attribution design — one team's habits,
all changed together in one session. Hypotheses for `06`-style one-axis tests, not rules.]

- **Publish sequentially, one campaign at a time.** Mass-publishing (their example: 100
  accounts / 100 ad sets in one go) was blamed for a reject wave on bought spend accounts.
  Cheap to comply with and consistent with the burst-behaviour logic already in `01`; our
  bulk launcher creates PAUSED and activates on a confirm gate, which spreads writes anyway.
- **Reject-recovery by duplicate-and-swap.** When part of a batch is approved and part
  rejected: duplicate an APPROVED ad set and swap the not-yet-used creatives into the copy,
  rather than editing or resubmitting the rejected one. Same logic as `04`'s "refresh as a
  new object, don't edit a live ad." They also changed domain and Page in the same recovery
  — so the swap alone is unattributed.

## Identity / BM verification gates

Full gate table (docs, thresholds, KYC specifics) → `09`. Summary: three+ separate
gates, buying "verified" clears only one. Market (2026, vendor prices, volatile):
verified BM ~$50-$350. What still links
after purchase: user ID/cookies-tokens, phone/2FA, the verification ID, the card
— a verified BM clears none of those. Liveness: presentation attacks (print/
screen-replay/2D mask) mostly dead vs certified PAD; injection (virtual camera/
Android camera hook) is the live class, unverified efficacy claims circulate.
Same nominee on Google+Meta+bank = real intra-platform cascade; shared phone/
legal name/address/card is the practical radius, cross-platform selfie-sharing
undocumented.

## Gaps

No official UA for ad review distinct from sharing/product crawl, no official
JS-execution or residential-reviewer spec, Circumventing Systems text unreadable
(redirect), macro/url_tags split unverified, DLO-Default-scored-first is
practitioner consensus with no Meta confirmation (seat-dependent ~50/50), catalog
full-page-crawl-vs-cover-only not confirmed, RTL/U+202E on Meta ads not found.
