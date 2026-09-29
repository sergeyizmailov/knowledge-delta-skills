# 01 — Infra & identity: antidetect, proxies, sessions

Reviewed 2026-08-28; proxy note added 2026-09-29. **Practitioner doctrine, not Meta documentation** — nothing here
is [official]; validate against your own portfolio. Attribution method → `06`.

Chain Meta reads as one "user": FB profile → antidetect profile → proxy (exit IP) →
agency ad accounts/BM/pages. Inconsistency (two IPs, two devices, odd hours) raises
security score → checkpoint / session kill / restriction / disable.

## IP discipline (core rule)

Operational session hygiene, not a Meta auth requirement — API calls needn't share
the browser's IP. A grey persona's trust rests on looking like one consistent human.
Token type does not waive the assigned-egress rule; direct egress needs an explicit
`META_ALLOW_NO_PROXY=1` decision for that BM (`02`); under `metaops` that decision lives in the
workspace (`defaults.allow_no_proxy: true`), an exported env var is dropped. Field 2026-09-29: a scraped
EAAB from a Mac with no proxy passed `metaops doctor` on an own BM — it works, it does not show the
direct IP is safe (`02` §5).

- Persona's entire life from ONE exit IP: browser, API, token gen. Route scripts
  through the same proxy from a secrets file — don't trust a human to VPN.
- Don't rotate casually (new IP = new signal). Change only when burned or unusably
  slow, then change BOTH ends (antidetect + scripts) together.
- Datacenter IPs = cheap/fast/risk; residential/mobile safer for the main persona.
  Agency setups usually ship a proxy — use theirs.
- **How many personas per exit is genuinely contested. Do not let either side sound settled.**
  - Community consensus, both languages, essentially without dissent: **one dedicated exit per
    account**. Stated mechanism is that a shared IP across accounts is itself the linkage
    signal Meta's Account Integrity policy describes (`07`). A research pass on 2026-09-24
    found no source anywhere defending shared exits at scale. Note the incentive runs both
    ways and does not explain the unanimity: proxy sellers profit from this advice, antidetect
    vendors would profit from the opposite, and none of them take the opposite.
  - Against it, one practitioner report: a TL running grey traffic at scale describes a buyer
    holding **65 accounts on one proxy set** with no elevated mortality (2026-09-22). Single
    source, one team, one account-quality tier. The obvious confound is that good accounts
    carry bad infra for a while, so surviving on shared exits does not show shared exits are
    safe.
  🔺 If an operator's TL asserts the shared-exit position, that is a live disagreement with the
  whole community, not a settled shortcut — say so plainly and let them decide, because they
  carry the cost either way. Absent a TL ruling, follow the consensus: one exit per account.
- What is NOT contested is how to assign them: a **fixed list** and a deterministic map, e.g.
  row N takes entry `(N-1) % len(list)`. Every bookkeeping scheme tried instead failed —
  a numbered slot list with an offset wrapped modulo and handed out an exit tied to a banned
  account (field-observed 2026-09-21), and the consume-and-delete pool that replaced it ran
  empty and blocked all profile creation (field-observed 2026-09-22). No state file, nothing to
  run out of, nothing to reconcile, and re-running a row reproduces the same exit.

## socks5 vs socks5h (gotcha)

Script through `socks5h://` (proxy resolves DNS). Plain `socks5://` resolves DNS
locally → TLS to graph.facebook.com dies with `SSL: UNEXPECTED_EOF_WHILE_READING`.
Python: `pip install pysocks`, `proxies={"https":"socks5h://user:pass@ip:port"}`.
curl: `-x socks5h://user:pass@ip:port`.

## Sessions ↔ tokens

- API calls are stateless — no sessions, can't "hang." "Leftover API sessions" is a myth.
- Session a token was minted from dies on logout / password change / Meta security
  rotation / multi-session flag → token dies with it, even a 60-day one.
- Regenerating a token = new login. During a flag, every regen pokes the bear:
  regen once, exchange to long-lived immediately, stop.

## Restrictions & checkpoints

- "Can't create multiple sessions" (~1 day): not a documented Meta rule (Meta
  allows concurrent sessions) — anti-abuse response to disparate-geo logins/cookie
  collisions from juggling personas on one device/IP. Freeze, let expire, keep ONE
  session; fix is IP/device discipline, not a setting.
- Checkpoint (long load → logout): identity confirmation. Complete ONCE, calmly,
  from the antidetect profile — repeated failures worsen it.
- Ad account disabled/restricted: background rate. Agency/old-personal/log accounts are
  consumables — don't appeal alone, ask TL/agency "appeal or replace"; keep a reserve pipeline
  (`05`).

## Pre-buy / farmed-account QC [practitioner, MagicClick, 2026-08-30]

View-source logged-in Ads Manager HTML for `ADS_TRUST_TIER_`/`ADS_TRUSTED_TIER_` —
farmed-vs-newreg tell, **not** a spend cap (circulating dollar-tier tables are
vendor construction, already rejected in `09`). Empty Off-Facebook activity **or**
"Ads based on custom audiences" **or** no feed ads → likely not farmed. Empty Fan
Page = review flag. Still judge after $30-50 spend (SKILL #6). Chrome-agent driving
Ads Manager inside antidetect on rented seats → selfie/SMS/freeze risk.

## Domain / pixel rotation cadence (rotate before burn)

Signal-driven, not a fixed clock:

- Domain: rotate on signals — rising bot_share/moderation crawlers on the white
  page, spam/reputation flag, SSL/blocklist hit, or LP CTR collapse with normal
  clicks (`tracker-ops/03`). Keep fresh domains pre-provisioned (SSL valid, DNS
  propagated, slightly aged), run each through the pre-flight stack first
  (`google-grey-ops/05`: Safe Browsing/VirusTotal/Wayback/WHOIS). Rotate the
  domain, not the whole funnel — keeps attribution possible.
- Pixel: asset with history — rotating costly (new pixel = cold, re-learns,
  audiences reset), don't rotate reactively. Real lever: pre-segment — split
  pixels per domain-cluster/risk tier so a burned funnel doesn't take the shared
  pixel with it, as far as each dataset still gets enough events to optimize. By
  the time a pixel is flagged it's usually too late — decision is upstream.
- Never rotate domain + pixel + creative + account together — loses which one
  burned (`06` balanced designs).

## Where sessions live

Accounts Center → Password and security → Where you're logged in
(`accountscenter.facebook.com/password_and_security`; old
`facebook.com/settings?tab=security` redirects/dies). Non-setup geos = the leak
that flagged the persona.

## Cookie liveness can't be scripted

Facebook returns HTTP 400 to ANY non-browser client (curl/urllib) even through a
healthy proxy with no cookies — it fingerprints TLS (field-observed 2026-09-21). A
400 from a script proves nothing about cookie liveness. Do not build a checker:
the only valid liveness test is opening the antidetect profile itself. Local API
mechanics for driving that profile → the fuller reference `20-adspower-local-api.md`.

## Human behavior

- Open FB/developers/business sites for a work persona ONLY inside its antidetect
  profile — never a daily browser.
- No mass actions on a fresh profile: a few logins, some browsing, then work.
  Profile creation → ads day 0 is a classic ban path.
- One action at a time when unstable. Batch API edits (rename, pause) fine; creates are
  paced per ad account (`00` §5); profile/security edits agitate the system.
