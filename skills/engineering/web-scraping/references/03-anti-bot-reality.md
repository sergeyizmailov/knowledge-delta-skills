# 03 — What beats what

2026-08-27. Labels: **[src]** installed source · **[test]** run here · **[bench]** third-party, single
study · 🔺 unverified.

## Benchmark

**[bench]** 7 tools, 31 targets, 3 sweeps, 651 verdicts, one residential IP, 5h, zero drift:

| Tool | OK | Gated | Blocked |
|---|---|---|---|
| nodriver | 28 | 3 | **0** |
| CloakBrowser | 26 | 3 | 2 |
| curl_cffi | 26 | 3 | 2 |
| Patchright | 25 | 3 | 3 |
| Camoufox | 25 | 3 | 3 |
| vanilla Playwright | 24 | 2 | 5 |
| rebrowser-playwright | 24 | 2 | 5 |

1. **The detected layer is CDP itself**, not the JS environment. nodriver drives Chrome directly with
   no Playwright middleware → only zero-block tool. Patching a browser that still speaks
   Playwright-flavoured CDP doesn't fix the tell.
2. **`rebrowser-playwright` failed identically to vanilla** — its patches did nothing measurable.
3. **`curl_cffi` (6.4MB, no browser) matched a 130MB patched Chromium fork.** TLS/JA3 impersonation
   alone clears a lot. **Try a TLS-impersonating HTTP client before any headless browser** — ~100x
   cheaper per page.

Caveats: one publication, one IP, 31 sites, one moment. Vendors ship weekly — prior, not law.
Peak RAM in that study: 57.9MB (curl_cffi) → 13.3GB (Patchright, many contexts).

## Why nodriver isn't installed

It won the benchmark but: 4.7k ★, last commit **2026-05-13** (stale), **AGPL-3.0** — a licensing
problem for anything commercial. Camoufox is MPL-2.0, Crawl4AI Apache-2.0. If rung 4 fails and
licensing is a non-issue, nodriver is next — flag it, don't install silently.

## Captcha taxonomy

| Type | Offline? | Action |
|---|---|---|
| Cloudflare Turnstile | **No** | Avoid triggering: rungs 2-4 + clean residential IP |
| reCAPTCHA v3 | **No** — behavioral score, no challenge | Same; age the session, don't hit cold |
| reCAPTCHA v2 image | Partial | Paid solver API, or visual agent (`browser-use`) |
| hCaptcha | Partial | `hcaptcha-challenger` (2.5k ★, GPL-3.0), not installed |
| Simple image/text | **Yes** | `ddddocr` (14.7k ★, MIT), not installed — last commit 2026-03-10 |
| CF "under attack" JS | n/a | Any real browser; rung 1-2 |

Repos named `cloudflare-bypass-*` / `turnstile-solver-*` are one of: a SeleniumBase UC Mode wrapper,
a token harvester (tokens expire in minutes, bound to harvesting IP), or a paid-API client. **Never
present one as a free solver.**

## Failure signatures — diagnose before escalating

| Symptom | Cause | Fix |
|---|---|---|
| Instant 403, no JS run | IP reputation / TLS fingerprint | Proxy or `curl_cffi`. Browser won't help. |
| CF interstitial never resolves | Browser fingerprint | Rung 2 → 3 → 4 |
| Loads fine, content empty | JS-rendered | `wait_for=`, `scan_full_page` — not evasion |
| ~20 pages then blocks | Rate/behavior | `RateLimiter`, lower `max_session_permit` |
| Headful works, headless fails | Headless tells | Camoufox `headless=True` or `virtual_display` |
| Blocked only some geos | Geo-gate / locale mismatch | Camoufox `geoip=True` + matching proxy |

**Most common self-inflicted block:** proxy in country A, browser reporting locale/timezone of
country B. Camoufox `geoip=True` fixes it; nothing in the Chromium lane does.

## From installed source

**[src]** `browser_manager.py:763` — `if self.config.enable_stealth and not self.use_undetected:`.
Stealth and undetected are **mutually exclusive**; the common "combine for max evasion" advice is
false here. Crawl4AI's own docstring agrees: *"Cannot be used with use_undetected browser mode."*

**[src]** Crawl4AI's "undetected browser" **is Patchright** (`browser_adapter.py:19,411`). Rung 3 buys
exactly the Patchright row above — one better than vanilla, 3 blocks left. Hence rung 4.

**[test]** 2026-08-27: plain, stealth, undetected, `arun_many` 3/3 — all working.

## The layer no open-source tool provides

**Residential IP pools.** Not free, and at volume it's the real cost centre. Every stealth browser
above eventually loses to IP-level blocking regardless of fingerprint quality. Say this upfront when
someone asks for "free scraping at scale" — not after a week of fingerprint debugging.
