# CSS-in-JS — styled-components, Emotion (Responsive Patterns)

## Theme breakpoints (Material 3-aligned)

```ts
// theme.ts
export const breakpoints = {
  sm: '390px',
  md: '600px',
  lg: '840px',
  xl: '1200px',
  xxl: '1600px',
} as const;

export const media = {
  sm: `@media (min-width: ${breakpoints.sm})`,
  md: `@media (min-width: ${breakpoints.md})`,
  lg: `@media (min-width: ${breakpoints.lg})`,
  xl: `@media (min-width: ${breakpoints.xl})`,
  xxl: `@media (min-width: ${breakpoints.xxl})`,
};

export const theme = { breakpoints, media };
```

## styled-components usage

```tsx
const Grid = styled.div`
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;

  ${({ theme }) => theme.media.md} {
    grid-template-columns: 1fr 1fr;
  }

  ${({ theme }) => theme.media.lg} {
    grid-template-columns: 1fr 1fr 1fr;
  }
`;
```

## Emotion usage

```tsx
import { css } from '@emotion/react';

const gridStyle = (theme) => css`
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;

  ${theme.media.md} {
    grid-template-columns: 1fr 1fr;
  }
`;
```

## Prop-driven helper (styled-components)

```ts
import { css, DefaultTheme } from 'styled-components';

type BPKey = keyof DefaultTheme['breakpoints'];

export const above = (bp: BPKey) => (
  styles: TemplateStringsArray | string
) => (props: { theme: DefaultTheme }) => css`
  @media (min-width: ${props.theme.breakpoints[bp]}) {
    ${styles}
  }
`;

// Usage
const Card = styled.div`
  padding: 1rem;
  ${above('md')`padding: 2rem;`}
  ${above('lg')`padding: 3rem;`}
`;
```

## Container queries in CSS-in-JS

```tsx
const CardWrap = styled.div`
  container-type: inline-size;
  container-name: card;
`;

const CardLayout = styled.div`
  display: grid;
  gap: 1rem;

  @container card (min-width: 32rem) {
    grid-template-columns: 12rem 1fr;
  }
`;
```

## Fluid type via clamp() — lowest-maintenance, no breakpoint juggling

```tsx
const Heading = styled.h1`
  font-size: clamp(2rem, 1.1rem + 4.3vw, 5rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
`;
```

## Component-level adaptation (renders correctly in any slot)

```tsx
const Widget = styled.article`
  container-type: inline-size;
  display: grid;
  gap: 0.75rem;
  padding: 1rem;

  & > .widget__body {
    display: grid;
    gap: 0.5rem;
  }

  @container (min-width: 30rem) {
    & > .widget__body { grid-template-columns: auto 1fr; }
  }
  @container (min-width: 45rem) {
    & > .widget__chart { display: block; }
    & > .widget__sparkline { display: none; }
  }
`;
```

## SSR (Next.js, Remix, etc.) — critical
- DO: pure CSS media/container queries — identical SSR and client.
- DON'T: `useMediaQuery` for layout — hydration mismatch flash (server renders mobile, client switches).
- Dialog/Drawer swap (one of few legit JS cases): render both, toggle via CSS; or `useIsClient()` + accept one-frame flash.

```tsx
// SSR-safe responsive component swap
const ResponsiveModal = ({ children }) => (
  <>
    <DesktopDialog className="hidden md:block">{children}</DesktopDialog>
    <MobileDrawer className="md:hidden">{children}</MobileDrawer>
  </>
);
```

## Bad vs good patterns

```tsx
// BAD — re-renders on resize, hydration mismatch
const isMobile = window.innerWidth < 768;
const Card = styled.div`
  padding: ${isMobile ? '1rem' : '2rem'};
`;
// BAD — props-based pixel value
<Card padding={isMobile ? 16 : 32} />
// BAD — useMediaQuery for layout (SSR flash)
const isMobile = useMediaQuery('(max-width: 768px)');
return isMobile ? <MobileLayout /> : <DesktopLayout />;

// GOOD — pure CSS media query
const Card = styled.div`
  padding: 1rem;
  @media (min-width: 768px) { padding: 2rem; }
`;
// GOOD — fluid via clamp
const Card = styled.div`
  padding: clamp(1rem, 4vw, 2rem);
`;
// GOOD — container query (component-self-aware)
const Card = styled.div`
  container-type: inline-size;
  padding: 1rem;
  @container (min-width: 30rem) { padding: 2rem; }
`;
```

## Library-specific notes
- **styled-components v6+**: dropped babel-plugin; for SSR + theme-matching class names use `--theme-X` CSS custom properties on the theme provider.
- **Emotion v11+**: `css` prop for one-offs, `styled` for reusable — both support CSS features identically.
- **vanilla-extract**: zero-runtime, type-safe CSS-in-TS — treat as vanilla CSS with TS types (see `vanilla-css.md`). Use `style({ '@media': {...} })` and `style({ '@container': {...} })`.
- **stitches** (deprecated 2024): migrate to vanilla-extract or styled-components v6.
