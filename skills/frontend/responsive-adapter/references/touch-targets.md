# Touch Target Sizes — 2026 Standards

## Specs
- **Material 3: 48 × 48 dp minimum** (~9mm). Visual icon may be 24dp — tap region MUST extend to 48dp via transparent padding. FAB: 56dp.
- **Apple HIG: 44 × 44 pt minimum** (pt ≈ CSS px). < 44pt → 25%+ mis-tap rate (Apple research). Exception: inline text links.
- **WCAG 2.2 SC 2.5.8 Target Size Minimum (AA, mandatory):** 24 × 24 CSS px minimum. Alternatives: 24px spacing (24px-diameter circles per target don't overlap), inline in paragraph, conformant alternative on same page, UA-controlled/essential. Floor, not goal.
- **WCAG 2.5.5 (AAA):** 44 × 44 CSS px.

## Ship-this table

| Context | Size | Rationale |
|---------|------|-----------|
| Primary CTAs (touch) | 48–56 CSS px | MD3 spec, thumb reach |
| Secondary actions | 44 CSS px | WCAG 2.5.5 / HIG |
| Dense table / icon-only toolbar | 32 CSS px with 24 CSS px gap | meets 2.5.8 via spacing exception |
| Inline text links | natural line-height | exempt from 2.5.8 |
| Form inputs | 44–48 CSS px height + 16px font | tap + zoom prevention |

## Spacing
2.5.8 spacing exception permits 24px targets if circles don't overlap.

```css
/* Minimum */
.toolbar > * + * { margin-inline-start: 8px; }

/* Better */
.toolbar { display: flex; gap: 12px; }
.toolbar button { min-block-size: 44px; min-inline-size: 44px; }
```
HIG: 8pt between targets. MD3: 8dp.

## Practical baseline (drop-in)

```css
:where(button, a, input, select, [role="button"]) {
  min-block-size: 44px;
  min-inline-size: 44px;
}

/* Tighten on fine-pointer devices */
@media (hover: hover) and (pointer: fine) {
  :where(button, a, input, select, [role="button"]) {
    min-block-size: 32px;
    min-inline-size: 32px;
  }
}
```
`:where()` keeps specificity 0 for easy override.

## Extend hit area without growing visual

```css
.icon-btn { position: relative; }
.icon-btn::before {
  content: "";
  position: absolute;
  inset: -10px;
  /* click area 20px larger each side */
}
```
