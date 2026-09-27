# 17 — Catalog via one Google Sheet (agent-editable)

Verified 2026-09-03 (Meta fields page, MC help 12158053/14990942, Sheets API limits, IAM docs).
Fastest catalog path for small/medium catalogs and for swapping product links/images without
re-uploading feeds: **one Google Sheet is the source of truth; Meta (and MC, if used) pull it on a
schedule; the agent edits rows through a service account with permanent access.**

## Setup once (user, Cloud Console — 5 min)

1. Cloud Console → project → APIs & Services → Enable **Google Sheets API**.
2. IAM → Service Accounts → Create (no roles needed) → Keys → Add key → JSON. Save it outside the
   skills tree; `export GSHEETS_JSON_KEY_FILE=/path/key.json`. Never paste it in chat or argv.
   If key creation is blocked (`iam.disableServiceAccountKeyCreation`, default for orgs created
   after 2024-05-03) → use a personal Cloud project or Workload Identity/ADC.
3. Create the sheet, tab `products`. Share → add the SA email (`client_email` in the key; also
   printed by `sheetfeed info`) as **Editor**. SA beats OAuth here: keys don't expire, access
   survives password changes and sessions.
4. Sheets API caps: 60 reads + 60 writes/min/user, 300/min/project. `sheetfeed` batches writes.

### Meta API prerequisite for a new catalog

If the catalog does not yet exist, create it through `metaops … catalog create` (`16`) with an
**Admin-role System User** token. An Employee System User may maintain an already assigned
catalog, but `POST /{business_id}/owned_product_catalogs` needs the Business Portfolio's Admin
role; OAuth scopes alone do not grant it. `workspace.json.api_version`: follow the canonical
Workspace contract in `16`; `metaops` refuses a mismatch before any Graph call.

Before the create, run `metaops --workspace . --profile <name> --json doctor --scope
provisioning`. It is read-only and verifies that the token is the workspace's current Admin System
User; `catalog create` repeats the same check immediately before its POST.

## Connect the platforms (UI only)

| Platform | Path | Sharing the platform needs | Schedule |
|---|---|---|---|
| Meta | Commerce Manager → Catalog → Data sources → Add → **Scheduled feed** → paste the sheet URL (or the CSV export URL from `sheetfeed info`) | link-sharing **Anyone with the link (Viewer)** — Meta cannot use your SA | hourly / daily / weekly, never sub-hourly; "Request update now" for an immediate fetch |
| Merchant Center | Products → Add product source → **Google Sheets** → existing sheet | MC uses its **own** fetch identity; Workspace admin may need to allow external sharing / allowlist MC | default every 24 h, configurable; UI-only (Merchant API can only list a Sheets source, not create one) |

Public link = public data: nothing but feed columns on that tab (no cost/margin/supplier).
The CSV-export-URL variant is common practice, not documented by Meta — prefer the plain sheet URL.

## Columns

Header row = exact attribute names, no custom headers, no blank rows, no merged cells. Renaming a
header silently drops the attribute.
Required: `id title description availability condition price link image_link brand`.
Recommended: `gtin mpn identifier_exists sale_price item_group_id google_product_category …`
(`sheetfeed init-header` writes the canonical row).

| Field | Meta | MC |
|---|---|---|
| `price` | `9.99 USD` | same |
| `availability` | `in stock` / `out of stock` / `preorder` / `available for order` / `discontinued` | `in_stock` / `out_of_stock` / `preorder` / `backorder` |
| `condition` | `new` / `refurbished` / `used` | same |

One sheet serving both platforms needs a second tab with `=SUBSTITUTE(availability," ","_")`
(or `--target both` on validate to see the conflicts). Meta-only: keep Meta values.

## Agent workflow (`sheetfeed`, project `meta-grey-ops`)

```bash
S=/path/to/meta/meta-grey-ops; SHEET="https://docs.google.com/spreadsheets/d/<id>/edit"
uv run --isolated --project $S sheetfeed --sheet "$SHEET" --json info          # gid, CSV URL, SA email to share with
uv run --isolated --project $S sheetfeed --sheet "$SHEET" --json init-header   # empty tab only
uv run --isolated --project $S sheetfeed --sheet "$SHEET" --json upsert --file items.csv   # by id; appends new
uv run --isolated --project $S sheetfeed --sheet "$SHEET" --json set --id SKU1 --field link --value "https://…"
uv run --isolated --project $S sheetfeed --sheet "$SHEET" --json validate --target meta
uv run --isolated --project $S sheetfeed --sheet "$SHEET" --json pull --out items.json
```

Result envelope `sheetfeed.result/v1`; `validate` exit 1 lists `problems`. Then force the fetch:
`metaops feed sync --sheet <url> --confirm FEED` (`POST /{feed_id}/uploads`, ~10 s) instead of waiting for the
schedule or clicking "Request update now"; one-shot swap = `metaops feed swap --file items.json --confirm FEED`
(`16`). Then `metaops assets set-products` / catalog product-set repair
(`04`) as usual. Edit the sheet, not `/{catalog_id}/batch`, when the sheet is the source: the next
scheduled fetch overwrites API edits.

## Traps

- **Image cache by URL**: Meta will not re-fetch a changed image behind the same URL. New image →
  new URL (`?v=2` or new filename). Same for `link` swaps: change the value, not the target page.
- **`raw.githubusercontent.com` caches 404s** (~5 min). Probing a URL before the file is pushed
  poisons it: the push succeeds, the API returns the `download_url`, and raw keeps serving 404
  while `GET /repos/{owner}/{repo}/contents` already lists the file. Never curl the URL first;
  if you did, push under a name that was never requested (`tr_08_v1.jpeg`) rather than waiting.
  Verified 2026-09-22.
- Feed `link` may carry the macro tail (`?utm_campaign={{campaign.name}}&adset_id={{adset.id}}…`)
  — put it in before first delivery (`04`).
- Price/availability must equal the landing page (Meta rejects items; MC preemptive disapproval).
- `image_link` must be crawler-stable and `https`; fbcdn signed URLs fail.
- Swap gate applies (`04`): `feed swap` changes rows as soon as every ad showing those items (sets
  holding the ids + rule-based sets) is approved; unrelated ads never hold it; never wait for delivery.
- Sheet limit is 10M cells (not 5M); stray formatting, not rows, is what hits it.
