#!/usr/bin/env python3
"""Mass status / budget edits with the guards a human forgets at 22:00.

    python3 edit.py --ids 111,222 --status PAUSED
    python3 edit.py --state .metaops/run.json --level adset --status PAUSED
    python3 edit.py --ids 333 --budget-minor 6000                # +20% cap unless --force-step
    python3 edit.py --ids 333 --budget-pct +20
    python3 edit.py --ids 333 --budget-minor 12000 --force-step  # you accept the learning reset
    python3 edit.py --ids 444,555 --rename-prefix "J41-16|"
    python3 edit.py --ids 444 --name "EN0039-<buyer>-1"                       # exact new name, one id
    python3 edit.py --ids 444,555 --set 444="EN0039-<buyer>-1" --set 555="EN0040-<buyer>-1"
    python3 edit.py --ids 666 --bid-minor 15000                            # ad-set bid/cost cap
    python3 edit.py --ids 666 --start-time 2026-10-01T08:00:00-07:00 --end-time 2026-10-08T00:00:00-07:00
    python3 edit.py --account act_1 --level campaign --status PAUSED --all   # kill switch

Guards (04 → Spend warm-up, Metric levers):
  · a budget RAISE above +20% per edit is refused without --force-step — that is the
    practitioner threshold for re-entering learning, and a +200% evening raise on a fresh
    account produced an account-wide delivery freeze (field 2026-08-31). The comparison is
    rounded to 0.1%, so +20% on a budget that does not divide evenly (10368 -> 12442 is
    +20.004%) is not refused for integer rounding. A CUT of any size is allowed: it only
    lowers spend and is never subject to the +20% or the late-day guard
  · a budget raise in the last 2 hours of the account's day is refused without --force-step
    (Meta's own troubleshooting doc: a doubled budget at 22:00 has 2 h to spend)
  · every edit is read back; the printed value is what Graph holds, not what was sent
  · edits are idempotent, so transport retries are allowed
  · budget edits go to whichever level owns the budget; a CBO ad set has none and Graph says so

  · --name / --set rename to an EXACT string (400 chars max); no review impact. Every --set
    id must be among the resolved ids (a stray id fails the run instead of silently doing nothing)
  · --bid-minor / --start-time / --end-time are AD-SET fields: each object is probed for
    optimization_goal first and anything else (campaign, ad) is refused before any POST.
    (A campaign's end is `stop_time`; this tool does not edit it.)
  · --start-time / --end-time need a UTC offset; an end_time in the past would stop delivery
    and is refused (pause instead)
  · --budget-pct must be a number > -100 (checked before any object is touched)

This does not activate PAUSED launches — activate.py does, behind --confirm SPEND. Setting
--status ACTIVE here on an object that never ran asks for the same confirmation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
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
# Content edits (targeting, ad copy, tags) must not touch anything that is not delivering right
# now: a fresh launch in review or a child under a paused parent is edited on purpose, by id.
ACTIVE_ONLY_STATUSES = ["ACTIVE"]


def ids_from_account(account: str, level: str, statuses: list[str] | None = None) -> list[str]:
    """Every object at `level` whose effective_status is in `statuses`. Default is the wide
    LIVE list (kill switch); pass ACTIVE_ONLY_STATUSES for edits that need ACTIVE objects only."""
    edge = {"campaign": "campaigns", "adset": "adsets", "ad": "ads"}[level]
    out, path, params = [], f"{account}/{edge}", {
        "fields": "id", "limit": 500,
        "effective_status": json.dumps(list(statuses or LIVE_EFFECTIVE_STATUSES))}
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


NAME_LIMIT = 400


def parse_name_map(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        oid, sep, name = pair.partition("=")
        oid, name = oid.strip(), name.strip()
        if not sep or not oid.isdigit() or not name:
            sys.exit(f"--set expects NUMERIC_ID=NEW_NAME, got {pair!r}")
        if len(name) > NAME_LIMIT:
            sys.exit(f"--set {oid}: name is {len(name)} chars; Meta allows {NAME_LIMIT}")
        if oid in out:
            sys.exit(f"--set {oid} given twice; one exact name per id")
        out[oid] = name
    return out


def parse_budget_pct(raw: str) -> float:
    """--budget-pct as a percent number (+20, -15, 12.5). Empty / non-numeric / <= -100 exit."""
    try:
        value = float(str(raw).strip())
    except ValueError:
        sys.exit(f"--budget-pct must be a number such as +20 or -15, got {raw!r}")
    if not math.isfinite(value) or value <= -100:
        sys.exit(f"--budget-pct must be a finite number above -100, got {raw!r}")
    return value


def parse_iso(flag: str, raw: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        sys.exit(f"{flag} must be ISO-8601, e.g. 2026-10-01T08:00:00-07:00 (got {raw!r})")
    if parsed.tzinfo is None:
        sys.exit(f"{flag} needs a UTC offset (an offsetless time is read in the wrong zone): got {raw!r}")
    return parsed


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
    ap.add_argument("--budget-pct", help="relative change in percent, e.g. +20 or -15 (a cut of any size is allowed)")
    ap.add_argument("--rename-prefix")
    ap.add_argument("--rename-suffix")
    ap.add_argument("--name", help="exact new name (needs exactly one id)")
    ap.add_argument("--set", dest="set_names", action="append", default=[], metavar="ID=NAME",
                    help="exact rename of one id, repeatable")
    ap.add_argument("--bid-minor", type=int, help="new bid_amount (bid/cost cap) on ad sets only, integer minor units")
    ap.add_argument("--start-time", help="ad-set start_time (ad sets only), ISO-8601 with UTC offset")
    ap.add_argument("--end-time", help="ad-set end_time (ad sets only), ISO-8601 with UTC offset")
    ap.add_argument("--force-step", action="store_true",
                    help="bypass the +20%% raise cap and the late-day raise guard (cuts are never guarded)")
    ap.add_argument("--confirm", help="literal ACTIVATE when setting --status ACTIVE")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate-only", action="store_true",
                    help="like --dry-run, and also POST each payload with execution_options=[validate_only]: "
                         "Meta checks it and applies nothing")
    args = ap.parse_args()
    if args.validate_only:
        args.dry_run = True

    graph.require_write_authority(
        "POST",
        f"{graph.normalize_account(args.account)}/objects" if args.account else "object",
    )

    # Argument-only validation first: nothing below may need the network, and nothing may be
    # half-applied because a later flag turned out to be malformed.
    budget_pct = parse_budget_pct(args.budget_pct) if args.budget_pct is not None else None
    if args.budget_minor is not None and args.budget_minor <= 0:
        sys.exit("--budget-minor must be a positive integer (minor units)")
    if args.budget_minor is not None and budget_pct is not None:
        sys.exit("pick one budget form: --budget-minor or --budget-pct")

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
    ids = list(dict.fromkeys(ids))  # a repeated id would take the same raise twice
    if not ids:
        sys.exit("no ids")
    name_map = parse_name_map(args.set_names)
    if name_map:
        stray = [oid for oid in name_map if oid not in ids]
        if stray:
            sys.exit(f"--set id(s) {', '.join(stray)} are not among the resolved ids ({', '.join(ids)}); "
                     f"nothing was changed")
    if args.name is not None:
        if len(ids) != 1:
            sys.exit("--name renames exactly one id; use --set ID=NAME for several")
        if not args.name.strip():
            sys.exit("--name is empty")
        if len(args.name) > NAME_LIMIT:
            sys.exit(f"--name is {len(args.name)} chars; Meta allows {NAME_LIMIT}")
    if sum([args.name is not None, bool(name_map), bool(args.rename_prefix or args.rename_suffix)]) > 1:
        sys.exit("pick one rename form: --name, --set, or --rename-prefix/--rename-suffix")
    start_dt = parse_iso("--start-time", args.start_time) if args.start_time is not None else None
    end_dt = parse_iso("--end-time", args.end_time) if args.end_time is not None else None
    if end_dt and end_dt <= dt.datetime.now(dt.timezone.utc):
        sys.exit("--end-time is in the past: that stops delivery. Use --status PAUSED (--confirm PAUSE) instead.")
    if start_dt and end_dt and end_dt <= start_dt:
        sys.exit("--end-time must be after --start-time")
    if args.bid_minor is not None and args.bid_minor <= 0:
        sys.exit("--bid-minor must be a positive integer (minor units)")
    if not any([args.status, args.budget_minor is not None, budget_pct is not None, args.rename_prefix,
                args.rename_suffix, args.name is not None, name_map, args.bid_minor is not None,
                start_dt, end_dt]):
        sys.exit("nothing to do")
    if name_map and not any([args.status, args.budget_minor is not None, budget_pct is not None,
                             args.bid_minor is not None, start_dt, end_dt]):
        unnamed = [oid for oid in ids if oid not in name_map]
        if unnamed:
            sys.exit(f"--set names {len(name_map)} id(s) but {', '.join(unnamed)} have no name and no other "
                     f"change was asked for; pass exactly the ids you rename")
    adset_only = args.bid_minor is not None or start_dt is not None or end_dt is not None
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
                print(f"  x {oid}: cannot read this object ({e}); nothing sent for this id", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": f"read failed: {e}"})
                continue
            try:
                obj = graph.get(oid, params={"fields": "name,status,account_id,effective_status"},
                                context=f"read {oid}")
            except graph.GraphError as e2:
                print(f"  x {oid}: cannot read this object ({e2}); nothing sent for this id", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": f"read failed: {e2}"})
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
        cur_bid = None
        if adset_only:
            # bid_amount / start_time / end_time are AD-SET fields. optimization_goal exists on ad
            # sets only: campaigns and ads answer #100 (nonexisting field). Refuse those levels
            # here, before any POST, instead of letting Graph reject (or misapply) the write.
            probe_fields = "optimization_goal,bid_amount" if args.bid_minor is not None else "optimization_goal"
            try:
                probe = graph.get(oid, params={"fields": probe_fields}, context=f"adset probe {oid}")
            except graph.GraphError as e:
                if e.code != 100:
                    raise
                what = "/".join(f for f, on in (("--bid-minor", args.bid_minor is not None),
                                                ("--start-time", start_dt is not None),
                                                ("--end-time", end_dt is not None)) if on)
                print(f"  x {oid} {obj.get('name')}: not an ad set (no optimization_goal) — {what} apply to "
                      f"ad sets only; nothing sent for this id", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": f"{what} apply to ad sets only; this is not an ad set"})
                continue
            cur_bid = probe.get("bid_amount")
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
        if oid in name_map:
            payload["name"] = name_map[oid]
        elif args.name is not None:
            payload["name"] = args.name.strip()
        elif args.rename_prefix or args.rename_suffix:
            payload["name"] = f"{args.rename_prefix or ''}{obj.get('name', '')}{args.rename_suffix or ''}"
        if args.bid_minor is not None:
            if cur_bid is None:
                print(f"  ! {oid} {obj.get('name')}: ad set has no bid_amount now (lowest cost without a cap?); "
                      f"Graph decides whether the cap is accepted", file=sys.stderr)
            payload["bid_amount"] = int(args.bid_minor)
        if start_dt or end_dt:
            if start_dt:
                payload["start_time"] = start_dt.isoformat()
            if end_dt:
                payload["end_time"] = end_dt.isoformat()
        if args.budget_minor is not None or budget_pct is not None:
            cur = int(obj.get("daily_budget") or 0)
            if not cur:
                print(f"  x {oid} {obj.get('name')}: no daily_budget on this level (CBO child or lifetime "
                      f"budget) — edit the level that owns it", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": "no daily_budget on this level"})
                continue
            if budget_pct is not None:
                exact = cur * (1 + budget_pct / 100)
                new = round(exact)
                if budget_pct > 0 and round((new - cur) / cur, 3) > round(budget_pct / 100, 3):
                    # Integer rounding alone must not push a step past what was asked (small
                    # budgets: 104 * 1.2 = 124.8 -> 125 is +20.2%); take the lower integer.
                    new = math.floor(exact + 1e-9)
            else:
                new = args.budget_minor
            step = (new - cur) / cur
            if new < 1:
                print(f"  x {oid} {obj.get('name')}: {cur} → {new} would zero the budget; use "
                      f"--status PAUSED (--confirm PAUSE) to stop delivery instead.", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": "budget below 1 minor unit"})
                continue
            if step < -0.5 and not args.force_step:
                print(f"  x {oid} {obj.get('name')}: {cur} → {new} is {step:+.0%}; a cut deeper than 50% in one edit "
                      f"almost stops delivery and restarts learning. Cut in steps, pause, or --force-step.",
                      file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": f"budget cut {step:+.0%} exceeds -50%"})
                continue
            # Guard RAISES only: a cut can only lower spend, so any size passes. Compare at 0.1%
            # resolution: integer minor units make a "+20%" edit land a hair over (10368 -> 12442
            # is +20.004%) and that must not refuse `--budget-pct +20` or stall `edit ramp`.
            if step > 0 and round(step, 3) > STEP_LIMIT and not args.force_step:
                print(f"  x {oid} {obj.get('name')}: {cur} → {new} is {step:+.1%}; a raise above +20% per edit "
                      f"re-enters learning and on fresh accounts has frozen delivery. Step in ≤20% "
                      f"moves 48-72 h apart, or --force-step.", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": f"budget raise {step:+.1%} exceeds +20%"})
                continue
            hour = account_hour(obj) if step > 0 else None
            if step > 0 and hour is not None and hour >= 22 and not args.force_step:
                print(f"  x {oid} {obj.get('name')}: raising at {hour:02d}:00 account time leaves "
                      f"<2 h to spend it. Raise in the morning, or --force-step.", file=sys.stderr)
                bad += 1
                results.append({"id": oid, "ok": False, "error": "budget raise in last 2h of account day"})
                continue
            payload["daily_budget"] = int(new)
        if not payload:
            results.append({"id": oid, "ok": True, "skipped": True, "reason": "nothing to change for this id"})
            continue
        if args.dry_run:
            print(f"  would POST /{oid} {json.dumps(payload)}  (now: status={obj.get('status')} "
                  f"budget={obj.get('daily_budget')})")
            row = {"id": oid, "ok": True, "dry_run": True, "payload": payload}
            if args.validate_only:
                try:
                    graph.post(oid, dict(payload, execution_options=["validate_only"]),
                               context=f"validate edit {oid}", idempotent=True)
                    row["validated"] = True
                    print(f"  ✓ {oid}: Meta accepts this payload (validate_only, nothing applied)")
                except graph.GraphError as e:
                    print(f"  x {oid}: Meta rejects this payload: {e}", file=sys.stderr)
                    row.update({"ok": False, "validated": False, "error": str(e)})
                    bad += 1
            results.append(row)
            continue
        try:
            graph.post(oid, payload, context=f"edit {oid}", idempotent=True)
            back_fields = "name,status,effective_status" if "daily_budget" not in obj else "name,status,daily_budget,effective_status"
            if "bid_amount" in payload:
                back_fields += ",bid_amount"
            if "start_time" in payload or "end_time" in payload:
                back_fields += ",start_time,end_time"
            back = graph.get(oid, params={"fields": back_fields}, context="readback")
            extra = "".join(f" {k}={back.get(k)}" for k in ("bid_amount", "start_time", "end_time") if k in back)
            print(f"  ✓ {oid} {back.get('name')}: status={back.get('status')} "
                  f"effective={back.get('effective_status')} daily_budget={back.get('daily_budget')}{extra}")
            row = {
                "id": oid, "ok": True, "name": back.get("name"), "status": back.get("status"),
                "effective_status": back.get("effective_status"), "daily_budget": back.get("daily_budget"),
            }
            row.update({k: back[k] for k in ("bid_amount", "start_time", "end_time") if k in back})
            results.append(row)
        except graph.GraphError as e:
            print(f"  x {oid}: {e}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": str(e)})
    print(json.dumps({"schema": "edit.result/v1", "dry_run": args.dry_run, "validate_only": args.validate_only, "ok": bad == 0,
                      "count": len(ids), "failed": bad, "results": results}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
