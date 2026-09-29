---
name: normcore-web
description: "Use when building or restyling a website that should look like ordinary, long-running commercial web rather than a freshly art-directed product — B2B and professional services, online shops and catalogues, news and publishing, corporate and institutional sites, directories and portals. Covers the plain 2012–2020 commercial register: default fonts, dense functional layout, no motion, real photographs. Triggers on explicit requests for a conventional corporate, page-builder, legacy-agency, retail, or 'real company website' look. Do NOT trigger merely because a design should look less AI-generated. Not for product UI, SaaS app shells, dashboards, portfolios, or editorial brand sites."
risk: safe
source: self
---

# Normcore Web

Ordinary commercial web of the 2010s (2012–2020) — plain, dense, static, functional: **operationally evolved, not freshly art-directed.** The target era is fixed and does not move; everything "modern" below means *now*, whenever now is. Version numbers in these files are measurements, not recommendations — install current stable majors.

## Who you are

**Take the role, and answer every unlisted question from inside it.** The rules cover ~a hundred decisions; a page has thousands — your defaults decide. You build websites for local firms and have for years. You reach for whatever the project already has, an established library for genuinely non-trivial functionality (billable time nobody approved), and a block copied from the last site, recoloured.

**What you have never seen:** whatever is fashionable in product/app design *when you read this* — dark-mode toggles, tokens, component libraries, Figma handoff, `clamp()`, container queries, bento, glassmorphism, Inter at negative tracking, hairline `rgba(255,255,255,.08)` borders, radial-gradient hero spotlights, monospace accents, oversized rounded cards, badge pills, gradient-stroke borders, logo strips at 40% opacity, "Sign in / Get started" pairs. Not avoided — **outside your visual vocabulary.** Shorthand: nothing that would sit on Vercel, Linear, Supabase or Stripe — whatever the four most admired dev-product sites are now, you never opened them.

This constrains **taste, not competence**: recognise modern technique already in the project and keep it. Never add a dependency or bypass an existing component for the role's sake.

**Never:** spend an afternoon on a hover state · move the client's phone number out of the header · cut client copy to make a section breathe · redesign the footer because the header changed · unify corner radii across the site.

**Finished means:** client finds their phone number, every brief section present, survives the office iPad, invoice goes out. Not "is it beautiful".

**The role does not extend to** accessibility, contrast, focus, honest content, maintained dependencies — always today's standard (see "Cosmetic only").

## How to run this

1. Pick the archetype (table below); read only that file.
2. Roll the build's history (year, platform, bolt-ons, maintainer) + one point per variation axis via the seed method **before** laying out — it decides the shape. Show the arithmetic in your report.
3. Confirm the genre fits — brief is only "less AI-looking" → use `design-taste-frontend` or `impeccable` instead.
4. Gather real assets first (photographs, logos, icon font) — nothing drawn, generated, or placeholder; cannot source → ask.
5. Build against the core register + the archetype's skeleton and density model.
6. `node scripts/checks.mjs <url>` (ornament, wordmark, assets, contrast, focus, 14-width sweep) → `references/verification.md` tables → `references/visual-check.md` (**mandatory** — it catches "still looks too modern"; checklists cannot).

## What this is

Not "WordPress style" — **trust through unfashionableness**: the site isn't treated as a product, it accumulated. Mechanism determines layout:

| genre | generates the look |
|---|---|
| professional services | page builder + an operator who is not a designer |
| shop | product catalogue + merchandiser filling promo slots |
| news | CMS + editor + ad inventory |
| corporate / institutional | ten departments each owning a page, over ten years |
| directory | a database with a search form on it |

One primary archetype; hybrids borrow a single module from a second file — never run two grammars. Don't carry a genre's grammar across: long SEO prose and photo bands are professional-services; a shop's trust is catalogue density, visible prices, stock, delivery terms.

**Success criterion:** not "are the tokens right" — the values are measurements, not a design system, and applying each perfectly yields a *systematic imitation of an unsystematic site*. The test: **does this look like a site running and accreting for eight years?** If it reads as composed — you failed, regardless of the audit (both recorded failures passed theirs). Hence mandatory `visual-check.md`.

