#!/usr/bin/env crawl4ai-python
"""Crawl a whole site from one seed URL. No URL list needed.

Usage: crawl4ai-python deep_crawl.py https://site.com --max-pages 200 \
           [--pattern '*/product/*'] [--keywords pricing,plans] [--out out.jsonl]
"""
import argparse, asyncio, json, sys
from urllib.parse import urlparse
from crawl4ai import (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode,
                      BFSDeepCrawlStrategy, BestFirstCrawlingStrategy, FilterChain,
                      DomainFilter, URLPatternFilter, KeywordRelevanceScorer,
                      DefaultMarkdownGenerator, PruningContentFilter)


async def main(a):
    domain = urlparse(a.seed).netloc
    filters = [DomainFilter(allowed_domains=[domain])]
    if a.pattern:
        filters.append(URLPatternFilter(patterns=a.pattern.split(",")))

    scorer = (KeywordRelevanceScorer(keywords=a.keywords.split(","), weight=0.8)
              if a.keywords else None)
    Strategy = BestFirstCrawlingStrategy if scorer else BFSDeepCrawlStrategy

    cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        stream=True,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.48)),
        deep_crawl_strategy=Strategy(
            max_depth=a.max_depth, max_pages=a.max_pages, include_external=False,
            filter_chain=FilterChain(filters), url_scorer=scorer),
    )

    seen, ok = set(), 0
    fh = open(a.out, "w", encoding="utf-8") if a.out else None
    async with AsyncWebCrawler(config=BrowserConfig(headless=True, text_mode=True)) as c:
        async for r in await c.arun(a.seed, config=cfg):
            key = r.url.rstrip("/")            # frontier does NOT normalize trailing slashes
            if key in seen:
                continue
            seen.add(key)
            if not r.success:
                print(f"FAIL {r.url}: {r.error_message}", file=sys.stderr); continue
            ok += 1
            rec = {"url": r.url, "depth": r.metadata.get("depth"),
                   "markdown": r.markdown.fit_markdown or r.markdown.raw_markdown}
            (fh.write(json.dumps(rec, ensure_ascii=False) + "\n") if fh
             else print(rec["depth"], rec["url"]))
    if fh: fh.close()
    print(f"pages={ok} unique={len(seen)}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--max-pages", type=int, default=100)
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--pattern"); ap.add_argument("--keywords"); ap.add_argument("--out")
    asyncio.run(main(ap.parse_args()))
