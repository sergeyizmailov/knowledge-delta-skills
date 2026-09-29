#!/usr/bin/env python3
"""Read-only inspection commands for metaops: account tree, activity log, image library.

    metaops review --tree [--campaign ID] [--statuses A,B]       # flags live in cmd_operate.py
    metaops activity --since D [--until D] [--event-types A,B] [--limit N]
    metaops images list [--since D] [--unused] [--limit N]

`--profile` is the global metaops flag and goes BEFORE the command:
`metaops --profile P --json activity --since 2026-09-27`.

Strictly GET. This module never posts: the only Graph entry point it uses is `ctx.graph.get`
(a static test in test_inspect_features.py pins that). The ad account always comes from the
active workspace profile; `--campaign` is checked against it before anything is shown.

Field names were checked against the installed facebook_business 26.0.1 source (offline),
NOT against a live call. What is still unverified is listed in references/16.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from collections import Counter
from typing import Any

import insights

PAGE_PAUSE = 0.25  # seconds between pages of one listing; a read still costs API budget
REVIEW_BLOCKING = ("DISAPPROVED", "WITH_ISSUES")
_UTC = dt.timezone.utc


# --------------------------------------------------------------------------- shared helpers


def _warn(message: str) -> None:
    print(f"  ! {message}", file=sys.stderr)


def _account(ctx, args, label: str) -> str:
    workspace = getattr(args, "workspace_obj", None)
    if not workspace:
        raise ctx.MetaOpsError(f"{label} requires a workspace; run inside a workspace or pass --workspace")
    _, profile = workspace.profile(args.profile)
    return ctx.graph.normalize_account(profile["ad_account_id"])


def _clean(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _compact(value: Any, width: int) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return text if len(text) <= width else text[: width - 3] + "..."


def _instant(text: Any) -> dt.datetime | None:
    """Graph timestamp ('2026-09-27T13:40:52+0000', '...Z', '...+03:00') -> aware UTC datetime."""
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    match = re.match(r"^(.*[+-]\d{2})(\d{2})$", raw)
    if match:
        raw = f"{match.group(1)}:{match.group(2)}"
    try:
        value = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    return value.replace(tzinfo=_UTC) if value.tzinfo is None else value.astimezone(_UTC)


def _stamp(value: Any) -> str:
    moment = _instant(value)
    return moment.strftime("%Y-%m-%d %H:%M:%SZ") if moment else (str(value) if value else "-")


def parse_when(ctx, text: str, flag: str, end: bool = False) -> dt.datetime:
    """`YYYY-MM-DD` is a UTC day (an --until day is inclusive, so it ends at next 00:00 UTC);
    anything else must be an ISO datetime (no offset = UTC)."""
    raw = (text or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            day = dt.datetime.fromisoformat(raw).replace(tzinfo=_UTC)
        except ValueError:
            day = None
        if day is not None:
            return day + dt.timedelta(days=1) if end else day
    moment = _instant(raw)
    if moment is None:
        raise ctx.MetaOpsError(f"{flag} must be YYYY-MM-DD or an ISO datetime, got {text!r}")
    return moment


def _minor(value: Any) -> Any:
    """Graph sends money as a string of minor units; JSON keeps it minor, as an int."""
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return value


def _money(ctx, value: Any, currency: str | None) -> str:
    """Minor units -> "20.00 USD" / "300 TWD" (launch.major owns the currency offset table)."""
    if value is None:
        return "-"
    launch = getattr(ctx, "launch", None)
    if not isinstance(value, int) or not currency or launch is None:
        return f"{value} (minor units)"
    return launch.major(value, currency)


class _Reader:
    """`graph.get` with the two retries a listing may need, each at most once per command.

    * Graph code 1 "reduce the amount of data": the same request again with a smaller page
      (the caller's `build(reduced)` picks the limits; later pages stay small).
    * `fallback(exc)` for a code 100 caused by an optional request feature: the caller drops
      it and returns True to retry once without it.
    A GET, so a repeat is safe; a second failure of either kind raises."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.reduced = False
        self.warnings: list[str] = []

    def note(self, message: str) -> None:
        self.warnings.append(message)
        _warn(message)

    def get(self, path: str, build, context: str, fallback=None) -> dict[str, Any]:
        graph = self.ctx.graph
        for _ in range(3):
            try:
                return graph.get(path, params=build(self.reduced), context=context)
            except graph.GraphError as exc:
                if not self.reduced and insights.is_reduce_data_error(exc):
                    self.reduced = True
                    self.note(f"{context}: Graph asked to reduce the amount of data; "
                              "retrying once with smaller pages")
                    continue
                if fallback is not None and exc.code == 100 and fallback(exc):
                    continue
                raise
        raise AssertionError("unreachable")  # pragma: no cover



# --------------------------------------------------------------------------- review --tree

TREE_CAMPAIGN_FIELDS = (
    "id,name,status,effective_status,configured_status,daily_budget,lifetime_budget,"
    "bid_strategy,objective"
)
TREE_ADSET_FIELDS = (
    "id,name,campaign_id,status,effective_status,configured_status,daily_budget,lifetime_budget,"
    "bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,"
    "learning_stage_info,attribution_spec,targeting"
)
TREE_AD_FIELDS = (
    "id,name,adset_id,campaign_id,status,effective_status,configured_status,issues_info,"
    "ad_review_feedback,creative{id,name},updated_time"
)
# The tree is read from three FLAT edges (act_/campaigns, act_/adsets, act_/ads) and joined in
# Python on campaign_id / adset_id. A nested `adsets{ads{...}}` expansion is NOT used: live on
# CF1 (2026-09-29) it returned an empty `ads` list for 4 of 5 ad sets whose 5 ads were all ACTIVE,
# with or without an effective_status modifier, while the flat /ads edge returned all five.
# (rows per page, rows per page after Graph code 1)
TREE_PAGES = {"campaign": (100, 25), "adset": (50, 15), "ad": (100, 25)}
# Rows read per edge before the load is declared incomplete (each page is one API call).
TREE_CAPS = {"campaign": 1000, "adset": 3000, "ad": 5000}

# effective_status values per level, from the SDK 26.0.1 EffectiveStatus enums.
LEVEL_STATUSES = {
    "campaign": ("ACTIVE", "PAUSED", "IN_PROCESS", "WITH_ISSUES", "ARCHIVED", "DELETED"),
    "adset": ("ACTIVE", "PAUSED", "CAMPAIGN_PAUSED", "IN_PROCESS", "WITH_ISSUES", "ARCHIVED",
              "DELETED"),
    "ad": ("ACTIVE", "PAUSED", "ADSET_PAUSED", "CAMPAIGN_PAUSED", "PENDING_REVIEW", "PREAPPROVED",
           "PENDING_BILLING_INFO", "IN_PROCESS", "WITH_ISSUES", "DISAPPROVED", "ARCHIVED",
           "DELETED"),
}


def resolve_statuses(ctx, text: str | None) -> dict[str, Any]:
    """`--statuses` -> the effective_status list requested at each level, plus `shown`.

    No --statuses: every level asks for everything except DELETED, `shown` is None.
    With it: only the ads are filtered server-side (a list is valid at the ad level whatever
    it holds: the ad enum contains every campaign/ad-set value). Campaigns and ad sets are
    still fetched in full, because a parent that does not match must stay reachable when a
    child does (WITH_ISSUES is valid at every level, yet the DISAPPROVED ad under an ACTIVE
    campaign must not vanish). `shown` is the requested list; load_tree keeps an object when
    its own status is in it or when a shown object sits below it."""
    default = {level: [s for s in valid if s != "DELETED"] for level, valid in LEVEL_STATUSES.items()}
    if text is None:
        return {**default, "shown": None}
    requested = list(dict.fromkeys(s.strip().upper() for s in text.split(",") if s.strip()))
    if not requested:
        raise ctx.MetaOpsError("--statuses is empty")
    known = set().union(*LEVEL_STATUSES.values())
    unknown = sorted(set(requested) - known)
    if unknown:
        raise ctx.MetaOpsError(f"unknown --statuses value(s) {unknown}; known: {sorted(known)}")
    wants_deleted = "DELETED" in requested
    return {
        "campaign": LEVEL_STATUSES["campaign"] if wants_deleted else default["campaign"],
        "adset": LEVEL_STATUSES["adset"] if wants_deleted else default["adset"],
        "ad": requested,
        "shown": requested,
    }


def summarize_targeting(targeting: Any) -> dict[str, Any]:
    if not isinstance(targeting, dict):
        return {}
    geo = targeting.get("geo_locations") or {}

    def names(items: Any) -> list[Any]:
        return [i.get("name") or i.get("key") for i in items or [] if isinstance(i, dict)]

    return {
        "countries": geo.get("countries"),
        "regions": names(geo.get("regions")),
        "cities": names(geo.get("cities")),
        "location_types": geo.get("location_types"),
        "age_min": targeting.get("age_min"),
        "age_max": targeting.get("age_max"),
        "genders": targeting.get("genders"),
        "publisher_platforms": targeting.get("publisher_platforms"),
        "positions": {
            key: targeting[key]
            for key in ("facebook_positions", "instagram_positions", "messenger_positions",
                        "audience_network_positions")
            if targeting.get(key)
        },
        "device_platforms": targeting.get("device_platforms"),
        "advantage_audience": (targeting.get("targeting_automation") or {}).get("advantage_audience"),
    }


def _has_text(value: Any) -> bool:
    return bool(value) and value not in ({}, [], "")


def _text_id(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _ad_row(raw: dict[str, Any]) -> dict[str, Any]:
    creative = raw.get("creative") if isinstance(raw.get("creative"), dict) else None
    status = raw.get("effective_status")
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "status": raw.get("status"),
        "effective_status": status,
        "configured_status": raw.get("configured_status"),
        "adset_id": _text_id(raw.get("adset_id")),
        "campaign_id": _text_id(raw.get("campaign_id")),
        "issues_info": raw.get("issues_info"),
        "ad_review_feedback": raw.get("ad_review_feedback"),
        "creative": {"id": creative.get("id"), "name": creative.get("name")} if creative else None,
        "updated_time": raw.get("updated_time"),
        "flags": {
            "blocking": status in REVIEW_BLOCKING,
            "feedback": _has_text(raw.get("ad_review_feedback")),
            "issues": _has_text(raw.get("issues_info")),
        },
    }


def _attribution(spec: Any) -> list[dict[str, Any]] | None:
    """[{event_type, window_days}] as Graph returns it; None = the account default applies."""
    if not isinstance(spec, list) or not spec:
        return None
    return [{"event_type": e.get("event_type"), "window_days": e.get("window_days")}
            for e in spec if isinstance(e, dict)]


def _adset_row(raw: dict[str, Any], ads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "campaign_id": _text_id(raw.get("campaign_id")),
        "status": raw.get("status"),
        "effective_status": raw.get("effective_status"),
        "configured_status": raw.get("configured_status"),
        "daily_budget": _minor(raw.get("daily_budget")),
        "lifetime_budget": _minor(raw.get("lifetime_budget")),
        "bid_amount": _minor(raw.get("bid_amount")),
        "bid_strategy": raw.get("bid_strategy"),
        "optimization_goal": raw.get("optimization_goal"),
        "billing_event": raw.get("billing_event"),
        "start_time": raw.get("start_time"),
        "end_time": raw.get("end_time"),
        "learning_stage_info": raw.get("learning_stage_info"),
        "attribution_spec": _attribution(raw.get("attribution_spec")),
        "targeting": summarize_targeting(raw.get("targeting")),
        "ads": ads,
    }


def _campaign_row(raw: dict[str, Any], adsets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "status": raw.get("status"),
        "effective_status": raw.get("effective_status"),
        "configured_status": raw.get("configured_status"),
        "daily_budget": _minor(raw.get("daily_budget")),
        "lifetime_budget": _minor(raw.get("lifetime_budget")),
        "bid_strategy": raw.get("bid_strategy"),
        "objective": raw.get("objective"),
        "adsets": adsets,
    }


def _allowed(raw: dict[str, Any], statuses: list[str]) -> bool:
    status = raw.get("effective_status")
    return status is None or status in statuses


def load_tree(ctx, account: str, campaign_id: str | None, statuses: dict[str, Any]) -> dict[str, Any]:
    """Read the three flat edges, join them in Python, guard against what did not join.

    -> {"tree", "unattached", "loaded", "complete", "load", "warnings"}. A page that fails to
    load raises (GraphError) and the command fails: there is no partial success. A load that
    stops at its cap or on a repeated cursor is reported `complete=False`. Rows whose parent
    is not in the loaded set are never dropped: they go under `unattached`."""
    reader = _Reader(ctx)
    shown = statuses.get("shown")

    def wanted(row: dict[str, Any]) -> bool:
        return shown is None or row.get("effective_status") in shown

    def edge(level: str, path: str, fields: str) -> tuple[list[dict[str, Any]], bool]:
        page, reduced = TREE_PAGES[level]
        return _scan(ctx, reader, path,
                     lambda: {"fields": fields, "effective_status": statuses[level]},
                     page, reduced, TREE_CAPS[level], f"review tree {level}s")

    if campaign_id:
        node = reader.get(
            campaign_id, lambda _r: {"fields": f"account_id,{TREE_CAMPAIGN_FIELDS}"},
            "review tree campaign")
        actual = node.get("account_id")
        if not actual or ctx.graph.normalize_account(actual) != account:
            raise ctx.MetaOpsError(
                f"review campaign {campaign_id} belongs to {actual or '?'} not {account}; "
                "refusing cross-profile read")
        raw_campaigns, campaigns_complete = [node], True
        base = campaign_id
    else:
        raw_campaigns, campaigns_complete = edge("campaign", f"{account}/campaigns",
                                                 TREE_CAMPAIGN_FIELDS)
        base = account
    raw_adsets, adsets_complete = edge("adset", f"{base}/adsets", TREE_ADSET_FIELDS)
    raw_ads, ads_complete = edge("ad", f"{base}/ads", TREE_AD_FIELDS)

    def unique(rows: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out = []
        for row in rows:
            ident = str(row.get("id"))
            if ident in seen or not _allowed(row, statuses[level]):
                continue
            seen.add(ident)
            out.append(row)
        return out

    raw_campaigns = raw_campaigns if campaign_id else unique(raw_campaigns, "campaign")
    raw_adsets, raw_ads = unique(raw_adsets, "adset"), unique(raw_ads, "ad")

    campaigns = {str(r["id"]): _campaign_row(r, []) for r in raw_campaigns}
    adsets = {str(r["id"]): _adset_row(r, []) for r in raw_adsets}
    orphan_ads: list[dict[str, Any]] = []
    for raw in raw_ads:
        row = _ad_row(raw)
        parent = adsets.get(str(raw.get("adset_id")))
        (parent["ads"] if parent else orphan_ads).append(row)
    orphan_adsets: list[dict[str, Any]] = []
    for row in adsets.values():
        parent = campaigns.get(str(row["campaign_id"]))
        (parent["adsets"] if parent else orphan_adsets).append(row)

    def keep(row: dict[str, Any]) -> bool:
        return bool(row["ads"]) or wanted(row)

    tree = []
    for campaign in campaigns.values():
        campaign["adsets"] = [s for s in campaign["adsets"] if keep(s)]
        if campaign_id or campaign["adsets"] or wanted(campaign):
            tree.append(campaign)
    unattached = {"adsets": [s for s in orphan_adsets if keep(s)], "ads": orphan_ads}

    load = {
        "campaigns": {"rows": len(raw_campaigns), "complete": campaigns_complete},
        "adsets": {"rows": len(raw_adsets), "complete": adsets_complete},
        "ads": {"rows": len(raw_ads), "complete": ads_complete},
    }
    warnings = list(reader.warnings)
    for name, info in load.items():
        if not info["complete"]:
            warnings.append(f"{name} load stopped after {info['rows']} rows (cap or repeated "
                            "cursor): the tree is INCOMPLETE; narrow with --statuses or --campaign")
    if unattached["ads"] or unattached["adsets"]:
        warnings.append(
            f"{len(unattached['ads'])} ad(s) and {len(unattached['adsets'])} ad set(s) have a parent "
            "that is not in the loaded set (deleted, filtered out or not returned): shown under "
            "unattached")
    hollow = [s for c in tree for s in c["adsets"]
              if shown is None and s["effective_status"] == "ACTIVE" and not s["ads"]]
    if hollow:
        warnings.append(f"{len(hollow)} ACTIVE ad set(s) have no ads in the loaded ad list "
                        f"({', '.join(str(s['id']) for s in hollow[:5])}): check them in Ads Manager")
    return {
        "tree": tree, "unattached": unattached,
        "loaded": {"campaigns": len(raw_campaigns), "adsets": len(raw_adsets), "ads": len(raw_ads)},
        "complete": campaigns_complete and adsets_complete and ads_complete,
        "load": load, "warnings": warnings,
    }


def tree_summary(tree: list[dict[str, Any]], unattached: dict[str, Any]) -> dict[str, Any]:
    """Counts come from what is in `tree` + `unattached`, i.e. what was actually loaded."""
    by_status: Counter[str] = Counter()
    flagged: list[dict[str, Any]] = []
    adset_rows = [s for c in tree for s in c["adsets"]] + list(unattached["adsets"])
    ad_rows = [a for s in adset_rows for a in s["ads"]] + list(unattached["ads"])
    for ad in ad_rows:
        by_status[str(ad["effective_status"] or "?")] += 1
        if any(ad["flags"].values()):
            flagged.append({
                "id": ad["id"], "name": ad["name"], "effective_status": ad["effective_status"],
                "adset_id": ad["adset_id"], "campaign_id": ad["campaign_id"], **ad["flags"],
            })
    return {
        "counts": {"campaigns": len(tree), "adsets": len(adset_rows), "ads": len(ad_rows),
                   "unattached_adsets": len(unattached["adsets"]),
                   "unattached_ads": len(unattached["ads"])},
        "summary": dict(by_status),
        "blocking": sum(by_status.get(s, 0) for s in REVIEW_BLOCKING),
        "flagged_ads": flagged,
    }


def _status_tag(row: dict[str, Any]) -> str:
    effective = row.get("effective_status") or "?"
    configured = row.get("configured_status") or row.get("status")
    return f"{effective}" if configured in (None, effective) else f"{effective} cfg={configured}"


def _budget_text(ctx, row: dict[str, Any], currency: str | None) -> str:
    if row.get("daily_budget"):
        return f"{_money(ctx, row['daily_budget'], currency)}/day"
    if row.get("lifetime_budget"):
        return f"{_money(ctx, row['lifetime_budget'], currency)} lifetime"
    return ""


def _targeting_text(t: dict[str, Any]) -> str:
    if not t:
        return "targeting unreadable"
    geo = [*(t.get("countries") or []), *(t.get("regions") or []), *(t.get("cities") or [])]
    genders = {1: "male", 2: "female"}
    parts = [
        "geo " + (",".join(_clean(g) for g in geo) if geo else "-"),
        f"age {t.get('age_min') or '-'}-{t.get('age_max') or '-'}",
        "gender " + (",".join(genders.get(g, str(g)) for g in t["genders"]) if t.get("genders") else "all"),
        "pub " + (",".join(t["publisher_platforms"]) if t.get("publisher_platforms") else "auto"),
    ]
    positions = t.get("positions") or {}
    if positions:
        parts.append(" ".join(
            f"{key.removesuffix('_positions')}:{','.join(vals)}" for key, vals in positions.items()))
    if t.get("device_platforms"):
        parts.append("dev " + ",".join(t["device_platforms"]))
    parts.append(f"adv_aud {t.get('advantage_audience') if t.get('advantage_audience') is not None else '-'}")
    return " | ".join(parts)


def _ad_markers(ad: dict[str, Any]) -> str:
    marks = []
    if ad["effective_status"] in REVIEW_BLOCKING:
        marks.append(f"!! {ad['effective_status']}")
    if ad["flags"]["feedback"]:
        marks.append(f"!! FEEDBACK {_compact(ad['ad_review_feedback'], 140)}")
    if ad["flags"]["issues"]:
        marks.append(f"!  ISSUES {_compact(ad['issues_info'], 100)}")
    return "  " + "  ".join(marks) if marks else ""


def _adset_lines(ctx, adset: dict[str, Any], currency: str | None, indent: str,
                 filtered: bool) -> list[str]:
    bits = [_budget_text(ctx, adset, currency)]
    if adset.get("bid_amount") is not None:
        bits.append(f"bid {_money(ctx, adset['bid_amount'], currency)}")
    if adset.get("bid_strategy"):
        bits.append(adset["bid_strategy"])
    bits.append(f"{adset.get('optimization_goal') or '-'}/{adset.get('billing_event') or '-'}")
    bits.append(f"{adset.get('start_time') or '-'} -> {adset.get('end_time') or 'open'}")
    attribution = adset.get("attribution_spec")
    bits.append("attr " + (" ".join(f"{e['event_type']}:{e['window_days']}" for e in attribution)
                           if attribution else "account default"))
    learning = adset.get("learning_stage_info") or {}
    if learning.get("status"):
        conv = learning.get("conversions")
        bits.append(f"learn {learning['status']}" + (f" {conv}" if conv is not None else ""))
    bits.append(_targeting_text(adset["targeting"]))
    lines = [f"{indent}S {adset['id']} [{_status_tag(adset)}] {_clean(adset['name'])} | "
             + " | ".join(b for b in bits if b)]
    if not adset["ads"]:
        lines.append(f"{indent}  " + ("(no ads match --statuses)" if filtered else "(no ads)"))
    lines += [_ad_line(ad, indent + "  ") for ad in adset["ads"]]
    return lines


def _ad_line(ad: dict[str, Any], indent: str, note: str = "") -> str:
    creative = ad.get("creative") or {}
    return (f"{indent}A {ad['id']} [{_status_tag(ad)}] {_clean(ad['name'])} | creative "
            f"{creative.get('id') or '-'} {_clean(creative.get('name'))} | upd "
            f"{_stamp(ad.get('updated_time'))}{note}{_ad_markers(ad)}")


def render_tree(ctx, data: dict[str, Any]) -> str:
    currency = data.get("currency")
    filtered = (data.get("statuses") or {}).get("shown")
    counts, loaded = data["counts"], data["loaded"]
    by_status = ", ".join(f"{k} {v}" for k, v in sorted(data["summary"].items())) or "none"
    header = (f"{data['account_id']} ({currency or 'currency unknown'}): {counts['campaigns']} campaigns, "
              f"{counts['adsets']} ad sets, {counts['ads']} ads | ads: {by_status}")
    if counts["unattached_adsets"] or counts["unattached_ads"]:
        header += (f" | UNATTACHED {counts['unattached_adsets']} ad sets, "
                   f"{counts['unattached_ads']} ads")
    if (loaded["campaigns"], loaded["adsets"], loaded["ads"]) != (
            counts["campaigns"], counts["adsets"], counts["ads"]):
        header += (f" | loaded {loaded['campaigns']}/{loaded['adsets']}/{loaded['ads']} "
                   "campaigns/ad sets/ads, rest filtered out")
    if not data["complete"]:
        header += " | INCOMPLETE"
    if data["blocking"]:
        header += f" | BLOCKING {data['blocking']}"
    lines = [header]
    for campaign in data["tree"]:
        camp_bits = [campaign.get("objective"),
                     _budget_text(ctx, campaign, currency) or "no campaign budget (ABO)",
                     campaign.get("bid_strategy")]
        lines.append(f"C {campaign['id']} [{_status_tag(campaign)}] {_clean(campaign['name'])} | "
                     + " | ".join(_clean(b) for b in camp_bits if b))
        if not campaign["adsets"]:
            lines.append("  (no ad sets match --statuses)" if filtered else "  (no ad sets)")
        for adset in campaign["adsets"]:
            lines += _adset_lines(ctx, adset, currency, "  ", bool(filtered))
    orphans = data["unattached"]
    if orphans["adsets"] or orphans["ads"]:
        lines.append(f"U UNATTACHED: parent not in the loaded set ({len(orphans['adsets'])} ad sets, "
                     f"{len(orphans['ads'])} ads)")
        for adset in orphans["adsets"]:
            lines += _adset_lines(ctx, adset, currency, "  ", bool(filtered))
        for ad in orphans["ads"]:
            lines.append(_ad_line(ad, "  ", f" | parent adset {ad.get('adset_id') or '?'} not loaded"))
    for note in data.get("warnings") or []:
        lines.append(f"! {note}")
    return "\n".join(lines)


def command_review_tree(args, ctx) -> tuple[int, dict[str, Any]]:
    account = _account(ctx, args, "review --tree")
    campaign_id = None
    if args.campaign:
        campaign_id = str(args.campaign).strip()
        if not re.fullmatch(r"\d+", campaign_id):
            raise ctx.MetaOpsError("--campaign must be a numeric campaign id")
    statuses = resolve_statuses(ctx, args.statuses)

    currency = ctx.graph.get(account, params={"fields": "currency"},
                             context="review tree currency").get("currency")
    loaded = load_tree(ctx, account, campaign_id, statuses)
    warnings = loaded.pop("warnings")
    if currency and hasattr(ctx, "launch"):
        offset = ctx.launch.currency_offset(currency)
    else:
        offset = None
        warnings.append("account currency unknown: money is shown as raw minor units")
    stats = tree_summary(loaded["tree"], loaded["unattached"])
    data = {
        "account_id": account, "currency": currency, "currency_offset": offset,
        "campaign_id": campaign_id, "statuses": statuses, "warnings": warnings,
        **loaded, **stats,
    }
    if not getattr(args, "json", False):
        print(render_tree(ctx, data))
    counts = data["counts"]
    problems = []
    if not data["complete"]:
        problems.append("INCOMPLETE load: not every object was read")
    if data["blocking"]:
        problems.append(f"{data['blocking']} ad(s) DISAPPROVED/WITH_ISSUES")
    ok = not problems
    if ok:
        next_action = (f"No DISAPPROVED/WITH_ISSUES ad among the {counts['ads']} ad(s) loaded "
                       f"({counts['adsets']} ad sets, {counts['campaigns']} campaigns).")
    elif not data["complete"]:
        next_action = ("Not everything was loaded: an absence of rejects proves nothing. Narrow with "
                       "--statuses or --campaign and run again.")
    else:
        next_action = ("A rejected ad cannot be re-enabled (2490468); do not edit or resubmit it "
                       "(operator rule).")
    phase = "tree" if ok else ("incomplete" if not data["complete"] else "blocked")
    return (0 if ok else 1), ctx.result_envelope(
        "review", ok, phase, data=data,
        error=None if ok else {
            "kind": "incomplete" if not data["complete"] else "ad_review",
            "message": "; ".join(problems),
        },
        next_action=next_action,
    )


# --------------------------------------------------------------------------- activity

ACTIVITY_FIELDS = (
    "event_time,event_type,translated_event_type,object_id,object_name,object_type,"
    "actor_id,actor_name,extra_data,application_name"
)
ACTIVITY_PAGE = 200
ACTIVITY_PAGE_REDUCED = 50
ACTIVITY_SCAN_CAP = 5000
ACTIVITY_MAX_LIMIT = 2000
_EVENT_TYPE = re.compile(r"^[a-z0-9_]+$")


def _activity_row(raw: dict[str, Any]) -> dict[str, Any]:
    extra = raw.get("extra_data")
    if isinstance(extra, str) and extra.strip()[:1] in ("{", "["):
        try:
            extra = json.loads(extra)
        except ValueError:
            pass
    return {
        "event_time": raw.get("event_time"),
        "event_type": raw.get("event_type"),
        "translated_event_type": raw.get("translated_event_type"),
        "object_id": raw.get("object_id"),
        "object_name": raw.get("object_name"),
        "object_type": raw.get("object_type"),
        "actor_id": raw.get("actor_id"),
        "actor_name": raw.get("actor_name"),
        "application_name": raw.get("application_name"),
        "extra_data": raw.get("extra_data"),
        "extra": extra,
    }


def _actor_label(row: dict[str, Any]) -> str:
    name, ident = row.get("actor_name"), row.get("actor_id")
    if name and ident:
        return f"{name} ({ident})"
    return str(name or ident or "unknown")


def _extra_text(extra: Any) -> str:
    if isinstance(extra, dict) and ("old_value" in extra or "new_value" in extra):
        return f"{_compact(extra.get('old_value'), 60)} -> {_compact(extra.get('new_value'), 60)}"
    return _compact(extra, 90) if extra not in (None, "", {}, []) else ""


def render_activity(data: dict[str, Any]) -> str:
    lines = [
        f"{data['account_id']} activity {data['since']} .. {data['until']}: "
        f"{data['returned']} shown of {data['matched']} matched ({data['scanned']} scanned)"
    ]
    for ev in data["events"]:
        obj = f"{ev.get('object_type') or '?'} {ev.get('object_id') or '-'}"
        if ev.get("object_name"):
            obj += f" {_clean(ev['object_name'])!r}"
        via = f" via {ev['application_name']}" if ev.get("application_name") else ""
        extra = _extra_text(ev.get("extra"))
        lines.append(f"{_stamp(ev.get('event_time'))}  {ev.get('event_type')}  {obj}  by "
                     f"{_actor_label(ev)}{via}" + (f"  {extra}" if extra else ""))
    summary = data["summary"]
    for title, key in (("by event type", "by_event_type"), ("by actor", "by_actor"),
                       ("by application", "by_application")):
        if summary[key]:
            lines.append(f"{title}: " + ", ".join(f"{k} {v}" for k, v in summary[key].items()))
    for note in data["warnings"]:
        lines.append(f"! {note}")
    return "\n".join(lines)


def command_activity(args, ctx) -> tuple[int, dict[str, Any]]:
    account = _account(ctx, args, "activity")
    since = parse_when(ctx, args.since, "--since")
    now = dt.datetime.now(_UTC)
    until = parse_when(ctx, args.until, "--until", end=True) if args.until else now
    if until <= since:
        raise ctx.MetaOpsError("--until must be after --since")
    limit = args.limit if args.limit is not None else 200
    if not 1 <= limit <= ACTIVITY_MAX_LIMIT:
        raise ctx.MetaOpsError(f"--limit must be 1..{ACTIVITY_MAX_LIMIT}")
    types: list[str] = []
    if args.event_types:
        types = list(dict.fromkeys(t.strip().lower() for t in args.event_types.split(",") if t.strip()))
        bad = [t for t in types if not _EVENT_TYPE.match(t)]
        if not types or bad:
            raise ctx.MetaOpsError(f"--event-types must be comma-separated names like "
                                   f"update_ad_run_status, got {args.event_types!r}")

    reader = _Reader(ctx)
    cursor: dict[str, str | None] = {"after": None}

    def build(reduced: bool) -> dict[str, Any]:
        params: dict[str, Any] = {
            "fields": ACTIVITY_FIELDS, "since": int(since.timestamp()), "until": int(until.timestamp()),
            "limit": ACTIVITY_PAGE_REDUCED if reduced else ACTIVITY_PAGE,
        }
        if cursor["after"]:
            params["after"] = cursor["after"]
        return params

    matched: list[dict[str, Any]] = []
    fetched: Counter[str] = Counter()
    scanned = 0
    capped = False
    seen: set[str] = set()
    while True:
        page = reader.get(f"{account}/activities", build, "activity")
        for raw in page.get("data") or []:
            if not isinstance(raw, dict):
                continue
            scanned += 1
            row = _activity_row(raw)
            fetched[str(row["event_type"])] += 1
            moment = _instant(row["event_time"])
            # Graph is asked for the window, but the same bounds are enforced here: the
            # inclusive/exclusive edge of since/until is not documented in this repo.
            if moment is not None and not since <= moment < until:
                continue
            if types and row["event_type"] not in types:
                continue
            matched.append(row)
        nxt = ctx.graph.next_page_params(page, {})
        if nxt is None:
            break
        if nxt["after"] in seen or scanned >= ACTIVITY_SCAN_CAP:
            capped = True             # a repeated cursor or the cap: more exists, not loaded
            break
        seen.add(nxt["after"])
        cursor["after"] = nxt["after"]
        time.sleep(PAGE_PAUSE)

    # Newest first no matter what order Graph used: --limit must keep the newest events.
    matched.sort(key=lambda r: _instant(r["event_time"]) or dt.datetime.min.replace(tzinfo=_UTC),
                 reverse=True)
    events = matched[:limit]
    warnings = list(reader.warnings)
    if capped:
        warnings.append(f"stopped after {scanned} events (scan cap {ACTIVITY_SCAN_CAP} or a repeated "
                        "cursor): the window is incomplete, narrow --since/--until")
    if len(matched) > limit:
        warnings.append(f"{len(matched) - limit} older matching event(s) not shown; raise --limit")
    if types and not matched and scanned:
        warnings.append("no event matched --event-types (filtered client-side); event types seen in "
                        "the window: " + ", ".join(f"{k} {v}" for k, v in fetched.most_common()))
    data = {
        "account_id": account,
        "since": since.replace(microsecond=0).isoformat(),
        "until": until.replace(microsecond=0).isoformat(),
        "event_types": types or None, "limit": limit,
        "scanned": scanned, "matched": len(matched), "returned": len(events),
        "truncated": capped or len(matched) > limit,
        "summary": {
            "by_event_type": dict(Counter(str(r["event_type"]) for r in matched).most_common()),
            "by_actor": dict(Counter(_actor_label(r) for r in matched).most_common()),
            "by_application": dict(Counter(str(r["application_name"]) for r in matched
                                           if r["application_name"]).most_common()),
            "newest": matched[0]["event_time"] if matched else None,
            "oldest": matched[-1]["event_time"] if matched else None,
        },
        "events": events,
        "warnings": warnings,
    }
    if not getattr(args, "json", False):
        print(render_activity(data))
    return 0, ctx.result_envelope(
        "activity", True, "listed", data=data,
        next_action="Compare event_time (UTC) with the disable/rejection time; actor and application "
                    "show whether the change came from Ads Manager, an app or Meta itself.",
    )


# --------------------------------------------------------------------------- images

IMAGE_FIELDS = "name,hash,created_time,status,width,height,original_width,original_height"
IMAGE_ADS_FIELDS = (
    "id,name,effective_status,creative{id,name,image_hash,object_story_spec,asset_feed_spec}"
)
IMAGES_PAGE = 100
IMAGES_PAGE_REDUCED = 25
IMAGES_SCAN_CAP = 5000
ADS_PAGE = 50
ADS_PAGE_REDUCED = 15
ADS_SCAN_CAP = 5000
IMAGES_MAX_LIMIT = 2000


def creative_hashes(creative: Any) -> set[str]:
    """Every image hash a creative references: `image_hash` at any depth (link_data,
    child_attachments, photo_data, video_data thumbnail, top level) and the `hash` of each
    asset_feed_spec image. A creative built on an existing Page post carries none, so an ad
    like that can not be seen here."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image_hash" and isinstance(value, str) and value:
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if isinstance(creative, dict):
        walk(creative)
        feed = creative.get("asset_feed_spec")
        for image in (feed.get("images") if isinstance(feed, dict) else None) or []:
            if isinstance(image, dict) and isinstance(image.get("hash"), str):
                found.add(image["hash"])
    return found


def _scan(ctx, reader: _Reader, path: str, base, page: int, reduced_page: int, cap: int,
          context: str, fallback=None) -> tuple[list[dict[str, Any]], bool]:
    """Paged GET of one edge: (rows, complete). `base()` returns the fixed params and is called
    on every attempt, so a fallback can change them. Stops at `cap` rows: complete=False."""
    rows: list[dict[str, Any]] = []
    cursor: dict[str, str | None] = {"after": None}
    seen: set[str] = set()

    def build(reduced: bool) -> dict[str, Any]:
        params = {**base(), "limit": reduced_page if reduced else page}
        if cursor["after"]:
            params["after"] = cursor["after"]
        return params

    while True:
        resp = reader.get(path, build, context, fallback)
        rows.extend(r for r in resp.get("data") or [] if isinstance(r, dict))
        nxt = ctx.graph.next_page_params(resp, {})
        if nxt is None:
            return rows, True
        if nxt["after"] in seen or len(rows) >= cap:
            return rows, False        # a repeated cursor or the cap: more exists, not loaded
        seen.add(nxt["after"])
        cursor["after"] = nxt["after"]
        time.sleep(PAGE_PAUSE)


def _image_row(raw: dict[str, Any], ads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": raw.get("name"),
        "hash": raw.get("hash"),
        "created_time": raw.get("created_time"),
        "status": raw.get("status"),
        "width": raw.get("width"),
        "height": raw.get("height"),
        "original_width": raw.get("original_width"),
        "original_height": raw.get("original_height"),
        "permalink_url": raw.get("permalink_url"),
        "used": bool(ads),
        "ad_count": len(ads),
        "active_ad_count": sum(1 for a in ads if a.get("effective_status") == "ACTIVE"),
        "ads": ads,
    }


def render_images(data: dict[str, Any]) -> str:
    s = data["summary"]
    lines = [
        f"{data['account_id']} images{' since ' + data['since'] if data['since'] else ''}: "
        f"{s['images']} in scope, {s['used']} used, {s['unused']} unused | ads scanned "
        f"{s['ads_scanned']} ({'complete' if s['ads_scan_complete'] else 'INCOMPLETE'})"
    ]
    for image in data["images"]:
        size = f"{image.get('width') or '?'}x{image.get('height') or '?'}"
        if (image.get("original_width"), image.get("original_height")) != (image.get("width"), image.get("height")) \
                and image.get("original_width"):
            size += f" (orig {image['original_width']}x{image['original_height']})"
        if image["used"]:
            shown = ", ".join(f"{a['id']} {a.get('effective_status')}" for a in image["ads"][:3])
            more = f" +{image['ad_count'] - 3}" if image["ad_count"] > 3 else ""
            use = f"ads {image['active_ad_count']}/{image['ad_count']}: {shown}{more}"
        else:
            use = "UNUSED"
        link = f"  {image['permalink_url']}" if image.get("permalink_url") else ""
        lines.append(f"{image['hash']}  {_stamp(image.get('created_time'))}  {size}  "
                     f"{_clean(image.get('name'))}  {use}{link}")
    for note in data["warnings"]:
        lines.append(f"! {note}")
    return "\n".join(lines)


def command_images_list(args, ctx) -> tuple[int, dict[str, Any]]:
    account = _account(ctx, args, "images list")
    since = parse_when(ctx, args.since, "--since") if args.since else None
    limit = args.limit if args.limit is not None else 100
    if not 1 <= limit <= IMAGES_MAX_LIMIT:
        raise ctx.MetaOpsError(f"--limit must be 1..{IMAGES_MAX_LIMIT}")

    reader = _Reader(ctx)
    fields = {"permalink_url": True}

    def drop_permalink(exc: Exception) -> bool:
        if not fields["permalink_url"] or "permalink_url" not in str(getattr(exc, "message", "")):
            return False
        fields["permalink_url"] = False
        reader.note("adimages rejected permalink_url; listing without it")
        return True

    def image_params() -> dict[str, Any]:
        return {"fields": IMAGE_FIELDS + (",permalink_url" if fields["permalink_url"] else "")}

    image_rows, images_complete = _scan(
        ctx, reader, f"{account}/adimages", image_params, IMAGES_PAGE, IMAGES_PAGE_REDUCED,
        IMAGES_SCAN_CAP, "images adimages", drop_permalink)
    ad_rows, ads_complete = _scan(
        ctx, reader, f"{account}/ads",
        lambda: {"fields": IMAGE_ADS_FIELDS,
                 "effective_status": [s for s in LEVEL_STATUSES["ad"] if s != "DELETED"]},
        ADS_PAGE, ADS_PAGE_REDUCED, ADS_SCAN_CAP, "images ads")

    users: dict[str, dict[str, dict[str, Any]]] = {}
    for ad in ad_rows:
        for image_hash in creative_hashes(ad.get("creative")):
            users.setdefault(image_hash, {})[str(ad.get("id"))] = {
                "id": ad.get("id"), "name": ad.get("name"),
                "effective_status": ad.get("effective_status"),
            }

    library = {str(r.get("hash")) for r in image_rows if r.get("hash")}
    scoped = [
        r for r in image_rows
        if r.get("hash") and (since is None or (_instant(r.get("created_time")) or since) >= since)
    ]
    scoped.sort(key=lambda r: _instant(r.get("created_time")) or dt.datetime.min.replace(tzinfo=_UTC),
                reverse=True)
    rows = [_image_row(r, list(users.get(str(r["hash"]), {}).values())) for r in scoped]
    used = sum(1 for r in rows if r["used"])
    listed = [r for r in rows if not r["used"]] if args.unused else rows

    warnings = list(reader.warnings)
    if not images_complete:
        warnings.append(f"image scan stopped at {len(image_rows)} (cap {IMAGES_SCAN_CAP}): list incomplete")
    if not ads_complete:
        warnings.append(f"ad scan stopped at {len(ad_rows)} (cap {ADS_SCAN_CAP}): an image shown as "
                        "UNUSED may be used by an ad that was not scanned")
    warnings.append("UNUSED = no scanned ad creative references the hash; ads built on an existing Page "
                    "post (object_story_id) carry no hash and are invisible here, and DELETED ads are "
                    "not scanned. Not proof that deleting is safe.")
    if not fields["permalink_url"]:
        warnings.append("permalink_url unavailable on this edge; column omitted")
    data = {
        "account_id": account, "since": since.isoformat() if since else None,
        "unused_only": bool(args.unused), "limit": limit,
        "summary": {
            "images": len(rows), "used": used, "unused": len(rows) - used,
            "referenced_not_in_library": len(set(users) - library),
            "ads_scanned": len(ad_rows), "ads_scan_complete": ads_complete,
            "images_scan_complete": images_complete,
        },
        "returned": min(len(listed), limit),
        "images": listed[:limit],
        "warnings": warnings,
    }
    if not getattr(args, "json", False):
        print(render_images(data))
    return 0, ctx.result_envelope(
        "images", True, "listed", data=data,
        next_action="Read-only. Image hashes belong to one ad account; UNUSED is not proof that "
                    "deleting or reusing an image is safe.",
    )


# --------------------------------------------------------------------------- registration


def register(sub, ctx) -> None:
    p = sub.add_parser(
        "activity",
        help="account activity log: who changed what, newest first (read-only)",
        description=(
            "Reads act_<id>/activities for the profile's account. Times are UTC: YYYY-MM-DD is a UTC "
            "day (--until day inclusive). Event types are filtered client-side (the edge has no "
            "event_type filter). The profile is the global flag: metaops --profile P activity ..."
        ),
    )
    p.add_argument("--since", required=True, help="YYYY-MM-DD or ISO datetime (UTC)")
    p.add_argument("--until", help="YYYY-MM-DD or ISO datetime (UTC); default now")
    p.add_argument("--event-types", dest="event_types",
                   help="comma list, e.g. update_ad_run_status,ad_account_update_status")
    p.add_argument("--limit", type=int, default=200,
                   help=f"max events shown, newest first (default 200, max {ACTIVITY_MAX_LIMIT})")
    p.set_defaults(handler=lambda args: command_activity(args, ctx))

    p = sub.add_parser("images", help="ad image library and which ads use each hash (read-only)")
    isub = p.add_subparsers(dest="images_action", required=True)
    lst = isub.add_parser(
        "list",
        help="images of the profile's account joined to the ads that use them",
        description=(
            "act_<id>/adimages joined to act_<id>/ads via creative image hashes. Costs about "
            "ceil(ads/50) + ceil(images/100) GETs, so run it rarely on big accounts. Named `images` "
            "because `metaops media` is the upload command."
        ),
    )
    lst.add_argument("--since", help="only images created on/after this date (YYYY-MM-DD or ISO, UTC)")
    lst.add_argument("--unused", action="store_true", help="only hashes no scanned ad references")
    lst.add_argument("--limit", type=int, default=100,
                     help=f"max images shown, newest first (default 100, max {IMAGES_MAX_LIMIT})")
    lst.set_defaults(handler=lambda args: command_images_list(args, ctx))
