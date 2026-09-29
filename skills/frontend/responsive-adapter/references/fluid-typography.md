# Fluid Typography Best Practices — 2025-2026

`clamp(MIN, PREFERRED, MAX)` where preferred = linear interpolation between two design points (min/max viewport). Rule: always mix `rem` + `vw` (pure `vw` violates WCAG 1.4.4 — `vw` ignores browser zoom). Safe ratio: `MAX ≤ 2.5 × MIN`.

## 1. Canonical `clamp()` formula

```css
font-size: clamp(MIN_rem, SLOPE_vw + INTERCEPT_rem, MAX_rem);
```

Given `(x1, y1)` = (min viewport, min size) and `(x2, y2)` = (max viewport, max size), in px:

```
SLOPE_vw   = 100 · (y2 − y1) / (x2 − x1)
INTERCEPT  = (x1·y2 − x2·y1) / (x1 − x2)         // px
INTERCEPT_rem = INTERCEPT / 16
```

### Example 1 — body: 16px @ 320px → 18px @ 1280px
```
SLOPE_vw  = 100 · (18 − 16) / (1280 − 320) = 200/960 ≈ 0.2083vw
INTERCEPT = (320·18 − 1280·16) / (320 − 1280) = −14720 / −960 ≈ 15.333px → 0.9583rem
MIN = 1rem ; MAX = 1.125rem
```
```css
body { font-size: clamp(1rem, 0.9583rem + 0.2083vw, 1.125rem); }
```

### Example 2 — hero h1: 32px @ 320px → 80px @ 1440px
```
SLOPE_vw  = 100 · (80 − 32) / (1440 − 320) = 4800/1120 ≈ 4.2857vw
INTERCEPT = (320·80 − 1440·32) / (320 − 1440) = −20480 / −1120 ≈ 18.286px → 1.1429rem
MIN = 2rem ; MAX = 5rem
```
```css
h1.hero { font-size: clamp(2rem, 1.1429rem + 4.2857vw, 5rem); }
```
`MAX/MIN = 2.5` — exactly on the WCAG threshold.

## 2. Type scale ratios

| Ratio   | Name             | Feel                |
|---------|------------------|---------------------|
| 1.067   | Minor second     | Very tight          |
| 1.125   | Major second     | Subtle              |
| 1.200   | Minor third      | Common UI           |
| 1.250   | Major third      | Comfortable default |
| 1.333   | Perfect fourth   | Editorial           |
| 1.414   | Augmented fourth | Punchy              |
| 1.500   | Perfect fifth    | Strong hierarchy    |
| 1.618   | Golden ratio     | Maximum drama       |

Utopia method (Trys Mudford / James Gilyead): two viewport endpoints (e.g. 320/1240); smaller ratio mobile (1.2), larger desktop (1.333–1.414); generate `clamp()` per step.

### Ready-made h1-h6 + body scale (320 → 1240, ratio 1.2 → 1.25)

```css
:root {
  --step--1: clamp(0.8333rem, 0.7997rem + 0.1678vw, 0.9375rem);
  --step-0:  clamp(1rem,      0.9565rem + 0.2174vw, 1.125rem);
  --step-1:  clamp(1.2rem,    1.1413rem + 0.2935vw, 1.4063rem);
  --step-2:  clamp(1.44rem,   1.3592rem + 0.4038vw, 1.7578rem);
  --step-3:  clamp(1.728rem,  1.6149rem + 0.5658vw, 2.1973rem);
  --step-4:  clamp(2.0736rem, 1.9132rem + 0.802vw,  2.7466rem);
  --step-5:  clamp(2.4883rem, 2.2598rem + 1.1426vw, 3.4332rem);
  --step-6:  clamp(2.986rem,  2.6628rem + 1.616vw,  4.2915rem);
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

## 3. Tools
- Utopia — utopia.fyi/type/calculator/ + Figma plugin (figma.com/community/plugin/951884648789524000)
- fluid-type-scale.com
- modern-css.com/playground/css-clamp-fluid-typography/
- tailwind-utopia — github.com/cwsdigital/tailwind-utopia

## 4. Line-height & letter-spacing

```css
body { line-height: 1.5; }     /* unitless REQUIRED; px line-height freezes */
h1, h2 { line-height: 1.1; }
h3, h4 { line-height: 1.2; }
h5, h6 { line-height: 1.3; }
body   { line-height: 1.55; }

/* Josh Comeau fluid trick */
* { line-height: calc(1em + 0.5rem); }

/* Letter-spacing inversely scales */
h1, h2 { letter-spacing: -0.02em; }
h3, h4 { letter-spacing: -0.01em; }
body   { letter-spacing: 0; }
small  { letter-spacing: 0.04em; }
```

## 5. Pitfalls
1. Body min < 16px → iOS input auto-zoom; anchor MIN at `1rem`.
2. Pixel bounds `clamp(16px, ..., 24px)` — frozen vs zoom; use `rem`.
3. Pure `vw` middle `clamp(1rem, 4vw, 2rem)` — doesn't move on zoom; mix `rem`.
4. MAX/MIN > 2.5 — violates WCAG 1.4.4.
5. px line-height — breaks at extremes.
6. Mobile hierarchy collapse → different ratio per endpoint (Utopia).
7. Browser zoom is the a11y lever, not `prefers-reduced-motion`.
8. One clamp for everything — each h-level needs own MIN/MAX.
9. Component-scoped fluidity: replace `vw` with `cqi`.

## 6. Apple HIG & Material 3

### Apple Dynamic Type
- Text styles: `largeTitle`, `title1-3`, `headline`, `body`, `callout`, `subheadline`, `footnote`, `caption1-2`.
- xSmall → AX5 (~310% of base); min readable 11pt.
- Web compat: Dynamic Type ≈ browser zoom + root font-size; `clamp(MIN_rem, ..., MAX_rem)` honors both.

### Material 3 type scale

| Role       | Large | Medium | Small |
|------------|-------|--------|-------|
| Display    | 57px  | 45px   | 36px  |
| Headline   | 32px  | 28px   | 24px  |
| Title      | 22px  | 16px   | 14px  |
| Body       | 16px  | 14px   | 12px  |
| Label      | 14px  | 12px   | 11px  |

M3 default is NOT fluid. Conversion:
```css
.md-typescale-display-large {
  font-size: clamp(2.25rem, 1.5rem + 3.75vw, 3.5625rem);
  line-height: 1.12;
  letter-spacing: -0.015625em;
}
```
Apple/Material role naming maps 1:1 onto web `clamp()`.