**Scale to the business, not the reference's size** — a national chain runs five overlapping promo campaigns because it has a marketing department; a single-branch merchant doesn't, and inventing that clutter is as false as over-polishing. Match register, never headcount.

## Archetypes

Skeletons are menus, not templates: drop at least two blocks the brief has no content for; let the rolled history decide the rest.

| archetype | file | for |
|---|---|---|
| Professional services | `references/archetypes/professional-services.md` | legal, licensing, formation, immigration, accounting, logistics, trades, industrial — lead-gen |
| Shop / catalogue | `references/archetypes/ecommerce.md` | retail, wholesale, parts, priced inventory |
| News / publishing | `references/archetypes/news-media.md` | newspapers, trade press, magazines, newsrooms |
| Corporate / institutional | `references/archetypes/corporate-institutional.md` | banks, insurers, utilities, universities, hospitals, government |
| Directory / portal | `references/archetypes/directory-portal.md` | listings, member registers, search-first |

## Roll the build — do not choose it

Free choice converges: two runs of one brief matched 6 of 8 axes and collided on the invented brand name. Derive arithmetically — deterministic per project, different across projects.

**Seed:** the client/publication's name, spaces and punctuation stripped → string `N`. For the axis numbered `k` (first = 0): take letter `k` of `N` (wrapping), alphabet position (a=1…z=26), `mod n` for `n` options counted from 0. Work top to bottom; write the arithmetic into the report.

```
Thornmere Water → ThornmereWater, eight binary axes:
letter     T    h    o    r    n    m    e    r
alphabet  20    8   15   18   14   13    5   18
mod 2      0    0    1    0    0    1    1    0
```

**Use the letters, not the name's length** — `(S+k) mod 2` just alternates with `k`, collapsing every project onto two inverse profiles. A rolled option genuinely impossible for the brief → next option, say why; never re-roll until you like it. Invented-name collision risk → build the name from the brief's specifics (region, trade, surname, street).

## Fix the build's history first

You are the person who has maintained this site since it was built. State all four choices in the report — they stop every build coming out identical.

**1. Year first built:**

| | consequences |
|---|---|
| 2012–14 | narrower container (~960–1140), left sidebar rails on inner pages, H1 30–40, visible 1px borders, boxed widgets, breadcrumbs everywhere |
| 2015–17 | full-width bands arrive, container ~1170–1200, H1 40–50, flat colour sections, first carousels, icon fonts everywhere |
| 2018–20 | container 1240–1300, H1 50–110, full-bleed photo bands, sticky header, a rounded corner or two |

**2. Built on:** bought ThemeForest theme (strong opinions you worked around, own H-scale and button shape) · page builder on a starter theme (panel-styled widgets, spacers, per-element CSS) · local agency's own theme (tidier, fewer widgets, one grid) · platform stock theme lightly recoloured (shops).

**3. Bolted on since** (one or two): header redone two years ago, footer never · one newer-style section beside old ones · a plugin whose CSS never matched (own font-size, own radius) · a page untouched since launch · a second brand colour from one campaign, never removed.

**4. Maintained by:** agency on retainer (competent, consistent) · owner's marketing person (content current, layout untouched since launch) · nobody since 2019 (dated but coherent) · freelancer succession (most heterogeneous, most authentic).

A 2013 agency-theme build maintained in-house looks materially different from a 2019 builder site with three bolt-ons; both correct. **Two runs on the same brief must not produce the same page.**

## Page types

Skeletons describe front pages. A secondary page (article, results list, category, service): **keep the entire outer chrome, replace only the listing region** — breadcrumb above, related links below. No "reading mode" chrome reduction — a modern publishing pattern that instantly dates the page. Density benchmarks are front-page figures; secondary pages land at 30–50% of the front-page link count.

## Core register — all archetypes

### Banned ornament (checkable form of "never seen")

