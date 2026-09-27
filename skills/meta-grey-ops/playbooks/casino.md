# Playbook — iGaming / Casino / Betting

Reviewed 2026-09-19. Vendor/team numbers below are directional priors — replace with live data.
Execution mechanics → `00`; structures/leftover reset → `04`; scale mode → `senior-buyer-ops/01`.
Practitioner block (Admatrix 2026-08/09: T1 DE/FR-multi + T3 AR/ZA) is labelled; not a platform rule.

**Gate:** A&V authorization + per-jurisdiction licence, filed before any ad exists, intent declared per new territory. 19 no-gambling markets, social-casino carve-out → `10`. Approvals bind to portfolio+account — replacement account needs new approval (`09`).

**Placements:** manual, FB `feed, story, facebook_reels` + IG `stream, story, reels`; drop Audience Network, Messenger, Marketplace, search, in-stream, profile feed, Explore. Field KG 2026-09-21..25: every reg/FTD came from FB Feed + Reels; practitioners (Partnerkin/Magic Click, CPALenta 2026) name AN the budget sink. Change on live ad sets with `metaops edit targeting --publisher-platforms … --facebook-positions … --instagram-positions …`. Expect re-review: a targeting edit put a live ad back through review and it came back DISAPPROVED (`19` §4, field 2026-09-22).

**Objective/event:** OUTCOME_LEADS → optimize CompleteRegistration first (FTD too sparse on small budgets); switch to Purchase (FTD) at ~20–30 FTD via a NEW campaign. Counter-example, FIELD 2026-09-27 (US, Louisiana longread, PWA, n=1): OUTCOME_SALES + OFFSITE_CONVERSIONS `PURCHASE` from day one, CBO, bid cap $200 → 26/09 €103 spend, 22 installs, 17 regs, 6 FTD (reg→dep 35%, install→dep 27%). Prior stands; one GEO/day is not a rule flip. **Payout KPI = CPA per FTD** always (click-date cohorts). T3 *operating* KPI = reg CPA (CR stable enough that dep closes); T1 operating = full chain.

**Attribution (set explicitly in every spec, immutable after create):** Purchase (FTD) → `{"click_days": 7, "view_days": 1}` (no engage); CompleteRegistration → `{"click_days": 1}`. Contested in the market, field-default only — `21`. Conversion count All unless the PWA fires Purchase on redeposits.

**Funnel/tracking:** FB/IG ad → pre-lander → casino LP or PWA/WebView, or FB→Telegram bot→deposit.
- PWA/H5/web-checkout: WEB tracking (tracker postback + Pixel/CAPI, carry fbclid through smart-link) — no app-store gate.
- FB→TG bot: no Pixel; CAPI from bot with a short token, not raw fbclid (tracker-ops/03).
- Native app: MMP (AppsFlyer/Adjust) SDK → S2S to Meta (needs UA+IP); pin which MMP event = FTD, mirror to tracker.
- Messenger/ManyChat: still CTM greeting+thread gate (`07`) — not a review skip.

**T1 vs T3 (operating split, not just payout):** T3 buys more tests per $ — primary KPI is **reg CPA** (CR more stable than T1; same-day dep CPA is noise until lag lands). T1: judge the full chain, campaigns often live hours not days. Start budget: T3 **$15–20**; T1 either **$100–150** test / **$250–350** proven, or ≈ CPA payout ($300–500 on a ~$250 FTD GEO). Weak/new account (thin spend history): start smaller, one campaign create per ~3h, optionally first launch in UI (FIELD 2026-09-27, `16` § Pacing). iOS slack vs Android/PWA: all metrics dearer — unique-click hold ~2× the Android bar on first tests. T3 localization of **currency + language + brand** is mandatory; EN free-spin leftovers underperform. Switch offers on **live CR**, not a single payout number.

