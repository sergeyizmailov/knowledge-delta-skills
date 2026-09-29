# Archetype — professional services

Lead-gen for legal, licensing, formation, immigration, accounting, logistics, trades,
industrial services. **The densest and most measured archetype.** Generator: a page builder
and an operator who is not a designer.

Reference teardown: 2010s WordPress + Elementor Pro build. Stack and exact versions under
Measured evidence are proof of what was measured, not install recommendations.

## Overrides on the core

| core rule | here |
|---|---|
| shadows | **zero in content.** Only a sticky header and floating widgets cast. The reference stylesheet contains no `box-shadow` at all |
| density | prose, not links. 60–90 word paragraphs, 2–3 per band |
| icon cards | banned outright — the single strongest AI tell |

## Density model

Prose volume is the point. Each band: heading + 2–3 substantial paragraphs + a CTA row.
65–75 character measure, 1.5 line-height, paragraphs reaching the bottom of the block.
~40 images, ~12 buttons, low link count. If supplied copy is short, request more — do not
let the layout collapse into whitespace.

## Rhythm

**white band → photo band → white → photo.** Bands `100px 0`, full width, container inside.
Photo bands close with a centred CTA row. One column — no sidebars, no offset grids.

Social proof order: review badges → awards → video testimonials → cases → press logos.

## Modes

| | hero | type |
|---|---|---|
| **A** default | full-bleed photo under a flat semi-transparent fill, uppercase heading over it | one sans, 700 uppercase |
| **B** | no photo, centred sentence-case heading, one CTA plus a text link | Inter / Rubik 600 |
| **C** ceiling, on request only | split, or serif display over photo | one serif display + one sans |

## Tokens — Mode A

```
type      one family. 700 headings uppercase / 500 nav+labels / 400 body
          H1 50/60  H2 40/52  H3 30  H4-5 20  H6 16  body 16/24
          @1024 H1 40 H2 30 H3 30   @767 H1 36 H2 26 H3 26 + headings align left
colour    --accent buttons · --accent-deep links + nav active · --accent-pale hover on dark
          --highlight one gold note used twice site-wide
          --text #333 · --bg #fff · --band-fill rgba(accent-deep, .62–.66)
metrics   container min(100%,1240px) · bands 100px 0 · split columns 49% / 48%
radii     button 2-6 · photo 10 · panel 12 + 2px solid accent · chip 50 · input 3
buttons   solid accent + solid white, no third variant
          label 15px / 400 / text-transform:none / sentence case
```

## Page skeleton — a menu, not an order

1. Utility topbar — socials, phone with glyph, "Send us an Email"
2. Sticky header — logo + italic serif tagline, uppercase nav with carets
3. Hero — full-bleed photo + flat fill, uppercase H1; below it a 49/48 split, dense copy left,
   video or 16:9 photo right; one centred CTA row under both
4. White band — H2 + 2–3 paragraphs; 50/50 with a photo, no frame
5. Photo band — white H2 + prose, closing with 2–3 unequal CTAs
6. Repeat 4–5 per service pillar
7. Badges → awards carousel → video testimonials → cases → press logos → partner grid
8. FAQ — plain accordion, no card
9. Dark footer — legal entity name in caps, full street address with icons
10. Floating — chat, cookie card, captcha, only where a real integration exists

## Widget census — one page, the professional-services reference

```
container 109 · wrap 64 · image 40 · heading 15 · text-editor 13 · SPACER 13 · button 12
icon-list 4 · social-icons 3 · video 2 · testimonial-carousel 2 · form 1 · accordion 1
divider 0 · table 0 · back-to-top 0 · banner strip 0
```

What is there (the zeros mean critique-expected furniture is absent):

- **13 Spacers** stacked on top of band `100px` padding. Heights
  `75 ×9 · 100 ×7 · 50 ×3 · 10 ×3 · 80 ×2 · 20 · 15`. Rhythm is an operator dropping
  spacers until it looked right, not a scale.
- **Checkmark icon-lists** — period-correct, unlike icon cards.
- **Repeated CTAs**: "Send us an Email" ×2, phone ×2 on one page.

Sample size one page — real-build proportions, not law.

## Compositional awkwardness

Deliberate and specific, not random. Apply three or four:

