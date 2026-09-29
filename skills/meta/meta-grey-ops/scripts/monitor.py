#!/usr/bin/env python3
"""Status + spend sweep across accounts. The detection half of the ban loop (03).

    python3 monitor.py --accounts accounts.json                 # today + yesterday
    python3 monitor.py --accounts act_1,act_2 --log survival.jsonl
    python3 monitor.py --accounts accounts.json --json out.json --quiet

Per account, in one pass:
  · account_status / disable_reason / balance / spend_cap / amount_spent
  · yesterday's and today's spend (account level, account timezone)
  · counts of ads by effective_status — DISAPPROVED / WITH_ISSUES / ACTIVE / PAUSED
  · ad sets with issues_info

Verdicts it prints (never acts on):
  DISABLED         account_status != 1 → document (id, date, spend at death) and replace (03)
  UNSETTLED        status 3 = unpaid balance, a topup fixes it — NOT a ban
  SILENT_STOP      was spending yesterday, ~0 today past mid-day → ASL cap, billing hold,
                   throttle or a restriction not yet surfaced as status
  REJECTS          DISAPPROVED ads present → new ads, do not fight (2490468)
  ISSUES           WITH_ISSUES ads or ad sets carrying issues_info
  STALL            ACTIVE ad set with impressions and 0 clicks today (04)
  ASL_HIT          amount_spent reached the account spend cap
  UNREACHABLE      the account itself could not be read - nothing below applies
  ERROR            the account read fine but a later call failed mid-sweep (spend / ads / ad sets):
                   the counts in that row are PARTIAL, so it is never reported OK. It sits beside
                   any real verdict found on the data that did load (REJECTS,ERROR) and exits 1
  OK

Every row is appended to --log as JSONL with a UTC timestamp: that log is what makes the
forensics in 06 and the agency replacement lists possible. Autolaunch SaaS shows this on a
dashboard; here it is a cron line.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import graph

ACCOUNT_FIELDS = ("id,name,account_status,disable_reason,currency,timezone_name,"
                  "timezone_offset_hours_utc,balance,spend_cap,amount_spent")
STATUS = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
          8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE", 101: "CLOSED"}


def load_accounts(arg: str) -> list[str]:
    if arg.endswith(".json"):
        with open(arg, encoding="utf-8") as fh:
            rows = json.load(fh)
        ids = [r["account_id"] if isinstance(r, dict) else r for r in rows]
    else:
        ids = arg.split(",")
    return [graph.normalize_account(i) for i in ids if str(i).strip()]


def spend(account: str, preset: str) -> float:
    rows = graph.get(f"{account}/insights",
                     params={"fields": "spend", "date_preset": preset, "level": "account"},
                     context=f"spend {preset}").get("data", [])
    return float(rows[0]["spend"]) if rows else 0.0


def ad_status_counts(account: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    path, params = f"{account}/ads", {"fields": "effective_status", "limit": 500,
                                       "effective_status": json.dumps(
                                           ["ACTIVE", "PAUSED", "DISAPPROVED", "WITH_ISSUES",
                                            "PENDING_REVIEW", "ADSET_PAUSED", "CAMPAIGN_PAUSED"])}
    while True:
        resp = graph.get(path, params=params, context="ads status")
        for ad in resp.get("data", []):
            counts[ad.get("effective_status", "?")] = counts.get(ad.get("effective_status", "?"), 0) + 1
        params = graph.next_page_params(resp, params)
        if params is None:
            return counts


def adset_issues(account: str) -> list[dict]:
    rows = _adsets(
        account,
        {"fields": "id,name,effective_status,issues_info", "limit": 200},
        "adset issues",
    )
    return [{"id": a["id"], "name": a.get("name"), "issues": a["issues_info"]}
            for a in rows if a.get("issues_info")]


STALL_MIN_IMPRESSIONS = 40


def _adsets(account: str, params: dict, context: str) -> list[dict]:
    """Fetch every matching ad set; an account routinely has more than one page."""
    rows: list[dict] = []
    path = f"{account}/adsets"
    page_params = dict(params)
    while True:
        response = graph.get(path, params=page_params, context=context)
        rows.extend(response.get("data", []))
        page_params = graph.next_page_params(response, page_params)
        if page_params is None:
            return rows


def adset_delivery(account: str) -> list[dict]:
    rows = _adsets(
        account,
        {"fields": "id,name,effective_status,insights.date_preset(today){impressions,clicks}",
         "effective_status": json.dumps(["ACTIVE"]), "limit": 200},
        "adset delivery",
    )
    out = []
    for a in rows:
        ins = ((a.get("insights") or {}).get("data") or [{}])[0]
        out.append({"id": a["id"], "name": a.get("name"), "impressions": int(ins.get("impressions", 0) or 0),
                    "clicks": int(ins.get("clicks", 0) or 0)})
    return out


def stalled(adsets: list[dict], min_impressions: int = STALL_MIN_IMPRESSIONS) -> list[dict]:
    """Practitioner heuristic (2026-09): an ACTIVE ad set with >= min_impressions today and 0 clicks
    has an eCTR the auction reads as zero; it freezes without any API-visible issue. Swap the
    creative angle, do not raise the budget."""
    return [a for a in adsets if a["impressions"] >= min_impressions and a["clicks"] == 0]


def local_hour(offset_hours: float | None) -> int | None:
    if offset_hours is None:
        return None
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=float(offset_hours))).hour


def sweep(account: str, stall_min: int = STALL_MIN_IMPRESSIONS) -> dict:
    row: dict = {"account": account, "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        acct = graph.get(account, params={"fields": ACCOUNT_FIELDS}, context="account")
    except graph.GraphError as e:
        row.update({"verdict": "UNREACHABLE", "error": str(e), "code": e.code, "subcode": e.subcode})
        return row
    st = acct.get("account_status")
    row.update({
        "name": acct.get("name"), "status": st, "status_label": STATUS.get(st, f"UNKNOWN({st})"),
        "disable_reason": acct.get("disable_reason"), "currency": acct.get("currency"),
        "tz": acct.get("timezone_name"), "balance": acct.get("balance"),
        "spend_cap": acct.get("spend_cap"), "amount_spent": acct.get("amount_spent"),
    })
    try:
        row["spend_yesterday"] = spend(account, "yesterday")
        row["spend_today"] = spend(account, "today")
        row["ads"] = ad_status_counts(account)
        row["adset_issues"] = adset_issues(account)
        row["stalled_adsets"] = stalled(adset_delivery(account), stall_min)
    except graph.GraphError as e:
        # Partial data: whatever loaded before the failure stays in the row, but the row can no
        # longer claim OK (a missing "ads" block reads as "no rejects").
        row["error"] = str(e)
        row["code"] = e.code
        row["subcode"] = e.subcode

    hour = local_hour(acct.get("timezone_offset_hours_utc"))
    verdicts = []
    if st == 3:
        verdicts.append("UNSETTLED")
    elif st != 1:
        verdicts.append("DISABLED")
    if row.get("ads", {}).get("DISAPPROVED"):
        verdicts.append("REJECTS")
    if row.get("ads", {}).get("WITH_ISSUES") or row.get("adset_issues"):
        verdicts.append("ISSUES")
    y, t = row.get("spend_yesterday", 0.0), row.get("spend_today", 0.0)
    # Only a verdict when something is supposed to be delivering: all-paused accounts
    # legitimately spend 0 (false positive seen 2026-09-02 on a paused account).
    active_ads = row.get("ads", {}).get("ACTIVE", 0)
    if st == 1 and active_ads and y > 0 and hour is not None and hour >= 12 and t < 0.05 * y:
        verdicts.append("SILENT_STOP")
    if row.get("stalled_adsets"):
        verdicts.append("STALL")
    cap = acct.get("spend_cap")
    try:
        if cap and int(cap) > 0 and int(acct.get("amount_spent", 0)) >= int(cap):
            verdicts.append("ASL_HIT")
    except (TypeError, ValueError):
        pass
    if row.get("error"):
        verdicts.append("ERROR")
    row["verdict"] = ",".join(verdicts) or "OK"
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--accounts", required=True, help="accounts.json (bulk.py format) or act_1,act_2")
    ap.add_argument("--log", default="survival.jsonl", help="append-only JSONL survival log")
    ap.add_argument("--json", help="write this sweep's rows here")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--stall-impressions", type=int, default=STALL_MIN_IMPRESSIONS,
                    help="ACTIVE ad set with >= N impressions today and 0 clicks → STALL")
    args = ap.parse_args()

    rows = []
    for acct in load_accounts(args.accounts):
        row = sweep(acct, args.stall_impressions)
        rows.append(row)
        if not args.quiet:
            ads = row.get("ads", {})
            print(f"{acct:<20} {row.get('status_label', '?'):<18} y={row.get('spend_yesterday', '-'):<9} "
                  f"t={row.get('spend_today', '-'):<9} rej={ads.get('DISAPPROVED', 0)} "
                  f"issues={ads.get('WITH_ISSUES', 0)}  → {row['verdict']}")
            if row.get("error"):
                print(f"    ! sweep incomplete, counts above are partial: {row['error']}")
    with open(args.log, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(graph.redact(json.dumps(row, default=str)) + "\n")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(graph.redact(json.dumps(rows, indent=2, default=str)))
    bad = [r for r in rows if r["verdict"] != "OK"]
    errored = [r for r in rows if "ERROR" in r["verdict"].split(",") or r["verdict"] == "UNREACHABLE"]
    print(f"\n{len(rows)} account(s), {len(bad)} need attention. Log → {args.log}")
    if errored:
        print(f"{len(errored)} account(s) ERROR/UNREACHABLE: {', '.join(r['account'] for r in errored)} "
              f"- the sweep did not finish there, re-run before trusting their counts.")
    if bad:
        print("DISABLED → document + replace (03). UNSETTLED → topup. SILENT_STOP → check ASL, "
              "billing, review; touch nothing else. REJECTS → new ads, never re-enable. "
              "STALL → swap creative angle on the listed ad sets (04). "
              "ERROR/UNREACHABLE → API failed mid-sweep: partial data, re-run.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
