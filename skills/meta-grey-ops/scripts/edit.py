#!/usr/bin/env python3
"""Mass status / budget edits with the guards a human forgets at 22:00.

    python3 edit.py --ids 111,222 --status PAUSED
    python3 edit.py --state .metaops/run.json --level adset --status PAUSED
    python3 edit.py --ids 333 --budget-minor 6000                # +20% cap unless --force-step
    python3 edit.py --ids 333 --budget-pct +20
    python3 edit.py --ids 333 --budget-minor 12000 --force-step  # you accept the learning reset
    python3 edit.py --ids 444,555 --rename-prefix "J41-16|"
    python3 edit.py --account act_1 --level campaign --status PAUSED --all   # kill switch

Guards (04 → Spend warm-up, Metric levers):
  · a budget change > +20% or < -20% per edit is refused without --force-step — that is the
    practitioner threshold for re-entering learning, and a +200% evening raise on a fresh
    account produced an account-wide delivery freeze (field 2026-08-31)
  · a budget raise in the last 2 hours of the account's day is refused without --force-step
    (Meta's own troubleshooting doc: a doubled budget at 22:00 has 2 h to spend)
  · every edit is read back; the printed value is what Graph holds, not what was sent
  · edits are idempotent, so transport retries are allowed
  · budget edits go to whichever level owns the budget; a CBO ad set has none and Graph says so

This does not activate PAUSED launches — activate.py does, behind --confirm SPEND. Setting
--status ACTIVE here on an object that never ran asks for the same confirmation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import graph

STEP_LIMIT = 0.20


def ids_from_state(path: str, level: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        objects = json.load(fh)["objects"]
    prefix = {"campaign": "campaign", "adset": "adset[", "ad": "ad["}[level]
    return [v for k, v in objects.items() if k == prefix or k.startswith(prefix)]


# Everything that spends now or will spend without another human action: a fresh launch
# sits in IN_PROCESS / PENDING_REVIEW for minutes to hours before it reads ACTIVE, and a
# child under a paused parent resumes the moment the parent does. `--all` exists for the
# kill switch, so ACTIVE alone misses exactly the launches it is usually aimed at. Every
# value is in the effective_status enum of the ad-account campaigns/adsets/ads edges.
LIVE_EFFECTIVE_STATUSES = [
    "ACTIVE", "IN_PROCESS", "PENDING_REVIEW", "PREAPPROVED", "WITH_ISSUES",
    "CAMPAIGN_PAUSED", "ADSET_PAUSED",
]


def ids_from_account(account: str, level: str) -> list[str]:
    edge = {"campaign": "campaigns", "adset": "adsets", "ad": "ads"}[level]
    out, path, params = [], f"{account}/{edge}", {
        "fields": "id", "limit": 500,
        "effective_status": json.dumps(LIVE_EFFECTIVE_STATUSES)}
    while True:
        resp = graph.get(path, params=params, context=edge)
        out.extend(o["id"] for o in resp.get("data", []))
        params = graph.next_page_params(resp, params)
        if params is None:
            return out


def account_hour(obj: dict) -> int | None:
    acct = obj.get("account_id")
    if not acct:
        return None
    a = graph.get(f"act_{acct}", params={"fields": "timezone_offset_hours_utc"}, context="tz")
    off = a.get("timezone_offset_hours_utc")
    if off is None:
        return None
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=float(off))).hour


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ids", help="comma-separated object ids")
    src.add_argument("--state", help="launch.py state file")
    src.add_argument("--account", help="act_<id> with --all")
    ap.add_argument("--level", choices=["campaign", "adset", "ad"], help="needed with --state / --account")
    ap.add_argument("--all", action="store_true",
                    help="with --account: every live object at --level (ACTIVE, in review, "
                         "WITH_ISSUES, or under a paused parent)")
    ap.add_argument("--status", choices=["ACTIVE", "PAUSED", "ARCHIVED", "DELETED"])
    ap.add_argument("--budget-minor", type=int, help="new daily_budget, integer minor units")
    ap.add_argument("--budget-pct", help="relative change, e.g. +20 or -15")
    ap.add_argument("--rename-prefix")
    ap.add_argument("--rename-suffix")
    ap.add_argument("--force-step", action="store_true", help="bypass the 20%% / late-day guards")
    ap.add_argument("--confirm", help="literal ACTIVATE when setting --status ACTIVE")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    graph.require_write_authority(
        "POST",
        f"{graph.normalize_account(args.account)}/objects" if args.account else "object",
    )

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    elif args.state:
        if not args.level:
            sys.exit("--state needs --level")
        ids = ids_from_state(args.state, args.level)
    else:
        if not (args.level and args.all):
            sys.exit("--account needs --level and --all")
        ids = ids_from_account(graph.normalize_account(args.account), args.level)
    if not ids:
        sys.exit("no ids")
    if not any([args.status, args.budget_minor is not None, args.budget_pct is not None, args.rename_prefix, args.rename_suffix]):
        sys.exit("nothing to do")
    if args.status == "ACTIVE" and args.confirm != "ACTIVATE":
        sys.exit("--status ACTIVE is spend-producing: pass --confirm ACTIVATE (or use activate.py "
                 "for a fresh launch, which also refreshes start_time).")
    if args.status == "PAUSED" and args.confirm != "PAUSE":
        sys.exit("--status PAUSED changes delivery: pass --confirm PAUSE.")
    if args.status == "DELETED" and args.confirm != "DELETE":
        sys.exit("--status DELETED is irreversible: pass --confirm DELETE.")
    if args.status == "ARCHIVED" and args.confirm != "ARCHIVE":
        sys.exit("--status ARCHIVED is destructive: pass --confirm ARCHIVE.")

    bad = 0
    results: list[dict] = []
    for oid in ids:
        try:
            obj = graph.get(oid, params={"fields": "name,status,daily_budget,lifetime_budget,account_id,effective_status"},
                            context=f"read {oid}")
        except graph.GraphError as e:
            # Ads have no budget fields (#100 nonexisting field); re-read without them.
            if e.code != 100:
                raise
            obj = graph.get(oid, params={"fields": "name,status,account_id,effective_status"},
                            context=f"read {oid}")
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
        payload: dict = {}
        if args.status == "DELETED":
            # Meta keeps insights of deleted objects (account totals, "deleted" filter), so spend
            # is not a reason to refuse; just report it.
            ins = graph.get(f"{oid}/insights", params={"fields": "spend", "date_preset": "maximum"},
                            context=f"spend {oid}").get("data") or []
            spent = sum(float(r.get("spend") or 0) for r in ins)
            if spent > 0:
                print(f"  ! {oid}: deleting object with {spent:.2f} lifetime spend", file=sys.stderr)
        if args.status:
            payload["status"] = args.status
        if args.rename_prefix or args.rename_suffix:
            payload["name"] = f"{args.rename_prefix or ''}{obj.get('name', '')}{args.rename_suffix or ''}"
        if args.budget_minor is not None or args.budget_pct is not None:
            cur = int(obj.get("daily_budget") or 0)
            if not cur:
                print(f"  x {oid} {obj.get('name')}: no daily_budget on this level (CBO child or lifetime "
                      f"budget) — edit the level that owns it", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": "no daily_budget on this level"})
                continue
            if args.budget_pct:
                new = round(cur * (1 + float(args.budget_pct.replace('+', '')) / 100))
            else:
                new = args.budget_minor
            step = (new - cur) / cur
            if abs(step) > STEP_LIMIT and not args.force_step:
                print(f"  x {oid} {obj.get('name')}: {cur} → {new} is {step:+.0%}; > ±20% per edit "
                      f"re-enters learning and on fresh accounts has frozen delivery. Step in ≤20% "
                      f"moves 48-72 h apart, or --force-step.", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": f"budget step {step:+.0%} exceeds ±20%"})
                continue
            hour = account_hour(obj)
            if step > 0 and hour is not None and hour >= 22 and not args.force_step:
                print(f"  x {oid} {obj.get('name')}: raising at {hour:02d}:00 account time leaves "
                      f"<2 h to spend it. Raise in the morning, or --force-step.", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": "budget raise in last 2h of account day"})
                continue
            payload["daily_budget"] = int(new)
        if args.dry_run:
            print(f"  would POST /{oid} {json.dumps(payload)}  (now: status={obj.get('status')} "
                  f"budget={obj.get('daily_budget')})")
            results.append({"id": oid, "ok": True, "dry_run": True, "payload": payload})
            continue
        try:
            graph.post(oid, payload, context=f"edit {oid}", idempotent=True)
            back_fields = "name,status,effective_status" if "daily_budget" not in obj else "name,status,daily_budget,effective_status"
            back = graph.get(oid, params={"fields": back_fields}, context="readback")
            print(f"  ✓ {oid} {back.get('name')}: status={back.get('status')} "
                  f"effective={back.get('effective_status')} daily_budget={back.get('daily_budget')}")
            results.append({
                "id": oid, "ok": True, "name": back.get("name"), "status": back.get("status"),
                "effective_status": back.get("effective_status"), "daily_budget": back.get("daily_budget"),
            })
        except graph.GraphError as e:
            print(f"  x {oid}: {e}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": str(e)})
    print(json.dumps({"schema": "edit.result/v1", "dry_run": args.dry_run, "ok": bad == 0,
                      "count": len(ids), "failed": bad, "results": results}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
