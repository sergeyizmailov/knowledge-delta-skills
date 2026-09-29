"""sheetfeed — one Google Sheet as the product catalog for Merchant Center and Meta, edited by an agent.

Merchant Center reads the sheet as a Google Sheets data source; Meta reads it as a scheduled feed
(Google Sheets option or the sheet's CSV export URL). The agent edits rows here through a service
account that is shared on the sheet as Editor — no OAuth consent, no token expiry.

Env: GSHEETS_JSON_KEY_FILE (service-account key; falls back to GMC_JSON_KEY_FILE).
Sheets API v4 over REST (google-auth + requests); no gspread dependency.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import re
import sys
from typing import Any

SCOPE = "https://www.googleapis.com/auth/spreadsheets"
API = "https://sheets.googleapis.com/v4/spreadsheets"
RESULT_SCHEMA = "sheetfeed.result/v1"

# Column names shared by the Merchant Center product spec and the Meta catalog feed spec.
REQUIRED = ["id", "title", "description", "availability", "condition", "price", "link", "image_link", "brand"]
RECOMMENDED = ["gtin", "mpn", "identifier_exists", "sale_price", "item_group_id", "google_product_category",
               "product_type", "additional_image_link", "custom_label_0", "custom_label_1", "custom_label_2",
               "custom_label_3", "custom_label_4", "shipping", "color", "size", "gender", "age_group"]
# Enum spellings differ between the two platforms; one sheet cannot satisfy both literally.
AVAILABILITY = {"mc": {"in_stock", "out_of_stock", "preorder", "backorder"},
                "meta": {"in stock", "out of stock", "preorder", "available for order", "discontinued"}}
CONDITION = {"mc": {"new", "refurbished", "used"}, "meta": {"new", "refurbished", "used"}}
PRICE_RE = re.compile(r"^\d+(\.\d{1,2})? [A-Z]{3}$")
URL_RE = re.compile(r"^https://")


class SheetError(Exception):
    pass


def envelope(command: str, ok: bool, phase: str, *, data: dict | None = None, error: dict | None = None,
             next_action: str | None = None) -> dict[str, Any]:
    return {"schema": RESULT_SCHEMA, "ok": ok, "command": command, "phase": phase, "artifacts": {},
            "data": data or {}, "error": error, "next_action": next_action}


def sheet_id(value: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", value)
    if m:
        return m.group(1)
    if re.match(r"^[A-Za-z0-9_-]{20,}$", value):
        return value
    raise SheetError("pass the spreadsheet URL or its id")


def csv_export_url(spreadsheet: str, gid: int = 0) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id(spreadsheet)}/export?format=csv&gid={gid}"


def validate_rows(header: list[str], rows: list[list[str]], target: str) -> list[str]:
    """Header + row checks that fail feed ingestion or trigger price/availability disapprovals."""
    problems: list[str] = []
    cols = [h.strip() for h in header]
    if len(set(cols)) != len(cols):
        problems.append("duplicate header names")
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        problems.append(f"missing required columns: {missing}")
    if "gtin" not in cols and "mpn" not in cols and "identifier_exists" not in cols:
        problems.append("no gtin/mpn/identifier_exists column — products without identifiers lose visibility")
    idx = {c: i for i, c in enumerate(cols)}
    seen_ids: set[str] = set()
    targets = ("mc", "meta") if target == "both" else (target,)
    for n, row in enumerate(rows, start=2):
        if not any(cell.strip() for cell in row):
            problems.append(f"row {n}: empty row inside the data range (breaks some fetchers)")
            continue
        def cell(name: str) -> str:
            i = idx.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""
        pid = cell("id")
        if not pid:
            problems.append(f"row {n}: empty id")
        elif pid in seen_ids:
            problems.append(f"row {n}: duplicate id {pid!r}")
        seen_ids.add(pid)
        if "availability" in idx:
            av = cell("availability")
            if not any(av in AVAILABILITY[t] for t in targets):
                problems.append(f"row {n}: availability {av!r} not valid for {targets} "
                                f"(MC: in_stock; Meta: 'in stock')")
        if "condition" in idx and cell("condition") not in CONDITION["mc"]:
            problems.append(f"row {n}: condition {cell('condition')!r}")
        if "price" in idx and not PRICE_RE.match(cell("price")):
            problems.append(f"row {n}: price must look like '19.99 USD', got {cell('price')!r}")
        if "sale_price" in idx and cell("sale_price") and not cell("price"):
            problems.append(f"row {n}: sale_price without price (misrepresentation trigger)")
        for col in ("link", "image_link"):
            if col in idx and not URL_RE.match(cell(col)):
                problems.append(f"row {n}: {col} must be an absolute https URL")
        if "title" in idx and len(cell("title")) > 150:
            problems.append(f"row {n}: title over 150 chars")
        if "description" in idx and len(cell("description")) > 5000:
            problems.append(f"row {n}: description over 5000 chars")
    return problems


class Sheet:
    def __init__(self, spreadsheet: str, tab: str):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        key = os.environ.get("GSHEETS_JSON_KEY_FILE") or os.environ.get("GMC_JSON_KEY_FILE")
        if not key:
            raise SheetError("set GSHEETS_JSON_KEY_FILE (service account shared on the sheet as Editor)")
        creds = service_account.Credentials.from_service_account_file(key, scopes=[SCOPE])
        self.session = AuthorizedSession(creds)
        self.id = sheet_id(spreadsheet)
        self.tab = tab
        self.sa_email = getattr(creds, "service_account_email", None)

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        r = self.session.get(f"{API}/{self.id}{path}", params=params, timeout=60)
        if r.status_code == 403:
            raise SheetError(f"403: share the sheet with {self.sa_email} as Editor, or enable the Sheets API "
                             "on the service account's project")
        if r.status_code == 404:
            raise SheetError("404: spreadsheet id not found (or not shared with the service account)")
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict[str, Any], **params: Any) -> dict[str, Any]:
        r = self.session.post(f"{API}/{self.id}{path}", params=params, json=body, timeout=60)
        if r.status_code >= 400:
            raise SheetError(f"{r.status_code}: {r.text[:400]}")
        return r.json()

    def _put(self, path: str, body: dict[str, Any], **params: Any) -> dict[str, Any]:
        r = self.session.put(f"{API}/{self.id}{path}", params=params, json=body, timeout=60)
        if r.status_code >= 400:
            raise SheetError(f"{r.status_code}: {r.text[:400]}")
        return r.json()

    def meta(self) -> dict[str, Any]:
        info = self._get("", fields="spreadsheetId,properties.title,sheets.properties")
        tabs = {s["properties"]["title"]: s["properties"] for s in info.get("sheets", [])}
        if self.tab not in tabs:
            raise SheetError(f"tab {self.tab!r} not found; tabs: {sorted(tabs)}")
        return {"title": info["properties"]["title"], "gid": tabs[self.tab]["sheetId"],
                "rows": tabs[self.tab].get("gridProperties", {}).get("rowCount"),
                "cols": tabs[self.tab].get("gridProperties", {}).get("columnCount")}

    def read(self) -> tuple[list[str], list[list[str]]]:
        values = self._get(f"/values/{self.tab}", valueRenderOption="UNFORMATTED_VALUE").get("values", [])
        if not values:
            return [], []
        header = [str(h) for h in values[0]]
        rows = [[str(c) for c in row] for row in values[1:]]
        return header, rows

    def write_header(self, header: list[str]) -> None:
        self._put(f"/values/{self.tab}!1:1", {"values": [header]}, valueInputOption="RAW")

    def upsert(self, items: list[dict[str, Any]], header: list[str], rows: list[list[str]]) -> dict[str, int]:
        """Match on `id`; update in place, append new. Values written RAW so '19.99 USD' stays text."""
        if "id" not in header:
            raise SheetError("sheet has no id column")
        col_idx = {c: i for i, c in enumerate(header)}
        new_cols = [k for item in items for k in item if k not in col_idx]
        for k in dict.fromkeys(new_cols):
            header.append(k)
            col_idx[k] = len(header) - 1
        if new_cols:
            self.write_header(header)
        by_id = {row[col_idx["id"]]: n for n, row in enumerate(rows, start=2) if len(row) > col_idx["id"]}
        updates: list[dict[str, Any]] = []
        appends: list[list[str]] = []
        counts = {"updated": 0, "appended": 0}
        for item in items:
            pid = str(item.get("id", "")).strip()
            if not pid:
                raise SheetError("every item needs an id")
            if pid in by_id:
                n = by_id[pid]
                current = rows[n - 2] + [""] * (len(header) - len(rows[n - 2]))
                for k, v in item.items():
                    current[col_idx[k]] = "" if v is None else str(v)
                updates.append({"range": f"{self.tab}!A{n}", "values": [current]})
                counts["updated"] += 1
            else:
                line = [""] * len(header)
                for k, v in item.items():
                    line[col_idx[k]] = "" if v is None else str(v)
                appends.append(line)
                counts["appended"] += 1
        if updates:
            self._post("/values:batchUpdate", {"valueInputOption": "RAW", "data": updates})
        if appends:
            self._post(f"/values/{self.tab}:append", {"values": appends}, valueInputOption="RAW",
                       insertDataOption="INSERT_ROWS")
        return counts


def load_items(path: str) -> list[dict[str, Any]]:
    p = pathlib.Path(path)
    if p.suffix.lower() == ".csv":
        with p.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def main() -> int:
    ap = argparse.ArgumentParser(prog="sheetfeed", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True, help="spreadsheet URL or id")
    ap.add_argument("--tab", default="products")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="tab gid, size, CSV export URL, service-account email to share with")
    v = sub.add_parser("validate", help="header + row checks against MC/Meta feed rules")
    v.add_argument("--target", choices=["mc", "meta", "both"], default="mc")
    p = sub.add_parser("pull", help="read the tab as JSON rows")
    p.add_argument("--out")
    u = sub.add_parser("upsert", help="update rows by id / append new from CSV or JSON")
    u.add_argument("--file", required=True)
    u.add_argument("--target", choices=["mc", "meta", "both"], default="mc")
    s = sub.add_parser("set", help="set one field on one product")
    s.add_argument("--id", required=True)
    s.add_argument("--field", required=True)
    s.add_argument("--value", required=True)
    sub.add_parser("init-header", help="write the canonical header row into an empty tab")
    args = ap.parse_args()
    try:
        sheet = Sheet(args.sheet, args.tab)
        if args.command == "info":
            m = sheet.meta()
            result = envelope("info", True, "reported", data={**m, "csv_export_url": csv_export_url(args.sheet, m["gid"]),
                                                              "share_with": sheet.sa_email})
        elif args.command == "init-header":
            header, rows = sheet.read()
            if header:
                raise SheetError("tab already has a header; refusing to overwrite")
            sheet.write_header(REQUIRED + RECOMMENDED)
            result = envelope("init-header", True, "written", data={"header": REQUIRED + RECOMMENDED})
        elif args.command in ("validate", "pull"):
            header, rows = sheet.read()
            if args.command == "pull":
                items = [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows]
                if args.out:
                    pathlib.Path(args.out).write_text(json.dumps(items, indent=2, ensure_ascii=False))
                result = envelope("pull", True, "reported", data={"count": len(items), "items": None if args.out else items})
            else:
                problems = validate_rows(header, rows, args.target)
                result = envelope("validate", not problems, "valid" if not problems else "invalid",
                                  data={"rows": len(rows), "problems": problems},
                                  next_action=None if not problems else "Fix the rows, then fetch now in MC / Meta.")
        else:
            header, rows = sheet.read()
            items = load_items(args.file) if args.command == "upsert" else [{"id": args.id, args.field: args.value}]
            if args.command == "upsert":
                probe_header = list(dict.fromkeys(header + [k for i in items for k in i]))
                merged = {r[header.index("id")]: r for r in rows if header and len(r) > header.index("id")} if "id" in header else {}
                for it in items:
                    line = [""] * len(probe_header)
                    base = merged.get(str(it.get("id", "")))
                    if base:
                        for i, val in enumerate(base):
                            line[i] = val
                    for k, val in it.items():
                        line[probe_header.index(k)] = "" if val is None else str(val)
                    merged[str(it.get("id", ""))] = line
                problems = validate_rows(probe_header, list(merged.values()), args.target)
                if problems:
                    raise SheetError("refusing to write invalid rows: " + "; ".join(problems[:10]))
            counts = sheet.upsert(items, header, rows)
            result = envelope(args.command, True, "written", data=counts,
                              next_action="Merchant Center: Products → Data sources → Fetch now. Meta: Data sources → "
                                          "Request update. Then re-check statuses after processing.")
        code = 0 if result["ok"] else 1
    except SheetError as exc:
        code, result = 2, envelope(args.command, False, "rejected", error={"kind": "SheetError", "message": str(exc)})
    except Exception as exc:  # noqa: BLE001 — surface API errors as JSON
        code, result = 1, envelope(args.command, False, "api_error", error={"kind": type(exc).__name__,
                                                                            "message": str(exc)[:1500]})
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        print(f"[{result['command']}] ok={result['ok']} phase={result['phase']}", file=sys.stderr)
        print(json.dumps({k: result[k] for k in ("data", "error", "next_action")}, indent=2, ensure_ascii=False, default=str))
    return code


if __name__ == "__main__":
    sys.exit(main())
