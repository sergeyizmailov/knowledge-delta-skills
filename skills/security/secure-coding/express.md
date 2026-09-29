# Express Hardening & Production Misconfigurations

Related: `auth.md` (sessions, JWT, password, access control) · `db.md`
(SQL, race conditions) · `uploads.md` · `ssrf.md` · `dos.md` (ReDoS, WS) ·
`graphql.md` · `llm.md` · `headers-and-csp.md`.

## Express Hardening

```javascript
const express = require('express');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const cors = require('cors');

const app = express();

// CSP: no 'unsafe-inline' for script-src or style-src. Framework forces inline
// styles → prefer nonces (see headers-and-csp.md); 'unsafe-inline' in style-src
// only as a documented compromise. COEP/CORP are opt-in (cross-origin isolation,
// break most CDN/embeds). HSTS preload is irreversible — see headers-and-csp.md.
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'"],
      styleSrc: ["'self'"],
      imgSrc: ["'self'", "data:"],
      connectSrc: ["'self'"],
      fontSrc: ["'self'"],
      objectSrc: ["'none'"],
      frameAncestors: ["'none'"],
      baseUri: ["'self'"],
      formAction: ["'self'"],
      upgradeInsecureRequests: []
    }
  },
  crossOriginEmbedderPolicy: false,
  crossOriginOpenerPolicy: { policy: "same-origin" },
  crossOriginResourcePolicy: { policy: "same-origin" },
  hsts: { maxAge: 63072000, includeSubDomains: true, preload: false }
}));

app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || [],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.disable('x-powered-by');

// trust proxy must match actual topology, NOT a default `1` — wrong value →
// IP spoofing via X-Forwarded-For (rate limit + audit log bypass):
//   Direct exposure (Node on public IP):                   app.set('trust proxy', false)
//   One reverse proxy on same host (Nginx → 127.0.0.1):    app.set('trust proxy', 'loopback')
//   Nginx → Node, both you control:                        app.set('trust proxy', 1)
//   Cloudflare → Nginx → Node:                             app.set('trust proxy', 2)
//   Specific proxy CIDR you control:                       app.set('trust proxy', '10.0.0.0/8')
app.set('trust proxy', 'loopback');

app.use(express.json({ limit: '10kb' }));
app.use(express.urlencoded({ extended: false, limit: '10kb' }));

// index: false disables directory index serving for the static dir; remove it
// (or use index: 'index.html') if public/ is the SPA root serving `/`
app.use(express.static('public', {
  dotfiles: 'deny',
  index: false
}));
```

## Rate Limiting

```javascript
const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests' }
});

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 5,
  skipSuccessfulRequests: true,
  message: { error: 'Too many attempts' }
});

app.use(globalLimiter);
app.post('/login', authLimiter, loginHandler);
app.post('/register', authLimiter, registerHandler);
app.post('/reset-password', authLimiter, resetHandler);
```

Multi-instance production: `rate-limit-redis` store.

## Input Validation (Zod)

```javascript
const { z } = require('zod');

const loginSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(8).max(128)
});

const idParam = z.object({
  id: z.string().uuid()
});

function validate(schema) {
  return (req, res, next) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      return res.status(400).json({ error: 'Invalid input' });
    }
    req.validated = result.data;
    next();
  };
}

app.post('/login', validate(loginSchema), loginHandler);
```

Rules:
- Validate ALL input (body, params, query, headers)
- Whitelist allowed fields, reject unknown
- Max lengths on all strings
- `.strip()` / `.strict()` to remove extra fields
- Never pass raw `req.body` to database

## Error Handling

```javascript
app.use((err, req, res, next) => {
  const statusCode = err.statusCode || 500;

  if (statusCode >= 500) {
    console.error({
      message: err.message,
      stack: err.stack,
      url: req.originalUrl,
      method: req.method,
      ip: req.ip
    });
  }

  res.status(statusCode).json({
    error: statusCode >= 500 ? 'Internal server error' : err.message
  });
});

function asyncHandler(fn) {
  return (req, res, next) => fn(req, res, next).catch(next);
}

app.get('/users/:id', asyncHandler(async (req, res) => {
  const user = await getUser(req.params.id);
  if (!user) return res.status(404).json({ error: 'Not found' });
  res.json(user);
}));
```

