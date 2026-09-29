# Search Techniques

URLs below verified 2026-09-08 (see SKILL.md for the single verification-date policy).

## Operators (quick lookup, not tutorial — a model already knows the syntax)

| Operator | Effect |
|---|---|
| `site:` | restrict to domain |
| `filetype:` | restrict to file type |
| `inurl:` / `intitle:` | match in URL / title |
| `after:` / `before:` | date-restrict |
| `-term` | exclude |
| `allintitle:` (Scholar) | exact-title search |
| `author:"Name"` (Scholar) | author-restricted |

## GitHub gotcha

Google's `site:github.com` strips GitHub-only qualifiers — `language:`, `stars:`, `symbol:`, `path:` are silently ignored, not an error. Those work only inside GitHub's own search (https://github.com/search), not via Google.

GitHub Code Search qualifiers: `language:`, `repo:owner/name`, `org:`/`user:`, `path:`, `symbol:` (defined function/class), `content:` (substring match). `stars:>N` works on repo search, not code search.

Cross-repo alternates: https://sourcegraph.com/search (regex + structural search across many repos); https://grep.app (fast plain-text code search; rate-limits aggressively — expect periodic 429s, it is still alive).

## SIFT — apply before trusting any non-primary source

Stop → investigate the source → find better/independent coverage → trace the claim upstream (bibliography, "Source:"/"Via:" link, "based on/inspired by", or Scholar's "Cited by" for first publication). Original dead → check Wayback.

## Wayback Machine

- Browser: `https://web.archive.org/web/<YYYYMMDD>*/https://example.com/path` (wildcard over a date range)
- CDX API (programmatic): `https://web.archive.org/cdx/search/cdx?url=example.com&output=json&from=YYYYMMDD&to=YYYYMMDD`

Use for: recovering removed docs, diffing API/doc changes across versions, finding deleted repos, verifying a historical claim a live page no longer shows.

## awesome-* index repos

Valid starting point only after checking stars, last-commit recency, and a Contributing doc with actual inclusion criteria — its absence means an unmoderated dump. Treat every listed entry as a lead, not a verified source; evaluate independently. Meta-indexes: https://github.com/sindresorhus/awesome, https://github.com/best-of-lists/best-of.