**Proxy ladder** (fast events; payout still Poisson in `senior-buyer-ops/04`). From CPA payout: unique click ≈ **2%**, install **10%**, reg **20%**, then fold min ROI 20–30%. Attention-kill before that: ~**100–150 impressions / 0 clicks**, or T1 **~$10 spend / 0 link click** (don't wait for install price); T3 Africa ~**$2.50 / 0 regs**. CTR <0.5% is a screen, not a religion — expensive uniques with holding click→install / install→reg / reg→dep are often the better audience. ~**10–15% of deps never reach FB**; T3 lag **15–20% over 3–7d**; push **+5–10%** late deps. FB credits the *arrival* day, not the click day — day-1 loss in Ads Manager is not a kill (`tracker-ops/03`).

**Creative:** real **provider gameplay** (scatter / win-screen / slot recording) + offer bonus; recut “fake slot” loses message-match and traffic quality. Static = fewer rejects; motion/UGC = better dep CPA — split the test, don't default one. Refresh a depositing static as a **new file** (AI-animate / metadata variant) — don't edit the live ad (re-review, `04`). Spy-dump of a competitor's slot pack without a test plan is not a test. Setup matrix (1-1-1 / 1-5-1 same vs different / 1-3-3) → `04`. New GEO: **~3 cabinets**, not one (cabinet hook ≠ creative hook). Crash on creatives: higher CTR/reg, worse LTV, T1 advertisers often refuse; slots inverse [Traffic Cardinal 2026-02].

**Creative packaging** (ad + PWA *user* path; catalog/review camouflage stays in `07`). Three approaches in the wild. Sources 2026-01–09 practitioner/vendor (PWA.GROUP, Partnerkin, Affhub, LeadGenerals) — **not RCT**; no published logo-X vs no-logo vs local-spoof → FTD. Re-check on live CR before scaling.

| Approach | User sees | When it wins | Trap |
|---|---|---|---|
| **Game-first** | Slot/crash identity (Olympus, Chicken Road, Bonanza…); no casino logo | Offer brand unknown locally; want to swap offers without rebuilding the PWA | Game on the creative must exist on the offer |
| **Offer-branded** | Same logo as the actual offer LP, ad→PWA→offer | Brand is already known in-GEO | Unknown-brand logo adds no trust; leftover EN/foreign-currency packs underperform |
| **Local-brand camouflage** | GEO-famous operator (legal or grey household name) on ad+PWA; traffic to another offer | T3 where users actually know that brand — CTR/trust hook | Creative X → offer Y (or bonus/game not on the offer) ↑CTR ↓FTD. Meta Ad Standards: product on the ad must match the LP. Don't spoof a state/licensed operator you don't represent |

Match that repeats across those sources: **game + bonus + currency + language + payment marks** identical ad→PWA→offer. Casino logo is secondary. Unlocalized foreign PWA: claimed 2–3× CR drop. Local payment in onboarding: +25–40% dep CR [Affhub 2026-01]. Custom PWA visual vs stock: unique-click→install target **≥25–30%**, stock loses [practitioner 2026-04]. Split **3 PWA visuals per offer**. **PWA brand = the casino named in the texts/creatives** — FIELD 2026-09-27: a Florida PWA carried "Florida Lottery" state branding → not launched (government-brand impersonation). T1: UGC + real provider gameplay, licence-looking UX. T2: game-first + local currency/faces. T3: currency+language+**brand** mandatory (same line as T1 vs T3 above).

**Review traps:**
- Catalog camouflage (TR field-tested 2026-08-30): ≥4-product-set limit is Collection-format-only (error 2490457); submit with all-white cards, slot arts pre-uploaded but out-of-set, swap via API filter post-approval — no re-review. Gate and read-back: `00` 9.7. Never let set drop below 4. Alt: 1-product set renders as single deep-linked card, no minimum; `force_single_link: true` or catalog-item video + `format_option:"single_video"`.
- **State-split reject = content/brand/state, not account** [field 2026-09-25, n=1]: US-FL `link_video` casino ads rejected "Online Gambling and Games" on two different ad accounts (same video; byte-uniquified copy too), while US-IN with the same text template approved. Don't burn more accounts or re-uniquify. The same FL creative then PASSED inside a DLO (EN target slot + exotic default + white video, `07`): all 3 ads approved within ~50-60 min. Rejected ad → switch it off; never re-upload the same rejected creative/angle/PWA into the account that rejected it (FIELD 2026-09-27 rule — the DLO pass above is not a licence for that).
- Catalog-card clicks bypass ad url_tags (no sub1-4) — subid capture must live in the landing builder. Set/catalog changes propagate to render with 15–60 min lag; preview popups cache — verify via API, not previews.
- APP_PROMOTION/rented WebView [MagicClick 2026]: store-shell, not web cloak — do not port PHP-white here. Apps last ~1 week then Play-dead → re-share a new app into the **live** campaign, don't rebuild. Optimize in-app Purchases (FTD), not install. Audience Network = junk. OS 10+ for payer quality, 7+ only for reach. Deep link/campaign naming is the offer router (AppsFlyer OneLink or bot) — wrong name → recreate, it caches.

**What kills the account:**
- Running gambling without A&V authorization → burn, not rejection; plan replacement pipeline.
- Optimizing to cheap regs that don't deposit — advertiser scrubs non-FTD traffic.
- **Buying installs far under the GEO band.** A CPI well BELOW the local band is a defect signal,
  not efficiency: you are winning only inventory the rest of the auction declines. See
  § Price-vs-quality below.
- Payment method reused >10× → flagged "Risks" [vendor] — card vendors → `03`.
- API write bursts + retry loops on a weak account. FIELD 2026-09-27 (n=1, cause not proven): the
  account with 4 CBO launches in hours (two an hour apart) and a 12-min 17/2446079 retry storm, $43
  lifetime, was disabled "automation that doesn't follow our rules"; siblings on the same token/Page/
  domain lived. Pacing → `16` § Pacing, `02` §8.
- Broken app-event mapping → FTDs invisible, looks dead, gets killed as non-performing.

**Price-vs-quality — read the price you PAID before blaming the funnel.** A funnel-stage
collapse and a traffic-quality collapse look identical in a report; the unit price separates them.
Order of diagnosis:

1. Split the chain: click->install, install->reg, reg->FTD (bands in `11`).
2. If the UPSTREAM stage is inside its band and a downstream one is far outside it, the creative,
   the PWA and the cloak are all doing their job. Do not start rebuilding them.
3. Then compare CPI/CPL against the GEO band. **Far below band = the cause.** Cheap installs are
   cheap because nobody else bid on those users.
4. Only if the price is inside the band is the downstream stage genuinely broken (onboarding,
   payments, offer antifraud, `11` QA gate 6).

FIELD CASE 2026-09-23 (TR, King Royal, pwa.bot, CBO): click->install **28%** (band 20-35%, fine),
install->reg **11.5%** (band 40-60%), reg->FTD **3.6%** (band 10-20%), click->FTD **0.1%** (band
3-7%) — read as a PWA/offer leak for three days. CPI was **$0.84** against a TR field ceiling of
$4 and a PWA band of $0.50-1.80: bottom of every band. Co-cause, not sole cause: no ad set had
ever exited learning (`04`, ad-set budget floor). `[inference from the band spread; the causal
link was not isolated by a controlled test — unverified]`

**Kill numbers** (Poisson in `senior-buyer-ops/04`; proxy ladder above is the same-day filter). Example target CPL_reg $12 (2026-08-30 field test): spend $36/0 regs kill, $57/≤1, $76/≤2; FTD verdict only on matured click-date cohorts (reg→FTD 10–20% band, `11`); spend-without-FTD stop at ~2× target CPA_FTD on matured data. Don't kill the **campaign** on one bad day or a cabinet total — prune ad sets (`01`). Dep campaign that goes silent 2–3d: pause 1–2d, restart at start budget, not scale budget (CBO sometimes recovers; not always).

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

**GEO notes:** DE+AT first (shared EUR/PPP), CH later (higher CPM, CHF, iOS-heavier).
**TR** (public practitioner numbers, gathered 2026-09-23 — CPAMonstro $4k/30d case + affhub;
vendor-grade, not audited): structure `1-1-1` on a weak account / `1-3-1` on a strong one;
**$30-40 per AD SET**, raised to $60-70 once it performs — note that is per ad set, not per
campaign, and it is ~5x what a $30 CBO split four ways delivers. CPI ceiling **$4**, CPL norm up
to **$8**, install->reg **~1:2 (50%)**, FTD cost **$20-60**. That case optimized on `Purchase`
(FTD) and reported 106 FTD at ~100% ROI; the wider consensus (Alfaleads) is still
`CompleteRegistration`, because FTD volume is too sparse for the pixel on one account — which is
the same rule as § Objective/event above. Age 25-45 men, Android 10+ for payer quality. Kill one GEO without stopping campaign: Page → Followers → Country Restrictions "Show only to…". Dated team priors (Admatrix 2026-08, replace): AR reg **$4–5**, install ~**$2**, payout **$17–24**, dep ~**$11–13** plus; ZA install **$0.20–0.40**, reg ≤**$2**, payout **$8–10**, dep **$4–7** plus; FR T1-multi (no Balkans) dep ~**$250**, install **$25–30**, reg **$40–55**.

**Funnel builders:** pwa.bot join key `{user_id}` only (no `{subid}`), usd-only postback value, CAPI dataset+token via ЛК→Аналитика, pixel off by default (inject via `fbp=<dataset_id>`). Other vendors + universal QA gates → `11-pwa-funnel-builders.md`. Team PWAs (FIELD 2026-09-27): designers build them; the buyer only sets domain, naming, countries, pixel, activates.

**Metrics discipline:** pin which tracker event = payout (reg? FTD? qualified FTD?) before any
CPA math; cohort by click date. Keitaro (FIELD 2026-09-27): `leads` = regs not yet deposited (lead→sale
flips in place), total regs = leads + sales; money = `sale_revenue`; a campaign CPA-auto cost model adds
fake cost; cost push accepts EUR → `tracker-ops/01`. **The Meta event NAME carries no meaning** — it is whatever string
the funnel builder was configured to send, and builders differ: `CompleteRegistration` maps to the
real registration on pwa.bot (`11`) but is wired to the INSTALL on plenty of other setups. Never
infer the mapping from the name. Verify it by count-matching a day of Meta pixel events against
the same day in the builder's own panel (e.g. `Lead` 101 vs panel "Installs" 101, field-checked
2026-09-20), and match EVERY stage you will make decisions on, not just the easy top one — a
top-stage match does not prove the deeper mapping. Until reg is count-matched against the
advertiser's own reg count, an "install->reg leak" may just be a different denominator.

