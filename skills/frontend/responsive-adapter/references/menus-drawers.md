# Mobile Menus & Drawers — 2026 Patterns

## Pure-CSS approaches — NOT production-grade for accessible nav in 2026
- **Checkbox hack:** label not predictably focusable; SR announces "checkbox" not "menu button".
- **`:target`:** changes URL hash, breaks back button, conflicts with anchors.
- **`<details>/<summary>`:** not announced as expanded on iOS VoiceOver + Safari; NVDA + Chrome inconsistent; no focus-trap or Escape.

## Minimal-JS disclosure (≤15 lines)

```html
<button aria-expanded="false" aria-controls="nav" id="nav-btn">Menu</button>
<nav id="nav" hidden>
  <a href="/">Home</a>
  <a href="/about">About</a>
</nav>
<script>
  const btn = document.getElementById('nav-btn');
  const nav = document.getElementById('nav');
  btn.addEventListener('click', () => {
    const open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!open));
    nav.hidden = open;
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && btn.getAttribute('aria-expanded') === 'true') {
      btn.setAttribute('aria-expanded', 'false');
      nav.hidden = true;
      btn.focus();
    }
  });
</script>
```
Heydon Pickering disclosure-widget pattern. Nav links = list of links, NOT `role="menu"` (desktop-app menubars only).

## Native `<dialog>` drawer (RECOMMENDED 2026)

```html
<button aria-controls="drawer">Menu</button>
<dialog id="drawer" aria-label="Site navigation" class="drawer">
  <button autofocus aria-label="Close" formmethod="dialog">×</button>
  <nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
  </nav>
</dialog>
<script>
  const dlg = document.getElementById('drawer');
  document.querySelector('[aria-controls="drawer"]').onclick = () => dlg.showModal();
  // backdrop click closes
  dlg.addEventListener('click', e => {
    if (e.target === dlg) dlg.close();
  });
</script>
```

```css
.drawer {
  margin: 0 0 0 auto;
  block-size: 100dvh;
  max-inline-size: 20rem;
  inline-size: 85vw;
  border: 0; padding: 1rem;
  padding-block-start: max(1rem, env(safe-area-inset-top));
  padding-inline-end:  max(1rem, env(safe-area-inset-right));
}
.drawer::backdrop { background: rgb(0 0 0 / .5); }
.drawer[open] { animation: slide .2s ease-out; }
@keyframes slide { from { translate: 100% 0; } }
```

`showModal()` gives FREE: focus management (first focusable / `autofocus`), Escape close, focus trapping, top-layer rendering (escapes z-index hell), `::backdrop`, `inert` on rest of page. WCAG 2025 guidance no longer mandates manual focus-trapping inside `<dialog>` — UA handles it.

## Bottom sheet (mobile-preferred)

```css
.sheet {
  position: fixed;
  inset: auto 0 0 0;
  margin: 0;
  max-block-size: 90dvh;
  border-radius: 1rem 1rem 0 0;
  padding-block-end: max(1rem, env(safe-area-inset-bottom));
}
.sheet::backdrop { background: rgb(0 0 0 / .4); }
.sheet[open] { animation: rise .25s cubic-bezier(.32, .72, 0, 1); }
@keyframes rise { from { translate: 0 100%; } }
```
Drag-to-dismiss: Vaul (`vaul.emilkowal.ski`) or own `onDragEnd` velocity threshold ≈500.

## View Transitions enhancement (Baseline Oct 2025)

```css
.drawer { view-transition-name: drawer; }
::view-transition-old(drawer) { animation: slide-out .2s ease-in; }
::view-transition-new(drawer) { animation: slide-in  .2s ease-out; }
@keyframes slide-in  { from { translate: 100% 0; } }
@keyframes slide-out { to   { translate: 100% 0; } }

@media (prefers-reduced-motion: reduce) {
  ::view-transition-old(*),
  ::view-transition-new(*) { animation: none; }
}
```

```js
function toggleDrawer() {
  if (!document.startViewTransition) return openDrawer();
  document.startViewTransition(() => openDrawer());
}
```

## A11y checklist (every drawer)
- Trigger: `aria-expanded`, `aria-controls`, `aria-label` or visible text
- Open → focus to first focusable (or close button); close → focus back to trigger
- Escape closes (free with `showModal()`)
- Rest of page `inert` (free with `showModal()`; manual otherwise)
- Visible `:focus-visible` styles — never remove without replacement
- Close (×) button ≥ 44×44
- Label purpose, not appearance: `"Open navigation"`, never `"Hamburger"`

## UX variants
- **Slide-in** — overlay + backdrop dim; primary nav
- **Push-aside** — content shifts; janky on mobile, AVOID
- **Fade overlay** — full-screen menu; marketing sites, large targets
- **Bottom sheet** — thumb reach; mobile-preferred

## Decision table

| Context | Pattern | Why |
|---------|---------|-----|
| Marketing landing, ≤7 nav items | Minimal-JS disclosure (`hidden` toggle) | No modal needed |
| Admin app sidebar on mobile | `<dialog>` slide-in drawer | Focus trap + escape + top layer |
| Filter / action sheet on mobile | `<dialog>` bottom-sheet | Thumb reach |
| Settings panel on desktop | Side-sheet (not modal) | Doesn't block context |
| Confirmation prompt | `<dialog>` centered modal | Forces decision |
