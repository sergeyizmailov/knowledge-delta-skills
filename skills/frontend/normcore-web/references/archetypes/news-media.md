# Archetype — news / publishing

Newspapers, trade press, magazines, company newsrooms. Generator: a CMS, an editor filling
slots on deadline, ad inventory. **Trust = volume, recency, hierarchy.**

Measured:

```
an English regional daily   Merriweather + Open Sans · radius 4-5px · 5 shadows · 0 transform
                      145 images · 278 links · 5 ad slots
a Scottish daily   Source Serif 4 + Libre Franklin · 5px/3px · 46 shadows · 0 transform
                      112 images · 424 links · 54 lists · 6 ad slots
a national tabloid, drifted modern             Noto Sans · 8px ×83 · 6 shadows · 6 transform · 151 images · 265 links
```

**Zero transform transitions on both English papers** — the register holds hardest here.

Reference availability rots: the English regional daily now serves a Cloudflare challenge to
headless browsers; the Scottish daily still works. If a reference is unreachable, substitute
another regional daily or trade title of the same vintage — any county newspaper site will
do; the measurements stand on their own.

## Overrides on the core

| core rule | here |
|---|---|
| one sans family | **serif headlines over a sans body is correct and measured.** Merriweather / Source Serif / Noto Serif for headlines, Open Sans / Libre Franklin for body and furniture. The only archetype with a two-face pairing |
| shadows | allowed, 5–46 measured. One value, on cards and dropdowns |
| prose density | **links, not paragraphs** — see below |
| photo bands, CTA rows | not a news pattern |

## Density model — link count is the defining variable

**265–424 links on one page**, 112–151 images, 14–54 lists — measured on complete home pages.
Benchmark for a full page, scaled to the content actually supplied; do not pad toward it with
invented articles.

Link count is the genre test: it separates a news home page from a blog. Thirty links means
you built a blog. A small company newsroom will not reach this — route it to
`corporate-institutional.md` and use this grammar only for its article list.

## Page skeleton

Menu, not template: drop the blocks the brief has no content for — at least two. Order below
is conventional; deviations justified by the site's history are correct.

1. **Masthead** — wordmark centred or hard left, today's date, weather, edition/place name
2. **Section nav** — horizontal, News / Sport / Business / Opinion / Lifestyle / Jobs /
   Notices / Announcements. Uppercase or sentence, 14–15px, often a second tier below
3. **Leaderboard ad** — full width, directly under the nav, at real IAB dimensions (728×90 or
   970×250) reserved with fixed height so it does not shift
4. **Lead story** — one large image, a big serif headline, a standfirst, byline and timestamp
5. **Secondary leads** — 2–4 across, medium images, serif headlines, no summaries
6. **Article river** — the main column: repeated rows of thumbnail left, headline plus
   section-tag and timestamp right. Twenty or more. Produces most of the link count
7. **Sidebar** — "Most read" numbered list, an MPU ad (300×250), newsletter signup, another
   MPU further down
8. **Section blocks** — a heading strip per section (Sport, Business), each with 4–6 links
9. **In-river ad slots** — one every 5–8 items
10. **Notices / classifieds strip** — deaths, planning, public notices. Very in-register
11. **Fat footer** — every section, contact, advertise with us, terms, ownership, a second
    masthead of sister titles

## Variation axes — measured, roll one point on each

**Roll these, do not choose them** — see "Roll the build" in `SKILL.md`. Number the axes
top to bottom starting at 0 and take letter `k` of the name for each row.

| axis | one real point | the other |
|---|---|---|
| masthead | wordmark hard left, nav beside it | wordmark centred, date left, weather right |
| headline face | Merriweather (an English regional daily) | Source Serif 4 + Libre Franklin (a Scottish daily) |
| shadows | 5, borders do the work | 46, cards everywhere |
| link count | ~278 | ~424 |
| lead treatment | one large lead + 2–4 secondary across | a 2-column split lead with a "more top stories" list beside it |
| river | thumbnail left, headline right | headline-only list with an occasional image |
| sections | one long river then section strips | section strips only, no single river |
| sidebar | Most Read + MPU + newsletter | Most Read + weather + notices + two MPUs |

## Article page — the other template

Keeps the home page's outer chrome and swaps the river for the story:

1. Utility topbar, masthead, section nav — **identical to the home page**, never a reduced
   "reading mode" header
2. Leaderboard slot — same rule as above; collapse it if unfilled
3. Breadcrumb — `Home › Section › Place › headline`, ~13px
4. Section tag, then the H1 in the serif face, then an italic standfirst of one or two
   sentences
5. Byline row — author with role, `Published` and `Updated` timestamps, share glyphs
6. Lead image, full column width, caption and credit line beneath in small muted text
7. Body — 300–800 words in short paragraphs of two or three sentences. A pull quote, a
   subheading or two, an in-body ad after the third or fourth paragraph
8. Tag list, then a "Related stories" block of 3–6 links
9. Sidebar — Most Read numbered list, MPU slot, newsletter box, one section block of further
   links. Same sidebar the home page uses; a CMS does not vary it
10. Comment count or a comments block
11. Notices strip and the fat footer — identical to the home page

**Article-page density: 80–140 links** — far below the home page's 265–424 because the river
is gone, but the chrome still carries most of it. Under 50 means you stripped the furniture
to a blog post. Images: 6–12 — one lead plus sidebar and related thumbs.

Applies to every archetype: **a detail page keeps all the chrome and replaces only the
listing region.** Stripping it for reading comfort is what makes it look like a modern
publication.

## Article furniture

Byline · timestamp with "Updated" · section tag as a small solid rectangle in accent above or
beside the headline (a tag, not a banned kicker — it is a link and it labels a section) ·
share row using icon-font glyphs · "Read more" links · related-stories list at the end ·
comment count.

## Ad slots are the aesthetic

5–6 per page, measured. Not clutter — their presence is half of why the page reads as a real
publication. Reserve space with a fixed-height container at real IAB sizes: 728×90, 970×250,
300×250, 300×600, 320×50 mobile.

**No real ad tag → collapse the slot** (omit the container or leave it zero-height), keep the
markup as a comment naming the slot and its IAB size, and report which slots are unfilled. A
visible blank band or grey "advertisement" placeholder reads as broken layout, not as a real
publication.

Filled slots get fixed dimensions — an ad that loads late and shifts the page is worse.
"Unstyled" means no chrome, borders or filler text; not no sizing.

## Traps

- **No summaries.** River items are a headline and a timestamp; a two-line description on
  every item halves the density and reads as a blog.
- **Do not equalise thumbnails to one aspect ratio.** Lead wide, river thumbs small and
  near-square, sidebar none.
- **Keep the timestamps.** Recency is the trust signal; leads show "Updated".
- No generous whitespace between sections — heading strip straight into links.

## Verification — this archetype

| wrong | right |
|---|---|
| river items carry a two-line summary | headline plus timestamp only |
| under ~200 links on a full home page | 265–424 measured; scale to the content supplied |
| no timestamps | every item dated; leads show "Updated" |
| thumbnails all one aspect ratio | lead wide, river small, sidebar none |
| no ad slots planned at all | 5–6 positions identified at real IAB sizes; filled ones get fixed heights, unfilled ones collapse |
| a visible empty band where an ad would go, or a grey "advertisement" placeholder | unfilled slots collapsed to an HTML comment naming the IAB size; space reserved only once a real tag fills it |
| generous whitespace between sections | heading strip, then straight into links |
| sans headlines | serif headline face over a sans body |
| no "Most read" or notices block | present |
