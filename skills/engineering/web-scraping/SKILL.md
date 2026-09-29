---
name: web-scraping
description: "Mass crawl/scrape sites incl. anti-bot (Cloudflare, Akamai, DataDome, PerimeterX). Crawl4AI = scale (arun_many, dispatchers, deep crawl, LLM-ready markdown); Camoufox = fingerprint evasion. For: scrape N pages, crawl a site, extract structured data, 403/challenge/bot-detection, captcha."
allowed-tools: Bash
---

# Mass Scraping — Crawl4AI + Camoufox

Verified 2026-08-27 (macOS arm64). Both engines and all three templates smoke-tested.

## Install (if `crawl4ai-python` is not on PATH)

- **crawl4ai** — `github.com/unclecode/crawl4ai` · PyPI `crawl4ai`
- **camoufox** — `github.com/daijro/camoufox` · PyPI `camoufox[geoip]`
- **curl_cffi** — `github.com/lexiforest/curl_cffi` · PyPI `curl_cffi`

Dedicated venv, then `crawl4ai-setup` and `python -m camoufox fetch`. Four traps, each verified here:

1. **Python 3.10–3.13 only.** 3.14 is not supported — if `python3` is 3.14, install 3.13 explicitly.
2. **`crawl4ai`, not `crawl4ai[all]`.** The extra pulls torch + transformers (GBs) that scraping never uses.
3. **`crawl4ai-setup`, not `playwright install chromium`.** Setup also installs **Patchright**, which
   rung 3 needs; without it the undetected adapter dies.
4. **Shim the venv python with a wrapper, never a symlink.** A symlinked venv python resolves
   `sys.prefix` to the system interpreter and cannot import crawl4ai:
   ```sh
   printf '#!/bin/sh\nexec "$VENV/bin/python" "$@"\n' > ~/.local/bin/crawl4ai-python
   ```

## Entry points

```bash
crwl https://example.com -o md -bc   # one page → markdown
crawl4ai-python script.py            # anything bigger
```

Both are shims into the dedicated venv. **System `python3` cannot import crawl4ai/camoufox** — always
`crawl4ai-python` or the venv binary directly. Don't pip-install these into another environment.

`crwl`: `-o md` · `-o all` (JSON) · `-bc` (bypass cache) · `--deep-crawl bfs --max-pages N`.
`-o json` fails without an extraction schema — use `-o all`.

## Escalation ladder — climb only on failure

| # | Approach | Cost | When |
|---|---|---|---|
| 0 | `curl_cffi` (TLS/JA3 impersonation, no browser) | ~10ms/page | **Try first.** Clears more than expected — see `03` |
| 1 | `crwl` / plain `AsyncWebCrawler` | ~1s/page | Page needs JS |
| 2 | `BrowserConfig(enable_stealth=True)` | ~0 | Rung 1 → challenge/403 |
| 3 | `UndetectedAdapter()` (= Patchright) | +~1s/page | Rung 2 still blocked |
| 4 | Camoufox + `raw://` bridge | 200MB/instance, slow | Chromium fingerprint-blocked |
| 5 | Residential proxies | $ | Blocked by IP, not fingerprint |

**Rungs 2 and 3 are mutually exclusive** — `browser_manager.py:763`:
`if self.config.enable_stealth and not self.use_undetected:`. The undetected adapter silently drops
`enable_stealth`. "Combine both for max evasion" advice is false; verified in installed source.

## Captcha

**reCAPTCHA v3 and Turnstile are not solvable offline** — behavioral/TLS scoring, no image. The only
play is not triggering them (rungs 2-4). Repos named `*-turnstile-solver` = token harvesters
(minutes-long TTL) or paid-API wrappers.

Simple image captchas *are* offline-solvable → `ddddocr`, not installed. Ask first.

Still blocked at rung 5? Say so. Never return partial data silently.

## References

| Need | File |
|---|---|
| `arun_many`, dispatchers, deep crawl, extraction, tuning | `references/01-crawl4ai-scale.md` |
| Fingerprints, proxy+geoip, humanize, `raw://` bridge | `references/02-camoufox.md` |
| Benchmarks, failure signatures, what beats what | `references/03-anti-bot-reality.md` |

`templates/` — copy, don't retype: `mass_crawl.py` (rungs 1-3) · `camoufox_bridge.py` (rung 4) ·
`deep_crawl.py` (whole site).

## Non-negotiables

- `cache_mode=CacheMode.BYPASS` / `-bc` — default ENABLED serves stale pages and still reports success.
- One `AsyncWebCrawler` context for all URLs. Per-URL `async with` relaunches the browser (~50x slower).
- Check `result.success` per item — `arun_many` returns failures, never raises.
- Respect robots.txt + rate limits unless the target is the user's. Use `RateLimiter`, not a bare loop.
