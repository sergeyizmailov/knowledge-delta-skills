#!/usr/bin/env python3
"""Tyver spy (FB/IG ad library) public API CLI. Stdlib only. Reference: references/07-tyver-spy-api.md

Auth: env TYVER_KEY (tyv_...). Quota: every creative RETURNED costs 1 view (a search page = 60).
Search results already carry full creative data; `get` is only for a known id.

  tyver.py me
  tyver.py search --country KG --vertical GAMBLING --countries-limit 1 --active-since 2026-09-23 \
      --pages 3 --out kg.jsonl            # appends, dedupes by provider_id; prints next cursor
  tyver.py summary kg.jsonl [--top 15]   # advertisers, domains, angles, formats, longest runners
  tyver.py media kg.jsonl --dir media/ [--min-days 7] [--limit 30]
  tyver.py get <provider_id>
  tyver.py blacklist list | add <fan_page_id> | rm <fan_page_id>
"""
import argparse
import collections
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.tyver.io/public/v1"
PAGE = 60  # items per search page (fixed by the API)
UA = "tyver-cli/1.0"


def call(method: str, path: str, params: list[tuple[str, str]] | None = None) -> dict:
    key = os.environ.get("TYVER_KEY")
    if not key:
        sys.exit("TYVER_KEY not set (source the env file that holds it)")
    url = f"{BASE}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(5):
        req = urllib.request.Request(url, method=method,
                                     headers={"X-Tyver-Authorization": key, "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt * 3)
                continue
            hint = {401: "bad/missing token", 403: "Free plan or quota exhausted",
                    400: "bad cursor", 422: "invalid filter value (see enum in the message)"}.get(e.code, "")
            sys.exit(f"HTTP {e.code} {hint}: {body[:1500]}")
        except urllib.error.URLError as e:
            if attempt < 4:
                time.sleep(3)
                continue
            sys.exit(f"network: {e}")
    sys.exit("unreachable")


def remaining() -> int:
    return call("GET", "info/me")["data"]["remainder_views"]


# flag -> API param; list=True means repeatable (array param, sent as repeated keys)
FILTERS = [
    ("country", "countries", True), ("language", "languages", True),
    ("media-type", "media_types", True), ("media-format", "media_formats", True),
    ("cta", "cta", True), ("placement", "placements", True), ("app-store", "app_stores", True),
    ("cms", "cms", True), ("subcategory", "vertical_subcategories", True),
    ("vertical", "vertical", False), ("search", "search", False),
    ("countries-limit", "countries_limit", False),
    ("created-since", "creation_date_gte", False), ("created-until", "creation_date_lte", False),
    ("min-days", "activity_days_amount_gte", False), ("max-days", "activity_days_amount_lte", False),
    ("active-since", "recent_activity_gte", False), ("active-until", "recent_activity_lte", False),
    ("in-link", "in_link", False), ("fan-page", "fan_page", False), ("app", "app", False),
    ("domain", "domain", False), ("domain-zone", "domain_zones", False),
    ("gender", "gender", False), ("age-gte", "age_gte", False), ("age-lte", "age_lte", False),
    ("min-impressions", "impressions_gte", False), ("max-impressions", "impressions_lte", False),
    ("with-lead-form", "with_lead_form", False), ("sort", "sort", False),
]


def cmd_search(a) -> None:
    params = []
    for flag, api, is_list in FILTERS:
        v = getattr(a, flag.replace("-", "_"))
        if v is None:
            continue
        params += [(api, x) for x in v] if is_list else [(api, str(v))]
    if a.include_blacklisted:
        params.append(("without_blacklist", "false"))
    left = remaining()
    cost = a.pages * PAGE
    if cost > left or (cost > a.max_views):
        sys.exit(f"refusing: up to {cost} views needed, {left} left, --max-views {a.max_views}")
    out = Path(a.out) if a.out else None
    seen = set()
    if out and out.exists():
        seen = {json.loads(l)["provider_id"] for l in out.read_text().split("\n") if l.strip()}
    cursor, new, total = a.cursor, 0, None
    for _ in range(a.pages):
        d = call("GET", "creatives/", params + ([("cursor", cursor)] if cursor else []))["data"]
        total = d["total"]
        items = d["items"]
        for it in items:
            if it["provider_id"] in seen:
                continue
            seen.add(it["provider_id"])
            new += 1
            if out:
                with out.open("a") as f:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            else:
                print(json.dumps(it, ensure_ascii=False))
        cursor = d.get("cursor")
        if not cursor or len(items) < PAGE:
            cursor = None
            break
    print(json.dumps({"total_matching": total, "new_saved": new, "file": str(out) if out else None,
                      "next_cursor": cursor}), file=sys.stderr)


def load(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().split("\n") if l.strip()]


def host(url: str | None) -> str:
    if not url:
        return "-"
    h = urllib.parse.urlsplit(url if "//" in url else "//" + url).hostname or url
    return h.removeprefix("www.")


def cmd_summary(a) -> None:
    rows = load(a.file)
    n = a.top
    C = collections.Counter

    def show(title, counter):
        print(f"\n## {title}")
        for k, v in counter.most_common(n):
            print(f"{v:5}  {k}")

    print(f"creatives: {len(rows)}  active now: {sum(r.get('is_active') for r in rows)}")
    pages = collections.defaultdict(list)
    for r in rows:
        pages[(r["provider_page_id"], r.get("provider_page_name"))].append(r)
    print(f"\n## advertisers (pages) by creative count, top {n}")
    print("  ads active maxdays  page_id  name  | top landing hosts")
    for (pid, name), rs in sorted(pages.items(), key=lambda kv: -len(kv[1]))[:n]:
        hs = C(host(r.get("target_url")) for r in rs).most_common(2)
        print(f"{len(rs):5} {sum(r.get('is_active') for r in rs):6} {max(r.get('activity_days_amount') or 0 for r in rs):7}"
              f"  {pid}  {name}  | {', '.join(h for h, _ in hs)}")
    show("landing host (target_url)", C(host(r.get("target_url")) for r in rows))
    show("resolved domain field", C(r.get("domain") or "-" for r in rows))
    show("app id / store link", C(urllib.parse.parse_qs(urllib.parse.urlsplit(r.get("target_url") or "").query).get("id", ["-"])[0]
                                  for r in rows if "play.google" in (r.get("target_url") or "") or "apps.apple" in (r.get("target_url") or "")))
    show("cta", C(r.get("cta") or "-" for r in rows))
    show("language", C(",".join(r.get("languages") or ["-"]) for r in rows))
    show("media type", C(r.get("media_type") for r in rows))
    show("media format", C(",".join(r.get("media_formats") or ["-"]) for r in rows))
    show("game subcategory", C(s for r in rows for s in (r.get("vertical_subcategories") or ["-"])))
    show("placements", C(",".join(sorted(r.get("placements") or [])) for r in rows))
    show("countries per ad", C(len(r.get("countries") or []) for r in rows))
    show("link title", C((r.get("link_titles") or ["-"])[0][:70] for r in rows))
    days = sorted((r.get("activity_days_amount") or 0 for r in rows))
    if days:
        print(f"\n## activity days: median {days[len(days)//2]}, p90 {days[int(len(days)*.9)]}, max {days[-1]}")
    print(f"\n## longest-running {n} (days, active, page, cta, host, body)")
    for r in sorted(rows, key=lambda r: -(r.get("activity_days_amount") or 0))[:n]:
        body = " ".join(((r.get("bodies") or [""])[0]).split())[:110]
        print(f"{r.get('activity_days_amount'):4} {'A' if r.get('is_active') else '-'} {r['provider_id']}  "
              f"{(r.get('provider_page_name') or '')[:24]} | {r.get('cta')} | {host(r.get('target_url'))} | {body}")


def cmd_media(a) -> None:
    rows = [r for r in load(a.file) if (r.get("activity_days_amount") or 0) >= a.min_days]
    rows.sort(key=lambda r: -(r.get("activity_days_amount") or 0))
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    got = 0
    for r in rows[: a.limit]:
        for i, m in enumerate(r.get("media") or []):
            url = m.get("url") or m.get("video_image_preview_url")
            if not url:
                continue
            ext = Path(urllib.parse.urlsplit(url).path).suffix or ".bin"
            dst = d / f"{r.get('activity_days_amount') or 0:03d}d_{r['provider_id']}_{i}{ext}"
            if dst.exists():
                continue
            try:
                urllib.request.urlretrieve(url, dst)
                got += 1
            except Exception as e:  # media hosts expire links; skip, don't abort the batch
                print(f"skip {r['provider_id']}: {e}", file=sys.stderr)
    print(f"downloaded {got} files to {d}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("me")
    g = sub.add_parser("get")
    g.add_argument("provider_id")
    b = sub.add_parser("blacklist")
    b.add_argument("action", choices=["list", "add", "rm"])
    b.add_argument("fan_page_id", nargs="?")
    s = sub.add_parser("search")
    for flag, _, is_list in FILTERS:
        s.add_argument(f"--{flag}", action="append" if is_list else "store")
    s.add_argument("--include-blacklisted", action="store_true")
    s.add_argument("--pages", type=int, default=1)
    s.add_argument("--cursor")
    s.add_argument("--out")
    s.add_argument("--max-views", type=int, default=1200, help="safety cap per run (default 20 pages)")
    sm = sub.add_parser("summary")
    sm.add_argument("file")
    sm.add_argument("--top", type=int, default=15)
    md = sub.add_parser("media")
    md.add_argument("file")
    md.add_argument("--dir", required=True)
    md.add_argument("--min-days", type=int, default=0)
    md.add_argument("--limit", type=int, default=30)
    a = p.parse_args()
    if a.cmd == "me":
        print(json.dumps(call("GET", "info/me")["data"]))
    elif a.cmd == "get":
        print(json.dumps(call("GET", f"creatives/{a.provider_id}")["data"], ensure_ascii=False, indent=1))
    elif a.cmd == "blacklist":
        if a.action == "list":
            print(json.dumps(call("GET", "blacklist/")["data"]))
        else:
            if not a.fan_page_id:
                sys.exit("fan_page_id required")
            print(json.dumps(call("POST" if a.action == "add" else "DELETE", "blacklist/",
                                  [("fan_page_id", a.fan_page_id)])))
    elif a.cmd == "search":
        cmd_search(a)
    elif a.cmd == "summary":
        cmd_summary(a)
    elif a.cmd == "media":
        cmd_media(a)


if __name__ == "__main__":
    main()
