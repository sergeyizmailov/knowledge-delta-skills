#!/usr/bin/env python3
"""Operate-phase commands for metaops: the autolaunch-SaaS dashboard, agent-side (16, 13).

Adds workspace-bound, no-Graph-code commands to the metaops CLI:

    metaops review [--state PATH | --ids a,b | --all] [--previews --format F1,F2]
    metaops review --tree [--campaign ID] [--statuses A,B]     # campaign > ad set > ad, logic in cmd_inspect.py
    metaops monitor --accounts accounts.json|act_a,act_b [--telegram] [--stall-impressions N] [--out-json PATH]
    metaops comments list|hide|delete [--ads a,b | --all] [--matching REGEX] --confirm HIDE|DELETE
    metaops page show|set|list-pages [--avatar f] [--cover f] [--about ..] [--website URL] --confirm PAGE
    metaops insights pull --level L (--date-preset X | --since --until) [--breakdown B1,B2]
        [--time-increment 1|7|monthly|all_days] [--action-attribution-windows 7d_click,1d_view] [--fields F1,F2]
    metaops insights leaderboard --accounts accounts.json [--date-preset X] [--top N]
    metaops insights fatigue [--days 14] [--min-spend 20] [--event E]

Every command is workspace-bound: the ad account and Page come from the active profile
(`ad_account_id`, `page_id`), never typed in by the agent. Nothing here builds Graph
payloads directly for writes — comments/page mutations run through comments.py/page.py
as children (Page-token scripts), same transport-guard contract as every other metaops
command (run_child inherits the parent's write authorization over METAOPS_AUTH_FD).

register(sub, ctx) wires these onto the shared subparsers object from metaops.parser();
ctx is the metaops module itself (graph, run_child, echo_child, child_failure,
result_envelope, MetaOpsError, resolve_input, read_json, now_utc).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
from typing import Any

import cmd_inspect
import insights

# facebook_business 26.0.1 AdPreview.AdFormat — verified via
#   python -c "from facebook_business.adobjects.adpreview import AdPreview; ..."
# Hardcoded (no facebook_business runtime dependency) so --format can be validated locally.
ALLOWED_AD_FORMATS = frozenset({
    "AUDIENCE_NETWORK_INSTREAM_VIDEO", "AUDIENCE_NETWORK_INSTREAM_VIDEO_MOBILE",
    "AUDIENCE_NETWORK_OUTSTREAM_VIDEO", "AUDIENCE_NETWORK_REWARDED_VIDEO",
    "BIZ_DISCO_FEED_MOBILE", "DESKTOP_FEED_STANDARD", "FACEBOOK_IFU_REELS_MOBILE",
    "FACEBOOK_PROFILE_FEED_DESKTOP", "FACEBOOK_PROFILE_FEED_MOBILE",
    "FACEBOOK_PROFILE_REELS_MOBILE", "FACEBOOK_REELS_BANNER",
    "FACEBOOK_REELS_BANNER_DESKTOP", "FACEBOOK_REELS_BANNER_FEED_ANDROID",
    "FACEBOOK_REELS_BANNER_FEED_ANDROID_LARGE", "FACEBOOK_REELS_BANNER_FULLSCREEN_IOS",
    "FACEBOOK_REELS_BANNER_FULLSCREEN_MOBILE", "FACEBOOK_REELS_MOBILE",
    "FACEBOOK_REELS_POSTLOOP", "FACEBOOK_REELS_POSTLOOP_FEED",
    "FACEBOOK_REELS_SIMILAR_PRODUCTS_MOBILE", "FACEBOOK_REELS_STICKER",
    "FACEBOOK_STORY_MOBILE", "FACEBOOK_STORY_STICKER_MOBILE",
    "INSTAGRAM_EXPLORE_CONTEXTUAL", "INSTAGRAM_EXPLORE_GRID_HOME",
    "INSTAGRAM_EXPLORE_IMMERSIVE", "INSTAGRAM_FEED_WEB", "INSTAGRAM_FEED_WEB_M_SITE",
    "INSTAGRAM_LEAD_GEN_MULTI_SUBMIT_ADS", "INSTAGRAM_PROFILE_FEED",
    "INSTAGRAM_PROFILE_REELS", "INSTAGRAM_REELS", "INSTAGRAM_REELS_OVERLAY",
    "INSTAGRAM_REELS_WEB", "INSTAGRAM_REELS_WEB_M_SITE", "INSTAGRAM_SEARCH_CHAIN",
    "INSTAGRAM_SEARCH_GRID", "INSTAGRAM_STANDARD", "INSTAGRAM_STORY",
    "INSTAGRAM_STORY_EFFECT_TRAY", "INSTAGRAM_STORY_WEB", "INSTAGRAM_STORY_WEB_M_SITE",
    "INSTANT_ARTICLE_RECIRCULATION_AD", "INSTANT_ARTICLE_STANDARD",
    "INSTREAM_BANNER_DESKTOP", "INSTREAM_BANNER_FEED_IOS",
    "INSTREAM_BANNER_FULLSCREEN_IOS", "INSTREAM_BANNER_FULLSCREEN_MOBILE",
    "INSTREAM_BANNER_IMMERSIVE_MOBILE", "INSTREAM_BANNER_MOBILE",
    "INSTREAM_VIDEO_DESKTOP", "INSTREAM_VIDEO_FULLSCREEN_IOS",
    "INSTREAM_VIDEO_FULLSCREEN_MOBILE", "INSTREAM_VIDEO_IMAGE",
    "INSTREAM_VIDEO_IMMERSIVE_MOBILE", "INSTREAM_VIDEO_MOBILE", "JOB_BROWSER_DESKTOP",
    "JOB_BROWSER_MOBILE", "MARKETPLACE_MOBILE", "MESSENGER_MOBILE_INBOX_MEDIA",
    "MESSENGER_MOBILE_STORY_MEDIA", "MOBILE_BANNER", "MOBILE_FEED_BASIC",
    "MOBILE_FEED_STANDARD", "MOBILE_FULLWIDTH", "MOBILE_INTERSTITIAL",
    "MOBILE_MEDIUM_RECTANGLE", "MOBILE_NATIVE", "RIGHT_COLUMN_STANDARD",
    "SUGGESTED_VIDEO_DESKTOP", "SUGGESTED_VIDEO_FULLSCREEN_MOBILE",
    "SUGGESTED_VIDEO_IMMERSIVE_MOBILE", "SUGGESTED_VIDEO_MOBILE", "WATCH_FEED_HOME",
    "WATCH_FEED_MOBILE", "WHATSAPP_STATUS_MEDIA",
})

PULL_HELP = """Pull spend and delivery in the account timezone. GET only, paged, sync.

