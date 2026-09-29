#!/usr/bin/env python3
"""Pull spend and delivery for the daily sync. Account timezone, no eyeballing.

    python3 insights.py --account act_123 --level campaign --since 2026-08-25 --until 2026-08-31
    python3 insights.py --account act_123 --level ad --date-preset yesterday --csv day.csv

Feeds the tracker cost push (tracker-ops/01 update_costs). Two rules it enforces so the
numbers reconcile:

· Every row is in the AD ACCOUNT timezone, which is what Meta reports in and what the
  daily CPL must be computed in — for spend AND for leads. Mixing timezones is the
  quiet way to get a CPL that is wrong by one day's worth of traffic.
· `action_attribution_windows` is stated explicitly. Meta's default is 7-day click, so
  an unstated window silently reports more conversions than a 1-day-click ad set
  actually earned, and the tracker will disagree.

What this does NOT do is decide anything. Meta numbers are one source; the payout
metric lives in the tracker (tracker-ops metric rule) and cohorts mature on click date.
Never conclude from this output alone.

Optional request shaping (all validated locally, before any call; GET only):

    --breakdown publisher_platform,platform_position   allow-list, see ALLOWED_BREAKDOWNS
    --time-increment 1|7|monthly|all_days              (any integer day count still accepted here)
    --action-attribution-windows 7d_click,1d_view      or --click-window 1|7|28 --view-window 1
    --fields reach,outbound_clicks                     ADDS columns to the default set

Rows of a breakdown pull are for reading (placement, geo, age); do not push them to the
tracker as cost. Join a placement pull with Keitaro `sub11` (`placement={{placement}}`):
sub11 is a Keitaro string such as `Facebook_Mobile_Feed`, Meta returns `publisher_platform`
and `platform_position` as separate columns, and how the two spellings map is NOT
documented in this repo (unverified): build the join key by hand and check it on one day.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time

import graph

SUMMARY_SCHEMA = "insights.result/v1"

FIELDS = [
    "date_start", "date_stop", "account_currency",
    "campaign_id", "campaign_name", "adset_id", "adset_name", "ad_id", "ad_name",
    "spend", "impressions", "clicks", "inline_link_clicks", "reach", "frequency",
    "cpm", "ctr", "cpc", "actions", "action_values", "cost_per_action_type",
]

# v26.0 removed these; requesting them errors on ANY version. Listed so nobody adds
# them back from an older snippet.
REMOVED_AT_V26 = ("total_video_impressions", "total_video_views_unique")

# --- request validation, shared with `metaops insights pull` (cmd_operate.py) --------------
# Names below were read from the installed facebook_business 26.0.1 source
# (AdsInsights.Breakdowns / .Field / .ActionAttributionWindows), offline, never from a live
# call. Anything not listed is rejected locally instead of costing a Graph call.

ALLOWED_BREAKDOWNS = (
    "country", "region", "dma", "age", "gender",
    "publisher_platform", "platform_position", "device_platform", "impression_device",
    "hourly_stats_aggregated_by_advertiser_time_zone",
    "hourly_stats_aggregated_by_audience_time_zone",
)

# Which breakdown combinations Meta forbids is NOT documented anywhere in this repo, so no
# combination is rejected locally: Graph answers a bad one with a code 100 on a GET that
# changed nothing. This is the one pairing worth a heads-up (advisory only, unverified).
BREAKDOWN_ADVISORIES = (
    (("platform_position",), ("publisher_platform",),
     "platform_position is normally read together with publisher_platform (not confirmed by "
     "the repo docs); if Graph answers code 100, add publisher_platform"),
)

# Attribution windows still served after 2026-01-12 (meta-ads/08 section 12): 1d_ev is the
# API name of "1-day engaged view" (SDK enum). 7d_view / 28d_view were dropped on that date
# and come back as a SILENT empty result, so they are refused with the reason.
ATTRIBUTION_WINDOWS = ("1d_click", "7d_click", "28d_click", "1d_view", "1d_ev")
DROPPED_WINDOWS = ("7d_view", "28d_view")
CLICK_WINDOW_DAYS = (1, 7, 28)
VIEW_WINDOW_DAYS = (1,)

# `--time-increment` accepted by the metaops wrapper (Graph also takes other day counts,
# unverified here); the script itself still takes any positive integer.
WRAPPER_TIME_INCREMENTS = ("1", "7", "monthly", "all_days")

# Columns `--fields` may ADD to FIELDS. Every name exists in the SDK 26.0.1 AdsInsights.Field
# enum; the two removed at v26 are refused by name.
EXTRA_FIELDS = (
    "reach", "frequency", "clicks", "unique_clicks", "cpc", "cpm", "cpp", "ctr", "unique_ctr",
    "cost_per_unique_click", "inline_link_clicks", "inline_link_click_ctr",
    "cost_per_inline_link_click", "unique_inline_link_clicks",
    "cost_per_unique_inline_link_click", "outbound_clicks", "outbound_clicks_ctr",
    "cost_per_outbound_click", "unique_outbound_clicks", "cost_per_unique_outbound_click",
    "website_ctr", "actions", "action_values", "cost_per_action_type", "unique_actions",
    "cost_per_unique_action_type", "conversions", "conversion_values", "cost_per_conversion",
    "purchase_roas", "website_purchase_roas", "video_play_actions",
    "video_30_sec_watched_actions", "video_p25_watched_actions", "video_p50_watched_actions",
    "video_p75_watched_actions", "video_p95_watched_actions", "video_p100_watched_actions",
    "video_avg_time_watched_actions", "video_thruplay_watched_actions", "cost_per_thruplay",
    "quality_ranking", "engagement_rate_ranking", "conversion_rate_ranking",
    "objective", "optimization_goal", "buying_type", "attribution_setting", "social_spend",
    "account_id", "account_name", "created_time", "updated_time",
)

# Window keys an `actions` entry may carry next to `value` when windows are requested.
WINDOW_KEYS = ("1d_click", "7d_click", "28d_click", "1d_view", "1d_ev", "7d_view", "28d_view")

PAGE_LIMIT = 500
REDUCED_PAGE_LIMIT = 100


def _csv_names(text) -> list[str]:
    return [part.strip() for part in str(text or "").split(",") if part.strip()]


def parse_breakdowns(text) -> list[str]:
    names = [n.lower() for n in _csv_names(text)]
    if not names:
        raise ValueError("--breakdown is empty")
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"--breakdown repeats {repeated}")
    unknown = sorted(set(names) - set(ALLOWED_BREAKDOWNS))
    if unknown:
        raise ValueError(
            f"unknown --breakdown name(s) {unknown}; allowed: {', '.join(ALLOWED_BREAKDOWNS)}"
        )
    return names


def breakdown_advisories(names: list[str]) -> list[str]:
    have = set(names)
    return [
        message for present, missing, message in BREAKDOWN_ADVISORIES
        if set(present) <= have and not set(missing) & have
    ]


def parse_time_increment(text, strict: bool = False) -> int | str:
    value = str(text).strip().lower()
    if value in ("all_days", "monthly"):
        return value
    try:
        days = int(value)
    except ValueError:
        days = 0
    if days < 1:
        raise ValueError("--time-increment must be a positive integer day count, 'monthly' or 'all_days'")
    if strict and str(days) not in WRAPPER_TIME_INCREMENTS:
        raise ValueError(f"--time-increment must be one of {', '.join(WRAPPER_TIME_INCREMENTS)}")
    return days


def parse_windows(text) -> list[str]:
    names = [n.lower() for n in _csv_names(text)]
    if not names:
        raise ValueError("--action-attribution-windows is empty")
    dropped = sorted(set(names) & set(DROPPED_WINDOWS))
    if dropped:
        raise ValueError(
            f"{dropped}: Meta dropped 7-day and 28-day view windows on 2026-01-12; the Insights "
            "API now returns a silent empty result for them (meta-ads/08 section 12). Use "
            f"{', '.join(ATTRIBUTION_WINDOWS)}"
        )
    unknown = sorted(set(names) - set(ATTRIBUTION_WINDOWS))
    if unknown:
        raise ValueError(
            f"unknown attribution window(s) {unknown}; allowed: {', '.join(ATTRIBUTION_WINDOWS)}"
        )
    return list(dict.fromkeys(names))


def windows_from_days(click: int | None, view: int | None) -> list[str]:
    click = 1 if click is None else click
    view = 1 if view is None else view
    if click not in CLICK_WINDOW_DAYS:
        raise ValueError(f"--click-window must be one of {list(CLICK_WINDOW_DAYS)}")
    if view not in VIEW_WINDOW_DAYS:
        raise ValueError(
            f"--view-window must be {list(VIEW_WINDOW_DAYS)}: 7-day and 28-day view windows were "
            "dropped on 2026-01-12 (silent empty result)"
        )
    return [f"{click}d_click", f"{view}d_view"]


def parse_extra_fields(text) -> list[str]:
    names = [n.lower() for n in _csv_names(text)]
    if not names:
        raise ValueError("--fields is empty")
    removed = sorted(set(names) & set(REMOVED_AT_V26))
    if removed:
        raise ValueError(f"{removed} were removed at API v26 and error on every version")
    unknown = sorted(set(names) - set(EXTRA_FIELDS) - set(FIELDS))
    if unknown:
        raise ValueError(f"unknown --fields name(s) {unknown}; allowed: {', '.join(EXTRA_FIELDS)}")
    return list(dict.fromkeys(names))


def request_fields(extra: list[str] | None = None) -> list[str]:
    return list(dict.fromkeys([*FIELDS, *(extra or [])]))


def is_reduce_data_error(exc: Exception) -> bool:
    """Graph code 1 "Please reduce the amount of data you're asking for": a smaller page fixes it."""
    return getattr(exc, "code", None) == 1 and "reduce the amount of data" in str(
        getattr(exc, "message", "")
    ).lower()


def flatten_actions(row: dict) -> dict:
    """Actions arrive as a list of {action_type, value}. Flatten the ones worth a column
    and keep the raw list in the JSON output."""
    out = dict(row)
    for key in ("actions", "cost_per_action_type", "action_values"):
        for entry in row.get(key) or []:
            atype = entry.get("action_type", "?")
            out[f"{key}:{atype}"] = entry.get("value")
            # With action_attribution_windows set, each entry also carries one key per
            # window ("7d_click": "3"); without a column per window a 7d pull would look
            # identical to a 1d one in the CSV.
            for window in WINDOW_KEYS:
                if window in entry:
                    out[f"{key}:{atype}:{window}"] = entry[window]
        out.pop(key, None)
    return out


def fetch(account: str, level: str, params: dict, fields: list[str] | None = None) -> list[dict]:
    """Insights are computed async on large ranges; this follows paging and waits out
    the empty-result window on fresh objects (15-40 min, not a failure).

    Sync GET + cursor paging only. Throttle handling is graph.call's: the
    `x-fb-ads-insights-throttle` / `x-app-usage` / BUC headers are read on every response
    (sleep at 85 %), and a throttle code sets the account cooldown and is never retried.
    One extra rule here: Graph code 1 "reduce the amount of data" (common with breakdowns)
    is retried ONCE with a smaller page, for the rest of the pull."""
    rows: list[dict] = []
    path = f"{account}/insights"
    query = dict(params, level=level, fields=",".join(fields or FIELDS), limit=PAGE_LIMIT)
    reduced = False

    while True:
        try:
            resp = graph.get(path, params=query, context=f"insights {level}")
        except graph.GraphError as exc:
            if reduced or not is_reduce_data_error(exc):
                raise
            reduced = True
            query = dict(query, limit=REDUCED_PAGE_LIMIT)
            print(f"  ! Graph asked to reduce the amount of data; retrying once with "
                  f"limit={REDUCED_PAGE_LIMIT}", file=sys.stderr)
            continue
        rows.extend(resp.get("data", []))
        query = graph.next_page_params(resp, query)
        if query is None:
            return rows
        time.sleep(0.3)  # a read is 1 point; do not sprint through paging


def build_request(args) -> tuple[dict, list[str], dict]:
    """Validate the CLI flags and return (Graph params, fields, echo of what was requested).

    Raises ValueError with a usable message; nothing here touches the network."""
    time_increment = parse_time_increment(args.time_increment)
    if args.action_attribution_windows:
        if args.click_window is not None or args.view_window is not None:
            raise ValueError("--action-attribution-windows replaces --click-window/--view-window; "
                             "give one or the other")
        windows = parse_windows(args.action_attribution_windows)
    else:
        windows = windows_from_days(args.click_window, args.view_window)
    breakdowns = parse_breakdowns(args.breakdown) if args.breakdown else []
    extra = parse_extra_fields(args.fields) if args.fields else []

    params: dict = {"action_attribution_windows": windows, "time_increment": time_increment}
    if args.since or args.until:
        if not (args.since and args.until):
            raise ValueError("--since and --until must be given together")
        params["time_range"] = {"since": args.since, "until": args.until}
    else:
        params["date_preset"] = args.date_preset or "yesterday"
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)
    echo = {
        "breakdowns": breakdowns, "time_increment": time_increment,
        "attribution_windows": windows, "extra_fields": extra,
        "advisories": breakdown_advisories(breakdowns),
    }
    return params, request_fields(extra), echo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", required=True)
    ap.add_argument("--level", default="campaign", choices=["account", "campaign", "adset", "ad"])
    ap.add_argument("--since", help="YYYY-MM-DD, account timezone")
    ap.add_argument("--until", help="YYYY-MM-DD, account timezone")
    ap.add_argument("--date-preset", help="e.g. yesterday, last_7d — used when --since is absent")
    ap.add_argument("--time-increment", default="1",
                     help="Graph time_increment: an integer day count, 'monthly', or 'all_days' to "
                          "collapse the whole range into one row per object (reach is then "
                          "deduplicated by Graph across the range, not summed) (default 1)")
    ap.add_argument("--click-window", type=int, default=None,
                    help="attribution click days: 1, 7 or 28 (default 1)")
    ap.add_argument("--view-window", type=int, default=None,
                    help="attribution view days: 1 only (7d/28d view were dropped 2026-01-12) (default 1)")
    ap.add_argument("--action-attribution-windows", dest="action_attribution_windows",
                    help="explicit list, e.g. 7d_click,1d_view (allowed: "
                         + ", ".join(ATTRIBUTION_WINDOWS) + "); replaces --click-window/--view-window")
    ap.add_argument("--breakdown", help="comma list from: " + ", ".join(ALLOWED_BREAKDOWNS))
    ap.add_argument("--fields", help="extra columns added to the default set (allow-list, see "
                                     "EXTRA_FIELDS in this file)")
    ap.add_argument("--csv", help="Write a flat CSV here")
    ap.add_argument("--json", help="Write the raw rows here")
    args = ap.parse_args()

    try:
        params, fields, echo = build_request(args)
    except ValueError as exc:
        sys.exit(str(exc))

    account = graph.normalize_account(args.account)

    acct = graph.get(account, params={"fields": "timezone_name,currency"}, context="account tz")
    print(f"{account}  tz={acct.get('timezone_name')}  currency={acct.get('currency')}")
    print("All dates below are in that timezone. Compute CPL against tracker leads in the "
          "SAME timezone or the number is wrong.\n")
    print(f"windows={','.join(echo['attribution_windows'])}  time_increment={echo['time_increment']}"
          f"  breakdowns={','.join(echo['breakdowns']) or '-'}")
    for note in echo["advisories"]:
        print(f"  ! {note}", file=sys.stderr)

    rows = fetch(account, args.level, params, fields)
    if not rows:
        print("No rows. On freshly created objects insights stay empty for 15-40 min — "
              "that is propagation, not a delivery failure.")
        print(json.dumps({
            "schema": SUMMARY_SCHEMA, "account": account, "level": args.level, "rows": 0,
            "total_spend": 0.0, "currency": acct.get("currency"), "timezone": acct.get("timezone_name"),
            "csv": args.csv, "json": args.json, **echo,
        }, ensure_ascii=False))
        return 0

    flat = [flatten_actions(r) for r in rows]
    total = sum(float(r.get("spend", 0) or 0) for r in rows)
    print(f"{len(rows)} rows, total spend {total:.2f} {acct.get('currency')}")

    if args.csv:
        cols: list[str] = []
        for r in flat:
            for k in r:
                if k not in cols:
                    cols.append(k)
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(flat)
        print(f"csv → {args.csv}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(graph.redact(json.dumps(rows, indent=2)))
        print(f"json → {args.json}")

    if not (args.csv or args.json):
        for r in flat[:50]:
            name = r.get("ad_name") or r.get("adset_name") or r.get("campaign_name") or account
            print(f"  {r.get('date_start')}  {name[:44]:<44}  spend {r.get('spend')}")

    if echo["breakdowns"]:
        print("\nBreakdown rows are for reading (join placement rows with Keitaro sub11). "
              "Do NOT push them as cost: push the plain ad-level daily pull "
              "(tracker-ops/01 update_costs).")
    else:
        print("\nNext: push these as cost into the tracker (tracker-ops/01 update_costs). "
              "No cost push = report cost is 0 = no CPL.")
    print(json.dumps({
        "schema": SUMMARY_SCHEMA, "account": account, "level": args.level, "rows": len(rows),
        "total_spend": round(total, 2), "currency": acct.get("currency"),
        "timezone": acct.get("timezone_name"), "csv": args.csv, "json": args.json, **echo,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
