#!/usr/bin/env crawl4ai-python
"""Rungs 1-3: mass crawl a URL list with escalating evasion.

Usage: crawl4ai-python mass_crawl.py urls.txt [--rung 1|2|3] [--out out.jsonl]
"""
import argparse, asyncio, json, sys
from crawl4ai import (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode,
                      MemoryAdaptiveDispatcher, RateLimiter, DefaultMarkdownGenerator,
                      PruningContentFilter)
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.browser_adapter import UndetectedAdapter


def build_crawler(rung: int):
    """Rung 1 plain · 2 stealth · 3 undetected (Patchright). 2 and 3 are mutually exclusive."""
    if rung == 3:
        bc = BrowserConfig(headless=True, text_mode=True)
        strat = AsyncPlaywrightCrawlerStrategy(browser_config=bc, browser_adapter=UndetectedAdapter())
        return AsyncWebCrawler(crawler_strategy=strat, config=bc)
    bc = BrowserConfig(headless=True, text_mode=True, enable_stealth=(rung == 2))
    return AsyncWebCrawler(config=bc)


async def main(urls, rung, out, concurrency):
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,                       # never serve stale
        stream=True,                                       # process as they land
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.48)),
    )
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=85.0,
        max_session_permit=concurrency,
        rate_limiter=RateLimiter(base_delay=(1.0, 3.0), max_delay=60.0, max_retries=3),
    )
    ok = dead = 0
    fh = open(out, "w", encoding="utf-8") if out else None
    async with build_crawler(rung) as crawler:                  # ONE context for all URLs
        async for r in await crawler.arun_many(urls, config=run_cfg, dispatcher=dispatcher):
            if r.success:
                ok += 1
                rec = {"url": r.url,
                       "markdown": r.markdown.fit_markdown or r.markdown.raw_markdown,
                       "status": r.status_code}
                (fh.write(json.dumps(rec, ensure_ascii=False) + "\n") if fh
                 else print(rec["url"], len(rec["markdown"])))
            else:
                dead += 1
                print(f"FAIL {r.url}: {r.error_message}", file=sys.stderr)
    if fh: fh.close()
    print(f"rung={rung} ok={ok} failed={dead}", file=sys.stderr)
    if dead and rung < 3:
        print(f"-> {dead} failed; retry those with --rung {rung + 1}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("urlfile")
    ap.add_argument("--rung", type=int, default=1, choices=(1, 2, 3))
    ap.add_argument("--out")
    ap.add_argument("--concurrency", type=int, default=10)
    a = ap.parse_args()
    urls = [l.strip() for l in open(a.urlfile) if l.strip() and not l.startswith("#")]
    asyncio.run(main(urls, a.rung, a.out, a.concurrency))
