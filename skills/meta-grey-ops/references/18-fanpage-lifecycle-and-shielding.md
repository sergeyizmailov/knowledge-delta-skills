# 18 — Fanpage identity by GEO/tier, then share/PBIA

Reviewed 2026-09-04. Muse pass 2026-09-04. **Unmeasured.** Freeze → `01`. BM recovery → `03`. 1772103 / `--create-pbia` → `04`. PBIA token type → `meta-ads/13` §5. Ad-copy unicode → `07`. A&V / no-path geos → `09`/`10`. DLO language layers → `07`.

This file is how the **Page identity** is filled and whether it moves with GEO. Ad-set geo/language is not a Page edit. Vertical gates (casino A&V) are not skipped by a “clean” Page.

## Decision: one Page or many

Default: **one warmed Page per offer-identity**, GEO on the ad set. Kill one GEO without a new Page: Page → Followers → Country Restrictions “Show only to…” (`playbooks/casino.md`) — same control PWA.GROUP 2025-06 uses to hide the Page from non-buy geos. Not a substitute for ad-set geo.

New Page only when: current `page_publish` / unpublished; name already burned (operator TM / hijack); script/language of the *visible Page name* would be alien to both the user and a T1 reviewer (e.g. Arabic name on US) **and** you will not run DLO. Multi-Page clone of the same violating ads = Evading (`07`). Same avatar/cover/About across Pages = network fingerprint [practitioner, Conversion.im 2026-01].

Do not spin a Page per T1 country “to look local.” Reviewer sees Page name + avatar on the ad; 12 DE Pages named `Casino Berlin` is a fingerprint, not localization. Improve Team (all-GEO iGaming, UAFF 2025-10): scale by cabinets + new funnels (landing + creatives), not a Page per country. “Don’t scale TR and KR the same.” GEO lives on warmup spend, creatives, landings, proxy — not on a new Page.

## Name / avatar / about — by Page type, then GEO

**Hijack and trademark trips are global.** T3 does not unlock renaming a kháng Page. T1 only raises the chance a human looks. Registered marks in the Page name violate name policy + impersonation (help 519912414718764, 863561650424723). No public “Policy 13” / auto-unpublish / trademark-list mechanism — don’t invent one.

| Field | After first ads spend, or any PZRD/kháng Page | Fresh unused Page (create-time only) |
|---|---|---|
| **Name** | Freeze. Personal name stays (`Ciaran Ross`). Never → `Casino …` / operator TM | Set once to a personal/UGC name or unregistered fantasy (`MadridBet`). Never `1xBet`/`Melbet`/`Stake`/`Bet365`/`Vulkan` |
| **Username** | Freeze | Set once, no TM |
| **Avatar** | Freeze after first spend. PBIA copies it. Change = identity shift on live ads | Neutral face or vector human. No slot UI, no operator logo, no stolen celebrity |
| **Cover** | Freeze | Lifestyle/neutral. Slot screenshot is a review object (Page is crawled) |
| **About / category** | Freeze if kháng/in-review | `Digital creator` / `Entertainment`. No odds/bonus/FTD copy |
| **Website** | Never the money URL | Empty or white. Money URL on the Page is a crawled dest (`07`) |
| **Location** | Blank, or the **buy GEO**. Farm GEO (NG/BD) + T1 targeting = farmed Page. Phone/WhatsApp must not contradict location (BR + RU number = check) [Conversion.im 2026-01] | Same |
| **Page language** | Don’t put EN on the Page if DLO Default is exotic (`07`) | Match buy-GEO UI language or leave default |

Homoglyphs in the Page name: skip. Evade ASCII, fail OCR/manual. Named Circumventing on ads (`07`).

### GEO overlay (casino example; same skeleton for nutra/news)

| | T1 (US/UK/DE/AU/NL/…) | T2 (TR, LATAM majors, EE) | T3 |
|---|---|---|---|
| Name | Keep personal. Highest hijack/manual rate | Keep personal if kháng. Fantasy / mechanic name only if **born that way** and never spent | Same freeze. T3 ≠ rename licence |
| Avatar | Face/UGC. No logo | Face; local-looking OK. Mechanic art only if born that way | Face. Still no operator logo (OCR) |
| About | Target language or empty. No “casino” | Local language OK. Still no bonus copy | Same |
| Extra Page per country | No | No, unless script split (AR vs LATN) | No |
| A&V / licence | Unchanged by Page fill (`09`/`10`) | Unchanged | Unchanged |

