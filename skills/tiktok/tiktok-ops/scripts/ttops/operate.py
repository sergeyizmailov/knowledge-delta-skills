"""Day-2 operations: reporting, budget/status edits, delivery sweep.

Reporting note that governs every number here: TikTok reports in the **ad
account's own timezone**, and the attribution window is fixed at ad-group
creation. Two accounts in one portfolio can therefore disagree about what
"yesterday" means. Always state the timezone alongside a daily number.
"""

from __future__ import annotations

import datetime as _dt

try:                                    # stdlib from 3.9
    from zoneinfo import ZoneInfo
except ImportError:                     # pragma: no cover
    ZoneInfo = None

from . import money
from .api import TikTokError
from .errors import explain_status

# Metrics that are safe to request at every data level and are what a buyer
# actually decides on. Ask for more only when a question needs them: a wide
# metric list is a common source of invalid-combination errors.
CORE_METRICS = [
    "spend", "impressions", "clicks", "ctr", "cpc", "cpm",
    "conversion", "cost_per_conversion", "conversion_rate",
    "result", "cost_per_result",
]
VIDEO_METRICS = [
    "video_play_actions", "video_watched_2s", "video_watched_6s",
    "average_video_play", "video_views_p25", "video_views_p50",
    "video_views_p75", "video_views_p100",
]
VALUE_METRICS = ["total_purchase_value", "value_per_purchase", "total_complete_payment_rate"]

DATA_LEVELS = {
    "campaign": ("AUCTION_CAMPAIGN", "campaign_id"),
    "adgroup": ("AUCTION_ADGROUP", "adgroup_id"),
    "ad": ("AUCTION_AD", "ad_id"),
    "advertiser": ("AUCTION_ADVERTISER", "advertiser_id"),
}


def account_today(profile):
    """Today in the AD ACCOUNT's timezone, not the machine's.

    A buyer in Berlin pulling "yesterday" for a Los Angeles account gets a
    different day than the account did, and the numbers will not match Ads
    Manager. Falls back to the machine date only if the timezone is unresolvable,
    and that case is reported rather than hidden.
    """
    name = (profile or {}).get("timezone")
    if name and ZoneInfo is not None:
        try:
            return _dt.datetime.now(ZoneInfo(name)).date(), name
        except Exception:               # noqa: BLE001 — unknown tz name
            pass
    return _dt.date.today(), None


def report(client, profile, *, level="ad", start=None, end=None, days=1,
           metrics=None, extra_metrics=None, filters=None, page_size=200):
    """Synchronous integrated report. For big pulls use the async task endpoints."""
    if level not in DATA_LEVELS:
        raise ValueError(f"level must be one of {sorted(DATA_LEVELS)}")
    data_level, dimension = DATA_LEVELS[level]

    tz_warning = None
    if not start or not end:
        today, resolved = account_today(profile)
        if resolved is None:
            tz_warning = (
                f"Could not resolve the account timezone {profile.get('timezone')!r}; "
                "the date window was computed from this machine's clock and may be off "
                "by a day. Pass --start/--end explicitly."
            )
        end_d = today - _dt.timedelta(days=1)
        start_d = end_d - _dt.timedelta(days=max(days, 1) - 1)
        start, end = start_d.isoformat(), end_d.isoformat()

    wanted = list(metrics or CORE_METRICS)
    for extra in (extra_metrics or []):
        if extra not in wanted:
            wanted.append(extra)

    params = {
        "advertiser_id": profile["advertiser_id"],
        "report_type": "BASIC",
        "data_level": data_level,
        "dimensions": [dimension],
        "metrics": wanted,
        "start_date": start,
        "end_date": end,
        "page_size": page_size,
    }
    if filters:
        params["filtering"] = filters

    rows = []
    try:
        # Paginated: an ad-level report on a real account runs past one page, and a
        # silently truncated report is worse than no report.
        rows = list(client.paged("/report/integrated/get/", params, page_size=page_size))
    except TikTokError as exc:
        if exc.code == 40002:
            raise TikTokError(
                exc.code,
                f"{exc.message} — a metric/dimension combination was rejected. Retry with "
                f"just CORE_METRICS at this data_level before adding video or value metrics.",
                exc.request_id, exc.path,
            ) from exc
        raise

    flat = []
    for row in rows:
        item = dict(row.get("dimensions") or {})
        item.update(row.get("metrics") or {})
        flat.append(item)

    return {
        "ok": True,
        "level": level,
        "start_date": start,
        "end_date": end,
        "timezone": profile["timezone"],
        "currency": profile["currency"],
        "rows": flat,
        "note": f"Dates and spend are in the AD ACCOUNT timezone ({profile['timezone']}) "
                f"and currency ({profile['currency']}). Reconcile against the tracker on "
                "click date before drawing a conclusion.",
        **({"warning": tz_warning} if tz_warning else {}),
    }


def spend_to_date(client, profile, object_id, level):
    """Lifetime spend for one object — needed for the 105%-of-spend budget floor."""
    data_level, dimension = DATA_LEVELS[level]
    id_field = {"campaign": "campaign_ids", "adgroup": "adgroup_ids", "ad": "ad_ids"}[level]
    today, _tz = account_today(profile)
    data = client.get("/report/integrated/get/", {
        "advertiser_id": profile["advertiser_id"],
        "report_type": "BASIC",
        "data_level": data_level,
        "dimensions": [dimension],
        "metrics": ["spend"],
        # TikTok's sync report caps the range; 365 days is enough for a budget floor.
        "start_date": (today - _dt.timedelta(days=365)).isoformat(),
        "end_date": today.isoformat(),
        "filtering": {id_field: [str(object_id)]},
        "page_size": 10,
    })
    total = 0.0
    for row in data.get("list", []):
        total += float((row.get("metrics") or {}).get("spend") or 0)
    return total


