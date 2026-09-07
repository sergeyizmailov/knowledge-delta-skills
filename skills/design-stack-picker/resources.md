# Resource catalog

Pick **one per axis per project**. House defaults ⭐. Pricing/status verified June 2026 — volatile [V], re-check before buying.

**Licensing:** OFL = SIL Open Font License (modify/redistribute OK) · ITF-FFL = free commercial but **no modify/redistribute/self-host-repackage** (Fontshare originals) · CC0 = public domain · CC-BY = attribution.

**Method:** this is a menu, not an install list. Read the project first (framework, existing design system, deps, constraints); pick one resource per axis only where the project lacks a good answer; prefer framework-fit; don't add a package if a local component/dependency/static asset suffices; re-check pricing/license/maintenance before paid or high-dependency picks.

| Situation | Start here |
|---|---|
| Existing Astro/static site | Local components first; `astro:assets` for images; HyperUI/Preline as layout references, not deps. |
| Existing React/Next app | Current UI library first; shadcn/Radix when complex interactive primitives missing. |
| Ecommerce/catalog | Product data/media, image optimization, stable card patterns, category/search UX. |
| Admin/dashboard | Tables, forms, filters, density, focus states; avoid decorative illustration-heavy choices. |
| Marketing page | Fonts, imagery/video, section blocks, motion, image performance. |
| One-off prototype | Smallest working choice; no full design system unless it continues. |

---

## 1. Icons — never hand-draw

**Meta-library (use first):**
- ⭐ **Iconify** — https://iconify.design · search https://icon-sets.iconify.design — 200k+ icons / 150+ sets, one API. Astro (`astro-icon`), React (`@iconify/react`), web component, CSS, Tailwind.

**House set:**
- ⭐ **Solar** — https://icon-sets.iconify.design/solar/ — huge, consistent, multiple styles (Linear/Outline/Bold/Broken/Duotone). Default `-linear`. `@iconify-json/solar`.
- ⭐ **Simple Icons** — https://simpleicons.org — brand/logo marks only. `@iconify-json/simple-icons`.

**Swap whole set to fit aesthetic (never mix sets):**
- **Lucide** — https://lucide.dev — 1500+ outline; React/shadcn default; clean SaaS.
- **Phosphor** — https://phosphoricons.com — 6 weights; playful-but-refined.
- **Tabler** — https://tabler.io/icons — 5000+; widest coverage.
- **Heroicons** — https://heroicons.com — Tailwind team's MIT set; smaller but very polished; outline/solid/mini.
- **Remix Icon** — https://remixicon.com — neutral system symbols, outline + filled; strong general UI/app choice.
- **Iconoir** — https://iconoir.com — elegant 24px outline; when Lucide feels too generic but open source wanted.
- **Radix Icons** — https://www.radix-ui.com/icons — crisp 15×15; dense React/admin controls, not large marketing UI.
- **Bootstrap Icons** — https://icons.getbootstrap.com — broad, practical SVG/sprite/font; usable without Bootstrap.
- **Hugeicons** — https://hugeicons.com — large modern family; free + paid; broad coverage.
- **Material Symbols** — https://fonts.google.com/icons — variable icon font, multiple axes; Google/Material-adjacent products.
- **Font Awesome** — https://fontawesome.com — huge ecosystem; compatibility/coverage over distinctiveness.

**Premium / team-scale (check license):**
- **Streamline** — https://www.streamlinehq.com — very large professional library, many families/styles; team breadth.
- **Nucleo** — https://nucleoapp.com — large bundle + manager; product teams with custom icon workflows.

**Niche / expressive (use intentionally):**
- **Pikaicons** — https://pikaicons.com — more characterful than Lucide/Heroicons; playful/product-led UI.
- **Mage Icons** — https://mageicons.com — clean open-source interface icons.
- **Flowbite Icons** — https://flowbite.com/icons — Tailwind/Flowbite-adjacent; if already using Flowbite.

