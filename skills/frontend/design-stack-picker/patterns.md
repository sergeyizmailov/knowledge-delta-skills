# Code patterns

Copy-paste starting points. Adapt token values to the chosen aesthetic — keep the structure.

## Existing project integration

Map each pattern to the codebase first:

- Existing tokens → extend/rename these variables, never a parallel set.
- Existing icon wrapper → add names to it, never a second icon system.
- Fonts load in root layout → update that flow, no extra `<link>` in components.
- Images go through a framework pipeline → use it, not raw `<picture>`.
- Astro/static project → `.astro` + scoped CSS + small progressive scripts over React-only primitives.
- Existing Tailwind/theme tokens → translate these CSS vars into that system, don't mix.

Use as **shape**, not forced theme.

---

## Tokens — semantic CSS custom properties

Define once on `:root`; semantic names (surface/ink/brand/line/state), not raw colors. One dominant brand + sharp accent. Fluid scales via `clamp()`.

```css
:root {
  /* Surfaces (light → darker) */
  --bg: #ffffff;
  --bg-soft: #f6f7f9;
  --bg-card: #f3f4f6;
  --bg-card-hover: #eef0f3;
  /* Ink (strong → faint) */
  --ink: #1f2430;
  --ink-2: #565d6d;
  --ink-3: #9aa1ae;
  --on-brand: #ffffff;
  /* Brand: ONE dominant + gradient + tint */
  --brand: #ff6b6b;
  --brand-strong: #fb5a5f;
  --brand-soft: #ffecec;
  --brand-grad: linear-gradient(135deg, #ff8e8e 0%, #fb5a5f 100%);
  /* Lines */
  --line: #e9ebef;
  --line-strong: #dde0e6;
  /* Shadows — layered + brand-tinted (see Shadows) */
  --shadow-sm: 0 1px 2px rgba(31, 36, 48, 0.04);
  --shadow:    0 8px 28px -14px rgba(31, 36, 48, 0.18);
  --shadow-lg: 0 24px 60px -24px rgba(31, 36, 48, 0.28);
  --shadow-brand: 0 14px 30px -12px rgba(251, 90, 95, 0.5);
  /* State */
  --ok: #1fae6a;  --ok-soft: #e6f6ee;
  --warn: #d9892b; --warn-soft: #fbf0df;
  /* Radii */
  --r-xs: 8px; --r-sm: 12px; --r: 18px; --r-lg: 26px; --r-pill: 999px;
  /* Type */
  --font-sans: "Onest Variable", system-ui, sans-serif;     /* body */
  --font-display: "Unbounded", var(--font-sans);            /* headings */
  /* Fluid layout (Utopia-style) */
  --container: 1340px;
  --gutter: clamp(16px, 4vw, 48px);
  --header-h: 72px;
}
```

Full fluid type+space scale: generate at https://utopia.fyi, paste here (keep min/max in `rem` so zoom works).

---

## Reset — modern, minimal

```css
* { box-sizing: border-box; }
html { scroll-behavior: smooth; text-size-adjust: 100%; overflow-x: clip; }
body {
  margin: 0; min-height: 100dvh;
  font-family: var(--font-sans); font-size: 16px; line-height: 1.55;
  color: var(--ink); background: var(--bg);
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
h1, h2, h3, h4 {
  margin: 0; font-weight: 700; line-height: 1.1;
  letter-spacing: -0.02em; color: var(--ink); font-family: var(--font-display);
}
p { margin: 0; }
a { color: inherit; text-decoration: none; }
img, svg, video, canvas { display: block; max-inline-size: 100%; block-size: auto; }
button { font-family: inherit; cursor: pointer; border: none; background: none; }
input, button, textarea, select { font: inherit; }
input, textarea, select { font-size: 16px; }  /* prevents iOS zoom */
ul { margin: 0; padding: 0; list-style: none; }
:focus-visible { outline: 2px solid var(--brand-strong); outline-offset: 2px; border-radius: 4px; }
```

---

## Icons — thin semantic wrapper (NEVER hand-draw)

Map friendly names → library icon ids in one place; set stays swappable.

### Astro (`astro-icon` + Iconify)

```bash
npm i astro-icon @iconify-json/solar @iconify-json/simple-icons
```

```js
// astro.config.mjs
import icon from 'astro-icon';
export default defineConfig({ integrations: [icon()] });
```

