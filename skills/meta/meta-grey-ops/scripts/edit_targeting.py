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
SCALAR_FIELDS. A dotted field name ("geo_locations.regions", "targeting_automation.
advantage_audience") overlays one key INSIDE a nested object and keeps its siblings (the one
exception: --geo-regions, see below). cmd_edit.py's TARGETING_SCALAR_FLAGS needs the matching
dest name so the agent-facing `metaops edit targeting` wrapper passes it through.

Guards:
  · an empty value (`--user-os ""`, `--genders ""`) is refused, never turned into []
  · --geo-regions keeps ONLY geo_locations.regions and .location_types (a WHITELIST: every other
    geo key - countries, cities, zips, custom_locations, ... - is dropped) and is refused
    together with --all: one region list would overwrite the geography of every active ad set
  · Advantage+ audience (targeting_automation.advantage_audience = 1) makes Meta clamp age_min
    to 25 and force age_max to 65, so an age range narrower than 25..65 under it is refused;
    turn Advantage+ off (--advantage-audience 0) or drop the age flags
  · after the POST the read-back is compared with what was asked; any field that did not stick
    is listed under `not_applied` and the row is not ok
  · --all covers ACTIVE ad sets only (effective_status ACTIVE)

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
    out = [v.strip() for v in raw.split(",") if v.strip()]
    if not out:
        sys.exit(f"expected a non-empty comma-separated list, got {raw!r} "
                 f"(an empty value would erase the field; refusing)")
    return out


def _int_in(lo: int, hi: int) -> Callable[[str], int]:
    def parse(raw: str) -> int:
        try:
            value = int(raw)
        except ValueError:
            sys.exit(f"expected an integer, got {raw!r}")
        if not lo <= value <= hi:
            sys.exit(f"{value} is outside {lo}..{hi}")
        return value
    return parse


def _int_list(raw: str) -> list[int]:
    values = _csv_list(raw)
    try:
        return [int(v) for v in values]
    except ValueError:
        sys.exit(f"expected comma-separated integers, got {raw!r}")


def _regions(raw: str) -> list[dict]:
    keys = _csv_list(raw)
    if not all(k.isdigit() for k in keys):
        sys.exit(f"--geo-regions takes numeric Meta region keys (e.g. 3879 = Oklahoma), got {raw!r}")
    return [{"key": k} for k in keys]


# CLI dest name -> (Targeting object field name, value parser).
SCALAR_FIELDS: dict[str, tuple[str, Callable[[str], object]]] = {
    "user_os": ("user_os", _csv_list),
    "publisher_platforms": ("publisher_platforms", _csv_list),
    "facebook_positions": ("facebook_positions", _csv_list),
    "instagram_positions": ("instagram_positions", _csv_list),
    "device_platforms": ("device_platforms", _csv_list),
    "age_min": ("age_min", _int_in(13, 65)),
    "age_max": ("age_max", _int_in(13, 65)),
    "genders": ("genders", _int_list),
    "geo_regions": ("geo_locations.regions", _regions),
    "advantage_audience": ("targeting_automation.advantage_audience", _int_in(0, 1)),
}
# When regions are set, geo_locations is rebuilt from a WHITELIST: only these keys survive. A
# leftover country/city/zip/custom_location/geo_market/place beside the new regions would widen the
# audience past what the operator asked for, and a blacklist of "known siblings" silently lets any
# key Meta adds later through.
GEO_KEPT_WITH_REGIONS = ("regions", "location_types")


def _fit_age_range(merged: dict) -> None:
    """Advantage+ audience ad sets carry a derived `age_range` (the suggestion window) next to the hard
    age_min/age_max. Live validate_only 29/09: age_min 21 -> 25 with age_range still [21, 65] is rejected
    (code 100/1359201 "invalid age range"), so pull the window inside the new bounds, or drop it when
    nothing is left of it."""
    window = merged.get("age_range")
    if not (isinstance(window, list) and len(window) == 2):
        return
    try:
        lo, hi = int(window[0]), int(window[1])
        floor = int(merged["age_min"]) if merged.get("age_min") is not None else lo
        ceil = int(merged["age_max"]) if merged.get("age_max") is not None else hi
    except (TypeError, ValueError):
        merged.pop("age_range", None)
        return
    lo, hi = max(lo, floor), min(hi, ceil)
    if lo > hi:
        merged.pop("age_range", None)
    else:
        merged["age_range"] = [lo, hi]