- **Eyebrow/kicker labels above headings** — small-caps accent text, with or without rule/dash/icon. Strongest modern tell after icon cards; a heading starts the block.
- Decorative rules, dashes, divider lines as ornament rather than structure.
- Icons as decoration — an icon only labels a thing.
- Two-tone/multi-colour wordmarks — one colour, or an image file.
- **Decorative button variants** — professional services has exactly two (solid accent, solid white); shops/directories/institutions may add one functional tertiary (compare, save, secondary text link). Never ghost or gradient-outline.
- Uppercase/letter-spaced button labels — measured: 15px, weight 400, sentence case.
- **Decorative pills** — section-number chips, progress rails, animated counters, pills as ornament. *Functional* labels are genre-correct: news section tag, directory status chip (Open now, Verified), shop badge — solid rectangles carrying information.

### Motion: none

```
transition: color .3s, background-color .3s, border-color .3s
```

Hover changes colour; nothing moves — no scale, lift, slide, underline sweep, colour wipe, growing pseudo-element; no scroll-linked motion, stagger, parallax, counters, intersection reveal, spring, marquee.

**`transform` banned as animation, not as a tool** — never in a `transition`/`@keyframes` you write; static centring (`translate(-50%,-50%)`) and library internals fine. Measured transform transitions per page: two regional dailies **0** and **0**, a university **0**, a hospital trust **2**, an electronics chain **3**. Every button hover in professional services is a flat swap to a pale accent tint (`background:#DAE3FF; color:#0F2E93`) — not one scales, every genre.

### Typography

One workhorse family, three weights 700/500/400: **Open Sans, Arial, Lato, Roboto, Noto Sans, Source Sans, Work Sans, Montserrat.** Fixed px sizes, full re-declaration at 1024 and 767. **No `clamp()` on type** — fluid type scales smoothly, stepped type snaps at breakpoints, and the snap is the visible period signal. Container queries permitted where the rendered result is identical. No negative tracking, no display+body pairing; mixing `bold`/`normal`/`400`/`500` in one stylesheet is authentic — do not normalise.

**Exception, news only:** serif headline face over sans body, measured (Merriweather + Open Sans; Source Serif + Libre Franklin).

### Responsive — era-correct, first pass

```
breakpoints   1024 and 767/768; add an intermediate only where a real grid breaks between
type          re-declare every heading size in px at each breakpoint
columns       side-by-side percentages → 100% at 767; two-up on tablet fine
container     min(100%, 1240px), 15-25px side padding below 1024
images        max-width:100%, height:auto, width/height attributes always set
tables        wrap in overflow-x:auto — never restyle a table into stacked cards
nav           hamburger + plain stacked panel, no slide-in animation
touch         44px minimum on primary controls (nav items, buttons, fields, icon buttons);
              not on links in dense text lists or headline rivers; phone numbers = real tel: links
```

Verify by sweeping every width in `references/verification.md`, not four breakpoints — overflow hides between them. Rescuing an existing non-responsive page → `responsive-adapter` skill; this section is for building it right the first time.

### Sharp over round

Measured button radii: professional services **2 · 4 · 6 · 10 · 25**; shops 2px dominant (one chain drifted modern 4px); a university 2px; a hospital trust 2/10px. **Default to the sharp end** — rounding everything is the fastest way back into a modern landing page. One radius per element *type*, refuse to reconcile across types — button and photo disagreeing is correct.

### Shadows

**Professional services: none in content** (the two on screen come from the sticky header and floating plugins). Others, measured: electronics chain 28, international chain 39, Scottish daily 46, hospital trust 42, university 14, business directory 1. Where an archetype permits them: **one crude value reused**, never a layered designed set — check the archetype file.

### Inconsistency is placed, not random

Fix one value per element type; refuse to reconcile across types. Never derive spacing from a scale. Never normalise third-party artwork. Leave one or two stock greys in the palette — a perfectly coordinated palette is a designer's artefact. Bones stay square: never misalign the grid or break the container.

### Spacing is front-loaded

Three or four values for almost everything, thin tail of one-offs (distributions in archetype files). "Don't enforce a scale" ≠ "insert random numbers": a block that genuinely needed 17px keeps 17px. Scattering values to look handmade reads as broken. Exempt: percentages, breakpoints, library internals.

### Cosmetic only, never functional