**Catalog texts — where they live (operator 2026-09-26, after B showed the PWA white page title under a casino card):**

| what the viewer sees | set in | follows the swap |
|---|---|---|
| image | catalog item | yes |
| card headline | creative `template_data.name` = `{{product.name}}` → the ITEM's name | yes (only via the tag) |
| card description | creative `template_data.description` = `{{product.description}}` → the ITEM's description | yes (only via the tag) |
| primary text above the card | creative `message`, fixed | never → `-----` |
| ad set | holds no texts | — |

So the texts are written in the CATALOG ITEMS: white wording in the white item (what review reads),
casino wording in the target item (what runs after the swap). The creative only carries the tags.
Do NOT put target wording into the creative from the start: review would read casino text under a
white card. (A/C got "Spam" on 26.09 hours AFTER the swap, with casino items live: a post-swap re-check exists.) A creative without the tags keeps a fixed text, or Meta
scrapes the link page `<title>`, and editing it later re-reviews the ad.

Enforced (`meta-grey-ops`): `launch.py` refuses a wordy `message` or a static headline/description
(overrides `allow_message` / `allow_static_text`); `plan` refuses white items with empty texts or
gambling words (`swapgate.TARGET_WORDS`; override `creative.allow_white_text`) and target SKUs
(`swap_to`) without name/description/image; `verify` diffs message/headline/description/cta;
`assets swap` refuses ads without the tags.