def merge_targeting(current: dict, changes: dict) -> dict:
    """Deep-copy `current` and overlay only `changes` — every other key survives untouched."""
    merged = json.loads(json.dumps(current))
    for field, value in changes.items():
        if "." in field:
            head, tail = field.split(".", 1)
            node = merged.get(head)
            if not isinstance(node, dict):
                node = {}
            node[tail] = value
            merged[head] = node
        else:
            merged[field] = value
    if {"age_min", "age_max"} & set(changes):
        _fit_age_range(merged)
    if "geo_locations.regions" in changes:
        merged["geo_locations"] = {k: v for k, v in merged["geo_locations"].items() if k in GEO_KEPT_WITH_REGIONS}
    # Narrowing publisher_platforms must drop the position lists of removed platforms,
    # or Meta rejects positions for a platform that is no longer targeted.
    if "publisher_platforms" in changes:
        keep = set(changes["publisher_platforms"])
        for plat in ("facebook", "instagram", "messenger", "audience_network"):
            if plat not in keep:
                merged.pop(f"{plat}_positions", None)
    return merged


ADVANTAGE_FIELD = "targeting_automation.advantage_audience"
ADVANTAGE_AGE_MIN_CAP = 25   # Advantage+ audience clamps age_min down to at most 25 ...
ADVANTAGE_AGE_MAX_FLOOR = 65  # ... and forces age_max up to 65


def _dig(obj: dict, dotted: str):
    """Value at a dotted path, or None when any hop is missing."""
    node = obj
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _comparable(value):
    """Order- and type-insensitive form for comparing what was sent with what Graph returns:
    lists compare as sets, numbers and numeric strings match, region objects compare by key
    (Graph adds name / country / supports_region to them)."""
    if isinstance(value, list):
        return sorted(json.dumps(_comparable(v), sort_keys=True) for v in value)
    if isinstance(value, dict):
        if "key" in value:
            return str(value["key"])
        return {k: _comparable(v) for k, v in sorted(value.items())}
    return None if value is None else str(value).lower()


def _comparable_field(field: str, value):
    """`genders` missing, [] and [1, 2] all mean "all genders" to Graph."""
    if field == "genders" and (value is None or sorted(str(v) for v in value) in ([], ["1", "2"])):
        return "all"
    return _comparable(value)


