# Vanilla CSS / CSS Modules — Responsive Patterns

## Breakpoint strategy (em in media queries)
`em` in `@media` resolves against the BROWSER default font size (rem/px don't) — user font-size prefs scale breakpoints too.

```css
:root {
  --bp-sm: 24.375em;  /* 390px */
  --bp-md: 37.5em;    /* 600px — M3 Compact→Medium */
  --bp-lg: 52.5em;    /* 840px — M3 Medium→Expanded */
  --bp-xl: 75em;      /* 1200px — M3 Expanded→Large */
  --bp-2xl: 100em;    /* 1600px — M3 Large→Extra-large */
}

@media (min-width: 37.5em) { /* md */ }
```

## Reset / foundation (drop-in)

```css
*, *::before, *::after { box-sizing: border-box; }

html {
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
  font-size: 100%;       /* respect user default */
  scroll-behavior: smooth;
  overflow-x: clip;      /* preferred over hidden */
}

body {
  margin: 0;
  min-height: 100dvh;
  line-height: 1.5;
  font-family: system-ui, -apple-system, sans-serif;
}

img, picture, video, canvas, svg {
  display: block;
  max-inline-size: 100%;
  block-size: auto;
}

input, button, textarea, select {
  font: inherit;
  font-size: 16px;      /* iOS zoom prevention */
  min-block-size: 44px; /* touch target */
}

button { min-inline-size: 44px; cursor: pointer; }

h1, h2, h3, h4, h5, h6 {
  text-wrap: balance;
  line-height: 1.1;
}

p { text-wrap: pretty; max-inline-size: 65ch; }

:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
```

## Container one-liner (no media queries)

```css
.container {
  inline-size: min(100% - 2rem, 75rem);
  margin-inline: auto;
}
```
Narrow: `100% - 2rem` (32px gutters). Wide: caps at `75rem` (1200px).

## Auto-fit RAM grid (320px-safe)

```css
.grid {
  display: grid;
  gap: clamp(0.75rem, 2vw, 1.5rem);
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));
}
```
`min(100%, 16rem)` — below 16rem (256px) min collapses to 100%, killing horizontal scroll.

## Container queries

```css
.card-wrap {
  container-type: inline-size;
  container-name: card;
}
@container card (min-width: 32rem) {
  .card { display: grid; grid-template-columns: 12rem 1fr; }
  .card__title { font-size: clamp(1.25rem, 4cqi, 1.75rem); }
}
```
Use `cqi` (not `cqw`) for writing-mode safety.

## Fluid type scale (Utopia-style)

```css
:root {
  --step--1: clamp(0.83rem, 0.80rem + 0.17vw, 0.94rem);
  --step-0:  clamp(1rem,    0.96rem + 0.22vw, 1.13rem);
  --step-1:  clamp(1.20rem, 1.14rem + 0.29vw, 1.41rem);
  --step-2:  clamp(1.44rem, 1.36rem + 0.40vw, 1.76rem);
  --step-3:  clamp(1.73rem, 1.61rem + 0.57vw, 2.20rem);
  --step-4:  clamp(2.07rem, 1.91rem + 0.80vw, 2.75rem);
  --step-5:  clamp(2.49rem, 2.26rem + 1.14vw, 3.43rem);
  --step-6:  clamp(2.99rem, 2.66rem + 1.62vw, 4.29rem);
}
body { font-size: var(--step-0); }
h1 { font-size: var(--step-6); }
h2 { font-size: var(--step-5); }
h3 { font-size: var(--step-4); }
h4 { font-size: var(--step-3); }
h5 { font-size: var(--step-2); }
h6 { font-size: var(--step-1); }
small { font-size: var(--step--1); }
```

## Sidebar layout

```css
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}
@media (min-width: 64em) {  /* 1024px */
  .layout { grid-template-columns: 18rem minmax(0, 1fr); }
}
@media (max-width: 63.99em) {
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    inline-size: 85vw;
    max-inline-size: 20rem;
    transform: translateX(-100%);
    transition: transform 200ms ease;
    background: var(--bg);
    z-index: 100;
  }
  .sidebar[data-open] { transform: translateX(0); }
}
```
Accessible drawer → prefer `<dialog>` — see `menus-drawers.md`.

## Every-layout primitives (Heydon Pickering, every-layout.dev) — responsiveness without media queries

```css
/* Stack — vertical rhythm */
.stack > * + * { margin-block-start: var(--space, 1rem); }

/* Cluster — wrapping inline items */
.cluster {
  display: flex; flex-wrap: wrap;
  gap: var(--gap, 1rem);
  align-items: center;
}

/* Switcher — single column below 30rem threshold */
.switcher {
  display: flex; flex-wrap: wrap;
  gap: var(--gap, 1rem);
}
.switcher > * {
  flex-grow: 1;
  flex-basis: calc((30rem - 100%) * 999);
  /* container < 30rem → basis goes negative-huge, forces wrap */
}

/* Center */
.center {
  box-sizing: content-box;
  margin-inline: auto;
  max-inline-size: 60ch;
  padding-inline: 1rem;
}

/* Sidebar — stacks below threshold */
.sidebar-layout { display: flex; flex-wrap: wrap; gap: 1rem; }
.sidebar-layout > :first-child {
  flex-basis: 16rem;
  flex-grow: 1;
}
.sidebar-layout > :last-child {
  flex-basis: 0;
  flex-grow: 999;
  min-inline-size: 50%;
}
```

## `@media` vs `@container`

| Use `@media` for | Use `@container` for |
|------------------|----------------------|
| Page-level layout (sidebar+main+aside) | Reusable components in varying contexts |
| Nav paradigm switch | Card adapting to sidebar vs main column |
| OS preferences (`prefers-*`) | Component-local typography scaling |
| Print styles | Widget showing/hiding sub-views |
| Image `srcset` `sizes` (no `@container` option) | Component-internal grid switches |

Heuristic: removing component from page changes applicable styles → `@container`; only browser resize does → `@media`.
