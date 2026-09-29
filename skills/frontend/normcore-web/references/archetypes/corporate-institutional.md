# Archetype — corporate / institutional

Banks, insurers, utilities, universities, hospitals, government, large multi-department
firms. Generator: **ten departments each owning a page, over ten years.** Numerically the
largest category of sites in this register.

Measured:

```
a university     Open Sans + Arial + FontAwesome · 2px/5px · 14 shadows · 0 transform
               34 images · 261 links · WordPress: TRUE
a hospital trust   Arial + Open Sans · 2px/10px · 42 shadows · 2 transform
               18 images · 150 links
a large energy utility, drifted modern      Cabin · 15px ×135 · 28 shadows · 8 transform      <- drifted modern, not a target
```

The two in-register sites: **Arial and Open Sans**, 2px corners, essentially no motion.
a hospital trust renders **18 images on the whole page** — the inverse of a shop.

## Overrides on the core

| core rule | here |
|---|---|
| shadows | allowed, 14–42 measured. One value on cards and menus |
| prose density | moderate. Short intro paragraphs, then links. Not the professional-services wall of text |
| images | **few.** 18–34. Text and links carry the page |
| photo bands with flat colour fill | occasionally one hero band; not a repeating rhythm |

## Variation axes — measured, roll one point on each

**Roll these, do not choose them** — see "Roll the build" in `SKILL.md`. Number the axes
top to bottom starting at 0 and take letter `k` of the name for each row.

| axis | one real point | the other |
|---|---|---|
| type | Open Sans (a university) | **Arial** (a hospital trust) — plainer, and very authentic |
| images | 34, a photo per department | 18, text and links carry it |
| links | 261 | 150 |
| hero | one photo band with a short heading | a plain solid-colour strip, no photo at all |
| audience routing | a topbar switcher | a row of large labelled blocks below the hero |
| nav | 8 top-level items with multi-column dropdowns | 5 items plus a left sidebar tree on inner pages |
| news | two columns of dated items | one column plus a separate events list |
| a11y controls | text-size and contrast in the topbar | an accessibility page linked from the footer only |

## Density model

150–261 links, 18–34 images. The page is a **routing surface**: eleven audiences to eleven
departments, each audience a labelled entry point rather than a persuasive argument. Write
signage, not marketing copy.

## Page skeleton

Menu, not template: drop the blocks the brief has no content for — at least two. Order below
is conventional; deviations justified by the site's history are correct.

1. **Utility topbar** — audience switcher (For students / For staff / For patients / For
   investors), language, A11y controls (text size, contrast), search toggle
2. **Header** — crest or wordmark, often with a sub-brand lockup, and a prominent search
3. **Primary nav** — 5–8 items with multi-column dropdowns. Depth is the point
4. **Hero** — one photo band with a short heading and one or two links, or a plain coloured
   strip with the institution's current priority. Not a sales hero
5. **Audience quick-links** — a row of labelled blocks, one per audience. Text-first
6. **Service / department grid** — 6–12 plain tiles, each a short title and a one-line
   description. This is the icon-card shape the core bans; here it is allowed **only** as
   text tiles with no icons, or with one small icon-font glyph and no paragraph
7. **News and events** — two columns, dated items with short headlines. Institutions publish
   constantly and showing it is the trust signal
8. **Notices / alerts** — a coloured strip for service disruption, closures, deadlines
9. **Documents and downloads** — a plain list of PDFs with file type and size shown
10. **Statistics row** — plain numbers with labels, static, never animated
11. **Partner and accreditation logos** — real files, native sizes, uneven
12. **Fat footer** — every department, contact, accessibility statement, privacy, freedom of
    information, complaints, careers, and the full registered address

## Furniture that carries the genre

Accessibility statement link in the footer · text-size and contrast controls in the topbar ·
a "last reviewed / last updated" date on content · document lists showing `PDF, 240 KB` · a
complaints or feedback route · an emergency or out-of-hours contact block · a site map link.

None decorative. Their absence is why an institutional page built from instinct reads as a
startup.

## Traps

- **Do not consolidate the navigation.** Eight top-level items with deep dropdowns is
  correct; four tidy ones is not.
- **No value proposition.** The hero says what the institution is or what is happening now,
  not why you should choose it.
- **Do not animate the statistics.** Counters ticking up is the strongest single tell here.
- **Keep the notices strip** despite ugliness — the most authentic element.
- Multiple sub-brands with slightly different logo lockups is normal — do not unify them.

## Verification — this archetype

| wrong | right |
|---|---|
| navigation consolidated to four tidy items | 5–8 top level with multi-column dropdowns |
| a marketing value proposition in the hero | what the institution is, or what is happening now |
| animated statistics | plain static numbers |
| notices / alerts strip removed for tidiness | present |
| service tiles with icons and paragraphs | text tiles, one line each |
| no "last updated" dates | present on content |
| document links without type and size | `PDF, 240 KB` shown |
| no accessibility statement or text-size controls | both present |
| sub-brand lockups unified | left inconsistent |
| image count near a shop's | 18–34 is correct; text and links carry the page |