**Shortcut:** Solar for expressive retail/consumer, Lucide for clean SaaS, Heroicons for Tailwind-style marketing, Remix/Iconoir for less-common neutral, Radix for tiny dense controls, Tabler/Material/Font Awesome when coverage beats personality.

---

## 2. Fonts — distinctive display + refined body

### Sources
- ⭐ **Fontsource** — https://fontsource.org — self-host OFL/Apache fonts as npm (`@fontsource-variable/<name>`). Best for builds: no external request, version-locked, no tracking.
- **Google Fonts** — https://fonts.google.com — 1800+ OFL; easiest `<link>`. (CDN logs IPs — self-host or proxy for EU.)
- **Fontshare** — https://www.fontshare.com — highest-quality free fonts by Indian Type Foundry (Satoshi, Clash Display, General Sans…). ⚠️ Mostly **ITF-FFL, not OFL** → can't self-host via Fontsource or modify; use their CDN/static files.
- **Bunny Fonts** — https://fonts.bunny.net — GDPR-safe Google Fonts drop-in.

**Independent / editorial free foundries (distinctive, OFL):**
- **Velvetyne** — https://velvetyne.fr — experimental French libre foundry (Pilowlava, Karrik).
- **Collletttivo** — https://www.collletttivo.it — 80+ OFL families (Apfel Grotezk, Sprat).
- **uncut.wtf** — https://uncut.wtf — 160+ curated contemporary free fonts.
- **The League of Moveable Type** — https://www.theleagueofmoveabletype.com — League Gothic, League Mono.
- **Open Foundry** — https://open-foundry.com — curated OFL discovery.

### Trending 2026 typefaces (one display + one body)
*Display (free unless noted):*
- ⭐ **Unbounded** (house) · **Bricolage Grotesque** (OFL, strongest-growing free face) · **Instrument Serif** (OFL — "free Canela alternative") · **Clash Display** (ITF-FFL) · **Cabinet Grotesk** (ITF-FFL) · **Boska** (ITF-FFL Didone) · **Tanker / Nippo** (ITF-FFL) · **Fraunces** (OFL, variable "wonk" axis). *Premium:* **Neue Montreal**, **Monument Extended**, **Editorial New** (Pangram Pangram), **Canela** (Commercial Type).

*Body/UI sans (screen, variable preferred):*
- ⭐ **Onest** (house, OFL) · **Geist** (Vercel, OFL) · **Inter** (OFL — fine as body when display carries personality) · **DM Sans** · **Plus Jakarta Sans** · **Figtree** · **Manrope** · **Albert Sans** · **Satoshi / General Sans** (ITF-FFL).

*Serif (editorial/luxury):* **Fraunces** · **Cormorant Garamond** · **EB Garamond** · **Newsreader**. *Premium:* **Editorial New**, **Canela**, **Tiempos** (Klim).

*Mono (techy/data):* **Geist Mono** · **JetBrains Mono** · **Commit Mono** · **Fira Code** (ligatures) · **Fragment Mono** · **Martian Mono**. *Premium:* **Berkeley Mono** (usgraphics.com, ~$75).

**Premium foundries (distinctive brand work):** Pangram Pangram (best price/quality, free-to-try), Klim, Grilli Type, Commercial Type, Displaay (Roobert), OH no Type (Degular), ABC Dinamo (Monument Grotesk), Frere-Jones. Multi-foundry stores: Type Network, Future Fonts (early-access).

### Pairing & scale tools
- **Fontpair** — https://www.fontpair.co (curated, all free) · **Fontjoy** — https://fontjoy.com (ML generator + contrast slider) · **Typewolf** — https://www.typewolf.com (what real sites ship — trend signal) · **Fonts In Use** — https://fontsinuse.com · **Beautiful Web Type** — https://beautifulwebtype.com (best OFL specimens).
- **Type scale:** ⭐ **Utopia** — https://utopia.fyi (fluid type+space `clamp()` tokens) · **type-scale.com** (fixed modular) · **fluid-type-scale.com** (named fluid tokens).

