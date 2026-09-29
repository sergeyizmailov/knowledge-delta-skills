# Authentication, Sessions & Access Control

Related: `express.md` (rate limit auth endpoints) · `db.md` ·
`headers-and-csp.md` (cookie flags).

## Password Hashing (Argon2id)

```javascript
const argon2 = require('argon2');

async function hashPassword(password) {
  return argon2.hash(password, {
    type: argon2.argon2id,
    memoryCost: 19456,
    timeCost: 2,
    parallelism: 1
  });
}

async function verifyPassword(hash, password) {
  return argon2.verify(hash, password);
}
```

Fallback if argon2 native build fails: `bcrypt` with cost 12+.

## JWT (jose library)

```javascript
const { SignJWT, jwtVerify, generateKeyPair } = require('jose');

const { privateKey, publicKey } = await generateKeyPair('RS256');

async function signToken(payload) {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: 'RS256' })
    .setIssuedAt()
    .setExpirationTime('15m')
    .setIssuer(process.env.JWT_ISSUER)
    .setAudience(process.env.JWT_AUDIENCE)
    .sign(privateKey);
}

async function verifyToken(token) {
  const { payload } = await jwtVerify(token, publicKey, {
    issuer: process.env.JWT_ISSUER,
    audience: process.env.JWT_AUDIENCE,
    algorithms: ['RS256']
  });
  return payload;
}
```

Rules:
- Always set `algorithms` whitelist (never allow `none`)
- Short-lived access tokens (15m), longer refresh tokens (7d) in httpOnly cookie
- Rotate keys periodically
- RS256 (asymmetric) over HS256 for microservices

## Session Security

```javascript
const session = require('express-session');
const RedisStore = require('connect-redis').default;

app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET,
  name: '__sid',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: true,
    httpOnly: true,
    sameSite: 'lax',
    maxAge: 24 * 60 * 60 * 1000,
    domain: process.env.COOKIE_DOMAIN
  }
}));

function regenerateSession(req) {
  return new Promise((resolve, reject) => {
    req.session.regenerate(err => err ? reject(err) : resolve());
  });
}

app.post('/login', async (req, res) => {
  // ... verify credentials ...
  await regenerateSession(req); // prevent session fixation
  req.session.userId = user.id;
  res.json({ ok: true });
});
```

## Access Control Patterns

```javascript
function requireAuth(req, res, next) {
  if (!req.session?.userId) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

function requireRole(...roles) {
  return (req, res, next) => {
    if (!roles.includes(req.user?.role)) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
}

async function requireOwnership(req, res, next) {
  const resource = await getResource(req.params.id);
  if (!resource || resource.userId !== req.session.userId) {
    return res.status(404).json({ error: 'Not found' });
  }
  req.resource = resource;
  next();
}
```

Return 404 (not 403) when user shouldn't know resource exists — prevents enumeration.

## Timing-Safe Comparison

```javascript
const { timingSafeEqual } = require('crypto');

function safeCompare(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return timingSafeEqual(bufA, bufB);
}
```

Use for: API keys, webhook signatures, TOTP codes. Not needed for `argon2.verify` / `bcrypt.compare` (built-in).

## JWT Attack Prevention

```javascript
const { payload } = await jwtVerify(token, publicKey, {
  algorithms: ['RS256'],
  issuer: 'your-app',
  audience: 'your-api'
});
```

Attacks:
- `alg: "none"` — signature removed, some libs accept it
- `alg: "HS256"` with RS256 public key — algorithm confusion
- Weak secret brute-force: `hashcat -m 16500 jwt.txt rockyou.txt`
- `kid` injection: `"kid": "../../dev/null"` → empty key → forge any token
- `jku`/`x5u` injection — point to attacker's JWK Set URL
- Expired token replay — server doesn't check `exp`

Defense: `jose` with explicit `algorithms`; verify `iss`, `aud`, `exp`.
