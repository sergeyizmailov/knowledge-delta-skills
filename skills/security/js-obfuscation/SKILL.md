---
name: js-obfuscation
description: Use when obfuscating JavaScript, building anti-detection layers, evading Google Safe Browsing, hiding payloads from scanners, adding anti-bot/anti-DevTools protection, or preparing phishing/red-team pages for deployment
---

# JS Obfuscation & Anti-Detection

## Architecture: Defense-in-Depth Layers

```
Request arrives
  ├─ L1: Server-side cloaking (IP/ASN/GeoIP) → anti-bot.md
  │   ├─ L2: CAPTCHA gate (Turnstile) → anti-bot.md
  │   │   ├─ L3: JS anti-bot (webdriver, fingerprint, behavior) → anti-bot.md
  │   │   │   ├─ L4: Encrypted payload (AES/XOR/Unicode) → encryption.md
  │   │   │   │   └─ L5: Obfuscated JS (javascript-obfuscator) → obfuscator-configs.md
  │   │   │   └─ L6: One-time URLs (single use, then 404)
  │   │   └─ Anti-DevTools → anti-devtools.md
```

Without L1 everything else just delays detection. With L1, site can live weeks.

## Quick Decision Guide

| Scenario | Layers |
|----------|----------------|
| Quick red team page | L5 (balanced) + anti-DevTools |
| Production phishing with longevity | All 6 |
| Landing page (BitB popup) | L3 + L5 + anti-DevTools |
| Cloudflare Worker | L1 (ASN via CF) + L4 + L5 |
| Email attachment HTML | L4 (AES, key in URL fragment) + L5 (max) + anti-DevTools |

## Evasion Checklist (Safe Browsing / VirusTotal / PhishTank / CF WAF)

1. Server-side IP/ASN/GeoIP filter — crawlers never see payload
2. CAPTCHA gate (Turnstile) — scanners can't solve; CF sees "protected site"
3. JS anti-bot — headless/sandbox detected and redirected
4. Encrypted payload, RC4/AES — never raw base64, `atob()` is a detection signature
5. Obfuscated JS — no `eval(atob(`, `password`, known-kit signatures in source
6. `domainLock` — code breaks on wrong domain (VirusTotal, sandboxes)
7. One-time URLs — reported link is already 404
8. Domain rotation — flagged → reserve; aged domains (.com, 2+ years) flagged slower
9. Delayed execution — `setTimeout` 3–5s; scanner budgets are short
10. Interaction-gated — real click/scroll required before payload
11. Polymorphic mutation — same code for every visitor → signatures
12. Email whitelist (Cephas pattern) — serve only if email matches target list
13. Legit hosting (`.workers.dev`, `.pages.dev`, `.netlify.app`) = high reputation; Workers/Pages get less scrutiny

Does NOT work: client-side blocking of `safebrowsing.googleapis.com` — checks happen at browser level before page JS.

## What to Obfuscate

**Yes:** tracking scripts, form handlers, exfil logic, CF Worker code, custom frontend JS.
**No:** server-side code, Nginx/HAProxy configs, CSS, HTML structure, proxied content, Docker internals.

## One-Time URLs

```python
active = {}

@app.route('/<token>')
def land(token):
    if token in active:
        del active[token]
        return render_page()
    return '', 404
```

## Common Mistakes

1. Obfuscation without server-side filtering
2. `base64` instead of RC4/AES — `atob()` is a signature
3. Hardcoded URLs in source — construct dynamically or decrypt at runtime
4. No `domainLock` — code runs on VirusTotal → flagged
5. `renameGlobals: true` without testing — breaks external scripts
6. No mouse check — sandboxes bypass webdriver but don't move mouse
7. Static CAPTCHA — if cached forever, scanner reuses session
8. Same code for every visitor — polymorphic mutation prevents signatures

## Reference Files

- `obfuscator-configs.md` — javascript-obfuscator presets (balanced/max/light), CLI, options
- `anti-bot.md` — anti-bot, anti-sandbox, CDP detection, server-side cloaking, Turnstile
- `anti-devtools.md` — 7 methods, disable-devtool npm
- `encryption.md` — AES-256-GCM, XOR, invisible Unicode, DOM cloaking, polymorphic JS
- `phaas-reference.md` — 11 PhaaS kits (2025-2026), techniques, stats