### Self-hosting performance
WOFF2 only · prefer **variable fonts** (one file = 4–8 weights) · `font-display: swap` + metric-adjusted fallback (`size-adjust`/`ascent-override`) · `<link rel=preload as=font crossorigin>` the one critical weight · subset with **subfont** (static sites) or **glyphhanger** · cache `immutable, max-age=31536000`.

---

## 3. Components & blocks — assemble, don't reinvent

**Copy-paste section blocks (HTML/Tailwind/Astro):**
- ⭐ **HyperUI** — https://hyperui.dev · ⭐ **Preline** — https://preline.co (640+, full sections) · **Flowbite** — https://flowbite.com · **DaisyUI** v5 — https://daisyui.com (themed) · **Pagedone** (Tailwind v4-native) · **MVPBlocks** (animated, free).

**React — shadcn ecosystem (you own the code):**
- ⭐ **shadcn/ui** + **Blocks** — https://ui.shadcn.com (Radix-based standard; full page sections).
- **Origin UI** — https://originui.com (hundreds, Tailwind v4) · **ReUI** — https://reui.io (1000+, Radix+Base UI, Data Grid/Kanban) · **Tremor** — https://tremor.so (free dashboards/charts).
- **Discovery:** **registry.directory** (index of all shadcn registries) · **ui.shadcn.com/awesome**.

**Animated / "design-engineered" libraries:**
- ⭐ **Magic UI** — https://magicui.design (NumberTicker, Marquee, Border/Animated Beam, Globe — MIT) · **Aceternity UI** — https://ui.aceternity.com (3D Card, Spotlight, Tracing Beam) · ⭐ **ReactBits** — https://reactbits.dev (536 components, biggest community) · **Motion Primitives** — https://motion-primitives.com (installs via `npx shadcn add`) · **Animata** — https://animata.design (WAAPI, no Motion dep).

**Accessible headless primitives (NEVER hand-roll menus/dialogs/combobox/tabs):**
- ⭐ **Radix UI** — https://www.radix-ui.com/primitives (React) · **Base UI** — https://base-ui.com (MUI's v1.0 Radix alternative) · **Ark UI** — https://ark-ui.com (cross-framework: React/Vue/Solid/Svelte) · **Headless UI** — https://headlessui.com · **React Aria** — deepest a11y.

**Framework-specific kits:**
- **Vue/Nuxt:** ⭐ **Nuxt UI v4** — https://ui.nuxt.com (125+, now fully free, Reka UI + Tailwind v4) · **PrimeVue** · **Reka UI** (headless, ex-Radix Vue) · **Inspira UI** (animated, Aceternity-for-Vue).
- **Svelte:** **shadcn-svelte** + **Bits UI** (headless) · **Skeleton v3** (Svelte 5).
- **Solid:** **Kobalte** (headless) · **Solid UI**.

**Design-token baseline:** **Open Props** — https://open-props.style (300+ CSS-var tokens) + **Open Props UI** · **Style Dictionary v5** (cross-platform token build) · **Tailwind v4 `@theme`** (CSS-first tokens).

---

## 4. Imagery — real assets, one consistent style

### SVG illustrations & scenes (recolor to brand)
For empty states, onboarding, editorial blocks, feature sections — never product substitutes in ecommerce (product/category pages need real product imagery first).

Free-source rule: prefer clear free/no-attribution pages; on freemium marketplaces link directly to free sections, verify asset-level license + export format, no watermarked previews.