Rules:
- Never expose stack traces, internal paths, DB errors, query details
- Log errors with context (URL, method, IP, timestamp); never log passwords, tokens, session data
- Generic messages for 5xx, specific for 4xx
- Always handle promise rejections

## Production Misconfigurations

### Files that should never be accessible

| Path | Risk | Check |
|------|------|-------|
| `/.env` | Credentials, API keys, DB connection strings | `curl -s https://target/.env` |
| `/.git/HEAD` | Full source code reconstruction | `curl -s https://target/.git/HEAD` |
| `/.git/config` | Remote repo URLs, potentially creds | Part of .git enumeration |
| `/package.json` | Dependency versions, scripts, internal paths | `curl -s https://target/package.json` |
| `/*.js.map` | Full original source code | `curl -s https://target/app.js.map` |
| `/node_modules/` | Dependency code, version fingerprinting | Directory listing check |
| `/.npmrc` | npm tokens | `curl -s https://target/.npmrc` |
| `/docker-compose.yml` | Infrastructure layout, ports, secrets | `curl -s https://target/docker-compose.yml` |
| `/.vscode/`, `/.idea/` | IDE configs, local paths | Directory listing |

### Nginx block for sensitive paths

```nginx
location ~ /\. {
    deny all;
    return 404;
}

location ~* \.(env|git|npmrc|dockerignore|editorconfig)$ {
    deny all;
    return 404;
}

location ~* \.map$ {
    deny all;
    return 404;
}

location = /package.json { deny all; return 404; }
location = /package-lock.json { deny all; return 404; }
location = /tsconfig.json { deny all; return 404; }
location = /docker-compose.yml { deny all; return 404; }
location /node_modules/ { deny all; return 404; }
```

### NODE_ENV in production

```javascript
if (process.env.NODE_ENV !== 'production') {
  console.error('WARNING: Not running in production mode');
}
```

`NODE_ENV=development` in production: verbose error stacks to clients, template
caching disabled, some packages enable debug logging, GraphQL introspection may be on.

### Source maps

```javascript
// webpack.config.js — PRODUCTION
module.exports = {
  mode: 'production',
  devtool: false // NO source maps in production
};
// Need error tracking: 'hidden-source-map' (no //# sourceMappingURL) —
// but .map files still exist on disk, block via Nginx
```

### Open database ports

| Port | Service | Default Auth |
|------|---------|-------------|
| 27017 | MongoDB | None |
| 6379 | Redis | None |
| 5432 | PostgreSQL | Password |
| 3306 | MySQL | Password |
| 9200 | Elasticsearch | None |
| 5984 | CouchDB | Admin party |

MongoDB without auth and Redis on `0.0.0.0` still among most common bug bounty findings.

### Debug endpoints left in production

```javascript
// REMOVE before deploy:
app.get('/debug/routes', ...);
app.get('/debug/env', ...);
app.get('/health/detailed', ...);   // if it exposes internals
app.get('/api/test', ...);
app.get('/admin', ...);              // without auth middleware

// Stack dump — leaks all routes
app.get('/debug', (req, res) => {
  res.json(app._router.stack);
});
```

### Pentest checklist for misconfigs

- `curl -s https://target/.env`
- `curl -s https://target/.git/HEAD`
- `curl -s https://target/package.json`
- `curl -s https://target/main.js.map` (and other common bundle names)
- `nmap -p 27017,6379,5432,3306,9200 target`
- Check `X-Powered-By`, `Server` headers
- Check verbose error pages (send invalid JSON, bad routes)
- Check GraphQL playground / introspection
- Check Swagger/OpenAPI docs at `/docs`, `/api-docs`, `/swagger`
