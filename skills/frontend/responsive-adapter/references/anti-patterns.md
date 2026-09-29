# Responsive Anti-Patterns — Catalog & Fixes

## A1. Missing/broken viewport meta
- Detect: no `<meta name="viewport">` in `<head>`, or `width` ≠ `device-width`.
- Symptom: mobile renders at 980px logical width, shrink-fit; fluid CSS frozen; sub-pixel tap targets; `100vw` broken.
- Fix:
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```
`viewport-fit=cover` REQUIRED for `env(safe-area-inset-*)` to be non-zero on notched / Dynamic-Island devices.

## A2. Disabled pinch-zoom (WCAG 1.4.4 violation)
- Detect: `maximum-scale=`, `minimum-scale=`, `user-scalable=no` in viewport meta. Lighthouse + axe-core flag automatically.
- Fix: remove the attributes. If suppressing iOS input zoom → fix A4 root cause instead.

## A3. Fixed px width / `min-width` lock-out
- Detect: `width:\s*\d{3,}px` on containers; `min-width:\s*\d{3,}px` on layout elements. `min-width` is silent — nothing overflows at desktop sizes.
- Symptom: element won't shrink → body blowout, horizontal scroll below the value.
- Fix:
```css
.container { width: 100%; max-width: 75rem; margin-inline: auto; }
.card      { min-width: 0; inline-size: 100%; }
/* min-width: 0 MANDATORY on flex/grid children wrapping long content */
```

## A4. Inputs `font-size < 16px` (iOS auto-zoom)
- Detect: `input`, `textarea`, `select`, `[contenteditable]` with font-size < 16px.
- Symptom: iOS Safari zooms viewport on focus, never zooms back. Reproduces iOS 18 / iPhone 16 (late 2025).
- Fix (simple):
```css
input, textarea, select { font-size: 16px; }
```
Fix (14px visual mandatory):
```css
@supports (-webkit-touch-callout: none) {
  input, textarea, select {
    font-size: 16px;
    transform: scale(0.875);
    transform-origin: left top;
  }
}
```
Never fix with `maximum-scale=1` — see A2.

## A5. `100vh` on mobile
- Detect: `height:\s*100vh` / `min-height:\s*100vh` on hero/full-screen elements.
- Symptom: `vh` = largest viewport (chrome retracted) → taller than screen with URL bar visible. iOS 18 still doesn't update `window.innerHeight` when address bar expands.
- Fix:
```css
.hero {
  height: 100vh;       /* old-browser fallback */
  height: 100svh;      /* small viewport — stable, no jank */
  min-height: 100dvh;  /* if fill needed */
}
```
- `svh` = chrome visible — hero default, no jank
- `lvh` = chrome hidden — immersive full-bleed
- `dvh` = dynamic — NEVER animate to/from `dvh` (jitter)
Baseline since June 2025.

## A6. Tap targets < 44 CSS px
- Detect: interactive elements (button, a, [role=button], input[type=checkbox/radio/submit]) < 44px on mobile widths.
- Symptom: fails WCAG 2.2 SC 2.5.8 (24×24 minimum). 25%+ mis-tap rate per Apple research.
- Fix:
```css
.icon-btn {
  inline-size: 44px;
  block-size: 44px;
  display: inline-grid;
  place-items: center;
}
/* Extend hit area without growing visual: */
.icon-btn { position: relative; }
.icon-btn::before { content: ""; position: absolute; inset: -10px; }
```

## A7. Tables without overflow wrapper
- Detect: `<table>` not in an `overflow-x` element, or wrapper lacks `role="region"` + `tabindex="0"`.
- Symptom: wide table forces body-level horizontal scroll.
- Fix:
```html
<div role="region" aria-labelledby="tbl-cap" tabindex="0" class="table-wrap">
  <table>
    <caption id="tbl-cap">Q4 results</caption>
    ...
  </table>
