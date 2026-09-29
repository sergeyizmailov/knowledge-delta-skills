# HTTP Security Headers & CSP

## Baseline (apply to most sites)

```
Strict-Transport-Security: max-age=63072000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'; upgrade-insecure-requests
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Cross-Origin-Opener-Policy: same-origin
```

### Opt-in: Cross-Origin Isolation (only when you need `SharedArrayBuffer` / high-resolution timers)

Breaks CDN scripts, embedded analytics, fonts, iframes that don't serve
`Cross-Origin-Resource-Policy` / `Cross-Origin-Embedder-Policy: credentialless`:

```
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin
```

### Opt-in: HSTS `preload`

`preload` bakes the domain into browsers — effectively irreversible (removal takes months, ships in next major browser releases). Add ONLY after:
1. All subdomains serve HTTPS
2. `max-age` ≥ 1 year live for 1+ months without rollback
3. Commitment to HTTPS-only on apex + all subdomains long-term

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

Submit at https://hstspreload.org after verifying the above.

## Header Reference

| Header | Purpose | Value |
|--------|---------|-------|
| `Strict-Transport-Security` | Force HTTPS, prevent downgrade | `max-age=63072000; includeSubDomains` (+ `; preload` only after opt-in checklist) |
| `Content-Security-Policy` | Control resource loading | See CSP section below |
| `X-Content-Type-Options` | Prevent MIME sniffing | `nosniff` |
| `X-Frame-Options` | Anti-clickjacking | `DENY` or `SAMEORIGIN` |
| `Referrer-Policy` | Control URL leaking | `strict-origin-when-cross-origin` or `no-referrer` |
| `Permissions-Policy` | Disable browser features | `camera=(), microphone=(), geolocation=()` |
| `Cross-Origin-Opener-Policy` | Isolate browsing context | `same-origin` |
| `Cross-Origin-Embedder-Policy` | Require CORP for subresources | `require-corp` |
| `Cross-Origin-Resource-Policy` | Prevent cross-origin reads | `same-origin` |

### Headers to Remove

```
Server: (remove or set generic)
X-Powered-By: (remove completely)
X-AspNet-Version: (remove)
X-AspNetMvc-Version: (remove)
```

## CSP Directives Reference

| Directive | Controls | Common Values |
|-----------|----------|---------------|
| `default-src` | Fallback for all | `'self'` |
| `script-src` | JavaScript | `'self'`, `'nonce-xxx'`, `'strict-dynamic'` |
| `style-src` | CSS | `'self'`, `'unsafe-inline'` (often needed) |
| `img-src` | Images | `'self'`, `data:`, `https:` |
| `font-src` | Fonts | `'self'`, specific CDN |
| `connect-src` | XHR/Fetch/WS | `'self'`, API domains |
| `frame-src` | iframes | `'none'` or specific |
| `frame-ancestors` | Who can frame you | `'none'` (= X-Frame-Options: DENY) |
| `base-uri` | `<base>` tag | `'self'` |
| `form-action` | Form targets | `'self'` |
| `object-src` | Plugins (Flash) | `'none'` |
| `media-src` | Audio/video | `'self'` |
| `worker-src` | Web workers | `'self'` |
| `manifest-src` | Web manifest | `'self'` |
| `upgrade-insecure-requests` | HTTP→HTTPS auto | (no value) |

## CSP with Nonces (recommended for inline scripts/styles)

Goal: zero `'unsafe-inline'` in `script-src` AND `style-src` — mixing it into a
strict policy gives XSS full execution rights (policy theater). Third-party CSS
framework needs inline styles → prefer nonces/hashes; `'unsafe-inline'` in
`style-src` only as a documented compromise.

```javascript
// Express middleware
const crypto = require('crypto');

app.use((req, res, next) => {
  res.locals.nonce = crypto.randomBytes(16).toString('base64');
  next();
});

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", (req, res) => `'nonce-${res.locals.nonce}'`, "'strict-dynamic'"],
      styleSrc: ["'self'", (req, res) => `'nonce-${res.locals.nonce}'`],
      imgSrc: ["'self'", "data:"],
      connectSrc: ["'self'"],
      fontSrc: ["'self'"],
      objectSrc: ["'none'"],
      frameAncestors: ["'none'"],
      baseUri: ["'self'"],
      formAction: ["'self'"]
    }
  }
}));
```

