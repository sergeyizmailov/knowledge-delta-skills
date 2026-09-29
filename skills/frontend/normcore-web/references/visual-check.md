# Visual check

The token checklist cannot detect "still looks too modern" — both recorded failures passed their audits. **Look at the page next to a real one before calling it done.** Not optional; cannot be replaced by reading the CSS.

## Capture

Pick the two or three references matching **your archetype**, never a generic sample. **No named URLs on purpose** — they rot (redesigns, bot challenges, disappearances). Find live references by search, never skip the comparison because one broke — substitute.

| archetype | search for |
|---|---|
| professional services | `"company formation" OR "licensing consultancy" site:*.com` · a law or accountancy firm trading 15+ years |
| shop | a national electronics or tool retailer in a mid-size European market — not global flagship brands, whose sites are designed |
| news | a county or regional daily, or a trade weekly · `"est. 18.." newspaper` |
| corporate / institutional | a regional water or energy utility, an NHS-equivalent hospital trust, a public university |
| directory | a national business directory, a trades register, a classifieds portal |

**Qualify each candidate before comparing** — open it and check: one workhorse sans (or serif headline face for news), corners at or near square, nothing moves on hover, dense text or dense listings, real photographs, no ornament above headings. Fails any → redesigned, search again. A large chain with a commissioned typeface will *feel* dated but still be a real design system — not a target. Any long-running firm, county newspaper, utility, university, regional retailer or listings site in the genre will do.

```bash
cat > /tmp/board.mjs <<'EOF'
import { chromium } from 'playwright-core';   // or an absolute path to it
const SHOTS = [
  ['ref-a', 'https://REFERENCE-ONE'],
  ['ref-b', 'https://REFERENCE-TWO'],
  ['mine',  'file:///ABSOLUTE/PATH/index.html'],
];
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH });
for (const [name, url] of SHOTS) {
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  try {
    await p.goto(url, { waitUntil: 'load', timeout: 45000 });
    await p.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) {
      await p.evaluate(y => window.scrollTo(0, y), i * 1900);
      await p.waitForTimeout(400);
      await p.screenshot({ path: `${name}-${i}.png` });
    }
  } catch (e) { console.log(name, 'failed:', e.message); }
  await p.close();
}
await b.close();
EOF
CHROME_PATH=<chrome-headless-shell> node /tmp/board.mjs
```

No headless browser? Open your page and one reference side by side in a real browser at the same window width and compare by eye. The comparison is mandatory; the automation is not.

Then **open the images and look at them.** Reading the HTML back is not this step.

## Score against the board

Answer each out loud. Any "mine" answer that is the tidier one is a failure.

**Universal — every archetype:**

| | reference | yours |
|---|---|---|
| Corners | how sharp? | sharper or equal, never rounder |
| Hover | what actually moves? | nothing moves; colour only |
| Ornament above headings | none | none |
| Is the palette coordinated? | no, stock greys sit in it | no |
| Does it look art-directed? | no | no |
| Could you tell which is the newer build? | — | **it should not be obvious** |

That last row is the whole test: if yours is instantly identifiable as the modern one, the token audit passing means nothing.

**Then the genre question — one only, yours:**

| archetype | ask |
|---|---|
| professional services | Is every band full of prose, or does it breathe? Does a CTA row close each photo band? |
| shop | Is the price the loudest thing in the tile? Is the grid crowded enough to scroll past? Do tiles stay still on hover? |
| news | Can you count 250+ links? Are river items headline-and-timestamp with no summaries? Are unfilled ad slots collapsed rather than blank bands? |
| corporate / institutional | Does the nav go deep? Notices strip and a dated news list? Hero signage rather than sales pitch? |
| directory | Rows with hairlines rather than cards? Search block loud and slightly crude? Numbered pagination? |

Text volume, section repetition and image count are **not** universal criteria — a directory has almost no text, a shop almost no prose. Use the density table in `verification.md`.

## Controls — optional, not shipped with the skill

Workspace artefacts from the project they were built in; if the paths are absent, skip this entirely.

| | verdict | what it shows |
|---|---|---|
| `references/skill-test-2/` (industrial refrigeration) | **user-approved** | what "right" looks like |
| `references/forward-test-sonnet-safety/` (safety training) | close, one flaw | correct except a wireframe placeholder box in the hero — since banned |
| `references/normcore-forward-test-pumpworks/` (pumps) | **rejected** | token-compliant, visually wrong: kickers, animated nav underline, scale hovers, uppercase buttons, rounded everything, too composed |

The negative control is the most useful — compare and ask which of its faults you repeated.

## The two failures on record, and what fooled the audit

- **Rounded + polished.** Every radius at the top of its range, hover scale on every button, perfectly ranged headings — each value individually within stated bounds; the sum read as a modern landing page. Default to the sharp end.
- **Wireframe furniture.** A dashed grey "VIDEO PLACEHOLDER" box in the hero — satisfied the then-current asset rule; made the page look unfinished rather than ordinary.
