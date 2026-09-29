# Archetype — shop / catalogue

Retail, wholesale, parts, any priced inventory. Generator: a product catalogue plus a
merchandiser filling promo slots. **Trust = catalogue density, visible prices, stock and
delivery terms — not prose.**

Measured: a regional electronics chain (in register), a second electronics chain (drifted
modern), a large international chain (out — commissioned typeface `MMHeadline`, 175 × 8px
radii, a real design system that merely feels dated; not a target).

```
a regional electronics chain, in register      Lato only · radius 2px dominant · 28 shadows · 3 transform · 353 images
a second electronics chain, drifted modern   Poppins+Roboto · 4px ×136 · 9 shadows · 53 transform · 121 images
```

a regional electronics chain, in register is the model: **one Google workhorse face, 2px
corners, near-zero motion, an enormous number of images.**

## Overrides on the core

| core rule | here |
|---|---|
| "icon cards are the strongest AI tell" | **carve-out.** The delivery / returns / warranty / price-guarantee reassurance bar is icon + short label, and every real retailer ships one. Allowed — as a single horizontal strip of 3–5, never a grid of cards with paragraphs |
| shadows | **allowed**, 28–39 measured. One crude value reused on product tiles and dropdowns. Never a layered set |
| prose density | **inverted.** Almost no prose. A category page may carry one SEO paragraph block at the very bottom, below the grid, which is where real shops put it |
| photo bands with flat colour fill | **not a retail pattern.** Do not use |
| CTA row of 2–3 unequal buttons | one action per tile: "Add to basket" |

## Density model

Images are the page — 353 on the reference. Product tiles small and numerous: a home page
shows 40–80 products across several rails. Text per tile is a truncated name, a price, and a
stock or delivery line. Nothing breathes.

## Variation axes — measured, roll one point on each

**Roll these, do not choose them** — see "Roll the build" in `SKILL.md`. Number the axes
top to bottom starting at 0 and take letter `k` of the name for each row.

The two references differ on every axis — all combinations are authentic:

| axis | older / plainer | newer / slicker |
|---|---|---|
| nav | **left category rail** down the side of the home page, top nav minimal — very 2012–15 | full-width top mega-menu only |
| search | left, next to the logo, modest | centred and wide, dominating the header |
| hero | a static grid of 2–4 promo banners | one full-width carousel |
| type | Lato / Open Sans (a regional electronics chain, in register) | Poppins / Roboto (a second electronics chain, drifted modern) |
| tile radius | 2px (a regional electronics chain, in register) | 4px (a second electronics chain, drifted modern) |
| tile separation | 1px borders, no shadow | one crude shadow |
| price block | price only | price + was-price + `%` badge + monthly finance line |
| rails | 4-across static grids with "see all" | horizontally scrolling carousels |

A 2013 left-rail + static-banner shop looks nothing like a 2019 centred-search + carousel
one. Both pass.

## Page skeleton

Menu, not template: drop the blocks the brief has no content for — at least two. Order below
is conventional; deviations justified by the site's history are correct.

1. **Utility topbar** — store finder, order tracking, help, account, language. Dense, ~13px
2. **Header** — logo left, a wide search field taking the centre (search is the primary
   navigation), basket and account right with counts
3. **Category mega-menu** — full-width dropdown, multi-column, plain text links, no imagery
4. **Promo carousel** — full-bleed merchandiser banners with baked-in typography. Supplied
   image files, not composed in CSS. Arrows and dots
5. **Reassurance strip** — 3–5 icon+label items: free delivery over X, N-day returns,
   warranty, price guarantee, click and collect
6. **Category tiles** — a grid of 6–12, image plus name, no description
7. **Product rails** — "Deals", "Bestsellers", "Recently viewed". Horizontal scroll or a
   4–6 across grid, with a "see all" link
8. **Deal-of-the-day block** — larger tile, original price struck through, discount badge,
   sometimes a countdown
9. **Brand strip** — manufacturer logos at native sizes, full colour, uneven
10. **Editorial / guides row** — 3–4 article links with thumbnails
11. **SEO prose block** — one dense text section at the very bottom, below everything
12. **Fat footer** — 5–7 columns: departments, service, delivery, returns, corporate, plus
    payment method logos and a newsletter field
13. Cookie card

## Product tile — the load-bearing component

```
white ground · 1px #e5e5e5 border or one crude shadow · radius 2-4
image 1:1, contained, on white, no crop
name: 2 lines max, ellipsis, 14-15px, regular weight, NOT bold
price: the largest text in the tile, bold, accent or near-black
was-price struck through beside or above it, muted
discount badge: solid rectangle, top-left of the image, radius 0-2
stock/delivery line: 13px, green for in-stock, plain text
rating: filled/empty stars from the icon font + a review count in brackets
one button: solid accent, full tile width, sentence case
```

Hover: a colour change on the border or the button. **Nothing lifts, scales or shadows in** —
the single hardest place to resist motion and the most obvious tell if you do not.

## Traps

- **No equalised tile heights** via truncating to the same line count. Real grids have ragged
  names and some tiles taller.
- **Price is never a muted small caption** — the loudest element in the tile.
- **Do not design the promo banners.** Real shops ship supplied JPEGs with the type baked in.
  Fallback where the client has none: a real photograph as the slide with headline and button
  as HTML text over it — allowed and correct. Banned is *manufacturing the artwork*: CSS
  gradient, abstract shape, composed graphic standing in for a photograph.
- Reassurance strip stays cramped, 13px, directly under the header or carousel — not three
  tasteful icons with airy spacing.
- Badges ("NEW", "-30%", "FREE DELIVERY") are solid rectangles, not pills.

## Verification — this archetype

| wrong | right |
|---|---|
| product tiles lift, scale or shadow in on hover | colour change on border or button only |
| tiles equalised to identical heights by truncation | ragged names, some tiles taller |
| price in a muted small caption | price is the loudest element in the tile |
| discount badges as pills | solid rectangles, radius 0–2 |
| promo banner composed in CSS as a gradient | a supplied JPEG or a real photograph |
| reassurance strip as 3 airy tasteful icons | cramped 13px strip of 3–5, under header or carousel |
| no visible stock or delivery line | present on the tile |
| long SEO prose above the grid | one block at the very bottom, if at all |
| search is a small header afterthought | a wide field, the primary navigation |
| infinite scroll on a category page | numbered pagination |

**Product imagery.** Never stock photography and never generated. Source: the client's
catalogue export, a vendor or distributor feed, or the manufacturer's press/media asset
pages. None supplied → build the grid against real assets you can obtain for genuine
products, or ask for the feed — do not fill a shop with Unsplash.
