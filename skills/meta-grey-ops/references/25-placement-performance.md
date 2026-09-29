# 25 — Reading placement performance (which placements to keep)

Written 2026-09-29. Money truth is the tracker; Meta placement columns only tell you where spend went.

**Sources.**
- Keitaro: the ad link carries `placement={{placement}}` → `sub11` (e.g. `Facebook_Mobile_Feed`);
  report by `sub11` with `sale_revenue`, sales (= deposits), regs = leads + sales, cost from the push
  (`tracker-ops/01`). Cohort on click date, matured days only.
- Ads Manager: Breakdown → By delivery → Placement (or Platform + Placement in Ads Reporting for the
  two-way split, `meta-ads/02` §6/§8) for spend / impressions / link clicks. Export CSV.
  `metaops insights pull --breakdown publisher_platform,platform_position --time-increment all_days`
  does the same read (`16` Inspect). Insights `platform_position` names differ from targeting names and from `{{placement}}`: seen 2026-09-29 on CF1 `facebook/feed`, `facebook/facebook_profile_feed`, `instagram/instagram_stories`, `instagram/instagram_reels`; Keitaro `sub11` so far only `Facebook_Mobile_Feed` (= `facebook/feed`), the other mappings are unverified until those clicks land. `analyze_ads_export.py` (as reviewed 2026-09-29) prints totals and top
  rows per CSV row, with no Platform+Placement key, no per-entity aggregation and no currency check: read
  the Platform and Placement columns yourself.
- Empty `sub11` happens in some ASC/catalog configs (`11`): count unlabeled rows separately.

**Decision rule.**
1. Join by placement: spend (Meta) ÷ sales and regs (Keitaro). Same currency, account-tz day, click date.
2. Keep every placement until it has spent ~2× target CPA_FTD on matured data with 0 sales
   (`casino.md` kill numbers; Poisson ladder `senior-buyer-ops/04`). CTR, CPC and "few results" are not a
   reason (`meta-ads/04` §3: removing cheap assist placements usually raises cost).
3. ~10-15% of deps never reach FB and the WebView strips pixel events (`casino.md`): Keitaro sale counts win.
4. Field: KG 2026-09-21..25 every reg/FTD came from FB Feed + Reels (one GEO, n=1). No US placement read
   is recorded yet; do not copy it.

**Acting on it.**
- Narrow through a NEW ad set with `placements` / explicit positions (`SKILL.md`), not by editing a
  live one: a targeting edit re-reviewed a live ad and it came back DISAPPROVED (2026-09-22).
- Never drop Instagram entirely (operator rule); never add Audience Network / Messenger / Threads.
- Exclusions leak: "Allow limited spending to excluded placements" lets Meta spend up to 5% per excluded
  placement, and Meta is removing ad-set exclusions (progressive, account-dependent, unverified per
  account). Expect some spend on placements you excluded.
