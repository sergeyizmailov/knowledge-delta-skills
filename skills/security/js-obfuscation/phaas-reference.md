# PhaaS Kits: Techniques Reference (2025-2026)

| Kit | Key techniques |
|-----|---------------|
| Tycoon2FA | Invisible Unicode encoding, Proxy get-trap execution, custom canvas CAPTCHA (replaced Turnstile), AES+LZString compression, multi-layer nesting |
| Sneaky2FA | BitB integration, anti-DevTools (debugger+timing+size), keyboard blocking, long random URL paths (150+ chars) |
| Astaroth | Real-time AiTM proxy, reCAPTCHA/BotGuard bypass, encrypted payloads |
| GhostFrame | Blob URI iframes, cross-origin with dynamic subdomain validation, postMessage parent manipulation |
| Salty2FA | XOR with static key + Base64, session-based rotating subdomains from pre-computed pools, IP/ASN filtering, HTML filler noise |
| Mamba 2FA | Socket.IO real-time exfil, Turnstile, auto corporate branding from victim email domain |
| FlowerStorm | FingerprintJS before content, multi-hop redirect chains, Cloudflare Workers hosting |
| SessionShark | High-fidelity MS365 mimicry, custom HTTP headers for feed evasion, dynamic content per viewer |
| Rockstar 2FA | Near-zero font-size hidden words between visible text, HTML structural obfuscation |
| Greatness | AES with PBKDF2 key derivation via CryptoJS, encrypted config/payload/exfil |
| GlassWorm | Variation Selectors (U+FE00-FE0F) for encoding, Solana transaction memos for C2 |

## Payload Encoding
- **Invisible Unicode** (Tycoon2FA): Hangul fillers U+FFA0/U+3164 as binary 0/1, decoded via Proxy get-trap
- **Variation Selectors** (GlassWorm): U+FE00-FE0F as nibbles, 50% smaller than Hangul
- **XOR + Base64** (Salty2FA): Static key `684c985a29c67596b5e66d6028bdad6d`, runtime decryption
- **AES + PBKDF2** (Greatness): CryptoJS `__g()` function, derived key
- **AES + LZString** (Tycoon2FA): Compression under encryption, multi-layer nesting

## Anti-Analysis
- **Anti-DevTools** (Sneaky2FA): debugger trap + timing + window size + keyboard blocking
- **Infinite debugger** (JScrambler-style): `Function.constructor('debugger')` — resists regex removal
- **HTML filler noise** (Salty2FA): Random quotes as HTML comments between code
- **Near-zero font-size** (Rockstar 2FA): Invisible words between visible text break keyword matching
- **WOFF font cipher**: Custom font remaps glyphs, source text is garbled

## Bot Detection
- **Turnstile gate** (Mamba, Salty2FA, Sneaky2FA, FlowerStorm): CAPTCHA before any content
- **Custom canvas CAPTCHA** (Tycoon2FA): Replaced Turnstile to avoid Cloudflare dependency
- **FingerprintJS** (FlowerStorm): Canvas, WebGL, AudioContext before content loads
- **IP/ASN filtering** (Salty2FA, CoGUI): Block security vendors, cloud providers
- **navigator.webdriver** (Tycoon2FA, EvilProxy, CoGUI): Redirect bots to legit site

## Infrastructure
- **Rotating subdomains** (Salty2FA): Pre-computed dictionary pools, session-triggered assignment
- **Dynamic subdomains** (GhostFrame): Random per-visit, cross-origin iframe validation
- **Cloudflare Workers** (Tycoon2FA, FlowerStorm): workers.dev reputation, serverless
- **Multi-hop redirects** (FlowerStorm): Open redirect abuse on legit sites (Indeed, Upwork)
- **Long random URL paths** (Sneaky2FA): 150+ chars, defeats pattern-based blocklisting

## Visual Deception
- **BitB popups** (Sneaky2FA): Fake browser window with OS-adaptive themes
- **Auto corporate branding** (Mamba): Logo/colors from victim's email domain
- **Blob URI rendering** (GhostFrame): Screenshot as blob image, invisible overlaid inputs
- **postMessage manipulation** (GhostFrame): Parent title/favicon changes from iframe

## Exfiltration
- **Socket.IO** (Mamba): Real-time bidirectional, lower latency than HTTP
- **AJAX/Fetch** (Whisper 2FA, Cephas): Lightweight, no reverse proxy needed
- **Telegram bots** (SessionShark, Astaroth, Mamba, Salty2FA, Greatness): Instant delivery
- **Blockchain C2** (GlassWorm): Solana transaction memos, Google Calendar backup

## Multi-Layer Nesting (Tycoon2FA, ~90% of samples)
`Invisible Unicode → Base64 → Encryption (XOR / AES-256-CBC / CryptoJS)`, optional gzip to normalize size anomalies.

## Stats (2025-2026)
- 48% of high-volume campaigns: URL obfuscation, MFA bypass, or CAPTCHA abuse
- 90% of high-volume phishing uses commercial PhaaS kits
- 36% of malicious pages use runtime assembly (polymorphic/LLM)
- 20% generate unique code per deployment
- 19% use QR codes to bypass URL scanners
- Known PhaaS kits doubled in volume during 2025