```astro
---
// UI/device icons: Solar (linear); brand marks: Simple Icons. No custom icons.
import { Icon as Iconify } from "astro-icon/components";
interface Props { name: string; size?: number; class?: string; }
const { name, size = 24, class: cls = "" } = Astro.props;
const map: Record<string, string> = {
  telegram: "simple-icons:telegram", instagram: "simple-icons:instagram",
  search: "solar:magnifer-linear", menu: "solar:hamburger-menu-linear",
  cart: "solar:cart-large-2-linear", check: "solar:check-circle-linear",
  "arrow-right": "solar:arrow-right-linear", chat: "solar:chat-round-linear",
};
const iconName = map[name] ?? name; // pass-through allows raw "solar:..." ids
---
<Iconify name={iconName} class={`icon ${cls}`} width={size} height={size} />
```

### React / Next (`@iconify/react`)

```bash
npm i @iconify/react
```

```tsx
import { Icon as Iconify } from "@iconify/react";
const MAP: Record<string, string> = {
  search: "solar:magnifer-linear",
  menu: "solar:hamburger-menu-linear",
  telegram: "simple-icons:telegram",
};
export function Icon({ name, size = 24, className = "" }:
  { name: string; size?: number; className?: string }) {
  return <Iconify icon={MAP[name] ?? name} width={size} height={size} className={`icon ${className}`} />;
}
```

### Plain HTML (Iconify web component — no build step)

```html
<script src="https://code.iconify.design/iconify-icon/2.1.0/iconify-icon.min.js"></script>
<iconify-icon icon="solar:magnifer-linear" width="24" height="24"></iconify-icon>
```

> Browse/copy ids: https://icon-sets.iconify.design/solar/. Stay in one set.

---

## Fonts — load from a library

### Fontsource (Astro/Vite/Next — self-hosted, no layout shift)

```bash
npm i @fontsource-variable/onest @fontsource/unbounded
```

```js
// import once in root layout — only the weights you use
import "@fontsource-variable/onest/index.css"; // variable: all weights, one file
import "@fontsource/unbounded/400.css";
import "@fontsource/unbounded/600.css";
import "@fontsource/unbounded/700.css";
```

### Plain HTML (Google Fonts / Bunny Fonts)

```html
<link rel="preconnect" href="https://fonts.bunny.net">
<link rel="stylesheet"
  href="https://fonts.bunny.net/css?family=onest:400,500,600|unbounded:400,600,700&display=swap">
```

Wire into `--font-sans` / `--font-display`.

---

## Fluid type & spacing — clamp()

```css
h1 { font-size: clamp(2rem, 1.2rem + 4vw, 3.5rem); }       /* min, fluid, max */
.section { padding-block: clamp(40px, 6vw, 72px); }
.section-head h2 { font-size: clamp(1.5rem, 3.2vw, 2.1rem); }
```

---

## Components — buttons, badges, eyebrow

```css
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 9px;
  font-weight: 600; font-size: 0.95rem; line-height: 1;
  padding: 14px 22px; border-radius: var(--r-pill); white-space: nowrap;
  transition: transform .18s ease, box-shadow .2s ease, background .2s ease;
}
.btn:active { transform: translateY(1px); }
.btn-primary { background: var(--brand-grad); color: var(--on-brand); box-shadow: var(--shadow-brand); }
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 18px 36px -12px rgba(251,90,95,.6); }
.btn-ghost { background: var(--bg); color: var(--ink); border: 1px solid var(--line-strong); }
.btn-ghost:hover { border-color: var(--ink-3); background: var(--bg-soft); }

.badge {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: .78rem; font-weight: 600; padding: 5px 11px;
  border-radius: var(--r-pill); line-height: 1;
}
.badge-ok { color: var(--ok); background: var(--ok-soft); }

/* eyebrow: small uppercase display label above a heading */
.eyebrow {
  font-family: var(--font-display); font-size: .72rem; font-weight: 600;
  letter-spacing: .16em; text-transform: uppercase; color: var(--brand-strong);
}
```

---

## Shadows — layered + brand-tinted

Never a single flat shadow; tint toward brand.

```css
.card { box-shadow: var(--shadow); }
.card:hover { box-shadow: var(--shadow-lg); }

/* layered (generate at joshwcomeau.com/shadow-palette) */
.elevated {
  box-shadow:
    0 0.5px 0.6px rgba(31,36,48,0.10),
    0 1.6px 1.8px -0.8px rgba(31,36,48,0.10),
    0 4px 4.5px -1.7px rgba(31,36,48,0.10),
    0 9.6px 10.8px -2.5px rgba(31,36,48,0.10);
}
```

