# Sources, Databases & APIs

URLs and rate limits below verified 2026-09-08 (see SKILL.md for the single verification-date policy) against each service's own docs — recheck a number here before relying on it if this file looks old.

## Docs-index tools

Prefer one of these over general web search for library/API/framework documentation — narrower, version-scoped, and current.

| Tool class | Example | Notes |
|---|---|---|
| Docs-index MCP/CLI | Context7 (https://github.com/upstash/context7) | 9000+ libraries; one example of the class, not the only option |
| Offline/general doc aggregator | https://devdocs.io/ | 100+ doc sets, fuzzy search |
| Canonical web-platform reference | https://developer.mozilla.org/ | HTML/CSS/JS/Web APIs |
| Browser feature support | https://caniuse.com/ | Support tables |

## Standards bodies

Root domains are stable; cite the specific spec or RFC number, not just the domain.

| Body | URL | Covers |
|---|---|---|
| IETF / RFC Editor | https://www.rfc-editor.org/ | TCP/IP, HTTP, TLS, DNS, email |
| W3C | https://www.w3.org/ | HTML, CSS, SVG, WAI-ARIA, WASM |
| WHATWG | https://whatwg.org/ | HTML, DOM, Fetch (living standards) |
| TC39 | https://github.com/tc39/proposals | ECMAScript/JS evolution |

## Academic paper databases

| Database | URL | Access | API notes |
|---|---|---|---|
| arXiv | https://arxiv.org/ | Free | REST + OAI-PMH; official ToU caps at **1 request per 3 seconds**, not the "few req/s" a model tends to assume |
| Semantic Scholar | https://www.semanticscholar.org/ | Free | Unauthenticated: 1000 req/s shared across *all* anonymous callers (effectively far less per IP under load); an API key raises the floor to 1 req/s guaranteed — request one via the site's own API page |
| OpenAlex | https://openalex.org/ | Free | REST; successor to Microsoft Academic Graph |
| DBLP | https://dblp.org/ | Free, CC0 | XML dumps |
| Connected Papers | https://www.connectedpapers.com/ | Free | Visual citation graph, not an API |
| Google Scholar | https://scholar.google.com/ | Free | No official API |

Paywalled — check arXiv or the author's site for a preprint first: ACM DL (https://dl.acm.org/), IEEE Xplore (https://ieeexplore.ieee.org/). Both return anti-bot challenge codes to a plain fetch; that is not proof either is down.

## Code search across repos

| Tool | URL | Notes |
|---|---|---|
| GitHub Search API | https://docs.github.com/en/rest/search | 30 req/min authenticated for repo/issue/user/topic search; code search is capped separately, lower, at 10 req/min |
| GitHub Advisory DB | https://github.com/advisories | Security advisories |
| Sourcegraph | https://sourcegraph.com/search | Cross-repo regex + structural search |

## Books

Commercial: O'Reilly (oreilly.com), Manning (manning.com, MEAP early access), No Starch (nostarch.com, security focus), Packt (packtpub.com).
Open: Internet Archive (archive.org, Controlled Digital Lending), Project Gutenberg (gutenberg.org), author home pages (often carry a free preprint of a paywalled paper).

**Shadow libraries** (unauthorized copies of copyrighted work — illegal to access/download in many jurisdictions): use only with the user's explicit approval for the current task, and only after trying the author's site, an institutional repository, Scholar's "All N versions", a direct request to the author, and library access. Their domains rotate on a legal-takedown cycle — verified 2026-09-08, the two best-known mirror names did not resolve even via a DNS-over-HTTPS resolver — so search for the current mirror at time of use rather than trusting any hardcoded domain, including one in this file. Never cite the shadow source in output; cite the canonical DOI or arXiv ID, the mirror is a delivery channel only.

## Patents

| Database | URL | Coverage |
|---|---|---|
| Google Patents | https://patents.google.com/ | Global, full-text, free |
| USPTO (PubEasy) | https://ppubs.uspto.gov/pubwebapp/ | US patents |
| Espacenet | https://worldwide.espacenet.com/ | 140M+ publications, EU |

## Web archive

https://web.archive.org/ — CDX API syntax and use cases: `search-techniques.md`.
