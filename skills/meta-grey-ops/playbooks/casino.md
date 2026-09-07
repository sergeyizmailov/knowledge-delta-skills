# Playbook — iGaming / Casino / Betting

Reviewed 2026-09-06. Vendor/team numbers below are directional priors — replace with live data.
Execution mechanics → `00`; structures/leftover reset → `04`; scale mode → `senior-buyer-ops/01`.
Practitioner block (Admatrix 2026-08/09: T1 DE/FR-multi + T3 AR/ZA) is labelled; not a platform rule.

**Gate:** A&V authorization + per-jurisdiction licence, filed before any ad exists, intent declared per new territory. 19 no-gambling markets, social-casino carve-out → `10`. Approvals bind to portfolio+account — replacement account needs new approval (`09`).

**Objective/event:** OUTCOME_LEADS → optimize CompleteRegistration first (FTD too sparse on small budgets); switch to Purchase (FTD) at ~20–30 FTD via a NEW campaign. **Payout KPI = CPA per FTD** always (click-date cohorts). T3 *operating* KPI = reg CPA (CR stable enough that dep closes); T1 operating = full chain.

**Funnel/tracking:** FB/IG ad → pre-lander → casino LP or PWA/WebView, or FB→Telegram bot→deposit.
- PWA/H5/web-checkout: WEB tracking (tracker postback + Pixel/CAPI, carry fbclid through smart-link) — no app-store gate.
- FB→TG bot: no Pixel; CAPI from bot with a short token, not raw fbclid (tracker-ops/03).
- Native app: MMP (AppsFlyer/Adjust) SDK → S2S to Meta (needs UA+IP); pin which MMP event = FTD, mirror to tracker.
- Messenger/ManyChat: still CTM greeting+thread gate (`07`) — not a review skip.

**T1 vs T3 (operating split, not just payout):** T3 buys more tests per $ — primary KPI is **reg CPA** (CR more stable than T1; same-day dep CPA is noise until lag lands). T1: judge the full chain, campaigns often live hours not days. Start budget: T3 **$15–20**; T1 either **$100–150** test / **$250–350** proven, or ≈ CPA payout ($300–500 on a ~$250 FTD GEO). iOS slack vs Android/PWA: all metrics dearer — unique-click hold ~2× the Android bar on first tests. T3 localization of **currency + language + brand** is mandatory; EN free-spin leftovers underperform. Switch offers on **live CR**, not a single payout number.

