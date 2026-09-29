# 11 — Field notes: what practitioners report, and how much to trust it

Compiled 2026-09-14 from RU and EN affiliate/media-buying sources plus two Russian-language
media-buying video transcripts supplied by the operator. Every claim below was checked individually
against TikTok's official documentation and current platform behavior where a corresponding official
claim exists; where a source is stale or where the material describes evading policy rather than
complying with it, that is flagged in place rather than silently repeated.

**Nothing in this file is a TikTok fact.** It is what people who buy traffic say, which is valuable
precisely where documentation is silent — account supply, enforcement reality, what breaks — and
worthless when it contradicts a primary source. Where it does contradict, the primary source wins
(`00`).

## Read the evidence quality first

The 2026 TikTok information environment is unusually bad, and an agent researching it will be misled
unless it knows the failure modes:

- **A large share of "TikTok benchmark 2026" content is AI-generated content-farm output.** One
  heavily cited benchmark site attributes figures to research firms that do not exist.
- **Reported CPMs disagree by more than 2× between "benchmark" sources published the same week.**
  There is no single trustworthy TikTok CPM.
- **The "Nielsen 780-campaign Spark Ads study"** cited across dozens of agency blogs traces, on
  direct fetch, to TikTok's own help page. A citation laundered into a fake third-party study.
- Reddit and the main practitioner forums (AffiliateFix, STM, BlackHatWorld) were **inaccessible to
  automated fetch** — 403s and blocks. The EN practitioner picture here is therefore built from
  agency blogs and published case studies, not from forum primary sources. That is a known gap, not
  an oversight.
- Much RU material is genuinely old. A partnerkin case dated in the compilation as 2026 may describe
  a 2020 campaign. **Check the campaign's date, not the article's.**

## Structure doctrine is a Meta port

"3–5 ad groups, 3–5 creatives each, ABO first then CBO" appears across nearly every 2026 TikTok
guide. **No controlled test supports it on TikTok, and no source repeating it cites one.** It is Meta
convention, re-badged.

Treat it as a starting shape when you have nothing better, say that is what you are doing, and derive
the real structure from conversion volume and the number of readable tests (`03`).

## Agency accounts (агентские кабинеты) — the RU market

Consistent across partnerkin, affmoment, vc.ru and others:

- **TikTok agency accounts are rented, not bought.** You attach to a reseller's trusted structure.
  You do **not** get raw API credentials, and if the account is banned, **the reseller argues with
  TikTok, not you.**
- Commission models run roughly 3–10% on top-ups, sometimes with a monthly fee; terms move fast and
  any price list is stale on arrival.
- Rule of thumb repeated across sources: move to an agency account at roughly **3–4 stable clients or
  ~$5,000/month** in budget. Below that, self-serve is considered adequate.
- What agency accounts are believed to unlock: exemption from new-account probationary spend caps,
  access to restricted verticals via the agency's existing certifications, and a support path.
  Structurally consistent with TikTok's documented verification model (`02`, `08`) — but TikTok
  states none of it.
- **Explicit scam warning, verbatim from a forum:** unsolicited Telegram DMs offering cheap agency
  cabinet rentals are *"скорее всего, развод"* — almost certainly a scam. Vet by asking which listed
  Marketing Partner the account actually belongs to.
- Risks that land on you, not the reseller: the account dies with your money on its balance
  (*"деньги зависли"*), and an aged or purchased account can still be banned regardless of history.

## Account survival and warming (прогрев)

- **No RU source argues warming is cargo-cult** — unlike Meta-arbitrage discourse, every
  TikTok-specific piece treats it as necessary. That unanimity is itself weak evidence: no
  contrarian was published, so nobody tested the null.
- The documented-in-the-field method (partnerkin, updated 2026-06): register via Google account or
  rental SMS; days 1–3 no posting or profile edits, just 30+ minutes a day of watching and
  organic-looking engagement; ramp to 1–2 videos/day, then ~5; never delete and repost; avoid
  18+/gambling/finance content during warm-up; proxies and an antidetect browser throughout.
- The same article states plainly that the old "mass ad flooding" approach **"больше не работает"** —
  stopped working around 2022. A source flagging its own folklore as stale is a good sign; treat
  pre-2022 TikTok tactics as dead by default.