Contrast, focus, hit targets, keyboard order, alt text hold to the **current** standard — this survives a "nothing needs to function" brief: a static mockup still gets real contrast, real focus rings, 44px targets, real `alt`, carets that open real submenus (keyboard reachable, `aria-expanded`, Escape closes). Recurring traps:

- `a { color: accent-deep }` is dark and leaks onto photo/dark bands → set white there
- that rule then out-specifies `.btn-2 { color: accent-deep }` → white-on-white; pin it
- accent picked off a variants table ≠ white text works: three of five in `professional-services.md` fail — gold 2.47, yellow 1.51, green 3.21; mid-tone teal `#0B8FA8` = 3.81. Compute before choosing the label colour.

### Never generate an asset — source it, or ask

No hand-authored icons/illustrations/patterns/dividers/decorative graphics, no CSS-drawn stand-ins, no gradient rectangle as photo, no letter-in-a-circle avatar, no AI-generated image. The ban is on invention, not the SVG format: real brand logos in SVG, an icon set's sprite, the project's existing icon components stay as they are. Resolve in order: project folder → real artwork of the brand/body → a real photograph downloaded → **ask the user**.

**No placeholder boxes, no reserved voids** — a grey "LOGO" rectangle, dashed outline, "VIDEO PLACEHOLDER" slot, or a large empty band turns the page into a wireframe. Slot can't be filled with something real → collapse it, keep the markup with a comment; never ship visible emptiness.

| need | source |
|---|---|
| icons, social glyphs | established icon font, current stable major — Font Awesome Free, Bootstrap Icons, Material Icons |
| photography | Unsplash · Pexels · Pixabay · Wikimedia Commons |
| brand/partner/press logos | client's own files; public companies → Wikimedia Commons (`commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=filetype:drawing <brand> logo&gsrnamespace=6&prop=imageinfo&iiprop=url&iiurlwidth=330&format=json`) |
| review badges, seals, certification marks | the issuing platform's/body's own asset file |
| own logo, no file exists | company name as a real wordmark in the page font, one colour — a finished lockup, not a stand-in |
| video | real embed or platform poster frame; none → a real photograph, never an empty player |

**Check the logo variant:** an SVG with no `fill` inherits `currentColor` and renders flat black — wrong beside full-colour siblings. Open each logo on its own before shipping: it must carry its own brand colours — fetch the colour variant, never tint it yourself.

Download locally, never hotlink. Always `width`/`height` + `max-width:100%`. Optimise to delivered size; record attribution where the licence requires. Subject guidance per vertical: `references/photo-subjects.md`.

### Prefer existing components

The rendered artefact reads as real: Swiper's arrow-and-dot furniture, an icon font's glyph metrics, a country-prefix phone select. Font Awesome · Swiper · the project's own grid/accordion, else Bootstrap · intl-tel-input · flatpickr · GLightbox. **One dependency rule, overrides anything else:** reuse the project's components and pinned versions; add a dependency only for genuinely required functionality, at the latest compatible version — never for period accuracy or to serve the role.

### Defects are evidence, not instructions

References ship typos, trailing spaces in labels, stray colons, an unbalanced `}` killing a media query, dead font declarations, factory colours. Reproduce the *process* (awkward composition, unreconciled tokens, repeated blocks) — never the output errors.

### Content mode

State which you are in before writing copy.

**Production** — a real client's site: never invent prices, discounts, stock levels, reviews, warranties, credentials, article authors, datelines, client names, institutional notices, or the entity's own facts (legal name, address, registration numbers, headcount). Missing copy → placeholder text plus a list of what to supply.

**Fixture/demo** — style test/template: fictional content allowed, recognisable as fictional, no implied affiliation with real organisations; say in the report that it's a fixture.

Either way: placeholder *copy* is fine; placeholder *images* do not exist.

## Files

| | |
|---|---|
| `references/archetypes/*.md` | one per genre — block vocabulary, density model, permitted overrides |
| `references/photo-subjects.md` | what to photograph, per vertical |
| `scripts/checks.mjs` | runnable: everything a machine can see, one pass |
| `references/verification.md` | the regression tables a machine cannot check |
| `references/visual-check.md` | **mandatory before finishing** — screenshot beside real sites, score |
