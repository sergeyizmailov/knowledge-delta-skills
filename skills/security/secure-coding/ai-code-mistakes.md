# AI-Generated Code: Security Mistakes & Patterns

## The Problem (2025-2026 Data)

| Metric | Value | Source |
|--------|-------|--------|
| AI code vulnerability rate vs human | 2.74x higher | Veracode (100+ LLMs) |
| AI samples with OWASP Top 10 vulns | 45% | Veracode |
| XSS defense failure rate | 86% | Veracode |
| Log injection failure rate | 88% | Veracode |
| Privilege escalation paths | 322% more | Apiiro (Fortune 50) |
| Design flaws | 153% more | Apiiro |
| Secrets exposure jump | 40% more | Apiiro |
| AI-assisted commit secret leak rate | 3.2% (vs 1.5% baseline) | GitGuardian 2026 |
| New hardcoded secrets in GitHub (2025) | 28.65 million | GitGuardian |
| CVEs from AI code (Mar 2026) | 35 confirmed / est. 400-700 | Georgia Tech |
| Vibe-coded apps with critical vulns | 58% | Escape.tech (1,400 apps) |

## Top CWE Patterns AI Gets Wrong

### 1. CWE-79: Cross-Site Scripting (86% failure rate)

```javascript
// VULNERABLE
app.get('/search', (req, res) => {
  res.send(`<h1>Results for: ${req.query.q}</h1>`);
});
element.innerHTML = `<div class="user">${userData.name}</div>`;

// SAFE
app.get('/search', (req, res) => {
  const escaped = req.query.q.replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  res.send(`<h1>Results for: ${escaped}</h1>`);
});
element.textContent = userData.name;
```

### 2. CWE-89: SQL Injection

```javascript
// VULNERABLE — string interpolation, and manual quote "sanitization" too:
db.query(`SELECT * FROM users WHERE email = '${email}'`);
const safe = email.replace(/'/g, "''");

// SAFE
const user = await db.query('SELECT * FROM users WHERE email = $1', [email]);
```

### 3. CWE-798: Hardcoded Credentials

```javascript
// VULNERABLE
const API_KEY = 'sk-proj-abc123def456';
const DB_URL = 'postgres://admin:password123@db.example.com:5432/prod';
const JWT_SECRET = 'super-secret-key-change-in-production';

// SAFE
const API_KEY = process.env.API_KEY;
const DB_URL = process.env.DATABASE_URL;
const JWT_SECRET = process.env.JWT_SECRET;
```

### 4. CWE-327: Cryptographic Failures

```javascript
// VULNERABLE — MD5 or unsalted SHA256 for passwords; weak JWT secret
crypto.createHash('md5').update(password).digest('hex');
crypto.createHash('sha256').update(password).digest('hex');
jwt.sign(payload, 'secret', { algorithm: 'HS256' });

// SAFE
const hash = await argon2.hash(password, { type: argon2.argon2id });

const token = await new SignJWT(payload)
  .setProtectedHeader({ alg: 'RS256' })
  .sign(privateKey);
```

### 5. CWE-117: Log Injection (88% failure rate)

```javascript
// VULNERABLE — username = "admin\nLogin successful for user: admin" fakes log
console.log(`Login attempt for user: ${username}`);

// SAFE
const safeUsername = username.replace(/[\n\r\t]/g, '_');
logger.info({ event: 'login_attempt', user: safeUsername });
```

### 6. CWE-22: Path Traversal

```javascript
// VULNERABLE — GET /files/../../../etc/passwd
res.sendFile(path.join(__dirname, 'uploads', req.params.name));

// SAFE
const safeName = path.basename(req.params.name);
const fullPath = path.join(__dirname, 'uploads', safeName);
if (!fullPath.startsWith(path.join(__dirname, 'uploads'))) {
  return res.status(400).json({ error: 'Invalid path' });
}
res.sendFile(fullPath);
```

### 7. CWE-862: Missing Authorization

```javascript
// VULNERABLE — no auth check
app.delete('/api/users/:id', async (req, res) => {
  await db.query('DELETE FROM users WHERE id = $1', [req.params.id]);
});

// SAFE
app.delete('/api/users/:id', requireAuth, requireRole('admin'), async (req, res) => {
  await db.query('DELETE FROM users WHERE id = $1', [req.params.id]);
});
```

## Patterns AI Consistently Gets Wrong

- **Input validation**: AI trusts `req.body` and passes it straight to DB. Always add Zod/Joi validation.
- **Rate limiting**: never added to auth endpoints — login/register/reset need strict limits (5 attempts / 15 min).
- **Error handling**: `catch (err) { res.status(500).json({ error: err.message }); }` leaks info ("relation 'users' does not exist" → Postgres fingerprint).
- **Insecure defaults**: `cors()` no options = all origins; `express.json()` no `limit` = payload DoS; `trust proxy true` = IP spoofing; session cookies without `secure`/`httpOnly`.
- **Outdated libraries**:
  - `request` (deprecated 2020) → `node-fetch` or `undici`
  - `jsonwebtoken` → `jose`
  - `bcryptjs` → `argon2`
  - `body-parser` → `express.json()` (built-in since Express 4.16)
  - `csurf` (deprecated) → `csrf-csrf`
  - `express-validator` v4 → v7 or `zod`

## AI Code Review Checklist

Before accepting ANY AI-generated code, verify:

- [ ] No hardcoded secrets, API keys, tokens, passwords
- [ ] No `eval()`, `new Function()`, `setTimeout(string)`
- [ ] No `innerHTML` with user data (use `textContent` or DOMPurify)
- [ ] No string concatenation in SQL/DB queries
- [ ] No `res.send(error.message)` or `res.send(error.stack)`
- [ ] All endpoints have auth middleware
- [ ] All user input validated (Zod/Joi, not manual checks)
- [ ] Rate limiting on auth endpoints
- [ ] `express.json({ limit: '10kb' })`
- [ ] `cors()` has explicit `origin` list
- [ ] Cookies have `httpOnly`, `secure`, `sameSite`
- [ ] JWT verification specifies `algorithms` array
- [ ] File paths use `path.basename()` or validated against root
- [ ] URLs validated before `fetch()` (no SSRF)
- [ ] Dependencies pinned to exact versions
- [ ] No deprecated packages

## OpenSSF Guidance (Sep 2025)

1. Write security requirements in prompts ("parameterized queries", "validate all input", "no hardcoded secrets")
2. Don't tell AI it's a security expert — causes overconfidence, skipping basics
3. Use Recursive Criticism and Improvement (RCI) — AI reviews its own code, repeat
4. Treat AI output as untrusted junior developer code
5. Automated scanning before merge: `npm audit`, Semgrep, CodeQL
6. Pin dependencies explicitly — AI suggests `^` versions by default

## Real Incidents (2025-2026)

- **Moltbook breach**: fully AI-generated app; exposed prod DB in 3 days — 1.5M API tokens, 35K emails, private messages
- **Copilot prompt injection** (CVE-2025-53773, CVSS 9.6): hidden prompt in PR description → arbitrary code execution during review
- **CamoLeak** (CVE-2025-59145, CVSS 9.6): prompt injection extracts API keys and private source from Copilot context
