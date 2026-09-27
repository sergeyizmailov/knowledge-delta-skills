#!/usr/bin/env python3
"""Page housekeeping that autolaunch SaaS does from a form: avatar, cover, about, website.

    python3 page.py 456 --show
    python3 page.py 456 --avatar avatar.jpg
    python3 page.py 456 --cover cover.jpg
    python3 page.py 456 --about "Short bio" --website https://example.tld
    python3 page.py 456 --list-pages          # every Page the token can advertise from

All writes go through the PAGE token (graph.page_token) and need pages_manage_metadata /
pages_manage_posts on a Page role — a plain user/System User token gets #283 / 200.

Not here, because the API does not expose them: renaming an established Page (name changes go
through a review flow in the UI), creating a Page (UI), username claim. Do those in the
antidetect profile, one action at a time (01).
"""

from __future__ import annotations

import argparse
import json
import sys

import graph

SUMMARY_SCHEMA = "page.result/v1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page_id", nargs="?")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--list-pages", action="store_true")
    ap.add_argument("--avatar", help="image file")
    ap.add_argument("--cover", help="image file")
    ap.add_argument("--about")
    ap.add_argument("--website")
    ap.add_argument("--clear-website", action="store_true", help="remove the website (sends an empty value)")
    ap.add_argument("--remove-cover", action="store_true",
                    help="delete the current cover photo; only works on a cover this app uploaded (#200 "
                         "otherwise: remove in the UI or replace with --cover)")
    args = ap.parse_args()

    if args.list_pages:
        rows: list[dict] = []
        params: dict = {"fields": "id,name,category,tasks,fan_count", "limit": 200}
        while True:
            response = graph.get("me/accounts", params=params, context="pages")
            rows.extend(response.get("data", []))
            params = graph.next_page_params(response, params)
            if params is None:
                break
        for p in rows:
            print(f"  {p['id']}  {(p.get('name') or '?')[:40]:<40} {p.get('category')}  tasks={p.get('tasks')}")
        print(json.dumps({"schema": SUMMARY_SCHEMA, "action": "list-pages", "pages": rows},
                         ensure_ascii=False))
        return 0
    if not args.page_id:
        sys.exit("page_id required")
    pid = args.page_id

    if args.show or not any([args.avatar, args.cover, args.about, args.website, args.clear_website,
                             args.remove_cover]):
        p = graph.get(pid, params={"fields": "id,name,username,category,about,website,fan_count,"
                                             "picture{url},cover{source},is_published,verification_status"},
                      context="page")
        print(json.dumps(p, indent=2, ensure_ascii=False))
        print(json.dumps({"schema": SUMMARY_SCHEMA, "action": "show", "page_id": pid, "page": p},
                         ensure_ascii=False))
        return 0

    ptoken = graph.page_token(pid)
    if args.avatar:
        # Bytes, not a handle: a retried upload would otherwise re-read a handle at EOF.
        with open(args.avatar, "rb") as fh:
            avatar = fh.read()
        graph.call("POST", f"{pid}/picture", files={"source": (args.avatar, avatar)},
                   token_override=ptoken, context="avatar", idempotent=True)
        print("  ✓ avatar")
    if args.cover:
        with open(args.cover, "rb") as fh:
            cover = fh.read()
        photo = graph.call("POST", f"{pid}/photos", data={"published": False},
                           files={"source": (args.cover, cover)}, token_override=ptoken,
                           context="cover upload")
        graph.call("POST", pid, data={"cover": photo["id"]}, token_override=ptoken,
                   context="cover set", idempotent=True)
        print("  ✓ cover")
    if args.remove_cover:
        cover = (graph.get(pid, params={"fields": "cover{id,cover_id}"}, context="cover") or {}).get("cover") or {}
        photo_id = cover.get("cover_id") or cover.get("id")
        if photo_id:
            try:
                graph.call("DELETE", str(photo_id), token_override=ptoken, context="cover delete",
                           idempotent=True)
                print(f"  ✓ cover {photo_id} deleted")
            except graph.GraphError as e:
                # Field 2026-09-26: (#200) "App can only delete photos created by the same app" — a
                # cover uploaded in the UI can only be removed in the UI (or replaced via --cover).
                if e.code != 200:
                    raise
                print(f"  ! cover {photo_id} was not uploaded by this app: remove it in the UI "
                      "(page -> cover -> Remove) or replace it with --cover", file=sys.stderr)
        else:
            print("  = no cover to delete")
    fields = {k: v for k, v in (("about", args.about), ("website", args.website)) if v}
    if args.clear_website:
        fields["website"] = ""
    if fields:
        graph.call("POST", pid, data=fields, token_override=ptoken, context="page fields", idempotent=True)
        print(f"  ✓ {', '.join(fields)}")
    back = graph.get(pid, params={"fields": "name,about,website,picture{url},cover{id}"}, context="readback")
    print(json.dumps(back, indent=2, ensure_ascii=False))
    print(json.dumps({
        "schema": SUMMARY_SCHEMA, "action": "set", "page_id": pid,
        "fields_set": sorted(list(fields) + (["avatar"] if args.avatar else [])
                             + (["cover"] if args.cover else []) + (["cover_removed"] if args.remove_cover else [])),
        "page": back,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
