# 02 — Camoufox

camoufox **0.5.5**, browser build **v152.0.4-beta.29**, `[geoip]` extra (GeoLite2 ipv4+ipv6).
Browser binary is cached outside the venv (`python -m camoufox path` prints where).

Firefox fork patched at **C++ level**, not injected JS. That's the point: JS-patch stealth
(playwright-stealth, rebrowser) is detectable by inspecting the patch. Camoufox has nothing to
inspect — the engine reports the spoofed value natively.

## Verified on this machine

```python
from camoufox.sync_api import Camoufox
with Camoufox(headless=True, humanize=True, os=("windows", "macos")) as b:
    p = b.new_page(); p.goto("https://example.com")
```
2026-08-27 from macOS arm64: `navigator.webdriver=False`, UA `Windows NT 10.0; Win64; x64; rv:152.0
Firefox/152.0`, `platform=Win32`, `hardwareConcurrency=8` — coherent Windows fingerprint from a Mac.

Async: `from camoufox.async_api import AsyncCamoufox`. Page object is standard **Playwright**.

## Options

```python
Camoufox(
    os=("windows","macos","linux"),  # random per launch; keep plausible vs proxy
    humanize=True,                   # cursor curves; True=auto or float=max seconds
    geoip=True,                      # locale/timezone/lat-lon derived FROM THE PROXY IP
    proxy={"server":"http://host:port","username":"u","password":"p"},
    locale="en-US",                  # only if not using geoip
    block_images=True,               # big speedup; some sites detect missing image loads
    block_webrtc=True,               # stops WebRTC IP leak past the proxy
    enable_cache=True, screen=..., window=..., headless=True,  # "virtual" on Linux = Xvfb
)
```

**`geoip=True` is the highest-value flag.** A German residential proxy with an
`en-US`/`America/New_York` browser is a trivial contradiction — and this mismatch catches more
stealth setups than any JS leak.

Full surface: `config, os, block_images, block_webrtc, block_webgl, disable_coop, webgl_config,
geoip, geoip_db, humanize, locale, addons, fonts, custom_fonts_only, exclude_addons, screen, window,
fingerprint, fingerprint_preset, ff_version, headless, main_world_eval, executable_path, browser,
firefox_user_prefs, proxy, enable_cache, args, env, i_know_what_im_doing, debug, virtual_display`.

`i_know_what_im_doing=True` disables incoherent-fingerprint guardrails. Almost always a mistake —
incoherence *is* the detection vector.

## The bridge — Camoufox fetch → Crawl4AI markdown (verified)

They don't compose directly: Crawl4AI connects over CDP, Camoufox is Firefox and speaks none.
Passing Camoufox as `browser_type` does not work. The join is `raw://`:

```python
async with AsyncCamoufox(headless=True, humanize=True, geoip=True) as b:
    page = await b.new_page()
    await page.goto(url, wait_until="domcontentloaded")
    html = await page.content()

async with AsyncWebCrawler() as c:
    r = await c.arun(f"raw://{html}", config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
    md = r.markdown.raw_markdown
```

Verified end-to-end 2026-08-27. Gains Camoufox evasion + Crawl4AI markdown/filters/extraction.
Loses `arun_many`, dispatchers, deep crawl — write your own `asyncio.Semaphore` loop.
Template: `templates/camoufox_bridge.py`.

## Cost

200MB+ RAM/instance and slow — one third-party benchmark measured ~42s average through a Turnstile
challenge. One browser, many `new_page()`, concurrency 3-5. Never one instance per URL.

## CLI

```bash
crawl4ai-python -m camoufox fetch|active|list|set|path|server|remove
```
Re-run `fetch` after upgrading the pip package — binary and package versions are coupled.
`server` gives a Playwright **Firefox** ws endpoint for sharing a warm browser across workers; still
not CDP, so Crawl4AI can't attach — use the `raw://` bridge.
