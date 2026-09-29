# GraphQL Security

Related: `express.md` (rate limiting baseline) · `auth.md`.

GraphQL threat model: one endpoint, many shapes — rate limiting by request count alone is insufficient.

## Disable introspection in production

```javascript
// Apollo Server
const server = new ApolloServer({
  schema,
  introspection: process.env.NODE_ENV !== 'production',
  plugins: [
    process.env.NODE_ENV === 'production'
      ? ApolloServerPluginLandingPageDisabled()
      : ApolloServerPluginLandingPageLocalDefault()
  ]
});
```

```javascript
// express-graphql
const { NoIntrospection } = require('graphql');

app.use('/graphql', graphqlHTTP({
  schema: mySchema,
  validationRules: [NoIntrospection],
  graphiql: false
}));
```

## Query depth limiting

```javascript
const depthLimit = require('graphql-depth-limit');

app.use('/graphql', graphqlHTTP({
  schema: mySchema,
  validationRules: [depthLimit(5)]
}));
```

## Query complexity / cost analysis

```javascript
const { createComplexityLimitRule } = require('graphql-validation-complexity');

app.use('/graphql', graphqlHTTP({
  schema: mySchema,
  validationRules: [
    depthLimit(5),
    createComplexityLimitRule(1000, {
      scalarCost: 1,
      objectCost: 10,
      listFactor: 20
    })
  ]
}));
```

## Batching attack prevention

Batching = hundreds of queries in one HTTP request, bypassing per-request rate limits (OTP/password brute-force, enumeration).

```javascript
// Limit batch size
app.use('/graphql', (req, res, next) => {
  if (Array.isArray(req.body) && req.body.length > 5) {
    return res.status(400).json({ error: 'Batch limit exceeded' });
  }
  next();
});

// Apollo Server — disable batching entirely
const server = new ApolloServer({
  schema,
  allowBatchedHttpRequests: false
});
```

## Field-level authorization

```javascript
// WRONG: auth only on query resolver — any authenticated user sees any user's email/SSN
const resolvers = {
  Query: {
    user: (_, { id }, ctx) => {
      requireAuth(ctx);
      return db.users.findById(id);
    }
  },
  User: {
    email: (parent) => parent.email,
    ssn: (parent) => parent.ssn
  }
};

// CORRECT: auth on sensitive fields
const resolvers = {
  Query: {
    user: (_, { id }, ctx) => {
      requireAuth(ctx);
      return db.users.findById(id);
    }
  },
  User: {
    email: (parent, _, ctx) => {
      if (ctx.user.id !== parent.id && !ctx.user.isAdmin) {
        throw new ForbiddenError('Not authorized');
      }
      return parent.email;
    },
    ssn: (parent, _, ctx) => {
      if (!ctx.user.isAdmin) throw new ForbiddenError('Not authorized');
      return parent.ssn;
    }
  }
};
```

## Pentest checklist

- Introspection query: `{__schema{types{name,fields{name}}}}`
- Deeply nested queries (depth bomb)
- Unbounded lists: `{ users(first:99999) { ... } }`
- Batch multiple queries in one request
- Alias same field 1000 times: `{ a1: user(id:1){name} a2: user(id:2){name} ... }`
- Field suggestions in error messages (schema leakage without introspection)
- IDOR via direct ID access in queries/mutations
