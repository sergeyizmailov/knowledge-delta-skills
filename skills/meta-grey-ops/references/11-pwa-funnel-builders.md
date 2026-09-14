# 11 — PWA funnel builders (casino/iGaming)

Reviewed 2026-09-09.

Builders = PWA "install-page" LP + tracker + geo-cloak + CAPI forwarder, one per domain. Contract identical across vendors; only macro spelling, postback host, test tooling differ. Facts: vendor docs/bundles fetched 2026-08-30 (SPA sites, extracted from JS bundles) + practitioner sources — mostly vendor blogs, not neutral measurement.

## Universal contract — verify all 5 per vendor before spend

| # | Item | Failure if skipped |
|---|---|---|
| 1 | Join key: click id at entry, exposed as offer-URL macro (spelling varies per vendor) | Wrong macro → literal in offer URL → postbacks never match → zero CAPI events, funnel looks dead. Test: substituted value visible in offer URL |
| 2 | Postbacks IN from network: reg + dep (dep carries value+currency; rules differ — pwa.bot usd-only, MonsterPWA `{currency}`) | Value/currency mismatch corrupts spend reporting |
| 3 | CAPI forwarder: dataset id + token, map install→Lead, reg→CompleteRegistration, dep→Purchase | No shared `event_id` pixel↔CAPI → deposits double-count |
| 4 | Cloak: non-target geo/crawler UA/datacenter IP → whitepage | Remote curl QA always shows white; must test user-branch from target geo (proxy/SIM) |
| 5 | Test tooling: test-event feature or manual postback fire | Check Events Manager Test Events before trusting live data |

## Vendor table (fetched 2026-08-30)

| Builder | Join macro | Postback IN | FB events | Cloak | Notes |
|---|---|---|---|---|---|
| **pwa.bot** | `{user_id}` (only one; `{subid}` doesn't exist) | `api.pwa.bot/postback/?user_id={...}&event=reg\|dep&value={profit}&currency=usd` (usd only) | install→Lead, reg→CompleteRegistration, dep→Purchase | Geo whitepage ("Stope page") | Test: «Пульс» + test_event_code; pixel off PWA unless `fbp=<dataset_id>` param; full setup → `playbooks/casino.md` |
| **Monster PWA** (monsterpwa.com) | `{external_id}` + `{subId}` (case-insensitive) | `pwac.world/postback?external_id={external_id}&event=reg\|dep&value=&currency=` | install→Lead, open→ViewContent, reg→CompleteRegistration, dep→Purchase; CAPI delivery logs; event_id dedup undocumented | Built-in cloaca + Adspect; device rules; per-country PWA mapping; white from Play/AI | Only vendor publishing full inbound postback contract |
| **PWA.Group** | Per-network click_id (templates); outgoing as `{get_PARAM}` | Template postbacks, reg/dep separate | install→Lead auto; "no duplicate events" toggle = dedup | "non-target GEO" whitepage + filter module | Macro list via support TG; pixel+token CAPI |
| **APEX** (app.apex-pwa.com) | clickid persisted across install; macro unpublished | Keitaro/Binom/RedTrack/Voluum S2S guides; reg/dep/qualified | event_id dedup documented; pixel per domain (survives rotation) | Cloaca + antibot: geo, ASN/datacenter, VPN, UA, JS-challenge; `?nc=1` bypass | EMQ/Test Events guide; HTTPS auto |
| **Comsign** (comsign.io) | Docs in-app only | — | Pixel insertable on safe page | Modes Strict/Money/Flexible/Manual; AI whites; 48-lang; HTML randomization | Moderation-protection positioning |

Dead/no public docs 2026-08-30 (don't waste time): AFFPRO, app-pwa.com, ipwa.io, pwabudget.com, pwawave.com, pwa2win.com, appsb.io (dead/parked); EpicPWA, PWA.Market (live, doc-opaque).

Named, contract unknown (evaluate via the 5 points above before spend): **SetPro** — affiliate-promoted, no macro/postback/event mapping published [2026-09-08].

## Failure modes (documented in the wild, 2026 sources)

| Symptom | Cause |
|---|---|
| Funnel looks dead, zero CAPI | Click-id stripped by a redirect/builder hop — once gone, no postback reconstructs it |
| FB optimizes wrong target | Postback status macros mismatched to pixel events |
| Optimization poisoned toward non-payers | reg+dep+rebill flattened into one generic Purchase |
| Deposits double-counted | pixel+CAPI without shared event_id (generated independently per side — common bug) |
| Low EMQ | fbc/fbp/external_id not captured at click; fbc expires 7 days; pixel-only EMQ 3–5 vs 6–8 with postbacks; 20–30% of purchases lost to browser prevention, recoverable via CAPI |
| Real events route to test panel | `test_event_code` left live |
| CAPI feed silently cuts | Expired System User token |
| Attribution window missed | Network batching postbacks past the window |
| Empty macro values | `{{placement}}`/`{{site_source_name}}` return empty in some ASC/catalog configs |
| fbclid missing | iOS Link Tracking Protection strips it in Mail/Messages/Safari-private |

## QA gates before scaling

1. Walk click→deposit end-to-end in tracker's live UI; substituted join-key visible at every hop.
2. Test events: event_name/value/event_id correct; pixel+CAPI share event_id; EMQ ≥6.
3. Postback delivery logs clean (no 404/timeout); weekly health audit after.
4. Target-geo SIM, mid-range Android: PWA loads <2s on 3G; separate iOS/Safari install page.
5. Events Manager diagnostics 2–3 days live → remove test_event_code; keep 5–10 domain pool with rotation plan (Meta flags domains system-wide — a URL seen in a banned ad underperforms even from new accounts).
6. reg→FTD split diagnostic: installs high/regs low = onboarding problem; regs high/FTD low = payments or traffic quality.

## Numbers (practitioner/self-reported bands, no independent audit)

| Metric | Band |
|---|---|
| click→install | 18–35% PWA (vs 8–14% mobile landing) |
| install→reg | 40–60% |
| reg→FTD | 10–20% |
| click→FTD | 3–7% solid |
| Meta installs cost / FTD (case) | $1.2–1.5 / ~$30 |
| Deep links lift | +20–40% FTD CR |
| Local payments lift | +25–40% deposit CR |
| Push campaigns lift | +20–30% FTD |

Sources: affhub.media 2026-01-09, affstudio.org 2026-03/05, partnerkin 2026-06.

**Moderation reality**: NordVPN (2026-07-30) logged a 400+ domain network serving fake Play-style "clean" pages to automated review (3,100+ instances) vs 7,200 casino-page instances — proof Meta adversarially re-crawls at scale. Treat the funnel as a window, not immunity: rotate domains/accounts, expect re-crawl, keep the white set intact until every first review is done.
