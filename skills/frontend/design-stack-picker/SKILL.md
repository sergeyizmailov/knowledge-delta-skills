---
name: design-stack-picker
description: "Use when building or restyling frontend UI and choosing building blocks — icon sets, fonts, component/block libraries, accessible primitives, imagery sources, color systems, motion, shadows, spacing, and image optimization. For landing pages, ecommerce, dashboards, web apps, emails, and single components."
risk: low
source: custom
date_added: "2026-06-15"
---

# design-stack-picker

A selection layer, not a mandate to replace the project's design system.

## Decision order

Audit first: framework and rendering model, existing icons/fonts/tokens/components/image pipeline/breakpoints, current dependencies, visual style. Then:

1. Reuse the existing project system if it works.
2. Extend it with the smallest compatible building block.
3. Add a library only when there is no good local solution.
4. Hand-craft only for brand assets, tiny static pieces, or where a dependency outweighs the implementation.

## Defaults

Starting points, not requirements.

| Axis | Default |
|---|---|
| Icons | Iconify + Solar; Simple Icons for brand marks |
| Fonts | Unbounded display + Onest body via Fontsource |
| Components | Project components first; HyperUI/Preline for static sections; shadcn/Radix for React primitives |
| Color | Semantic CSS variables; one dominant brand color + one accent |
| Motion | CSS-first restrained reveal; Motion for React; GSAP only for complex timelines |
| Imagery | Real product/user/stock/CMS assets; AVIF/WebP where practical |

## Dependency budget

No dependency for: a single icon when an icon system exists; one static section existing primitives can handle; a basic disclosure/dropdown in Astro or plain HTML where scoped JS is smaller and verifiable; a visual effect existing CSS covers; anything duplicating a current dependency.

Add one when it removes real implementation risk: complex accessible widgets, broad consistent icon coverage, image optimization at scale, multi-screen design systems.

## Context routing

| Context | Bias |
|---|---|
| Astro/static | Local `.astro` components, scoped CSS, progressive JS, `astro:assets`; avoid React-only primitives unless already used |
| React/Next | Current UI layer first; shadcn/Radix for missing complex primitives |
| Admin/dashboard | Dense scannable forms/tables/filters, minimal decoration |
| Ecommerce | Real product photos, neutral placeholders, stable card dimensions with `object-fit: contain`; price/stock/spec/action hierarchy over decorative labels; reachable category nav, autocomplete, dismissible mobile filters; test long names, missing images, sale/stock states, uneven counts |
| Marketing | Stronger typography, imagery/video, section blocks, restrained motion |
| Prototype | Smallest working choice; no full design system unless it will continue |

## Hard rules

- One family per axis: one icon set, one illustration style, one color system, one type pairing.
- Never hand-draw generic SVG icons — use the icon set (supplied brand logos excepted).
- Choose and load type intentionally; never ship default fonts on brand-facing UI.
- Tokens for colors, spacing, radii, shadows, type, and states — no scattered inline magic values.
- Accessible primitives for dialogs, comboboxes, tabs, menus, tooltips, switches — with real keyboard/focus behavior.
- Respect `prefers-reduced-motion`, visible focus, AA contrast.
- Optimize important images, set dimensions, eager-load only the LCP image.
- Verify in a browser from phone to wide desktop: no horizontal overflow, key images load at natural dimensions.

Where a hard rule conflicts with a mature existing convention, keep the convention and improve incrementally.

## Resources

Load only what the task needs, never both by default.

- `resources.md` — the catalog: libraries, fonts, icon sets, imagery, components, motion, color systems. §12 first for vague "make it look better" tasks, to fix concrete references before touching UI.
- `patterns.md` — implementation snippets: tokens, reset, icons, fonts, cards, image markup, motion, CSS.