- ⭐ **unDraw** — https://undraw.co — open-source SVG, easy color matching, no attribution.
- ⭐ **Storyset** — https://storyset.com — customizable SVG scenes, multiple styles, optional animation.
- **DrawKit** — https://www.drawkit.com — free + premium packs across business/tech/family/finance.
- **Blush** — https://blush.design — customizable collections by many artists; distinctive character styles.
- **Open Peeps** — https://openpeeps.com — hand-drawn character system; warm, informal, startup-friendly.
- **Humaaans** — https://humaaans.com — mix-and-match people; team/people sections.
- **ManyPixels Gallery** — https://www.manypixels.co/gallery — free SVG/PNG, several styles.
- **IRA Design archive** — https://github.com/ira-design/ira-illustrations — old MIT pack; `iradesign.io` may be empty/offline — archived material only.
- **Icons8 free icons** — https://icons8.com/icons — large free catalog; free use requires Icons8 attribution unless paid/OSS arrangement.
- **Icons8 free illustrations / Ouch!** — https://icons8.com/illustrations — free SVG/PNG clipart; attribution rules apply.
- **Icons8 free animated icons** — https://icons8.com/animated-icons — animated GIF icons marked free; Lottie/AEP may be paid.
- **Icons8 free license** — https://icons8.com/license — attribution requirements for free use.
- **IconScout free illustrations** — https://iconscout.com/free-illustrations — free-only entry; verify asset license before download.
- **IconScout free icons** — https://iconscout.com/free-icons — avoid paid marketplace previews/watermarks.
- **IconScout freebies** — https://iconscout.com/freebies — rotating; verify terms/formats per item.
- **IconScout free 3D icons** — https://iconscout.com/free-3d-icons — check whether needed format is included.
- **IconScout license** — https://iconscout.com/licenses — asset-level terms reference.
- **SVG Repo** — https://www.svgrepo.com — large open-licensed SVG search; style consistency varies.

**Shortcut:** unDraw = safest generic SaaS; Storyset = customizable scenes/animation; DrawKit = polished packs; Blush/Open Peeps/Humaaans = people/character tone; SVG Repo/IconScout free pages = specific object when license verified. One visual style per project.

### Stock photos (free, commercial OK, no attribution)
- ⭐ **Unsplash** — https://unsplash.com · **Pexels** — https://pexels.com · **Pixabay** — https://pixabay.com. (Proprietary-but-free licenses; can't resell raw or use to train models.)

### Stock VIDEO (hero backgrounds)
- ⭐ **Pexels Video** — https://www.pexels.com/videos/ (no attribution, 4K) · ⭐ **Coverr** — https://coverr.co (web-optimized; ⚠️ free tier needs attribution, Coverr+ removes it) · **Mixkit** — https://mixkit.co (no attribution; ⚠️ music not for broadcast/games; check per-clip Free vs Restricted) · **Pixabay Video** · **Dareful** — https://dareful.com (free 4K cinematic, CC-BY). Pattern: mute + autoplay + loop, WebM+MP4 ~1080p.

### 3D / interactive
- ⭐ **Spline** — https://spline.design (no-code 3D, `<spline-viewer>` web component embed) · **Rive** — https://rive.app (interactive state-machine animations, GPU, KB-light; runtime MIT, ⚠️ `.riv` export needs $9/mo Cadet since Oct 2025) · **Sketchfab** (embed models, per-model license). CC0 GLB packs for Three.js/R3F: **Kenney** — https://kenney.nl · **Quaternius** · **Poly.pizza** · **market.pmnd.rs**. PNG 3D render sets: **3Dicons** (CC0), **Shapefest**, **Handz**.

### Mockup generators (hero/device shots)
- ⭐ **Shots.so** — https://shots.so (browser/device beautify, free tier) · **Screely** — https://screely.com (free, local) · **Mockup World** — https://www.mockupworld.co (free PSD/Figma aggregator) · **Mockuuups Studio** (API) · **Mockuphone** (OSS). ⚠️ **Smartmockups** shut down Sep 2024.

