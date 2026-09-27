#!/usr/bin/env python3
"""Read-modify-write scalar targeting edits across many ad sets.

    python3 edit_targeting.py --ids 111,222 --user-os iOS,Android --confirm TARGETING
    python3 edit_targeting.py --state run.json --user-os Android --confirm TARGETING --dry-run
    python3 edit_targeting.py --account act_1 --all --user-os iOS --confirm TARGETING

Why this script exists (04 -> "Targeting POSTs REPLACE the whole object"; launch.py
build_targeting): a POST that carries only `targeting.user_os` REPLACES the entire
`targeting` object on the ad set — every other key (geo_locations, custom_audiences,
age range, ...) is wiped, not merely left alone. So this never sends a delta. Per ad
set: GET the current `targeting` object in full, deep-copy it, overlay only the
requested key(s), POST the complete merged object back, then read it back. If the GET
fails, that ad set is skipped with an error row — never posted to — because a partial
object is exactly the trap this script exists to avoid.

Extending the flag surface: add one `ap.add_argument("--flag-name", dest="dest_name")`
call in main() and one `"dest_name": ("targeting_field_name", parser)` entry in
SCALAR_FIELDS. cmd_edit.py's TARGETING_SCALAR_FLAGS needs the matching dest name so the
agent-facing `metaops edit targeting` wrapper passes it through.

API facts verified against the installed facebook_business SDK, 26.0.1 (same source
cmd_edit.py cites, not developers.facebook.com):
  · `Targeting.Field.user_os` exists; `AdSet.api_update` param_types type it
    `'list<string>'` — a comma-separated OS list, not a single string.
  · `AdSet.api_update` param_types include `'targeting': 'Targeting'`, confirming the
    whole-object POST target this script writes to.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

import edit
import graph

TARGETING_CONFIRM = "TARGETING"


def _csv_list(raw: str) -> list[str]:
    return [v.strip() for v in raw.split(",") if v.strip()]


# CLI dest name -> (Targeting object field name, value parser).
SCALAR_FIELDS: dict[str, tuple[str, Callable[[str], object]]] = {
    "user_os": ("user_os", _csv_list),
    "publisher_platforms": ("publisher_platforms", _csv_list),
    "facebook_positions": ("facebook_positions", _csv_list),
    "instagram_positions": ("instagram_positions", _csv_list),
}


def merge_targeting(current: dict, changes: dict) -> dict:
    """Deep-copy `current` and overlay only `changes` — every other key survives untouched."""
    merged = json.loads(json.dumps(current))
    merged.update(changes)
    # Narrowing publisher_platforms must drop the position lists of removed platforms,
    # or Meta rejects positions for a platform that is no longer targeted.
    if "publisher_platforms" in changes:
        keep = set(changes["publisher_platforms"])
        for plat in ("facebook", "instagram", "messenger", "audience_network"):
            if plat not in keep:
                merged.pop(f"{plat}_positions", None)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ids", help="comma-separated ad set ids")
    src.add_argument("--state", help="launch.py state file (adset ids)")
    src.add_argument("--account", help="act_<id> with --all")
    ap.add_argument("--all", action="store_true", help="with --account: every ACTIVE ad set")
    ap.add_argument("--user-os", dest="user_os", help="comma-separated OS list, e.g. iOS,Android")
    ap.add_argument("--publisher-platforms", dest="publisher_platforms", help="e.g. facebook,instagram")
    ap.add_argument("--facebook-positions", dest="facebook_positions", help="e.g. feed,story,facebook_reels")
    ap.add_argument("--instagram-positions", dest="instagram_positions", help="e.g. stream,story,reels")
    ap.add_argument("--confirm", help=f"literal {TARGETING_CONFIRM}, required (including --dry-run)")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    graph.require_write_authority(
        "POST", f"{graph.normalize_account(args.account)}/objects" if args.account else "object",
    )

    changes: dict = {}
    for dest, (field, parse) in SCALAR_FIELDS.items():
        raw = getattr(args, dest)
        if raw is not None:
            changes[field] = parse(raw)
    if "publisher_platforms" in changes and "instagram" not in changes["publisher_platforms"]:
        sys.exit("publisher_platforms must include instagram (operator rule)")
    if not changes:
        sys.exit("nothing to change — pass at least one scalar targeting flag (currently: --user-os)")
    if args.confirm != TARGETING_CONFIRM:
        sys.exit(f"targeting changes reach: pass --confirm {TARGETING_CONFIRM} (--dry-run too).")

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    elif args.state:
        ids = edit.ids_from_state(args.state, "adset")
    else:
        if not args.all:
            sys.exit("--account needs --all")
        ids = edit.ids_from_account(graph.normalize_account(args.account), "adset")
    if not ids:
        sys.exit("no ids")

    bad = 0
    results: list[dict] = []
    for oid in ids:
        try:
            obj = graph.get(oid, params={"fields": "name,targeting,account_id"}, context=f"read {oid}")
        except graph.GraphError as e:
            print(f"  x {oid}: GET failed — refusing to POST a partial targeting object: {e}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": f"GET failed: {e}"})
            continue
        if args.expected_account:
            actual = obj.get("account_id")
            if not actual or graph.normalize_account(actual) != graph.normalize_account(args.expected_account):
                print(
                    f"  x {oid}: belongs to {actual or '?'} not {args.expected_account}; refusing cross-profile edit",
                    file=sys.stderr,
                )
                bad += 1
                results.append({"id": oid, "ok": False, "error": "object outside profile account"})
                continue
        current = obj.get("targeting")
        if not isinstance(current, dict):
            print(f"  x {oid} {obj.get('name')}: no readable targeting object — refusing to post one",
                  file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": "no readable targeting object"})
            continue

        before = current
        after = merge_targeting(current, changes)
        if args.dry_run:
            print(f"  would POST /{oid} targeting (full read-modify-write object; fields changed: "
                  f"{', '.join(sorted(changes))})")
            print(f"    before: {json.dumps(before, sort_keys=True)}")
            print(f"    after:  {json.dumps(after, sort_keys=True)}")
            results.append({"id": oid, "ok": True, "dry_run": True, "before": before, "after": after})
            continue

        try:
            graph.post(oid, {"targeting": after}, context=f"targeting {oid}", idempotent=True)
            back = graph.get(oid, params={"fields": "name,targeting"}, context="readback")
            print(f"  ✓ {oid} {back.get('name')}: targeting updated ({', '.join(sorted(changes))})")
            results.append({
                "id": oid, "ok": True, "name": back.get("name"), "targeting": back.get("targeting"),
            })
        except graph.GraphError as e:
            print(f"  x {oid}: {e}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": str(e)})

    print(json.dumps({
        "schema": "edit_targeting.result/v1", "dry_run": args.dry_run, "ok": bad == 0,
        "count": len(ids), "failed": bad, "changed_fields": sorted(changes), "results": results,
    }, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
