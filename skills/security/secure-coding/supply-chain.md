# Supply Chain Security & Dependencies

## Major npm Attacks (2025-2026)

| Attack | Date | Impact | Vector |
|--------|------|--------|--------|
| Shai-Hulud worm | Sep 2025 | 500+ packages, 2.6B weekly downloads | Stolen maintainer tokens, self-propagating |
| Axios compromise | Mar 2026 | v1.14.1 + v0.30.4 with RAT | Compromised maintainer account |
| Chalk supply chain | 2025 | color/faker packages | Maintainer sabotage |
| TeamPCP | 2025 | Multiple packages | Typosquatting + install scripts |

## Package.json Hardening

```json
{
  "dependencies": {
    "express": "4.21.2",
    "helmet": "8.1.0",
    "cors": "2.8.5"
  },
  "overrides": {
    "axios": "1.7.9"
  },
  "scripts": {
    "preinstall": "npx only-allow npm",
    "audit": "npm audit --audit-level=high",
    "audit:fix": "npm audit fix",
    "check-deps": "npx depcheck"
  }
}
```

Rules:
- Pin EXACT versions (no `^`, `~`, `*`, `latest`)
- `overrides` to force transitive dependency versions
- Review changelog before upgrading

## Lockfile Security

```bash
# CI: always ci (respects lockfile exactly)
npm ci --ignore-scripts

# Development: after updating package.json
npm install

# Commit lockfile to git
git add package-lock.json
```

Rules:
- Always commit `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml`
- `npm ci` in CI/CD (fails if lockfile ≠ package.json)
- `--ignore-scripts` prevents postinstall attacks
- Review lockfile diffs in PRs (detect unexpected dependency changes)

## Dependency Audit

```bash
npm audit                      # known vulnerabilities
npm audit fix                  # auto-fix where possible
npm outdated                   # outdated packages
npx depcheck                   # unused dependencies
npx license-checker --onlyAllow "MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0"
```

### Automated Auditing

```yaml
# GitHub Actions: scheduled audit
name: Security Audit
on:
  schedule:
    - cron: '0 8 * * 1'  # every Monday 8am
  push:
    paths: ['package-lock.json']

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci --ignore-scripts
      - run: npm audit --audit-level=high
```

## Choosing Safe Dependencies

### Checklist Before Adding a Package

1. **Maintenance**: security patches land, not deprecated/archived, ownership not recently transferred to unknown party. Raw commit cadence is a poor proxy — mature crypto/security libs (`argon2`, `helmet`, `jose`) can be quiet for months and still be canonical
2. **Downloads**: >10K weekly, trending stable (sudden spike = recently-popular, unaudited)
3. **Issues**: no unanswered CVE/GHSA reports older than 90 days
4. **Dependencies**: how many transitive deps?
5. **Size**: reasonable for what it does?
6. **Alternatives**: built-in Node.js APIs possible?
7. **Security**: known CVEs? Check `npm audit` and GHSA after install
8. **Source**: inspect for postinstall scripts, network calls in install hooks, obfuscated code

### Red Flags

- Published within last 30 days (unless major org)
- Few downloads but claims popular use
- Many dependencies for a simple task
- `postinstall` script that downloads external code
- Obfuscated source
- Author has very few published packages
- Name similar to popular package (typosquatting)

### Recommended Libraries by Category

| Purpose | Package | Weekly Downloads | Notes |
|---------|---------|-----------------|-------|
| HTTP framework | `express` | 35M+ | Industry standard |
| Validation | `zod` | 15M+ | TypeScript-first, zero deps |
| Password hash | `argon2` | 500K+ | OWASP recommended |
| JWT | `jose` | 10M+ | Universal runtime, maintained |
| Sanitize HTML | `dompurify` | 8M+ | Cure53 maintained |
| Rate limiting | `express-rate-limit` | 2M+ | Simple, pluggable stores |
| Security headers | `helmet` | 3M+ | Express middleware |
| ORM | `drizzle-orm` / `prisma` | 2M+ / 5M+ | Type-safe queries |
| Env vars | `dotenv` | 40M+ | Simple, no deps |
| Logging | `pino` | 5M+ | Fast, structured JSON |

## Subresource Integrity (SRI)

```html
<script
  src="https://cdn.example.com/lib@1.2.3/dist/lib.min.js"
  integrity="sha384-HASH_VALUE_HERE"
  crossorigin="anonymous"
></script>

<link
  rel="stylesheet"
  href="https://cdn.example.com/styles@2.0.0/dist/main.css"
  integrity="sha384-HASH_VALUE_HERE"
  crossorigin="anonymous"
>
```

```bash
# Generate SRI hash
openssl dgst -sha384 -binary file.js | openssl base64 -A
# Or: shasum -b -a 384 file.js | awk '{ print $1 }' | xxd -r -p | base64
```

Rules:
- SRI on ALL CDN-loaded scripts and stylesheets
- Pin exact version in URL (never `/latest/`)
- Self-host critical libraries
- Regenerate hashes when upgrading versions

## .npmrc Hardening

```ini
# .npmrc (project root)
engine-strict=true
ignore-scripts=true
audit=true
fund=false
save-exact=true
```

| Setting | Purpose |
|---------|---------|
| `engine-strict=true` | Fail if Node version doesn't match |
| `ignore-scripts=true` | Block postinstall hooks by default |
| `audit=true` | Run audit on every install |
| `save-exact=true` | Pin exact versions (no ^ or ~) |

## Registry Security

```bash
# npm Granular Access Tokens (2025+) — minimal scope:
npm token create --read-only --cidr=CIDR_RANGE

# 2FA on npm account
npm profile enable-2fa auth-and-writes

# Trusted publishing (GitHub Actions OIDC) — no static tokens,
# short-lived token per publish
```

## Private Registry / Proxy

```ini
# .npmrc — Verdaccio, Artifactory, etc.
registry=https://npm.internal.company.com/
@company:registry=https://npm.internal.company.com/
```

Benefits: cache survives registry outages; scan before reaching developers; block typosquat/malicious packages; audit who installed what.

## Emergency Response

```bash
# 1. Check if you have the bad version
npm ls <package-name>

# 2. Check lockfile for specific version
grep '"<package-name>"' package-lock.json

# 3. Force safe version
npm install <package-name>@SAFE_VERSION

# 4. If postinstall ran: check persistence (cron, new files, modified configs, new processes)
crontab -l
find /tmp -newer package-lock.json -type f
ps aux | grep -i node

# 5. Rotate all secrets/tokens on the affected system
```

## Dependency Tree Visualization

```bash
npm ls --all                     # full tree
npm ls --prod                    # production deps only
npm explain <package-name>       # why installed
npm dedupe --dry-run             # find duplicates
```
