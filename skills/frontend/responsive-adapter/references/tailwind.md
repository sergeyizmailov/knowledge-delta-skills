# Tailwind Responsive Patterns (v3 + v4)

## Default breakpoints (mobile-first)

| Prefix | Min width | Class |
|--------|-----------|-------|
| (none) | 0px       | Mobile-first base |
| `sm:`  | 640px     | Large phone / small tablet |
| `md:`  | 768px     | Tablet |
| `lg:`  | 1024px    | Laptop |
| `xl:`  | 1280px    | Desktop |
| `2xl:` | 1536px    | Large desktop |

Write base styles unprefixed, override upward. Never `max-*:` when `sm:`/`md:`/`lg:` suffice — desktop-first cascade harder to maintain.

## Cross-platform breakpoint override (Material 3-aligned)

```js
// tailwind.config.js (v3)
module.exports = {
  theme: {
    screens: {
      sm: '390px',    // iPhone baseline
      md: '600px',    // M3 Compact→Medium
      lg: '840px',    // M3 Medium→Expanded
      xl: '1200px',   // M3 Expanded→Large
      '2xl': '1600px' // M3 Large→Extra-large
    }
  }
}
```

```css
/* Tailwind v4 */
@theme {
  --breakpoint-sm: 390px;
  --breakpoint-md: 600px;
  --breakpoint-lg: 840px;
  --breakpoint-xl: 1200px;
  --breakpoint-2xl: 1600px;
}
```

## Container queries (v4 native; v3 via `@tailwindcss/container-queries`)

```html
<div class="@container">
  <div class="grid @md:grid-cols-2 @lg:grid-cols-3">
    <!-- adapts to container, not viewport -->
  </div>
</div>
```
Named:
```html
<div class="@container/card">
  <div class="@md/card:grid-cols-2">...</div>
</div>
```
Units `cqi/cqw/cqh/cqb/cqmin/cqmax` work in arbitrary values: `text-[clamp(0.875rem,3cqi,1.5rem)]`.

## Patterns

```html
<!-- Stack → row at breakpoint -->
<div class="flex flex-col md:flex-row gap-4">
  <div class="flex-1">A</div>
  <div class="flex-1">B</div>
</div>

<!-- Grid columns adapt -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

<!-- Auto-fit RAM pattern (320px-safe grid) -->
<div class="grid gap-4
            [grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))]">

<!-- Show/hide by viewport -->
<nav class="hidden md:flex">...desktop nav...</nav>
<button class="md:hidden">menu</button>

<!-- Fluid spacing & type -->
<section class="py-[clamp(2rem,5vw,6rem)] px-[clamp(1rem,4vw,3rem)]">
  <h1 class="text-[clamp(2rem,1rem+4vw,4rem)] leading-tight">

<!-- Container width -->
<div class="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
<!-- or with min() -->
<div class="mx-auto w-[min(100%-2rem,80rem)]">

<!-- Safe-area mobile nav -->
<nav class="fixed inset-x-0 bottom-0
            pb-[max(0.75rem,env(safe-area-inset-bottom))]
            bg-white border-t">

<!-- Mobile drawer with <dialog> -->
<dialog class="ml-auto m-0 h-dvh w-[85vw] max-w-[20rem]
               border-0 p-4 open:translate-x-0
               backdrop:bg-black/50">
  <button autofocus formmethod="dialog">×</button>
  <nav>...</nav>
</dialog>

<!-- Sticky table with first-column lock -->
<div role="region" tabindex="0" class="overflow-x-auto focus:outline-2">
  <table class="min-w-full">
    <thead class="bg-gray-50">
      <tr>
        <th class="sticky left-0 bg-gray-50 z-10 px-3 py-2">ID</th>
        <th class="px-3 py-2">...</th>
      </tr>
    </thead>
  </table>
</div>
```

## Arbitrary values
One-off fluid scaling only: `text-[clamp(...)]`, `py-[clamp(...)]`, `w-[min(100%-2rem,80rem)]`, `h-[100dvh]`, `gap-[clamp(0.75rem,2vw,1.5rem)]`. Repeated values → promote to `theme.extend` tokens.

## Common sins
- `w-screen` full-bleed → `100vw` includes scrollbar. Use `w-full` in `w-[min(100vw,100%)]` parent, or `w-full` + `margin-inline: calc(50% - 50vw)` breakout.
- `h-screen` hero → `100vh`. Use `h-svh` / `min-h-dvh` (v3.4+).
- `text-xs` inputs → 12px → iOS zoom. Minimum `text-base` / `text-[16px]`.
- `hidden md:block` on critical CTA → gone on mobile; keep mobile alternative.
- `space-y-4` on responsive flex/grid that changes direction → breaks; use `gap-4` everywhere.
- `lg:p-12` without unprefixed padding → 0 padding on mobile.

## Plugins
- `@tailwindcss/container-queries` (v3; v4 built in)
- `@tailwindcss/forms` — 16px fonts, proper control sizing
- `@tailwindcss/aspect-ratio` (v3; v4 has `aspect-*`)
- `tailwind-utopia` — Utopia fluid type/space scale utilities

## Tailwind v4 highlights
- Native container queries (no plugin)
- CSS-first config via `@theme {}`
- `@variant` for custom variants
- `dvh`/`svh`/`lvh` built into `h-*` / `min-h-*` / `max-h-*`
