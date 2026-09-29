# Modern CSS Responsive Primitives — 2026 Reference

## 1. `clamp(min, fluid, max)`
Baseline April 2020, ~97-98%.

```css
html { font-size: clamp(1rem, 0.875rem + 0.5vw, 1.25rem); }
h1 { font-size: clamp(1.75rem, 1.25rem + 2.5vw, 3.5rem); line-height: 1.1; }
.section {
  padding-block: clamp(2rem, 5vw, 6rem);
  padding-inline: clamp(1rem, 4vw, 3rem);
}
```
Pitfalls:
- Pure viewport middle (`clamp(1rem, 5vw, 2rem)`) breaks WCAG 1.4.4 — always mix `rem` into middle.
- If `max < min`, browsers silently use `min`.
- WCAG rule: `max ≤ 2.5 × min`.

Use: typography, padding, gaps, border-radius, gradient stops, widths. Don't: pixel-perfect icon sizes, grid cell counts.

## 2. `min()` / `max()`
Baseline April 2020, ~97-98%.

```css
.wrapper {
  width: min(100% - 2rem, 1200px);
  margin-inline: auto;
}
.sidebar { flex-basis: max(30%, 280px); }

/* Full-bleed inside constrained parent */
.full-bleed {
  width: min(100vw, 100%);
  margin-inline: calc(50% - 50vw);
}
```
Pitfall: `min()` picks the smaller value at compute time — `min(80%, 780px)` = "whichever is smaller now"; opposite of `min-width` intuition.

Use: max-width + padding wrapper in one line, button/modal constraints. Don't: when hard breakpoints needed.

## 3. Container queries
Baseline Feb 2023, size queries ~94-95%. Style queries Chrome/Edge only. Scroll-state Chrome 133+.

```css
.card {
  container-type: inline-size;
  container-name: card;
}
@container card (min-width: 400px) {
  .card__layout { grid-template-columns: 1fr 2fr; }
  .card__title { font-size: clamp(1.25rem, 4cqi, 1.75rem); }
}
```
Pitfalls:
- `container-type: inline-size` = layout containment → container no longer sized by children's intrinsic widths.
- Never `container-type` on `html`/`body` — breaks `vh`-based child layouts.
- `cqi`/`cqb`/`cqw`/`cqh` without eligible container ancestor silently fall back to small viewport — always pair with explicit `container-type`.

Use: reusable components in varying contexts. Don't: page-level layout — use media queries (cheaper, no containment).

## 4. `dvh` / `svh` / `lvh`
Baseline. Safari 15.4+ (Mar 2022), Chrome 108+ (Nov 2022), Firefox 101+. ~95%+.
- `svh` = UI expanded (smallest); `lvh` = UI retracted (largest); `dvh` = changes live.

```css
.hero { min-height: 100svh; }
.mobile-menu { position: fixed; inset: 0; height: 100dvh; }

/* Fallback chain */
.fullscreen {
  height: 100vh;
  height: 100dvh;
}
```
Pitfalls:
- `dvh` reflows as address bar animates — never on `font-size` or shift-prone layout.
- On-screen keyboard does NOT shrink viewport — `100dvh` ignores it. Use `visualViewport` API or `interactive-widget=resizes-content` meta.
- None account for scrollbar — `100vw` overflows by scrollbar on desktop.

Use: heroes (`100svh`), modals, full-screen menus. Don't: typography, animations, body height (breaks iOS scroll).

## 5. `aspect-ratio`
Baseline Sep 2021, ~97%.

```css
.video-embed { aspect-ratio: 16 / 9; width: 100%; }
.avatar {
  aspect-ratio: 1;
  width: clamp(48px, 8vw, 96px);
  border-radius: 50%;
  object-fit: cover;
}
.card__media { aspect-ratio: 4 / 3; }
.card__media img { width: 100%; height: 100%; object-fit: cover; }
```
Pitfalls:
- Ignored if BOTH dimensions constrained — `width: 200px; height: 200px; aspect-ratio: 16/9` does nothing.
- `min-content`/`max-content` flex/grid children can win over ratio.
- On `<img>`, intrinsic ratio from width/height attrs wins unless `aspect-ratio: auto 16/9`.

## 6. Grid `auto-fit/auto-fill` + `minmax(min(100%, Npx), 1fr)` (RAM pattern)
~98%.

```css
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));
  gap: clamp(0.75rem, 2vw, 1.5rem);
}
/* auto-fill — preserves empty tracks */
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr));
}
```
THE 320px fix: plain `minmax(250px, 1fr)` overflows < 250px viewports; `min(100%, 250px)` collapses min to 100% of parent.
- `auto-fit` collapses empty tracks (single item stretches full-width); `auto-fill` reserves them (last item stays card-width).

Use: card grids, "fit as many per row". Don't: exact column counts at breakpoints — use container queries.

## 7. Subgrid
Baseline Newly available Sep 2023. Firefox 71+, Safari 16+, Chrome 117+. ~92-93%.

```css
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1rem;
}
.card {
  display: grid;
  grid-row: span 3;
  grid-template-rows: subgrid;
  gap: 0.5rem;
}
```
Pitfalls:
- Child must span tracks FIRST: `grid-row: span 3` before `grid-template-rows: subgrid`.
- No implicit tracks — parent must define them.
- Subgrid child's gap overrides parent's gap for those tracks.

Use: card-internal alignment, label/input alignment, shared baselines. Don't: independent inner layouts — nested grid.

## 8. Logical properties
Baseline, ~96%.

```css
.container {
  padding-inline: clamp(1rem, 4vw, 3rem);
  padding-block: 2rem;
  margin-inline: auto;
  max-inline-size: 65ch;
}
.toast {
  position: fixed;
  inset-block-end: 1rem;
  inset-inline-end: 1rem;
}
.callout {
  border-inline-start: 4px solid currentColor;
  padding-inline-start: 1rem;
}
```
Pitfalls: mixing physical (`padding-left`) + logical (`padding-inline-start`) = cascade chaos; RTL flips inline-start, block-start stays top unless `writing-mode: vertical-*`.

Use in all new code. Legacy: convert in one pass, don't mix.

## 9. `:has()`
Baseline Dec 2023, ~94%.

```css
.grid:has(> :nth-child(4)) { grid-template-columns: repeat(2, 1fr); }
.form-row:has(input:required) label::after { content: " *"; color: red; }
body:has(dialog[open]) { overflow: hidden; }
.card:has(img) { grid-template-columns: 1fr 2fr; }
.card:not(:has(img)) { grid-template-columns: 1fr; }
@supports selector(:has(*)) { /* :has() rules here */ }
```
Pitfalls: invalid selector inside `:has()` invalidates the whole rule; `*:has(...)`/deep chains degrade perf in large apps.

Use: quantity queries, state-based layout, parent-conditional styling without JS.

## 10. `@supports`
Baseline 2015, ~99%. `@supports selector()` since 2022.

```css
@supports (aspect-ratio: 1) { .media { aspect-ratio: 16 / 9; } }
@supports selector(:has(*)) { .card:has(img) { grid-template-columns: 1fr 2fr; } }
@supports not (display: grid) { .layout > * { display: inline-block; width: 32%; } }
@supports (display: grid) and (gap: 1rem) { .layout { display: grid; gap: 1rem; } }
```
Pitfalls: tests syntax parsing only — can't detect feature bugs; `@supports not (X)` also true in browsers without `@supports` itself.

Use: leading-edge CSS (View Transitions, anchor positioning, `@scope`). Don't: Baseline Widely available features — dead code.
