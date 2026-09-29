# Archetype — directory / portal

Listings, business registers, member directories, classifieds, property and job boards,
search-first sites. Generator: **a database with a search form on it.**

Measured: a national business directory — Open Sans + Source Sans 3 · radius 5px ·
**1 shadow** · 2 transform · **10 images** · 173 links. Ten images and one shadow on the
entire page: the plainest archetype of the five.

## Overrides on the core

| core rule | here |
|---|---|
| shadows | effectively none, 1 measured. Borders do the separating |
| images | **almost none.** 10. Listings carry a small logo or thumbnail at most; many have neither |
| prose density | near zero. One SEO block at the bottom of a results page |
| photo bands, CTA rows | not a pattern here |

## Density model

Page = **form plus rows**. Two numbers matter: the search controls above the fold and the
number of result rows below. Everything else subordinate.

## Page skeleton

Menu, not template: drop the blocks the brief has no content for — at least two. Order below
is conventional; deviations justified by the site's history are correct.

1. **Utility topbar** — add your business, advertise, log in
2. **Header** — wordmark, then the search block, which is the page
3. **Search block** — two or three fields side by side: what, where, and often a category
   select. A solid accent submit button. Sits highest and is visually loudest
4. **Popular categories** — a dense multi-column list of plain text links, 20–60 of them.
   Not tiles, not cards. Source of most of the link count
5. **Results or featured listings** — repeated rows, see below
6. **Location list** — every town or region as a link, in columns
7. **A–Z index** — letters as links across a strip
8. **SEO prose block** — bottom, below everything
9. **Fat footer** — categories, locations, about, terms, add a listing

## Results page — the other template

Keeps the front page's chrome and swaps the category columns for the result set:

1. Utility topbar and header **unchanged**, with the search block still loud and still at the
   top — pre-filled with the current query, never shrunk to a small header input
2. Breadcrumb — `Home / Category / Place`
3. H1 stating the query in words (`Plumbers in Marlport`), result count beneath
   (`Showing 1–15 of 62 results`), sort dropdown on the same line, right-aligned
4. Filter sidebar left or above — plain checkboxes with counts in brackets
5. The result rows
6. Numbered pagination
7. **A trimmed related-searches strip** — nearby towns, adjacent categories, "plumbers near
   Marlport". Real directories keep this; it is SEO interlinking and correct here. Drop the
   front page's full A–Z index and location list
8. One short SEO paragraph, then the fat footer

Link count lands around 90–120 against the front page's ~173 — the categories wall is gone
but the chrome and the related-searches strip remain.

## Variation axes — roll one point on each

**Roll these, do not choose them** — see "Roll the build" in `SKILL.md`. Number the axes
top to bottom starting at 0 and take letter `k` of the name for each row.

Only one reference was measured (a national business directory) — these are the genre's
common variants, plausible not verified:

| axis | one way | the other |
|---|---|---|
| search block | three fields in a bordered panel | two fields inline on a coloured band |
| filters | left sidebar of checkboxes | a horizontal filter bar above the results |
| listing thumb | small logo left | no image at all, text-only rows |
| listing actions | a solid button plus a text link | phone number as the primary action, no button |
| rating | stars plus a review count | a numeric score in a solid square |
| categories | a dense multi-column text list | an A–Z index only |

## Listing row — the load-bearing component

```
one row, 1px bottom border, no card, no shadow, radius 0-2
optional 60-80px logo or thumbnail on the left; many rows have none — that is correct
business name: link, accent-deep, 16-18px, weight 600
category and address on one muted line beneath
phone number shown in full as text
star rating + review count from the icon font
2-3 small tag chips (Open now, Verified, Delivers)
right side: one solid accent action button, plus a plain text secondary link
```

Rows are **not equal height** — some have a logo, some do not; some have three tags, some
none. Do not normalise them into identical cards; the raggedness is the genre.

## Furniture

Pagination as numbered page links with Previous / Next, never infinite scroll · result count
("1–25 of 1,340") · sort dropdown · filter sidebar of plain checkboxes with counts in
brackets · breadcrumb above the results · map panel, if any, as a static embed rather than an
interactive canvas.

## Traps

- **No listings as cards on a grid.** Rows in one column with hairline separators.
- **No "show number" button on phone numbers** unless the client asked — full text is the
  older, more trustworthy pattern.
- **No infinite scroll.** Numbered pages are the tell.
- **No category lists as tiles with icons.** Plain text links in columns.
- The search block is loud and slightly crude — do not refine it into a tasteful single input.

## Verification — this archetype

| wrong | right |
|---|---|
| listings as cards on a grid | rows in one column, hairline separators, no shadow |
| rows normalised to equal height | ragged — some have logos and tags, some none |
| category lists as tiles with icons | plain text links in columns |
| infinite scroll | numbered pagination with Previous / Next |
| no result count or sort control | "1–25 of 1,340" plus a sort dropdown |
| phone numbers hidden behind a button | shown in full as text, unless the client asked |
| the search block refined to one tasteful input | two or three fields, loud, slightly crude |
| more than a handful of images | ~10 measured; listings carry a small logo at most |
| a two-tone wordmark in the header | one colour — run the grouped-by-size check in `verification.md` |
| the search block shrunk to a header input on a results page | still loud, still at the top, pre-filled |
