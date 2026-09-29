# iOS Safari + Android Chrome — Platform Quirks (2026)

## iOS Safari (iOS 17 / 18 / 26)

### Input zoom (16px)
Still triggers on iOS 18 / iPhone 16; unchanged since iOS 5. Fix: input/textarea/select `font-size: 16px` (see anti-patterns A4). NEVER `maximum-scale=1` — a11y violation.

### `100vh` vs `100dvh`
iOS 18 does NOT update `window.innerHeight` when address bar expands; `100vh` always equals `lvh` on iOS Safari. Fix: `dvh`/`svh`/`lvh` (Baseline June 2025). Don't animate `dvh`.

### Safe-area insets
```css
.app {
  padding-block-start: env(safe-area-inset-top);
  padding-block-end:   env(safe-area-inset-bottom);
  padding-inline-start: env(safe-area-inset-left);
  padding-inline-end:   env(safe-area-inset-right);
}
/* iOS 16.4+ static maximum: */
.fixed-overlay {
  padding-block-end: max(12px, env(safe-area-max-inset-bottom));
}
```
REQUIRES `viewport-fit=cover` in viewport meta — otherwise env values are 0 and Safari letterboxes landscape with black bars. iOS landscape has unreported ~20px touch dead-zone along the top.

### Sticky + overflow bugs
`position: sticky` inside `overflow: auto` or transformed ancestor BREAKS on iOS Safari through iOS 18. Fix: move sticky out of the scroll container, or `overflow: clip` + fixed positioning.

### Bounce / rubberband
```css
html, body { overscroll-behavior: none; }
/* Or contain for nested scrollers: */
.scroller { overscroll-behavior: contain; }
```

### `-webkit-text-size-adjust`
iOS portrait→landscape silently inflates fonts.
```css
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
```
Use `100%`, NOT `none` (`none` blocks user text-size prefs = a11y violation).

### Date inputs
iOS 17: `<input type="date">` with `display: inline-flex` ignores `width: 100%`. iOS 18 fixed, but `display: inline-block` adds random bottom padding.

### PWA standalone
- Detect: `window.matchMedia('(display-mode: standalone)').matches` or `navigator.standalone` (iOS-only).
- Different safe-area behavior — Dynamic Island can hide top UI; always pad `env(safe-area-inset-top)`.
- iOS 17+ rotation animation ~500ms — debounce dimension reads.

## Android Chrome

### Soft keyboard (Chrome 108+)
Chrome 108+ default: keyboard resizes only the **visual** viewport, NOT layout viewport — `100vh` elements no longer collapse (good). Opt back into legacy resize for chat apps:
```html
<meta name="viewport"
      content="width=device-width, initial-scale=1, interactive-widget=resizes-content">
```
Values: `resizes-visual` (default), `resizes-content` (legacy), `overlays-content`.

VisualViewport API:
```js
window.visualViewport.addEventListener('resize', () => {
  document.documentElement.style.setProperty(
    '--kb',
    (innerHeight - visualViewport.height) + 'px'
  );
});
```

VirtualKeyboard API (Chromium-only) — enables `env(keyboard-inset-height)`:
```js
if ('virtualKeyboard' in navigator) {
  navigator.virtualKeyboard.overlaysContent = true;
}
```

### Pull-to-refresh
```css
html, body { overscroll-behavior-y: contain; } /* preserves nested scrolls */
/* or none — fully kills PTR + bounce */
```

### Address bar / cutout
Same `dvh`/`svh`/`lvh` and `env(safe-area-inset-*)` (with `viewport-fit=cover`) as iOS.

### Foldables (Galaxy Z Fold/Flip, Surface Duo)
```css
@media (horizontal-viewport-segments: 2) {
  .layout {
    grid-template-columns: env(viewport-segment-right 0 0) 1fr;
  }
}
@media (device-posture: folded) { /* book/laptop posture */ }
```
Viewport Segments API + Device Posture API — Chrome 125 (origin trial → stable). `vertical-viewport-segments` for Flip-style hinges. Guard with `@supports`.

## Safe-area drop-in recipe (iOS + Android)

```css
:root {
  --safe-t: env(safe-area-inset-top);
  --safe-r: env(safe-area-inset-right);
  --safe-b: env(safe-area-inset-bottom);
  --safe-l: env(safe-area-inset-left);
}

.app-shell {
  padding-block-start: var(--safe-t);
  padding-block-end:   var(--safe-b);
  padding-inline-start: var(--safe-l);
  padding-inline-end:   var(--safe-r);
}

.bottom-nav {
  position: fixed;
  inset: auto 0 0 0;
  padding-block-end: max(0.75rem, var(--safe-b));
  padding-inline:    max(1rem,    var(--safe-l));
  background: #fff; /* extend bg into inset */
}
```