### Placeholders & avatars (generated — no AI-image filler)
- **Placeholders:** ⭐ **picsum.photos** (real photos, `…/seed/x/800/600`) · **placehold.co** (color/label blocks). ⚠️ `placeholder.com` / `via.placeholder.com` **dead** — don't use.
- **Avatars:** ⭐ **DiceBear** — https://dicebear.com (40+ styles, API; check per-style license) · **Boring Avatars** (use the `boring-avatars` **npm** — hosted API went paid) · **pravatar.cc** (real faces, CC0) · **ui-avatars.com** (initials) · **Robohash** · **Gravatar** (email-linked, now SHA256).

---

## 5. Color — use a system, not random hex

- ⭐ **Radix Colors** — https://www.radix-ui.com/colors (12-step accessible scales, light+dark, APCA) · **Open Color** · Tailwind/Material ramps.
- **Prefer OKLCH** over HSL (perceptually uniform lightness; P3 gamut). Pickers: **oklch.com**, **Evil Martians OKLCH picker**. Tint with `color-mix(in oklch, …)`.
- **Generators/preview:** ⭐ **Realtime Colors** — https://realtimecolors.com (preview on real UI) · **Coolors** · **Huemint** (AI palettes by role) · **Leonardo** (contrast-target).
- **Rule:** semantic 3-tier tokens (primitive → semantic → component); one dominant brand + one sharp accent; AA contrast on text + states.

---

## 6. Shadows & depth
- ⭐ **Josh Comeau Shadow Palette** — https://www.joshwcomeau.com/shadow-palette/ (layered, hue-tinted scale) · **Smooth Shadows** — https://smoothshadows.com.
- Technique: stack 3–6 `box-shadow` layers (rising offset, low alpha); tint hue toward surface/brand. Never a single harsh `0 4px 6px rgba(0,0,0,.5)`.

---

## 7. Motion & animation — restrained, accessible
- **CSS-first** (plain HTML): staggered load reveals; native **scroll-driven** (`animation-timeline: view()`); `@starting-style`; **View Transitions API**. Always guard `prefers-reduced-motion`.
- ⭐ **Motion** — https://motion.dev (ex-Framer Motion; package `motion`, import `motion/react`; React UI) · **GSAP** — https://gsap.com (**100% free** incl. ScrollTrigger/SplitText/MorphSVG; complex timelines/scroll) · **Auto-Animate** — https://auto-animate.formkit.com (one-line list animations) · **Lenis** (smooth scroll).
- **Drop-in CSS:** **Animista** (keyframe generator) · **Animate.css** · **Hover.css** · **react-fast-marquee**. Easing: **easings.net**, **linear() spring generators**, **cubic-bezier.com**.
- One orchestrated load reveal > scattered micro-interactions. GSAP is overkill for a fade — prefer CSS.

---

## 8. Backgrounds & texture
- ⭐ **fffuel** — https://fffuel.co — 30+ free SVG/CSS generators: **gggrain** (grainy gradients), **ffflux/uuunion** (mesh), **nnnoise** (noise), **ssshape** (blobs), **nnneon** (glow), **pppalette**.
- ⭐ **Haikei** — https://haikei.app (blobs, waves, layers, blurry gradients) · **Hero Patterns** — https://heropatterns.com (SVG tiles) · **Pattern Monster** — https://pattern.monster (320+ SVG patterns).
- **SVG Backgrounds** — https://www.svgbackgrounds.com — customizable SVG backgrounds/patterns; section texture.
- **Gradients:** **gradient.style** (Argyle, conic/CSS4) · **Coolhue** · **Hypercolor** (Tailwind gradient classes) · mesh tools above.
- **Blobs/shapes:** **Blobmaker** — https://blobmaker.app · **Blobs.app**.
- **Animated JS backgrounds:** **Vanta.js** — https://vantajs.com · **Particles** (tsParticles).
- **Glassmorphism:** **css.glass** — https://css.glass (`backdrop-filter` + translucent bg + subtle border).