</div>
```
```css
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.table-wrap:focus-visible { outline: 2px solid currentColor; }
```
`tabindex="0"` + `role="region"` exposes scroll area to keyboard + AT.

## A8. Non-fluid images
- Detect: `<img>` without `max-width: 100%` applying.
- Symptom: image renders at intrinsic width, widens viewport.
- Fix:
```css
img, svg, video, canvas {
  max-inline-size: 100%;
  block-size: auto;
}
```
Keep `width`/`height` HTML attrs — CLS-preventing aspect-ratio reservation.

## A9. `position: fixed` ignoring mobile chrome
- Detect: `position: fixed; bottom: 0` (or `inset: auto 0 0 0`) without `env(safe-area-inset-bottom)`.
- Symptom: sits under iOS home indicator / Android nav gestures.
- Fix:
```css
.bottom-nav {
  position: fixed;
  inset: auto 0 0 0;
  padding-block-end: max(12px, env(safe-area-inset-bottom));
}
```
Sticky inside `overflow: auto` or transformed ancestors breaks on iOS Safari (bug through iOS 18).

## A10. Sidebars always rendered open
- Detect: `aside`, `nav`, `.sidebar` fixed width, no responsive collapse.
- Fix:
```css
.layout { display: grid; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 64rem) {
  .layout { grid-template-columns: 18rem minmax(0, 1fr); }
}
```
Mobile sidebar reveal → `<dialog>` + `showModal()` — see `menus-drawers.md`.

## A11. Hard-coded `px` everywhere
- Detect: `font-size`, `padding`, `margin` in px on typography/layout elements.
- Symptom: user text-size prefs and zoom >200% can't rescale UI — defeats WCAG 1.4.4.
- Fix:
```css
:root { font-size: 100%; } /* respect user default */
.heading {
  font-size: clamp(1.5rem, 1rem + 2vw, 2rem);
  padding-block: 1.5rem;
  padding-inline: 1rem;
}
```
`rem` for type/spacing, `clamp()` for fluid scaling, `em` for component-local rhythm.

## A12. `text-align: justify` on narrow widths
- Detect: `text-align: justify` without wide-screen media query.
- Symptom: rivers, illegible on mobile, harms dyslexic readers.
- Fix:
```css
p { text-align: start; hyphens: auto; }
@media (min-width: 60rem) {
  .prose p { text-align: justify; hyphens: auto; }
}
```

## A13. Horizontal scroll from transforms / negative margins
- Detect: `margin-left:\s*-?\d+vw`, `width:\s*100vw`, `transform.*scale\s*\(\s*[\d.]+\s*\)` on full-bleed sections.
- Symptom: `100vw` includes scrollbar width on desktop; transformed full-bleeds escape parent clipping.
- Fix:
```css
html { overflow-x: clip; }   /* `clip` does NOT create scroll container, unlike `hidden` */
.full-bleed {
  width: 100%;
  margin-inline: calc(50% - 50cqw); /* container-relative */
}
```
`overflow: clip` (Baseline) preferred — `overflow: hidden` on `<body>` breaks descendant `position: sticky`.

## A14. `overflow: hidden` on body as "fix"
- Detect: `body { overflow-x: hidden }` or `html { overflow-x: hidden }`.
- Symptom masking: disables `position: sticky` below, breaks scroll restoration, doesn't fix root overflow.
- Fix: find offender via `* { outline: 1px solid red; }`; fix root cause (A3/A8/A13). If clipping required → `overflow-x: clip` on `html`.

## A15. Hover-only interactions on touch
- Detect: `:hover` reveals interactive content (menus, action tooltips) without `:focus-within` or tap fallback.
- Symptom: touch first-tap simulates hover → double-tap, no affordance; stylus/keyboard blocked.
- Fix:
```css
.menu:has(:focus-within) .submenu,
.menu:hover .submenu { display: block; }
@media (hover: none) and (pointer: coarse) {
  .menu .submenu { /* always show or aria-expanded-driven */ }
}
```
Gate hover-only effects: `(hover: hover) and (pointer: fine)`.

## A16. Mobile-only z-index regressions
- Detect: mobile menu/dialog behind sticky header or under iOS URL bar overlay.
- Cause: stacking contexts from `transform`, `opacity < 1`, `filter`, `will-change`, `backdrop-filter` reset z-index inside themselves.
- Fix: `<dialog>` + `::backdrop` (top layer escapes all stacking contexts); else audit ancestors.

## A17. `<meta http-equiv="X-UA-Compatible">` (legacy)
- Detect: `<meta http-equiv="X-UA-Compatible" content="IE=edge">`.
- Fix: remove. No effect 2026.

## Lint-checkable rules (static scan; first 3 catch ~70% of sins)
1. `width:\s*\d{3,}px` on layout containers without `max-width: 100%`
2. `maximum-scale=1|user-scalable=no` in viewport meta
3. `input|textarea|select.*font-size:\s*(0\.\d|1[0-5])(px|rem)` (< 16px inputs)
4. No `<meta name="viewport">` in `<head>`
5. `<table>` not wrapped in `overflow-x:auto` ancestor
6. `100vh` without `dvh`/`svh` fallback
7. `position:\s*fixed.*bottom` without `safe-area-inset-bottom`
8. Sidebar `width:\s*\d+(px|rem)` with no media query collapsing it
