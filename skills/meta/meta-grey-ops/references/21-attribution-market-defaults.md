# 21 — Attribution: market defaults by vertical

Research 2026-09-27 (Meta help, Jon Loomer 2025-26, Foxwell 2025, aksanov 08.2026, CPA Lenta 03.2026, FB-Killa /
Traffic Cardinal / Traffhub gambling guides, CPA.RIP, conversion.im). [К] = 2+ sources agree, [1] = single source.
Arbitrage sources are mostly 2019-2023; there is **no consensus for gambling** — the table is what people set,
not a proven optimum. Mechanics (immutable after create, `window_days`, 1885501) → `04`. `plan` WARNS on a PURCHASE ad set
without an explicit `attribution` (silent default is 1d/1d/1d, not the casino 7d click / 1d view).
`insights pull` reports 1d click / 1d view unless told otherwise, whatever the ad set uses: pass
`--action-attribution-windows 7d_click,1d_view` to match a casino ad set (`16` Inspect; `metaops review --tree` shows each ad set's `attribution_spec`).

## Pick the window (set explicitly in the spec, every ad set)

| Vertical / optimization event | Market default | Why |
|---|---|---|
| Casino, PWA/web, **Purchase (FTD)** on bid cap | **7d click / 1d view, no engage** (our field default, LA longread 25-27/09 paid FTD on it) | low Purchase volume → wider window feeds learning; Traffhub "don't touch, 7d" [1]; FB-Killa/TC say 1d click [1] — contested |
| Casino, **CompleteRegistration / Lead** | 1d click | high volume, short cycle; matches tracker [К for lead gen] |
| Nutra / COD / impulse | 1d click | [К], old sources; CPA Academy says 7d for COD [1] |
| Free leads, regs, sweeps | 1d click, view off | Loomer, Foxwell [К] |
| E-com purchase | 7d click / 1d view; if view share 25-30% test click-only, >50% switch | Foxwell [К] |
| Non-conversion goals (LINK_CLICKS, REACH…) | 1d click only (forced) | Graph rejects view windows (1885501) |
| Dating, crypto | not found | — |

Rules everyone agrees on [К]:
- The window drives BOTH reporting and what Meta learns from — one window per ad set, no "optimize on 7d,
  report on 1d". Other windows only via Compare Attribution Settings.
- Changing it on a live ad set = learning reset / not allowed via API → duplicate the ad set.
- Tracker (Keitaro) never sees view/engage conversions; closest to tracker = click-only. Money truth = tracker.

## Conversion count: All vs First

- All (default) = every conversion per person in the window; First = only the first. Selectable in the ad set
  since late 2025, only Sales → Website → Maximize conversions; else fixed All [1, Loomer 11.2025].
- If only FTD fires Purchase → setting barely matters, keep All. If redeposits also fire Purchase → All inflates
  Purchase vs tracker FTD and pulls optimization toward re-depositors (not the paid event). Check what the PWA
  sends before choosing; no buyer source on FTD vs redeposit found.

## Meta changes 2025-2026 (verify in UI before relying)

- Options: click 1d/7d, view 1d/none, engage-through 1d/none; models Standard / Incremental (windows locked) /
  Custom [Meta help 2198119873776795]. UI default 7d click + 1d engage + 1d view, All. FIELD 2026-09-27: an API-created OFFSITE_CONVERSIONS/PURCHASE ad set with NO attribution_spec reads back `[CLICK_THROUGH 7]` only — no view, no engage (account `is_attribution_spec_system_default: true`). The UI's 7d click + 1d engage + 1d view default is NOT what the API applies.
- 03.03.2026: "click" = link clicks only; likes/shares moved to engage-through, which replaced engaged-view;
  video threshold reported as 5s (older docs 10s) [К, secondary]. API event type still `ENGAGED_VIDEO_VIEW` in
  our launcher — unverified against the new naming; read back after create.
- 12.01.2026: 7d_view / 28d_view removed from Ads Insights API (reporting only) [К].
