#!/usr/bin/env python3
"""Comment moderation on ad posts: list, hide, delete — with a Page token.

    python3 comments.py --account act_123 --page 456 --list
    python3 comments.py --account act_123 --page 456 --hide-all      # skips the Page's own comments
    python3 comments.py --account act_123 --page 456 --hide-matching "scam|мошенн|развод|fake"
    python3 comments.py --ads 1111,2222 --page 456 --delete-matching "http"

Grey funnels get negative comments within hours and each one is social proof against the
ad; autolaunch SaaS auto-hides them. Mechanics:
  ad → creative.effective_object_story_id (the promoted post) → /{post}/comments
  → POST /{comment_id} is_hidden=true  (or DELETE)
All comment calls use the PAGE token (graph.page_token), which needs a Page role with
pages_manage_engagement / pages_read_user_content on the Page — a user or System User token
gets 200 permission errors here, that is not a missing comment.

Hidden comments stay visible to their author and friends (Meta behaviour) — hide, don't
delete, unless the text is a link or slur; deletion can be reported and looks worse.
Idempotent: hiding an already-hidden comment is a no-op, so this can run on a cron.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import graph

SUMMARY_SCHEMA = "comments.result/v1"


def ad_ids(account: str | None, ads: str | None) -> list[str]:
    if ads:
        return [a.strip() for a in ads.split(",") if a.strip()]
    if not account:
        sys.exit("pass --account or --ads")
    account = graph.normalize_account(account)
    out, path, params = [], f"{account}/ads", {
        "fields": "id,effective_status", "limit": 500,
        "effective_status": json.dumps(["ACTIVE", "PAUSED", "PENDING_REVIEW", "CAMPAIGN_PAUSED",
                                        "ADSET_PAUSED", "WITH_ISSUES"])}
    while True:
        resp = graph.get(path, params=params, context="ads")
        out.extend(a["id"] for a in resp.get("data", []))
        params = graph.next_page_params(resp, params)
        if params is None:
            return out


def story_id(ad_id: str, expected_account: str | None = None) -> str | None:
    ad = graph.get(ad_id, params={"fields": "account_id,creative{effective_object_story_id}"}, context="ad story")
    if expected_account:
        actual = ad.get("account_id")
        if not actual or graph.normalize_account(actual) != graph.normalize_account(expected_account):
            raise SystemExit(f"{ad_id} belongs to {actual or '?'} not {expected_account}; refusing cross-profile comments")
    return (ad.get("creative") or {}).get("effective_object_story_id")


def comments(post_id: str, ptoken: str) -> list[dict]:
    out, path, params = [], f"{post_id}/comments", {
        "fields": "id,message,from,created_time,is_hidden,like_count", "limit": 100,
        "filter": "stream", "order": "reverse_chronological"}
    while True:
        resp = graph.call("GET", path, params=params, token_override=ptoken, context="comments")
        out.extend(resp.get("data", []))
        next_params = graph.next_page_params(resp, params)
        if next_params is None or len(out) >= 1000:
            if next_params is not None:
                print("  ! 1000-comment cap hit — older comments were NOT swept; re-run later", file=sys.stderr)
            return out
        params = next_params


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", help="act_<id>: all ACTIVE/PAUSED/PENDING ads")
    ap.add_argument("--ads", help="comma-separated ad ids instead of --account")
    ap.add_argument("--page", required=True, help="Page id that owns the ad posts")
    ap.add_argument("--expected-account", help="internal metaops profile binding for explicit ad ids")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--hide-all", action="store_true")
    g.add_argument("--hide-matching", help="regex (case-insensitive) on comment text")
    g.add_argument("--delete-matching", help="regex; deletion is irreversible")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be hidden/deleted; `acted` counts the would-be actions")
    args = ap.parse_args()

    ptoken = graph.page_token(args.page)
    pattern = re.compile(args.hide_matching or args.delete_matching or "", re.IGNORECASE) \
        if (args.hide_matching or args.delete_matching) else None

    seen_posts: set[str] = set()
    acted = 0
    rows_out: list[dict] = []
    for aid in ad_ids(args.account, args.ads):
        try:
            post = story_id(aid, args.expected_account)
        except graph.GraphError as e:
            print(f"  ! ad {aid}: {e}", file=sys.stderr)
            continue
        if not post or post in seen_posts:
            continue
        seen_posts.add(post)
        try:
            rows = comments(post, ptoken)
        except graph.GraphError as e:
            print(f"  ! post {post}: {e} — Page role / pages_read_user_content?", file=sys.stderr)
            continue
        print(f"post {post} (ad {aid}): {len(rows)} comment(s)")
        for c in rows:
            text = c.get("message", "")
            who = (c.get("from") or {}).get("name", "?")
            flag = "[hidden] " if c.get("is_hidden") else ""
            if args.list:
                print(f"    {flag}{c['created_time'][:16]}  {who[:20]:<20} {text[:100]}")
                rows_out.append({
                    "id": c["id"], "post": post, "ad": aid, "from": who,
                    "text": text, "is_hidden": bool(c.get("is_hidden")),
                    "created_time": c.get("created_time"), "like_count": c.get("like_count"),
                })
                continue
            # Never hide or delete the Page's own replies (the answers under the ad), in any mode.
            if str((c.get("from") or {}).get("id")) == str(args.page):
                continue
            hit = args.hide_all or (pattern and pattern.search(text or ""))
            if not hit or (c.get("is_hidden") and not args.delete_matching):
                continue
            action = "DELETE" if args.delete_matching else "hide"
            print(f"    {action:<6} {who[:20]:<20} {text[:80]}")
            if args.dry_run:
                acted += 1  # "would be acted on": the summary counts what a real run would do
                continue
            try:
                if args.delete_matching:
                    graph.call("DELETE", c["id"], token_override=ptoken, context="delete comment",
                               idempotent=True)
                else:
                    graph.call("POST", c["id"], data={"is_hidden": True}, token_override=ptoken,
                               context="hide comment", idempotent=True)
                acted += 1
            except graph.GraphError as e:
                print(f"      ! {e}", file=sys.stderr)
    if not args.list:
        print(f"\n{acted} comment(s) {'would be ' if args.dry_run else ''}acted on across {len(seen_posts)} post(s).")
    mode = "list" if args.list else ("delete" if args.delete_matching else "hide")
    summary = {
        "schema": SUMMARY_SCHEMA, "mode": mode, "posts_checked": len(seen_posts),
        "acted": acted, "dry_run": args.dry_run,
    }
    if args.list:
        summary["rows"] = rows_out
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