Default is one row per object per day with 1d_click + 1d_view conversions. Shape it with:
  --breakdown publisher_platform,platform_position --time-increment all_days
  --action-attribution-windows 7d_click,1d_view      (Meta reports only the windows you name)
  --fields reach,outbound_clicks                     (added to the default columns)

Placement read, joined with Keitaro:
  1. Pull the breakdown above at --level ad (or adset).
  2. In Keitaro report by sub11 (ad link `placement={{placement}}`, e.g. `Facebook_Mobile_Feed`),
     with the same days, currency and click-date cohort (25-placement-performance.md).
  3. Meta returns publisher_platform and platform_position as two columns; Keitaro gets ONE
     string from the {{placement}} macro. The mapping between Meta's platform_position names
     and the {{placement}} values is UNVERIFIED: this repo documents one macro value only
     (Facebook_Mobile_Feed). Build the join key by hand and check it on one day before use.
  4. Breakdown rows are for reading; do not push them to the tracker as cost.

Meta's rules for which breakdowns may be combined are not documented in this repo, so no
combination is rejected locally: Graph answers a bad one with code 100 on a GET."""
REVIEW_BLOCKING = {"DISAPPROVED", "WITH_ISSUES"}
AD_REVIEW_FIELDS = "id,account_id,name,effective_status,configured_status,issues_info,ad_review_feedback"


# --------------------------------------------------------------------------- shared helpers


def _require_workspace(ctx, args, label: str):
    if not getattr(args, "workspace_obj", None):
        raise ctx.MetaOpsError(f"{label} requires a workspace; run inside a workspace or pass --workspace")
    return args.workspace_obj


def _profile(ctx, args, label: str):
    workspace = _require_workspace(ctx, args, label)
    name, profile = workspace.profile(args.profile)
    return workspace, name, profile


def _operate_dir(workspace) -> pathlib.Path:
    path = (workspace.state_root / "operate").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stamp(ctx) -> str:
    return ctx.now_utc().replace(":", "").replace("+", "_")


def _last_json_line(stdout: str) -> dict[str, Any]:
    """Same convention as metaops.run_feed_upload: the last line starting with '{' is the
    structured result. comments.py/page.py/insights.py each print exactly one such compact
    (single-line, no indent) summary as their final line."""
    result: dict[str, Any] = {}
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                result = json.loads(line)
            except ValueError:
                continue
    return result


def _load_accounts(ctx, arg: str) -> list[str]:
    if arg.endswith(".json"):
        rows = ctx.read_json(ctx.resolve_input(arg), "accounts")
        ids = [row["account_id"] if isinstance(row, dict) else row for row in rows]
    else:
        ids = arg.split(",")
    return [ctx.graph.normalize_account(i) for i in ids if str(i).strip()]


def _bound_accounts(ctx, workspace, arg: str, label: str) -> list[str]:
    """Resolve an input list and reject token-visible accounts outside this workspace."""
    accounts = _load_accounts(ctx, arg)
    declared = {
        ctx.graph.normalize_account(profile["ad_account_id"])
        for profile in workspace.data.get("profiles", {}).values()
    }
    outside = sorted(set(accounts) - declared)
    if outside:
        raise ctx.MetaOpsError(
            f"{label} accounts are not declared by this workspace: {outside}; add/select their profiles first"
        )
    return accounts


# --------------------------------------------------------------------------- review


def _review_ad_ids(ctx, args, account: str) -> list[str]:
    if args.state:
        state = ctx.read_json(ctx.resolve_input(args.state), "state")
        objects = state.get("objects") or {}
        return [str(v) for k, v in objects.items() if k.startswith("ad[")]
    if args.ids:
        return [a.strip() for a in args.ids.split(",") if a.strip()]
    out: list[str] = []
    path, params = f"{account}/ads", {"fields": "id", "limit": 500}
    while True:
        resp = ctx.graph.get(path, params=params, context="review ads")
        out.extend(str(a["id"]) for a in resp.get("data", []))
        params = ctx.graph.next_page_params(resp, params)
        if params is None:
            break
    return out


def _review_all_ads(ctx, account: str) -> list[dict[str, Any]]:
    """Read review fields on the account edge to avoid one request per ad."""
    rows: list[dict[str, Any]] = []
    path = f"{account}/ads"
    params: dict[str, Any] = {"fields": AD_REVIEW_FIELDS, "limit": 500}
    while True:
        response = ctx.graph.get(path, params=params, context="review ads")
        rows.extend(row for row in response.get("data", []) if isinstance(row, dict))
        params = ctx.graph.next_page_params(response, params)
        if params is None:
            return rows


def command_review(args, ctx) -> tuple[int, dict[str, Any]]:
    _, _, profile = _profile(ctx, args, "review")
    account = ctx.graph.normalize_account(profile["ad_account_id"])

    formats: list[str] = []
    if args.previews:
        formats = [f.strip().upper() for f in (args.format or "").split(",") if f.strip()]
        unknown = sorted(set(formats) - ALLOWED_AD_FORMATS)
        if unknown:
            raise ctx.MetaOpsError(
                f"unknown --format value(s): {unknown}; see facebook_business AdPreview.AdFormat"
            )

    if args.all:
        ads = _review_all_ads(ctx, account)
    else:
        ad_ids = _review_ad_ids(ctx, args, account)
        ads = [
            ctx.graph.get(ad_id, params={"fields": AD_REVIEW_FIELDS}, context="review ad")
            for ad_id in ad_ids
        ]
    if not ads:
        if args.all:
            raise ctx.MetaOpsError(f"no ads found on {account}")
        raise ctx.MetaOpsError("no ad ids resolved from --state or --ids")

    for ad in ads:
        actual = ad.get("account_id")
        if not actual or ctx.graph.normalize_account(actual) != account:
            raise ctx.MetaOpsError(
                f"review ad {ad.get('id') or '?'} belongs to {actual or '?'} not {account}; refusing cross-profile read"
            )

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for ad in ads:
        ad_id = str(ad.get("id") or "")
        status = ad.get("effective_status", "?")
        counts[status] = counts.get(status, 0) + 1
        row: dict[str, Any] = {
            "id": ad.get("id", ad_id),
            "name": ad.get("name"),
            "effective_status": status,
            "configured_status": ad.get("configured_status"),
            "issues_info": ad.get("issues_info"),
            "ad_review_feedback": ad.get("ad_review_feedback"),
        }
        if formats:
            previews: dict[str, Any] = {}
            for fmt in formats:
                resp = ctx.graph.get(f"{ad_id}/previews", params={"ad_format": fmt}, context="ad preview")
                previews[fmt] = ((resp.get("data") or [{}])[0]).get("body")
            row["previews"] = previews
        rows.append(row)

    bad = sum(counts.get(status, 0) for status in REVIEW_BLOCKING)
    ok = bad == 0
    return (0 if ok else 1), ctx.result_envelope(
        "review", ok, "reviewed" if ok else "blocked",
        data={"summary": counts, "ads": rows, "blocking": bad, "account_id": account},
        error=None if ok else {
            "kind": "ad_review",
            "message": f"{bad} ad(s) DISAPPROVED/WITH_ISSUES",
        },
        next_action=(
            "No blocking review state." if ok else
            "A rejected ad cannot be re-enabled (2490468); build replacement creatives (07)."
        ),
    )


def command_review_entry(args, ctx) -> tuple[int, dict[str, Any]]:
    """`review` handler: --tree is the read-only account tree (cmd_inspect.py), everything else
    is the flat per-ad review above. --campaign/--statuses only make sense with --tree."""
    if args.tree:
        if args.previews:
            raise ctx.MetaOpsError("review --tree does not take --previews")
        return cmd_inspect.command_review_tree(args, ctx)
    if args.campaign or args.statuses:
        raise ctx.MetaOpsError("--campaign/--statuses belong to review --tree")
    return command_review(args, ctx)


# --------------------------------------------------------------------------- monitor


def _telegram_text(row: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    ads = row.get("ads") or {}
    return (
        f"<b>{esc(row.get('account'))}</b> {esc(row.get('name') or '')}\n"
        f"verdict: <b>{esc(row.get('verdict'))}</b>  status: {esc(row.get('status_label'))}\n"
        f"spend y/t: {row.get('spend_yesterday')}/{row.get('spend_today')} {esc(row.get('currency'))}\n"
        f"rejects={ads.get('DISAPPROVED', 0)} issues={ads.get('WITH_ISSUES', 0)} "
        f"stalled={len(row.get('stalled_adsets') or [])}"
    )


def command_monitor(args, ctx) -> tuple[int, dict[str, Any]]:
    workspace = _require_workspace(ctx, args, "monitor")
    tg_token = os.environ.get("TG_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TG_CHAT_ID", "").strip()
    if args.telegram and not (tg_token and tg_chat):
        raise ctx.MetaOpsError(
            "--telegram requires TG_BOT_TOKEN and TG_CHAT_ID in the environment (never on argv)"
        )

    operate_dir = _operate_dir(workspace)
    accounts = _bound_accounts(ctx, workspace, args.accounts, "monitor")
    accounts_arg = ",".join(accounts)
    log_path = ctx.resolve_input(args.log) if args.log else (workspace.state_root / "survival.jsonl").resolve()
    json_path = (
        ctx.resolve_input(args.out_json)
        if args.out_json
        else (operate_dir / f"monitor.{_stamp(ctx)}.json").resolve()
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    child_args = [
        "--accounts", accounts_arg, "--log", str(log_path), "--json", str(json_path),
        "--quiet", "--stall-impressions", str(args.stall_impressions),
    ]
    # A file left by an earlier run (same --out-json) must not survive a child that crashes before
    # writing: it would be read below as this sweep's rows.
    if json_path.is_file():
        json_path.unlink()
    child = ctx.run_child("monitor.py", child_args, args.timeout)
    ctx.echo_child(child)
    if not json_path.is_file():
        return child.returncode or 1, ctx.child_failure("monitor", "sweep_failed", child)
    rows = ctx.read_json(json_path, "monitor rows")

    verdict_counts: dict[str, int] = {}
    attention: list[dict[str, Any]] = []
    for row in rows:
        verdict = row.get("verdict", "OK")
        for one in verdict.split(","):
            verdict_counts[one] = verdict_counts.get(one, 0) + 1
        if verdict != "OK":
            attention.append(row)

    telegram: dict[str, Any] | None = None
    if args.telegram:
        telegram = {"sent": 0, "errors": []}
        # Plain session: same proxy, but the Facebook cookies stay off api.telegram.org.
        session = ctx.graph.plain_session()
        for row in attention:
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            payload = {
                "chat_id": tg_chat, "text": _telegram_text(row), "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            }
            try:
                resp = session.post(url, json=payload, timeout=30)
                body = resp.json()
            except Exception as exc:  # noqa: BLE001 - network/transport, redact and record
                # TG token is masked by the central graph.redact (TG_BOT_TOKEN env +
                # registered secrets) — no ad-hoc replace here so new secret kinds
                # cannot leak through this path.
                telegram["errors"].append({
                    "account": row.get("account"),
                    "error": ctx.graph.redact(str(exc)),
                })
                continue
            if body.get("ok"):
                telegram["sent"] += 1
            else:
                telegram["errors"].append({
                    "account": row.get("account"),
                    "error": ctx.graph.redact(str(body.get("description", ""))),
                })

    ok = not attention
    return (0 if ok else 1), ctx.result_envelope(
        "monitor", ok, "ok" if ok else "attention",
        artifacts={"log": str(log_path), "json": str(json_path)},
        data={
            "accounts": len(rows), "verdict_counts": verdict_counts,
            "attention": attention, "rows": rows, "telegram": telegram,
        },
        next_action=None if ok else (
            "ERROR/UNREACHABLE -> the read failed, re-run before trusting OK. DISABLED -> document+replace (03). UNSETTLED -> topup. SILENT_STOP -> check "
            "ASL/billing/review, touch nothing else. REJECTS -> new ads, never re-enable. "
            "STALL -> swap creative angle on the listed ad sets (04)."
        ),
    )


# --------------------------------------------------------------------------- comments


def command_comments(args, ctx) -> tuple[int, dict[str, Any]]:
    mode = args.comments_mode
    _, _, profile = _profile(ctx, args, "comments")
    page_id = str(profile["page_id"])
    account = ctx.graph.normalize_account(profile["ad_account_id"])

    child_args = ["--page", page_id]
    if args.ads:
        child_args += ["--ads", args.ads, "--expected-account", account]
    elif args.all:
        child_args += ["--account", account]
    else:
        raise ctx.MetaOpsError("comments requires --ads or --all")

    if mode == "list":
        child_args.append("--list")
    elif mode == "hide":
        if args.confirm != "HIDE":
            raise ctx.MetaOpsError("comments hide requires the literal --confirm HIDE")
        if args.all_comments:
            child_args.append("--hide-all")
        elif args.matching:
            child_args += ["--hide-matching", args.matching]
        else:
            raise ctx.MetaOpsError("comments hide requires --matching or --all-comments")
    else:  # delete
        if args.confirm != "DELETE":
            raise ctx.MetaOpsError("comments delete requires the literal --confirm DELETE")
        if not args.matching:
            raise ctx.MetaOpsError("comments delete requires --matching (there is no delete-all)")
        child_args += ["--delete-matching", args.matching]
    if args.dry_run:
        child_args.append("--dry-run")

    child = ctx.run_child("comments.py", child_args, args.timeout)
    ctx.echo_child(child)
    if not child.ok:
        return child.returncode, ctx.child_failure("comments", "moderation_failed", child)
    summary = _last_json_line(child.stdout)
    return 0, ctx.result_envelope(
        "comments", True, mode,
        data={"account_id": account, "page_id": page_id, "summary": summary},
        next_action=(
            None if mode == "list" else
            "Hidden comments stay visible to their author/friends; delete only for links/slurs."
        ),
    )


# --------------------------------------------------------------------------- page


def command_page(args, ctx) -> tuple[int, dict[str, Any]]:
    mode = args.page_mode

    if mode == "list-pages":
        child = ctx.run_child("page.py", ["--list-pages"], args.timeout)
        ctx.echo_child(child)
        if not child.ok:
            return child.returncode, ctx.child_failure("page", "list_failed", child)
        summary = _last_json_line(child.stdout)
        return 0, ctx.result_envelope("page", True, "listed", data={"pages": summary.get("pages", [])})

    _, _, profile = _profile(ctx, args, "page")
    page_id = str(profile["page_id"])

    if mode == "show":
        child = ctx.run_child("page.py", [page_id, "--show"], args.timeout)
        ctx.echo_child(child)
        if not child.ok:
            return child.returncode, ctx.child_failure("page", "show_failed", child)
        summary = _last_json_line(child.stdout)
        return 0, ctx.result_envelope("page", True, "shown", data={"page_id": page_id, "page": summary.get("page")})

    # mode == "set"
    if args.confirm != "PAGE":
        raise ctx.MetaOpsError("page set requires the literal --confirm PAGE")
    clear_website = getattr(args, "clear_website", False)
    remove_cover = getattr(args, "remove_cover", False)
    if not any([args.avatar, args.cover, args.about, args.website, clear_website, remove_cover]):
        raise ctx.MetaOpsError("page set requires at least one of --avatar/--cover/--about/--website/"
                               "--clear-website/--remove-cover")
    if args.website and clear_website:
        raise ctx.MetaOpsError("--website and --clear-website are exclusive")
    if args.cover and remove_cover:
        raise ctx.MetaOpsError("--cover and --remove-cover are exclusive")
    child_args = [page_id]
    if args.avatar:
        child_args += ["--avatar", str(ctx.resolve_input(args.avatar))]
    if args.cover:
        child_args += ["--cover", str(ctx.resolve_input(args.cover))]
    if args.about:
        child_args += ["--about", args.about]
    if args.website:
        child_args += ["--website", args.website]
    if clear_website:
        child_args.append("--clear-website")
    if remove_cover:
        child_args.append("--remove-cover")
    child = ctx.run_child("page.py", child_args, args.timeout)
    ctx.echo_child(child)
    if not child.ok:
        return child.returncode, ctx.child_failure("page", "set_failed", child)
    summary = _last_json_line(child.stdout)
    return 0, ctx.result_envelope("page", True, "updated", data={"page_id": page_id, "summary": summary})


# --------------------------------------------------------------------------- insights


def _pull_request(args, ctx) -> dict[str, Any]:
    """Validate the `insights pull` shaping flags locally (before any child or Graph call).
    The child re-validates with the same insights.py functions."""
    try:
        breakdowns = insights.parse_breakdowns(args.breakdown) if args.breakdown else []
        increment = (insights.parse_time_increment(args.time_increment, strict=True)
                     if args.time_increment is not None else None)
        if args.action_attribution_windows:
            if args.click_window is not None or args.view_window is not None:
                raise ValueError("--action-attribution-windows replaces --click-window/--view-window; "
                                 "give one or the other")
            windows = insights.parse_windows(args.action_attribution_windows)
        elif args.click_window is not None or args.view_window is not None:
            windows = insights.windows_from_days(args.click_window, args.view_window)
        else:
            windows = None
        extra = insights.parse_extra_fields(args.fields) if args.fields else []
    except ValueError as exc:
        raise ctx.MetaOpsError(str(exc)) from exc
    return {
        "breakdowns": breakdowns, "time_increment": increment, "windows": windows,
        "extra_fields": extra, "advisories": insights.breakdown_advisories(breakdowns),
    }


def _insights_pull(args, ctx) -> tuple[int, dict[str, Any]]:
    workspace, _, profile = _profile(ctx, args, "insights pull")
    account = ctx.graph.normalize_account(profile["ad_account_id"])
    request = _pull_request(args, ctx)
    operate_dir = _operate_dir(workspace)
    csv_path = ctx.resolve_input(args.csv) if args.csv else None
    json_path = (operate_dir / f"pull-{account}-{args.level}-{_stamp(ctx)}.json").resolve()

    child_args = ["--account", account, "--level", args.level]
    if args.since or args.until:
        if not (args.since and args.until):
            raise ctx.MetaOpsError("insights pull --since/--until must be given together")
        child_args += ["--since", args.since, "--until", args.until]
    else:
        child_args += ["--date-preset", args.date_preset or "yesterday"]
    if request["breakdowns"]:
        child_args += ["--breakdown", ",".join(request["breakdowns"])]
    if request["time_increment"] is not None:
        child_args += ["--time-increment", str(request["time_increment"])]
    if request["windows"]:
        child_args += ["--action-attribution-windows", ",".join(request["windows"])]
    if request["extra_fields"]:
        child_args += ["--fields", ",".join(request["extra_fields"])]
    if csv_path:
        child_args += ["--csv", str(csv_path)]
    child_args += ["--json", str(json_path)]

    for note in request["advisories"]:
        print(f"  ! {note}", file=sys.stderr)
    child = ctx.run_child("insights.py", child_args, args.timeout)
    ctx.echo_child(child)
    if not child.ok:
        return child.returncode, ctx.child_failure("insights", "pull_failed", child)
    summary = _last_json_line(child.stdout)
    return 0, ctx.result_envelope(
        "insights", True, "pulled",
        artifacts={"csv": str(csv_path) if csv_path else None, "json": str(json_path)},
        data={"account_id": account, "level": args.level, "summary": summary,
              "request": request},
        next_action=(
            "Breakdown rows are for reading. Do not push them as cost; join placement rows with "
            "Keitaro sub11 by hand (mapping unverified, see 16 / 25)." if request["breakdowns"] else
            "Push spend as cost into the tracker (tracker-ops/01 update_costs)."
        ),
    )


def _insights_leaderboard(args, ctx) -> tuple[int, dict[str, Any]]:
    workspace = _require_workspace(ctx, args, "insights leaderboard")
    operate_dir = _operate_dir(workspace)
    accounts = _bound_accounts(ctx, workspace, args.accounts, "insights leaderboard")
    if not accounts:
        raise ctx.MetaOpsError("insights leaderboard: no accounts resolved from --accounts")

    aggregate: dict[str, dict[str, Any]] = {}
    currencies_seen: set[str] = set()
    per_account: list[dict[str, Any]] = []
    for account in accounts:
        json_path = (operate_dir / f"lb-{account}-{_stamp(ctx)}.json").resolve()
        child_args = ["--account", account, "--level", "ad", "--date-preset", args.date_preset,
                      "--json", str(json_path)]
        child = ctx.run_child("insights.py", child_args, args.timeout)
        ctx.echo_child(child)
        if not child.ok:
            per_account.append({"account": account, "ok": False,
                                "error": (child.stderr or child.stdout)[-500:]})
            continue
        rows = ctx.read_json(json_path, "insights rows") if json_path.is_file() else []
        for row in rows:
            name = row.get("ad_name") or "?"
            currency = str(row.get("account_currency") or "UNKNOWN")
            currencies_seen.add(currency)
            bucket = aggregate.setdefault(name, {
                "ad_name": name, "spend": 0.0, "impressions": 0, "clicks": 0,
                "actions": {}, "accounts": set(), "currencies": set(),
            })
            bucket["spend"] += float(row.get("spend", 0) or 0)
            bucket["impressions"] += int(row.get("impressions", 0) or 0)
            bucket["clicks"] += int(row.get("clicks", 0) or 0)
            bucket["accounts"].add(account)
            if row.get("account_currency"):
                bucket["currencies"].add(row["account_currency"])
            for entry in row.get("actions") or []:
                atype = entry.get("action_type", "?")
                try:
                    value = float(entry.get("value", 0) or 0)
                except (TypeError, ValueError):
                    value = 0.0
                bucket["actions"][atype] = bucket["actions"].get(atype, 0.0) + value
        per_account.append({"account": account, "ok": True, "summary": _last_json_line(child.stdout)})

    if len(currencies_seen) > 1:
        return 1, ctx.result_envelope(
            "insights", False, "currency_mismatch",
            data={"accounts": per_account, "currencies": sorted(currencies_seen)},
            error={
                "kind": "currency_mismatch",
                "message": "cannot sum or rank nominal spend across different account currencies",
            },
            next_action="Run the leaderboard separately for each account currency or convert spend outside metaops.",
        )

    leaderboard = [
        {
            "ad_name": bucket["ad_name"],
            "spend": round(bucket["spend"], 2),
            "impressions": bucket["impressions"],
            "clicks": bucket["clicks"],
            "actions": {k: round(v, 2) for k, v in bucket["actions"].items()},
            "accounts": sorted(bucket["accounts"]),
            "currencies": sorted(bucket["currencies"]),
        }
        for bucket in aggregate.values()
    ]
    leaderboard.sort(key=lambda row: row["spend"], reverse=True)
    top = leaderboard[: args.top] if args.top else leaderboard

    csv_path = None
    if args.csv:
        csv_path = ctx.resolve_input(args.csv)
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ad_name", "spend", "impressions", "clicks", "accounts", "currencies"])
            for row in leaderboard:
                writer.writerow([row["ad_name"], row["spend"], row["impressions"], row["clicks"],
                                 ";".join(row["accounts"]), ";".join(row["currencies"])])

    return 0, ctx.result_envelope(
        "insights", True, "ranked",
        artifacts={"csv": str(csv_path) if csv_path else None},
        data={"accounts": per_account, "leaderboard": top, "total_ad_names": len(leaderboard)},
        next_action=(
            "ad_name follows the 03 creative-naming convention; verify a cross-account match is "
            "genuinely the same creative before comparing spend."
        ),
    )


# Creative fatigue (meta-ads/08 §10): compare each ad against its OWN baseline, several signals
# together, never a fixed frequency threshold, never auto-pause. Verdicts are notifications.
FATIGUE_MIN_IMPRESSIONS = 1000


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _half_totals(rows: list[dict[str, Any]], event: str | None) -> dict[str, float]:
    """Sum spend/impressions/clicks/results across rows. NEVER sum `reach` here — reach is
    unique users, not additive across days or ads (meta-ads/12 §5: "never sum reach across
    rows"). Ad-set saturation reach/frequency come from single-row-per-half adset pulls via
    _adset_half_totals, not from this function."""
    t = {"spend": 0.0, "impressions": 0.0, "clicks": 0.0, "results": 0.0}
    for r in rows:
        t["spend"] += _num(r.get("spend"))
        t["impressions"] += _num(r.get("impressions"))
        t["clicks"] += _num(r.get("inline_link_clicks") or r.get("clicks"))
        if event:
            for a in r.get("actions") or []:
                if a.get("action_type") == event:
                    t["results"] += _num(a.get("value"))
    t["ctr"] = t["clicks"] / t["impressions"] if t["impressions"] else 0.0
    t["cpc"] = t["spend"] / t["clicks"] if t["clicks"] else 0.0
    t["cpa"] = t["spend"] / t["results"] if t["results"] else 0.0
    return t


def _adset_half_totals(row: dict[str, Any] | None) -> dict[str, float]:
    """One adset-level row (time_increment=all_days over a single date range) → reach taken
    as-is (Graph already deduplicated it across that range) and frequency = impressions/reach
    from that same row. Never call this with more than one row per half."""
    if not row:
        return {"spend": 0.0, "impressions": 0.0, "reach": 0.0, "frequency": 0.0}
    spend = _num(row.get("spend"))
    impressions = _num(row.get("impressions"))
    reach = _num(row.get("reach"))
    return {"spend": spend, "impressions": impressions, "reach": reach,
            "frequency": impressions / reach if reach else 0.0}


def fatigue_cut(rows: list[dict[str, Any]]) -> str | None:
    """The baseline/recent boundary: first date of the recent half, taken from the days that
    actually have data. Days with no delivery are absent from insights, so a calendar midpoint
    would put the ad-level halves and the ad-set-level halves on different cuts."""
    dates = sorted({r.get("date_start") for r in rows if r.get("date_start")})
    if len(dates) < 4:
        return None
    return dates[len(dates) // 2]


def fatigue_verdicts(rows: list[dict[str, Any]], min_spend: float = 20.0,
                     event: str | None = None,
                     adset_halves: dict[str, dict[str, dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Daily ad-level insight rows → one row per ad: baseline half vs recent half.

    ROTATE-CANDIDATE: frequency +20% AND CTR -20% AND (CPC or CPA +20%) with enough recent
    volume. WATCH: two of the three, or CTR -30% alone. NO-DATA: recent spend < min_spend or
    recent impressions < 1000 (fresh objects, conversion lag). POSSIBLE-SATURATION is an ad-set
    flag: reach -20% while spend within ±15% — a differential diagnosis, not a verdict.

    `adset_halves`, when given, is {adset_id: {"baseline": row, "recent": row}} where each row
    is ONE adset-level insights row (time_increment=all_days) for that half's date range, so
    its `reach` is already deduplicated by Graph and safe to compare directly — never derived
    by summing the daily ad-level `rows` (reach is unique users, not additive). Ad-level
    frequency is also read from these rows, not from summed ad-level impressions/reach. When
    `adset_halves` is absent, no POSSIBLE-SATURATION flag and no frequency signal are computed
    (there is no correct way to get either from summed daily rows)."""
    cut = fatigue_cut(rows)
    if cut is None:
        days = len({r.get("date_start") for r in rows if r.get("date_start")})
        return [{"ad_id": None, "verdict": "NO-DATA", "reason": f"only {days} day(s) with data; need >= 4 for baseline/recent halves"}]
    by_ad: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_ad.setdefault(str(r.get("ad_id")), []).append(r)
    saturated: set[str] = set()
    adset_freq: dict[str, dict[str, float]] = {}
    if adset_halves:
        for adset_id, halves in adset_halves.items():
            b = _adset_half_totals(halves.get("baseline"))
            c = _adset_half_totals(halves.get("recent"))
            adset_freq[adset_id] = {"baseline": b["frequency"], "recent": c["frequency"]}
            if b["reach"] and b["spend"] and abs(c["spend"] - b["spend"]) <= 0.15 * b["spend"] and c["reach"] < 0.8 * b["reach"]:
                saturated.add(adset_id)
    out = []
    for ad_id, arows in by_ad.items():
        b = _half_totals([r for r in arows if r.get("date_start") < cut], event)
        c = _half_totals([r for r in arows if r.get("date_start") >= cut], event)
        adset_id = str(arows[0].get("adset_id"))
        freq = adset_freq.get(adset_id)
        if freq:
            b["frequency"], c["frequency"] = freq["baseline"], freq["recent"]
        row = {"ad_id": ad_id, "ad_name": arows[0].get("ad_name"), "adset_id": arows[0].get("adset_id"),
               "baseline": {k: round(v, 4) for k, v in b.items()}, "recent": {k: round(v, 4) for k, v in c.items()},
               "flags": ["POSSIBLE-SATURATION"] if adset_id in saturated else []}
        if c["spend"] < min_spend or c["impressions"] < FATIGUE_MIN_IMPRESSIONS or not b["impressions"]:
            row.update(verdict="NO-DATA", reason="recent half below min spend/impressions or no baseline")
            out.append(row)
            continue
        freq_up = bool(freq) and b["frequency"] and c["frequency"] > 1.2 * b["frequency"]
        ctr_down = b["ctr"] and c["ctr"] < 0.8 * b["ctr"]
        ctr_crash = b["ctr"] and c["ctr"] < 0.7 * b["ctr"]
        cost_up = (b["cpc"] and c["cpc"] > 1.2 * b["cpc"]) or (event and b["cpa"] and c["cpa"] > 1.2 * b["cpa"])
        signals = [n for n, v in (("frequency_up", freq_up), ("ctr_down", ctr_down), ("cost_up", cost_up)) if v]
        if len(signals) == 3:
            verdict = "ROTATE-CANDIDATE"
        elif len(signals) == 2 or ctr_crash:
            verdict = "WATCH"
        else:
            verdict = "OK"
        row.update(verdict=verdict, signals=signals)
        out.append(row)
    order = {"ROTATE-CANDIDATE": 0, "WATCH": 1, "OK": 2, "NO-DATA": 3}
    return sorted(out, key=lambda r: (order[r["verdict"]], -r["recent"].get("spend", 0) if "recent" in r else 0))


def _insights_fatigue(args, ctx) -> tuple[int, dict[str, Any]]:
    import datetime as dt
    workspace, _, profile = _profile(ctx, args, "insights fatigue")
    account = ctx.graph.normalize_account(profile["ad_account_id"])
    if args.days < 4 or args.days > 60:
        raise ctx.MetaOpsError("insights fatigue --days must be 4..60")
    until = dt.date.today() - dt.timedelta(days=1)
    since = until - dt.timedelta(days=args.days - 1)
    stamp = _stamp(ctx)
    json_path = (_operate_dir(workspace) / f"fatigue-{account}-{stamp}.json").resolve()
    child = ctx.run_child("insights.py", ["--account", account, "--level", "ad", "--since", since.isoformat(),
                                         "--until", until.isoformat(), "--json", str(json_path)], args.timeout)
    ctx.echo_child(child)
    if not child.ok:
        return child.returncode, ctx.child_failure("insights", "pull_failed", child)
    rows = ctx.read_json(json_path, "insights rows") if json_path.is_file() else []

    # Halves are cut on the days that actually have delivery, not on the calendar midpoint:
    # days with no impressions are absent from insights, so a calendar cut would compare the
    # ad-level CTR/CPA halves against ad-set reach halves drawn from a different period.
    cut = fatigue_cut(rows)
    if cut is None:
        return 0, ctx.result_envelope(
            "insights", True, "assessed",
            artifacts={"json": str(json_path)},
            data={"account_id": account, "since": since.isoformat(), "until": until.isoformat(),
                  "event": args.event, "counts": {"NO-DATA": 1},
                  "ads": fatigue_verdicts(rows, args.min_spend, args.event),
                  "adset_saturation_available": False},
            next_action="Not enough days with delivery for a baseline/recent split (need >= 4).",
        )
    recent_since = dt.date.fromisoformat(cut)
    baseline_until = recent_since - dt.timedelta(days=1)

    # Two ad-set-level pulls, one per half of the cut above, each time_increment=all_days — so
    # `reach` in a returned row is deduplicated by Graph over exactly that half. A single pull
    # over the whole window would collapse to one row per ad set and leave `recent` empty,
    # silently disabling frequency and saturation (meta-ads/12 §5). Per-ad CTR/CPC/CPA stay on
    # the summed daily ad rows; those fields sum fine.
    adset_halves: dict[str, dict[str, dict[str, Any]]] = {}
    adset_artifacts: dict[str, str] = {}
    adset_ok = True
    for half, (h_since, h_until) in (("baseline", (since, baseline_until)),
                                     ("recent", (recent_since, until))):
        half_json = (_operate_dir(workspace) / f"fatigue-adset-{half}-{account}-{stamp}.json").resolve()
        half_child = ctx.run_child(
            "insights.py",
            ["--account", account, "--level", "adset",
             "--since", h_since.isoformat(), "--until", h_until.isoformat(),
             "--time-increment", "all_days", "--json", str(half_json)],
            args.timeout,
        )
        ctx.echo_child(half_child)
        if not (half_child.ok and half_json.is_file()):
            adset_ok = False
            continue
        adset_artifacts[half] = str(half_json)
        for r in ctx.read_json(half_json, "adset insights rows") or []:
            adset_halves.setdefault(str(r.get("adset_id")), {})[half] = r
    # Saturation and frequency need both halves; a partial pull is not usable.
    if not adset_ok or not any(len(h) == 2 for h in adset_halves.values()):
        adset_halves = {}

    verdicts = fatigue_verdicts(rows, args.min_spend, args.event, adset_halves=adset_halves or None)
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    return 0, ctx.result_envelope(
        "insights", True, "assessed",
        artifacts={"json": str(json_path), "adset_json": adset_artifacts or None},
        data={"account_id": account, "since": since.isoformat(), "until": until.isoformat(),
              "baseline_range": [since.isoformat(), baseline_until.isoformat()],
              "recent_range": [recent_since.isoformat(), until.isoformat()],
              "event": args.event, "counts": counts, "ads": verdicts[: args.top],
              "adset_saturation_available": bool(adset_halves)},
        next_action="ROTATE-CANDIDATE → build a new creative angle, do not pause on this alone; "
                    "POSSIBLE-SATURATION → audience, not creative (meta-ads/08 §10).",
    )


def command_insights(args, ctx) -> tuple[int, dict[str, Any]]:
    if args.insights_mode == "pull":
        return _insights_pull(args, ctx)
    if args.insights_mode == "fatigue":
        return _insights_fatigue(args, ctx)
    return _insights_leaderboard(args, ctx)


# --------------------------------------------------------------------------- registration


def register(sub, ctx) -> None:
    p = sub.add_parser("review", help="ad review status + previews, or the account tree; no writes")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--state", help="launch state.json to read ad ids from")
    g.add_argument("--ids", help="comma-separated ad ids")
    g.add_argument("--all", action="store_true", help="every ad on the profile's account")
    g.add_argument("--tree", action="store_true",
                   help="campaign > ad sets > ads in one read: status, budget, bid, schedule, "
                        "learning, targeting summary, review feedback. Text is an indented tree "
                        "(money in account-currency units, `!!` marks DISAPPROVED/WITH_ISSUES/"
                        "feedback); --json keeps money in minor units. Exit 1 if any ad is "
                        "DISAPPROVED/WITH_ISSUES")
    p.add_argument("--campaign", help="--tree only: one campaign id (must belong to the profile's account)")
    p.add_argument("--statuses",
                   help="--tree only: comma list of effective_status values (default: everything "
                        "except DELETED). Shows the ads with those statuses, campaigns/ad sets that "
                        "have one themselves, and the parents of everything shown")
    p.add_argument("--previews", action="store_true")
    p.add_argument("--format", default="DESKTOP_FEED_STANDARD,MOBILE_FEED_STANDARD",
                   help="comma-separated AdPreview.AdFormat values (only with --previews)")
    p.set_defaults(handler=lambda args: command_review_entry(args, ctx))

    p = sub.add_parser("monitor", help="status+spend sweep, STALL detection, optional Telegram alerts")
    p.add_argument("--accounts", required=True, help="accounts.json (bulk.py format) or act_1,act_2")
    p.add_argument("--stall-impressions", type=int, default=40)
    p.add_argument("--telegram", action="store_true", help="TG_BOT_TOKEN + TG_CHAT_ID from env, never argv")
    p.add_argument("--log", help="default: <workspace>/survival.jsonl")
    p.add_argument("--out-json", dest="out_json",
                   help="write monitor rows here; default: a fresh file under <workspace>/.metaops/operate")
    p.set_defaults(handler=lambda args: command_monitor(args, ctx))

    p = sub.add_parser("comments", help="comment moderation on ad posts via the Page token")
    csub = p.add_subparsers(dest="comments_action", required=True)
    for name in ("list", "hide", "delete"):
        a = csub.add_parser(name)
        g = a.add_mutually_exclusive_group(required=True)
        g.add_argument("--ads", help="comma-separated ad ids")
        g.add_argument("--all", action="store_true", help="every ad on the profile's account")
        a.add_argument("--matching", help="regex, case-insensitive")
        a.add_argument("--all-comments", action="store_true",
                       help="hide only: act on every comment, not just matches")
        a.add_argument("--confirm", help="literal HIDE for hide, DELETE for delete")
        a.add_argument("--dry-run", action="store_true")
        a.set_defaults(handler=lambda args: command_comments(args, ctx), comments_mode=name)

    p = sub.add_parser("page", help="Page housekeeping writes via the Page token")
    psub = p.add_subparsers(dest="page_action", required=True)
    show = psub.add_parser("show")
    show.set_defaults(handler=lambda args: command_page(args, ctx), page_mode="show")
    lst = psub.add_parser("list-pages")
    lst.set_defaults(handler=lambda args: command_page(args, ctx), page_mode="list-pages")
    setp = psub.add_parser("set")
    setp.add_argument("--avatar", help="image file")
    setp.add_argument("--cover", help="image file")
    setp.add_argument("--about")
    setp.add_argument("--website")
    setp.add_argument("--clear-website", action="store_true", help="remove the page website")
    setp.add_argument("--remove-cover", action="store_true", help="delete the current cover photo")
    setp.add_argument("--confirm", help="must be literal PAGE")
    setp.set_defaults(handler=lambda args: command_page(args, ctx), page_mode="set")

    p = sub.add_parser("insights", help="spend/delivery pulls and cross-account creative leaderboard")
    isub = p.add_subparsers(dest="insights_action", required=True)
    pull = isub.add_parser(
        "pull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=PULL_HELP,
    )
    pull.add_argument("--level", required=True, choices=["campaign", "adset", "ad"])
    pull.add_argument("--date-preset")
    pull.add_argument("--since")
    pull.add_argument("--until")
    pull.add_argument("--breakdown",
                      help="comma list, validated locally: " + ", ".join(insights.ALLOWED_BREAKDOWNS))
    pull.add_argument("--time-increment", dest="time_increment", metavar="1|7|monthly|all_days",
                      help="rows per day (default 1), per 7 days, per month, or one row for the "
                           "whole range (all_days: use it for placement/geo reads)")
    pull.add_argument("--action-attribution-windows", dest="action_attribution_windows",
                      metavar="LIST",
                      help="e.g. 7d_click,1d_view; allowed: " + ", ".join(insights.ATTRIBUTION_WINDOWS)
                           + " (7d_view/28d_view were dropped 2026-01-12 and come back empty)")
    pull.add_argument("--click-window", dest="click_window", type=int, choices=insights.CLICK_WINDOW_DAYS,
                      help="shorthand: click days 1|7|28 (default 1); replaced by "
                           "--action-attribution-windows")
    pull.add_argument("--view-window", dest="view_window", type=int, choices=insights.VIEW_WINDOW_DAYS,
                      help="shorthand: view days, 1 only (default 1)")
    pull.add_argument("--fields", metavar="LIST",
                      help="extra columns ADDED to the default set (allow-list; "
                           "see insights.EXTRA_FIELDS)")
    pull.add_argument("--csv")
    pull.set_defaults(handler=lambda args: command_insights(args, ctx), insights_mode="pull")
    lb = isub.add_parser("leaderboard")
    lb.add_argument("--accounts", required=True)
    lb.add_argument("--date-preset", default="yesterday")
    lb.add_argument("--csv")
    lb.add_argument("--top", type=int, default=20)
    lb.set_defaults(handler=lambda args: command_insights(args, ctx), insights_mode="leaderboard")
    fat = isub.add_parser("fatigue", help="per-ad creative-fatigue verdicts vs own baseline; notifies, never pauses")
    fat.add_argument("--days", type=int, default=14,
                      help="window, split into baseline/recent halves; bounds are UTC dates "
                           "(host clock), not the ad account's reporting timezone")
    fat.add_argument("--min-spend", type=float, default=20.0, help="recent-half spend below this → NO-DATA")
    fat.add_argument("--event", help="action_type for CPA signal, e.g. offsite_conversion.fb_pixel_lead")
    fat.add_argument("--top", type=int, default=50)
    fat.set_defaults(handler=lambda args: command_insights(args, ctx), insights_mode="fatigue")