---

## Motion — one orchestrated load reveal + reduced-motion guard

```css
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
.reveal { animation: rise .6s cubic-bezier(.22, 1, .36, 1) both; }
/* stagger: */
.reveal:nth-child(1) { animation-delay: .00s; }
.reveal:nth-child(2) { animation-delay: .08s; }
.reveal:nth-child(3) { animation-delay: .16s; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .001ms !important;
    transition-duration: .001ms !important;
    scroll-behavior: auto !important;
  }
}
```

Scroll reveals without JS — native scroll-driven animations:

```css
@media (prefers-reduced-motion: no-preference) {
  .on-scroll { animation: rise linear both; animation-timeline: view(); animation-range: entry 0% cover 30%; }
}
```

React: **Motion** (`motion.dev`). Scroll storytelling / SVG morph: **GSAP** (free).

---

## Ecommerce product card stability

Stable dimensions so mixed names/aspect ratios don't shift the grid.

```css
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: clamp(14px, 2vw, 24px);
}
.product-card {
  display: grid;
  grid-template-rows: auto 1fr;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: var(--r);
  background: var(--bg);
  overflow: hidden;
}
.product-media {
  aspect-ratio: 1 / 1;
  padding: clamp(12px, 2vw, 18px);
  background: var(--bg-card);
}
.product-media img { width: 100%; height: 100%; object-fit: contain; }
.product-body { display: grid; align-content: start; gap: 8px; padding: 16px; }
.product-title { min-width: 0; font-weight: 650; line-height: 1.25; overflow-wrap: anywhere; }
.product-spec { color: var(--ink-3); font-size: 0.9rem; }
.product-price { margin-top: auto; font-weight: 750; font-variant-numeric: tabular-nums; }
```

Test with: long names, missing images, varied price lengths, uneven grid counts.

---

## Container & layout helpers

```css
.container { width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); }
.section { padding-block: clamp(40px, 6vw, 72px); }
.section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: clamp(20px, 3vw, 32px); }
```

---

## Imagery — AVIF + WebP with fallback (responsive)

Always set `width`/`height` (no layout shift); eager-load only the hero/LCP image.

```html
<picture>
  <source type="image/avif"
    srcset="hero-480.avif 480w, hero-800.avif 800w, hero-1200.avif 1200w"
    sizes="(max-width: 600px) 480px, (max-width: 900px) 800px, 1200px">
  <source type="image/webp"
    srcset="hero-480.webp 480w, hero-800.webp 800w, hero-1200.webp 1200w"
    sizes="(max-width: 600px) 480px, (max-width: 900px) 800px, 1200px">
  <img src="hero-800.jpg" alt="…" width="800" height="600"
    fetchpriority="high" decoding="async">
</picture>
<!-- non-hero: loading="lazy", drop fetchpriority -->
```

Astro: `<Picture formats={['avif','webp']} priority />` (`astro:assets`). React/Next: `next/image` + `formats: ['image/avif','image/webp']` in config. Build batch: **Sharp**.

---

## Modern CSS techniques (2026)

### OKLCH tokens (perceptually uniform) + tinting
```css
:root { --brand: oklch(0.62 0.19 18); }
.btn-soft { background: color-mix(in oklch, var(--brand) 14%, white); }
```

### Balanced headings
```css
h1, h2, h3 { text-wrap: balance; }   /* no single-word last lines */
p, li      { text-wrap: pretty; }
```

### Animated gradient via @property (raw gradients can't interpolate without this)
```css
@property --stop { syntax: "<percentage>"; inherits: false; initial-value: 0%; }
.cta { background: linear-gradient(120deg, var(--brand) var(--stop), var(--brand-strong));
       transition: --stop .5s ease; }
.cta:hover { --stop: 70%; }
```

### Enter animation from display:none — no JS (@starting-style)
```css
.popover { transition: opacity .25s, transform .25s; opacity: 1; transform: translateY(0); }
@starting-style { .popover { opacity: 0; transform: translateY(-8px); } }
```

### Glassmorphism (sparingly; needs busy bg behind it)
```css
.glass {
  background: color-mix(in srgb, var(--bg) 55%, transparent);
  backdrop-filter: blur(12px) saturate(140%);
  border: 1px solid color-mix(in srgb, white 30%, transparent);
}
```

### Same-document View Transition — progressive
```js
function update(dom) {
  if (!document.startViewTransition) return dom();   // graceful fallback
  document.startViewTransition(dom);
}
```