News-tg (US): news-photo persona, no finance/regulation debate in About (`playbooks/news-tg.md`). Name is a person or a fake outlet, not a broker.

## What casino buyers actually run (2025–2026)

Three Page identities are live in Ad Library / named teams. Default remains **white freeze**. Do not treat a spy screenshot as a T1 rule.

| Pattern | Who | Page | Use |
|---|---|---|---|
| **White cover** | Improve Team, UAFF 2025-10 (iGaming, all GEO) | Buy white PZRD. Beauty / wedding / photo studio. No casino/betting in logo or cover (OCR). Contacts, hours, site via PWA — never money URL. 4–5 boost posts $2–3 **tuned to buy GEO**. | Default T1/T2. Keep white after grey ads start. |
| **Mechanic-themed** | TraffHub GreenLight spy 2026-04, UA Plinko / Chicken Road, weeks–months live | FP visual = creative = PWA. Fake followers, pinned link post. Page **name** is the Ad Library search key. | **Disputed.** Live T2/T3 spy. Created that way — not a rename of a white kháng Page. OCR / operator TM still apply. |
| **Empty** | AffMoment 2026-02; TraffHub связка #2 | Almost no fill. Trust on BM history + king + creative/prelander. Empty gambling Pages have lived a month+. | Not DOA. Don’t invent fill. If you fill, fill-once-then-freeze. |

Longevity of those spy campaigns attributed more to **BM spend history** than Page fill [TraffHub 2026-04]. Page fill does not skip A&V (`09`/`10`).

**Theme-switch is a trip.** White goods → gambling on the same Page = hijack [Conversion.im 2026-01]. Improve buys already-white PZRD and **keeps them white**. Mechanic Pages were born mechanic. 888STARZ 2025-09: white RKs on the Page first, then grey — that is PPE/posts, not a rename.

**Self-create vs buy.** Dolphin 2026-08: self-create looks more natural than a shop Page. AffMoment 2026-02: buy if no farm desk; aged unused Pages often still allow a **create-time** name change — shop check, not a live edit after spend. NPE is not a trust premium. Meta Verified badge is not ban-proof and blocks partner share (below).

**EN.** Partnerkin 2025-10: warmup post is **non-gambling**, then boost; licensed-geo gate for white casino ads unchanged. Italy case “refreshed Fan Page” on trusted accounts ≠ licence to rename kháng. NPPR seller case (one aged Page per ad account) is one shop, not a rule.

**Skip.** Homoglyphs in the Page name to dodge spy [PWA.GROUP 2025-06] = Circumventing (`07`). Fake like/comment consensus — split among buyers; Dolphin skips. PirateCPA “Community / Public figure” for grey is SEO-y, weaker than `Digital creator` / `Entertainment`. Bank/operator logos on avatar (Magic Click 2026-05 Revolute/bank parasitism) = TM hijack.

## Fill checklist (once, then freeze)

1. `GET /{page_id}?fields=name,is_published,has_transitioned_to_new_page_experience,location,website,access_token` + `GET /{page_id}/page_status`.
2. `is_published=false` or `page_publish` restricted → don’t launch; new Page, uniquify (`07`). Don’t appeal CS-unpublish as an ads reject. Unpublished Page: delivery check `page_status` = “Page Unpublished” — ad cannot deliver [official deliverychecks]. Do not invent `ad_creative_page_disabled`. Page still tied to a banned BM → unbind first or it cannot launch [Dolphin 2026-08; AffMoment]. Recovery → `03`.
3. Patch only empty/wrong **create-time** fields. Any name/avatar/about write on a spent or kháng Page = hijack surface. Restriction on the persona → FREEZE (`01`). Don’t clone avatar/cover/About from another live Page.
4. Warm-up (Page, not `04` account ramp): 3–5 non-violating posts ≥24h apart [practitioner]; 4–5 boosts $2–3 **on buy GEO** [Improve 2025-10] or $2–5 PPE on white creative. Comment-lock warmup posts [Dolphin]. Billing **hold**: boost an existing Page post (“use this post as the ad”) [Dolphin 2026-08]. No operator marks. White-then-grey is this step, not a Page rename [888STARZ 2025-09; Partnerkin EN 2025-10].
5. Set Page country restrictions to the buy GEO (Dolphin “intended countries”; PWA.GROUP Country Restrictions). Then share + PBIA (below). Don’t edit identity after ads are live — PBIA name/pic follow the Page.

