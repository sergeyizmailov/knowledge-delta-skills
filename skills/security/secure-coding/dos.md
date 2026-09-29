# ReDoS & WebSocket Security

Related: `express.md` · `auth.md` (JWT for WS auth).

## ReDoS Prevention

Single-threaded Node: one exponential regex blocks the entire event loop. Real outages: Stack Overflow (34 min), Cloudflare (global WAF).

### Dangerous patterns

| Pattern | Why | Example |
|---------|-----|---------|
| Nested quantifiers `(.+)*`, `(.+)+` | Exponential O(2^n) branching | `/^(.+\.)*localhost$/` |
| Overlapping alternations `(a\|ab)*` | Multiple paths match same substring | `/("[^"]*"\|[^@])*@/` |
| Greedy quantifiers before anchors `.+$` | Quadratic O(n^2) backtracking | `/^[\s\u200c]+\|[\s\u200c]+$/` |

### Vulnerable code AI commonly generates

```javascript
// VULNERABLE: nested quantifier — hangs on 'a.'.repeat(25) + 'X'
const isLocalhost = /^(.+\.)*localhost$/.test(hostname);

// VULNERABLE: email regex with backtracking
const emailRegex = /^([a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})*$/;

// VULNERABLE: whitespace trimming — O(n^2)
const trimmed = input.replace(/^[\s\u200c]+|[\s\u200c]+$/, '');
```

### Safe alternatives

```javascript
// String operations instead of regex
const isLocalhost = host === 'localhost' || host.endsWith('.localhost');

// RE2 — guaranteed linear time, no backtracking
const RE2 = require('re2');
const safePattern = new RE2('^([a-z]+)+$');
safePattern.test(userInput);

// Always limit input length before regex
function safeMatch(input, pattern, maxLen = 1000) {
  if (input.length > maxLen) return null;
  return input.match(pattern);
}
```

### CI integration

```bash
npm install --save-dev eslint-plugin-redos
# or use vuln-regex-detector
npx vuln-regex-detector --dir ./src
```

## WebSocket Security

WebSockets are exempt from Same-Origin Policy: with cookie auth and no Origin check, any site can open a WS and the browser attaches the victim's cookies (CSWSH).

### Secure ws implementation

```javascript
const WebSocket = require('ws');
const wss = new WebSocket.Server({
  port: 8080,
  maxPayload: 64 * 1024,      // 64 KB (default 100 MB — way too large)
  perMessageDeflate: false     // disable compression (zip bomb defense)
});

const ALLOWED_ORIGINS = ['https://app.example.com'];

wss.on('connection', (ws, req) => {
  // 1. Validate origin
  const origin = req.headers.origin;
  if (!ALLOWED_ORIGINS.includes(origin)) {
    ws.close(1008, 'Origin not allowed');
    return;
  }

  // 2. Validate auth token (query string or first message)
  const url = new URL(req.url, `http://${req.headers.host}`);
  const token = url.searchParams.get('token');
  if (!verifyJWT(token)) {
    ws.close(1008, 'Unauthorized');
    return;
  }

  ws.on('message', (data) => handleMessage(data));
});
```

### Rate limiting WebSocket messages

```javascript
const { RateLimiterMemory } = require('rate-limiter-flexible');

const wsLimiter = new RateLimiterMemory({
  points: 20,
  duration: 1
});

wss.on('connection', (ws, req) => {
  const clientIP = req.socket.remoteAddress;

  ws.on('message', async (data) => {
    try {
      await wsLimiter.consume(clientIP);
      handleMessage(data);
    } catch {
      ws.close(1008, 'Rate limited');
    }
  });
});
```

### Socket.IO specific

```javascript
const io = require('socket.io')(server, {
  cors: {
    origin: ['https://app.example.com'],
    credentials: true
  },
  maxHttpBufferSize: 64 * 1024,
  pingTimeout: 20000,
  pingInterval: 25000,
  connectTimeout: 10000
});

io.use((socket, next) => {
  const token = socket.handshake.auth?.token;
  try {
    socket.user = verifyJWT(token);
    next();
  } catch {
    next(new Error('Authentication failed'));
  }
});
```

### Pentest checklist

- Connect from different origin (CSWSH test)
- Send oversized messages (memory DoS)
- Flood messages rapidly (rate limit test)
- Send malformed JSON / unexpected types
- Connect without auth token
- Expired/tampered JWT
- `ws://` (unencrypted) accepted in production?