```html
<script nonce="{{nonce}}">
  // inline script allowed by nonce
</script>
```

## CSP strict-dynamic (modern approach)

```
Content-Security-Policy: script-src 'nonce-RANDOM' 'strict-dynamic'; object-src 'none'; base-uri 'self'
```

`strict-dynamic` = scripts loaded by nonce-approved scripts are auto-trusted. No CDN domain whitelisting. Works with bundlers and dynamic imports.

## CSP for Common Scenarios

### Static site (no inline JS)
```
default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

### Site with Google Fonts + Analytics
```
default-src 'self'; script-src 'self' 'nonce-RANDOM' https://www.googletagmanager.com; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https://www.google-analytics.com; connect-src 'self' https://www.google-analytics.com; frame-ancestors 'none'
```

### SPA with API backend
Prefer nonces for unavoidable inline styles; `'unsafe-inline'` in `style-src` is a documented compromise — remove when the framework allows nonces/hashes:
```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://api.example.com wss://api.example.com; font-src 'self'; frame-ancestors 'none'; base-uri 'self'
```

### Admin panel (strict)
```
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

## CSP Deployment Strategy

1. Start with `Content-Security-Policy-Report-Only`
2. Monitor violations (console / reporting endpoint)
3. Fix violations (inline scripts → files, add nonces)
4. Switch to enforcing `Content-Security-Policy`
5. Add `report-uri` for ongoing monitoring

## Cookie Flags

```javascript
res.cookie('session', token, {
  httpOnly: true,    // no JS access (prevents XSS theft)
  secure: true,      // HTTPS only
  sameSite: 'lax',   // CSRF protection
  maxAge: 86400000,  // 24h in ms
  path: '/',
  domain: '.example.com'
});
```

| Flag | Purpose | When to Use |
|------|---------|-------------|
| `httpOnly` | Block `document.cookie` access | Always for auth tokens |
| `secure` | HTTPS only | Always in production |
| `sameSite=lax` | Block cross-site POST | Default for most cookies |
| `sameSite=strict` | Block all cross-site requests | Sensitive actions |
| `sameSite=none` | Allow cross-site (requires secure) | Cross-domain auth only |
| `__Host-` prefix | Force secure + no domain + path=/ | Strictest option |
| `__Secure-` prefix | Force secure flag | Strong option |

## CORS Configuration

```javascript
const cors = require('cors');

// Production: explicit origins
app.use(cors({
  origin: ['https://app.example.com', 'https://admin.example.com'],
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  maxAge: 86400
}));

// NEVER in production:
// app.use(cors()); // allows all origins
// Access-Control-Allow-Origin: *  // with credentials = browser error anyway
```

Rules:
- Exact origins, never `*`
- Only needed methods/headers
- `maxAge` caches preflight
- `credentials: true` only if needed

## Nginx Security Headers

```nginx
server {
    # HSTS without preload by default (see "Opt-in: HSTS preload" first)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
    add_header Cross-Origin-Opener-Policy "same-origin" always;
    # CORP/COEP are opt-in — see header file
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;

    # Hide server info
    server_tokens off;
    more_clear_headers Server;
    more_clear_headers X-Powered-By;

    # SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;

    # Deny hidden files
    location ~ /\. { deny all; }
}
```

## Caddy Security Headers

```
(security_headers) {
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()"
        Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        -Server
        -X-Powered-By
    }
}

example.com {
    import security_headers
    reverse_proxy localhost:3000
}
```

## Cloudflare Workers Headers

```javascript
function addSecurityHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set('Strict-Transport-Security', 'max-age=63072000; includeSubDomains');
  headers.set('X-Content-Type-Options', 'nosniff');
  headers.set('X-Frame-Options', 'DENY');
  headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  headers.delete('Server');
  headers.delete('X-Powered-By');
  return new Response(response.body, { ...response, headers });
}
```

## Verification

```bash
curl -I https://example.com

# Online scanners:
# securityheaders.com — grades A to F
# observatory.mozilla.org — comprehensive scan
# csp-evaluator.withgoogle.com — CSP analysis
```
