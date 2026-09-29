# Material 3 + Apple HIG — Adaptive Guidelines

## Material 3 — Window Size Classes

| Class | Width | Device coverage (Google stat) |
|---|---|---|
| Compact     | < 600dp        | 99.96% phones portrait |
| Medium      | 600 – 839dp    | 93.73% tablets portrait, foldable inner portrait |
| Expanded    | 840 – 1199dp   | 97.22% tablets landscape, foldable inner landscape |
| Large       | 1200 – 1599dp  | Large tablets |
| Extra-large | ≥ 1600dp       | Desktop |

Height classes: Compact < 480dp · Medium 480–899dp · Expanded ≥ 900dp.

dp ≈ CSS px at DPR 1 → M3 breakpoints map directly to CSS `min-width`.

## M3 layout per class

| Class | Columns | Margins | Gutters | Navigation |
|-------|---------|---------|---------|------------|
| Compact (< 600)     | 4  | 16dp               | 16dp | Bottom navigation bar |
| Medium (600-839)    | 8  | 24dp               | 24dp | Navigation rail (80dp wide) |
| Expanded (840-1199) | 12 | 24dp (up to 200dp) | 24dp | Nav rail + optional drawer |
| Large (1200-1599)   | 12 | up to 200dp        | 24dp | Permanent drawer / multi-pane |
| Extra-large (≥1600) | 12 | up to 200dp        | 24dp | Permanent drawer + multi-pane |

Other M3: pane padding 16dp internal / 24dp between panes; max content line length 60 chars on large screens; touch target 48dp minimum; 8dp baseline grid; canonical patterns — Feed, List/Detail, Supporting Pane.

## Apple HIG — Size Classes
Two values per axis: Compact (C) / Regular (R). No numeric breakpoints in points — OS reports via trait collection.

| Device / state | H | V |
|----------------|---|---|
| All iPhones portrait | C | R |
| Standard iPhones landscape | C | C |
| Plus/Max iPhones landscape | R | C |
| iPad full-screen any orientation | R | R |
| iPad Slide Over | C | R |
| iPad Split View 1/2 | C | R for both |
| iPad Pro 12.9/13" 1/2 landscape | R | R |
| iPad 2/3-1/3 landscape | Primary R, secondary C | R |

Vertical size class on iPad is always Regular — design focus is horizontal.

## HIG specifics
- Min hit target: 44 × 44 pt for all controls.
- Layout margins: 16pt compact (iPhone), 20pt regular (iPad).
- Readable content width: per-device "readable content guide".
- Safe area: `env(safe-area-inset-*)` on web — REQUIRED for notch/Dynamic Island/home indicator; needs `viewport-fit=cover`.
- 8pt grid (4pt tight controls).

## iPad multitasking
Slide Over / Split View / Stage Manager produce app window widths ~320–1366pt — never hard-code device widths.
- Slide Over: forces compact ~320-375pt regardless of device.
- Split View 1/2: compact for both on most iPads; only 12.9/13" Pro regular for both.
- Stage Manager: arbitrary resizable windows.

## Web applicability
- No "compact" media query — map by viewport width: ~390-440 CSS px = compact (iPhone), ~744+ = regular (iPad).
- Apple 44pt = 44 CSS px on iOS Safari. WCAG 2.5.5 = 44px, WCAG 2.5.8 = 24px.
- M3 dp = CSS px 1:1. M3 grid ladder (4/8/12 columns at 600/840/1200/1600) = most ergonomic cross-platform numeric set for web.

## Recommendation
Build web breakpoints from M3 numbers (600 / 840 / 1200 / 1600); layer Apple's 44pt target + `safe-area-inset` rules on top → Android-correct, iOS-friendly, WCAG 2.2-compliant defaults.