def advantage_conflict(after: dict) -> str | None:
    """Why `after` cannot hold under Advantage+ audience, or None. Meta silently clamps age_min to
    25 and forces age_max to 65 while advantage_audience is 1, so a narrower range is never applied."""
    if _dig(after, ADVANTAGE_FIELD) not in (1, "1", True):
        return None
    age_min, age_max = after.get("age_min"), after.get("age_max")
    clash = []
    if age_min is not None and int(age_min) > ADVANTAGE_AGE_MIN_CAP:
        clash.append(f"age_min={age_min} (Meta clamps it to {ADVANTAGE_AGE_MIN_CAP})")
    if age_max is not None and int(age_max) < ADVANTAGE_AGE_MAX_FLOOR:
        clash.append(f"age_max={age_max} (Meta forces it to {ADVANTAGE_AGE_MAX_FLOOR})")
    if not clash:
        return None
    return ("Advantage+ audience is on (targeting_automation.advantage_audience=1) but the result would "
            "carry " + " and ".join(clash) + ". Choose: --advantage-audience 0 to keep this age range, "
            "or keep Advantage+ and use age_min<=25 / age_max=65.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ids", help="comma-separated ad set ids")
    src.add_argument("--state", help="launch.py state file (adset ids)")
    src.add_argument("--account", help="act_<id> with --all")
    ap.add_argument("--all", action="store_true",
                    help="with --account: every ACTIVE ad set (effective_status ACTIVE only; not with --geo-regions)")
    ap.add_argument("--user-os", dest="user_os", help="comma-separated OS list, e.g. iOS,Android")
    ap.add_argument("--publisher-platforms", dest="publisher_platforms", help="e.g. facebook,instagram")
    ap.add_argument("--facebook-positions", dest="facebook_positions", help="e.g. feed,story,facebook_reels")
    ap.add_argument("--instagram-positions", dest="instagram_positions", help="e.g. stream,story,reels")
    ap.add_argument("--device-platforms", dest="device_platforms", help="e.g. mobile or mobile,desktop")
    ap.add_argument("--age-min", dest="age_min", help="minimum age, 13..65")
    ap.add_argument("--age-max", dest="age_max", help="maximum age, 13..65")
    ap.add_argument("--genders", help="1=male, 2=female, comma-separated; omit to keep all")
    ap.add_argument("--geo-regions", dest="geo_regions",
                    help="numeric Meta region keys, e.g. 3879 (Oklahoma); replaces the whole geo selection "
                         "(keeps only regions + location_types); refused with --all")
    ap.add_argument("--advantage-audience", dest="advantage_audience",
                    help="0 or 1 (1 clamps age_min to <=25 and forces age_max to 65)")
    ap.add_argument("--confirm", help=f"literal {TARGETING_CONFIRM}, required (including --dry-run)")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate-only", action="store_true",
                    help="like --dry-run, and also POST each targeting with execution_options=[validate_only]: "
                         "Meta checks it and applies nothing")
    args = ap.parse_args()
    if args.validate_only:
        args.dry_run = True

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
        sys.exit("nothing to change — pass at least one targeting flag (see --help)")
    if args.geo_regions is not None and args.all:
        sys.exit("--geo-regions cannot be combined with --all: one region list would overwrite the "
                 "geography of every active ad set. Pass explicit --ids.")
    if args.confirm != TARGETING_CONFIRM:
        sys.exit(f"targeting changes reach: pass --confirm {TARGETING_CONFIRM} (--dry-run too).")

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    elif args.state:
        ids = edit.ids_from_state(args.state, "adset")
    else:
        if not args.all:
            sys.exit("--account needs --all")
        ids = edit.ids_from_account(graph.normalize_account(args.account), "adset",
                                    statuses=edit.ACTIVE_ONLY_STATUSES)
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
        touches_audience = bool({"age_min", "age_max", ADVANTAGE_FIELD} & set(changes))
        conflict = advantage_conflict(after) if touches_audience else None
        if conflict:
            print(f"  x {oid} {obj.get('name')}: {conflict}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": conflict})
            continue
        if args.dry_run:
            print(f"  would POST /{oid} targeting (full read-modify-write object; fields changed: "
                  f"{', '.join(sorted(changes))})")
            print(f"    before: {json.dumps(before, sort_keys=True)}")
            print(f"    after:  {json.dumps(after, sort_keys=True)}")
            row = {"id": oid, "ok": True, "dry_run": True, "before": before, "after": after}
            if args.validate_only:
                try:
                    graph.post(oid, {"targeting": after, "execution_options": ["validate_only"]},
                               context=f"validate targeting {oid}", idempotent=True)
                    row["validated"] = True
                    print(f"  ✓ {oid}: Meta accepts this targeting (validate_only, nothing applied)")
                except graph.GraphError as e:
                    print(f"  x {oid}: Meta rejects this targeting: {e}", file=sys.stderr)
                    row.update({"ok": False, "validated": False, "error": str(e)})
                    bad += 1
            results.append(row)
            continue

        try:
            graph.post(oid, {"targeting": after}, context=f"targeting {oid}", idempotent=True)
            back = graph.get(oid, params={"fields": "name,targeting"}, context="readback")
            back_targeting = back.get("targeting") if isinstance(back.get("targeting"), dict) else {}
            not_applied = {}
            for field in sorted(changes):
                wanted, got = _dig(after, field), _dig(back_targeting, field)
                if _comparable_field(field, wanted) != _comparable_field(field, got):
                    not_applied[field] = {"requested": wanted, "actual": got}
            row = {"id": oid, "ok": not not_applied, "name": back.get("name"), "targeting": back.get("targeting")}
            if not_applied:
                print(f"  x {oid} {back.get('name')}: POST accepted but Graph did not keep: "
                      f"{', '.join(not_applied)} (requested vs actual in the result row)", file=sys.stderr)
                row["not_applied"] = list(not_applied)
                row["not_applied_detail"] = not_applied
                row["error"] = "fields not applied: " + ", ".join(not_applied)
                bad += 1
            else:
                print(f"  ✓ {oid} {back.get('name')}: targeting updated ({', '.join(sorted(changes))})")
            results.append(row)
        except graph.GraphError as e:
            print(f"  x {oid}: {e}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": str(e)})

    print(json.dumps({
        "schema": "edit_targeting.result/v1", "dry_run": args.dry_run, "validate_only": args.validate_only, "ok": bad == 0,
        "count": len(ids), "failed": bad, "changed_fields": sorted(changes), "results": results,
    }, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