---

## 9. Modern CSS techniques (2026) — pro vs generic
Production-ready: `clamp()` fluid type (always include a `rem` term for zoom/WCAG) · **OKLCH** + `color-mix()` · `@property` · `@starting-style` · container queries · `text-wrap: balance`/`pretty` · **View Transitions** same-document (`document.startViewTransition?.()`) · layered shadows · CSS Subgrid.
Progressive-enhance (guard with `@supports`): **scroll-driven animations** (`animation-timeline: view()` — no Firefox yet; IntersectionObserver fallback) · cross-document View Transitions (Chromium) · CSS anchor positioning.
Snippets: `patterns.md`.

---

## 10. Image performance — quality = perceived speed
- **Optimize:** **Sharp** (Node build pipelines) · **SVGO** (strip SVG cruft). Avoid Imagemin (stale).
- **Formats:** **AVIF with WebP fallback** via `<picture>` (~50% smaller than JPEG). Always `width`/`height`; `fetchpriority="high"` + eager on LCP/hero; lazy the rest.
- **Framework built-ins:** `next/image` (enable AVIF in config) · Astro `astro:assets` `<Picture>` (Sharp, build-time) · `@nuxt/image` `<NuxtPicture>`.
- **Free CDN if dynamic:** **ImageKit** (generous free tier) or **Cloudinary**.

---

## 11. Templates & starters — whole site fast
- **Free:** **Vercel Templates** — https://vercel.com/templates (official Next.js/Astro starters) · **Astro Themes** — https://astro.build/themes (375+) · **Open SaaS** — https://opensaas.sh (full free SaaS).
- **Premium:** **Tailwind Plus** — https://tailwindcss.com/plus (500+ blocks + Catalyst, $299) · **Cruip** (~$79 landing/SaaS) · **ShipFast** ($199, ship-in-a-weekend) · **Supastarter** (multi-tenant).

---

## 12. Inspiration, UX patterns & design QA

Pull patterns, not decoration: layout, hierarchy, spacing, density, mobile behavior, CTA placement, interaction states.

### Website / landing inspiration
- ⭐ **Land-book** — https://land-book.com — hand-picked sites with filters incl. ecommerce, product pages, portfolios, blogs.
- ⭐ **Lapa Ninja** — https://www.lapa.ninja — large landing archive: categories, colors, full-page screenshots, page recordings.
- **One Page Love** — https://onepagelove.com — one-page sites + section examples/templates.
- **Landingfolio** — https://www.landingfolio.com — curated landings, templates, components; SaaS/product pages.
- **Godly** — https://godly.website — bold, high-polish; visual direction, not copy-paste complexity.
- **Awwwards** — https://www.awwwards.com/websites — craft-level; avoid overbuilding award-site effects.

### Product UI / real app patterns
- ⭐ **Mobbin** — https://mobbin.com — searchable mobile/web app screenshots and flows; best for real UX patterns, onboarding, settings, commerce, forms.
- **UXArchive** — https://uxarchive.com — mobile flows; onboarding, purchase, search, account.
- **Refero** — https://refero.design — product UI references and flow inspiration.
- **Pageflows** — https://pageflows.com — recorded user flows; interactions beyond static screenshots.

### Focused UI galleries
- **Footer.design** — https://www.footer.design · **Navbar Gallery** — https://www.navbar.gallery · **CTA.gallery** — https://www.cta.gallery · **Deck Gallery** — https://deck.gallery (decks/slides; visual storytelling, section rhythm).

### Fast polish / CSS generators
- **CSSTools.io** — https://csstools.io — gradients, shadows, filters, clip paths, glass.
- **HYPE4 Glassmorphism** — https://hype4.academy/tools/glassmorphism-generator (use sparingly).
- **Get Waves** — https://getwaves.io (SVG wave separators) · **Clippy** — https://bennettfeely.com/clippy (clip-path) · **Cubic Bezier** — https://cubic-bezier.com (easing curves).

