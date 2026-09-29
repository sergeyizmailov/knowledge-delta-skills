# Database: SQL Safety & Race Conditions (TOCTOU)

Related: `express.md` · `auth.md`.

## SQL / Database

```javascript
// Parameterized queries (any driver)
db.query('SELECT * FROM users WHERE email = $1', [email]);

// Prisma (safe by default)
const user = await prisma.user.findUnique({ where: { email } });

// Drizzle (safe by default)
const user = await db.select().from(users).where(eq(users.email, email));
```

Never concatenate user input into SQL strings. ORM methods above are
parameterized by design; raw `$queryRaw` / `db.execute(string)` is not.

## Race Conditions / TOCTOU

Node is single-threaded but not single-tasked — every `await` is a yield point where other requests execute. Check-then-act windows let concurrent requests exploit stale state.

### The classic double-spend

```javascript
// VULNERABLE: read balance, check, then update — gap between read and write
app.post('/transfer', async (req, res) => {
  const { amount, to } = req.body;
  const user = await db.query('SELECT balance FROM accounts WHERE id = $1', [req.userId]);

  // --- TOCTOU window: 10 concurrent requests all read the same balance ---

  if (user.balance >= amount) {
    await db.query('UPDATE accounts SET balance = balance - $1 WHERE id = $2', [amount, req.userId]);
    await db.query('UPDATE accounts SET balance = balance + $1 WHERE id = $2', [amount, to]);
  }
});
// Attack: 10 concurrent requests with full balance → negative balance
```

### Fix 1: Atomic SQL (best for simple cases)

```javascript
app.post('/transfer', async (req, res) => {
  const { amount, to } = req.body;

  const result = await db.query(
    'UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND balance >= $1 RETURNING balance',
    [amount, req.userId]
  );

  if (result.rowCount === 0) {
    return res.status(400).json({ error: 'Insufficient funds' });
  }

  await db.query('UPDATE accounts SET balance = balance + $1 WHERE id = $2', [amount, to]);
  res.json({ success: true });
});
```

### Fix 2: Database transaction with row locking

```javascript
app.post('/transfer', async (req, res) => {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // SELECT FOR UPDATE locks the row until COMMIT
    const { rows } = await client.query(
      'SELECT balance FROM accounts WHERE id = $1 FOR UPDATE',
      [req.userId]
    );

    if (rows[0].balance < req.body.amount) {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: 'Insufficient funds' });
    }

    await client.query('UPDATE accounts SET balance = balance - $1 WHERE id = $2', [req.body.amount, req.userId]);
    await client.query('UPDATE accounts SET balance = balance + $1 WHERE id = $2', [req.body.amount, req.body.to]);
    await client.query('COMMIT');
    res.json({ success: true });
  } catch (e) {
    await client.query('ROLLBACK');
    res.status(500).json({ error: 'Transaction failed' });
  } finally {
    client.release();
  }
});
```

### Fix 3: Distributed lock (multi-process / Kubernetes)

```javascript
app.post('/transfer', async (req, res) => {
  const idempotencyKey = req.headers['x-idempotency-key'];
  if (!idempotencyKey) return res.status(400).json({ error: 'Missing idempotency key' });

  const lockKey = `lock:transfer:${req.userId}`;
  const locked = await redis.set(lockKey, '1', 'NX', 'EX', 10);

  if (!locked) {
    return res.status(409).json({ error: 'Concurrent request in progress' });
  }

  try {
    const existing = await redis.get(`idem:${idempotencyKey}`);
    if (existing) return res.json(JSON.parse(existing));

    // ... perform transfer ...

    await redis.set(`idem:${idempotencyKey}`, JSON.stringify(result), 'EX', 3600);
    res.json(result);
  } finally {
    await redis.del(lockKey);
  }
});
```

### Pentest checklist

- N identical requests simultaneously (`curl --parallel`, Turbo Intruder, race-the-web)
- Targets: balance transfers, coupon redemption, vote/like endpoints, account creation
- Any read-then-write pattern in state-changing endpoints
- Same idempotency key and different keys
- DELETE + CREATE sequences raced