- Same widget styled differently in two places: the reference declares button hover per
  element ID, six times, one on a different accent variable → one CTA whose hover colour
  differs from siblings.
- Vertical space via bare spacer divs (75px, two or three across the page), not section padding.
- Top-align columns with unequal content — ragged bottoms; two adjacent columns with
  different inner padding.
- Same CTA repeated three times with slightly different labels.
- One SEO section restating a service pillar in different keywords — keep it navigable and
  labelled; do not muddle the information architecture.
- Let one heading wrap rather than tuning it to fit.

## Block construction

| block | how |
|---|---|
| Photo band | `background: linear-gradient(fill, fill), url(photo) center/cover` — two identical stops. `padding:100px 0`, white text |
| CTA row | `flex; justify-content:center; gap:25px; flex-wrap:wrap` — no `min-width`, no `flex:1` |
| Split block | `49% 48%`, `gap:30px`, image radius 10, `align-items:center` |
| Badge row | flex, `space-between`. Native proportions, never a uniform CSS height, dimensions always set |
| Award carousel | 4 visible slides, chevrons outside the track, dots beneath |
| Stat tiles | 5–6 tiles, `border-radius:0`, dark fill, `gap:2px` seams |
| Coverage grid | `width:17%; float:left; margin:0 25px 25px 0`. Needs an intermediate breakpoint or it overflows at 768 |
| FAQ | `h3` question, answer in a div with left padding, chevron from the icon font |
| Lead form | stacked labels, r3 inputs, phone field with a flag-prefix select, `max-width:240px` |

## Verification — this archetype

| wrong | right |
|---|---|
| row of 3 icon cards | prose band + CTA row |
| no Spacer divs, no checkmark list | present |
| divider rules, banner strips, back-to-top, related-services | absent — the reference has none |
| any `box-shadow` on content | flat; only header and floating widgets cast |
| hero is one full-width column | 49/48 split, copy left, media right |
| a prose band with one short paragraph | ≥2 paragraphs, ≥110 words total, one ≥55 |
| no utility topbar | socials + phone + email link |
| hero overlay is a real gradient | two identical stops = flat fill |
| CTAs share a `min-width` | widths hug labels |
| every CTA label distinct | one repeats across the page |
| columns balanced and bottom-aligned | ragged, top-aligned, unequal inner padding |

## Accent palettes — professional services

**Accent** — swap `--accent` and the band fill; everything else holds.

**Contrast is measured, and three of these cannot take white button text.** Hex values are
real, off live sites; button label colour not optional.

| accent | vs white text | button label | band mood | seen on |
|---|---|---|---|---|
| `#3868FA` royal blue | 4.64 | white — passes, barely | navy over glass towers | the professional-services reference |
| `#1BA631` green | **3.21 FAIL** | darken to ~`#0F7A1F` first | navy over glass towers | a sibling build by the same agency |
| `#BFA161` gold | **2.47 FAIL** | use `#333` text (5.11) | warm sepia over city skyline | a company-formation firm |
| `#FFCC00` yellow | **1.51 FAIL** | use `#333` text (8.36) | near-black over dark tech photo | a corporate-services firm |
| purple | measure it | — | violet over people-with-phones | a fintech consultancy |

Pale accents are button *fills with dark labels*, not failed dark accents. Do not darken gold
or yellow into mud — put `#333` on them, as the real sites do.

**Heading scale** — heavier weight = smaller size. Both extremes authentic.

| H1 | weight | case | seen on |
|---|---|---|---|
| 50 / 60 | 700 | upper | the professional-services reference |
| 64 / 76.8 | 700 | upper | a fintech consultancy |
| 110 / 110 | 700 | upper | a corporate-services firm |
| 100 / 130 | **400** | sentence | an international law firm |
| 36 / 36 | 700 | upper | a company-formation firm — Alice serif + Nunito body |

**Button radius** — one per project; other element types still disagree with it.
Measured across five sites: `2` · `4` · `6` · `10` · `25` (pill). Default to the sharp end.

## Measured evidence — the professional-services reference, as captured

Stack as captured (evidence, not shopping list): WordPress 7.0.4 · Elementor Pro 3.29.2 · `hello-elementor-child` · WP Rocket 3.22 ·
Cookie Law Info · `sticky-chat-widget` · reCAPTCHA Enterprise · `intlTelInput` · Swiper 8 ·
Font Awesome.