## Supply (which Page to buy)

| Tier | What | Use |
|---|---|---|
| Fresh / autoreg | 0 spend, 0 appeal | Skip grey. Hours–1d death (`03` DOA) |
| PZRD / trang kháng | Restricted → appealed → reinstated | Default. Name freeze is the whole point of buying it |
| Aged spent | >$500 clean Page-ads history | Best. Same freeze |

## Partner share (Mother owns, Daughter spends)

Mother BM owns the Page; no grey spend, no untrusted cards on Mother. Daughter gets ads-only. Daughter death → stop using the share; don’t “fix” the dead BM (`03`).

```
POST /{page_id}/agencies   {business: <daughter_bm>, permitted_tasks: [...]}
```

Page token + `MANAGE` on the Page. Partner must accept. **No DELETE/PATCH** on this edge — revoke in UI (Business Settings → Partners).

| Page | Grant Daughter | Never grant |
|---|---|---|
| Classic (`has_transitioned_to_new_page_experience=false`) | `ADVERTISE` | `MANAGE` |
| NPE (`true`) | `PROFILE_PLUS_ADVERTISE` | `PROFILE_PLUS_FULL_CONTROL` / `MANAGE` |

NPE migration is ongoing — no public completion figure. Treat as NPE iff `has_transitioned_to_new_page_experience=true`. NPE `/feed` `/posts` need a **Page token** (user/SU → 200 [community]). v26+ NPE: don’t request `current_location,genre,network,parking,start_info`. After the ~90-day window (late Oct 2026, date TBC) the same block hits **all versions** — drop the fields unconditionally, not only on v26+ [v26 blog 2026-07-29].

**CLI gap:** `metaops business partner share --asset page` allows `ADVERTISE,ANALYZE,MANAGE` only. `PROFILE_PLUS_*` is rejected. NPE: try `ADVERTISE`; Graph `100` → Ads permission in UI [practitioner — agencies ref does not list accepted `permitted_tasks`].

| Graph | Move |
|---|---|
| **3989** | Already shared; stop |
| **3946** | They’re owner, not partner |
| **368** | Freeze. Check Meta Verified badge, 2FA, restricted BM |
| **200** | Page token + MANAGE, not SU token |

Share blockers: paid **Meta Verified badge** on Page/IG blocks partner assign until cancelled or Verified Support [practitioner, Leadsie 2026-08] — not Business Verification (`09`). 2FA **state** blocks asset assignment in practice [practitioner, Leadsie 2026-08] — official 2FA is portfolio-level (>90d forced-on) and ads-publish, not a Help-Center “must be on to add partners”. Advertising-restricted BM cannot *request* Page access [practitioner — Help 183277585892925 lists no ad-restriction gate]. **No official “unverified BM cannot share Pages”** — don’t claim it.

## PBIA

`POST|GET /{page_id}/page_backed_instagram_accounts` — Page token, ≥`ADVERTISER`, one per Page, idempotent. `metaops doctor --create-pbia`. 190 / 1772103 → `04` / `13`.

**User-owned ad account + page-connected IG → PBIA illegal on the creative.** Use `instagram_accounts` id. **BM-owned ad accounts: restriction does not apply.** [official pages-ig-account, 2025-09-17]. Graph rejecting a real PBIA id on that combo → swap to the connected IG id; don’t invent a public error string.

Ads-only identity (no login/organic). Rename/avatar on the Page rewrites live IG ads identity — another reason T1 freeze.

Around PBIA create: high-reach **identity confirmation** (deadline → cannot post as Page). **SU cannot publish until every BM on that Page is Business-verified** [help 1939753742723975]. Persona checkpoint → freeze (`01`).

## Integrity

`GET /{page_id}/page_status` (Integrity doc updated 2026-07-06): `page_publish` = unpublished, Page dead; `page_read_only` = no new posts, existing ads may still run. Ads on unpublished Page fail delivery check `page_status` (“Page Unpublished”).
