# 03 — Funnel ops (end-to-end QA)

The dead zone between meta-ads (ad) and tracker-ops (numbers): click-to-conversion chain. When
leads vanish but delivery looks fine, it's almost always here. Cloaking MECHANICS (how a filter
decides black/white) assumed known — this file is the QA that catches where the chain silently
breaks, including two objects agreeing on paper but disagreeing on who they let through.

## Click-ID persistence (the #1 silent killer)

- Tracker click id/`subid` must survive EVERY hop: ad → tracker redirect → (cloaca white/black) →
  pre-lander → offer → postback. Each redirect or meta-refresh that drops the query string breaks
  attribution — leads fire but can't be matched, tracker shows near-zero while offer records them.
- fbclid → CAPI is more than "pass it through": capture `fbclid` on entry, but to attribute a web
  conversion back to Meta, format it into `fbc` (`fb.1.<timestamp>.<fbclid>`), send with other
  matching params (fbp, IP, UA, hashed email/phone) in the CAPI event, and set a shared `event_id`
  on BOTH Pixel and CAPI events so Meta DEDUPLICATES them. Passing fbclid to the offer alone
  doesn't attribute — fbc/event_id/dedup is the actual work. A prelander that hard-links (new
  anchor, no params) severs it.
- Test: click a live ad end-to-end, watch the query string at each hop, fire a test conversion,
  confirm it lands on the right subid in the tracker.

## Cloaker filter ↔ Meta targeting alignment

- **Device/OS**: the cloaker's device/OS filter must exactly match the ad set's `user_os`
  targeting. Android-only cloak + ad sets not restricted to `user_os: Android` → iOS clicks get
  served the white page (paid-for traffic filtered out) or, if the cloak is looser than
  targeting, non-target OS gets the black page (budget burned on clicks that can never convert).
- Same rule for GEO: cloaker GEO allowlist must match ad-set geo-targeting, or the same two
  failure modes hit on country instead of OS. Check both every time targeting changes — a
  geo-expansion that forgets the cloaker is the common trigger. Tracker geo on mobile IPv6 maps
  to carrier hubs (out-of-target cities on real deps) — not a leak by itself (tracker-ops/01,
  FIELD 2026-09-27).

## Creative ↔ offer match (pre-launch)

Before an ad goes live, verify each creative's GEO, language, currency, and on-image logo/sizes
match the offer it's paired with — a mismatch here presents as a targeting or conversion problem
downstream but is actually a build error caught for free by looking once. Approaches (game-first
vs offer logo vs local-brand spoof) and which moves FTD vs CTR: meta-grey-ops
`playbooks/casino.md` § Creative packaging. Each creative also needs its own sub + creative_id
so results attribute per-creative (mapping mechanics: tracker-ops/03 § Markup & the mapping contract
— don't split by campaign name alone here).

## WebView / in-app browser / Telegram / PWA

- Ads open in the platform's IN-APP WebView (FB/IG). Query string (`fbclid`) SURVIVES IAB — Meta
  appends it; field logs show `FBAN/FBIOS`/`FB_IAB/FB4A` with `?fbclid=`. What does NOT survive is
  the COOKIE JAR: WKWebView ≠ Safari/Chrome. `_fbc` stays in the WebView; "Open in Safari" is a new
  session. Prefer S2S/CAPI (`fbc` from the query string) over a JS pixel needing cookies. iOS Link
  Tracking Protection (17+) strips `fbclid`/`gclid` in Mail, Messages, Safari Private — Apple, not
  Meta. Do not put `fbclid={fbclid}` in Keitaro URL Parameters (placeholder blocks capture).
- PWA is WEB, not a native app: Pixel + CAPI + tracker postbacks + web attribution all apply — a
  PWA "install" is add-to-home-screen, not a store install. Track like web (carry fbclid/subid
  through, fire web events). An MMP/SDK is needed ONLY for a real native app or app-store WebView
  wrapper — don't reach for MMP just because it's called a "PWA app" (casino playbook).
- TG bot/Mini App: Pixel inside Telegram WebView is unreliable. CAPI from bot/backend is the path.
  Short token in `start`/`startapp`, never raw `fbclid` (64-byte/charset limits). Payload →
  tracker-ops/03.

## Domain / transport health (rotating grey domains)

- Fresh/rotated domains: SSL cert must be provisioned and valid BEFORE traffic (cert lag/mismatch
  → browser block → LP CTR collapses to ~0 with normal clicks). DNS fully propagated. Check the
  cloaca gate returns black page to real users, white to reviewers from the target GEO (not your
  office IP).
- GEO latency: a slow pre-lander in-GEO tanks LP CTR/CR independent of creative — test page speed
  from the target country, budget for a CDN or in-region host on T2/T3.

## Forms / checkout / routing

- Validate the form/checkout actually submits in the target GEO on mobile (field validation, phone
  format, COD address fields). A broken field = leads that never reach the network.
- Routing/rotation: if a path rotates offers/landers, confirm each branch carries the click id and
  fires the same conversion contract.

## Version → result binding

Tag every funnel version (prelander vN, offer vN, path vN) so a result attaches to the exact
version that produced it — via a sub_id/token or the tracker's lander/offer id. Without it you
can't tell which prelander won or roll back a regression. Bind the version in the mapping contract
(tracker-ops/03).