def set_status(client, profile, *, level, ids, status, confirm):
    """ENABLE/DISABLE/DELETE a batch. ENABLE spends, so it needs --confirm SPEND."""
    if status not in ("ENABLE", "DISABLE", "DELETE"):
        raise ValueError("status must be ENABLE, DISABLE or DELETE")
    needed = {"ENABLE": "SPEND", "DISABLE": "PAUSE", "DELETE": "DELETE"}[status]
    if confirm != needed:
        raise RuntimeError(f"{status} requires --confirm {needed}")
    if len(ids) > 20:
        raise ValueError("TikTok accepts at most 20 IDs per status update; batch smaller")

    path = {"campaign": "/campaign/status/update/",
            "adgroup": "/adgroup/status/update/",
            "ad": "/ad/status/update/"}[level]
    field = {"campaign": "campaign_ids", "adgroup": "adgroup_ids", "ad": "ad_ids"}[level]
    body = {"advertiser_id": profile["advertiser_id"], field: list(ids),
            "operation_status": status}
    client.post(path, body)
    return {"ok": True, "level": level, "ids": list(ids), "status": status}


def set_budget(client, profile, *, level, object_id, budget, confirm, store_product_source=False):
    """Change a budget, with the 105%-of-spend floor checked before the write."""
    if confirm != "SPEND":
        raise RuntimeError("Budget changes require --confirm SPEND")
    currency = profile["currency"]
    spent = spend_to_date(client, profile, object_id, level)
    value = money.check_update(budget, spent, currency, level,
                               store_product_source=store_product_source)

    if level == "adgroup":
        client.post("/adgroup/budget/update/", {
            "advertiser_id": profile["advertiser_id"],
            "adgroup_id": str(object_id),
            "budget": float(value),
        })
    elif level == "campaign":
        client.post("/campaign/update/", {
            "advertiser_id": profile["advertiser_id"],
            "campaign_id": str(object_id),
            "budget": float(value),
        })
    else:
        raise ValueError("budget can be set at campaign or adgroup level only")

    return {"ok": True, "level": level, "id": str(object_id),
            "budget": money.describe(value, currency),
            "spend_to_date": money.describe(spent, currency),
            "floor_applied": money.describe(money.min_increase_floor(spent, currency), currency)}


def sweep(client, profile, *, stall_impressions=50):
    """Delivery sweep: what is live, what is stalled, what is rejected.

    STALL = impressions accrued with zero clicks. On TikTok this usually means the
    creative is being served and ignored, not that delivery is broken.
    """
    advertiser_id = profile["advertiser_id"]
    ads = list(client.paged("/ad/get/", {
        "advertiser_id": advertiser_id,
        "filtering": {"primary_status": "STATUS_NOT_DELETE"},
    }, page_size=1000))

    by_id = {str(a.get("ad_id")): a for a in ads}
    perf = report(client, profile, level="ad", days=1)
    rows = {str(r.get("ad_id")): r for r in perf["rows"]}

    findings = []
    for ad_id, ad in by_id.items():
        row = rows.get(ad_id, {})
        impressions = float(row.get("impressions") or 0)
        clicks = float(row.get("clicks") or 0)
        spend = float(row.get("spend") or 0)
        secondary = ad.get("secondary_status") or ad.get("status")
        flags = []
        if secondary:
            # Never substring-match these: AD_STATUS_AUDIT_DENY contains "AUDIT" and
            # does not contain "REJECT", so naive matching calls a rejection a
            # pending review and you wait for delivery that is never coming.
            info = explain_status(secondary)
            if info["severity"] == "BLOCKED":
                flags.append("REJECTED" if "DENY" in str(secondary).upper() else "BLOCKED")
            elif info["severity"] == "REVIEW":
                flags.append("IN_REVIEW")
            elif info["severity"] == "MONEY":
                flags.append("BALANCE")
        if impressions >= stall_impressions and clicks == 0:
            flags.append("STALL")
        if ad.get("operation_status") == "ENABLE" and impressions == 0 and spend == 0:
            flags.append("NO_DELIVERY")
        if flags:
            findings.append({
                "ad_id": ad_id, "ad_name": ad.get("ad_name"),
                "adgroup_id": ad.get("adgroup_id"),
                "operation_status": ad.get("operation_status"),
                "secondary_status": secondary,
                "impressions": impressions, "clicks": clicks,
                "spend": money.describe(spend, profile["currency"]),
                "flags": flags,
            })

    return {"ok": True, "window": f"{perf['start_date']}..{perf['end_date']}",
            "timezone": profile["timezone"],
            "ads_checked": len(by_id), "findings": findings,
            "note": "NO_DELIVERY on a freshly activated ad is normal for 15-40 minutes. "
                    "Persisting: check review status, billing balance, schedule start time, "
                    "and whether the ad group's audience is too narrow."}


def review_status(client, profile, *, ad_ids=None):
    """Rejection reasons. A rejected ad cannot be fixed into life — build a new one."""
    params = {"advertiser_id": profile["advertiser_id"]}
    if ad_ids:
        params["ad_ids"] = list(ad_ids)
    data = client.get("/ad/review_info/", params)
    return {"ok": True, "review": data.get("list", data)}