**Proxy ladder** (fast events; payout still Poisson in `senior-buyer-ops/04`). From CPA payout: unique click ≈ **2%**, install **10%**, reg **20%**, then fold min ROI 20–30%. Attention-kill before that: ~**100–150 impressions / 0 clicks**, or T1 **~$10 spend / 0 link click** (don't wait for install price); T3 Africa ~**$2.50 / 0 regs**. CTR <0.5% is a screen, not a religion — expensive uniques with holding click→install / install→reg / reg→dep are often the better audience. ~**10–15% of deps never reach FB**; T3 lag **15–20% over 3–7d**; push **+5–10%** late deps. FB credits the *arrival* day, not the click day — day-1 loss in Ads Manager is not a kill (`tracker-ops/03`).

**Creative:** real **provider gameplay** (scatter / win-screen / slot recording) + offer bonus; recut “fake slot” loses message-match and traffic quality. Static = fewer rejects; motion/UGC = better dep CPA — split the test, don't default one. Refresh a depositing static as a **new file** (AI-animate / metadata variant) — don't edit the live ad (re-review, `04`). Spy-dump of a competitor's slot pack without a test plan is not a test. Setup matrix (1-1-1 / 1-5-1 same vs different / 1-3-3) → `04`. New GEO: **~3 cabinets**, not one (cabinet hook ≠ creative hook).

**Review traps:**
- Catalog camouflage (TR field-tested 2026-08-30): ≥4-product-set limit is Collection-format-only (error 2490457); submit with all-white cards, slot arts pre-uploaded but out-of-set, swap via API filter post-approval — no re-review. Never let set drop below 4. Alt: 1-product set renders as single deep-linked card, no minimum; `force_single_link: true` or catalog-item video + `format_option:"single_video"`.
- Catalog-card clicks bypass ad url_tags (no sub1-4) — subid capture must live in the landing builder. Set/catalog changes propagate to render with 15–60 min lag; preview popups cache — verify via API, not previews.
- APP_PROMOTION/rented WebView [MagicClick 2026]: store-shell, not web cloak — do not port PHP-white here. Apps last ~1 week then Play-dead → re-share a new app into the **live** campaign, don't rebuild. Optimize in-app Purchases (FTD), not install. Audience Network = junk. OS 10+ for payer quality, 7+ only for reach. Deep link/campaign naming is the offer router (AppsFlyer OneLink or bot) — wrong name → recreate, it caches.

**What kills the account:**
- Running gambling without A&V authorization → burn, not rejection; plan replacement pipeline.
- Optimizing to cheap regs that don't deposit — advertiser scrubs non-FTD traffic.
- Payment method reused >10× → flagged "Risks" [vendor] — card vendors → `03`.
- Broken app-event mapping → FTDs invisible, looks dead, gets killed as non-performing.

**Kill numbers** (Poisson in `senior-buyer-ops/04`; proxy ladder above is the same-day filter). Example target CPL_reg $12 (2026-08-30 field test): spend $36/0 regs kill, $57/≤1, $76/≤2; FTD verdict only on matured click-date cohorts (reg→FTD 15–25% band); spend-without-FTD stop at ~2× target CPA_FTD on matured data. Don't kill the **campaign** on one bad day or a cabinet total — prune ad sets (`01`). Dep campaign that goes silent 2–3d: pause 1–2d, restart at start budget, not scale budget (CBO sometimes recovers; not always).

**Economics (vendor bands, 2025-10/2026 sources — replace with live data):**
| Metric | Band |
|---|---|
| reg→FTD (FB traffic) | 15–25% after ~4wk warmup; FB/ASO 30–50% |
| reg→FTD (overall) | 20–50% by GEO; EU 47–50%, CIS/EE 17–19% |
| FTD as % of clicks | ~5–15% |
| Payout/FTD T1 EU | $250–500 (via FB ~$90–100, up to $500–700 high-intent) |
| Payout/FTD NA/LATAM/SEA | NA $300–500; LATAM $50–200 (low <$35); SEA $60–150 |
| RevShare alt model | 25–50% (top 55–60%) |
| Named programs (Partnerkin 2025-10, low weight) | 1Win $200–400+RS40%, Welcome.Partners $150–320, Pin-Up $100–280, Leadshub $180–350, Pelican $120–250 (no-KYC crypto) |

**GEO notes:** DE+AT first (shared EUR/PPP), CH later (higher CPM, CHF, iOS-heavier). Kill one GEO without stopping campaign: Page → Followers → Country Restrictions "Show only to…". Dated team priors (Admatrix 2026-08, replace): AR reg **$4–5**, install ~**$2**, payout **$17–24**, dep ~**$11–13** plus; ZA install **$0.20–0.40**, reg ≤**$2**, payout **$8–10**, dep **$4–7** plus; FR T1-multi (no Balkans) dep ~**$250**, install **$25–30**, reg **$40–55**.

**Funnel builders:** pwa.bot join key `{user_id}` only (no `{subid}`), usd-only postback value, CAPI dataset+token via ЛК→Аналитика, pixel off by default (inject via `fbp=<dataset_id>`). Other vendors + universal QA gates → `11-pwa-funnel-builders.md`.

**Metrics discipline:** pin which tracker event = payout (reg? FTD? qualified FTD?) before any CPA math; cohort by click date.