### Product and app mockups
- ⭐ **Shots.so** — https://shots.so · **Device Shots** — https://deviceshots.com (free device mockups) · **Mockuuups Studio** — https://mockuuups.studio (large realistic library, Figma/desktop workflow) · **Placeit** — https://placeit.net (broad marketing/product mockups; ecommerce/POD, social assets).

### Quality checks
- **PageSpeed Insights** — https://pagespeed.web.dev (performance, LCP/CLS/image) · **WebPageTest** — https://www.webpagetest.org (waterfalls, filmstrips) · **WAVE** — https://wave.webaim.org (a11y) · **WebAIM Contrast Checker** — https://webaim.org/resources/contrastchecker/ (text/bg contrast) · **Leonardo** — https://leonardocolor.io (generate accessible color scales) · **Responsively** — https://responsively.app (multi-device visual checks).

**Workflow:** pick 3-5 references of the same page type, extract concrete patterns, implement with the project's components/tokens. Never clone a reference wholesale.

---

## 13. Discovery & reference
- **Awesome lists:** **awesome-shadcn-ui** (github.com/birobirobiro/awesome-shadcn-ui) · **awesome-tailwindcss** (aniftyco) · **awesome-react-components** (brillout) · **awesome-css** · **awesome-web-animation**.
- **Design-engineering reading:** Josh Comeau (joshwcomeau.com) · Adam Argyle (nerdy.dev) · Ahmad Shadeed (ishadeed.com + defensivecss.dev) · Piccalilli (piccalil.li) · Modern CSS (moderncss.dev) · web.dev/learn/css · every-layout.dev.

---

## Quick decision table

| Need | Reach for |
|---|---|
| Any UI/category icon | Iconify → **Solar** (`-linear`) · brand logo → **Simple Icons** |
| Heading font | **Unbounded** / Bricolage Grotesque / Instrument Serif (serif) |
| Body font | **Onest** / Geist / Inter |
| Self-host fonts | **Fontsource** (OFL only; Fontshare = ITF-FFL, CDN/static) |
| Font pairing / scale | **Fontjoy** / Typewolf · **Utopia** |
| Landing section | **HyperUI** / **Preline** block, restyled |
| React components | **shadcn/ui** (+ Origin UI / ReUI); animated → **Magic UI** / ReactBits |
| Accessible menu/dialog/combobox | **Radix** / Base UI / Ark UI |
| Vue / Svelte kit | **Nuxt UI v4** / **shadcn-svelte** + Bits UI |
| Illustration / photo | **unDraw** / Storyset · **Unsplash** / Pexels |
| Hero background video | **Pexels Video** / **Coverr** |
| 3D / interactive hero | **Spline** / **Rive** |
| Device/browser mockup | **Shots.so** / Screely |
| Placeholder / avatar | **picsum.photos** / placehold.co · **DiceBear** |
| Color system | **Radix Colors** (OKLCH) · preview **Realtime Colors** |
| Shadow scale | **Josh Comeau Shadow Palette** |
| Background / texture / grain | **fffuel** · **Haikei** · Hero Patterns |
| Glassmorphism | **css.glass** |
| Fluid type/space | **Utopia** |
| React motion | **Motion** · scroll/timeline → **GSAP** (free) |
| Image optimization | **Sharp** + AVIF/`<picture>`; CDN → **ImageKit** |
| Whole-site starter | **Vercel Templates** / Astro Themes / Tailwind Plus |
| Design references | **Land-book** / Lapa Ninja / Mobbin |
| UX flows | **Mobbin** / UXArchive / Pageflows |
| CSS polish generators | **CSSTools.io** / fffuel / Haikei / HYPE4 |
| Device/product mockups | **Shots.so** / Device Shots / Mockuuups Studio |
| Quality checks | **PageSpeed Insights** / WAVE / WebPageTest |
