---
name: responsive-adapter
description: Make an existing landing page, admin panel, dashboard, or any non-responsive page work at every viewport from 320px to 2560px+ without changing the visual design. Triggers on requests to make a page responsive, fix mobile layout or breakpoints, adapt a landing or admin to phones / tablets / widescreens, and on symptoms alone — horizontal scroll, elements overflowing, text unreadable on mobile, sidebar broken on tablet, empty space on widescreen — even when the word "responsive" is never used.
risk: low
source: custom
date_added: "2026-05-12"
---

# Responsive Adapter

> `$SKILL_DIR` = this SKILL.md's directory; set once per session. All script paths are relative to it.

The desktop visual is the source of truth; every other width is a graceful adaptation — layout adapts, style does not. Fixing what wasn't broken on responsiveness grounds is scope creep — report it, don't touch it.

## Allowed vs forbidden

| Allowed | Forbidden |
|---|---|
| Any CSS / Tailwind utility class | Color palette, brand colors |
| Adding `<meta name="viewport">` if missing | Font families |
| Wrapping elements (`overflow-x-auto` around a wide table) | Iconography, illustrations, content, copy |
| `hidden md:block` / `md:hidden` toggles for off-canvas menu | New components or redesigns of existing ones |
| A small hamburger toggle (≤15 lines, or native `<dialog>`) | Swapping the established UI library |
| Restructuring grid columns (`grid-cols-3` → `grid-cols-1 md:grid-cols-3`) | Removing sections that "don't fit" — adapt them |
| Replacing fixed `px` widths with fluid units | Refactor beyond what responsiveness demands |
| `aria-label` where mobile UX needs it for an icon button | |

Desktop screenshots before and after must be indistinguishable except where you intentionally stacked or collapsed.

## Breakpoints (Material 3-aligned)

```
xs 320  — ultra-small, foldable cover
sm 390  — iPhone baseline (12–16)
md 600  — M3 Compact→Medium (iPad mini portrait, phone landscape)
lg 840  — M3 Medium→Expanded (iPad portrait, foldable inner)
xl 1200 — M3 Expanded→Large (laptop)
2xl 1600 — M3 Large→XL (desktop)
```

If the project already has a system (Tailwind 640/768/1024/1280/1536, Bootstrap), **extend it, never run a second one in parallel**.

## Phase 1 — Discover

1. Identify project root; ask once if unstated.
2. Detect stack per file — `.html` + `.css` → vanilla (`references/vanilla-css.md`); `tailwind.config.*` / `@tailwind` / `md:` classes → Tailwind (`references/tailwind.md`); `styled-components` / `@emotion` / `.styled.ts` → CSS-in-JS (`references/css-in-js.md`); `*.module.css` → treat as vanilla. Mixes are common.
3. Enumerate pages/routes in scope.
4. Note the existing breakpoint conventions.
5. Open at 1440px via `agent-browser` and capture the **baseline screenshot** — the visual contract.

**Exit:** stack per file, file list, breakpoint conventions, baseline screenshot.

## Phase 2 — Static scan

```bash
bash $SKILL_DIR/scripts/scan.sh <project-root>
```

Outputs issues by severity with file:line. Full catalog and fixes: `references/anti-patterns.md`.

Caught: **A1** missing/broken viewport meta · **A2** `maximum-scale=1` / `user-scalable=no` (WCAG 1.4.4) · **A3** fixed `width: Npx` / large `min-width` · **A4** inputs `font-size < 16px` (iOS Safari auto-zoom, still present in iOS 18) · **A5** `100vh` without `dvh`/`svh` · **A8** no fluid-image baseline · **A9** bottom-fixed without `safe-area-inset-bottom` · **A13** `100vw` (includes scrollbar) · **A14** `overflow: hidden` on body.

Inspect manually: tables without an `overflow-x: auto` ancestor; sidebars always rendered open; hover-only menus without `:focus-within`; tap targets (WCAG 2.2 SC 2.5.8 AA floor 24×24, ship target 44×44 — `references/touch-targets.md`).

**Exit:** written issue list by severity with file:line.

## Phase 3 — Apply fixes

**Rule A:** modern primitives, not breakpoint salad — `clamp()`, `min()`/`max()`, container queries, `dvh/svh/lvh`, `aspect-ratio`, `grid auto-fit/minmax` (`references/modern-primitives.md`).
**Rule B:** follow the idioms of each file's stack reference from Phase 1.

Order matters — earlier fixes prevent later breakage:

