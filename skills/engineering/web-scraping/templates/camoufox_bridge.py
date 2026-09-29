#!/usr/bin/env crawl4ai-python
"""Rung 4: Camoufox fetches (fingerprint evasion), Crawl4AI converts (markdown/extraction).

Camoufox speaks no CDP, so Crawl4AI cannot drive it. The join is the raw:// scheme.
Usage: crawl4ai-python camoufox_bridge.py urls.txt [--proxy http://u:p@host:port]
"""
import argparse, asyncio, json, sys
from camoufox.async_api import AsyncCamoufox
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode


async def fetch_all(urls, proxy, concurrency):
    sem = asyncio.Semaphore(concurrency)          # Camoufox has no dispatcher — cap it yourself
    opts = dict(headless=True, humanize=True, block_webrtc=True,
                os=("windows", "macos"), enable_cache=True)
    if proxy:
        opts["proxy"] = {"server": proxy}
        opts["geoip"] = True                      # locale/tz derived FROM the proxy IP — critical

    pages = {}
    async with AsyncCamoufox(**opts) as browser:  # ONE browser, many pages
        async def one(url):
            async with sem:
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    pages[url] = await page.content()
                except Exception as e:
                    print(f"FETCH FAIL {url}: {type(e).__name__}: {e}", file=sys.stderr)
                finally:
                    await page.close()
        await asyncio.gather(*(one(u) for u in urls))
    return pages


async def main(urls, proxy, out, concurrency):
    pages = await fetch_all(urls, proxy, concurrency)
    fh = open(out, "w", encoding="utf-8") if out else None
    async with AsyncWebCrawler() as c:
        for url, html in pages.items():
            r = await c.arun(f"raw://{html}",
                             config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
            if not r.success:
                print(f"CONVERT FAIL {url}", file=sys.stderr); continue
            rec = {"url": url, "markdown": r.markdown.raw_markdown}
            (fh.write(json.dumps(rec, ensure_ascii=False) + "\n") if fh
             else print(url, len(rec["markdown"])))
    if fh: fh.close()
    print(f"fetched={len(pages)}/{len(urls)}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("urlfile"); ap.add_argument("--proxy")
    ap.add_argument("--out"); ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()
    urls = [l.strip() for l in open(a.urlfile) if l.strip() and not l.startswith("#")]
    asyncio.run(main(urls, a.proxy, a.out, a.concurrency))
