# 01 — Crawl4AI at volume

crawl4ai **0.9.2** on Python 3.13.3, in a dedicated venv (`crawl4ai-python`).
API below introspected from the installed package, not docs.

## Dispatchers

```python
from crawl4ai import MemoryAdaptiveDispatcher, SemaphoreDispatcher, RateLimiter

MemoryAdaptiveDispatcher(memory_threshold_percent=85.0, max_session_permit=10)  # default choice
SemaphoreDispatcher(max_session_permit=5)                    # hard cap (e.g. proxy pool size)
RateLimiter(base_delay=(1.0, 3.0), max_delay=60.0, max_retries=3)  # attach to either on 429s
```

`max_session_permit` = tabs, not processes. Past ~15 on 32GB the memory dispatcher throttles anyway.

## arun_many

```python
async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
    results = await crawler.arun_many(urls, config=run_cfg, dispatcher=dispatcher)
```

`stream=True` → async generator; use it on large batches so page 1 processes while page 900 fetches.

Failures don't raise:
```python
ok   = [r for r in results if r.success]
dead = [(r.url, r.error_message) for r in results if not r.success]
```

## Deep crawl — no URL list needed

```python
from crawl4ai import BFSDeepCrawlStrategy, FilterChain, DomainFilter, URLPatternFilter

CrawlerRunConfig(deep_crawl_strategy=BFSDeepCrawlStrategy(
    max_depth=3, max_pages=500, include_external=False,
    filter_chain=FilterChain([DomainFilter(allowed_domains=["example.com"]),
                              URLPatternFilter(patterns=["*/product/*"])])))
```

`BFSDeepCrawlStrategy` (broad) · `DFSDeepCrawlStrategy` (deep branches) · `BestFirstCrawlingStrategy`.
All take `url_scorer=` (`KeywordRelevanceScorer`, `PathDepthScorer`, `FreshnessScorer`,
`DomainAuthorityScorer`, `CompositeScorer`) + `score_threshold`. Best-first = the *relevant* 500
pages, not the first 500.

All take `resume_state` / `on_state_change` / `should_cancel`. On any crawl worth restarting, persist
via `on_state_change` — a crash otherwise costs the whole run.

CLI: `crwl URL --deep-crawl bfs --max-pages 50 -o all -bc`

🔺 **Verified:** the frontier does not normalize trailing slashes — a 5-page run returned both
`quotes.toscrape.com` and `quotes.toscrape.com/`. Dedupe on `url.rstrip('/')` or pay double on every
root-linked site.

## Extraction — pick by cost

| Strategy | Cost | Use |
|---|---|---|
| `JsonCssExtractionStrategy` | free | Stable DOM. **Default.** |
| `JsonXPathExtractionStrategy` / `JsonLxmlExtractionStrategy` | free | CSS can't express it |
| `RegexExtractionStrategy` | free | Emails, prices, phones, IDs |
| `LLMExtractionStrategy` | $/page | Layout varies and nothing else works |

Generate a CSS schema once from a sample page, then run it free forever. Never put
`LLMExtractionStrategy` on a 10k-page crawl untested.

```python
schema = {"name": "Products", "baseSelector": "div.product",
          "fields": [{"name": "title", "selector": "h2", "type": "text"},
                     {"name": "price", "selector": ".price", "type": "text"},
                     {"name": "url",   "selector": "a", "type": "attribute", "attribute": "href"}]}
CrawlerRunConfig(extraction_strategy=JsonCssExtractionStrategy(schema))
# → json.loads(result.extracted_content)
```

## Cutting output tokens

`raw_markdown` = whole page incl. nav/footer. For LLM input, filter and read `fit_markdown`:

```python
DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.48))    # boilerplate
DefaultMarkdownGenerator(content_filter=BM25ContentFilter(user_query="pricing")) # query-relevant
```

## Params that change outcomes

- `cache_mode=CacheMode.BYPASS` — **set it**; `arun` defaults to ENABLED → stale pages.
- `wait_for="css:.results"` / `"js:() => ..."` — content arriving after `domcontentloaded`.
- `scan_full_page=True` + `scroll_delay` — infinite scroll. `virtual_scroll_config` for virtualized
  lists (Twitter-style) where scrolled-past DOM is destroyed.
- `js_code` — click "load more" before extraction.
- `session_id` — reuse one tab across sequential `arun` calls to keep login/state.
- `simulate_user` / `override_navigator` / `magic` (bundles both) — light heuristic evasion only, not
  a substitute for rungs 2-4.
- `text_mode=True` (**BrowserConfig**, not run config) — kills images/CSS, large speedup for text.

No first-class locale param in the Chromium lane — Camoufox handles that properly (`02`).