1. **Foundation** — viewport meta with `viewport-fit=cover`, `box-sizing: border-box`, `-webkit-text-size-adjust: 100%`, base `font-size: 100%`, `overflow-x: clip` on html (never `hidden`, see A14), `img, svg, video { max-inline-size: 100%; block-size: auto; }`.
2. **Fluid type** — `clamp(MIN_rem, fluid_with_rem_component, MAX_rem)`, WCAG-safe `MAX ≤ 2.5 × MIN`. Never pure `vw` in the middle term — it stops responding to zoom: `clamp(1rem, 0.875rem + 1vw, 2rem)`. Formula and scales: `references/fluid-typography.md`.
3. **Containers** — `width: Npx` → `max-width: Npx; width: 100%` + `padding-inline`; centered: `inline-size: min(100% - 2rem, 1280px)`.
4. **Layout primitives** — `grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));` — the `min(100%, …)` is what makes 320px safe.
5. **Breakpoint adaptations** — stack columns, hide decorative side elements, sidebar → off-canvas drawer (`references/menus-drawers.md`), tables → scroll wrapper or cards (`references/admin-patterns.md`).
6. **Mobile nav** — prefer native `<dialog>` + `showModal()`: focus management, Escape, focus trap, top layer, `::backdrop` for free.
7. **Touch** — tap targets ≥44px at touch widths, inputs ≥16px.
8. **Safe areas** — `max(12px, env(safe-area-inset-bottom))` on bottom-fixed elements; requires `viewport-fit=cover`. See `references/platform-quirks.md`.
9. **Edge widths** — cap main content (`max-w-[1400px] mx-auto`) so ≥1920px isn't empty stretch; at 320px verify no `min-width > viewport − 2 × padding`.
10. **Query choice** — `@media` for app shell, OS preferences, `srcset sizes`, print. `@container` for reusable components adapting to their slot. Heuristic: moving the component to another slot changes styles → `@container`.

Then diff your own changes against the forbidden list. Anything that matches — revert.

**Exit:** every Phase-2 issue fixed or marked "won't fix — <reason>", no forbidden changes.

## Phase 4 — Browser verification

Static scans miss computed layouts, JS-driven UI, font fallbacks, real iOS behavior — non-negotiable: CSS that diffs clean is not a page that works at 320px.

Serve the page (`python3 -m http.server 8000` or dev script), screenshot via `agent-browser` at the minimum matrix (full list: `references/device-matrix.md`):

| 360×780 | 390×844 | 393×852 | 430×932 | 768×1024 | 1024×768 | 1440×900 | 1920×1080 |
|---|---|---|---|---|---|---|---|
| Android | iPhone 12–14 | iPhone 15/16 | Pro Max | iPad portrait | iPad landscape | designer baseline | Full HD |

Thorough QA adds 320, 884–984 (foldable inner — frequent breakage), 1280/1366, 1536, 2560/3440.

Check each screenshot for:

| Category | Checks |
|---|---|
| Layout | No horizontal scrollbar, no bleed past viewport, nothing cut off behind another element |
| Typography | Body ≥14px effective, inputs ≥16px, heading hierarchy intact |
| Tap targets | ≥24×24 with ≥8px gap (AA floor); 44×44 at ≤1024. Inline text links exempt |
| Density | Columns stacked, sidebar collapsed ≤768, tables scrolling or carded |
| ≥1920 | Content not stretched edge-to-edge, no vast empty regions |
| 320 | No `min-width > viewport − 2 × padding`; hero text not gigantic from clamp overshoot |
| Interactive | Open modal/menu/drawer at mobile widths and re-screenshot; confirm Escape, backdrop click, and close button all work |

Also re-screenshot 1440px and compare to the Phase-1 baseline — a mobile-focused request must not regress desktop.

**Exit:** a screenshot per matrix width, with annotated issues for failures.

## Phase 5 — Report

```
# Responsive Adaptation Report

## Stack detected
## Files modified — <path>:<lines> — <reason>
## Anti-patterns fixed — [SEVERITY] <name> (×N) — <how>
## Verification results — | Width | Status | Issues | for every matrix width
## Screenshots — path per width
## Won't-fix — <issue> — <reason>
## Remaining concerns
```

Done = PASS at every matrix width, desktop visually equivalent to baseline, no forbidden changes, report + screenshots delivered. Any failing width → iterate Phase 3, re-verify affected widths only, re-report. Can't reach PASS → list failing widths and blockers. Never claim done otherwise.

## Execution rules

- Surgically adapt existing CSS, however ugly. Never rewrite the page from scratch.
- Never add a CSS framework the project doesn't use.
- CSS over JS: modern primitives cover ~90% of cases; `useMediaQuery`-style hooks also cause SSR hydration flashes. Legit JS: `ResizeObserver` for canvas/charts, virtualized tables, dynamic font measurement.
- Stay in scope — don't gate work on dark mode, RTL, or reduced motion.

## References

Read only when a phase points to them.

| File | For |
|---|---|
| `anti-patterns.md` | Phase 2 — full catalog, detection + fix |
| `modern-primitives.md` | Phase 3 — clamp, min/max, container queries, dvh/svh, aspect-ratio, auto-fit, subgrid, logical props, `:has()`, `@supports` |
| `fluid-typography.md` | Phase 3 — Utopia scale, clamp formula, safe ratios |
| `device-matrix.md` | Phases 1 & 4 — full device list, what to check where |
| `design-systems.md` | Breakpoint values — Material 3 + Apple HIG |
| `admin-patterns.md` | Dashboards — sidebar collapse, tables→cards, dense forms, widget grids |
| `menus-drawers.md` | Mobile nav — `<dialog>` drawer, bottom sheet, a11y |
| `touch-targets.md` | WCAG 2.5.8 vs 2.5.5, MD3 vs HIG |
| `platform-quirks.md` | iOS Safari / Android Chrome — input zoom, safe-area, dvh, foldables |
| `tailwind.md` / `vanilla-css.md` / `css-in-js.md` | Per detected stack |