- Reported shadowban triggers: artificial engagement velocity (the figure quoted is "500+ likes/day,
  200+ follows/day"), content pattern-matching against known violations, reused flagged hashtags,
  and **duplicate content fingerprinted across multiple accounts flagging all of them**.
- **Antidetect: no RU source describes TikTok as needing a materially different configuration from
  Meta.** The one detailed review treats it as "one more supported platform". The common claim that
  TikTok fingerprints harder or softer than Meta **is not supported by any source found** — it is
  unanswered, not answered.
- Named tools: Dolphin Anty (with Dolphin Cloud for ad launching), AdsPower, Indigo, Octo, GoLogin.
  Cloud phone farms ($30–40/device/month) for organic multi-accounting.

## Automation maturity

**There is no mature FBTool-equivalent for TikTok.** The TikTok-specific autolaunch tool found
("Dolphin {TT}") is described **by its own review** as "still in beta and being refined".

That gap is the argument for this skill's own stack: with an official MCP server and a documented
API, the deterministic layer you build (`tiktok-ops/04`) is more capable than the off-the-shelf
tooling the RU market has.

## Creative, by field consensus

- **Video massively outperforms static** — stated flatly everywhere ("статичные картинки не
  конвертят"), consistent with TikTok's own creative policy against static images as video.
- **Before/after content faces TikTok-specific moderation rejection** — reported in a nutra case and
  consistent with TikTok's documented creative policy (`08`). One of the few places field reports and
  official policy agree exactly.
- AI-generated creative is now openly discussed as the default for volume production (a 2026 dating
  case frames neural-net image generation as more efficient than sourcing manually).
- EN-side consensus: 3–5 creatives per ad group, refreshed every 7–10 days; decay measured in days,
  not weeks. Prior, not constant (`06`, `09`).
- Spy tools covering TikTok: **PiPiAds** (the TikTok-dedicated one), Minea (e-commerce), BigSpy.
  TikTok's own **Creative Center** is free and closer to an ad library than a spy tool — and has no
  API (`06`).

## The transcripts the operator supplied

Two Russian-language videos: a solo "техничка" tutorial and a two-host live gambling launch on Egypt.
Both were transcribed in full and checked claim by claim against TikTok's official documentation and
current platform behavior; the sections below mark what held up, what is stale, and what is
evasion-oriented rather than compliant.

**What is genuinely useful in them:**

- An end-to-end operator sequence, in order, with the decision points a written guide leaves out.
- Concrete launch parameters from a real session: $30/day, Men 25–54, **optimize for Purchase rather
  than Install**, kill at $1 spent with no click, CPA sanity checks at 3–4% and 8–10% of payout.
  Reported result: ~$400 spent against ~$600 revenue over a weekend — **~50% ROI, below their own
  ~100% target.** Worth noting that the demonstrated case underperformed its own goal; the video
  presents it as a success anyway.
- The Egypt warm-up tactic: farm the account with a soft casual WebView game before running the real
  offer, exploiting lenient moderation of "just a game" content.

**What is stale or contradicted:**

- The **Adjust MMP postback flow** demonstrated was **officially discontinued 31 March 2025** in
  favour of mandatory SAN direct integration (`07`). If the videos are genuinely 2026, that segment
  was already dead when filmed.
- **Daily ad-set duplication to scale** is advised *against* by TikTok's own best-practice guidance.
- Several named services could not be verified as still existing; one cloaking domain used in the
  tutorial is dead.

**What the videos are actually demonstrating:** a policy-evasion stack — farmed accounts, a fabricated
VAT number to dodge tax withholding, virtual cards, a cloaker, and **firing fake Purchase/Install
events to "activate" a pixel**. Real-money gambling requires jurisdiction licensing and nutra requires
regulatory approval (`08`); the entire apparatus exists to route around that.

Recorded here as landscape, because an agent operating in these verticals will meet operators who
work this way and should understand what it is. This skill does not implement it: it does not cloak,
does not fabricate events or tax identifiers, and does not swap landing pages after approval. Those
are the exact mechanisms TikTok's suspension policy names, and the exposure lands on the operator's
accounts and the advertiser's legal entity — not on the person who taught the tactic.

If the operator's actual business is a regulated vertical, the compliant path in `08` is the one that
survives, and its real cost is the certification lead time.

## Vertical notes

- **Gambling/betting is thin on TikTok relative to Facebook** in RU material; one vertical overview
  frames betting/esports as better suited to Twitch, Discord and Telegram.
- **PWA and WebView funnel content essentially ignores TikTok** — the dedicated RU PWA-vs-WebView
  article contains zero TikTok mentions. That pairing is far less developed than on Facebook/Google.
- Russian legal exposure is a separate layer from platform policy: promoting unlicensed casino offers
  in Russia carries proposed penalties up to 6 years' imprisonment and fines to 500K RUB. A 2025
  legal Q&A distinguishes current law from *proposed* escalation — **re-verify against a primary
  legal source before repeating it as settled.**

## Where the community is

RU: partnerkin.com · affmoment.com · zorbasmedia.ru · cpa.rip · protraffic.com ·
traffcardinal.com · vc.ru · Telegram arbitrage channels.
EN: r/PPC and r/TikTokAds · afflift.com · agency blogs that publish real numbers (Common Thread
Collective, Motion, Triple Whale, Tinuiti) · published case studies with disclosed method.

Two 2026 operational notes: **Revealbot rebranded to Bïrch** — stale references are a dead brand; and
agencies reportedly maintain "TikTok Shop kill-switch" documents plus quarterly
platform-concentration audits for clients with >20% revenue exposure. Single anonymous source, but a
concrete behaviour worth knowing about.

## How to use this file

1. As a **source of questions**, not answers. "Practitioners say X" is a hypothesis to check against
   the account's own data.
2. As a **map of where documentation is silent** — account supply, enforcement reality, what actually
   gets banned. Docs will never cover these.
3. **Never as a citation in a plan.** If a decision rests on something here, say it is a practitioner
   claim and name what would falsify it (`01` § C2).
