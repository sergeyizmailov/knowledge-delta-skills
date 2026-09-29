---
name: secure-coding
description: Use when writing JavaScript, Node.js, HTML, CSS code for websites, landing pages, admin panels, APIs. Reduces common vulnerability classes (XSS, injection, SSRF, etc.) via secure libraries, proper headers, and safe patterns. Includes AI code vulnerability patterns.
---

# Secure Coding (JS / Node.js / HTML / CSS)

Apply automatically when writing any web code — hardened by default. Validate deployment topology (reverse proxy, TLS termination, CDN) before applying `trust proxy`, HSTS `preload`, or cross-origin isolation defaults. AI-generated code has 2.74x more vulnerabilities than human-written; 45% of AI samples introduce an OWASP Top 10 vuln (Veracode, 100+ LLMs).

## Workflow

**New code:** secure defaults first (helmet, cors explicit origins, rate-limit, body size limit) → per endpoint: auth middleware → zod validation → parameterized queries → generic errors → scan against "Never Do" table.

**Dependencies (prefer `context7` MCP; else npm registry / GitHub / GHSA):** latest stable version, no open critical/high CVEs, maintainer disqualify only on: deprecated, archived, unanswered CVE > 90 days, ownership transferred to unknown party (mature libs like `argon2`/`helmet`/`jose` sit quiet for months and stay canonical). Apps: `package-lock.json` + `npm ci`; libs: semver ranges + audit in CI. Prefer Safe Library Stack below.

**Auditing existing code:** entry point → routes → middleware chain → static serving → `npm audit` + pinned versions + known compromised packages → configs (NODE_ENV, exposed .env/.git/source maps, debug endpoints) → per route: auth → validation → data handling → errors → headers/CSP/CORS/cookies/ports → report.

**Audit output format:**
```
### [CRITICAL/HIGH/MEDIUM/LOW] Finding title
- **Location**: file:line
- **Vulnerability**: CWE-XXX (name)
- **Impact**: what an attacker can do
- **Fix**: specific code change
```

## OWASP Top 10:2025 Quick Map

| # | Risk | Exploit | Defense |
|---|------|---------|---------|
| A01 | Broken Access Control | IDOR: `/api/user/123` → `/124` | Auth check on EVERY endpoint, 404 not 403 |
| A02 | Security Misconfiguration | Default creds, debug, verbose errors, exposed files | Helmet, CSP, no defaults, generic errors, block dotfiles |
| A03 | Supply Chain | Compromised npm packages (Shai-Hulud: 500+) | Pin versions, `npm ci --ignore-scripts`, audit |
| A04 | Cryptographic Failures | Weak hashing, plaintext, broken TLS | Argon2id, AES-256-GCM, TLS 1.2+ only |
| A05 | Injection | SQLi, XSS, SSTI, prototype pollution, prompt injection | Parameterized queries, DOMPurify, no `eval()` |
| A06 | Insecure Design | No rate limit on login, no anti-automation | Rate limit, CAPTCHA, lockout |
| A07 | Auth Failures | JWT `alg:none`, weak secrets, no rotation | `jose` + RS256, strong secrets, regenerate on login |
| A08 | Integrity Failures | Tampered CDN scripts, unsigned updates | SRI hashes, verify signatures |
| A09 | Logging Failures | No auth logging, secrets in logs | Log auth events, NEVER log tokens/passwords |
| A10 | Exception Mishandling | Stack traces + DB errors to client | Generic 500, detail to server logs only |

## Never Do (hacker's wishlist)

