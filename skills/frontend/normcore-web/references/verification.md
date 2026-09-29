# Verification

Any left-column item is a regression. **◆ rows are archetype-dependent — check your archetype file before treating them as failures.**

## Genre density targets

Fastest way to detect a genre mismatch (measured front-page figures; secondary pages run ~30–50% of link count, same chrome — see "Page types" in `SKILL.md`):

| archetype | links | images | shadows seen | prose |
|---|---|---|---|---|
| professional services | low | ~40 | **0** | 60–90 word paragraphs, 2–3 per band |
| shop | moderate | **121–353** | 9–39 | almost none; one SEO block at the bottom |
| news | **265–424** | 112–151 | 5–46 | headlines and timestamps, no summaries |
| corporate / institutional | 150–261 | **18–34** | 14–42 | short intros, then links |
| directory | ~173 | **~10** | ~1 | near zero |

**Benchmarks for a complete home page — never minimums to pad toward.** Scale every row to the content that exists (a 50-product trader has 50 images; a 9-product shop has 9 — say so in the report, don't invent inventory). A small newsroom won't reach newspaper density: route it to `corporate-institutional`, use news grammar only for its article list. Shadow counts are what the genre **tolerates**, not targets — eight is fine where the reference had forty; never add shadows to reach a number.

## Style

Applies to **every** archetype. Genre-specific checks live in the archetype file — run both.

| wrong | right |
|---|---|
| eyebrow / kicker label above a heading | the heading starts the block |
| decorative rule, dash or icon beside a heading | nothing there |
| two-tone wordmark | one colour, or an image file |
| ◆ a decorative third button variant (ghost, outline, tinted) | two in professional services; elsewhere one functional tertiary action allowed |
| uppercase or letter-spaced button labels | 15px / 400 / sentence case |
| spatial hover — scale, lift, slide, underline sweep, colour wipe | colour change only |
| `transform` in a transition or keyframes you authored | none. Static positioning (`translate(-50%,-50%)`) fine; library internals exempt |
| anything reacts to scroll position | static |
| animated counters | plain static numbers |
| all radii equal | one per element type, unreconciled across types |
| radii at the round end of the measured range | default sharp — 2–6 |
| a derived 8pt scale, **or** values scattered on purpose to look handmade | ordinary front-loaded values, odd ones only where content forced them |
| `clamp()` on type | fixed px, re-declared @1024 / @767 |
| a container query that changes the visual result | none introduced; existing project ones may stay where rendered layout is the same stepped one |
| negative letter-spacing | normal tracking |
| palette perfectly coordinated | one or two stock greys left in |
| logos normalised to one height or equal tiles | own proportions, uneven |
| a nav caret that opens nothing | real submenu, keyboard reachable, `aria-expanded`, Escape closes |
| every section has one clear distinct job | some overlap and repetition |
| could pass for a currently-admired product site | should pass for an ordinary firm's site running for years |
| ◆ icon cards | banned in professional services; carved out for a retail reassurance strip and institutional text tiles |
| ◆ two text faces | one family — except news: serif headlines over sans body is correct and measured |
| ◆ `box-shadow` on content | none in professional services; elsewhere one crude value reused only where something needs separating — count is not a target |
| ◆ density | per the archetype's model — table above |
| the build's history was never fixed or stated | year, platform, bolt-ons and maintainer chosen and reported |
| every block in the archetype's skeleton was built, in its listed order | at least two dropped; order reflects the history |
| no point chosen on the archetype's variation axes | one point per axis, stated |
| it looks like the last build from this skill | two runs on one brief must differ structurally |

## Assets

| wrong | right |
|---|---|
| a hand-authored or invented `<svg>` — drawn icon, illustration, divider, seal | icon-set glyph, official brand SVG, or a real `<img>` |
| a real vector logo downgraded to text or bitmap to satisfy the SVG rule | keep the official SVG as supplied |
| a logo rendering flat black beside full-colour siblings — SVG with no `fill`, inheriting `currentColor` | the colour variant of the same mark |
| an AI-generated or improvised image | a real sourced file |
| a placeholder box, dashed outline or "LOGO / VIDEO" marked slot | a real image — no wireframe furniture anywhere |
| an empty video player frame | a real photograph in that slot |
| hotlinked remote image | downloaded locally |
| icon is CSS shapes or a drawn path | icon-font class |
| logo is typeset text posing as a mark | real file, or company name as header text |
| "photo" is a gradient or illustration | real photograph |
| hand-written carousel or accordion | Swiper / project component, configured |
| `<img>` without `width`+`height` | both set |
| 1920px source in a 204px slot | optimised to delivered size |
| dependency added for period accuracy | maintained versions only |
| an asset's origin is unrecorded | source known, attribution kept where licence requires |

Run automated checks — ornament, two-tone wordmark, assets, contrast, focus rings, full width sweep, in one pass:

```bash
CHROME=<chrome-headless-shell> PW=<playwright-core/index.mjs> \
  node scripts/checks.mjs file:///abs/path/index.html
```

Prints image/link/shadow counts against the density band, then only failures, exits non-zero. Deliberately does **not** assert `svg.length === 0` — official brand SVGs and icon-set sprites are legitimate; confirm each traces to an icon set, brand file or project component. Prose-density checking is archetype-specific (`archetypes/professional-services.md` only; the other four genres have no paragraph-length target).

## Function

- **Contrast.** Every text node ≥4.5:1, or 3:1 at ≥24px / ≥18.66px bold. Check the three contrast traps under "Cosmetic only, never functional" in `SKILL.md`.
- **Widths.** Script covers it (14 widths, 320–1920; four breakpoints is not enough). Two offenders appear only between breakpoints: percentage float grid with fixed margins (`width:17%; margin-right:25px` × 5 fits 1440, overflows 768 — add intermediate breakpoint); unbreakable token in fixed-width box (`overflow-wrap: anywhere`).
- **Keyboard.** Everything reachable, sensible order, visible focus ring (the era dropped them; this skill does not). Every nav caret: real submenu, keyboard reachable, `aria-expanded` maintained, Escape closes.
- **Motion.** Nothing animates — confirm `prefers-reduced-motion` has nothing to silence, don't assume.
- **Images.** All load, no layout shift, real `alt`.
- **Console.** No JS errors, no failed requests.
- **Placeholders.** Zero. Every logo a real file, every photo slot a photograph. Files the user owes go in the report, not on the page.
- **Build history.** Four choices — year, platform, bolt-ons, maintainer — stated in the report, with variation-axis points picked.
- **Content mode.** Stated explicitly. Production mode: no invented entity names, addresses, registration numbers, dates, headcount, prices. Placeholder *copy* marked as such and listed; placeholder *images* do not exist.

## Then run your archetype's checklist

`archetypes/<yours>.md` ends with the genre-specific regressions; the core table cannot catch building the wrong genre.

## Final — the only question that matters

Run `visual-check.md` first: capture your page and 2–3 real sites at 1440px and **look at the images**. Everything above can pass on a page that is still visibly modern. Then ask:

> Does this look like a site that has been running and accreting for eight years?

And from the other side: **would the person described in "Who you are" have made this?** Not "does it pass" — would they have bothered? Would they have known how? Anything answering no is the thing to cut.

Not "are the tokens right" — tokens can all be right and the answer still no. Specifically:

- Anything hover-animating beyond a colour change? Must be nothing.
- Every section doing one clear job with tidy rhythm? That is a designer's page.
- Palette perfectly coordinated? One or two stock greys should sit in it.
- Density matches the genre, or is it a landing page in a costume?

**If yours looks tidier, more composed, or better art-directed than the reference, you have failed in the specific way this skill exists to prevent.**
