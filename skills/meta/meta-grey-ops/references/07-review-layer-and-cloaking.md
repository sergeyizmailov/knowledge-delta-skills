# 07 — Review layer, cloaking, creative-classifier tricks

Reviewed 2026-09-09; re-review, tr-1 and display-link rows updated 2026-09-29. Session/IP → `01`. Agency/BM → `03`. API launch / re-moderation → `04`.
Policy taxonomy (clean lane) → `meta-ads/07`. Vendor tool configs and `🔺`/unverified hypotheses
→ `07a-vendor-recipes.md` — build nothing load-bearing on them without a `06`-style one-axis test.

**Not authorization.** This documents how review fetch works so launches don't die on
architecture mistakes (no-redirect white, referrer/macro gates, pixel-leak hygiene). Disguising a
destination is Circumventing Systems — named, and cited in Meta's 2026-02-26 lawsuit. On
detection: freeze/replace/rotate (failure signatures below, `05`), never self-farmed evasion.

## What Meta named (official, live-fetched 2026-08-27)

- Ad product/service **must match landing page**. Evading/circumventing enforcement or review is
  prohibited and a restriction ground.
- 2024 Circumventing Systems (URL now redirects to Account Integrity): **cloaking** (limiting
  Meta's destination access), **unicode/symbol obfuscation**, **obscure images**. Evading
  Enforcement: recreating violating ads across assets; spinning new assets after restriction.
- 2026-02-26 newsroom: cloaking = "webpage shows one version to ad review, different content to
  real users." AI cloaking detection; faster reject on redirect chains.
- **Display URL must match Website URL's domain.** "~25 char truncation" has no official source
  (likely Link Description's 30-char cap, Marketplace/search/AN only) — measure in preview.
- Mar 2026: single-media + A+ catalog collection ads on FB Feed no longer show footer URL —
  mismatch less visible, not less enforced.
- **Domain block**: restricted LP domain → all ads to it rejected, 60-day block, repeats if linked
  accounts keep violating. Fix = **change domain**, never appeal it.

## Crawlers (official page, `developers.facebook.com/docs/sharing/webmasters/crawler/`)

| UA | Job | Ad review? |
|---|---|---|
| `facebookexternalhit/1.1` | OG link-preview | Not stated |
| `meta-externalads/1.1` | ad/business products | Closest named; not labeled "review" |
| `meta-externalagent/1.1` | AI training/indexing | No |
| `meta-externalfetcher/1.1` | user-requested; may bypass robots.txt | No |
| `meta-webindexer/1.1` | Meta AI search | No |

Not on current page: `Facebot`, `FacebookBot`, IG crawler, `facebookcatalog/1.0`.

`facebookexternalhit`: gzip+deflate, OG in first 1MB, `Range: bytes=0-524288`, seconds, may
ignore robots.txt for integrity checks. Simulate: `curl -v --compressed -H "Range:
bytes=0-524288" -H "Connection: close" -A "facebookexternalhit/1.1
(+http://www.facebook.com/externalhit_uatext.php)" "$URL"`. IPs: `whois -h whois.radb.net --
'-i origin AS32934'` + AS63293; IPv6 `2a03:2880::/32`; 2026 logs add **57.141.0.0/24**.
WhatsApp preview UA = link preview, not review. **JS execution by ad review: undocumented** —
vendors assume a second Chrome-class/residential path; don't bet on "review can't run JS."

## Review layering (order)

1. Automated pre-serve on create/edit, "In review" ~24h (often minutes); ad **may deliver before
   all checks finish**.
2. Destination fetch of Website URL + redirect path (no published fetcher UA).
3. Re-review any time, including post-live.
4. Official re-review triggers: targeting, creative, optimization, billing event. Field (`04`,
   2026-08, 45 ad sets): geo/device/age/placement/budget/bid/schedule did **not** change status —
   but field 2026-09-22 a targeting edit put a live ad back into review and it came back DISAPPROVED
   (`19` §4). Not review-safe; only a rename (~15 s IN_PROCESS, 2026-09-29), budget, bid and schedule
   have been seen not to re-review.
5. **Click-to-Messenger**: welcome message reviewed as a thread-level gate — second gate, not a
   skip.
6. **Instant Experience**: button URLs still crawlable; since Jun 2025 IX ≠ landing-page view.
7. Ads Library `ad_snapshot_url` = archived creative; Library CTA click is a normal browser to the
   advertised URL.

No official human-reviewer UA/IP. Account-restriction review ~48h (expectation, not SLA).

## Filter stack (build AND, architecture-first: zero-redirect PHP white; JS-only/Tilda-Shopify/IP-only die)

0. **Same-host PHP reverse/local file** — white displays **without redirect** (Adspect: mandatory
   for FB PHP). 302-the-white is the leak.
1. **Named crawler identity** — UA ∈ facebookexternalhit/meta-externalads/(hist.) Facebot AND IP
   ∈ AS32934/AS63293/57.141 → white 200. Never 403 these.
2. IPv6 reject (optional — real users use v6 too).
3. **Unsubstituted macros / missing url_tags/fbclid** — money requires `{{ad.name}}` (or utm) not
   `@empty`. Works only if review fetches the **declared** URL without url_tags (docs say macros
   are "replaced when rendered" — if Meta fetches the expanded href, this gate dies).
   Vendor-documented (Binom 2025-05, CPA.RIP). Keitaro: don't put `fbclid={fbclid}` in URL
   Parameters — Meta auto-appends fbclid; the placeholder blocks capture. If a cloak rule keys on a
   sub id being non-empty, only a genuine ad click reaches money — a hand-typed visit landing on
   white is correct, not a broken funnel (field 2026-09-21/22).
4. Referrer contains facebook (Binom money-path requirement).
5. Language + geo match targeting (empty/unknown language = common white).
6. First-N-clicks white (Binom `FIRST`; Adspect On Review + blacklist-all-IPs-in-Review — never
   click your own On-Review link).
7. JS/TLS fingerprint (second stage). Binom TLS/TCP/VPN die behind Cloudflare; Adspect requires
   Cloudflare — pick CF+PHP or Binom-TLS-without-CF.
8. **Pixel on money**: no standard FB JS pixel (Referer leaks money URL) — use `<meta
   name="referrer" content="no-referrer">` or noscript/`fetch` with `referrerPolicy:
   "no-referrer"`. Automatic Advanced Matching OFF on that dataset — it scans the money page's
   form fields (email/phone/name/city/region/country/postcode/gender) and ships them hashed to
   Meta (confirmed 2026-09-22 vs Advanced Matching docs). Overrides `meta-ads/08:13`'s "Enable"
   (clean-funnel advice).

Don't enable the cloak day 0 — watch the click log (bot flag/geo/UA/macros) first.

**Tracking-URL token scope**: a tracking URL goes to a third-party lander operator — only the
pixel-scoped CAPI token, never the BM System User token (that would hand never-expiring ADMIN over
the BM). Field 2026-09-21: the CAPI token can't even read its pixel's metadata.

**White bar**: official is thin (product match, working destination, unrestricted domain).
Vendor practice: real site, unique, mobile, legal pages, self-hosted, 200, no redirect, not a bare
affiliate link. Empty-HTML whites pass `facebookexternalhit` OG, fail human re-review.

## What actually kills an account

1. **Content substitution** (Meta's 2026 lawsuit definition) → account/BM/domain cascade.
2. JS-primary/Tilda-Shopify white — constructor pre-ban.
3. IP-only allowlist — misses 57.141 + residential reviewers.
4. 302-the-white.
5. Standard FB pixel on money.
6. Restricted domain.
7. Recreating violating ads across Pages/BMs (Evading).
8. CTM/IX used as a cloak.
9. Direct link to offer with no catalog/landing/dynamic layer — practitioner prior (2026): ~1 in
   10 accounts survives even in nominally-white verticals. That layer is baseline survival gear.

**Account integrity — separate axis, judged on account provenance before any creative/cloak/DLO:**

10. Autoreg/automation fingerprint: `account_status 2`, `disable_reason 1`, `amount_spent 0`,
    **zero impressions ever**, notice "created or used with an automation that doesn't follow our
    rules" (field 2026-09-21, two accounts). Zero impressions + $0 spend = **account-level**
    disable; creative rejections surface as per-ad `DISAPPROVED`+`review_feedback`, never
    `account_status 2`. Content was still seen: any API create (ACTIVE or PAUSED) submits to
    review immediately (`04`). Don't rebuild creative/cloak/DLO for it. Ban detection → `03`;
    automation-fingerprint clustering → `06`. Counter-sequence, field 2026-09-29 (tr-1, ~$9 billed):
    all 3 ads approved, then DISAPPROVED "Spam" within 1-2 min each, and the account went `status 2`,
    `disable_reason 1` two minutes after the third; so per-ad rejections can precede an account-level
    disable when the account itself is the target. Triage → `23`.
11. Speed/sequence compression [practitioner, cpa.rip 2026-09-24, guide to *deliberately
    provoking* the restriction: create BM → spend limit + card → immediately create ads]. So
    "account → card → campaign inside an hour" is a known burn shape. Prevention: decouple steps in
    time; leave the first campaign unpublished for hours — a UI-draft buffer with no API
    equivalent (`04`).

**`disable_reason` / `account_status` enum** [first-party, verified 2026-09-24,
developers.facebook.com/docs/marketing-api/reference/ad-account/]:
```
disable_reason: 0 NONE · 1 ADS_INTEGRITY_POLICY · 2 ADS_IP_REVIEW · 3 RISK_PAYMENT
· 4 GRAY_ACCOUNT_SHUT_DOWN · 5 ADS_AFC_REVIEW · 6 BUSINESS_INTEGRITY_RAR
· 7 PERMANENT_CLOSE · 8 UNUSED_RESELLER_ACCOUNT · 9 UNUSED_ACCOUNT
· 10 UMBRELLA_AD_ACCOUNT · 11 BUSINESS_MANAGER_INTEGRITY_POLICY
· 12 MISREPRESENTED_AD_ACCOUNT · 13 AOAB_DESHARE_LEGAL_ENTITY
· 14 CTX_THREAD_REVIEW · 15 COMPROMISED_AD_ACCOUNT
account_status: 1 ACTIVE · 2 DISABLED · 3 UNSETTLED · 7 PENDING_RISK_REVIEW ·
8 PENDING_SETTLEMENT · 9 IN_GRACE_PERIOD · 100 PENDING_CLOSURE · 101 CLOSED
```
Reason **1** = entity/**linkage** bucket: Account Integrity standard is reported (quote from a
research pass, not re-rendered) to name "close linkage with a network of accounts", inauthentic
users setting up business assets, assets "connected to other abusive assets". Reason **4** exists
separately for mass-created grey accounts — so reason 1 on a farmed account points at what it's
*connected to* (shared app/system-user/card/proxy/page/BM). Isolate shared app/system-user across
a pack. Not the only reading: FIELD 2026-09-27 reason 1 hit a spent account after heavy API write load while
siblings on the same SU token/page/domain survived (`06`) — load and account weakness are suspects too. No source
maps RU "ЗРД" to an enum value — don't assert one.

## Failure signatures

| Signature | What it is | Move |
|---|---|---|
| Ad rejected, account live | Creative/destination | Switch it off; new ad with a different creative/angle/PWA (`04`); rejected ad can't re-enable (2490468); never re-upload it into the same account (FIELD 2026-09-27). Operator rule: on a disapproval do not edit or resubmit (no appeal-and-resubmit here) |
| Approved → later reject | Official re-review | Isolate creative vs domain vs account. All ads "Spam" within minutes of approval, then a disable → `23` |
| Ad account restricted | Asset-level | Agency/log stock: ask TL/agency "appeal or replace", don't appeal alone (`05`) |
| User restricted from advertising | Other admins may still run | Freeze the persona |
| BM/portfolio restriction | "Connected abusive assets" | Isolate; don't attach clean Pages |
| Domain restricted 60d | Meta-specific | Rotate domain; don't reuse on next seat |
| Pixel/event domain blocked | Events Manager, separate | New dataset; don't share across risk tiers (`01`) |
| Page unpublished | Community Standards + ads | New Page, uniquify |
| Tracker clicks ≈2× FB clicks | Bots on white | Normal; watch for domain/account wave |
| Instant copy reject | Classifier, not cloak | Image-baked text/new copy — see tricks table |
| Same creative rejected in one US state, approved in another | Content/brand/state rule, not the account | Don't burn more accounts or re-uniquify; change the creative or wrap it in DLO (`playbooks/casino.md`) [field 2026-09-25, n=1] |
| Circumventing/evading | 2024 named; page moved 2026 | Freeze; replacement is `03`, not a self-farmed BM |

## Creative-classifier tricks

Named Circumventing (live UI 2026-08-27): cloaking · unicode/symbol obfuscation · obscure images
(blur/pixelate/object-cover) · emoji-as-numbers/prices. Named Evading: cloning violating ads
across assets; new assets post-restriction.

| Trick | Mechanism | 2026 status |
|---|---|---|
| **DLO Default-exotic + Added-GEO** (`04`→DLO) | Default=VI/AZ/KK+white URL; Added=ES/PT/ID+grey+money URL; bot scores Default, users follow UI language | Split ~50/50 by seat/batch, not dead. Needs Website dest (no IX/Messaging). Fails if EN sits in the default slot |
| Soft-language copy, no DLO | Non-EN vs US/EU targeting | Degraded — OCR is multilingual |
| Homoglyphs/ZWSP/ZWNJ/BOM, RTL/U+202E, emoji-as-claim | Cyrillic а, Greek ο, U+200B/C/D, U+FEFF; bidi reverse; 💰💊🎰, 9️⃣9️⃣9️⃣ prices | Named Circumventing. Homoglyphs live vs keyword filters, dead vs CV/OCR; RTL unknown on Meta |
| Image-baked headline + empty ad text | — | Live as copy-field skip; dead if baked string is the violation (OCR). Blank text may pull from Website URL. A+ can rewrite baked text — opt out |
| Blur/pixelate/object-cover | Hide slot UI/body | Dead for gambling/nutra icons; video covers on porn called adversarial |
| Collection/A+ catalog | Innocent cover + grey product set; click→feed link unless Override deep links set | Live as structure — Commerce Manager rejects products independently, link crawled |
| Catalog feed-swap post-review (gate: `00` 9.7) | Change images/links after approval | Circumventing if destination disguised; high ban on re-crawl |
| Catalog set-membership mutate (gate: `00` 9.7) | Pass review on white set, swap members to grey SKUs after | Claimed no re-moderation [MagicClick 2026] — still Circumventing risk; pixel must be attached or catalog invisible |
| 3-min / 10-min white tail | 10-15s grey + 2-3min neutral / ~2min + 8min filler | 3-min live/degraded; 10-min unverified; CPM hit grows with length |
| Crop-from-white-collage | ~3000×3000 collage, ~95% white + grey corner, crop in-UI; FB feed only (Stories/Reels render full asset) | Uncorroborated. Meta retains original → re-review on any post-approval edit |
| Flexible/dynamic mix | 4-5 white sources + 1 grey | Live [MagicClick 2026]; dilution, not causal proof |
| Branding toggle flip on stuck ad | ON↔OFF, no new creative | Unverified requeue 5-20min; if still fails (2490468) → new ad |
| Instant Experience first hop | White IE canvas, CTA to money | Live; button URLs crawled; DLO off |
| Display URL ≠ Website URL | e.g. news domain vs tracker | Official: must match; masking still at scale; 60-day block risk. Our rule: display link empty or the root domain, never a casino subdomain and never an unrelated domain |
| CTM/WhatsApp/IG Direct | No web LP | Live LP-skip; greeting/creative still reviewed; DLO off |
| Instant Forms | No offer LP; privacy-policy URL required | Live LP-skip; 2026 default buries Single-form (Website+Forms) — accidental website dest re-enables LP review |
| Carousel: grey card1 + white 2-n | Disable card optimization | Live; per-card review |
| Placement mix (grey Feed/IG, white Messenger/Search) | Dilute | Dying — Aug 2026 placement-control removal |
| Split claim across headline+description | Neither string trips | Degraded; A+ can swap headline↔primary |
| Video: no captions/clean first 3s/white thumbnail | Skip ASR/OCR | Audio is still reviewed; first-3s is a view metric not a review window |
| SAC undeclared | Avoid Financial targeting tax | Kill — may reject if uncategorized (US Financial, 2025-01-14); declare Financial |
| Dark posts / multi-Page clone / PostID reuse | Hide from Ad Library; port cleared creative | Dark posts appear when active; clone = named Evading; PostID reuse Evading if same violation |
| A+ gen-bg/expand/text-gen | Camouflage | Trip — crops disclaimers, invents claims; grey default OPT_OUT |
| Page name/IG bio as the pitch | Ad stays clean | Unknown/weak, no sourced playbook |

**Choosing the two DLO locale slots:**

- **Added/target slot = every language spoken in the buy GEO.** TR: 19 + Kurmanji 76,
  Azerbaijani 53, Arabic 28. Users on an unlisted UI language fall through to the default (white)
  creative at full price. Field 2026-09-23: TR shipped `[19]`, widened to `[19, 76, 53, 28]`.
- **Default/exotic slot: anything rare in the GEO.** Catch-all (`04`) — no delivery effect, only
  shapes what the reviewer sees; widening is free.
- **English (6, 24, 1001): never in the default slot** (kills the trick). In the TARGET slot it's
  fine, and required for English-majority geos (US/UK/AU/CA). Field 2026-09-25 US-FL: en 1001
  target + vi/az/kk default with white kitten video → 3/3 approved where the plain ad was rejected
  twice [n=1 campaign].
- **White slot creative**: any neutral stock (CC nature/pet video, 9:16); same link in all slots is
  fine — the cloak handles bots [field 2026-09-25].

**Replacement stack if unicode/blur died:** UGC lifestyle (no slot UI, no before/after) + DLO
(~50/50) + empty ad copy + image-baked non-keyword headline + CTWA/forms if funnel allows +
Collection/IE first hop + declare SAC if finance-shaped. A grey web dest still needs the PHP-white
cloak stack — format tricks don't replace it.

Adult-arousal dest = no-path (`10`). Flashing/25th-frame on **paid** ads = official
video-disruptive trip. Organic Reels farm (not ads) [MagicClick 2026]: unique video + non-offer
caption + neutral cover, dest = bio/Highlights.

**Catalog camouflage** [Rentacc 2025-05]: budget across many product cards blurs the footprint vs
one mono-creative link — update feed daily, segment via product sets, per-card ROAS via
`content_id`. Commerce Manager rejects products independently; post-approval swaps disguising
destination = Circumventing.

## Delivery-cloaking (steers targeting, not review)

Single-source hypothesis (n=1) → `07a-vendor-recipes.md`. Not a review-pass tool; risk-bearing.

## Submission-shape tricks (cheap, no cloak) 🔺

One team's habits (Praktichesky Arbitrazh 2026-09-08) → `07a-vendor-recipes.md`; hypotheses for
`06`-style tests. `bulk-apply` creates every row in one run — to publish in waves, one `bulk-plan
--only act_X` per wave.

## Identity / BM verification gates

Full gate table → `09`. Three+ separate gates; buying "verified" clears one. Verified BM ~$50-$350
(2026 vendor prices, volatile). Still linking after purchase: user ID/cookies-tokens, phone/2FA,
the verification ID, the card. Liveness: presentation attacks (print/screen-replay/2D mask)
mostly dead vs certified PAD; injection (virtual camera/Android camera hook) is the live class,
efficacy unverified. Same nominee on Google+Meta+bank = real cascade; shared phone/legal
name/address/card is the practical radius; cross-platform selfie-sharing undocumented.

## Gaps

No official ad-review UA distinct from sharing/product crawl; no official JS-execution or
residential-reviewer spec; Circumventing Systems text unreadable (redirect); macro/url_tags split
unverified; DLO-Default-scored-first is practitioner consensus (~50/50 by seat); catalog
full-page-crawl vs cover-only unconfirmed; RTL/U+202E on Meta ads not found.