Tokens live in the Elementor Global Kit; everything else bolted on in Appearance → Custom CSS
— ~7 KB of hardcoded px with `!important`, overrides keyed to element IDs, one unbalanced
`}` inside a `@media` block silently killing the rest of it.

- Kit declares Heebo for headings. **Every rendered node resolves to Open Sans** — dead declaration.
- Elementor factory defaults `#54595F` / `#363A3F` never changed, still ship.
- Home-page radii: `50% 10 6 3 20 28 2 50` — eight.
- Motion observed (not a spec — default build is static): only
  `fadeInLeft` / `fadeInUp` / `fadeInRight` and `elementor-animation-grow`.
- Breakpoints: hard 1024 and 768, every heading size fully re-declared. No `clamp()`.
- Copy: parallel SEO formula — `WE CAN PROVIDE…` / `WE CAN OBTAIN…` / `WE CAN OFFER…`.

### Per-page stylesheet — `uploads/elementor/css/post-1536.css`, 66 KB, 152 elements

The distributions are the whole of it — no system, values reused until they ran out.

```
padding        15px ×4 shorthand ×26   0 25px 0 0 ×25   0 0 0 0 ×23   0 25px 0 25px ×8
               0 50px ×5   0 15px ×5   0 30px ×4   10px ×4   0 0 50px ×4   100px 0 ×2
border-radius  20px 20px 20px 20px ×4     0px ×2        <- two values, whole page
box-shadow     ZERO occurrences
font-size      15 ×19   20 ×4   14 ×2   30 ×1           <- four values, whole page
font-weight    400 ×13   bold ×5   normal ×2   500 ×1   <- keywords and numbers mixed
transition     only the two canned builder strings, 12 uses each
column width   100% ×6   49% ×2   48% ×1                <- not 50%
media queries  max-width:1024px | max-width:767px | min-width:768px
```

Spacing across three page stylesheets — `15 / 25 / 10 / 50` = 292 of 361 declarations (81%),
the eight common values = 329 (91%), tail = 32 (9%):

```
15 ×129   25 ×93   10 ×39   50 ×31   100 ×10   5 ×10   20 ×9   30 ×8
tail:     17 ×12   75 ×9    34 ×4    8 ×2     35 ×2    70 ×1   1 ×2
plus `00px` ×2 — a literal typo in the hand-written Custom CSS
```

Takeaways: always four-value shorthand · no shadows in content (on-screen ones come from the
sticky header and floating plugins) · colours via kit variables, sizes and spacing not ·
one `#2B313A` and one `#000` bypass the kit entirely.

## Reference grading

| in pattern (Mode A) | drifting | off pattern |
|---|---|---|
| the professional-services reference/.com, a fintech consultancy, an international law firm, a corporate-services firm | a company-formation firm (serif display, gold on cream), a Gulf corporate-services firm (translucent hero panel, r0 tiles) | —, —, —, —, —, —, —, — |

Off-pattern sites have real designers behind them — better designed, therefore wrong here;
copying them lands back in generic-modern territory. Use as Mode C only.

## Raw material and mining a live reference

Era-correct GPL theme source, all verified: [ColorlibHQ/illdy](https://github.com/ColorlibHQ/illdy)
2016 · [wpexplorer/wpex-corporate](https://github.com/wpexplorer/wpex-corporate) 2017 ·
[paragonthemes/nexas](https://github.com/paragonthemes/nexas) 2018 ·
[okfn/wordpress-theme](https://github.com/okfn/wordpress-theme) 2018, Bootstrap-based ·
[ceylonthemes/wordpress-business-theme](https://github.com/ceylonthemes/wordpress-business-theme)
2019 · [colorlib.com/wp/cat/bootstrap](https://colorlib.com/wp/cat/bootstrap/). Any Elementor
template kit for a law, finance or consulting niche is the actual source of the aesthetic.

To mine a live reference:

```bash
curl -sSL -A 'Mozilla/5.0' https://example.test -o page.html
grep -oiE "href='[^']*\.css[^']*'" page.html | sed "s/href='//;s/'$//" | sort -u
# uploads/elementor/css/post-<id>.css is the goldmine
```

Count distinct values of `padding`, `border-radius`, `font-size`, `box-shadow`. The size and
rawness of those sets is all the structure there ever was.