| Bad Code | Attack | Impact |
|----------|--------|--------|
| `eval(userInput)` | Code injection | RCE |
| `innerHTML = userInput` | XSS | Session theft, keylogging |
| `db.query(\`...${id}\`)` | SQL injection | Full DB dump |
| `res.send(error.stack)` | Info leak | DB creds, paths, versions |
| `jwt.verify(token, key)` without `algorithms` | `alg:none` bypass | Auth bypass, admin |
| `require(userInput)` | Path traversal | RCE, file read |
| `fetch(userUrl)` without validation | SSRF | Internal scan, cloud metadata |
| `JSON.parse` + unchecked deep merge | Prototype pollution | RCE via gadget chain |
| `password = md5(input)` | Hashcat 100B/sec GPU | Account takeover |
| `cors({ origin: '*' })` | Cross-origin access | Data theft from any domain |
| `cookie: { sameSite: 'none' }` without reason | CSRF | Unauthorized actions |
| `npm install` in CI | Supply chain | Malicious postinstall |
| `/^(.+)+$/.test(userInput)` | ReDoS | Event loop freeze |
| WebSocket without origin check | CSWSH | Session hijack via any site |
| `SELECT` then `UPDATE` without lock | Race condition | Double-spend |

## Safe Library Stack (2025-2026)

| Purpose | Use | Avoid | Why |
|---------|-----|-------|-----|
| Password hash | `argon2` / `@node-rs/argon2` | md5, sha256 | GPU-resistant, OWASP standard |
| JWT | `jose` (v6+) | `jsonwebtoken` | Maintained, universal runtime, no `alg:none` |
| HTML sanitize | `DOMPurify` (v3+) | regex sanitizers | 55% of sanitizers vulnerable to DOM clobbering |
| HTTP security | `helmet` (v8+) | manual headers | 11 headers correct by default |
| Rate limit | `express-rate-limit` + Redis | nothing | Brute-force takes minutes without it |
| Validation | `zod` / `joi` | manual `if` | Type-safe, strips unknown fields |
| ORM | `drizzle-orm` / `prisma` | string concat | Parameterized by design |
| Session | `express-session` + Redis | cookie-only | Server-side, revocable |
| Template | Handlebars / Nunjucks (`autoescape:true`) | EJS `<%-` | Auto-escape prevents XSS |
| Regex | `re2` | nested quantifiers | Linear time, no backtracking |

## Critical CVEs (2025-2026)

| CVE | Target | CVSS | Impact |
|-----|--------|------|--------|
| CVE-2025-55182 | React Server Components / Next.js | 10.0 | Pre-auth RCE, single HTTP request |
| CVE-2025-59465 | Node.js HTTP/2 | 7.5 | Crash via malformed HEADERS |
| CVE-2026-33660 | n8n | 9.4 | RCE via workflow nodes |
| CVE-2025-53773 | GitHub Copilot | 9.6 | RCE via prompt injection |
| CVE-2026-3125 | OpenNext Cloudflare | High | SSRF via path normalization bypass |
| CVE-2025-59145 | GitHub Copilot (CamoLeak) | 9.6 | Secret exfiltration |
| Shai-Hulud | npm ecosystem | Critical | Self-propagating worm, 500+ packages |
| Axios compromise | axios 1.14.1 / 0.30.4 | Critical | RAT in 3-hour window (DPRK) |

## Reference Files

| Concern | File |
|---------|------|
| Express baseline, rate limit, Zod, error handler, prod misconfigs | `express.md` |
| Argon2id, JWT (`jose`), sessions, RBAC, timing-safe, JWT attacks | `auth.md` |
| Parameterized SQL, TOCTOU, row locks, distributed locks | `db.md` |
| Uploads (multer, MIME, magic bytes), path traversal | `uploads.md` |
| SSRF (DNS resolve, private-IP block, redirects), prototype pollution | `ssrf.md` |
| ReDoS, WebSocket hardening, CSWSH | `dos.md` |
| GraphQL: introspection, depth/complexity, batching, field auth | `graphql.md` |
| LLM apps: injection filter, delimited prompts, output validation, tool least-privilege | `llm.md` |
| XSS, DOM clobbering, template injection, postMessage, iframe sandbox | `frontend-security.md` |
| Security headers, CSP nonces, cookie flags, CORS | `headers-and-csp.md` |
| Dependencies, lockfiles, SRI, supply-chain attacks, emergency response | `supply-chain.md` |
| Reviewing AI-generated code, CWE stats, OpenSSF guidance | `ai-code-mistakes.md` |
