// normcore-web automated checks. Runnable as-is:
//
//   CHROME=<path-to-chrome-headless-shell> \
//   PW=<path-to-playwright-core/index.mjs> \
//   node checks.mjs file:///abs/path/index.html
//
// Reports only failures. Exit code 1 if any. These cover what a machine can see —
// they do NOT replace visual-check.md, which is where "still looks too modern" is caught.

const [, , URL] = process.argv;
if (!URL) { console.error('usage: node checks.mjs <url>'); process.exit(2); }
const { chromium } = await import(process.env.PW || 'playwright-core');
const browser = await chromium.launch({ executablePath: process.env.CHROME });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

const errors = [], failed = [];
page.on('console', m => m.type() === 'error' && errors.push(m.text()));
page.on('requestfailed', r => failed.push(r.url()));
page.on('response', r => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`); });
await page.goto(URL, { waitUntil: 'load' });
await page.waitForTimeout(1200);
// trigger lazy-loading before judging images, or loading="lazy" reads as broken
await page.evaluate(async () => {
  for (let y = 0; y < document.body.scrollHeight; y += 700) {
    window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60));
  }
  window.scrollTo(0, 0);
});
await page.waitForTimeout(600);

const out = [];
const fail = (name, detail) => out.push({ name, detail });

// ─── ornament ────────────────────────────────────────────────────────────────
const orn = await page.evaluate(() => {
  const cs = (e, p) => getComputedStyle(e, p || null);
  const r = {};

  // authored transform ANIMATION — static positioning is allowed, library internals exempt
  r.transformAnim = [...document.querySelectorAll('body *')]
    .filter(e => (cs(e).transitionDuration || '').split(',').some(d => parseFloat(d) > 0)
              && /transform/.test(cs(e).transitionProperty)
              && !/swiper|slick|flickity|glide/i.test(e.className + ' ' + (e.parentElement?.className || '')))
    .map(e => e.tagName + '.' + String(e.className).slice(0, 24)).slice(0, 5);

  // pseudo-element hover ornament — computed style, NOT cssRules (cssRules throws on file://)
  r.pseudo = [...document.querySelectorAll('a,li,h1,h2,h3')]
    .filter(e => /transform|width|scale/.test(cs(e, '::after').transitionProperty
                                            + cs(e, '::before').transitionProperty))
    .map(e => e.tagName + '.' + String(e.className).slice(0, 24)).slice(0, 5);

  // eyebrow / kicker: small uppercase text immediately above a heading
  r.eyebrow = [...document.querySelectorAll('h1,h2')].map(h => h.previousElementSibling)
    .filter(p => p && parseFloat(cs(p).fontSize) <= 16 && cs(p).textTransform === 'uppercase'
                 && p.innerText.trim().length < 70)
    .map(p => p.innerText.trim().slice(0, 40));

  // button labels
  r.buttons = [...document.querySelectorAll('.btn,button,.button,[class*="btn"]')]
    .filter(b => { const s = cs(b);
      return s.textTransform !== 'none' || s.letterSpacing !== 'normal'; })
    .map(b => b.innerText.trim().slice(0, 30)).slice(0, 5);

  // two-tone wordmark. Scope to the mark; a container's OWN size may be small while its
  // spans render large, so never filter candidates by the container's font-size. Group runs
  // by size — a muted tagline beneath the mark is sanctioned and sits smaller.
  let mark = document.querySelector('.wordmark,.logo,.brand,.masthead,[class*="logo"],[class*="brand"]')
    || [...document.querySelectorAll('header a, header h1, a, h1')]
         .find(e => { const b = e.getBoundingClientRect();
                      return b.top < 200 && b.height > 14 && e.textContent.trim(); });
  r.twoTone = null;
  if (mark) {
    const bySize = {};
    const w = document.createTreeWalker(mark, NodeFilter.SHOW_TEXT);
    let t;
    while ((t = w.nextNode())) {
      if (!t.textContent.trim()) continue;
      const s = cs(t.parentElement);
      if (parseFloat(s.fontSize) < 18) continue;
      (bySize[s.fontSize] ??= new Map()).set(s.color, t.textContent.trim().slice(0, 18));
    }
    for (const [size, m] of Object.entries(bySize))
      if (m.size > 1) r.twoTone = { size, runs: [...m].map(([c, x]) => `"${x}" ${c}`) };
  } else r.noMark = true;

  // transition-property defaults to "all", so it is only meaningful where a duration is set
  const active = e => (cs(e).transitionDuration || '')
    .split(',').some(d => parseFloat(d) > 0);
  r.transitionAll = [...document.querySelectorAll('body *')]
    .filter(e => active(e) && /(^|,)\s*all\s*($|,)/.test(cs(e).transitionProperty))
    .map(e => e.tagName + '.' + String(e.className).slice(0, 24)).slice(0, 5);
  // a vendored library stylesheet is full of keyframes nothing on this page uses, so collect
  // the animation names actually running first and only report those
  const running = new Set();
  for (const e of document.querySelectorAll('body, body *'))
    for (const pseudo of [null, '::before', '::after'])
      for (const n of (getComputedStyle(e, pseudo).animationName || '').split(','))
        if (n.trim() && n.trim() !== 'none') running.add(n.trim());

  // computed styles resolve clamp() to a used px value, so this has to read the stylesheet text
  const clamp = new Set();
  const keyframes = new Set();
  const scan = (text, where) => {
    for (const m of (text || '').matchAll(/([-a-z]+)\s*:\s*[^;}]*clamp\(/g))
      clamp.add(`${m[1]} (${where})`);
  };
  const walk = (rules, where) => {
    for (const rule of rules || []) {
      if (rule.type === CSSRule.KEYFRAMES_RULE) {
        if (running.has(rule.name) &&
            [...rule.cssRules].some(kf => /transform/.test(kf.style?.cssText || '')))
          keyframes.add(rule.name);
        continue;                                    // a keyframe step is not authored type
      }
      if (rule.style) scan(rule.style.cssText, where);
      if (rule.cssRules) walk(rule.cssRules, where);  // @media, @supports, @layer
    }
  };
  for (const sh of document.styleSheets) {
    let rules; try { rules = sh.cssRules; } catch { continue; }   // throws cross-origin
    walk(rules, sh.href ? sh.href.split('/').pop() : 'inline <style>');
  }
  for (const e of document.querySelectorAll('[style]'))
    scan(e.getAttribute('style'), 'style attribute');
  r.keyframes = [...keyframes];
  r.clamp = [...clamp].slice(0, 6);
  return r;
});
if (orn.transformAnim.length) fail('transform in an authored transition', orn.transformAnim);
if (orn.pseudo.length)        fail('pseudo-element hover ornament', orn.pseudo);
if (orn.eyebrow.length)       fail('eyebrow / kicker above a heading', orn.eyebrow);
if (orn.buttons.length)       fail('button label uppercased or tracked', orn.buttons);
if (orn.twoTone)              fail('two-tone wordmark', orn.twoTone);
if (orn.noMark)               fail('no wordmark found — check by eye', '');
if (orn.transitionAll.length) fail('transition: all — hides transform behind a shorthand', orn.transitionAll);
if (orn.keyframes.length)     fail('@keyframes animating transform, and in use', orn.keyframes);
if (orn.clamp.length)         fail('clamp() — use stepped px per breakpoint', orn.clamp);

// ─── assets ──────────────────────────────────────────────────────────────────
const assets = await page.evaluate(() => {
  const imgs = [...document.querySelectorAll('img')];
  return {
    broken: imgs.filter(i => !i.naturalWidth).map(i => i.getAttribute('src')),
    noDims: imgs.filter(i => !i.getAttribute('width') || !i.getAttribute('height'))
                .map(i => i.getAttribute('src')).slice(0, 8),
    // alt="" is valid and correct for decorative images; only a MISSING attribute fails
    noAlt: imgs.filter(i => i.getAttribute('alt') === null).map(i => i.getAttribute('src')).slice(0, 8),
    // 2x is legitimate retina, so only flag beyond 2.5x
    oversized: imgs.filter(i => i.clientWidth > 0 && !/\.svg(\?|$)/i.test(i.currentSrc || i.src || '')
                             && i.naturalWidth > i.clientWidth * 2.5)
                   .map(i => `${i.getAttribute('src')} ${i.naturalWidth}px in ${i.clientWidth}px`).slice(0, 8),
    hotlinked: [...document.querySelectorAll('img,link,script')]
                 .map(e => e.getAttribute('src') || e.getAttribute('href'))
                 .filter(u => u && /^https?:/.test(u)).slice(0, 8),
    // SVG is allowed when it is an icon set or a brand file — list them for a human to confirm
    svgs: [...document.querySelectorAll('svg')].length,
    counts: { imgs: imgs.length, links: document.querySelectorAll('a').length,
              shadows: [...document.querySelectorAll('body *')]
                         .filter(e => getComputedStyle(e).boxShadow !== 'none').length },
  };
});
if (assets.broken.length)    fail('broken image', assets.broken);
if (assets.noDims.length)    fail('img without width/height', assets.noDims);
if (assets.noAlt.length)     fail('img without alt', assets.noAlt);
if (assets.oversized.length) fail('image far larger than its desktop slot — confirm it is not '
  + 'sized for a wider mobile/retina rendering before shrinking', assets.oversized);
if (assets.hotlinked.length) fail('hotlinked remote asset', assets.hotlinked);

// ─── contrast ────────────────────────────────────────────────────────────────
const contrast = await page.evaluate(() => {
  const lum = c => { const [r, g, b] = c.match(/\d+/g).slice(0, 3).map(Number)
      .map(v => v / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  // Returns null when the text sits over a background IMAGE — the ratio is then
  // indeterminate and must be judged by eye, not reported as a failure. Photo bands are a
  // core pattern here, so guessing white would flag every one of them at 1.00:1.
  const bg = e => { for (let n = e; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.backgroundImage && s.backgroundImage !== 'none') return null;
      const c = s.backgroundColor;
      if (c && !/rgba?\(0, 0, 0, 0\)|transparent/.test(c)) return c; } return 'rgb(255,255,255)'; };
  const out = []; let overImage = 0;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let t;
  while ((t = w.nextNode())) {
    const txt = t.textContent.trim(); if (!txt) continue;
    const e = t.parentElement; const s = getComputedStyle(e);
    if (s.visibility === 'hidden' || s.display === 'none' || !e.getClientRects().length) continue;
    const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
    const back = bg(e);
    if (back === null) { overImage++; continue; }
    const a = lum(s.color), b = lum(back);
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    if (ratio < need) out.push(`${ratio.toFixed(2)}:1 (need ${need}) "${txt.slice(0, 34)}"`);
  }
  return { fails: out.slice(0, 12), overImage };
});
if (contrast.fails.length) fail('contrast below AA', contrast.fails);

// ─── focus visibility ────────────────────────────────────────────────────────
const noFocus = await page.evaluate(() => {
  const t = [...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')].slice(0, 40);
  return t.filter(e => { e.focus();
      const s = getComputedStyle(e);
      return s.outlineStyle === 'none' && !/inset/.test(s.boxShadow) && s.boxShadow === 'none';
    }).length;
});
if (noFocus) fail('focusable elements with no visible focus ring', `${noFocus} of the first 40`);

// ─── width sweep ─────────────────────────────────────────────────────────────
const over = [];
for (const w of [320, 360, 414, 600, 700, 768, 800, 900, 1024, 1100, 1280, 1440, 1600, 1920]) {
  await page.setViewportSize({ width: w, height: 900 });
  await page.waitForTimeout(220);
  const px = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (px > 0) over.push(`${w}px overflows by ${px}px`);
}
if (over.length) fail('horizontal overflow', over);

if (errors.length) fail('console errors', errors.slice(0, 5));
if (failed.length) fail('failed requests', failed.slice(0, 5));

// ─── report ──────────────────────────────────────────────────────────────────
const c = assets.counts;
if (contrast.overImage) console.log(
  `note    ${contrast.overImage} text nodes sit over a background image — ratio not computable,\n        check those by eye against the flat fill.`);
console.log(`counts  images ${c.imgs} · links ${c.links} · shadows ${c.shadows} · inline svg ${assets.svgs}`);
console.log('        (compare against your archetype\'s density band; svg is fine when every one');
console.log('         traces to an icon set, a brand file or a project component)\n');
if (!out.length) console.log('PASS — no automated failures. Now run visual-check.md; it catches what this cannot.');
else { console.log(`${out.length} FAILING:\n`);
  for (const f of out) console.log(`  ${f.name}\n    ${JSON.stringify(f.detail)}\n`); }

await browser.close();
process.exit(out.length ? 1 : 0);
