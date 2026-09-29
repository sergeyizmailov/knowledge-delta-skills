# Google Agent Ops

`googleops` is the deterministic execution layer for AI agents launching Google Ads campaigns.
It converts a JSON spec into one atomic `GoogleAdsService.Mutate` (Search, Shopping; PMax runs a
text/image asset request first, then the atomic graph — a graph failure can leave unused assets),
runs `validate_only` first, creates everything PAUSED, reads the result back through GAQL, and
makes activation a separate command. `gmcops` is the Merchant Center counterpart (gates, issues, products, Ads link).

## Install

```bash
cd google/google-grey-ops
uv tool install .
# or, without installing:
uv run --project . googleops --help
```

Python 3.11–3.14. Depends on `google-ads` (Ads API client, **not** the legacy `googleads` package)
and the `google-shopping-merchant-*` Merchant API v1 clients.

## Credentials (environment only, never in files)

```bash
export GADS_DEVELOPER_TOKEN='...'                 # issued at MCC level
export GADS_CLIENT_ID='...' GADS_CLIENT_SECRET='...' GADS_REFRESH_TOKEN='...'   # oauth
# or: export GADS_JSON_KEY_FILE=/path/key.json   # service account added as a user on the MCC
export GADS_PROXY='http://user:pass@host:port'     # identity egress (grpc_proxy); or
export GADS_ALLOW_NO_PROXY=1                       # direct egress is deliberate for this identity
export GMC_JSON_KEY_FILE=/path/key.json            # gmcops; or GMC_REFRESH_TOKEN with the same client id/secret
```

## Workspace

`workspace.json` lives in a per-MCC project directory outside the skills directory. Start from
`scripts/specs/example-workspace.json`. A profile binds one client customer to its MCC
(`login_customer_id`), currency, timezone, Merchant Center id, known conversion actions and a
hard `budget_cap_major`. Generated plans, states and receipts live under `.googleops/`.

## Lifecycle

```bash
googleops --workspace . --profile <p> --json workspace validate
googleops --workspace . --profile <p> --json doctor
googleops --workspace . --profile <p> --json plan --spec launches/search.json
googleops --workspace . --profile <p> --json apply --plan .googleops/plans/<plan>.json
googleops --workspace . --profile <p> --json verify --plan .googleops/plans/<plan>.json
googleops --workspace . --profile <p> --json activate --plan .googleops/plans/<plan>.json \
  --confirm-ui REVIEWED --confirm SPEND
```

Bulk: `bulk-plan --template spec.json --accounts accounts.json --run wave-1` → `bulk-apply --verify`
→ `bulk-activate --customer <id> --confirm-ui REVIEWED --confirm SPEND` (one customer per command).

Read-only: `report --gaql "..."`, `monitor --range YESTERDAY --jsonl survival.jsonl`,
`link status|accept --merchant <id>`.

## Merchant Center

```bash
gmcops --account <mc-id> --json doctor --country US --ads-customer <customer-id>
gmcops --account <mc-id> --json products status --status NOT_ELIGIBLE_OR_DISAPPROVED
gmcops --account <mc-id> --json datasources create-api --display-name api --feed-label US --language en --countries US
gmcops --account <mc-id> --json products insert --data-source accounts/<mc>/dataSources/<ds> --file items.json --wait 600
gmcops --account <mc-id> --json link propose --ads-customer <customer-id>
```

## Checks

```bash
SKILL_ROOT=/path/to/google/google-grey-ops
uv run --isolated --project "$SKILL_ROOT" python "$SKILL_ROOT/scripts/test_googleops.py"
uv run --isolated --with ruff ruff check --no-cache "$SKILL_ROOT/scripts"
uv lock --check --project "$SKILL_ROOT"
```
