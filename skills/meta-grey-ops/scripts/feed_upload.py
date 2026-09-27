#!/usr/bin/env python3
"""Trigger an immediate product-feed fetch and wait for it.

    python3 feed_upload.py --feed-id 123 --url https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=0

POST /{feed_id}/uploads {url} makes Meta fetch the file now instead of waiting for the
scheduled fetch (hourly at best). Then GET /{upload_id} until end_time is set and report
num_persisted_items / num_invalid_items / error_count; --errors also lists /{upload_id}/errors.
The URL must be reachable without auth (sheet shared "Anyone with the link"). Writes only
inside a workspace-bound metaops process (graph.require_write_authority).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import graph

UPLOAD_FIELDS = "id,start_time,end_time,input_method,url,num_detected_items,num_persisted_items,num_invalid_items,num_deleted_items,error_count,warning_count"


def start(feed_id: str, url: str, update_only: bool) -> str:
    # Duplicate-safe by design (no in-flight needed): POST /{feed_id}/uploads only
    # triggers another fetch of the SAME url. Re-posting after outcome_unknown may
    # start a second fetch, but both converge to the same catalog state — no money
    # moves, no twin objects. Poll the returned upload id; if the POST itself broke
    # unknown, re-post the identical payload and poll the new id.
    data: dict = {"url": url}
    if update_only:
        data["update_only"] = True
    resp = graph.post(f"{feed_id}/uploads", data, context="feed upload")
    return str(resp["id"])


def poll(upload_id: str, wait_s: int, interval_s: int = 5) -> dict:
    deadline = time.monotonic() + wait_s
    while True:
        u = graph.get(upload_id, params={"fields": UPLOAD_FIELDS}, context="feed upload status")
        if u.get("end_time") or time.monotonic() >= deadline:
            return u
        time.sleep(interval_s)


def finished(u: dict) -> bool:
    return bool(u.get("end_time"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed-id", required=True)
    ap.add_argument("--url", required=True, help="public CSV/TSV/XML URL Meta fetches now")
    ap.add_argument("--update-only", action="store_true", help="never delete items missing from the file")
    ap.add_argument("--wait", type=int, default=120, help="seconds to wait for end_time")
    ap.add_argument("--errors", action="store_true", help="list /{upload_id}/errors when error_count > 0")
    args = ap.parse_args()
    upload_id = start(args.feed_id, args.url, args.update_only)
    u = poll(upload_id, args.wait)
    out = {"upload_id": upload_id, "finished": finished(u), **{k: u.get(k) for k in UPLOAD_FIELDS.split(",") if k != "id"}}
    if args.errors and (u.get("error_count") or 0) > 0:
        errors: list[dict] = []
        params: dict = {"fields": "id,severity,summary,description,total_count", "limit": 50}
        while True:
            response = graph.get(f"{upload_id}/errors", params=params, context="feed upload errors")
            errors.extend(response.get("data", []))
            params = graph.next_page_params(response, params)
            if params is None:
                break
        out["errors"] = errors
    print(json.dumps(out, ensure_ascii=False))
    if not finished(u):
        print("upload still running; re-check GET /{upload_id}", file=sys.stderr)
        return 1
    return 0 if (u.get("error_count") or 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
